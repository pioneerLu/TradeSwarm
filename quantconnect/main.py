# QUANTCONNECT.COM - TradeSwarm 信号执行算法
# Algorithm Lab 云端无法读项目文件，需将信号嵌入下方 EMBEDDED_SIGNALS

from AlgorithmImports import *
import os
import json
from datetime import datetime, timedelta

# 嵌入信号（Algorithm Lab 必填）：将 qc_signals/signals.json 的 by_execution_date 部分粘贴到下面；
# 实验区间 2025-01-01~2025-03-01，运行 run_signal_export 后粘贴对应内容
EMBEDDED_SIGNALS = {}


class LocalDailyBar(PythonData):
    """读取本地 CSV 日线：date,open,high,low,close,volume"""

    def GetSource(self, config, date, isLiveMode):
        source = os.path.join(Globals.DataFolder, "custom", "nvda_daily.csv")
        return SubscriptionDataSource(
            source,
            SubscriptionTransportMedium.LocalFile,
            FileFormat.Csv
        )

    def Reader(self, config, line, date, isLiveMode):
        if not line or line.startswith("date,"):
            return None
        parts = line.split(",")
        if len(parts) < 6:
            return None
        bar = LocalDailyBar()
        bar.Symbol = config.Symbol
        bar.Time = datetime.strptime(parts[0], "%Y-%m-%d")
        bar.EndTime = bar.Time + timedelta(days=1)
        bar["open"] = float(parts[1])
        bar["high"] = float(parts[2])
        bar["low"] = float(parts[3])
        bar["close"] = float(parts[4])
        bar["volume"] = float(parts[5])
        bar.Value = bar["close"]
        return bar


class TradeSwarmSignalAlgorithm(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2025, 1, 1)
        self.set_end_date(2025, 3, 1)
        self.set_cash(100000)
        self.SetBenchmark(lambda _: 0)

        self.symbol_str = "NVDA"
        self._last_processed_date = None
        self.symbol = None
        self._init_symbol()

        self.signals = self._load_signals()
        if not self.signals:
            self.error("未加载到信号，请确保 signals/signals.json 存在且格式正确")

    def _init_symbol(self):
        use_local = (os.environ.get("TS_LOCAL_DATA", "1").strip() != "0")
        if use_local:
            try:
                custom = self.AddData(LocalDailyBar, "NVDA_LOCAL", Resolution.DAILY)
                self.symbol = custom.Symbol
                self.SetBrokerageModel(BrokerageName.Default, AccountType.Cash)
                self.Debug("使用本地数据 custom/nvda_daily.csv")
                return
            except Exception as e:
                self.Debug(f"本地数据初始化失败，回退 add_equity: {e}")
        self.equity = self.add_equity(self.symbol_str, Resolution.DAILY)
        self.symbol = self.equity.symbol

    def _load_signals(self):
        """优先使用 EMBEDDED_SIGNALS（Algorithm Lab），否则尝试读文件（本地/Lean CLI）"""
        if EMBEDDED_SIGNALS:
            self.debug("使用嵌入信号 EMBEDDED_SIGNALS")
            return EMBEDDED_SIGNALS
        try:
            base = os.path.dirname(os.path.abspath(__file__))
        except Exception:
            base = os.getcwd()
        for path in [
            os.path.join(base, "signals", "signals.json"),
            os.path.join(base, "signals.json"),
            os.path.join(base, "qc_signals", "signals.json"),
        ]:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    return data.get("by_execution_date", data.get("signals", {}))
                except Exception as e:
                    self.error(f"加载信号失败 {path}: {e}")
        return {}

    def on_data(self, data: Slice):
        # 每个交易日仅处理一次信号
        if self.symbol is None or not data.ContainsKey(self.symbol):
            return
        today = self.time.date().isoformat()
        if today == self._last_processed_date:
            return
        self._last_processed_date = today
        signal = self.signals.get(today) if isinstance(self.signals, dict) else None

        if not signal:
            return

        action = (signal.get("action") or "HOLD").upper()
        if action == "HOLD":
            return

        entry_type = (signal.get("entry_type") or "MKT_OPEN").upper()
        entry_price_raw = signal.get("entry_price")
        try:
            entry_price = float(entry_price_raw) if entry_price_raw is not None else None
        except Exception:
            entry_price = None

        if action == "BUY":
            target_pct = float(signal.get("target_pct", 0.5))
            target_pct = max(0.01, min(1.0, target_pct))
            if entry_type == "LIMIT" and entry_price is not None and entry_price > 0:
                qty = self.calculate_order_quantity(self.symbol, target_pct)
                if qty > 0:
                    self.limit_order(self.symbol, qty, entry_price)
                    self.debug(f"[{today}] BUY LIMIT qty={qty} price={entry_price} target_pct={target_pct}")
                else:
                    self.debug(f"[{today}] BUY LIMIT skipped qty={qty}")
            elif entry_type == "STOP" and entry_price is not None and entry_price > 0:
                qty = self.calculate_order_quantity(self.symbol, target_pct)
                if qty > 0:
                    self.stop_market_order(self.symbol, qty, entry_price)
                    self.debug(f"[{today}] BUY STOP qty={qty} stop={entry_price} target_pct={target_pct}")
                else:
                    self.debug(f"[{today}] BUY STOP skipped qty={qty}")
            else:
                self.set_holdings(self.symbol, target_pct)
                self.debug(f"[{today}] BUY MKT target_pct={target_pct}")

        elif action == "SELL":
            held_qty = self.portfolio[self.symbol].quantity
            if entry_type == "LIMIT" and entry_price is not None and entry_price > 0 and held_qty > 0:
                self.limit_order(self.symbol, -held_qty, entry_price)
                self.debug(f"[{today}] SELL LIMIT qty={held_qty} price={entry_price}")
            elif entry_type == "STOP" and entry_price is not None and entry_price > 0 and held_qty > 0:
                self.stop_market_order(self.symbol, -held_qty, entry_price)
                self.debug(f"[{today}] SELL STOP qty={held_qty} stop={entry_price}")
            else:
                self.liquidate(self.symbol)
                self.debug(f"[{today}] SELL MKT")
