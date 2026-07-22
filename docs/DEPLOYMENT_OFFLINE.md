# 폐쇄망 배포 가이드 (오프라인 반입 · 서버 기동 · 테스트)

> **대상 독자**: 폐쇄망 배포 PC(RTX 5090, 오프라인) 운영자 및 협업 PC(RTX 3060, 폐쇄망) 운영자 — 두 PC
> 모두 **동일한 방식**(venv 없이 전용 Python `C:\Python312`에 직접 설치)으로 환경을 세팅한다.
> **목적**: 개발 PC(RTX 3080, 온라인)에서 라이브러리·모델을 준비해 USB로 옮기고, 폐쇄망에서
> **master(가장 좋은 버전)** 실시간 STT를 켜서 내장 UI 전사 → React 프론트 연결 → 번역까지 검증하는 전 과정.
> 폐쇄망에선 Claude 자동화가 불가하므로 **모든 명령을 복붙 가능**하게 정리했다.
> **설치 방식(2026-07-16 확정)**: 회사 DLP(문서보안)가 사용자 프로필 폴더 안 `.venv`/`site-packages`의
> 메타파일을 암호화해 Python 실행을 깨뜨리는 문제를 피하기 위해, **venv를 쓰지 않고** 감시 폴더 밖
> 전용 Python(`C:\Python312`)에 직접 설치한다(§3.0 원리·프로브 참조).
> **번역 기본값(2026-07-16 확정)**: LLM 번역이 **기본 ON**으로 바뀌었다(배포 PC의 llama.cpp `gpt-oss-20b`
> 대상, `--llm-translation` 등 플래그를 따로 줄 필요 없음 — §5 참조). 번역 환경 설정(dev/배포 서버 종류·
> 엔드포인트·모델)은 이 문서 §5로 통합됐다(구 `TRANSLATION_SETUP.md`·`TRANSLATION_DEPLOY_RUNBOOK.md`는 폐지).
>
> 관련 문서: [TESTING.md](TESTING.md)(경로 정의) · [MASTER_CHANGES.md](MASTER_CHANGES.md)(master 변경요약) ·
> [FRONTEND_HANDOFF_SUMMARY.md](FRONTEND_HANDOFF_SUMMARY.md)(React 연결).

---

## 0. 빠른 경로 (이미 환경이 갖춰진 경우)

```powershell
# (0) 오프라인 런타임 안전장치 (세션마다, 또는 시스템 환경변수로 영구 등록)
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"

# (1) master 설정으로 경로 C 자동 테스트 — 음성 넣으면 정답 있으면 비교, 없으면 전사 저장
C:\Python312\python.exe scripts/closed_test.py <음성파일_또는_폴더>

# (2) 경로 B (마이크 직접) — 서버 켜고 브라우저로 말하기
#     master 권장 설정이 parse_args.py 기본값이라 인자 없이 그대로 켜진다.
C:\Python312\python.exe -m whisperlivekit.basic_server
# → 브라우저에서 http://localhost:8900/ 접속 후 마이크로 발화
```

> **⚠️ 항상 저장소 루트에서 실행한다(요청 1).** 기본값의 모델·warmup 경로(`whisperlivekit/model/...`,
> `test_data/sbs1_10s.mp3`)는 **루트 기준 상대경로**다. 다른 폴더에서 띄우면 모델을 못 찾는다.
>
> **venv가 없다** — DLP 회피를 위해 `C:\Python312`에 직접 설치했으므로 활성화 단계 자체가 없다(§3.0).
> 대신 **인터프리터를 항상 `C:\Python312\python.exe`로 명시**한다. `python`(PATH의 다른 Python)으로 실행하면
> `numpy`/`torch` 등을 못 찾는 에러가 난다(§8 트랩 참조). **whisperlivekit 프로젝트 자체는 wheel로 설치하지
> 않으므로 `whisperlivekit-server` 콘솔 스크립트는 존재하지 않는다** — 항상 `python -m
> whisperlivekit.basic_server`를 쓴다(§4 참조).

환경 준비가 안 됐다면 아래 §1~§4를 순서대로 따른다. **처음 반입한다면 §1.1(통째 복사 함정)을 먼저 읽고, 검증은 §4.4의 3단계(전사 → React 프론트 → 번역) 순서를 권장한다.**

---

## 1. 무엇을 USB로 옮기는가 (반입 체크리스트)

| # | 항목 | 내용 / 경로 | 비고 |
|---|---|---|---|
| 1 | **소스 코드** | `whisperlivekit/`, `scripts/`, `test_data/`, `docs/`, `pyproject.toml`, `uv.lock` | **`.git/`·`worktrees/`·`.venv/` 제외** — §1.1의 `git archive` 방식 권장 |
| 2 | **STT 모델** | `whisperlivekit/model/whisper-large-v3-turbo/` (≈1.6GB, `model.safetensors`+토크나이저) | 이미 저장소에 동봉됨 → 코드와 함께 이동 |
| 3 | **화자분할 모델** | `whisperlivekit/model/sortformer-4spk-v2.nemo` | 이미 저장소에 동봉됨 |
| 4 | **번역 LLM** | `gpt-oss-20b-F16.gguf` (≈40GB) + `start_oss.bat` | **배포 PC에 기설치** — 별도 반입 불필요 |
| 5 | **의존성 + 설치도구** | `deploy/` 전체 — `wheelhouse/`(서드파티 의존성 패키지), `uv-installer/`(uv, 선택 — plain pip 설치엔 불필요), `python-installer/`(Python 3.12), `deploy_source.zip`, `requirements-deploy.txt` (§2에서 생성) | 오프라인 pip 설치용. **배포 PC Python은 반드시 3.12** — wheelhouse가 dev(3.12) 태그로 고정됨(§2.2·§3.0). whisperlivekit 프로젝트 자체는 wheel로 만들지 않는다 — raw 소스(①)만으로 실행 |
| 6 | **playwright 브라우저** | `%USERPROFILE%\AppData\Local\ms-playwright\` (chromium) | 경로 C 자동화에 필요 |
| 7 | **시스템 바이너리** | `ffmpeg.exe`(PATH 등록), VBCable 드라이버 설치본 | ffmpeg=WebM/mp3 디코딩, VBCable=경로 C 루프백 |

> `whisperlivekit/model/whisper-large-v3/`(turbo 아님) 폴더와 그 안의 `.cache/huggingface/download/*.lock` 잔재는
> **배포에 불필요**하다. 용량 절약 차 제외해도 된다(실제 사용 모델은 turbo).

### 1.1 ⚠️ "폴더를 통째로 USB에 복사하면 그대로 실행되는가" — 아니다

개발 PC의 `.venv`(editable 설치)를 통째로 복사해 오면 절대경로가 박혀 있어 폐쇄망에서 그대로 깨진다.
**패키지는 절대 복사해오지 않고, 대상 PC의 `C:\Python312`에 wheelhouse에서 새로 설치한다**(§3). USB로는
**소스 코드 + 모델 폴더 + wheelhouse**만 옮기면 된다.

| 구분 | 항목 | 이유 |
|---|---|---|
| ❌ 옮기지 않음 | 개발 PC `.venv/`(전체) | 절대경로(Python 설치 경로·`.venv` 폴더) + editable finder가 **개발 PC 워크트리 경로**를 가리켜 폐쇄망에서 무효. 어차피 §3에서 `C:\Python312`에 새로 설치하므로 옮길 이유 자체가 없음 |
| ❌ 옮기지 않음 | `worktrees/*/.git`, 워크트리 `.venv` Junction | 메인 `.git`·`.venv`를 절대경로로 참조 — **워크트리는 옮길 필요 없음** |
| ✅ 그대로 따라옴 | `whisperlivekit/model/`(≈20GB), `.py` 소스, `pyproject.toml`, `uv.lock` | 절대경로 하드코딩 없음 |

**권장 반입 방식 — `git archive`로 소스만 추출**:

```powershell
# 개발 PC에서 (인터넷 가능, 저장소 루트에서 실행)
# master 브랜치를 명시 — 현재 체크아웃 브랜치(feature 등)에 무관하게 master 기준으로 묶임
git archive master --output=deploy_source.zip
```

`git archive`는 **추적 파일만** zip으로 묶는다 — `.git/`(git 이력 전체)·`worktrees/`·`.venv/`·gitignore된 파일이 **자동 제외**된다. 결과물은 **git 기록·worktree가 없는 깨끗한 단일 폴더** — IDE에서 열면 버전 관리 없는 일반 프로젝트로 보인다. 절대경로 함정 없이 가장 깔끔한 방식이다.

**✅ raw 소스 복사만으로 충분하다**: 서버는 항상 `python -m whisperlivekit.basic_server`(모듈 실행)로
켜고, 이 방식은 cwd(저장소 루트)를 sys.path 최우선에 둔다 — `whisperlivekit/` raw 소스 폴더가 있으면
그게 항상 로드된다. whisperlivekit 프로젝트 자체는 더 이상 wheel로 빌드·설치하지 않으므로 별도 재설치
단계가 없다. **단, 그만큼 파일 복사 누락에 대한 안전장치도 없어졌다** — `whisperlivekit/**` 변경분이
일부라도 복사에서 빠지면 예전처럼 wheel이 백스톱 역할을 해주지 못하고 그대로 stale 코드가 조용히
실행된다. 매 반입 시 `deploy-sync` 6단계의 `diff -q` 검증을 반드시 거친다(§8 트랩 "raw 소스 파일
복사 누락" 참조).

USB에 담을 3가지:

| # | 내용 | 방법 |
|---|---|---|
| ① `deploy/deploy_source.zip` | master 소스 코드 | `git archive master --output=deploy\deploy_source.zip` |
| ② `whisperlivekit/model/` 디렉터리(≈20GB + ≈1.5GB) | STT·화자분할 모델 | `.gitignore` 비추적이라 아카이브에 안 들어옴 → **폴더 수동 복사** |
| ③ `deploy/` 전체 | 서드파티 의존성 패키지+uv 설치도구 | §2에서 생성 (`wheelhouse/`·`uv-installer/` 포함) |

배포 PC에서 unzip 후 §3대로 `C:\Python312`에 오프라인 설치하면 Python 경로가 폐쇄망 기준으로 새로 잡혀 정상 동작한다.

**반복 갱신은 `wlk_in`을 통해 — `SYNC_STATE.txt`로 이력 추적**: 위 방식은 최초 1회 전체 셋업 기준이다.
이후 master에 변경이 쌓이면 매번 `deploy_source.zip`을 통째로 새로 만들 필요 없이, dev PC의 반입
스테이징 디렉터리(`wlk_in`, 저장소 밖 sibling 폴더)를 `/deploy-sync` 절차로 증분 갱신한다.
`wlk_in\SYNC_STATE.txt`가 마지막으로 동기화된 master 커밋·시각·범위를 기록하는 1차 소스다 — 다음
반입 때 이 파일을 기준으로 "무엇이 바뀌었는지"만 diff해 해당 파일만 옮기면 된다. 단, `wlk_in`이
최신이라는 것과 배포 PC가 실제로 그 내용을 반영했다는 것은 별개다(폐쇄망이라 여기서 검증 불가) —
USB 반입·적용 여부는 매번 별도로 확인해야 한다. **`whisperlivekit/**` 변경분은 raw 소스 사본 복사만으로
충분하다** — 위 설명 및 §8 트랩 "raw 소스 파일 복사 누락" 참조. 상세 절차는
`.claude/commands/deploy-sync.md` 참조.

---

## 2. 오프라인 의존성 패키징 (개발 PC에서)

### 2.1 폐쇄망에서 켤 기능별 필요 extra

| 기능 | 필요한 것 | pyproject extra |
|---|---|---|
| STT 기본(전사) | base deps (fastapi, faster-whisper, torch/torchaudio cu128, tiktoken, safetensors …) | (기본) |
| 화자분할(sortformer) | `nemo-toolkit[asr]` (**무겁다** — lightning/hydra 등 다수 의존) | `diarization-sortformer` |
| 경로 C 자동측정 | `playwright`, `comtypes`, **`sounddevice`**(+chromium 바이너리) | `vbcable` |
| 번역(LLM) | `httpx` (이미 `uv.lock`에 포함) | (별도 extra 불필요) |
| GPU(RTX 30/50) | torch/torchaudio **cu128** 휠 | `cu128` |

> **[정정]** 과거 이 문서는 "`listen`(sounddevice) extra는 경로 B/C에 불필요"라고 적었으나 **틀렸다** —
> `scripts/vbcable_test.py`의 `run_browser_test()`가 `sd.play()`로 VBCable Input에 오디오를 재생하는 게
> 경로 C의 실제 재생 메커니즘이라 `sounddevice`는 하드 의존성이다(실사고로 확인, §8 트랩 참조).
> `vbcable` extra에 `sounddevice`를 추가해 바로잡았다. `listen` extra는 여전히 CLI 마이크 청취 모드 전용으로 별개다.
> `translation`(`nllw`) extra는 NLLB(`--target-language`) 경로용으로 **LLM 번역(gpt-oss)에는 불필요**.

### 2.2 deploy/ 폴더 만들기 (온라인 개발 PC)

모든 배포 산출물은 **`deploy/`** 한 폴더에 모인다. USB 반입 시 이 폴더만 통째로 복사하면 된다.

> **⚠️ 반드시 독립 `.venv`에서 실행 — 공유(Junction) `.venv`에 절대 금지.**
> 아래 블록은 `uv export`·`uv pip install pip`·(재생성 시)`uv venv`를 dev `.venv`에 돌린다.
> 워크트리들이 메인 `.venv`를 Junction 공유하므로, 이를 **공유 venv에 실행하면 병렬로 진행 중인
> `/eval` 측정을 clobber**하고, 그 순간 IDE(antigravity Jedi 언어서버)가 `.venv\Scripts\python.exe`를
> 잡고 있으면 **Lib·pyvenv.cfg만 소실되는 반쪽 손상(python.exe exit 106 `No pyvenv.cfg`)**으로
> 악화돼 모든 세션의 측정·pytest가 전면 차단된다(실사고). 따라서 wheelhouse 빌드는:
> 1. **전용 워크트리**를 만들고 Junction을 해제(`rmdir .venv`) 후 **독립 `.venv`** 를 구성(`uv venv` + `uv sync --extra …`)한다(CLAUDE.md 워크트리 규약의 "독립 venv" 예외 케이스).
> 2. **IDE의 Python 인터프리터를 공유 `.venv`에서 분리**(또는 IDE 종료)한 뒤 uv를 실행한다 — 만약의 clobber가 반쪽 손상이 아니라 복구 가능한 클린 상태로 끝난다.
> 3. 손상 발생 시 복구: base python으로 임시 venv를 만들어 그 `pyvenv.cfg`를 `.venv\`에 복사 → python 기동 회복 → `uv sync --extra diarization-sortformer --extra vbcable --extra cu128`로 Lib 재설치(§8 트랩 표 참조).

```powershell
# 0) 폴더 초기화 (최초 1회 또는 재생성 시)
New-Item -ItemType Directory -Force deploy\wheelhouse, deploy\uv-installer | Out-Null

# 1) lock된 의존성을 requirements로 내보내기 (배포에서 켤 extra 포함)
#    --no-emit-project 필수: 빼면 프로젝트 자체가 editable(-e .)로 박혀 hash 모드 pip download가 실패한다.
uv export --frozen --no-dev --no-emit-project `
  --extra diarization-sortformer --extra vbcable --extra cu128 -o deploy\requirements-deploy.txt

# 2) 모든 wheel 다운로드 (torch cu128 인덱스 포함)
#    uv엔 pip download 서브커맨드가 없다. .venv에 pip를 넣고 그 python으로 받는다
#    (배포 타깃과 동일한 마커: Windows AMD64 + 동일 파이썬으로 받아야 한다).
#    ⚠️ 이 명령은 .venv\Scripts\python.exe(= 현재 dev Python 버전, 예: 3.12)의 태그로 wheel을 받는다.
#    컴파일된 wheel(torch·numpy·aiohttp 등)은 그 버전에 고정되므로 배포 PC Python도 반드시 동일 마이너 버전이어야 한다(§3.0).
uv pip install pip
.venv\Scripts\python.exe -m pip download -r deploy\requirements-deploy.txt -d deploy\wheelhouse `
  --extra-index-url https://download.pytorch.org/whl/cu128

# 3) sdist 빌드 백엔드 보강: 일부 의존성(antlr4·docopt·kaldi-python-io·sox·wget 등)은
#    wheel이 없는 sdist라 폐쇄망에서 빌드된다 → setuptools·wheel이 wheelhouse에 있어야 한다.
.venv\Scripts\python.exe -m pip download wheel -d deploy\wheelhouse   # setuptools는 보통 자동 동봉됨

# 4) (선택) uv 설치 파일 준비 — 배포 PC를 plain pip(C:\Python312, §3) 대신 uv 경유로 설치하고 싶을 때만.
#    기본 배포 절차(§3)는 plain pip라 이 단계는 건너뛰어도 된다.
#    4a) standalone binary — pip 없이도 설치 가능
$uvVer = (uv --version).Split(" ")[1]
Invoke-WebRequest -Uri "https://github.com/astral-sh/uv/releases/download/$uvVer/uv-x86_64-pc-windows-msvc.zip" `
  -OutFile "deploy\uv-installer\uv-$uvVer-x86_64-pc-windows-msvc.zip" -UseBasicParsing
#    4b) uv wheel — pip 경유 설치용 (wheelhouse에 포함)
.venv\Scripts\python.exe -m pip download uv -d deploy\wheelhouse

# 5) 소스 아카이브 — HEAD가 아닌 master 명시 (feature 브랜치 체크아웃 중이어도 master 기준으로 묶임)
#    whisperlivekit 프로젝트 자체는 wheel로 빌드하지 않는다 — 이 아카이브(raw 소스)가 배포 PC에서
#    `python -m whisperlivekit.basic_server`로 cwd 우선 로드되는 그대로 실행 대상이다.
git archive master --output=deploy\deploy_source.zip

# 6) 경로 C 자동화용 브라우저
python -m playwright install chromium    # → %USERPROFILE%\AppData\Local\ms-playwright\

# 7) 배포 PC용 Python 설치파일 확보 (배포 PC엔 wheelhouse와 같은 마이너 버전 Python이 없을 수 있음)
New-Item -ItemType Directory -Force deploy\python-installer | Out-Null
Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe" `
  -OutFile "deploy\python-installer\python-3.12.10-amd64.exe" -UseBasicParsing
```

> ⚠️ **반드시 개발 PC에서 1회 검증**: `deploy\wheelhouse\`에 torch cu128(`torch-2.x+cu128-...win_amd64.whl`),
> `nemo-toolkit`과 그 전이 의존성까지 **빠짐없이** 받아졌는지 확인하라(nemo는 의존성이 매우 많다).
> pip 마지막 줄 `Successfully downloaded ...`에 전체 목록이 나오면 OK. 빠진 wheel이 있으면 폐쇄망 설치가 중단된다.
> dev/deploy 둘 다 Windows x64 + cu128이므로 wheel 호환은 일반적으로 OK — **단, Python 마이너 버전은 반드시 일치**시켜야 한다(아래).
> (실측: 192개·약 3.0GB, torch `2.11.0+cu128` 포함. sdist 5개는 위 setuptools+wheel로 폐쇄망에서 빌드됨.)
>
> **wheel 태그 실측 (188개 중)**: `cp312-cp312`(3.12 고정) 46개 + `soxr`(`cp312-abi3`) 1개 + `multiprocess`(`py312-none-any`) 1개
> = **48개가 Python 3.11에서 설치 거부**된다(`cp311` 전용 wheel은 0개). 배포 PC가 3.11이면 `aiohttp` 등에서
> "Python 버전이 안 맞는다" 에러가 난다 — **배포 PC Python을 dev와 동일한 3.12로 맞추는 것이 해결책**(§3.0).

### 2.3 RTX 5090(Blackwell) 주의
RTX 5090은 Blackwell(sm_120)이라 **CUDA 12.8+ / cu128 torch**가 필수다. 개발 PC(RTX 3080)에서 받은
cu128 torch wheel의 버전이 **Blackwell 커널을 포함**하는지(torch 2.7+ 계열) 확인하라. 너무 낮은 torch면 5090에서 커널 미지원으로 실패할 수 있다.

---

## 3. 폐쇄망 설치 (배포 PC / 협업 PC 공통, 오프라인)

> 설치 기준 경로: **`C:\whist\wlk\`**(배포 PC) 또는 해당 PC의 저장소 루트(협업 PC, 예 `C:\wlk`).
> `deploy_source.zip`을 이 경로에 풀고, `deploy/`·`ms-playwright/`·`whisperlivekit/model/` 폴더도 같은 위치에 배치한 뒤 아래 명령을 순서대로 실행한다.
> **venv를 만들지 않는다** — 아래 §3.0의 이유로 전용 Python(`C:\Python312`)에 직접 설치한다.

### 3.0 Python 3.12 설치(venv·uv 없이) + DLP 사전 프로브

#### 왜 venv 없이 전용 Python에 직접 설치하는가 (DLP 회피)

회사 문서보안(DLP) 프로그램은 보통 **사용자 프로필 폴더**(`Desktop`, `Documents`, `Downloads`)를 감시하다가
그 안에서 특정 확장자(`.txt` 등) 파일이 생기면 자동 암호화한다. 저장소가 `Desktop\...\.venv`처럼 프로필
폴더 안에 있으면, `pip install`이 만드는 `RECORD`·`LICENSE.txt`·`entry_points.txt` 같은 메타파일이 걸려
Python이 깨진 파일로 읽고 실행에 실패한다.

**"venv를 안 쓰는 것" 자체가 해결책이 아니다.** 시스템 Python의 `site-packages`에도 똑같이 `.txt`가 생긴다.
**핵심은 설치 위치를 감시 폴더 밖으로 옮기는 것.** 그래서:

- **`C:\Python312`에 wlk 전용 Python 3.12를 새로 깐다**(사용자 프로필 폴더 밖, PATH 미등록).
- 그 `site-packages`에 **venv 없이 직접 설치**한다(§3.1).

→ venv를 안 쓰면서도 전용 인터프리터라 다른 프로그램과 격리된다. 사실상 "venv 없는 격리 환경"이다.

> ⚠️ **단, DLP가 `C:\` 드라이브 전체를 감시하면 이 방법도 무효다.** 아래 프로브로 먼저 확인한다.

#### 착수 전 30초 DLP 프로브 (반드시 먼저)

설치 위치(`C:\`)가 DLP 감시 밖인지 실측한다:

```powershell
"test" | Out-File C:\dlp_probe.txt
Get-Content C:\dlp_probe.txt      # "test" 그대로 나오면 → 감시 밖, 진행
Remove-Item C:\dlp_probe.txt
```

- **"test"가 그대로 출력** → `C:\` 루트는 감시 밖. 아래대로 진행.
- **깨진 문자/암호화 헤더가 출력** → `C:\`까지 감시하는 것. 이 방법 무효 →
  **대안**: (a) WSL2/Docker로 회피, 또는 (b) IT 보안팀에 `C:\Python312` 폴더·`python.exe`
  프로세스를 암호화 예외로 등록 요청.

#### Python 3.12 설치 (`C:\Python312`)

**Python 버전 정합이 먼저다**: §2.2에서 만든 wheelhouse는 dev PC(3.12)의 wheel 태그로 고정돼 있어, 대상 PC가
Python 3.11이면 `aiohttp` 등 46개+ wheel이 설치 거부된다(위 §2.2 경고 참조).

USB의 `deploy\python-installer\python-3.12.10-amd64.exe`를 실행하고 설치 마법사에서:

- ⚠️ **"Add python.exe to PATH" 체크 해제** — 이 PC의 기존 시스템 Python(3.11 등)을 건드리지 않기 위함.
- **"Customize installation"** → 설치 경로를 **`C:\Python312`**로 지정.
- pip 포함(기본 체크 유지). "Install launcher for all users (py)"는 체크해도 무방 — `py.exe`는 버전
  선택기라 기존 Python과의 공존을 해치지 않는다.

설치 확인:
```powershell
C:\Python312\python.exe --version    # Python 3.12.10
C:\Python312\python.exe -m pip --version
```

> **기존 시스템 Python 오염 아님**: `C:\Python312`는 wlk 전용으로 새로 깐 인터프리터(PATH 미등록)라 다른
> 프로그램과 충돌 없음.
>
> **uv가 필요 없다** — plain pip로 설치하므로(§3.1) 이 PC에 uv를 설치할 필요가 없다. uv 경유 설치를
> 굳이 쓰고 싶다면 §2.2에서 준비한 `deploy\uv-installer\`(standalone binary) 또는 wheelhouse의 uv wheel로
> 설치할 수 있으나, 아래 §3.1은 이를 전제하지 않는다.

### 3.1 패키지 설치 (venv 없이 `C:\Python312`에 직접)

```powershell
# 0) 오프라인 환경변수 (런타임 HF/네트워크 호출 차단 — 세션마다 또는 시스템 환경변수로)
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"

# 1) pip 최신화 (오프라인 → wheelhouse에서)
C:\Python312\python.exe -m pip install --no-index --find-links C:\whist\wlk\deploy\wheelhouse --upgrade pip

# 2) 의존성 전체 설치 — venv 없이 C:\Python312\Lib\site-packages 에 직접
#    requirements-deploy.txt = extras(diarization-sortformer·vbcable·cu128) 포함 전체 목록
C:\Python312\python.exe -m pip install --no-index --find-links C:\whist\wlk\deploy\wheelhouse `
  -r C:\whist\wlk\deploy\requirements-deploy.txt

# 3) playwright 브라우저 배치: USB의 ms-playwright 폴더를
#    %USERPROFILE%\AppData\Local\ms-playwright\ 로 복사
#    (또는) $env:PLAYWRIGHT_BROWSERS_PATH = "C:\whist\wlk\ms-playwright"

# 4) ffmpeg.exe 를 PATH에 등록, VBCable 드라이버 설치(경로 C용)

# 5) 설치 확인 — venv 활성화 단계가 없으므로 바로 실행. whisperlivekit는 wheel로 설치되지
#    않았으므로 저장소 루트(C:\whist\wlk)에서 실행해야 raw 소스가 cwd 우선으로 로드된다.
C:\Python312\python.exe -c "import whisperlivekit, torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"
# → 예: torch 2.x+cu128 cuda True  ← cuda True 나오면 성공
```

> **온라인 인덱스가 되는 경우**(내부 미러 또는 인터넷 접근 가능)는 wheelhouse 없이 소스에서 직접
> 설치할 수 있다:
> ```powershell
> C:\Python312\python.exe -m pip install "C:\whist\wlk[diarization-sortformer,vbcable,cu128]" `
>   --extra-index-url https://download.pytorch.org/whl/cu128
> ```
> 코드 수정이 즉시 반영되는 editable가 필요하면 경로 대신 `-e C:\whist\wlk`를 쓴다 — 단 editable는
> `site-packages`에 `.txt`/finder 파일을 남기므로, 그 위치(`C:\Python312`)가 위 DLP 프로브를 통과했는지
> 확인한다. 이 경로를 타더라도 `python -m whisperlivekit.basic_server`로 실행하는 한 cwd의 raw 소스가
> 여전히 우선 로드되므로, whisperlivekit 자체를 이렇게 설치하는 건 필수가 아니라 선택 사항이다.

### 3.2 런타임 자동 다운로드 차단 — 이제 기본값이 로컬 경로

> **변경됨**: 과거엔 아래 3개를 매번 CLI로 오버라이드해야 했으나, 이제 `parse_args.py` **기본값이 로컬 경로**라
> `python -m whisperlivekit.basic_server`만 쳐도 다운로드 시도 없이 켜진다(요청 3). 아래는 그 기본값과 근거 — **추가 조치 불필요**.

| 위험 지점 | 과거 기본값(다운로드 시도) | 현재 기본값(로컬, 자동) | 근거 |
|---|---|---|---|
| Whisper 모델 | `--model base` → HF 다운로드 | **`--model_dir whisperlivekit/model/whisper-large-v3-turbo`** | [parse_args.py](../whisperlivekit/parse_args.py) |
| Sortformer | `nvidia/diar_streaming_sortformer_4spk-v2`(HF) | **`whisperlivekit/model/sortformer-4spk-v2.nemo`**(로컬 `.nemo`) | [parse_args.py](../whisperlivekit/parse_args.py) |
| warmup | 미지정 → github `jfk.wav` 다운로드 | **`test_data/sbs1_10s.mp3`** | [parse_args.py](../whisperlivekit/parse_args.py) |

> 다른 모델로 바꾸려면 해당 플래그를 직접 주면 기본값을 덮어쓴다. `HF_HUB_OFFLINE=1`은 그래도 안전상 권장.

**안전 항목(추가 조치 불필요)**:
- `tiktoken` vocab(`whisper/assets/*.tiktoken`), `silero` VAD(`silero_vad_models/*.jit/*.onnx`)는 패키지에 **번들**되어 오프라인 안전([pyproject.toml:152-156](../pyproject.toml#L152-L156)).
- `--segmentation-model`(pyannote)·`--embedding-model`은 **diart 백엔드 전용**이라 sortformer 사용 시 호출되지 않는다.

---

## 4. master "최선" 서버 기동 + 테스트

> master 권장 설정(= [MASTER_CHANGES.md](MASTER_CHANGES.md) Exp-105, 단 §2 수치 자체는 stale — 위 §7-6 참조): 백엔드 SimulStreaming(기본), `--beams 2`(기본),
> `--vac-chunk-size 0.2`(기본), **화자분할 ON**, **`--compression-ratio-threshold 3.0`**, **`--periodic-lang-check` 기본 None(비활성 — Exp-160, turbo에서 PLC=4.0이 ytn2 환각 유발 확인)**,
> **`--audio-max-len` 기본 15.0초(Exp-161 — turbo 인코더가 base보다 무거워 기존 30.0초 버퍼가 sbs1류 밀집발화에서 최대 41초 실시간 지연 유발, 15.0초로 축소해 2초대로 해결)**.
> **이 설정 전체가 이제 `parse_args.py` 기본값**이라(요청 3) 인자 없이 서버만 켜도 그대로 켜진다.
> 기본 포트는 **8900**(과거 8000), 자동측정(`eval.py`/`closed_test.py`)은 **8901**(과거 8001) — 배포 PC의 기존 8000/8001 점유와 충돌 회피(요청 2).
> 향후 설정 변경은 **CLI를 늘리지 말고 `parse_args.py` 기본값을 고친다**(closed_test도 그 값을 자동 동기화 — 요청 5).
> **저장소 루트에서 실행.** venv가 없으므로(§3) **인터프리터를 직접 지정**해 실행한다:
> `C:\Python312\python.exe -m whisperlivekit.basic_server`. **whisperlivekit 프로젝트는 wheel로 설치되지
> 않으므로 `whisperlivekit-server` 콘솔 스크립트 자체가 존재하지 않는다** — 항상 위 `-m` 형태로 실행한다.
>
> ⚠️ **가상환경 활성화 단계가 없다** — `python`(시스템/PATH의 다른 Python)으로 실행하지 말고 항상
> `C:\Python312\python.exe`를 명시한다(§8 트랩 참조).

### 4.1 경로 C — 자동 전사/평가 (`closed_test.py`) ★요청 기능

음성 파일(또는 폴더)을 넣으면 **경로 C(VBCable 루프백)** 로 자동 전사하고:
- **같은 stem 정답 `.txt`가 있으면** → WER + 문장분리 F1 계산 + 리포트 저장
- **정답이 없으면** → 전사 결과만 로컬 `.txt`로 저장

```powershell
# 단일 파일 (정답 test_data/sbs1.txt 있으면 비교, 없으면 전사 저장)
C:\Python312\python.exe scripts/closed_test.py test_data/sbs1.mp3

# 폴더 일괄 (폴더 내 모든 mp3/wav/m4a/flac/ogg)
C:\Python312\python.exe scripts/closed_test.py test_data/

# 채택 확정용 반복 측정(분산 확인, 채택판단=3) + 결과 폴더 지정
C:\Python312\python.exe scripts/closed_test.py my_audio.wav --repeat 3 --out-dir transcripts

# 화자분할 끄기(예: 번역까지 보고 싶을 때 — §5 제약 참조)
C:\Python312\python.exe scripts/closed_test.py my_audio.wav --no-diarization
```

- 기본값이 곧 master 설정이다: `--model-dir whisperlivekit/model/whisper-large-v3-turbo`,
  화자분할 ON + `--sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo`,
  `--compression-ratio-threshold 3.0`, `--periodic-lang-check` None(비활성, Exp-160). (인자로 덮어쓸 수 있음)
- 결과는 `transcripts/<stem>_<타임스탬프>.txt`에 저장. 정답이 있으면 상단에 WER/F1 median/min/max/stdev 헤더 + 회차별 전사가, 없으면 회차별 전사만 들어간다.
- **전제**: VBCable 드라이버 + playwright(chromium) + comtypes + ffmpeg 설치(§1·§3). VBCable 설정 실패 시 즉시 중단되고 안내가 출력된다.
- 콘솔 출력 예:
  ```
  [closed_test] ▶ sbs1.mp3  (정답 있음 → WER/F1)
  [closed_test]   서버 기동(포트 8901) 회차 1/3 ...
  [closed_test]   → WER 19.6% | F1 76.2%
  ...
  [closed_test] ✓ sbs1.mp3  WER median 19.6% | F1 median 76.2%  → transcripts\sbs1_20260624_....txt
  ```

> `closed_test.py`는 검증된 `scripts/eval.py`의 서버 기동·VBCable 재생·metric 함수를 재사용한다.
> 채택 확정 정량 비교가 목적이면 기존 `scripts/eval.py --repeat 3 --diarization --sortformer-model ... --compression-ratio-threshold 3.0`도 그대로 쓸 수 있다(고정 테스트셋, 채택 확정 N≥3 기준; `--periodic-lang-check`는 기본 None이므로 명시 불필요).

### 4.2 경로 B — 마이크 직접 (정성 평가)

서버를 master 설정으로 띄우고 브라우저에서 직접 말한다(`--pcm-input` 없음 = 브라우저 MediaRecorder).
master 설정이 기본값이라 인자가 없다(저장소 루트에서 실행).

```powershell
C:\Python312\python.exe -m whisperlivekit.basic_server
```
→ 브라우저에서 **http://localhost:8900/** 접속 → 내장 웹 UI에서 마이크로 발화, 실시간 전사·화자 확인.

### 4.3 경로 A — 파일 직접 송신 (빠른 스모크, 참고)

VBCable 없이 코드 회귀만 빠르게 보는 용도(성능 판정 아님):
```powershell
# 서버: --pcm-input 만 추가(나머지는 기본값). 화자분할 빼고 더 빠른 스모크는 --no-diarization 추가.
C:\Python312\python.exe -m whisperlivekit.basic_server --pcm-input
# 송신:
$env:PYTHONIOENCODING = "utf-8"
C:\Python312\python.exe -m whisperlivekit.test_client test_data/sbs1.mp3 --live
```

### 4.4 배포 검증 3단계 (권장 시나리오) ★

기능을 한 번에 다 켜지 말고 **전사 → 프론트 연결 → 번역** 순으로 하나씩 늘려가며 확인한다.
**1·2단계는 playwright/VBCable이 필요 없다**(마이크 직접). 경로 C 자동측정(§4.1)에만 그 둘이 필요하다.

#### 1단계 — whisperlivekit 내장 UI로 전사 확인 (번역 OFF)
master 설정으로 서버를 띄우고, 추가 설치 없이 브라우저만으로 전사·화자분할이 도는지 본다. **번역은 기본
ON이므로(§5) 이 단계에서는 `--no-llm-translation`으로 명시적으로 꺼야 한다** — 안 끄면 아직 켜지 않은
llama.cpp 번역 서버로 연결을 시도한다(실패해도 전사 자체는 안 깨지지만 불필요한 경고 로그가 남는다, §5.7).
```powershell
C:\Python312\python.exe -m whisperlivekit.basic_server --no-llm-translation
```
→ 브라우저 **http://localhost:8900/** 접속(내장 UI) → 마이크 권한 허용 후 한·영 섞어 발화.
- **통과 기준**: 발화가 끊김·환각 없이 실시간 전사되고, 화자가 바뀌면 화자 배지(1·2·3…)가 분리된다.
- 음성 파일로 보려면 VBCable 재생장치를 통해 틀거나(경로 C), 빠른 방법은 마이크 앞에서 직접 발화.
- 저장 버튼을 누르면 내장 UI가 그 시점까지의 누적 전사를 서버 로컬 폴더(`--transcript-save-dir`, 기본값 `./transcripts`)에 `.txt`로 저장한다(녹음 종료 시 자동 저장되지 않음).

#### 2단계 — whisperlive React 프론트 UI 연결
같은 서버(`/asr`)에 기존 whisperlive React UI를 붙인다. 기존 whisperlive와 **달라진 점**만 맞추면 된다 — 상세·코드 위치는 [FRONTEND_HANDOFF_SUMMARY.md](FRONTEND_HANDOFF_SUMMARY.md):

> **정적 서빙 배선 구현 완료**: React 빌드 산출물(dist)을 배포 PC의 `frontend/static/`(즉 `frontend/static/index.html` +
> `frontend/static/assets/...`)에 배치하고 서버를 재기동하면, `GET /`가 내장 데모 UI 대신 그 dist를 자동 서빙한다
> (서빙 루트는 `--frontend-dir`로 변경 가능, 기본값 `frontend/static`). **dist가 Vite `base`(예 `/wlkies`)로 빌드된
> 경우**도 그대로 배치하면 되며, 백엔드가 `index.html`에서 base를 자동 추출해 그 하위(`/wlkies/assets`, `/wlkies/{spa}`)로
> 서빙하고 `GET /`는 base로 리다이렉트한다(`--frontend-base`, 기본값 `auto`; 루트 빌드도 하위호환). dist가 아직 없으면
> 지금처럼 내장 데모 UI로 폴백하므로 이 단계를 건너뛰어도 안전하다. dist를 언제·어떻게 배포 PC로 옮기는지는 별도 반입 절차 소관.

| 맞출 항목 | 신규 whisperlivekit |
|---|---|
| 엔드포인트 | WebSocket **`ws://<host>:<port>/asr`** (기존 SSE/REST 아님) |
| 메시지 모델 | 50ms마다 **전체 스냅샷** `lines[]`(델타 아님) |
| 시간 필드 | `start`/`end`가 **문자열 `"HH:MM:SS"`**(기존 float 아님) — PC 실제 벽시계 시각(녹음 시작 0초 기준 경과시간 아님) |
| 확정 표시 | `finalized`(별칭 `completed`) bool |
| 화자 | `lines[].speaker` int(−2=침묵, 0=diar 로딩중, 1·2·3…=화자) |
| 오디오 송신 | 서버 `config` 메시지의 `useAudioWorklet` 분기 — PCM AudioWorklet(16kHz s16le) 또는 WebM MediaRecorder |

- **통과 기준**: React 화면에 1단계와 동일한 전사·화자가 표시된다.

#### 3단계 — OSS 20b 실행 후 번역 확인
번역기를 마지막에 켠다(1·2단계로 전사가 검증된 뒤). 번역은 **기본 ON**(§5)이라 llama.cpp 서버만 띄우면
되고 추가 플래그는 필요 없다 — 단 실제 서빙 모델 id가 기본값(`gpt-oss-20b`)과 다르면 덮어써야 한다.
```powershell
# (1) llama.cpp 번역 서버 기동 + 실제 서빙 모델 id 확인 (반드시 먼저 — §5.5)
start_oss.bat                        # llama.cpp가 localhost:2010에 서빙 시작
curl http://localhost:2010/v1/models # 실제 모델 id 확인 → gpt-oss-20b와 다르면 --translation-model로 덮어씀

# (2) STT 서버 재기동 — 전사·화자분할·번역 모두 기본값이라 인자 없이 그대로 켜진다
#     (1)에서 확인한 id가 gpt-oss-20b와 다르면: --translation-model <실측 id> 만 추가
C:\Python312\python.exe -m whisperlivekit.basic_server
```
→ React(또는 내장 UI)에서 한↔영 한 문장씩 발화.
- **통과 기준**: 문장이 **확정되는 순간** `lines[].translation`에 번역문이 채워져 표시된다.
- 화자분할 ON 상태에선 화자가 바뀌어야 직전 문장이 확정·번역된다(§5.4 한계). 한 화자만 길게 말하면 번역이 늦으니, 검증은 **두 사람이 번갈아** 또는 짧게 끊어 발화.

### 4.5 배포 상황별 파라미터 튜닝(`--scenario`, Phase A)

현장 음성 상황(화자 수·언어 전환 텀·겹침 여부)에 따라 문장 확정·화자 귀속·언어 재감지 관련 파라미터를
서버 재시작 없이 코드 수정 없이 조정할 수 있다 — `--scenario {mono,dialogue,sequential,codeswitch,multi}`
플래그로 상황별 프리셋을 한 번에 적용한다(예: 다화자 겹침이 많은 현장이면 `multi`).

```powershell
# 다화자·텀 없이 겹치는 상황(bong1류)
C:\Python312\python.exe -m whisperlivekit.basic_server --scenario multi

# 프리셋 + 특정 값만 개별 override(개별 플래그가 프리셋보다 항상 우선)
C:\Python312\python.exe -m whisperlivekit.basic_server --scenario multi --frame-threshold 40
```

`--scenario` 미지정 + 개별 플래그도 미지정이면 기존 마스터와 100% 동일하게 동작한다(무회귀). 프리셋
값은 **미검증 방향값 출발점**이라 배포 현장에서 실제 음성으로 들어보며 미세조정하는 것을 전제로 한다 —
knob별 방향(↑/↓ 효과)·상황별 매트릭스·프리셋 수치 전체는 [OPERATOR_TUNING_GUIDE.md](OPERATOR_TUNING_GUIDE.md)
참조.

---

## 5. 번역(gpt-oss-20b) 배포 설정 — Q3

> 번역 환경 설정 정본. 구 `docs/TRANSLATION_SETUP.md`(환경별 비교표·config.yaml 예시)와
> `docs/TRANSLATION_DEPLOY_RUNBOOK.md`(현장 검증 절차·트러블슈팅)를 이 절로 통합했다(폐지, 2026-07-16).

### 5.1 결론
현재 이식된 번역기(`LlamaTranslator`)는 **프로토콜상 gpt-oss-20b와 호환**된다(`/v1/completions` + harmony 프롬프트 + 완성형 응답 파싱이 원본 whisperlive와 동일, [translator.py:58-93](../whisperlivekit/llm_translation/translator.py#L58-L93)).
확정 문장 번역(`lines[].translation`)뿐 아니라 **중간(미확정) 번역(`buffer_translation`, `TranslationManager.apply_interim_translation()`)도 동일한 `TranslationManager`/`--translation-serve`·`--translation-endpoint`·`--translation-model` 설정으로 동작**한다 — 별도 설정 없이 아래 기본값 그대로 중간 번역도 gpt-oss-20b로 붙는다.

### 5.2 [수정 완료] config.py LLM 4필드 누락 — master 머지됨
- **버그(과거)**: `parse_args.py`는 `--llm-translation`/`--translation-serve`/`--translation-endpoint`/`--translation-model`을 파싱하지만([parse_args.py:375-404](../whisperlivekit/parse_args.py#L375-L404)), `WhisperLiveKitConfig`에 해당 4필드가 없어 `from_namespace`가 버렸다 → `TranslationManager`가 생성되지 않아 **번역이 절대 안 켜졌다**(코드로 4단 체인 확인).
- **수정(완료)**: `config.py`에 4필드 추가(`llm_translation`/`translation_serve`/`translation_endpoint`/`translation_model`, [config.py:85-89](../whisperlivekit/config.py#L85-L89)). master에 머지 완료.

### 5.3 배포/개발 환경 비교 — 번역 **기본 ON**(2026-07-16 확정)

| 환경 | 모델 | 서빙 도구 | 엔드포인트 | `--translation-serve` | 비고 |
|---|---|---|---|---|---|
| **배포(폐쇄망, RTX 5090) — 기본값** | gpt-oss-20b (`gpt-oss-20b-F16.gguf`) | llama.cpp (`start_oss.bat`) | `http://localhost:2010` | `llama` | `parse_args.py`/`config.py` 기본값이 이 환경을 가리킨다 |
| 개발(RTX 3080) | qwen2.5:7b | Ollama | `http://localhost:11434` | `ollama` | 아래 §5.6로 재정의(override) |

**배포 PC 기동 — 인자 없이 그대로**: `--llm-translation`이 **기본 ON**이고 `--translation-serve`/`--translation-endpoint`/`--translation-model` 기본값이 위 배포 PC 값(`llama`/`http://localhost:2010`/`gpt-oss-20b`)이므로, 전제(`start_oss.bat`로 llama.cpp가 `localhost:2010`에 서빙 중)만 갖춰지면 **번역 플래그를 하나도 주지 않아도** 화자분할과 동시에 켜진다(저장소 루트에서 실행).
```powershell
C:\Python312\python.exe -m whisperlivekit.basic_server
```
> 실제 서빙 모델 id가 `gpt-oss-20b`와 다르면(§5.5 — `synatra` 등 별칭 가능) `--translation-model <실측 id>`로 덮어쓴다.
> **번역을 완전히 끄려면** `--no-llm-translation`을 추가한다(§5.6·§8 트랩 참조 — 예: llama.cpp가 아직 안 떠 있는 상태에서 전사만 스모크 테스트할 때).

### 5.4 [수정 완료] 화자분할 ON + 번역 동시 가능
- **과거 버그**: 화자분할 경로가 `finalized=True`를 설정하지 않아 번역 매니저가 모든 세그먼트를 건너뛰어, 화자분할과 번역을 함께 쓰면 번역이 안 붙었다.
- **수정(완료)**: `get_lines_diarization()`이 화자 전환이 끝난 세그먼트(`segments[:-1]`)에 `finalized=True`를 부여한다([tokens_alignment.py:214-216](../whisperlivekit/tokens_alignment.py#L214-L216)). master 머지 완료 → 화자분할 + 번역 **동시 기동 가능**(현재 기본값 그대로가 이 조합).
- **한 가지 한계**: 현재 발화 중인 마지막 세그먼트(`segments[-1]`)는 아직 미확정이라, **다음 화자로 전환되는 순간** 확정되며 번역이 붙는다(화자가 계속 말하는 동안엔 그 문장 번역이 한 박자 늦게 표시됨). 실사용엔 무방하나 동작 특성으로 알아둘 것. (스키마 영향은 [FRONTEND_HANDOFF_SUMMARY.md §5](FRONTEND_HANDOFF_SUMMARY.md))

### 5.5 배포 전 점검 — LLM 서버 격리 스모크 (wlk 기동 전)

wlk를 붙이기 전에 번역 서버 자체가 살아있는지 wlk와 무관하게 먼저 확인한다. 여기서 실패하면 wlk 문제가
아니라 llama.cpp 서버/모델 문제로 원인을 좁힐 수 있다.

```powershell
# 1) 서빙 중인 모델 id 확인 — 기본값(gpt-oss-20b)과 다르면 --translation-model에 이 값을 쓴다
curl http://localhost:2010/v1/models
```
```powershell
# 2) harmony 프롬프트로 completions 1발 직접 호출 — 번역문이 돌아오는지 확인 (model은 1)의 실측 id로 교체)
curl -X POST http://localhost:2010/v1/completions `
  -H "Content-Type: application/json" `
  -d '{
        "model": "gpt-oss-20b",
        "prompt": "<|start|>system<|message|>You are a military professional translator.\n            Rules:\n            1. Always translate the given Korean content into natural, fluent, polite, and formal English.\n            4. Output only the final translated English!!\n            <|end|>\n<|start|>user<|message|>안녕하세요, 오늘 날씨가 좋습니다.<|end|>\n<|start|>assistant<|channel|>final<|message|>",
        "temperature": 0,
        "max_tokens": 128,
        "top_p": 1,
        "top_k": 0,
        "repeat_penalty": 1,
        "stream": false
      }'
```
- 통과 기준: `choices[0].text`에 영어 번역문이 채워진다. 실패(연결 거부/타임아웃/빈 응답)면 llama.cpp 서버·모델
  적재 문제이니 wlk를 켜기 전에 먼저 해결한다.
- **모델 별칭 주의**: 문서/코드 기본값은 `gpt-oss-20b`이나, 과거 구 whisperlive 배포 현장에서 서빙 별칭이
  `synatra`로 관측된 적이 있다(`whisperlive_code/whisper_1023.txt:29` `model_name:'synatra'`). **항상 위 1)
  curl로 실측 확인 후 다르면 `--translation-model`로 덮어쓴다** — 문서 기본값을 맹신하지 말 것.
- Windows 한글 전송: `httpx`(wlk 내부)가 `ensure_ascii` 기본으로 UTF-8 처리해 깨지지 않는다(위 curl 직접
  호출은 인코딩이 깨질 수 있으나 wlk 실사용과 무관). 첫 기동 시 한↔영 문장 1회로 스모크 권장.

### 5.6 개발 환경으로 재정의(override) — Ollama qwen2.5:7b

배포 PC 기본값(§5.3)을 dev PC에서 그대로 쓰면 존재하지 않는 `localhost:2010` 서버로 연결을 시도한다(실패해도
전사 자체는 안 깨지지만 불필요한 경고 로그가 남는다 — 원인은 §5.7 트러블슈팅 참조). dev PC에서는 3개 플래그로
Ollama를 가리키도록 **명시적으로 재정의**한다.

**전제조건**: Ollama 설치 + `ollama pull qwen2.5:7b` 완료.

```powershell
# Ollama 서비스 실행 (이미 실행 중이면 불필요)
ollama serve

# 번역을 dev Ollama로 재정의하여 서버 기동 (전사·화자분할은 기본값 그대로)
C:\Python312\python.exe -m whisperlivekit.basic_server `
  --translation-serve ollama `
  --translation-endpoint http://localhost:11434 `
  --translation-model qwen2.5:7b
```
- Ollama는 `/v1/chat/completions`(messages 형식, harmony 채널 태그 미사용) — llama.cpp(`/v1/completions`,
  harmony 태그)와 프로토콜이 다르므로 `--translation-serve`를 반드시 `ollama`로 맞춘다.
- **번역 자체를 끄고 전사만 보려면**(dev·배포 공통): `--no-llm-translation` 하나만 추가한다.
  ```powershell
  C:\Python312\python.exe -m whisperlivekit.basic_server --no-llm-translation
  ```
- config.yaml로 관리한다면 (CLI 인자로 직접 전달해도 동일):
  ```yaml
  translation:
    enabled: true
    serve: ollama          # 배포는 llama
    endpoint: http://localhost:11434   # 배포는 http://localhost:2010
    model: qwen2.5:7b      # 배포는 gpt-oss-20b
  ```

### 5.7 번역 트러블슈팅 + 기존 whisperlive 대비 알려진 차이

| 증상 | 원인 후보 | 확인 방법 |
|---|---|---|
| `translation` 항상 `""` | llama.cpp/Ollama 서버 미기동 또는 포트 상이 | §5.5의 `curl /v1/models`가 실패하는지 재확인 |
| `translation` 항상 `""` | 모델 별칭 불일치(`gpt-oss-20b` 기본값이 실제 서빙 id와 다름) | `--translation-model`을 §5.5 실측 id로 재기동 |
| `translation` 항상 `""` | `--translation-serve`가 실제 서버 종류와 안 맞음(`llama`↔`ollama` 반대로 줌) | 경로가 `/v1/completions`(llama) vs `/v1/chat/completions`(ollama)로 잘못 감 — 값 확인 |
| 번역을 끄고 싶은데 계속 시도됨 | `--llm-translation`이 **기본 ON**이라 아무 플래그 없이도 켜진다(과거엔 반대) | `--no-llm-translation` 추가 |
| 서버 로그에 completions 호출은 찍히는데 번역이 안 붙음 | 화자분할 ON에서 세그먼트가 아직 `finalized`가 아님 | 정상 동작 특성(§5.4) — 화자 전환을 유도 |
| 번역이 한 박자 늦게 뜸 | 발화 중인 마지막 세그먼트는 다음 화자 전환 시 확정 | 정상(§5.4) |
| 한 화자만 계속 말하면 번역이 안 붙음 | 화자 전환이 없어 확정 트리거가 안 걸림 | 두 명이 번갈아 발화로 재현 |
| 한글이 깨져서 전송됨 | curl로 직접 호출 시 인코딩 문제 | httpx(wlk 내부)는 `ensure_ascii`로 정상 처리됨 — curl 자체 결함이니 wlk 실사용에는 무관 |

**알려진 차이 — 기존 whisperlive 대비(버그 아님, 의도적 보류)**:
- **Qdrant 벡터 few-shot 미이식(Stage 2)**: 기존 whisperlive는 Qdrant(bge-m3 임베딩) 벡터 검색으로
  입력과 유사한 예시 문장을 동적으로 골라 프롬프트에 주입한다. wlk는 이 벡터 검색 단계만 미이식이다 —
  용어집(`glossary_block`) 동적 주입·고정 예시 문장(`sentence_block`) 주입은 이미 이식·연결 완료됐다
  (Stage 1, §6.3 참조). 동일 입력이라도 예시 선택 방식 차이로 번역 품질/용어 일관성이 기존과 다를 수 있다.
- **스트리밍 미사용**: 기존은 SSE 스트리밍(`_stream`), wlk는 단일 non-streaming POST(`stream:false`). 최종
  번역 결과는 동등하나, 화면에 토큰 단위로 흘러나오는 연출은 없다.

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

### 6.3 번역 Glossary — **Stage 1 이식 완료**(2026-07-16, master `534bad1`)

> **[정정, 2026-07-17]** 이 절은 한동안 "미이식/배포 범위 밖"이라고 적혀 있었으나 이미 Stage 1(glossary_block +
> sentence_block)이 이식·머지된 뒤 문서 갱신이 누락돼 있었다(CLAUDE.md "코드 변경 시 연동 갱신 문서" 표
> 위반 사례). 아래가 현재 상태다.

`whisperlivekit/llm_translation/`에 `TranslationPromptManager`(`prompt_manager.py`) + `get_prompt_manager()`
싱글턴 팩토리 + `translator.py`의 `build_system_blocks()` 연결까지 완료돼 있다(`whisperlivekit/filtering/`과
동일한 콜로케이션 패턴). `/api/prompts`(`GET` 조회, `POST /api/prompts/add-item` 추가, `POST
/api/prompts/delete-item` 삭제)로 운용 중 동적 추가/삭제가 가능하고, 변경은 **다음 번역 요청부터 즉시
반영**된다(API 계약 상세는 [API_SPEC.md §3.4](API_SPEC.md) 참조).

| 파일 | dev 위치 | 배포 시 해야 할 일 |
|---|---|---|
| `admin_translation_glossary.json` | `whisperlivekit/llm_translation/` | 배포 원본의 실제 용어집으로 내용 교체. **포맷은 `{origin: translation}` dict** — 단어교정 `admin_replacement.json`의 리스트 포맷(§6.1)과 다르므로 혼동 금지 |
| `user_translation_glossary.db` | `whisperlivekit/llm_translation/` | 기존 사용자 glossary를 이어쓰려면 배포 DB 파일 복사, 새로 시작이면 불필요(매니저가 테이블 자동 생성) |

**미이식으로 남은 것은 Stage 2(Qdrant 벡터 유사 예시 검색)뿐**이다 — `sentence_block`(few-shot 예시 문장)
자체는 이미 동작하며 항상 전체가 주입된다, "입력과 유사도가 가장 높은 예시만 동적으로 고른다"는 부분만
아직 없다. 설계 상세: [docs/superpowers/specs/2026-07-16-translation-glossary-design.md](superpowers/specs/2026-07-16-translation-glossary-design.md) §8.

> **⚠️ 배포 PC 반영 확인 필수**: `whisperlivekit/llm_translation/` 서브패키지 raw 소스 파일 복사가
> 누락되면(§8 트랩 "raw 소스 파일 복사 누락") 이 API 자체가 없는 것처럼(404) 보인다. 배포 후
> `curl http://localhost:8900/api/prompts`로 반드시 라이브 확인할 것(§7 점검 순서에 반영).

---

## 7. 배포 점검 순서 (권장)

> **빠른 기능 검증은 §4.4의 3단계**(전사 → React 프론트 → 번역)를 따른다. 아래는 **설치 무결성 + 정량 측정 + 단어 교정**까지 포함한 전체 점검 체크리스트로, §4.4를 감싸는 상위 순서다.

1. **설치 확인**: `C:\Python312\python.exe -c "import whisperlivekit, torch; print(torch.cuda.is_available())"` → `True`.
2. **경로 A 스모크**(§4.3): 파일 송신으로 전사가 나오는지 — 코드/모델 로드 정상 확인.
3. **내장 UI 전사**(§4.4 1단계): 브라우저 마이크로 한·영 발화 → 전사·화자 배지 정성 확인.
4. **React 프론트 연결**(§4.4 2단계): React UI를 `/asr`에 붙여 동일 전사 표시 확인.
5. **번역**(§4.4 3단계 / §5): `start_oss.bat` 후 번역 + 화자분할 동시 ON 기동 → 한↔영 1문장 스모크(동시 사용 가능, §5.4).
6. **경로 C 정량**(§4.1): `C:\Python312\python.exe scripts/closed_test.py test_data/sbs1.mp3` → WER/F1이 [EXPERIMENTS.md](../EXPERIMENTS.md) "현재 베이스라인"(turbo, diar-ON, Exp-161 기준: sbs1 ≈ WER 14.9%/F1 16.7% — F1은 diar-ON 문장경계 과분할로 낮게 나오는 게 정상, WER이 1차 지표) 근처인지. (playwright/VBCable 필요) — ⚠️ [MASTER_CHANGES §2](MASTER_CHANGES.md)의 수치(sbs1 19.6%/76.2%)는 Exp-105(2026-06-22, diar-OFF·base 기질) 기준으로 **stale** — 참조하지 말 것.
7. **단어 교정**(§6.2): `admin_replacement.json`/`hallucination.json`을 배포본으로 채운 뒤 해당 단어가 교정되는지 확인.
8. **번역 glossary**(§6.3): `curl http://localhost:8900/api/prompts`가 404가 아니라 200 JSON을 반환하는지, `/api/prompts/add-item`으로 추가한 용어가 다음 번역 요청부터 실제 반영되는지 확인.

---

## 8. 알려진 트랩 모음

| 트랩 | 증상 | 조치 |
|---|---|---|
| **DLP가 `C:\` 전체 감시** | `C:\dlp_probe.txt`에 쓴 텍스트가 다시 읽었을 때 깨진 문자·암호화 헤더로 나옴(§3.0 프로브) | no-venv `C:\Python312` 방식도 무효 — (a) WSL2/Docker로 회피, 또는 (b) IT 보안팀에 `C:\Python312` 폴더·`python.exe` 프로세스를 암호화 예외로 등록 요청 |
| uv 미설치 (dev PC 전용) | `uv: command not found` | 배포/협업 PC는 uv가 불필요(§3 — plain pip). **dev PC의 wheelhouse 빌드(§2.2)**에서만 필요 — 로컬 uv 설치 또는 `deploy\uv-installer\uv-*.zip` 압축 해제 후 PATH 등록 |
| HF repo ID 기본값 | (과거) 기동 시 네트워크 시도/실패 | **해결됨** — 기본값이 로컬 경로(§3.2). 안전상 `HF_HUB_OFFLINE=1` 권장 |
| `--warmup-file` 미지정 | (과거) github `jfk.wav` 다운로드 | **해결됨** — 기본값 `test_data/sbs1_10s.mp3`(§3.1) |
| 루트 밖에서 실행 | 모델·warmup 상대경로 못 찾음 | **저장소 루트에서** `python -m whisperlivekit.basic_server` 실행(요청 1) |
| 번역 미동작(과거) | `--llm-translation` 줘도 번역 안 붙음 | **해결됨** — config.py 4필드 master 머지(§5.2) |
| diar + 번역(과거) | 화자분할 ON이면 번역 공백 | **해결됨** — `get_lines_diarization` finalized 마킹 master 머지(§5.4). 동시 사용 가능 |
| **번역이 의도치 않게 켜짐/시도됨(2026-07-16~)** | 전사만 보려 했는데 llama.cpp 연결 시도 로그가 남거나, dev PC에서 없는 서버(`localhost:2010`)로 연결 실패 경고가 뜸 | `--llm-translation`이 **기본 ON**으로 바뀜(과거엔 기본 OFF). 전사만 보려면 `--no-llm-translation`, dev Ollama로 쓰려면 §5.6 재정의 플래그 필요(§5.3·§5.7) |
| VBCable 불안정 | 경로 C 무음/100% WER/분산 폭증 | 케이블 상태(코드 아님) — 재부팅/Audiosrv 재시작, `vbcable_test.py --verify` |
| playwright 미설치 | 경로 C 실패 | chromium 바이너리 복사 + `PLAYWRIGHT_BROWSERS_PATH` |
| RTX 5090 커널 | torch가 sm_120 미지원 | cu128 + torch 2.7+ 버전 확인 |
| 포트 충돌 | 수동 서버=8900, eval/closed_test=8901(기본). 배포 PC 기존 점유와 충돌하면 | `--port`로 변경, 또는 `parse_args.py`/`eval.py SERVER_PORT` 기본값 수정. 동시 기동 시 GPU 2배 점유 주의 |
| 문서 플래그 오타 | `--avg-logprob-threshold`는 없음 | 실제 플래그는 `--logprob-threshold`([parse_args.py:321](../whisperlivekit/parse_args.py#L321)) |
| **Python 버전 불일치** | `pip install -r requirements-deploy.txt` 중 `aiohttp`(또는 soxr·multiprocess 등)가 "Python 버전이 안 맞는다"고 실패 | wheelhouse가 **dev(3.12) 태그로 고정**됨(§2.2). 대상 PC에 `python-installer\python-3.12.10-amd64.exe`를 `C:\Python312`(PATH 미등록)로 설치(§3.0) 후 `C:\Python312\python.exe -m pip install ...`로 그 인터프리터에 직접 설치(§3.1). 기존 3.11 프로그램은 PATH를 건드리지 않으므로 영향 없음 |
| **잘못된 Python 호출** | 설치 로그엔 `numpy`·`torch` 등이 분명히 설치됐는데, `python -c "import ..."`나 `python -m whisperlivekit.basic_server` 실행 시 `ModuleNotFoundError: No module named 'numpy'` 등 발생 | venv가 없으므로 **활성화 단계 자체가 없다** — 대신 PATH의 다른 Python(시스템 3.11 등)이 실행돼 벌어지는 증상이다. 항상 **`C:\Python312\python.exe`를 직접 지정**해서 실행한다(§3.1·§4) |
| **sounddevice 누락** | `C:\Python312\python.exe scripts/closed_test.py ...`(경로 C) 실행 시 `ModuleNotFoundError: No module named 'sounddevice'` | `scripts/vbcable_test.py`가 `sd.play()`로 VBCable에 오디오를 재생하는 하드 의존성인데 과거 `vbcable` extra(playwright+comtypes만)에 빠져 있었음 — master에서 수정 완료(pyproject.toml `vbcable` extra에 `sounddevice` 추가, requirements-deploy.txt·wheelhouse 갱신). 이미 설치된 PC는 `C:\Python312\python.exe -m pip install --no-index --find-links C:\whist\wlk\deploy\wheelhouse sounddevice==0.5.5`로 단건 추가하면 된다(전체 재설치 불필요) |
| **공유 `.venv` 반쪽 손상** (dev PC §2.2 패키징 전용 — 배포/협업 PC는 venv가 없어 해당 없음) | dev PC에서 `.venv\Scripts\python.exe`가 `No pyvenv.cfg file`(exit 106)로 기동 불가 → 측정·pytest 전면 차단. `.venv` 최상위에 `Lib`/`pyvenv.cfg` 없이 `Scripts`/`share`만 잔존 | **원인**: 배포/wheelhouse 작업(§2.2)의 `uv venv`/`uv pip`/`uv sync`를 **공유(Junction) `.venv`에 실행**했고, 그 순간 IDE Jedi 언어서버가 python.exe를 잠가 Scripts 제거가 실패한 반쪽 손상. **예방**: §2.2 경고대로 wheelhouse 빌드는 독립 `.venv`에서 + IDE 인터프리터 분리. **복구(무중단)**: `uv venv` 출력의 base python(`Using CPython … at <경로>`)으로 임시 probe venv 생성 → 그 `pyvenv.cfg`를 손상된 `.venv\`에 복사 → python 기동 회복 → `uv sync --extra diarization-sortformer --extra vbcable --extra cu128`로 Lib 재설치(Scripts 제거를 안 하므로 IDE 잠금과 무관). 진행 중 uv 경합이 있으면 먼저 멈춘 뒤 복구 |
| **`wlk_in` 최신화 ≠ 배포 PC 반영** | dev PC의 `wlk_in`은 최신 master 기준으로 갱신됐는데, 배포 PC(`C:\whist\wlk`)는 여전히 구버전 코드로 동작(예: `model_dir` 미전파로 인터넷 다운로드 시도 → `getaddrinfo failed`) | `wlk_in`을 갱신하는 것과 그걸 USB로 옮겨 배포 PC에 실제로 덮어쓰는 것은 별개 단계다. `wlk_in\SYNC_STATE.txt`의 `deploy_pc_confirmed_applied`가 `unknown`이면 아직 배포 PC 반영이 확인되지 않은 것 — 매번 USB 반입·적용 여부를 사용자에게 확인한다 |
| **raw 소스 파일 복사 누락** | 일부 `whisperlivekit/**` 변경이 반영 안 된 듯 보이는데 재설치할 wheel이 없음(예: 특정 버그 수정이 재현되거나, 신규 서브패키지의 API가 404) | whisperlivekit 프로젝트는 wheel로 설치하지 않으므로 유일한 반영 경로는 raw 소스 파일 복사뿐이다 — `C:\Python312\python.exe -c "import whisperlivekit; print(whisperlivekit.__file__)"`로 실제 로드 경로(`C:\whist\wlk\whisperlivekit\...`)를 확인하고, `deploy-sync` 절차의 `git diff --name-status` 목록과 `wlk_in`/배포 PC의 실제 파일을 `diff -q`로 대조해 빠짐없이 복사됐는지 확인한다 — wheel이라는 안전장치가 사라졌으므로 이 확인이 유일한 검증 수단이다 |
| **`git show`로 반입 복사 시 줄바꿈만 다른 거짓 mismatch** | `deploy-sync` 6단계에서 `git show master:<path> > wlk_in\<path>`로 복사하면 `diff -q`가 매번 실제 변경 없는 파일까지 mismatch로 잡음 | 이 저장소는 `core.autocrlf=true`라 워킹트리 체크아웃 파일은 CRLF인데, `git show`는 blob 원본(LF 정규화됨)을 그대로 출력한다 — 내용은 같고 줄바꿈만 달라 `diff -q`가 오탐한다. 반입 복사는 `git show`가 아니라 **워킹트리 파일을 직접 복사**(`cp`/`Copy-Item`)한다 |
