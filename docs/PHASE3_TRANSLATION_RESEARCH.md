# Phase 3/4 번역 파이프라인 개선 리서치 (2026-07-06)

> 이 문서는 새 세션에서도 맥락 없이 이어갈 수 있도록, 2026-07-06에 수행한 두 차례 deep-research
> 워크플로우(웹 검색 fan-out → 소스 페치 → 주장별 3표 적대적 검증)의 결과를 정리한 것이다.
> 원본 조사는 143+105개 서브에이전트, 40여 개 1차 출처(arXiv/ACL/WMT/IWSLT 등)를 사용했다.
> **모든 수치는 영어·소비자/특허 도메인에서 측정된 것으로, 군사 한↔영 도메인 일반화는 미검증이다.**
> 채택 전 CLAUDE.md §4 규약(경로 C, N≥3, worst-case 1순위)에 따른 실측이 반드시 필요하다.

---

## 0. 이 문서가 다루는 두 가지 질문

1. **번역 품질 개선**: 현재 whisperlive 이식 방식(단순 키워드 in-매칭 glossary + 프롬프트 지시)의
   구조적 한계를 어떻게 개선하나?
2. **모델·아키텍처**: gpt-oss-20b 말고 최근 로컬 모델 대안은? cascaded(STT→별도 LLM) vs
   end-to-end 음성번역 중 어느 쪽이 우리 목적에 맞나?

---

## 1. ⚠️ 발견된 긴급 이슈 — 배포 설정과 하드웨어 VRAM 불일치

[docs/TRANSLATION_SETUP.md:55](TRANSLATION_SETUP.md#L55)는 "RTX 5090 환경에서만 gpt-oss-20b-F16.gguf
(~40GB) 적재 가능"이라고 되어 있으나, **RTX 5090의 VRAM은 32GB**다. F16 gguf(~40GB)는 5090 한 장에
**단독으로도 적재 불가능**하다.

- gpt-oss-20b의 네이티브 포맷은 **MXFP4(~16GB)**다. 배포를 F16 → MXFP4 빌드로 전환하면
  Whisper-large-v3-turbo(+Sortformer 화자분할)와 32GB 안에서 공존 가능해진다.
- **이건 모델 교체 이전에 먼저 처리해야 할 선결 항목이다.** 착수 전 실물 GPU로 VRAM 재확인 필요.
- 관련 문서(TRANSLATION_SETUP.md, ROADMAP.md:164, docs/DEPLOYMENT_OFFLINE.md)의 "~40GB" 서술도
  전환 시 함께 갱신해야 한다 (CLAUDE.md §4 "코드 변경 시 연동 갱신 문서" 표 참조).

---

## 2. 번역 품질 개선 — 두 가지 핵심 문제와 해법

### 2.1 문제 정의

현재 [whisperlive_code/translator.py:115](../whisperlive_code/translator.py#L115)의
`get_relevant_glossary()`는 `origin.lower() in input_lower` 단순 in-매칭이다. 두 가지 문제:

- **(1) 매칭 견고성**: STT가 "공군"을 "공궁"으로 오전사하면 in-매칭 실패 → 용어쌍이 프롬프트에서 누락.
- **(2) LLM 지시 무시**: 프롬프트에 "공군은 ROKAF로 번역하라"고 넣어도 LLM이 무시하고 자유 번역할 때가 있음.

### 2.2 문제(1) 해법: glossary 매칭을 fuzzy/음소 매칭으로 교체

동일한 실패모드(단일 문자 치환에도 매칭 파손)가 선행 연구의 Trie 정확매칭에도 존재함이 확인됨
([WMT 2024, 2410.15690](https://arxiv.org/pdf/2410.15690), 3-0 검증) — exact-match 계열 전체의
구조적 한계.

| 방법 | 신뢰도 | 요지 | 우리 적용성 |
|---|---|---|---|
| **한국어 자모 단위 편집거리** ⭐ | high, 3-0 | `hangul-jamo`의 `decompose()`로 음절을 자모 분해. "공군"=ㄱㅗㅇㄱㅜㄴ vs "공궁"=ㄱㅗㅇㄱㅜㅇ → 종성 1자모 차이 = 편집거리 1 | **최우선 권고**. 외부 의존 0, Unicode 수식 기반이라 안정, 폐쇄망 OK. §3.8 일반화(음소 거리 척도라 특정 단어 암기 아님) |
| 음향/음소 임베딩 retrieval | high, 3-0 (단 영어 도메인) | Acoustic Neighbor Embeddings가 exact·semantic·BM25보다 ASR 오전사 회수에 우월 (tail recall 83.9% vs BM25 59.5%) ([2409.06062](https://arxiv.org/html/2409.06062v1)) | 자모 매칭으로 부족할 때 검토. 한↔영 혼용 음소 표현 통일이 미해결 |
| ASR n-best + 음소 대응 랭킹으로 **전사 자체**를 교정 | high, 3-0 | context를 n-best ASR 가설에 자모 LCS로 매칭해 교정 → recall +34%, F1 +16% ([COLING 2025](https://aclanthology.org/2025.coling-industry.32.pdf)) | **가장 근본적 레버리지**: 전사를 먼저 고치면 기존 glossary가 그대로 동작 → 문제(2)도 완화 |

> ⚠️ 반증됨: 특정 NPD 음소거리 레시피, "음향 임베딩 retrieval error 49.9% 감소" 수치는 적대적 검증에서
> killed(0-3, 1-2). 접근법 방향은 유효하나 **그 구체 수치는 인용 금지**.

### 2.3 문제(2) 해법: LLM 용어 지시 불이행 → 강제 계층 추가

프롬프트 주입만으로는 불완전함이 모델 횡단으로 확인됨(high): ChatGPT가 glossary 용어 적용 실패·반대언어
사용, GPT-4.1도 용어 사전 제공 시 정확 사용률 37.1%로 하락 ([2410.15690](https://arxiv.org/pdf/2410.15690),
[2507.03580](https://arxiv.org/abs/2507.03580)). 단, 프롬프트 주입 자체가 무용은 아님(+9 BLEU 효과 유지)
— 버리지 말고 강제층을 얹는 구조로.

**A. 번역 후 결정론적 용어 강제(post-edit) — 우리 스택에 현실적 (high, 2-1)**
- 누락 용어 재삽입 지시 → 용어 준수율 36.67%→**72.88%** ([WMT 2023, 2310.14451](https://arxiv.org/abs/2310.14451))
- DuTerm: NMT 초안 → LLM을 generator 아닌 "context-driven mutator"로 post-edit ([WMT 2025, 2511.07461](https://arxiv.org/abs/2511.07461))
- ⚠️ 72.88% = **~27% 여전히 누락** → soft/확률적. **최종 결정론적 string 치환 검증 필수**.

**B. 하드 제약 디코딩 — 학계 최강 보장이나 우리 스택 미지원 (high, 3-0)**
- Post & Vilar 2018: 제약 수 O(1) lexically constrained decoding ([N18-1119](https://aclanthology.org/N18-1119/))
- Cascade Beam Search: logit 조작 + grid-beam, **학습 불필요**, WMT21 우승작 수준 ([2305.14538](https://arxiv.org/abs/2305.14538))
- ❗ **현실 제약**: 이 기법들은 encoder-decoder NMT + beam search 전제. 우리는 llama.cpp
  `/v1/completions` HTTP로 gpt-oss-20b 호출(`use_beam_search: False`) → llama.cpp가 grid-beam·
  per-constraint 강제를 노출하지 않아 **B를 쓰려면 추론 엔진 교체 필요**.
  - 절충안: llama.cpp `logit_bias`로 "타깃 용어 토큰 확률 ↑"(Cascade의 절반)는 저비용 구현 가능.
    멀티토큰 용어 완전 보장은 안 되므로 결국 A의 사후 치환이 신뢰 보장층.

> ⚠️ 반증됨(중요): "유연한 LLM이 하드 제약보다 항상 우월", "미세조정이 제약 디코딩보다 항상 우월",
> "post-edit이 미세조정보다 항상 우월" — **모두 0-3 killed**. 단일 기법 만능론 금지. 조합이 정답.

### 2.4 권고 파이프라인 (3층)

```
[STT 전사]
   │
   ├─ Layer A (문제1): 자모 편집거리 fuzzy 매칭으로 glossary 용어 탐지
   │     "공궁입니다" → 편집거리 1 → "공군:ROKAF" 주입   ← 외부의존 0, 즉시 적용 가능
   │
   ├─ Layer B (문제2): 프롬프트 주입 유지(+llama.cpp logit_bias로 타깃 토큰 부스트)
   │
   └─ Layer C (문제2): 번역 후 결정론적 검증
         탐지된 source 용어의 target("ROKAF")이 출력에 없으면
         → 통제된 치환 또는 재요청   ← ~27% 누락 흡수
```

우선순위: **Layer A부터** — 가장 싸고, 가장 §3.8 일반화 안전하고, 문제(2)까지 부분 완화.

### 2.5 다음 실측으로 답할 질문

- **레버리지 비교(최우선 실측 권고)**: ASR 단계에서 음소 교정(Layer A / 위 표 3번째 행)을 먼저 하면
  기존 exact glossary가 그대로 동작 → 번역 단계 제약 없이 문제(2)까지 풀릴 가능성. 이걸 먼저
  비교 실측할 것.
- 자모 편집거리가 군사 용어(약어 ROKAF·F-15, 한↔영 code-switching 구간)에서 실제로 회수율을 올리는지.
- Layer C의 한↔영 양방향 치환을 형태변형(곡용/활용/복수형) 없이 하드코딩 없이 일반화하는 규칙.

---

## 3. 모델·아키텍처 리서치

### 3.1 아키텍처: cascaded(STT→별도 LLM) 유지가 맞다 — 강하게 확인됨

| 근거 | 내용 | 출처 |
|---|---|---|
| Whisper 내장 번역 불가 | translate task는 **X→영어 전용**, 한국어 출력 불가. **large-v3-turbo는 translate 줘도 원어 반환**(내장 번역 사실상 무력) | [openai/whisper](https://github.com/openai/whisper) |
| e2e는 용어 제어가 구조적으로 어려움 | cascaded는 ASR↔MT 사이 텍스트 중간표상이 있어 glossary·제약디코딩·필터를 명시 주입 가능. e2e(S2S)는 중간 텍스트층이 없어 어렵고 재학습 요구 | [Coval](https://www.coval.ai/blog/speech-to-speech-vs-cascaded-voice-ai-which-architecture-should-you-deploy/) |
| 용어 밀집 도메인서 cascaded 우위 | IWSLT: terminology-dense 과학강연 번역에서 cascaded(34.0) > e2e(31.4 BLEU) | [KIT IWSLT'23](https://arxiv.org/abs/2306.05320) |
| 모듈성 = 오류 격리·독립 개선 | ASR/MT 분리로 오류 위치 특정·표적 개선·교체 가능(§3.8 worst-case 추적과 정합) | [2502.00377](https://arxiv.org/html/2502.00377v1) |
| 지연 약점이 우리는 작음 | cascaded 단점 = 오류 전파+지연. 우리는 **"문장 확정 후 번역" 배치 트리거**(§3.4)라 simultaneous MT의 revision-latency를 회피 | [2106.06636](https://arxiv.org/abs/2106.06636) |

**균형추**:
- SeamlessM4T v2는 한국어 텍스트 출력이 실제로 가능함(e2e가 무조건 한국어 못 낸다는 건 틀림).
  단 glossary/프롬프트 용어 제어 수단이 없고 범용 도메인 → 우리 목적(군사 용어 제어)엔 부적합.
- cascaded의 잔존 약점 = **ASR 오류 전파**. bong1류 다화자·code-switching worst-case에서 ASR이
  틀린 용어가 그대로 번역에 전파됨 → §2의 Layer A(음소 매칭)·ASR 바이어싱(아래 3.3)으로 완화.

**결론**: STT→별도 LLM 번역(cascaded) 유지가 정답. e2e 통합 모델은 한국어 미지원이거나,
지원해도 용어 튜닝성을 잃는다.

### 3.2 로컬 번역 모델 후보 (2025 하반기~2026, RTX 5090 32GB 단일 GPU 전제)

**전제**: 배포 = 단일 RTX 5090(32GB), Whisper-large-v3-turbo(SimulStreaming PyTorch fp16 백엔드,
실가동 ~6GB대) + Sortformer 화자분할과 동시 구동 → 번역 LLM 가용 VRAM 실질 **~20~24GB**.
군 폐쇄망 = 오프라인 온프레미스 + **상업 배포 허용 라이선스**가 1차 필터.

#### 채택 가능 (Apache 2.0 = 가장 깨끗)

| 모델 | VRAM(Q4) | 비고 |
|---|---|---|
| **gpt-oss-20b (현행)** | MXFP4 ~16GB | Apache 2.0. **기준선(incumbent)으로 유지**. 한국어 번역 품질 입증 벤치 없음 → 실측 필요. §1의 F16→MXFP4 전환 선결 |
| **Qwen3-30B-A3B-Instruct-2507** ⭐ | ~18.6GB (Q4_K_M) | Apache 2.0, MoE(총 30.5B/활성 3.3B) — 30B급 품질 + 3B급 속도. 강한 다국어(MultiIF 67.9, INCLUDE 71.9). Unsloth 기반 LoRA/QLoRA 지원. **신규 1순위 후보** |
| Mistral Small 3.1 24B Instruct | ~14.3GB (Q4_K_M) | Apache 2.0(가장 깨끗). 멀티모달이라 텍스트 전용 동급 대비 학습예산 분산 가능성. 한국어 특화 아님 |
| Qwen3-14B | ~9GB (Q4_K_M) | Apache 2.0. 32GB에선 VRAM 여유가 변별점 안 됨 — 지연 우선일 때만 |

#### 라이선스 주의 (법무 검토 필요)

- **Gemma 3 27B** (~14~16GB): Gemma 라이선스(Apache 아님, 상업·온프레미스 허용). Prohibited Use
  Policy에 무기/WMD 관련 조항 + Google 일방 해지권 잔존 → 군사 맥락 잔여 리스크. 차순위·법무 검토.
- **HyperCLOVA X SEED Think 32B**: 한국어 추론 최강급(KoBALT 50.6, EXAONE 4.0 32B 48.3 상회)이나
  **비전-언어 멀티모달이라 ~68GB/멀티GPU 권장** → 단일 32GB에 native 부적합. 양자화+실측 필요.
- **Kanana-2-30B-A3B**: 한국어 강함(KMMLU 67.32). 내부 폐쇄망 자체 운용은 라이선스 조항(4.3조)상
  허용 가능성 높으나 "Powered by Kanana" 표기·파생모델 명명 의무 있음 → 검토.

#### 기각

- **EXAONE 4.0/4.5**: 한국어 최상급(KMMLU-Pro 67.7)이나 **"1.2-NC"(비상업) 라이선스** → LG와
  별도 계약 없이 군 배포 불가.
- **Llama 3.3 70B**: AWQ INT4도 ~35GB > 32GB, 단독 적재도 불가.
- **DeepSeek V3/R1**: 671B, 400GB+ 필요. 로컬 대안(R1-Distill-Qwen-14B)은 사실상 Qwen이라 이점 적음.

#### VRAM 예산 정리 (confirmed)

- faster-whisper(CTranslate2) 기준이면 turbo int8 ~1.5GB, FP16 ~2.5GB로 매우 작음. 단 **우리
  실제 백엔드는 CTranslate2가 아니라 SimulStreaming PyTorch fp16**이라 실가동 ~6GB대가 더 근접.
- Sortformer 스트리밍(v2, 117M)은 고정 윈도라 파일 길이 무관 상수 메모리(정확한 수치는 미공개,
  실측 권장). 참고: v1(비스트리밍)은 길이에 O(T²) 비례해 OOM 가능하지만 우리는 v2만 사용.
- 결론: ASR+diar 실가동 ~8~12GB 보수적으로 잡으면 번역 LLM 몫은 **~20~24GB** — 30B-A3B Q4(~18.6GB)
  까지 동시 구동 현실적. 단 worst-case 마진은 실측 확정 필요.

#### ⚠️ 인용 금지 — killed된 벤치마크 수치

적대적 검증에서 다음이 **반증(0-2, 0-3)**됨. 채택 근거로 재인용하지 말 것:
- "Gemma2-9B FLORES-200 KO→EN spBLEU 23.24/COMET 88.1" → 방향(KO→EN↔EN→KO)과 지표(COMET↔COMETKiwi)가
  뒤바뀐 오인용. 실제 Gemma2-9B KO→EN은 spBLEU 35.96/COMET 88.47(GPT-3.5 32.12/88.12 상회).
- "Trillion-7B MMLU 77.93/MATH 77.89" → 이 수치는 7B가 아니라 **21B 모델(Tri-21B)**의 점수.
  실제 Trillion-7B-preview는 MMLU 63.52/MATH 32.70.
- "Gemma 3 27B 인간평가 3위(8.57)"의 출처(Nuenki)는 **인간평가가 아니라 LLM-as-judge**이며
  언어별 분해가 없는 종합 평균(한국어 개별 수치 아님). 단, TranslateGemma 기술보고서(2601.09012)는
  실제 EN→Korean 인간(MQM) 개별 수치를 제공함(TranslateGemma 27B 3.1 < Gemma 3 27B 3.8, 낮을수록 좋음)
  — 이쪽은 인용 가능.

### 3.3 ASR 단계 용어 바이어싱 (참고 — cascaded 오류 전파 완화 수단)

- Whisper `initial_prompt`: 도메인 용어·고유명사 철자를 재학습 없이 교정 가능하나 **224토큰 한계**
  + "스타일 steering일 뿐 음향 이해를 덮어쓰지 못함"(신뢰성 한계, OpenAI 공식 가이드 verbatim).
- TCPGen(Tree-Constrained Pointer Generator) 등 dynamic vocabulary deep biasing은 224토큰 한계를
  우회하고 도메인 WER를 대폭 낮춤(해양 도메인 WER 27.82%→11.12%) — 단, biasing 모듈 자체는 도메인
  데이터로 별도 학습 필요, 검증은 전부 영어/오프라인 배치이며 한국어·실시간 스트리밍·turbo 미검증.
  우리 파이프라인(faster-whisper/CTranslate2 계열)은 디코더 토큰 확률을 노출하지 않아 커스텀 디코드
  루프가 필요 → **1순위는 이미 지원되는 hotwords/initial_prompt 활성화 + glossary 연동**, TCPGen은
  그것으로 부족할 때만 검토할 무거운 대안.

---

## 4. 종합 권고 (실행 순서)

```
1. [선결] 배포 gpt-oss-20b: F16(~40GB) → MXFP4(~16GB) 빌드 전환
   ← 이거 안 하면 RTX 5090(32GB)에 안 올라감. TRANSLATION_SETUP.md/ROADMAP.md/DEPLOYMENT_OFFLINE.md
     동반 갱신 필요 (CLAUDE.md §4 연동 갱신 표)

2. [아키텍처] cascaded 유지 확정. e2e 통합 모델(SeamlessM4T 등) 도입 안 함.

3. [번역 품질] Layer A(자모 fuzzy glossary 매칭)부터 프로토타입.
   가장 싸고, §3.8 일반화 안전하고, ASR 오전사→번역 전파 문제까지 부분 완화.
   그 다음 Layer C(번역 후 결정론적 치환 검증) 추가.

4. [모델] gpt-oss-20b(MXFP4 전환 후)를 기준선으로, Qwen3-30B-A3B-Instruct-2507 ·
   Mistral Small 3.1 24B를 동일 군사 한↔영 코퍼스로 경로 C N≥3 실측
   (품질·지연·VRAM, worst-case 우선) 후 채택 결정.

5. [레버리지 실측 우선순위] "ASR 단계 음소 교정 먼저 vs 번역 단계 용어 강제 먼저" 비교 —
   전자가 유효하면 후자 없이도 문제(2)까지 완화될 가능성 있음. 이 비교부터 먼저 실측 권고.
```

---

## 5. 리서치 방법론 메모 (재현/확장 시 참고)

- 워크플로우: `Workflow` tool의 5각도 병렬 웹서치 → 소스 페치 → 주장별 3표 적대적 검증
  (각 검증자가 독립적으로 반증 시도, ≥2/3 반증 시 killed) → 신뢰도별 synthesis.
- 리서치 1(번역 품질): 105 서브에이전트, 23 소스, 109 claims → 25 검증 → 16 confirmed/9 killed.
- 리서치 2(모델·아키텍처): 143 서브에이전트, 46 claims → 41 confirmed/5 killed.
- 두 리서치 모두 시간민감 정보(2025 하반기~2026 모델 동향) 포함 — **재사용 시 모델 버전·라이선스는
  재확인 권장** (예: Qwen3/Gemma의 후속 버전 출시 여부, 라이선스 조항 변경).
