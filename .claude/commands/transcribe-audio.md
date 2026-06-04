# /transcribe-audio — 음성 파일 정답 전사 워크플로

새 음성 파일을 정답(ground truth) 텍스트로 변환하는 3단계 워크플로:
① 자동 전사 → ② 사람 검토 → ③ Claude 문맥 검증

## 사용법

```
/transcribe-audio test_data/foo.mp3
```

`$ARGUMENTS` = 음성 파일 경로 (예: `test_data/ytn1.mp3`)

---

## Claude가 따를 순서

### Step 1 — 자동 전사 실행

```powershell
$env:PYTHONIOENCODING = "utf-8"
uv run --no-sync python scripts/transcribe_groundtruth.py $ARGUMENTS
```

- 완료 후 생성된 `.txt` 파일 내용을 전체 출력한다.
- 출력 형식: 문장당 한 줄, 문장 사이 빈 줄 (sbs1.txt 형식과 동일).

### Step 2 — 사람 검토 요청

스크립트 실행 후 다음 메시지를 출력하고 **반드시 멈춘다**:

> 전사 결과를 확인해주세요.
> 음성을 직접 들으면서 `[출력된 txt 경로]` 파일을 수정하세요.
> - 잘못 전사된 단어 수정
> - 문장 경계 조정 (필요 시 줄 추가/삭제)
> - 불필요한 줄 삭제
>
> **수정이 완료되면 "검토 완료"라고 알려주세요.**

### Step 3 — 문맥 기반 검증

사용자가 "검토 완료"라고 하면:

1. 수정된 `.txt` 파일을 읽는다.
2. 아래 항목을 점검하고 의심되는 부분을 표로 정리해 보고한다:

| 항목 | 설명 |
|------|------|
| 동음이의어·맞춤법 | 문맥상 어색한 단어 (예: 철턴→철통, 초토→초토화) |
| 고유명사 | 인명·지명·기관명의 오기 (예: Rock Alliance→ROK Alliance) |
| 한·영 혼용 오류 | 영어를 한국어로 잘못 전사하거나 반대인 경우 |
| 문장 완결성 | 문장이 잘리거나 이어져야 할 내용이 분리된 경우 |
| 반복·환각 | whisper 특유의 반복 구절이나 관계없는 내용 삽입 |

3. 수정 제안은 **원문 → 제안** 형식으로 라인 번호와 함께 제시한다.
4. 사용자가 확인·반영하면 최종 파일을 저장한다.

---

## 참고

- 모델 경로: `whisperlivekit/model/whisper-large-v3-turbo/`
- VAD 병합 간격(MERGE_GAP_S), 최대 청크(MAX_CHUNK_S) 등은
  `scripts/transcribe_groundtruth.py` 상단 상수에서 조정 가능
- 전사 품질이 낮으면 재실행 전 해당 상수를 조정한 뒤 다시 시도
