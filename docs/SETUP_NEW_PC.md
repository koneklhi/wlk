# 새 PC 개발 환경 셋업

두 번째 PC에서 개발을 이어서 진행하기 위한 절차. 동일 Windows 환경 기준.

---

## 전제 조건

- Git, Python 3.11 이상 설치 확인
- `uv` 패키지 매니저 설치: `pip install uv`
- FFmpeg 시스템 설치 확인 (경로 A 파일 송신에 필요)
  - 확인: `ffmpeg -version`
  - 없으면: `winget install ffmpeg` 또는 공식 사이트에서 수동 설치

---

## 셋업 순서

### 1. 저장소 클론

```
git clone https://github.com/hyungillee/wlk.git
cd wlk
```

### 2. 라이브러리 설치

```
uv sync
```

- `uv.lock` 기준으로 `.venv`가 자동 생성됨
- CUDA 12.8 호환 PyTorch 휠이 자동 설치됨 (별도 CUDA 툴킷 설치 불필요)
- 소요 시간: 수 분 (약 7GB 다운로드)

### 3. 모델 가중치 배치 (수동 복사)

`model.safetensors`(1.6GB)는 GitHub에 없으므로, USB 또는 네트워크 공유로 복사:

```
whisperlivekit\model\whisper-large-v3-turbo\model.safetensors
```

model.safetensors 외 나머지 파일(config.json, tokenizer.json 등)은 git으로 자동 포함.

### 4. GPU 동작 확인

```
uv run python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

`True <GPU 이름>` 이 출력되면 정상.

### 5. 서버 기동 + 스모크 테스트

`docs/TESTING.md` 의 절차를 따라 서버 기동 후 경로 A 스모크 확인.

---

## 이후 일상 동기화

```
# 작업을 마친 PC에서
git push

# 다른 PC로 이동 후
git pull
```

모델 가중치는 한 번 복사하면 재복사 불필요. 코드만 git으로 오감.
