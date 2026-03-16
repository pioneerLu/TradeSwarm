# -*- coding: utf-8 -*-
"""memory.db 本地 Web 查看器"""
import sqlite3
import json
from pathlib import Path
from flask import Flask, render_template_string, jsonify, request

APP_DIR = Path(__file__).parent
PROJECT_ROOT = APP_DIR.parent
DB_PATH = PROJECT_ROOT / "memory.db"

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
    return jsonify({"content": row["report_content"], "created_at": row["created_at"]})


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
        <div id="reportContent" class="report-content">选择日期和类型查看报告内容</div>
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

    document.querySelectorAll('.tab').forEach(t => {
      t.onclick = () => {
        document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
        document.querySelectorAll('.panel').forEach(x => x.classList.remove('active'));
        t.classList.add('active');
        document.getElementById('panel-' + t.dataset.panel).classList.add('active');
        if (t.dataset.panel === 'reports') loadDates();
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
      if (!date) { el.textContent = '请选择日期'; return; }
      el.textContent = '加载中...';
      try {
        const r = await fetch(API + `/api/report?symbol=${symbol}&date=${date}&type=${type}`);
        const j = await r.json();
        if (j.error) el.textContent = j.error;
        else el.textContent = j.content || '(空)';
      } catch (e) { el.textContent = '加载失败: ' + e.message; }
      document.getElementById('selType').onchange = loadReport;
    }

    function loadTableList() {
      if (!overview) return;
      const sel = document.getElementById('selTable');
      sel.innerHTML = '<option value="">选择表</option>' +
        overview.tables.filter(t => !t.name.startsWith('sqlite')).map(t =>
          `<option value="${t.name}">${t.name} (${t.rows} 行)</option>`
        ).join('');
      sel.onchange = loadTableData;
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
        el.innerHTML = '<table class="data-table"><thead><tr>' +
          cols.map(c => '<th>' + c + '</th>').join('') + '</tr></thead><tbody>' +
          rows.map(row => '<tr>' + cols.map(c => {
            let v = row[c];
            if (v === null) v = '';
            return '<td>' + String(v).replace(/</g, '&lt;').replace(/>/g, '&gt;').substring(0, 300) + (String(v).length > 300 ? '...' : '') + '</td>';
          }).join('') + '</tr>').join('') + '</tbody></table>' +
          `<div style="margin-top:0.5rem;color:#8b949e">共 ${j.total} 行，显示前 ${rows.length} 行</div>`;
      } catch (e) { el.textContent = '加载失败: ' + e.message; }
    }

    document.getElementById('selSymbol').onchange = () => { loadDates(); loadReport(); };
    document.getElementById('selType').onchange = loadReport;

    loadOverview().then(() => {
      loadDates();
    });
  </script>
</body>
</html>
"""


def main():
    if not DB_PATH.exists():
        print(f"数据库不存在: {DB_PATH}")
        return
    print(f"启动 memory.db 查看器: http://127.0.0.1:5555")
    print("按 Ctrl+C 停止")
    app.run(host="127.0.0.1", port=5555, debug=False)


if __name__ == "__main__":
    main()
