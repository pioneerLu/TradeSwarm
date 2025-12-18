# TradeSwarm

TradeSwarm是一个基于Agent的开源的炒股系统，通过多智能体协作架构实现智能投资分析和决策。 TradeSwarm采用多Agent架构，模拟专业投资团队的分析流程，整合基本面分析、市场分析、新闻分析、社交媒体分析等多个维度，为投资决策提供全面支持。系统基于LangChain框架构建，支持多种数据源接入，实现了模块化、可扩展的智能交易分析平台。

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

## 使用方式

```bash
# 安装环境
conda create -n TradeSwarm python=3.12
pip install requirements.txt

# 设置环境变量
cp -r .env.example .env
```

## 开发规范

本项目遵循研究型代码开发规范，注重代码质量、文档完整性和系统可扩展性，所有代码均通过严格的语法验证和类型检查。
