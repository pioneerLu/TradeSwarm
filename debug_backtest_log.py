"""
回测诊断日志模块

将关键节点的决策信息写入临时日志文件，便于追踪 HOLD 根因。
"""
from pathlib import Path
from datetime import datetime
from typing import Optional

_LOG_FILE: Optional[Path] = None


def set_log_file(path: str | Path) -> None:
    """设置日志文件路径"""
    global _LOG_FILE
    _LOG_FILE = Path(path)
    _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _LOG_FILE.write_text(
        f"=== Backtest Debug Log {datetime.now().isoformat()} ===\n\n",
        encoding="utf-8",
    )


def log(trade_date: str, symbol: str, stage: str, data: dict) -> None:
    """写入一条诊断日志"""
    global _LOG_FILE
    if _LOG_FILE is None:
        return
    line = f"[{trade_date}] [{symbol}] [{stage}] {data}\n"
    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
