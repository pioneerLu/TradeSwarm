from typing import TypedDict, List, Optional, Literal, Union, Any

class ValidityFactor(TypedDict):
    factor: str  # e.g., "rsi_14", "volume_ratio"
    condition: str  # e.g., "< 70", "> 1.2"

class ExecutionParameters(TypedDict):
    trigger_condition: str  # e.g., "price > ma_20"
    buy_limit_price: Optional[float]  # Max price to buy
    stop_loss_price: float  # Hard stop loss
    take_profit_price: float  # Take profit target
    position_size_pct: float  # 0.0 to 1.0
    max_holding_time_mins: Optional[int]  # Max holding time in minutes

class ExecutionPlan(TypedDict):
    target_symbol: str
    direction: Literal["long", "short", "hold"]
    strategy_id: str  # e.g., "breakout_ma_v1"
    parameters: ExecutionParameters
    validity_factors: List[ValidityFactor]
    expiration: str  # HH:MM:SS

class ExecutionLogEntry(TypedDict):
    timestamp: str
    action: Literal["buy", "sell", "hold", "cancel"]
    price: float
    volume: float
    reason: str
    pnl: Optional[float]  # Realized PnL for sell actions

class ExecutionLog(TypedDict):
    entries: List[ExecutionLogEntry]
    summary: str # Brief summary of the day's execution
