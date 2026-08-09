"""LLM 调用结果 SQLite 缓存。"""

from __future__ import annotations

import hashlib
import sqlite3
import time
from pathlib import Path
from typing import Any, ClassVar

from commons.json_codec import dumps


_DEFAULT_MAX_ROWS = 1_000_000
_DEFAULT_EVICT_CHECK_INTERVAL_PUTS = 1000
_DEFAULT_EVICT_CHECK_INTERVAL_SECONDS = 300.0

_SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_cache (
    cache_key      TEXT PRIMARY KEY,
    url            TEXT NOT NULL,
    request_json   TEXT NOT NULL,
    response_data  TEXT NOT NULL,
    response_status TEXT NOT NULL DEFAULT 'success',
    duration_ms     INTEGER NOT NULL DEFAULT 0,
    model          TEXT NOT NULL,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    last_hit_at    TEXT NOT NULL DEFAULT (datetime('now')),
    hit_count      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_llm_cache_created_at ON llm_cache(created_at);
"""


class LLMCache:
    """按请求 URL + payload 缓存模型文本输出。
    为避免锁定，应该通过LLMCache.open()来获取示例，而不要直接使用LLMCache()的实例化方法。
    """

    # 类变量：存储所有已创建的实例 {规范化路径: 实例对象}
    _instances: ClassVar[dict[str, LLMCache]] = {}

    def __init__(
        self,
        db_path: str | Path,
        *,
        max_rows: int = _DEFAULT_MAX_ROWS,
        evict_check_interval_puts: int = _DEFAULT_EVICT_CHECK_INTERVAL_PUTS,
        evict_check_interval_seconds: float = _DEFAULT_EVICT_CHECK_INTERVAL_SECONDS,
    ) -> None:
        self.db_path = str(db_path)
        self.max_rows = max_rows
        self._evict_check_interval_puts = evict_check_interval_puts
        self._evict_check_interval_seconds = evict_check_interval_seconds
        self._puts_since_evict_check = 0
        self._last_evict_check_at = time.monotonic()
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    @classmethod
    def open(cls, db_path: str | Path) -> LLMCache:
        abs_path = str(Path(db_path).resolve())
        if abs_path in cls._instances:
            return cls._instances[abs_path]
        instance = cls(abs_path)
        cls._instances[abs_path] = instance
        return instance

    @staticmethod
    def make_key(url: str, payload: dict[str, Any]) -> str:
        canonical = dumps(
            {"url": url, "payload": payload},
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    def get(self, cache_key: str) -> tuple[str, str, int] | None:
        """读取缓存，返回 ``(response_data, response_status, duration_ms)``；未命中返回 ``None``。"""
        row = self.conn.execute(
            "SELECT response_data, response_status, duration_ms"
            " FROM llm_cache WHERE cache_key=?",
            (cache_key,),
        ).fetchone()
        if row is None:
            return None
        self.conn.execute(
            """
            UPDATE llm_cache
            SET hit_count = hit_count + 1, last_hit_at = datetime('now')
            WHERE cache_key=?
            """,
            (cache_key,),
        )
        self.conn.commit()
        return str(row[0]), str(row[1]), int(row[2])

    def put(
        self,
        cache_key: str,
        *,
        url: str,
        payload: dict[str, Any],
        response_data: str,
        response_status: str,
        duration_ms: int,
        model: str,
    ) -> None:
        request_json = dumps(payload, sort_keys=True)
        self.conn.execute(
            """
            INSERT INTO llm_cache
                (cache_key, url, request_json, response_data, response_status, duration_ms, model)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
                response_data=excluded.response_data,
                response_status=excluded.response_status,
                duration_ms=excluded.duration_ms,
                last_hit_at=datetime('now')
            """,
            (
                cache_key,
                url,
                request_json,
                response_data,
                response_status,
                duration_ms,
                model,
            ),
        )
        self._maybe_evict()
        self.conn.commit()

    def _maybe_evict(self) -> None:
        if self.max_rows <= 0:
            return
        self._puts_since_evict_check += 1
        now = time.monotonic()
        if (
            self._puts_since_evict_check < self._evict_check_interval_puts
            and now - self._last_evict_check_at
            < self._evict_check_interval_seconds
        ):
            return
        self._puts_since_evict_check = 0
        self._last_evict_check_at = now
        self._evict_if_needed()

    def _evict_if_needed(self) -> None:
        row = self.conn.execute("SELECT COUNT(*) FROM llm_cache").fetchone()
        count = int(row[0])
        excess = count - self.max_rows
        if excess <= 0:
            return
        self.conn.execute(
            """
            DELETE FROM llm_cache
            WHERE cache_key IN (
                SELECT cache_key FROM llm_cache
                ORDER BY created_at ASC
                LIMIT ?
            )
            """,
            (excess,),
        )

    def close(self) -> None:
        self.conn.close()
