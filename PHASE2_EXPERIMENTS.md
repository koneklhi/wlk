# Phase 2 실험 로그

STT 성능 개선 과정에서 수행한 실험을 기록한다.
각 실험은 **가설 → 변경 → 결과 → 결론** 흐름으로 작성한다.

---

## 빠른 참조 (최신순)

| Exp | 날짜 | 제목 | 핵심 변경 | WER | Latency | 결론 |
|---|---|---|---|---|---|---|
| [Exp-002](#exp-002-자동화-평가-인프라-구축--wer-베이스라인-측정) | 2026-05-22 | 자동화 평가 인프라 구축 | eval.py 경로 A+C 자동 실행 + WER 베이스라인 측정 | A: 0.232 / C: 0.411 | — | **베이스라인 확정** |
| [Exp-001](#exp-001-vbcable-마이크-정성-평가--정책-최종-확정) | 2026-05-21 | VBCable 마이크 정성 평가 | 브라우저 마이크 입력으로 실사용 품질 비교 | — | — | **SimulStreaming 채택** |
| [Exp-000](#exp-000-정책-선택-기준-벤치마크-베이스라인) | 2026-05-20 | 정책 선택 기준 벤치마크 | SimulStreaming vs LocalAgreement 비교 | SS: 0.321 / LA: 0.434 | SS: 114ms / LA: 2511ms | → Exp-001에서 확정 |

---

## Exp-000: 정책 선택 기준 벤치마크 (베이스라인)

**날짜**: 2026-05-20
**정책**: simulstreaming vs localagreement (비교)
**가설**: Phase 2 알고리즘을 어느 정책 위에서 설계할지 결정하기 위해 동일 음성에서 두 정책을 실측 비교한다.

**설정**
- 샘플: `test_data/sbs1.mp3` (108.5s) — 한국어 + 영어 인용구 포함
- 모델: `whisper-large-v3-turbo` (로컬)
- 언어: `--lan auto` (코드 스위칭 평가)
- 속도: `speed=1.0` (실시간, latency 측정 의미 보장)
- 명령어: `uv run python scripts/bench_phase2_policies.py --sample test_data/sbs1.mp3`
- 결과 파일: [.omc/benchmarks/phase2_policies_20260520T003636Z.md](.omc/benchmarks/phase2_policies_20260520T003636Z.md)

**정량 결과**

| 항목 | SimulStreaming | LocalAgreement |
|---|---|---|
| WER | **0.321** | 0.434 |
| WER 세부 (subs/ins/del) | 28 / 24 / 2 | 7 / 0 / 66 |
| avg latency | **114ms** | 2511ms |
| p95 latency | 221ms | 9665ms |
| RTF | 1.541 | 1.572 |
| 영문 매치 (hits/ref) | **96%** (25/26) | 0% (0/26) |
| n_transcription_calls | 184 | 31 |
| n_tokens_produced | 242 | 27 |

**정성 관찰**
- SimulStreaming: 반복·버벅임 패턴 있음 ("브런스는", "바 바뀌면" 등). 영어 인용구는 거의 완벽하게 포착.
- LocalAgreement: 더 자연스러운 문장 생성. 영어 인용구 전체 누락 (del 66개). 지연이 매우 큼 (p95 약 10초).
- (마이크 정성 평가 후 상세 인상 추가 예정)

**결론**: → Exp-001(VBCable 정성 평가)에서 SimulStreaming으로 최종 확정
**이유**: 정량 지표 SimulStreaming 우세, 마이크 실사용 결과로 재확인
**다음 실험**: Phase 2 문장 확정 알고리즘 첫 구현 → Exp-002

---

## Exp-001: VBCable 마이크 정성 평가 — 정책 최종 확정

**날짜**: 2026-05-21
**정책**: simulstreaming vs localagreement (최종 비교)
**가설**: 정량 벤치마크(Exp-000)에서 SimulStreaming이 우세했으나, 마이크 실입력 환경에서도 동일한 우열이 유지되는지 확인하고 Phase 2 개발 정책을 확정한다.

**테스트 설정**
- 도구: VBCable — `sbs1.mp3`를 PC 재생 → 가상 오디오 케이블로 마이크 입력에 라우팅
- 입력 방식: 브라우저 마이크 캡처 (`--pcm-input` 없이 서버 기동)
- 서버 명령어:
  ```powershell
  # SimulStreaming
  uv run whisperlivekit-server --model_dir whisperlivekit/model/whisper-large-v3-turbo --backend whisper --backend-policy simulstreaming --lan auto --warmup-file test_data/sbs1_10s.mp3
  # LocalAgreement
  uv run whisperlivekit-server --model_dir whisperlivekit/model/whisper-large-v3-turbo --backend whisper --backend-policy localagreement --lan auto --warmup-file test_data/sbs1_10s.mp3
  ```
- 결과 파일: `Desktop/simul_sbs_output.txt`, `Desktop/local_sbs_output.txt`

**정성 결과**

| 항목 | SimulStreaming | LocalAgreement |
|---|---|---|
| 전체 커버리지 | 완주 (SBS 김수영까지) | **절반 이후 누락** |
| 한국어 반복 아티팩트 | `미 미 미`, `한 한 한도도도`, `-그 -그 -그` 다수 | 없음 (깔끔) |
| 영어 코드 스위칭 | **완벽 포착** ("From a satellite image..." 등) | **전체 누락** |
| 단어 왜곡 | `국건한`, `공군역과`, `간순한` 등 | `성빈 바다`(→텅 빈), `사령관관관계획` |
| 체감 지연 | 낮음 | 높음 |

**SimulStreaming 전사 샘플 (주요 구간)**
- 반복 예시: `"미 미 미어어어트"`, `"한 한 한도도도 동쪽이를를를"`, `"지 지 지를를 올 올렸습니다"`
- 영어 포착: `"From a satellite image, the Republic of Korea, looks like an island."` ✓
- 영어 포착: `"Like a fixed aircraft carrier floating in the water between Japan, and mainland China."` ✓

**LocalAgreement 전사 샘플**
- 깔끔한 한국어: `"지도를 돌려보면 태평양은 성빈 바다가 아니라 동맹국들이 연결된 거대한 방어선"` (문장 자연스러움)
- 영어 구간 이후 출력 없음 — 약 60초 이후 내용 전체 누락

**결론**: **SimulStreaming 채택** (Phase 2 개발 기반 정책 확정)
**이유**: LocalAgreement의 영어 누락과 커버리지 손실은 LCS 합의 알고리즘의 구조적 문제로 Phase 2에서 패치 불가. SimulStreaming의 반복 아티팩트는 문장 확정 로직(직전 commit과 중복 비교)으로 보완 가능.
**다음 가설**: SimulStreaming의 반복 토큰 (`바 바 바`, `지 지 지`) 및 노이즈 접두어 (`-그`) 를 문장 확정 단계에서 후처리로 제거 → Phase 2 알고리즘 설계 시작 → Exp-002

---

## 실험 템플릿 (신규 항목 작성 시 복사)

```markdown
## Exp-N: [제목]

**날짜**: YYYY-MM-DD
**정책**: simulstreaming / localagreement
**가설**: 왜 이 변경이 필요한가 — 어떤 문제를 해결하려 했는가

**변경 내용**
- `파일경로:라인번호` — 무엇을 어떻게 바꿨는가
- (추가 변경 항목)

**테스트**
- 샘플: test_data/XXX.mp3 (Xs)
- 명령어: `uv run python scripts/bench_phase2_policies.py --sample test_data/XXX.mp3`
- 결과 파일: .omc/benchmarks/phase2_XXX.md

**정량 결과**

| 항목 | 이전 (Exp-N-1) | 이번 (Exp-N) |
|---|---|---|
| WER | | |
| avg latency | | |
| p95 latency | | |
| 영문 매치 | | |

**정성 관찰**: 환각, 단어 유실, 코드 스위칭, 체감 지연 등 주관적 인상

**결론**: 채택 / 기각 / 수정 예정
**이유**: 한 줄 요약
**다음 가설**: 이 결과를 보고 다음에 뭘 시험할지
```
