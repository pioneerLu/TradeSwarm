"""
统一 Memory 接口，支持 ChromaDB 语义召回 + cycle_reflections fallback。

当 ChromaDB 可用且有数据时，优先使用语义相似度召回；
否则回退到 cycle_reflections 表按时间顺序取最近 N 条。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from tradingagents.agents.utils.memory_db_helper import MemoryDBHelper


def _build_recommendation_from_reflection(r: Dict[str, Any]) -> str:
    """从 cycle_reflection 记录构造 recommendation 文本"""
    parts = []
    if r.get("key_insights"):
        parts.append(f"关键洞察：{r['key_insights']}")
    if r.get("error_patterns"):
        parts.append(f"错误模式：{r['error_patterns']}")
    if r.get("success_patterns"):
        parts.append(f"成功模式：{r['success_patterns']}")
    if r.get("strategy_conditions"):
        parts.append(f"策略适用条件：{r['strategy_conditions']}")
    if r.get("environment_biases"):
        parts.append(f"环境判断偏差：{r['environment_biases']}")
    return "\n".join(parts) if parts else "无结构化反思内容。"


class HybridMemory:
    """
    统一 past_memory_str 召回：ChromaDB 优先，cycle_reflections fallback。
    """

    def __init__(
        self,
        db_path: str,
        symbol: str,
        chroma_memory: Optional[Any] = None,
        limit: int = 5,
    ) -> None:
        self.db_helper = MemoryDBHelper(db_path)
        self.symbol = symbol
        self.limit = limit
        self.chroma_memory = chroma_memory

    def get_memories(self, current_situation: str, n_matches: int = 3) -> List[Dict[str, Any]]:
        """优先 ChromaDB 语义召回，空则 fallback 到 cycle_reflections"""
        # 1. 若配置了 ChromaDB，优先语义召回
        if self.chroma_memory and hasattr(self.chroma_memory, "get_memories"):
            try:
                chroma_results = self.chroma_memory.get_memories(current_situation, n_matches=n_matches)
                if chroma_results:
                    return chroma_results
            except Exception:
                pass

        # 2. Fallback：从 cycle_reflections 读取
        try:
            reflections = self.db_helper.query_cycle_reflections_by_symbol(
                symbol=self.symbol,
                cycle_type="weekly",
                limit=max(self.limit, n_matches),
            )
            if not reflections:
                return []

            memories = []
            for r in reflections[:n_matches]:
                recommendation = _build_recommendation_from_reflection(r)
                matched_situation = f"周期 {r.get('cycle_start_date', '')} ~ {r.get('cycle_end_date', '')}"
                memories.append({
                    "matched_situation": matched_situation,
                    "recommendation": recommendation,
                    "similarity_score": 0.8,
                })
            return memories
        except Exception:
            return []

    def close(self) -> None:
        self.db_helper.close()
