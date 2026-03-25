# -*- coding: utf-8 -*-
"""
The Polaris Report HTTP 客户端。

- 使用 httpx 且默认 trust_env=True，以便走系统/环境变量中的 HTTP(S)_PROXY（与 yfinance 数据拉取一致）。
- 密钥：POLARIS_TOKEN 或 POLARIS_API_KEY；可选 POLARIS_BASE_URL。

文档: https://thepolarisreport.com/docs
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx

DEFAULT_BASE_URL = "https://api.thepolarisreport.com"


def get_polaris_token() -> Optional[str]:
    raw = (os.getenv("POLARIS_TOKEN") or os.getenv("POLARIS_API_KEY") or "").strip().strip("\"'")
    if raw:
        return raw
    try:
        from utils.config_loader import load_config

        cfg = (load_config().get("data_sources") or {}).get("polaris_token")
        if cfg and isinstance(cfg, str):
            s = cfg.strip().strip("\"'")
            if s and not s.startswith("${"):
                return s
    except Exception:
        pass
    return None


def get_polaris_base_url() -> str:
    return (os.getenv("POLARIS_BASE_URL") or DEFAULT_BASE_URL).strip().rstrip("/")


def _client(timeout: float = 45.0) -> httpx.Client:
    """Polaris 调用需代理时：依赖 HTTP_PROXY/HTTPS_PROXY（trust_env=True）。"""
    trust = os.getenv("POLARIS_TRUST_ENV", "true").lower() not in ("0", "false", "no")
    return httpx.Client(timeout=timeout, trust_env=trust)


def polaris_search(
    query: str,
    *,
    limit: int = 10,
    min_confidence: Optional[float] = 0.35,
    timeout: float = 45.0,
) -> Dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {"success": False, "error": "query 为空", "briefs": []}

    token = get_polaris_token()
    if not token:
        return {"success": False, "error": "未配置 POLARIS_TOKEN / POLARIS_API_KEY", "briefs": []}

    params: Dict[str, Any] = {"q": q, "limit": max(1, min(int(limit), 50))}
    if min_confidence is not None:
        params["min_confidence"] = float(min_confidence)

    url = f"{get_polaris_base_url()}/api/v1/search"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    try:
        with _client(timeout) as client:
            r = client.get(url, params=params, headers=headers)
        if r.status_code >= 400:
            return {
                "success": False,
                "error": f"HTTP {r.status_code}",
                "detail": (r.text or "")[:800],
                "briefs": [],
            }
        body = r.json()
    except Exception as exc:
        return {"success": False, "error": str(exc), "briefs": []}

    briefs = body.get("briefs")
    if briefs is None:
        briefs = body.get("data") or []
    if not isinstance(briefs, list):
        briefs = []
    ok = body.get("status") == "ok" or bool(briefs)
    return {"success": ok, "briefs": briefs, "raw": body}


def polaris_agent_feed(
    *,
    limit: int = 10,
    category: Optional[str] = "markets",
    min_confidence: Optional[float] = 0.4,
    timeout: float = 45.0,
) -> Dict[str, Any]:
    token = get_polaris_token()
    if not token:
        return {"success": False, "error": "未配置 POLARIS_TOKEN / POLARIS_API_KEY", "briefs": []}

    params: Dict[str, Any] = {"limit": max(1, min(int(limit), 50))}
    if category:
        params["category"] = category.strip()
    if min_confidence is not None:
        params["min_confidence"] = float(min_confidence)

    url = f"{get_polaris_base_url()}/api/v1/agent-feed"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    try:
        with _client(timeout) as client:
            r = client.get(url, params=params, headers=headers)
        if r.status_code >= 400:
            return {
                "success": False,
                "error": f"HTTP {r.status_code}",
                "detail": (r.text or "")[:800],
                "briefs": [],
            }
        body = r.json()
    except Exception as exc:
        return {"success": False, "error": str(exc), "briefs": []}

    briefs = body.get("briefs")
    if briefs is None:
        briefs = body.get("data") or []
    if not isinstance(briefs, list):
        briefs = []
    return {"success": True, "briefs": briefs, "raw": body}
