# Goal Prompt — 코드스위칭 후속 개선 루프 (Exp-153 이후)

> **이 파일을 새 Claude Code 세션의 첫 메시지로 붙여넣는다.**
> Exp-150~153(GOAL_CODESWITCH_STRUCTURAL 단계 1·2 + diar-ON 배선)이 master에 채택된 **E4 상태**에서 이어지는 후속 루프다.
> Claude는 아래 **단계 A~E를 의존관계 순서로** 구현·측정·채택/기각하며 자율 진행하되, §보고 시점에서만 사용자 입력을 대기한다.
> **부모 문서 [GOAL_CODESWITCH_STRUCTURAL.md](GOAL_CODESWITCH_STRUCTURAL.md)의 §2 진행 규율·§5 측정 명령·§6 채택 기준·§7 보고 시점을 그대로 상속한다** (여기서는 그 위에 얹히는 새 baseline·새 단계만 정의). 두 파일이 함께 주어지면 **더 최신인 이 파일의 단계가 우선**한다.

> ⚠️ **진행 상황 갱신 (2026-07-05)**: **단계 A(PLC 재평가)·D(위생)는 완료**(Exp-154, 커밋 2e163c6). **단계 E의 단계3(조건부 리셋)은 기각**(Exp-155), **단계4(token-logprob)는 NO-GO**(Exp-156), **단계5(2-pass) 프로브 2a는 turbo로 통과** — 이후 `model_dir` 배선 버그 발견으로 2b/2c 중단, [GOAL_TURBO_MODEL_FIX.md](GOAL_TURBO_MODEL_FIX.md)에서 turbo 정상화 완료(Exp-158, ✅완료). **아래 §0의 baseline(E4, base 기질)은 전부 무효** — 현재는 turbo 기질(E5), [EXPERIMENTS.md](../EXPERIMENTS.md) 참조. 단계 B(트림 튜닝)·C(QualityGate 감사)·단계5 2b/2c는 held-out 측정 이후 재검토 필요(별도 후속).

---

## 0. 현재 상태 (2026-07-03, Exp-153 채택 후)

- **master = Epoch 4 (E4)**: E3 + diar-ON 언어전환 경로 배선 활성화(`lang_before_reset` fallback + `PuncSegment.hard_boundary`). 머지 `dc312bb`.
- **무엇이 켜졌나**: E3까지 dormant였던 트림 재디코딩 + 문장경계 마커가 diar-ON(측정 기본)에서 **실동작**. bong1 smoke 기준 switch=True 9·마커 7·트림 1.
- **무엇을 얻었나 / 잃었나 (정직하게)**:
  - ✅ 전환 경계 단어 보존(§3.2/Q4) · **ytn2 worst-case WER 29.1→26.1 + 분산 붕괴(stdev 0.5%)**
  - ⚠️ **F1 전 파일 하락**(마커 과분할, 일부 metric-mismatch) · **재디코딩 filler 신규 환각**(전환 직후 "You know, in Bukhpil, there."류 ytn2 3회 일관 · bong1 R3 "sorry"×9)
  - ➡️ 플랜 1차 가설(F1 개선)은 실패. 실제 이득은 worst-case + 구조 활성화. 채택은 사용자 결정(게이트 혼합).
- **이 후속 루프의 목적**: Exp-153이 **열어놓은 능력을 활용**(A)하고, **새로 만든 비용을 상환**(B·C)하며, **원 로드맵 잔여 단계로 복귀**(E)한다.

### 새 baseline (E4, Exp-153 N=3 — 채택값 = 이후 게이트 기준, ⚠️base 기질·무효 — turbo baseline은 EXPERIMENTS.md 참조)

| 파일 | WER median | WER **max**(게이트) | F1 median | 특성 |
|------|-----------|------|-----------|------|
| bong1 | 36.3% | **37.5%** | 36.8% | 다화자·웃음 비음성 |
| ytn2  | 25.6% | **26.1%** | 47.6% | 짧은 텀 코드스위칭 (median은 filler로 +2.0 악화 상태 — 회복 대상) |
| sbs1  | 20.2% | **26.8%**(변산) | 16.7% | 한국어 중심·중간 영어 |
| **평균** | **27.4%** | — | 33.7% | 최종 목표 avg<15% (GOAL_WER15 공유) |
| held-out | ytn1 33.1 / eng1 3.8(=base, 무회귀) | | | |

> **주의**: ytn2 median 25.6은 filler가 얹힌 값 → 단계 A·B가 이를 회복시키는 것이 1차 목표. sbs1 max 26.8은 Exp-153서 변산 인정.

---

## 1. 단계 정의 (A~E)

### 단계 A — Exp-154: PLC 재평가 (filler 공동 계측) 【기승인 · 최우선】

**브랜치**: `exp/plc-reeval` · **성격**: 파라미터만(코드 변경 없음)

**배경**: `periodic_lang_check`(PLC)는 과거 3회 기각(Exp-131/143/145)됐으나 전부 **전환 세금 미제거·클록 버그 상태**였다. 이제 전제조건이 처음 충족 — Exp-151(PLC 절대클록 수정) + Exp-153(전환 배선 활성화). PLC는 **화자전환·침묵 트리거가 없는 전환**(ytn2 동시통역의 무휴지 en→ko)을 잡는 유일한 경로다.

**구현/측정**:
- `--periodic-lang-check 4.0` N=1 스크리닝 → 유망 시 N=3. (유망하면 `2.0`도 비교.)
- **filler 공동 계측 (필수)**: PLC는 재감지를 늘려 → 트림 재디코딩 횟수↑ → **Exp-153 filler를 증폭**할 수 있다. 매 회차 `--trace-tokens`로 서버 로그의 `switch=True` 빈도 + filler 문자열(`"You know"`·`">>"` 등) 발생 수를 before/after 집계.

**1차 관찰**: ytn2 WER median 회복(25.6→) + 전 파일 max 미회귀. F1(무휴지 전환 경계 포착으로 recall 개선 여지).
**채택**: ytn2 개선 + max 미회귀 + filler 미폭증. **기각 시**: 전환세금 제거·배선 완료 상태에서도 PLC가 악화면 "감지 자체의 문제"로 확정하고 **PLC 영구 종료**(부모 문서 단계1 후속 규칙 계승). filler가 폭증하면 단계 B를 선행.

---

### 단계 B — 재디코딩 filler 억제 (트림 오버랩 튜닝)

**브랜치**: `exp/switch-trim-tuning` · **성격**: 파라미터/소규모 코드

**배경**: 전환 시 [align_att_base.py](../whisperlivekit/simul_whisper/align_att_base.py) `_trim_segments_to_recent(LANG_SWITCH_KEEP_SECS=2.5)`가 경계 오디오를 재디코딩하는데, 그 오버랩 구간이 filler 환각을 만든다(Exp-153 정성 확인).

**구현/측정**:
- `LANG_SWITCH_KEEP_SECS` 축소 스윕(2.0 · 1.5) N=1 → 유망 시 N=3.
- **Trade-off 측정**: 축소 → filler↓ 기대, 그러나 **너무 줄이면 보존하려던 전환 경계 단어를 다시 유실**. 전사 정성으로 "filler 감소 vs 전환 단어 유실"을 함께 본다.
- 대안(파라미터로 부족 시): 전환 직후 첫 배치 오버랩 생성 억제, 또는 filler suffix 매칭 드롭. **하드코딩·특정문구 암기 금지(§3.8)** — backend 대안 우선.

**1차 관찰**: ytn2 median 회복(filler 제거분) + 전환 단어 보존 유지 + max 미회귀.
**조건**: 단계 A에서 filler가 문제로 확인되면 A와 병행/선행. 아니면 후순위.

---

### 단계 C — Q1: QualityGate 부당 드롭 규명 【측정 후 사용자 결정 게이트】

**브랜치**: `exp/q1-qualitygate-audit` · **성격**: 계측 하니스 + 분석 (수정은 사용자 결정 후)

**배경**: Exp-153 하니스로 QualityGate 드롭 **볼륨**은 확보(N=3 per-run: bong1 54 / ytn2 43 / sbs1 18 — 매우 높음). 그러나 로그가 `[QualityGate] avg_logprob X < -2.000 — suppressing`처럼 **logprob만 남기고 버려진 텍스트는 안 남겨** legit-Korean vs 환각 분류 불가.

**구현/측정**:
1. **하니스 업그레이드(측정 동작 불변)**: [align_att_base.py](../whisperlivekit/simul_whisper/align_att_base.py) QualityGate WARNING에 **억제된 세그먼트 텍스트를 함께 로깅**. `[BatchRepeatFilter]`·CJK 드롭도 동일하게 텍스트 포함.
2. **계측**: 경로 C 재측정 → `.omc/server_logs`의 드롭 텍스트 vs `.omc/transcripts` 정답 대조 → **"정상 한국어인데 버려진" 비율** 산출(파일별).
3. **보고 → 사용자 결정**: 비율을 보고하고 수정 방향을 사용자가 택함:
   - QualityGate 드롭 → **버리지 말고 재디코딩**
   - **언어별 logprob 임계**(한국어는 분포가 달라 −2.0이 과도할 수 있음)
   - CJK 스팬 strip / BatchRepeatFilter 조건 강화
   - → 채택 시 **원 문서 단계 4(token logprob gate)와 합류**.

**주의**: 이 단계는 계측·규명이 본체다. 하니스 업그레이드는 저비용·독립이라 아무 때나 가능. **수정은 자율 채택/기각 금지 — 계측 보고 후 사용자 질의**.

---

### 단계 D — 코드 위생: 리뷰 deferred minor 정리 【저비용·측정 불필요】

**브랜치**: `exp/lang-switch-hygiene` (또는 위 단계에 묶어 처리)

Exp-153 opus 리뷰가 SHIP과 함께 남긴 2건 (동작 불변 수준):
- **D-1 — MLX 필드 패리티**: [mlx/decoder_state.py](../whisperlivekit/simul_whisper/mlx/decoder_state.py)에 `pending_language_switch: Optional[float] = None` 추가. 크래시는 아니나(non-slots 동적속성) 위생. CUDA 배포 경로 무관이라 저위험.
- **D-2 — ForeignLang `lang_before_reset` 처리**: [backend.py](../whisperlivekit/simul_whisper/backend.py) `"(speaking foreign language)"` 복구 경로가 `detected_language=None`은 리셋하나 `lang_before_reset`은 미처리 → 드물게 spurious 경계 1개. **⚠️ 지우면 정당한 전환을 억제할 수 있는 양날** — 단위테스트로 의도(유지 vs clear)를 명시적으로 고정하고 결정. 애매하면 현행 유지 + 주석.

**검증**: 단위테스트 + `ruff check`만. 동작 불변이면 경로 C 측정 없이 머지 가능(구조 무변경이라 epoch 유지). 다른 단계 브랜치에 묶어 커밋해도 됨.

---

### 단계 E — 원 로드맵 잔여 복귀 (GOAL_CODESWITCH_STRUCTURAL 단계 3→4→5)

Exp-153으로 단계 1·2가 완료됐으므로, 부모 문서의 **잔여 단계를 그대로 이어간다**:
- **단계 3 — 화자 전환 리셋 조건부화** (`exp/conditional-speaker-reset`): 부모 §3 단계 3 스펙 그대로. 1차 관찰 = sbs1 F1 회복 + ytn2 미회귀. **단, Exp-153의 `new_speaker` 변경(lang_before_reset 배선)과 상호작용 재확인** 필요.
- **단계 4 — 단어 단위 신뢰도 배관 + run 게이트** (`exp/token-logprob-gate`): 부모 §3 단계 4 스펙 + **단계 C의 Q1 규명 결과를 입력으로 반영**(QualityGate 부당 드롭 데이터가 이 단계의 임계·언어별 설계에 직결).
- **단계 5 — 2-pass 재전사**: ⛔ **자율 착수 금지**. 프로브(2a/2b/2c)까지만, 보고 후 정지.

### backlog (게이트 무관·후순위)
- **Q2 — 온점 재부착 (가독성 전용)**: [metrics.py](../whisperlivekit/metrics.py) normalize가 구두점을 전부 strip → 온점 재부착은 **WER·F1에 0 영향**. 순수 가독성이라 정량 루프와 분리.

---

## 2. 실행 순서 · 의존관계

```
A (PLC 재평가)  ──┬── filler 폭증? ──► B (트림 튜닝) 선행/병행
   기승인·최우선   └── 정상 ─────────► 다음
                    · A·B는 ytn2 median 회복(filler 상환)이 공동 목표

C (Q1 하니스+규명) ── 독립·저비용 ── 아무때나 착수 가능 ──► [사용자 결정] ──► 단계 4에 합류
D (위생 D-1·D-2)  ── 저비용·측정불필요 ── 다른 단계 커밋에 묶어 처리 가능

E (원 로드맵 3→4→5) ── A·B·C 정리 후 큰 로드맵 계속
   · 단계 4는 단계 C 결과를 입력으로 받음(선행 권장)
   · 단계 5는 프로브까지만(자율 금지)
```

**권장 1회차**: 단계 A(PLC)를 **filler 계측과 묶어** N=1부터. filler가 나쁘면 B로 분기, 아니면 C(Q1 하니스는 병행 가능)로.

---

## 3. 이 루프의 채택 기준 (부모 §6 상속 + 명시)

- **게이트**: ① max WER 미회귀 (**E4 baseline max**: bong1 ≤37.5 / ytn2 ≤26.1 / sbs1 ≤26.8) ② median 개선. **WER > F1**.
- **ytn2 특례 관찰**: Exp-153로 ytn2 max가 26.1로 낮아졌으므로 **ytn2 max 게이트가 타이트**(26.1). 후속 단계가 ytn2 max를 다시 29대로 올리면 회귀 — 주의.
- **§3.2 예외**: 언어전환 직결 기능(A·B·D-2)이 게이트 탈락 시 **자율 기각 금지 → 사용자 질의**.
- **epoch**: A·B·C는 파라미터/계측 위주라 **E4 유지**(구조 무변경). 단계 4(신뢰도 배관)가 실패모드를 바꾸면 E4→E5.
- **held-out**: 채택 후보 한정 ytn1+eng1 단회. **eng1 무회귀 필수**(Exp-153서 3.8% 유지 확인됨 — 후속도 지켜야 함).

---

## 4. 보고 시점 (부모 §7 상속 + 추가)

부모 문서 §7(단계 5 착수 전 / avg<15% 달성 / 단계 소진 / §3.2 게이트 탈락 / VBCable 사망)에 **추가**:
- **단계 C(Q1) 계측 완료 시**: 부당 드롭 비율 + 수정 방향 옵션 보고 → 사용자 결정 대기.
- **단계 A에서 PLC 영구 종료 판정 시**: 전환세금 제거 후에도 악화면 "감지 자체 문제"로 확정 — 방향 전환이므로 보고.

---

## 5. 참조 (부모 §8 + 추가)

| 파일 | 이 루프에서의 용도 |
|------|------|
| `EXPERIMENTS.md` (STATE) | **항상 먼저** — E4 baseline·epoch·Exp-153 결론 |
| `docs/GOAL_CODESWITCH_STRUCTURAL.md` | §2 규율·§5 측정·§6 기준·§7 보고 상속 + 단계 3·4·5 원 스펙 |
| `EXPERIMENTS_LOG.md` | `grep "Exp-153"` (배선·filler·과분할·Q1 계측 상세) / `Exp-142`(logprob 임계 근거) |
| `align_att_base.py` | `_apply_detected_language`·`_trim_segments_to_recent`(LANG_SWITCH_KEEP_SECS)·QualityGate 로그(단계 B·C 대상) |
| `backend.py` | `new_speaker`(lang_before_reset)·`end_silence`·ForeignLang 경로(D-2)·PLC 발동(단계 A) |
| `mlx/decoder_state.py` | `pending_language_switch` 미추가(D-1) |
| `.omc/server_logs/` | Exp-153 하니스 — QualityGate/switch/filler 계측(단계 A·C) |
| `scripts/eval.py` | `--periodic-lang-check`(단계 A)·서버 로그 하니스 |
