# 새 PC 개발 환경 셋업

두 번째 PC에서 개발을 이어서 진행하기 위한 절차. 동일 Windows 환경 기준.

---

## 표준 경로 (PC 간 통일) — 중요

**두 PC 모두 저장소를 동일한 절대경로에 둔다: `C:\dev\wlk`**

이유: PC마다 경로가 다르면(`C:\Users\<사용자A>\...` vs `C:\Users\<사용자B>\...`) editable 설치
메타데이터·이전 절대경로 참조가 어긋나 `uv run` 이 매번 재설치를 시도하거나 import가 깨진다.
**username에 의존하지 않는 동일 경로**를 쓰면 이 불일치가 근원적으로 사라진다.

> `C:\dev\wlk` 가 아닌 다른 경로를 써도 되지만, **두 PC가 글자 단위로 똑같아야** 한다.

기계별로 달라지는 파일은 git에서 추적하지 않는다(이미 `.gitignore` 처리됨):
`.venv/`, `.claude/settings.local.json`, `.omc/benchmarks/*.json`. 이들은 각 PC 로컬에만 둔다.

---

## 전제 조건

- Git, Python 3.11 이상 설치 확인
- `uv` 패키지 매니저 설치: `pip install uv`
- FFmpeg 시스템 설치 확인 (경로 A 파일 송신에 필요)
  - 확인: `ffmpeg -version`
  - 없으면: `winget install ffmpeg` 또는 공식 사이트에서 수동 설치

---

## 셋업 순서

### 1. 저장소 클론 (표준 경로로)

```
git clone https://github.com/hyungillee/wlk.git C:\dev\wlk
cd C:\dev\wlk
```

> 이미 다른 경로에 체크아웃돼 있다면, 새로 clone하지 말고 아래 **"기존 체크아웃을 표준 경로로 이동"** 절차를 따른다(모델 가중치 ~1.6GB 재복사 방지).

### 2. 라이브러리 설치

```
uv sync
```

- `uv.lock` 기준으로 `.venv`가 자동 생성됨
- CUDA 12.8 호환 PyTorch 휠이 자동 설치됨 (별도 CUDA 툴킷 설치 불필요)
- 소요 시간: 수 분 (약 7GB 다운로드)

### 3. 모델 가중치 배치 (수동 복사)

`model.safetensors`(1.6GB)는 GitHub에 없으므로, USB 또는 네트워크 공유로 복사:

```
whisperlivekit\model\whisper-large-v3-turbo\model.safetensors
```

model.safetensors 외 나머지 파일(config.json, tokenizer.json 등)은 git으로 자동 포함.

### 4. GPU 동작 확인

```
uv run python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

`True <GPU 이름>` 이 출력되면 정상.

### 5. 서버 기동 + 스모크 테스트

`docs/TESTING.md` 의 절차를 따라 서버 기동 후 경로 A 스모크 확인.

---

## 기존 체크아웃을 표준 경로로 이동 (재clone 아님)

이미 `C:\Users\...\wlk` 등 다른 경로에 체크아웃돼 있고 모델 가중치·워크트리가 들어있는 경우,
**새로 clone하지 말고 폴더를 통째로 이동**한다(모델 1.6GB 재복사·worktree 재생성 방지).

각 PC에서 1회 수행:

```powershell
# 1. 해당 폴더를 쓰는 모든 프로세스 종료 (VSCode / Claude / STT 서버 등)

# 2. 폴더 이동 (예: 현재 경로 → 표준 경로)
Move-Item "C:\Users\<현재사용자>\Desktop\260605wlk\wlk" "C:\dev\wlk"
Set-Location "C:\dev\wlk"

# 3. 워크트리 링크 복구 (.worktrees/* 의 절대경로 갱신)
git worktree repair

# 4. .venv 재생성 (editable 설치를 새 경로로 재고정)
uv sync

# 5. import 정상 확인
uv run python -c "import whisperlivekit; print(whisperlivekit.__file__)"
```

5번 출력이 `C:\dev\wlk\whisperlivekit\__init__.py` 를 가리키면 이동 완료.

> `.venv` 는 절대경로가 박혀 있어 이동만으로는 깨진다 — 반드시 `uv sync` 로 재생성한다.
> 모델 가중치(`*.safetensors`)는 gitignore라 이동으로 보존되며 재복사 불필요.

---

## 새 워크트리에서 작업 시작 시 (.venv 공유가 기본)

새 `git worktree`를 만들 때 **`.venv`를 새로 만들지 않는다 — 메인 저장소(루트 `.venv`)를 Windows
Directory Junction으로 연결하는 것이 기본값**이다. 워크트리를 수십 개 운용해도 공유 `.venv` 하나로
동작에 차이가 없으며, 독립 `.venv`는 ~8GB씩 복제돼 디스크를 낭비한다.

```cmd
cd worktrees\<name>
mklink /J .venv ..\..\.venv
```

Junction을 걸면 메인 `.venv`의 옵셔널 의존성(`sounddevice`, `playwright`, `comtypes` 등)이 그대로
보이므로 워크트리에서 `ModuleNotFoundError`가 나지 않는다.

**예외 — 독립 `.venv`를 만드는 경우**: 해당 워크트리에서 **패키지 추가/버전 변경이 명시적으로 필요할 때만.**

1. Junction 제거: `rmdir .venv`
2. 독립 venv 생성 후 동기화: `uv venv && uv sync --extra vbcable --extra listen`

> `--extra vbcable`=경로 C 브라우저 자동화(`playwright`/`comtypes`), `--extra listen`=VBCable 재생
> (`sounddevice`). extra 이름은 `pyproject.toml`의 `[project.optional-dependencies]`에서 확인.

**중요 — `ModuleNotFoundError`가 나도 같은 설치를 반복하거나 pip 직접 호출로 전환하지 말 것.**
먼저 Junction이 제대로 걸렸는지 확인하고, 독립 venv가 필요한 예외 상황이면 위 `uv sync`를 **1회만**
실행하고 멈춘다.

---

## 이후 일상 동기화

```
# 작업을 마친 PC에서
git push

# 다른 PC로 이동 후
git pull
```

모델 가중치는 한 번 복사하면 재복사 불필요. 코드만 git으로 오감.
양 PC가 동일한 `C:\dev\wlk` 경로를 쓰면 경로 불일치 에러가 발생하지 않는다.

> **주의**: `.claude/settings.local.json`, `.omc/benchmarks/*.json` 는 추적하지 않으므로 git으로 오가지 않는다.
> 각 PC에서 로컬로만 관리한다(권한 설정·벤치마크 결과는 기계별).
