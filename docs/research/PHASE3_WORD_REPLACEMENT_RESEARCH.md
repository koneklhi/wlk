# Phase 3 단어 대치(용어 인식) 개선 — Deep Research 결과

- **날짜**: 2026-06-23
- **성격**: 채택/기각 실험이 아닌 **조사·설계 스파이크**. 아직 코드 변경 없음 — 다음 세션에서 여기 3계층 중
  하나를 골라 별도 브랜치/워크트리에서 구현·측정 시작.
- **조사 방법**: `deep-research` 스킬(5각도 병렬 검색 → 소스 20건 fetch → claim 99개 추출 →
  3-vote 적대적 검증 25건 → confirmed 18 / killed 7) + 저장소 코드 실측(Explore 서브에이전트 + 직접 grep).

## 1. 배경 / 동기

기존 `whisperlive` 개발 때는 배포 PC에서 인식 안 되는 단어를 하나하나 확인하며 JSON exact-match
대치 리스트(`origin: "6군" → replaced: "육군"`)를 수작업으로 쌓았다. `replaced` 항목(정답 용어)만
~1000개 넘게 누적되어 있다. 그러나:

- **whisperlivekit는 whisperlive와 오류 패턴이 다름** → 기존 exact-match 리스트를 그대로 못 씀.
- 보유 자산은 **정답 용어 텍스트 리스트뿐** — 해당 용어가 실제 발화된 음성+전사 쌍 데이터셋 없음.
- **과거 시도**: `whisper-large-v3-turbo` LoRA 파인튜닝(한·영 mix 교차학습) — 학습 데이터 WER은
  소폭 개선됐으나 **마이크 실환경·타 음성에서 성능 하락**(overfit, 일반화 붕괴) 확인.

이번 조사 목표: 파인튜닝 포함 전 방안을 놓고, 폐쇄망 오프라인·실시간 저지연·worst-case 강건성
제약 하에서 **현실적으로 적용 가능한 경로**를 찾는다.

## 2. 핵심 판정 — 음향 파인튜닝은 재시도하지 않는다

과거 실패에 학술적 이름이 있었다: **synthetic-to-real gap**(분포 이동).

- 텍스트/TTS-합성 데이터만으로 ASR을 파인튜닝하면 합성↔실음성 분포 차이로 OOD 성능이
  무너진다는 것이 다수 1차 소스의 합의(EMNLP 2024 [arXiv 2406.02925](https://arxiv.org/abs/2406.02925),
  SYNT++ [arXiv 2211.16049](https://arxiv.org/abs/2211.16049)) — synthetic-only는 WER 2배 이상 열화 보고.
  **당신이 마이크/타 음성에서 본 붕괴가 정확히 이 현상.**
- 완화책(SYN2REAL 가중치 task arithmetic)도 **real source-domain 오디오를 어딘가에서 요구**
  → 텍스트만 보유한 우리 제약에 부적합.
- "TTS-only LoRA가 in-domain 개선 + OOD 미회귀를 동시 달성한다"는 가장 매력적인 반대 주장
  (DAS, [arXiv 2501.12501](https://arxiv.org/pdf/2501.12501))은 **적대적 검증에서 일관 기각(0-3, 1-2)**
  — 즉 당신의 과거 관찰이 옳았고 논문 쪽 주장이 과장이었음.

> **결론**: real paired audio(용어가 실제 발화된 음성)를 확보하기 전까지 **음향 파인튜닝(LoRA 포함) 금지**.
> 같은 실패를 반복할 구조적 이유가 명확하다.

## 3. 채택 방향 — Whisper 가중치 동결 + 3계층 바이어싱

세 layer는 경쟁이 아니라 **레이어링**(상류 디코더 → 하류 후처리) 관계.

### Tier 2 — 오류 허용 퍼지/음소 후처리 (먼저 착수, 최저비용)

현 exact-match JSON 대치를 **음소·자모 G2P 유사도 매칭**으로 일반화. 1000개 정답 용어를 키로
음소 인덱스 구축 → STT 출력을 최근접 용어에 매핑하되 **거리 임계 + confidence 게이트** 하에서만 대치.

- **왜**: exact-match 리스트가 whisperlivekit의 다른 오류 패턴엔 전이 안 됨(현재 문제 그 자체).
  퍼지 매칭은 미리 못 본 오변형(예: 신규 "6군"류 오전사)도 흡수.
- **연구 근거**: ⚠️ 본 라운드에서 1차 소스로 직접 검증되지 않음(low confidence, 통과 claim 0개).
  g2pK([github.com/Kyubyong/g2pK](https://github.com/Kyubyong/g2pK)) 등은 fetch됐으나 over-correction
  통제 기법 자체는 미확보 — "무효"가 아니라 "이번 라운드에 증거 없음".
- **코드 적용 지점**: `whisperlivekit/filtering/__init__.py:66-71`의 regex exact-sub를 퍼지 매처로
  교체/보강. 동적 사전(`WordCorrectionManager`, SQLite, `filtering/__init__.py:6-101` /
  `add_user_word`·`delete_user_word` at 85-100)는 그대로 재사용.
- **평가**: 오프라인 ✅(g2pK 로컬) · 지연 ✅(후처리 0 추가) · overfit ✅(가중치 불변) ·
  **worst-case ⚠️ — over-correction(오대치)이 최대 리스크**, 거리임계·confidence gating·U-WER 회귀
  감시 필수.

### Tier 0 — 발화별 동적 프롬프트 바이어싱 (두 번째, 기존 코드 재사용)

`static_init_prompt` + 발화별 동적 용어 top-K 선별로 224토큰(~70단어) 한계를 우회.

- **근거**: 기본 prompt 경로는 **224토큰 하드 상한**(faster-whisper 소스 코드 1차 검증 —
  `hotwords_tokens[: self.max_length // 2 - 1]`, max_length=448) → 1000개를 다 못 넣고 희석됨.
  해법은 BR-ASR식 **발화별 후보 축소**([arXiv 2505.19179](https://arxiv.org/pdf/2505.19179), 200k 용어도
  per-utterance retrieval로 B-WER 2.9%만 열화) — 단 원 논문 retriever는 학습 필요 → 우리는
  **학습 없는 근사**(최근 컨텍스트 텍스트 ↔ 1000개 용어의 문자열/임베딩 유사도로 top-K 선별)로 대체.
- **코드 적용 지점**:
  - 주입: `whisperlivekit/simul_whisper/config.py:22` `static_init_prompt` —
    `align_att_base.py:98`의 `trim_context()`에서 **컨텍스트 트리밍에도 살아남는 영구 프롬프트**
    (`after = len(self.cfg.static_init_prompt)` 기준으로 보존). glossary 상주 주입에 적합.
    일반 `init_prompt`(config.py:21)는 트리밍 시 사라짐 — 상주시키려면 반드시 `static_init_prompt` 사용.
  - 동적 구성: `simul_whisper.py:157-160`의 컨텍스트 초기화부.
  - 후보 선별기: `whisperlive_code/prompt_manager.py:144-169` `get_relevant_glossary(input_text)`가
    **이미 "입력 텍스트 ↔ 용어 매칭" 로직**을 갖고 있음(번역 glossary용) → 같은 패턴을 STT 프롬프트용으로 재사용.
- **평가**: 오프라인 ✅ · 지연 ✅(프롬프트 주입은 저렴) · overfit ✅ ·
  **worst-case ⚠️** — 소프트 프롬프트는 말하지 않은 용어를 환각으로 끌어낼 수 있음(over-biasing).
  K를 작게(예 20~40) 유지하고 U-WER 회귀 필수 감시.

### Tier 1 — TTS 발음변이 + prefix-trie shallow-fusion (연구근거 최강, 구현 리스크 중)

각 용어를 **로컬 TTS로 합성 → frozen Whisper로 전사 → Whisper 토큰 공간의 발음 변이 추출**
(텍스트에서 시작, 오디오 데이터셋 불필요) → 변이를 prefix-trie로 쌓고 **beam search 중 토큰당
+1 보너스(shallow fusion)**. acoustic/LM logit은 안 건드려 Whisper 거동 보존.

- **근거 강도**: 본 연구 최강. [arXiv 2508.17796](https://arxiv.org/html/2508.17796v1)
  (APSIPA 2025 peer-reviewed), Whisper-large-v3, **N=1000 distractor에서 B-WER 42~43% 감소,
  unbiased WER 2.81%→2.31%로 사실상 불변**(over-biasing 미발생). 가중치 미변경 = 과거 overfit
  실패 모드를 **구조적으로 회피**.
- **우리 코드에 유리한 점**: AlignAtt 디코더에 **beam 경로가 이미 존재**
  (`whisperlivekit/simul_whisper/backend.py:339-340`
  `decoder_type = 'greedy' if self.beams == 1 else 'beam'`, `config.py:18` `beam_size: int = 5` 기본값)
  → 논문이 우려한 "greedy 비호환"이 우리 백엔드엔 덜 치명적. 보너스 가산 훅은 beam score 계산부
  (`simul_whisper.py` 디코딩 루프 / `mlx/decoders.py:113-122` beam 확장부)에 삽입.
- **평가**: 오프라인 ⚠️(폐쇄망에 **로컬 한·영 TTS** 필요 — 1회성 오프라인 전처리 단계) ·
  지연 ⚠️(beam>1 강제 시 스트리밍 지연 — **실측 필수**, 논문에 latency 분석 없음) · overfit ✅ ·
  worst-case ✅(논문상 U-WER 불변, 1000 규모 직접 검증) · 구현 ⚠️(디코더 내부 수정).
- **핵심 미검증**: 영어 LibriSpeech 단일 평가 — **한국어 자모/G2P 변이가 Whisper 토큰 공간에서
  영어만큼 잘 잡히는지, code-switching(ROKAF·육군)에서의 변이 품질** 미검증.

## 4. 기각된 방안 (검증에서 떨어진 것 — 재조사 불필요)

| 방안 | vote | 기각 사유|
|---|---|---|
| CB-Whisper OV-KWS가 완전 training-free | 0-3 | CNN 분류기(0.2M params)를 라벨 데이터로 학습해야 함 — training-free 아님 |
| OV-KWS를 텍스트+템플릿만으로 재현 가능 | 1-2 | keyword enrollment에 용어별 TTS 오디오를 encoder에 통과시켜야 함(텍스트 전용 아님) |
| BR-ASR류가 ASR 파인튜닝 없이 overfit 회피 | 0-3 | retriever 자체가 speech+bias paired data로 학습 필요 — 우리 자산엔 없음 |
| faster-whisper가 70단어 한계 극복 retriever를 자체 제공 | 0-3 | 논문 확장 제안일 뿐 stock API엔 없음 |
| DAS: TTS-only LoRA가 OOD 미회귀 | 0-3 | 본 라운드 검증서 반증 — 과거 실패 관찰과 일치 |
| synthetic fine-tuning이 OOD에 미미한 영향(-1%)만 준다 | 0-3 | 상동, 근거 불충분 |

## 5. 저장소 현황 코드 맵 (참고용 — 구현 시작 시 바로 참조)

| 항목 | 파일:라인 |
|---|---|
| 단어 대치 매니저(JSON+SQLite 병합) | `whisperlivekit/filtering/__init__.py:6-101` |
| JSON 기본 사전 포맷 | `whisperlivekit/filtering/admin_replacement.json` — `[{"origin":"6군","replaced":"육군"}]` |
| 환각 토큰 사전 | `whisperlivekit/filtering/hallucination.json` |
| exact-match 치환 실행 | `whisperlivekit/filtering/__init__.py:42-73` `filter_hallucination()` / `:76-110` `filter_segments()` |
| 사용자 사전 동적 추가/삭제 | `filtering/__init__.py:85-100` `add_user_word()` / `delete_user_word()` |
| 환각 필터(Exp-002/028/057) | `whisperlivekit/simul_whisper/backend.py:184-243` `_filter_cross_batch_repetitions()` |
| 라이브 디코더 설정(beam_size 등) | `whisperlivekit/simul_whisper/config.py` (`AlignAttConfig`) |
| `static_init_prompt`(트리밍 생존 프롬프트) | `config.py:22`, 보존 로직 `align_att_base.py:98` |
| `init_prompt`(휘발성 프롬프트) | `config.py:21`, 주입 `simul_whisper.py:159-160` |
| beam/greedy 분기 | `simul_whisper/backend.py:339-340` |
| MLX beam 디코더 확장부 | `simul_whisper/mlx/decoders.py:113-122` |
| 번역 glossary 동적 매칭(재사용 대상) | `whisperlive_code/prompt_manager.py:14-183`, 매칭 로직 `:144-169` `get_relevant_glossary()` |
| faster-whisper hotwords(레거시, 라이브 미배선) | `whisperlive_code/transcriber.py:1542-1546` — **whisperlivekit SimulStreaming엔 없음**, 별도 배선 필요 |
| 테스트 | `tests/test_filtering.py:139-200` `TestFilterHallucination` |

**주의**: faster-whisper식 `hotwords` 파라미터는 **레거시 `whisperlive_code` 전용**이며 실제 배포
백엔드인 `whisperlivekit`의 SimulStreaming(AlignAtt) 라이브 경로엔 배선돼 있지 않다. Tier 0/1은
AlignAtt 쪽(`config.py`/`simul_whisper.py`/`backend.py`)에 새로 연결해야 한다.

## 6. 권장 실행 순서

```
1단계  Tier 2 (퍼지 후처리)   — 가장 싸고 현 방식의 직접 일반화. 먼저 깔아 베이스라인 확보.
2단계  Tier 0 (동적 프롬프트) — 상류에서 오류 자체를 줄임. 기존 get_relevant_glossary 재사용.
3단계  Tier 1 (trie shallow-fusion) — 근거 최강이나 구현·지연 리스크 큼. 1·2로 부족할 때 투입.
   ✗  파인튜닝 — real paired audio 확보 전 금지.
```

## 7. 측정·채택 게이트 (CLAUDE.md §4 준수 — 생략 금지)

- 위 어떤 것도 "채택"이 아니라 "측정 후보 가설". 경로 C(VBCable) **N≥3 median+분산**,
  화자분할 ON, 테스트=bong1+ytn2+sbs1 + held-out=ytn1+eng1.
- **bias 계열의 핵심 지표는 용어 recall이 아니라 U-WER(unbiased WER) 회귀** — worst-case 우선
  원칙상, 용어 인식이 올라도 일반 단어를 망가뜨리면(over-biasing/over-correction) 기각.
  논문이 U-WER 불변을 강조한 이유와 정확히 일치.
- §3.8 데이터 특화 하드코딩 제약 위배 아님: 유지보수되는 1000개 용어 리스트(데이터) 기반이며
  리스트 내 임의 용어가 균일하게 혜택 → ytn2/bong1 특화 암기가 아닌 일반화 메커니즘.

## 8. 남은 미검증 질문 (다음 조사/실험 대상)

1. Tier 1(trie shallow-fusion, beam size 10)을 저지연 스트리밍(beam≥1)에 통합 시 실측 latency·
   worst-case WER — large-v3-turbo + 화자분할 ON 파이프라인에서 측정 필요.
2. 폐쇄망 배치 가능한 오프라인 한·영 TTS로 ~1000개 용어의 발음 변이를 Whisper-large-v3-turbo
   토큰 공간에서 추출할 때, 한국어 자모/code-switching 변이 품질이 영어만큼 잡히는지.
3. Tier 0+1 결합: 학습 없는 텍스트 유사도 retriever로 1000→소수 발화별 축소가 224토큰 희석과
   over-biasing distractor 문제를 동시에 줄이는지(미검증 응용).
4. Tier 2의 한국어 자모 G2P 퍼지 후처리 over-correction 통제(confidence gating·U-WER 회귀
   모니터) — 본 라운드 1차 소스 미확보, 별도 deep-research 후보.

## 9. 핵심 출처

- Tier 1 근거: [arXiv 2508.17796](https://arxiv.org/html/2508.17796v1) (APSIPA 2025) —
  TTS→frozen Whisper 발음변이 + trie shallow-fusion, N=1000 B-WER↓42-43%
- 224토큰 한계: [faster-whisper transcribe.py](https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/transcribe.py) + [arXiv 2502.11572](https://arxiv.org/html/2502.11572v1)
- frozen biasing 기법군/code-switching: CB-Whisper [arXiv 2309.09552](https://arxiv.org/html/2309.09552v3)
  (단, OV-KWS는 CNN 분류기 학습 필요 — "training-free" 주장은 기각)
- 학습형 모듈 부적합: TCPGen [arXiv 2410.18363](https://arxiv.org/html/2410.18363v1),
  BR-ASR [arXiv 2505.19179](https://arxiv.org/pdf/2505.19179) (paired audio 요구)
- 파인튜닝 기각 근거: synthetic-to-real gap [arXiv 2406.02925](https://arxiv.org/abs/2406.02925);
  DAS TTS-only 주장 기각 [arXiv 2501.12501](https://arxiv.org/pdf/2501.12501)
- 한국어 G2P 도구(Tier 2용, 별도 검증 필요): [g2pK](https://github.com/Kyubyong/g2pK)

## 10. 다음 세션에서 시작할 때

- 이 문서 §3(Tier 2/0/1 중 택1) + §5(코드 맵) + §7(측정 게이트)만 읽으면 바로 구현 착수 가능.
- 워크트리 규약(개인 CLAUDE.md): 새 브랜치+워크트리에서 subagent가 구현, 메인 세션은 main에 머묾.
- 구현 완료 후 §4 자율 루프(구현→측정→기록) 그대로 적용, `/log-experiment`로 기록.
