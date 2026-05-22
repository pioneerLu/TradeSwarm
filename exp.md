# 实验矩阵

**统一回测窗口**：`2024-01-02` ~ `2024-03-29`（预检可用 `2025-01-02` ~ `2025-01-10`）。**默认**：标的 `TSLA`、大模型 `通义千问 Qwen3-32B`、模块为完整配置、评测为交错回测。每行跑前须完成对应标的的 data prep（`analyst_reports` / `analyst_summaries`）。


| 实验编号        | 阶段   | 标的（代码）     | 大模型            | 分析师组合              | 模块消融              | 评测方式 | 启用分析师（命令行）                         | 额外参数或配置                                    | 完成  | 总收益率 | 夏普比率 | 最大回撤 |
| ----------- | ---- | ---------- | -------------- | ------------------ | ----------------- | ---- | ---------------------------------- | ------------------------------------------ | --- | ---- | ---- | ---- |
| 预检_冒烟       | 预检   | 特斯拉（TSLA）  | 通义千问 Qwen3-32B | 仅市场                | 完整配置              | 交错回测 | market                             | 研究/风险辩论各 1 轮；短窗口                           | ☐   |      |      |      |
| 预检_买入持有基准   | 预检   | 特斯拉（TSLA）  | —              | —                  | —                 | 规则基准 | —                                  | `--strategies "bh"`                        | ☐   |      |      |      |
| 领域_仅市场      | 多领域  | 特斯拉（TSLA）  | 通义千问 Qwen3-32B | 仅市场                | 完整配置              | 交错回测 | market                             |                                            | ☐   |      |      |      |
| 领域_市场加新闻    | 多领域  | 特斯拉（TSLA）  | 通义千问 Qwen3-32B | 市场 + 新闻            | 完整配置              | 交错回测 | market,news                        |                                            | ☐   |      |      |      |
| 领域_市场加情绪    | 多领域  | 特斯拉（TSLA）  | 通义千问 Qwen3-32B | 市场 + 情绪            | 完整配置              | 交错回测 | market,sentiment                   |                                            | ☐   |      |      |      |
| 领域_市场加基本面   | 多领域  | 特斯拉（TSLA）  | 通义千问 Qwen3-32B | 市场 + 基本面           | 完整配置              | 交错回测 | market,fundamentals                |                                            | ☐   |      |      |      |
| 领域_四分析师完整   | 多领域  | 特斯拉（TSLA）  | 通义千问 Qwen3-32B | 市场 + 新闻 + 情绪 + 基本面 | 完整配置              | 交错回测 | market,news,sentiment,fundamentals | **主基线**                                    | ☐   |      |      |      |
| 领域_留一_去掉新闻  | 多领域  | 特斯拉（TSLA）  | 通义千问 Qwen3-32B | 全量去掉新闻             | 完整配置              | 交错回测 | market,sentiment,fundamentals      |                                            | ☐   |      |      |      |
| 领域_留一_去掉情绪  | 多领域  | 特斯拉（TSLA）  | 通义千问 Qwen3-32B | 全量去掉情绪             | 完整配置              | 交错回测 | market,news,fundamentals           |                                            | ☐   |      |      |      |
| 领域_留一_去掉基本面 | 多领域  | 特斯拉（TSLA）  | 通义千问 Qwen3-32B | 全量去掉基本面            | 完整配置              | 交错回测 | market,news,sentiment              |                                            | ☐   |      |      |      |
| 模型_通义千问     | 多模型  | 特斯拉（TSLA）  | 通义千问 Qwen3-32B | 四分析师完整             | 完整配置              | 交错回测 | market,news,sentiment,fundamentals | `--llm-profile qwen3_32b`                  | ☐   |      |      |      |
| 模型_DeepSeek | 多模型  | 特斯拉（TSLA）  | DeepSeek V3    | 四分析师完整             | 完整配置              | 交错回测 | market,news,sentiment,fundamentals | `--llm-profile deepseek_v3`                | ☐   |      |      |      |
| 模型_GLM      | 多模型  | 特斯拉（TSLA）  | GLM-4-9B 对话    | 四分析师完整             | 完整配置              | 交错回测 | market,news,sentiment,fundamentals | `--llm-profile glm_4_9b`                   | ☐   |      |      |      |
| 标的_特斯拉      | 多标的  | 特斯拉（TSLA）  | 通义千问 Qwen3-32B | 四分析师完整             | 完整配置              | 交错回测 | market,news,sentiment,fundamentals |                                            | ☐   |      |      |      |
| 标的_摩根大通     | 多标的  | 摩根大通（JPM）  | 通义千问 Qwen3-32B | 四分析师完整             | 完整配置              | 交错回测 | market,news,sentiment,fundamentals | 须单独 data prep                              | ☐   |      |      |      |
| 标的_埃克森美孚    | 多标的  | 埃克森美孚（XOM） | 通义千问 Qwen3-32B | 四分析师完整             | 完整配置              | 交错回测 | market,news,sentiment,fundamentals | 须单独 data prep                              | ☐   |      |      |      |
| 模块_完整基线     | 模块消融 | 特斯拉（TSLA）  | 通义千问 Qwen3-32B | 四分析师完整             | 完整配置              | 交错回测 | market,news,sentiment,fundamentals | 同「领域_四分析师完整」                               | ☐   |      |      |      |
| 模块_研究辩论一轮   | 模块消融 | 特斯拉（TSLA）  | 通义千问 Qwen3-32B | 四分析师完整             | 研究子图辩论减为 1 轮      | 交错回测 | market,news,sentiment,fundamentals | `--max-research-debate-rounds 1`           | ☐   |      |      |      |
| 模块_风险辩论一轮   | 模块消融 | 特斯拉（TSLA）  | 通义千问 Qwen3-32B | 四分析师完整             | 风险子图辩论减为 1 轮      | 交错回测 | market,news,sentiment,fundamentals | `--max-risk-debate-rounds 1`               | ☐   |      |      |      |
| 模块_关闭策略技能   | 模块消融 | 特斯拉（TSLA）  | 通义千问 Qwen3-32B | 四分析师完整             | 关闭 Trader 策略技能注入  | 交错回测 | market,news,sentiment,fundamentals | `--strategy-skills-mode off`               | ☐   |      |      |      |
| 模块_全开策略技能   | 模块消融 | 特斯拉（TSLA）  | 通义千问 Qwen3-32B | 四分析师完整             | 注入全部策略技能模板        | 交错回测 | market,news,sentiment,fundamentals | `--strategy-skills-mode all`               | ☐   |      |      |      |
| 模块_仅数据库记忆   | 模块消融 | 特斯拉（TSLA）  | 通义千问 Qwen3-32B | 四分析师完整             | 长记忆仅用 SQLite 周期反思 | 交错回测 | market,news,sentiment,fundamentals | `config.yaml` → `memory.mode: sql_only`    | ☐   |      |      |      |
| 模块_仅向量库记忆   | 模块消融 | 特斯拉（TSLA）  | 通义千问 Qwen3-32B | 四分析师完整             | 长记忆仅用 Chroma 向量召回 | 交错回测 | market,news,sentiment,fundamentals | `config.yaml` → `memory.mode: chroma_only` | ☐   |      |      |      |


**实验标识建议**：`{实验编号}_{代码}_主窗口`（示例：`领域_四分析师完整_TSLA_主窗口`）。指标自 `storage/interleaved_backtests/` 汇总 JSON 的 `metrics` 填写；规则基准自 `storage/baseline_backtests/`。

```powershell
python scripts\runtime\run_interleaved_backtest.py `
  --symbol TSLA --start 2024-01-02 --end 2024-03-29 `
  --db storage\db\memory.db --initial-cash 100000 `
  --enabled-analysts market,news,sentiment,fundamentals `
  --experiment-id 领域_四分析师完整_TSLA_主窗口 `
  --llm-profile qwen3_32b `
  --report-output-root storage\reports --graph-dump storage\graph_dumps -v
```

