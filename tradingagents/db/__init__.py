"""
统一数据库访问层。

所有对 ``memory.db`` 的访问都应通过本模块，不再散落在各处。

Public API::

    from tradingagents.db import MemoryDBHelper, get_connection

"""

from tradingagents.db.connection import get_connection
from tradingagents.db.memory_db import MemoryDBHelper

__all__ = ["MemoryDBHelper", "get_connection"]
