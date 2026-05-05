"""
Graph 工具函数（兼容层）。

实际配置与 LLM 初始化逻辑已迁移至 ``tradingagents.config``。
本文件保留公开 API 以避免下游 import 断裂，内部委托至新模块。
"""

from __future__ import annotations

from tradingagents.config import (
    create_chroma_memory_if_available,
    get_graph_debate_rounds as _get_rounds,
    get_llm,
)


def load_llm_from_config(
    config_path: str = "config/config.yaml",
    llm_profile: str | None = None,
    llm_model: str | None = None,
    llm_temperature: float | None = None,
):
    """Wrapper — delegates to ``tradingagents.config.get_llm`` with optional overrides."""
    return get_llm(
        config_path,
        profile=llm_profile,
        model_override=llm_model,
        temperature_override=llm_temperature,
    )


def load_graph_debate_rounds(config_path=None):
    """Backward-compatible wrapper — delegates to ``tradingagents.config.get_graph_debate_rounds``."""
    return _get_rounds(config_path)


__all__ = [
    "load_llm_from_config",
    "load_graph_debate_rounds",
    "create_chroma_memory_if_available",
]
