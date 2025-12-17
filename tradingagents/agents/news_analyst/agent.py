from typing import Callable, Any
from pathlib import Path
from jinja2 import Template
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel

from .state import NewsAnalystState


def create_news_analyst(llm: BaseChatModel) -> Callable[[NewsAnalystState], dict[str, Any]]:
    """
    创建 News Analyst agent 节点函数
    
    该函数返回一个符合 LangGraph 节点规范的函数，用于执行新闻和宏观经济分析。
    agent 会分析过去7天的全球新闻和公司特定事件，生成详细的新闻分析报告。
    
    Args:
        llm: LangChain BaseChatModel 实例，用于驱动 agent 的推理和决策
        
    Returns:
        news_analyst_node: 一个接受 NewsAnalystState 并返回更新字典的函数
        
    节点函数返回值:
        dict 包含以下键:
            - messages: 更新后的消息历史（append 策略）
            - news_report: 生成的新闻分析报告文本
    
    实现细节:
        - 从 prompt.j2 加载 Jinja2 模板并渲染 system prompt
        - 使用 LangChain 的 create_agent 创建 agent 实例
        - 仅当 agent 未调用工具时，才提取最终报告内容
    """
    
    def news_analyst_node(state: NewsAnalystState) -> dict[str, Any]:
        """
        News Analyst 节点的执行函数
        
        Args:
            state: 当前的 NewsAnalystState
            
        Returns:
            包含 messages 和 news_report 的更新字典
        """
        # 第一阶段：准备参数
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        
        # NOTE: 工具列表需要用户根据实际情况补充
        # 例如: get_news, get_global_news 等
        tools = [
            # get_news,
            # get_global_news,
        ]
        
        # 第二阶段：加载并渲染 prompt 模板
        prompt_path = Path(__file__).parent / "prompt.j2"
        with open(prompt_path, "r", encoding="utf-8") as f:
            template = Template(f.read())
        
        system_prompt = template.render(
            tool_names=", ".join([tool.name for tool in tools]),
            current_date=current_date,
            ticker=ticker
        )
        
        # 第三阶段：创建并调用 agent
        agent = create_agent(
            model=llm,
            tools=tools,
            system_prompt=system_prompt
        )
        
        result = agent.invoke({
            "messages": state["messages"]
        })
        
        # 第四阶段：提取结果
        # 仅当没有工具调用时，说明 agent 已生成最终报告
        news_report = ""
        if len(result["messages"][-1].tool_calls) == 0:
            news_report = result["messages"][-1].content
        
        return {
            "messages": result["messages"],
            "news_report": news_report,
        }
    
    return news_analyst_node
