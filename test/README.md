# Manager 和 Risk Management 节点测试

本目录包含用于验证 Manager 和 Risk Management 节点在新 AgentState 结构下是否正常运行的测试脚本。

## 测试文件

- `test_research_manager.py`: 测试 Research Manager 节点
- `test_risk_manager.py`: 测试 Risk Manager 节点
- `test_conservative_debator.py`: 测试 Conservative Debator (Safe Debator) 节点
- `test_all_managers.py`: 综合测试脚本，运行所有上述测试

## 运行测试

### 运行单个测试

```bash
# 测试 Research Manager
python test/test_research_manager.py

# 测试 Risk Manager
python test/test_risk_manager.py

# 测试 Conservative Debator
python test/test_conservative_debator.py
```

### 运行所有测试

```bash
# 使用综合测试脚本
python test/test_all_managers.py
```

## 测试数据

所有测试使用 A 股股票代码 `000001`（平安银行）作为测试标的，测试数据包括：

- **Market Analyst Summary**: 市场分析报告（银行板块表现）
- **News Analyst Summary**: 新闻分析报告（零售业务转型）
- **Sentiment Analyst Summary**: 情绪分析报告（数字化转型）
- **Fundamentals Analyst Summary**: 基本面分析报告（资产质量改善）

## 验证内容

每个测试脚本验证以下内容：

1. **节点创建**: 验证节点工厂函数可以正常创建节点
2. **状态处理**: 验证节点可以正确处理新的 AgentState 结构
3. **数据封装**: 验证 `research_summary` 和 `risk_summary` 的封装结构
4. **输出格式**: 验证节点返回的数据格式符合预期

## 注意事项

- 确保已配置 `.env` 文件中的 `DASHSCOPE_API_KEY`
- 测试需要网络连接以调用 LLM API
- 测试可能需要一些时间完成（取决于 LLM 响应速度）

