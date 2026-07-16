# 배포 PC 번역(oss20b) 검증 런북

## 목적

배포 PC에는 **기존 whisperlive가 이미 oss20b(llama.cpp, `synatra` 별칭)로 번역을 수행 중**이다. 이 런북은
새 **wlk**(whisperlivekit 기반)를 그 동일한 번역 서버에 붙여, 번역이 기존과 동등하게 동작하는지 배포 PC
현장에서 **그대로 따라 할 순서**만 담는다. 배경 설계·근거는 중복 서술하지 않고
[DEPLOYMENT_OFFLINE.md §4.4/§5](DEPLOYMENT_OFFLINE.md), [TRANSLATION_SETUP.md](TRANSLATION_SETUP.md),
[FRONTEND_HANDOFF_SUMMARY.md §7](FRONTEND_HANDOFF_SUMMARY.md)를 참조한다.

**코드 변경은 필요 없다.** wlk의 `LlamaTranslator`([translator.py:58-93](../whisperlivekit/llm_translation/translator.py#L58-L93))는
기존 whisperlive `LlamaTranslator`([whisperlive_code/translator.py:145-200](../whisperlive_code/translator.py))와
엔드포인트(`{endpoint}/v1/completions`)·harmony 프롬프트·JSON 파라미터(`temperature:0, max_tokens:1024,
top_p:1, top_k:0, repeat_penalty:1, stream:false`)·군사 번역 시스템 프롬프트까지 **프로토콜이 동일**하다.
과거 번역이 안 켜지던 차단 버그 2건(config 필드 누락, 화자분할 ON 시 finalized 미설정)도 master에 이미
머지되어 있다. 남은 일은 **CLI 플래그로 기존 서버에 연결해 확인**하는 것뿐이다.

---

## 0. 전제 확인 — 기존 번역 서버 값 파악

배포 PC에서 기존 whisperlive가 쓰던 값을 그대로 재사용한다. 새로 지어내지 말 것:

| 항목 | 값 | 근거 |
|---|---|---|
| 엔드포인트 | `http://localhost:2010` | `whisperlive_code/translator.py:150` |
| 서버 타입 | `llama` (llama.cpp, `/v1/completions`, harmony 태그) | 동일 |
| 모델 별칭 | **`synatra`** (⚠️ 문서 기본값 `gpt-oss-20b`가 아님) | `whisperlive_code/whisper_1023.txt:29` `model_name:'synatra'` |

> `synatra`는 배포 PC의 llama.cpp가 gpt-oss-20b 모델을 서빙할 때 붙인 **서빙 별칭**일 뿐이다. 값이
> 바뀌었을 수 있으니 아래 1단계 `curl`로 항상 실측 확인한다.

---

## 1. LLM 서버 격리 스모크 (wlk 기동 전)

wlk를 붙이기 전에 번역 서버 자체가 살아있는지 wlk와 무관하게 먼저 확인한다. 여기서 실패하면
wlk 문제가 아니라 llama.cpp 서버/모델 문제로 원인을 좁힐 수 있다.

```powershell
# 1) 서빙 중인 모델 id 확인 — 이 값을 아래 --translation-model에 그대로 쓴다
curl http://localhost:2010/v1/models
```

```powershell
# 2) harmony 프롬프트로 completions 1발 직접 호출 — 번역문이 돌아오는지 확인
curl -X POST http://localhost:2010/v1/completions `
  -H "Content-Type: application/json" `
  -d '{
        "model": "synatra",
        "prompt": "<|start|>system<|message|>You are a military professional translator.\n            Rules:\n            1. Always translate the given Korean content into natural, fluent, polite, and formal English.\n            4. Output only the final translated English!!\n            <|end|>\n<|start|>user<|message|>안녕하세요, 오늘 날씨가 좋습니다.<|end|>\n<|start|>assistant<|channel|>final<|message|>",
        "temperature": 0,
        "max_tokens": 128,
        "top_p": 1,
        "top_k": 0,
        "repeat_penalty": 1,
        "stream": false
      }'
```
- `model`은 1단계 실측 id로 바꿔 넣는다.
- 통과 기준: `choices[0].text`에 영어 번역문이 채워진다.
- 실패(연결 거부/타임아웃/빈 응답)면 → 아래 §4 트러블슈팅으로.

---

## 2. wlk 기동 — 번역 4플래그 추가

전사·화자분할·포트(8900)는 배포 기본값 그대로 두고, 번역 플래그 4개만 추가한다(저장소 루트에서 실행):

```powershell
whisperlivekit-server `
  --llm-translation `
  --translation-serve llama `
  --translation-endpoint http://localhost:2010 `
  --translation-model synatra
```

> `--translation-model`은 반드시 §1에서 실측한 id로 맞춘다. 문서 기본값(`gpt-oss-20b`)을 그대로 쓰지 말 것.
> 화자분할을 빼고 번역만 보려면 `--no-diarization`을 추가한다 ([DEPLOYMENT_OFFLINE.md §5.3](DEPLOYMENT_OFFLINE.md#5-번역gpt-oss-20b-배포-설정--q3)).

---

## 3. 번역 동작 검증

내장 UI(`http://localhost:8900/`, 이미 §4.4 1·2단계로 전사·React 연결이 검증돼 있어야 함) 또는 React 프론트에서:

- **한↔영 문장을 번갈아 또는 짧게 끊어 발화**한다(중요 — 아래 §5 타이밍 특성 참조).
- 통과 기준: 문장이 **확정되는 순간** `lines[].translation`에 번역문이 채워져 화면에 표시된다.

---

## 4. 통과/실패 판정 + 트러블슈팅

| 증상 | 원인 후보 | 확인 방법 |
|---|---|---|
| `translation` 항상 `""` | 서버 미기동/포트 상이 | §1의 `curl /v1/models`가 실패하는지 재확인 |
| `translation` 항상 `""` | 모델 별칭 불일치 (`synatra` 대신 `gpt-oss-20b`로 줌) | `--translation-model`을 §1 실측 id로 재기동 |
| `translation` 항상 `""` | `--translation-serve`를 `ollama`로 줌 | `llama`로 수정 (경로가 `/v1/chat/completions`로 잘못 감) |
| `translation` 항상 `""` | `--llm-translation` 누락 | 플래그 확인 |
| 서버 로그에 completions 호출은 찍히는데 번역이 안 붙음 | 화자분할 ON에서 세그먼트가 아직 `finalized`가 아님 | 정상 동작 특성(§5) — 화자 전환을 유도 |
| 번역이 한 박자 늦게 뜸 | 발화 중인 마지막 세그먼트는 다음 화자 전환 시 확정 | 정상 (`DEPLOYMENT_OFFLINE.md §5.4`) |
| 한 화자만 계속 말하면 번역이 안 붙음 | 화자 전환이 없어 확정 트리거가 안 걸림 | 두 명이 번갈아 발화로 재현 |
| 한글이 깨져서 전송됨 | curl로 직접 호출 시 인코딩 문제 | httpx(wlk 내부)는 `ensure_ascii`로 정상 처리됨 — curl 자체 결함이니 wlk 실사용에는 무관 |

---

## 5. 알려진 차이 — 기존 whisperlive 대비 (버그 아님, 이번 범위 밖)

- **Glossary/벡터 few-shot 미이식**: 기존 whisperlive는 Qdrant(bge-m3 임베딩) 벡터 검색으로 예시 문장을
  프롬프트에 주입하고 동적 glossary(`admin_translation_glossary.json`/`user_translation_glossary.db`)를
  참조한다. wlk 번역기는 **정적 군사 프롬프트만** 사용한다 — glossary·few-shot 관련 클래스·팩토리가
  존재하지 않는다 ([TRANSLATION_SETUP.md §6.3](TRANSLATION_SETUP.md) 참조). 결과: **동일 입력이라도 번역
  품질/용어 일관성이 기존과 다를 수 있다.** 이는 결함이 아니라 이번 배포 범위에서 의도적으로 보류한 기능이다.
- **`buffer_translation`(미확정 문장 중간 번역) 미구현**: 스키마 필드는 존재하나 항상 `""`. 확정된 문장만
  번역된다 ([FRONTEND_HANDOFF_SUMMARY.md §7](FRONTEND_HANDOFF_SUMMARY.md)).
- **스트리밍 미사용**: 기존은 SSE 스트리밍(`_stream`), wlk는 단일 non-streaming POST. 둘 다 `stream:false`로
  동작하므로 최종 번역 결과는 동등하나, 화면에 토큰 단위로 흘러나오는 연출은 없다.

---

## 6. 사전 점검(권장) — 배포 PC 가기 전 dev PC dry-run

배포 현장에서 변수를 줄이려면, dev PC에서 wlk 번역 배선 자체가 살아있는지 먼저 확인해둔다:

```powershell
# Ollama 기동 후
whisperlivekit-server `
  --llm-translation `
  --translation-serve ollama `
  --translation-endpoint http://localhost:11434 `
  --translation-model qwen2.5:7b
```

내장 UI에서 한↔영 발화 → `lines[].translation` 채워짐을 확인한다. 이게 통과하면 배포 PC와의 차이는
**`--translation-serve llama` + 엔드포인트(`:2010`) + 모델 별칭(`synatra`)뿐**임이 보장되어, 배포 현장에서
실패 시 원인을 그 세 가지로 좁힐 수 있다.

---

## 참조

- [DEPLOYMENT_OFFLINE.md §4.4](DEPLOYMENT_OFFLINE.md) — 배포 검증 3단계(전사 → React 연결 → 번역)
- [DEPLOYMENT_OFFLINE.md §5](DEPLOYMENT_OFFLINE.md) — 번역 배포 설정, 차단 버그 수정 이력
- [TRANSLATION_SETUP.md](TRANSLATION_SETUP.md) — dev/배포 환경별 서버 기동 명령
- [FRONTEND_HANDOFF_SUMMARY.md §7](FRONTEND_HANDOFF_SUMMARY.md) — 번역 스키마(`lines[].translation`, `buffer_translation`)
- `whisperlivekit/llm_translation/translator.py`, `manager.py` — 번역기 구현
- `whisperlivekit/config.py:86-89`, `whisperlivekit/parse_args.py:408-437` — 번역 CLI 플래그 정의
