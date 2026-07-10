# CASE1 문장 꼬리 분리 수정 계획

## Context

사용자가 실시간 전사 테스트에서 3대 문제를 확인: **CASE1** 문장 꼬리(마지막 3~4음절) 분리, **CASE2** 코드스위칭 서두 유실, **CASE3** 환각 폭주. 방향 = 단순 성능 개선이 아니라 이 문제들의 순차 해결, **CASE1부터**.

### 근본 원인 (조사 완료 — 서버로그·코드로 실증)

꼬리 토큰의 **타임스탬프는 옳은데 커밋 순서가 틀리다**. 생성 경로 3중:

1. **커밋 순서 경쟁**: AlignAtt가 마지막 단어를 유보(frame_threshold=25≈0.5s≈3~4음절, `align_att_base.py:437-440`)하는 동안, `_end_silence`가 Silence 마커를 `state.new_tokens`에 **직접 append**(`audio_processor.py:199-200`, 큐 미경유) → transcription lag ≥ 침묵 길이면 마커가 꼬리보다 먼저 커밋 (flush 성공 경계 13개 중 3/6).
2. **flush 0토큰 방출(zero-emission)**: is_last flush는 QG **면제**(`align_att_base.py:405` — 초기 가설 정정)이지만, attention end-break가 is_last에서도 마지막 토큰을 드롭(`:382-389`)하는 등으로 flush의 46%(6/13)가 0토큰 → 꼬리는 발화 재개 후 재디코딩되어 마커 뒤 커밋.
3. **QG 3연속→refresh 버퍼 파괴**(1/13): 침묵 경계 인접 일반 배치의 구두점-only 억제가 streak을 채워 `refresh_segment(complete=True)` → 꼬리+다음 문장 서두("공")까지 유실. (`quality_suppress_streak`이 침묵 경계에서 리셋 안 됨.)

어느 경로든 꼬리가 Silence 마커 **뒤에** all_tokens로 들어가 다음 줄 첫머리가 되고, 확정된 앞 줄엔 후처리가 **무조건 온점 부착**(`audio_processor.py:562-566`) → "…올렸**.**" / "습니다. …". 유령 ". ." 줄은 구두점-only 세그먼트 병합이 filter의 `set(text)=={"."}` 검사를 공백으로 통과해 생김(`filtering/__init__.py:140` 부근).

정량: sbs1 정답 3문장 → hyp 8~12조각(전 run 재현), seg_f1 0.15~0.33. 화자전환·언어전환과 무상관(sbs1 로그 ChangeSpeaker 0회).

### 검증된 핵심 전제 (재귀속 성립성)

- 짧은 침묵(0.4~2.0s)에서 backend는 제로 오디오 삽입으로 버퍼 연속 유지(`backend.py:86-97`) → 재디코딩된 꼬리 토큰 start = 실제 발화 시각(침묵 **이전**). 재귀속 술어 성립.
- 긴 침묵(≥2.0s)은 refresh로 꼬리 폐기 + 앵커 전진 → 술어 false → 현행 동작으로 안전 강등.
- **함정**: 긴 침묵 앵커 재설정 시 직후 토큰 start가 침묵 end보다 최대 ~0.5s 앞으로 찍힐 수 있음 → 술어 기준은 silence.**end가 아니라 start** (`token.start + ε < silence.start`, ε=0.05).

---

## 수정 전략: 2단계 실험 (단일 변수 원칙)

### Exp-A — 정렬/확정 계층 방어 세트 (1차, 이번 구현)

워크트리 `worktrees/case1-tail-reattach` + 브랜치 `exp/case1-tail-reattach` (`.venv`는 Junction 공유: `mklink /J .venv ..\..\.venv`). 순수 로직 계층이라 유닛테스트 가능, 디코더 무접촉, 술어 실패 시 no-op(악화 없음). 상류(Exp-B)와 멱등 공존.

| # | 파일:위치 | 변경 |
|---|---|---|
| A0 | `scripts/analyze_case1_boundaries.py` (신규) | 서버로그 파서: Silence/QG/refresh 이벤트 → 경계별 zero_emission·qg_refresh·ordering_risk 비율 산출 (수정 전후 비교용) |
| A1 | `tests/test_tail_reattachment.py` (신규) | **실패 테스트 먼저**(TDD). 8케이스: diar/비-diar CASE1 재현, 유예 동작, 오귀속 방어(앵커 함정), LanguageSwitch 경계 불가침, 유령 온점, 온점 게이트, 연속 침묵. `test_finalized_flag.py`의 state 주입 패턴 재사용 |
| A2 | `whisperlivekit/filtering/__init__.py:140` | 구두점-only 판정 강화: `bare=text.replace(' ','')` 후 `set(bare) <= {'.','?','!','。','！','？'}` 드롭 (유령 ". ." 차단) |
| A3 | `whisperlivekit/tokens_alignment.py:52` | `all_tokens.extend` → `_insert_with_reattachment`: 새 토큰이 일반 토큰이고 `token.start + 0.05 < 직전 Silence.start`면 그 Silence **앞에** insert. 스캔은 뒤에서부터 Silence만 통과, is_boundary/일반 토큰에서 중단. 상수 `TAIL_REATTACH_EPS=0.05` |
| A4 | `whisperlivekit/tokens_alignment.py:200-235, 259-289` | **finalize 유예**: trailing이 Silence이고 직전이 텍스트 세그먼트면 `audio_time - silence.start < FINALIZE_GRACE_SECS(=2.0, backend refresh 임계와 동기)` 동안 finalize 보류. 종료 조건 = 다음 발화 토큰 도착 or 2.0s cap. `get_lines`는 이미 `audio_time` 보유(`:243`) → `get_lines_diarization(audio_time)`로 전달. 비-diar 경로(`:259-289`)는 validated 누적형이라 재귀속+유예를 루프 내 개별 처리 |
| A5 | `whisperlivekit/audio_processor.py:562-566` | 온점 부착에 `seg.finalized` 게이트 추가 → 유예 중(꼬리 미도착) 세그먼트에 온점 안 붙음 → "올렸." 소멸. 부착이 `apply_translations`(`:567`)보다 앞이므로 번역 캐시 키는 최종 텍스트로 1회 형성 |

**번역 트리거 결합**: 번역은 finalize에 발동(캐시 키 `(start, text)`, `llm_translation/manager.py:19-22`). 유예 없이 재귀속만 하면 불완전 텍스트로 이중 번역 → A3와 A4는 한 세트. 추가 번역 지연 ≤ min(≈1.5s, 2.0−침묵길이), CASE1 창(0.4~2.0s 침묵)에서만 발생.

**잔존 위험(수용)**: 유예 만료(>2s) 후 pre-silence 타임스탬프 꼬리가 도착하면 finalize 후 텍스트 변경 → 이중 번역. 단 ≥2s 침묵은 decoder refresh가 꼬리를 폐기/재앵커하므로 사실상 도달 불가 — 유닛테스트 4로 앵커 함정만 방어하고 모니터링.

### 구현 조정 (실제 반영 — 서브에이전트 보고 + 검토 완료)
1. **비-diar 재귀속은 별도 함수**: 비-diar 경로는 all_tokens를 안 읽고 new_tokens→validated_segments 누적형이라, A3의 `_insert_with_reattachment`(all_tokens 재정렬, diar 경로만 유효)와 별도로 `_reattach_tail_nondiar()`를 만들어 validated_segments 말미 `[텍스트,침묵]`에 꼬리 병합(tokens_alignment.py:264). Whisper 워드 토큰이 선행 공백을 품으므로 `prev.text + token.text` 무구분자 결합이 한/영 모두 정상.
2. **finalize 유예는 통합 패스**: `get_lines_diarization(audio_time)` 시그니처 변경 대신, diar/비-diar이 만든 segments에 공통 적용되는 `_apply_finalize_grace()`를 `get_lines` 말미(tokens_alignment.py:355)에서 1회 호출 — 덜 침습적.
3. 온점 부착은 `_append_terminal_punctuation()` 모듈 함수로 추출(audio_processor.py:32) + finalized 게이트. `compute_new_punctuations_segments`는 dead code라 미변경.
- 검증: pytest **137 passed, 1 skipped**(신규 8케이스 + 기존 회귀 무결), ruff 클린(기존 E402만 잔존, 무관).

### N=3 채택 확정 측정에서 발견된 회귀 및 근본 수정 (2026-07-06)
Exp-A+B 결합 N=3 스크리닝에서 ytn2 max가 베이스라인(34.5%) 대비 46.3%로 회귀. WER은 lines[] join 결과로 계산됨을 확인(scripts/vbcable_test.py:199 `.linesTranscript .textcontent`) — 재귀속이 세그먼트 텍스트를 직접 조작하므로 WER에 영향 가능하다는 전제로 격리 진단 실시:
- 환경노이즈 통제(순수 베이스라인 오늘 재측정): ytn2 [29.1, 24.6] — 정상, 오늘 환경 문제 아님.
- Exp-A **단독**(B1/B2/B3 제외)도 ytn2 [37.9, 30.5]로 회귀 — B2가 원인이라는 최초 가설 기각, **재귀속 로직(A3) 자체**가 원인으로 특정.
- 회귀 회차 전사 확인: "President Trump: These goals" 등은 전형적 디코더 환각(CASE3)이지 텍스트 스플라이싱 흔적이 아님 — 재귀속이 직접 오답을 생성한 게 아니라, **거리 상한 없는 술어**가 타임스탬프 불안정 구간(ytn2의 잦은 언어전환·backend 에러)에서 무관한 발화를 잘못 병합할 이론적 허점이 있었음.
- **수정**: `TAIL_REATTACH_MAX_LOOKBACK_SECS=1.5` 추가(`tokens_alignment.py`) — 정상 유보 폭(~0.5s)의 3배 여유, 구조적 상한(데이터 특화 아님). `_insert_with_reattachment`의 while 조건에 `silence.start - t.start <= 1.5` 추가.
- **재측정 결과**: ytn2 N=3 [19.7, 26.6, 25.6] median=25.6/max=26.6 — 베이스라인(28.1/34.5)보다 **개선**. pytest 154 passed 유지.
- 교훈: 워크트리 진단 중 `cd`로 실수로 main 저장소(master)에 진입해 `git checkout 40f65f2 -- <2파일>`을 실행한 적 있음 — 다행히 그 두 파일은 Exp-A가 건드리지 않아 diff 0(무해)이었음을 확인. 이후 워크트리 절대경로를 매 명령 앞에 `cd`로 명시하는 습관으로 전환.

### Exp-B — 디코더/flush 계층 후속 (Exp-A 측정·기록 후 별도 실험)

1. **P1 순서 보장**: `_end_silence`의 직접 append 제거 → Silence end 마커를 transcription 큐 경유 커밋(`audio_processor.py:199-200, 367-371`) — flush 토큰이 항상 선행.
2. **P3 refresh 오발동 차단**: `end_silence()`에서 `quality_suppress_streak=0` 리셋 + 구두점-only 억제는 streak 미산입(억제 자체는 유지 — Exp-154 QG 안전성 보존). 경로 3은 실제 단어 유실이라 **WER 개선 여지**.
3. (선택) P2: is_last end-break의 마지막 토큰 드롭(`align_att_base.py:388`) 생략 — zero-emission 완화.

Exp-B는 Exp-A 결과를 보고 범위 확정(A가 F1을 회복하면 B는 경로 3의 단어 유실만 targeting).

---

## 검증

1. **유닛**: `.venv\Scripts\python.exe -m pytest tests/` (uv run 금지). A1 신규 8케이스 + 기존 `test_finalized_flag.py`·`test_metrics_segmentation.py`·`test_schema_aliases.py` 회귀 무결.
2. **린트**: `.venv\Scripts\python.exe -m ruff check` (직접 호출).
3. **통합 (경로 C, 자율 루프)**: VBCable 상태 확인(`vbcable=ok`) → **워크트리 cwd에서** eval.py 실행(editable import 함정 — 측정 전 import 경로 검증), 스크리닝 N=1, diar-ON 기본 설정. 동시 측정 금지.
   - **게이트**: WER max 미회귀(bong1≤30.5 / ytn2≤34.5 / sbs1≤16.1) — WER는 경계 이동이라 원칙상 무영향이어야 하며 변동 시 원인 규명.
   - **목표 지표**: sbs1 hyp 문장수 8~12 → ≤5, seg_f1 0.17 → 상승. `analyze_case1_boundaries.py` 전후 비교.
   - **정성**: `.omc/transcripts/`에서 "…올렸." / "습니다. …" 꼬리분리·". ." 줄 소멸 확인 (JSON 기준 — .txt는 평문화 주의).
4. 통과 시 **채택 확정 N=3**(fail-fast 금지, median+min/max) → `/log-experiment`로 Exp-167(번호는 STATE 확인) 기록 → master 머지. F1 산출 파이프라인이 바뀌므로 기록에 "F1 베이스라인 비교성 변화(과분할 수정)" 명시. WER 실패모드 불변이라 epoch 마커는 유지(머지 시 재판단).

## 실행 방식

메인 세션은 main에 머물고, 구현·측정은 서브에이전트를 워크트리 절대 경로로 디스패치(uv 가드레일·no_grad 규칙 프롬프트에 명시). 자율 루프 규칙에 따라 구현→측정→기록→채택/기각까지 자율 진행, major 방향 전환만 보고.

## 이후 로드맵 (이번 범위 밖, CASE1 완료 후)

- **CASE2 (서두 유실)**: 최우선 단서 = ytn2 run당 `SimulStreaming processing error: tensor size mismatch` **66~68회 폭주**(sbs1은 0회) — 언어전환 경계 backend 크래시 조사부터. 그다음 감지 지연×2.5s 트림 창, 트림 경계 onset 훼손.
- **CASE3 (환각 폭주)**: 오프라인 oracle floor 진단(모델 천장 vs 스트리밍 세금 분기) → 비-ASR 분류기 or 디코드 정책. ("MBC 뉴스…" 반복형은 base 시절 형태, 현재는 "Thank you" 연쇄로 발현 — 동일 문제.)
