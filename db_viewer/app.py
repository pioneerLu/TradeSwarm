# -*- coding: utf-8 -*-
"""memory.db 本地 Web 查看器"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
import json
from pathlib import Path
from flask import Flask, render_template_string, jsonify, request

APP_DIR = Path(__file__).parent
PROJECT_ROOT = APP_DIR.parent


def resolve_db_path(cli_db: str | None = None) -> Path:
  # Priority: CLI > env > storage/db/memory.db > legacy memory.db
  if cli_db:
    return Path(cli_db).expanduser().resolve()

  env_db = os.getenv("DB_VIEWER_DB")
  if env_db:
    return Path(env_db).expanduser().resolve()

  storage_db = PROJECT_ROOT / "storage" / "db" / "memory.db"
  if storage_db.exists():
    return storage_db

  return PROJECT_ROOT / "memory.db"


DB_PATH = resolve_db_path()

# 允许按 id 删除行的表（本地工具，仍做白名单）
ALLOWED_DELETE_BY_ID_TABLES = frozenset({"analyst_reports", "analyst_summaries"})

app = Flask(__name__)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = lambda c, r: dict(zip([x[0] for x in c.description], r))
    return conn


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/overview")
def api_overview():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    tables = [r["name"] for r in cur.fetchall()]
    result = []
    for t in tables:
        cur.execute(f"SELECT COUNT(*) as cnt FROM {t}")
        cnt = cur.fetchone()["cnt"]
        cur.execute(f"PRAGMA table_info({t})")
        cols = [r["name"] for r in cur.fetchall()]
        info = {"name": t, "rows": cnt, "columns": cols}
        if t == "analyst_reports" and cnt > 0:
            cur.execute("SELECT symbol, COUNT(*) as n FROM analyst_reports GROUP BY symbol")
            info["by_symbol"] = [{"symbol": r["symbol"], "count": r["n"]} for r in cur.fetchall()]
        if t == "analyst_summaries" and cnt > 0:
            cur.execute("SELECT symbol, COUNT(*) as n FROM analyst_summaries GROUP BY symbol")
            info["by_symbol"] = [{"symbol": r["symbol"], "count": r["n"]} for r in cur.fetchall()]
        if t == "daily_trading_summaries" and cnt > 0:
            cur.execute("SELECT symbol, COUNT(*) as n FROM daily_trading_summaries GROUP BY symbol")
            info["by_symbol"] = [{"symbol": r["symbol"], "count": r["n"]} for r in cur.fetchall()]
        if t == "cycle_reflections" and cnt > 0:
            cur.execute("SELECT COALESCE(symbol,'(null)') as symbol, COUNT(*) as n FROM cycle_reflections GROUP BY symbol")
            info["by_symbol"] = [{"symbol": r["symbol"], "count": r["n"]} for r in cur.fetchall()]
        result.append(info)
    conn.close()
    return jsonify({"tables": result, "db": str(DB_PATH)})


@app.route("/api/dates")
def api_dates():
    symbol = request.args.get("symbol", "NVDA")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT trade_date FROM analyst_reports WHERE symbol=? ORDER BY trade_date DESC",
        (symbol,),
    )
    dates = [r["trade_date"] for r in cur.fetchall()]
    conn.close()
    return jsonify({"symbol": symbol, "dates": dates})


@app.route("/api/summary_dates")
def api_summary_dates():
    """analyst_summaries 可选日期列表（与 analyst_reports 的 /api/dates 对称）"""
    symbol = request.args.get("symbol", "NVDA")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT trade_date FROM analyst_summaries WHERE symbol=? ORDER BY trade_date DESC",
        (symbol,),
    )
    dates = [r["trade_date"] for r in cur.fetchall()]
    conn.close()
    return jsonify({"symbol": symbol, "dates": dates})


@app.route("/api/trading_summary_dates")
def api_trading_summary_dates():
    """daily_trading_summaries 可选日期列表"""
    symbol = request.args.get("symbol", "NVDA")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT date FROM daily_trading_summaries WHERE symbol=? ORDER BY date DESC",
        (symbol,),
    )
    dates = [r["date"] for r in cur.fetchall()]
    conn.close()
    return jsonify({"symbol": symbol, "dates": dates})


@app.route("/api/trading_summary")
def api_trading_summary():
    """单条 daily_trading_summaries（同时返回解析后的 summary_json）"""
    symbol = request.args.get("symbol", "NVDA")
    date = request.args.get("date")
    if not date:
        return jsonify({"error": "缺少 date"}), 400
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, date, symbol, market_regime, selected_strategy, expected_behavior,
                  actual_return, actual_max_drawdown, positioning, anomaly, summary_json,
                  created_at, updated_at
           FROM daily_trading_summaries
           WHERE symbol=? AND date=?
           ORDER BY id DESC LIMIT 1""",
        (symbol, date),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "未找到 trading summary"}), 404

    parsed = None
    sj = row.get("summary_json") if isinstance(row, dict) else None
    if isinstance(sj, str) and sj.strip():
        try:
            parsed = json.loads(sj)
        except Exception:
            parsed = None
    return jsonify({**row, "summary_json_parsed": parsed})


@app.route("/api/cycle_reflections")
def api_cycle_reflections():
    """cycle_reflections 列表（可按 symbol/cycle_type 过滤，返回最新若干条）"""
    symbol = request.args.get("symbol", "")
    cycle_type = request.args.get("cycle_type", "")
    limit = min(int(request.args.get("limit", 50)), 200)
    where = []
    params = []
    if symbol:
        where.append("symbol=?")
        params.append(symbol)
    if cycle_type:
        where.append("cycle_type=?")
        params.append(cycle_type)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"""SELECT id, cycle_type, cycle_start_date, cycle_end_date, symbol,
                   key_insights, created_at, updated_at, reflection_content
            FROM cycle_reflections
            {where_sql}
            ORDER BY cycle_end_date DESC, id DESC
            LIMIT ?""",
        tuple(params + [limit]),
    )
    rows = cur.fetchall()
    conn.close()
    # 列表页里 reflection_content 只保留短预览
    for r in rows:
        rc = r.get("reflection_content")
        if isinstance(rc, str) and len(rc) > 500:
            r["reflection_content_preview"] = rc[:500] + "..."
        else:
            r["reflection_content_preview"] = rc or ""
        r.pop("reflection_content", None)
    return jsonify({"rows": rows, "limit": limit})


@app.route("/api/cycle_reflection")
def api_cycle_reflection():
    """读取单条 cycle_reflections（返回解析后的 reflection_content）"""
    rid = request.args.get("id")
    if rid is None:
        return jsonify({"error": "缺少 id"}), 400
    try:
        rid_int = int(rid)
    except Exception:
        return jsonify({"error": "id 须为整数"}), 400
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, cycle_type, cycle_start_date, cycle_end_date, symbol,
                  key_insights, error_patterns, success_patterns, strategy_conditions,
                  environment_biases, created_at, updated_at, reflection_content
           FROM cycle_reflections WHERE id=? LIMIT 1""",
        (rid_int,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "未找到 cycle reflection"}), 404
    parsed = None
    rc = row.get("reflection_content")
    if isinstance(rc, str) and rc.strip():
        try:
            parsed = json.loads(rc)
        except Exception:
            parsed = None
    return jsonify({**row, "reflection_content_parsed": parsed})


@app.route("/api/report")
def api_report():
    symbol = request.args.get("symbol", "NVDA")
    date = request.args.get("date")
    atype = request.args.get("type", "market")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, report_content, created_at FROM analyst_reports
           WHERE symbol=? AND trade_date=? AND analyst_type=?
           ORDER BY id DESC LIMIT 1""",
        (symbol, date, atype),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "未找到报告"}), 404
    return jsonify(
        {
            "id": row["id"],
            "content": row["report_content"],
            "created_at": row["created_at"],
        }
    )


@app.route("/api/summary")
def api_summary():
    """单条 analyst_summaries：与 /api/report 相同的 JSON 形状，额外返回窗口元数据"""
    symbol = request.args.get("symbol", "NVDA")
    date = request.args.get("date")
    atype = request.args.get("type", "market")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, summary_content, created_at, window_start_date, window_end_date,
                  source_reports_count, llm_model, token_usage, updated_at
           FROM analyst_summaries
           WHERE symbol=? AND trade_date=? AND analyst_type=?
           ORDER BY id DESC LIMIT 1""",
        (symbol, date, atype),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "未找到 summary"}), 404
    return jsonify(
        {
            "id": row["id"],
            "content": row["summary_content"],
            "created_at": row["created_at"],
            "window_start_date": row["window_start_date"],
            "window_end_date": row["window_end_date"],
            "source_reports_count": row["source_reports_count"],
            "llm_model": row["llm_model"],
            "token_usage": row["token_usage"],
            "updated_at": row["updated_at"],
        }
    )


@app.route("/api/delete_report", methods=["POST"])
def api_delete_report():
    """按 symbol + trade_date + analyst_type 删除 analyst_reports（可删多条重复）"""
    data = request.get_json() or {}
    symbol = (data.get("symbol") or "NVDA").strip().upper()
    date = data.get("date")
    atype = (data.get("type") or "market").strip().lower()
    if not date:
        return jsonify({"error": "缺少 date"}), 400
    valid_types = {"market", "news", "fundamentals", "sentiment"}
    if atype not in valid_types:
        return jsonify({"error": f"type 须为 {valid_types}"}), 400
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM analyst_reports WHERE symbol=? AND trade_date=? AND analyst_type=?",
        (symbol, date, atype),
    )
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "deleted": deleted})


@app.route("/api/delete_summary", methods=["POST"])
def api_delete_summary():
    """按 symbol + trade_date + analyst_type 删除 analyst_summaries"""
    data = request.get_json() or {}
    symbol = (data.get("symbol") or "NVDA").strip().upper()
    date = data.get("date")
    atype = (data.get("type") or "market").strip().lower()
    if not date:
        return jsonify({"error": "缺少 date"}), 400
    valid_types = {"market", "news", "fundamentals", "sentiment"}
    if atype not in valid_types:
        return jsonify({"error": f"type 须为 {valid_types}"}), 400
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM analyst_summaries WHERE symbol=? AND trade_date=? AND analyst_type=?",
        (symbol, date, atype),
    )
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "deleted": deleted})


@app.route("/api/delete_row", methods=["POST"])
def api_delete_row():
    """按主键 id 删除白名单表中的单行"""
    data = request.get_json() or {}
    table = data.get("table")
    row_id = data.get("id")
    if not table or row_id is None:
        return jsonify({"error": "缺少 table 或 id"}), 400
    if not isinstance(table, str) or not re.match(r"^[a-zA-Z0-9_]+$", table):
        return jsonify({"error": "非法表名"}), 400
    if table not in ALLOWED_DELETE_BY_ID_TABLES:
        return jsonify({"error": f"仅允许删除表: {sorted(ALLOWED_DELETE_BY_ID_TABLES)}"}), 400
    try:
        row_id = int(row_id)
    except (TypeError, ValueError):
        return jsonify({"error": "id 须为整数"}), 400
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"DELETE FROM {table} WHERE id=?", (row_id,))
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    if deleted == 0:
        return jsonify({"ok": False, "deleted": 0, "error": "未找到该行"}), 404
    return jsonify({"ok": True, "deleted": deleted})


@app.route("/api/table/<name>")
def api_table(name):
    limit = min(int(request.args.get("limit", 50)), 200)
    offset = int(request.args.get("offset", 0))
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) as cnt FROM {name}")
    total = cur.fetchone()["cnt"]
    cur.execute(f"SELECT * FROM {name} LIMIT ? OFFSET ?", (limit, offset))
    rows = cur.fetchall()
    cur.execute(f"PRAGMA table_info({name})")
    columns = [r["name"] for r in cur.fetchall()]
    conn.close()
    # 长文本截断便于列表展示
    for r in rows:
        for k, v in list(r.items()):
            if isinstance(v, str) and len(v) > 500:
                r[k] = v[:500] + "..."
    return jsonify({"rows": rows, "total": total, "columns": columns, "limit": limit, "offset": offset})


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>memory.db 查看器</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      margin: 0;
      background: #0f1419;
      color: #e6edf3;
      min-height: 100vh;
    }
    .header {
      background: #161b22;
      padding: 1rem 1.5rem;
      border-bottom: 1px solid #30363d;
      display: flex;
      align-items: center;
      gap: 1rem;
    }
    .header h1 { margin: 0; font-size: 1.25rem; }
    .header .path { color: #8b949e; font-size: 0.875rem; }
    .container { max-width: 1200px; margin: 0 auto; padding: 1.5rem; }
    .tabs { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
    .tab {
      padding: 0.5rem 1rem;
      background: #21262d;
      border: 1px solid #30363d;
      border-radius: 6px;
      cursor: pointer;
      font-size: 0.9rem;
    }
    .tab:hover { background: #30363d; }
    .tab.active { background: #238636; border-color: #238636; }
    .panel { display: none; }
    .panel.active { display: block; }
    .card {
      background: #161b22;
      border: 1px solid #30363d;
      border-radius: 8px;
      padding: 1rem;
      margin-bottom: 1rem;
    }
    .card h3 { margin: 0 0 0.75rem; font-size: 1rem; }
    .table-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 0.75rem; }
    .table-item {
      background: #21262d;
      padding: 0.75rem 1rem;
      border-radius: 6px;
      cursor: pointer;
    }
    .table-item:hover { background: #30363d; }
    .table-item .name { font-weight: 600; }
    .table-item .rows { color: #8b949e; font-size: 0.8rem; }
    .report-selector { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1rem; align-items: center; }
    .report-selector select, .report-selector input {
      padding: 0.5rem 0.75rem;
      background: #21262d;
      border: 1px solid #30363d;
      border-radius: 6px;
      color: #e6edf3;
      font-size: 0.9rem;
    }
    .report-content {
      background: #0d1117;
      border: 1px solid #30363d;
      border-radius: 8px;
      padding: 1.25rem;
      white-space: pre-wrap;
      font-family: "Cascadia Code", "Consolas", monospace;
      font-size: 0.875rem;
      line-height: 1.6;
      max-height: 70vh;
      overflow-y: auto;
    }
    .report-content markdown-like h1, .report-content h2 { font-size: 1rem; margin: 1rem 0 0.5rem; }
    .data-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.85rem;
    }
    .data-table th, .data-table td {
      padding: 0.5rem 0.75rem;
      text-align: left;
      border-bottom: 1px solid #30363d;
    }
    .data-table th { color: #8b949e; font-weight: 500; }
    .loading { color: #8b949e; }
    .btn-row { display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; margin-top: 0.75rem; }
    .btn {
      padding: 0.45rem 0.9rem;
      border-radius: 6px;
      border: 1px solid #30363d;
      background: #21262d;
      color: #e6edf3;
      cursor: pointer;
      font-size: 0.85rem;
    }
    .btn:hover { background: #30363d; }
    .btn-danger { background: #6e1515; border-color: #a40f0f; }
    .btn-danger:hover { background: #8b1a1a; }
    .btn-mini { padding: 0.2rem 0.45rem; font-size: 0.75rem; }
    .meta { color: #8b949e; font-size: 0.8rem; margin-top: 0.5rem; }
    .kv { display: grid; grid-template-columns: 180px 1fr; gap: 0.35rem 0.75rem; font-size: 0.85rem; }
    .kv .k { color: #8b949e; }
    .split { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
    @media (max-width: 1000px) { .split { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <div class="header">
    <h1>memory.db 查看器</h1>
    <span class="path" id="dbPath">-</span>
  </div>
  <div class="container">
    <div class="tabs">
      <span class="tab active" data-panel="overview">概览</span>
      <span class="tab" data-panel="reports">Analyst 报告</span>
      <span class="tab" data-panel="summaries">Summary（7日）</span>
      <span class="tab" data-panel="trading">Trading Summary（日）</span>
      <span class="tab" data-panel="reflections">Reflector（周期反思）</span>
      <span class="tab" data-panel="tables">数据表</span>
    </div>

    <div id="panel-overview" class="panel active">
      <div class="card">
        <h3>数据表</h3>
        <div class="table-list" id="overviewTables"></div>
      </div>
    </div>

    <div id="panel-reports" class="panel">
      <div class="card">
        <h3>选择报告</h3>
        <div class="report-selector">
          <select id="selSymbol"><option value="NVDA">NVDA</option><option value="AAPL">AAPL</option></select>
          <select id="selDate"><option value="">选择日期</option></select>
          <select id="selType">
            <option value="market">Market</option>
            <option value="news">News</option>
            <option value="fundamentals">Fundamentals</option>
            <option value="sentiment">Sentiment</option>
          </select>
        </div>
        <div class="btn-row">
          <button type="button" class="btn btn-danger" id="btnDeleteReport">删除当前报告</button>
          <span class="meta" id="reportMeta"></span>
        </div>
        <div id="reportContent" class="report-content">选择日期和类型查看报告内容</div>
      </div>
    </div>

    <div id="panel-summaries" class="panel">
      <div class="card">
        <h3>选择 7 日滚动 Summary（analyst_summaries）</h3>
        <div class="report-selector">
          <select id="selSummarySymbol"><option value="NVDA">NVDA</option><option value="AAPL">AAPL</option></select>
          <select id="selSummaryDate"><option value="">选择日期</option></select>
          <select id="selSummaryType">
            <option value="market">Market</option>
            <option value="news">News</option>
            <option value="fundamentals">Fundamentals</option>
            <option value="sentiment">Sentiment</option>
          </select>
        </div>
        <div class="btn-row">
          <button type="button" class="btn btn-danger" id="btnDeleteSummary">删除当前 Summary</button>
          <span class="meta" id="summaryMeta"></span>
        </div>
        <div id="summaryContent" class="report-content">选择日期和类型查看 summary 内容</div>
      </div>
    </div>

    <div id="panel-trading" class="panel">
      <div class="card">
        <h3>选择 Daily Trading Summary（daily_trading_summaries）</h3>
        <div class="report-selector">
          <select id="selTradingSymbol"><option value="NVDA">NVDA</option><option value="AAPL">AAPL</option></select>
          <select id="selTradingDate"><option value="">选择日期</option></select>
        </div>
        <div class="btn-row">
          <span class="meta" id="tradingMeta"></span>
        </div>
        <div class="split">
          <div>
            <div class="card" style="margin-bottom:0">
              <h3 style="margin-bottom:0.75rem">字段概览</h3>
              <div id="tradingKv" class="kv"></div>
            </div>
          </div>
          <div>
            <div class="card" style="margin-bottom:0">
              <h3 style="margin-bottom:0.75rem">summary_json（解析后）</h3>
              <div id="tradingJson" class="report-content">(选择日期后显示)</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div id="panel-reflections" class="panel">
      <div class="card">
        <h3>周期反思（cycle_reflections）</h3>
        <div class="report-selector">
          <select id="selReflSymbol">
            <option value="">(全部 symbol)</option>
            <option value="NVDA">NVDA</option>
            <option value="AAPL">AAPL</option>
          </select>
          <select id="selReflCycle">
            <option value="">(全部 cycle_type)</option>
            <option value="weekly">weekly</option>
            <option value="monthly">monthly</option>
          </select>
        </div>
        <div class="btn-row">
          <button type="button" class="btn" id="btnLoadReflections">刷新列表</button>
          <span class="meta" id="reflMeta"></span>
        </div>
        <div id="reflList" class="report-content">点击“刷新列表”加载</div>
        <div style="height:0.75rem"></div>
        <div class="card" style="margin-bottom:0">
          <h3 style="margin-bottom:0.75rem">详情（reflection_content）</h3>
          <div id="reflDetail" class="report-content">(从列表点选一条)</div>
        </div>
      </div>
    </div>

    <div id="panel-tables" class="panel">
      <div class="card">
        <h3>选择表</h3>
        <div class="report-selector">
          <select id="selTable"><option value="">选择表</option></select>
        </div>
        <div id="tableData" class="report-content">选择表查看数据</div>
      </div>
    </div>
  </div>

  <script>
    const API = '';
    let overview = null;
    let currentReportId = null;
    let currentSummaryId = null;
    let currentTradingSummaryId = null;

    document.querySelectorAll('.tab').forEach(t => {
      t.onclick = () => {
        document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
        document.querySelectorAll('.panel').forEach(x => x.classList.remove('active'));
        t.classList.add('active');
        document.getElementById('panel-' + t.dataset.panel).classList.add('active');
        if (t.dataset.panel === 'reports') loadDates();
        if (t.dataset.panel === 'summaries') loadSummaryDates();
        if (t.dataset.panel === 'trading') loadTradingSummaryDates();
        if (t.dataset.panel === 'reflections') loadReflections();
        if (t.dataset.panel === 'tables') loadTableList();
      };
    });

    async function loadOverview() {
      const r = await fetch(API + '/api/overview');
      overview = await r.json();
      document.getElementById('dbPath').textContent = overview.db;
      const el = document.getElementById('overviewTables');
      el.innerHTML = overview.tables.map(t => `
        <div class="table-item" data-table="${t.name}">
          <div class="name">${t.name}</div>
          <div class="rows">${t.rows} 行</div>
          ${t.by_symbol ? t.by_symbol.map(s => `<div class="rows">${s.symbol}: ${s.count}</div>`).join('') : ''}
        </div>
      `).join('');
      document.querySelectorAll('#overviewTables .table-item').forEach(item => {
        item.onclick = () => {
          document.querySelector('.tab[data-panel=tables]').click();
          document.getElementById('selTable').value = item.dataset.table;
          loadTableData();
        };
      });
    }

    async function loadDates() {
      const symbol = document.getElementById('selSymbol').value;
      const r = await fetch(API + '/api/dates?symbol=' + symbol);
      const d = await r.json();
      const sel = document.getElementById('selDate');
      sel.innerHTML = '<option value="">选择日期</option>' + d.dates.map(x => `<option value="${x}">${x}</option>`).join('');
      sel.onchange = loadReport;
    }

    async function loadReport() {
      const symbol = document.getElementById('selSymbol').value;
      const date = document.getElementById('selDate').value;
      const type = document.getElementById('selType').value;
      const el = document.getElementById('reportContent');
      const meta = document.getElementById('reportMeta');
      currentReportId = null;
      meta.textContent = '';
      if (!date) { el.textContent = '请选择日期'; return; }
      el.textContent = '加载中...';
      try {
        const r = await fetch(API + `/api/report?symbol=${symbol}&date=${date}&type=${type}`);
        const j = await r.json();
        if (j.error) { el.textContent = j.error; return; }
        currentReportId = j.id != null ? j.id : null;
        el.textContent = j.content || '(空)';
        meta.textContent = j.id != null ? `id=${j.id}  ${j.created_at || ''}` : '';
      } catch (e) { el.textContent = '加载失败: ' + e.message; }
      document.getElementById('selType').onchange = loadReport;
    }

    async function loadSummaryDates() {
      const symbol = document.getElementById('selSummarySymbol').value;
      const r = await fetch(API + '/api/summary_dates?symbol=' + encodeURIComponent(symbol));
      const d = await r.json();
      const sel = document.getElementById('selSummaryDate');
      sel.innerHTML = '<option value="">选择日期</option>' + d.dates.map(x => `<option value="${x}">${x}</option>`).join('');
      sel.onchange = loadSummary;
    }

    async function loadSummary() {
      const symbol = document.getElementById('selSummarySymbol').value;
      const date = document.getElementById('selSummaryDate').value;
      const type = document.getElementById('selSummaryType').value;
      const el = document.getElementById('summaryContent');
      const meta = document.getElementById('summaryMeta');
      currentSummaryId = null;
      meta.textContent = '';
      if (!date) { el.textContent = '请选择日期'; return; }
      el.textContent = '加载中...';
      try {
        const r = await fetch(API + `/api/summary?symbol=${encodeURIComponent(symbol)}&date=${encodeURIComponent(date)}&type=${encodeURIComponent(type)}`);
        const j = await r.json();
        if (j.error) { el.textContent = j.error; return; }
        currentSummaryId = j.id != null ? j.id : null;
        el.textContent = j.content || '(空)';
        const parts = [];
        if (j.id != null) parts.push('id=' + j.id);
        if (j.created_at) parts.push(String(j.created_at));
        if (j.window_start_date && j.window_end_date) {
          parts.push('窗口 ' + j.window_start_date + ' ~ ' + j.window_end_date);
        }
        if (j.source_reports_count != null) parts.push('源报告数=' + j.source_reports_count);
        if (j.llm_model) parts.push('model=' + j.llm_model);
        if (j.token_usage != null) parts.push('tokens=' + j.token_usage);
        meta.textContent = parts.join('  ·  ');
      } catch (e) { el.textContent = '加载失败: ' + e.message; }
      document.getElementById('selSummaryType').onchange = loadSummary;
    }

    async function loadTradingSummaryDates() {
      const symbol = document.getElementById('selTradingSymbol').value;
      const r = await fetch(API + '/api/trading_summary_dates?symbol=' + encodeURIComponent(symbol));
      const d = await r.json();
      const sel = document.getElementById('selTradingDate');
      sel.innerHTML = '<option value="">选择日期</option>' + d.dates.map(x => `<option value="${x}">${x}</option>`).join('');
      sel.onchange = loadTradingSummary;
    }

    function fmt(v) {
      if (v === null || v === undefined) return '';
      if (typeof v === 'number') return String(v);
      return String(v);
    }

    function renderKv(map) {
      const entries = Object.entries(map || {});
      if (entries.length === 0) return '(无)';
      return entries.map(([k,v]) => `<div class="k">${k}</div><div class="v">${String(v).replace(/</g,'&lt;').replace(/>/g,'&gt;')}</div>`).join('');
    }

    async function loadTradingSummary() {
      const symbol = document.getElementById('selTradingSymbol').value;
      const date = document.getElementById('selTradingDate').value;
      const kvEl = document.getElementById('tradingKv');
      const jsonEl = document.getElementById('tradingJson');
      const meta = document.getElementById('tradingMeta');
      currentTradingSummaryId = null;
      meta.textContent = '';
      kvEl.innerHTML = '';
      jsonEl.textContent = '(选择日期后显示)';
      if (!date) { jsonEl.textContent = '请选择日期'; return; }
      jsonEl.textContent = '加载中...';
      try {
        const r = await fetch(API + `/api/trading_summary?symbol=${encodeURIComponent(symbol)}&date=${encodeURIComponent(date)}`);
        const j = await r.json();
        if (!r.ok || j.error) { jsonEl.textContent = j.error || '加载失败'; return; }
        currentTradingSummaryId = j.id != null ? j.id : null;
        meta.textContent = j.id != null ? `id=${j.id}  ${j.created_at || ''}` : '';
        kvEl.innerHTML = renderKv({
          date: j.date,
          symbol: j.symbol,
          market_regime: j.market_regime,
          selected_strategy: j.selected_strategy,
          expected_behavior: j.expected_behavior,
          actual_return: j.actual_return,
          actual_max_drawdown: j.actual_max_drawdown,
          positioning: j.positioning,
          anomaly: j.anomaly,
        });
        const parsed = j.summary_json_parsed;
        if (parsed) {
          jsonEl.textContent = JSON.stringify(parsed, null, 2);
        } else {
          jsonEl.textContent = j.summary_json || '(空)';
        }
      } catch (e) {
        jsonEl.textContent = '加载失败: ' + e.message;
      }
    }

    async function loadReflections() {
      const symbol = document.getElementById('selReflSymbol').value;
      const cycle = document.getElementById('selReflCycle').value;
      const listEl = document.getElementById('reflList');
      const meta = document.getElementById('reflMeta');
      listEl.textContent = '加载中...';
      meta.textContent = '';
      try {
        const qs = new URLSearchParams();
        if (symbol) qs.set('symbol', symbol);
        if (cycle) qs.set('cycle_type', cycle);
        qs.set('limit', '100');
        const r = await fetch(API + '/api/cycle_reflections?' + qs.toString());
        const j = await r.json();
        const rows = j.rows || [];
        meta.textContent = `共 ${rows.length} 条（显示最近 ${rows.length}）`;
        if (rows.length === 0) { listEl.textContent = '无数据'; return; }
        listEl.innerHTML = rows.map(row => {
          const title = `${row.cycle_type} ${row.cycle_start_date}~${row.cycle_end_date} ${row.symbol || ''}`.trim();
          const ki = row.key_insights ? String(row.key_insights).replace(/</g,'&lt;').replace(/>/g,'&gt;') : '';
          return `<div style="padding:0.5rem 0;border-bottom:1px solid #30363d">
            <div style="display:flex;gap:0.5rem;align-items:center;flex-wrap:wrap">
              <button class="btn btn-mini" data-refl-id="${row.id}">查看</button>
              <div style="font-weight:600">${title}</div>
            </div>
            <div class="meta">${ki}</div>
          </div>`;
        }).join('');
        listEl.querySelectorAll('[data-refl-id]').forEach(btn => {
          btn.onclick = () => loadReflectionDetail(btn.getAttribute('data-refl-id'));
        });
      } catch (e) {
        listEl.textContent = '加载失败: ' + e.message;
      }
    }

    async function loadReflectionDetail(id) {
      const el = document.getElementById('reflDetail');
      el.textContent = '加载中...';
      try {
        const r = await fetch(API + '/api/cycle_reflection?id=' + encodeURIComponent(id));
        const j = await r.json();
        if (!r.ok || j.error) { el.textContent = j.error || '加载失败'; return; }
        if (j.reflection_content_parsed) {
          el.textContent = JSON.stringify(j.reflection_content_parsed, null, 2);
        } else {
          el.textContent = j.reflection_content || '(空)';
        }
      } catch (e) {
        el.textContent = '加载失败: ' + e.message;
      }
    }

    document.getElementById('btnDeleteSummary').onclick = async () => {
      const symbol = document.getElementById('selSummarySymbol').value;
      const date = document.getElementById('selSummaryDate').value;
      const type = document.getElementById('selSummaryType').value;
      if (!date) { alert('请先选择日期'); return; }
      if (!confirm('确定删除「' + symbol + ' / ' + date + ' / ' + type + '」这条 Summary？不可恢复。')) return;
      try {
        const r = await fetch(API + '/api/delete_summary', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ symbol, date, type })
        });
        const j = await r.json();
        if (j.error) { alert(j.error); return; }
        alert('已删除 ' + (j.deleted || 0) + ' 条');
        document.getElementById('summaryContent').textContent = '已删除，请重新选择或刷新日期列表';
        document.getElementById('summaryMeta').textContent = '';
        currentSummaryId = null;
        loadSummaryDates();
      } catch (e) { alert('删除失败: ' + e.message); }
    };

    document.getElementById('btnDeleteReport').onclick = async () => {
      const symbol = document.getElementById('selSymbol').value;
      const date = document.getElementById('selDate').value;
      const type = document.getElementById('selType').value;
      if (!date) { alert('请先选择日期'); return; }
      if (!confirm('确定删除「' + symbol + ' / ' + date + ' / ' + type + '」这条报告？不可恢复。')) return;
      try {
        const r = await fetch(API + '/api/delete_report', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ symbol, date, type })
        });
        const j = await r.json();
        if (j.error) { alert(j.error); return; }
        alert('已删除 ' + (j.deleted || 0) + ' 条');
        document.getElementById('reportContent').textContent = '已删除，请重新选择或刷新日期列表';
        document.getElementById('reportMeta').textContent = '';
        currentReportId = null;
        loadDates();
      } catch (e) { alert('删除失败: ' + e.message); }
    };

    function loadTableList() {
      if (!overview) return;
      const sel = document.getElementById('selTable');
      sel.innerHTML = '<option value="">选择表</option>' +
        overview.tables.filter(t => !t.name.startsWith('sqlite')).map(t =>
          `<option value="${t.name}">${t.name} (${t.rows} 行)</option>`
        ).join('');
      sel.onchange = loadTableData;
    }

    const ALLOW_DELETE_TABLES = ['analyst_reports', 'analyst_summaries'];

    async function deleteTableRow(table, id) {
      if (!confirm('确定删除 id=' + id + ' ？不可恢复。')) return;
      try {
        const r = await fetch(API + '/api/delete_row', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ table, id })
        });
        const j = await r.json();
        if (!r.ok) { alert(j.error || '删除失败'); return; }
        loadTableData();
        loadOverview();
      } catch (e) { alert('删除失败: ' + e.message); }
    }

    async function loadTableData() {
      const name = document.getElementById('selTable').value;
      const el = document.getElementById('tableData');
      if (!name) { el.textContent = '请选择表'; return; }
      el.textContent = '加载中...';
      try {
        const r = await fetch(API + '/api/table/' + encodeURIComponent(name) + '?limit=100');
        const j = await r.json();
        const cols = j.columns;
        const rows = j.rows;
        if (rows.length === 0) { el.innerHTML = '无数据'; return; }
        const showDel = ALLOW_DELETE_TABLES.includes(name) && cols.includes('id');
        const headCols = showDel ? ['<th>操作</th>'].concat(cols.map(c => '<th>' + c + '</th>')) : cols.map(c => '<th>' + c + '</th>');
        el.innerHTML = '<table class="data-table"><thead><tr>' + headCols.join('') + '</tr></thead><tbody>' +
          rows.map(row => '<tr>' +
            (showDel ? '<td><button type="button" class="btn btn-danger btn-mini" data-del-id="' + row.id + '">删除</button></td>' : '') +
            cols.map(c => {
            let v = row[c];
            if (v === null) v = '';
            return '<td>' + String(v).replace(/</g, '&lt;').replace(/>/g, '&gt;').substring(0, 300) + (String(v).length > 300 ? '...' : '') + '</td>';
          }).join('') + '</tr>').join('') + '</tbody></table>' +
          `<div style="margin-top:0.5rem;color:#8b949e">共 ${j.total} 行，显示前 ${rows.length} 行</div>`;
        if (showDel) {
          el.querySelectorAll('[data-del-id]').forEach(btn => {
            btn.onclick = () => deleteTableRow(name, btn.getAttribute('data-del-id'));
          });
        }
      } catch (e) { el.textContent = '加载失败: ' + e.message; }
    }

    document.getElementById('selSymbol').onchange = () => { loadDates(); loadReport(); };
    document.getElementById('selType').onchange = loadReport;
    document.getElementById('selSummarySymbol').onchange = () => { loadSummaryDates(); loadSummary(); };
    document.getElementById('selSummaryType').onchange = loadSummary;
    document.getElementById('selTradingSymbol').onchange = () => { loadTradingSummaryDates(); loadTradingSummary(); };
    document.getElementById('btnLoadReflections').onclick = loadReflections;
    document.getElementById('selReflSymbol').onchange = loadReflections;
    document.getElementById('selReflCycle').onchange = loadReflections;

    loadOverview().then(() => {
      loadDates();
      loadSummaryDates();
      loadTradingSummaryDates();
    });
  </script>
</body>
</html>
"""


def main():
    global DB_PATH
    parser = argparse.ArgumentParser(description="TradeSwarm SQLite Web viewer")
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Path to SQLite file (default: storage/db/memory.db, fallback: memory.db)",
    )
    args = parser.parse_args()

    DB_PATH = resolve_db_path(args.db)
    if not DB_PATH.exists():
        print(f"数据库不存在: {DB_PATH}")
        print("可通过 --db 或环境变量 DB_VIEWER_DB 指定数据库路径")
        return
    print(f"启动 memory.db 查看器: http://127.0.0.1:5555")
    print(f"当前数据库: {DB_PATH}")
    print("按 Ctrl+C 停止")
    app.run(host="127.0.0.1", port=5555, debug=False)


if __name__ == "__main__":
    main()
