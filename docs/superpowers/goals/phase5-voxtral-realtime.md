# Phase 5 Goal — Voxtral Realtime 백엔드 전환 자율 루프

작성: 2026-07-08. 핵심 전제: **동작 유무 검증 → 통과 시 사람 개입 없이 WER/F1 배포 수준까지 자율 개선 루프.**
기존 whisper-large-v3-turbo(AlignAtt) 기반 로직은 voxtral 경로에 한해 갈아엎기 허용. Sortformer 화자분할은
pyproject conflict로 **공존 불가 — diar-OFF 강제**(사용자 사전 승인).

---

## 1. 배경 — 왜 Voxtral 인가

ytn2(짧은 텀 한↔영 코드스위칭)·bong1(다화자 웃음 환각)이 AlignAtt 구조 한계에 막혀 있다.
Phase 4(late-commit goal)가 손으로 복원하려던 레버 3개 중 2개를 Voxtral-Mini-4B-Realtime-2602는 학습된 형태로 내장한다:

| Phase 4 레버 | AlignAtt (현재) | Voxtral Realtime |
|---|---|---|
| 늦은 확정 / 수정 가능 꼬리 | frame_threshold + provisional 버퍼 수제작 필요 | **네이티브** — learned emission delay τ 80~2400ms 런타임 설정(Ada RMS-Norm, 권장 480ms) |
| 매 스텝 언어 재감지 | 2초 후 언어 고정, PLC로만 재감지 | **네이티브** — 언어 토큰/조기 고정 없음, per-token 암묵 처리 |
| 환각 폭주 차단 | 없음 | **없음 (동일 약점)** → V2/V3에서 재구축 |

### 모델 확정 사실 (서베이 완료, 재조사 불필요)
- causal 인코더(from-scratch, Whisper 계보 아님) + 3.4B LM 디코더, 15초 sliding window, forward-only(커밋 토큰 재수정 없음)
- 한국어 공식 지원(13개 언어). FLEURS ko WER: delay 480ms=15.74% / 2400ms=14.30% (단일언어 clean 기준)
- **한↔영 발화 내 코드스위칭 공개 근거 전무 — 실측만이 답**
- transformers ≥5.2.0 필요, Apache 2.0, HF 1회 다운로드 후 완전 오프라인 가능
- VRAM: 4.4B bf16 ≈ 8.8GB — RTX 3080 10GB 개발기에서 아슬아슬 (Gate 0에서 실측)

### 코드 배선 확정 사실 (조사 완료)
- `--backend voxtral` 분기·온라인 프로세서 인터페이스·WebSocket lines[]/finalized 스키마 = **완비, 백엔드 무관**
- 공유 경로 필터(환각사전·CJK드롭·단어교정·온점·번역 트리거)는 voxtral에도 적용됨
- AlignAtt 내부 안전장치(lang_restrict_koen·CASE3 앵커게이트·logprob/CRT/no_speech·first_timestamp)는
  voxtral 경로에서 **전부 자동 우회** — §3.2 한/영 방어선이 filter_segments 하나로 축소
- 현 래퍼(voxtral_hf_streaming.py)는 즉시확정(`n_to_commit = len(words)-1`) + **delay τ 미노출**
- eval.py L209 `--backend whisper` 하드코딩 → 패스스루 신설 필요(Gate 1 선행 작업)
- 공유 .venv transformers=4.53.3 → **워크트리 독립 .venv 필수** (voxtral-hf ↔ diarization-sortformer conflict)

## 2. 핵심 통찰

Voxtral은 코드스위칭 축(늦은 확정·언어 무고정)을 공짜로 이기지만, **AlignAtt 시절 안전장치가 전부 우회되므로
"방어선 재구축"이 이 전환의 본질적 리스크**다. 루프의 절반은 delay τ 튜닝(V1), 나머지 절반은 방어선 재건(V2/V3)이다.
또한 양자화 구성(int8 이하)에서 얻은 수치는 **방향 신호**이며, 최종 확정은 배포기(RTX 5090 bf16) 재측정을 전제한다.

## 3. 베이스라인 + 성공 기준

### 참고: AlignAtt diar-ON (E5, Exp-161, N=3 — 직접 비교 불가, 참고용)
| 파일 | WER med | WER max | F1 med |
|---|---|---|---|
| bong1 | 30.5% | 30.5% | 50.0% |
| ytn2 | 28.1% | 34.5% | 38.5% |
| sbs1 | 14.9% | 16.1% | 16.7% |
held-out 단회: ytn1 21.5% / eng1 4.8%

### 공정 비교 기준: AlignAtt diar-OFF (2026-07-08 측정, N=3, master@53553d6, `.omc/benchmarks/eval_alignatt_diaroff_gate2.json`)
| 파일 | WER med | WER max | F1 med |
|---|---|---|---|
| bong1 | 29.6% | 51.7% | 35.0% |
| ytn2 | 47.8% | 53.7% | 51.9% |
| sbs1 | 12.5% | 17.3% | 22.2% |

### 성공 기준 (사용자 확정)
- **M1 (마일스톤, 비차단 알림)**: 테스트 3종 모두 median WER ≤ AlignAtt diar-OFF AND max ≤ diar-OFF max +5%p
- **M2 (최종 목표 = 루프 종료)**: 테스트 3종 모두 **median WER < 15% AND F1 ≥ 80%** (repeat 3)
  + held-out(ytn1/eng1) AlignAtt held-out 대비 미회귀(≤ +5%p)
  + 양자화 구성이면 "배포기 bf16 재측정 필요" 단서를 달아 보고

## 4. 핵심 제약

1. **폐쇄망(§3.1)**: 모델은 HF에서 **1회 다운로드가 유일한 승인된 네트워크 예외**. 이후 서버 실행은
   `HF_HUB_OFFLINE=1` + 로컬 절대경로로만. 신규 코드 런타임 네트워크 호출 금지.
2. **격리(오염 방지)**: 모든 코드 작업은 `worktrees/voxtral-realtime`(브랜치 `exp/voxtral-realtime`)에서만.
   main 편집은 docs/**·.claude/**·루트 메타파일만. 기존 워크트리·공유 .venv·병렬 세션 작업물에 불간섭.
3. **독립 .venv 규칙 (uv 불사용)**: 이 워크트리는 Junction 공유 금지 — **`python -m venv`로 독립 venv 생성 후
   pip로 설치**한다(공유 venv 보호 hook은 uv 계열만 차단하며, 본 방식은 공유 venv를 일절 건드리지 않아 hook 의도와 무충돌).
   설치 순서: ① torch/torchaudio는 cu128 인덱스(`--index-url https://download.pytorch.org/whl/cu128`)
   ② `pip install -e .[voxtral-hf,vbcable]` (sortformer extra 절대 미포함). uv.lock 핀과 버전이 다를 수 있으나
   격리된 실험 venv이므로 허용 — 단 transformers ≥5.2.0·torch cu128 빌드는 설치 후 검증 필수.
   공유 `.venv`(메인·Junction 워크트리)에는 어떤 설치 명령도 실행 금지.
4. **diar-OFF 고정**: 전 측정에서 `--diarization` 생략(서버에 `--no-diarization` 자동 전달).
5. **VBCable 직렬화**: VBCable·포트 8901은 머신 전역 자원. 매 측정 전 포트 선점·타 eval 프로세스 확인.
   병렬 세션 측정과 동시 실행 금지. 무음 캡처 등 하니스 버그는 즉시 중단·수리(측정 아님).
6. **갈아엎기 경계** — 허용: `voxtral_hf_streaming.py` 전면 재작성, voxtral 전용 신규 모듈, AlignAtt 전용 코드 무시.
   **불가침**: WebSocket lines[]/finalized 스키마, eval 채점 로직·정답 전사, whisper 경로 기본 동작(--backend 기본값 포함),
   CLAUDE.md 측정 규약, main 브랜치 코드, 데이터 특화 하드코딩 금지(§3.8).
7. **기록 격리**: 루프 중 실험 기록은 워크트리 브랜치의 `EXPERIMENTS_VOXTRAL.md`에 **Exp-V01…** 네임스페이스로.
   main의 EXPERIMENTS.md/LOG는 건드리지 않는다(병렬 세션 Exp-N 경합 회피). 종료 보고 시 정식 편입 제안.

## 5. Stage 구성

### Stage 0 = Gate 0 — ✅ 통과 (2026-07-08, 프로토콜 변경 1건 사용자 승인)

**실측 결과**: 오프라인 로드 OK / `device_map="auto"`는 GPU가 비어도 CPU 오프로딩 선택(RTF 3.3~19 파탄) →
`device_map={"": 0}` 전량 GPU 강제로 해결(가중치 8.86GB, 피크 9.28GB ≤ 9.3, OOM 0). 병목 프로파일:
CPU 전처리 1.9ms/토큰(무죄), GPU generate 126ms/토큰 — **bf16 최선 RTF 1.5**, int8(bnb)은 RTF 4.95로 기각.
3080에서 실시간(RTF<1) 구조적 불가, 5090(대역폭 2.4×)은 RTF ≈ 0.6~0.7 추정.

**프로토콜 변경 (사용자 승인, 2026-07-08)**: **지연 허용 측정** — 개발기에서는 오디오 실시간 유입 + 전사 지연
완성을 허용하고 **품질(WER)만 유효 지표**로 본다. F1은 침묵 flush 타이밍 왜곡 가능성으로 **참고치**.
실시간성(S5류 기준)·최종 확정 수치는 5090 배포기 재검증 전제(§3 M2 단서와 동일 원칙).
이행 사항: 래퍼 finish/start_silence drain을 백로그 연동으로 보강, eval 대기창을 오디오길이 연동으로 연장,
Gate 1 S5는 "재생 종료 후 ≤ 0.7×오디오길이 내 finish + 유실 없음"으로 대체.

#### (원래 계획 — 기록 보존)
- **변경**: 워크트리+독립 venv, 모델 다운로드(`whisperlivekit/model/Voxtral-Mini-4B-Realtime-2602`, 메인 저장소, gitignore 등재).
- **통과 기준**: ① transformers 5.2.x + `VoxtralRealtimeForConditionalGeneration` 임포트 성공
  ② `HF_HUB_OFFLINE=1` 로컬 로드 성공 ③ 15초 더미 오디오 추론 1회 피크 VRAM ≤ 9.3GB AND OOM 0 (nvidia-smi 계측)
- **OOM 폴백 트리 (순서 시도, 성공 구성으로 고정)**:
  1. Playwright 브라우저 `--disable-gpu` + `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` + GPU 앱 정리
  2. `torch.inference_mode`/sdpa attention/KV cache 상한 확인
  3. **int8 양자화(bitsandbytes)** — 자율 진행(보고서에 구성 명시). 품질 페널티는 Gate 2 수치가 판단
  4. **4bit — 진입 전 사용자 보고 필수**(사용자 확정: "4bit로 계속 vs 5090 반입 후 재개" 질의)
  5. CPU 오프로딩 — Gate 1 S5(준실시간) 미달 시 즉시 기각
  6. 전부 소진 → 하드 블로커 보고 중단 (각 단계 피크 VRAM 수치 첨부)

### Stage 1 = Gate 1 (동작 유무 — 경로 C 스모크)
- **선행 변경**: eval.py `--backend` 패스스루 신설(기본 whisper — 기존 경로 바이트 무변경), pytest 통과.
- **측정**: sbs1 단독, `--backend voxtral`, diar 생략, `--repeat 1`.
- **통과 기준 (5개 전부)**: S1 서버 60초 내 기동+WS 접속 / S2 lines[] 갱신 ≥5회 AND finalized ≥1회 /
  S3 전사에 한글 포함 AND 총 문자수 ≥ 정답의 30% / S4 트레이스백·예외 0 / S5 재생 종료 후 30초 내 finish 완료.
- **실패 분기**: 로그로 원인 분류(임포트/스키마/타임스탬프/ASRToken) → 래퍼 수정 → 재시도 **최대 3라운드** → 소진 시 하드 블로커 보고.

### Stage 2 = Gate 2 (계측 기준선)
- **AlignAtt diar-OFF 베이스라인**: 메인 저장소(master·공유 venv·기본 whisper)에서 3종 `--repeat 3` → §3 표 기입.
- **Voxtral Exp-V00**: 워크트리에서 3종 `--repeat 1` 스크리닝. **완주+지표 산출 = PASS** (수치 무관 — 루프 출발점).
- **참사 예외**: 3종 모두 WER ≥80% 또는 F1=0 → 하니스 디버그 1회 → 재발 시 V2/V3 선적용 2회 →
  그래도 3종 median이 AlignAtt diar-OFF 대비 +30%p 열세면 조기 무익 판정으로 이동.

### Stage 3 = Gate 3 (자율 개선 루프)
이터레이션: 가설 → 구현(워크트리) → 스크리닝(repeat 1, bong1+ytn2+sbs1) → 유망 시 확정(repeat 3, fail-fast 금지)
→ 자율 채택/기각 → Exp-V 기록 + §3 표 갱신 → 다음 가설. 채택본이 다음 베이스라인.

**개선 후보 메뉴 (우선순위 — 소진 시 신규 가설 발굴 허용)**:
| # | 후보 | 가설 | 채택 신호 |
|---|---|---|---|
| V1 | **delay τ 노출+스윕** (래퍼/서버 플래그, 480/960/2400ms) | 지연↑=정확도↑ 곡선에서 최적점 존재 | median WER 개선 + 곡선 확보 |
| V2 | **오언어(일/중) 억제 재구축** (사후필터 강화 or 디코더 토큰 제약) | lang_restrict 우회 보상 필요 | 오언어 0 + WER 미회귀 — **§3.2 필수기능: 게이트 미달 시 자율기각 금지·사용자 질의** |
| V3 | **반복폭주 가드** (백엔드 무관 n-gram 감지·꼬리 드롭) | CASE3 게이트 우회 보상 | worst-case max 개선 |
| V4 | 문장확정/F1 튜닝 (FINALIZE_GRACE·tail-reattach·타임스탬프 보정) | voxtral 타임스탬프 특성에 재적합 | F1 개선 + WER 미회귀 |
| V5 | 침묵 처리·커밋 정책(n_to_commit) 조정 | 즉시확정 완화 여지 | 무음 환각 감소 |
| V6 | 공유 필터 voxtral 특화 분기 | 백엔드별 오류 분포 상이 | voxtral 개선 AND whisper 경로 무변경 |

## 6. 측정 프로토콜 (경로 C 전용, cwd=워크트리, 워크트리 venv python 직접 호출)

```powershell
# 사전: 포트 8901 미점유 + 타 eval 프로세스 없음 확인 (VBCable 직렬화)
# 스크리닝 (매 이터레이션)
.venv\Scripts\python.exe scripts\eval.py --backend voxtral `
  --model-dir <메인저장소절대경로>\whisperlivekit\model\Voxtral-Mini-4B-Realtime-2602 `
  --files test_data/bong1.wav test_data/ytn2.mp3 test_data/sbs1.mp3 `
  --repeat 1 --output .omc/benchmarks/eval_voxtral_<ts>.json
# 채택 확정 (유망 후보만): --repeat 3 (fail-fast 금지)
# held-out (마일스톤 후보만): --files test_data/ytn1.mp3 test_data/eng1.mp3 --repeat 1
# AlignAtt diar-OFF 베이스라인 (메인 저장소에서 1회만): 기본 whisper 백엔드, --repeat 3, diar 생략
```
- `--diarization` 항상 생략(diar-OFF). `--frame-threshold`/`--beams`/`--compression-ratio-threshold` 등 AlignAtt 전용 플래그 금지.
- eval 후 `.omc/transcripts/` 정성 평가 필수(목표 구간 개선 여부·신규 이슈) — 정량+정성 종합으로 채택 판단.

## 7. 전역 채택 조건 + 자율 권한

**공통 채택 게이트**: ① 3종 worst(max) ≤ 현 voxtral 최선 +5%p ② 1종 이상 median WER 개선(WER > F1 우선)
③ pytest 통과. 스크리닝 수치는 방향 신호로만, 채택 확정은 repeat 3.

**자율 권한 (명시 부여)**: 공통 게이트 통과 → 사용자 승인 없이 브랜치 커밋(채택). 미달 → 자율 기각.
int8 양자화 진입·래퍼 재작성·필터 재구축은 자율 진행(보고서에 구성 이력 명시).

**자율 금지 (반드시 질의)**: 채점 로직/정답 전사/측정 프로토콜 변경, main 머지, 4bit 양자화 진입,
§3.1·§3.8 위반 소지 변경, V2(§3.2 필수기능)가 게이트 탈락한 경우의 기각.

## 8. 실험 기록 규칙

- 워크트리 브랜치 `EXPERIMENTS_VOXTRAL.md`에 Exp-V01부터. 각 항목: 가설/변경/측정(3종 med·max + 구성:
  양자화 여부·delay τ)/`### 분석`(정성 포함)/채택 여부. main의 EXPERIMENTS.md·LOG는 종료 시까지 불간섭.
- 종료 보고에 정식 Exp-N 편입안 + AlignAtt 대비표 + 구성 이력(양자화·τ) 포함.

## 9. 주요 파일 색인

| 역할 | 경로 |
|---|---|
| voxtral 래퍼 (재작성 허용) | `whisperlivekit/voxtral_hf_streaming.py` |
| 백엔드 분기 | `whisperlivekit/core.py` (voxtral 분기 L119-123, online_factory L274-276) |
| 공유 필터 (V2/V6 대상) | `whisperlivekit/filtering/__init__.py` `filter_segments` |
| 문장확정 (V4 대상) | `whisperlivekit/tokens_alignment.py` |
| eval 하니스 (--backend 패스스루) | `scripts/eval.py` (서버 기동 L206-224) |
| extras/conflict | `pyproject.toml` (voxtral-hf L52-56, conflicts L84-97) |

## 10. 루프 순서도 + 중단 조건

```
Gate 0 ─OOM→ 폴백 1~3(자율) → 4bit는 [사용자 질의] → 5 → 소진 [하드 블로커 보고]
  └PASS→ Gate 1 ─실패→ 래퍼 수정 ≤3라운드 → 소진 [하드 블로커 보고]
      └PASS→ Gate 2 (diar-OFF 베이스라인 + Exp-V00) ─참사→ 디버그→V2/V3 선적용→ 조기 무익?
          └PASS→ Gate 3: V1→V2→V3→V4→(V5/V6)→신규가설 루프
              ├ M1 달성 → [비차단 알림] 후 계속
              ├ M2 달성 → [최종 성공 보고·종료]
              ├ 무익 판정 → [중단 보고]
              └ 예산 상한 → [결산 보고 후 사용자 질의]
```

| 중단/보고 조건 | 판정 기준 | 행동 |
|---|---|---|
| M2 목표 달성 | §3 M2 (3종 WER<15% AND F1≥80%, repeat 3, held-out 미회귀) | 최종 성공 보고·종료 |
| M1 마일스톤 | §3 M1 | 비차단 알림 후 계속 |
| 하드 블로커 | venv/모델 확보 실패·OOM 트리 소진·Gate 1 3라운드 소진·VBCable 자체복구 불가(무음 2연속)·디스크 부족 | 보고 후 대기 |
| 무익 판정 | 확정측정 5연속 채택실패 or 스크리닝 10연속 무개선, AND 3종 중 2종 median이 AlignAtt diar-OFF 대비 +10%p 열세 | 중단 보고 (최선 구성+대비표+원인 가설+하이브리드 대안) |
| **ytn2 유예 (사용자 확정)** | 무익 판정 시점에 직전 5이터레이션 내 ytn2 median이 diar-OFF 베이스라인 대비 −5%p 이상 개선 추세면 **1회 한정 +5이터레이션 유예** | 유예 소진 후 재판정 |
| 예산 상한 | 이터레이션 20회 or 경로 C 측정 60런 | **결산 보고 후 사용자 질의 (사용자 확정)** |
