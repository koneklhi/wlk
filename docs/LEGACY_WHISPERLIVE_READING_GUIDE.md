# 레거시 whisperlive 코드 읽기 가이드

[whisperlive_code/](../whisperlive_code/)를 **어떤 순서로, 어디에 초점을 맞춰** 읽을지 안내하는 문서다.
인수인계 대상자가 코드 분석에 들어가기 **전에** 읽는 것을 전제로 한다.

이 디렉터리의 존재 목적은 하나다 — **기존 시스템이 어떤 로직으로 구성되어 있었는지 읽는 것.**
성능·기법 비교용 참고 자료이며 **코드·임시방편 로직을 그대로 이식하지 않는다**([CLAUDE.md](../CLAUDE.md) §1).

> **읽기 전 3줄 요약**
> 1. 서버가 **미확정 구간 전체를 매 루프마다 다시 디코딩**한다 — 이 시스템의 거의 모든 로직이 여기서 파생된다.
> 2. "확정"이란 곧 **커밋 포인터(`timestamp_offset`)를 전진시켜 그 앞을 재디코딩 대상에서 빼는 일**이다.
> 3. 그래서 확정 판정 4갈래, 클라이언트 중복 제거, 문장 묶기가 **각각 따로가 아니라 하나의 구조에서 나온 대응**이다.

---

## 0. 먼저 알아야 할 것 — 이 디렉터리의 정체

### 0.1 실행 대상이 아니라 로직 참조용 사본이다

`whisperlive_code/`는 **패키지가 아니다.** 원본 `realtime_asr` 프로젝트에서 *우리 요구사항에 맞게 수정했던 파일만* 골라내
디렉터리 구조를 파일명에 평탄화(`filtering/__init__.py` → `filtering____init__.py`)해 복사한 스냅샷이다.
모든 파일이 `realtime_asr.*`를 import하지만 그 모듈들은 여기 없다.

**실제 레거시 시스템은 배포 PC에서 정상 동작 중이다.** 이 사본에 보이는 오타·미정의 참조·설정 파일 포맷 문제는
개발 PC로 옮기는 과정의 사본화 아티팩트(또는 구버전 혼입)다. **실행을 시도하지 말고 로직만 읽는다.**
코드가 모호해 판단이 필요하면 최종 근거는 **배포 PC의 `src/realtime_asr/` 원본**이다.

### 0.2 평탄화된 파일명 → 원본 경로

| 이 디렉터리의 파일 | 원본 경로 | 줄 수 |
|---|---|---|
| `main.py` | `src/realtime_asr/main.py` | 203 |
| `app.py` | `src/realtime_asr/app.py` | 247 |
| `server.py` | `src/realtime_asr/WhisperLive/server.py` | 1,008 |
| `client.py` | `src/realtime_asr/WhisperLive/client.py` | 895 |
| `transcriber.py` | `src/realtime_asr/WhisperLive/transcriber.py` (faster-whisper 포크) | 1,956 |
| `translator.py` | `src/realtime_asr/translator.py` | 201 |
| `filtering____init__.py` | `src/realtime_asr/filtering/__init__.py` | 91 |
| `manager.py` | `src/realtime_asr/filtering/manager.py` | 104 |
| `prompt_manager.py` | `src/realtime_asr/filtering/prompt_manager.py` | 183 |
| `whisper_1023.txt` | `configs/whisper_1023.yaml` (기본 설정) | 29 |

합계 4,917줄. 단 **실제로 정독할 분량은 1,500줄 남짓**이다(§0.4).

### 0.3 여기 없는 모듈 (import를 따라가려 할 때)

- `realtime_asr/config.py` — `SETTINGS`(전역 설정 dict), `PROJECT_ROOT`, `DIST_PATH`, `init_settings()`
- `WhisperLive/utils.py` — `print_segment()`(서버 응답 → `(start, end, text)` 튜플 변환), `clear_screen()`
- `WhisperLive/dataclass.py` — UI 레벨 `Segment`(`spk`·`content`·`completed`·`forced`). `spk`는 Enum이다([app.py:77](../whisperlive_code/app.py) `spk.value`)
- `OllamaTranslator`, `ModelInfo`, `configs/*.json`(사전·용어집·환각 목록), React 프론트엔드 일체

`SETTINGS`가 안 보여도 당황할 필요 없다 — 값은 전부 [whisper_1023.txt](../whisperlive_code/whisper_1023.txt)에 있고,
어떤 키가 어디서 읽히는지는 §5.3 표에 정리해 뒀다.

### 0.4 읽지 않아도 되는 것

- **`transcriber.py` 1,956줄 중 통독 대상은 3곳뿐이다.** 나머지는 faster-whisper 원본과 같다 (§4.2)
- **`BatchedInferencePipeline`**(`transcriber.py:113-551`) — 서버 경로가 쓰지 않는다
- 이 사본 범위에서 호출부가 보이지 않는 함수: `server.py:859` `filtering_segments_by_prob`, `server.py:427` `clip_audio_if_no_valid_segment`.
  사본 범위 밖일 수 있으니 로직 이해에 비중을 두지 않는다

---

## 1. 전체 그림 — 3프로세스 구조

[main.py:151-194](../whisperlive_code/main.py) `entry_point()`가 spawn 컨텍스트로 프로세스 3개를 띄우고 `Event`/`Queue`로 잇는다.

```
 [마이크]
    │ PyAudio (16kHz / int16 / mono)
    ▼
┌─────────────────┐   WebSocket        ┌──────────────────┐
│ client 프로세스  │ ──binary float32──▶│  ASR 서버 프로세스 │
│                 │                    │                  │
│ · 마이크 캡처    │◀──JSON segments────│ · 오디오 버퍼링   │
│ · 중복 제거      │                    │ · 재디코딩 루프   │
│ · 환각 필터      │                    │ · 확정 판정      │
│ · 문장 묶기      │                    └──────────────────┘
└────────┬────────┘
         │ mp.Queue(3)
         ▼
┌─────────────────┐    SSE      ┌──────────┐
│  API 프로세스    │ ──────────▶ │ React UI │
│  FastAPI :8000  │             └────┬─────┘
└────────┬────────┘                  │ POST /api/translate
         │                           │ (프론트가 줄 단위로 호출)
         ▼                           │
   vLLM :2010 ◀──────────────────────┘
```

| 프로세스 | 진입 함수 | 하는 일 |
|---|---|---|
| 오디오 수신 | `main.py:80` `audio_receiver` | 마이크 캡처 → 서버 전송 → 결과 후처리 |
| ASR 서버 | `main.py:56` `asr_process` | `TranscriptionServer.run()`, 포트는 설정값 |
| API | `main.py:130` `run_api` | uvicorn `0.0.0.0:8000`, SSE + REST |

**공유 IPC** (`main.py:168-172`) — 프로세스 간 상태는 전부 이 4개로만 오간다:

| 객체 | 역할 |
|---|---|
| `recording_event` | 녹음 on/off. 클라이언트 전송 게이트([client.py:506-517](../whisperlive_code/client.py))이자 SSE 종료 조건 |
| `reset` | 클라이언트 상태 초기화 |
| `db_reset` | 사전 갱신 신호. REST에서 set → 클라이언트가 다음 루프에 사전 재로드 |
| `transcript_list` | `Queue(3)`. 전사 결과가 client → API로 흐르는 유일한 통로 |

**CLI 인자는 `-c/--config` 하나뿐**(`main.py:157-166`). 나머지는 설정파일 + 하드코딩이다.

> **현행과의 최대 구조 차이**
> 레거시는 **마이크가 서버 옆 프로세스**에 있고 브라우저는 텍스트만 SSE로 받는다.
> 현행 whisperlivekit은 **브라우저가 오디오를 WebSocket으로 올린다**. 입력 주체가 반대편으로 옮겨갔다.

---

## 2. 읽는 순서 (권장 6단계)

| # | 파일 | 범위 | 이 단계에서 잡을 것 |
|---|---|---|---|
| 1 | `main.py` | 151-204, 56-141 | 프로세스 3개와 IPC 배선. §1의 그림을 코드로 확인 |
| 2 | `client.py` | 551-607, 692-756 | 마이크 → float32 → 소켓. 가장 단순한 구간이라 몸풀기용 |
| 3 | `server.py` | 187-206, 395-456, 820-846 | **버퍼링과 재디코딩 루프 ← 이 시스템의 핵심 구조** |
| 4 | `transcriber.py` | 682-725, 997-1012, 1826-1839 | 튜닝된 디코더 파라미터 + 프로젝트 커스텀 3곳 |
| 5 | `server.py` | **893-1008** | **확정 판정 4갈래 — 가장 중요한 함수** |
| 6 | `client.py` 199-386 → `filtering____init__.py` → `app.py` → `translator.py` | | 중복 제거 → 문장 묶기 → 필터 → SSE → 번역 |

**3번을 건너뛰지 말 것.** 3번을 이해하지 못하면 5번과 6번이 "왜 이런 임시방편이 세 군데나 있지?"로만 보인다.

---

## 3. 음성 입력 → 버퍼 → 재디코딩 (핵심 구조)

### 3.1 캡처와 전송 — 클라이언트

| 단계 | 위치 | 내용 |
|---|---|---|
| PyAudio 스트림 | [client.py:583-607](../whisperlive_code/client.py) | `paInt16` / mono / **16kHz** / `frames_per_buffer=8192` (상수 `:569-573`) |
| 읽기 루프 | `client.py:715-742` | `stream.read(chunk, exception_on_overflow=False)` |
| 변환 | `client.py:811-825` | int16 → `astype(float32) / 32768.0` |
| 전송 | `client.py:506-517` | `ABNF.OPCODE_BINARY`, `recording_event` 게이트 |

**리샘플링이 없다.** 마이크를 16kHz로 직접 열고, 장치가 못 하면 `self.stream = None`으로 두고 끝난다(`client.py:605-607`).
서버의 `RATE`도 16000 고정(`server.py:150`, `:340`)이라 전 구간이 16kHz 단일 가정 위에 있다.

### 3.2 서버 수신과 버퍼

[server.py:187-206](../whisperlive_code/server.py) `get_audio_from_websocket()`이 3종을 구분한다:

- `b"END_OF_AUDIO"` → `False` 반환 → 연결 종료
- `"reset"` → `client.data_reset()`(`:380-393`)로 상태 초기화
- 그 외 → `np.frombuffer(frame_data, dtype=np.float32)`

버퍼는 [server.py:395-425](../whisperlive_code/server.py) `add_frames()`에서 **하나의 성장하는 `frames_np` 배열**로 관리한다.
45초를 넘으면 앞부분을 잘라내고 `frames_offset`을 전진시킨다(`:412-415`).

### 3.3 ★ 슬라이딩 재디코딩 — 이 절의 결론

```python
# server.py:452-456
samples_take = max(0, (self.timestamp_offset - self.frames_offset) * self.RATE)
input_bytes = self.frames_np[int(samples_take):].copy()
duration = input_bytes.shape[0] / self.RATE
```

`timestamp_offset`부터 버퍼 끝까지 — 즉 **아직 확정되지 않은 구간 전체**를 잘라
[server.py:820-846](../whisperlive_code/server.py) `speech_to_text()` 루프가 **매 회차 통째로 다시 디코딩**한다.
(최소 1.0초 게이트 `:830-832`, 결과가 비면 offset만 전진시키고 넘어감 `:836-839`.)

**따라서 이 시스템에서 "확정"은 텍스트를 잠그는 일이 아니라 `timestamp_offset`을 전진시켜
그 앞 구간을 재디코딩 대상에서 빼는 일이다.** 확정이 안 되면 같은 오디오가 계속 다시 디코딩되고,
매번 조금씩 다른 결과가 나온다. 여기서 세 가지 귀결이 나온다:

| 귀결 | 대응 로직 | 위치 |
|---|---|---|
| 확정 신호를 스스로 만들어야 함 | 확정 판정 4갈래 | §5 |
| 새 결과가 직전 결과의 꼬리를 반복함 | 클라이언트 중복 제거 | §6.1 |
| 디코더가 같은 자리를 맴돌 수 있음 | 타임스탬프 정체 감지 | §4.2, §5.1 |

### 3.4 VAD는 서버가 아니라 디코더 안에 있다

Silero VAD는 `transcriber.py` 내부에서 돈다 — import `:28-33`, 적용 `:816-848`, 기본값 `vad_filter=True`(`:717`),
잘라낸 뒤 타임스탬프 복원 `restore_speech_timestamps`(`:1859`). 설정 `transcribe:` 블록으로 `vad_parameters` 조정 가능.

---

## 4. 전사 경로

### 4.1 모델 호출과 언어 래치

모델 생성은 `server.py:673-685`, 클라이언트 간 단일 모델 공유는 `SINGLE_MODEL` 클래스 속성 + Lock(`:549-550`, `:741-756`).

```python
# server.py:746-753
segment_generator, info = self.transcriber.transcribe(
    input_sample,
    initial_prompt=self.initial_prompt,                                  # :744에서 None 강제
    language=self.language if self.cnt >= self.language_cnt_threshold else None,
    task=self.task,
    hotwords=self.hotwords,
    **SETTINGS["transcribe"],
)
```

**언어 래치**(`server.py:766-777`)가 이 시스템의 코드스위칭 대응 전부다:

- `info.language ∈ {en, ko}` **그리고** `language_probability > 0.9`일 때만 카운터 증가
- 직전과 다른 언어가 나오면 카운터를 1로 리셋(`:770-771`)
- `language_cnt_threshold`(3)회 연속 같은 언어여야 `language=`를 넘김. 그 전까지는 **매번 재감지**
- **확정이 일어날 때마다 `self.language = None; self.cnt = 0`**(`:929`, `:973`, `:998`) → **발화 단위 래치**

즉 레거시의 코드스위칭 전략은 "확신이 설 때까지 언어를 고정하지 않고, 문장이 끝나면 다시 푼다"는 **수동적·보수적 방식**이다.

### 4.2 `transcriber.py` 커스텀 3곳 (여기만 보면 됨)

`transcribe()` 정의부에 `# 여기에서 whisper param 수정!!!!!!@@!!!`(`:682`) 주석이 붙어 있다. 원본 대비 실질 변경은 셋이다.

**① `Segment`에 강제완료 플래그 추가** — `transcriber.py:51-72`
`timestamp_forced_completion: Optional[bool]` 필드가 추가됐다. 생산은 ②, 소비는 서버(§5).

**② last-timestamp 회전큐 — 디코더 정체 감지** — `transcriber.py:649-654` + `:997-1012`

```python
# :649-654  (하드코딩)
self.last_timestamp_rotation_queue_length = 4
self.last_timestamp_rotation_queue = [-1] * 4
self.last_timestamp_diff_threshold = 0.1

# :1010-1012
if -1 not in self.last_timestamp_rotation_queue:
    if max(queue) - min(queue) < self.last_timestamp_diff_threshold:
        timestamp_forced_completion = True
```

디코딩 결과의 마지막 타임스탬프 토큰을 4칸 회전큐에 넣고, **4회 연속 max−min이 0.1초 미만이면
디코더가 같은 자리를 맴도는 것으로 보고 강제 분할 신호를 세운다.**

**③ 언어 감지를 ko/en으로 제한** — `transcriber.py:1826-1839`
`detect_language`의 전체 언어 확률에서 `target_langs`(설정 `["ko","en"]`)만 남기고 최댓값을 취한다.
그중 1등조차 확률 0.1 미만이면 0으로 만든다(잡음 구간에서 억지 판정 방지).

### 4.3 튜닝된 디코딩 기본값 — `transcriber.py:688-725`

| 파라미터 | 값 | 비고 |
|---|---|---|
| `beam_size` / `best_of` | 7 / 7 | 원본 5에서 상향 |
| `repetition_penalty` | 1.3 | 설정파일이 덮어씀 |
| `no_repeat_ngram_size` | 2 | |
| `temperature` | `[0.0, 0.2, 0.3, 0.4, 0.5]` | **fallback 사다리** |
| `compression_ratio_threshold` | 2.2 | |
| `log_prob_threshold` | -1.0 | **미달 시 온도를 올려 재시도**(폐기가 아님) |
| `no_speech_threshold` | 0.9 | 주석에 `0.75 -> 0.9` |
| `condition_on_previous_text` | `False` | 이전 문맥 미사용 |
| `word_timestamps` | `True` | cross-attention DTW |
| `language_detection_threshold` | 0.7 | |

> **현행과 대조할 때 눈여겨볼 지점**: 레거시는 품질 게이트에 걸린 결과를 **버리지 않고 온도를 올려 다시 뽑는다.**
> 이 차이가 전사 누락 양상에 직결된다.

---

## 5. ★ 확정(commit) 로직 — 가장 중요한 절

[server.py:893-1008](../whisperlive_code/server.py) `update_segments()` 한 함수 안에 4갈래가 순서대로 들어 있다.
이 함수만 제대로 읽으면 레거시 전사 동작의 8할이 설명된다.

### 5.1 4갈래

| 갈래 | 줄 | 조건 | 결과 |
|---|---|---|---|
| **A1** 자연 확정 | 910-930 | Whisper가 세그먼트를 **2개 이상** 내면 마지막 제외 전부 | `completed=True` |
| **A2** 미확정 꼬리 | 931-940 | 마지막 세그먼트는 **항상 잠정** | `completed=False` (transcript에 넣지 않고 `last_segment`로만 전송) |
| **A3** **N회 반복 확정** | 941-978 | 같은 출력이 `same_output_threshold`(**10**)회 초과 반복 | `completed=False, forced=True` |
| **A4** **타임스탬프 정체 확정** | 979-1003 | §4.2 ②의 `timestamp_forced_completion` 플래그 | `completed=True, forced=True` |

**A1의 논리**: Whisper가 세그먼트를 여러 개 냈다는 건 앞쪽 세그먼트들의 경계가 확정됐다는 뜻이다. 그래서 마지막만 남기고 커밋한다.

**A3/A4는 `elif`다 — A3가 우선**(`:979`).

### 5.2 A3·A4를 읽을 때 놓치기 쉬운 것

**A3 — 왜 첫 반복 시점으로만 offset을 전진시키나**

```python
# server.py:944-947 (주석 원문)
# if we remove the audio because of same output on the nth reptition we might remove the
# audio thats not yet transcribed so, capturing the time when it was repeated for the first time
if self.end_time_for_same_output is None:
    self.end_time_for_same_output = segments[-1].end
```

10회를 기다리는 동안 뒤쪽에 새 발화가 쌓인다. 10번째 시점의 end로 커밋하면 **아직 전사되지 않은 오디오까지 버린다.**
그래서 *첫 반복 시점*의 end를 기억해 두고 거기까지만 전진시킨다(`:976`).

**A4 — 플래그는 여기서 만들어지지 않는다**

`update_segments()`는 `segments[-1].timestamp_forced_completion`을 **읽기만** 한다.
생산지는 `transcriber.py:997-1012`(§4.2 ②)다. 두 파일을 오가며 읽어야 이해된다.

**공통 — 확정은 언어 래치를 푼다**

A1·A3·A4 모두 커밋 직후 `self.language = None; self.cnt = 0`을 실행한다(`:928-929`, `:972-973`, `:997-998`).
§4.1의 "발화 단위 래치"가 여기서 닫힌다.

> **A3와 A4가 바로 [CLAUDE.md](../CLAUDE.md) §1이 "이식하지 말라"고 명시한 임시방편 로직이다**
> ("같은 문장 N회 반복 시 확정", "타임스탬프 변화량 임계치"). 현행이 왜 이걸 안 썼는지는 §7 참조.

### 5.3 임계값이 어디서 오는가

**설정파일** [whisper_1023.txt](../whisperlive_code/whisper_1023.txt):

| 키 | 값 | 읽는 곳 | 쓰는 곳 |
|---|---|---|---|
| `no_speech_thresh` | 0.7 | `server.py:600` | `:910`, `:921`, `:931` |
| `same_output_threshold` | 10 | `server.py:602` | `:955` (A3) |
| `language_cnt_threshold` | 3 | `server.py:603` | `:749`, `:766` |
| `target_langs` | `["ko","en"]` | `create_model` | `transcriber.py:1826` |
| `repetition:` 블록 | head 1 / middle 1 / min 3 | `client.py:297` | §6.1 |

**하드코딩** (설정으로 못 바꾼다 — 튜닝 이력을 볼 때 중요):

| 값 | 위치 | 의미 |
|---|---|---|
| 0.1초 | `transcriber.py:654` | A4 정체 판정 임계 |
| 큐 길이 4 | `transcriber.py:649` | A4 관찰 창 |
| 45초 → 트림 | `server.py:412-415` | 버퍼 상한 |
| 1.0초 | `server.py:830` | 최소 청크 |
| 5 | `server.py:365` | `send_last_n_segments` |
| 0.9 | `server.py:768` | 언어 래치 확률 하한 |

---

## 6. 중복 제거 → 문장 묶기 → 필터 → 번역

### 6.1 중복 제거 — `client.py:199-278`

§3.3의 재디코딩 때문에 **새 세그먼트가 직전 세그먼트의 꼬리를 반복한다.** `check_repeat_with_last_segment(base, candidate)`가
이를 잘라낸다 (`base` = 새 내용, `candidate` = 직전 세그먼트, 호출 `client.py:297`).

1. 양쪽 정규화 — `:187-197` `_norm_no_space_and_map`. 공백과 `.,!?::()[]{}*"'` 제거 후 casefold, **원본 인덱스 맵 유지**(잘라낼 위치를 원본 좌표로 되돌리기 위해)
2. `base`의 단어/문장부호 경계 수집 — `:214-223`
3. **긴 경계부터** 훑으며 `base`의 접두사가 `candidate`의 **접미사**와 퍼지 매칭되는지 검사 — `:229-244`
4. 매칭되면 그 앞부분을 잘라 반환 — `:246-258`. 매칭 없으면 원본 그대로

퍼지 매칭 `:260-278`은 앞쪽 `max_head_mismatch`자 건너뛰기 + 위치별 치환 `max_middle_edits`자 허용.
설정은 각각 1·1·최소 길이 3 (함수 기본값 0·0·3보다 느슨하다).

### 6.2 문장 묶기 — `client.py:280-386`

`add_transcript_segmentation()`이 세그먼트를 문장으로 묶는다. 커서 3개가 어디까지 소비했는지를 추적한다:

| 커서 | 가리키는 것 |
|---|---|
| `savepoint` | 서버 transcript 중 소비 완료 위치 |
| `segment_flag` | `result_list`(세그먼트) 소비 위치 |
| `sentence_flag` | UI 문장 리스트 위치 |

**문장 경계 규칙** — `client.py:349-351`:

```python
if segment.forced or (content and content[-1] in ['.', '?'] and segment.completed):
```

- **`forced`면 무조건 문장 끝** — §5의 A3·A4가 곧 문장 경계가 된다
- 아니면 `completed`이면서 마지막 문자가 `.` 또는 `?`
- **`!`는 종결자가 아니다.** 클래스 상수 `PUNCTS = {",", ".", "!", "?"}`(`client.py:89`)와 §6.1 정규화 문자셋(`:193`)에는
  `!`가 들어 있는데 이 경계 규칙에만 빠져 있어서 헷갈리기 쉽다
- 화자/언어(`spk`)가 바뀌어도 flush — `:335-342`
- 발행은 큐를 완전히 비우고 리스트를 통째로 교체 — `:382-384` (마지막 상태만 유효)

### 6.3 환각 필터 + 단어 교정 — `filtering____init__.py:61`

`filter_hallucination(raw_transcript)`이 클라이언트에서 매 응답마다 돈다(`client.py:413`):

1. `hallucination.json`의 토큰을 문자열에서 제거 — 길이 긴 것부터(`:55`)
2. 남은 다중 공백 정리 — `:78`
3. `.`·`?`만 남은 세그먼트 폐기 — `:81`
4. 단어 교정 사전을 **하나의 alternation 정규식으로 컴파일**해 일괄 치환 — `:88-90`

사전은 `manager.py:74-91`에서 admin JSON + 사용자 SQLite를 병합하고 **긴 키 우선 정렬**(`:88`)한다
— `"국방부"`가 `"국방"`보다 먼저 매칭되게 하려는 것이다. `db_reset` Event로 런타임 갱신(`client.py:402-405`).

### 6.4 UI 전달 — `app.py:63-99`

`generate_stream()`이 `transcript_list` 큐를 폴링해 SSE로 내보낸다.
`focus_flag` 커서는 **`completed`일 때만 전진**(`:94`)한다 — 미확정 문장은 같은 인덱스를 계속 다시 보낸다.

```
data: {"content": "...", "language": "ko", "status": "process"|"complete"}
```

**`language` 필드는 `segment.spk`인데(`:77`) 이건 화자 ID가 아니라 감지된 언어다.**
(현행 whisperlivekit은 화자분할이 붙어 `speaker`가 실제 화자를 뜻한다 — 같은 이름이 다른 걸 가리키니 주의.)

### 6.5 번역 — pull 방식

**ASR 파이프라인은 번역기를 부르지 않는다.** 프론트가 줄마다 `POST /api/translate`(`app.py:117-123`)를 호출한다.
→ **현행과의 근본적 설계 차이** (현행은 확정 시점에 백엔드가 자동 트리거).

`LlamaTranslator.translate()`(`translator.py:103-134`)가 시스템 블록을 순서대로 쌓는다:

1. **정적 8규칙** `:61-72` — 항상 번역 / 거부·설명 금지 / 대상 언어만 출력 / `-습니다` 종결 /
   문두 `"다음"` → `"Next slide,"` / `rock·lock·rog` → `Rok` / `"sir"` 무시
2. **매칭된 용어집** `prompt_manager.py:144-169` — **양방향 부분일치**(`origin.lower() in input_lower or trans.lower() in input_lower`).
   한국어 조사 결합(`공군은`)을 견디려는 설계다. 매칭 없으면 빈 문자열을 반환해 빈 헤더 주입을 막는다(`:166-167`)
3. **few-shot 예시** `prompt_manager.py:171`
4. **Qdrant 유사도 검색 k=3** `translator.py:124-131`

프롬프트는 Harmony 채널 형식(`:79-86`), 엔드포인트는 `http://localhost:2010/v1/completions`(`:148-163`),
응답 파서는 `:166-200`.

번역 방향은 인자로 받지 않고 추론한다 — `get_to_lang()`(`:44-46`)이 `en → ko`, 그 외 전부 `→ en`.

---

## 7. 현행 whisperlivekit과 대조할 때

| 레거시 | 현행 | 핵심 차이 |
|---|---|---|
| `server.py` 슬라이딩 재디코딩 + `update_segments` 4갈래 | [whisperlivekit/simul_whisper/](../whisperlivekit/simul_whisper/) + [tokens_alignment.py](../whisperlivekit/tokens_alignment.py) | 재디코딩+반복확정 → **AlignAtt/CIF 어텐션 유도 커밋**. 정본 [SENTENCE_FINALIZATION_LOGIC.md](SENTENCE_FINALIZATION_LOGIC.md) |
| `client.py` 마이크 캡처 프로세스 | 브라우저 → WebSocket `/asr` | **오디오 입력 주체가 반대편으로** 이동. [API_SPEC.md](API_SPEC.md) |
| `client.py` 중복 제거(§6.1) | — | 재디코딩이 없어져 **휴리스틱 자체가 불필요** |
| `client.py` 문장 묶기(§6.2) | `tokens_alignment.py` | `forced`·온점 규칙 → 경계 원인 3종(silence·language_switch·speaker_change) + 온점 형태소 분할 |
| 언어 래치(§4.1) | 세션 언어모드 auto/ko/en + 코드스위칭 경계 | 수동적 락 → **능동적 전환 경계 + 경계 단어 보존**. [CLAUDE.md](../CLAUDE.md) §3.2 |
| `filtering____init__.py`·`manager.py` | [whisperlivekit/filtering/](../whisperlivekit/filtering/) | **이식 완료** |
| `translator.py`·`prompt_manager.py` | [whisperlivekit/llm_translation/](../whisperlivekit/llm_translation/) | **이식 완료** + 확정 시점 자동 트리거(pull → push) |
| SSE `/api/recordings` | 델타 프로토콜 | [DELTA_PROTOCOL_SPEC.md](DELTA_PROTOCOL_SPEC.md), [SCHEMA_CHANGES.md](SCHEMA_CHANGES.md) |
| 화자 구분 없음(`spk` = 언어) | Sortformer 화자분할 | 현행 최우선 지표가 **화자분리 F1** |

**심화 대조**는 [docs/archive/WL_VS_WLK_COMPARISON.md](archive/WL_VS_WLK_COMPARISON.md)에 이미 정리돼 있다 —
확정정책·문장분리·코드스위칭·군사용어 인식 차이를 절별로 다룬다.
단 **작성 시점(2026-07-10) 스냅샷**이고 archive는 재참조 전제가 아니므로, 현행 쪽 서술은 위 표의 정본 문서로 교차 확인할 것.

특정 모듈을 직접 비교하려면 `/code-guide compare <모듈명>` 슬래시 커맨드를 쓴다.

**현행 쪽 진입점**: [whisperlivekit/basic_server.py](../whisperlivekit/basic_server.py)(FastAPI + WS `/asr`) →
[audio_processor.py](../whisperlivekit/audio_processor.py)(파이프라인) → [core.py](../whisperlivekit/core.py)(`TranscriptionEngine`).
전체 색인은 [FILE_INDEX.md](FILE_INDEX.md).

---

## 8. 부록 — 빠른 참조

### 8.1 하드코딩된 주소·경로

| 값 | 위치 |
|---|---|
| ASR 모델 `models/faster-whisper-large-v3-turbo` | `main.py:71` |
| API 서버 `0.0.0.0:8000` | `main.py:140` |
| LLM 엔드포인트 `http://localhost:2010/v1/completions` | `translator.py:150` |
| ASR 서버 포트 | 설정값(샘플 1234) `main.py:70-73` |
| 클라이언트 접속 대상 `localhost:{port}`, `max_clients=3` | `main.py:105-119` |
| 임베딩 `bge-m3` + 로컬 Qdrant `official_translation` | `translator.py:23-38` |

### 8.2 메시지 스키마

**① 클라이언트 → 서버** (WebSocket)

- 핸드셰이크: JSON 텍스트 1프레임 `{uid, language, task, model, initial_prompt, hotwords, max_clients, max_connection_time}` — `client.py:491-504` → `server.py:211-217`
- 오디오: binary 프레임, little-endian float32 @16kHz
- 제어: 텍스트 `"reset"` / 종료 `b"END_OF_AUDIO"`

**② 서버 → 클라이언트** (전부 JSON, 전부 `uid` 포함)

| 메시지 | 형태 | 위치 |
|---|---|---|
| 준비 완료 | `{message:"SERVER_READY", backend}` | `server.py:663-671` |
| 언어 감지 | `{language, language_prob}` | `server.py:722-723` |
| 대기 | `{status:"WAIT", message:<분>}` | `server.py:112` |
| 오류 | `{status:"ERROR", message}` | `server.py:697-705` |
| 연결 종료 | `{message:"DISCONNECT"}` | `server.py:529-532` |
| **전사** | `{segments:[...]}` | `server.py:512-517` |

> **`segments` 배열이 이종(heterogeneous)이다** — 세그먼트 객체 최대 5개(`send_last_n_segments`) 뒤에
> **정수 `transcript_len`이 하나 붙는다**(`server.py:509`). 읽다 보면 반드시 걸리는 지점이다.

세그먼트 객체 (`server.py:849-857`) — **`start`/`end`가 문자열**(`"{:.3f}"` 포맷):

```json
{"start": "12.340", "end": "14.120", "text": "...", "completed": false, "lang": "ko", "forced": false}
```

`completed`/`forced` 조합의 의미 (§5와 연결):

| completed | forced | 의미 |
|---|---|---|
| `true` | `false` | A1 자연 확정 |
| `false` | `false` | A2 미확정 꼬리(잠정) |
| `false` | `true` | **A3 N회 반복 확정** |
| `true` | `true` | **A4 타임스탬프 정체 확정** |

**③ API → 브라우저**

- SSE `GET /api/recordings` → `{content, language, status:"process"|"complete"}` — `app.py:87`, `:91`
- SSE `POST /api/translate` → `{content}` 반복, 종료 `{status:"done"}` — `translator.py:195`, `:200`
- REST: `/api/corrections` GET·POST·DELETE(`app.py:169-193`), `/api/prompts` + `/add-item` + `/delete-item`(`:198-239`),
  `/api/recordings/start|stop|status`(`:125-152`)

### 8.3 함수 위치 빠른 색인

| 찾는 것 | 위치 |
|---|---|
| 프로세스 기동 | `main.py:151` `entry_point` |
| 마이크 루프 | `client.py:692` `record` |
| 오디오 수신 | `server.py:187` `get_audio_from_websocket` |
| 버퍼 관리 | `server.py:395` `add_frames` |
| **재디코딩 청크 추출** | `server.py:438` `get_audio_chunk_for_processing` |
| 전사 루프 | `server.py:820` `speech_to_text` |
| 모델 호출 | `server.py:725` `transcribe_audio` |
| **확정 판정** | `server.py:893` `update_segments` |
| 응답 포맷 | `server.py:849` `format_segment` |
| 디코딩 파라미터 | `transcriber.py:682` `transcribe` |
| 정체 감지 | `transcriber.py:966` `_split_segments_by_timestamps` |
| 언어 감지 제한 | `transcriber.py:1766` `detect_language` |
| 중복 제거 | `client.py:199` `check_repeat_with_last_segment` |
| 문장 묶기 | `client.py:280` `add_transcript_segmentation` |
| 환각 필터 | `filtering____init__.py:61` `filter_hallucination` |
| 사전 병합 | `manager.py:74` `refresh_replacements` |
| 용어집 매칭 | `prompt_manager.py:144` `get_relevant_glossary` |
| 번역 프롬프트 | `translator.py:103` `translate` |
| SSE 발행 | `app.py:63` `generate_stream` |

---

## 관련 문서

- [FILE_INDEX.md](FILE_INDEX.md) — 현행 코드 파일 색인
- [archive/WL_VS_WLK_COMPARISON.md](archive/WL_VS_WLK_COMPARISON.md) — 구/신 확정정책·문장분리 심화 비교 (2026-07-10 시점)
- [SENTENCE_FINALIZATION_LOGIC.md](SENTENCE_FINALIZATION_LOGIC.md) — 현행 문장 확정·분리 정본
- [API_SPEC.md](API_SPEC.md) · [DELTA_PROTOCOL_SPEC.md](DELTA_PROTOCOL_SPEC.md) — 현행 서버 계약
- [MASTER_CHANGES.md](MASTER_CHANGES.md) — 현행 master의 upstream 대비 전체 변경
- [CLAUDE.md](../CLAUDE.md) §1 — 이 디렉터리의 취급 규약
