"""Typed configuration for the WhisperLiveKit pipeline."""
import logging
from dataclasses import dataclass, fields
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class WhisperLiveKitConfig:
    """Single source of truth for all WhisperLiveKit configuration.

    Replaces the previous dict-based parameter system in TranscriptionEngine.
    All fields have defaults matching the prior behaviour.
    """

    # Server / global
    host: str = "localhost"
    port: int = 8000
    diarization: bool = False
    punctuation_split: bool = False
    target_language: str = ""
    vac: bool = True
    vac_chunk_size: float = 0.04
    log_level: str = "DEBUG"
    ssl_certfile: Optional[str] = None
    ssl_keyfile: Optional[str] = None
    forwarded_allow_ips: Optional[str] = None
    transcription: bool = True
    vad: bool = True
    pcm_input: bool = False
    disable_punctuation_split: bool = False
    transcript_save_dir: str = "transcripts"
    # WebSocket 출력 프로토콜 기본값. "full" = 매 메시지 전체 스냅샷(구 동작), "delta" = snapshot 1회 + 이후 증분(diff).
    # 기본값이 full인 이유: 델타 미대응 클라이언트(배포 React)가 코드 수정 없이 그대로 동작해야 하므로
    # 델타는 opt-in(?mode=delta)이다. 쿼리파라미터 ?mode=delta|full 이 이 기본값을 오버라이드한다.
    ws_protocol: str = "full"
    frontend_dir: str = "frontend/static"
    frontend_base: str = "auto"
    diarization_backend: str = "sortformer"
    backend_policy: str = "simulstreaming"
    backend: str = "auto"

    # Transcription common
    warmup_file: Optional[str] = None
    min_chunk_size: float = 0.1
    model_size: str = "base"
    model_cache_dir: Optional[str] = None
    model_dir: Optional[str] = None
    model_path: Optional[str] = None
    lora_path: Optional[str] = None
    lan: str = "auto"
    direct_english_translation: bool = False

    # LocalAgreement-specific
    buffer_trimming: str = "segment"
    confidence_validation: bool = False
    buffer_trimming_sec: float = 15.0

    # SimulStreaming-specific
    disable_fast_encoder: bool = False
    custom_alignment_heads: Optional[str] = None
    frame_threshold: int = 25
    beams: int = 1
    decoder_type: Optional[str] = None
    audio_max_len: float = 30.0
    audio_min_len: float = 0.0
    cif_ckpt_path: Optional[str] = None
    never_fire: bool = False
    init_prompt: Optional[str] = None
    static_init_prompt: Optional[str] = None
    max_context_tokens: Optional[int] = None
    logprob_threshold: Optional[float] = None
    compression_ratio_threshold: Optional[float] = None
    trace_tokens: bool = False
    periodic_lang_check_secs: Optional[float] = None
    lang_restrict_koen: bool = True
    silence_grammar_gate: bool = True
    silence_hard_secs: Optional[float] = None

    # Diarization — Sortformer
    sortformer_model: str = "nvidia/diar_streaming_sortformer_4spk-v2"

    # Diarization (diart)
    segmentation_model: str = "pyannote/segmentation-3.0"
    embedding_model: str = "pyannote/embedding"

    # Translation
    nllb_backend: str = "transformers"
    nllb_size: str = "600M"

    # LLM translation (parse_args --llm-translation 계열; config 누락으로 from_namespace에서 버려지던 버그 수정)
    # 기본값 = 배포 PC(llama.cpp, gpt-oss-20b) 대상. dev Ollama는 parse_args 플래그로 재정의.
    llm_translation: bool = True
    translation_serve: str = "llama"
    translation_endpoint: str = "http://localhost:2010"
    translation_model: str = "gpt-oss-20b"

    # vLLM Realtime backend
    vllm_url: str = "ws://localhost:8000/v1/realtime"
    vllm_model: str = ""

    def __post_init__(self):
        # .en model suffix forces English
        if self.model_size and self.model_size.endswith(".en"):
            self.lan = "en"
        # Normalize backend_policy aliases
        if self.backend_policy == "1":
            self.backend_policy = "simulstreaming"
        elif self.backend_policy == "2":
            self.backend_policy = "localagreement"

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_namespace(cls, ns) -> "WhisperLiveKitConfig":
        """Create config from an argparse Namespace, ignoring unknown keys."""
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in vars(ns).items() if k in known})

    @classmethod
    def from_kwargs(cls, **kwargs) -> "WhisperLiveKitConfig":
        """Create config from keyword arguments; warns on unknown keys."""
        known = {f.name for f in fields(cls)}
        unknown = set(kwargs.keys()) - known
        if unknown:
            logger.warning("Unknown config keys ignored: %s", unknown)
        return cls(**{k: v for k, v in kwargs.items() if k in known})
