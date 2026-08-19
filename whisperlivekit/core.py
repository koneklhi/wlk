import logging
import threading
from argparse import Namespace
from dataclasses import asdict

from whisperlivekit.config import WhisperLiveKitConfig
from whisperlivekit.local_agreement.online_asr import OnlineASRProcessor
from whisperlivekit.local_agreement.whisper_online import backend_factory
from whisperlivekit.simul_whisper import SimulStreamingASR

logger = logging.getLogger(__name__)

class TranscriptionEngine:
    _instance = None
    _initialized = False
    _lock = threading.Lock()  # Thread-safe singleton lock

    def __new__(cls, *args, **kwargs):
        # Double-checked locking pattern for thread-safe singleton
        if cls._instance is None:
            with cls._lock:
                # Check again inside lock to prevent race condition
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset the singleton so a new instance can be created.

        For testing only — allows switching backends between test runs.
        In production, the singleton should never be reset.
        """
        with cls._lock:
            cls._instance = None
            cls._initialized = False

    def __init__(self, config=None, **kwargs):
        # Thread-safe initialization check
        with TranscriptionEngine._lock:
            if TranscriptionEngine._initialized:
                return

        try:
            self._do_init(config, **kwargs)
        except Exception:
            # Reset singleton so a retry is possible
            with TranscriptionEngine._lock:
                TranscriptionEngine._instance = None
                TranscriptionEngine._initialized = False
            raise

        with TranscriptionEngine._lock:
            TranscriptionEngine._initialized = True

    def _do_init(self, config=None, **kwargs):
        # Handle negated kwargs from programmatic API
        if 'no_transcription' in kwargs:
            kwargs['transcription'] = not kwargs.pop('no_transcription')
        if 'no_vad' in kwargs:
            kwargs['vad'] = not kwargs.pop('no_vad')
        if 'no_vac' in kwargs:
            kwargs['vac'] = not kwargs.pop('no_vac')

        if config is None:
            if isinstance(kwargs.get('config'), WhisperLiveKitConfig):
                config = kwargs.pop('config')
            else:
                config = WhisperLiveKitConfig.from_kwargs(**kwargs)
        self.config = config

        # Backward compat: expose as self.args (Namespace-like) for AudioProcessor etc.
        self.args = Namespace(**asdict(config))

        self.asr = None
        self.tokenizer = None
        self.diarization = None
        self.vac_session = None

        if config.vac:
            from whisperlivekit.silero_vad_iterator import is_onnx_available

            if is_onnx_available():
                from whisperlivekit.silero_vad_iterator import load_onnx_session
                self.vac_session = load_onnx_session()
            else:
                logger.warning(
                    "onnxruntime not installed. VAC will use JIT model which is loaded per-session. "
                    "For multi-user scenarios, install onnxruntime: pip install onnxruntime"
                )

        transcription_common_params = {
            "warmup_file": config.warmup_file,
            "min_chunk_size": config.min_chunk_size,
            "model_size": config.model_size,
            "model_cache_dir": config.model_cache_dir,
            "model_dir": config.model_dir,
            "model_path": config.model_path,
            "lora_path": config.lora_path,
            "lan": config.lan,
            "direct_english_translation": config.direct_english_translation,
        }

        if config.transcription:
            if config.backend == "vllm-realtime":
                from whisperlivekit.vllm_realtime import VLLMRealtimeASR
                self.tokenizer = None
                self.asr = VLLMRealtimeASR(
                    vllm_url=config.vllm_url,
                    model_name=config.vllm_model or "Qwen/Qwen3-ASR-1.7B",
                    lan=config.lan,
                )
                logger.info("Using vLLM Realtime streaming backend at %s", config.vllm_url)
            elif config.backend == "voxtral-mlx":
                from whisperlivekit.voxtral_mlx_asr import VoxtralMLXASR
                self.tokenizer = None
                self.asr = VoxtralMLXASR(**transcription_common_params)
                logger.info("Using Voxtral MLX native backend")
            elif config.backend == "voxtral":
                from whisperlivekit.voxtral_hf_streaming import VoxtralHFStreamingASR
                self.tokenizer = None
                self.asr = VoxtralHFStreamingASR(**transcription_common_params)
                logger.info("Using Voxtral HF Transformers streaming backend")
            elif config.backend == "qwen3-mlx-simul":
                from whisperlivekit.qwen3_mlx_simul import Qwen3MLXSimulStreamingASR
                self.tokenizer = None
                self.asr = Qwen3MLXSimulStreamingASR(
                    **transcription_common_params,
                    alignment_heads_path=config.custom_alignment_heads,
                    border_fraction=getattr(config, 'border_fraction', 0.15),
                )
                logger.info("Using Qwen3 MLX SimulStreaming backend")
            elif config.backend == "qwen3-mlx":
                from whisperlivekit.qwen3_mlx_asr import Qwen3MLXASR
                self.tokenizer = None
                self.asr = Qwen3MLXASR(**transcription_common_params)
                logger.info("Using Qwen3 MLX native backend")
            elif config.backend == "qwen3-simul-kv":
                from whisperlivekit.qwen3_simul_kv import Qwen3SimulKVASR
                self.tokenizer = None
                self.asr = Qwen3SimulKVASR(
                    **transcription_common_params,
                    alignment_heads_path=config.custom_alignment_heads,
                    border_fraction=getattr(config, 'border_fraction', 0.25),
                )
                logger.info("Using Qwen3-ASR backend with SimulStreaming+KV policy")
            elif config.backend == "qwen3-simul":
                from whisperlivekit.qwen3_simul import Qwen3SimulStreamingASR
                self.tokenizer = None
                self.asr = Qwen3SimulStreamingASR(
                    **transcription_common_params,
                    alignment_heads_path=config.custom_alignment_heads,
                )
                logger.info("Using Qwen3-ASR backend with SimulStreaming policy")
            elif config.backend == "qwen3":
                from whisperlivekit.qwen3_asr import Qwen3ASR
                self.asr = Qwen3ASR(**transcription_common_params)
                self.asr.confidence_validation = config.confidence_validation
                self.asr.tokenizer = None
                self.asr.buffer_trimming = config.buffer_trimming
                self.asr.buffer_trimming_sec = config.buffer_trimming_sec
                self.asr.backend_choice = "qwen3"
                from whisperlivekit.warmup import warmup_asr
                warmup_asr(self.asr, config.warmup_file)
                logger.info("Using Qwen3-ASR backend with LocalAgreement policy")
            elif config.backend_policy == "simulstreaming":
                simulstreaming_params = {
                    "disable_fast_encoder": config.disable_fast_encoder,
                    "custom_alignment_heads": config.custom_alignment_heads,
                    "frame_threshold": config.frame_threshold,
                    "beams": config.beams,
                    "decoder_type": config.decoder_type,
                    "audio_max_len": config.audio_max_len,
                    "audio_min_len": config.audio_min_len,
                    "cif_ckpt_path": config.cif_ckpt_path,
                    "never_fire": config.never_fire,
                    "init_prompt": config.init_prompt,
                    "static_init_prompt": config.static_init_prompt,
                    "max_context_tokens": config.max_context_tokens,
                    "logprob_threshold": config.logprob_threshold,
                    "compression_ratio_threshold": config.compression_ratio_threshold,
                    "lang_restrict_koen": config.lang_restrict_koen,
                    "short_lang_reset_secs": config.short_lang_reset_secs,
                    "script_anchor_n_words": config.script_anchor_n_words,
                    "new_speaker_max_keep_secs": config.new_speaker_max_keep_secs,
                    "lang_detect_general_secs": config.lang_detect_general_secs,
                    "no_speech_threshold": config.no_speech_threshold,
                    "quality_gate_reset_after": config.quality_gate_reset_after,
                }

                self.tokenizer = None
                self.asr = SimulStreamingASR(
                    **transcription_common_params,
                    **simulstreaming_params,
                    backend=config.backend,
                )
                logger.info(
                    "Using SimulStreaming policy with %s backend",
                    getattr(self.asr, "encoder_backend", "whisper"),
                )
            else:
                whisperstreaming_params = {
                    "buffer_trimming": config.buffer_trimming,
                    "confidence_validation": config.confidence_validation,
                    "buffer_trimming_sec": config.buffer_trimming_sec,
                }

                self.asr = backend_factory(
                    backend=config.backend,
                    **transcription_common_params,
                    **whisperstreaming_params,
                )
                logger.info(
                    "Using LocalAgreement policy with %s backend",
                    getattr(self.asr, "backend_choice", self.asr.__class__.__name__),
                )

        if config.diarization:
            if config.diarization_backend == "diart":
                from whisperlivekit.diarization.diart_backend import DiartDiarization
                self.diarization_model = DiartDiarization(
                    block_duration=config.min_chunk_size,
                    segmentation_model=config.segmentation_model,
                    embedding_model=config.embedding_model,
                )
            elif config.diarization_backend == "sortformer":
                from whisperlivekit.diarization.sortformer_backend import SortformerDiarization
                self.diarization_model = SortformerDiarization(config.sortformer_model)

        self.translation_model = None
        if config.target_language:
            if config.lan == 'auto' and config.backend_policy != "simulstreaming":
                raise ValueError('Translation cannot be set with language auto when transcription backend is not simulstreaming')
            else:
                try:
                    from nllw import load_model
                except ImportError:
                    raise ImportError('To use translation, you must install nllw: `pip install nllw`')
                self.translation_model = load_model(
                    [config.lan],
                    nllb_backend=config.nllb_backend,
                    nllb_size=config.nllb_size,
                )

        # Stage 2 RAG(Qdrant 유사 예시 검색) 매니저를 서버 기동 시 1회 준비한다.
        # 자산 경로는 whisperlivekit/llm_translation/__init__.py에 고정돼 있고, 그 디렉터리가
        # 실제로 있으면 켜지고 없으면 조용히 비활성화된다(설정 불필요). 여기서 미리 부르는
        # 이유는 bge-m3 로드가 수 초 걸려서다 — 첫 확정 문장 번역이 그 지연을 물면 안 된다.
        # try/except: RAG는 부가 기능이므로 어떤 이유로 못 뜨든 서버 기동을 막아선 안 된다.
        # TranscriptionEngine.__init__은 예외를 그대로 re-raise하므로 여기가 마지막 방어선이다.
        if config.llm_translation:
            try:
                from whisperlivekit.llm_translation import get_rag_manager
                rag_manager = get_rag_manager()
                logger.info(
                    "Translation RAG(Qdrant) %s", "enabled" if rag_manager.enabled else "disabled"
                )
            except Exception as e:
                logger.warning(
                    "Translation RAG(Qdrant) disabled: warm-up failed (%s: %s)", type(e).__name__, e
                )


def online_factory(args, asr, language=None):
    """Create an online ASR processor for a session.

    Args:
        args: Configuration namespace.
        asr: Shared ASR backend instance.
        language: Optional per-session language override (e.g. "en", "fr", "auto").
            If provided and the backend supports it, transcription will use
            this language instead of the server-wide default.

    Note:
        SimulStreaming/LocalAgreement(qwen3)만 세션 언어 오버라이드 실효.
        qwen3-simul/voxtral/vllm 계열은 asr.cfg.language를 직접 읽어 오버라이드
        무효(알려진 한계).
    """
    backend = getattr(args, 'backend', None)
    # SimulStreaming은 세션 cfg에서 언어를 직접 적용한다(SessionASRProxy는 transcribe()만
    # 가로채는데 SimulStreaming은 infer()를 호출해 프록시가 무효). 그 외 백엔드는 프록시 사용.
    _is_simulstreaming = args.backend_policy == "simulstreaming" and backend not in (
        "vllm-realtime", "qwen3-simul-kv", "qwen3-mlx-simul", "qwen3-mlx",
        "qwen3-simul", "voxtral-mlx", "voxtral", "qwen3",
    )
    if language is not None and not _is_simulstreaming:
        from whisperlivekit.session_asr_proxy import SessionASRProxy
        asr = SessionASRProxy(asr, language)
    if backend == "vllm-realtime":
        from whisperlivekit.vllm_realtime import VLLMRealtimeOnlineProcessor
        return VLLMRealtimeOnlineProcessor(asr)
    if backend == "qwen3-simul-kv":
        from whisperlivekit.qwen3_simul_kv import Qwen3SimulKVOnlineProcessor
        return Qwen3SimulKVOnlineProcessor(asr)
    if backend == "qwen3-mlx-simul":
        from whisperlivekit.qwen3_mlx_simul import Qwen3MLXSimulStreamingOnlineProcessor
        return Qwen3MLXSimulStreamingOnlineProcessor(asr)
    if backend == "qwen3-mlx":
        from whisperlivekit.qwen3_mlx_asr import Qwen3MLXOnlineProcessor
        return Qwen3MLXOnlineProcessor(asr)
    if backend == "qwen3-simul":
        from whisperlivekit.qwen3_simul import Qwen3SimulStreamingOnlineProcessor
        return Qwen3SimulStreamingOnlineProcessor(asr)
    if backend == "voxtral-mlx":
        from whisperlivekit.voxtral_mlx_asr import VoxtralMLXOnlineProcessor
        return VoxtralMLXOnlineProcessor(asr)
    if backend == "voxtral":
        from whisperlivekit.voxtral_hf_streaming import VoxtralHFStreamingOnlineProcessor
        return VoxtralHFStreamingOnlineProcessor(asr)
    if backend == "qwen3":
        return OnlineASRProcessor(asr)
    if args.backend_policy == "simulstreaming":
        from whisperlivekit.simul_whisper import SimulStreamingOnlineProcessor
        return SimulStreamingOnlineProcessor(asr, language=language)
    return OnlineASRProcessor(asr)


def online_diarization_factory(args, diarization_backend):
    if args.diarization_backend == "diart":
        online = diarization_backend
        # Not the best here, since several user/instances will share the same backend, but diart is not SOTA anymore and sortformer is recommended
    elif args.diarization_backend == "sortformer":
        from whisperlivekit.diarization.sortformer_backend import SortformerDiarizationOnline
        online = SortformerDiarizationOnline(shared_model=diarization_backend)
    else:
        raise ValueError(f"Unknown diarization backend: {args.diarization_backend}")
    return online


def online_translation_factory(args, translation_model):
    #should be at speaker level in the future:
    #one shared nllb model for all speaker
    #one tokenizer per speaker/language
    from nllw import OnlineTranslation
    return OnlineTranslation(translation_model, [args.lan], [args.target_language])
