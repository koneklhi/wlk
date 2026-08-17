# ytn2 언어전환 경계 유령 stub("In.") 중복 수정 계획

## Context

2026-08-14 전수 스크리닝(eval_all9_20260814_0844)에서 ytn2 전사에 `In. ⟨language_switch⟩` stub 문장이
확정된 직후 `In support of these ends, ...`가 다시 확정돼 "In"이 중복 출력됨(spk2·ko로 오귀속).
사용자 요구 = 원인 규명 + **다른 곳 성능 회귀 없이** 수정. 같은 패턴이 과거 run에서도 반복
(ytn2_C_R2 `there.`→"There is more work...", kinno `Today.` 등). 반면 bong1 `네.`/ytn1 `감사합니다.` 등
실발화 stub은 보존해야 함.

## 근본 원인 (코드 검증 완료)

**실발화 반복이 아니라 언어전환 재디코딩 아티팩트.** 인과 사슬:

1. 전환 감지 직전, ko 잠금 디코더가 영어 서두 "In support of"를 `detected_language='ko'` 스탬프로
   커밋·방출 (증거: 서버 로그 `[QualityGate] (lang=ko): in support`, `[SwitchTaxMeasure] 3/5 겹침
   tail=['했습니다','.','In','support','of']`).
2. 마커 방출 직전 철회(Exp-171)가 3단어를 정상 tombstone — 여기까진 설계대로
   ([tokens_alignment.py:233](../../Desktop/260605wlk/wlk/whisperlivekit/tokens_alignment.py) `_retract_stale_language_tokens`).
3. **직접 원인**: `boundary_reconcile.py:146 resolve()`의 복원/대체 파티션이 **순수 시간 기준**
   (컷 T=신언어 토큰 최소 start, `T-COVER_TOL(0.5s)` 미만 전량 복원). 재디코딩 타임스탬프가
   0.5s+ 뒤로 재앵커되면 텍스트가 문자 그대로 재방출됐는데도 유령 'In'을 복원
   ('support','of'는 컷 위라 영구 대체 — 관측과 정확히 일치). 복원 자체는 Exp-173 교훈
   (철회 후 미복구=순유실) 방지 장치라 제거 불가 — **텍스트 동일성 확인 없음**이 결함.
4. 복원된 'In'은 마커 앞 위치 → `tokens_alignment.py:759-762` hard_boundary 분기(무조건 확정,
   :750-752 병합 금지)로 stub 확정. 온점은 `audio_processor.py:32-43` 후처리 부착.
   spk2 귀속은 max-overlap 정상 동작.
5. 방어막 전멸 이유: dedup supersede(`boundary_reconcile.py:354`)는 new_lang 스탬프만 후보(ko 유령 제외,
   유닛테스트도 'en' 유령만 커버); **별개 확정 버그** — `align_att_base.py:327`이
   `cumulative_time_offset` 누락(같은 함수 :307-309는 올바른 3항 공식) → boundary_t 최대 27s+
   과소평가 → dedup_batch 전면 no-op·D1 첫 토큰 즉시 마감·floor 무력화; `_filter_cross_batch_repetitions`는
   1단어·인접·미정규화 비교라 원리적 미포착; `[SwitchTaxMeasure]`는 관측 전용; stub 억제 로직 부재.
6. 로깅: eval 서버 로그는 root=WARNING(`basic_server.py:25`) — `[RetractScan]`/`[Restore]` INFO는
   `--trace-tokens`를 줘야 기록됨(`eval.py:736-737` → `basic_server.py:31-45` 로거 승격).

## 수정 설계 — A/B 분리 (A 먼저, B는 별도 브랜치·별도 실험)

### A안 (주력, Exp-207): resolve() 텍스트 커버 가드 — `fix/boundary-ghost-textcover`

**파일: `whisperlivekit/boundary_reconcile.py`**

1. `ReconcileWindow.observe()`에 관측 텍스트 수집 추가: `observed_texts: List[(start, _dedup_norm(text))]`
   (cap `_OBSERVED_TEXT_CAP=64`).
2. `resolve()`의 시간 파티션+단어스냅 직후, **컷 인접 entry부터 아래로 단조 확장**:
   복원될 tombstone의 정규화 텍스트가 관측 신언어 토큰과 **완전일치**(+`abs(Δstart) ≤
   TEXT_COVER_SLACK_SECS=2.5` 잠정)하면 복원 대신 대체. 비일치 즉시 중단(구멍 금지 = 단일 컷포인트
   불변식 보존 → Case B 구조적 불가). 순수 구두점 tombstone은 look-through. 관측 **1:1 소비**로
   실발화 반복 보호. 대체 시 `[TextCover]` INFO 로그(기존 tokens_alignment 로거 채널).
3. 롤백 플래그 `RECONCILE_TEXT_COVER_GUARD_ENABLED=True` (`:46-56` 관례, monkeypatch 가능).
4. (동일 PR, 관측 개선) `backend.py:929-940 [SwitchTaxMeasure]` 겹침 비교를 `_dedup_norm`
   (소문자화+구두점 제거)으로 교체 — "In."↔"In" 미포착 해소. 순환 import 없음 확인됨.

**실발화 보호 논리**: 텍스트 완전일치 + 시간 상한 + 컷 인접 연속만 + 1:1 소비 + 언어전환 창 스코프
+ 전용 플래그 + `[TextCover]` 전수 로깅(스크리닝에서 발동 건별 육안 검증, 모호하면 CLAUDE.md §4
원본 발화 확인 규칙대로 사용자 청취 확인). `네.`/`감사합니다.`류는 다음 문장과 텍스트 불일치라 비발동.
알려진 한계: 음차 변종(kor2 `You.`→"유무인")은 텍스트 불일치라 이번 범위 밖.
트레이드오프: 진짜 말더듬 반복("In... In support")이 전환 경계 + 텍스트 일치 + 2.5s 이내면 병합될 수 있음.

**테스트 추가 (`tests/test_boundary_reconcile.py`, 8건)**: ① ko 스탬프 유령 인시던트 정밀 재현
(기존 :473 테스트의 'en' 유령 사각지대 커버) ② 완전일치만(접두어 불허) ③ slack 초과 시 복원 유지
④ 1:1 소비(실반복 보존) ⑤ 비연속 대체 금지(구멍 없음) ⑥ 구두점 look-through ⑦ 플래그 OFF 레거시 거동
⑧ 단어스냅 Case B 방지.

### B안 (후속 별도 실험, Exp-208): 좌표계 수정 — `fix/langswitch-coord`

`align_att_base.py:327`에 `cumulative_time_offset` 추가(1줄, :330/:335는 파생이라 자동 정정).
롤백 플래그 없음(버그 좌표 유지 플래그는 모순) — revert+pin 테스트로 담보. 옵션으로
`RECONCILE_TIMEDEDUP_ENABLED` 세분 플래그(처음 실동작하게 되는 dedup_batch만 격리 OFF 가능하게).
pin 테스트 2건(`tests/test_lang_switch_wiring.py`): `pending_retract_from` 절대값을 토큰 좌표 공식과
대조(현재 tests/ 전체에 부재), 트림 전후 버퍼끝 절대시각 불변식.

**분리 사유**: A=국소 가드(리스크 소), B=dormant 방어선(dedup_batch·늦은커버·D3·zone2) 일괄
실활성화(리스크 대) → 회귀 귀속을 위해 1변경-1측정. 상호 비종속(A는 B 없이도 이 버그 클래스를 잡음 —
D1 조기 resolve여도 첫 신언어 토큰=유령 텍스트가 관측 집합에 항상 포함). B 머지 시 epoch bump(E7)
여부는 사용자 질의 사항(실패 모드를 바꾸는 구조 변경 가능성 — Exp-171/174/192 결론 재검증 태깅).

## 검증 절차 (A안 기준)

0. 워크트리: `git worktree add worktrees/ghost-textcover -b fix/boundary-ghost-textcover master`
   + `.venv` Junction(`mklink /J`) + test_data wav·모델 하드링크. **uv run/sync 금지**,
   lint는 `.venv\Scripts\python.exe -m ruff check` 직접.
1. 유닛: `.venv\Scripts\python.exe -m pytest tests/ -q` 전체 + 표적 3파일.
2. ytn2 재현 스크리닝(메인 세션, cwd=워크트리, VBCable 겹침 확인 후):
   `scripts/eval.py --files test_data/ytn2.mp3 --lan auto --repeat 1 --diarization
   --sortformer-model ... --compression-ratio-threshold 3.0 --trace-tokens
   --server-frontend-dir .omc/eval_empty_frontend` → ① stub 부재 ② `[TextCover]` 발동 건별 전사 대조
   ③ Case B 0건.
3. 전체 스크리닝: bong1/ytn2/sbs1/kor1~3 `--repeat 1 --trace-tokens` — bong1 `네.`/`감사합니다.`
   실발화 보존(오억제 0) 필수 확인, 화자분리 줄분리 유지, kinno `Today.` 소멸(정성 sanity).
4. 채택 확정(머지 직전): 표준 설정(--trace-tokens 없이) `--repeat 3`, fail-fast 금지.
   게이트: 화자분리 F1 worst 미회귀 → WER max 미회귀 → WER median → 문장분리 F1.
5. 기록: `/log-experiment` Exp-207(E6, auto) + `docs/SENTENCE_FINALIZATION_LOGIC.md` §3.2/§5 갱신
   (새 상수 "잠정" 태그, 손대는 행의 stale file:line 실측 정정).

## 위험 요소

- A안 오억제: 위 7중 방어 + 스크리닝 `[TextCover]` 전수 육안 검증으로 한정. 모호 건은 사용자 청취 확인.
- A안 한계: 좌표 버그(B) 미수정 상태에선 관측 집합이 작아 다단어 유령 깊은 단어는 미포착 가능 —
  실패 방향이 "현행 유지(복원)"라 회귀는 아님. B 머지 시 커버리지 자연 확장.
- 측정 분산(±30~120%p)이 개선폭 압도 — repeat 1은 방향 신호, 채택은 repeat 3 median+worst.

## 수정 대상 파일

- `whisperlivekit/boundary_reconcile.py` — A안 본체(observe/resolve, 상수·플래그)
- `whisperlivekit/simul_whisper/backend.py` — SwitchTaxMeasure 정규화(관측 전용)
- `tests/test_boundary_reconcile.py` — 8건 추가
- `docs/SENTENCE_FINALIZATION_LOGIC.md` — §3.2/§5 연동 갱신
- (B안, 별도) `whisperlivekit/simul_whisper/align_att_base.py:327` + `tests/test_lang_switch_wiring.py` 2건
