import os
from pathlib import Path

from dotenv import load_dotenv
from langchain.messages import HumanMessage, AIMessage, SystemMessage

load_dotenv()

from tradingagents.graph.utils import load_llm_from_config

_REPO_ROOT = Path(__file__).resolve().parents[4]
llm = load_llm_from_config(str(_REPO_ROOT / "config" / "config.yaml"))

system_msg = SystemMessage("You are a helpful assistant.")
human_msg = HumanMessage("how are you")

# Use with chat models
messages = [system_msg, human_msg]

# response = llm.invoke(messages)

# 测试代码已注释
# from langchain.agents import create_agent
# 
# agent = create_agent(model=llm)
# response = agent.invoke(input= {
#     "messages": messages
# })
# 
# print(response)




