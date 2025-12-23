#!/usr/bin/env python3
"""
分析akshare_provider财务报表返回结果的脚本
"""

import json
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_sources.akshare_provider import AkshareProvider

def analyze_method_return(provider, method_name, symbol="600519"):
    """分析方法返回结果的具体格式与内容"""
    print(f"\n{'='*60}")
    print(f"分析 {method_name} 方法")
    print(f"股票代码: {symbol}")
    print(f"{'='*60}")
    
    # 获取方法
    method = getattr(provider, method_name)
    
    # 调用方法获取结果
    result = method(symbol, "annual", 1, "all")
    
    print(f"\n1. 返回结果类型: {type(result)}")
    
    if isinstance(result, dict):
        print(f"\n2. 字典键列表: {list(result.keys())}")
        
        for key, value in result.items():
            print(f"\n3. 键 '{key}' 的详细信息:")
            print(f"   - 类型: {type(value)}")
            
            if key == "data" and isinstance(value, list):
                print(f"   - 列表长度: {len(value)}")
                if len(value) > 0:
                    print(f"   - 第一个元素类型: {type(value[0])}")
                    if isinstance(value[0], dict):
                        print(f"   - 第一个元素的键: {list(value[0].keys())}")
                        # 显示前几个键值对作为示例
                        for i, (k, v) in enumerate(value[0].items()):
                            if i < 5:  # 只显示前5个
                                print(f"     - {k}: {v} (类型: {type(v)})")
                            else:
                                print(f"     - ... (还有 {len(value[0]) - 5} 个键)")
                                break
            elif key == "actual_source":
                print(f"   - 值: {value}")
            elif key == "errors" and isinstance(value, list):
                print(f"   - 错误列表长度: {len(value)}")
                for i, error in enumerate(value):
                    print(f"     - 错误 {i+1}: {error}")
            else:
                print(f"   - 值: {value}")
    
    print(f"\n4. 完整返回结果(JSON格式，美化):")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

def main():
    """主函数"""
    # 初始化AkshareProvider
    config = {}
    akshare_provider = AkshareProvider(config=config)
    
    print("开始分析财务报表方法的返回结果...")
    
    # 分析三个方法
    methods_to_analyze = [
        "get_profit_statement",
        "get_balance_sheet", 
        "get_cash_flow_statement"
    ]
    
    for method in methods_to_analyze:
        try:
            analyze_method_return(akshare_provider, method)
        except Exception as e:
            print(f"分析 {method} 时出错: {str(e)}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)
    print("分析完成!")
    print("="*60)

if __name__ == "__main__":
    main()
