## 项目 TODO 总览（高层规划）

> 说明：本文件记录当前阶段围绕"可持续运行数周/月的多智能体交易系统"目标的主要开发任务。具体实现细节请结合 `README.md`、`docs/开发日志.md` 和各模块内联文档一起查看。

> **参考代码位置**：`trading_sys/` 目录下包含完整的选股、因子、策略、组合管理实现，可作为参考。集成时需要将这些代码复制到主目录对应位置，而不是使用引用。

---

### 一、日级与多日闭环

- **plan-1：单标的多日回测驱动器** ✅
  - 按日期区间循环，每天依次调用：Pre-Open Graph → Market Open → Post Close。
  - 先固定一个 `symbol`，不做截面选股，只确保"多日动态仓位 + 资金曲线"跑通。
  - **实现文件**：`run_single_symbol_backtest.py`
  - **功能**：
    - 自动获取交易日历（基于 SPY 数据）
    - 每日执行完整流程：Pre-Open 分析 → Market Open 交易 → Post Close 更新
    - 保存每日结果到 `backtest_results/daily_results/YYYY-MM-DD.json`
    - 生成最终回测报告 `backtest_results/backtest_report.json`
    - 使用缓存数据，避免 Alpha Vantage API 限制
  - **参考代码**：
    - `trading_sys/main.py` - 单股票回测入口
    - `trading_sys/run_portfolio.py` - 组合回测主程序（包含日期循环逻辑）

- **plan-2：`daily_trading_summaries` 表与日级 summary 写入**
  - 设计并创建 `daily_trading_summaries`（或等价命名）表结构，字段能容纳如下结构：
    - `date`, `symbol`, `market_regime`, `selected_strategy`, `expected_behavior`,
      `actual_outcome.return`, `actual_outcome.max_drawdown`, `positioning`, `anomaly`, 以及原始 JSON。
  - 在每天收盘后（Post Close 或日驱动器末尾）组装 summary JSON 并写入 DB。
  - **参考代码**：
    - `trading_sys/core/portfolio.py` - `PortfolioManager.nav_history` 记录净值历史的方式
    - `trading_sys/run_portfolio.py` - 每日快照保存逻辑

- **plan-3：标准化决策字段（Trader / Strategy / Risk）**
  - 在 Strategy Selector / Trader / Risk Manager 的 JSON schema 中显式加入并稳定命名：
    - `market_regime`
    - `selected_strategy`
    - `expected_behavior`
  - 确保这些字段可以被 `daily_trading_summaries` 直接消费。
  - **参考代码**：
    - `trading_sys/strategies/strategy_lib.py` - `StrategyResult` 数据类结构
    - `trading_sys/timing/market_timer.py` - `MarketRegime` 枚举定义

---

### 二、执行与组合管理

- **plan-4：完善 Market Open 执行逻辑**
  - 明确从 `trader_investment_plan` + `strategy_selection` + `risk_summary.final_decision`
    推导具体下单动作（买入/卖出/保持 + 数量/仓位）。
  - 约束"每天只执行一次交易"，通过 `PortfolioManager` 正确更新组合现金与持仓。
  - **参考代码**：
    - `trading_sys/core/portfolio.py` - `PortfolioManager.buy()` / `sell()` 方法
    - `trading_sys/run_portfolio.py` - 交易执行逻辑（T+1日开盘价执行）
    - `trading_sys/strategies/strategy_lib.py` - `execute_strategy()` 统一接口

- **plan-5：完善 Post Close & 收益计算**
  - Post Close 使用 `DataAdapter` 更新所有持仓的当日收盘价。
  - 计算单日收益率和累计收益（至少组合层面），为 `daily_trading_summaries.actual_outcome`
    中的 `return` 和（简化版）`max_drawdown` 提供数据。
  - **参考代码**：
    - `trading_sys/core/portfolio.py` - `PortfolioManager.update_prices()` / `get_nav_dataframe()` 方法
    - `trading_sys/run_portfolio.py` - 每日收益计算逻辑

---

### 三、周期级反思与长期记忆

- **plan-6：周期级 Reflector Agent**
  - 设计 Reflector 节点/脚本：
    - 读取一个周期内（周 / 月）的 `daily_trading_summaries` 与关键决策字段；
    - 输出结构化周期反思（错误模式、成功模式、策略适用条件、环境判断偏差等）。
  - 将周期反思写入长期记忆表（例如 `cycle_reflections`），供 `past_memory_str` 使用。
  - **参考代码**：
    - `trading_sys/run_portfolio.py` - 回测报告生成逻辑（可作为周期总结的参考）

---

### 四、截面因子与再平衡

- **plan-7：截面因子选股与 Rebalance** 🔄
  - 实现基础因子计算（如 20 日动量、波动率、简单估值因子等），为 `StockSelector` 提供输入。
  - 在每个周 / 月 Rebalance Day 根据因子得分 + 约束选出 top N 标的，
    并通过 `PortfolioManager` 更新目标组合。
  - **参考代码位置**：
    - **选股器核心逻辑**：`trading_sys/selection/selector.py`
      - `calculate_factors()` - 计算6个核心因子（动量、波动率、RSI、成交量比率、趋势强度）
      - `calculate_factor_ics()` - IC动态权重计算
      - `rank_stocks()` - 股票排名
      - `select_stocks()` - 选股主方法
    - **因子库**：`trading_sys/factors/alpha_factors.py`
      - `Alpha101` 类 - WorldQuant Alpha101因子实现（可选扩展）
    - **股票池定义**：`trading_sys/selection/stock_pool.py`
      - `STOCK_POOL` - 各行业Top 10股票池
      - `SECTOR_STOCKS` - 按行业分类的股票列表
    - **主目录已有**：
      - `tradingagents/core/selection/stock_selector.py` - 已有基础实现，需要增强
      - `tradingagents/core/portfolio/portfolio_manager.py` - 已有基础实现
  - **集成方案**：
    1. **增强现有选股器**：将 `trading_sys/selection/selector.py` 中的完整因子计算逻辑复制到 `tradingagents/core/selection/stock_selector.py`
    2. **添加股票池**：将 `trading_sys/selection/stock_pool.py` 复制到 `tradingagents/core/selection/stock_pool.py`
    3. **可选：添加Alpha101因子库**：将 `trading_sys/factors/alpha_factors.py` 复制到 `tradingagents/core/factors/alpha_factors.py`（作为扩展）
    4. **增强组合管理器**：参考 `trading_sys/core/portfolio.py` 完善 `tradingagents/core/portfolio/portfolio_manager.py` 的再平衡逻辑

---

### 五、长期运行脚本与工程化

- **plan-8：多标的、多周期持续运行脚本**
  - 把上述组件（选股 + 多日驱动 + 执行 + Post Close + Reflector）串联成一个长跑脚本，
    支持按周 / 月定义周期，在整个周期内按交易日迭代。
  - 加上异常处理、日志和简单监控，支持"若干周/若干月"连续实验运行。
  - **参考代码**：
    - `trading_sys/run_portfolio.py` - 完整的组合回测流程（选股 → 择时 → 交易 → 再平衡）
    - `trading_sys/core/backtest_engine.py` - 回测引擎（可选参考）

---

### 六、数据质量与 API 限制

- **plan-9：memory.db 中受 API 限制的报告补建与防护** 🔄
  - **问题**：部分 Analyst 报告因 Alpha Vantage API 限流/密钥耗尽未能获取真实数据，报告内容为「未能获取」「API 失效」等 fallback 说明，影响 Pre-Open 决策质量。
  - **影响范围**：NVDA 约 15 条报告、AAPL 6 条，涉及 2026-01-21 至 2026-02-12 多个日期。
  - **相关文件**：
    - `docs/开发日志.md` - 详细受影响列表、处理建议与已实施修正
    - `scripts/experimental/check_api_failures.py` - 扫描脚本
    - `scripts/experimental/build_analyst_dataset.py` - 按 `--dates` + `--only-missing` 补全失败日
  - **已完成**：
    1. ✅ `scripts/experimental/build_analyst_dataset.py` 增加 Alpha Vantage 限流（news/fundamentals/sentiment 间 sleep 13s）
    2. ✅ 报告含 API 失败关键词时跳过写入，避免污染数据集
    3. ✅ `--dates` 指定精确日期；`--only-missing` 先检测再运行，仅补失败/缺失类型
  - **待办**：
    1. 按 `check_api_failures` 结果对失败日执行 `build_analyst_dataset.py --dates ... --only-missing` 完成 NVDA 等标的补建
    2. 可选：Analyst 端当 API 失败时降级为 yfinance + 公开财报摘要

---

## 参考代码详细说明

### 选股模块 (`trading_sys/selection/`)

#### `selector.py` - 核心选股器
- **关键方法**：
  - `calculate_factors(df)` - 计算6个核心因子：
    - `momentum_20d` / `momentum_60d` - 动量因子
    - `volatility` - 年化波动率（负权重）
    - `rsi_score` - RSI得分（0-1，接近50时得分最高）
    - `volume_ratio` - 成交量比率（近5日/20日均量）
    - `trend_strength` - 趋势强度（综合MA20/MA50）
  - `calculate_factor_ics(date)` - 计算IC并动态调整权重
  - `rank_stocks(date)` - 股票排名（返回DataFrame）
  - `select_stocks(date)` - 选股（返回股票列表）
- **IC动态权重机制**：
  - 使用最近4个历史时点计算截面IC
  - 根据IC绝对值分配权重，平滑更新（70%旧权重 + 30%新权重）
- **市场状态权重**（可选）：
  - 牛市/熊市/震荡市使用不同的因子权重配置

#### `stock_pool.py` - 股票池定义
- 包含10个行业的Top 10股票（共约100只）
- 行业分类：科技、金融、医疗、消费品、通信、工业、能源、必需消费品、公用事业、房地产、材料

### 策略库 (`trading_sys/strategies/strategy_lib.py`)

- **5个语义正交策略**：
  1. `trend_following` - 趋势跟踪（MA20/MA50 + ATR止损）
  2. `mean_reversion` - 均值回归（RSI + 布林带）
  3. `momentum_breakout` - 动量突破（价格突破20日高点 + 成交量）
  4. `reversal` - 反转策略（相对位置 + RSI）
  5. `range_trading` - 震荡区间（支撑阻力 + RSI）
- **统一接口**：`execute_strategy(strategy_type, df, is_holding) -> StrategyResult`
- **主目录已有**：`tradingagents/core/strategies/strategy_lib.py`（需要确认是否完整）

### 组合管理 (`trading_sys/core/portfolio.py`)

- **关键功能**：
  - `buy()` / `sell()` - 交易执行
  - `update_prices()` - 更新持仓价格
  - `check_stop_loss()` - 检查止损止盈（支持策略个性化）
  - `rebalance()` - 再平衡（等权重分配）
  - `get_nav_dataframe()` - 获取净值历史
- **主目录已有**：`tradingagents/core/portfolio/portfolio_manager.py`（需要增强）

---

后续如有新需求（例如更复杂的因子库、实盘接入、可视化监控等），可以在本文件下继续追加章节与条目。


