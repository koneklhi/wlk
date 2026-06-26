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
- **한국어 / 영어 두 언어만** 들어오는 환경. 두 언어 모두 인식률 극대화가 목표.
- **Code-Switching**(한 발화 안에 한·영 혼용) 상황에서 단어 유실 / 환각 / 문장 조기 확정이 발생하지 않도록 설계한다. 특히 **전환 간격이 짧은 환경**(대표 데이터 = ytn2) 및 **다화자 장시간 발화 환경**(대표 데이터 = bong1 — 영어 2명+한국어 2명)에서도 인식률을 유지하는 것이 현재 최우선 과제다.

### 3.3 문장 단위 출력 — 백엔드 책임 범위
- **백엔드(우리 작업)가 하는 일**: ① 한 문장이 끝났는지 판단(확정/비확정 상태 결정) ② 결과를 React UI에 메시지로 전달.
- **배포 환경 React**는 프론트 개발자 담당(이 저장소에 React 코드 없음). **단, 개발/테스트 단계에선 내장 UI에 가벼운 프론트 기능을 직접 넣어 검증해도 된다.**
- 메시지 스키마는 [docs/SCHEMA_CHANGES.md](docs/SCHEMA_CHANGES.md)로 **확정·구현됨**. 문장 확정 알고리즘(신호 조합)은 일부 미정 — [docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md) §1 참조 후 합의해 확정.
- 문장 확정 품질은 `/eval`의 **문장 분리 F1**(정답 기준: 빈 줄 = 화자전환 경계(1순위 필수) + 긴 발화 온점분리 경계(2순위 선택), STT `lines[]` 경계와 단어 정렬 비교; F1 primary=화자전환 경계·secondary=온점 경계 — metric 구현 후속)로 정량 평가한다.
  **성능 판정 기준은 경로 C(VBCable 루프백)만** 사용한다. 경로 A(PCM 파일 주입)는 브라우저 오디오 파이프라인을 우회해 실사용과 무관한 수치를 내므로 폐기.

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
- **상용화 worst-case 우선**: 동일 음성·환경에도 실행마다 편차 큼 — 배포·상용화 관점에서 **worst 케이스 감소가 최우선**이다. 개선 방향 검토 시 median보다 **최악 케이스 축소를 먼저** 생각한다(측정·채택 규칙은 §4).
- **범용 개선만 + 테스트/held-out 분리**: 측정 **테스트 세트 = bong1 + ytn2 + sbs1**(채택/기각 판단, `--repeat 3`), **held-out = ytn1 + eng1**(채택 후보에 한해 일반화 검증). ytn1은 ytn2 동일 이벤트 쌍둥이 → 미학습 코드스위칭 일반화 검증, eng1은 영어 회귀 감시. 새 실험 전 "이 변경이 bong1/ytn2/sbs1 특화인가?" 자문. 추후 테스트 데이터 추가 시 회귀 없어야 한다.
- **하드코딩·백엔드 우선, 탈출구 허용**: 디코더 파라미터(beam_size, compression_ratio_threshold, no_speech_threshold 등)·오디오 전처리·VAD 등 backend 레벨 개선을 우선한다. **정 방법이 없는 경우 하드코딩·후처리 필터도 사용 가능**(남용 금지; 근거는 실험기록에 남긴다). 특정 언어·패턴 특화 하드코딩(한국어 N-gram 필터, N-word 배치 드롭 등)은 신규 추가보다 backend 대안을 먼저 탐색한다. 기존 베이스라인 필터(Exp-002/028/057)는 유지.

## 4. 코드 스타일 / 운영 규칙

- **언어**: 코드 식별자·주석을 제외한 모든 사용자 응답·문서·커밋 메시지는 한국어. 기존 `whisperlivekit` 코드의 영어 식별자/주석은 보존.
- **Python**: `pyproject.toml` 기준 Python `>=3.11, <3.14`, FastAPI 기반. 린트 `ruff check`(line-length 120, target `py311`).
  테스트 `pytest`(`tests/`). 패키지 매니저 `uv`(`uv.lock` 존재).
- **Git Worktree 환경 관리**: 디스크 용량 절약을 위해 실험/기능 개발용 워크트리 생성 시, 기본적으로 메인 저장소의 `.venv`를 공유(Windows 교차점/Junction 연결)하여 사용한다. 워크트리에서 패키지 추가나 버전 변경이 명시적으로 필요한 경우에만 예외적으로 독립된 `.venv`를 구성한다.
- **실험 기록**: STT 성능 분석/개선 작업 시 [EXPERIMENTS.md](EXPERIMENTS.md)(활성 로그)를 먼저 확인해 이전 시도와
  결론을 파악한다. 코드 변경 + 벤치마크 완료 후 새 항목(Exp-N, 131부터 이어감)을 추가하며, 작성은 `/log-experiment` 슬래시 커맨드로 수행한다. (Exp-001~130은 [PHASE2_EXPERIMENTS.md](PHASE2_EXPERIMENTS.md) 아카이브.)
- **구현 → 측정 → 기록 자율 루프**: STT 개선 코드 구현이 끝나면 **사용자 지시를 기다리지 않고** 자율적으로 eval.py를 실행한다. VBCable 상태 확인(`vbcable=ok`) → 경로 C 측정 → 결과 분석 → `/log-experiment` 기록 → 채택/기각 자율 결정 → 다음 단계 진행. **major 방향 전환**(Stage 변경, 실험 방향 변경, 루프 종료)은 사용자에게 보고 후 진행한다. (근거: §4 경로 C 반복 측정 규칙과 동일한 자율 루프 원칙.)
- **경로 C 반복 측정**: 실시간 STT 특성 상 동일 조건에서도 매 실행마다 성능 편차가 크다(±30~120%p 관측 — 분산이
  개선폭을 압도). 채택/기각 판단에 쓰는 경로 C 수치는 **동일 파일·설정으로 N≥3회 반복 측정**(`eval.py --repeat 3`) 후
  **median + 분산(min/max/stdev)을 함께** 본다. 1회 결과로 결론 금지. **측정 기본 설정 = 화자분할 ON**(Sortformer; `--diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo --compression-ratio-threshold 3.0`; 테스트·held-out 분리는 §3.8 참조). **fail-fast(첫 회차 나쁘면 중단) 금지** —
  분산 자체가 데이터이므로 N회를 전부 측정한다(단, VBCable 미설정·포트 충돌·무음 캡처 등 *하니스 버그*는 즉시 멈추고 고친다).
  **채택 우선순위: 1순위 = 최악 케이스(max) 미회귀, 2순위 = median 개선.** 최악 케이스가 catastrophic하게 터지는 설정은
  median이 좋아도 실사용에서 무너지므로 기각. 최악 케이스가 발생하면 median 개선보다 그 원인 파악과 해결을 먼저 수행한다.

### 코드 변경 시 연동 갱신 문서

코드 변경 커밋과 **동일 작업 단위**에 아래 문서를 함께 갱신한다. 갱신 누락이 발견되면 즉시 수정할 것.

| 변경한 코드 | 반드시 함께 갱신할 문서 |
|---|---|
| `parse_args.py` 기본값 (포트·모델경로·warmup·플래그·threshold) | `docs/TESTING.md` (경로 A/B/C 명령·URL), `ROADMAP.md`, `docs/FRONTEND_HANDOFF.md`, `docs/DEPLOYMENT_OFFLINE.md` §3-4 |
| `scripts/eval.py` `SERVER_PORT` 또는 측정 기본 설정 | `docs/TESTING.md` 경로 C, `.claude/commands/eval.md` |
| `whisperlivekit/test_client.py` 기본 URL | `docs/TESTING.md` 경로 A |
| `config.py` `WhisperLiveKitConfig` 필드 (WebSocket 메시지 스키마 영향) | `docs/SCHEMA_CHANGES.md`, `docs/FRONTEND_HANDOFF.md` |
| `pyproject.toml` extras 추가/제거 | `docs/DEPLOYMENT_OFFLINE.md` §2.1 기능별 extra 표 및 §2.2 export 명령 |
| 번역 파이프라인 변경 (`translator.py`, config 번역 필드) | `docs/DEPLOYMENT_OFFLINE.md` §5, `docs/FRONTEND_HANDOFF.md` |
| `test_data/` 파일 추가 또는 정답 .txt 추가 | `docs/TESTING.md` 파일 목록, `CLAUDE.md` §4 측정 기본 설정(테스트셋 변경 시) |
| WhisperLiveKit 본체 대규모 변경 | `docs/MASTER_CHANGES.md` — `/update-master-changes` 슬래시 커맨드 실행 |

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
- 미정 설계 사항(문장 확정 알고리즘, 메시지 스키마, Code-Switching, 폐쇄망 패키징) → [docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md)
- Phase 정의·태스크·완료 기준 → [ROADMAP.md](ROADMAP.md) / 실험 기록(활성) → [EXPERIMENTS.md](EXPERIMENTS.md) (Exp-001~130 아카이브 → [PHASE2_EXPERIMENTS.md](PHASE2_EXPERIMENTS.md))
- master 최종본 upstream 대비 전체 변경 + 향후 개선 → [docs/MASTER_CHANGES.md](docs/MASTER_CHANGES.md)

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
