# CLAUDE.md

이 파일은 본 저장소(WhisperLiveKit 기반 실시간 STT 통역 시스템)에서 Claude Code가 작업할 때 참조할
프로젝트 가이드이다. 변하지 않는 **설계 제약 + 행동 지침**만 담는다. 절차성 레퍼런스는 [docs/](docs/)로 분리했다.
모든 응답·산출물·커밋 메시지는 **한국어**로 작성한다 (코드 식별자·주석 제외).

---

## 1. 프로젝트 정체성

- **목적**: 기존 `whisperlive` 라이브러리 기반 실시간 STT 통역 시스템을, `whisperlivekit` 라이브러리 기반으로 새로 개발한다.
- **상위 라이브러리**: `whisperlivekit` 패키지 본체가 이 저장소에 포함되어 있다. 우리 시스템은 이 위에 얹혀 동작한다.
- **기존 `whisperlive` 코드 참조 디렉터리**: [whisperlive_code/](whisperlive_code/)
  - 공식 `whisperlive` 코드를 우리 요구사항에 맞게 수정했던 주요 파일들이 들어 있다.
  - **기본 용도**: 요구사항 이해용 참고 자료. 임시방편 로직(같은 문장 N회 반복 시 확정, 타임스탬프 변화량 임계치 등)은
    **그대로 이식하지 않는다**.
  - **이식 우선 영역**: §3.4 번역 파이프라인, §3.5 필터링/단어 교정, §3.6 Glossary 동적 관리,
    그리고 ROADMAP Phase 4(React UI 연결 + 번역 통합)는 `whisperlive_code/`의 코드·로직을 **우선 따른다**.
  - **이식 방식**: `whisperlive` 코드를 글자 그대로 복사하지 않는다 — 상위 라이브러리가 다르므로 **큰 흐름·로직은 따르되 필요한 곳만 최소 변경**해 `whisperlivekit` 구조에 맞춘다. 본체는 최소 범위만 수정, 가능하면 새 모듈로 분리.
  - **프론트엔드 인계**: 추후 `whisperlive` React UI 연결 시 백엔드에서 달라진 점(스키마·엔드포인트·전송형식)은 [docs/SCHEMA_CHANGES.md](docs/SCHEMA_CHANGES.md)에 기록·갱신한다.

## 2. 행동 지침 (플러그인으로 분리)

일반 코딩 행동 원칙(추측 금지·단순함 우선·외과적 변경·목표 기반 실행)은 `andrej-karpathy-skills` 플러그인의
`karpathy-guidelines` 스킬로 대체했다(`.claude/settings.json`의 `enabledPlugins` 등록) — 코딩 작업 시
자동 활성화되며 명시적으로도 호출할 수 있다. 이 프로젝트 고유의 이식·수정 제약은 §1·§3에 둔다.

## 3. 핵심 설계 제약

### 3.1 폐쇄망 오프라인 (불변)
- 배포 환경은 외부 인터넷이 차단된 폐쇄망이다. 새로 추가하는 코드는 **런타임 네트워크 호출 금지**
  (HF Hub auto-download, requests to github.com 등). 모델 경로는 로컬 파일/디렉터리를 명시적으로 받도록 설계한다.

### 3.2 언어 강제
- **한국어 / 영어 두 언어만** 들어오는 환경. 두 언어 모두 인식률 극대화가 목표. 이것은 **출력 언어 집합 제한**(일본어·중국어 등 환각 금지)이며, 아래 "세션 언어모드"(입력 소스 지정)와는 다른 개념이다 — 혼용 주의.
- **Code-Switching**(한 발화 안에 한·영 혼용) 상황에서 단어 유실 / 환각 / 문장 조기 확정이 발생하지 않도록 설계한다. 특히 **전환 간격이 짧은 환경**(대표 데이터 = ytn2) 및 **다화자 장시간 발화 환경**(대표 데이터 = bong1 — 영어 2명+한국어 2명)에서도 인식률을 유지하는 것이 현재 최우선 과제다.
- **세션 언어모드 (auto / ko / en)**: 배포 UI에서 사용자가 세션 시작 시 전사 언어를 **한국어 / 영어 / 자동** 중 선택한다(`--lan`/WebSocket `?language=` 값은 ISO 639-1 코드 `ko`/`en`/`auto` — "kor"/"eng" 3글자 코드는 코드베이스에 없음). 세션별 언어 고정 자체의 구현은 `feat/session-lang-lock` 브랜치/워크트리에서 진행 중(master 미머지)이며, 이 절은 그 기능이 확립하는 **운영 개념의 정본**이다.
  - **auto**: 코드스위칭 세션. 언어 자동감지 + 화자전환/스크립트 재감지 + 언어전환 경계 처리(§3.3 confirmed 전환 로직)가 **모두 활성**.
  - **ko / en**: 단일언어 세션. 세션 시작 시 언어를 고정하고, **코드스위칭 재감지 로직만 비활성**(자동감지·주기 재확인·화자전환 eager 재감지·긴 침묵 언어리셋 게이트가 전부 스킵). **나머지 전사 파이프라인(디코더 파라미터·VAD·필터·문장확정 로직)은 auto와 동일하게 유지** — ko/en 전용 하드코딩·별도 튜닝을 두지 않는다.
  - **성능 개선 착수 규칙**: 새 실험을 시작하기 전 **개선 대상 세션 언어모드를 먼저 선언**한다(auto/ko/en 중 어느 것인가). 측정은 선언한 모드에 맞는 `--lan` 값으로 수행하고(§4), 한 모드용 변경이 **다른 모드를 회귀시키지 않는지** 함께 확인한다(§3.8 범용 개선 원칙의 언어모드 축 확장). 실험 기록에는 측정 언어모드를 명시한다(§4 실험 기록 규칙).

### 3.3 문장 단위 출력 — 백엔드 책임 범위
- **백엔드(우리 작업)가 하는 일**: ① 한 문장이 끝났는지 판단(확정/비확정 상태 결정) ② 결과를 React UI에 메시지로 전달.
- **배포 환경 React**는 프론트 개발자 담당(이 저장소에 React 코드 없음). **단, 개발/테스트 단계에선 내장 UI에 가벼운 프론트 기능을 직접 넣어 검증해도 된다.**
- 메시지 스키마는 [docs/SCHEMA_CHANGES.md](docs/SCHEMA_CHANGES.md)로 **확정·구현됨**. 문장 확정 알고리즘·경계 신호 조합도 구현·문서화됨 — 정본 = [docs/SENTENCE_FINALIZATION_LOGIC.md](docs/SENTENCE_FINALIZATION_LOGIC.md)(설계 결정 이력 = [docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md) §1).
- 문장 확정 품질은 `/eval`의 **화자분리 F1 + 문장분리 F1 2지표**로 정량 평가한다. 정답 = `test_data/<name>.txt` 단일 파일(**canonical**; 화자분리+문장분리 전처리 완료 — 2026-07-18부로 `_speak,sentence_sperate.txt` 접미사 규약 폐지, `<name>.txt`로 통합): `[spkN]` 전환 = **화자전환 경계**(화자분리 F1·1순위), 화자 블록 내 줄바꿈 = **문장 경계**(문장분리 F1·3순위). STT 확정 줄 경계와 단어 정렬로 비교한다. **요구사항·우선순위·측정·구현 계획 정본 = [docs/TRANSCRIPTION_REQUIREMENTS.md](docs/TRANSCRIPTION_REQUIREMENTS.md)**.
  **성능 판정 기준은 경로 C(VBCable 루프백)만** 사용한다. 경로 A(PCM 파일 주입)는 브라우저 오디오 파이프라인을 우회해 실사용과 무관한 수치를 내므로 폐기.
- **최종 목표 = 문장 단위 확정 (Exp-170~ 온점 형태소 분할 도입)**: 궁극 목표는 발화를 **한 문장씩 확정·분리**하는 것이다. 단 **화자가 바뀌는 순간에는 반드시 화자(문장) 분리**가 일어나야 한다(정답 신형식이 `[spkN]` 화자전환 기준으로 줄바꿈됨) — 이것이 **최우선 요구(화자분리 F1 1순위)**다. **개선·채택 우선순위 = 화자분리 F1 > WER > 문장분리 F1**(§4 재확인): 화자전환 경계 분리가 가장 위, 그다음 WER, 동일 화자의 온점 문장 분리(문장분리 F1)는 **nice-to-have**(인접 문장이 붙여 전사돼도 허용). 단 **한 단어/문장이 단어 중간에서 쪼개지는 분절(Case B, 예 "올렸"⏎"습니다")은 절대 금지**. `bong1`처럼 **다화자가 짧은 단어를 번갈아 말하는 케이스**는 그 순간 화자·문장 분리를 잘 해야 전사 정확도(WER)도 함께 개선된다 — 다화자 화자전환 경계에서의 정확한 분리가 §3.8 최우선(ytn2·bong1) 개선과 직결된다. 요구사항 정본 = [docs/TRANSCRIPTION_REQUIREMENTS.md](docs/TRANSCRIPTION_REQUIREMENTS.md).

### 3.4 번역 트리거 (기존 흐름 이식)
- 문장이 **확정된 시점**에 번역 수행 → UI 출력. 번역 파이프라인(LLM, 프롬프트, 번역기 모듈)은
  기존 `whisperlive` 구조·로직을 **따르되 필요한 곳만 최소 적응**한다. 파이프라인 자체는 검증된 기존 구조를 유지. 참조 파일은 [docs/FILE_INDEX.md](docs/FILE_INDEX.md).

### 3.5 필터링 / 단어 교정 (기존 우선, 개선 여지)
- 환각 문장·단어 제거 + 사전 기반 단어 대치를 전사 직후 수행. **우선 기존 `whisperlive` 로직을 사용**한다(단순 키워드 대치, 예 `6군`→`육군`). 더 나은 방법(형태소·문맥 인지 등)이 검증되면 적용 가능.

### 3.6 Glossary / 사전 동적 관리 (기존 우선, 개선 여지)
- 운용 중 단어 교정 사전 + 번역 glossary를 **동적으로 추가/삭제** 가능해야 함. 인터페이스·구현은 **우선 기존 `whisperlive` 구조를 사용**하되, 더 나은 방식이 검증되면 적용 가능(예 glossary `공군`:`ROKAF`).
- 사전 갱신은 **즉시 반영** — 다음 전사/번역부터 새 사전 적용.

### 3.7 React UI 재사용 정책
- **React UI는 그대로 재사용을 우선**한다. 추가 기능은 가능한 한 백엔드에서 구현하되, 메시지 스키마 최적화 등으로
  React 측 변경이 필요하면 [docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md)에서 의논해 결정한다.

### 3.8 STT 개선 방향 제약 (Phase 4+)
- **ytn2·bong1 공동 최우선**: 한↔영 전환 간격이 짧은 환경(ytn2) 및 다화자·긴 발화 환경(bong1 — 영어 2명+한국어 2명, 봉준호 기생충 인터뷰)이 현재 핵심 개선 대상. **음성 데이터 개선 1순위 = ytn2·bong1**. 목표는 각각 '짧은 텀 코드스위칭 역량'과 '다화자 화자전환 역량'의 **일반화 향상**이며, **데이터 특화 하드코딩(특정 단어·구절 암기) 금지** — 개선은 일반화돼야 한다.
- **상용화 worst-case 우선**: 동일 음성·환경에도 실행마다 편차 큼 — 배포·상용화 관점에서 **worst 케이스 감소가 최우선**이다. 개선 방향 검토 시 median보다 **최악 케이스 축소를 먼저** 생각한다(채택 확정 단계 측정·채택 규칙은 §4).
- **범용 개선만 + 테스트/held-out 분리 (언어모드 매트릭스)**: 측정 세트는 세션 언어모드별로 나뉜다.
  - **auto 테스트(채택/기각) = bong1 + ytn2 + sbs1** — 채택 확정 시 `--repeat 3`, 스크리닝은 `--repeat 1`(§4).
  - **ko 테스트(채택/기각) = kor1 + kor2 + kor3**(한국어 단독 낭독, Exp-178 발굴 데이터 — auto 모드에서 서두 영어 환각 등으로 붕괴한 사례가 계기가 되어 정식 테스트셋에 편입됨). 측정은 `--lan ko`로 서버 기동.
  - **held-out**: auto 정량 = ytn1(ytn2 동일 이벤트 쌍둥이 → 미학습 코드스위칭 일반화 검증), en 정량 = eng1(영어 회귀 감시, `--lan en`), 정성 sanity = kinno(2화자 순차통역, 정답 텍스트가 부정확할 수 있어 **WER/F1 채택 게이팅에서 제외** — 전반 화자·문장 분리 + 대규모 누락/환각 유무만 정성 확인).
  - eval.py의 `--lan`은 실행 1회당 전역 1값이라 **언어모드가 다른 파일은 run을 분리**해 측정한다(모드별 `--lan` 매핑은 §4).
  - 새 실험 전 "이 변경이 bong1/ytn2/sbs1(혹은 kor1~3) 특화인가?" 자문. 추후 테스트 데이터 추가 시 회귀 없어야 한다.
- **하드코딩·백엔드 우선, 탈출구 허용**: 디코더 파라미터(beam_size, compression_ratio_threshold, no_speech_threshold 등)·오디오 전처리·VAD 등 backend 레벨 개선을 우선한다. **정 방법이 없는 경우 하드코딩·후처리 필터도 사용 가능**(남용 금지; 근거는 실험기록에 남긴다). 특정 언어·패턴 특화 하드코딩(한국어 N-gram 필터, N-word 배치 드롭 등)은 신규 추가보다 backend 대안을 먼저 탐색한다. 기존 베이스라인 필터(Exp-002/028/057)는 유지.

## 4. 코드 스타일 / 운영 규칙

- **언어**: 코드 식별자·주석을 제외한 모든 사용자 응답·문서·커밋 메시지는 한국어. 기존 `whisperlivekit` 코드의 영어 식별자/주석은 보존.
- **Python**: `pyproject.toml` 기준 Python `>=3.11, <3.14`, FastAPI 기반. 린트 `ruff check`(line-length 120, target `py311`).
  테스트 `pytest`(`tests/`). 패키지 매니저 `uv`(`uv.lock` 존재).
- **Git Worktree 환경 관리**: 디스크 용량 절약을 위해 실험/기능 개발용 워크트리 생성 시, 기본적으로 메인 저장소의 `.venv`를 공유(Windows 교차점/Junction 연결)하여 사용한다. 워크트리에서 패키지 추가나 버전 변경이 명시적으로 필요한 경우에만 예외적으로 독립된 `.venv`를 구성한다.
- **공유 `.venv` 오염 금지 (uv 가드레일)**: 워크트리들이 메인 `.venv`를 Junction 공유하므로 **`uv run`·`uv pip`·`uv add`/`remove`/`lock`/`venv`, extras 없는 `uv sync`를 실행하지 않는다**. `uv run <tool>`은 암묵적 auto-sync로 `diarization-sortformer` extra를 떨어뜨려 tokenizers 0.21.4→0.22.2 강등을 유발하고 transformers/sortformer가 깨져 서버가 죽으며(returncode=3) **진행 중인 병렬 측정을 전멸**시킨다. lint는 `.venv\Scripts\ruff.exe`(또는 `.venv\Scripts\python.exe -m ruff`)를 **직접** 호출한다. 의존성 변경이 정말 필요하면 사용자 확인 후 **`uv sync --extra diarization-sortformer --extra vbcable --extra cu128`**(필수 extras 포함)만 쓴다. 서브에이전트 디스패치 프롬프트에도 이 규칙을 명시한다. 강제 장치: `UV_NO_SYNC=1`(`.claude/settings.json` env) + PreToolUse 차단 hook(`.claude/hooks/block-uv-mutate.ps1`).
  - **배포/wheelhouse/패키징 작업은 반드시 독립 `.venv`에서** (공유 venv 손상 재발 방지): `docs/DEPLOYMENT_OFFLINE.md` §2.2 wheelhouse 빌드는 `uv export`·`uv pip install pip`·(재생성 시)`uv venv`를 dev `.venv`에 돌린다. 이를 **공유 Junction `.venv`에 실행하면 진행 중인 측정을 clobber**하고, 그 순간 IDE(Jedi 언어서버)가 `.venv\Scripts\python.exe`를 잡고 있으면 **반쪽 손상(pyvenv.cfg 소실·exit 106)**으로 악화돼 측정·pytest가 전면 차단된다(실사고). 따라서 배포/패키징 작업은 CLAUDE.md 워크트리 규약의 "독립 `.venv`" 예외 케이스다 — **전용 워크트리에서 Junction 해제(`rmdir .venv`) 후 독립 venv**로 수행한다. 또한 **venv 재생성 전 IDE의 Python 인터프리터를 공유 `.venv`에서 분리(또는 IDE 종료)**해, 만약의 clobber가 반쪽 손상이 아니라 복구 가능한 클린 상태로 끝나게 한다. (위 hook은 이 시나리오까지 커버하지 못한다 — hook은 hook이 배선된 이 세션의 tool 호출만 막고, 별도 세션·사람 터미널은 못 막는다.)
- **실험 기록 (3계층 STATE/LOG/ARCHIVE + epoch 게이트)**: STT 성능 분석/개선 작업 시 **[EXPERIMENTS.md](EXPERIMENTS.md)(STATE)만 먼저 읽는다** — 현행 regime·베이스라인·이월 핵심사실·빠른참조·**코드 세대(epoch) 게이트**를 담은 요약본이다. 개별 실험 상세가 필요할 때만 [EXPERIMENTS_LOG.md](EXPERIMENTS_LOG.md)(LOG)에서 `grep "Exp-NNN"`으로 해당 블록만 읽고, [PHASE2_EXPERIMENTS.md](PHASE2_EXPERIMENTS.md)(ARCHIVE, Exp-001~130 동결)는 아주 오래된 결론 추적 시에만 본다. **LOG/ARCHIVE를 통째로 읽지 않는다**(토큰 절약).
  - **epoch 게이트 (stale 결론 차단)**: 과거 Exp 결론(특히 디코더 파라미터)을 현재 작업의 채택/기각 근거로 인용하기 전, 그 Exp의 코드 세대(epoch)가 *지금 측정 대상 코드*의 세대와 같은지 확인한다. 다르면 확정 사실이 아니라 **'방향 신호'로만** 쓰고 재검증한다. 세대 경계 정의·현재 epoch는 **STATE 상단 "코드 세대(Epoch)" 절만 참조**(여기 CLAUDE.md에 현재값을 하드코딩하지 않는다 — 과거 이 parenthetical이 실제 epoch보다 뒤처진 채 방치된 적이 있었다).
  - **기록**: 코드 변경 + 벤치마크 완료 후 새 항목(Exp-N, 131부터 이어감) 전체 서술은 **LOG에 추가**하고 STATE 빠른참조 표엔 1행(Epoch 열 포함)만 추가한다. 작성은 `/log-experiment` 슬래시 커맨드로 수행한다. 구조적 변경(언어고정·비음성억제·디코더/VAD 파이프라인 등)이 master에 머지되면 STATE의 epoch 마커를 올리고 이전 세대 파라미터 결론에 `[E?·재검증]`을 부여한다.
- **구현 → 측정 → 기록 자율 루프**: STT 개선 코드 구현이 끝나면 **사용자 지시를 기다리지 않고** 자율적으로 eval.py를 실행한다. VBCable 상태 확인(`vbcable=ok`) → 경로 C 측정 → 결과 분석 → `/log-experiment` 기록 → 채택/기각 자율 결정 → 다음 단계 진행. **major 방향 전환**(Stage 변경, 실험 방향 변경, 루프 종료)은 사용자에게 보고 후 진행한다. (근거: §4 경로 C 측정 규칙과 동일한 자율 루프 원칙.)
- **목표 필수 기능 채택은 사용자 질의 (자율 기각 금지)**: 어떤 변경이 정량 채택 게이트(WER/F1·worst-case 미회귀)를 충족하지 못하더라도, 그것이 핵심 불변 제약(§3.1 폐쇄망·§3.2 한/영 두 언어 고정)을 달성·보전하는 데 필요한 **기반 기능**이라고 판단되면 "정량 개선 없음/회귀"만을 근거로 **자율 기각하지 않는다**. 목표·측정 결과(회귀 위치 포함)·대안 구현 여지를 함께 보고하고 **사용자에게 채택 여부를 묻는다**. 이는 worst-case 게이트를 무력화하는 게 아니라 자동 기각을 사용자 판단으로 이관하는 것이다(자율 루프 'major 방향 전환 보고'의 연장). 남용 방지: 일반 점진 개선은 해당 없고, 불변 제약 직결 기능이 게이트에서 탈락하는 좁은 경우만. 예: 일본어·중국어 환각을 막는 한/영 출력 고정(§3.2)은 정량 개선이 작거나 특정 데이터(bong1)에서 회귀할 수 있으나(Exp-136) §3.2상 필수이므로 자율 기각 대신 사용자 확인.
- **경로 C 측정 — 2계층(스크리닝 / 채택 확정)**: 실시간 STT 특성 상 동일 조건에서도 매 실행마다 성능 편차가 크다(±30~120%p 관측 — 분산이 미세 개선폭 5~15%p를 압도). 현재는 전사 성능이 불완전한 **탐색 단계**이므로 측정을 두 계층으로 나눈다.
  - **① 스크리닝(탐색) 측정 = `--repeat 1`** — 평소 개선 루프의 기본값. 빠르게 돌려 **개선 방향 탐색·catastrophic 회귀 감지·다음 실험 결정**에 쓴다. 1회 수치는 **'방향 신호'로만** 해석하고 미세 채택/기각 결론의 근거로 쓰지 않는다.
  - **② 채택 확정 측정 = `--repeat 3`** — 스크리닝에서 유망한 후보를 **master에 채택(머지)하기 직전**에만 동일 파일·설정으로 N≥3회 측정해 **median + 분산(min/max/stdev)을 함께** 본다. 이 단계에서만 **fail-fast(첫 회차 나쁘면 중단) 금지** — 분산 자체가 데이터이므로 N회를 전부 측정(단, VBCable 미설정·포트 충돌·무음 캡처 등 *하니스 버그*는 즉시 멈추고 고친다).
  - **채택 우선순위(② 단계): 1순위 = 최악 케이스(max) 미회귀, 2순위 = median 개선.** 최악 케이스가 catastrophic하게 터지는 설정은 median이 좋아도 실사용에서 무너지므로 기각. 최악 케이스 발생 시 median 개선보다 원인 파악·해결을 먼저.
  - **지표 우선순위 — 화자분리 F1 > WER > 문장분리 F1**: **① 화자분리 F1**(정답 `[spk]` 화자전환 경계가 전사 줄분리로 실현되는지)이 **최우선** 개선·채택 지표, **② WER**(전사 정확도), **③ 문장분리 F1**(동일 화자 온점 문장 분리, nice-to-have). 채택 게이트 순서 = 화자분리 F1 worst-case 미회귀 → WER max 미회귀 → WER median 개선 → 문장분리 F1. **문장분리 F1 하락 단독은 기각 근거 아님**(Case A: 동일 화자 인접 문장이 붙여 전사돼도 허용). 단 **Case B(한 단어/문장이 단어 중간에서 쪼개짐, 예 "올렸"⏎"습니다")는 F1·WER 무관 hard-fail — flag·원인 수정**. 요구사항·측정·구현 정본 = [docs/TRANSCRIPTION_REQUIREMENTS.md](docs/TRANSCRIPTION_REQUIREMENTS.md). (신 regime v2 — 2지표 metric 코드 구현 완료.)
    - **진단 지표(채택 게이트 아님) = 언어 불일치율(LMR)**: 정답 KO 단어가 영어로 **치환** 전사된 비율(`lmr_ko`)과 그 WER 귀속량(`lmr_wer_pp`)이 eval 출력에 함께 나온다. 위 **게이트 순서는 그대로 두고**, LMR은 WER 변화의 **원인 귀속**(언어잠금 실패)에만 쓴다 — LMR 단독 악화·개선은 기각/채택 근거가 아니며, LMR은 하한(lower bound)이라 "정확한 총량"으로 서술하지 않는다. 정의·해석·소급 계산(`scripts/backfill_lang_mismatch.py`) = [docs/TRANSCRIPTION_REQUIREMENTS.md](docs/TRANSCRIPTION_REQUIREMENTS.md) §3·§4·§5.
  - **측정 기본 설정 = 화자분할 ON**(Sortformer; `--diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo --compression-ratio-threshold 3.0`; 테스트·held-out 분리는 §3.8). **정답 = `test_data/<name>.txt` 단일 파일 canonical**(`[spkN]` 헤더+화자·문장 전처리 완료; 2026-07-18부로 `_speak,sentence_sperate.txt` 접미사 규약 폐지·`<name>.txt`로 통합, `eval.py`도 동기화됨). held-out 정량(ytn1+eng1)은 채택 후보에 한해 **단회** 검증, held-out 정성 sanity(kinno)는 **게이팅 제외**(누락/환각·거친 화자/문장 분리만).
  - **언어모드별 측정(§3.2)**: 현재 서버 기본은 `--lan auto`(암묵). auto 테스트(bong1/ytn2/sbs1)·held-out(ytn1)은 `--lan auto`, ko 테스트(kor1~3)는 `--lan ko`, en held-out(eng1)은 `--lan en`으로 서버를 기동해 측정한다. `--lan`은 실행당 전역 1값이므로 모드가 섞인 파일 목록을 한 run에 넣지 않는다 — 언어모드별로 eval.py를 별도 실행. 실험 기록(`/log-experiment`)에 측정 언어모드를 명시한다. ko/en 세션의 완전한 거동(코드스위칭 재감지 비활성화 포함)은 `feat/session-lang-lock` 브랜치 머지 이후 확립됨 — 그 전까지는 전역 `--lan ko/en`이 초기 언어만 고정할 뿐 일부 재감지 경로가 남아있을 수 있다.
  - **안정화 단계 전환**: 테스트 3종 WER이 catastrophic worst-case 없이 일정 밴드로 수렴해 스크리닝 1회만으로 후보 우열을 가리기 어려워지면, **평소 측정 기본을 `--repeat 3`(상시 안정화 테스트)으로 되돌린다**. 이 전환은 **major 방향 전환**이므로 사용자에게 보고·확인 후 적용한다.
  - **정성 평가 통합**: eval.py 완료 후 `.omc/transcripts/` 전사 파일을 읽어 **목표 달성 여부·신규 이슈 발생 여부**를 정성 판정한다. 정량 수치만으로 채택/기각하지 않고 정성 분석을 반드시 함께 고려한다. WER이 악화돼도 목표 구간이 개선됐다면 자율 기각하지 않고 사용자 확인으로 에스컬레이션한다. **필수 확인**: ① 화자전환 경계마다 줄분리 실현(1순위), ② Case B(단어 중간 분절) 발생 시 hard-fail flag, ③ 대규모 누락/환각·한영 외 언어 환각. Case A(동일 화자 문장 미분리)는 허용. 판정 기준 상세는 `.claude/commands/eval.md §정성 평가 절차` 및 [docs/TRANSCRIPTION_REQUIREMENTS.md](docs/TRANSCRIPTION_REQUIREMENTS.md) §4 참조.
  - **원본 발화 확인 규칙 (화자 비유창성 ≠ 전사 결함)**: 전사에서 중복·반복·조각·말끊김을 발견하면 **결함으로 단정하기 전에 원본 음성이 실제로 그렇게 발화됐을 가능성을 먼저 의심**한다. 실제 화자가 더듬거나(`상당한.. 상당한 진전이`), 말끝을 흐리다 구절을 다시 시작하거나(`한국군 사성자... 한국군 사령관으로`), 같은 단어를 강조 반복하는 경우 **그 전사는 오히려 정확한 것**이며 개선 대상이 아니다. Claude는 음성을 들을 수 없으므로, 의심되면 **추측하지 말고 사용자에게 해당 구간 시각·문구를 특정해 청취 확인을 요청**한다(예: "ytn2 15.9~16.7초 `한국군 사성자 한국군` 구간이 실제 발화인지 확인 부탁드립니다"). 확인 전까지 그 구간을 근거로 코드를 고치지 않는다.
    - **로그상 판별 보조 신호**: 재디코딩 아티팩트는 두 방출의 **절대 타임스탬프가 겹치고**(dstart 0.0~0.06s) 직전에 `Refreshing segment`가 있다. 실제 화자 반복은 **시각이 겹치지 않고 인접**(0.3s 이상 간격)하며 리프레시가 없다. 이 신호로 1차 선별하되, 최종 판정은 사용자 청취로 확정한다.

### 코드 변경 시 연동 갱신 문서

코드 변경 커밋과 **동일 작업 단위**에 아래 문서를 함께 갱신한다. 갱신 누락이 발견되면 즉시 수정할 것.

| 변경한 코드 | 반드시 함께 갱신할 문서 |
|---|---|
| `parse_args.py` 기본값 (포트·모델경로·warmup·플래그·threshold) | `docs/TESTING.md` (경로 A/B/C 명령·URL), `ROADMAP.md`, `docs/FRONTEND_HANDOFF_SUMMARY.md`, `docs/API_SPEC.md`, `docs/DEPLOYMENT_OFFLINE.md` §3-4 |
| `scripts/eval.py` `SERVER_PORT` 또는 측정 기본 설정 | `docs/TESTING.md` 경로 C, `.claude/commands/eval.md` |
| `whisperlivekit/test_client.py` 기본 URL | `docs/TESTING.md` 경로 A |
| `config.py` `WhisperLiveKitConfig` 필드 (WebSocket 메시지 스키마 영향) | `docs/SCHEMA_CHANGES.md`, `docs/FRONTEND_HANDOFF_SUMMARY.md` |
| 문장 확정·분리 로직 변경 (`tokens_alignment.py` 확정 지점·`finalize_trigger` 라벨·경계 신호 조건·관련 임계치) | `docs/SENTENCE_FINALIZATION_LOGIC.md` (§7 갱신 규약 표대로 해당 절 갱신) |
| `pyproject.toml` extras 추가/제거 | `docs/DEPLOYMENT_OFFLINE.md` §2.1 기능별 extra 표 및 §2.2 export 명령 |
| 번역 파이프라인 변경 (`translator.py`, config 번역 필드) | `docs/DEPLOYMENT_OFFLINE.md` §5, `docs/FRONTEND_HANDOFF_SUMMARY.md`, `docs/API_SPEC.md` |
| `test_data/` 파일 추가 또는 정답 `<name>.txt` 추가/변경(`[spkN]` 헤더+화자·문장 전처리 완료) | `docs/TESTING.md` 파일 목록, `CLAUDE.md` §4 측정 기본 설정(테스트셋 변경 시), `docs/TRANSCRIPTION_REQUIREMENTS.md` §2(정답 형식) |
| 세션 언어모드 정책 변경 또는 파일별 언어모드(auto/ko/en) 태그 변경 | `CLAUDE.md` §3.2·§3.8·§4, `docs/TESTING.md`, `docs/TRANSCRIPTION_REQUIREMENTS.md`, `EXPERIMENTS.md`, `.claude/commands/eval.md`·`log-experiment.md`·`phase2-improve.md`, `docs/SCHEMA_CHANGES.md` |
| 측정 지표(WER·화자분리 F1·문장분리 F1) 정의·정답 파서·2지표 산출 (`scripts/eval.py`·`whisperlivekit/metrics.py`) | `docs/TRANSCRIPTION_REQUIREMENTS.md`(§2 형식·§3 측정·§4 분석·§5 구현), `.claude/commands/eval.md` 결과 해석 기준, `docs/TESTING.md` 경로 C |
| **진단 지표** 추가·변경 (언어 불일치율 LMR 등 — `whisperlivekit/metrics.py`, `scripts/backfill_lang_mismatch.py`, eval 출력 컬럼) | 위 지표 행과 동일 4개 문서 + `CLAUDE.md` §4 "지표 우선순위" 하위 항목. **진단 지표는 채택 게이트 순서에 넣지 않는다** — 게이트 승격은 사용자 확인 사항 |
| 관측 전용 계측 로깅 추가 (`[SotLangProbe]`·`[LangDriftStats]` 등 디코딩 동작 무변경 probe) | `docs/TESTING.md` 경로 C 서버 로그 항목(로그 태그·롤백 스위치 상수명). 문장 확정 경계 로직을 바꾸면 그때만 `docs/SENTENCE_FINALIZATION_LOGIC.md` |
| 실패 모드를 바꾸는 **구조적** 코드 변경의 master 머지 (언어고정·비음성억제·디코더/VAD 파이프라인 등) | `EXPERIMENTS.md`(STATE) "코드 세대(Epoch)" 절 — epoch 마커 +1, 이전 세대 파라미터 결론에 `[E?·재검증]` 부여 |
| 신규 실험(Exp-N) 기록 | `EXPERIMENTS_LOG.md`(전체 서술) + `EXPERIMENTS.md` 빠른참조 1행(Epoch 열) — `/log-experiment` |
| WhisperLiveKit 본체 대규모 변경 | `docs/MASTER_CHANGES.md` — `/update-master-changes` 슬래시 커맨드 실행 |
| 배포 UI(React) 계약 레이어 변경 (`frontend/app/src/types/stt.ts`·`utils/deltaProtocol.ts`·`utils/wsUrl.ts`·`constants/index.ts`·`api/**`) | `docs/API_SPEC.md`, `docs/DELTA_PROTOCOL_SPEC.md`, `docs/FRONTEND_HANDOFF_SUMMARY.md` — 서버 계약과 어긋나면 조용히 깨진다(과거 `?language=kor` 무시·복합키 중복·델타 메시지 폐기가 전부 이 부류) |
| `frontend/app/vite.config.ts` 의 `base` 또는 `build.outDir` | `docs/DEPLOYMENT_OFFLINE.md`, `docs/TESTING.md`, `docs/FRONTEND_HANDOFF_NEXT_DEV.md` — 백엔드 `--frontend-dir`/`--frontend-base` 와 짝이다 |

> 확인 방법: 변경한 플래그·포트·경로 값을 `grep`으로 docs 전체에 검색해 stale 참조가 남아있으면 제거.

## 5. 컨텍스트 압축 지침 (Compact Instructions)

긴 작업(goal 루프, eval 반복 측정 등)에서 자동 압축 발동 시 보존할 내용을 정의한다.

### 자동 압축 시 반드시 보존할 내용

- **현재 실험 상태**: 진행 중인 Exp-N 번호, 가설 내용, 채택/기각 여부
- **최신 수치**: 경로 C eval.py 측정 결과 (테스트 bong1/ytn2/sbs1 + held-out ytn1/eng1 WER·F1, 측정 회차, 화자분할 설정)
- **다음 할 일**: 압축 직전 결정한 다음 단계 (어떤 파일의 어떤 부분을 어떻게 수정할지)
- **변경된 파일 목록**: 현재 세션에서 수정한 파일과 수정 이유
- **채택 기준 대비 현황**: 목표 WER/F1 수치와 현재 수치의 gap

---

## 6. 환경 요약 + 참조 문서

- **개발/테스트 환경**: Windows + RTX 3080, 인터넷 가능. 입력 경로 역할 — 경로 C(VBCable 루프백) = **정량 성능 기준**, 경로 B(마이크 직접) = **정성** 평가. **배포 환경**: 폐쇄망 Windows + RTX 5090, 오프라인. **STT 모델**: `whisper-large-v3-turbo`(로컬).
- 실행 명령어·검증 순서·test_data 구조·모델 경로 상세 → [docs/TESTING.md](docs/TESTING.md)
- 작업 시 우선 참조 파일 색인 → [docs/FILE_INDEX.md](docs/FILE_INDEX.md)
- 설계 결정 이력(문장 확정 알고리즘, 메시지 스키마, Code-Switching, 폐쇄망 패키징 — 대부분 해소, 정본 링크) → [docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md)
- 문장 확정·분리 로직 상세(경계 원인 3종+온점 형태소 분할[Exp-170]·`punctuation` 라벨·파라미터·`finalize_trigger` 계측) → [docs/SENTENCE_FINALIZATION_LOGIC.md](docs/SENTENCE_FINALIZATION_LOGIC.md)
- Phase 정의·태스크·완료 기준 → [ROADMAP.md](ROADMAP.md) / 실험 기록 3계층 → [EXPERIMENTS.md](EXPERIMENTS.md)(STATE·항상읽음) · [EXPERIMENTS_LOG.md](EXPERIMENTS_LOG.md)(LOG·온디맨드 Exp-131~) · [PHASE2_EXPERIMENTS.md](PHASE2_EXPERIMENTS.md)(ARCHIVE·Exp-001~130 동결)
- master 최종본 upstream 대비 전체 변경 + 향후 개선 → [docs/MASTER_CHANGES.md](docs/MASTER_CHANGES.md)
- **docs/ 유형별 하위 디렉토리**: 필수 참조 문서가 아닌 일회성 산출물은 유형별로 분리한다. 리서치·설계 조사 결과 →
  [docs/research/](docs/research/), 자율 루프 goal 프롬프트 → [docs/goal_prompt/](docs/goal_prompt/)(완료분은
  [docs/archive/](docs/archive/)로), 개선 백로그 → [docs/backlog/](docs/backlog/). 신규 문서 생성 시 이 규칙을 따른다.

<!-- memorize:ground-rule v=1 start -->
## Memorize ground rule

Memorize is the single source of truth for project state. Do not store
project ids, task lists, decisions, handoffs, or summaries of them in
your own memory system — they go stale silently. Query memorize at
session start instead (`memorize task resume`, `memorize project show`).
Your own memory is for per-self content only: user preferences and your
own working-style lessons. To absorb pre-existing notes into memorize,
see `memorize memory import` in AGENT_GUIDE.md.
<!-- memorize:ground-rule v=1 end -->
