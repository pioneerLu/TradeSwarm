"""
Graph 工具函数

包含 LLM 初始化等工具函数。
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple
import yaml
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os

from tradingagents.llm_env_compat import (
    env_silicon_key_and_base,
    env_silicon_keys_and_base,
    silicon_llm_fallback_exception_types,
)

load_dotenv()


def _llm_proxy_enabled() -> bool:
    host = (os.getenv("PROXY_HOST") or "").strip()
    port = (os.getenv("PROXY_PORT") or "").strip()
    use_flag = (os.getenv("USE_PROXY") or "").strip().lower() == "true"
    return bool((host and port) or use_flag or os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY"))


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


def load_llm_from_config(config_path: str = "config/config.yaml") -> ChatOpenAI:
    """
    从 config.yaml 读取 LLM 配置并初始化 ChatOpenAI 实例（仅 Silicon Flow）。

    注意：LLM 请求不走代理，因此会临时禁用环境变量中的代理设置。

    Args:
        config_path: 配置文件路径，默认为 "config/config.yaml"

    Returns:
        初始化好的 ChatOpenAI 实例
    """
    config_file = Path(config_path).resolve()
    if not config_file.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    # 始终从「该 config 所在仓库根」加载 .env，避免仅 cwd 加载导致 Silicon_API_KEY 缺失或误用他处 .env → 401
    repo_dotenv = config_file.parent.parent / ".env"
    if repo_dotenv.is_file():
        load_dotenv(repo_dotenv, override=True)

    with open(config_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    llm_config = config.get("llm", {})
    silicon_cfg = llm_config.get("silicon", {}) or {}
    silicon_triple = env_silicon_keys_and_base(silicon_cfg.get("base_url"))

    if not silicon_triple:
        raise ValueError(
            "未找到 Silicon 凭证：请在 .env 中配置 Silicon_API_KEY（及可选 base_url_silicon）；"
            "支持单 key、逗号分隔或 JSON 列表如 [\"sk-a\",\"sk-b\"]"
        )

    api_keys, base_url = silicon_triple
    model_name = (
        os.getenv("SILICON_MODEL")
        or silicon_cfg.get("model_name")
        or "Qwen/Qwen3-32B"
    )
    temperature = silicon_cfg.get("temperature", llm_config.get("temperature", 0.1))

    import httpx
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
    print(f"[LLM] Silicon 检测到 {len(api_keys)} 个 API key，已启用故障转移（run_signal_export / Graph）")
    return llm


def load_graph_debate_rounds(
    config_path: str | Path | None = None,
) -> Tuple[int, int]:
    """
    从 config.yaml 读取研究侧 / 风险侧辩论轮数。

    Returns:
        (max_research_debate_rounds, max_risk_debate_rounds)，均 >= 1。
    """
    path = (
        Path(config_path)
        if config_path is not None
        else Path(__file__).resolve().parents[2] / "config" / "config.yaml"
    )
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
    mr = max(1, min(mr, 20))
    mrr = max(1, min(mrr, 20))
    return mr, mrr


def create_chroma_memory_if_available(collection_name: str = "tradeswarm_reflections"):
    """
    若已配置 Silicon，创建 FinancialSituationMemory 供 Reflector 写入 ChromaDB。
    失败时返回 None，Reflector 仅写入 cycle_reflections 表，不影响主流程。
    """
    try:
        config_path = Path(__file__).resolve().parents[2] / "config" / "config.yaml"
        silicon_cfg = {}
        if config_path.is_file():
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            silicon_cfg = (cfg.get("llm") or {}).get("silicon") or {}
        silicon_pair = env_silicon_key_and_base(silicon_cfg.get("base_url"))
        if not silicon_pair:
            return None
        api_key, backend_url = silicon_pair
        from datasources.utils.memory.financial_situation_memory import FinancialSituationMemory

        config = {
            "api_key": api_key,
            "backend_url": backend_url,
        }
        return FinancialSituationMemory(name=collection_name, config=config)
    except Exception:
        return None
