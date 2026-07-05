# Goal Prompt — turbo 모델 정상 전사 복구 (model_dir 배선 버그 후속)

> ✅ **완료 (2026-07-05, Exp-158)**: 이 goal의 목표(turbo 실시간 stall 해소)는 달성됐다 — `detect_current_language()`의 `@torch.no_grad()` 누락이 근본원인(turbo 인코더 forward 0.2s→31.96s 폭주)으로 확정·수정됐고, 경로 C N=3 검증에서 3파일 전부 timeout 없이 완주했다. §2에서 범위 밖으로 미뤄뒀던 **머지·EXPERIMENTS.md 재수립도 같은 세션에서 처리됨** — turbo 기질(Epoch 5) baseline은 [EXPERIMENTS.md](../EXPERIMENTS.md) 참조, 전체 서술은 EXPERIMENTS_LOG.md의 Exp-158. 이 파일은 진단 근거·재현 절차 기록으로 보존한다.
>
> **이 파일을 새 Claude Code 세션의 첫 메시지로 붙여넣는다.**
> 이전 세션에서 단계5(2-pass 재전사) 프로브를 준비하던 중 **라이브 파이프라인이 처음부터 `whisper-large-v3-turbo`가 아니라 `base`(74M)를 로드하고 있었다**는 구조적 버그를 발견했다. 배선 자체는 고쳤지만, 고치고 나니 **turbo가 실시간 스트리밍에서 특정 지점에서 멎어버리는 새 버그**가 나왔다 — 사용자가 직접 확인한 증상과 동일: **첫 문장만 전사되고 그 이후로 전사가 끊긴다.**
> 이 goal은 **turbo가 정상적으로 끝까지 전사될 때까지**를 목표로 한다. 이게 해결돼야 이전 baseline(EXPERIMENTS.md 전체, base 기준) 재검토·단계5(2-pass) 재개 등 모든 후속 작업이 가능하다.

---

## 0. 배경 — 어쩌다 여기까지 왔나

1. 단계5(2-pass 재전사) 프로브 2b(동시경합) 하니스를 준비하던 중, 서버와 동일한 config로 `TranscriptionEngine`을 직접 구성해보니 **로드된 모델 파라미터가 807M(turbo)가 아니라 71.8M(base)** 였다.
2. **근본 원인**: [whisperlivekit/simul_whisper/backend.py](../whisperlivekit/simul_whisper/backend.py)의 `SimulStreamingASR.__init__`이 `self.model_path`만 확인하고 `self.model_dir`(서버가 `--model_dir whisperlivekit/model/whisper-large-v3-turbo`로 항상 전달하는 실제 경로)을 완전히 무시했다. `model_path`는 아무 데서도 세팅되지 않으므로 `model_size`(기본값 `"base"`)로 폴백되고, 개발 PC는 인터넷이 되므로 `whisper.load_model()`이 base를 조용히 자동 다운로드해(`~/.cache/whisper/base.pt`, 2026-06-05 캐시 생성) 크래시 없이 넘어갔다. **폐쇄망 배포에서는 인터넷이 없어 이 폴백이 아예 실패했을 것.**
   - 증거: LIVE(서버 config로 로드) params=71.8M, n_audio_state=512, n_audio_layer=6, n_text_layer=6 — turbo(807.0M, 1280, 32, 4)와 완전히 다르고 base와 소수점까지 일치.
3. **워크트리 `worktrees/fix-turbo-model-wiring`(브랜치 `exp/fix-turbo-model-wiring`)에서 배선을 수정**했다(아직 커밋·머지 안 됨, uncommitted). 정확한 diff:
   ```diff
   -        if self.model_path:
   -            resolved_model_path = resolve_model_path(self.model_path)
   +        model_path_or_dir = self.model_path or getattr(self, 'model_dir', None)
   +        if model_path_or_dir:
   +            resolved_model_path = resolve_model_path(model_path_or_dir)
   ```
   (위치: `SimulStreamingASR.__init__`, 약 399행 부근. `resolve_model_path` 인자만 바뀜, 나머지 로직 그대로.) 수정 후 **동일 검증으로 turbo 807.0M 로드 확정**됨. `ruff check` 통과.
4. 이 수정 후 경로 C로 측정했더니 **WER 88% 대의 참사**가 나왔는데, 원인을 파보니 **품질 문제가 아니라 실시간 파이프라인이 멎어서 강제 종료된 것**이었다(아래 §1).
5. 측정 중 별도 사고 있었음(이 goal과 무관하지만 재발 방지용 기록): 서브에이전트가 재개(resume)될 때마다 이전 측정을 정지시키지 않고 새 `eval.py`를 또 실행해 **동일 포트(8901)·동일 VBCable 장치에 2개의 측정이 동시에 재생되는 오염**이 발생했었다(sbs1 전사 결과에 ytn2 참조문이 섞여 나옴 — 스모킹건). 사용자 승인 하에 프로세스 정리 후 맨세션이 직접 단일 실행으로 재측정해 이 오염은 해소됨. **교훈: 새 측정 시작 전 반드시 `Get-CimInstance Win32_Process | Where CommandLine -match 'eval.py|basic_server'`로 잔여 프로세스 없음 + 포트 8901 비어있음을 확인.**

---

## 1. 재현되는 정확한 증상 (핵심 증거 — 이미 확보됨)

**증상**: turbo로 전사 시작 후 **최초 한두 문장만 나오고 그 이후 전사가 멈춘다.** (사용자가 실사용에서 직접 겪은 것과 서버 로그 진단이 정확히 일치.)

**서버 로그 재현 (3회 독립 재현, 위치는 모두 `worktrees/fix-turbo-model-wiring/.omc/`)**:

| 실행 | 설정 | 증상 |
|---|---|---|
| bong1.wav 전체(스크리닝 N=1) | beams=2, min-chunk-size=0.1(기본) | `last_end=9.1s` 근방에서 `lag` 0.2s → **143.4s로 순간 폭증** → `FFmpeg read timeout` |
| ytn2.mp3 전체 | beams=2, min-chunk-size=0.1(기본) | ~40s까지 정상(lag<1s) → 이후 39.8→43.4→70.4→91.1s로 점진 폭증 → timeout |
| sbs1.mp3 전체 | beams=2, min-chunk-size=0.1(기본) | lag는 시종 0~0.6s로 **정상**인데 `last_end=15.1s`(전체 108.5s 중 14%)에서 ffmpeg 자체가 끊김 |
| **bong1 25초 클립(최소 재현, 진단용)** | **beams=1, min-chunk-size=1.0** (가벼운 설정으로도 재현!) | **정확히 동일한 `last_end≈9.1s` 지점**에서 재현. 그 직전 로그: `+ Silence starting`→`+ Silence of = 1.96s`→QualityGate가 `"?"` 토큰 2회 연속 억제 → 그 직후 lag 0.00s→**14.61s→29.75s로 폭증** |

**핵심 단서**: beams(2→1)·min-chunk-size(0.1→1.0) 둘 다 바꿔도 **정확히 같은 시점(bong1 last_end≈9.1s)**에서 재현된다. 이는 "turbo가 그냥 느려서 실시간을 못 따라간다"는 단순 스루풋 문제가 **아니라, 침묵 처리 직후 실행되는 특정 코드 경로가 turbo에서 병적으로 느려지거나 멈추는 것**을 강하게 시사한다.

**진단용 산출물(재사용 가능, 커밋 안 된 로컬 파일)**:
- `worktrees/fix-turbo-model-wiring/.omc/diag_turbo_stall/diag_turbo_light.py` — 서버를 임의 플래그로 띄우고 짧은 클립 하나로 빠르게 재현 테스트하는 스크립트(`eval.py`의 `start_server`/`vbcable_test.run_browser_test`를 직접 재사용).
- `worktrees/fix-turbo-model-wiring/.omc/diag_turbo_stall/bong1_25s.wav` — bong1 첫 25초 클립(정지 지점을 넘기는 최소 재현 오디오, ffmpeg로 즉시 재생성 가능: `ffmpeg -y -i test_data/bong1.wav -t 25 -ar 16000 out.wav`).
- `worktrees/fix-turbo-model-wiring/.omc/diag_turbo_stall/diag_light_bong1_25s.log` — 위 재현의 서버 로그 원본.
- `worktrees/fix-turbo-model-wiring/.omc/server_logs/server_{bong1,ytn2,sbs1}_C_R1_*.log` — 전체 파일 스크리닝 원본 로그 3종(각 파일명에 타임스탬프 있음, `ls -t`로 최신 것 확인).
- `worktrees/fix-turbo-model-wiring/.omc/benchmarks/eval_turbofix_screen_clean.json` — 오염 없는 단독 스크리닝 결과(WER 88.4% 평균 — 위 stall로 인한 잘린 전사 때문, **품질 지표로 쓰지 말 것**, stall 재현 확인용으로만 참고).

---

## 2. 이 goal의 목표 (완료 기준)

**최종 완료 기준**: turbo 모델로 bong1.wav **전체(약 100초+)** 를 경로 C로 전사했을 때, 서버가 멎지 않고 `FFmpeg read timeout` 없이 끝까지 처리되며, 전사 문장 수가 정답 문장 수(15문장)에 근접한 수준으로 나온다. (WER 수치 자체를 개선하는 게 목표가 아니다 — **끝까지 멈추지 않고 도는 것**이 1차 목표.) 이후 ytn2·sbs1도 동일하게 확인.

이 goal이 끝나면(=turbo가 정상 작동하면):
- `worktrees/fix-turbo-model-wiring` 브랜치를 master에 머지할지, 아니면 이 stall 수정까지 포함해서 머지할지 사용자와 상의.
- **EXPERIMENTS.md 전체가 base 기준 baseline이었다는 사실**을 반영해 STATE 문서를 재수립해야 한다(별도 후속 논의 — 이 goal 범위 밖, 완료 후 보고).
- 그 다음에야 원래 하던 단계5(2-pass) 프로브 2b/2c를 turbo 기준으로 재개할 수 있다(`docs/GOAL_CODESWITCH_FOLLOWUP.md` 단계 E 참조, 2a는 이미 통과: RTF 0.128<0.5).

**이 goal 범위가 아닌 것**: 단계5 2-pass 본구현, EXPERIMENTS.md epoch 재수립, 코드스위칭 성능 개선 자체. 지금은 **turbo가 라이브에서 정상 작동하게만** 만든다.

---

## 3. 조사 우선순위 — 의심 지점 (증거 기반, 하지만 확정 아님)

정지 시점 직전 로그 패턴(침묵 이벤트 → QualityGate가 `"?"` 반복 억제 → lag 폭증)을 근거로 아래 순서로 의심하되, **추측으로 고치지 말고 반드시 타이밍 계측 후 확정**할 것(§4 방법론 참조):

1. **`SimulStreamingOnlineProcessor.end_silence()`** ([backend.py:86](../whisperlivekit/simul_whisper/backend.py#L86)) — 정지 직전 로그에 `+ Silence starting`/`+ Silence of = 1.96s`가 있다. `long_silence` 분기의 `self.model.refresh_segment(complete=True)` 또는 언어 재감지 관련 상태 리셋이 turbo 차원에서 이상 동작할 가능성.
2. **언어 재감지 경로** — `detect_current_language()` / `_apply_detected_language()` / `_check_short_silence_language()`. turbo는 `n_text_layer=4`(base는 6), `n_vocab=51866`(base는 51865, 토큰 레이아웃이 다를 수 있음) — 언어 감지 로직이 특정 레이어 인덱스나 vocab 크기를 하드코딩 가정하고 있다면 여기서 깨질 수 있다.
3. **QualityGate 반복 억제 로직** — 정지 직전 `"?"` 토큰이 연속 억제됐다. `align_att_base.py`의 QualityGate가 "3 consecutive suppressions → refresh_segment" 같은 반복 트리거를 가지고 있는데(EXPERIMENTS.md 이월핵심 참조), 이 refresh가 turbo에서 훨씬 무거운 재인코딩을 유발하거나, 최악의 경우 refresh→재억제→refresh의 **무한/준무한 루프**에 빠질 가능성.
4. **AlignAtt 디코더 자체의 turbo 차원 가정** — `frame_threshold=25`(0.02s/frame 가정, large-v3 계열은 맞음), `rewind_threshold`, `last_attend_frame` 계산 등이 인코더 레이어 수(6→32)·attention head 구조 차이에 따라 O(n²)로 튀거나 잘못된 인덱싱으로 비정상적으로 느려질 가능성.
5. **GIL/스레드 경합** (가능성 낮게 재분류 — sbs1처럼 lag가 정상인데도 ffmpeg가 끊기는 사례가 있어 완전 배제는 금물이지만, beams=1로도 재현되는 걸 보면 단순 컴퓨팅 총량 문제는 아닐 가능성이 큼). `process_iter`는 이미 `asyncio.to_thread`로 오프로드돼 있다([audio_processor.py:387](../whisperlivekit/audio_processor.py#L387)).

**주의**: 위는 로그 패턴에서 추론한 가설일 뿐 확정된 원인이 아니다. §4 방법론으로 실제 병목을 찍은 뒤 고칠 것.

---

## 4. 진행 방법론

1. **세션 시작**: `git worktree list`로 `fix-turbo-model-wiring` 워크트리 존재 확인 → 거기서 이어서 작업(새 워크트리 만들지 말 것). `.venv`는 이미 Junction 공유돼 있음.
2. **재현 확인 (최소 비용)**: `.omc/diag_turbo_stall/diag_turbo_light.py`를 그대로 실행해 `bong1_25s.wav`로 stall이 여전히 재현되는지 먼저 30초 안에 확인. (실행 전 반드시 `Get-CimInstance Win32_Process | Where CommandLine -match 'eval.py|basic_server'`로 잔여 프로세스 없음 확인 — 동시측정 오염 재발 방지.)
3. **타이밍 계측 추가** — §3의 의심 함수들(`end_silence`, `detect_current_language`, `_apply_detected_language`, QualityGate의 refresh 트리거, `model.infer`)에 `time.perf_counter()` 전후 로깅을 임시로 추가해, **정확히 어느 호출이 9.1s 지점에서 오래 걸리는지/멈추는지** 확정한다. 의심 가는 곳에 한꺼번에 걸지 말고, 로그 순서대로 하나씩 좁혀가며(systematic-debugging 스킬 활용 권장) 원인을 확정한다.
4. **원인 확정 후 최소 수정** — 원인이 예를 들어 "refresh_segment가 turbo에서 너무 무거워 폭주"라면 refresh 트리거 조건을 조정하거나, "특정 인덱스가 base 차원을 가정한 하드코딩"이라면 그 부분만 고친다. 파라미터 전체를 turbo에 맞게 재튜닝하는 큰 작업으로 확대하지 말고, **정지를 유발하는 근본 버그만** 최소 수정한다.
5. **검증**: 먼저 `bong1_25s.wav`(또는 더 긴 클립)로 정지 지점을 넘겨 끝까지 도는지 빠르게 확인 → 통과하면 bong1.wav 전체 → ytn2.mp3 → sbs1.mp3 순서로 경로 C 스크리닝(N=1) 실행해 전부 `FFmpeg read timeout` 없이 완주하는지 확인.
6. **완료 기준 충족 후**: 사용자에게 보고(원인·수정 내용·검증 결과) → 머지 여부 상의. **EXPERIMENTS.md 갱신·baseline 재수립·단계5 재개는 이 goal 범위 밖 — 별도 지시 대기.**

---

## 5. 측정 규율 (엄수 — 이번 세션에서 실제로 문제가 됐던 것들)

- **경로 C만, VBCable**. 매 측정 전 잔여 `eval.py`/`basic_server` 프로세스 없음 + 포트 8901 비어있음을 반드시 확인 후 시작(§0.5 사고 재발 방지).
- **워크트리 규약**: 메인 세션은 `worktrees/fix-turbo-model-wiring` cwd로 이동하지 않는다(EnterWorktree 금지). 코드 수정·측정은 서브에이전트에 위임하거나, 메인 세션이 `(cd "절대경로" && 명령)` 형태의 서브셸로 실행해 자신의 persistent cwd는 유지한다.
- **서브에이전트 위임 시 주의**: 이번 세션에서 서브에이전트가 "완료" 보고 후에도 실제로는 작업을 안 했거나(1회 tool 호출·56초 만에 "완료"), 재개 지시 후 **이전 측정을 정지시키지 않고 새 측정을 또 실행**해 동시재생 오염을 일으킨 사고가 있었다. 서브에이전트를 쓴다면: (1) 시작 전 반드시 기존 프로세스 없음을 스스로 확인하게 지시, (2) "background에서 기다리겠다"는 식으로 턴을 끝내지 말고 실제로 명령이 끝날 때까지 블로킹(run_in_background + 완료 대기)하도록 명시, (3) 결과 보고에 실제 diff·실제 수치·실제 로그 인용을 요구.
- **uv 가드레일**: 공유 `.venv`에 `uv run`/`uv sync`/`uv pip` 금지(재동기화 시 tokenizers 강등 → sortformer 붕괴). `.venv\Scripts\python.exe`/`.venv\Scripts\ruff.exe` 직접 호출.
- **인코딩**: Windows 콘솔(cp949)에서 한글/특수문자(em dash `—` 등) `print()`가 `UnicodeEncodeError`로 죽을 수 있다 — 진단 스크립트의 출력 메시지는 ASCII로 쓰거나 `PYTHONIOENCODING=utf-8` 환경변수를 명시할 것(이번 세션에 실제로 겪은 삽질).

---

## 6. 참조

| 파일 | 용도 |
|------|------|
| `whisperlivekit/simul_whisper/backend.py` | `SimulStreamingASR.__init__`(model_dir 배선, 이미 수정됨) · `SimulStreamingOnlineProcessor.end_silence`·`_check_short_silence_language`·`new_speaker`·`process_iter`(§3 의심 지점 다수) |
| `whisperlivekit/simul_whisper/align_att_base.py` | `_apply_detected_language`·`detect_current_language`·QualityGate·`infer()` |
| `whisperlivekit/audio_processor.py` | `transcription_processor`(387행 `to_thread(process_iter)`)·ffmpeg 리더 |
| `worktrees/fix-turbo-model-wiring/.omc/diag_turbo_stall/` | 이번 세션 진단 산출물(재현 스크립트·클립·로그) |
| `worktrees/fix-turbo-model-wiring/.omc/server_logs/` | 전체 파일 스크리닝 원본 로그(오염 전/후 포함, 파일명 타임스탬프로 구분) |
| `EXPERIMENTS.md` | 현재 전체가 base 기준 baseline — 이 goal 완료 후 별도로 재수립 필요(이 세션 범위 아님) |
| `docs/GOAL_CODESWITCH_FOLLOWUP.md` §단계E, `docs/GOAL_CODESWITCH_STRUCTURAL.md` §단계5 | turbo 정상화 후 재개할 2-pass 프로브 원 스펙(2a RTF<0.5 이미 통과) |
| `CLAUDE.md` §3~4 | 측정 규율·워크트리/uv 가드레일 원 규정 |
