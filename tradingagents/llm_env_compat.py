# -*- coding: utf-8 -*-
"""Silicon Flow：从环境变量解析 API Key 与 base_url（无 LangChain 依赖）。"""

from __future__ import annotations

import os
from typing import List


def _strip_base_url(url: str) -> str:
    return (url or "").strip().strip("\"'").rstrip("/")


def parse_silicon_api_keys(raw: str) -> List[str]:
    """
    解析 Silicon_API_KEY，与 build_analyst_dataset._parse_api_keys 行为一致：
    - 单 key：sk-xxx
    - 逗号分隔：sk-a,sk-b
    - JSON / Python 列表字符串：["sk-a","sk-b"]（.env 里常见）
    """
    import ast
    import json

    text = (raw or "").strip()
    if not text:
        return []

    if text.startswith("[") and text.endswith("]"):
        parsed = None
        try:
            parsed = json.loads(text)
        except Exception:
            try:
                parsed = ast.literal_eval(text)
            except Exception:
                parsed = None
        if isinstance(parsed, (list, tuple)):
            keys = [str(x).strip().strip("\"'") for x in parsed if str(x).strip()]
            return [k for k in keys if k]

    if "," in text:
        keys = [p.strip().strip("\"'") for p in text.split(",") if p.strip()]
        return [k for k in keys if k]

    return [text.strip().strip("\"'")]


def _resolve_silicon_base_url(fallback_base_url: str | None = None) -> str:
    raw = (
        os.getenv("base_url_silicon")
        or os.getenv("BASE_URL_SILICON")
        or (fallback_base_url or "")
        or "https://api.siliconflow.cn/v1"
    )
    raw = str(raw).strip().strip("\"'")
    return _strip_base_url(raw)


def env_silicon_keys_and_base(
    fallback_base_url: str | None = None,
) -> tuple[list[str], str] | None:
    """
    返回解析后的全部 Silicon key 与 base_url；无有效 key 时 None。
    """
    silicon_api = os.getenv("Silicon_API_KEY") or os.getenv("SILICON_API_KEY")
    if not silicon_api:
        return None
    keys = parse_silicon_api_keys(silicon_api)
    if not keys:
        return None
    return keys, _resolve_silicon_base_url(fallback_base_url)


def env_silicon_key_and_base(fallback_base_url: str | None = None) -> tuple[str, str] | None:
    """
    .env 中 Silicon_API_KEY / SILICON_API_KEY + base_url_silicon。
    fallback_base_url：来自 config.yaml 的 silicon.base_url（环境变量未设时）。
    多 key 时仅返回第一个（兼容旧调用方）；图加载请用 env_silicon_keys_and_base + 故障转移。
    """
    triple = env_silicon_keys_and_base(fallback_base_url)
    if not triple:
        return None
    keys, base = triple
    return keys[0], base


def silicon_llm_fallback_exception_types() -> tuple[type, ...]:
    """与 build_analyst_dataset 一致：限流/超时/连接/5xx/认证错误时切换下一个 key。"""
    try:
        import openai

        exc_list: list[type] = [
            openai.RateLimitError,
            openai.APITimeoutError,
            openai.APIConnectionError,
        ]
        internal = getattr(openai, "InternalServerError", None)
        auth = getattr(openai, "AuthenticationError", None)
        permission = getattr(openai, "PermissionDeniedError", None)
        if internal is not None:
            exc_list.append(internal)
        if auth is not None:
            exc_list.append(auth)
        if permission is not None:
            exc_list.append(permission)
        return tuple(exc_list)
    except Exception:
        return (Exception,)
