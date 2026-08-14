Phase 1 — 기본 STT 동작 확인 ✅ 완료 (2026-05-19)
whisperlivekit + whisper-large-v3-turbo 로컬 모델로 실시간 전사 동작을 경로 A(파일 기반)·경로 B(마이크)
양쪽에서 확인, 폐쇄망 환경(HF_HUB_OFFLINE=1)에서 외부 호출 0건 확인 완료.


Phase 2 — 문장 단위 확정 로직 구현
목표
전사된 텍스트가 문장 단위로 비확정→확정 전환되도록 만들고,
실시간 전사 품질(응답 지연·전사 완전성)도 함께 확인한다.
검증 경로 역할(하단 "목표 수치" 절과 일치):
- 경로 C (VBCable 루프백) — **1차 정량 성능 신호**. 문장 분리 F1·WER 채택/기각 기준.
- 경로 A (`test_client.py` 터미널) — **빠른 개발 스모크**(코드 변경이 회귀를 냈는지)용. 성능 판정 기준 아님.
- 경로 B (브라우저 + 배포 UI) — 마이크 직접 입력 **정성** 평가.
태스크

 2-1. 문장 단위 확정 알고리즘 선택 및 구현 [설계 세션]
→ 비교 대상 (예시이며 이 목록에 한정하지 않음):
  - 스트리밍 정책: SimulStreaming (AlignAtt + CIF 기반, WLK 기본값), LocalAgreement (가설 비교 기반)
  - 확정 신호: Whisper segment 경계, no_speech_prob, VAD 무음 구간, 구두점, 언어 전환 등
→ 구체적인 정책·신호 조합은 설계 세션에서 후보를 비교한 후 사용자와 합의해 결정한다
→ 기존 whisperlive의 임시방편(N회 반복 확정, 타임스탬프 변화량 임계치)은 이식하지 않음
 2-2. 비확정 / 확정 플래그를 전사 텍스트와 함께 출력 (`test_client.py --live` 출력의 `lines[]` / `buffer_transcription`으로 확인)
 2-3. 경로 B (마이크 직접 녹음) 정성 평가 — 배포 UI에서 시각 + 실시간 품질 확인
→ 확정 시 글자색이 옅은 회색에서 일반 색상으로 자연스럽게 전환되는지 확인
→ 한·영 언어 전환 시 양쪽 모두 정상 인식되는지 확인
→ 실시간 품질 정성 기준:
  - 발화 종료 후 화면에 전사 완료까지 체감 지연이 없음
  - 말한 단어가 큰 누락 없이 전사됨
  - 환각 출력이 산발적 수준 (Phase 3 필터링 도입 전이라 0건은 비현실적)
 2-4. Code-Switching(한영 혼용 발화) 동작 확인 (기본 동작 후 문제 발생 시 보강)
→ 단어 유실·환각·문장 조기 확정 발생 여부 확인 후 필요 시 대응

완료 기준

[경로 C — 1차 정량 성능 (채택/기각 기준)]
- `/eval`의 문장 분리 F1로 확정 경계 정확도를 정량 측정 — 목표 ≥ 0.7(1차), 이상적으로 ≥ 0.8
  (문장 확정 로직 도입 전 F1≈0이 정상, 로직 구현 후 상승 확인)
- WER이 경로 C 베이스라인 대비 개선 또는 유지 (상세 기준은 하단 "채택/기각 규칙" 참조)

[경로 A — 파일 기반 스모크, `test_client.py`] (성능 판정 아님, 회귀 확인용)
- 문장이 끝날 때 확정 플래그가 `test_client.py --live` / `--json` 터미널 출력에 표시됨
- 한국어만 입력 시 영어 오감지로 인한 환각 출력이 산발적 수준
- 영어만 입력 시 한국어 오감지로 인한 환각 출력이 산발적 수준
  (환각 완전 제거는 Phase 3 필터링 단계에서 처리)

[경로 B — 마이크 직접 녹음, 배포 UI]
- 확정 시 글자가 옅게(미확정) → 진하게(확정) 자연스럽게 전환 (배포 UI는 `opacity` 0.4 → 1)
- 발화 종료 후 화면에 전사 완료까지 체감 지연이 없음
- 말한 단어가 큰 누락 없이 전사됨
- 한·영 전환 시 양쪽 언어 모두 인식됨

[공통]
- 한영 혼용 발화 테스트에서 심각한 단어 유실 없음 (문제 발생 시 2-4 보강 진행)


Phase 2 성능 개선 우선순위 (반자율 개선 루프 기준)

데이터 우선순위 (CLAUDE.md §3.8 현행 regime)
- **1순위 = ytn2·bong1 공동 최우선**: ytn2(짧은 텀 코드스위칭) + bong1(영어 2명+한국어 2명, 다화자·긴 발화). 일반 역량 향상이 목표 — 데이터 특화 하드코딩 금지.
- 측정 세트: **테스트(채택/기각) = bong1 + ytn2 + sbs1**, **held-out(일반화 검증) = ytn1 + eng1**.
- 측정 설정: 화자분할 ON (`--diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo --compression-ratio-threshold 3.0`).
- 측정 2계층: **① 스크리닝 = `--repeat 1`** (평소 기본, 방향 신호), **② 채택 확정(머지 직전) = `--repeat 3`** (median+분산, worst-case 1순위 — CLAUDE.md §4).

개선 대상 우선순위
- 1순위 — 코드스위칭 신뢰성 (적극 개선):
  · 한↔영 전환 시점 단어 유실·환각 억제 — ytn2(짧은 텀 코드스위칭) 핵심 지표
  · 언어 고착 후 환각 체인 억제 — periodic_lang_check(PLC) 기본 4.0 채택(Exp-154, base 기질) → **turbo 기질(E5)에서 재검증 후 기본 None(비활성)으로 전환(Exp-160)**: PLC=4.0이 ytn2에서 스퓨리어스 전환→환각을 유발함을 N=3로 확인
  · 디코더 파라미터 — beam=3은 Exp-162에서 N=3 재검증·기각(게이트 초과). 추가 디코더 탐색은 EXPERIMENTS.md 빠른참조 참조
  · worst-case WER 최소화 — median 개선보다 최악 케이스 스파이크 억제 우선
- 2순위 — 다화자·장시간 발화 안정성:
  · bong1 웃음 구간 환각 다발 — 비음성 구간 억제 개선
  · Sortformer 과분할 완화 — 단일화자(sbs1) 문장분리 F1 급락 원인은 Exp-155/167에서 과분할로 규명(문장분리 F1은 현행 3순위 nice-to-have)
- 관리 대상 (적극 추적 제외):
  · 반복 토큰 아티팩트("바 바 바"·"보 보 보") — Exp-002/028/057 필터로 기초 억제 완료, 추가 하드코딩보다 backend 대안 우선
  · 단어 치환 오류 (예: "육군"→"6군") — Phase 3 사전 필터로 처리 완료, 모델 한계 범주

목표 수치 (경로 C 기준 — 실제 오디오 파이프라인 신호)
- 지표 우선순위(정본 = [docs/TRANSCRIPTION_REQUIREMENTS.md](docs/TRANSCRIPTION_REQUIREMENTS.md)): ① 화자분리 F1(화자전환 경계 실현, 1순위) → ② WER → ③ 문장분리 F1(nice-to-have). 구 "문장분리 F1 단일 ≥0.7" 목표는 2지표 regime으로 대체됨
- WER: 경로 C 베이스라인 대비 개선 또는 유지 (환각 삽입·단어 누락은 WER로 검출)
  · WER이 높을 때 원인이 치환 오류("육군"→"6군")라면 Phase 2에서 직접 추적하지 않는다.
    원인이 환각 삽입·단어 누락이라면 스트리밍 단계 문제이므로 개선 대상이다.
  · 원인 구분은 전사 출력(JSON) 및 경로 B 정성 점검에서 확인한다.
  · 경로 A(`--paths A`)는 빠른 개발 체크용(코드 변경이 뭔가 망가뜨렸는지 확인)으로만 사용한다.

채택/기각 규칙 (하이브리드 루프)
- 채택 후보 조건 (모두 충족):
  ① 경로 C 화자분리 F1(정답 `[spkN]` 화자전환 경계가 전사 줄분리로 실현, 1순위)이 worst-case 미회귀 — 최우선 게이트
  ② 경로 C WER worst-case(max) 미회귀 후 median 개선 (문장분리 F1은 3순위 nice-to-have — 하락 단독은 기각 근거 아님, Case A 허용; 단 Case B 단어 중간 분절은 hard-fail). 정본 = [docs/TRANSCRIPTION_REQUIREMENTS.md](docs/TRANSCRIPTION_REQUIREMENTS.md)
  ③ pytest 유닛 테스트 전부 통과
  ④ 삽입 아티팩트가 전사 출력/경로 B 점검에서 악화되지 않음
  ⑤ held-out(ytn1+eng1) 단회 diar-ON 검증에서 catastrophic 회귀 없음 (테스트 세트 변경과 무관히 held-out은 ytn1+eng1 유지)
- 위 조건 충족 시 Claude가 근거와 함께 보고 → 사용자가 최종 채택/기각 결정
- **목표 필수 기능 예외 (자율 기각 금지 → 사용자 질의)**: 위 ①~⑤ 정량 게이트를 충족하지 못하더라도, 그 변경이 핵심 불변 제약(CLAUDE.md §3.1 폐쇄망·§3.2 한/영 두 언어 고정 등)을 달성·보전하는 데 필요한 **기반 기능**이면, "정량 개선 없음/회귀"만을 근거로 자율 기각하지 않는다. ⓐ어떤 목표·제약을 위한 것인지 ⓑ측정에서 어디가 회귀/중립인지(worst-case 포함) ⓒ대안 구현 여지를 함께 보고하고 **사용자에게 채택 여부를 묻는다**(채택 / 다른 구현 시도 / 기각은 사용자가 결정). 단 일반 점진 개선(평범한 WER 감소 등)은 해당 없음 — 불변 제약에 직접 연결되는 기능이 게이트에서 탈락하는 좁은 경우에만 발동한다. (계기: Exp-136 한/영 마스킹이 bong1 회귀로 자율 기각된 뒤 Exp-138에서 일·중 환각 재발.)

반자율 개선 루프 절차
1. 계획: EXPERIMENTS.md 직전 기록 + 현재 베이스라인 검토 후 가설 수립
2. 구현: 외과적 변경 (CLAUDE.md §2 — karpathy-guidelines 스킬 준수)
3. 테스트: `/eval` (경로 C = 1차 자동 성능 신호; 경로 A `--paths A` = 선택적 빠른 개발 체크) + pytest
4. 분석: 베이스라인 대비 F1·WER 비교, 삽입/확정 정성 확인
5. 보고: 채택/기각 판단 근거를 정리해 사용자에게 제시 → 승인 대기
6. 기록: `/log-experiment`로 EXPERIMENTS.md에 결과 기록 (실패 포함) 후 반복
   → 채택분을 master에 머지했다면 `/update-master-changes`로 docs/MASTER_CHANGES.md도 갱신


Phase 3 — 필터링 / 단어 교정 이식 ✅ 완료 (3-6 번역 Glossary는 Phase 5로 이월)
whisperlive의 환각 제거(filtering/__init__.py)·단어 대치(WordCorrectionManager, SQLite 기반 동적
추가/삭제, pytest 18케이스)를 whisperlivekit 파이프라인(filter_segments 훅)에 이식 완료. 사전 갱신은
즉시 반영됨. 세부 태스크 3-1~3-5·3-7 전부 완료, 3-6(번역 Glossary)만 Phase 5로 이월.


Phase 4 — React UI 연결 + 번역 파이프라인 통합 ✅ 완료 (2026-07-21 배포 UI 반입·통합검증, 2026-07-19 배포 PC 실반영 확인)
whisperlivekit 백엔드를 React UI(배포 UI, `frontend/app/`)와 WebSocket(`/asr`)으로 연결하고
번역(LLM) 파이프라인까지 묶어 전체 흐름을 통합했다.

스키마 방침
whisperlive 스키마({text, start, end, completed, lang, …}) 대비 whisperlivekit 출력 구조와의
불가피한 차이만 최소 변경했다(SSE+REST → WebSocket 단일 연결로 전환). 변경 이력은
[docs/SCHEMA_CHANGES.md](docs/SCHEMA_CHANGES.md)에 계약 문서로 기록·유지된다.

Phase 4 사전 준비 — 번역 모델 테스트 환경 (2026-06-21 완료)
배포(gpt-oss-20b @ llama.cpp:2010) vs 개발(qwen2.5:7b @ Ollama:11434)은 서빙 엔드포인트·포트가
다르다. 상세 설정은 [docs/DEPLOYMENT_OFFLINE.md](docs/DEPLOYMENT_OFFLINE.md) §5 참조.

태스크

 ✅ 4-1. 스키마 변경 범위 확정 [설계 세션]
→ whisperlive React API(SSE)와 whisperlivekit 출력({status, lines[], buffer_transcription, …})을
  필드별 비교, 변경 항목을 docs/SCHEMA_CHANGES.md에 정리. 호환 별칭 추가: completed←finalized,
  lang←detected_language (Segment.to_dict)
 ✅ 4-2. whisperlivekit 기반 API 서버 구현 [이식 + 신규]
→ /api/corrections, /api/save-transcript, /api/prompts 연결 완료
 ✅ 4-3. 번역 모델(OSS 20B LLM) 로컬 경로 및 파일 존재 확인
→ 배포: gpt-oss-20b @ llama.cpp:2010(기본값), 개발: qwen2.5:7b @ Ollama:11434(재정의) (docs/DEPLOYMENT_OFFLINE.md §5)
 ✅ 4-4. 번역 파이프라인 이식 [이식]
→ whisperlivekit/llm_translation/translator.py (LlamaTranslator/OllamaTranslator)
 ✅ 4-5. 번역 결과 전달 필드 구현
→ Segment.translation 필드로 전달 (to_dict 직렬화 포함)
 ✅ 4-6. 문장 확정 시점 → 번역 수행 → UI 출력 흐름 연결
→ TranslationManager: finalized 세그먼트 확정 후 비차단 async 번역 캐시 (filter_segments 직후 훅)
 ✅ 4-7. React UI에서 전사·번역 결과 최종 확인
→ 배포 UI(`frontend/app/`, `feat/deploy-ui`)가 이 저장소에 반입·통합검증 완료(2026-07-21).
  백엔드 정적 서빙 배선(`frontend/static/`, `--frontend-dir`/`--frontend-base`, SPA fallback,
  Vite `base` 자동 추출) 구현 완료. 배포 PC(`C:\whist\wlk`) 실제 반영·전사/번역/단어대치 동작
  확인 완료(2026-07-19, `wlk_in/SYNC_STATE.txt`).

완료 기준

4-1에서 확정된 스키마로 백엔드 구현 완료
whisperlive 스키마에서 변경된 사항이 docs/SCHEMA_CHANGES.md에 빠짐없이 명세화됨
확정된 문장이 번역되어 React UI에 출력됨
인터넷 차단 상태에서 전체 파이프라인 동작함
배포 PC에서 실제 React UI로 전사·번역 결과가 확인됨


Phase 5 — Glossary 동적 관리 ✅ 완료
운용 중 단어 교정 사전과 번역 Glossary를 동적으로 추가·삭제하고 즉시 반영되도록 한다.
태스크

 5-1. (Phase 3-4/3-5에서 이미 구현됨 — WordCorrectionManager 재사용, 중복 항목)
 ✅ 5-2. 번역 Glossary 동적 추가/삭제 기능 이식 [이식] (Stage 1+2 완료 — glossary_block+sentence_block+RAG)
→ whisperlive_code/prompt_manager.py 기반(TranslationPromptManager), whisperlivekit/llm_translation/에
  filtering/ 콜로케이션 패턴으로 이식. Qdrant RAG(유사 예시 검색)는 Stage 2 코드 이식 완료
  (whisperlivekit/llm_translation/rag_manager.py, 2026-07-21) — 문장 확정 시에만 주입(미확정 버퍼
  번역 제외), 자산 디렉터리 존재 시에만 배포 PC에서 활성화(개발 PC는 미적용)
  (docs/superpowers/specs/2026-07-16-translation-glossary-design.md §8, docs/DEPLOYMENT_OFFLINE.md §6.3).
 ✅ 5-3. 사전 갱신 즉시 반영 확인 (다음 전사/번역부터 새 사전 적용)
→ translator.py가 매 번역 호출마다 사전을 새로 조회 — 재시작 불필요, 즉시 반영 확인됨.

완료 기준

운용 중 사전 수정 후 다음 발화부터 즉시 반영됨(word correction·glossary 모두 확인)
Glossary 등록 단어가 번역에 반영됨


Phase 6 — 폐쇄망 배포 검증 🔄 진행 중 (반입·검증 지속, 6-7 지연시간 실측만 잔여)
개발 환경(RTX 3080)에서 검증된 코드를 폐쇄망(RTX 5090)으로 이식하고
실제 마이크 입력으로 전체 파이프라인을 최종 검증한다.
태스크

 ✅ 6-1. 폐쇄망용 모델 디렉터리 레이아웃 및 배포 패키징 형태 결정 [설계 세션]
→ docs/OPEN_QUESTIONS.md §4 해소, 정본 = docs/DEPLOYMENT_OFFLINE.md
 ✅ 6-2. uv로 오프라인 설치용 wheel 패키징
→ deploy/wheelhouse/(194개 wheel) 구성 완료
 ✅ 6-3. STT 모델(whisper-large-v3-turbo) + OSS 20B LLM 가중치 파일 이동/배포 준비
→ whisperlivekit/model/ 내 whisper-turbo·sortformer 포함, LLM은 배포 PC 사전 설치
 ✅ 6-4. HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1 등 오프라인 환경변수 설정 확인
→ docs/DEPLOYMENT_OFFLINE.md §0 표준 기동 절차로 확립
 ✅ 6-5. 폐쇄망 RTX 5090 환경으로 코드·모델 이식
→ wlk_in/SYNC_STATE.txt로 지속 반복 수행 중(최신 동기화 커밋 e5461a9, 2026-07-29). `/deploy-sync`
  슬래시 커맨드로 master 변경사항을 wlk_in에 동기화 후 사용자가 배포 PC(C:\whist\wlk)에 반영.
 ✅ 6-6. 실제 마이크 입력으로 한·영 전사 및 번역 동작 확인
→ 배포 PC 실사용 확인(2026-07-19, wlk_in/SYNC_STATE.txt: 렌더·전사·번역·단어대치 동작 확인됨).
  실사용 피드백 기반 버그 수정 사례도 존재(Exp-193, RTX 5090 코드스위칭 이슈).
 ⏳ 6-7. 성능 확인 (지연 시간 측정 — 목표 수치는 실측 후 결정)
→ 현재 RTX 3080(개발)에서만 측정됨(sbs1 실시간 lag 최대 41s) — RTX 5090(배포) 재측정 필요.

완료 기준

폐쇄망에서 외부 연결 없이 전체 시스템 동작 — 6-1~6-6 충족, `/deploy-sync` 워크플로로 지속 검증 중
실제 마이크 입력으로 한·영 전사·번역이 정상 동작 — 배포 PC 실사용으로 확인됨
지연 시간 측정 결과 기록 — RTX 5090 실측(6-7)만 남은 유일한 항목


추후 결정 항목 (현재 비활성)

디버깅용 로그 파일 저장
hotwords / initial_prompt 주입 기능
