"""
Social Media Analyst Agent 模块

该模块提供社交媒体情绪和新闻分析功能，用于分析过去一周的社交媒体帖子、
公司新闻和公众情绪。Agent 会生成详细的综合分析报告，为交易决策提供支持。

主要导出:
    - create_social_media_analyst: 创建 social media analyst agent 节点的工厂函数
    - SocialMediaAnalystState: Agent 状态的类型定义
"""

from .agent import create_social_media_analyst
from .state import SocialMediaAnalystState

__all__ = [
    "create_social_media_analyst",
    "SocialMediaAnalystState",
]
