# Polaris × NVDA：与现有 `get_news` / `get_global_news` 的契约对齐说明

本文记录 **以 NVDA 为例** 的 Polaris API 真实输出形态，以及如何映射到当前工具返回值，便于 **不改 prompt、仅在 `news_tools` 内合并数据源** 的实现。

---

## 1. 当前工具返回值（代码契约）

### `get_news(symbol, …) -> str`（JSON）

成功时由 `tradingagents/tool_nodes/utils/news_tools.py` 序列化的顶层结构为：

- `success`, `message`, `format`（`"json"`）, `data`, `summary`

`data` 为 **字典列表**，每条与 Alpha Vantage `NEWS_SENTIMENT` 经 `DataFrame.to_dict("records")` 后的字段一致（见 `datasources/data_sources/alphavantage_provider.py`）：

| 字段 | 含义 |
|------|------|
| `title` | 标题 |
| `url` | 链接 |
| `time_published` | 发布时间（AV 多为 `YYYYMMDDTHHMMSS`） |
| `summary` | 摘要 |
| `source` | 来源名称 |
| `overall_sentiment_score` | 情绪分数（数值） |
| `overall_sentiment_label` | 情绪标签 |

### `get_global_news(…) -> str`（JSON）

成功时：

- `format`: `"markdown"`
- `content`: 一整段 Markdown 宏观简报
- `summary`: 含 `data_source`, `date_range`, `total_records` 等

Polaris 的 `/api/v1/agent-feed` **不是按 AV 的 time_from/time_to 过滤**，更适合作为 **Markdown 附录** 或单独 `summary.polaris_*` 元数据，而不是逐条伪造 AV 宏观表结构。

---

## 2. NVDA：Polaris `/api/v1/search` 真实响应（摘录）

以下摘自本地探针保存文件（Bearer + `q=NVIDIA earnings guidance`）：

- 文件：`tmp/polaris_api_probe/20260325T055739Z/02_search_bearer_200.json`

**响应顶层（与工具映射相关）：**

```json
{
  "status": "ok",
  "query": "NVIDIA earnings guidance",
  "total": 2,
  "took_ms": 166,
  "briefs": [ "..." ],
  "facets": { "tech": 2 },
  "related_queries": ["Nvidia", "China", "Vera Rubin", "Biden administration", "AMD"],
  "meta": { "total": 2, "page": 1, "per_page": 8, "sort": "relevance", "depth": "standard" }
}
```

**单条 `brief`（第 1 条，与 NVDA 直接相关）——完整结构示例：**

```json
{
  "id": "PR-FbJAxNRe",
  "headline": "Nvidia Shifts Focus from China Exports to Vera Rubin Development",
  "summary": "Chip giant abandons China-bound semiconductor production to accelerate domestic Vera Rubin project amid ongoing trade restrictions.",
  "body": "Nvidia has reportedly abandoned plans to export certain chips to China...",
  "category": "tech",
  "published_at": "2026-03-07T16:07:33.966Z",
  "provenance": {
    "review_status": "ai_generated",
    "confidence_score": 0.4,
    "bias_score": 0,
    "agents_involved": ["SC", "NL"]
  },
  "sources": [],
  "counter_argument": "Some analysts might argue that abandoning lucrative Chinese markets could hurt Nvidia's near-term profitability...",
  "topics": ["semiconductor exports", "U.S.-China trade relations", "Vera Rubin project", "chip manufacturing"],
  "entities": ["Nvidia", "China", "Vera Rubin", "Biden administration"],
  "entities_enriched": [
    {
      "name": "Nvidia",
      "type": "organization",
      "role": "subject",
      "ticker": "NVDA",
      "sentiment": "neutral",
      "sentiment_score": 0
    }
  ],
  "sentiment": "neutral",
  "impact_score": 7.2,
  "tags": ["tech", "markets", "startups", "politics"],
  "source_count": 3,
  "highlights": {
    "headline": "<mark>Nvidia</mark> Shifts Focus from China Exports to Vera Rubin Development",
    "summary": "Chip giant abandons China-bound semiconductor production...",
    "body_snippet": "strategic realignment may influence <mark>Nvidia</mark>'s market valuation..."
  }
}
```

说明：

- `sources` 在此条目中为空数组，故映射为 `get_news` 时 **`url` 可为空字符串**（与 AV 常有直连 url 不同）。
- `confidence_score` 在 `provenance` 下；`agent-feed` 变体也可能在顶层出现 `confidence` / `bias`（见探针 `04_agent_feed_bearer_200.json`）。

**同次请求第 2 条 brief**：主题为 Oracle 财报，但 `entities` / `highlights` 中提及 Nvidia（相关性略低，`search_score` 更低）。合并进 `data` 时可按 `entities_enriched[].ticker == "NVDA"` 过滤，避免噪声。

---

## 3. 字段映射：Polaris `brief` → `get_news.data[]` 一行

| `get_news.data`（AV 行） | Polaris `brief` |
|--------------------------|-----------------|
| `title` | `headline` |
| `url` | `sources[0].url`（无则 `""`） |
| `time_published` | `published_at`（ISO）→ 建议规范为 `YYYYMMDDTHHMMSS` 以贴近 AV |
| `summary` | `summary`；可选追加 `\n\n[Counter-argument] {counter_argument}` |
| `source` | `sources[].name` 拼接；无则为 `Polaris Report` |
| `overall_sentiment_label` | `sentiment` → Bullish / Bearish / Neutral / Mixed（见 `polaris_av_news_adapter.py`） |
| `overall_sentiment_score` | 若 `entities_enriched` 含请求 ticker 的 `sentiment_score` 则取其平均并截断至 `[-1,1]`；否则由顶层 `sentiment` 粗映射 |
| （行字段） | **仅上述 7 键**，与 AV `get_news` 行一致（方案 A，无额外 `polaris_*` 列） |

---

## 4. 映射后的「工具形状」示例（仅 Polaris，未与 AV 拼接）

入库样例（可随 API 响应更新而替换）：

- `docs/samples/polaris_nvda_search_raw.example.json`：一次真实 `search` 的 `http_status` + `body`
- `docs/samples/polaris_nvda_get_news_av_shape.example.json`：`data` 为按 `polaris_brief_to_av_news_row` 映射后的列表，`summary.polaris` 含 `query` / `api_total` 等

**实测（`20260325T060442Z_*`）**：query 使用  
`NVDA stock NVIDIA earnings guidance US market` 时，`briefs=8` 全部进入 `data`，但 **多条与 NVDA 弱相关**（宽主题市场简报）。生产合并建议：

- 仅保留 `entities_enriched` 中存在 `ticker == "NVDA"` 或 `name` 含 NVIDIA 的 brief；或
- 提高 `min_confidence` / 收紧 query；或
- 用 `resolved_ticker` + 服务端排序，只取前 N 条高 `search_score`。

**生产策略（已实现）**：**不**与 AV 拼接；AV 有数据时仅返回 AV；仅当 AV 空或异常时再单独使用 Polaris 映射结果，`summary.data_source` 为 `polaris_report` 并带 `summary.polaris.fallback`。

---

## 5. `get_global_news` 与 `/api/v1/agent-feed`

`agent-feed` 返回 `briefs` 与顶层 `instruction`（见 `04_agent_feed_bearer_200.json`），条目不一定与 NVDA 或宏观日期范围对齐。

建议：

- 在现有 `content` Markdown **末尾** 增加一节 `## Polaris agent-feed（补充）`，列出若干 `headline` + `summary` + `confidence`；
- 或在 `summary` 中增加 `polaris_agent_feed_count`，避免改动 `format: markdown` 约定。

---

## 6. NVDA 的查询串（自动生成）

草案：**由代码生成**，不经 LLM。示例：

```text
{symbol} stock NVIDIA earnings guidance US market
```

与探针中 `q=NVDA stock AI`、`q=NVIDIA earnings guidance` 同类；上线后可增配置 **别名表**（如 `NVDA` → `NVIDIA Corporation`）以提高召回。

---

*关联草案：`docs/IMPLEMENTATION_IDEAS.md` 第二节*

**已实现（2026-03）**：Polaris 作为 **fallback** 写入 `news_tools.get_news` / `get_global_news`——仅当 Alpha Vantage 无数据或抛错时再请求 Polaris，**不会在 AV 成功时追加给 LLM**。HTTP 见 `datasources/polaris_report_client.py`（`trust_env=True`）。**数据集构建** `scripts/experimental/build_analyst_dataset.py` 经 `news_analyst` / `social_media_analyst` 调用同一套工具，行为一致。
