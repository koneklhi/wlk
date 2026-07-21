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

        import 실패(패키지 미설치)·로드 실패(파일 손상 등) 모두 여기서 잡아 조용히
        비활성화한다. 절대 예외를 상위로 던지지 않는다(서버 기동을 막으면 안 됨).
        """
        try:
            from qdrant_client import QdrantClient
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            logger.warning(
                "Translation RAG disabled: qdrant-client/sentence-transformers import failed (%s). "
                "배포 PC에 `translation-rag` extra가 설치돼 있는지 확인하라.",
                e,
            )
            return

        try:
            self._embedder = SentenceTransformer(self.embedding_model_path)
            self._client = QdrantClient(path=self.qdrant_path)
            self._enabled = True
        except Exception as e:
            logger.warning("Translation RAG disabled: failed to load embedder/client (%s)", e)
            self._embedder = None
            self._client = None
            self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def search_similar(self, content: str) -> str:
        """content와 유사한 기존 번역 예시를 검색해 프롬프트 블록 문자열로 반환.

        비활성 상태이거나 content가 빈 문자열이면 빈 문자열을 반환한다(예외 없음).

        주의(배포 PC 검증 필요): qdrant-client의 구 API인 `client.search()`를 사용한다.
        광범위한 버전 호환을 위한 선택이나, 배포 PC의 qdrant-client 버전이 1.12+ 계열이라
        `search()`가 제거/deprecated됐다면 `client.query_points()`로 교체해야 한다.

        payload 파싱: 기존 Qdrant 컬렉션은 langchain의 Qdrant vectorstore로 색인됐으므로
        payload가 `{"page_content": ..., "metadata": {"source": ..., "target": ...}}` 형태로
        중첩돼 있을 가능성이 높다(langchain-qdrant 기본 `metadata_payload_key="metadata"`).
        `hit.payload.get("metadata", hit.payload)`로 중첩 유무를 방어적으로 처리한다.
        """
        if not self._enabled or not content:
            return ""

        try:
            vector = self._embedder.encode(content).tolist()
            hits = self._client.search(
                collection_name=self.collection_name,
                query_vector=vector,
                limit=self.top_k,
            )

            lines = []
            for hit in hits:
                payload = hit.payload or {}
                data = payload.get("metadata", payload)
                source = data.get("source", "")
                target = data.get("target", "")
                if source and target:
                    lines.append(f"{source} : {target}")

            if not lines:
                return ""

            return "### SIMILAR EXAMPLES (RAG)\n" + "\n".join(lines)
        except Exception as e:
            if not self._warned:
                logger.warning("Translation RAG search_similar failed, suppressing further warnings: %s", e)
                self._warned = True
            return ""
