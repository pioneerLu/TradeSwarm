# 工具输出样例

本文档记录每个工具的实际返回样例，用于后续的清洗和格式化工作。

**收集时间**: 2025-12-30  
**测试股票**: 600519 (贵州茅台)

## 1. get_stock_data

**参数**:
```json
{
  "ts_code": "600519.SH",
  "start_date": "20251130",
  "end_date": "20251230"
}
```

**返回样例**:
```json
{
  "success": true,
  "message": "成功获取 22 条数据",
  "data": [
    {
      "ts_code": "600519.SH",
      "trade_date": "20251201",
      "open": 1451.0,
      "high": 1462.27,
      "low": 1442.0,
      "close": 1448.0,
      "pre_close": 1450.5,
      "change": -2.5,
      "pct_chg": -0.1724,
      "vol": 27333.42,
      "amount": 3961994.999
    }
  ],
  "summary": {
    "total_records": 22,
    "date_range": {
      "start": "20251201",
      "end": "20251230"
    },
    "latest_price": {
      "close": 1431.0,
      "pct_chg": -0.1465
    }
  }
}
```

**字段说明**:
- `data`: 数组，每个元素包含单日行情数据
- `summary`: 数据摘要，包含总条数、日期范围、最新价格

---

## 2. get_indicators

**参数**:
```json
{
  "ts_code": "600519.SH",
  "indicators": "MA,RSI",
  "period": 30
}
```

**返回样例**:
```json
{
  "success": true,
  "message": "成功计算技术指标",
  "indicators": ["MA5", "MA10", "MA20", "RSI"],
  "data": [
    {
      "trade_date": "20251230",
      "close": 1431.0,
      "MA5": 1425.2,
      "MA10": 1420.5,
      "MA20": 1415.8,
      "RSI": 52.3
    }
  ],
  "summary": {
    "total_records": 43,
    "indicators_calculated": ["MA5", "MA10", "MA20", "RSI"],
    "latest_indicators": {
      "MA5": 1425.2,
      "MA10": 1420.5,
      "MA20": 1415.8,
      "RSI": 52.3
    }
  }
}
```

**字段说明**:
- `indicators`: 已计算的指标列表
- `data`: 数组，每个元素包含原始数据和技术指标
- `summary.latest_indicators`: 最新日期的指标值

---

## 3. get_news

**参数**:
```json
{
  "ts_code": "600519",
  "days": 7,
  "limit": 5
}
```

**返回样例**:
```json
{
  "success": true,
  "message": "成功从 AkShare 获取股票 600519 的新闻",
  "format": "markdown",
  "content": "# 个股新闻简报 - 600519\n\n**更新时间**: 2025-12-30 21:26:56\n\n## 数据概览\n\n- **股票代码**: 600519\n- **新闻数量**: 0 条\n- **数据来源**: AkShare (东方财富)\n\n## ⚠️ 数据获取提示\n\n未找到股票 600519 的相关新闻数据。\n\n可能原因：\n- 该股票近期没有新闻\n- 数据源暂时不可用\n- 网络连接问题\n\n建议：稍后重试或手动关注相关新闻。\n",
  "summary": {
    "data_source": "akshare",
    "date_range": {
      "start": "2025-12-23",
      "end": "2025-12-30"
    },
    "note": "数据以 Markdown 格式返回，便于 LLM 理解和处理"
  }
}
```

**字段说明**:
- `format`: 返回格式（"markdown"）
- `content`: Markdown 格式的新闻内容
- `summary`: 数据源和日期范围信息

---

## 4. get_global_news

**参数**:
```json
{
  "days": 7,
  "limit": 5
}
```

**返回样例**:
```json
{
  "success": true,
  "message": "成功获取宏观市场全景简报",
  "format": "markdown",
  "content": "# 宏观市场全景简报\n\n**更新时间**: 2025-12-30 21:26:56\n\n---\n\n## 📰 宏观新闻 (5条)\n\n### 1. [新闻标题](链接)\n\n- **时间**: 2025-12-30\n- **摘要**: ...\n\n---\n\n## 💰 北向资金流向\n\n- **状态**: 净流入\n- **金额**: 10.5亿元\n- **日期**: 2025-12-30\n\n---\n\n## 📊 核心指数表现\n\n| 指数 | 代码 | 最新价 | 涨跌幅 |\n|------|------|--------|--------|\n| 上证指数 | 000001 | 3000.5 | +0.5% |\n\n---\n\n## 💱 汇率信息\n\n- **货币对**: USD/CNY\n- **汇率**: 7.1234\n- **涨跌幅**: +0.1%\n\n*数据来源: AkShare (东方财富)*\n",
  "summary": {
    "data_source": "akshare",
    "date_range": {
      "start": "2025-12-23",
      "end": "2025-12-30"
    },
    "note": "数据以 Markdown 格式返回，包含宏观新闻、北向资金、核心指数、汇率四个维度",
    "errors": []
  }
}
```

**字段说明**:
- `content`: Markdown 格式的宏观市场全景简报
- `summary.errors`: 数据获取失败的模块列表（如果有）

---

## 5. get_company_info

**参数**:
```json
{
  "ts_code": "600519"
}
```

**返回样例**:
```json
{
  "success": true,
  "message": "成功获取公司信息",
  "data": {
    "ts_code": "600519.SH",
    "name": "贵州茅台",
    "area": "贵州",
    "industry": "酒、饮料和精制茶制造业",
    "market": "主板",
    "list_date": "20010827",
    "total_share": 125619.78,
    "float_share": 125619.78
  },
  "summary": {
    "data_source": "akshare",
    "update_time": "2025-12-30 21:26:56"
  }
}
```

**字段说明**:
- `data`: 公司基本信息对象
- `summary.data_source`: 数据来源（"akshare" 或 "tushare"）

---

## 6. get_financial_statements

**参数**:
```json
{
  "ts_code": "600519",
  "report_type": "annual",
  "periods": 2
}
```

**返回样例**:
```json
{
  "success": true,
  "message": "成功获取财务报表",
  "data": {
    "income_statement": {
      "preview": [
        {
          "end_date": "20231231",
          "revenue": 150000000000,
          "net_profit": 70000000000
        }
      ],
      "meta": {
        "total_rows": 2,
        "preview_rows": 2,
        "columns": ["end_date", "revenue", "net_profit", ...]
      }
    },
    "balance_sheet": {
      "preview": [...],
      "meta": {...}
    },
    "cash_flow": {
      "preview": [...],
      "meta": {...}
    }
  },
  "summary": {
    "report_type": "annual",
    "periods": 2,
    "data_source": "akshare"
  }
}
```

**字段说明**:
- `data`: 包含三大报表的对象
- 每个报表包含 `preview`（预览数据）和 `meta`（元信息）
- `preview` 限制为前 N 条记录

---

## 7. get_financial_indicators

**参数**:
```json
{
  "ts_code": "600519",
  "report_type": "annual",
  "periods": 2
}
```

**返回样例**:
```json
{
  "success": true,
  "message": "成功获取财务指标",
  "data": {
    "preview": [
      {
        "end_date": "20231231",
        "roe": 0.35,
        "roa": 0.25,
        "gross_profit_rate": 0.92,
        "net_profit_rate": 0.47
      }
    ],
    "meta": {
      "total_rows": 2,
      "preview_rows": 2,
      "columns": ["end_date", "roe", "roa", "gross_profit_rate", ...]
    }
  },
  "summary": {
    "report_type": "annual",
    "periods": 2,
    "data_source": "akshare"
  }
}
```

**字段说明**:
- `data.preview`: 财务指标预览数据
- `data.meta`: 数据元信息

---

## 8. get_valuation_indicators

**参数**:
```json
{
  "ts_code": "600519",
  "include_market_comparison": false
}
```

**返回样例**:
```json
{
  "success": true,
  "message": "成功获取估值指标",
  "data": {
    "pe": 28.5,
    "pb": 8.2,
    "ps": 12.3,
    "dividend_yield": 0.015,
    "update_date": "2025-12-30"
  },
  "summary": {
    "data_source": "akshare",
    "include_market_comparison": false
  }
}
```

**字段说明**:
- `data`: 估值指标对象，包含 PE、PB、PS、股息率等
- `summary.include_market_comparison`: 是否包含市场对比数据

---

## 9. get_earnings_data

**参数**:
```json
{
  "ts_code": "600519",
  "limit": 5
}
```

**返回样例**:
```json
{
  "success": true,
  "message": "成功获取业绩数据",
  "data": {
    "forecast": {
      "preview": [
        {
          "report_date": "20241231",
          "type": "业绩预告",
          "change_min": 0.15,
          "change_max": 0.20
        }
      ],
      "meta": {
        "total_rows": 3,
        "preview_rows": 3
      }
    },
    "express": {
      "preview": [...],
      "meta": {...}
    }
  },
  "summary": {
    "data_source": "akshare",
    "total_forecast": 3,
    "total_express": 2
  }
}
```

**字段说明**:
- `data.forecast`: 业绩预告数据
- `data.express`: 业绩快报数据
- 每个都包含 `preview` 和 `meta`

---

## 输出格式总结

### 通用结构

所有工具返回 JSON 字符串，解析后包含：

```json
{
  "success": boolean,      // 是否成功
  "message": string,      // 提示信息
  "data": any,           // 数据内容（格式因工具而异）
  "summary": {           // 数据摘要
    "data_source": string,
    ...
  }
}
```

### 数据格式类型

1. **数组格式**: `get_stock_data`, `get_indicators`
   - `data`: 数组，每个元素是一条记录

2. **对象格式**: `get_company_info`, `get_valuation_indicators`
   - `data`: 对象，包含字段-值对

3. **Markdown 格式**: `get_news`, `get_global_news`
   - `format`: "markdown"
   - `content`: Markdown 字符串

4. **预览格式**: `get_financial_statements`, `get_financial_indicators`, `get_earnings_data`
   - `data.preview`: 预览数据（限制条数）
   - `data.meta`: 元信息（总条数、列名等）

### 待清洗和格式化的点

1. **数据一致性**: 统一数组/对象格式
2. **字段命名**: 统一字段命名规范
3. **数据类型**: 确保数值类型正确（int/float）
4. **日期格式**: 统一日期格式（YYYY-MM-DD）
5. **错误处理**: 统一错误返回格式
6. **Markdown 内容**: 考虑是否需要结构化数据替代

