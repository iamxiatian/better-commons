"""LLM 调用结果 SQLite 缓存。

并发说明
--------
- **连接按线程隔离**：sqlite3 连接不可跨线程并发使用，共享同一个连接会导致事务
  状态错乱（``cannot start a transaction within a transaction`` 等）。本模块为每个
  线程维护独立连接，因此可以在 ``asyncio.to_thread`` 线程池等多线程环境中安全使用。
- **启用 WAL**：读写互不阻塞，允许多个进程（如多个 uvicorn worker）共用同一库文件。
- **读操作不写库**：:meth:`LLMCache.get` 为纯读；命中计数先在内存累加，再随淘汰检查
  批量落盘，避免每次命中都产生一次写事务。
"""

from __future__ import annotations

import hashlib
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, ClassVar

import structlog

from commons.json_codec import dumps


_DEFAULT_MAX_ROWS = 1_000_000
_DEFAULT_EVICT_CHECK_INTERVAL_PUTS = 1000
_DEFAULT_EVICT_CHECK_INTERVAL_SECONDS = 300.0
_DEFAULT_BUSY_TIMEOUT_MS = 5000
# 内存中待回写的命中计数键数上限，超过即强制落盘，避免键空间过大导致内存膨胀
_MAX_PENDING_HIT_KEYS = 10_000

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

logger = structlog.get_logger(__name__)


class LLMCache:
    """按请求 URL + payload 缓存模型输出。

    线程安全：内部按线程维护独立的 sqlite3 连接，可在多线程 / 线程池环境中使用。
    为避免同一进程内产生多个实例（各持一份连接与计数），应通过 :meth:`LLMCache.open`
    获取实例，而不要直接调用构造函数。
    """

    # 类变量：存储所有已创建的实例 {规范化路径: 实例对象}
    _instances: ClassVar[dict[str, LLMCache]] = {}
    _instances_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(
        self,
        db_path: str | Path,
        *,
        max_rows: int = _DEFAULT_MAX_ROWS,
        evict_check_interval_puts: int = _DEFAULT_EVICT_CHECK_INTERVAL_PUTS,
        evict_check_interval_seconds: float = _DEFAULT_EVICT_CHECK_INTERVAL_SECONDS,
        busy_timeout_ms: int = _DEFAULT_BUSY_TIMEOUT_MS,
    ) -> None:
        self.db_path = str(db_path)
        self.max_rows = max_rows
        self.busy_timeout_ms = busy_timeout_ms
        self._evict_check_interval_puts = evict_check_interval_puts
        self._evict_check_interval_seconds = evict_check_interval_seconds
        # 以下状态被多个线程共享，统一由 _state_lock 保护
        self._puts_since_evict_check = 0
        self._last_evict_check_at = time.monotonic()
        self._hit_deltas: dict[str, int] = {}
        self._state_lock = threading.Lock()
        # 每线程连接：threading.local() 持有本线程连接，_connections 记录全部连接以便关闭
        self._local = threading.local()
        self._connections: list[sqlite3.Connection] = []
        self._closed = False

        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        # 立即建连并初始化 schema，尽早暴露路径、权限等问题
        _ = self.conn

    @classmethod
    def open(cls, db_path: str | Path) -> LLMCache:
        """获取（或创建）指定路径的缓存单例。

        加锁保证并发首次创建时不会产生多个实例。
        """
        abs_path = str(Path(db_path).resolve())
        with cls._instances_lock:
            instance = cls._instances.get(abs_path)
            if instance is None:
                instance = cls(abs_path)
                cls._instances[abs_path] = instance
            return instance

    # ---- 连接管理 ----

    @property
    def conn(self) -> sqlite3.Connection:
        """返回**当前线程**专属的 sqlite3 连接，首次访问时惰性创建。"""
        if self._closed:
            raise RuntimeError(f"LLMCache 已关闭: {self.db_path}")
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = self._connect()
            self._local.conn = conn
            with self._state_lock:
                self._connections.append(conn)
        return conn

    def _connect(self) -> sqlite3.Connection:
        # 每个连接只由其创建线程使用（见 conn 属性），线程安全由该约束保证；
        # check_same_thread=False 仅用于允许 close() 在其它线程统一关闭连接。
        conn = sqlite3.connect(
            self.db_path,
            timeout=self.busy_timeout_ms / 1000,
            check_same_thread=False,
        )
        # WAL：读写互不阻塞，多进程共用同一库文件的前提
        try:
            row = conn.execute("PRAGMA journal_mode=WAL").fetchone()
            if row and str(row[0]).lower() != "wal":
                logger.warning(
                    f"启用 WAL 失败，当前 journal_mode={row[0]}",
                    db_path=self.db_path,
                )
        except sqlite3.Error as e:
            logger.warning(f"启用 WAL 失败: {e}", db_path=self.db_path)
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute(f"PRAGMA busy_timeout={int(self.busy_timeout_ms)}")
        conn.executescript(_SCHEMA)
        conn.commit()
        return conn

    @staticmethod
    def make_key(url: str, payload: dict[str, Any]) -> str:
        canonical = dumps(
            {"url": url, "payload": payload},
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    # ---- 读写 ----

    def get(
        self, cache_key: str, trace_id: str | None = None
    ) -> tuple[str, str, int] | None:
        """读取缓存，返回 ``(response_data, response_status, duration_ms)``；未命中返回 ``None``。

        纯读操作：不开启写事务，也不阻塞其他读者。命中计数在内存中累加，
        随后由 :meth:`_flush_hit_stats` 批量落盘。
        """
        try:
            row = self.conn.execute(
                "SELECT response_data, response_status, duration_ms"
                " FROM llm_cache WHERE cache_key=?",
                (cache_key,),
            ).fetchone()
        except Exception as e:
            logger.error(
                f"get cache error, key={cache_key}: {e}", trace_id=trace_id
            )
            return None
        if row is None:
            return None
        self._record_hit(cache_key)
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
        trace_id: str | None = None,
    ) -> None:
        try:
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
            self.conn.commit()
        except Exception as e:
            logger.error(
                f"put cache error, key={cache_key}: {e}", trace_id=trace_id
            )
            return
        # 淘汰检查在事务提交后进行，避免与上面的写事务纠缠
        self._maybe_evict()

    # ---- 命中计数 ----

    def _record_hit(self, cache_key: str) -> None:
        """在内存中累计命中次数；待回写键数超限时批量落盘。"""
        with self._state_lock:
            self._hit_deltas[cache_key] = self._hit_deltas.get(cache_key, 0) + 1
            over_limit = len(self._hit_deltas) >= _MAX_PENDING_HIT_KEYS
        if over_limit:
            self._flush_hit_stats()

    def _flush_hit_stats(self) -> None:
        """把内存中累计的命中计数批量写回数据库；失败仅记日志。"""
        with self._state_lock:
            if not self._hit_deltas:
                return
            pending = self._hit_deltas
            self._hit_deltas = {}
        try:
            self.conn.executemany(
                """
                UPDATE llm_cache
                SET hit_count = hit_count + ?, last_hit_at = datetime('now')
                WHERE cache_key=?
                """,
                [(delta, key) for key, delta in pending.items()],
            )
            self.conn.commit()
        except Exception as e:
            logger.error(f"flush hit stats error: {e}")

    # ---- 淘汰 ----

    def _maybe_evict(self) -> None:
        if self.max_rows <= 0:
            return
        now = time.monotonic()
        with self._state_lock:
            self._puts_since_evict_check += 1
            due = (
                self._puts_since_evict_check >= self._evict_check_interval_puts
                or now - self._last_evict_check_at
                >= self._evict_check_interval_seconds
            )
            if not due:
                return
            self._puts_since_evict_check = 0
            self._last_evict_check_at = now
        # 淘汰与命中计数回写都按“到期”触发，顺带在此刷新计数，避免额外定时器
        self._flush_hit_stats()
        self._evict_if_needed()

    def _evict_if_needed(self) -> None:
        try:
            row = self.conn.execute("SELECT COUNT(*) FROM llm_cache").fetchone()
            count = int(row[0]) if row is not None else 0
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
            self.conn.commit()
        except Exception as e:
            logger.error(f"evict cache error: {e}")

    # ---- 关闭 ----

    def close(self) -> None:
        """回写命中计数、关闭所有线程创建的连接，并把本实例移出单例注册表。"""
        self._flush_hit_stats()
        self._closed = True
        with self._state_lock:
            conns = self._connections
            self._connections = []
        for conn in conns:
            try:
                conn.close()
            except sqlite3.Error as e:
                logger.error(f"close cache connection error: {e}")
        # 关闭后允许再次 open() 得到全新实例，避免复用到已关闭的连接
        abs_path = str(Path(self.db_path).resolve())
        with LLMCache._instances_lock:
            if LLMCache._instances.get(abs_path) is self:
                del LLMCache._instances[abs_path]
