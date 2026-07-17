# /eval — 경로 C 성능 평가 (실제 파이프라인 기준)

기능 수정 후 경로 C(VBCable 루프백)로 실제 오디오 파이프라인 전체를 통과한 성능을 측정한다.
**WER(전사 정확도) + 화자분리 F1 + 문장분리 F1**를 출력한다. 개선·채택 우선순위 = **화자분리 F1 > WER > 문장분리 F1** (요구사항 정본 [docs/TRANSCRIPTION_REQUIREMENTS.md](../../docs/TRANSCRIPTION_REQUIREMENTS.md)). *2지표(화자분리/문장분리) 분리 구현 완료 — 신형식 정답(`<name>_speak,sentence_sperate.txt`) 존재 시 `seg_f1`=화자분리 F1, `sentence_f1`=문장분리 F1(모든 블록이 단일 문장이면 `None`)로 함께 산출된다. 아직 이 regime v2 기준 경로 C 베이스라인 실측 전이다.*
서버 기동/종료와 VBCable 장치 설정/복원은 스크립트가 자동으로 처리한다.
**세션 언어모드 매트릭스**(CLAUDE.md §3.2·§3.8 — `--lan`은 서버 기동당 전역 1값이라 언어모드가 다른 파일은 **run을 분리**):
- **auto 테스트(채택/기각) = `bong1.wav` + `ytn2.mp3` + `sbs1.mp3`** (`--lan auto`; 화자분할 ON; ytn2·bong1 공동 최우선)
- **ko 테스트(채택/기각) = `kor1.wav` + `kor2.wav` + `kor3.wav`** (`--lan ko`; 한국어 단독 낭독, Exp-178에서 auto 붕괴가 발견돼 편입)
- **held-out 정량**: auto = `ytn1.mp3`(`--lan auto`), en = `eng1.mp3`(`--lan en`) — 채택 후보에 한해 **단회** diar-ON, 각각 별도 run
- **held-out 정성 sanity = `kinno.mp3`**(`--lan auto`; 2화자; 정답 텍스트 부정확 → **WER/F1 게이팅 제외**, 대규모 누락/환각·거친 화자/문장 분리만 정성 확인)

측정은 **2계층**: ① 평소 스크리닝 = `--repeat 1`(방향 신호), ② master 채택 직전 확정 = `--repeat 3`(median+분산 판단). `eval.py`의 기본 `--files`는 코드 상 여전히 sbs1/ytn1/eng1이므로 **루틴은 `--files`와 `--lan` 명시 필수**.

**성능 판정 기준은 경로 C만** 사용한다. 경로 A(PCM 파일 주입)는 브라우저 오디오 파이프라인을 우회하므로 폐기.

**채택 판단 우선순위(② 채택 확정 단계)**: **1순위 = 최악 케이스(max) 미회귀**, 2순위 = median 개선.
최악 케이스가 발생하면 median 개선보다 원인 파악과 해결이 먼저다.
스크리닝(1회) 수치는 방향 신호로만 해석 — 미세 채택/기각 결론의 근거로 쓰지 않는다.
채택 확정(머지 직전)에만 `--repeat 3`으로 돌려 median + 분산(min/max/stdev)으로 판단. **채택 확정 시 fail-fast 금지.**
단 VBCable 미설정·무음 캡처 등 *하니스 버그*는 즉시 중단·수정.
**목표 필수 기능 예외**: §3.1·§3.2 불변 제약 달성에 필요한 기반 기능이 게이트 탈락 시 자율 기각 금지 — 결과·대안 보고 후 사용자 질의.

## 기본 사용법

```powershell
# ① 스크리닝(기본, auto 모드) — bong1 + ytn2 + sbs1, 화자분할 ON, 방향 탐색·catastrophic 회귀 감지용
$env:PYTHONIOENCODING = "utf-8"
$ts = Get-Date -Format "yyyyMMdd_HHmm"
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir whisperlivekit/model/whisper-large-v3-turbo `
  --files test_data/bong1.wav test_data/ytn2.mp3 test_data/sbs1.mp3 `
  --lan auto `
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo `
  --compression-ratio-threshold 3.0 `
  --output ".omc/benchmarks/eval_$ts.json"
# ↑ --repeat 생략 = 기본값 1회. 수치는 '방향 신호'로만 해석한다.

# ① 스크리닝(ko 모드) — kor1 + kor2 + kor3, 한국어 세션 개선 시 이 run으로 측정
$ts = Get-Date -Format "yyyyMMdd_HHmm"
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir whisperlivekit/model/whisper-large-v3-turbo `
  --files test_data/kor1.wav test_data/kor2.wav test_data/kor3.wav `
  --lan ko `
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo `
  --compression-ratio-threshold 3.0 `
  --output ".omc/benchmarks/eval_$ts.json"

# ② 채택 확정용 (master 머지 직전에만 — N≥3회 반복, median+분산 판단). auto 테스트 예시, ko는 --lan ko + kor1~3로 동일하게 반복
$ts = Get-Date -Format "yyyyMMdd_HHmm"
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir whisperlivekit/model/whisper-large-v3-turbo `
  --files test_data/bong1.wav test_data/ytn2.mp3 test_data/sbs1.mp3 `
  --lan auto `
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo `
  --compression-ratio-threshold 3.0 --repeat 3 `
  --output ".omc/benchmarks/eval_$ts.json"

# held-out 일반화 검증 — 채택 후보에 한해 ytn1(auto) + eng1(en), 언어모드가 다르므로 run 분리(단회, diar-ON)
$ts = Get-Date -Format "yyyyMMdd_HHmm"
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir whisperlivekit/model/whisper-large-v3-turbo `
  --files test_data/ytn1.mp3 `
  --lan auto `
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo `
  --compression-ratio-threshold 3.0 `
  --output ".omc/benchmarks/eval_$ts.json"

$ts = Get-Date -Format "yyyyMMdd_HHmm"
.venv\Scripts\python.exe scripts/eval.py `
  --model-dir whisperlivekit/model/whisper-large-v3-turbo `
  --files test_data/eng1.mp3 `
  --lan en `
  --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo `
  --compression-ratio-threshold 3.0 `
  --output ".omc/benchmarks/eval_$ts.json"
# ↑ held-out은 단회 검증(채택 확정이라도 --repeat 3 불필요)
```

## 실행 절차 (Claude가 따를 순서)

0. **측정 대상 세션 언어모드를 먼저 확인**(auto/ko/en) — 개선 대상 파일군에 맞는 `--files`+`--lan` 조합을 위 명령 블록에서 선택한다. 모드가 섞인 파일을 한 run에 넣지 않는다.
1. `$env:PYTHONIOENCODING = "utf-8"` 설정 후 eval.py 실행 (`--output`으로 JSON 자동 저장됨)
2. VBCable 자동 설정 여부 로그 확인 (성공/실패/건너뜀)
3. 저장된 JSON에서 파일별 `wer_median/min/max/stdev`, `seg_f1_median`, `avg_wer_c_median`/`avg_seg_f1_c_median` 추출.
   **median + 최악 케이스(max)를 함께** 본다 (경로 C = 성능 기준 지표).
4. `.omc/transcripts/`에 저장된 전사 파일을 읽어 **정성 평가**를 수행한다 (아래 §정성 평가 절차 참조).
   정량(WER/F1)과 정성(목표 달성 여부·신규 이슈)을 **함께** 고려해 채택/기각/사용자 확인을 판정한다.
5. `.omc/benchmarks/`의 가장 최근 JSON과 비교:
   ```powershell
   Get-ChildItem .omc/benchmarks/eval_*.json | Sort-Object LastWriteTime -Descending | Select-Object -First 1
   ```
6. 개선 여부를 "이전 WER → 현재 WER (변화량%p)" 및 정성 판정 결과와 함께 표시
7. 결과를 `/log-experiment`로 기록할지 사용자에게 확인

## 정성 평가 절차

**(선택) 시각화**: `.venv\Scripts\python.exe scripts/render_eval_report.py .omc/benchmarks/eval_*.json --output .omc/transcripts/eval_report.html`로 전사·정답을 단어 단위 색깔 하이라이트(삭제=빨강 취소선·삽입=파랑·치환=노랑·**Case B=굵은 빨강 테두리**, 문장별 확정 트리거 칩 포함)한 자체완결 HTML로 렌더링하면, 아래 절차(특히 2번 Case B·6번 트리거 확인)를 원문 `.txt`보다 훨씬 빠르게 육안 판정할 수 있다. 여러 JSON(테스트셋+held-out 등)을 한 번에 넘기면 한 리포트에 합쳐진다.

eval.py 완료 후 `.omc/transcripts/`에 저장된 `{파일명}_{경로}_R{회차}.txt`를 읽어
**정량 지표가 포착 못하는 목표 달성 여부**를 판정한다.

각 전사 파일의 `[전사]` vs `[정답]` 텍스트를 비교해 다음 항목을 분석한다(우선순위 = **화자분리 > WER > 문장분리**, 정본 [docs/TRANSCRIPTION_REQUIREMENTS.md](../../docs/TRANSCRIPTION_REQUIREMENTS.md) §4):

1. **[1순위] 화자전환 경계 분리**: 정답 `[spkN]`이 바뀌는 지점마다 전사가 **줄분리·확정**됐는가? 안 갈라진 화자전환 지점 = **최우선 개선 대상**. (수단 불문 — diarization·언어감지·침묵·구두점 무엇으로든 분리되면 OK.)
2. **[hard-fail] Case B(단어 중간 분절)**: 한 단어/문장이 **단어 중간에서 쪼개져** 확정됐는가(예 "올렸"⏎"습니다")? 발견 시 F1·WER 무관 **critical flag** — 원인 수정 대상.
3. **목표 달성**: 이번 실험의 가설(예: "언어 전환 시 truncation 감소")이 실제로 개선됐는가?
   - 가설이 겨냥한 구간(예: 코드스위칭 전환부, 다화자 발화 경계)의 오류 패턴 변화 확인
4. **신규 문제**: 이전에 없던 오류 유형(환각 폭주·**한/영 외 언어 혼용**·단어 누락 폭증)이 생겼는가?
5. **오류 분포 변화**: WER 개선/악화가 어느 구간에서 발생했는가? (특정 구간 집중인지 전반적인지)
6. **[3순위·nice-to-have] 문장 분리 로직**: 전사 txt의 `[문장별 확정 트리거]` 섹션(각 문장 뒤 `⟨silence/punctuation/language_switch/speaker_change⟩`)을 읽어, 문장이 **어떤 로직으로 확정·분리됐는지** 분석한다. 동일 화자 인접 문장이 붙어 나오는 **Case A는 허용**(감점 아님). 조기/지연 확정, 코드스위칭·화자전환 경계에서 트리거가 기대대로 작동했는지 F1 정성 판단에 활용한다.
7. **kinno(정성 sanity held-out) 전용**: 정답 텍스트가 부정확하므로 **WER/F1 수치를 신뢰하지 말 것**. 대규모 누락/환각 유무 + 전반적 화자·문장 분리가 대충 되는지만 본다.

### 정량 + 정성 통합 채택 판정

| 정량(WER) | 정성 | 판정 |
|-----------|------|------|
| 개선 | 목표 달성, 신규 이슈 없음 | **채택** |
| 개선 | 목표 달성, 신규 이슈 있음 | **사용자 확인** — 이슈 규모·성격 함께 보고 |
| 변화 없음 | 목표 달성 | **사용자 확인** — 달성 근거와 수치 변화 없음 이유 함께 보고 |
| 회귀 | 목표 달성, 다른 구간 악화 | **사용자 확인** — 목표 달성 구간과 회귀 구간을 모두 보고 |
| 회귀 | 목표 미달성 | **기각** |

> 위 표의 "정량"은 **화자분리 F1(1순위) → WER(2순위)** 순으로 읽는다: 화자전환 경계 분리가 무너지면 WER이 좋아도 채택 보류. **문장분리 F1(3순위)은 판정에 넣지 않는다**(Case A 허용). **Case B(단어 중간 분절) 발생 = 수치 무관 원인 수정 우선**.
> §3.1·§3.2 불변 제약 관련 기능이 정량 게이트 탈락 시 자율 기각 금지 — 결과·대안 보고 후 사용자 질의.

## 결과 해석 기준

지표 우선순위 = **화자분리 F1 > WER > 문장분리 F1**([docs/TRANSCRIPTION_REQUIREMENTS.md](../../docs/TRANSCRIPTION_REQUIREMENTS.md) §1). 세 지표를 함께 보되 이 순서로 가중한다.

### WER (전사 정확도)

환각 단어 생성(삽입)·단어 누락(삭제)을 포함한 전반적인 전사 정확도를 측정한다.

| WER 변화 | 판정 |
|----------|------|
| -5%p 이상 감소 | 유의미한 개선 |
| ±5%p 이내 | 유의미한 변화 없음 |
| +5%p 이상 증가 | 성능 저하 — 원인 조사 필요 |

**WER 원인 구분:** WER이 높거나 개선되지 않을 때, 전사 출력(JSON)을 확인해 원인을 구분한다.
- **치환 오류** ("육군"→"6군", "공군력"→"공군역"): 모델 자체 한계 — Phase 2에서 직접 추적하지 않음
- **환각 삽입·단어 누락**: 스트리밍 단계 문제 — Phase 2 개선 대상

### 화자분리 F1 (1순위 — 화자전환 경계 분리)

정답 신형식 `[spkN]` **전환 경계**가 STT 확정 줄분리로 실현됐는지 단어 정렬로 비교한다. **최우선 지표.**

| 화자분리 F1 | 판정 |
|----|------|
| 0.8 이상 | 화자전환마다 분리 잘 됨 |
| 0.5 ~ 0.8 | 일부 화자전환에서 미분리 — 개선 대상 |
| 0.5 미만 | 화자전환 경계 분리 실패 — **최우선 개선**(Recall↓ = 화자전환 미분리) |

### 문장분리 F1 (3순위 — nice-to-have)

동일 화자 블록 내 **온점 문장 경계**가 STT 줄분리로 실현됐는지 비교한다. **후순위** — 하락 단독은 기각 근거 아님(Case A 허용). 단 Precision↓이 **Case B(단어 중간 분절)** 때문이면 hard-fail.

| 문장분리 F1 | 판정 |
|----|------|
| 높음 | 문장 단위 확정 잘 됨 |
| 낮음(Recall↓) | 동일 화자 문장 미분리 — **허용**(Case A, 감점 아님) |
| 낮음(Precision↓) | 과분할 — **Case B(단어중간)면 hard-fail**, 아니면 후순위 |

> 구현 현황: 2지표 분리 metric **구현 완료**. `scripts/eval.py`가 신형식 정답(`<name>_speak,sentence_sperate.txt`)을
> 우선 읽어 `seg_f1`=화자분리 F1·`sentence_f1`=문장분리 F1을 각각 산출한다(신형식 파일이 없거나 `[spkN]` 헤더
> 파싱에 실패하면 구 `<name>.txt`·빈 줄 경계=구 regime으로 폴백 — 이 경우 `sentence_f1`은 `None`).
> 상세는 [docs/TRANSCRIPTION_REQUIREMENTS.md](../../docs/TRANSCRIPTION_REQUIREMENTS.md) §5 참조. 경로 C 화자 id
> 배선(§5 step 4, 귀속 정확도)은 아직 미구현이며, regime v2 기준 신 베이스라인 실측도 다음 세션 과제다.

## VBCable 자동 설정

스크립트가 자동으로 처리한다:
- CABLE이 이미 기본 장치면 그대로 진행
- 아니면 `audio_device.py`로 임시 설정 → 테스트 완료 후 원래 장치로 복원
- 자동 설정 실패 시 경고 출력 후 경로 C 건너뜀

수동 설정이 필요한 경우 (자동 설정 실패 시):
- Windows 소리 → 재생 장치: `CABLE Input` 기본값으로 변경
- Windows 소리 → 녹음 장치: `CABLE Output` 기본값으로 변경

## 주의사항

- 서버 포트 8901 사용 (수동 서버 기본값 8900과 충돌 방지)
- 서버 ready까지 최대 120초 대기 (모델 로딩 시간)
- 경로 C `--repeat 3` 실행 시 (오디오 길이 + `--wait`) × 3 소요 (테스트 3파일 bong1+ytn2+sbs1 기준: 약 18분 이상; 화자분할 서버 로딩 최초 1회 +약 30초 추가). 백그라운드 실행 권장
- 결과 JSON은 `.omc/benchmarks/` 디렉토리에 저장 권장 (`.gitignore` 적용됨)
- **서버 로그**(Exp-153~): eval.py가 매 회차 서버 stdout/stderr를 `.omc/server_logs/server_<stem>_<path>_R<rep>_<ts>.log`로 **항상** 저장한다. `[QualityGate]`(avg_logprob 억제)·`[BatchRepeatFilter]` 등 필터 계측은 기본 기록되고, `[LangSwitch]` 전환 트레이스는 `--trace-tokens` 시 기록. Q1(필터 기여도) 분석에 사용
