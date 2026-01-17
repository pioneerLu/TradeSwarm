# TradeSwarm 自治多时间尺度系统设计文档

> 本文档用于记录 TradeSwarm 实验性系统的整体设计思想、核心结构与关键概念，作为**开发与研究并行推进**的长期参考文档。

---

## 1. 设计目标

TradeSwarm 的目标并非构建一次性推理或短期交互式的交易系统，而是一个：

* 可**连续自治运行数周**
* 具备**多智能体协作能力**
* 能同时处理**中高频与低频信息**
* 拥有**长期记忆与自我稳定机制**

的实验性研究框架。

系统强调：

* 可解释性
* 结构清晰性
* 对研究假设与因子分析友好

---

## 2. 总体系统架构

系统采用分层、流水线式结构：

```
Raw Data
   ↓
Factor Layer (外生因子状态)
   ↓
Parallel Analysts (并行分析)
   ↓
Analyst Memory (长期/短期记忆)
   ↓
Fusion Layer (时间感知融合)
   ↓
Researcher (研究推理)
   ↓
Manager (决策与风控)
```

各层之间**单向流动、职责明确**，避免循环依赖与自我放大。

---

## 3. 多时间尺度设计（Multi-Timescale Design）

系统显式区分不同时间尺度的信息与决策权限，以保证长期稳定性。

### 3.1 时间尺度划分

| 时间尺度     | 典型频率   | 主要信息       | 作用        |
| -------- | ------ | ---------- | --------- |
| Intraday | 秒 / 分  | 盘口、价格、成交量  | 快速响应、风险控制 |
| Daily    | 日（收盘后） | 行情汇总、新闻、公告 | 形成阶段性判断   |
| Slow     | 周 / 月  | 宏观、结构性信息   | 稳定长期信念    |

### 3.2 权限原则

* **盘中（Intraday）**：

  * 不允许修改长期 belief
  * 不写入长期 memory
  * 只能调整短期状态与风险

* **收盘后（Daily）**：

  * 允许写入 analyst memory
  * 触发融合与研究推理

* **低频（Slow）**：

  * 进行 memory consolidation
  * 更新长期信念与 regime

---

## 4. Analyst 设计原则

Analyst 是系统中的基础感知单元，遵循以下原则：

* **并行运行**，互不通信
* **无状态**，不读取历史 memory
* **只分析，不决策**
* 输出**结构化报告**，而非自由文本

Analyst 报告用于：

* 写入 Analyst Memory
* 为 Fusion 提供多视角输入

---

## 5. Memory 系统设计

Memory 是 TradeSwarm 实现长期自治的核心组件。

### 5.1 Memory 分层

1. **Intraday State Memory**

   * 高频、短生命周期
   * 保存盘中状态与异常标记

2. **Episodic Analyst Memory**

   * 天级 / 周级
   * 存储 analyst 的结构化输出
   * 带时间衰减权重

3. **Semantic / Belief Memory**

   * 周 / 月级
   * 存储稳定趋势与长期判断

4. **Factor Regime Memory**

   * 专用于外生因子与市场状态
   * 生命周期最长

---

## 6. Memory Consolidation（记忆整合）

为防止 memory 膨胀与噪声累积，系统定期执行 consolidation：

* 合并相似 analyst 结论
* 移除低置信度或失效信息
* 提炼长期 belief 与 recurring risk

该过程通常在低频时间尺度触发。

---

## 7. Fusion Layer（融合层）

Fusion 层并非简单拼接信息，而是：

* 对齐多 analyst 的观点
* 结合历史 memory
* 引入因子与 regime 约束
* 显式识别共识与冲突

Fusion 的输出是 **Researcher 可直接推理的结构化输入**。

---

## 8. Factor Layer（因子层）

### 8.1 因子的系统定位

因子被视为：

> 外部、可检验、缓慢演化的市场状态描述（latent state）

而不是交易信号或 analyst 意见。

### 8.2 因子抽象原则

* 不使用原始数值
* 只以**状态**形式存在（高/低、上升/下降、极端/中性）
* 按 **Factor Family** 组织（如 Value、Momentum）

### 8.3 因子的作用

* 约束 analyst 观点的解释
* 作为 Fusion 的参照轴
* 为 Manager 提供行为边界

---

## 9. Researcher 与 Manager

### 9.1 Researcher

* 输入：Fusion 结果 + Memory
* 输出：研究假设、支持证据、反例与不确定性
* 不直接下交易指令

### 9.2 Manager

* 输入：Researcher 输出 + Factor Regime
* 职责：

  * 最终决策
  * 仓位与风险控制
  * 触发系统级反馈（如 memory 降权）

---

## 10. 系统稳定性与安全机制

为支持长期自治运行，系统引入以下约束：

* Analyst 不可读取自身历史结论
* Memory 必须带来源与时间戳
* 高频信息无法直接污染长期 belief
* 决策结果可反向修正 memory 权重

---

## 11. 设计哲学总结

TradeSwarm 并非追求最优即时决策，而是构建一个：

> 能长期观察、记忆、修正自身认知的多智能体研究系统。

其核心思想在于：

* 多时间尺度
* 结构化记忆
* 因子作为信念约束
* 决策与认知解耦

---

## 12. 备注

本设计文档将随着系统演进持续更新，用于：

* 指导开发
* 支撑实验设计
* 作为论文与技术报告的基础材料
