# 테스트 / 환경 가이드

본 문서는 [CLAUDE.md](../CLAUDE.md)에서 분리한 **환경 상세 + 테스트 실행 절차**를 담는다.
불변 설계 제약·운영 규칙은 CLAUDE.md를, 본 문서는 "어떻게 실행하고 검증하는가"를 다룬다.

---

## 1. 개발 / 테스트 환경 (현재 작업 환경)

- Windows PC, **RTX 3080**, 인터넷 연결 가능
- VS Code IDE에서 Claude Code를 통해 개발/테스트
- 테스트 입력 경로 — 세 가지 방식 병렬 운영 (경로 C는 Phase 2에서 도입)

### 경로 A — 파일 기반 (빠른 개발 스모크/회귀 확인)

- WhisperLiveKit 내장 헤드리스 클라이언트 [whisperlivekit/test_client.py](../whisperlivekit/test_client.py)로
  **`test_data/` 내 로컬 mp3/wav 파일을 WebSocket `/asr`에 직접 송신**한다.
- **가상 오디오 케이블(VB-Cable, VoiceMeeter 등)에 의존하지 않는다.** 사운드 카드/드라이버 설치도 불필요.
- 의존성: 시스템 `ffmpeg` 설치 필수 (파일을 PCM s16le 16kHz mono로 변환).
- 서버는 `--pcm-input` 플래그로 기동 → 클라이언트가 PCM 청크를 직접 송신.
- 실행 예:
  - 서버 기동: `whisperlivekit-server --pcm-input` (나머지는 모두 parse_args.py 기본값)
  - 파일 송신: `python -m whisperlivekit.test_client test_data/sbs1.mp3 --live`
  - Windows PowerShell에서 한국어 출력 깨짐 방지: `$env:PYTHONIOENCODING = "utf-8"` 선행 실행 필요
- 옵션: `--speed 1.0`(실시간) / `--speed 0`(가능한 한 빠르게), `--language ko`/`--language en` 강제,
  `--live`로 비확정/확정 진행 출력, `--json`으로 원본 응답 로깅.
- **자동 평가**: `scripts/eval.py`는 기본적으로 경로 C(1차 정량)를 실행한다. 경로 A는 `--paths A`로
  빠른 개발 스모크(코드 회귀 확인)용으로 돌린다. 두 경로 모두 **WER + (화자분리 F1 + 문장분리 F1)**을 산출한다.
  F1은 정답 신형식 `[spkN]` 전환 경계(화자분리 F1) / 화자 블록 내 줄바꿈 경계(문장분리 F1)와 STT 확정 문장(`lines[]`) 경계를 비교한다(2지표 분리 구현 완료 — [TRANSCRIPTION_REQUIREMENTS.md](TRANSCRIPTION_REQUIREMENTS.md) §5).

### 경로 B — 마이크 직접 녹음 (정성적)

- 서버를 `--pcm-input` 플래그 없이 기동 → 브라우저가 `MediaRecorder` 방식으로 마이크 음성을 실시간 캡처
- 브라우저에서 `http://localhost:8900/` 접속 → 내장 웹 UI
  ([whisperlivekit/web/live_transcription.html](../whisperlivekit/web/live_transcription.html))에서 마이크 직접 녹음
  (`--frontend-dir`가 가리키는 디렉터리에 `index.html`이 있으면 — 기본값 `frontend/static` — 내장 UI 대신 React
  dist가 서빙된다. dist가 Vite `base`(예 `/wlkies`)로 빌드됐으면 백엔드가 base를 자동 추출해 그 하위로 서빙하고
  `GET /`는 base로 리다이렉트한다 — `--frontend-base`(기본값 `auto`)로 오버라이드. 개발 PC엔 보통 dist가 없으므로
  이 절 그대로 내장 UI가 뜬다.)
- 마이크에 직접 말하면서 전사 결과를 실시간 확인 (정성적 평가)
- 서버 기동: `whisperlivekit-server` (모든 인자가 parse_args.py 기본값 — `--lan auto` + simulstreaming. `--periodic-lang-check` 기본 None(비활성 — turbo 기질 Exp-160 채택, PLC=4.0이 ytn2에서 스퓨리어스 전환→환각 유발 확인); 탐색 시 다른 값 명시. 상세는 [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) 참조)
- 목적: 실제 마이크 입력에 대한 정성적 평가 (경로 C 정량 평가와 병행)
- 저장 버튼 클릭 시 내장 UI가 그 시점까지의 누적 전사를 `--transcript-save-dir`(기본값 `./transcripts`) 폴더에 `.txt`로 저장한다 (`POST /api/save-transcript`, 녹음 중에도 클릭 가능, 녹음 종료 시 자동 저장 아님).
- **소스 언어 드롭다운 수동 검증(세션 언어 고정, 2026-07-17~)**: 우상단 설정(⚙) 패널의 "Source Language" 드롭다운(`auto`/`ko`/`en`)으로 그 세션의 소스 언어를 지정한다. 녹음 시작 **전에** 선택한다(녹음/처리 중엔 select 비활성 — 언어는 연결 시점에만 적용). 검증 포인트:
  - `ko`/`en` 선택 시 브라우저 개발자도구 Network에서 WS `/asr` 요청 URL에 `?language=ko`(또는 `en`)가 붙는지, `auto` 선택 시 `language` 파라미터가 생략되는지 확인.
  - 연결 직후 콘솔의 `Server applied source language: <값>` 로그(= `config` 메시지 `language` 필드)가 선택값과 일치하는지 확인.
  - 언어 고정 시 한↔영 재감지·`language_switch` 경계가 비활성인지(예: 한국어 고정 세션에서 영어 발화가 억제/재감지 안 됨) 정성 확인. 선택값은 `localStorage`에 저장돼 새로고침 후에도 복원된다.

### 경로 C — 오디오 루프백 (1차 정량 성능 기준, Phase 2 도입)

- VBCable로 테스트 파일을 PC에서 재생해 가상 마이크 경유 전사
- 마이크 입력 경로(경로 B)를 유지하면서 동일 음성으로 반복 측정 가능 → 재현성 있는 정량 평가.
  실제 오디오 파이프라인을 거치므로 Phase 2 채택/기각의 **1차 정량 신호**다.
- 헬퍼: [scripts/vbcable_test.py](../scripts/vbcable_test.py)
- `scripts/eval.py`는 기본으로 경로 C를 실행해 **WER + 화자분리 F1 + 문장분리 F1**을 산출한다(우선순위 = 화자분리 F1 > WER > 문장분리 F1; 정답 = 신형식 `_speak,sentence_sperate.txt` canonical). *2지표 분리·신형식 파서 구현 완료 — 신형식 정답이 있으면 `seg_f1`=화자분리 F1·`sentence_f1`=문장분리 F1을 산출하고, 없거나 파싱 실패 시 구 regime(빈 줄 경계, `sentence_f1=None`)으로 폴백한다: [TRANSCRIPTION_REQUIREMENTS.md](TRANSCRIPTION_REQUIREMENTS.md) §5.*
  브라우저 `#linesTranscript`의 `.textcontent`(확정 문장)만 추출하므로 타임스탬프 행이 섞이지 않는다.
- **산출물 위치**: 벤치마크 JSON `--output`(관례 `.omc/benchmarks/`) · 전사 `.omc/transcripts/{파일}_{경로}_R{회차}.txt` · **서버 로그** `.omc/server_logs/server_<stem>_<path>_R<rep>_<ts>.log`(회차별 항상 저장 — Exp-153; `[QualityGate]`/`[LangSwitch]`(후자는 `--trace-tokens` 시) 등 필터·전환 계측용).
- **문장별 확정 트리거**: 전사 txt에 `[문장별 확정 트리거]` 섹션(각 문장 뒤 `⟨silence/punctuation/language_switch/speaker_change/-⟩`)이, JSON `files[].hyp_lines`(`[{"text","trigger"}, …]`)가 additive로 추가된다(WER/F1 계산은 불변). 문장 분리 로직 정성 분석용 — 경로 C는 UI DOM `data-trigger` 속성, 경로 A는 `lines[].finalize_trigger`에서 수집.

**수동 서버 기동 명령:**
```
whisperlivekit-server
```
모든 인자가 `parse_args.py` 기본값(포트 8900, `--lan auto`, 화자분할 ON, `--compression-ratio-threshold 3.0`, `--logprob-threshold -2.0` 등)이라
인자 없이 기동해도 eval.py/closed_test.py 자동 기동 설정과 동일하다.
단, eval/closed_test는 서버를 **8901**로 자동 기동한다(수동 서버 8900과 포트 충돌 없이 병행 가능).

> **배포 상황별 파라미터 튜닝(`--scenario`, Phase A)**: `--scenario {mono,dialogue,sequential,codeswitch,multi}`로
> 문장 확정/화자 귀속/언어 재감지 관련 9개 파라미터 + `--frame-threshold`/`--silence-hard-secs`를 상황별
> 프리셋으로 한 번에 적용할 수 있다(개별 플래그가 프리셋보다 우선). 미지정 시 기존 마스터와 100% 동일하게
> 동작(무회귀). 상세는 [OPERATOR_TUNING_GUIDE.md](OPERATOR_TUNING_GUIDE.md) 참조.

> **세션 언어모드(CLAUDE.md §3.2)**: `--lan auto`가 코드스위칭(auto) 세션의 기본값. 한국어/영어 단일 세션을
> 측정하려면 `--lan ko` / `--lan en`으로 기동한다(eval.py 사용 시 `--lan` 인자로 전달 — 아래 파일 목록의
> 언어모드 태그와 일치시킬 것). `--lan`은 서버 1회 기동당 전역 1값이므로 언어모드가 다른 파일은 별도 실행으로 측정한다.

> ⚠️ **반복 측정 — 2계층**: 실시간 STT는 동일 조건에서도 매 실행마다 성능 편차가 발생한다.
> **① 평소 스크리닝 = 1회** (`--repeat` 생략) — 방향 탐색·catastrophic 회귀 감지용. 1회 수치는 방향 신호로만 해석한다.
> **② master 채택 확정(머지 직전)만 최소 3회** (`--repeat 3`) — median+분산(min/max/stdev)으로 판단. 상세 규칙은 CLAUDE.md §4.

- 상세 배경은 [ROADMAP.md](../ROADMAP.md) Phase 2 참조.

### test_data 디렉토리 구조

- `test_data/` 디렉토리: 음성 파일(mp3/wav) + 선택적 정답 스크립트(txt)
- 파일명 규칙: 음성파일과 정답 스크립트 파일명 동일, 확장자만 다름 (예: `sbs1.mp3` ↔ `sbs1.txt`)
- 정답 스크립트가 없는 음성파일도 존재 가능
- **정답 스크립트 형식 (canonical, 2026-07-18부로 `<name>.txt` 단일 규약)**: 성능 개선 정답 = `<name>.txt`. 두 경계를 라벨링한다:
  1. **`[spkN]` 헤더 전환 = 화자전환 경계** → **화자분리 F1**(1순위·필수). 화자가 바뀌면 새 `[spkN]` 헤더(사람 단위 — 같은 화자는 한·영 code-switch 가능, bong1=4화자 `spk1`~`spk4`).
  2. **화자 블록 내 줄바꿈 = 온점 문장 경계** → **문장분리 F1**(3순위·nice-to-have). WER 정답은 `[spkN]` 헤더 제거·라벨 미포함 텍스트.
  - `[spkN]` 헤더가 없는 `<name>.txt`(라벨 없는 빈 줄 경계만)는 구형식으로 폴백 파싱된다(문장분리 F1 미산출) — `eval.py`가 같은 `<name>.txt`에 대해 신형식 파싱을 우선 시도하고 실패 시에만 폴백. 과거엔 `_speak,sentence_sperate.txt`라는 별도 접미사 파일명으로 신/구형식을 구분했으나 **폐지되고 `<name>.txt`로 통합**됐다(전 파일 `[spkN]` 헤더 포함 상태). 형식·측정 정본 = [TRANSCRIPTION_REQUIREMENTS.md](TRANSCRIPTION_REQUIREMENTS.md) §2·§3.
- **파일 목록** (측정 기본 설정: 화자분할 ON — 이 옵션 전체가 이제 `parse_args.py` 기본값이라 추가 인자 없이 `whisperlivekit-server`만 기동해도 동일 설정임). **언어모드** 태그(CLAUDE.md §3.2)는 측정 시 넘길 `--lan` 값을 가리킨다:
  - `bong1.mp3` / `bong1.txt` — 봉준호 기생충 인터뷰. **영어 2명 + 한국어 2명**, 화자 교대·긴 발화 혼재. 다화자·온점분리 역량의 핵심 테스트 대상. **언어모드: auto**.
    **테스트(채택/기각) + 개선 최우선 대상**(다화자·긴 발화). 채택 확정 시 `--repeat 3` 루틴.
    `bong1.txt`는 2026-07-21부로 웃음·박수·환호·잡음·더듬 등 **비언어적 표시**를 포함한다(청취 재검수 결과 반영) —
    형식·WER 제외 처리는 [TRANSCRIPTION_REQUIREMENTS.md](TRANSCRIPTION_REQUIREMENTS.md) §2 참조.
  - `ytn2.mp3` / `ytn2.txt` — SCM 회의 통역. 영어 발화자 발화 → 한국인 통역, **한 문장씩 화자 교대**(순차통역). EN↔KO 짧은 텀 교차. **언어모드: auto**.
    **테스트(채택/기각) + 개선 최우선 대상**(짧은 텀 코드스위칭). 채택 확정 시 `--repeat 3` 루틴.
  - `sbs1.mp3` / `sbs1.txt` — 뉴스 리포트. **대부분 한국어 → 중간 영어 인용 → 다시 한국어 종료**(사실상 단일 앵커, 언어 전환 경계). **언어모드: auto**(영어 인용 구간이 있어 ko 고정 시 오전사 위험 — auto 유지). **테스트(채택/기각)**.
  - `ytn1.mp3` / `ytn1.txt` — SCM 회의 통역, ytn2 동일 이벤트 다른 구간. 영어 발화자+한국어 통역, 한 문장씩 화자 교대. **언어모드: auto**.
    **held-out 정량**(ytn2 동일 이벤트 쌍둥이 — ytn2 개선이 미학습 데이터에 일반화되는지 코드스위칭 검증용).
  - `eng1.mp3` / `eng1.txt` — **단일 영어 발화자**만 말하는 상황. script-switch false split 감시용. **언어모드: en**(`--lan en`).
    **held-out 정량**(영어 전용 회귀 감시).
  - `kor1.wav` / `kor2.wav` / `kor3.wav` — 한국어 단독 낭독체(Exp-178 발굴). auto 모드에서 서두 영어 환각 등으로 붕괴하는 실패모드가 발견되어 **정식 테스트셋(채택/기각)에 편입**됨. **언어모드: ko**(`--lan ko`).
    **테스트(채택/기각)**. 채택 확정 시 `--repeat 3` 루틴.
  - `kinno.mp3` / `kinno.txt` — ITS 2021 K-혁신기업 행사, **2화자 순차통역**(한국어 MC + 통역사), 한↔영 교차. **언어모드: auto**.
    **held-out 정성 sanity** — 정답 텍스트의 단어·철자가 부정확할 수 있어 **WER/F1 채택 게이팅에서 제외**. 전반적 화자·문장 분리 + 대규모 누락/환각 유무만 정성 확인.
    **알려진 개선 불가 구간**: `[spk2]`(통역사) 영어 도입부("Good morning, ladies and gentlemen. Welcome to the Dialogue with K-Innovative Companies at ITS 2021.")는 화자 본인의 콩글리시 발음이 원인이라 발음대로 한국어로 오전사되는 것이 정상 — 개선 대상 아님(상세: [TRANSCRIPTION_REQUIREMENTS.md](TRANSCRIPTION_REQUIREMENTS.md) kinno 절).
- **정답 스크립트**: 위 모든 파일에 `<name>.txt`가 존재(canonical, `[spkN]` 헤더+화자·문장 전처리 완료). 2026-07-18 이전엔 `_speak,sentence_sperate.txt` 접미사 파일로 별도 관리됐으나 폐지·통합됨.
- 용도: STT 전사 정확도(WER) + 화자분리 F1 + 문장분리 F1 정량 분석(우선순위 화자분리 F1 > WER > 문장분리 F1)

### STT 동작 확인용 UI 선택지

- **터미널**: `test_client.py --live` 또는 `--json` 출력으로 `lines[]`(확정) + `buffer_transcription`(비확정)
  흐름까지 확인 가능. 백엔드 로그/print 병행. (경로 A 파일 기반 테스트용)
- **WhisperLiveKit 내장 웹 UI**
  ([whisperlivekit/web/live_transcription.html](../whisperlivekit/web/live_transcription.html) + `live_transcription.js`,
  `live_transcription.css`, 서버 실행 시 `GET /`에서 자동 서빙됨): 서버 기동 후 브라우저에서 접속하면 마이크 캡처 및
  실시간 전사 결과를 UI상에서 시각적으로 확인 가능. (경로 B 마이크 직접 녹음 테스트용)
- **기존 React 웹 UI**: 번역(llama) 파이프라인까지 묶어 최종 검증할 때 연결.

### 권장 검증 순서

1. `test_client.py`로 mp3/wav 송신 (경로 A) → 터미널에서 번역 제외, 실시간 STT 전사 동작 확인 (개발 스모크)
2. 서버 기동 후 브라우저 + 마이크 직접 녹음 (경로 B) → 내장 웹 UI에서 실시간 전사 결과 시각 확인 (정성 평가)
3. `test_client.py --live` 터미널 출력으로 확정/비확정 플래그 + 언어 전환 동작 확인
4. 기존 React 웹 UI 연결 후 번역 + 최종 UI 표출까지 확인

---

## 2. 배포 환경

- **폐쇄망** Windows PC, **RTX 5090**, 외부 인터넷 차단
- 실제 마이크 입력 사용
- 모든 모델·라이브러리는 **오프라인 / 로컬 경로 기반**으로 동작해야 한다. 런타임에 HuggingFace Hub, PyPI,
  GitHub 등에 접속하면 안 된다. (불변 제약 — [CLAUDE.md](../CLAUDE.md) §3 참조)

---

## 3. 모델

- **STT**: `whisper-large-v3-turbo` — 로컬 경로:
  [whisperlivekit/model/whisper-large-v3-turbo/](../whisperlivekit/model/whisper-large-v3-turbo/)
  (`config.json` / `model.safetensors` / `tokenizer.json` 등)
- **번역**: 기존 `whisperlive`에서 쓰던 **OSS 20B LLM** 그대로 사용.
