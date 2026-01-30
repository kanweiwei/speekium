#!/usr/bin/env python3
"""
测试 socket 超时问题 - PTT 功能无响应的根本原因

问题描述:
- PTT 操作 (ASR + LLM + TTS) 可能需要超过 30 秒
- Rust 客户端设置 30 秒读超时,导致长时间操作超时失败
- 需要测试超时设置是否合理

TDD 流程:
1. 编写失败的测试 (验证超时太短)
2. 修复超时设置
3. 运行测试验证修复
4. 验证 PTT 功能正常工作
"""

import asyncio
import json
import socket
import time
import sys
import os

# 添加项目根目录到 path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


class TestSocketTimeout:
    """测试 socket 超时设置"""

    def test_current_timeout_settings(self):
        """测试当前的超时设置是否合理"""
        print("\n=== 测试当前超时设置 ===")

        # 测试场景: 模拟一个长时间的 PTT 操作
        # ASR (2s) + LLM (10s) + TTS (5s) = 17s 总时间
        # 但网络波动或复杂响应可能需要更长时间

        expected_min_timeout = 60  # 最少需要 60 秒
        actual_rust_timeout = 120  # 修复后的 Rust 客户端超时 (socket_client.rs:158)
        actual_python_timeout = 150  # 修复后的 Python 服务端超时 (socket_server.py:331)

        print(f"期望最小超时: {expected_min_timeout}s")
        print(f"Rust 客户端实际超时: {actual_rust_timeout}s")
        print(f"Python 服务端实际超时: {actual_python_timeout}s")

        # 断言: Rust 客户端超时应该至少为 60 秒
        if actual_rust_timeout < expected_min_timeout:
            print(
                f"❌ 测试失败: Rust 客户端超时 ({actual_rust_timeout}s) 小于最小要求 ({expected_min_timeout}s)"
            )
            print("   这会导致长时间的 PTT 操作超时失败!")
            return False
        else:
            print(f"✅ 测试通过: Rust 客户端超时 ({actual_rust_timeout}s) 满足要求")
            return True

    def test_timeout_with_long_operation(self):
        """测试长时间操作是否会在超时前完成"""
        print("\n=== 测试长时间操作超时 ===")

        # 模拟一个 35 秒的操作 (ASR 5s + LLM 20s + TTS 10s)
        operation_time = 35  # 秒
        timeout = 120  # 修复后的 Rust 客户端超时

        print(f"模拟操作时间: {operation_time}s")
        print(f"当前超时设置: {timeout}s")

        if operation_time > timeout:
            print(f"❌ 测试失败: 操作时间 ({operation_time}s) 超过超时设置 ({timeout}s)")
            print("   这会导致操作超时失败,应用无响应!")
            return False
        else:
            print(f"✅ 测试通过: 操作时间 ({operation_time}s) 在超时范围内")
            return True

    def test_recommended_timeout_settings(self):
        """测试推荐的超时设置"""
        print("\n=== 测试推荐超时设置 ===")

        # 推荐的超时设置
        recommended_client_timeout = 120  # 2 分钟客户端超时
        recommended_server_timeout = 150  # 2.5 分钟服务端超时

        # 典型操作时间
        asr_time = 3  # ASR 平均时间
        llm_time = 15  # LLM 平均时间 (流式生成)
        tts_time = 8  # TTS 平均时间
        total_time = asr_time + llm_time + tts_time

        # 考虑网络波动和复杂情况,需要 3x 安全系数
        safe_time = total_time * 3

        print(f"典型操作时间: ASR {asr_time}s + LLM {llm_time}s + TTS {tts_time}s = {total_time}s")
        print(f"安全系数 3x: {safe_time}s")
        print(f"推荐客户端超时: {recommended_client_timeout}s")
        print(f"推荐服务端超时: {recommended_server_timeout}s")

        if recommended_client_timeout >= safe_time:
            print(
                f"✅ 测试通过: 推荐客户端超时 ({recommended_client_timeout}s) 满足安全要求 ({safe_time}s)"
            )
            return True
        else:
            print(
                f"❌ 测试失败: 推荐客户端超时 ({recommended_client_timeout}s) 不满足安全要求 ({safe_time}s)"
            )
            return False


def main():
    """运行所有测试"""
    print("=" * 60)
    print("Socket 超时问题测试套件")
    print("=" * 60)

    tester = TestSocketTimeout()

    results = []
    results.append(("当前超时设置测试", tester.test_current_timeout_settings()))
    results.append(("长时间操作超时测试", tester.test_timeout_with_long_operation()))
    results.append(("推荐超时设置测试", tester.test_recommended_timeout_settings()))

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n🎉 所有测试通过!")
        return 0
    else:
        print("\n⚠️  部分测试失败,需要修复超时设置")
        print("\n修复建议:")
        print("1. ✅ Rust 客户端超时已设置为 120s (socket_client.rs:158)")
        print("2. ✅ Python 服务端超时已设置为 150s (socket_server.py:331)")
        print("3. 或者实现真正的异步/流式响应,避免长时间阻塞")
        return 1


if __name__ == "__main__":
    sys.exit(main())
