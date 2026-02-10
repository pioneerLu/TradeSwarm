"""
Memory DB 交互工具模块

提供与 memory.db 数据库交互的便捷函数，包括：
- 插入分析师报告
- 查询报告（今日报告、历史报告）
- 更新报告
- 删除报告
- 统计信息
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import sqlite3
from pathlib import Path


class MemoryDBHelper:
    """
    Memory DB 交互助手类
    
    提供与 memory.db 数据库交互的完整功能。
    """
    
    def __init__(self, db_path: str = "memory.db") -> None:
        """
        初始化数据库连接。
        
        Args:
            db_path: 数据库文件路径，默认为 "memory.db"
        """
        self.db_path = Path(db_path)
        self.conn: Optional[sqlite3.Connection] = None
        self._ensure_table_exists()
    
    def _ensure_table_exists(self) -> None:
        """确保底层数据表存在。

        当前包括：

        - analyst_reports: 存储原始的 today_report 报告
        - analyst_summaries: 存储 7 个交易日滚动窗口的结构化 summary
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 原始报告表（today_report）
        create_reports_table_sql = """
        CREATE TABLE IF NOT EXISTS analyst_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analyst_type TEXT NOT NULL,
            symbol TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            report_content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        cursor.execute(create_reports_table_sql)

        # 新增：summary 表（7 日滚动窗口的结构化 summary）
        create_summaries_table_sql = """
        CREATE TABLE IF NOT EXISTS analyst_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analyst_type TEXT NOT NULL,
            symbol TEXT NOT NULL,
            trade_date TEXT NOT NULL,              -- summary 对应日期（窗口结束日，T）
            summary_content TEXT NOT NULL,         -- 结构化 summary（通常为 JSON 字符串）
            window_start_date TEXT NOT NULL,       -- 窗口开始日期（T-6，按交易日计算）
            window_end_date TEXT NOT NULL,         -- 窗口结束日期（T）
            source_reports_count INTEGER,          -- 窗口内原始报告数量
            llm_model TEXT,                        -- 可选：使用的 LLM 模型标识
            token_usage INTEGER,                   -- 可选：token 消耗
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(analyst_type, symbol, trade_date)
        )
        """
        cursor.execute(create_summaries_table_sql)

        # 索引：加速按 analyst_type / symbol / trade_date 查询
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_analyst_reports_lookup
            ON analyst_reports(analyst_type, symbol, trade_date)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_analyst_summaries_lookup
            ON analyst_summaries(analyst_type, symbol, trade_date)
            """
        )

        conn.commit()
        conn.close()
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接（单例模式）。"""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
        return self.conn
    
    def close(self) -> None:
        """关闭数据库连接。"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def insert_report(
        self,
        analyst_type: str,
        symbol: str,
        trade_date: str,
        report_content: str,
    ) -> bool:
        """
        插入分析师报告到数据库。
        
        Args:
            analyst_type: 分析师类型（'market', 'news', 'sentiment', 'fundamentals'）
            symbol: 股票代码（如 '000001'）
            trade_date: 交易日期（如 '2024-01-15'）
            report_content: 报告内容（文本）
            
        Returns:
            插入是否成功
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            insert_sql = """
            INSERT INTO analyst_reports (analyst_type, symbol, trade_date, report_content)
            VALUES (?, ?, ?, ?)
            """
            
            cursor.execute(
                insert_sql,
                (analyst_type, symbol, trade_date, report_content)
            )
            conn.commit()
            cursor.close()
            
            print(f"[OK] 成功插入报告: {analyst_type} - {symbol} - {trade_date}")
            return True
            
        except Exception as e:
            print(f"[ERROR] 插入报告失败: {e}")
            if self.conn:
                self.conn.rollback()
            return False
    
    def query_today_report(
        self,
        analyst_type: str,
        symbol: str,
        trade_date: str,
    ) -> Optional[str]:
        """
        查询今日报告（返回最新的一个）。
        
        Args:
            analyst_type: 分析师类型
            symbol: 股票代码
            trade_date: 交易日期
            
        Returns:
            报告内容，如果不存在返回 None
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            sql = """
            SELECT report_content 
            FROM analyst_reports
            WHERE analyst_type=? 
                AND symbol=? 
                AND trade_date=?
            ORDER BY created_at DESC 
            LIMIT 1
            """
            
            cursor.execute(sql, (analyst_type, symbol, trade_date))
            result = cursor.fetchone()
            cursor.close()
            
            if result and result[0]:
                return result[0]
            return None
            
        except Exception as e:
            print(f"[ERROR] 查询今日报告失败: {e}")
            return None
    
    def query_history_reports(
        self,
        analyst_type: str,
        symbol: str,
        trade_date: str,
        lookback_days: int = 7,
    ) -> List[Dict[str, Any]]:
        """
        查询历史报告。
        
        Args:
            analyst_type: 分析师类型
            symbol: 股票代码
            trade_date: 交易日期（基准日期）
            lookback_days: 回溯天数，默认 7 天
            
        Returns:
            报告列表，每个元素包含 id, trade_date, report_content, created_at
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            sql = """
            SELECT id, trade_date, report_content, created_at
            FROM analyst_reports
            WHERE analyst_type=? 
                AND symbol=? 
                AND trade_date <= ?
                AND trade_date >= date(?, '-{} days')
                AND report_content IS NOT NULL
                AND report_content != ''
            ORDER BY trade_date ASC, created_at ASC
            """.format(lookback_days)
            
            cursor.execute(sql, (analyst_type, symbol, trade_date, trade_date))
            results = cursor.fetchall()
            cursor.close()
            
            reports = []
            for row in results:
                reports.append({
                    "id": row[0],
                    "trade_date": row[1],
                    "report_content": row[2],
                    "created_at": row[3],
                })
            
            return reports
            
        except Exception as e:
            print(f"[ERROR] 查询历史报告失败: {e}")
            return []

    # ------------------------------------------------------------------
    # Summary（7 日窗口结构化历史报告）相关接口
    # ------------------------------------------------------------------

    def upsert_summary(
        self,
        analyst_type: str,
        symbol: str,
        trade_date: str,
        summary_content: str,
        window_start_date: str,
        window_end_date: str,
        source_reports_count: int,
        llm_model: Optional[str] = None,
        token_usage: Optional[int] = None,
    ) -> bool:
        """插入或更新 7 日窗口的结构化 summary。

        - 如果 (analyst_type, symbol, trade_date) 已存在，则执行 UPDATE
        - 否则执行 INSERT
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            sql = """
            INSERT INTO analyst_summaries (
                analyst_type,
                symbol,
                trade_date,
                summary_content,
                window_start_date,
                window_end_date,
                source_reports_count,
                llm_model,
                token_usage,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(analyst_type, symbol, trade_date)
            DO UPDATE SET
                summary_content = excluded.summary_content,
                window_start_date = excluded.window_start_date,
                window_end_date = excluded.window_end_date,
                source_reports_count = excluded.source_reports_count,
                llm_model = excluded.llm_model,
                token_usage = excluded.token_usage,
                updated_at = CURRENT_TIMESTAMP
            """

            cursor.execute(
                sql,
                (
                    analyst_type,
                    symbol,
                    trade_date,
                    summary_content,
                    window_start_date,
                    window_end_date,
                    source_reports_count,
                    llm_model,
                    token_usage,
                ),
            )
            conn.commit()
            cursor.close()

            print(
                "[OK] 成功更新 summary: "
                f"{analyst_type} - {symbol} - {trade_date} "
                f"(窗口 {window_start_date} ~ {window_end_date}, 报告数={source_reports_count})"
            )
            return True

        except Exception as e:
            print(f"[ERROR] 更新 summary 失败: {e}")
            if self.conn:
                self.conn.rollback()
            return False

    def query_summary(
        self,
        analyst_type: str,
        symbol: str,
        trade_date: str,
    ) -> Optional[Dict[str, Any]]:
        """查询指定日期的结构化 summary（7 日滚动窗口）。

        按 (analyst_type, symbol, trade_date) 精确匹配。
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            sql = """
            SELECT
                id,
                analyst_type,
                symbol,
                trade_date,
                summary_content,
                window_start_date,
                window_end_date,
                source_reports_count,
                llm_model,
                token_usage,
                created_at,
                updated_at
            FROM analyst_summaries
            WHERE analyst_type = ?
              AND symbol = ?
              AND trade_date = ?
            LIMIT 1
            """

            cursor.execute(sql, (analyst_type, symbol, trade_date))
            row = cursor.fetchone()
            cursor.close()

            if not row:
                return None

            return {
                "id": row[0],
                "analyst_type": row[1],
                "symbol": row[2],
                "trade_date": row[3],
                "summary_content": row[4],
                "window_start_date": row[5],
                "window_end_date": row[6],
                "source_reports_count": row[7],
                "llm_model": row[8],
                "token_usage": row[9],
                "created_at": row[10],
                "updated_at": row[11],
            }

        except Exception as e:
            print(f"[ERROR] 查询 summary 失败: {e}")
            return None
    
    def query_all_reports(
        self,
        analyst_type: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        查询所有报告（支持过滤）。
        
        Args:
            analyst_type: 分析师类型（可选）
            symbol: 股票代码（可选）
            limit: 限制返回数量（可选）
            
        Returns:
            报告列表
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            conditions = []
            params = []
            
            if analyst_type:
                conditions.append("analyst_type = ?")
                params.append(analyst_type)
            
            if symbol:
                conditions.append("symbol = ?")
                params.append(symbol)
            
            where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
            limit_clause = f" LIMIT {limit}" if limit else ""
            
            sql = f"""
            SELECT id, analyst_type, symbol, trade_date, created_at
            FROM analyst_reports
            {where_clause}
            ORDER BY created_at DESC
            {limit_clause}
            """
            
            cursor.execute(sql, params)
            results = cursor.fetchall()
            cursor.close()
            
            reports = []
            for row in results:
                reports.append({
                    "id": row[0],
                    "analyst_type": row[1],
                    "symbol": row[2],
                    "trade_date": row[3],
                    "created_at": row[4],
                })
            
            return reports
            
        except Exception as e:
            print(f"[ERROR] 查询所有报告失败: {e}")
            return []
    
    def update_report(
        self,
        report_id: int,
        report_content: str,
    ) -> bool:
        """
        更新报告内容。
        
        Args:
            report_id: 报告 ID
            report_content: 新的报告内容
            
        Returns:
            更新是否成功
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            sql = """
            UPDATE analyst_reports
            SET report_content = ?, created_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """
            
            cursor.execute(sql, (report_content, report_id))
            conn.commit()
            cursor.close()
            
            print(f"[OK] 成功更新报告 ID: {report_id}")
            return True
            
        except Exception as e:
            print(f"[ERROR] 更新报告失败: {e}")
            if self.conn:
                self.conn.rollback()
            return False
    
    def delete_report(self, report_id: int) -> bool:
        """
        删除报告。
        
        Args:
            report_id: 报告 ID
            
        Returns:
            删除是否成功
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            sql = "DELETE FROM analyst_reports WHERE id = ?"
            cursor.execute(sql, (report_id,))
            conn.commit()
            cursor.close()
            
            print(f"[OK] 成功删除报告 ID: {report_id}")
            return True
            
        except Exception as e:
            print(f"[ERROR] 删除报告失败: {e}")
            if self.conn:
                self.conn.rollback()
            return False
    
    def get_statistics(
        self,
        symbol: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        获取统计信息。
        
        Args:
            symbol: 股票代码（可选，如果提供则只统计该股票）
            
        Returns:
            统计信息字典
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if symbol:
                sql = """
                SELECT 
                    analyst_type,
                    COUNT(*) as count,
                    MIN(trade_date) as earliest_date,
                    MAX(trade_date) as latest_date
                FROM analyst_reports
                WHERE symbol = ?
                GROUP BY analyst_type
                """
                cursor.execute(sql, (symbol,))
            else:
                sql = """
                SELECT 
                    analyst_type,
                    COUNT(*) as count,
                    MIN(trade_date) as earliest_date,
                    MAX(trade_date) as latest_date
                FROM analyst_reports
                GROUP BY analyst_type
                """
                cursor.execute(sql)
            
            results = cursor.fetchall()
            cursor.close()
            
            stats = {
                "total_reports": 0,
                "by_type": {},
            }
            
            for row in results:
                analyst_type = row[0]
                count = row[1]
                earliest = row[2]
                latest = row[3]
                
                stats["total_reports"] += count
                stats["by_type"][analyst_type] = {
                    "count": count,
                    "earliest_date": earliest,
                    "latest_date": latest,
                }
            
            return stats
            
        except Exception as e:
            print(f"[ERROR] 获取统计信息失败: {e}")
            return {"total_reports": 0, "by_type": {}}
    
    def __enter__(self):
        """上下文管理器入口。"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口。"""
        self.close()


# ==================== 便捷函数 ====================

def insert_report(
    analyst_type: str,
    symbol: str,
    trade_date: str,
    report_content: str,
    db_path: str = "memory.db",
) -> bool:
    """
    便捷函数：插入报告。
    
    Args:
        analyst_type: 分析师类型
        symbol: 股票代码
        trade_date: 交易日期
        report_content: 报告内容
        db_path: 数据库路径
        
    Returns:
        插入是否成功
    """
    with MemoryDBHelper(db_path) as helper:
        return helper.insert_report(analyst_type, symbol, trade_date, report_content)


def query_today_report(
    analyst_type: str,
    symbol: str,
    trade_date: str,
    db_path: str = "memory.db",
) -> Optional[str]:
    """
    便捷函数：查询今日报告。
    
    Args:
        analyst_type: 分析师类型
        symbol: 股票代码
        trade_date: 交易日期
        db_path: 数据库路径
        
    Returns:
        报告内容，如果不存在返回 None
    """
    with MemoryDBHelper(db_path) as helper:
        return helper.query_today_report(analyst_type, symbol, trade_date)


def query_history_reports(
    analyst_type: str,
    symbol: str,
    trade_date: str,
    lookback_days: int = 7,
    db_path: str = "memory.db",
) -> List[Dict[str, Any]]:
    """
    便捷函数：查询历史报告。
    
    Args:
        analyst_type: 分析师类型
        symbol: 股票代码
        trade_date: 交易日期
        lookback_days: 回溯天数
        db_path: 数据库路径
        
    Returns:
        报告列表
    """
    with MemoryDBHelper(db_path) as helper:
        return helper.query_history_reports(analyst_type, symbol, trade_date, lookback_days)


def upsert_summary(
    analyst_type: str,
    symbol: str,
    trade_date: str,
    summary_content: str,
    window_start_date: str,
    window_end_date: str,
    source_reports_count: int,
    llm_model: Optional[str] = None,
    token_usage: Optional[int] = None,
    db_path: str = "memory.db",
) -> bool:
    """便捷函数：插入或更新 summary。"""
    with MemoryDBHelper(db_path) as helper:
        return helper.upsert_summary(
            analyst_type=analyst_type,
            symbol=symbol,
            trade_date=trade_date,
            summary_content=summary_content,
            window_start_date=window_start_date,
            window_end_date=window_end_date,
            source_reports_count=source_reports_count,
            llm_model=llm_model,
            token_usage=token_usage,
        )


def query_summary(
    analyst_type: str,
    symbol: str,
    trade_date: str,
    db_path: str = "memory.db",
) -> Optional[Dict[str, Any]]:
    """便捷函数：查询指定日期的 summary。"""
    with MemoryDBHelper(db_path) as helper:
        return helper.query_summary(analyst_type, symbol, trade_date)


if __name__ == "__main__":
    """示例用法。"""
    print("=" * 80)
    print("Memory DB Helper 示例")
    print("=" * 80)
    
    # 使用上下文管理器
    with MemoryDBHelper() as db:
        # 1. 插入报告
        print("\n[1] 插入测试报告...")
        success = db.insert_report(
            analyst_type="market",
            symbol="000001",
            trade_date="2024-01-15",
            report_content="这是测试报告内容",
        )
        print(f"插入结果: {success}")
        
        # 2. 查询今日报告
        print("\n[2] 查询今日报告...")
        report = db.query_today_report("market", "000001", "2024-01-15")
        if report:
            print(f"报告内容: {report[:50]}...")
        else:
            print("未找到报告")
        
        # 3. 查询历史报告
        print("\n[3] 查询历史报告...")
        history = db.query_history_reports("market", "000001", "2024-01-15", lookback_days=7)
        print(f"历史报告数量: {len(history)}")
        
        # 4. 获取统计信息
        print("\n[4] 获取统计信息...")
        stats = db.get_statistics(symbol="000001")
        print(f"总报告数: {stats['total_reports']}")
        for analyst_type, info in stats["by_type"].items():
            print(f"  {analyst_type}: {info['count']} 条")
    
    print("\n" + "=" * 80)
    print("示例完成")
    print("=" * 80)

