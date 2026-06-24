"""
基于 ChromaDB + Embedding 的长期记忆与公司知识库真实实现。
所有 ChromaDB 同步操作通过 asyncio.to_thread 包装，避免阻塞事件循环。
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import chromadb

from agent.tools import CompanyKB, MemoryStore
from core.config import Settings, get_settings
from core.embeddings import EmbeddingClient

logger = logging.getLogger(__name__)


def _init_embedding(settings: Settings) -> Optional[EmbeddingClient]:
    """优先使用配置的真实 embedding API；未配置则降级到 ChromaDB 默认 embedding"""
    has_key = bool(
        settings.embedding_api_key
        or settings.cloud_api_key
        or settings.openai_api_key
    )
    if has_key and settings.embedding_base_url:
        try:
            return EmbeddingClient(settings)
        except Exception as e:
            logger.warning(f"EmbeddingClient 初始化失败，降级到默认 embedding: {e}")
    return None


class ChromaMemoryStore(MemoryStore):
    """基于 ChromaDB + 真实 embedding 的员工长期记忆存储"""

    def __init__(
        self,
        collection_name: str = "employee_memories",
        persist_dir: Optional[str] = None,
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or get_settings()
        self.persist_dir = persist_dir or self.settings.vector_store_dir
        self.embedding = _init_embedding(self.settings)

        self.client = chromadb.PersistentClient(path=self.persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    async def get_employee_history(
        self,
        employee_id: str,
        period: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """向量检索员工历史记忆（排除当前周期）"""
        query = f"员工 {employee_id} 历史评估记忆"
        query_kwargs: Dict[str, Any] = {"n_results": limit, "include": ["metadatas", "documents", "distances"]}

        where: Dict[str, Any] = {"employee_id": employee_id}
        if period:
            where["period"] = {"$ne": period}
        query_kwargs["where"] = where

        if self.embedding:
            query_kwargs["query_embeddings"] = [await self.embedding.embed_query(query)]
        else:
            query_kwargs["query_texts"] = [query]

        try:
            results = await asyncio.to_thread(self.collection.query, **query_kwargs)
        except Exception as e:
            logger.warning(f"Chroma 记忆查询失败: {e}")
            return []

        memories = []
        metadatas = results.get("metadatas", [[]])[0]
        documents = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for meta, doc, distance in zip(metadatas, documents, distances):
            if not meta:
                continue
            payload = meta.get("payload")
            if payload:
                try:
                    memory = json.loads(payload)
                except json.JSONDecodeError:
                    memory = {"summary": doc, **meta}
            else:
                memory = {"summary": doc, **meta}
            memory["_retrieval_score"] = 1.0 - float(distance or 0.0)
            memories.append(memory)
        return memories

    async def add_memory(self, employee_id: str, memory: Dict[str, Any]) -> None:
        """添加/更新一条员工记忆，并写入真实向量"""
        period = memory.get("period", "unknown")
        doc_id = f"{employee_id}-{period}"
        document = json.dumps(memory, ensure_ascii=False)

        upsert_kwargs: Dict[str, Any] = {
            "ids": [doc_id],
            "documents": [document],
            "metadatas": [
                {
                    "employee_id": employee_id,
                    "period": period,
                    "payload": document,
                }
            ],
        }

        if self.embedding:
            try:
                upsert_kwargs["embeddings"] = [await self.embedding.embed_query(document)]
            except Exception as e:
                logger.error(f"记忆 embedding 失败，跳过写入: {e}")
                raise

        await asyncio.to_thread(self.collection.upsert, **upsert_kwargs)


class ChromaCompanyKB(CompanyKB):
    """基于 ChromaDB + 真实 embedding 的公司知识库 RAG"""

    def __init__(
        self,
        collection_name: str = "company_kb",
        persist_dir: Optional[str] = None,
        settings: Optional[Settings] = None,
    ):
        self.settings = settings or get_settings()
        self.persist_dir = persist_dir or self.settings.vector_store_dir
        self.embedding = _init_embedding(self.settings)

        self.client = chromadb.PersistentClient(path=self.persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    async def query(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """向量检索公司知识库"""
        query_kwargs: Dict[str, Any] = {"n_results": top_k, "include": ["metadatas", "documents", "distances"]}
        if self.embedding:
            query_kwargs["query_embeddings"] = [await self.embedding.embed_query(query)]
        else:
            query_kwargs["query_texts"] = [query]
        try:
            results = await asyncio.to_thread(self.collection.query, **query_kwargs)
        except Exception as e:
            logger.warning(f"Chroma KB 查询失败: {e}")
            return []

        docs = []
        metadatas = results.get("metadatas", [[]])[0]
        documents = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for meta, doc, distance in zip(metadatas, documents, distances):
            if not meta:
                continue
            docs.append(
                {
                    "kb_id": meta.get("kb_id", ""),
                    "title": meta.get("title", ""),
                    "content": doc or meta.get("content", ""),
                    "metadata": meta.get("metadata", {}),
                    "_retrieval_score": 1.0 - float(distance or 0.0),
                }
            )
        return docs

    async def add_document(
        self,
        kb_id: str,
        title: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """向知识库添加文档并生成 embedding"""
        document = f"{title}\n{content}"
        upsert_kwargs: Dict[str, Any] = {
            "ids": [kb_id],
            "documents": [document],
            "metadatas": [
                {
                    "kb_id": kb_id,
                    "title": title,
                    "content": content,
                    "metadata": json.dumps(metadata or {}, ensure_ascii=False),
                }
            ],
        }
        if self.embedding:
            try:
                upsert_kwargs["embeddings"] = [await self.embedding.embed_query(document)]
            except Exception as e:
                logger.error(f"KB embedding 失败，跳过写入: {e}")
                raise
        await asyncio.to_thread(self.collection.upsert, **upsert_kwargs)

