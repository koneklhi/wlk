# Goal Prompt — 문법-조건부 침묵 경계로 구 중간 과분할·Case B 제거 (무인 자율 루프)

> **이 파일을 새 Claude Code 세션의 첫 메시지로 붙여넣는다.**
> 목적: **같은 화자·같은 언어 연속 발화 중, 화자전환도 언어전환도 아닌 지점에서 짧은 pause만으로
> 문장이 구 중간(심하면 단어 중간)에서 두 줄로 잘리는 과분할**을 제거한다. 근본원인은 규명 완료
> (§1). 이 루프는 그 수정을 구현·측정·기록하고 채택 여부만 사용자에게 묻는다.
>
> ⚠️ **진행 규율 — 완전 자율 (사용자 장시간 부재 가정)**:
> - **모든 중간 판단(구현 세부·임계값 선택·재측정 여부·스크리닝 기각·재시도)은 자율 결정**하고 근거를 기록.
> - CLAUDE.md §4 "게이트 애매 시 사용자 질의"는 이 루프에서 **"판단 보류 + 최종 보고서에 질의 항목 축적"**으로 대체.
> - **유일한 사용자 질문 = 마지막 채택(머지) 여부.** 최종 산출물 = "채택/기각/판단유보 권고 + 전체 근거 +
>   사용자가 예/아니오만 답하면 되는 질문".
> - **master 머지는 절대 하지 않는다** — 채택 확정 측정까지 끝내고 브랜치에 커밋만 남긴 뒤 사용자 승인 대기.

---

## 0. 현재 상태 / 준비 (2026-07-10)

- **master = Epoch 5 (E5, turbo 기질), `d469ef7`** (Exp-175 스크립트-앵커 재감지 + eval-report-legend 머지 반영).
- **베이스라인·채택 게이트**: [EXPERIMENTS.md](../EXPERIMENTS.md) STATE 상단을 **정본**으로 따른다. 작성 시점 값:
  - 확정 게이트(max, Exp-161): bong1≤30.5% / ytn2≤34.5% / sbs1≤16.1%.
  - **★ 채택 우선순위 = regime v2** (EXPERIMENTS.md 현행 measurement regime 절):
    **화자분리 F1 worst-case 미회귀 → WER max 미회귀 → WER median 개선 → 문장분리 F1(후순위·Case A 허용).
    Case B(단어 중간 분절)는 수치 무관 hard-fail.** ← 이 루프의 1차 표적이 바로 Case B 제거다.
  - 2-F1 신 베이스라인은 재측정 단계 — STATE 표 F1 열은 구 regime이라 직접 비교 불가. **변동성이 크므로
    이 루프는 STATE 게이트 표를 맹신하지 말고 §3의 짝지음 A/B(플래그 ON/OFF 동일 세션)로 순효과를 직접 잰다**(Exp-175 방법).
- **신규 실측 증거원 (이 루프의 출발점)**: [.omc/transcripts/eval_report_20260710_1433.html](../.omc/transcripts/eval_report_20260710_1433.html)
  — 최근 baseline 3회 측정 리포트. **여기 색깔 하이라이트로 표기된 과분할·Case B 사례가 이 루프가 없애야 할 대상이다.**
- **워크트리 준비 (측정 전 필수 — 자율 수행)**: 기존 `worktrees/silence-split-koen-gate`는 base가
  `48df44b`(Exp-170 시절)로 **stale**(Exp-171/173/174/175 누락)이다. 현재 master에서 새로 준비한다:
  - `exp/silence-split-koen-gate` 브랜치를 현재 master `d469ef7`로 리셋하거나 새 브랜치를 판다.
  - `.venv`는 **메인 저장소 Junction 공유**(CLAUDE.md 워크트리 규약) — 새로 만들지 않는다.
  - **측정은 반드시 cwd=워크트리에서**([[worktree-eval-import-resolution]] editable 설치 함정), `--model-dir`·`--files`·
    `--sortformer-model`은 메인 저장소 절대경로 지정. 측정 전 import 경로·`vbcable=ok`([[vbcable-loopback-instability]]) 확인.

## 1. 근본원인 (규명 완료 — 실측·코드 확인. 재조사 불필요)

과분할 사례는 예외 없이 **침묵(silence) 경계 트리거**가 만든다(벤치마크 JSON `"trigger":"silence"` 실측 4개 run 일치, 위 리포트 재확인).

- **트리거 지점**: VAD 침묵 duration > `MIN_DURATION_REAL_SILENCE`(0.4s, [audio_processor.py](../whisperlivekit/audio_processor.py) `:29`)이면
  Silence 토큰이 `state.new_tokens`에 삽입(`:215-216`)되고, `tokens_alignment`가 이를 **무조건** 경계로 소비한다:
  - diar: [tokens_alignment.py](../whisperlivekit/tokens_alignment.py) `compute_punctuations_segments` `:285-296`(침묵 PuncSegment 분리자) +
    `get_lines_diarization` 병합 루프 `:401-427`(라벨 `:412-422`, 확정 `:426-427`).
  - 비-diar: `get_lines` `:499-516`(무조건 닫고 `finalized=True`, 라벨 `:505`).
- **핵심 결함**: 문법 판별기 `is_genuine_sentence_end`([sentence_boundary.py](../whisperlivekit/sentence_boundary.py) `:73-97`)는
  **온점 경로 2곳(`:278` `_punct_split_here`, `:457` `_nondiar_punct_split_pending`)에만 연결**되어 있고,
  **침묵 경로에는 미연결**이다. 그래서 "짧은 pause = 무조건 하드 경계". 두 예시를 판별기에 넣으면 정확히 "미종결"(False)
  판정("operational"→다음 어절 소문자 / "관련"→종결어미 아님)이므로 **판별기는 옳은데 연결이 안 된 상태**.
- **run 간 편차 = 0.4s 문턱 부근 VAD 민감도**(Exp-167 실측: 동일 pause가 0.39s 병합/0.45s 분할). 리포트에서 "이와 관련"이
  run마다 분리됐다 안 됐다 하는 것이 이 시그니처.
- **Case B(단어 중간 분절) = 이 결함의 최악 형태**: 위 리포트에서 hard-fail로 플래그된
  **ytn2 R2 "관련해서"→"관련. 해서"**, **sbs1 R1/R2 "올렸습니다"→"올렸. 습니다"**는 침묵이 **한 단어 내부**를
  끊은 것이다. 문법 게이트가 직접 제거한다: `is_sentence_final_ko("올렸")`=False, `is_sentence_final_ko("관련")`=False → **병합 판정**.
  (표시된 중간 온점은 ASR 원문이 아니라 `_append_terminal_punctuation` [audio_processor.py](../whisperlivekit/audio_processor.py) `:32-43`가
  finalized 세그먼트 끝에 붙인 것 — 잘못된 경계의 하류 증상이다. 경계를 없애면 온점도 사라진다.)
- **스코프 밖(이 루프에서 손대지 않음)**: bong1 "What was the." 류는 침묵이 아니라 **온점 경로**의 영어 환각마침표+대문자
  오분할(Exp-170 기지 실패모드) — 구두점으로 끝나는 닫힘은 이 게이트의 비대상. 정성 기록만 남긴다.

## 2. 설계 — 문법-조건부 침묵 경계 (grammar-gated silence boundary)

**핵심**: 침묵이 닫으려는 세그먼트가 **① 종결 구두점 없이 끝나고(=silence 라벨이 될 경우만)** ② 문법적으로 미완결이며
③ 침묵이 짧으면, 경계를 **생략**하고 다음 발화와 이어붙인다. 구두점으로 끝나는 닫힘(punctuation 라벨)은 현행 유지 —
"…간다." 같은 화이트리스트 밖 정상 종결의 과병합을 막는 스코프 격리다. 신규 언어별 문구 하드코딩 없음(§3.8) — 기존
형태소 판별기 + 침묵 길이 + 화자/언어 신호 조합만 쓴다.

**판정 규칙** (침묵 유효 span `d_eff`, 닫히는 텍스트 `T`(무구두점), 다음 발화 첫 어절 `N`):
- `d_eff >= SILENCE_HARD_SECS`(신설 상수, 초기 0.8s) → **현행대로 분할**(진짜 긴 침묵은 문법 무관).
- 미만이고 `T` 마지막 어절이 한국어 → `is_sentence_final_ko`면 분할, 아니면 **병합**.
- 미만이고 영어 → `N`이 대문자 시작이면 분할, 소문자면 **병합**, `N` 아직 없으면 **보류**(decide-late).
- **병합 필수 3중 조건**: 같은 화자(diar) ∧ 침묵/직전 세그먼트 `hard_boundary` 아님 ∧ `detected_language` 동일(None==None 허용).

**적대 검증에서 확정된 필수 보완 (구현 시 반드시 반영 — 초안대로 하면 깨진다)**:
1. **decide-late 원칙**: 게이트 판정은 침묵 도착 시점이 아니라 **B 첫 토큰 도착 시 또는 캡 만료 시**에 한다. AlignAtt 유보
   꼬리가 Silence보다 늦게 도착하므로(CASE1 메커니즘, `tokens_alignment.py:26-32`) 침묵 시점의 `T`는 불완전 —
   "보고했(+습니다 유보중)"을 개방 오판, "했습니다(+만 유보중)"를 종결 오판한다. diar는 매 틱 전체 재계산이라 자동 충족;
   비-diar은 pending 중 도착 토큰을 꼬리(`start < silence.start`)/새 발화 B로 구분해 **B 도착 시 완성 텍스트로 재판정**.
2. **확정 유예 이원화**: 게이트 대상 침묵은 `audio_time - silence.end >= PENDING_RESOLVE_CAP`(2.0s)에 분할 확정+finalize를
   **단일 스위치로** 결정; 그 외는 현행 `_apply_finalize_grace`(`:459-476`)의 `silence.start + FINALIZE_GRACE_SECS(2.0)` 유지.
   현행 start 기준대로 두면 B 디코드 지연(1~2s) 중 grace가 만료→finalized=True 방출→번역 발사([llm_translation/manager.py](../whisperlivekit/llm_translation/manager.py) `:38`,
   캐시 키 `:21-22`)→다음 틱 병합으로 텍스트 변경 = **확정 계약 위반**.
3. **결정 메모(diar)**: diar 무상태 재계산에서 캡 만료로 분할 확정한 뒤 B가 늦게 도착하면 병합으로 뒤집히는 플래핑을 막는다 —
   `resolved_split_silences: set`(키 `round(S.start,2)`), `_prune`(`:200-231`) 연동. ~15줄.
4. **hard_boundary 스탬프**: 토큰 순서 `[A…, SIL, LS, B…]`에서 SIL~LS 빈 스팬이 `previous_segment=None`이 되어
   `hard_boundary`가 소실된다(`compute_punctuations_segments` `:297-305`) → boundary 토큰이 빈 스팬을 닫을 때
   **직전 침묵 PuncSegment에 hard_boundary를 스탬프**해 언어전환을 넘는 병합을 구조적으로 차단.

**보조 규칙**: 화자 미귀속(speaker=-1) B는 병합도 분할확정도 않는 pending 지속(캡이 상한) / 연속 침묵은 span 누적으로 `d_eff` /
스트림 종료 시 `flush` 인자로 pending 강제 해소 / **불변식 `SILENCE_HARD_SECS ≤ 2.0`**(backend 2s 미만 침묵은
zero-gap 오디오 삽입으로 디코드 문맥 연속 → 병합 seam의 BPE 공백 보존, [backend.py](../whisperlivekit/simul_whisper/backend.py) `end_silence` 부근).

**불변 보존 (건드리지 않는 것)**: `all_tokens`의 Silence 토큰 **자체는 유지**한다(세그먼트 조립 계층에서만 경계 생략) —
언어전환 철회 스캔(`_retract_stale_language_tokens` `:170-171`)과 꼬리 재귀속(`_insert_with_reattachment` `:135`)의 **배리어**로 쓰이므로
제거하면 과잉 철회가 난다. 디코더/번역/diar용 침묵 큐 이벤트(`audio_processor.py:218`)는 0.4s 게이트와 무관한 별도 채널 —
**출력 계층만 바꾸므로 원리상 WER 중립**(Exp-170 선례).

**구현 위치·규모**: [tokens_alignment.py](../whisperlivekit/tokens_alignment.py)(병합 루프 재구성 +50~70줄·grace 분기 +12·메모 +15·스탬프 +8),
[sentence_boundary.py](../whisperlivekit/sentence_boundary.py)(게이트 헬퍼 — 기존 순수 함수 재사용),
[audio_processor.py](../whisperlivekit/audio_processor.py)(`SILENCE_HARD_SECS`·`PENDING_RESOLVE_CAP` 상수·`flush` 전달).
diar ≈120~150줄/함수 5개, 비-diar ≈60~80줄. **롤백 플래그 `SILENCE_GRAMMAR_GATE_ENABLED`**(조기 return, 격리·짝지음 A/B용) +
게이트 판정 전수 로깅(`[SilenceGate]` 태그: 위치·`d_eff`·꼬리어절·판정·다음어절·화자쌍·언어쌍·해소경로=merge|split_grammar|split_hard|split_cap|split_memo) — Exp-175식 오탐 감사.

## 3. 실행 계획 (자율 — 순서대로, 각 단계 판단 근거를 기록하며)

1. **사전 확인**: §0 워크트리 준비(현재 master 기반) + import 경로 + `vbcable=ok`.
2. **유닛테스트 먼저 (TDD)**: 신규 `tests/test_silence_grammar_gate.py`. 최소 케이스 —
   한국어 종결("…했습니다"+짧은침묵)→분할 / 한국어 미종결("올렸"·"관련"+짧은침묵)→병합(Case B 회귀 테스트) /
   영어 다음어절 대문자→분할·소문자→병합·다음어절 미도착→보류 / `d_eff≥HARD`→문법무관 분할 /
   구두점 종결("…간다.")→게이트 비대상(현행 분할 유지) / hard_boundary(언어전환) 인접 시 병합 차단 /
   화자 상이 시 병합 차단 / 연속 침묵 span 누적 / 캡 만료 분할 확정 + 재계산 불변(메모) / `flush` 강제 해소 /
   무력화 플래그 동작. **전부 통과 후 다음 단계**. (`.venv\Scripts\python.exe -m pytest` 직접 호출 — uv 금지.)
3. **Stage 0 — dry-run 계측 (동작 불변, 강력 권장)**: 게이트 판정을 **로깅만** 하고 경계는 현행대로. 스크리닝
   `--repeat 1 --trace-tokens` 테스트 3파일(bong1+ytn2+sbs1, diar-ON/Sortformer/CRT=3.0/PLC=None/beams=2/turbo,
   [.claude/commands/eval.md](../.claude/commands/eval.md) 기본). `[SilenceGate]` 판정표를 뽑아 **오탐(정상 종결을 병합 판정) 감사** +
   침묵 `d_eff` 분포 실측으로 `SILENCE_HARD_SECS` 초기값 확정(초안 0.8s = 실측 오분할 ≤0.45s에 여유, bong1 0.8~0.96s 반말
   참경계는 하드 분할 보존). catastrophic 오탐률이면 판정 규칙부터 교정.
4. **Stage 1 — diar 경로 구현 + 짝지음 A/B 스크리닝**: §2 게이트를 diar 경로에 구현(H1~H4 반영·메모 포함).
   **플래그 ON/OFF 동일 세션 짝지음**(`--repeat 1 --trace-tokens`)으로 순효과 측정 — 변동성 상쇄(Exp-175 방법).
   - **정성 필수**(전사 대조): ⓐ 리포트의 Case B 3건("관련해서"·"올렸습니다"·동종) 제거 확인, ⓑ 구 중간 과분할
     ("operational control"·"이와 관련해서"·"것으로 보입니다"·"선을 그었습니다"·"저 아들 놈이 아주…") 병합 확인,
     ⓒ **코드스위칭 경계(language_switch)·화자 경계(speaker_change) 유지 확인**(trigger 분포: silence↓, language_switch/speaker_change 불변이 회귀 센티널),
     ⓓ finalized-flip 카운트 0.
   - catastrophic(게이트 대폭 초과·환각 폭주·stall·화자 F1 붕괴)이면: 원인 분석 → 파라미터(HARD/CAP) 1~2회 조정
     재스크리닝 → 그래도 catastrophic이면 **기각 권고로 전환**(무한 튜닝 금지 — 조정 총 3회 상한).
5. **Stage 2 — HARD 스윕**: {0.6, 0.8, 1.0} × 스크리닝. 판단 지표 = "bong1 화자/문장 F1·recall 하락 최소 안에서 ytn2/sbs1
   과분할 제거 최대". 스윕은 방향 신호용(N=3 재측정 아님).
6. **Stage 3 — 채택 확정 (`--repeat 3 --trace-tokens`)**: 스크리닝 유망 시만. **fail-fast 금지** — 3회 전부,
   median+min/max/stdev. 하니스 버그(VBCable 무음/사망·포트 충돌·sibling 세션 충돌)만 즉시 중단·수리 후 재실행
   ([[vbcable-loopback-instability]] — 재부팅 불가 시 Audiosrv 재시작·프로세스 정리, 복구 불가면 그 시점 결과로 보고서).
   짝지음 A/B(플래그 ON/OFF) N=3로 순효과 확정.
7. **held-out (ytn1+eng1, 단회)**: 채택 확정이 게이트 통과 시만. **eng1 = 영어 병합 규칙(대소문자 판정) 회귀 감시로 특히 중요.**
   kinno는 정성 sanity(게이팅 제외).
8. **정성 종합**: `.omc/transcripts/` 전사 정답 대조 — Case B 잔존 0 확인, 과분할 개선 목록, 신규 오병합(두 문장이 한 줄) 사례 수집,
   코드스위칭/화자 경계 무결성.
9. **기록**: `/log-experiment`로 Exp-176(또는 다음 번호) — EXPERIMENTS_LOG 전체 서술 + EXPERIMENTS.md 빠른참조 1행.
   커밋은 워크트리 브랜치에만.
10. **최종 보고서 작성 후 정지**(§5 형식). **머지하지 않는다.**

### 3.5 잔여 시간 자율 탐사 (본 임무 완료 후 — 유휴 정지 금지)

시간이 남으면 우선순위 순으로 반복(목적: 다음 루프 착수 대상을 실측 근거와 함께 준비):
1. **비-diar 경로 구현 + `flush`**: 동일 게이트를 비-diar(`get_lines` `:499-516`)에 이식(`_reattach_tail_nondiar`·
   `_nondiar_punct_split_pending`과의 순서는 §2 decide-late로 무충돌). 경로 A/내장 UI 정성 검증(비-diar은 정량 기준 경로 아님).
2. **잔존 과분할·오병합 카탈로그**: 스크리닝 회차 추가(`--repeat 1 --trace-tokens`)로 전사·`[SilenceGate]` 로그를
   정성 분석 — ⓐ 게이트가 못 잡은 과분할(트리거 미발동인지 규칙 보수성인지), ⓑ 오병합(반말·"습니까" 종결이 화이트리스트
   밖이라 병합된 참경계 — "니까" EXCLUDE 충돌 포함), ⓒ 화자 F1 영향. 파일·시각·정답/전사·로그 태그와 함께.
3. **개선 방향 도출**: 유형별 근본원인 가설 + 수정 후보(파일:라인·리스크·관련 회귀 교훈). **구현하지 않음** — 설계 제안까지만.
4. **산출물**: `docs/BACKLOG_SILENCE_GATE_FOLLOWUP.md`에 우선순위 순 기록(최종 보고서에서 링크). 형식 =
   "증상 → 실측 근거(로그/전사 인용) → 가설 → 제안 방향 → 예상 게이트 리스크".

**탐사 규율**: 코드 변경은 §3-4의 조정 3회 상한 안에서만(신규 기능 구현은 §3.5-1 비-diar 이식만 허용) / 탐사 측정은 스크리닝만 /
매 회차 VBCable 확인, 복구 실패 시 그때까지 결과로 보고서 마무리 / 발견이 본 임무 채택 판정을 뒤집으면 탐사 산출물이 아니라
**본 보고서 게이트 판정에 반영**.

## 4. 채택 게이트 (hard — 최종 권고 판정 기준, regime v2)

우선순위 순서(EXPERIMENTS.md 현행 regime):
1. **Case B(단어 중간 분절) 0건** — 리포트 플래그 3건이 제거되고 신규 Case B 미발생. **수치 무관 hard-fail 항목.**
2. **화자분리 F1 worst-case 미회귀** — 게이트가 화자 경계를 흐리지 않았는지.
3. **WER max 미회귀** — 테스트 3파일(bong1은 Exp-174 전례처럼 필러/웃음 기존모드 초과면 정성 대조 후 판단 유보 항목으로).
4. **WER median 개선(또는 중립)** — 출력 계층 전용이라 중립 기대, "올렸 습니다"류 공백 join 해소로 소폭 개선 가능.
5. **문장분리 F1** — 후순위. 과분할 감소로 상승 기대(상한 시뮬레이션 ytn2·sbs1 대폭 상승)하나 하락해도 Case A면 허용.
6. **held-out(ytn1+eng1) 미회귀** — 특히 eng1 영어 규칙.
7. **코드스위칭/화자 경계 무결성** — language_switch·speaker_change 트리거가 게이트 발동과 인과로 소실/오생성된 사례 0건.

이 수정은 §3.1 폐쇄망·§3.2 두 언어 고정 **불변 제약에 직결되지 않는 품질 개선**이므로 일반 채택 규율 적용 —
단 Case B는 STATE가 명시한 hard-fail이고 사용자가 직접 지목한 표적이므로, **정량이 애매하면 자율 기각/채택 대신
"판단 유보 + 증거 정리 + 사용자 질의"**로 보고서에 남긴다.

## 5. 최종 보고서 형식 (루프 종료 시 사용자에게 제시)

1. **한 줄 결론**: 채택 권고 / 기각 권고 / 판단 유보.
2. 정량 표(짝지음 A/B 스크리닝·N=3·held-out, baseline 대비 — 화자F1·문장F1·WER median/max 분리) + 게이트 7항 판정 표.
3. **정성 핵심**: Case B 3건 before/after 전사 인용, 구 중간 과분할 병합 사례 인용, 코드스위칭/화자 경계 무결성 근거.
4. 자율 결정 이력(HARD/CAP 선택·조정·재측정 근거) + 신규 오병합 관측.
5. 미해결·후속(비-diar 이식 여부·"습니까" 화이트리스트 보강·bong1 온점경로 오분할) + §3.5 수행 시 `BACKLOG_SILENCE_GATE_FOLLOWUP.md` 링크·상위 3개.
6. **사용자 질문은 단 하나**: "master에 머지(채택)할까요?" — 예/아니오로 답할 수 있게.

## 6. 회귀 교훈 (반드시 준수)

- **decide-late 필수**: 침묵 도착 시점 판정 금지(AlignAtt 유보 꼬리) — B 도착/캡 만료 시 완성 텍스트로 판정(§2-보완1).
- **유예 이원화 필수**: finalized 방출 후 텍스트 변경 = 번역 캐시 오적중·UI 깜빡임. 게이트 침묵은 `silence.end` 기준 캡(§2-보완2).
- **Silence 토큰 제거 금지**: 철회/재귀속 배리어(`:170-171`,`:135`) — 표시 계층에서만 병합.
- **hard_boundary/화자/언어 3중 조건 없이 병합 금지**: 코드스위칭·화자 경계를 넘는 병합 = §3.2/§3.3 위반.
- **`SILENCE_HARD_SECS ≤ 2.0` 불변식**: 넘으면 backend 리셋 구간이라 seam 보증 없음.
- **데이터 특화 하드코딩 금지(§3.8)**: 특정 단어·구절 암기 아닌 형태소·신호 조합만.
- **공유 .venv 가드레일**: `uv run`/`uv sync`/`uv pip` **절대 금지**([[shared-venv-uv-run-concurrency-hazard]]). lint·pytest는
  `.venv\Scripts\python.exe -m ruff` / `-m pytest` **직접** 호출.
- **측정 정본**: 경로 C만, provenance 육안 확인(`branch=…@… vbcable=ok`), 스크리닝=`--repeat 1`(방향 신호)·채택확정=`--repeat 3`(fail-fast 금지).

## 7. 기록·연동 문서 (채택 시 사용자 승인 후 동일 작업 단위 — 보고서에 체크리스트로만 포함)

- [docs/SENTENCE_FINALIZATION_LOGIC.md](SENTENCE_FINALIZATION_LOGIC.md): §3.1(침묵 경계에 문법 게이트 추가) · §5(`SILENCE_HARD_SECS`·
  `PENDING_RESOLVE_CAP` 상수 행, "잠정" 태그) · §7 규약. **덤으로 기존 문서-코드 불일치 정정**: ① 다수 file:line 앵커가
  구버전(예: 비-diar 침묵 확정 `:374,377` → 실제 `:504,505`), ② §3.4 트리거 우선순위 문서(`…>speaker_change>…>silence`)와
  코드(`language_switch>silence>speaker_change>punctuation`, `:412-422`) 불일치.
- master 머지 후 `/update-master-changes`. **epoch 판단**: 출력 계층 전용(Exp-170 선례 = 미bump)이되 STATE 세대경계 규칙으로 최종 판단.
- 후속 백로그: deepgram_compat 라인 **개수** 기반 증분 전송(`deepgram_compat.py:161-170`)이 라인 수 감소 시 스킵 — finalized 기반 전송으로 별건 수리.
