"""
Fusion Layer 模块

负责从四个 Analyst 的 Memory Controller 中聚合信息，构建 Fusion State
"""
from tradingagents.agents.utils.agent_states import FusionState, AnalystMemorySummary
from .memory_controller import IMemoryController, BaseMemoryController

__all__ = [
    'FusionState',
    'AnalystMemorySummary',
    'IMemoryController',
    'BaseMemoryController',
]

