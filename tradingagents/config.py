"""
统一配置模块。

合并原 ``utils/config_loader.py`` （YAML + .env 加载）和
``tradingagents/graph/utils.py`` （LLM 初始化、辩论轮数、ChromaDB Memory）
的全部配置职责，对外暴露三个入口：

- ``get_config()``  — 返回校验后的配置字典
- ``get_llm()``     — 返回 ChatOpenAI 实例（Silicon Flow，含多 key 故障转移）
- ``get_graph_debate_rounds()`` — 返回 (research_rounds, risk_rounds)
- ``create_chroma_memory_if_available()`` — 创建 ChromaDB Memory（可选，支持持久化目录）
- ``get_memory_mode()`` — hybrid / sql_only / chroma_only
"""

from __future__ import annotations

import os
import re
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from dotenv import dotenv_values, load_dotenv

from tradingagents.llm_env_compat import (
    env_silicon_key_and_base,
    env_silicon_keys_and_base,
    silicon_llm_fallback_exception_types,
)

logger = logging.getLogger(__name__)

_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG_PATH: Path = _PROJECT_ROOT / "config" / "config.yaml"
_DEFAULT_ENV_PATH: Path = _PROJECT_ROOT / ".env"
_VALID_STRATEGY_SKILLS = {
    "strong_uptrend_skill",
    "range_bound_skill",
    "downtrend_skill",
    "high_vol_uncertain_skill",
}


# ---------------------------------------------------------------------------
# Alpha Vantage key helpers (migrated from utils/config_loader.py)
# ---------------------------------------------------------------------------

def _alpha_vantage_keys_from_env(env_vars: Dict[str, Any]) -> List[str]:
    """Parse numbered ``ALPHA_VANTAGE_API_KEY_N`` env vars, fall back to single key."""
    pattern = re.compile(r"^ALPHA_VANTAGE_API_KEY_(\d+)$")
    by_idx: Dict[int, str] = {}

    def _ingest(mapping: Dict[str, Any]) -> None:
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

    _ingest(env_vars or {})
    _ingest(dict(os.environ))

    if by_idx:
        return [by_idx[k] for k in sorted(by_idx.keys())]

    single = (env_vars.get("ALPHA_VANTAGE_API_KEY") if env_vars else None) or os.getenv(
        "ALPHA_VANTAGE_API_KEY", ""
    )
    single = str(single).strip().strip("\"'")
    return [single] if single else []


# ---------------------------------------------------------------------------
# Proxy helpers (migrated from graph/utils.py)
# ---------------------------------------------------------------------------

def _llm_proxy_enabled() -> bool:
    host = (os.getenv("PROXY_HOST") or "").strip()
    port = (os.getenv("PROXY_PORT") or "").strip()
    use_flag = (os.getenv("USE_PROXY") or "").strip().lower() == "true"
    return bool(
        (host and port) or use_flag or os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY")
    )


def _ensure_proxy_env() -> None:
    host = (os.getenv("PROXY_HOST") or "").strip()
    port = (os.getenv("PROXY_PORT") or "").strip()
    if not (host and port):
        return
    proxy_url = f"http://{host}:{port}"
    os.environ.setdefault("HTTP_PROXY", proxy_url)
    os.environ.setdefault("HTTPS_PROXY", proxy_url)
    os.environ.setdefault("http_proxy", proxy_url)
    os.environ.setdefault("https_proxy", proxy_url)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_config(config_path: Optional[str | Path] = None) -> Dict[str, Any]:
    """Load and validate the project configuration.

    Merges ``config/config.yaml`` with ``.env`` overrides and returns a
    validated configuration dictionary.

    Args:
        config_path: Override path to ``config.yaml``.  When *None* the
            default ``<project_root>/config/config.yaml`` is used.

    Returns:
        Merged and validated configuration dict.

    Raises:
        FileNotFoundError: If the YAML file is missing.
        ValueError: If required storage keys are absent.
    """
    cfg_file = Path(config_path).resolve() if config_path else _DEFAULT_CONFIG_PATH
    if not cfg_file.exists():
        raise FileNotFoundError(f"缺少配置文件: {cfg_file}")

    env_file = cfg_file.parent.parent / ".env"
    if env_file.is_file():
        load_dotenv(env_file, override=True)

    with cfg_file.open("r", encoding="utf-8") as f:
        config: Dict[str, Any] = yaml.safe_load(f) or {}
    if not isinstance(config, dict):
        raise ValueError("config.yaml 内容必须为字典结构")

    for section in ("llm", "data_sources", "storage"):
        if not isinstance(config.get(section), dict):
            config[section] = {}

    # .env overrides
    env_vars = dotenv_values(env_file) if env_file.is_file() else {}
    _env_mapping: Dict[str, tuple[str, str]] = {
        "MODEL_NAME": ("llm", "model_name"),
        "BASE_URL": ("llm", "base_url"),
        "TUSHARE_TOKEN": ("data_sources", "tushare_token"),
        "CURRENCY_API_KEY": ("data_sources", "currency_api_key"),
        "CURRENCYSCOOP_API_KEY": ("data_sources", "currency_api_key"),
        "SQLITE_PATH": ("storage", "sqlite_path"),
        "CHROMA_PERSIST_DIRECTORY": ("storage", "chroma_persist_directory"),
        "CHROMA_COLLECTION": ("storage", "chroma_collection"),
        "POLARIS_TOKEN": ("data_sources", "polaris_token"),
    }
    for env_key, (section, key) in _env_mapping.items():
        env_value = env_vars.get(env_key)
        if env_value:
            config[section][key] = env_value

    polaris_alt = env_vars.get("POLARIS_API_KEY")
    if polaris_alt and not (config.get("data_sources") or {}).get("polaris_token"):
        config["data_sources"]["polaris_token"] = polaris_alt

    ds = config.setdefault("data_sources", {})
    ds.pop("alpha_vantage_api_key_env", None)

    existing_av = ds.get("alpha_vantage_api_keys")
    has_yaml_av = isinstance(existing_av, list) and any(str(x).strip() for x in existing_av if x)
    if not has_yaml_av:
        av_keys = _alpha_vantage_keys_from_env(env_vars)
        if av_keys:
            ds["alpha_vantage_api_keys"] = av_keys

    # Validate storage
    storage_config = config.get("storage", {})
    required_storage_keys = ("sqlite_path", "chroma_persist_directory", "chroma_collection")
    missing = [k for k in required_storage_keys if not storage_config.get(k)]
    if missing:
        raise ValueError(f"storage 配置缺失或为空: {', '.join(missing)}")

    return config


def get_strategy_skills_config(
    *,
    config_path: Optional[str | Path] = None,
    mode_override: Optional[str] = None,
    fallback_mode_override: Optional[str] = None,
    force_skill_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve prompt strategy skill routing config.

    Supported modes:
    - reflect: Trader first reflects on regime/skill, then injects one selected skill.
    - all: inject all skill playbooks.
    - off: inject no skill playbook.
    """
    cfg_file = Path(config_path).resolve() if config_path else _DEFAULT_CONFIG_PATH
    config: Dict[str, Any] = {}
    if cfg_file.exists():
        with open(cfg_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    skills_cfg = config.get("strategy_skills", {}) if isinstance(config, dict) else {}
    skills_cfg = skills_cfg if isinstance(skills_cfg, dict) else {}

    mode = (
        mode_override
        or os.getenv("TRADESWARM_STRATEGY_SKILLS_MODE")
        or skills_cfg.get("mode")
        or "reflect"
    )
    fallback_mode = (
        fallback_mode_override
        or os.getenv("TRADESWARM_STRATEGY_SKILLS_FALLBACK_MODE")
        or skills_cfg.get("fallback_mode")
        or "off"
    )
    force_skill = (
        force_skill_override
        or os.getenv("TRADESWARM_FORCE_STRATEGY_SKILL")
        or skills_cfg.get("force_skill")
        or None
    )

    mode = str(mode).strip().lower()
    fallback_mode = str(fallback_mode).strip().lower()
    force_skill = str(force_skill).strip().lower() if force_skill is not None else None
    if force_skill in {"", "none", "null", "off"}:
        force_skill = None
    if mode not in {"reflect", "all", "off"}:
        raise ValueError("strategy_skills.mode must be one of: reflect, all, off")
    if fallback_mode not in {"all", "off"}:
        raise ValueError("strategy_skills.fallback_mode must be one of: all, off")
    if force_skill is not None and force_skill not in _VALID_STRATEGY_SKILLS:
        raise ValueError(
            "strategy_skills.force_skill must be one of: "
            + ", ".join(sorted(_VALID_STRATEGY_SKILLS))
        )

    return {"mode": mode, "fallback_mode": fallback_mode, "force_skill": force_skill}


def resolve_llm_config(
    *,
    config_path: Optional[str | Path] = None,
    profile: Optional[str] = None,
    model_override: Optional[str] = None,
    temperature_override: Optional[float] = None,
) -> Dict[str, Any]:
    """
    解析最终生效的 LLM 配置（SiliconFlow OpenAI-compatible）。

    支持 llm.silicon.profiles/default_profile，并允许 CLI/ENV 覆盖。

    优先级：
    1) model_override（CLI --llm-model）
    2) profile（CLI --llm-profile）
    3) 环境变量 SILICON_MODEL
    4) llm.silicon.default_profile
    5) 旧字段 llm.silicon.model_name
    6) 默认 Qwen/Qwen3-32B
    """
    cfg_file = Path(config_path).resolve() if config_path else _DEFAULT_CONFIG_PATH
    if not cfg_file.exists():
        raise FileNotFoundError(f"配置文件不存在: {cfg_file}")

    repo_dotenv = cfg_file.parent.parent / ".env"
    if repo_dotenv.is_file():
        load_dotenv(repo_dotenv, override=True)

    with open(cfg_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    llm_config = config.get("llm", {}) if isinstance(config, dict) else {}
    silicon_cfg = (llm_config.get("silicon", {}) or {}) if isinstance(llm_config, dict) else {}

    profiles = silicon_cfg.get("profiles") if isinstance(silicon_cfg, dict) else None
    profiles = profiles if isinstance(profiles, dict) else {}
    default_profile = (silicon_cfg.get("default_profile") if isinstance(silicon_cfg, dict) else None) or None

    requested_profile = (profile or "").strip() or None
    env_model = (os.getenv("SILICON_MODEL") or "").strip() or None

    model_name: str = ""
    temperature: Optional[float] = None
    used_profile: Optional[str] = None

    if model_override and str(model_override).strip():
        model_name = str(model_override).strip()
    else:
        if requested_profile:
            prof_cfg = profiles.get(requested_profile)
            prof_model = (prof_cfg.get("model_name") if isinstance(prof_cfg, dict) else None) or ""
            if not str(prof_model).strip():
                available = sorted([k for k, v in profiles.items() if isinstance(v, dict) and str(v.get("model_name") or "").strip()])
                raise ValueError(
                    f"未知或无效的 LLM profile: {requested_profile}. "
                    f"请在 config.yaml 的 llm.silicon.profiles 中配置该 profile。"
                    + (f" 可用 profiles: {available}" if available else " 当前未配置任何有效 profiles。")
                )

        prof_key = requested_profile or (str(default_profile).strip() if default_profile else None)
        prof_cfg = profiles.get(prof_key) if prof_key else None
        if isinstance(prof_cfg, dict) and str(prof_cfg.get("model_name") or "").strip():
            model_name = str(prof_cfg.get("model_name")).strip()
            used_profile = prof_key
            try:
                temperature = float(prof_cfg.get("temperature")) if prof_cfg.get("temperature") is not None else None
            except Exception:
                temperature = None
        elif env_model:
            model_name = env_model
        else:
            model_name = str(silicon_cfg.get("model_name") or "").strip() or "Qwen/Qwen3-32B"

    if temperature_override is not None:
        try:
            temperature = float(temperature_override)
        except Exception:
            temperature = None

    if temperature is None:
        temperature = silicon_cfg.get("temperature", llm_config.get("temperature", 0.1))
        try:
            temperature = float(temperature)
        except Exception:
            temperature = 0.1

    silicon_triple = env_silicon_keys_and_base(silicon_cfg.get("base_url"))
    if not silicon_triple:
        raise ValueError(
            "未找到 Silicon 凭证：请在 .env 中配置 Silicon_API_KEY"
            "（及可选 base_url_silicon）；"
            '支持单 key、逗号分隔或 JSON 列表如 ["sk-a","sk-b"]'
        )
    api_keys, base_url = silicon_triple

    return {
        "provider": "siliconflow",
        # Only record a profile when we actually resolved settings from it.
        "profile": used_profile,
        "model_name": model_name,
        "temperature": float(temperature),
        "base_url": base_url,
        "api_keys": api_keys,
    }


def get_llm(
    config_path: Optional[str | Path] = None,
    *,
    profile: Optional[str] = None,
    model_override: Optional[str] = None,
    temperature_override: Optional[float] = None,
):
    """Create a ``ChatOpenAI`` instance from the project config (Silicon Flow).

    Supports multi-key failover when multiple keys are supplied in
    ``Silicon_API_KEY``.

    Args:
        config_path: Override path to ``config.yaml``.

    Returns:
        A ``ChatOpenAI`` (or ``RunnableWithFallbacks``) instance.

    Raises:
        FileNotFoundError: Config file missing.
        ValueError: No valid Silicon credentials found.
    """
    from langchain_openai import ChatOpenAI
    import httpx

    cfg_file = Path(config_path).resolve() if config_path else _DEFAULT_CONFIG_PATH
    resolved = resolve_llm_config(
        config_path=cfg_file,
        profile=profile,
        model_override=model_override,
        temperature_override=temperature_override,
    )
    api_keys = resolved["api_keys"]
    base_url = resolved["base_url"]
    model_name = resolved["model_name"]
    temperature = resolved["temperature"]

    use_proxy = _llm_proxy_enabled()
    if use_proxy:
        _ensure_proxy_env()

    def _make_chat(key: str) -> ChatOpenAI:
        http_client = httpx.Client(
            verify=True,
            trust_env=use_proxy,
            timeout=httpx.Timeout(60.0),
        )
        return ChatOpenAI(
            api_key=key,
            base_url=base_url,
            model=model_name,
            temperature=temperature,
            http_client=http_client,
        )

    primary = _make_chat(api_keys[0])
    if len(api_keys) <= 1:
        return primary
    if not hasattr(primary, "with_fallbacks"):
        return primary

    fallbacks = [_make_chat(k) for k in api_keys[1:]]
    exc_types = silicon_llm_fallback_exception_types()
    try:
        llm = primary.with_fallbacks(fallbacks, exceptions_to_handle=exc_types)
    except TypeError:
        llm = primary.with_fallbacks(fallbacks)
    logger.info("[LLM] Silicon 检测到 %d 个 API key，已启用故障转移", len(api_keys))
    return llm


def get_llm_metadata(
    *,
    config_path: Optional[str | Path] = None,
    profile: Optional[str] = None,
    model_override: Optional[str] = None,
    temperature_override: Optional[float] = None,
) -> Dict[str, Any]:
    """返回最终生效的 LLM 配置（不创建网络连接），用于写入结果文件便于复现。"""
    resolved = resolve_llm_config(
        config_path=config_path,
        profile=profile,
        model_override=model_override,
        temperature_override=temperature_override,
    )
    return {
        "provider": resolved.get("provider"),
        "profile": resolved.get("profile"),
        "model_name": resolved.get("model_name"),
        "temperature": resolved.get("temperature"),
        "base_url": resolved.get("base_url"),
    }


def get_graph_debate_rounds(
    config_path: Optional[str | Path] = None,
) -> Tuple[int, int]:
    """Read debate round counts from config.

    Returns:
        ``(max_research_debate_rounds, max_risk_debate_rounds)``; both >= 1.
    """
    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
    default_r, default_rr = 2, 2
    if not path.is_file():
        return default_r, default_rr
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    g = cfg.get("graph") or {}
    try:
        mr = int(g.get("max_research_debate_rounds", default_r))
    except (TypeError, ValueError):
        mr = default_r
    try:
        mrr = int(g.get("max_risk_debate_rounds", default_rr))
    except (TypeError, ValueError):
        mrr = default_rr
    return max(1, min(mr, 20)), max(1, min(mrr, 20))


def get_memory_mode(config_path: Optional[str | Path] = None) -> str:
    """``hybrid`` | ``sql_only`` | ``chroma_only`` — 控制 pre-open 经验召回策略。"""
    path = Path(config_path).resolve() if config_path else _DEFAULT_CONFIG_PATH
    if not path.is_file():
        return "hybrid"
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    mode = str((cfg.get("memory") or {}).get("mode", "hybrid")).strip().lower()
    if mode in ("hybrid", "sql_only", "chroma_only"):
        return mode
    return "hybrid"


def create_chroma_memory_if_available(
    collection_name: Optional[str] = None,
    config_path: Optional[str | Path] = None,
):
    """Create a ``FinancialSituationMemory`` with optional on-disk persist dir from config.

    Reads ``storage.chroma_persist_directory`` and ``storage.chroma_collection`` when present.
    Returns *None* on failure so callers can gracefully degrade.
    """
    try:
        cfg_path = Path(config_path).resolve() if config_path else _DEFAULT_CONFIG_PATH
        cfg: Dict[str, Any] = {}
        if cfg_path.is_file():
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}

        storage = cfg.get("storage") or {}
        persist_raw = storage.get("chroma_persist_directory")
        persist_dir: Optional[str] = None
        if persist_raw:
            p = Path(str(persist_raw))
            persist_dir = str(p.resolve() if p.is_absolute() else _PROJECT_ROOT / p)

        coll = collection_name or storage.get("chroma_collection") or "tradeswarm_memory"

        from datasources.utils.memory.financial_situation_memory import FinancialSituationMemory

        mem_config: Dict[str, Any] = {}
        if persist_dir:
            mem_config["persist_directory"] = persist_dir

        # Embedding backend selection (default: silicon)
        emb_backend = str(storage.get("embedding_backend") or "silicon").strip().lower()
        mem_config["embedding_backend"] = emb_backend

        if emb_backend == "silicon":
            silicon_cfg = (cfg.get("llm") or {}).get("silicon") or {}
            silicon_pair = env_silicon_key_and_base(silicon_cfg.get("base_url"))
            if not silicon_pair:
                return None
            api_key, backend_url = silicon_pair
            mem_config["api_key"] = api_key
            mem_config["backend_url"] = backend_url
            mem_config["embedding_model"] = storage.get("embedding_model") or "text-embedding-v4"
        elif emb_backend == "bge_local":
            # Prefer local path under repo root
            mp_raw = storage.get("embedding_model_path") or storage.get("bge_model_path")
            mn_raw = storage.get("embedding_model_name") or storage.get("bge_model_name")
            if mp_raw:
                p = Path(str(mp_raw))
                mem_config["bge_model_path"] = str(p.resolve() if p.is_absolute() else _PROJECT_ROOT / p)
            if mn_raw:
                mem_config["bge_model_name"] = str(mn_raw)
        else:
            return None

        return FinancialSituationMemory(name=coll, config=mem_config)
    except Exception:
        logger.debug("ChromaDB memory 初始化失败，降级为无长期记忆", exc_info=True)
        return None
