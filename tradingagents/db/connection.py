"""
数据库连接工厂。

替代旧的 ``init_db.py`` 全局 ``conn`` / ``cursor`` 反模式，
提供线程安全的连接获取方式。
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator


_thread_local = threading.local()


def get_connection(db_path: str | Path = "memory.db") -> sqlite3.Connection:
    """Return a thread-local SQLite connection for *db_path*.

    Each thread gets at most one connection per *db_path* (cached on
    ``threading.local``).  Callers that need explicit lifecycle control
    should use :func:`connect` instead.
    """
    key = f"_conn_{Path(db_path).resolve()}"
    conn = getattr(_thread_local, key, None)
    if conn is None:
        conn = sqlite3.connect(str(db_path))
        setattr(_thread_local, key, conn)
    return conn


@contextmanager
def connect(db_path: str | Path = "memory.db") -> Generator[sqlite3.Connection, None, None]:
    """Context-managed one-off connection (closed on exit)."""
    conn = sqlite3.connect(str(db_path))
    try:
        yield conn
    finally:
        conn.close()
