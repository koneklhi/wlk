import logging
import os
from typing import List

import numpy as np
import torch
import torch.nn.functional as F

from whisperlivekit.backend_support import faster_backend_available, mlx_backend_available
from whisperlivekit.whisper.audio import N_FRAMES, N_SAMPLES, TOKENS_PER_SECOND, log_mel_spectrogram, pad_or_trim
from whisperlivekit.whisper.decoding import BeamSearchDecoder, GreedyDecoder, SuppressTokens
from whisperlivekit.whisper.timing import median_filter

from .align_att_base import DEC_PAD, AlignAttBase
from .beam import BeamPyTorchInference
from .config import AlignAttConfig
from .decoder_state import DecoderState
from .eow_detection import fire_at_boundary, load_cif
from .token_buffer import TokenBuffer

logger = logging.getLogger(__name__)

if mlx_backend_available():
    from mlx_whisper.audio import log_mel_spectrogram as mlx_log_mel_spectrogram
    from mlx_whisper.transcribe import pad_or_trim as mlx_pad_or_trim

if faster_backend_available():
    from faster_whisper.audio import pad_or_trim as fw_pad_or_trim
    from faster_whisper.feature_extractor import FeatureExtractor

USE_MLCORE = False


def load_coreml_encoder():
    try:
        from coremltools.models import MLModel
    except ImportError:
        logger.warning("coremltools is not installed")
        return None
    COREML_ENCODER_PATH = os.environ.get(
        "MLCORE_ENCODER_PATH",
        "whisperlivekit/whisper/whisper_encoder.mlpackage",
    )
    _coreml_encoder = MLModel(COREML_ENCODER_PATH)
    spec = _coreml_encoder.get_spec()
    _coreml_input_name = spec.description.input[0].name if spec.description.input else "mel"
    _coreml_output_name = spec.description.output[0].name if spec.description.output else None
    return _coreml_encoder, _coreml_input_name, _coreml_output_name


class AlignAtt(AlignAttBase):
    """
    PyTorch Alignment-based Attention decoder for SimulStreaming.

    Hookless — the model can be shared across multiple sessions,
    with each session maintaining its own DecoderState.
    """

    def __init__(
        self,
        cfg: AlignAttConfig,
        loaded_model=None,
        mlx_encoder=None,
        fw_encoder=None,
    ) -> None:
        self.mlx_encoder = mlx_encoder
        self.fw_encoder = fw_encoder
        if fw_encoder:
            self.fw_feature_extractor = FeatureExtractor(
                feature_size=loaded_model.dims.n_mels,
            )
        self.coreml_encoder_tuple = None
        if USE_MLCORE:
            self.coreml_encoder_tuple = load_coreml_encoder()
        self.use_mlcore = self.coreml_encoder_tuple is not None
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'

        # Common init (sets self.model, self.cfg, decode_options, etc.)
        self._base_init(cfg, loaded_model)
        logger.info(f"Model dimensions: {self.model.dims}")

        # Per-session state
        self.state = DecoderState()
        self._init_state(cfg)

    def _init_state(self, cfg: AlignAttConfig):
        self._init_state_common(cfg)

        # CIF helpers for end-of-word boundary detection
        self.state.CIFLinear, self.state.always_fire, self.state.never_fire = load_cif(
            cfg, n_audio_state=self.model.dims.n_audio_state, device=self.model.device,
        )

        # Build alignment source mapping
        self.state.align_source = {}
        self.state.num_align_heads = 0
        for layer_rank, head_id in self.model.alignment_heads.indices().T:
            layer_rank = layer_rank.item()
            heads = self.state.align_source.get(layer_rank, [])
            heads.append((self.state.num_align_heads, head_id.item()))
            self.state.align_source[layer_rank] = heads
            self.state.num_align_heads += 1

        # Build suppress tokens function
        suppress_tokens = [
            self.tokenizer.transcribe, self.tokenizer.translate,
            self.tokenizer.sot, self.tokenizer.sot_prev,
            self.tokenizer.sot_lm, self.tokenizer.no_timestamps,
        ] + list(self.tokenizer.all_language_tokens)
        if self.tokenizer.no_speech is not None:
            suppress_tokens.append(self.tokenizer.no_speech)
        suppress_tokens = tuple(sorted(set(suppress_tokens)))
        logger.debug(f"Suppress tokens: {suppress_tokens}")
        sup_tokens = SuppressTokens(suppress_tokens)
        self.state.suppress_tokens_fn = lambda logits: sup_tokens.apply(logits, None)

        self.init_tokens()
        self.init_context()

        # Decoder type
        self.state.decoder_type = cfg.decoder_type
        if cfg.decoder_type == "greedy":
            logger.info("Using greedy decoder")
            self.state.token_decoder = GreedyDecoder(0.0, self.tokenizer.eot)
        elif cfg.decoder_type == "beam":
            logger.info("Using beam decoder")
            self.state.inference = BeamPyTorchInference(
                self.model, self.state.initial_token_length,
            )
            self.state.inference.kv_cache = self.state.kv_cache
            self.state.token_decoder = BeamSearchDecoder(
                inference=self.state.inference,
                eot=self.tokenizer.eot,
                beam_size=cfg.beam_size,
            )

    # === Abstract method implementations ===

    def init_tokens(self):
        logger.debug(f"init tokens, {len(self.state.segments)}")
        self.state.initial_tokens = torch.tensor(
            self.tokenizer.sot_sequence_including_notimestamps,
            dtype=torch.long, device=self.model.device,
        ).unsqueeze(0)
        self.state.initial_token_length = self.state.initial_tokens.shape[1]
        self.state.sot_index = self.tokenizer.sot_sequence.index(self.tokenizer.sot)
        logger.debug(f"init tokens after, {len(self.state.segments)}")
        self.state.tokens = [self.state.initial_tokens]

    def init_context(self):
        kw = {
            'tokenizer': self.tokenizer,
            'device': self.model.device,
            'prefix_token_ids': [self.tokenizer.sot_prev],
        }
        self.state.context = TokenBuffer.empty(**kw)
        if self.cfg.static_init_prompt is not None:
            self.state.context = TokenBuffer.from_text(self.cfg.static_init_prompt, **kw)
        if self.cfg.init_prompt is not None:
            self.state.context.text += self.cfg.init_prompt

    def insert_audio(self, segment=None):
        if segment is not None:
            self.state.segments.append(segment)
        removed_len = 0
        segments_len = self.segments_len()
        while len(self.state.segments) > 1 and segments_len > self.cfg.audio_max_len:
            removed_len = self.state.segments[0].shape[0] / 16000
            segments_len -= removed_len
            self.state.last_attend_frame -= int(TOKENS_PER_SECOND * removed_len)
            self.state.cumulative_time_offset += removed_len
            self.state.segments = self.state.segments[1:]
            logger.debug(
                f"remove segments: {len(self.state.segments)} {len(self.state.tokens)}, "
                f"cumulative offset: {self.state.cumulative_time_offset:.2f}s"
            )
            if len(self.state.tokens) > 1:
                self.state.context.append_token_ids(self.state.tokens[1][0, :].tolist())
                self.state.tokens = [self.state.initial_tokens] + self.state.tokens[2:]
        return removed_len

    def _current_tokens(self):
        toks = self.state.tokens
        if toks[0].shape[0] == 1:
            toks[0] = toks[0].repeat_interleave(self.cfg.beam_size, dim=0)
        if not self.state.context.is_empty():
            context_toks = self.state.context.as_tensor_beam(
                self.cfg.beam_size, device=self.model.device,
            )
            toks = [context_toks] + toks
        if len(toks) > 1:
            current_tokens = torch.cat(toks, dim=1)
        else:
            current_tokens = toks[0]
        logger.debug("debug print current_tokens:")
        self.debug_print_tokens(current_tokens)
        return current_tokens

    def fire_at_boundary(self, chunked_encoder_feature: torch.Tensor):
        if self.state.always_fire:
            return True
        if self.state.never_fire:
            return False
        return fire_at_boundary(chunked_encoder_feature, self.state.CIFLinear)

    def _lang_candidate_token_ids(self) -> List[int]:
        """언어 감지 후보 토큰 id 목록 — cfg.lang_restrict_koen 반영.

        lang_id()의 마스크 구성과 SOT 프로브(_read_sot_posteriors)의 재정규화가
        **동일 규칙**을 쓰도록 한 곳에서 만든다(중복 구현 방지).

        배포 환경 불변식: lang_restrict_koen이면 감지 후보를 {ko, en}로 제한.
        매 디코드 스텝 마스킹(Exp-136, 기각)과 달리 감지 단계만 제한하므로
        코드스위칭·영어 전사 모두 보존된다.
        """
        if getattr(self.cfg, 'lang_restrict_koen', False):
            allowed = {"ko", "en"}
            return [
                tok for tok, code in zip(
                    self.tokenizer.all_language_tokens,
                    self.tokenizer.all_language_codes,
                )
                if code in allowed
            ]
        return list(self.tokenizer.all_language_tokens)

    @torch.no_grad()
    def lang_id(self, encoder_features):
        n_audio = encoder_features.shape[0]
        x = torch.tensor([[self.tokenizer.sot]] * n_audio).to(self.model.device)
        logits = self.model.logits(x, encoder_features)[:, 0]

        mask = torch.ones(logits.shape[-1], dtype=torch.bool)
        mask[self._lang_candidate_token_ids()] = False
        logits[:, mask] = -np.inf
        language_tokens = logits.argmax(dim=-1)
        language_token_probs = logits.softmax(dim=-1).cpu()
        language_probs = [
            {
                c: language_token_probs[i, j].item()
                for j, c in zip(
                    self.tokenizer.all_language_tokens,
                    self.tokenizer.all_language_codes,
                )
            }
            for i in range(n_audio)
        ]
        single = encoder_features.ndim == 2
        if single:
            language_tokens = language_tokens[0]
            language_probs = language_probs[0]
        self._clean_cache()
        return language_tokens, language_probs

    def _concat_segments(self):
        if len(self.state.segments) > 1:
            return torch.cat(self.state.segments, dim=0)
        return self.state.segments[0]

    def _encode(self, input_segments):
        if self.use_mlcore:
            coreml_encoder, coreml_input_name, coreml_output_name = self.coreml_encoder_tuple
            mel_padded = log_mel_spectrogram(
                input_segments, n_mels=self.model.dims.n_mels,
                padding=N_SAMPLES, device="cpu",
            ).unsqueeze(0)
            mel = pad_or_trim(mel_padded, N_FRAMES)
            content_mel_len = int((mel_padded.shape[2] - mel.shape[2]) / 2)
            mel_np = np.ascontiguousarray(mel.numpy())
            ml_inputs = {coreml_input_name or "mel": mel_np}
            coreml_outputs = coreml_encoder.predict(ml_inputs)
            if coreml_output_name and coreml_output_name in coreml_outputs:
                encoder_feature_np = coreml_outputs[coreml_output_name]
            else:
                encoder_feature_np = next(iter(coreml_outputs.values()))
            encoder_feature = torch.as_tensor(
                np.array(encoder_feature_np), device=self.device,
            )
        if self.mlx_encoder:
            mlx_mel_padded = mlx_log_mel_spectrogram(
                audio=input_segments.detach(),
                n_mels=self.model.dims.n_mels, padding=N_SAMPLES,
            )
            mlx_mel = mlx_pad_or_trim(mlx_mel_padded, N_FRAMES, axis=-2)
            mlx_encoder_feature = self.mlx_encoder.encoder(mlx_mel[None])
            encoder_feature = torch.as_tensor(mlx_encoder_feature)
            content_mel_len = int((mlx_mel_padded.shape[0] - mlx_mel.shape[0]) / 2)
        elif self.fw_encoder:
            audio_length_seconds = len(input_segments) / 16000
            content_mel_len = int(audio_length_seconds * 100) // 2
            mel_padded_2 = self.fw_feature_extractor(
                waveform=input_segments.numpy(), padding=N_SAMPLES,
            )[None, :]
            mel = fw_pad_or_trim(mel_padded_2, N_FRAMES, axis=-1)
            encoder_feature_ctranslate = self.fw_encoder.encode(mel)
            if self.device == 'cpu':
                encoder_feature_ctranslate = np.array(encoder_feature_ctranslate)
            try:
                encoder_feature = torch.as_tensor(encoder_feature_ctranslate, device=self.device)
            except TypeError:
                try:
                    arr = np.asarray(encoder_feature_ctranslate, dtype=np.float32)
                except (TypeError, ValueError):
                    arr = np.array(encoder_feature_ctranslate)
                    if arr.dtype == np.object_:
                        try:
                            arr = np.stack([
                                np.asarray(item, dtype=np.float32) for item in arr.flat
                            ])
                        except (TypeError, ValueError):
                            arr = np.array(
                                [[float(x) for x in row] for row in arr.flat],
                                dtype=np.float32,
                            )
                encoder_feature = torch.as_tensor(arr, device=self.device)
        else:
            mel_padded = log_mel_spectrogram(
                input_segments, n_mels=self.model.dims.n_mels,
                padding=N_SAMPLES, device=self.device,
            ).unsqueeze(0)
            mel = pad_or_trim(mel_padded, N_FRAMES)
            content_mel_len = int((mel_padded.shape[2] - mel.shape[2]) / 2)
            encoder_feature = self.model.encoder(mel)
        return encoder_feature, content_mel_len

    def _init_sum_logprobs(self):
        return torch.zeros(self.cfg.beam_size, device=self.device)

    def _sum_logprobs_value(self, sum_logprobs):
        return float(sum_logprobs[0].item())

    def _get_logits_and_cross_attn(self, tokens, encoder_feature):
        if self.state.decoder_type == "greedy":
            return self.model.decoder(
                tokens, encoder_feature,
                kv_cache=self.state.kv_cache,
                return_cross_attn=True,
            )
        else:
            logger.debug(f"Logits shape: {tokens.shape}")
            return self.state.inference.logits(
                tokens, encoder_feature, return_cross_attn=True,
            )

    def _sot_pos(self) -> int:
        """토큰 시퀀스에서 `<|sot|>`의 실제 절대 위치.

        `state.sot_index`는 `sot_sequence` 내부의 상대 인덱스라 context 길이를 반영하지 않는다.
        `_current_tokens()`가 context 토큰(`<|startofprev|>` 시작)을 **앞에** 붙이므로, context가
        비어 있지 않으면 그 길이만큼 뒤로 밀어야 한다. context가 비면 오프셋 0 → 기존 동작과 동일.
        """
        ctx_len = 0
        ctx = getattr(self.state, "context", None)
        if ctx is not None and not ctx.is_empty():
            ctx_len = len(ctx.as_token_ids())
        return ctx_len + int(self.state.sot_index)

    def _check_no_speech(self, logits):
        if self.tokenizer.no_speech is not None:
            # context 보정 필수 — 보정 없이 읽으면 `--max-context-tokens>0` /
            # `--static-init-prompt` 사용 시 `<|startofprev|>` 위치의 분포를 읽어
            # 무음 판정이 무의미해진다(스퓨리어스 "no speech, stop").
            sot_pos = self._sot_pos()
            if sot_pos < 0 or sot_pos >= logits.shape[1]:
                return False
            probs_at_sot = logits[:, sot_pos, :].float().softmax(dim=-1)
            no_speech_probs = probs_at_sot[:, self.tokenizer.no_speech].tolist()
            if no_speech_probs[0] > self.cfg.nonspeech_prob:
                logger.info("no speech, stop")
                return True
        return False

    def _read_sot_posteriors(self, logits):
        """첫 forward logits에서 SOT/task 위치 사후분포를 읽는다 — **계측 전용**.

        추가 forward 0회: infer()의 첫 forward는 new_segment일 때 전체 토큰 시퀀스를
        넣으므로 logits shape이 [beam, T, V]다. 위치 sot_pos(= <|sot|>)의 logits는
        "다음 토큰 = 언어 토큰" 분포이고, 이는 lang_id(encoder_feature)가 x=[[sot]]로
        새 forward를 돌려 얻는 값과 수학적으로 동일하다(언어 토큰은 위치 1 이후라
        causal mask 때문에 위치 0의 예측을 오염시키지 않는다).

        신호 4종:
          S1 p_ko/p_en        — lang_id와 동일 규칙(lang_restrict_koen)으로 재정규화한 확률.
                                기존 [SessionStartLangProbe]/[ShortSilenceLangCheck] 로그와
                                직접 비교 가능한 기준선.
          S2 p_abs_*/resid/H  — **비정규화** 절대 언어질량. 기존 값은 전부 재정규화라
                                "en 0.99"가 절대확신인지, 양쪽 질량이 미미한데 비율만
                                en쪽인지 구분할 수 없었다. 음차 구간이 "어느 쪽도 아닌
                                표상"이면 resid↑·H_lang↑로 나타난다.
          S3 p_translate/p_transcribe — task 위치(sot_pos+1) 사후분포. <|translate|>는
                                suppress_tokens로 **생성만** 막혀 있고 확률은 그대로 읽힌다.
                                주의: <|en|><|translate|>는 whisper 학습에도 거의 없는
                                조합이라 이 값은 "번역 의도 검출기"가 아니다 —
                                **off-manifold 이상탐지기**로만 취급할 것(검증 대상 가설).
          S4 p_nospeech       — 이미 계산돼 문턱 비교만 하고 버려지는 값(_check_no_speech).

        불변식: logits를 in-place로 절대 수정하지 않는다. 호출 직후 infer()가 같은
        텐서를 logits[:, -1, :]로 재사용하므로 슬라이스를 clone한 뒤에만 계산한다.
        beam이 여러 개면 beam 0 기준(_check_no_speech가 no_speech_probs[0]을 쓰는 관례).
        """
        tok = self.tokenizer
        if logits is None or getattr(logits, "ndim", 0) != 3:
            return None

        # sot 위치는 context 토큰 길이만큼 뒤로 밀린다(_current_tokens가 앞에 붙임) — _sot_pos() 참조.
        # (2026-08 캠페인에서 _check_no_speech도 같은 보정을 쓰도록 통일했다.)
        sot_pos = self._sot_pos()
        if sot_pos < 0 or sot_pos + 1 >= logits.shape[1]:
            return None

        all_ids = list(tok.all_language_tokens)
        all_codes = list(tok.all_language_codes)
        id_by_code = dict(zip(all_codes, all_ids))
        ko_id, en_id = id_by_code.get("ko"), id_by_code.get("en")
        if ko_id is None or en_id is None or not all_ids:
            return None
        cand_ids = self._lang_candidate_token_ids()
        if not cand_ids:
            return None

        # clone 필수 — 아래 어떤 연산도 원본 logits를 건드리면 안 된다.
        sot_logits = logits[0, sot_pos, :].detach().float().clone()
        task_logits = logits[0, sot_pos + 1, :].detach().float().clone()
        probs_sot = sot_logits.softmax(dim=-1)
        probs_task = task_logits.softmax(dim=-1)
        dev = probs_sot.device
        eps = 1e-12

        # S2: 전체 어휘 softmax에서의 절대 언어질량 + 언어 토큰 집합 엔트로피(nats)
        p_abs_ko = probs_sot[ko_id]
        p_abs_en = probs_sot[en_id]
        resid = 1.0 - p_abs_ko - p_abs_en
        lang_idx = torch.as_tensor(all_ids, dtype=torch.long, device=dev)
        p_lang = probs_sot[lang_idx]
        p_lang = p_lang / p_lang.sum().clamp_min(eps)
        h_lang = -(p_lang * torch.log(p_lang.clamp_min(eps))).sum()

        # S1: lang_id와 동일한 후보집합에 대한 재정규화 확률
        cand_idx = torch.as_tensor(cand_ids, dtype=torch.long, device=dev)
        cand_mass = probs_sot[cand_idx].sum().clamp_min(eps)
        p_ko = p_abs_ko / cand_mass
        p_en = p_abs_en / cand_mass

        # S3 / S4
        p_translate = probs_task[tok.translate]
        p_transcribe = probs_task[tok.transcribe]
        ns_id = getattr(tok, "no_speech", None)
        p_nospeech = (probs_sot[ns_id] if ns_id is not None
                      else torch.tensor(float("nan"), device=dev))

        # GPU→CPU 동기화를 1회로 묶는다(.item() 다발은 매 배치 sync를 유발).
        vals = torch.stack([
            p_ko, p_en, p_abs_ko, p_abs_en, resid, h_lang,
            p_translate, p_transcribe, p_nospeech,
        ]).tolist()
        return {
            "p_ko": vals[0], "p_en": vals[1],
            "p_abs_ko": vals[2], "p_abs_en": vals[3],
            "resid": vals[4], "H_lang": vals[5],
            "p_translate": vals[6], "p_transcribe": vals[7],
            "p_nospeech": None if ns_id is None else vals[8],
            "sot_pos": sot_pos, "ctx_len": sot_pos - int(self.state.sot_index),
        }

    def _suppress_blank_tokens(self, logits):
        logits[:, self.tokenizer.encode(" ") + [self.tokenizer.eot]] = -np.inf
        return logits

    def _apply_token_suppression(self, logits):
        self.state.suppress_tokens_fn(logits)
        return logits

    def _update_tokens(self, current_tokens, logits, sum_logprobs):
        return self.state.token_decoder.update(current_tokens, logits, sum_logprobs)

    def _process_cross_attention(
        self, cross_attns: List, content_mel_len: int,
    ) -> torch.Tensor:
        attn_of_alignment_heads = [[] for _ in range(self.state.num_align_heads)]
        num_decoder_layers = len(self.model.decoder.blocks)

        if cross_attns and isinstance(cross_attns[0], list):
            flattened_attns = [attn for layer_list in cross_attns for attn in layer_list]
        else:
            flattened_attns = cross_attns

        for idx, attn_mat in enumerate(flattened_attns):
            layer_rank = idx % num_decoder_layers
            align_heads_in_layer = self.state.align_source.get(layer_rank, [])
            if not align_heads_in_layer:
                continue
            attn_mat = F.softmax(attn_mat, dim=-1)
            for align_head_rank, head_id in align_heads_in_layer:
                if self.cfg.beam_size == 1:
                    if attn_mat.dim() == 4:
                        a = attn_mat[0, head_id, :, :]
                    else:
                        a = attn_mat[head_id, :, :]
                    a = a.unsqueeze(0)
                else:
                    a = attn_mat[:, head_id, :, :]
                attn_of_alignment_heads[align_head_rank].append(a)

        tmp = []
        for mat in attn_of_alignment_heads:
            if mat:
                tmp.append(torch.cat(mat, dim=1))
        if not tmp:
            return torch.zeros(self.cfg.beam_size, 1, content_mel_len, device=self.device)

        attn_of_alignment_heads = torch.stack(tmp, dim=1)
        std, mean = torch.std_mean(
            attn_of_alignment_heads, dim=-2, keepdim=True, unbiased=False,
        )
        attn_of_alignment_heads = (attn_of_alignment_heads - mean) / (std + 1e-8)
        attn_of_alignment_heads = median_filter(attn_of_alignment_heads, 7)
        attn_of_alignment_heads = attn_of_alignment_heads.mean(dim=1)
        attn_of_alignment_heads = attn_of_alignment_heads[:, :, :content_mel_len]
        return attn_of_alignment_heads

    def _get_attended_frames(self, attn):
        most_attended_frames = torch.argmax(attn[:, -1, :], dim=-1)
        return most_attended_frames.tolist(), most_attended_frames[0].item()

    def _is_special_token(self, current_tokens):
        return current_tokens[0, -2].item() >= DEC_PAD

    def _rewind_tokens(self):
        if len(self.state.tokens) > 0:
            return torch.cat(self.state.tokens, dim=1)
        return self.state.tokens[0]

    def _tokens_to_list(self, current_tokens, start_col):
        return current_tokens[0, start_col:].flatten().tolist()

    def _make_new_tokens_tensor(self, hypothesis):
        return (
            torch.tensor([hypothesis], dtype=torch.long)
            .repeat_interleave(self.cfg.beam_size, dim=0)
            .to(device=self.device)
        )

    def _evaluate(self, tensor):
        pass  # No-op for PyTorch

    @torch.no_grad()
    def infer(self, is_last=False):
        return super().infer(is_last)
