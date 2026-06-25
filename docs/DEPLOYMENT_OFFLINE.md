# 폐쇄망 배포 가이드 (오프라인 반입 · 서버 기동 · 테스트)

> **대상 독자**: 폐쇄망(RTX 5090, 오프라인) 배포 PC 운영자.
> **목적**: 개발 PC(RTX 3080, 온라인)에서 라이브러리·모델을 준비해 USB로 옮기고, 폐쇄망에서
> **master(가장 좋은 버전)** 실시간 STT를 켜서 경로 C(자동)·경로 B(마이크)로 검증하기까지의 전 과정.
> 폐쇄망에선 Claude 자동화가 불가하므로 **모든 명령을 복붙 가능**하게 정리했다.
>
> 관련 문서: [TESTING.md](TESTING.md)(경로 정의) · [MASTER_CHANGES.md](MASTER_CHANGES.md)(master 변경요약) ·
> [TRANSLATION_SETUP.md](TRANSLATION_SETUP.md)(번역) · [FRONTEND_HANDOFF.md](FRONTEND_HANDOFF.md)(React 연결).

---

## 0. 빠른 경로 (이미 환경이 갖춰진 경우)

```powershell
# (1) master 설정으로 경로 C 자동 테스트 — 음성 넣으면 정답 있으면 비교, 없으면 전사 저장
python scripts/closed_test.py <음성파일_또는_폴더>

# (2) 경로 B (마이크 직접) — 서버 켜고 브라우저로 말하기
whisperlivekit-server --model_dir whisperlivekit/model/whisper-large-v3-turbo --backend whisper --lan auto `
  --host localhost --port 8000 --warmup-file test_data/sbs1_10s.mp3 `
  --diarization --diarization-backend sortformer `
  --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo `
  --compression-ratio-threshold 3.0 --periodic-lang-check 4.0
# → 브라우저에서 http://localhost:8000/ 접속 후 마이크로 발화
```

환경 준비가 안 됐다면 아래 §1~§4를 순서대로 따른다.

---

## 1. 무엇을 USB로 옮기는가 (반입 체크리스트)

| # | 항목 | 내용 / 경로 | 비고 |
|---|---|---|---|
| 1 | **소스 코드** | 이 저장소 전체(`whisperlivekit/`, `scripts/`, `test_data/`, `docs/`, `pyproject.toml`, `uv.lock`) | `feat/closed-network-deploy` 머지된 master 권장(§5 번역 수정 포함) |
| 2 | **STT 모델** | `whisperlivekit/model/whisper-large-v3-turbo/` (≈1.6GB, `model.safetensors`+토크나이저) | 이미 저장소에 동봉됨 → 코드와 함께 이동 |
| 3 | **화자분할 모델** | `whisperlivekit/model/sortformer-4spk-v2.nemo` | 이미 저장소에 동봉됨 |
| 4 | **번역 LLM** | `gpt-oss-20b-F16.gguf` (≈40GB) + `start_oss.bat` | **저장소 외부** — 별도로 USB에 담아 배포 PC에 배치 |
| 5 | **의존성 wheelhouse** | `wheelhouse/` + `dist/*.whl` (§2에서 생성) | 오프라인 pip 설치용 |
| 6 | **playwright 브라우저** | `%USERPROFILE%\AppData\Local\ms-playwright\` (chromium) | 경로 C 자동화에 필요 |
| 7 | **시스템 바이너리** | `ffmpeg.exe`(PATH 등록), VBCable 드라이버 설치본 | ffmpeg=WebM/mp3 디코딩, VBCable=경로 C 루프백 |

> `whisperlivekit/model/whisper-large-v3/`(turbo 아님) 폴더와 그 안의 `.cache/huggingface/download/*.lock` 잔재는
> **배포에 불필요**하다. 용량 절약 차 제외해도 된다(실제 사용 모델은 turbo).

---

## 2. 오프라인 의존성 패키징 (개발 PC에서)

### 2.1 폐쇄망에서 켤 기능별 필요 extra

| 기능 | 필요한 것 | pyproject extra |
|---|---|---|
| STT 기본(전사) | base deps (fastapi, faster-whisper, torch/torchaudio cu128, tiktoken, safetensors …) | (기본) |
| 화자분할(sortformer) | `nemo-toolkit[asr]` (**무겁다** — lightning/hydra 등 다수 의존) | `diarization-sortformer` |
| 경로 C 자동측정 | `playwright`, `comtypes` (+chromium 바이너리) | `vbcable` |
| 번역(LLM) | `httpx` (이미 `uv.lock`에 포함) | (별도 extra 불필요) |
| GPU(RTX 30/50) | torch/torchaudio **cu128** 휠 | `cu128` |

> `listen`(sounddevice) extra는 별도 CLI 청취 모드용으로 **경로 B/C에는 불필요**(경로 B는 브라우저 마이크, 경로 C는 VBCable+브라우저).
> `translation`(`nllw`) extra는 NLLB(`--target-language`) 경로용으로 **LLM 번역(gpt-oss)에는 불필요**.

### 2.2 wheelhouse 만들기 (온라인 개발 PC)

```powershell
# 1) lock된 의존성을 requirements로 내보내기 (배포에서 켤 extra 포함)
uv export --frozen --no-dev --extra diarization-sortformer --extra vbcable --extra cu128 -o requirements-deploy.txt

# 2) 모든 wheel 다운로드 (torch cu128 인덱스 포함)
uv pip download -r requirements-deploy.txt -d wheelhouse
#   ↳ 설치된 uv가 download 서브커맨드를 지원 안 하면 pip 사용:
#   python -m pip download -r requirements-deploy.txt -d wheelhouse `
#       --extra-index-url https://download.pytorch.org/whl/cu128

# 3) 프로젝트 자체도 wheel로 빌드
uv build --wheel        # → dist/whisperlivekit-0.2.20-*.whl

# 4) 경로 C 자동화용 브라우저
python -m playwright install chromium    # → %USERPROFILE%\AppData\Local\ms-playwright\
```

> ⚠️ **반드시 개발 PC에서 1회 검증**: `wheelhouse/`에 torch cu128, `nemo-toolkit`과 그 전이 의존성까지
> **빠짐없이** 받아졌는지 확인하라(nemo는 의존성이 매우 많다). 빠진 wheel이 있으면 폐쇄망 설치가 중단된다.
> dev/deploy 둘 다 Windows x64 + cu128이므로 wheel 호환은 일반적으로 OK.

### 2.3 RTX 5090(Blackwell) 주의
RTX 5090은 Blackwell(sm_120)이라 **CUDA 12.8+ / cu128 torch**가 필수다. 개발 PC(RTX 3080)에서 받은
cu128 torch wheel의 버전이 **Blackwell 커널을 포함**하는지(torch 2.7+ 계열) 확인하라. 너무 낮은 torch면 5090에서 커널 미지원으로 실패할 수 있다.

---

## 3. 폐쇄망 설치 (배포 PC에서, 오프라인)

```powershell
# 0) 오프라인 환경변수 (런타임 HF/네트워크 호출 차단 — 세션마다 또는 시스템 환경변수로)
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"

# 1) 가상환경 + 오프라인 설치 (USB의 wheelhouse/ + dist/ 사용)
uv venv
uv pip install --no-index --find-links wheelhouse --find-links dist "whisperlivekit[diarization-sortformer,vbcable]"

# 2) playwright 브라우저 배치: USB의 ms-playwright 폴더를
#    %USERPROFILE%\AppData\Local\ms-playwright\ 로 복사
#    (또는) $env:PLAYWRIGHT_BROWSERS_PATH = "D:\ms-playwright"

# 3) ffmpeg.exe 를 PATH에 등록, VBCable 드라이버 설치(경로 C용)

# 4) 설치 확인
python -c "import whisperlivekit, torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"
```

### 3.1 런타임 자동 다운로드 차단 — 핵심 트랩

폐쇄망에서 **HF repo ID 기본값을 그대로 두면 다운로드를 시도**해 실패한다. 아래는 반드시 로컬 경로로 오버라이드:

| 위험 지점 | 기본값(다운로드 시도) | 폐쇄망 조치 | 근거 |
|---|---|---|---|
| Whisper 모델 | `--model base` → HF 다운로드 | **`--model_dir whisperlivekit/model/whisper-large-v3-turbo`** | [parse_args.py:96-115](../whisperlivekit/parse_args.py#L96-L115) |
| Sortformer | `--sortformer-model nvidia/diar_streaming_sortformer_4spk-v2`(HF) | **`--sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo`**(로컬 `.nemo`) | [parse_args.py:70-75](../whisperlivekit/parse_args.py#L70-L75) |
| warmup | `--warmup-file` 미지정 → github에서 `jfk.wav` 다운로드 | **`--warmup-file test_data/sbs1_10s.mp3`**(또는 빈 문자열로 비활성) | [parse_args.py:16-26](../whisperlivekit/parse_args.py#L16-L26) |

**안전 항목(추가 조치 불필요)**:
- `tiktoken` vocab(`whisper/assets/*.tiktoken`), `silero` VAD(`silero_vad_models/*.jit/*.onnx`)는 패키지에 **번들**되어 오프라인 안전([pyproject.toml:152-156](../pyproject.toml#L152-L156)).
- `--segmentation-model`(pyannote)·`--embedding-model`은 **diart 백엔드 전용**이라 sortformer 사용 시 호출되지 않는다.

---

## 4. master "최선" 서버 기동 + 테스트

> master 권장 설정(= [MASTER_CHANGES.md](MASTER_CHANGES.md) Exp-105): 백엔드 SimulStreaming(기본), `--beams 2`(기본),
> `--vac-chunk-size 0.2`(기본), **화자분할 ON**, **`--compression-ratio-threshold 3.0`**, **`--periodic-lang-check 4.0`**.
> `eval.py`/`closed_test.py`가 띄우는 서버도 이 설정과 동일하게 맞춰져 있다([eval.py:108-139](../scripts/eval.py#L108-L139)).
> 서버 진입점은 콘솔 스크립트 `whisperlivekit-server`(= `python -m whisperlivekit.basic_server`)를 쓴다.

### 4.1 경로 C — 자동 전사/평가 (`closed_test.py`) ★요청 기능

음성 파일(또는 폴더)을 넣으면 **경로 C(VBCable 루프백)** 로 자동 전사하고:
- **같은 stem 정답 `.txt`가 있으면** → WER + 문장분리 F1 계산 + 리포트 저장
- **정답이 없으면** → 전사 결과만 로컬 `.txt`로 저장

```powershell
# 단일 파일 (정답 test_data/sbs1.txt 있으면 비교, 없으면 전사 저장)
python scripts/closed_test.py test_data/sbs1.mp3

# 폴더 일괄 (폴더 내 모든 mp3/wav/m4a/flac/ogg)
python scripts/closed_test.py test_data/

# 반복 측정(분산 확인, 채택판단=3) + 결과 폴더 지정
python scripts/closed_test.py my_audio.wav --repeat 3 --out-dir transcripts

# 화자분할 끄기(예: 번역까지 보고 싶을 때 — §5 제약 참조)
python scripts/closed_test.py my_audio.wav --no-diarization
```

- 기본값이 곧 master 설정이다: `--model-dir whisperlivekit/model/whisper-large-v3-turbo`,
  화자분할 ON + `--sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo`,
  `--compression-ratio-threshold 3.0`, `--periodic-lang-check 4.0`. (인자로 덮어쓸 수 있음)
- 결과는 `transcripts/<stem>_<타임스탬프>.txt`에 저장. 정답이 있으면 상단에 WER/F1 median/min/max/stdev 헤더 + 회차별 전사가, 없으면 회차별 전사만 들어간다.
- **전제**: VBCable 드라이버 + playwright(chromium) + comtypes + ffmpeg 설치(§1·§3). VBCable 설정 실패 시 즉시 중단되고 안내가 출력된다.
- 콘솔 출력 예:
  ```
  [closed_test] ▶ sbs1.mp3  (정답 있음 → WER/F1)
  [closed_test]   서버 기동(포트 8001) 회차 1/3 ...
  [closed_test]   → WER 19.6% | F1 76.2%
  ...
  [closed_test] ✓ sbs1.mp3  WER median 19.6% | F1 median 76.2%  → transcripts\sbs1_20260624_....txt
  ```

> `closed_test.py`는 검증된 `scripts/eval.py`의 서버 기동·VBCable 재생·metric 함수를 재사용한다.
> 채택/기각 정량 비교가 목적이면 기존 `scripts/eval.py --repeat 3 --diarization --sortformer-model ... --compression-ratio-threshold 3.0 --periodic-lang-check 4.0`도 그대로 쓸 수 있다(고정 테스트셋 기준).

### 4.2 경로 B — 마이크 직접 (정성 평가)

서버를 master 설정으로 띄우고 브라우저에서 직접 말한다(`--pcm-input` 없음 = 브라우저 MediaRecorder).

```powershell
whisperlivekit-server `
  --model_dir whisperlivekit/model/whisper-large-v3-turbo `
  --backend whisper --lan auto `
  --host localhost --port 8000 `
  --warmup-file test_data/sbs1_10s.mp3 `
  --diarization --diarization-backend sortformer `
  --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo `
  --compression-ratio-threshold 3.0 --periodic-lang-check 4.0
```
→ 브라우저에서 **http://localhost:8000/** 접속 → 내장 웹 UI에서 마이크로 발화, 실시간 전사·화자 확인.

### 4.3 경로 A — 파일 직접 송신 (빠른 스모크, 참고)

VBCable 없이 코드 회귀만 빠르게 보는 용도(성능 판정 아님):
```powershell
# 서버: --pcm-input 으로 기동
whisperlivekit-server --model_dir whisperlivekit/model/whisper-large-v3-turbo --backend whisper --lan auto `
  --pcm-input --warmup-file test_data/sbs1_10s.mp3
# 송신:
$env:PYTHONIOENCODING = "utf-8"
python -m whisperlivekit.test_client test_data/sbs1.mp3 --live
```

---

## 5. 번역(gpt-oss-20b) 배포 설정 — Q3

### 5.1 결론
현재 이식된 번역기(`LlamaTranslator`)는 **프로토콜상 gpt-oss-20b와 호환**된다(`/v1/completions` + harmony 프롬프트 + 완성형 응답 파싱이 원본 whisperlive와 동일, [translator.py:58-93](../whisperlivekit/llm_translation/translator.py#L58-L93)). 다만 **그대로는 켜지지 않는 차단 버그가 있어 선결 수정이 필요**하다.

### 5.2 [필수 수정] config.py LLM 4필드 누락 — `feat/closed-network-deploy`에서 수정됨
- **버그**: `parse_args.py`는 `--llm-translation`/`--translation-serve`/`--translation-endpoint`/`--translation-model`을 파싱하지만([parse_args.py:375-404](../whisperlivekit/parse_args.py#L375-L404)), `WhisperLiveKitConfig`에 해당 4필드가 없어 `from_namespace`가 버렸다([config.py:100-104](../whisperlivekit/config.py#L100-L104)) → `TranslationManager`가 생성되지 않아 **번역이 절대 안 켜졌다**(코드로 4단 체인 확인).
- **수정**: `config.py`에 4필드 추가(`llm_translation`/`translation_serve`/`translation_endpoint`/`translation_model`). → **`feat/closed-network-deploy` 브랜치에 포함**. 배포 전 **master에 머지**해야 번역이 동작한다.

### 5.3 배포 기동 명령 (번역 ON)
전제: 배포 PC에서 `start_oss.bat` 더블클릭 → llama.cpp가 `localhost:2010`에 gpt-oss-20b 서빙.
```powershell
whisperlivekit-server `
  --model_dir whisperlivekit/model/whisper-large-v3-turbo `
  --backend whisper --lan auto --host localhost --port 8000 `
  --warmup-file test_data/sbs1_10s.mp3 `
  --llm-translation `
  --translation-serve llama `
  --translation-endpoint http://localhost:2010 `
  --translation-model gpt-oss-20b
```

### 5.4 ⚠️ 화자분할 ON ↔ 번역 동시 불가 (선택 필요)
- 화자분할 경로가 `finalized=True`를 설정하지 않아([tokens_alignment.py:184-214](../whisperlivekit/tokens_alignment.py#L184-L214)), 번역 매니저가 모든 세그먼트를 건너뛴다([manager.py:38](../whisperlivekit/llm_translation/manager.py#L38)). → **`--diarization`과 `--llm-translation`을 함께 쓰면 번역이 안 붙는다.**
- 현재 선택지: ① **번역 검증은 `--diarization` 빼고**(diar OFF) 수행, ② 화자분할+번역 동시 지원은 Phase 5 후속 과제(`get_lines_diarization`에 화자경계 finalized 부여)로 별도 진행. (자세한 영향은 [FRONTEND_HANDOFF.md §3.4](FRONTEND_HANDOFF.md))

### 5.5 배포 전 점검
```powershell
# llama.cpp 서빙 + 모델 별칭 확인 (gpt-oss-20b vs synatra 별칭 — start_oss.bat -a 값과 일치해야 함)
curl http://localhost:2010/v1/models
```
- 모델명: 문서/코드 기준 `gpt-oss-20b`이나 ROADMAP·원본 메모엔 서빙 별칭 `synatra`가 등장한다. **`/v1/models` 응답의 실제 id로 `--translation-model`을 맞춰라**(단일 모델 서빙이면 보통 무관).
- Windows 한글 전송: `httpx`가 `ensure_ascii` 기본으로 UTF-8 처리해 깨지지 않는다(curl 직접 전송만 깨짐). 첫 기동 시 한↔영 문장 1회로 스모크 권장.

---

## 6. 단어 교정 사전 / 번역 Glossary 파일 — Q1

> **조사 결과, 사용자가 우려한 "파일명이 다름"은 단어 교정 사전에는 해당하지 않았다.**
> 실제 차이는 ① 저장 디렉터리 ② 번역 glossary 미이식 ③ 동봉 데이터가 빈 배열, 세 가지다.

### 6.1 단어 교정 사전 — 파일명은 dev·배포가 **동일**
| 용도 | 파일명 | dev 위치(현재) | 배포 원본 위치 | 근거 |
|---|---|---|---|---|
| 단어대치 base | `admin_replacement.json` | `whisperlivekit/filtering/` | `PROJECT_ROOT/configs/` | [filtering/__init__.py:19](../whisperlivekit/filtering/__init__.py#L19) vs [whisperlive_code/filtering____init__.py:26](../whisperlive_code/filtering____init__.py) |
| 사용자 사전 | `user_replacement.db` | `whisperlivekit/filtering/` | `PROJECT_ROOT/configs/` | [filtering/__init__.py:20](../whisperlivekit/filtering/__init__.py#L20) |
| 환각 목록 | `hallucination.json` | `whisperlivekit/filtering/` | `PROJECT_ROOT/configs/` | [filtering/__init__.py:29](../whisperlivekit/filtering/__init__.py#L29) |

→ **파일명을 바꿀 것은 없다**(이미 100% 동일). 다른 점은 **저장 디렉터리**뿐(`filtering` 모듈 폴더 vs `configs/`).
폐쇄망에선 dev처럼 모듈 폴더에 두면 코드 수정 없이 그대로 동작한다(데이터는 코드와 함께 이동).

### 6.2 [실제 할 일] 빈 데이터 파일을 배포본으로 채우기
현재 동봉된 데이터가 **비어 있다**:
- `whisperlivekit/filtering/admin_replacement.json` → `[]` (빈 배열)
- `whisperlivekit/filtering/hallucination.json` → `[]` (빈 배열)
- `whisperlivekit/filtering/user_replacement.db` → 존재(런타임 자동 생성/갱신)

배포에서 단어 교정이 동작하려면 **배포용 실데이터로 두 JSON을 채워야** 한다(같은 파일명, 내용만 교체):
- `admin_replacement.json` 포맷: **객체 배열** `[{"origin":"6군","replaced":"육군"}, ...]` ([manager.py:37-58](../whisperlivekit/filtering/manager.py#L37-L58)).
- `hallucination.json` 포맷: **문자열 배열** `["감사합니다", ...]`.
- `user_replacement.db`: 기존 사용자 사전을 이어쓰려면 배포 DB 파일 복사, 새로 시작이면 불필요(매니저가 테이블 자동 생성).

### 6.3 번역 Glossary — **미이식**(파일명 교체가 아니라 신규 이식)
배포 원본은 `admin_translation_glossary.json` / `user_translation_glossary.db` + `TranslationPromptManager`를 쓰지만([whisperlive_code/filtering____init__.py:39-44](../whisperlive_code/filtering____init__.py), [whisperlive_code/prompt_manager.py](../whisperlive_code/prompt_manager.py)), **whisperlivekit엔 전혀 이식돼 있지 않다**(파일·클래스·팩토리 부재). 현재 번역기는 정적 군사 프롬프트만 쓴다.

> 사용자 결정(이번 범위: "현재 이식본 유지")에 따라 **glossary 동적주입은 이번 배포 범위 밖**이다.
> 추후 glossary가 필요하면 4단 이식이 필요하다(아래). 이건 "파일명 교체"가 아니라 별도 과제다:
> ① `prompt_manager.py` 이식(`whisperlivekit/llm_translation/prompt_manager.py`) — 원본에 `_load_default_glossary_from_file` 시그니처/`file_path` 버그가 있어 이식 시 수정 필요.
> ② `get_prompt_manager()` 팩토리 추가(base=`admin_translation_glossary.json`, db=`user_translation_glossary.db`).
> ③ `translator.py`에 glossary 주입 연결(원본 [translator.py:114-122](../whisperlive_code/translator.py) 패턴).
> ④ (선택) `/api/prompts` REST 엔드포인트 추가(동적 추가/삭제용).

---

## 7. 배포 점검 순서 (권장)

1. **설치 확인**: `python -c "import whisperlivekit, torch; print(torch.cuda.is_available())"` → `True`.
2. **경로 A 스모크**(§4.3): 파일 송신으로 전사가 나오는지 — 코드/모델 로드 정상 확인.
3. **경로 C 자동**(§4.1): `python scripts/closed_test.py test_data/sbs1.mp3` → WER/F1이 [MASTER_CHANGES §2](MASTER_CHANGES.md) 수치대(sbs1 ≈ WER 20%/F1 76%) 근처인지.
4. **경로 B 마이크**(§4.2): 브라우저에서 한·영 발화 → 화자 배지·실시간 품질 정성 확인.
5. **번역**(§5, 필요 시): config.py 머지 + `start_oss.bat` 후 diar OFF로 번역 ON 기동 → 한↔영 1문장 스모크.
6. **단어 교정**(§6.2): `admin_replacement.json`/`hallucination.json`을 배포본으로 채운 뒤 해당 단어가 교정되는지 확인.

---

## 8. 알려진 트랩 모음

| 트랩 | 증상 | 조치 |
|---|---|---|
| HF repo ID 기본값 | 기동 시 네트워크 시도/실패 | `--model_dir`·`--sortformer-model`(로컬) 명시, `HF_HUB_OFFLINE=1` |
| `--warmup-file` 미지정 | github `jfk.wav` 다운로드 시도 | `--warmup-file test_data/sbs1_10s.mp3` 또는 빈 문자열 |
| 번역 미동작 | `--llm-translation` 줘도 번역 안 붙음 | config.py 4필드 수정 머지(§5.2) |
| diar + 번역 | 화자분할 ON이면 번역 공백 | diar OFF로 번역 검증(§5.4) |
| VBCable 불안정 | 경로 C 무음/100% WER/분산 폭증 | 케이블 상태(코드 아님) — 재부팅/Audiosrv 재시작, `vbcable_test.py --verify` |
| playwright 미설치 | 경로 C 실패 | chromium 바이너리 복사 + `PLAYWRIGHT_BROWSERS_PATH` |
| RTX 5090 커널 | torch가 sm_120 미지원 | cu128 + torch 2.7+ 버전 확인 |
| 포트 충돌 | eval/closed_test는 8001, 수동 경로B는 8000 | 동시 기동 시 GPU 2배 점유 주의 |
| 문서 플래그 오타 | `--avg-logprob-threshold`는 없음 | 실제 플래그는 `--logprob-threshold`([parse_args.py:321](../whisperlivekit/parse_args.py#L321)) |
