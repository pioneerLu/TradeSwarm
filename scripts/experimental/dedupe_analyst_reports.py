# -*- coding: utf-8 -*-
"""
删除 analyst_reports 中重复记录，仅保留每组 (symbol, trade_date, analyst_type) 中 id 最大的一条。

用法:
  python dedupe_analyst_reports.py [--db memory.db] [--dry-run]
  python dedupe_analyst_reports.py --dry-run --export dedupe_preview.json   # 将待删除记录导出为 JSON 便于查看
  python dedupe_analyst_reports.py --ids 168,169                          # 仅删除指定 id（可加 --dry-run 先预览）
"""
import argparse
import json
import sqlite3
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="按 (symbol, trade_date, analyst_type) 去重，或按指定 id 删除")
    parser.add_argument("--db", type=str, default="memory.db", help="数据库路径")
    parser.add_argument("--dry-run", action="store_true", help="仅打印将删除的 id，不执行删除")
    parser.add_argument("--export", type=str, default=None, metavar="PATH", help="将待删除记录导出到该 JSON 文件（便于查看具体内容）")
    parser.add_argument("--ids", type=str, default=None, metavar="ID1,ID2,...", help="仅删除指定 id，多个用逗号分隔，如 168,169")
    args = parser.parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"数据库不存在: {db_path}")
        return

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if args.ids:
        to_delete = [int(x.strip()) for x in args.ids.split(",") if x.strip()]
        if not to_delete:
            print("--ids 未提供有效 id")
            conn.close()
            return
        print(f"将删除指定的 {len(to_delete)} 条记录: id = {to_delete}")
    else:
        # 每组 (symbol, trade_date, analyst_type) 保留 id 最大的；选出“存在同组且 id 更大”的行的 id 即待删除
        cur.execute("""
            SELECT a.id FROM analyst_reports a
            WHERE EXISTS (
                SELECT 1 FROM analyst_reports b
                WHERE a.symbol = b.symbol AND a.trade_date = b.trade_date AND a.analyst_type = b.analyst_type
                  AND b.id > a.id
            )
            ORDER BY a.id
        """)
        to_delete = [row["id"] for row in cur.fetchall()]
        if not to_delete:
            print("没有重复记录，无需删除。")
            conn.close()
            return
        print(f"将删除 {len(to_delete)} 条重复记录（保留每组 id 最大的一条）")
        print("待删除 id:", to_delete[:30], "..." if len(to_delete) > 30 else "")

    # 导出待删除记录到 JSON（便于查看具体内容）
    if args.export:
        placeholders = ",".join("?" * len(to_delete))
        cur.execute(
            f"SELECT id, analyst_type, symbol, trade_date, report_content, created_at FROM analyst_reports WHERE id IN ({placeholders}) ORDER BY id",
            to_delete,
        )
        rows = cur.fetchall()
        export_data = {
            "count": len(rows),
            "ids": to_delete,
            "records": [
                {
                    "id": row[0],
                    "analyst_type": row[1],
                    "symbol": row[2],
                    "trade_date": row[3],
                    "report_content": row[4],
                    "created_at": row[5],
                }
                for row in rows
            ],
        }
        out_path = Path(args.export)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        print(f"已导出 {len(rows)} 条待删除记录到 {out_path}")

    if args.dry_run:
        print("[dry-run] 未执行删除。去掉 --dry-run 后再次运行将真正删除。")
        conn.close()
        return

    for id_ in to_delete:
        cur.execute("DELETE FROM analyst_reports WHERE id = ?", (id_,))
    conn.commit()
    print(f"[OK] 已删除 {len(to_delete)} 条。")
    conn.close()


if __name__ == "__main__":
    main()
