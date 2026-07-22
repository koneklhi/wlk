# 번역 RAG(Stage 2) 오프라인 설치 wheel

폐쇄망 배포 PC의 **wlk 전용 Python 3.12**(`C:\Python312`)에 Qdrant RAG 의존성을 설치하기 위한
wheel 묶음이다. 기존 whisperlive가 Qdrant를 쓰고 있었더라도 그건 whisperlive가 쓰던 인터프리터
기준이므로, wlk 인터프리터에도 들어 있는지는 별개 문제다 — 없으면 RAG가 **조용히 비활성화**된다
(서버는 정상 기동하므로 눈치채기 어렵다).

기능·경로·활성 조건은 [docs/DEPLOYMENT_OFFLINE.md](../../docs/DEPLOYMENT_OFFLINE.md) §6.3이 정본이다.

## 1. 담긴 것과 담기지 않은 것

**담긴 것 — wlk 환경에 아직 없는 것만** (7개, 7.7MB):

| wheel | 역할 |
|---|---|
| `qdrant_client-1.18.0-py3-none-any.whl` | 벡터 검색 클라이언트(로컬 임베디드 모드) |
| `sentence_transformers-5.6.0-py3-none-any.whl` | bge-m3 임베딩 로더 |
| `portalocker-3.2.0-py3-none-any.whl` | qdrant 로컬 모드 파일 락 |
| `pywin32-312-cp312-cp312-win_amd64.whl` | portalocker의 Windows 백엔드 |
| `h2-4.3.0-py3-none-any.whl` | `httpx[http2]` extra |
| `hpack-4.2.0-py3-none-any.whl` | h2 의존 |
| `hyperframe-6.1.0-py3-none-any.whl` | h2 의존 |

**담기지 않은 것 — wlk 환경에 이미 있는 것**: `torch`(cu128), `transformers`, `tokenizers`,
`huggingface-hub`, `numpy`, `scipy`, `scikit-learn`, `tqdm`, `httpx`, `pydantic`, `protobuf`,
`grpcio`, `urllib3`, `typing-extensions`.

> **의도적으로 뺐다.** 특히 `torch`·`transformers`·`tokenizers`는 절대 재설치하면 안 된다 —
> sentence-transformers를 의존성까지 통째로 설치하면 CPU 빌드 torch가 cu128을 덮어써 Whisper와
> Sortformer가 죽는다. 아래 §2의 `--no-deps` + 명시 목록이 그걸 막는 장치다.

**호환 확인 완료** (개발 PC 실측, Python 3.12.10 동일):
`sentence-transformers 5.6.0`은 `transformers>=4.41,<6` / `torch>=1.11`을 요구하고, wlk에 설치된
`transformers 4.53.3` / `torch 2.11.0+cu128`이 이를 만족한다 — **업그레이드가 필요 없다**.

## 2. 설치 (배포 PC, 오프라인)

`--no-deps`가 핵심이다. 이걸 빼면 pip이 torch를 다시 끌어온다.

```cmd
cd C:\whist\wlk
C:\Python312\python.exe -m pip install --no-index --no-deps ^
  --find-links wheelhouse\translation-rag ^
  qdrant-client sentence-transformers portalocker pywin32 h2 hpack hyperframe
```

## 3. 설치 확인

```cmd
C:\Python312\python.exe -c "import qdrant_client, sentence_transformers, portalocker; print('import ok')"
```

torch가 그대로인지 **반드시 함께** 확인한다(cu128이 아니면 위 설치가 뭔가를 덮어쓴 것이다):

```cmd
C:\Python312\python.exe -c "import torch, transformers, tokenizers; print(torch.__version__, torch.cuda.is_available(), transformers.__version__, tokenizers.__version__)"
```

기대값: `2.11.0+cu128 True 4.53.3 0.21.4`.

## 4. 활성 확인

자산 디렉터리 2개(`whisperlivekit/llm_translation/local_qdrant_db/`, `.../bge-m3/`)를 제자리에 둔 뒤
서버를 기동하면 로그에 다음이 찍힌다(번역이 켜져 있을 때):

```
Translation RAG(Qdrant) enabled
```

`disabled`가 찍히면 바로 위 `Translation RAG disabled: ...` WARNING이 원인(경로 없음 / import 실패 /
로드 실패)을 알려준다.

## 5. 이 묶음을 다시 만들려면 (개발 PC)

공유 `.venv`에는 pip이 없고, 거기에 pip을 설치하는 것은 CLAUDE.md §4가 금지하는 clobber다.
**시스템 Python 3.12**로 받는다(공유 venv를 건드리지 않는다):

```cmd
set SYSPY=C:\Users\<user>\AppData\Local\Programs\Python\Python312\python.exe
%SYSPY% -m pip download qdrant-client sentence-transformers --no-deps ^
  --only-binary=:all: --python-version 312 --platform win_amd64 -d wheelhouse\translation-rag
%SYSPY% -m pip download portalocker h2 ^
  --only-binary=:all: --python-version 312 --platform win_amd64 -d wheelhouse\translation-rag
```

버전을 올릴 때는 새 `sentence-transformers`의 `Requires-Dist`가 wlk에 설치된
`transformers`/`torch` 범위를 벗어나지 않는지 먼저 확인하라 — 벗어나면 이 묶음만으로는 설치가
성립하지 않고, torch 재설치라는 위험한 경로로 끌려간다.
