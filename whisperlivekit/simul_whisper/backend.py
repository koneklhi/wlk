import gc
import logging
import platform
import re
import sys
from collections import Counter
from typing import List, Tuple

import numpy as np
import torch

from whisperlivekit.backend_support import faster_backend_available, mlx_backend_available
from whisperlivekit.model_paths import detect_model_format, resolve_model_path
from whisperlivekit.simul_whisper.config import AlignAttConfig
from whisperlivekit.simul_whisper.simul_whisper import AlignAtt
from whisperlivekit.timed_objects import ASRToken, ChangeSpeaker, LanguageSwitch, Transcript
from whisperlivekit.warmup import load_file
from whisperlivekit.whisper import load_model, tokenizer

logger = logging.getLogger(__name__)


HAS_MLX_WHISPER = mlx_backend_available(warn_on_missing=True)
if HAS_MLX_WHISPER:
    from .mlx import MLXAlignAtt
    from .mlx_encoder import load_mlx_encoder, load_mlx_model, mlx_model_mapping
else:
    mlx_model_mapping = {}
    MLXAlignAtt = None
HAS_FASTER_WHISPER = faster_backend_available(warn_on_missing=not HAS_MLX_WHISPER)
if HAS_FASTER_WHISPER:
    from faster_whisper import WhisperModel
else:
    WhisperModel = None

MIN_DURATION_REAL_SILENCE = 2
MIN_DURATION_SHORT_LANG_RESET = 0.5

# 디코더 멈춤 복구: 오디오가 이 시간(초) 이상 전진했는데 토큰이 전혀 안 나오면
# SimulStreaming 디코더가 비-fire 상태에 빠진 것으로 보고 강제 refresh로 복구한다.
STALL_RECOVER_SEC = 10.0

_FOREIGN_LANG_PATTERN = re.compile(r'\(speaking in foreign language', re.IGNORECASE)

class SimulStreamingOnlineProcessor:
    """Online processor for SimulStreaming ASR."""
    SAMPLING_RATE = 16000

    # 단일음절 반복 환각 억제: max_char_run >= _CHAR_RUN_THRESHOLD 인 토큰은 제거
    # _HALLUCINATION_RESET_THRESHOLD 연속 발생 시 context 리셋
    _CHAR_RUN_THRESHOLD = 4
    _HALLUCINATION_RESET_THRESHOLD = 5

    def __init__(self, asr, logfile=sys.stderr):
        self.asr = asr
        self.logfile = logfile
        self.end = 0.0
        self.buffer = []
        self.model = self._create_alignatt()
        self._last_emitted_word: str = None
        self._last_emit_end: float = 0.0  # 마지막으로 토큰을 방출한 시점의 audio end (stall 복구 baseline)
        self._consecutive_char_repeat: int = 0
        self._short_silence_check_at: float = 0.0
        self._recent_emitted_words: List[str] = []  # 중복 방출 계측용 최근 방출 단어(정규화) tail

        if asr.tokenizer:
            self.model.tokenizer = asr.tokenizer
            self.model.state.tokenizer = asr.tokenizer

    def _create_alignatt(self):
        """Create the AlignAtt decoder instance based on ASR mode."""
        if self.asr.use_full_mlx and HAS_MLX_WHISPER:
            return MLXAlignAtt(cfg=self.asr.cfg, mlx_model=self.asr.mlx_model)
        else:
            return AlignAtt(
                cfg=self.asr.cfg,
                loaded_model=self.asr.shared_model,
                mlx_encoder=self.asr.mlx_encoder,
                fw_encoder=self.asr.fw_encoder,
            )

    def start_silence(self):
        tokens, processed_upto = self.process_iter(is_last=True)
        return tokens, processed_upto

    def end_silence(self, silence_duration, offset):
        """Handle silence period."""
        self.end += silence_duration
        long_silence = silence_duration >= MIN_DURATION_REAL_SILENCE
        # 계측용(행동 비변경): 어느 분기를 타는지는 아래 if/elif와 동일 조건으로 별도 계산해
        # 로그 라벨만 만든다 — 기존 if/elif 조건식 자체는 건드리지 않는다.
        _short_cond = (
            silence_duration >= MIN_DURATION_SHORT_LANG_RESET
            and self.model.cfg.language == "auto"
            and self.model.state.detected_language is not None
        )
        logger.info(
            "[EndSilence] dur=%.2fs branch=%s det_lang=%s lang_before_reset=%s",
            silence_duration, "long" if long_silence else ("short" if _short_cond else "none"),
            self.model.state.detected_language, self.model.state.lang_before_reset,
        )
        if not long_silence:
            gap_len = int(16000 * silence_duration)
            if gap_len > 0:
                if self.asr.use_full_mlx:
                    gap_silence = np.zeros(gap_len, dtype=np.float32)
                else:
                    gap_silence = torch.zeros(gap_len)
                self.model.insert_audio(gap_silence)
        if long_silence:
            self.model.refresh_segment(complete=True)
            logger.info(
                "[EndSilence] long-silence 리셋 직전(폐기 예정): det_lang=%s→None lang_before_reset=%s→None",
                self.model.state.detected_language, self.model.state.lang_before_reset,
            )
            self.model.state.detected_language = None   # 재감지 허용
            self.model.state.lang_before_reset = None   # 긴 침묵 = 문장 경계, 전환 판정 불필요
            self.model.state.first_timestamp = None     # 재감지 조건 충족
            self.model.global_time_offset = silence_duration + offset
            self.model.state.quality_suppress_streak = 0  # 침묵 경계 넘어 streak 누적 → 엉뚱한 refresh 방지
            self._last_emitted_word = None
            self._last_emit_end = self.end
            self._consecutive_char_repeat = 0
            self._short_silence_check_at = 0.0
        elif (
            silence_duration >= MIN_DURATION_SHORT_LANG_RESET
            and self.model.cfg.language == "auto"
            and self.model.state.detected_language is not None
        ):
            self._short_silence_check_at = self.end + 1.5

    def _check_short_silence_language(self):
        """짧은 pause 후 1.5s 오디오 누적 시점에 언어 재감지. 전환 확인 시 전환 프로토콜 적용.

        (버그 수정) 기존엔 create_tokenizer+init_context만 호출하고 init_tokens()를 누락해
        state.tokens[0]의 SOT 언어 토큰이 옛 언어로 잔존했다 → 감지만 되고 디코딩에 미적용.
        재작성된 _apply_detected_language 호출로 SOT 토큰 갱신 + 경계 절단 + 문장 경계 arm.
        """
        new_lang = self.model.detect_current_language(window_secs=1.5, min_prob=0.90)
        if new_lang is not None and new_lang != self.model.state.detected_language:
            logger.info(
                "[ShortSilenceLangCheck] 언어 전환 감지: %s → %s",
                self.model.state.detected_language, new_lang,
            )
            self.model._apply_detected_language(new_lang)

    def insert_audio_chunk(self, audio: np.ndarray, audio_stream_end_time):
        """Append an audio chunk to be processed by SimulStreaming."""
        self.end = audio_stream_end_time
        if self.asr.use_full_mlx:
            self.model.insert_audio(audio)
        else:
            audio_tensor = torch.from_numpy(audio).float()
            self.model.insert_audio(audio_tensor)

    def new_speaker(self, change_speaker: ChangeSpeaker):
        """Handle speaker change event.

        경계 재디코딩: held 음역을 final 확정하지 않고(flush 생략), 최근 오디오(경계 구간)를
        complete=False 로 유지해 새 화자 언어로 재디코딩한다. refresh 전에 최근 1.5s 윈도우로
        언어를 즉시 재감지하고, 성공 시 refresh 후 토크나이저를 교정한다(실패 시 None → 기존 2.0s 폴백).
        """
        # 1. refresh 전 버퍼로 새 화자 언어 즉시 감지 (경계 오디오가 아직 버퍼에 있음)
        eager = self.model.detect_current_language(window_secs=1.5, min_prob=0.85)
        logger.info(
            "[NewSpeaker] spk=%s→%s det_before=%s eager=%s",
            self.model.state.speaker, change_speaker.speaker,
            self.model.state.detected_language, eager,
        )
        # 2. flush 생략 + 경계 오디오 유지(complete=False) + 미확정 음역 폐기
        self.model.refresh_segment(complete=False)
        self.buffer = []
        self.model.state.lang_before_reset = self.model.state.detected_language or self.model.state.lang_before_reset
        self.model.state.detected_language = None
        self.model.state.first_timestamp = None
        self.model.state.eager_lang_detect = True
        # 3. 감지 성공 시 토크나이저 즉시 교정 (refresh 후 적용)
        if eager:
            self.model._apply_detected_language(eager)
        logger.info(
            "[NewSpeaker] spk=%s det_after=%s (eager_applied=%s)",
            change_speaker.speaker, self.model.state.detected_language, bool(eager),
        )
        self.model.speaker = change_speaker.speaker
        self.model.global_time_offset = change_speaker.start
        self._last_emitted_word = None
        self._last_emit_end = self.end
        self._consecutive_char_repeat = 0

    def get_buffer(self):
        concat_buffer = Transcript.from_tokens(tokens= self.buffer, sep='')
        return concat_buffer

    @staticmethod
    def _normalize(text: str) -> str:
        """비교용 정규화: 공백 제거 + NFC 유니코드 정규화."""
        import unicodedata
        return unicodedata.normalize("NFC", text.strip())

    @staticmethod
    def _max_char_run(text: str) -> int:
        """문자열 내 최대 연속 동일 문자 수 반환. 단일음절 반복 환각 감지에 사용."""
        if not text:
            return 0
        max_run = 1
        cur_run = 1
        for i in range(1, len(text)):
            if text[i] == text[i - 1]:
                cur_run += 1
                if cur_run > max_run:
                    max_run = cur_run
            else:
                cur_run = 1
        return max_run

    def _filter_cross_batch_repetitions(self, tokens: List[ASRToken]) -> List[ASRToken]:
        """배치 경계를 넘나드는 연속 반복 토큰 제거 + 단일음절 반복 환각 억제."""
        # 배치 내 한글 단어 4회+ 반복 → cascade 환각 선제 차단
        batch_words = [self._normalize(t.text) for t in tokens if self._normalize(t.text)]
        korean_batch_words = [w for w in batch_words if re.search(r'[가-힣]', w)]
        if len(korean_batch_words) >= 4:
            counts = Counter(korean_batch_words)
            top_word, top_count = counts.most_common(1)[0]
            if top_count >= 4:
                logger.warning(
                    "[BatchRepeatFilter] 배치 내 반복 %r ×%d — 배치 드롭+리셋", top_word, top_count
                )
                self.model.refresh_segment(complete=True)
                self._last_emitted_word = None
                self._last_emit_end = self.end
                self._consecutive_char_repeat = 0
                return []
        result = []
        prev = self._last_emitted_word

        _LEADING_PUNCT = frozenset([".", "。", "!", "?", "！", "？"])
        # 직전 방출 단어가 이미 문장종료 구두점으로 끝난 진짜 중복일 때만 선두 구두점 제거.
        # 아니면 보존 — 직전 단어의 문장끝 온점을 살린다(UI 표시용).
        prev_ends_punct = bool(self._last_emitted_word) and self._last_emitted_word.rstrip()[-1:] in _LEADING_PUNCT
        if prev_ends_punct:
            while tokens and self._normalize(tokens[0].text) in _LEADING_PUNCT:
                logger.debug("[LeadingPunctFilter] 중복 선두 구두점 제거: %r", tokens[0].text)
                tokens = tokens[1:]

        for token in tokens:
            word = self._normalize(token.text)
            if not word:
                result.append(token)
                continue
            if word in ("-", "–", "—"):
                logger.debug("[DashFilter] 순수 대시 토큰 스킵: %r", word)
                continue
            stripped = word.lstrip('-').strip()
            if len(stripped) >= 4 and self._max_char_run(stripped) >= self._CHAR_RUN_THRESHOLD:
                self._consecutive_char_repeat += 1
                logger.debug("[HallucinationFilter] 단일음절반복 억제: %r (count=%d)", word, self._consecutive_char_repeat)
                if self._consecutive_char_repeat >= self._HALLUCINATION_RESET_THRESHOLD:
                    logger.warning(
                        "[HallucinationFilter] 환각 루프 임계치 초과 — context 리셋 (count=%d)",
                        self._consecutive_char_repeat,
                    )
                    self.model.refresh_segment(complete=True)
                    self._consecutive_char_repeat = 0
                    self._last_emitted_word = None
                    prev = None
                continue
            self._consecutive_char_repeat = 0
            if prev is not None and word == prev:
                logger.info("[CrossBatchFilter] 반복 제거: %r (prev=%r)", word, prev)
                continue
            result.append(token)
            prev = word
        if result:
            self._last_emitted_word = self._normalize(result[-1].text)
        return result

    def process_iter(self, is_last=False) -> Tuple[List[ASRToken], float]:
        """
        Process accumulated audio chunks using SimulStreaming.

        Returns a tuple: (list of committed ASRToken objects, float representing the audio processed up to time).
        """
        try:
            if self._short_silence_check_at > 0 and self.end >= self._short_silence_check_at:
                self._check_short_silence_language()
                self._short_silence_check_at = 0.0

            timestamped_words = self.model.infer(is_last=is_last)

            if timestamped_words:
                logger.debug("[TokenTrace] infer→%d tokens: %s", len(timestamped_words),
                             " ".join(t.text for t in timestamped_words[:20]))
                decoded_text = ''.join(t.text for t in timestamped_words)
                if _FOREIGN_LANG_PATTERN.search(decoded_text):
                    logger.warning("[ForeignLang] '(speaking in foreign language)' 감지 → 즉시 언어재감지 트리거")
                    # new_speaker와 일관되게 현재 언어를 전환 판정 기준으로 승계한다.
                    # ForeignLang은 방금 방출이 언어혼란(garbage)임을 뜻하므로, 재감지 후 언어가
                    # 달라지면 정당한 전환 → _apply_detected_language의 prev_lang 폴백이 경계
                    # 마커/트림을 발동해야 한다. 미승계 시 prev_lang이 stale해 전환이 누락된다.
                    self.model.state.lang_before_reset = (
                        self.model.state.detected_language or self.model.state.lang_before_reset
                    )
                    self.model.state.detected_language = None
                    self.model.state.first_timestamp = None
                    self.model.state.eager_lang_detect = True
                    self.model.state.last_lang_switch_time = 0.0
                    # 버려지는 세그먼트 텍스트를 로깅 (단계 C 계측: 정상 텍스트가 함께 유실되는지 감시).
                    dropped = [t for t in timestamped_words if _FOREIGN_LANG_PATTERN.search(t.text)]
                    if dropped:
                        logger.warning("[ForeignLang] 드롭 텍스트: %.200s",
                                       " ".join(t.text for t in dropped))
                    timestamped_words = [t for t in timestamped_words
                                         if not _FOREIGN_LANG_PATTERN.search(t.text)]

            if not timestamped_words:
                # 디코더 멈춤 복구 워치독: 오디오가 STALL_RECOVER_SEC 이상 전진했는데
                # 토큰이 전혀 안 나오면 디코더가 비-fire 상태(연속 발화 30s+, 침묵 없음)에
                # 빠진 것 → 강제 refresh로 세그먼트/상태를 리셋해 복구한다.
                if not is_last and self.end - self._last_emit_end > STALL_RECOVER_SEC:
                    logger.warning(
                        "SimulStreaming stall recovery: %.1fs without output "
                        "(end=%.1fs) — forcing segment refresh.",
                        self.end - self._last_emit_end, self.end,
                    )
                    self.model.refresh_segment(complete=True)
                    self._last_emitted_word = None
                    self._last_emit_end = self.end
                    self._consecutive_char_repeat = 0
                return [], self.end

            if self.model.cfg.language == "auto" and timestamped_words[0].detected_language is None:
                self.buffer.extend(timestamped_words)
                return [], self.end

            timestamped_words = self._filter_cross_batch_repetitions(timestamped_words)

            # 언어 전환 경계 마커 삽입 (_apply_detected_language가 진짜 전환 시 arm).
            pending = getattr(self.model.state, "pending_language_switch", None)
            if pending is not None and timestamped_words:
                # 중복 방출 계측: 전환 직후 첫 배치가 직전 방출 tail(최근 5개)과 겹치는지
                tail = self._recent_emitted_words[-5:]
                new_words = [self._normalize(t.text) for t in timestamped_words]
                new_words = [w for w in new_words if w]
                overlap = sum(1 for w in new_words if w in tail)
                if overlap:
                    logger.warning(
                        "[SwitchTaxMeasure] 전환 직후 배치 %d/%d 단어가 직전 tail과 겹침 (tail=%s)",
                        overlap, len(new_words), tail,
                    )
                else:
                    logger.info("[SwitchTaxMeasure] 전환 직후 배치 겹침 없음 (tail=%s)", tail)
                boundary_t = timestamped_words[0].start
                marker = LanguageSwitch(
                    start=boundary_t, end=boundary_t,
                    detected_language=self.model.state.detected_language,
                )
                timestamped_words = [marker] + timestamped_words
                self.model.state.pending_language_switch = None
                logger.info("[LangSwitch] 문장 경계 마커 방출 @ %.2fs (lang=%s)",
                            boundary_t, self.model.state.detected_language)

            if timestamped_words:
                logger.debug("[TokenTrace] emit→%d tokens: %s", len(timestamped_words),
                             " ".join(t.text for t in timestamped_words[:20]))
                # 계측용 최근 방출 단어 tail 갱신 (마커 제외, 최근 10개 유지)
                emitted = [self._normalize(t.text) for t in timestamped_words
                           if not getattr(t, "is_boundary", None) or not t.is_boundary()]
                emitted = [w for w in emitted if w]
                if emitted:
                    self._recent_emitted_words = (self._recent_emitted_words + emitted)[-10:]
            self.buffer = []
            self._last_emit_end = self.end
            return timestamped_words, self.end
        except Exception as e:
            logger.exception(f"SimulStreaming processing error: {e}")
            return [], self.end

    def warmup(self, audio, init_prompt=""):
        """Warmup the SimulStreaming model."""
        try:
            if self.asr.use_full_mlx:
                # MLX mode: ensure numpy array
                if hasattr(audio, 'numpy'):
                    audio = audio.numpy()
            self.model.insert_audio(audio)
            self.model.infer(True)
            self.model.refresh_segment(complete=True)
            logger.info("SimulStreaming model warmed up successfully")
        except Exception as e:
            logger.exception(f"SimulStreaming warmup failed: {e}")

    def __del__(self):
        gc.collect()
        if not getattr(self.asr, 'use_full_mlx', True) and torch is not None:
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass


class SimulStreamingASR:
    """SimulStreaming backend with AlignAtt policy."""
    sep = ""

    def __init__(self, logfile=sys.stderr, **kwargs):
        self.logfile = logfile
        self.transcribe_kargs = {}

        for key, value in kwargs.items():
            setattr(self, key, value)

        if getattr(self, 'max_context_tokens', None) is None:
            self.max_context_tokens = 0

        if self.decoder_type is None:
            self.decoder_type = 'greedy' if self.beams == 1 else 'beam'

        self.fast_encoder = False
        self._resolved_model_path = None
        self.encoder_backend = "whisper"
        self.use_full_mlx = getattr(self, "use_full_mlx", False)
        preferred_backend = getattr(self, "backend", "auto")
        compatible_whisper_mlx, compatible_faster_whisper = True, True

        model_path_or_dir = self.model_path or getattr(self, 'model_dir', None)
        if model_path_or_dir:
            resolved_model_path = resolve_model_path(model_path_or_dir)
            self._resolved_model_path = resolved_model_path
            self.model_path = str(resolved_model_path)

            model_info = detect_model_format(resolved_model_path)
            compatible_whisper_mlx = model_info.compatible_whisper_mlx
            compatible_faster_whisper = model_info.compatible_faster_whisper

            if not self.use_full_mlx and not model_info.has_pytorch:
                raise FileNotFoundError(
                    f"No PyTorch checkpoint (.pt/.bin/.safetensors) found under {self.model_path}"
                )
            self.model_name = resolved_model_path.name if resolved_model_path.is_dir() else resolved_model_path.stem
        elif self.model_size is not None:
            self.model_name = self.model_size
        else:
            raise ValueError("Either model_size or model_path must be specified for SimulStreaming.")

        is_multilingual = not self.model_name.endswith(".en")

        self.encoder_backend = self._resolve_encoder_backend(
            preferred_backend,
            compatible_whisper_mlx,
            compatible_faster_whisper,
        )
        self.fast_encoder = self.encoder_backend in ("mlx-whisper", "faster-whisper")
        if self.encoder_backend == "whisper":
            self.disable_fast_encoder = True

        # MLX full decoder disabled by default — MLXAlignAtt has known issues
        # with token generation after punctuation. Users can opt-in with
        # --use-full-mlx if they want to test it.
        # if self.encoder_backend == "mlx-whisper" and platform.system() == "Darwin":
        #     if not hasattr(self, '_full_mlx_disabled'):
        #         self.use_full_mlx = True

        self.cfg = AlignAttConfig(
                tokenizer_is_multilingual= is_multilingual,
                segment_length=self.min_chunk_size,
                frame_threshold=self.frame_threshold,
                language=self.lan,
                audio_max_len=self.audio_max_len,
                audio_min_len=self.audio_min_len,
                cif_ckpt_path=self.cif_ckpt_path,
                decoder_type="beam",
                beam_size=self.beams,
                task="translate" if self.direct_english_translation else "transcribe",
                never_fire=self.never_fire,
                init_prompt=self.init_prompt,
                max_context_tokens=self.max_context_tokens,
                static_init_prompt=self.static_init_prompt,
                logprob_threshold=self.logprob_threshold,
                compression_ratio_threshold=self.compression_ratio_threshold,
                lang_restrict_koen=getattr(self, 'lang_restrict_koen', True),
                periodic_lang_check_secs=getattr(self, 'periodic_lang_check_secs', None),
        )

        # Set up tokenizer for translation if needed
        if self.direct_english_translation:
            self.tokenizer = self.set_translate_task()
        else:
            self.tokenizer = None

        self.mlx_encoder, self.fw_encoder, self.mlx_model = None, None, None
        self.shared_model = None

        if self.use_full_mlx and HAS_MLX_WHISPER:
            logger.info('MLX Whisper backend used.')
            if self._resolved_model_path is not None:
                mlx_model_path = str(self._resolved_model_path)
            else:
                mlx_model_path = mlx_model_mapping.get(self.model_name)
            if not mlx_model_path:
                raise FileNotFoundError(
                    f"MLX Whisper backend requested but no compatible weights found for model '{self.model_name}'."
                )
            self.mlx_model = load_mlx_model(path_or_hf_repo=mlx_model_path)
            self._warmup_mlx_model()
        elif self.encoder_backend == "mlx-whisper":
            # hybrid mode: mlx encoder + pytorch decoder
            logger.info('SimulStreaming will use MLX Whisper encoder with PyTorch decoder.')
            if self._resolved_model_path is not None:
                mlx_model_path = str(self._resolved_model_path)
            else:
                mlx_model_path = mlx_model_mapping.get(self.model_name)
            if not mlx_model_path:
                raise FileNotFoundError(
                    f"MLX Whisper backend requested but no compatible weights found for model '{self.model_name}'."
                )
            self.mlx_encoder = load_mlx_encoder(path_or_hf_repo=mlx_model_path)
            self.shared_model = self.load_model()
        elif self.encoder_backend == "faster-whisper":
            logger.info('SimulStreaming will use Faster Whisper for the encoder.')
            if self._resolved_model_path is not None:
                fw_model = str(self._resolved_model_path)
            else:
                fw_model = self.model_name
            self.fw_encoder = WhisperModel(
                fw_model,
                device='auto',
                compute_type='auto',
            )
            self.shared_model = self.load_model()
        else:
            self.shared_model = self.load_model()

    def _warmup_mlx_model(self):
        """Warmup the full MLX model."""
        warmup_audio = load_file(self.warmup_file)
        if warmup_audio is not None:
            temp_model = MLXAlignAtt(
                cfg=self.cfg,
                mlx_model=self.mlx_model,
            )
            temp_model.warmup(warmup_audio)
            logger.info("Full MLX model warmed up successfully")


    def _resolve_encoder_backend(self, preferred_backend, compatible_whisper_mlx, compatible_faster_whisper):
        choice = preferred_backend or "auto"
        if self.disable_fast_encoder:
            return "whisper"
        if choice == "whisper":
            return "whisper"
        if choice == "mlx-whisper":
            if not self._can_use_mlx(compatible_whisper_mlx):
                raise RuntimeError("mlx-whisper backend requested but MLX Whisper is unavailable or incompatible with the provided model.")
            return "mlx-whisper"
        if choice == "faster-whisper":
            if not self._can_use_faster(compatible_faster_whisper):
                raise RuntimeError("faster-whisper backend requested but Faster-Whisper is unavailable or incompatible with the provided model.")
            return "faster-whisper"
        if choice == "openai-api":
            raise ValueError("openai-api backend is only supported with the LocalAgreement policy.")
        # auto mode
        if platform.system() == "Darwin" and self._can_use_mlx(compatible_whisper_mlx):
            return "mlx-whisper"
        if self._can_use_faster(compatible_faster_whisper):
            return "faster-whisper"
        return "whisper"

    def _has_custom_model_path(self):
        return self._resolved_model_path is not None

    def _can_use_mlx(self, compatible_whisper_mlx):
        if not HAS_MLX_WHISPER:
            return False
        if self._has_custom_model_path():
            return compatible_whisper_mlx
        return self.model_name in mlx_model_mapping

    def _can_use_faster(self, compatible_faster_whisper):
        if not HAS_FASTER_WHISPER:
            return False
        if self._has_custom_model_path():
            return compatible_faster_whisper
        return True

    def load_model(self):
        model_ref = str(self._resolved_model_path) if self._resolved_model_path else self.model_name
        lora_path = getattr(self, 'lora_path', None)
        whisper_model = load_model(
            name=model_ref,
            download_root=getattr(self, 'model_cache_dir', None),
            decoder_only=self.fast_encoder,
            custom_alignment_heads=self.custom_alignment_heads,
            lora_path=lora_path,
        )
        warmup_audio = load_file(self.warmup_file)
        if warmup_audio is not None:
            warmup_audio = torch.from_numpy(warmup_audio).float()
            if self.fast_encoder:
                temp_model = AlignAtt(
                    cfg=self.cfg,
                    loaded_model=whisper_model,
                    mlx_encoder=self.mlx_encoder,
                    fw_encoder=self.fw_encoder,
                )
                temp_model.warmup(warmup_audio)
            else:
                whisper_model.transcribe(warmup_audio, language=self.lan if self.lan != 'auto' else None)
        return whisper_model

    def set_translate_task(self):
        """Set up translation task."""
        if self.cfg.language == 'auto':
            raise ValueError('Translation cannot be done with language = auto')
        return tokenizer.get_tokenizer(
            multilingual=True,
            language=self.cfg.language,
            num_languages=99,
            task="translate"
        )

    def transcribe(self, audio):
        """
        Warmup is done directly in load_model
        """
        pass
