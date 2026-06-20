"""
基于 ChromaDB 的长期记忆存储实现
"""

import json
from typing import Any, Dict, List, Optional

from agent.tools import MemoryStore


class ChromaMemoryStore(MemoryStore):
    """ChromaDB 实现的员工长期记忆"""

    def __init__(self, collection_name: str = "employee_memories", persist_dir: str = "./chroma_db"):
        import chromadb

        self.client = chromadb.PersistentClient(path=persist_dir)
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
        where = {"employee_id": employee_id}
        if period:
            where["period"] = {"$ne": period}

        results = self.collection.query(
            query_embeddings=[[0.0] * 384],  # 占位向量，实际应使用 embedding
            where=where,
            n_results=limit,
            include=["metadatas"],
        )
        memories = []
        for meta in results.get("metadatas", [[]])[0]:
            if meta and "payload" in meta:
                memories.append(json.loads(meta["payload"]))
        return memories

    async def add_memory(self, employee_id: str, memory: Dict[str, Any]) -> None:
        doc_id = f"{employee_id}-{memory.get('period', 'unknown')}"
        self.collection.upsert(
            ids=[doc_id],
            documents=[json.dumps(memory, ensure_ascii=False)],
            metadatas=[{"employee_id": employee_id, "period": memory.get("period", ""), "payload": json.dumps(memory, ensure_ascii=False)}],
        )
