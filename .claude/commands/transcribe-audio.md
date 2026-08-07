# /transcribe-audio — 음성 파일 정답 전사 워크플로

새 음성 파일을 정답(ground truth) 텍스트로 변환하는 3단계 워크플로:
① (YouTube면 구간 다운로드) → ② 자동 전사 → ③ 사람 검토 → ④ Claude 문맥 검증

## 사용법

```
# 로컬 파일
/transcribe-audio test_data/foo.mp3

# YouTube URL + 시간 구간
/transcribe-audio https://youtu.be/XXXXX 1:30 5:00
/transcribe-audio https://www.youtube.com/watch?v=XXXXX 00:01:30 00:05:00
```

`$ARGUMENTS` 구조: `<파일경로_또는_YouTube_URL> [시작시간] [종료시간]`  
시간 포맷: `HH:MM:SS` 또는 `MM:SS`

---

## Claude가 따를 순서

### Step 0 — 입력 분기 판단

`$ARGUMENTS`의 첫 번째 토큰이 `https://` 또는 `youtu.be`로 시작하면 **YouTube 다운로드 분기**로, 그 외에는 **로컬 파일 분기**로 진행한다.

#### 로컬 파일 분기
`AUDIO_PATH = $ARGUMENTS` (첫 번째 토큰) 로 설정하고 Step 1로 바로 이동.

#### YouTube 다운로드 분기

인자를 파싱한다:
- `URL` = 첫 번째 토큰
- `START` = 두 번째 토큰
- `END` = 세 번째 토큰

`START` 또는 `END`가 없으면 아래를 출력하고 **중단**한다:

> **오류**: YouTube URL은 시작·종료 시간이 필요합니다.
> 사용법: `/transcribe-audio <youtube_url> <시작시간> <종료시간>`
> 예시: `/transcribe-audio https://youtu.be/XXXXX 1:30 5:00`

**1. yt-dlp 설치 확인**

```powershell
yt-dlp --version
```

실패하면 아래를 출력하고 **중단**한다:

> **오류**: yt-dlp 가 설치되어 있지 않습니다.
> 다음 명령으로 설치 후 재실행하세요:
> ```
> uv tool install yt-dlp
> ```

**2. 구간 다운로드**

```powershell
$env:PYTHONIOENCODING = "utf-8"
yt-dlp --download-sections "*{START}-{END}" -x --audio-format wav -o "test_data/yt_%(id)s.%(ext)s" {URL}
```

- `--download-sections "*START-END"` : 지정 구간만 다운로드 (전체 영상 다운로드 없음)
- `-x --audio-format wav` : 오디오 추출 후 WAV 변환
- 출력 파일: `test_data/yt_<video_id>.wav`

다운로드 완료 후 생성된 파일 경로를 확인해 `AUDIO_PATH`로 설정한다.  
다운로드 실패 시(비공개·지역 제한 등) yt-dlp 오류를 그대로 출력하고 **중단**한다.

---

### Step 1 — 자동 전사 실행

```powershell
$env:PYTHONIOENCODING = "utf-8"
.venv\Scripts\python.exe scripts/transcribe_groundtruth.py {AUDIO_PATH}
```

- 완료 후 생성된 `.txt` 파일 내용을 전체 출력한다.
- 스크립트는 화자 라벨 없이 **빈 줄 = 문장 경계**만으로 초안을 생성한다(화자분리 정보 없음). Step 2에서
  사람이 `[spkN]` 헤더(화자전환 경계, canonical 정답 형식)를 직접 추가해야 한다 — 정답 형식 정본 =
  [docs/TRANSCRIPTION_REQUIREMENTS.md](../../docs/TRANSCRIPTION_REQUIREMENTS.md) §2.

### Step 2 — 사람 검토 요청

스크립트 실행 후 다음 메시지를 출력하고 **반드시 멈춘다**:

> 전사 결과를 확인해주세요.
> 음성을 직접 들으면서 `[출력된 txt 경로]` 파일을 수정하세요.
> - 잘못 전사된 단어 수정
> - **화자가 바뀌는 지점마다 `[spkN]` 헤더 추가**(canonical 정답 형식 — TRANSCRIPTION_REQUIREMENTS.md §2)
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
- YouTube 다운로드 파일은 `test_data/yt_<video_id>.wav` 형태로 저장됨
