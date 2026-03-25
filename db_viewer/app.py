# -*- coding: utf-8 -*-
"""memory.db 本地 Web 查看器"""
import re
import sqlite3
from pathlib import Path
from flask import Flask, render_template_string, jsonify, request

APP_DIR = Path(__file__).parent
PROJECT_ROOT = APP_DIR.parent
DB_PATH = PROJECT_ROOT / "memory.db"

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
    return jsonify(
        {
            "id": row["id"],
            "content": row["report_content"],
            "created_at": row["created_at"],
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
        <div class="btn-row">
          <button type="button" class="btn btn-danger" id="btnDeleteReport">删除当前报告</button>
          <span class="meta" id="reportMeta"></span>
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
    let currentReportId = null;

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
