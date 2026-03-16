"""
Graph 工具函数

包含 LLM 初始化等工具函数。
"""

from pathlib import Path
import yaml
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os

load_dotenv()


def load_llm_from_config(config_path: str = "config/config.yaml") -> ChatOpenAI:
    """
    从 config.yaml 读取 LLM 配置并初始化 ChatOpenAI 实例。
    
    注意：qwen API 不支持代理，因此会临时禁用环境变量中的代理设置。
    
    Args:
        config_path: 配置文件路径，默认为 "config/config.yaml"
        
    Returns:
        初始化好的 ChatOpenAI 实例
    """
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    with open(config_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    llm_config = config.get("llm", {})
    
    # 如果配置了 SiliconFlow（优先级最高），则使用 Silicon + Qwen3
    silicon_api = os.getenv("Silicon_API_KEY") or os.getenv("SILICON_API_KEY")
    if silicon_api:
        silicon_cfg = llm_config.get("silicon", {}) or {}
        api_key = silicon_api.strip().strip("\"'")
        base_url = (
            os.getenv("base_url_silicon")
            or os.getenv("BASE_URL_SILICON")
            or silicon_cfg.get("base_url")
            or "https://api.siliconflow.cn/v1"
        )
        model_name = (
            os.getenv("SILICON_MODEL")
            or silicon_cfg.get("model_name")
            or "Qwen/Qwen3-32B"
        )
        temperature = silicon_cfg.get("temperature", llm_config.get("temperature", 0.1))
    else:
        # 默认走 DashScope Qwen
        api_key = os.getenv("DASHSCOPE_API_KEY") or llm_config.get("api_key")
        if not api_key:
            raise ValueError("未找到 API Key，请设置环境变量 DASHSCOPE_API_KEY 或 Silicon_API_KEY，或在配置文件中设置")
        base_url = llm_config.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        model_name = llm_config.get("model_name", "qwen-plus")
        temperature = llm_config.get("temperature", 0.1)
    
    # 临时禁用代理（qwen 不支持代理）
    if 'HTTP_PROXY' in os.environ:
        del os.environ['HTTP_PROXY']
    if 'HTTPS_PROXY' in os.environ:
        del os.environ['HTTPS_PROXY']
    
    # 创建 httpx 客户端，明确禁用代理
    import httpx
    http_client = httpx.Client(
        verify=True,
        trust_env=False,
        proxy=None,
        timeout=httpx.Timeout(60.0),
    )
    
    llm = ChatOpenAI(
        api_key=api_key,
        base_url=base_url,
        model=model_name,
        temperature=temperature,
        http_client=http_client,
    )
    
    return llm


def create_chroma_memory_if_available(collection_name: str = "tradeswarm_reflections"):
    """
    若已配置 DASHSCOPE_API_KEY，创建 FinancialSituationMemory 供 Reflector 写入 ChromaDB。
    失败时返回 None，Reflector 仅写入 cycle_reflections 表，不影响主流程。
    """
    try:
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            return None
        from datasources.utils.memory.financial_situation_memory import FinancialSituationMemory
        config = {
            "api_key": api_key,
            "backend_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        }
        return FinancialSituationMemory(name=collection_name, config=config)
    except Exception:
        return None
