# -*- coding: utf-8 -*-
"""
从 Summary 节点开始运行完整 Graph 流程

功能：
1. 从 memory.db 读取 Analyst 报告
2. 从 Summary 节点开始运行完整 Graph
3. 保存每一步输出（含 research / risk 子图内各节点，文件名带 step 序号与命名空间）
"""

import sys
from pathlib import Path
from typing import Any, Dict

# 添加项目根目录到路径
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tradingagents.graph.trading_graph import create_trading_graph
from tradingagents.graph.node_dump import (
    save_full_state_snapshot,
    save_node_output,
    stream_graph_updates_with_dump,
)
from tradingagents.graph.utils import load_llm_from_config
from tradingagents.agents.utils.memory_db_helper import MemoryDBHelper
from tradingagents.agents.utils.hybrid_memory import create_hybrid_trading_memory
from tradingagents.agents.utils.agentstate.agent_states import AgentState


def run_full_graph(
    symbol: str,
    trade_date: str,
    llm: Any,
    memory: Any,
    db_path: str = "memory.db",
    output_dir: str = "graph_outputs"
) -> Dict[str, Any]:
    """
    运行完整的 Graph 流程（从 Summary 节点开始）
    
    Args:
        symbol: 股票代码
        trade_date: 交易日期
        llm: LLM 实例
        memory: Memory 实例
        db_path: 数据库路径
        output_dir: 输出目录
        
    Returns:
        最终状态
    """
    print(f"\n{'='*80}")
    print(f"运行完整 Graph 流程（从 Summary 节点开始）")
    print(f"{'='*80}\n")
    
    # 检查数据库是否存在
    if not Path(db_path).exists():
        print(f"[ERROR] 数据库 {db_path} 不存在！")
        print("  请先运行 scripts/experimental/run_analysts_to_db.py 生成 Analyst 报告")
        raise FileNotFoundError(f"数据库不存在: {db_path}")
    
    # 创建输出目录
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 初始化数据库连接
    db_helper = MemoryDBHelper(db_path)
    
    # 创建 Graph
    print("[构建] 创建交易决策图...")
    graph = create_trading_graph(llm, memory, db_helper)
    print("[OK] Graph 创建成功")
    
    # 准备初始状态
    initial_state: AgentState = {
        "company_of_interest": symbol,
        "trade_date": trade_date,
        "trading_session": "pre_open",
        "messages": [],
    }
    
    # 运行 Graph
    print(f"\n[运行] 开始执行 Graph...")
    print(f"  股票代码: {symbol}")
    print(f"  交易日期: {trade_date}")
    print(f"  交易时段: pre_open")
    print(f"  数据库: {db_path}\n")
    
    current_state = dict(initial_state)
    executed_nodes: set[str] = set()

    try:
        print("\n[运行] 流式执行（含子图内每一步）并落盘...")
        final_state = stream_graph_updates_with_dump(
            graph,
            initial_state,
            dump_dir=output_path,
            verbose=True,
            log_prefix="执行",
        )
        if final_state:
            current_state.update(final_state)
            save_full_state_snapshot(final_state, output_path / "full_state_snapshot.json")
            save_node_output("final_state", final_state, output_path)
            print(f"  [OK] 最终状态与 full_state_snapshot.json 已保存")
        else:
            print("  [WARN] 未收到根图终态 values，跳过 final_state / full_state_snapshot")
        # 用于统计：统计 step_*_output.json 数量即可；保留集合兼容旧日志字段
        for p in sorted(output_path.glob("step_*_output.json")):
            executed_nodes.add(p.stem)
        
    except Exception as e:
        print(f"\n[ERROR] Graph 执行失败: {e}")
        import traceback
        traceback.print_exc()
        raise
    
    finally:
        db_helper.close()
    
    print(f"\n[完成] Graph 执行完成")
    print(f"  落盘步数（step_* 文件）: {len(executed_nodes)}")
    print(f"  输出目录: {output_path.absolute()}")
    
    return current_state


def main():
    """主函数"""
    print("="*80)
    print("从 Summary 节点开始运行完整 Graph 流程")
    print("="*80)
    
    # 配置参数
    symbol = "NVDA"
    trade_date = "2026-02-05"  # 使用指定的交易日期
    db_path = "memory.db"  # 使用 demo_data.db
    output_dir = "graph_outputs"
    
    # 删除旧的输出目录
    if Path(output_dir).exists():
        print(f"\n[清理] 删除旧的输出目录: {output_dir}")
        import shutil
        shutil.rmtree(output_dir)
    
    try:
        # 加载 LLM
        print(f"\n[初始化] 加载 LLM...")
        llm = load_llm_from_config()
        print("[OK] LLM 加载成功")
        
        memory = create_hybrid_trading_memory(
            db_path,
            symbol,
            config_path=REPO_ROOT / "config" / "config.yaml",
        )
        
        # 运行完整 Graph
        final_state = run_full_graph(
            symbol=symbol,
            trade_date=trade_date,
            llm=llm,
            memory=memory,
            db_path=db_path,
            output_dir=output_dir
        )
        
        # 打印摘要
        print(f"\n{'='*80}")
        print("执行摘要")
        print(f"{'='*80}")
        print(f"股票代码: {symbol}")
        print(f"交易日期: {trade_date}")
        print(f"数据库: {db_path}")
        print(f"输出目录: {output_dir}")
        print(f"\n[完成] Graph 执行完成！")
        
        # 关闭 Memory 数据库连接
        if 'memory' in locals():
            memory.close()
        
    except Exception as e:
        print(f"\n[ERROR] 执行失败: {e}")
        import traceback
        traceback.print_exc()
        # 确保关闭数据库连接
        if 'memory' in locals():
            memory.close()
        sys.exit(1)


if __name__ == "__main__":
    main()

