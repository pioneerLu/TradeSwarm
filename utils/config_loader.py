"""
配置加载模块（兼容层）。

实际逻辑已迁移至 ``tradingagents.config``。
保留 ``load_config()`` 以避免外部调用方断裂。
"""

from tradingagents.config import get_config


def load_config():
    """Backward-compatible wrapper — delegates to ``tradingagents.config.get_config``."""
    return get_config()
