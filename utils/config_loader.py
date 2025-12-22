"""
配置加载模块：负责读取 YAML 与环境变量，提供显式验证后的统一配置字典。
"""

from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import dotenv_values


def load_config() -> Dict[str, Any]:
    """
    加载配置文件并应用环境变量覆盖，返回经过校验的配置字典。

    参数:
        无。

    返回:
        Dict[str, Any]: 合并且校验后的配置数据。

    关键实现细节:
        - 第一阶段：定位配置路径并确保配置文件存在
        - 第二阶段：读取 YAML 内容并初始化必要配置段
        - 第三阶段：加载 .env 变量并按映射覆盖 YAML 值
        - 第四阶段：校验存储配置，防止运行期缺失
    """

    # 第一阶段：路径解析与存在性校验
    project_root = Path(__file__).resolve().parent.parent
    env_path = project_root / ".env"
    config_path = project_root / "config" / "config.yaml"

    if not config_path.exists():
        raise FileNotFoundError("缺少 config/config.yaml 配置文件")

    # 第二阶段：读取 YAML 并准备配置段
    config: Dict[str, Any] = {}
    with config_path.open("r", encoding="utf-8") as config_file:
        loaded_config = yaml.safe_load(config_file) or {}
        if not isinstance(loaded_config, dict):
            raise ValueError("config/config.yaml 内容必须为字典结构")
        config.update(loaded_config)

    for section in ("llm", "data_sources", "storage"):
        section_value = config.get(section)
        if not isinstance(section_value, dict):
            config[section] = {}

    # 第三阶段：环境变量覆盖
    env_vars = dotenv_values(env_path)
    mapping: Dict[str, tuple[str, str]] = {
        "MODEL_NAME": ("llm", "model_name"),
        "DASHSCOPE_API_KEY": ("llm", "api_key"),
        "BASE_URL": ("llm", "base_url"),
        "TUSHARE_TOKEN": ("data_sources", "tushare_token"),
        "SQLITE_PATH": ("storage", "sqlite_path"),
        "CHROMA_PERSIST_DIRECTORY": ("storage", "chroma_persist_directory"),
        "CHROMA_COLLECTION": ("storage", "chroma_collection"),
    }

    for env_key, (section, key) in mapping.items():
        env_value = env_vars.get(env_key)
        if env_value:
            config[section][key] = env_value

    # 第四阶段：存储配置校验
    storage_config = config.get("storage", {})
    required_storage_keys = (
        "sqlite_path",
        "chroma_persist_directory",
        "chroma_collection",
    )
    missing_fields = [field for field in required_storage_keys if not storage_config.get(field)]
    if missing_fields:
        raise ValueError(f"storage 配置缺失或为空: {', '.join(missing_fields)}")

    return config

