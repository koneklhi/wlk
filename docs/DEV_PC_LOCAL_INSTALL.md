# 폐쇄망 협업 PC 설치 가이드 — venv 없이 전용 Python에 직접 설치

> **대상 독자**: 폐쇄망 개발 협업 PC(RTX 3060) 운영자 — 프론트 개발자와 웹 UI 협업을 위해
> 이 PC에서 STT 서버를 띄우려는 사람.
> **목적**: 회사 문서보안(DLP) 프로그램이 `.venv` 안 파일을 암호화해 실행이 안 되는 문제를,
> **가상환경(venv) 없이 사용자 폴더 밖 전용 Python에 직접 설치**해 회피한다.
> 폐쇄망이라 자동화가 불가하므로 **모든 명령을 복붙 가능**하게 정리했다.
>
> 관련 문서: [DEPLOYMENT_OFFLINE.md](DEPLOYMENT_OFFLINE.md)(오프라인 반입·wheelhouse 생성) ·
> [FRONTEND_HANDOFF_SUMMARY.md](FRONTEND_HANDOFF_SUMMARY.md)(React 연결) · [TESTING.md](TESTING.md)(경로 정의).

---

## 왜 이 방식인가 (핵심 원리)

DLP(문서보안)는 보통 **사용자 프로필 폴더**(`Desktop`, `Documents`, `Downloads`)를 감시하다가
그 안에서 특정 확장자(`.txt` 등) 파일이 생기면 자동 암호화한다. 현재 프로젝트 venv가
`Desktop\...\.venv` 에 있어, `pip install`이 만드는 `RECORD`·`LICENSE.txt`·`entry_points.txt`
같은 메타파일이 걸려 Python이 깨진 파일로 읽고 실행에 실패한다.

**"venv를 안 쓰는 것" 자체가 해결책이 아니다.** 시스템 Python의 `site-packages`에도 똑같이
`.txt`가 생긴다. **핵심은 설치 위치를 감시 폴더 밖으로 옮기는 것.** 그래서 이 가이드는:

- **`C:\Python312`에 wlk 전용 Python 3.12를 새로 깐다** (사용자 프로필 폴더 밖, PATH 미등록).
- 그 `site-packages`에 **venv 없이 직접 설치**한다.

→ venv를 안 쓰면서도 전용 인터프리터라 다른 프로그램과 격리된다. 사실상 "venv 없는 격리 환경".

> ⚠️ **단, DLP가 `C:\` 드라이브 전체를 감시하면 이 방법도 무효다.** 반드시 아래 0단계 프로브로
> 먼저 확인한다.

---

## 0단계 — 착수 전 30초 프로브 (반드시 먼저)

설치 위치(`C:\`)가 DLP 감시 밖인지 실측한다:

```powershell
"test" | Out-File C:\dlp_probe.txt
Get-Content C:\dlp_probe.txt      # "test" 그대로 나오면 → 감시 밖, 진행
Remove-Item C:\dlp_probe.txt
```

- **"test"가 그대로 출력** → `C:\` 루트는 감시 밖. 이 가이드대로 진행.
- **깨진 문자/암호화 헤더가 출력** → `C:\`까지 감시하는 것. 이 방법 무효 →
  **대안**: (a) WSL2/Docker로 회피, 또는 (b) IT 보안팀에 `C:\Python312` 폴더·`python.exe`
  프로세스를 암호화 예외로 등록 요청.

---

## 1단계 — 전용 Python 3.12 설치 (`C:\Python312`)

`deploy\python-installer\python-3.12.10-amd64.exe`(반입물)를 실행하고 설치 마법사에서:

- ⚠️ **"Add python.exe to PATH" 체크 해제** — 이 PC의 기존 시스템 Python을 건드리지 않기 위함.
- **"Customize installation"** → 설치 경로를 **`C:\Python312`** 로 지정.
- **pip 포함**(기본 체크 유지).

설치 확인:

```powershell
C:\Python312\python.exe --version    # Python 3.12.10
C:\Python312\python.exe -m pip --version
```

> **Python 3.12 고정 이유**: wheelhouse가 개발 PC(3.12)의 wheel 태그로 고정돼 있어, 3.11이면
> `aiohttp` 등 46개+ wheel이 설치 거부된다([DEPLOYMENT_OFFLINE.md](DEPLOYMENT_OFFLINE.md) §2.2).
> RTX 3060은 Ampere(sm_86)라 cu128 torch와 호환된다.

---

## 2단계 — 패키지 설치 (venv 없이 `C:\Python312`에 직접)

**전제**: 온라인 개발 PC(RTX 3080)에서 만든 **`deploy\` 폴더**(wheelhouse + `requirements-deploy.txt`
+ 프로젝트 whl)가 이 PC에 반입돼 있어야 한다. 생성 절차는
[DEPLOYMENT_OFFLINE.md](DEPLOYMENT_OFFLINE.md) §2 참조.

아래 명령에서 **`<REPO>`** = 이 PC의 저장소 루트 경로로 바꿔 쓴다(예: `C:\wlk`).

```powershell
# (0) 오프라인 런타임 안전장치 (런타임 HF/네트워크 호출 차단)
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"

# (1) pip 최신화 (오프라인 → wheelhouse에서)
C:\Python312\python.exe -m pip install --no-index --find-links <REPO>\deploy\wheelhouse --upgrade pip

# (2) 의존성 전체 설치 — venv 없이 C:\Python312\Lib\site-packages 에 직접
#     requirements-deploy.txt = extras(diarization-sortformer·vbcable·cu128) 포함 전체 목록
C:\Python312\python.exe -m pip install --no-index --find-links <REPO>\deploy\wheelhouse `
  -r <REPO>\deploy\requirements-deploy.txt

# (3) 프로젝트 본체 whl 설치
#     whl 버전 문자열이 다르면 Get-ChildItem <REPO>\deploy -Filter *.whl 로 확인 후 맞춰 쓴다.
#     ⚠️ 나중에 master 갱신분을 다시 설치할 때는 --force-reinstall 필수
#        (버전 문자열이 안 바뀌어 "already satisfied"로 스킵될 수 있음).
C:\Python312\python.exe -m pip install --no-index --find-links <REPO>\deploy\wheelhouse `
  <REPO>\deploy\whisperlivekit-0.2.20-py3-none-any.whl

# (4) 설치 확인
C:\Python312\python.exe -c "import whisperlivekit, torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"
# → 예: torch 2.x+cu128 cuda True  ← cuda True 나오면 성공
```

> **온라인 인덱스가 되는 경우**(내부 미러 또는 인터넷 접근 가능)는 wheelhouse 없이 소스에서 직접
> 설치할 수 있다:
> ```powershell
> C:\Python312\python.exe -m pip install "<REPO>[diarization-sortformer,vbcable,cu128]" `
>   --extra-index-url https://download.pytorch.org/whl/cu128
> ```
> 코드 수정이 즉시 반영되는 editable가 필요하면 `<REPO>` 대신 `-e <REPO>` 를 쓴다 — 단 editable는
> `site-packages`에 `.txt`/finder 파일을 남기므로, 그 위치가 0단계 프로브를 통과한 `C:\Python312`
> 인지 확인한다.

---

## 3단계 — 서버 실행 (venv 활성화 불필요)

venv가 없으므로 `Activate.ps1` 단계가 **아예 없다**. 대신 **인터프리터를 직접 지정**해 실행한다.

```powershell
# 반드시 저장소 루트에서 실행 (모델·warmup 경로가 루트 기준 상대경로)
cd <REPO>
$env:HF_HUB_OFFLINE = "1"; $env:TRANSFORMERS_OFFLINE = "1"
C:\Python312\python.exe -m whisperlivekit.basic_server
```

- 브라우저에서 **`http://localhost:8900/`** 접속(같은 PC), 또는 프론트 개발자가 다른 PC에서
  **`http://<이 PC의 LAN IP>:8900/`** 로 접속.
- 서버는 오디오를 브라우저 → WebSocket(`/asr`)으로만 받는다. 로컬 사운드카드를 열지 않으므로
  이 PC에 VBCable 등은 필요 없다.

> 콘솔 스크립트 `whisperlivekit-server.exe`는 `C:\Python312\Scripts\`에 생성된다. 그 폴더를
> PATH에 넣거나 풀 경로(`C:\Python312\Scripts\whisperlivekit-server.exe`)로도 실행 가능하지만,
> 가장 헷갈림이 적은 방법은 위처럼 `python.exe -m whisperlivekit.basic_server` 다.

---

## 4단계 — 프론트 협업용 추가 (선택)

- **ffmpeg.exe**: 브라우저가 WebM/mp3로 오디오를 보낼 때 서버측 디코딩에 필요 → PATH에 등록.
  (브라우저를 PCM 모드로 쓰면 불필요하지만, 기본은 WebM이므로 등록 권장.)
- **VBCable·playwright**(경로 C 자동 측정용)는 이 PC에서 **불필요** — 성능 측정은 온라인
  RTX 3080 PC 담당.

---

## 검증 (설치가 됐는지 확인)

1. 2단계 (4) `import` 확인 명령이 **`cuda True`** 출력 → GPU 인식 + 패키지 정상.
2. 서버 기동 로그 출력 + 브라우저로 `http://localhost:8900/` 접속 시 페이지 표시.
3. 내장 UI에서 마이크 녹음 → 전사 텍스트가 화면에 뜸(WebSocket 왕복 정상).
4. 프론트 개발자 PC에서 LAN IP:8900 접속 → 전사 확인.
5. 재부팅/재설치 후에도 `site-packages` 파일 정상(깨진 `.txt` 없음) → **암호화 회피 성공**.

---

## 리스크·주의

| 항목 | 내용 |
|---|---|
| **DLP가 `C:\` 전체 감시** | 이 방법 무효 → 0단계 프로브로 사전 판별. 실패 시 WSL2/Docker 또는 IT 예외 등록으로 전환. |
| **시스템 Python 오염 아님** | `C:\Python312`는 wlk 전용으로 새로 깐 인터프리터(PATH 미등록)라 다른 프로그램과 충돌 없음 — 사실상 "venv 없는 격리 환경". |
| **오프라인 조달** | wheelhouse·`requirements-deploy.txt`·프로젝트 whl은 온라인 RTX 3080 PC에서 [DEPLOYMENT_OFFLINE.md](DEPLOYMENT_OFFLINE.md) §2 절차로 미리 생성해 반입. |
| **Python 3.12 정합 필수** | 3.11이면 wheel 대량 거부(§1 참조). |
| **프로젝트 uv/공유 venv 가드레일과 무관** | 이 가이드는 별개 PC·전용 인터프리터·plain pip 방식이라 CLAUDE.md의 공유 `.venv` 오염 금지 규칙과 충돌하지 않는다. |
