# 번역 모델 서빙 환경 설정

## 개요

Phase 4에서 이식된 LLM 번역 파이프라인은 두 환경을 지원한다.

| 환경 | 모델 | 서빙 도구 | 엔드포인트 | 서버 타입 |
|------|------|-----------|------------|-----------|
| 배포 (폐쇄망, RTX 5090) | gpt-oss-20b (gpt-oss-20b-F16.gguf) | llama.cpp | `http://localhost:2010` | `llama` |
| 개발 (RTX 3080) | qwen2.5:7b (Ollama) | Ollama | `http://localhost:11434` | `ollama` |

## 개발 환경 (qwen2.5:7b via Ollama)

### 전제조건
- Ollama 설치됨
- `ollama pull qwen2.5:7b` 완료

### 서버 기동
```bash
# Ollama 서비스 실행 (이미 실행 중이면 불필요)
ollama serve

# 번역 활성화하여 WLK 서버 기동
uv run wlk serve \
  --model large-v3-turbo \
  --llm-translation \
  --translation-serve ollama \
  --translation-endpoint http://localhost:11434 \
  --translation-model qwen2.5:7b
```

### 주의사항
- Windows에서 한글 전송 시 curl 인코딩 깨짐. httpx + ensure_ascii=False 로 처리됨..
- Ollama는 `/v1/chat/completions` (messages 형식). harmony 채널 태그 미사용.

## 배포 환경 (gpt-oss-20b via llama.cpp)

### 전제조건
- `gpt-oss-20b-F16.gguf` 모델 파일 배치
- `start_oss.bat` 더블클릭으로 llama.cpp 서버 기동 (포트 2010)

### 서버 기동
```bash
# start_oss.bat 실행 후 (llama.cpp :2010 서빙 대기)
wlk serve \
  --model large-v3-turbo \
  --llm-translation \
  --translation-serve llama \
  --translation-endpoint http://localhost:2010 \
  --translation-model gpt-oss-20b
```

### 주의사항
- gpt-oss-20b는 `/v1/completions` (harmony 채널 태그 형식). messages 미사용.
- RTX 5090 환경에서만 gpt-oss-20b-F16.gguf (~40GB) 적재 가능.

## config.yaml 예시 (개발 환경)

```yaml
# 번역 설정 예시 (CLI 인자로 직접 전달 또는 환경변수 설정)
translation:
  enabled: true
  serve: ollama          # "llama" for prod
  endpoint: http://localhost:11434   # http://localhost:2010 for prod
  model: qwen2.5:7b      # gpt-oss-20b for prod
```

## 번역 없이 전사만 실행

```bash
# --llm-translation 플래그 없이 기동 시 번역 비활성 (기본값)
uv run wlk serve --model large-v3-turbo
```
