# -*- coding: utf-8 -*-
"""
将 Polaris search 返回的 brief 映射为与 Alpha Vantage `get_news` DataFrame 行一致的字典：

    title, url, time_published, summary, source,
    overall_sentiment_score, overall_sentiment_label

方案 A：不改动 AV 侧；仅统一 Polaris fallback 行的字段集合，便于 analyst 按同一套键读取。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def iso_published_to_av_time_published(iso: str) -> str:
    """Polaris published_at / published (ISO-8601) -> AV 常见 time_published 形态 YYYYMMDDTHHMMSS（UTC）。"""
    if not iso:
        return ""
    s = str(iso).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%Y%m%dT%H%M%S")
    except ValueError:
        return ""


def _polaris_coarse_sentiment_score(label: Optional[str]) -> float:
    """仅有顶层 sentiment 标签时的粗粒度得分，区间约与 AV [-1, 1] 兼容。"""
    if not label:
        return 0.0
    x = str(label).lower().strip()
    if x == "positive":
        return 0.35
    if x == "negative":
        return -0.35
    return 0.0


def _entity_sentiment_scores_for_ticker(brief: Dict[str, Any], av_sym: str) -> List[float]:
    """优先使用与请求 ticker 匹配的 entities_enriched.sentiment_score（数值）。"""
    out: List[float] = []
    sym = av_sym.upper().split(".")[0]
    for e in brief.get("entities_enriched") or []:
        if not isinstance(e, dict):
            continue
        t = e.get("ticker")
        if t and str(t).upper().split(".")[0] == sym:
            ss = e.get("sentiment_score")
            if isinstance(ss, (int, float)):
                out.append(float(ss))
    return out


def _label_from_score(avg: float) -> str:
    if avg > 0.15:
        return "Bullish"
    if avg < -0.15:
        return "Bearish"
    return "Neutral"


def _polaris_sentiment_label_from_brief_sentiment(brief: Dict[str, Any]) -> str:
    """与 AV overall_sentiment_label 可读风格对齐（Bullish / Bearish / Neutral / Mixed）。"""
    lab = brief.get("sentiment")
    if lab is None or lab == "":
        return "Neutral"
    x = str(lab).lower().strip()
    if x == "positive":
        return "Bullish"
    if x == "negative":
        return "Bearish"
    if x == "mixed":
        return "Mixed"
    if x == "neutral":
        return "Neutral"
    return str(lab).strip().title() or "Neutral"


def polaris_brief_to_av_news_row(brief: Dict[str, Any], av_symbol: str) -> Dict[str, Any]:
    """
    单行 Polaris brief -> 与 `alphavantage_provider.AlphaVantageProvider.get_news` 中每条 dict 同键。

    Args:
        brief: Polaris API brief 对象
        av_symbol: 已去掉交易所后缀的代码，如 NVDA、AAPL
    """
    av_sym = (av_symbol or "").split(".")[0].strip().upper()

    sources = brief.get("sources") or []
    url = ""
    source_names: List[str] = []
    if isinstance(sources, list):
        for s in sources:
            if isinstance(s, dict):
                if not url and s.get("url"):
                    url = str(s.get("url"))
                n = s.get("name")
                if n:
                    source_names.append(str(n))

    published = brief.get("published_at") or brief.get("published") or ""
    tp = iso_published_to_av_time_published(str(published)) if published else ""
    if not tp and published:
        tp = str(published)[:32]

    summary = (brief.get("summary") or "").strip()
    contra = (brief.get("counter_argument") or "").strip()
    summary_for_av = summary
    if contra:
        summary_for_av = f"{summary}\n\n[Counter-argument] {contra[:900]}"

    ent_scores = _entity_sentiment_scores_for_ticker(brief, av_sym)
    if ent_scores:
        avg = sum(ent_scores) / len(ent_scores)
        avg = max(-1.0, min(1.0, float(avg)))
        overall_sentiment_score = float(avg)
        overall_sentiment_label = _label_from_score(avg)
    else:
        overall_sentiment_score = _polaris_coarse_sentiment_score(brief.get("sentiment"))
        overall_sentiment_label = _polaris_sentiment_label_from_brief_sentiment(brief)

    if source_names:
        source = ", ".join(source_names[:3])
    else:
        source = "Polaris Report"

    return {
        "title": brief.get("headline") or "",
        "url": url,
        "time_published": tp,
        "summary": summary_for_av[:4000],
        "source": source,
        "overall_sentiment_score": overall_sentiment_score,
        "overall_sentiment_label": overall_sentiment_label,
    }
