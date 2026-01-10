#!/usr/bin/env python3
"""
P0 安全修复测试脚本

测试内容：
1. 输入验证 - 长度限制、危险模式拒绝
2. 临时文件权限 - 0600 权限、自动清理
3. 资源限制 - 验证 worker_daemon.py 能正确导入
"""

import os
import sys


def test_input_validation():
    """测试输入验证功能"""
    print("\n" + "=" * 60)
    print("测试 1: 输入验证")
    print("=" * 60)

    from backends import validate_input

    # 测试 1.1: 正常输入
    try:
        result = validate_input("hello world")
        assert result == "hello world"
        print("✅ 1.1 正常输入通过")
    except Exception as e:
        print(f"❌ 1.1 正常输入失败: {e}")
        return False

    # 测试 1.2: 过长输入
    try:
        validate_input("a" * 10001)
        print("❌ 1.2 应该拒绝过长输入")
        return False
    except ValueError as e:
        if "too long" in str(e):
            print("✅ 1.2 正确拒绝过长输入")
        else:
            print(f"❌ 1.2 错误消息不正确: {e}")
            return False

    # 测试 1.3: 空输入
    try:
        validate_input("   ")
        print("❌ 1.3 应该拒绝空输入")
        return False
    except ValueError as e:
        if "empty" in str(e):
            print("✅ 1.3 正确拒绝空输入")
        else:
            print(f"❌ 1.3 错误消息不正确: {e}")
            return False

    # 测试 1.4: XSS 注入
    try:
        validate_input("<script>alert(1)</script>")
        print("❌ 1.4 应该拒绝 XSS 输入")
        return False
    except ValueError as e:
        if "blocked pattern" in str(e):
            print("✅ 1.4 正确拒绝 XSS 输入")
        else:
            print(f"❌ 1.4 错误消息不正确: {e}")
            return False

    # 测试 1.5: JavaScript URL 注入
    try:
        validate_input("javascript:alert(1)")
        print("❌ 1.5 应该拒绝 JavaScript URL")
        return False
    except ValueError as e:
        if "blocked pattern" in str(e):
            print("✅ 1.5 正确拒绝 JavaScript URL")
        else:
            print(f"❌ 1.5 错误消息不正确: {e}")
            return False

    # 测试 1.6: 空字节注入
    try:
        validate_input("test\x00injection")
        print("❌ 1.6 应该拒绝空字节注入")
        return False
    except ValueError as e:
        if "blocked pattern" in str(e):
            print("✅ 1.6 正确拒绝空字节注入")
        else:
            print(f"❌ 1.6 错误消息不正确: {e}")
            return False

    # 测试 1.7: 控制字符过滤
    try:
        result = validate_input("hello\x01world")
        if "\x01" not in result:
            print("✅ 1.7 正确过滤控制字符")
        else:
            print("❌ 1.7 未过滤控制字符")
            return False
    except Exception as e:
        print(f"❌ 1.7 控制字符过滤失败: {e}")
        return False

    return True


def test_temp_file_security():
    """测试临时文件安全"""
    print("\n" + "=" * 60)
    print("测试 2: 临时文件安全")
    print("=" * 60)

    from speekium import cleanup_temp_files, create_secure_temp_file

    # 测试 2.1: 文件创建
    tmp_file = create_secure_temp_file(suffix=".test")
    if not os.path.exists(tmp_file):
        print(f"❌ 2.1 文件创建失败: {tmp_file}")
        return False
    print(f"✅ 2.1 文件创建成功: {tmp_file}")

    # 测试 2.2: 文件权限
    file_stat = os.stat(tmp_file)
    actual_mode = file_stat.st_mode & 0o777

    if actual_mode == 0o600:
        print(f"✅ 2.2 文件权限正确: {oct(actual_mode)}")
    else:
        print(f"❌ 2.2 文件权限错误: {oct(actual_mode)} (期望: 0o600)")
        cleanup_temp_files()
        return False

    # 测试 2.3: 多个临时文件
    tmp_file2 = create_secure_temp_file(suffix=".test2")
    if not os.path.exists(tmp_file2):
        print("❌ 2.3 第二个文件创建失败")
        cleanup_temp_files()
        return False
    print("✅ 2.3 多个临时文件创建成功")

    # 测试 2.4: 自动清理
    cleanup_temp_files()
    if os.path.exists(tmp_file) or os.path.exists(tmp_file2):
        print("❌ 2.4 文件清理失败")
        return False
    print("✅ 2.4 所有临时文件已正确清理")

    return True


def test_resource_limits():
    """测试资源限制"""
    print("\n" + "=" * 60)
    print("测试 3: 资源限制")
    print("=" * 60)

    # 测试 3.1: worker_daemon 导入（这会触发资源限制设置）
    try:
        # 在子进程中测试，避免影响当前进程
        import subprocess

        result = subprocess.run(
            [sys.executable, "-c", "import worker_daemon; print('ok')"],
            capture_output=True,
            text=True,
            timeout=5,
        )

        if result.returncode == 0 and "ok" in result.stdout:
            print("✅ 3.1 worker_daemon 导入成功")

            # 检查是否有资源限制日志
            if "Resource limits set" in result.stderr:
                print("✅ 3.2 资源限制已设置")
            else:
                print("⚠️  3.2 未看到资源限制日志（可能在某些系统上不可用）")

            return True
        else:
            print("❌ 3.1 worker_daemon 导入失败:")
            print(f"   stdout: {result.stdout}")
            print(f"   stderr: {result.stderr}")
            return False

    except Exception as e:
        print(f"❌ 3.1 资源限制测试失败: {e}")
        return False


def main():
    """运行所有测试"""
    print("\n" + "🔒" * 30)
    print("P0 安全修复测试套件")
    print("🔒" * 30)

    results = []

    # 运行所有测试
    results.append(("输入验证", test_input_validation()))
    results.append(("临时文件安全", test_temp_file_security()))
    results.append(("资源限制", test_resource_limits()))

    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n🎉 所有安全测试通过！")
        return 0
    else:
        print("\n❌ 部分测试失败，请检查上面的错误信息")
        return 1


if __name__ == "__main__":
    sys.exit(main())
