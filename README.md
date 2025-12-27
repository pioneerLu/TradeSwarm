# TradeSwarm

TradeSwarm是一个基于Agent的开源的炒股系统，通过多智能体协作架构实现智能投资分析和决策。 TradeSwarm采用多Agent架构，模拟专业投资团队的分析流程，整合基本面分析、市场分析、新闻分析、社交媒体分析等多个维度，为投资决策提供全面支持。系统基于LangChain框架构建，支持多种数据源接入，实现了模块化、可扩展的智能交易分析平台。

## 主要思路与管线概览

系统包含五条并行/协同的处理管线，围绕数据采集、规则清洗、智能体分析、存储与决策形成闭环：

- 数据采集与清洗：四条主题管线分别监听基础面、市场行情、新闻、社交媒体，每条管线的专属爬虫按设定频率抓取数据，经基于规则的清洗后进入对应分析链路。
- 分析生成与存储：清洗后的数据送入 `tradingagents/agents/analyst` 下的四位 analyst，各自生成事件简报；原始数据写入 SQLite，简报向量化后写入 ChromaDB，二者同属统一的 prompt manager 以保持数据管理一致性。
- 并行独立性：前四条管线互不干扰，状态独立运行（现有 state 定义仍需校准以完全反映这一并行特性）。
- 轮循决策：第五条管线定时轮询 SQLite/ChromaDB 是否出现重要信息，若有触发 `tradingagents/agents/managers` 进行综合决策。

## 项目目录结构

```
TradeSwarm/
├── config/                     # 配置文件目录
│   └── config.yaml            # 系统配置文件（LLM配置、数据源配置等）
├── data_sources/              # 数据源模块
│   ├── akshare_provider.py    # AKShare数据源提供者
│   └── tushare_provider.py    # Tushare数据源提供者
├── docs/                      # 文档目录
├── momory/                    # 记忆模块（注：目录名可能需要修正为memory）
│   └── financial_situation_memory.py  # 财务状况记忆管理
├── tradingagents/             # 交易智能体模块
│   └── agents/
│       ├── analyst/           # 分析师智能体
│       │   ├── fundamentals_analyst/  # 基本面分析师
│       │   │   ├── agent.py          # 智能体实现
│       │   │   ├── state.py          # 状态管理
│       │   │   └── prompt.j2         # 提示词模板
│       │   ├── market_analyst/       # 市场分析师
│       │   ├── news_analyst/         # 新闻分析师
│       │   └── social_media_analyst/ # 社交媒体分析师
│       └── managers/         # 管理类智能体
│           ├── research_manager/     # 研究管理器
│           └── risk_manager/         # 风险管理器
└── utils/                     # 工具模块
    ├── config_loader.py       # 配置加载器
    ├── data_utils.py          # 数据处理工具
    └── llm_utils.py           # LLM工具函数
```

## 核心架构

## 项目技术选型

### 核心技术栈
- **Python 3.12**: 主要编程语言，提供现代化的语言特性和性能优化
- **LangChain 1.2.0**: 大语言模型应用开发框架，提供Agent构建和工具编排能力
- **OpenAI 2.12.0**: LLM接口支持，兼容多种大语言模型API
- **ChromaDB 1.3.7**: 向量数据库，用于知识检索和语义搜索
- **AKShare 1.17.96**: 开源金融数据接口库
- **Tushare 1.4.24**: 专业金融数据接口SDK

### 数据源集成
- **Tushare Pro**: 专业的金融数据接口，提供全面的股票、基金、期货数据
- **AKShare**: 开源的金融数据接口，支持多种数据源和实时数据获取

### 数据能力明细

| 指标名称 | 数据源 | 对应函数 | 简要说明 |
| :--- | :--- | :--- | :--- |
| **日线行情** | Tushare | `get_daily` | 获取历史日线数据（开高低收、成交量）|
| **每日指标** | Tushare | `get_daily_basic` | 获取每日收盘后的基本面指标（PE、PB、换手率等）|
| **实时盘口** | Tushare | `get_realtime_orderbook` | 获取实时五档买卖盘口及最新价 |
| **股票列表** | Tushare | `get_stock_basic` | 获取全市场股票基础信息列表 |
| **公司信息** | Tushare | `get_company_info` | 获取单个公司的详细背景、主营业务等 |
| **利润表** | Tushare | `get_income` | 获取季度/年度利润表数据 |
| **资产负债表** | Tushare | `get_balancesheet` | 获取季度/年度资产负债表数据 |
| **现金流量表** | Tushare | `get_cashflow` | 获取季度/年度现金流量表数据 |
| **财务指标** | Tushare | `get_fina_indicator` | 获取 ROE、ROA、毛利率等计算后指标 |
| **业绩预告** | Tushare | `get_forecast` | 获取上市公司业绩预告 |
| **业绩快报** | Tushare | `get_express` | 获取上市公司业绩快报 |
| **实时估值** | AkShare | `get_valuation_indicators` | 获取盘中实时的 PE/PB 估值数据 |
| **宏观新闻** | AkShare | `get_macro_news` | 获取央视/百度财经等宏观新闻资讯 |
| **北向资金** | AkShare | `get_northbound_money_flow` | 获取沪深港通北向资金实时流向 |
| **全球指数** | AkShare | `get_global_indices_performance` | 获取美股、港股等全球核心指数涨跌幅 |
| **实时汇率** | AkShare | `get_currency_exchange_rate` | 获取美元兑人民币实时汇率 (USD/CNY) |
| **(备用)财务报表** | AkShare | `get_financial_statements` | 作为 Tushare 的备用，包含三大报表 |
| **(备用)公司信息** | AkShare | `get_company_info` | 作为 Tushare 的备用 |

## 使用方式

```bash
# 安装环境
conda create -n TradeSwarm python=3.12
pip install -r requirements.txt

# 设置环境变量
cp -r .env.example .env
```

## 开发规范

本项目遵循研究型代码开发规范，注重代码质量、文档完整性和系统可扩展性，所有代码均通过严格的语法验证和类型检查。
