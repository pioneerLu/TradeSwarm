from langchain_openai import ChatOpenAI
from langchain.messages import HumanMessage, AIMessage, SystemMessage
import os


def init_llm(config: dict) -> ChatOpenAI:
    """
    Initialize the LLM from the provided configuration.
    
    注意：qwen API 不支持代理，因此会临时禁用环境变量中的代理设置。
    
    Args:
        config (dict): The configuration dictionary containing an 'llm' section.
        
    Returns:
        ChatOpenAI: The initialized LangChain ChatOpenAI object.
    """
    llm_config = config.get("llm", {})

    # 临时禁用代理（qwen 不支持代理，且 LLM 调用不应走代理）
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        if key in os.environ:
            del os.environ[key]

    # 创建 httpx 客户端，明确禁用代理、忽略系统环境中的代理设置
    import httpx

    http_client = httpx.Client(
        verify=True,
        trust_env=False,
        proxy=None,
    )

    llm = ChatOpenAI(
        api_key=llm_config.get("api_key"),
        base_url=llm_config.get("base_url"),
        model=llm_config.get("model_name"),
        temperature=llm_config.get("temperature", 0.1),
        http_client=http_client,  # 使用自定义的 http_client（不包含代理）
    )

    return llm
