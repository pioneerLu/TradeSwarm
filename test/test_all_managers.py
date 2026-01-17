"""
综合测试脚本：测试所有 Manager 和 Risk Management 节点

验证以下节点在新 AgentState 结构下是否可以正常运行：
- Research Manager
- Risk Manager
- Conservative Debator (Safe Debator)
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv()


def run_test(test_file: str, test_name: str) -> int:
    """运行单个测试模块"""
    print("\n" + "=" * 80)
    print(f"运行测试: {test_name}")
    print("=" * 80)

    try:
        # 直接执行测试文件
        import subprocess
        import sys
        result = subprocess.run(
            [sys.executable, test_file],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        # 只显示关键信息，避免编码问题
        if result.returncode == 0:
            print("[OK] 测试通过")
        else:
            print("[ERROR] 测试失败")
            # 只显示错误的关键部分
            if result.stderr:
                error_lines = result.stderr.split('\n')[:5]  # 只显示前5行
                for line in error_lines:
                    if line.strip():
                        print(f"  {line}")
        return result.returncode
    except Exception as e:
        print(f"[ERROR] 运行测试 {test_name} 时出错: {str(e)}")
        import traceback

        traceback.print_exc()
        return 1


def main():
    """主测试函数，运行所有测试"""
    print("=" * 80)
    print("综合测试：Manager 和 Risk Management 节点")
    print("=" * 80)
    print("\n将依次测试以下节点：")
    print("  1. Research Manager")
    print("  2. Risk Manager")
    print("  3. Conservative Debator (Safe Debator)")

    tests = [
        ("test/test_research_manager.py", "Research Manager"),
        ("test/test_risk_manager.py", "Risk Manager"),
        ("test/test_conservative_debator.py", "Conservative Debator"),
    ]

    results = []
    for module_name, test_name in tests:
        result = run_test(module_name, test_name)
        results.append((test_name, result))

    # 汇总结果
    print("\n" + "=" * 80)
    print("测试结果汇总")
    print("=" * 80)
    for test_name, result in results:
        status = "[PASS] 通过" if result == 0 else "[FAIL] 失败"
        print(f"  {test_name}: {status}")

    total = len(results)
    passed = sum(1 for _, result in results if result == 0)
    failed = total - passed

    print(f"\n总计: {total} 个测试")
    print(f"通过: {passed} 个")
    print(f"失败: {failed} 个")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit(main())

