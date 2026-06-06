import gc
import logging
import platform
import sys
from collections import Counter, deque
from typing import List, Tuple

import numpy as np
import torch

from whisperlivekit.backend_support import faster_backend_available, mlx_backend_available
from whisperlivekit.model_paths import detect_model_format, resolve_model_path
from whisperlivekit.simul_whisper.config import AlignAttConfig
from whisperlivekit.simul_whisper.simul_whisper import AlignAtt
from whisperlivekit.timed_objects import ASRToken, ChangeSpeaker, Transcript
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

MIN_DURATION_REAL_SILENCE = 5

# 디코더 멈춤 복구: 오디오가 이 시간(초) 이상 전진했는데 토큰이 전혀 안 나오면
# SimulStreaming 디코더가 비-fire 상태에 빠진 것으로 보고 강제 refresh로 복구한다.
STALL_RECOVER_SEC = 10.0

class SimulStreamingOnlineProcessor:
    """Online processor for SimulStreaming ASR."""
    SAMPLING_RATE = 16000

    # 반복 루프 감지 파라미터: 최근 N 토큰 중 동일 단어가 K회 이상이면 refresh_segment() 리셋
    _LOOP_WINDOW = 20
    _LOOP_THRESHOLD = 5

    def __init__(self, asr, logfile=sys.stderr):
        self.asr = asr
        self.logfile = logfile
        self.end = 0.0
        self.buffer = []
        self.model = self._create_alignatt()
        self._last_emitted_word: str = None
        self._last_emit_end: float = 0.0  # 마지막으로 토큰을 방출한 시점의 audio end (stall 복구 baseline)
        self._recent_tokens: deque = deque(maxlen=self._LOOP_WINDOW)

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
            self.model.global_time_offset = silence_duration + offset
            self._last_emitted_word = None
            self._last_emit_end = self.end
            self._recent_tokens.clear()

    def insert_audio_chunk(self, audio: np.ndarray, audio_stream_end_time):
        """Append an audio chunk to be processed by SimulStreaming."""
        self.end = audio_stream_end_time
        if self.asr.use_full_mlx:
            self.model.insert_audio(audio)
        else:
            audio_tensor = torch.from_numpy(audio).float()
            self.model.insert_audio(audio_tensor)

    def new_speaker(self, change_speaker: ChangeSpeaker):
        """Handle speaker change event."""
        self.process_iter(is_last=True)
        self.model.refresh_segment(complete=True)
        self.model.speaker = change_speaker.speaker
        self.model.global_time_offset = change_speaker.start
        self._last_emitted_word = None
        self._last_emit_end = self.end
        self._recent_tokens.clear()

    def get_buffer(self):
        concat_buffer = Transcript.from_tokens(tokens= self.buffer, sep='')
        return concat_buffer

    @staticmethod
    def _normalize(text: str) -> str:
        """비교용 정규화: 공백 제거 + NFC 유니코드 정규화."""
        import unicodedata
        return unicodedata.normalize("NFC", text.strip())

    def _filter_cross_batch_repetitions(self, tokens: List[ASRToken]) -> List[ASRToken]:
        """배치 경계를 넘나드는 연속 반복 토큰 제거.

        Whisper SimulStreaming은 배치 경계에서 직전 단어를 반복 생성하는 아티팩트가 있다.
        ("바 바 바", "-그 -그", "도도도도" 등) 직전 방출 단어와 동일한 연속 토큰을 제거한다.
        """
        result = []
        prev = self._last_emitted_word
        for token in tokens:
            word = self._normalize(token.text)
            if not word:
                result.append(token)
                continue
            if prev is not None and word == prev:
                logger.debug(f"[CrossBatchFilter] 반복 제거: {repr(word)}")
                continue
            result.append(token)
            prev = word
        if result:
            self._last_emitted_word = self._normalize(result[-1].text)
        return result

    def _detect_repetition_loop(self) -> bool:
        """최근 _LOOP_WINDOW 토큰 중 동일 단어가 _LOOP_THRESHOLD 이상이면 반복 루프로 판정."""
        if len(self._recent_tokens) < self._LOOP_WINDOW // 2:
            return False
        counts = Counter(self._recent_tokens)
        if not counts:
            return False
        _, most_count = counts.most_common(1)[0]
        return most_count >= self._LOOP_THRESHOLD

    def process_iter(self, is_last=False) -> Tuple[List[ASRToken], float]:
        """
        Process accumulated audio chunks using SimulStreaming.

        Returns a tuple: (list of committed ASRToken objects, float representing the audio processed up to time).
        """
        try:
            timestamped_words = self.model.infer(is_last=is_last)

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
                return [], self.end

            if self.model.cfg.language == "auto" and timestamped_words[0].detected_language is None:
                self.buffer.extend(timestamped_words)
                return [], self.end

            timestamped_words = self._filter_cross_batch_repetitions(timestamped_words)
            for token in timestamped_words:
                word = self._normalize(token.text)
                if word:
                    self._recent_tokens.append(word)
            if self._detect_repetition_loop():
                logger.warning(
                    "반복 루프 감지 (window=%d, threshold=%d) → refresh_segment() 리셋.",
                    self._LOOP_WINDOW, self._LOOP_THRESHOLD,
                )
                self.model.refresh_segment(complete=True)
                self._last_emitted_word = None
                self._last_emit_end = self.end
                self._recent_tokens.clear()
                return [], self.end
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

        if self.decoder_type is None:
            self.decoder_type = 'greedy' if self.beams == 1 else 'beam'

        self.fast_encoder = False
        self._resolved_model_path = None
        self.encoder_backend = "whisper"
        self.use_full_mlx = getattr(self, "use_full_mlx", False)
        preferred_backend = getattr(self, "backend", "auto")
        compatible_whisper_mlx, compatible_faster_whisper = True, True

        if self.model_path:
            resolved_model_path = resolve_model_path(self.model_path)
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
