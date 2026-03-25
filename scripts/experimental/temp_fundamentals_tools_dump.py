#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单独检查 fundamentals 使用的 Alpha Vantage 链（不经过 LangChain tools）：
与 build_analyst_dataset 中 fundamentals 工具同源，按 Provider 逐步请求并写入文件。

仓库根:
    python scripts/experimental/temp_fundamentals_tools_dump.py --symbol NVDA
    python scripts/experimental/temp_fundamentals_tools_dump.py --symbol NVDA --out tmp/fundamentals_av_nvda.txt

说明：基本面数据不随 trade_date 变化；工具层与「几天」无关，只需验证标的 NVDA 的 AV 是否正常。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

_API_FAILURE_KEYWORDS = [
    "未能获取",
    "API 失效",
    "API服务全面限频",
    "API访问中断",
    "API访问限制",
    "API密钥耗尽",
    "密钥耗尽",
    "Rate limited",
    "数据获取失败",
    "数据获取暂时不可用",
    "暂时不可用",
    "无法获取",
]


def _ensure_data_proxy() -> None:
    from tradingagents.core.data.loader import setup_proxy

    host = (os.getenv("PROXY_HOST") or "").strip()
    port = (os.getenv("PROXY_PORT") or "").strip()
    if host and port:
        os.environ["USE_PROXY"] = "true"
        setup_proxy()
        print("[PROXY] PROXY_HOST/PORT", flush=True)
    elif os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY"):
        os.environ["USE_PROXY"] = "true"
        print("[PROXY] HTTP(S)_PROXY", flush=True)


def _hits(text: str) -> List[str]:
    if not text:
        return []
    return [kw for kw in _API_FAILURE_KEYWORDS if kw in text]


def _jsonify(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


def _df_snap(df, max_rows: int = 2) -> Dict[str, Any]:
    if df is None:
        return {"empty": True, "reason": "None"}
    try:
        if getattr(df, "empty", True):
            return {"empty": True, "rows": 0}
        return {
            "rows": len(df),
            "columns": list(df.columns),
            "head": df.head(max_rows).to_dict("records"),
        }
    except Exception as exc:
        return {"error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="NVDA")
    parser.add_argument("--sleep", type=float, default=15.0)
    parser.add_argument("--out", default="tmp/fundamentals_tools_nvda_check.txt")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    try:
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass

    _ensure_data_proxy()

    from utils.config_loader import load_config
    from datasources.data_sources.alphavantage_provider import AlphaVantageProvider

    cfg = load_config()
    try:
        av = AlphaVantageProvider(cfg)
    except ValueError as exc:
        print(f"[ERROR] Alpha Vantage 未配置: {exc}", flush=True)
        return 2

    sym = args.symbol.strip()
    blocks: List[str] = []

    def step(name: str, fn) -> None:
        print(f"[RUN] {name} ...", flush=True)
        try:
            payload = fn()
            out = {"step": name, "ok": True, "data": payload}
        except Exception as exc:
            out = {"step": name, "ok": False, "error": str(exc)}
        text = _jsonify(out)
        blocks.append(f"\n{'='*20} {name} {'='*20}\n")
        blocks.append(f"[KEYWORD HIT vs build SKIP] {_hits(text) or '(none)'}\n")
        blocks.append(text + "\n")

    step("get_company_info", lambda: av.get_company_info(sym))

    def _stmt() -> Dict[str, Any]:
        r = av.get_financial_statements(sym, statement_type="all")
        return {k: _df_snap(r.get(k)) for k in ("income", "balance", "cashflow") if k in r} or {
            "note": "no keys"
        }

    if args.sleep > 0:
        time.sleep(args.sleep)
    step("get_financial_statements", _stmt)

    if args.sleep > 0:
        time.sleep(args.sleep)
    step("get_financial_indicators", lambda: _df_snap(av.get_financial_indicators(sym)))

    if args.sleep > 0:
        time.sleep(args.sleep)
    step("get_valuation_metrics", lambda: _df_snap(av.get_valuation_metrics(sym)))

    if args.sleep > 0:
        time.sleep(args.sleep)

    def _earn() -> Dict[str, Any]:
        d = av.get_earnings_data(sym, limit=10)
        return {
            "annual_count": len(d.get("annualEarnings") or []),
            "quarterly_count": len(d.get("quarterlyEarnings") or []),
            "annual_head": (d.get("annualEarnings") or [])[:2],
            "quarterly_head": (d.get("quarterlyEarnings") or [])[:2],
        }

    step("get_earnings_data", _earn)

    combined = "".join(blocks)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(combined, encoding="utf-8")
    print(f"[OK] 已写入 {out_path.resolve()}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
