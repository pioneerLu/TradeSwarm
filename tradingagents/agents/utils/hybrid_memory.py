"""
统一 Memory 接口：持久化 Chroma 向量召回 + cycle_reflections SQL 兜底。

- ``memory.mode``（config.yaml）：hybrid | sql_only | chroma_only
- 查询侧对 situation 加「标的 {symbol}。」前缀，与 Reflector 写入 Chroma 的文档前缀对齐（B2）。
- 设置环境变量 ``TRADESWARM_MEMORY_RECALL_LOG`` 为文件路径时，追加 JSONL 观测记录。
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from tradingagents.agents.utils.memory_db_helper import MemoryDBHelper


def build_recommendation_from_cycle_reflection_row(r: Dict[str, Any]) -> str:
    """从 cycle_reflection 行构造 recommendation 文本（与 Chroma 中 recommendation 风格一致）。"""
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


def _recall_query_text(symbol: str, current_situation: str) -> str:
    """B2：与 Reflector 索引中「标的 {symbol}」前缀对齐。"""
    s = (symbol or "").strip()
    prefix = f"标的 {s}。\n" if s else ""
    return prefix + (current_situation or "")


def _append_memory_recall_trace(payload: Dict[str, Any]) -> None:
    path = os.environ.get("TRADESWARM_MEMORY_RECALL_LOG")
    if not path:
        return
    payload = {**payload, "ts": datetime.now(timezone.utc).isoformat()}
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass


class HybridMemory:
    """past_memory_str 召回：Chroma（可选）优先，cycle_reflections 兜底。"""

    def __init__(
        self,
        db_path: str,
        symbol: str,
        chroma_memory: Optional[Any] = None,
        limit: int = 5,
        memory_mode: str = "hybrid",
    ) -> None:
        self.db_helper = MemoryDBHelper(db_path)
        self.symbol = symbol
        self.limit = limit
        self.chroma_memory = chroma_memory
        self.memory_mode = str(memory_mode or "hybrid").strip().lower()
        if self.memory_mode not in ("hybrid", "sql_only", "chroma_only"):
            self.memory_mode = "hybrid"

    def _sql_fallback(self, n_matches: int) -> List[Dict[str, Any]]:
        reflections = self.db_helper.query_cycle_reflections_by_symbol(
            symbol=self.symbol,
            cycle_type="weekly",
            limit=max(self.limit, n_matches),
        )
        if not reflections:
            return []
        memories = []
        for r in reflections[:n_matches]:
            recommendation = build_recommendation_from_cycle_reflection_row(r)
            matched_situation = f"周期 {r.get('cycle_start_date', '')} ~ {r.get('cycle_end_date', '')}"
            memories.append(
                {
                    "matched_situation": matched_situation,
                    "recommendation": recommendation,
                    "similarity_score": 0.8,
                    "source": "cycle_reflections",
                }
            )
        return memories

    def get_memories(self, current_situation: str, n_matches: int = 3) -> List[Dict[str, Any]]:
        query_text = _recall_query_text(self.symbol, current_situation)

        if self.memory_mode == "sql_only":
            out = self._sql_fallback(n_matches)
            _append_memory_recall_trace(
                {
                    "path": "sql_only",
                    "symbol": self.symbol,
                    "n_matches": n_matches,
                    "returned": len(out),
                    "query_len": len(query_text),
                }
            )
            return out

        if self.chroma_memory and self.memory_mode in ("hybrid", "chroma_only"):
            try:
                chroma_results = self.chroma_memory.get_memories(
                    query_text, n_matches=n_matches, symbol=self.symbol
                )
                if chroma_results:
                    _append_memory_recall_trace(
                        {
                            "path": "chroma",
                            "symbol": self.symbol,
                            "n_matches": n_matches,
                            "returned": len(chroma_results),
                            "query_len": len(query_text),
                            "scores": [x.get("similarity_score") for x in chroma_results],
                        }
                    )
                    return chroma_results
            except Exception:
                pass

        if self.memory_mode == "chroma_only":
            _append_memory_recall_trace(
                {
                    "path": "chroma_only_miss",
                    "symbol": self.symbol,
                    "n_matches": n_matches,
                    "returned": 0,
                }
            )
            return []

        out = self._sql_fallback(n_matches)
        _append_memory_recall_trace(
            {
                "path": "sql_fallback",
                "symbol": self.symbol,
                "n_matches": n_matches,
                "returned": len(out),
                "query_len": len(query_text),
            }
        )
        return out

    def close(self) -> None:
        self.db_helper.close()


def create_hybrid_trading_memory(
    db_path: str,
    symbol: str,
    *,
    config_path: Optional[Path] = None,
    limit: int = 5,
) -> HybridMemory:
    """按 config.yaml 的 ``memory.mode`` 与 ``storage.chroma_*`` 构造 HybridMemory。"""
    from tradingagents.config import create_chroma_memory_if_available, get_memory_mode

    path_arg: Optional[str] = str(config_path) if config_path else None
    mode = get_memory_mode(path_arg)
    chroma = None
    if mode != "sql_only":
        chroma = create_chroma_memory_if_available(config_path=path_arg)
    return HybridMemory(
        db_path=db_path,
        symbol=symbol,
        chroma_memory=chroma,
        limit=limit,
        memory_mode=mode,
    )


def backfill_cycle_reflections_to_chroma(
    db_path: str,
    *,
    symbol: Optional[str] = None,
    cycle_type: str = "weekly",
    limit: int = 2000,
    config_path: Optional[Path] = None,
) -> int:
    """
    将 ``cycle_reflections`` 行写入 Chroma（upsert），便于首次启用持久化向量库时补数据。
    返回成功提交条数。
    """
    from tradingagents.config import create_chroma_memory_if_available

    chroma = create_chroma_memory_if_available(config_path=str(config_path) if config_path else None)
    if chroma is None:
        return 0
    helper = MemoryDBHelper(db_path)
    try:
        rows = helper.query_cycle_reflections_backfill(symbol=symbol, cycle_type=cycle_type, limit=limit)
        if not rows:
            return 0
        items = []
        for r in rows:
            sym = r.get("symbol") or ""
            cs, ce = r.get("cycle_start_date", ""), r.get("cycle_end_date", "")
            situation = f"标的 {sym}，周期 {cs}~{ce}。周期反思摘要。"
            rec = build_recommendation_from_cycle_reflection_row(r)
            rid = f"ref_{sym}_{cs}_{ce}"
            items.append(
                (
                    situation,
                    rec,
                    {
                        "symbol": sym,
                        "cycle_start_date": str(cs),
                        "cycle_end_date": str(ce),
                        "id": rid,
                    },
                )
            )
        chroma.add_situations(items)
        return len(items)
    finally:
        helper.close()
