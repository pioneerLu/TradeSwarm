#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""下载 yfinance 日线并写入 Lean 本地 custom data CSV。"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yfinance as yf


def main() -> None:
    p = argparse.ArgumentParser(description="下载 Yahoo Finance 日线到 Lean custom data")
    p.add_argument("--symbol", default="NVDA")
    p.add_argument("--start", default="2025-01-01")
    p.add_argument("--end", default="2025-03-01")
    p.add_argument(
        "--output",
        default="lean_workspace/data/custom/nvda_daily.csv",
        help="输出 CSV 路径",
    )
    args = p.parse_args()

    df = yf.download(
        tickers=args.symbol,
        start=args.start,
        end=args.end,
        interval="1d",
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if df is None or df.empty:
        # 备选源：Stooq（免费日线 CSV）
        stooq_symbol = f"{args.symbol.lower()}.us"
        stooq_url = f"https://stooq.com/q/d/l/?s={stooq_symbol}&i=d"
        raw = pd.read_csv(stooq_url)
        raw["Date"] = pd.to_datetime(raw["Date"])
        mask = (raw["Date"] >= pd.to_datetime(args.start)) & (raw["Date"] <= pd.to_datetime(args.end))
        df = raw.loc[mask].copy()
        if df.empty:
            raise SystemExit("下载失败：yfinance 与 stooq 均返回空数据")
        df = df.rename(
            columns={
                "Date": "Date",
                "Open": "Open",
                "High": "High",
                "Low": "Low",
                "Close": "Close",
                "Volume": "Volume",
            }
        ).set_index("Date")

    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df.index).strftime("%Y-%m-%d"),
            "open": df["Open"].astype(float).round(6),
            "high": df["High"].astype(float).round(6),
            "low": df["Low"].astype(float).round(6),
            "close": df["Close"].astype(float).round(6),
            "volume": df["Volume"].fillna(0).astype(float).round(0).astype(int),
        }
    )
    out = out.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)
    print(f"[OK] 写入 {out_path}，共 {len(out)} 行")


if __name__ == "__main__":
    main()
