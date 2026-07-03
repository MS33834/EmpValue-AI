"""
异步评估任务队列抽象

历史背景:routes.py 原先用模块级 Dict 存 job 状态,导致只能单实例运行。
本模块抽取出 JobQueue 接口,提供 InMemory(测试/本地)与 Redis(多实例生产)两套实现,
解除单实例约束。create_job_queue 按 settings.redis_url 自动选择,Ruby 不可达时降级内存。
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# 模块级暴露 redis 客户端入口,便于测试 monkeypatch;
# 真正 import 失败(未装 redis)时降级为 None,工厂会回退到 InMemoryJobQueue。
try:
    import redis as redis_sync  # noqa: F401
    import redis.asyncio as redis_asyncio  # noqa: F401
except ImportError:  # pragma: no cover - redis 在 requirements 中,仅兜底
    redis_sync = None  # type: ignore[assignment]
    redis_asyncio = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class JobQueue(ABC):
    """任务队列抽象:语义对齐原 job_store 的 Dict 行为(get 返回 None 表示不存在)"""

    @abstractmethod
    async def enqueue(self, job_id: str, job_info: Dict[str, Any]) -> None:
        """整体写入一条任务(等同 job_store[job_id] = job_info)"""

    @abstractmethod
    async def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        """读取任务,不存在返回 None"""

    @abstractmethod
    async def update(self, job_id: str, job_info: Dict[str, Any]) -> None:
        """浅合并更新任务字段并刷新 updated_at(对齐原 _update_job 行为)"""

    @abstractmethod
    async def list_active(self) -> List[Dict[str, Any]]:
        """列出未完结(pending/running)任务,供运维巡检"""

    @abstractmethod
    async def delete(self, job_id: str) -> None:
        """删除任务"""

    @abstractmethod
    async def clear(self) -> None:
        """清空全部任务(测试间状态隔离用)"""


class InMemoryJobQueue(JobQueue):
    """内存实现:行为与原模块级 job_store Dict 完全一致,测试与本地开发默认使用"""

    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}

    async def enqueue(self, job_id: str, job_info: Dict[str, Any]) -> None:
        self._store[job_id] = job_info

    async def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        # 返回引用而非拷贝,保持与原 Dict.get 一致的就地变更语义
        return self._store.get(job_id)

    async def update(self, job_id: str, job_info: Dict[str, Any]) -> None:
        job = self._store.get(job_id)
        if not job:
            return
        job.update(job_info)
        job["updated_at"] = datetime.now(timezone.utc).isoformat()

    async def list_active(self) -> List[Dict[str, Any]]:
        return [
            j for j in self._store.values() if j.get("status") in ("pending", "running")
        ]

    async def delete(self, job_id: str) -> None:
        self._store.pop(job_id, None)

    async def clear(self) -> None:
        self._store.clear()


class RedisJobQueue(JobQueue):
    """Redis 实现:多实例共享任务状态,key 前缀 empvalue:job:

    所有操作包 try/except:Redis 故障时仅记日志不抛异常,避免拖垮评估主流程
    (任务状态查询失败远比阻断评估可接受)。
    """

    KEY_PREFIX = "empvalue:job:"

    def __init__(self, redis_url: str) -> None:
        self._client = redis_asyncio.from_url(redis_url, decode_responses=True)

    def _key(self, job_id: str) -> str:
        return f"{self.KEY_PREFIX}{job_id}"

    async def enqueue(self, job_id: str, job_info: Dict[str, Any]) -> None:
        try:
            await self._client.set(self._key(job_id), json.dumps(job_info, default=str))
        except Exception as e:
            logger.warning("Redis enqueue 失败 job_id=%s: %s", job_id, e)

    async def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        try:
            raw = await self._client.get(self._key(job_id))
            return json.loads(raw) if raw else None
        except Exception as e:
            logger.warning("Redis get 失败 job_id=%s: %s", job_id, e)
            return None

    async def update(self, job_id: str, job_info: Dict[str, Any]) -> None:
        try:
            job = await self.get(job_id)
            if not job:
                return
            job.update(job_info)
            job["updated_at"] = datetime.now(timezone.utc).isoformat()
            await self._client.set(self._key(job_id), json.dumps(job, default=str))
        except Exception as e:
            logger.warning("Redis update 失败 job_id=%s: %s", job_id, e)

    async def list_active(self) -> List[Dict[str, Any]]:
        try:
            keys = await self._client.keys(f"{self.KEY_PREFIX}*")
            jobs: List[Dict[str, Any]] = []
            for k in keys:
                raw = await self._client.get(k)
                if not raw:
                    continue
                job = json.loads(raw)
                if job.get("status") in ("pending", "running"):
                    jobs.append(job)
            return jobs
        except Exception as e:
            logger.warning("Redis list_active 失败: %s", e)
            return []

    async def delete(self, job_id: str) -> None:
        try:
            await self._client.delete(self._key(job_id))
        except Exception as e:
            logger.warning("Redis delete 失败 job_id=%s: %s", job_id, e)

    async def clear(self) -> None:
        try:
            keys = await self._client.keys(f"{self.KEY_PREFIX}*")
            if keys:
                await self._client.delete(*keys)
        except Exception as e:
            logger.warning("Redis clear 失败: %s", e)


def _can_connect_sync(redis_url: str, timeout: float = 1.0) -> bool:
    """同步探测 Redis 可达性。工厂在模块导入期被调用,此时无事件循环,
    用同步 client 做一次 ping 即可,失败时由调用方降级到内存队列。"""
    if redis_sync is None:
        return False
    try:
        client = redis_sync.from_url(
            redis_url, socket_timeout=timeout, socket_connect_timeout=timeout
        )
        client.ping()
        client.close()
        return True
    except Exception:
        return False


def create_job_queue(settings: Any) -> JobQueue:
    """按 settings.redis_url 选择实现:有 url 且能连通用 Redis,否则降级内存。

    降级而非崩溃是关键:本地开发或 CI 无 Redis 时也能正常启动。
    """
    redis_url = getattr(settings, "redis_url", None)
    if not redis_url:
        return InMemoryJobQueue()
    if _can_connect_sync(redis_url):
        logger.info("任务队列使用 RedisJobQueue: %s", redis_url)
        return RedisJobQueue(redis_url)
    logger.warning("Redis 不可达,降级使用 InMemoryJobQueue: %s", redis_url)
    return InMemoryJobQueue()
