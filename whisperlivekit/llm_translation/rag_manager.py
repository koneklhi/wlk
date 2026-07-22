# -*- coding: utf-8 -*-
"""번역 프롬프트에 주입할 Qdrant 벡터 유사 예시 검색(Stage 2 RAG).

whisperlive_code/translator.py 18-38줄(생성자의 embed/qdrant_client/vector_store 초기화)과
124-130줄(asyncio.to_thread로 감싼 유사도 검색 + EXAMPLES 블록 조립)을 이식한 것이다. 원본은
langchain의 Qdrant/HuggingFaceEmbeddings 래퍼를 썼지만, 여기서는
docs/superpowers/specs/2026-07-16-translation-glossary-design.md §8 결정에 따라 langchain
없이 qdrant-client(로컬 임베디드 모드) + sentence-transformers를 직접 사용한다.
"""

import logging
import os
import threading

logger = logging.getLogger(__name__)


class TranslationRagManager:
    """Qdrant 로컬 임베디드 DB에서 입력 문장과 유사한 기존 번역 예시를 검색한다.

    qdrant_path/embedding_model_path는 폐쇄망 배포 PC에만 실물이 존재하는 로컬 경로다.
    dev 환경처럼 경로가 비어있거나(None) 실제로 존재하지 않으면, 혹은 qdrant-client/
    sentence-transformers 패키지가 설치돼 있지 않거나 로드에 실패하면, 예외를 던지지
    않고 조용히 비활성 상태(enabled=False)로 남는다 — 서버는 RAG 블록 없이 정상 동작한다.
    """

    def __init__(
        self,
        qdrant_path,
        embedding_model_path,
        collection_name: str = "official_translation",
        top_k: int = 3,
    ):
        self.qdrant_path = qdrant_path
        self.embedding_model_path = embedding_model_path
        self.collection_name = collection_name
        self.top_k = top_k

        self._enabled = False
        self._embedder = None
        self._client = None
        self._warned = False
        # search_similar()는 asyncio.to_thread로 호출되고, 한 틱에 확정된 문장이 여러 개면
        # 여러 스레드가 동시에 들어온다. QdrantClient 로컬 임베디드 모드와 SentenceTransformer는
        # 스레드 안전이 보장되지 않으므로 인코딩+검색 구간을 직렬화한다(top_k=3 조회라 비용은 무시 가능).
        self._search_lock = threading.Lock()

        if not qdrant_path or not embedding_model_path:
            logger.warning(
                "Translation RAG disabled: qdrant_path/embedding_model_path not provided "
                "(qdrant_path=%r, embedding_model_path=%r)",
                qdrant_path,
                embedding_model_path,
            )
            return

        if not os.path.exists(qdrant_path) or not os.path.exists(embedding_model_path):
            logger.warning(
                "Translation RAG disabled: path does not exist on disk "
                "(qdrant_path=%r exists=%s, embedding_model_path=%r exists=%s)",
                qdrant_path,
                os.path.exists(qdrant_path),
                embedding_model_path,
                os.path.exists(embedding_model_path),
            )
            return

        self._try_load()

    def _try_load(self) -> None:
        """qdrant-client/sentence-transformers를 지연 import 후 모델/클라이언트 로드.

        import 실패·로드 실패 모두 여기서 잡아 조용히 비활성화한다. **절대 예외를 상위로
        던지지 않는다** — 이 함수는 서버 기동 경로(TranscriptionEngine 생성)에서 불리므로
        예외가 새면 폐쇄망에서 서버가 아예 뜨지 않는다.

        `except ImportError`가 아니라 `except Exception`인 이유: 미설치만이 아니라 torch DLL
        로드 실패(OSError WinError 126), transformers/tokenizers 버전 스큐(RuntimeError·
        AttributeError), pydantic v1/v2 스큐(TypeError) 등 **ImportError가 아닌 import 시점
        예외**가 폐쇄망 wheelhouse에서 실제로 터질 수 있다. RAG는 부가 기능이므로 어떤 이유로
        못 뜨든 전사·번역 본체를 죽여선 안 된다.
        """
        try:
            from qdrant_client import QdrantClient
            from sentence_transformers import SentenceTransformer
        except Exception as e:
            logger.warning(
                "Translation RAG disabled: qdrant-client/sentence-transformers import failed (%s: %s). "
                "배포 PC에 `translation-rag` extra가 설치돼 있는지 확인하라.",
                type(e).__name__,
                e,
            )
            return

        try:
            self._embedder = self._load_embedder(SentenceTransformer)
            self._client = QdrantClient(path=self.qdrant_path)
            self._enabled = True

            try:
                existing = [c.name for c in self._client.get_collections().collections]
                logger.warning(
                    "[RagProbe] startup: qdrant collections found=%r (expected collection_name=%r)",
                    existing,
                    self.collection_name,
                )
            except Exception as e:
                logger.warning("[RagProbe] startup: get_collections() probe failed (%s: %s)", type(e).__name__, e)
        except Exception as e:
            logger.warning(
                "Translation RAG disabled: failed to load embedder/client (%s: %s)", type(e).__name__, e
            )
            self._embedder = None
            self._client = None
            self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _load_embedder(self, sentence_transformer_cls):
        """bge-m3를 **로컬 파일만** 보고 로드한다(폐쇄망 제약 — CLAUDE.md §3.1).

        디렉터리는 있는데 내용이 불완전 복사된 경우(가중치·config.json 누락) 오프라인 강제가
        없으면 로더가 누락 파일을 HF Hub에서 해결하려 시도한다. 폐쇄망에서는 그게 즉시 예외가
        아니라 연결 타임아웃 + 재시도라, 서버 기동이 수 분간 멈춘다.

        `local_files_only` 인자는 sentence-transformers 5.6.0에 실존하지만, 배포 PC에 더 낡은
        버전이 깔려 있을 수 있다(기존 whisperlive가 설치해 둔 것). 그 경우 TypeError가 나므로
        환경변수로 오프라인을 강제한 뒤 인자 없이 재시도한다 — 어느 경로로 가든 네트워크로
        나가지 않는다.
        """
        try:
            return sentence_transformer_cls(self.embedding_model_path, local_files_only=True)
        except TypeError:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            logger.info(
                "Translation RAG: sentence-transformers가 local_files_only를 받지 않아 "
                "HF_HUB_OFFLINE=1로 대체한다(구버전으로 추정)."
            )
            return sentence_transformer_cls(self.embedding_model_path)

    def _query(self, vector: list) -> list:
        """qdrant-client 신·구 API를 모두 지원해 유사 벡터 상위 top_k를 반환한다.

        구 API `client.search()`는 1.12+ 계열에서 제거/deprecated됐고, 신 API
        `client.query_points()`는 그 이전 버전에 없다. 배포 PC에 어떤 버전이 깔려 있는지
        dev에서 확인할 수 없으므로 신 API를 먼저 시도하고 없으면 구 API로 내려간다.
        (버전 고정으로 풀지 않는 이유: 배포 PC의 qdrant-client는 기존 whisperlive가 이미
        설치해 쓰고 있어 우리가 버전을 고를 수 없다.)
        """
        query_points = getattr(self._client, "query_points", None)
        if query_points is not None:
            response = query_points(
                collection_name=self.collection_name,
                query=vector,
                limit=self.top_k,
            )
            # QueryResponse.points — 혹시 리스트를 그대로 주는 구현이면 그대로 쓴다.
            return getattr(response, "points", response)

        return self._client.search(
            collection_name=self.collection_name,
            query_vector=vector,
            limit=self.top_k,
        )

    def search_similar(self, content: str) -> str:
        """content와 유사한 기존 번역 예시를 검색해 프롬프트 블록 문자열로 반환.

        비활성 상태이거나 content가 빈 문자열이면 빈 문자열을 반환한다(예외 없음).

        qdrant-client 버전 차이는 `_query()`가 흡수한다(신 API `query_points` 우선, 구 API
        `search` 폴백) — 배포 PC 버전을 몰라도 동작한다.

        payload 파싱: 기존 Qdrant 컬렉션은 langchain의 Qdrant vectorstore로 색인됐으므로
        payload가 `{"page_content": ..., "metadata": {"source": ..., "target": ...}}` 형태로
        중첩돼 있을 가능성이 높다(langchain-qdrant 기본 `metadata_payload_key="metadata"`).
        `hit.payload.get("metadata", hit.payload)`로 중첩 유무를 방어적으로 처리한다.
        """
        if not self._enabled or not content:
            logger.warning(
                "[RagProbe] search_similar skipped: enabled=%s content_empty=%s",
                self._enabled, not content,
            )
            return ""

        try:
            with self._search_lock:
                vector = self._embedder.encode(content).tolist()
                hits = self._query(vector)

            lines = []
            for hit in hits:
                payload = hit.payload or {}
                data = payload.get("metadata", payload)
                source = data.get("source", "")
                target = data.get("target", "")
                if source and target:
                    lines.append(f"{source} : {target}")

            logger.warning(
                "[RagProbe] search_similar ok: hits=%d valid_pairs=%d sample_payload=%r",
                len(hits), len(lines), (hits[0].payload if hits else None),
            )

            if not lines:
                return ""

            return "### SIMILAR EXAMPLES (RAG)\n" + "\n".join(lines)
        except Exception as e:
            logger.warning("[RagProbe] search_similar EXCEPTION: %s: %s", type(e).__name__, e)
            if not self._warned:
                logger.warning("Translation RAG search_similar failed, suppressing further warnings: %s", e)
                self._warned = True
            return ""
