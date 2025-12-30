# Tool Nodes

将工具函数封装为 LangGraph 节点，支持在 Graph 中作为独立节点使用，或作为工具集合供 Agent 调用。

## 目录结构

```text
tool_nodes/
├── __init__.py              # 统一导出：工具节点函数 + 工具函数
├── market_node.py          # 市场数据工具节点（1个工具）
├── fundamentals_node.py    # 基本面分析工具节点（5个工具）
├── news_node.py            # 新闻工具节点（2个工具）
├── technical_node.py       # 技术分析工具节点（1个工具）
└── utils/                  # 工具函数实现
    ├── market_tools.py
    ├── fundamentals_tools.py
    ├── news_tools.py
    └── technical_tools.py
```

## 使用方式

### 1. 作为 LangGraph 节点

```python
from langgraph.graph import StateGraph
from tradingagents.tool_nodes import create_market_tool_node

graph = StateGraph(AgentState)
graph.add_node("market_tools", create_market_tool_node())
```

### 2. 作为工具集合供 Agent 使用

```python
from langchain.agents import create_agent
from tradingagents.tool_nodes import get_fundamentals_tools

tools = get_fundamentals_tools()
agent = create_agent(model=llm, tools=tools)
```

### 3. 直接使用工具函数

```python
from tradingagents.tool_nodes import get_stock_data

result = get_stock_data.invoke({
    "ts_code": "600519",
    "start_date": "20250101",
    "end_date": "20250131"
})
```

## 工具列表

| 类别 | 工具函数 | 说明 |
| :--- | :------- | :--- |
| 市场数据 | `get_stock_data` | 获取日线行情数据 |
| 基本面 | `get_company_info` | 公司基本信息 |
| 基本面 | `get_financial_statements` | 三大财务报表 |
| 基本面 | `get_financial_indicators` | 财务指标（ROE、ROA等） |
| 基本面 | `get_valuation_indicators` | 估值指标（PE、PB等） |
| 基本面 | `get_earnings_data` | 业绩预告/快报 |
| 新闻 | `get_news` | 个股新闻和公告 |
| 新闻 | `get_global_news` | 宏观市场全景简报 |
| 技术分析 | `get_indicators` | 技术指标（MA、RSI、MACD等） |

## 导出接口

```python
# 节点创建函数
create_market_tool_node()
create_fundamentals_tool_node()
create_news_tool_node()
create_technical_tool_node()

# 工具集合函数
get_market_tools()
get_fundamentals_tools()
get_news_tools()
get_technical_tools()

# 工具函数（直接导出）
get_stock_data, get_company_info, get_financial_statements, ...
```

## 配置

需要在 `config/config.yaml` 中配置：

- `data_sources.tushare_token`: Tushare API Token
- `data_sources.currency_api_key`: 可选，用于汇率 fallback

## Todo

- [ ] 对工具的具体输出进行清洗和格式化
  - 统一返回格式
  - 优化数据结构，将清洗流程固化，不要让模型干这个事情
  - 对各种简报数据、爬虫数据做清洗模板
  - 参考 [工具输出样例文档](./tool_outputs.md) 了解当前输出格式
