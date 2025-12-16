# original design: get messages from state in chain

# Market Analyst  
result = chain.invoke(state["messages"]) [1](#3-0)   
  
# Social Media Analyst    
result = chain.invoke(state["messages"]) [2](#3-1)   
  
# Fundamentals Analyst  
result = chain.invoke(state["messages"]) [3](#3-2)   
  
# News Analyst  
result = chain.invoke(state["messages"]) [4](#3-3)

# Notes
state["messages"] 初始为空列表，随着 agent 执行逐步填充
每个 agent 的输出会添加新的消息到 state 中，传递给下一个 agent
消息格式遵循 LangChain 的消息规范（SystemMessage, HumanMessage, AIMessage 等）
这种设计使得 agent 之间能够保持对话上下文和协作历史

消息通过 LangGraph 的 stream 机制流转
stream主要用于实时监控而非并行执行

# Streamflow
# Market Analyst完成后，设置Social Analyst为in_progress  
if "market_report" in chunk:  
    message_buffer.update_agent_status("Market Analyst", "completed")  
    if "social" in selections["analysts"]:  
        message_buffer.update_agent_status("Social Analyst", "in_progress")  
  
# Social Analyst完成后，设置News Analyst为in_progress    
if "sentiment_report" in chunk:  
    message_buffer.update_agent_status("Social Analyst", "completed")  
    if "news" in selections["analysts"]:  
        message_buffer.update_agent_status("News Analyst", "in_progress")


# task for xu
和前三个一样改写一下 fundamentals_analyst.py 然后 main 的 langgraph 测试可以跑通就可以了