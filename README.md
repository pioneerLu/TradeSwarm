# note
Agent 的改动简述：
- 数据源：重构 AkShare/Tushare 为工具库（封装成provider，避免开一堆文件），新闻拆分微观/宏观，统一 Markdown 输出。
- 基本面：新增公司信息、报表、指标、估值、业绩工具，AkShare 优先、Tushare 兜底，输出含 core/preview/meta，便于 LLM 直接使用。
- 分析师：在cx的版本基础上 调整了fundamentals_analyst 角色提示与工具清单，中文汇报。
- social_media：等cz搞定媒体数据源之后我接入
- 
# TODO
- [ ] 加入memory
- [ ] state传递内容设计
  
### ps：我们之后的prompt最好用中文写
运行示例：
`python -m tradingagents.agents.analysts.fundamentals_analyst`