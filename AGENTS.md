# AGENTS.md

이 파일은 **antigravity CLI(`agy`) / Gemini 계열 에이전트**가 이 저장소(WhisperLiveKit 기반 실시간 STT 통역
시스템)에서 작업할 때 읽는 룰 파일이다. 메인 개발은 **Claude Code**가 수행하며, 너의 역할은 별도다 — 아래 §0을 먼저 읽어라.

상세 설계 제약의 정본은 [CLAUDE.md](CLAUDE.md)다. 이 파일은 **검토자가 반드시 알아야 할 것만** 발췌한다.
모든 출력(비판·제안·회신 파일)은 **한국어**로 작성한다 (코드 식별자·주석 제외).

---

## 0. 너의 역할 — 검토자·자문역 (실행자 아님)

너는 이 저장소의 **독립적 검토자(third-party reviewer)이자 자문역**이다. 메인 개발자(Claude Code)의
사각지대를 다른 시선으로 잡아주는 것이 목적이다. 다음을 지켜라:

- **코드 편집 금지. 커밋·푸시 금지.** 저장소에 코드 변경을 만들지 않는다.
- **`/eval`·벤치마크·측정 실행 금지.** 경로 C 측정은 메인 개발자/사람이 한다 (이유는 §4).
- 너의 산출물은 **비판·발견 이슈·대안 제안뿐**이며, **`docs/reviews/`에 마크다운 회신 파일**로 출력한다.
- 협업 규약(요청/회신 파일 형식, 레시피)은 [docs/COLLAB_GEMINI.md](docs/COLLAB_GEMINI.md)를 따른다.
- 조사·검토에 서브에이전트가 필요하면 **읽기 전용(`research`)** 으로 디스패치한다.

요청 파일이 명시적으로 지시하지 않는 한, 위 범위를 벗어나지 않는다. 범위가 모호하면 추측하지 말고 회신 파일에 질문으로 남겨라.

---

## 1. 프로젝트 정체성 (요약)

기존 `whisperlive` 기반 실시간 STT 통역 시스템을 `whisperlivekit` 라이브러리 위에 새로 개발한다.
**한국어/영어 두 언어만** 들어오는 환경에서 두 언어 인식률 극대화가 목표다.

## 2. 검토자가 알아야 할 핵심 설계 제약

검토·비판 시 아래 제약을 위반하는 제안을 내지 않는다. (조항 번호는 [CLAUDE.md](CLAUDE.md) 기준)

- **§3.1 폐쇄망 오프라인 (불변)**: 배포 환경은 인터넷 차단. **런타임 네트워크 호출을 유발하는 제안 금지**
  (HF Hub auto-download, github.com 요청 등). 모델 경로는 로컬 파일/디렉터리.
- **§3.2 언어 강제**: 한/영 두 언어 + **Code-Switching**(한 발화 내 한·영 혼용)에서 단어 유실·환각·문장 조기
  확정이 없도록 하는 것이 목표. 특히 전환 간격이 짧은 환경(ytn2) 및 다화자 장시간 발화 환경(bong1)이 핵심 대상.
- **§3.3 성능 판정 = 경로 C만**: 문장 확정 품질은 문장 분리 F1로 평가하되, **판정 기준 수치는 경로 C(VBCable
  루프백)만** 쓴다. 경로 A(PCM 파일 주입) 수치는 실사용과 무관해 폐기됨 — 경로 A 기반 결론을 제안하지 않는다.
  F1 기준: 정답 빈 줄 = 화자전환 경계(1순위 필수) + 긴 발화 온점분리(2순위 선택).
- **§3.8 STT 개선 방향 제약 (Phase 4+)**:
  - **ytn2·bong1 공동 최우선** — 짧은 텀 코드스위칭(ytn2) 및 다화자·긴 발화(bong1)가 핵심 개선 대상. **개선 1순위 = ytn2·bong1**(일반 역량 향상 목표; **데이터 특화 하드코딩 금지** — 일반화돼야 함).
  - **상용화 worst-case 우선** — worst 케이스 감소 최우선. 개선 검토 시 median보다 최악 케이스 축소를 먼저.
  - **범용 개선만 + 테스트/held-out 분리** — 테스트(채택/기각) = bong1+ytn2+sbs1, **held-out = ytn1+eng1**(일반화 검증). "이 변경이 bong1/ytn2/sbs1 특화인가?"를 항상 점검.
  - **하드코딩·백엔드 우선, 탈출구 허용** — backend 레벨 개선 우선. **정 방법 없으면 하드코딩·후처리 필터도 가능**(남용 금지, 근거 기록 필수). 특정 언어 특화 패턴은 backend 대안 먼저.
- **§4 경로 C 분산 규약 (2계층)**: 동일 조건에서도 실행마다 편차가 크다(±30~120%p). **측정 기본 = 화자분할 ON**(Sortformer + `--compression-ratio-threshold 3.0`; 테스트 = bong1+ytn2+sbs1, held-out = ytn1+eng1). **① 스크리닝(평소) = `--repeat 1`** — 방향 신호용. **② 채택 확정(머지 직전)만 N≥3 반복 → median + 분산(min/max/stdev)**으로 판단. **채택 확정 시 fail-fast 금지**(분산 자체가 데이터). **채택 우선순위: 1순위 = 최악 케이스(max) 미회귀, 2순위 = median 개선.** 스크리닝(1회) 수치만으로 채택 결론을 내리는 비판/제안을 하지 않는다.

## 3. main 브랜치 규약

main 위에서는 코드 편집 금지(검토자는 어차피 편집하지 않으므로 해당 없음). plan/문서의 정본 채널은 main의
`docs/**`다 — 검토 대상 문서는 거기서 읽는다.

## 4. 우선 참조 문서

- 설계 제약 정본 → [CLAUDE.md](CLAUDE.md)
- 협업 규약(요청/회신) → [docs/COLLAB_GEMINI.md](docs/COLLAB_GEMINI.md)
- Phase 정의·완료 기준 → [ROADMAP.md](ROADMAP.md)
- 실험 기록(이전 시도·결론) → [EXPERIMENTS.md](EXPERIMENTS.md) (활성; Exp-001~130은 [PHASE2_EXPERIMENTS.md](PHASE2_EXPERIMENTS.md) 아카이브)
- 미정 설계 사항 → [docs/OPEN_QUESTIONS.md](docs/OPEN_QUESTIONS.md)
- 파일 색인 → [docs/FILE_INDEX.md](docs/FILE_INDEX.md)

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
