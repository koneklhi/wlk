Phase 1 — 기본 STT 동작 확인
목표
whisperlivekit 위에서 whisper-large-v3-turbo 로컬 모델이 실시간으로 전사되는지 확인한다.
번역·필터링·UI 연결 없이 백엔드 단독으로 동작을 검증한다.
태스크

 1-1. uv 가상환경 구성 및 whisperlivekit 의존성 설치
 1-2. whisperlivekit/model/whisper-large-v3-turbo/ 로컬 경로로 모델 로드 확인
 1-3. WhisperLiveKit 내장 `test_client.py`로 로컬 mp3/wav 파일을 WebSocket `/asr`에 송신하여 실시간 전사 동작 확인 (서버는 `--pcm-input`으로 기동, 터미널 출력 기준)
→ 가상 오디오 케이블(VB-Cable, VoiceMeeter 등) 의존 없음. 시스템 `ffmpeg` 설치만 필요.
 1-4. 런타임에 외부 네트워크 호출이 없는지 확인 (HF Hub, PyPI, GitHub 접속 차단 상태에서 동작)

완료 기준

고정 음성 파일(한국어/영어 각 1개)을 `python -m whisperlivekit.test_client`로 송신 → 터미널에 전사 텍스트가 실시간 스트리밍 출력됨
HF_HUB_OFFLINE=1 환경에서 서버 기동~첫 전사 출력까지 외부 HTTP 요청 0건 확인


Phase 2 — 문장 단위 확정 로직 구현
목표
전사된 텍스트가 문장 단위로 비확정→확정 전환되도록 만든다.
이 Phase까지는 `test_client.py` 터미널 출력으로 검증한다 (내장 웹 UI 시각 검증은 보류 — 2-3 참조).
태스크

 2-1. 문장 단위 확정 알고리즘 선택 및 구현 [설계 세션]
→ 후보: Whisper segment 경계 + no_speech_prob, VAD 무음 구간, 구두점, 토큰 안정화(Local Agreement) 등
→ Whisper segment 경계 + VAD 무음 + 구두점 조합을 첫 시도로 적용
→ 기존 whisperlive의 임시방편(N회 반복 확정, 타임스탬프 변화량 임계치)은 이식하지 않음
 2-2. 비확정 / 확정 플래그를 전사 텍스트와 함께 출력 (`test_client.py --live` 출력의 `lines[]` / `buffer_transcription`으로 확인)
 2-3. WhisperLiveKit 내장 웹 UI(GET /)에서 확정/비확정 플래그 시각 확인 — **보류 (추후 재논의)**
→ `test_client.py`는 헤드리스라 마이크 캡처 기반의 내장 웹 UI로는 검증 불가. Phase 2 완료 기준은 `test_client.py` 터미널 출력의 확정/비확정 플래그 확인으로 충족하고, 시각 검증 수단은 필요해질 때 별도 결정.
 2-4. Code-Switching(한영 혼용 발화) 동작 확인 (기본 동작 후 문제 발생 시 보강)
→ 단어 유실·환각·문장 조기 확정 발생 여부 확인 후 필요 시 대응

완료 기준 (`test_client.py` 터미널 출력 기준)

한국어만 입력 시 영어 환각 출력 0건, 영어만 입력 시 한국어 환각 출력 0건 (테스트 샘플 각 N개)
문장이 끝날 때 확정 플래그가 `test_client.py --live` / `--json` 터미널 출력에 표시됨
내장 웹 UI 시각 검증은 **보류 — 추후 결정** (2-3 참조)
한영 혼용 발화 테스트에서 심각한 단어 유실 없음 (문제 발생 시 2-4 보강 진행)


Phase 3 — 필터링 / 단어 교정 이식
목표
기존 whisperlive의 환각 제거·단어 대치 로직을 그대로 이식해 전사 결과에 적용한다.
태스크

 3-1. 환각 제거 로직 이식 [이식]
→ whisperlive_code/filtering____init__.py 그대로
 3-2. 단어 대치 로직 이식 [이식]
→ whisperlive_code/manager.py 그대로
 3-3. 전사 직후 필터링 → 확정 판단 순서로 파이프라인 연결
 3-4. 사전 갱신 인터페이스 형태 결정 + 구현 (기존 whisperlive 인터페이스 그대로 이식)
 3-5. 단어 교정 사전 동적 추가/삭제 기능
 3-6. 번역 Glossary 이식 (이식만, 동작 검증은 Phase 5에서)
 3-7. 사전 갱신 즉시 반영 확인 (다음 전사/번역부터 적용)

완료 기준

고정 환각 사례 N개로 회귀 테스트 작성 후 모두 제거 확인
대치 단어가 올바르게 치환됨
운용 중 사전 수정 후 다음 발화부터 즉시 반영됨 (갱신 직후 도착하는 첫 발화에 반영)


Phase 4 — React UI 연결 + 번역 파이프라인 통합
목표
기존 whisperlive React UI를 코드 수정 없이 연결하고,
번역(llama) 파이프라인까지 묶어 전체 흐름을 통합한다.
태스크

 4-1. React에 보내는 메시지 스키마 최종 결정 [설계 세션]
→ 후보 A: 기존 {text, start, end, completed, lang, …} 스키마 유지, 백엔드에서 변환
→ 후보 B: whisperlivekit 출력 기반 새 스키마 정의, React 측 변경 포함
→ Phase 3 완료 후 진입 직전에 사용자와 합의해 결정
 4-2. 기존 React UI WebSocket 프로토콜 호환 구현 [이식]
→ whisperlive_code/server.py, app.py 참조
 4-3. 번역 모델(OSS 20B LLM) 로컬 경로 및 파일 존재 확인
 4-4. 번역 파이프라인 이식 [이식]
→ whisperlive_code/translator.py, prompt_manager.py 그대로
 4-5. 번역 결과를 전달하기 위한 메시지 스키마 필드 정의 및 구현0
 4-6. 문장 확정 시점 → 번역 수행 → UI 출력 흐름 연결
 4-7. 기존 React UI에서 전사·번역 결과 최종 확인

완료 기준

4-1에서 합의된 스키마로 백엔드 구현 완료
React UI 코드 수정 없이 whisperlivekit 백엔드와 연동됨
확정된 문장이 번역되어 React UI에 출력됨
인터넷 차단 상태에서 전체 파이프라인 동작함


Phase 5 — Glossary 동적 관리
목표
운용 중 단어 교정 사전과 번역 Glossary를 동적으로 추가·삭제하고 즉시 반영되도록 한다.
태스크

 5-1. 단어 교정 사전 동적 추가/삭제 기능 이식 [이식]
→ whisperlive_code/manager.py 기반 그대로
 5-2. 번역 Glossary 동적 추가/삭제 기능 이식 [이식]
→ whisperlive_code/manager.py 기반 그대로
 5-3. 사전 갱신 즉시 반영 확인 (다음 전사/번역부터 새 사전 적용)

완료 기준

운용 중 사전 수정 후 다음 발화부터 즉시 반영됨
Glossary 등록 단어가 번역에 반영됨


Phase 6 — 폐쇄망 배포 검증
목표
개발 환경(RTX 3080)에서 검증된 코드를 폐쇄망(RTX 5090)으로 이식하고
실제 마이크 입력으로 전체 파이프라인을 최종 검증한다.
태스크

 6-1. 폐쇄망용 모델 디렉터리 레이아웃 및 배포 패키징 형태 결정 [설계 세션]
 6-2. uv로 오프라인 설치용 wheel 패키징
 6-3. STT 모델(whisper-large-v3-turbo) + OSS 20B LLM 가중치 파일 이동/배포 준비
 6-4. HF_HUB_OFFLINE=1, TRANSFORMERS_OFFLINE=1 등 오프라인 환경변수 설정 확인
 6-5. 폐쇄망 RTX 5090 환경으로 코드·모델 이식
 6-6. 실제 마이크 입력으로 한·영 전사 및 번역 동작 확인
 6-7. 성능 확인 (지연 시간 측정 — 목표 수치는 실측 후 결정)

완료 기준

폐쇄망에서 외부 연결 없이 전체 시스템 동작
실제 마이크 입력으로 한·영 전사·번역이 정상 동작
지연 시간 측정 결과 기록 (수치 기준은 실측 후 별도 정의)


추후 결정 항목 (현재 비활성)

녹음 제어 API (시작 / 정지 / 상태 조회)
디버깅용 로그 파일 저장
hotwords / initial_prompt 주입 기능
