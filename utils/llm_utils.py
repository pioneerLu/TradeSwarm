from langchain_openai import ChatOpenAI
from langchain.messages import HumanMessage, AIMessage, SystemMessage

def init_llm(config: dict) -> ChatOpenAI:
    """
    Initialize the LLM from the provided configuration.
    
    Args:
        config (dict): The configuration dictionary containing an 'llm' section.
        
    Returns:
        ChatOpenAI: The initialized LangChain ChatOpenAI object.
    """
    llm_config = config.get('llm', {})
    
    return ChatOpenAI(
        api_key=llm_config.get('api_key'),
        base_url=llm_config.get('base_url'),
        model=llm_config.get('model_name'),
        temperature=llm_config.get('temperature', 0.1) # Default to 0.1 if not present, though config.yaml has it
    )
