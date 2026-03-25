"""
配置加载模块：负责读取 YAML 与环境变量，提供显式验证后的统一配置字典。
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List

import yaml
from dotenv import dotenv_values


def _alpha_vantage_keys_from_env(env_vars: Dict[str, Any]) -> List[str]:
    """
    从环境读取 Alpha Vantage 密钥列表，支持：
    - ALPHA_VANTAGE_API_KEY_1 .. ALPHA_VANTAGE_API_KEY_N（按数字序）
    - 若无编号变量，则回退 ALPHA_VANTAGE_API_KEY
    先读 .env（dotenv_values），再读 os.environ，同名序号以后者为准。
    """
    pattern = re.compile(r"^ALPHA_VANTAGE_API_KEY_(\d+)$")
    by_idx: Dict[int, str] = {}

    def ingest_numbered(mapping: Dict[str, Any]) -> None:
        if not mapping:
            return
        for name, raw in mapping.items():
            if raw is None or name is None:
                continue
            val = str(raw).strip().strip("\"'")
            if not val:
                continue
            m = pattern.match(str(name).strip())
            if m:
                by_idx[int(m.group(1))] = val

    ingest_numbered(env_vars or {})
    ingest_numbered(dict(os.environ))

    if by_idx:
        return [by_idx[k] for k in sorted(by_idx.keys())]

    single = (env_vars.get("ALPHA_VANTAGE_API_KEY") if env_vars else None) or os.getenv(
        "ALPHA_VANTAGE_API_KEY", ""
    )
    single = str(single).strip().strip("\"'")
    return [single] if single else []


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
        "BASE_URL": ("llm", "base_url"),
        "TUSHARE_TOKEN": ("data_sources", "tushare_token"),
        "CURRENCY_API_KEY": ("data_sources", "currency_api_key"),
        "CURRENCYSCOOP_API_KEY": ("data_sources", "currency_api_key"),  # 别名支持
        "SQLITE_PATH": ("storage", "sqlite_path"),
        "CHROMA_PERSIST_DIRECTORY": ("storage", "chroma_persist_directory"),
        "CHROMA_COLLECTION": ("storage", "chroma_collection"),
        "POLARIS_TOKEN": ("data_sources", "polaris_token"),
    }

    for env_key, (section, key) in mapping.items():
        env_value = env_vars.get(env_key)
        if env_value:
            config[section][key] = env_value

    polaris_alt = env_vars.get("POLARIS_API_KEY")
    if polaris_alt and not (config.get("data_sources") or {}).get("polaris_token"):
        config["data_sources"]["polaris_token"] = polaris_alt

    ds = config.setdefault("data_sources", {})
    ds.pop("alpha_vantage_api_key_env", None)  # 历史误用字段，避免干扰 Provider

    existing_av = ds.get("alpha_vantage_api_keys")
    has_yaml_av = isinstance(existing_av, list) and any(
        str(x).strip() for x in existing_av if x
    )
    if not has_yaml_av:
        av_keys = _alpha_vantage_keys_from_env(env_vars)
        if av_keys:
            ds["alpha_vantage_api_keys"] = av_keys

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

