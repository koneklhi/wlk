
from argparse import ArgumentParser, BooleanOptionalAction


def _optional_float(value):
    """'none'/'None' 문자열은 None으로, 그 외는 float로 파싱 (CLI에서 진짜 비활성 전달용)."""
    if value.lower() == "none":
        return None
    return float(value)


def create_parser():
    # 아래 경로 기본값(model_dir/warmup/sortformer)은 저장소 루트 기준 상대경로다. 서버를 루트에서 실행할 것.
    parser = ArgumentParser(description="Whisper FastAPI Online Server")
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="The host address to bind the server to.",
    )
    parser.add_argument(
        "--port", type=int, default=8900, help="The port number to bind the server to. (기본값 8900: master 배포 설정)"
    )
    parser.add_argument(
        "--frontend-dir",
        type=str,
        default="frontend/static",
        dest="frontend_dir",
        help="React 프론트엔드 dist 서빙 루트 디렉터리 (기본값: frontend/static, 저장소 루트 기준 상대경로."
        " 절대경로로 오버라이드 가능). 이 디렉터리에 index.html이 있으면 GET /에서 React dist를 서빙하고"
        " /assets를 마운트한다. 없으면(개발 환경 등) 기존 내장 데모 UI로 폴백한다.",
    )
    parser.add_argument(
        "--frontend-base",
        type=str,
        default="auto",
        dest="frontend_base",
        help="React dist 서빙 base 경로. 기본값 'auto'는 index.html의 자산 참조에서 자동 추출(예: /wlkies)."
        " 빈 문자열 또는 '/'는 루트 서빙, '/wlkies' 등으로 명시 오버라이드 가능. dist가 Vite base로 빌드된 경우"
        " 그 base 하위에서 자산·SPA를 서빙해 자산 절대경로 URL을 맞춘다.",
    )
    parser.add_argument(
        "--warmup-file",
        type=str,
        default="test_data/sbs1_10s.mp3",
        dest="warmup_file",
        help="""
        The path to a speech audio wav file to warm up Whisper so that the very first chunk processing is fast.
        기본값 test_data/sbs1_10s.mp3 (저장소 루트 기준 상대경로). If empty, no warmup is performed.
        """,
    )

    parser.add_argument(
        "--confidence-validation",
        action="store_true",
        help="Accelerates validation of tokens using confidence scores. Transcription will be faster but punctuation might be less accurate.",
    )

    parser.add_argument(
        "--diarization",
        action=BooleanOptionalAction,
        default=True,
        help="화자분할 활성(기본 ON). 끄려면 --no-diarization.",
    )

    parser.add_argument(
        "--punctuation-split",
        action="store_true",
        default=False,
        help="Use punctuation marks from transcription to improve speaker boundary detection. Requires both transcription and diarization to be enabled.",
    )

    parser.add_argument(
        "--segmentation-model",
        type=str,
        default="pyannote/segmentation-3.0",
        help="Hugging Face model ID for pyannote.audio segmentation model.",
    )

    parser.add_argument(
        "--embedding-model",
        type=str,
        default="pyannote/embedding",
        help="Hugging Face model ID for pyannote.audio embedding model.",
    )

    parser.add_argument(
        "--diarization-backend",
        type=str,
        default="sortformer",
        choices=["sortformer", "diart"],
        help="The diarization backend to use.",
    )

    parser.add_argument(
        "--sortformer-model",
        type=str,
        default="whisperlivekit/model/sortformer-4spk-v2.nemo",
        help="Sortformer model: HF model name or local .nemo file path. 기본값 = 로컬 .nemo(저장소 루트 기준 상대경로).",
    )

    parser.add_argument(
        "--no-transcription",
        action="store_true",
        help="Disable transcription to only see live diarization results.",
    )

    parser.add_argument(
        "--disable-punctuation-split",
        action="store_true",
        help="Disable the split parameter.",
    )

    parser.add_argument(
        "--min-chunk-size",
        type=float,
        default=0.1,
        help="Minimum audio chunk size in seconds. It waits up to this time to do processing. If the processing takes shorter time, it waits, otherwise it processes the whole segment that was received by this time.",
    )

    parser.add_argument(
        "--model",
        type=str,
        default="base",
        dest='model_size',
        help="Name size of the Whisper model to use (default: tiny). Suggested values: tiny.en,tiny,base.en,base,small.en,small,medium.en,medium,large-v1,large-v2,large-v3,large,large-v3-turbo. The model is automatically downloaded from the model hub if not present in model cache dir.",
    )

    parser.add_argument(
        "--model_cache_dir",
        type=str,
        default=None,
        help="Overriding the default model cache dir where models downloaded from the hub are saved",
    )
    parser.add_argument(
        "--model_dir",
        type=str,
        default="whisperlivekit/model/whisper-large-v3-turbo",
        help="Dir where Whisper model.bin and other files are saved. This option overrides --model and --model_cache_dir parameter. 기본값 = 로컬 turbo 경로(저장소 루트 기준 상대경로).",
    )
    parser.add_argument(
        "--lora-path",
        type=str,
        default=None,
        dest="lora_path",
        help="Path or Hugging Face repo ID for LoRA adapter weights (e.g., QuentinFuxa/whisper-base-french-lora). Only works with native Whisper backend.",
    )
    parser.add_argument(
        "--lan",
        "--language",
        type=str,
        default="auto",
        dest='lan',
        help="Source language code, e.g. en,de,cs, or 'auto' for language detection.",
    )
    parser.add_argument(
        "--direct-english-translation",
        action="store_true",
        default=False,
        help="Use Whisper to directly translate to english.",
    )

    parser.add_argument(
        "--target-language",
        type=str,
        default="",
        dest="target_language",
        help="Target language for translation. Not functional yet.",
    )

    parser.add_argument(
        "--backend-policy",
        type=str,
        default="simulstreaming",
        choices=["1", "2", "simulstreaming", "localagreement"],
        help="Select the streaming policy: 1 or 'simulstreaming' for AlignAtt, 2 or 'localagreement' for LocalAgreement.",
    )
    parser.add_argument(
        "--backend",
        type=str,
        default="whisper",
        choices=["auto", "mlx-whisper", "faster-whisper", "whisper", "openai-api", "voxtral", "voxtral-mlx", "qwen3", "qwen3-mlx", "qwen3-mlx-simul", "qwen3-simul", "vllm-realtime"],
        help="Select the ASR backend implementation. Use 'qwen3-mlx-simul' for Qwen3-ASR SimulStreaming on Apple Silicon (MLX). Use 'qwen3-mlx' for Qwen3-ASR LocalAgreement on MLX. Use 'qwen3-simul' for Qwen3-ASR SimulStreaming (PyTorch). Use 'vllm-realtime' for vLLM Realtime WebSocket.",
    )
    parser.add_argument(
        "--no-vac",
        action="store_true",
        default=False,
        help="Disable VAC = voice activity controller.",
    )
    parser.add_argument(
        "--vac-chunk-size", type=float, default=0.2, help="VAC sample size in seconds."
    )

    parser.add_argument(
        "--no-vad",
        action="store_true",
        help="Disable VAD (voice activity detection).",
    )

    parser.add_argument(
        "--buffer_trimming",
        type=str,
        default="segment",
        choices=["sentence", "segment"],
        help='Buffer trimming strategy -- trim completed sentences marked with punctuation mark and detected by sentence segmenter, or the completed segments returned by Whisper. Sentence segmenter must be installed for "sentence" option.',
    )
    parser.add_argument(
        "--buffer_trimming_sec",
        type=float,
        default=15,
        help="Buffer trimming length threshold in seconds. If buffer length is longer, trimming sentence/segment is triggered.",
    )
    parser.add_argument(
        "-l",
        "--log-level",
        dest="log_level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the log level",
        default="DEBUG",
    )
    parser.add_argument("--ssl-certfile", type=str, help="Path to the SSL certificate file.", default=None)
    parser.add_argument("--ssl-keyfile", type=str, help="Path to the SSL private key file.", default=None)
    parser.add_argument("--forwarded-allow-ips", type=str, help="Allowed ips for reverse proxying.", default=None)
    parser.add_argument(
        "--transcript-save-dir",
        type=str,
        default="transcripts",
        dest="transcript_save_dir",
        help="종료 시 전사 .txt를 저장할 서버 로컬 폴더 (기본값: ./transcripts). 없으면 자동 생성.",
    )
    parser.add_argument(
        "--pcm-input",
        action="store_true",
        default=False,
        help="If set, raw PCM (s16le) data is expected as input and FFmpeg will be bypassed. Frontend will use AudioWorklet instead of MediaRecorder."
    )
    # vLLM Realtime backend arguments
    parser.add_argument(
        "--vllm-url",
        type=str,
        default="ws://localhost:8000/v1/realtime",
        dest="vllm_url",
        help="URL of the vLLM realtime WebSocket endpoint.",
    )
    parser.add_argument(
        "--vllm-model",
        type=str,
        default="",
        dest="vllm_model",
        help="Model name to use with vLLM (e.g. Qwen/Qwen3-ASR-1.7B).",
    )

    # SimulStreaming-specific arguments
    simulstreaming_group = parser.add_argument_group('SimulStreaming arguments (only used with --backend simulstreaming)')

    simulstreaming_group.add_argument(
        "--disable-fast-encoder",
        action="store_true",
        default=False,
        dest="disable_fast_encoder",
        help="Disable Faster Whisper or MLX Whisper backends for encoding (if installed). Slower but helpful when GPU memory is limited",
    )

    simulstreaming_group.add_argument(
        "--custom-alignment-heads",
        type=str,
        default=None,
        help="Use your own alignment heads, useful when `--model-dir` is used",
    )

    simulstreaming_group.add_argument(
        "--frame-threshold",
        type=int,
        default=None,
        dest="frame_threshold",
        help="Threshold for the attention-guided decoding. The AlignAtt policy will decode only until this number of frames from the end of audio. In frames: one frame is 0.02 seconds for large-v3 model."
        " 기본값(None)은 25 — --scenario 프리셋으로 오버라이드 가능(시나리오 튜닝 Phase A). parse_args()가"
        " 미지정 시 25로 폴백한다(WhisperLiveKitConfig.frame_threshold 기본값과 동일, 무회귀).",
    )

    simulstreaming_group.add_argument(
        "--beams",
        "-b",
        type=int,
        default=2,
        help="Number of beams for beam search decoding. If 1, GreedyDecoder is used.",
    )

    simulstreaming_group.add_argument(
        "--decoder",
        type=str,
        default=None,
        dest="decoder_type",
        choices=["beam", "greedy"],
        help="Override automatic selection of beam or greedy decoder. If beams > 1 and greedy: invalid.",
    )

    simulstreaming_group.add_argument(
        "--audio-max-len",
        type=float,
        default=15.0,
        dest="audio_max_len",
        help="Max length of the audio buffer, in seconds. 기본값 15.0(turbo 기질 Exp-161 채택 — 30.0에서"
        " sbs1 실시간 lag 최대 41s 관측, 15.0으로 lag~2s대 안정화 + WER 3파일 모두 개선/분산 대폭 감소).",
    )

    simulstreaming_group.add_argument(
        "--audio-min-len",
        type=float,
        default=0.0,
        dest="audio_min_len",
        help="Skip processing if the audio buffer is shorter than this length, in seconds. Useful when the --min-chunk-size is small.",
    )

    simulstreaming_group.add_argument(
        "--cif-ckpt-path",
        type=str,
        default=None,
        dest="cif_ckpt_path",
        help="The file path to the Simul-Whisper's CIF model checkpoint that detects whether there is end of word at the end of the chunk. If not, the last decoded space-separated word is truncated because it is often wrong -- transcribing a word in the middle. The CIF model adapted for the Whisper model version should be used. Find the models in https://github.com/backspacetg/simul_whisper/tree/main/cif_models . Note that there is no model for large-v3.",
    )

    simulstreaming_group.add_argument(
        "--never-fire",
        action="store_true",
        default=False,
        dest="never_fire",
        help="Override the CIF model. If True, the last word is NEVER truncated, no matter what the CIF model detects. If False: if CIF model path is set, the last word is SOMETIMES truncated, depending on the CIF detection. Otherwise, if the CIF model path is not set, the last word is ALWAYS trimmed.",
    )

    simulstreaming_group.add_argument(
        "--init-prompt",
        type=str,
        default=None,
        dest="init_prompt",
        help="Init prompt for the model. It should be in the target language.",
    )

    simulstreaming_group.add_argument(
        "--static-init-prompt",
        type=str,
        default=None,
        dest="static_init_prompt",
        help="Do not scroll over this text. It can contain terminology that should be relevant over all document.",
    )

    simulstreaming_group.add_argument(
        "--max-context-tokens",
        type=int,
        default=None,
        dest="max_context_tokens",
        help="Max context tokens for the model. Default is 0.",
    )

    simulstreaming_group.add_argument(
        "--logprob-threshold",
        type=float,
        default=-2.0,
        dest="logprob_threshold",
        help="avg-logprob 품질 게이트 임계값. 낮은 신뢰도 세그먼트 억제. 기본값 -2.0 (Exp-142 채택).",
    )

    simulstreaming_group.add_argument(
        "--compression-ratio-threshold",
        type=float,
        default=3.0,
        dest="compression_ratio_threshold",
        help="compression-ratio 품질 게이트 임계값. 반복 세그먼트 억제. 기본값 3.0(master 설정). None=비활성.",
    )

    simulstreaming_group.add_argument(
        "--model-path",
        type=str,
        default=None,
        dest="model_path",
        help="Direct path to the SimulStreaming Whisper .pt model file. Overrides --model for SimulStreaming backend.",
    )

    simulstreaming_group.add_argument(
        "--nllb-backend",
        type=str,
        default="transformers",
        help="transformers or ctranslate2",
    )

    simulstreaming_group.add_argument(
        "--nllb-size",
        type=str,
        default="600M",
        help="600M or 1.3B",
    )

    simulstreaming_group.add_argument(
        "--trace-tokens",
        action="store_true",
        default=False,
        dest="trace_tokens",
        help="TokenTrace 디버그 로그 활성화: infer/emit 단계별 토큰 목록을 DEBUG 레벨로 출력.",
    )

    simulstreaming_group.add_argument(
        "--periodic-lang-check",
        type=_optional_float,
        default=None,
        dest="periodic_lang_check_secs",
        help="주기적 언어재감지 간격(초). 기본값 None(비활성 — turbo 기질 Exp-160 채택: PLC=4.0이 ytn2에서"
        " 스퓨리어스 전환→환각을 유발함을 N=3로 확인). 수치 지정 시 그 간격(초)으로 재감지, 문자열 'none'으로도 비활성 지정 가능.",
    )

    simulstreaming_group.add_argument(
        "--lang-restrict-koen",
        action=BooleanOptionalAction,
        default=True,
        dest="lang_restrict_koen",
        help="언어 자동감지 후보를 {ko, en}으로 제한. 기본 ON. 끄려면 --no-lang-restrict-koen.",
    )

    simulstreaming_group.add_argument(
        "--silence-grammar-gate",
        action=BooleanOptionalAction,
        default=True,
        dest="silence_grammar_gate",
        help="문법-조건부 침묵 경계 게이트(과분할 억제, Case B 방지). 기본 ON. "
        "롤백/A-B 비교용으로 끄려면 --no-silence-grammar-gate.",
    )

    simulstreaming_group.add_argument(
        "--silence-hard-secs",
        type=float,
        default=None,
        dest="silence_hard_secs",
        help="문법-조건부 침묵 게이트의 안전망 문턱(초) — 이 이상 침묵이면 문법 판정 없이 항상 분할. "
        "기본값(None)은 tokens_alignment.SILENCE_HARD_SECS(현재 1.2s)를 사용. 실험용 스윕 오버라이드, 2.0s 초과 불가.",
    )

    # LLM 번역 인자
    parser.add_argument(
        "--llm-translation",
        action=BooleanOptionalAction,
        default=True,
        dest="llm_translation",
        help="LLM 기반 번역 활성화. 기본 ON(배포 PC llama.cpp). 끄려면 --no-llm-translation.",
    )
    parser.add_argument(
        "--translation-serve",
        type=str,
        default="llama",
        choices=["llama", "ollama"],
        dest="translation_serve",
        help="번역 서버 종류. 기본값 llama(배포 PC llama.cpp). dev Ollama로 바꾸려면 ollama 지정.",
    )
    parser.add_argument(
        "--translation-endpoint",
        type=str,
        default="http://localhost:2010",
        dest="translation_endpoint",
        help="번역 서버 엔드포인트 URL. 기본값: http://localhost:2010 (배포 PC llama.cpp)."
        " dev Ollama는 http://localhost:11434 지정.",
    )
    parser.add_argument(
        "--translation-model",
        type=str,
        default="gpt-oss-20b",
        dest="translation_model",
        help="번역 모델명. 기본값: gpt-oss-20b (배포 PC). dev는 qwen2.5:7b 지정.",
    )

    # 배포 시나리오 튜닝 인자 (Phase A — CLI 승격, 기본값은 기존 하드코딩 상수와 동일).
    # 미지정(None)이면 각 소비 지점의 기존 상수로 폴백한다(무회귀).
    scenario_group = parser.add_argument_group('Scenario tuning arguments (Phase A)')

    scenario_group.add_argument(
        "--min-real-silence-secs",
        type=float,
        default=None,
        dest="min_real_silence_secs",
        help="UI 침묵 경계(Silence 토큰) 생성 최소 길이(초). 기본값(None)은 "
        "audio_processor.MIN_DURATION_REAL_SILENCE(현재 0.4s)를 사용.",
    )
    scenario_group.add_argument(
        "--vad-threshold",
        type=float,
        default=None,
        dest="vad_threshold",
        help="Silero VAD(FixedVADIterator) 민감도 임계값. 기본값(None)은 0.3을 사용.",
    )
    scenario_group.add_argument(
        "--pending-resolve-cap-secs",
        type=float,
        default=None,
        dest="pending_resolve_cap_secs",
        help="문법-조건부 침묵 게이트가 다음 발화 도착을 기다리는 최대 시간(초, safety valve). "
        "기본값(None)은 tokens_alignment.PENDING_RESOLVE_CAP(현재 2.0s)를 사용.",
    )
    scenario_group.add_argument(
        "--min-speaker-attribution-secs",
        type=float,
        default=None,
        dest="min_speaker_attribution_secs",
        help="화자 귀속을 신뢰하는 최소 diarization 세그먼트 길이(초). 기본값(None)은 "
        "tokens_alignment.MIN_SPEAKER_ATTRIBUTION_SECS(현재 0.5s)를 사용.",
    )
    scenario_group.add_argument(
        "--finalize-grace-secs",
        type=float,
        default=None,
        dest="finalize_grace_secs",
        help="침묵 직후 직전 세그먼트 확정을 유예하는 시간(초, 유보 꼬리 도착 대기). "
        "기본값(None)은 tokens_alignment.FINALIZE_GRACE_SECS(현재 2.0s)를 사용.",
    )
    scenario_group.add_argument(
        "--short-lang-reset-secs",
        type=float,
        default=None,
        dest="short_lang_reset_secs",
        help="짧은 침묵 후 언어 재감지를 스케줄링하는 최소 침묵 길이(초). 기본값(None)은 "
        "simul_whisper.backend.MIN_DURATION_SHORT_LANG_RESET(현재 0.5s)를 사용.",
    )
    scenario_group.add_argument(
        "--script-anchor-n-words",
        type=int,
        default=None,
        dest="script_anchor_n_words",
        help="스크립트-앵커 재감지 트리거 연속 반대-스크립트 단어 수 문턱. 기본값(None)은 "
        "simul_whisper.backend._SCRIPT_ANCHOR_N_WORDS(현재 3)를 사용.",
    )
    scenario_group.add_argument(
        "--new-speaker-max-keep-secs",
        type=float,
        default=None,
        dest="new_speaker_max_keep_secs",
        help="화자전환 시 경계 재디코딩을 위해 유지하는 최근 오디오 길이 상한(초). 기본값(None)은 "
        "simul_whisper.backend._NEW_SPEAKER_MAX_KEEP(현재 5.0s)를 사용.",
    )
    scenario_group.add_argument(
        "--lang-detect-general-secs",
        type=float,
        default=None,
        dest="lang_detect_general_secs",
        help="일반(비-eager) 언어감지 누적 오디오 문턱(초). 기본값(None)은 "
        "align_att_base의 general 분기 상수(현재 2.0s)를 사용. eager(화자전환) 분기의 1.5s는 "
        "영향받지 않는다.",
    )
    scenario_group.add_argument(
        "--no-speech-threshold",
        type=float,
        default=None,
        dest="no_speech_threshold",
        help="무음판정 확률 임계값(AlignAttConfig.nonspeech_prob). 세그먼트 시작 시점의 no-speech 확률이 "
        "이 값을 초과하면(>) 무음으로 판정해 해당 세그먼트 디코딩을 즉시 중단한다. 낮추면(↓) 무음 판정이 "
        "관대해져(더 쉽게 무음으로 걸림) 'Thank you' 류 필러 환각이 줄어들지만, 실제로 작게 말한 발화까지 "
        "잘릴 위험이 있다. 높이면(↑) 무음 판정이 엄격해져(더 큰 확률이 필요) 디코딩이 잘 멈추지 않으므로 "
        "필러 환각 위험이 커진다. 기본값(None)은 AlignAttConfig.nonspeech_prob(현재 0.5)를 사용.",
    )

    scenario_group.add_argument(
        "--scenario",
        type=str,
        default=None,
        choices=["mono", "dialogue", "sequential", "codeswitch", "multi"],
        help="배포 음성 상황 프리셋 (mono=단일화자단일언어, dialogue=동일언어2인교대, "
        "sequential=순차통역텀김, codeswitch=코드스위칭텀짧음, multi=다화자겹침). "
        "명시한 개별 플래그가 프리셋 값보다 우선한다.",
    )

    return parser


def parse_args():
    args = create_parser().parse_args()
    args.transcription = not args.no_transcription
    args.vad = not args.no_vad
    args.vac = not args.no_vac
    delattr(args, 'no_transcription')
    delattr(args, 'no_vad')
    delattr(args, 'no_vac')

    from whisperlivekit.scenario_presets import apply_scenario_preset
    args = apply_scenario_preset(args)

    from whisperlivekit.config import WhisperLiveKitConfig
    # --frame-threshold는 시나리오 프리셋 오버라이드를 허용하기 위해 CLI 기본값을 None
    # 센티널로 뒀다(§scenario_presets). CLI/프리셋 둘 다 미지정이면 기존 기본값(25,
    # WhisperLiveKitConfig.frame_threshold와 동일)으로 폴백해 무회귀를 보장한다.
    if args.frame_threshold is None:
        args.frame_threshold = WhisperLiveKitConfig.frame_threshold
    return WhisperLiveKitConfig.from_namespace(args)
