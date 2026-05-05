# QUANTCONNECT.COM - TradeSwarm signal execution algorithm
# Supports both local file loading and Object Store loading.

from AlgorithmImports import *
import os
import json
from datetime import datetime, timedelta

EMBEDDED_SIGNALS = {}
OBJECT_STORE_KEYS = ["signals.json", "TradeSwarm/signals.json", "trade-swarm/signals.json"]


class LocalDailyBar(PythonData):
    """Read local CSV daily bars: date,open,high,low,close,volume."""

    FILE_BASENAME = "nvda_daily.csv"

    def GetSource(self, config, date, isLiveMode):
        source = os.path.join(Globals.DataFolder, "custom", self.FILE_BASENAME)
        return SubscriptionDataSource(
            source,
            SubscriptionTransportMedium.LocalFile,
            FileFormat.Csv,
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
        payload, signals = self._load_signals()
        self.signal_payload = payload
        self.signals = signals
        self.symbol_str = self._resolve_symbol(payload)
        self._apply_backtest_window(payload)
        self.set_cash(100000)
        self.SetBenchmark(lambda _: 0)

        self._last_processed_date = None
        self.symbol = None
        self._init_symbol()

        if not self.signals:
            self.error("未加载到有效信号，请确保 Object Store、signals/signals.json、signals.json 或 EMBEDDED_SIGNALS 可用")

    def _resolve_symbol(self, payload):
        symbol = None
        if isinstance(payload, dict):
            symbol = payload.get("symbol")
        if not symbol:
            msg = "signals.json 缺少 symbol 字段，无法初始化算法"
            self.error(msg)
            raise ValueError(msg)
        return str(symbol).upper()

    def _parse_date(self, value):
        if not value:
            return None
        try:
            return datetime.strptime(str(value), "%Y-%m-%d")
        except Exception:
            return None

    def _apply_backtest_window(self, payload):
        start_dt = self._parse_date(payload.get("start_date") if isinstance(payload, dict) else None)
        end_dt = self._parse_date(payload.get("end_date") if isinstance(payload, dict) else None)

        if (start_dt is None or end_dt is None) and isinstance(self.signals, dict) and self.signals:
            try:
                execution_dates = sorted(self.signals.keys())
                if start_dt is None:
                    start_dt = self._parse_date(execution_dates[0])
                    self.debug("signals.json 缺少 start_date，回退到最早执行日")
                if end_dt is None:
                    end_dt = self._parse_date(execution_dates[-1])
                    self.debug("signals.json 缺少 end_date，回退到最晚执行日")
            except Exception:
                pass

        if start_dt is None:
            start_dt = datetime(2025, 1, 1)
            self.debug("未解析到 start_date，使用默认 2025-01-01")
        if end_dt is None:
            end_dt = datetime(2025, 3, 1)
            self.debug("未解析到 end_date，使用默认 2025-03-01")

        self.set_start_date(start_dt.year, start_dt.month, start_dt.day)
        self.set_end_date(end_dt.year, end_dt.month, end_dt.day)

    def _init_symbol(self):
        use_local = (os.environ.get("TS_LOCAL_DATA", "1").strip() != "0")
        if use_local:
            try:
                LocalDailyBar.FILE_BASENAME = f"{self.symbol_str.lower()}_daily.csv"
                custom = self.AddData(LocalDailyBar, f"{self.symbol_str}_LOCAL", Resolution.DAILY)
                self.symbol = custom.Symbol
                self.SetBrokerageModel(BrokerageName.Default, AccountType.Cash)
                self.Debug(f"使用本地数据 custom/{LocalDailyBar.FILE_BASENAME}")
                return
            except Exception as e:
                self.Debug(f"本地数据初始化失败，回退 add_equity: {e}")
        self.equity = self.add_equity(self.symbol_str, Resolution.DAILY)
        self.symbol = self.equity.symbol

    def _normalize_signal_payload(self, payload):
        if not isinstance(payload, dict):
            return {}, {}
        by_execution_date = payload.get("by_execution_date")
        if isinstance(by_execution_date, dict):
            return payload, by_execution_date
        signals = payload.get("signals")
        if isinstance(signals, dict):
            return payload, signals
        return {}, payload

    def _load_from_object_store(self):
        store = getattr(self, "object_store", None) or getattr(self, "ObjectStore", None)
        if store is None:
            return None
        contains_key = getattr(store, "contains_key", None) or getattr(store, "ContainsKey", None)
        read = getattr(store, "read", None) or getattr(store, "Read", None)
        if contains_key is None or read is None:
            return None
        for key in OBJECT_STORE_KEYS:
            try:
                if contains_key(key):
                    raw = read(key)
                    if raw:
                        self.debug(f"使用 Object Store 信号: {key}")
                        return json.loads(raw)
            except Exception as e:
                self.debug(f"Object Store 读取失败 {key}: {e}")
        return None

    def _load_from_files(self):
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
                        payload = json.load(f)
                    self.debug(f"使用本地信号文件: {path}")
                    return payload
                except Exception as e:
                    self.error(f"加载信号失败 {path}: {e}")
        return None

    def _load_signals(self):
        payload = self._load_from_object_store()
        if payload is not None:
            return self._normalize_signal_payload(payload)

        payload = self._load_from_files()
        if payload is not None:
            return self._normalize_signal_payload(payload)

        if EMBEDDED_SIGNALS:
            self.debug("使用嵌入信号 EMBEDDED_SIGNALS")
            return self._normalize_signal_payload(EMBEDDED_SIGNALS)

        return {}, {}

    def on_data(self, data: Slice):
        if self.symbol is None or not data.ContainsKey(self.symbol):
            return
        today = self.time.date().isoformat()
        if today == self._last_processed_date:
            return
        self._last_processed_date = today
        signal = self.signals.get(today) if isinstance(self.signals, dict) else None

        if signal:
            self._execute_signal(today, signal)

        self._write_daily_snapshot(today)

    def _execute_signal(self, today, signal):
        # Optional guard: cancel existing open orders before placing new ones.
        # Prevents stale LIMIT orders from piling up across days.
        if bool(signal.get("cancel_pending_orders")):
            try:
                self.Transactions.CancelOpenOrders(self.symbol)
                self.debug(f"[{today}] CancelOpenOrders before executing new signal")
            except Exception as e:
                self.debug(f"[{today}] CancelOpenOrders failed: {e}")

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
            elif entry_type == "STOP" and entry_price is not None and entry_price > 0:
                qty = self.calculate_order_quantity(self.symbol, target_pct)
                if qty > 0:
                    self.stop_market_order(self.symbol, qty, entry_price)
                    self.debug(f"[{today}] BUY STOP qty={qty} stop={entry_price} target_pct={target_pct}")
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

    def _write_daily_snapshot(self, today):
        """Write portfolio snapshot to Object Store for interleaved backtest consumption."""
        holding = self.portfolio[self.symbol]
        snapshot = {
            "date": today,
            "symbol": self.symbol_str,
            "equity": self.portfolio.total_portfolio_value,
            "cash": self.portfolio.cash,
            "holdings": {
                self.symbol_str: {
                    "shares": float(holding.quantity),
                    "avg_price": float(holding.average_price),
                    "market_value": float(holding.holdings_value),
                    "market_price": float(holding.price),
                    "unrealized_pnl": float(holding.unrealized_profit),
                    "unrealized_pnl_pct": float(holding.unrealized_profit_percent * 100) if holding.quantity != 0 else 0.0,
                }
            },
            "pending_orders": self._collect_pending_orders(),
            "filled_today": self._collect_filled_today(today),
        }

        store = getattr(self, "object_store", None) or getattr(self, "ObjectStore", None)
        if store is not None:
            save_fn = getattr(store, "save", None) or getattr(store, "Save", None)
            if save_fn is not None:
                try:
                    save_fn(f"snapshots/{today}.json", json.dumps(snapshot))
                except Exception as e:
                    self.debug(f"Failed to write snapshot to Object Store: {e}")

    def _collect_pending_orders(self):
        pending = []
        def _first_attr(obj, names, default=None):
            for name in names:
                if hasattr(obj, name):
                    value = getattr(obj, name)
                    if value is not None:
                        return value
            return default

        try:
            for ticket in self.transactions.get_open_orders():
                order_type = _first_attr(ticket, ["order_type", "Type"])
                direction = _first_attr(ticket, ["direction", "Direction"])
                quantity = _first_attr(ticket, ["quantity", "Quantity"], 0)
                order_id = _first_attr(ticket, ["order_id", "OrderId", "id", "Id"])

                limit_price = _first_attr(ticket, ["limit_price", "LimitPrice"])
                stop_price = _first_attr(ticket, ["stop_price", "StopPrice"])
                # OrderTicket 形态可用 get(OrderField.*) 读取挂单价；Order 形态走属性读取
                if limit_price is None and hasattr(ticket, "get"):
                    try:
                        limit_price = ticket.get(OrderField.LIMIT_PRICE)
                    except Exception:
                        limit_price = None
                if stop_price is None and hasattr(ticket, "get"):
                    try:
                        stop_price = ticket.get(OrderField.STOP_PRICE)
                    except Exception:
                        stop_price = None

                pending.append({
                    "order_id": int(order_id) if order_id is not None else None,
                    "type": str(order_type) if order_type is not None else "UNKNOWN",
                    "direction": str(direction) if direction is not None else "UNKNOWN",
                    "quantity": float(quantity),
                    "limit_price": float(limit_price) if limit_price is not None else None,
                    "stop_price": float(stop_price) if stop_price is not None else None,
                })
        except Exception:
            pass
        return pending

    def _collect_filled_today(self, today):
        filled = []
        try:
            for order in self.transactions.get_orders(lambda o: o.last_fill_time is not None and o.last_fill_time.date().isoformat() == today and o.status == OrderStatus.FILLED):
                filled.append({
                    "order_id": order.id,
                    "direction": "BUY" if order.direction == OrderDirection.BUY else "SELL",
                    "quantity": float(abs(order.quantity)),
                    "fill_price": float(order.price),
                    "type": str(order.type),
                })
        except Exception:
            pass
        return filled
