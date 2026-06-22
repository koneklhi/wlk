# 화자 분할(Speaker Diarization) Feasibility 스파이크 결과

- **날짜**: 2026-06-19
- **브랜치/워크트리**: `phase4/diarization-spike` (`worktrees/diarization-spike`)
- **성격**: 채택/기각 실험이 아닌 **feasibility 스파이크** (정성 평가). PHASE2_EXPERIMENTS.md 대상 아님.

## 1. 배경 / 동기

상용 환경은 **한국인 발화 → 외국인이 통역**하는 구조가 잦다(= 화자 전환이 곧 언어 전환).
사용자 요구: (1) 화자 분할이 쓸 만한지 탐색, 잘 되면 (2) `speaker1/speaker2` 출력,
(3) **화자가 바뀌는 순간 무조건 새 문장**으로 시작. (3)은 현재 핵심 난제인
code-switching 언어 고착(Exp-092/093)과 직결된다.

## 2. 탐색으로 확정한 현재 코드 상태

whisperlivekit은 화자 분할 인프라를 **코드로 완비**했으나 4가지가 비어 있다:

| 레벨 | 현황 | 위치 |
|---|---|---|
| 출력 분리(speaker별 라인) | `--diarization`만 켜면 동작 — 화자 다르면 라인 미병합 | `tokens_alignment.py:184` get_lines_diarization |
| 메시지 스키마 | `speaker` 필드 이미 존재 → **React 변경 불필요** | `timed_objects.py:161` Segment.to_dict |
| 디코더 분리(화자전환→새문장) | 뼈대(`new_speaker()`→`refresh_segment`)는 있으나 **트리거(`ChangeSpeaker` enqueue) 미연결 = 죽은 경로** | `backend.py:111` / `audio_processor.py:360` |
| 폐쇄망 오프라인 적재 | `from_pretrained()` HF 다운로드, 로컬 경로 미지원 | `sortformer_backend.py:59`, `diart_backend.py:166` |

## 3. 환경 / 방법

- 개발 PC, RTX 3080, `torch 2.8.0+cu128`, Python 3.12
- 경로 A(`test_client` PCM 주입), `--speed 1.0`(실시간 재생 — Sortformer는 실시간 청크 가정)
- 데이터: **ytn1**(83s, EN↔KO 순차통역 2화자), **ytn2**(109s, held-out, EN→KO)

## 4. Sortformer 결과 ✅ (완전 동작)

- **설치**: `uv pip install nemo_toolkit[asr]` — 한 번에 성공(`nemo-toolkit 2.7.3`). 부수효과로
  `huggingface-hub 1.4.1→0.36.2`, `transformers→4.57.6` 다운그레이드됐으나 whisperlivekit STT import 무결성 검증 통과.
- **모델**: `nvidia/diar_streaming_sortformer_4spk-v2` — **비-gated**, 19s 로딩,
  **471MB 단일 `.nemo`** 로 로컬 저장 성공 → **폐쇄망 오프라인 적재 feasible**(`restore_from(로컬경로)`).
- **구동**: `--diarization --diarization-backend sortformer` 한 번에 성공(whisper turbo + Sortformer 동시 로딩).
- **ytn1 정성**(8개 화자 교대 경계 중 7 정확 ≈ **88%**):

| 정답 구간 | Sortformer 화자 | 정확 |
|---|---|---|
| 안녕하십니까…(한국어 통역) | Speaker 2 | ✅ |
| I want to first thank…(영어) | Speaker 3 | ✅ |
| 우선 오늘 안보협의…+This was our 51st… | Speaker 3 (한+영 병합) | ❌ |
| 이번 안보협의회는…(한국어) | Speaker 2 | ✅ |
| The United States remains…(영어) | Speaker 3 | ✅ |
| 미국은 대한민국…(한국어) | Speaker 2 | ✅ |
| The U.S. ROK alliance…(영어) | Speaker 3 | ✅ |
| 한미동맹은…/한반도…(한국어) | Speaker 2 | ✅ |

  한국어 통역=Speaker 2, 영어 원발화=Speaker 3로 **일관** 분리. 화자 바뀌면 라인 분리되어
  `Speaker N` 라벨이 React에 그대로 출력 가능. 실시간성 양호(전사 밀림 없음).

- **ytn2**: 한국어 통역 구간이 `(speaking in foreign language/Chinese/Japanese…)` 메타태그로 **환각 폭주** →
  텍스트가 무너져 화자-텍스트 정렬 평가가 가려짐. **이건 diarization 결함이 아니라 기존 언어 고착(STT) 문제.**
  오히려 화자 전환을 디코더에 신호로 주면(다음 세션) 이 환각을 끊을 잠재력을 보여줌.

## 5. Diart 결과 ⚠️ (의존성 지옥, 구동 실패)

`uv pip install diart` 자체는 성공(`diart 0.9.2`, `pyannote-audio 3.4.0`)하나, **NeMo 공존 환경에서 충돌 연쇄**:

1. **matplotlib 충돌**: NeMo가 설치한 matplotlib 3.11 ↔ pyannote가 쓰는 `matplotlib.cm.get_cmap`(3.9에서 제거) → `matplotlib<3.9` 다운그레이드 필요.
2. **core.py 키워드 버그**: `DiartDiarization(segmentation_model=…)` 호출 vs `__init__(segmentation_model_name=…)` 정의 → `TypeError` (**whisperlivekit 본체 버그** — Diart가 미검증 상태).
3. **torch weights_only**: torch 2.6+ `weights_only=True` 기본 ↔ pyannote 체크포인트(`TorchVersion` 글로벌) → `TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1` 필요.
4. **speechbrain k2**: `pytorch_lightning`(NeMo가 설치한 2.6.5)이 체크포인트 로딩 중 `inspect.stack()` 호출 → speechbrain `k2_fsa` LazyModule 강제 materialize → `k2`(Windows 빌드 난해) 미설치로 **구동 실패**.

- **모델**: `pyannote/segmentation-3.0` + `pyannote/embedding` — **gated**(HF 약관 동의 필요). HF 토큰으로 다운로드 자체는 성공.
- **폐쇄망 부적합**: gated 모델 + segmentation/embedding **2개 모델** + speechbrain/k2 무거운 의존성.

## 6. 비교표

| 항목 | Sortformer | Diart |
|---|---|---|
| 설치 | 한 번에 성공 | 충돌 4건 누적 |
| 모델 | 단일 `.nemo` 471MB, **비-gated** | seg+emb 2개, **gated** |
| 폐쇄망 적재 | 깔끔(`restore_from` 로컬) | 험난(gated+다중+k2) |
| 구동 | **성공** | **실패**(k2 미설치) |
| 화자 분리 품질 | ytn1 ≈88% | 미측정(구동 실패) |
| 실시간성 | OK(RTX 3080) | 미측정 |

## 7. 결론

- **Sortformer 채택 권고.** 화자 분할 feasibility 입증: ytn1 한↔영 순차통역 화자를 ~88% 깔끔히 분리,
  실시간성 양호, **폐쇄망 단일 `.nemo` 오프라인 적재 가능**. 사용자 요구(화자별 라인·라벨)가 출력 레벨에서 즉시 동작.
- **Diart 기각.** NeMo 공존 의존성 지옥 + 폐쇄망 부적합(gated·다중모델·k2).
- **whisperlivekit 본체 버그 발견**: `core.py` diart 분기 키워드 불일치(`segmentation_model` vs `segmentation_model_name`).
  Diart 미채택이므로 본 스파이크에서는 **수정 미적용**(워크트리 변경 되돌림). Diart를 쓸 일이 생기면 그때 수정.

## 8. 디코더 연결 구현 (2026-06-19, phase4/diarization-spike 브랜치)

스파이크 직후 같은 세션에서 구현 완료.

1. ✅ **죽은 경로 활성화**: `_update_diarization_state`에서 화자 변화 감지 → `transcription_queue.put(ChangeSpeaker)` (audio_processor.py:431-439). 첫 화자는 신호 미전송(불필요한 reset 방지).
2. ✅ **언어 재감지 시너지**: `new_speaker()`에 `detected_language=None`, `first_timestamp=None` 추가 (simul_whisper/backend.py:115-116). Exp-093 long_silence 리셋과 동일 패턴.
3. ✅ **폐쇄망 적재**: `_load_model()`에 `os.path.isfile()` 분기 추가 (sortformer_backend.py:60-63). `--sortformer-model` CLI 플래그 신규 추가 (parse_args.py / config.py / core.py).
4. ✅ **eval 지원**: `scripts/eval.py`에 `--diarization`, `--sortformer-model` 플래그 추가 (start_server 연동).
5. ✅ **smoke test**: 로컬 .nemo 경로로 서버 기동 성공, ytn1 화자 라벨 출력 확인 (Speaker 2=KO, Speaker 3=EN).

**남은 작업 (다음 세션):**
- **경로 C N=3 정량 측정**: VBCable 환경에서 직접 실행 필요.
  ```
  python scripts/eval.py --model-dir whisperlivekit/model/whisper-large-v3-turbo \
    --diarization --sortformer-model whisperlivekit/model/sortformer-4spk-v2.nemo \
    --repeat 3
  ```
- WER/F1이 개선되면 PHASE2_EXPERIMENTS.md에 채택 실험으로 기록.
- LocalAgreement 백엔드(`OnlineASRProcessor.new_speaker()`)의 언어 재감지 리셋 여부 추가 검토.

## 9. 환경 잔존물 (정리는 선택)

- 설치됨: `nemo-toolkit 2.7.3`(Sortformer 필수), `diart 0.9.2`/`pyannote-audio 3.4.0`/`speechbrain`(Diart, 미사용),
  `matplotlib 3.8.4`(Diart 위해 다운그레이드). Sortformer 경로엔 무해(import 안 함).
- 로컬 모델: `whisperlivekit/model/sortformer-4spk-v2.nemo`(471MB, 폐쇄망 적재용).
