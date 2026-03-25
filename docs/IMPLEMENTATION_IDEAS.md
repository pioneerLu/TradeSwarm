# 实现想法与待讨论项

记录尚未实现但值得考虑的技术方案，供后续迭代参考。

---

## 一、基于 Tool 返回值判断 API 失败（替代关键词检测）

**状态**：待实现，暂不改动

**背景**：当前 `scripts/experimental/build_analyst_dataset.py` 和 `check_api_failures.py` 通过报告文本中的关键词（如「暂时不可用」「API访问限制」「data_points_analyzed: 0」）判断报告是否因 API 失败而无效。这种方式容易误判或漏判。

**提议**：在 Analyst 执行时，直接根据 **Tool 调用的返回值或报错** 判断是否失败，而非事后解析报告文本。

### 当前架构要点

1. **工具已有结构化返回**：如 `get_stock_data` 返回 `{"success": false, "message": "未找到股票...", "data": []}` 表示失败。
2. **执行流程**：`agent.invoke()` 后，`result["messages"]` 包含 `ToolMessage`，其 `content` 即为工具返回的 JSON 字符串。
3. **可行做法**：遍历 `result["messages"]`，解析每个 `ToolMessage` 的 content，检查 `success` 是否为 `false`。

### 方案对比

| 维度 | 关键词检测 | 基于 tool 返回值 |
|------|------------|-----------------|
| 准确性 | 易误判、漏判 | 直接反映工具执行结果 |
| 实现位置 | 写入 DB 前检查报告文本 | Analyst 执行后检查 ToolMessage |
| 覆盖范围 | 仅当 LLM 在报告中写了失败表述 | 覆盖工具实际失败的情况 |
| LLM 未调工具 | 无法判断 | 无 ToolMessage，需单独策略 |
| 部分失败 | 难以区分 | 可逐条检查每个工具结果 |

### 实现思路

**思路 1：在 Analyst 节点内检查 ToolMessage**

在 `market_analyst_node` 等节点中，`agent.invoke()` 之后：

```python
# 伪代码
tool_failed = False
for msg in result["messages"]:
    if isinstance(msg, ToolMessage):
        try:
            data = json.loads(msg.content)
            if data.get("success") is False:
                tool_failed = True
                break
        except: pass
if tool_failed:
    return {"market_report": "", "tool_failed": True}  # 或抛出让上层不写入 DB
```

**思路 2：统一工具包装**

给工具加一层包装，在调用时记录成功/失败，Agent 执行完后统一检查。需要改工具或 `create_agent` 的绑定方式。

**思路 3：在 `build_analyst_dataset` 中处理**

让 Analyst 节点返回 `tool_failed` 等状态，`run_analysts_for_date` 根据该状态决定是否写入 DB。

### 待确认事项

1. **工具返回格式是否统一**：`get_news`、`get_company_info` 等是否都有 `success` 字段？失败时是返回 `{"success": false}` 还是抛异常？
2. **LLM 未调工具**：若 LLM 直接生成报告而不调工具，无 ToolMessage。策略：无 ToolMessage 时仍用关键词兜底，或要求 Analyst 必须调工具（通过 prompt 约束）。
3. **部分失败策略**：如 `get_stock_data` 成功、`get_indicators` 失败。可选：任一工具失败即视为失败，或按工具重要性分级处理。
4. **历史报告**：新逻辑只对「执行时」有效；对已入库的历史报告（如 `--only-missing` 时从 DB 读取），仍需关键词或类似方式判断是否需重建。

### 建议

- **新建报告**：优先用 tool 返回值判断，在 Analyst 节点中解析 ToolMessage 并设置 `tool_failed`，数据集脚本据此决定是否写入 DB。
- **历史报告**：保留关键词检测作为兜底，用于 `check_api_failures` 和 `--only-missing` 时的重建判断。
- **下一步**：先确认 `get_news`、`get_company_info` 等工具的返回格式，再选一个 Analyst（如 market）做试点实现。

---

## 二、Polaris 数据源：Prompt 不变、仅改 `get_news` / `get_global_news` 背后实现

**状态**：已实现（fallback）；**不**再使用独立 `polaris_*` 工具或改 prompt。

**目标**

- **不改动** `news_analyst` / `social_media_analyst` 的 `prompt.j2`（流程仍只有 `get_news`、`get_global_news`）。
- **工具名与签名不变**；LLM 侧行为约定不变。
- Polaris 作为 **fallback**：在 `news_tools.py` 内**仅当** AV 无数据或异常时调用 Polaris，AV 成功时不追加 Polaris；返回 JSON 中 `summary.polaris.fallback` 等字段标明来源。

**实现要点**

- 用 `(symbol, 日期区间)` 或模板自动生成 Polaris `search` 的 `q`（可选后续加「标的别名」提高召回）。
- `get_global_news` 在 fallback 时使用 `agent-feed`，以 Markdown 附录形式并入 `content`。
- 失败策略：AV 与 Polaris 独立；返回体中通过 `summary` / `message` 标明来源与错误片段。
- 字段映射与说明：`docs/POLARIS_NVDA_TOOL_ADAPTER.md`；**入库样例 JSON**：`docs/samples/polaris_nvda_search_raw.example.json`、`docs/samples/polaris_nvda_get_news_av_shape.example.json`。
- **数据集构建** `scripts/experimental/build_analyst_dataset.py` 与主流程共用上述工具，配置 `POLARIS_*` 后即具备相同 fallback。

**待决 / 改进**

- Polaris `search` 宽 query 可能混入弱相关 brief，已在 `news_tools` 中按 ticker / 正文做过滤，可继续收紧（见 `POLARIS_NVDA_TOOL_ADAPTER.md`）。

---

*最后更新：2026-03*
