# 已知问题与限制

## API 访问限制

### 问题描述
- **Alpha Vantage API** 有日访问限制（免费版通常为 5 次/分钟，500 次/天）
- 在运行选股和再平衡时，需要为多只股票获取数据，可能触发 API 限制

### 影响范围
- `test_stock_selection.py` - 选股测试脚本可能因 API 限制而超时
- `run_multi_symbol_backtest.py` - 多标的回测在选股阶段可能遇到限制
- **Analyst 报告**：`memory.db` 中部分 fundamentals/news/sentiment 报告因 API 限流未能获取真实数据，内容为「未能获取」「API 失效」等 fallback 说明。详见 `docs/开发日志.md`，可用 `python scripts/experimental/check_api_failures.py`（或根目录薄封装）扫描。

### 解决方案
1. **使用缓存数据**：`DataAdapter` 已支持缓存，数据下载后会自动保存
2. **行情 fallback**：当 yfinance 失败或限流时，若已设置 `FINANCIALDATA_API_KEY`，会自动使用 Financial Data API（Free 级别 stock-prices）拉取 OHLCV
3. **分批处理**：在选股时，可以分批获取数据，避免一次性请求过多
4. **使用本地数据**：如果有历史数据文件，可以直接使用
5. **等待时间**：在 API 限制之间添加适当的延迟

### 临时处理
- 在 API 限制情况下，可以：
  - 使用较小的股票池进行测试（如 `STOCK_POOL[:20]`）
  - 使用已缓存的数据
  - 跳过选股测试，直接使用固定标的列表

### 后续改进
- 实现更智能的 API 请求管理（请求队列、重试机制）
- 添加 API 使用监控和告警
- 支持从本地数据源加载（CSV、数据库等）

---

## 已解决问题 / 经验记录

以下为曾出现并已修复的问题，供后续遇到类似现象时快速排查。

### yfinance 返回带时区 Index 导致 DataAdapter 比较报错（2026-02）

#### 现象
- 使用代理拉取 SPY 等数据时，`load_stock_data` 成功返回 41 条，但 `DataAdapter.load_stock_data_until` 报错：
  `Invalid comparison between dtype=datetime64[ns, America/New_York] and Timestamp`

#### 原因
- **yfinance** 返回的 DataFrame 的 `index` 为带时区的 `DatetimeIndex`（如 `America/New_York`）。
- **DataAdapter** 内用 `pd.to_datetime(date)` 得到的是无时区（naive）的 `Timestamp`。
- Pandas 不允许带时区与不带时区的标量直接比较，会抛出上述错误。

#### 解决
- 在 `tradingagents/core/data_adapter.py` 中，凡是用「日期」与 `df.index` 比较的地方，若 `df.index.tz is not None`，先将该日期转为与 index 相同时区再比较，例如：
  - `load_stock_data_until`：`cutoff = pd.to_datetime(date)` 后，若 `df.index.tz` 存在则 `cutoff = cutoff.tz_localize(df.index.tz)`，再用 `df.index <= cutoff`。
  - `get_price`、`get_next_trading_day` 中对传入的 `date` / `current_date` 做同样处理。

#### 经验
- 凡是从 yfinance（或其它可能返回带时区时间序列）拿到的数据，在后续用「日期字符串」或 naive `Timestamp` 做筛选、比较时，要先统一时区（或转成 naive），避免 `Invalid comparison`。

