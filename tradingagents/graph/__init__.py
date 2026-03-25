"""
Graph 模块

提供完整的交易决策图构建功能。

同时导出:
    - create_trading_graph: 创建完整的交易决策图（惰性导入，需安装 langgraph）
    - load_llm_from_config: 从配置文件加载 LLM（不依赖 langgraph）

仅使用 ``load_llm_from_config`` 的脚本（如 ``build_analyst_dataset.py``）不应因在顶层导入
``create_trading_graph`` 而被迫安装 langgraph。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = [
    "create_trading_graph",
    "load_llm_from_config",
]


def __getattr__(name: str) -> Any:
    if name == "create_trading_graph":
        from tradingagents.graph.trading_graph import create_trading_graph as _cg

        return _cg
    if name == "load_llm_from_config":
        from tradingagents.graph.utils import load_llm_from_config as _ll

        return _ll
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if TYPE_CHECKING:
    from tradingagents.graph.trading_graph import create_trading_graph
    from tradingagents.graph.utils import load_llm_from_config
