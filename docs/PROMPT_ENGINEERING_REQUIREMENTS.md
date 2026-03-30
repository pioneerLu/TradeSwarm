# Prompt 工程需求文档

本文档用于定义 pre-open 阶段 prompt 的工程要求，交付对象是后续负责 prompt 打磨的专业人员。目标是提升内容质量，同时不改动现有运行时接线方式。

## 目标

这套 prompt 必须在动态 `enabled_analysts` 条件下稳定工作，并在以下场景中持续输出稳定、可机读、可解析的 JSON：

- 单 analyst 运行
- 部分 analyst 消融实验运行
- 全量 analyst 运行

核心要求是：提升决策质量，但不能重新引入“系统里永远有四个 analyst”的隐含假设。

## 运行时上下文契约

prompt 专家应将下列变量视为主要运行时接口。

### 必须依赖的动态输入

- `enabled_analysts_text`
  - 本次运行启用的 analyst 列表的可读文本
  - 示例：`market, news`
- `active_analyst_blocks`
  - 本次运行中 analyst 证据块的主输入
  - 这是 prompt 中 analyst 输入的首要信息源

### 兼容性保留输入

以下变量可能仍会存在，用于兼容旧代码，但不应再作为 prompt 的主要组织方式：

- `market_today_report`
- `market_history_report`
- `news_today_report`
- `news_history_report`
- `sentiment_today_report`
- `sentiment_history_report`
- `fundamentals_today_report`
- `fundamentals_history_report`

要求：

- prompt 不能依赖“所有 legacy 字段一定都有值”这一前提
- 即使只有 `enabled_analysts_text` 和 `active_analyst_blocks`，prompt 也必须能完整表达任务和输入上下文

## 角色边界

### Bull / Bear Researchers

必须做到：

- 只基于当前启用 analyst 的证据进行论证
- 给出明确方向性的观点，而不是泛泛总结
- 回应对手的论点，而不是重复自己的上一轮说法
- 显式使用 `active_analyst_blocks` 中的证据

不能出现：

- 把未启用 analyst 当成已参与
- 编造不存在的证据
- 在证据混合时立刻退化成空泛的 `HOLD`

### Research Manager

必须做到：

- 综合真实启用的 analyst 输入和辩论输出
- 给出明确结论和理由
- 说明哪条证据最关键、哪项风险最未解决

不能出现：

- 继续使用固定四 analyst 面板的叙述方式
- 输出没有依据的空泛总结

### Trader

必须做到：

- 把 research 输出转成可执行的交易意图
- 优先输出具体动作，而不是被动重复上游结论
- 明确区分：不交易、低置信度交易、高置信度交易

不能出现：

- 没有充分理由就默认 `HOLD`
- 输出无法审计或无法执行的模糊交易语言

### Risk Debators / Risk Manager

必须做到：

- 仅基于本次运行可见证据挑战交易方案
- 说清楚什么风险会使交易逻辑失效
- 在证据混合时保留结构化分歧，而不是强行统一

不能出现：

- 重复旧论点却不推进讨论
- 把未启用 analyst 的证据当成已存在

## JSON 输出契约

所有要求 JSON 输出的 prompt 都必须满足以下规则。

### 硬性要求

- 输出必须是合法 JSON，且只能是 JSON
- JSON 前后不能附带任何额外解释文字
- 字段名必须和当前运行时解析器完全一致
- 枚举类字段必须限制在代码已使用的允许值集合中

### 稳定性要求

- 不要随意增加额外 key
- 数值型置信度要有明确边界，且含义稳定
- `summary` 类字段应简洁但有信息量
- 不要在本该简洁的字段里输出冗长 chain-of-thought 风格内容

### 失败规避要求

prompt 应明确提醒模型不要：

- 用 markdown 代码块包裹 JSON
- 在 JSON 后继续输出说明
- 输出不完整数组、尾逗号或格式错误对象
- 在枚举字段中混用不可解析的中英文表达

## 质量要求

### 决策质量

prompt 需要尽量减少以下问题：

- 缺乏理由的机械 `HOLD`
- 对 analyst 输入的重复复述
- 结论空泛、看不出决策依据
- 辩论回合之间没有真正响应对手

### 证据使用

prompt 应鼓励：

- 显式使用当前运行中的 analyst 证据
- 在 analyst 输入不完整时明确指出缺失信息
- 在 1 analyst、2 analyst、4 analyst 模式下都能保持推理成立

### 消融实验鲁棒性

当只启用一个 analyst 时，prompt 也必须表现合理。

要求：

- 不得使用暗示“委员会审议”或“多方一致”的措辞
- 不得提及并不存在的缺失证据，好像它已经被审阅过
- 应明确说明结论仅建立在当前启用 analyst 子集之上

## 风格要求

prompt 专业人员应重点提升：

- 表达清晰度
- 去冗余
- 证据到结论的连接强度
- 输出的可执行性

同时必须保留：

- 当前角色分工
- 当前 JSON schema
- 动态 analyst 兼容性
- 机器可读性

## 验收标准

一套新的 prompt 版本只有在满足以下条件时才算合格。

### 功能验收

- `enabled_analysts=market` 时可正常工作
- `enabled_analysts=market,news` 时可正常工作
- `enabled_analysts=market,news,sentiment,fundamentals` 时可正常工作
- 所有依赖 prompt 输出 JSON 的节点都能得到合法 JSON

### 行为验收

- 不再使用固定四 analyst 的表达方式
- 能使用当前 analyst 输入，而不是依赖占位式历史变量
- 明显减少空泛或无理由的 `HOLD`
- 辩论回合能对上一轮输出形成有效回应

### 兼容性验收

- 除非和工程实现同步协商，否则不得修改运行时变量名
- 除非和工程实现同步协商，否则不得修改下游 JSON schema
- 不得依赖当前运行时没有提供的隐藏变量
