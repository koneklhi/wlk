# Goal Prompt — 비음성 게이팅(Layer 3b) tail-probe + 전환경계 보존 스윕 (2시간+ 무인 루프)

> **이 파일은 무인(사용자 부재) 자율 세션의 운영 지침이다.** 지금 이 파일을 브리핑으로 받은 세션(또는 서브에이전트)은
> **사용자 개입 없이 2시간 이상** 가설 검증 → 구현 → 측정 → 분석 → 다음 단계 재진입 루프를 실행한다.
> **★ 특수 전제: 사용자는 부재중이며 어떤 질문에도 응답할 수 없다.** 기존 규율(CLAUDE.md §4, `.claude/commands/phase2-improve.md`)의
> "사용자 질의/확인/승인 대기" 지점은 전부 **§4의 무인 대체 규칙**으로 치환된다 — 질문하고 대기하는 순간 루프가 죽는다.
> 판단이 애매하면 기록하고, 되돌리기 쉬운 쪽을 잠정 선택하고, 다음 단계로 진행한다.
> 세션이 도중에 끊기면, 다음 세션은 이 파일 + `EXPERIMENTS.md` 최신 상태만 읽으면 이어받을 수 있다(§7).

---

## 0. 배경 — 왜 tail-probe가 "디코더 개조"가 아닌가

`EXPERIMENTS_LOG.md`에서 `grep "Exp-163"` / `grep "Exp-164"`로 전체 서술을 확인할 수 있다. 요약:

- **Exp-163** (필러 반복 후처리 필터, 기각): turbo의 지배적 실패모드인 "Thank you" 연쇄 필러를 cross-batch 반복 탐지로 잡으려 했으나, 필터가 스톰을 정확히 탐지해도 ①디코더가 refresh 후 필러를 **재생성**해 출력 드롭만으론 못 막고 ②storm 시 잦은 `refresh_segment`가 ytn2 정렬을 교란해 max WER 34.5→46.8로 catastrophic 회귀. **결론: 필러는 후처리가 아니라 원천(비음성 구간) 차단이 필요.**
- **Exp-164** (비음성 게이팅 원천 차단 시도, 기각): 두 기존 메커니즘 모두 실패.
  - **no_speech SOT 게이트**: 3파일 1221 세그먼트 **전부 정확히 0.000** — 구조적으로 무효. 원인: `_check_no_speech()`(`simul_whisper.py:338-345`)가 읽는 logits는 `infer()`(`align_att_base.py:277-330`)의 `input_segments = self._concat_segments()`(288줄, **롤링 버퍼 전체**, 최대 15s) → `self._encode(input_segments)`(289줄)로 얻은 **기존 디코드 logits를 재사용**한 것이다. 버퍼에 실제 발화가 조금이라도 섞여 있으면(거의 항상) no_speech 확률이 절대 오르지 않는다.
  - **VAC(Silero) 임계값**: 신호 자체는 살아있으나(mean 0.715, max 0.996) 개념적으로 부적합 — 웃음·필러는 실제 음성 에너지(성대진동)를 동반해 임계값을 올려도 "speech"로 통과된다. bong1 게이트 초과(34.4>30.5)로 기각.
  - **다음 가설로 명시된 것**: "(a) no_speech를 세그먼트 전체가 아니라 신규 **tail만** 판정하도록 구조 변경 (리스크 큼, 별도 설계 세션 필요)".

**이 문서의 핵심 주장: "tail만 판정"은 사실 디코더 개조가 아니라 이미 코드에 있는 패턴의 재사용이다.**

`detect_current_language()`(`align_att_base.py:250-273`)가 정확히 이 패턴으로 **언어**를 판정한다:
```python
# align_att_base.py:261-268 요약
window_samples = int(window_secs * 16000)
all_audio = self._concat_segments()
recent = all_audio[-window_samples:] if len(all_audio) > window_samples else all_audio
encoder_feature, _ = self._encode(recent)          # ← tail만 별도 인코딩 (전체버퍼 재사용 아님)
_, language_probs = self.lang_id(encoder_feature)   # ← SOT 1-스텝 단독 forward
```
그리고 `lang_id()`(`simul_whisper.py:207-210`)가 SOT 위치 logits를 단독 forward로 얻는 패턴이다:
```python
x = torch.tensor([[self.tokenizer.sot]] * n_audio).to(self.model.device)
logits = self.model.logits(x, encoder_feature)[:, 0]
```
**no_speech 확률도 같은 SOT 위치 logits에서 읽는다**(`_check_no_speech`가 이미 그렇게 함, `simul_whisper.py:341`: `probs_at_sot[:, self.tokenizer.no_speech]`). 즉 "tail-only no_speech 확률"은 `detect_current_language`의 tail-slice + `lang_id`의 SOT 단독 forward를 조합하고, 언어 확률 대신 no_speech 토큰 확률을 읽으면 된다 — **새 아키텍처가 아니라 기존 두 메서드의 재조합**이다.

**대가**: 이건 `_check_no_speech`처럼 이미 계산된 디코드 logits를 재사용하는 게 아니라, `detect_current_language`/`lang_id`처럼 **매번 추가 인코더 forward**가 붙는다(주기적 언어체크와 동일 비용 클래스, turbo 0.2s/사이클 — `align_att_base.py:253-257` docstring 참조). 진단 단계에서는 이 비용을 감수한다.

**★★★ 최우선 경고 — `@torch.no_grad()` 누락 금지 ★★★**
`detect_current_language`는 `@torch.no_grad()` 데코레이터가 있다(`align_att_base.py:249`). 이유는 그 메서드 docstring에 있다: 이 계열 forward가 `no_grad` 밖에서 실행되면 turbo 인코더(807M·32층)가 autograd 그래프를 보존해 forward가 **~160배 느려진다**(0.2s→32s) — 이것이 정확히 Exp-158의 실시간 stall 버그였다. **tail-probe를 새로 만들 때 이 데코레이터를 빠뜨리면 같은 사고가 재발한다.** 구현 직후 반드시 확인할 것.

---

## 1. 세션 시작 절차 (즉시 실행)

1. **`EXPERIMENTS.md`(STATE)를 먼저 읽는다** — 현재 epoch(E5)·baseline·이월 핵심사실 확인. LOG/ARCHIVE 통째 읽기 금지.
2. `EXPERIMENTS_LOG.md`에서 `grep "Exp-163"` / `grep "Exp-164"`로 위 배경의 원본 서술을 확인한다. **이 세션 시작 전에 Exp-165+가 이미 기록돼 있으면**(이전 무인 세션이 진행한 흔적) 그 블록도 읽고 이어서 진행한다 — 처음부터 다시 하지 않는다.
3. `git worktree list`로 기존 워크트리를 확인한다. 특히 `worktrees/nonspeech-gating`(브랜치 `exp/nonspeech-gating`)가 있는지 — **이 워크트리를 재사용한다(§3 P1). 새로 만들지 않는다.** 그 외 `exp-langswitch-keepsecs-sweep` 등 이 문서가 만들 예정인 워크트리가 이미 있으면 거기서 이어서 작업한다.
4. §6-1 잔여 프로세스 확인을 수행한 뒤 첫 측정에 진입한다.

---

## 2. 현재 baseline (E5, Exp-161 확정 — 변경 없음)

diar-ON, CRT=3.0, **PLC=None**, **audio_max_len=15.0**(CLI 기본값), beams=2.

| 파일 | WER median | WER max | WER min | WER stdev | F1 median | 측정 N |
|------|-----------|---------|---------|-----------|-----------|--------|
| bong1 | 30.5% | 30.5% | 29.3% | 0.7% | 50.0% | 3 |
| ytn2  | 28.1% | 34.5% | 24.6% | 5.0% | 38.5% | 3 |
| sbs1  | 14.9% | 16.1% | 13.1% | 1.5% | 16.7% | 3 |
| ytn1(held-out) | 21.5% | — | — | — | 38.1% | 1 |
| eng1(held-out) | 4.8% | — | — | — | 0.0% | 1 |

**확정 게이트(max)**: bong1 ≤ 30.5% / ytn2 ≤ 34.5% / sbs1 ≤ 16.1%.

---

## 3. 우선순위 큐 (P1 → P4, 순차 실행 — 동시측정 절대 금지)

각 P 항목은 "구현(필요시) → pytest → 스크리닝(N=1) → 분석 → (유망 시) 확정(N=3) → held-out(채택 후보만) → `/log-experiment` 기록 → 채택/기각 판단"의 동일 절차를 따른다(§5 측정 규율). 순서대로 진행하되, 한 항목이 시간을 다 써도 괜찮다 — 못 끝낸 항목은 §7 체크포인트로 다음 세션에 넘긴다.

### P1 — Exp-165: tail no_speech shadow probe (진단 전용, 동작 불변)

- **워크트리**: `worktrees/nonspeech-gating`(`exp/nonspeech-gating`, 최신 커밋 `99db307`) **이어서 작업**. 이 브랜치엔 이미 Exp-164의 `--nonspeech-prob`/`--vac-threshold` CLI 노출과 `[NoSpeechProbe]`/`[VacProbe]` 로깅 인프라가 있다.
- **구현**: `align_att_base.py`에 `detect_current_language`와 같은 패턴으로 tail-slice 진단 메서드를 추가한다(예: `probe_tail_no_speech(window_secs=2.0)`). 설계 스케치(그대로 붙여넣지 말 것 — 실제 텐서 shape·에러 핸들링은 `detect_current_language`/`lang_id` 기존 구현을 참고해 맞출 것):
  ```python
  @torch.no_grad()  # ← 절대 누락 금지. §0 참조.
  def probe_tail_no_speech(self, window_secs: float = 2.0) -> float | None:
      if not self.state.segments:
          return None
      window_samples = int(window_secs * 16000)
      all_audio = self._concat_segments()
      recent = all_audio[-window_samples:] if len(all_audio) > window_samples else all_audio
      encoder_feature, _ = self._encode(recent)
      x = torch.tensor([[self.tokenizer.sot]] * encoder_feature.shape[0]).to(self.model.device)
      logits = self.model.logits(x, encoder_feature)[:, 0]
      no_speech_prob = logits.float().softmax(dim=-1)[:, self.tokenizer.no_speech].item()
      logger.info("[TailNoSpeechProbe] 최근 %.1fs → no_speech=%.4f", window_secs, no_speech_prob)
      return no_speech_prob
  ```
  - 호출 지점: `infer()` 루프 안(`align_att_base.py:277-330` 부근), 기존 `_check_no_speech` 호출(329줄) 근처에서 **매 사이클 병행 로깅만** 한다. **아직 게이팅(break/skip/emit 보류)에 연결하지 않는다** — 이번 단계는 순수 계측.
  - `align_att_base` 로거는 이미 `basic_server.py`의 `--trace-tokens` DEBUG 승격 목록에 있다(확인됨 — 추가 배선 불요). `logger.info(...)`면 바로 보인다.
  - `window_secs`는 1.5~2.5 범위에서 시작해 진단 중 필요하면 조정(고정 스펙 아님 — 웃음/필러를 잡되 인접 정상 발화를 덜 섞는 값을 실측으로 찾는다).
- **측정**: pytest 통과 확인 후, bong1(웃음구간)·ytn2(필러구간) 각 N=1, `--trace-tokens`로 진단. **이 run의 WER/lag 수치는 probe의 추가 forward 비용 때문에 해석 대상이 아니다** — 확인할 것은 오직 (a) baseline과 WER가 크게 어긋나지 않는지(동작 불변 검증, probe는 로깅만 하므로 출력에 영향 없어야 함) (b) `[TailNoSpeechProbe]` 값과 전사 타임스탬프상 웃음/필러 구간의 상관관계.
- **분기 판정**:
  - **(a) 분리 가능** — 웃음/필러 구간에서 tail 확률이 유의하게 상승하고 정상 발화 구간과 구분되는 임계값이 관측됨 → **P3(게이팅 설계)로 진행**.
  - **(b) 분리 불가** — 웃음에서도 확률이 낮게 유지(VAC와 동일한 한계 재확인, 성대진동이 있으면 no_speech도 낮게 나올 가능성) → Layer 3b를 no_speech 계열로는 **폐기 확정**, `EXPERIMENTS_LOG.md`에 결론 기록 후 **P3 스킵**, P2로 진행.
- `/log-experiment`로 Exp-165 기록(계측 결과 + 분기 판정 근거 + 전사 정성 대조 필수). **워크트리 보존, master 미머지**(Exp-163/164 선례와 동일 — 진단 인프라는 결론과 무관하게 보존만 한다).

### P2 — Exp-166: `LANG_SWITCH_KEEP_SECS` 스윕 (전환경계 보존)

- **새 워크트리**: `exp-langswitch-keepsecs-sweep`(master 기준 분기, §6-4 관례).
- **구현**: `align_att_base.py:13`의 `LANG_SWITCH_KEEP_SECS = 2.5`(현재 하드코딩, base 기질 튜닝값 — epoch 게이트상 재검증 대상)를 CLI로 노출한다. Exp-164의 `--vac-threshold` 배선(`parse_args.py` 약 430-434줄, `backend.py` 설정 전달, `eval.py` 534-537줄 패스스루 `extra_server_args.extend([...])`)을 그대로 참고 패턴으로 삼아 `--lang-switch-keep-secs`(dest 예: `lang_switch_keep_secs`, `None`=서버 기본 2.5)를 동일하게 배선한다.
- **스크리닝(N=1)**: 3.5초·4.5초 각각 bong1+ytn2+sbs1. 목표는 WER 1순위 오류 유형 (B) — ytn2 전환경계 서두 단어·문장 유실 완화.
- **트레이드오프 확인 필수**: keep_secs를 늘리면 전환 후 재디코딩 범위가 넓어져 **재방출(전환세금) 부활** 위험이 있다(이게 원래 Exp-150~153에서 2.5초로 줄인 이유). 전사 정성 대조로 "서두 유실 감소"와 "반복/재방출 증가" 여부를 **함께** 판정 — 하나만 보고 채택 판단하지 않는다.
- 유망하면(서두 유실 감소, 재방출 증가 없음, 게이트 미초과) N=3 확정 + held-out 단회.
- `/log-experiment` 기록. 게이트 명확 통과 시 master 머지 가능(CLAUDE.md §4 자율 루프 원칙 — 선례: Exp-160/161).

### P3 — 조건부: Layer 3b 게이팅 설계 (P1이 (a) 분기일 때만 진행)

- P1의 `nonspeech-gating` 워크트리 위에서 계속.
- **설계 힌트(확정 스펙 아님 — 실제 구현은 판단이 필요하다)**: Exp-163의 교훈은 "파괴적 개입(버퍼 trim·refresh_segment)이 정렬을 교란한다"였다. 따라서 트리밍·refresh 계열 개입은 **1순위 후보에서 제외**한다. 대신 우선 검토할 방향: tail no_speech 확률이 임계값을 넘는 사이클에서 **그 사이클의 디코드 결과를 방출(emit) 보류**하거나 **해당 사이클의 디코드 자체를 스킵**하는 형태 — 버퍼·상태는 그대로 두고 "이번 것만 안 내보낸다". 정확한 훅 지점(디코드 전 스킵 vs 디코드 후 emit 단계에서 필터)은 `infer()`/`process_iter` 흐름을 분석해 결정한다.
- 구현 후 pytest → 스크리닝 → (유망 시) 확정 → held-out, P1/P2와 동일 측정 절차(§5).
- 시간이 부족해 확정까지 못 가면 스크리닝 결과 + 설계 메모(시도한 훅 지점, 관찰된 부작용)만 기록하고 §7 체크포인트로 다음 세션에 이관 — 무리해서 끝내려 하지 않는다.

### P4 — 여유 시간이 남으면 (스트레치)

P1~P3를 목표 시간 내 완료하고도 시간이 남으면, 아래 중 자유롭게 선택해 이어간다(순서 무관):
- STATE 이월 과제 — 후보 4(diar 과분할 F1, sbs1/bong1 precision 붕괴): 근원이 화자전환이 아니라 `tokens_alignment` 온점분할 로직으로 이미 규명돼 있다(sbs1 `new_speaker` 발동 0회, Exp-155). 그 분할 로직 자체를 재조사.
- P1/P2/P3 중 채택된 변경이 있다면 held-out 재확인 또는 worst-case 분산 축소 방향 추가 이터레이션.

---

## 4. ★ 무인 대체 규칙 — "사용자 확인 필요" 상황의 처리 (이 세션 한정)

기존 규율에는 사용자 질의로 에스컬레이션하는 지점들이 있다(§3.2 등 불변 제약 직결 기능의 게이트 탈락 시 자율 기각 금지, major 방향 전환 보고, `phase2-improve` 6단계의 승인 대기 등). **이 세션에서는 사용자가 2시간+ 응답 불가**이므로 다음으로 치환한다:

1. **기록**: 판단 근거·양쪽 옵션·왜 애매한지를 해당 Exp의 `EXPERIMENTS_LOG.md` 서술 안에 `**[무인결정]**` 태그로 명확히 남긴다.
2. **보수적 기본값 잠정 선택**: 되돌리기 쉬운 쪽을 고른다. 기본 패턴 = **master 미머지 + 기각 처리하되 코드는 워크트리/브랜치에 보존**(워크트리 제거 금지). 채택이 보수적인 경우(명백한 correctness 버그 수정)는 채택이 기본값.
3. **계속 진행**: 그 지점에서 대기하지 않고 다음 단계(P큐의 다음 항목)로 넘어간다.
4. **목록 관리**: 무인결정 지점을 만날 때마다 이 문서 §9에 1행씩 추가한다. 세션 종료 시 이 목록이 사용자가 복귀 후 가장 먼저 볼 요약이 된다.
5. **예외 — 계속 보류(무인결정으로도 하지 않는 것)**: master 강제 push·history 재작성, 파괴적 git 명령(`reset --hard`, 남의 워크트리 제거 등), 의존성 변경(`uv sync` 계열), 시스템 재부팅, `test_data/` 정답 파일 수정, 외부 서비스 발행. 이런 조치가 필요해 보이면 §9에 기록만 하고 우회하거나 다른 항목으로 전환한다.

적용 예: P3 게이팅이 게이트에서 탈락했지만 §3.2(한/영 고정) 관련 불변식 달성에 필요해 보이는 경우 → (기존) 사용자 질의 → (이 세션) 기각하되 워크트리 보존 + `[무인결정]` 기록 + §9 추가 + 다음 항목 진행.

---

## 5. 측정 규율 (CLAUDE.md §4 계승 — 요약)

- **경로 C(VBCable)만** 채택 판정 기준. 매 측정 첫 줄 provenance `[provenance] code=wlk branch=… vbcable=ok`를 확인 — `vbcable=ok`가 아니면 측정 무효.
- **cwd = 워크트리 경로**에서 측정(editable install 함정 — main에서 실행하면 다른 코드가 측정됨). 측정 전 `python -c "import whisperlivekit; print(whisperlivekit.__file__)"`로 경로 확인.
- **2계층**: 스크리닝 N=1(방향 신호로만 해석) → 채택 확정 N=3(median+min/max/stdev, fail-fast 금지). 하니스 버그(무음 캡처·포트 충돌·VBCable 사망)는 양쪽 모두 즉시 중단·수리.
- **채택 우선순위**: ① 최악 케이스(max WER) 미회귀 ② median 개선. **WER > F1**(F1 하락 있어도 WER 명확 개선이면 채택 가능, F1 catastrophic 폭주만 원인 파악 우선).
- **게이트(max)**: bong1 ≤ 30.5% / ytn2 ≤ 34.5% / sbs1 ≤ 16.1% (§2).
- **측정 기본 설정**: diar-ON(Sortformer) + CRT=3.0. held-out(ytn1/eng1)은 채택 후보에 한해 단회.
- **정성 평가 필수**: eval 완료 후 전사를 정답과 직접 대조해 목표 구간(웃음/필러 억제, 전환경계 보존) 개선 여부·신규 이슈를 판정. 정량·정성 상충 시 §4 무인 대체 규칙.
- **VBCable 사망 시**(RMS<0.01·100% WER·무음 반복): `verify_loopback`으로 진단 → `Restart-Service Audiosrv` 시도. 재부팅이 필요한 수준이면(무인 세션에서 재부팅 불가) **측정 불요 작업(코드 분석·구현 준비·문서화)으로 전환**하고 §9에 기록. 측정 없는 채택/기각은 하지 않는다.

### 측정 명령 레퍼런스

```powershell
$env:PYTHONIOENCODING = "utf-8"
$ts = Get-Date -Format "yyyyMMdd_HHmm"
$root = "c:\Users\A040-000-0001\Desktop\260605wlk\wlk"

# 스크리닝 (N=1) — 워크트리 cwd에서
Set-Location "$root\worktrees\<워크트리명>"
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir "$root\whisperlivekit\model\whisper-large-v3-turbo" `
  --files "$root\test_data\bong1.wav" "$root\test_data\ytn2.mp3" "$root\test_data\sbs1.mp3" `
  --diarization --sortformer-model "$root\whisperlivekit\model\sortformer-4spk-v2.nemo" `
  --compression-ratio-threshold 3.0 --trace-tokens `
  --output "$root\.omc\benchmarks\eval_${ts}_<가설명>.json"
Set-Location $root

# 확정 (N=3) — 위와 동일 + --repeat 3 (trace-tokens는 로그량이 커지므로 확정 단계에선 생략 가능)
```

---

## 6. 운영 안전장치 (이전 세션들에서 실제로 겪은 사고 — 전부 필수)

### 6-1. 동시측정 오염 방지 (Exp-158 실사고)

VBCable은 공유 하드웨어다. 두 측정이 동시 재생되면 전사가 교차 오염된다(실사고: sbs1 전사에 ytn2 참조문이 섞여 나옴). **새 eval.py/basic_server 실행 전 매번**:
```powershell
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'eval\.py|basic_server' } |
  Select-Object ProcessId, CommandLine
```
결과가 비어있지 않으면 진행 중인 측정(내 것)의 완료를 기다리거나, 유령 프로세스면 정리 후 시작한다. **두 측정을 동시에 돌리지 않는다.**

### 6-2. 장시간 실행 원칙

- 측정 명령은 "끝날 때까지 블로킹"한다 — 다른 작업을 병행하며 "나중에 확인하겠다"는 식으로 넘어가지 않는다. 완료 통지 전 새 측정을 시작하지 않는다.
- 이 문서의 P1~P4는 **순차** 실행이다(동시에 여러 워크트리를 측정하지 않음, 6-1과 동일 이유).

### 6-3. uv 가드레일 (공유 .venv 오염 = 병렬 측정 전멸 실사고)

- **금지**: `uv run` · `uv pip` · `uv add/remove/lock/venv` · extras 없는 `uv sync`. 암묵적 auto-sync가 tokenizers를 강등시켜 sortformer가 붕괴, 서버 returncode=3으로 측정이 전멸한다.
- lint는 `.venv\Scripts\ruff.exe check` 또는 `.venv\Scripts\python.exe -m ruff check` **직접 호출**.
- 의존성 변경이 필요해 보이면 → §4-5 예외(계속 보류) — 기록만 하고 우회한다.

### 6-4. 워크트리 관례

```powershell
$name = "exp-langswitch-keepsecs-sweep"   # P2 예시
git worktree add -b "exp/$name" "$root\worktrees\$name" master
cmd /c mklink /J "$root\worktrees\$name\.venv" "$root\.venv"   # 공유 venv Junction — 새 .venv 생성 금지

# import 경로 검증 (워크트리 cwd에서 — editable 함정)
Set-Location "$root\worktrees\$name"
.venv\Scripts\python.exe -c "import whisperlivekit; print(whisperlivekit.__file__)"
```
메인 세션 cwd는 워크트리로 옮기지 않는다(검토/디스패치는 repo root에서). 기각된 실험의 워크트리는 §4-2에 따라 **보존**한다(사용자 복귀 후 판단 여지).

### 6-5. git 커밋 규율

- 다른 세션이 이 저장소를 동시에 건드릴 수 있다 — **`git add -A` / `git add -u` 금지**, 변경한 파일만 명시적으로 stage.
- master 머지는 게이트를 명확히 통과한 채택 실험만. 머지 후 연동 문서 갱신(CLAUDE.md §4 표) + 구조 변경이면 STATE epoch 마커 갱신.

### 6-6. Windows 콘솔 인코딩

한글·특수문자(em dash 등)를 `print()`하면 cp949 크래시가 날 수 있다 — 출력은 ASCII로 쓰거나 `$env:PYTHONIOENCODING = "utf-8"`을 매 셸에서 명시한다.

---

## 7. 체크포인트 / 재개 전략

컨텍스트 압축·세션 중단에 대비해 **진행 상황은 항상 문서에 먼저 남긴다** — 문서에 없는 진행은 세션이 끊기면 소실된다.

- **매 Exp 완료 시 즉시** `/log-experiment` — LOG 전체 서술(Exp-165부터 이어감) + STATE 빠른참조 1행(Epoch=E5). 측정 JSON 경로 포함.
- **P 항목 전환 시마다** 짧은 진행 요약을 LOG 말미 또는 이 문서 §9에 남긴다.
- 무인결정 발생 시마다 §9에 1행 추가.
- 세션이 도중에 끊겨도, 다음 세션이 §1 시작 절차(STATE → Exp-164+최신 → `git worktree list`)만 수행하면 이어받을 수 있는 상태를 항상 유지한다.

---

## 8. 종료 / 최종 보고 조건

사용자가 없으므로 "보고 후 대기"는 없다 — 아래 각 경우 모두 **결과를 문서에 남기고 자연 종료**한다. **2시간은 목표치이지 하드 컷오프가 아니다** — P1~P2가 훨씬 일찍(예: 40분) 끝나고 P3도 해당 없으면(P1이 (b) 분기), 없는 일감을 억지로 만들지 말고 P4로 넘어가거나, P4도 소진되면 §8(b)로 정리하고 종료해도 된다. 반대로 P3 설계가 유망해 2시간을 넘겨도 명확한 진전이 있으면 계속해도 된다.

- **(a) P1~P4 모두 처리(완료 또는 무인결정으로 종결)**: 최종 결과·채택 이력·핵심 발견을 LOG 말미 + 이 문서 §9에 정리하고 종료.
- **(b) 탐색 공간 소진**: 현황·시도한 것 전부·기각 사유·남은 아이디어를 정리해 기록 후 종료.
- **(c) major 방향 전환 지점 도달**(예: P3에서 디코더 흐름 자체를 바꿔야 할 정도로 큰 변경이 필요하다고 판단되는 경우): §4 무인 대체 규칙 적용 — 되돌리기 쉬운 형태(워크트리 안에서만, master 미머지)로 진행하되 §9에 기록. master 머지가 필요한 수준이면 게이트 명확 통과 시에만 머지.
- **(d) 하드웨어 복구 불능**(VBCable 사망이 Audiosrv 재시작으로도 복구 안 됨): 측정 불요 작업 소진 후 상태·재현 로그를 기록하고 종료.

---

## 9. 사용자 확인 대기 목록 (세션 진행 중 갱신)

> 무인결정(§4)이 발생할 때마다 아래 표에 1행씩 추가한다. 사용자 복귀 후 최우선 검토 대상. (세션 시작 시점엔 비어있다.)

| # | Exp | 지점 | 잠정 선택(보수적 기본값) | 보존 위치 | 사용자가 결정할 것 |
|---|-----|------|--------------------------|-----------|--------------------|
| 1 | Exp-165 | P1 분기판정 (b)분리불가 → Layer 3b **no_speech 계열 폐기 확정** | 기각·폐기확정, master 미머지, 워크트리 보존 | `worktrees/nonspeech-gating`(`exp/nonspeech-gating`, `647f053`/`5b525d9`/`1350f99`), EXPERIMENTS_LOG.md Exp-165 | 폐기 확정 재확인(재검증 불필요) / 웃음 전용 비-ASR 분류기 방향을 별도 세션으로 열지 여부 |
| 2 | (해소됨) | ~~병렬 세션 동시 활성 감지~~ → **오판으로 확인**: 실재하는 병렬 세션은 없었음(사용자 확인). "병렬 워커"는 이전 활동이 남긴 **orphan 서브에이전트**(P2 코드 `21266b2`만 커밋 후 종료)였고 활성 측정 아님. Exp-165 기각 결론은 이 오판과 무관하게 유효 | 이 세션이 **단독 워커**로 P2(Exp-166) 측정·기록을 이어받아 완료 → **기각**(keep_secs 3.5/4.5 ytn2 미개선) | Exp-166 워크트리 `exp/exp-langswitch-keepsecs-sweep` 보존, EXPERIMENTS_LOG.md Exp-166 | (해소 — 별도 결정 불요) |

---

## 10. 불변 제약 (무인 세션에서도 변경 불가)

- **폐쇄망**: 런타임 네트워크 호출 금지. 모델은 로컬 경로만.
- **한/영 두 언어 고정**(§3.2): 관련 기능 게이트 탈락 시 §4 무인 대체 규칙(기각+보존+기록) — 코드 삭제 금지.
- **데이터 특화 하드코딩 금지**: 특정 단어·구절 암기 금지(예: ytn2의 특정 필러 문자열을 직접 차단하는 식의 접근 금지). 개선은 일반화돼야 한다.
- **경로 C만 채택 기준**. 경로 A(PCM 주입)는 폐기됨.
- **`test_data/`·정답 파일 수정 금지**.
- **`@torch.no_grad()` 누락 금지**(§0) — tail-probe 계열 신규 forward 추가 시 반드시 확인. Exp-158 재발 방지.

---

## 참조 문서

| 파일 | 용도 |
|------|------|
| [EXPERIMENTS.md](../EXPERIMENTS.md) | **항상 먼저** — E5 epoch·baseline·이월 핵심사실 |
| [EXPERIMENTS_LOG.md](../EXPERIMENTS_LOG.md) `Exp-163`/`Exp-164`/`Exp-158` | 필러 후처리 기각·비음성게이팅 기각·turbo 전환 배경 전체 서술 |
| [GOAL_TURBO_AUTONOMOUS.md](GOAL_TURBO_AUTONOMOUS.md) | 무인 세션 운영 패턴의 원형(이 문서가 계승) — §4 무인결정·§6 안전장치·§9 목록 형식 |
| [../CLAUDE.md](../CLAUDE.md) §3~4 | 설계 제약·측정 규칙·자율 루프 원칙 |
| [.claude/commands/eval.md](../.claude/commands/eval.md) | eval.py 옵션 레퍼런스 |
| [.claude/commands/log-experiment.md](../.claude/commands/log-experiment.md) | 실험 기록 형식 |
| `whisperlivekit/simul_whisper/align_att_base.py` | `detect_current_language`(250)·`infer`(277)·`_check_no_speech` 호출지점(329)·`LANG_SWITCH_KEEP_SECS`(13) |
| `whisperlivekit/simul_whisper/simul_whisper.py` | `lang_id`(207)·`_check_no_speech`(338) |
| `worktrees/nonspeech-gating` (`exp/nonspeech-gating`) | P1 작업 대상 — Exp-164 계측 인프라 보유 |
