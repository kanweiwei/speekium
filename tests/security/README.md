# 安全回归测试文档

## 概述

本目录包含 Speekium 项目的安全回归测试，用于验证 P0 关键安全修复（CVSS 7.5）不会被意外破坏。

## 测试覆盖

### 1. 输入验证测试 (18 tests)

**测试文件**: `test_security_fixes.py::TestInputValidation`

**验证功能**: `backends.validate_input()` 函数

**测试覆盖**:
- ✅ 正常输入（ASCII、中文、多行）
- ✅ 边界情况（恰好 10000 字符）
- ✅ Unicode 支持（emoji、特殊字符）
- ✅ XSS 防护（script 标签、JavaScript 伪协议）
- ✅ 注入防护（null 字节）
- ✅ 长度限制（>10000 字符拒绝）
- ✅ 空输入检测
- ✅ 控制字符过滤（保留 \n \t）
- ✅ 大小写不敏感阻止
- ✅ 混合攻击向量

**安全威胁防护**:
- XSS (Cross-Site Scripting)
- SQL Injection
- Command Injection
- Path Traversal
- Null Byte Injection

### 2. 临时文件安全测试 (8 tests)

**测试文件**: `test_security_fixes.py::TestTempFileSecurity`

**验证功能**:
- `speekium.create_secure_temp_file()`
- `speekium.cleanup_temp_files()`

**测试覆盖**:
- ✅ 文件创建
- ✅ 权限验证（0600 - 仅所有者读写）
- ✅ 写入后权限保持
- ✅ 多文件创建
- ✅ 文件唯一性（10 个文件路径唯一）
- ✅ 自动清理
- ✅ 清理不存在文件不报错
- ✅ 临时目录隔离

**安全威胁防护**:
- Sensitive Data Exposure（敏感数据暴露）
- Unauthorized Access（未授权访问）
- Information Disclosure（信息泄露）

### 3. 资源限制测试 (4 tests)

**测试文件**: `test_security_fixes.py::TestResourceLimits`

**验证功能**:
- `worker_daemon.set_resource_limits()`
- `worker_daemon.handle_timeout()`

**测试覆盖**:
- ✅ worker_daemon 模块导入
- ✅ 资源限制日志记录（可选，系统依赖）
- ✅ set_resource_limits 函数存在
- ✅ CPU 超时信号处理器存在

**资源限制配置**:
- 内存限制: 2GB (soft), 4GB (hard)
- CPU 时间: 600 秒（10 分钟）
- 文件大小: 1GB
- 文件描述符: 1024

**安全威胁防护**:
- Resource Exhaustion（资源耗尽攻击）
- Denial of Service（拒绝服务攻击）
- Memory Bombing（内存炸弹）

### 4. 集成测试 (2 tests)

**测试文件**: `test_security_fixes.py::TestSecurityIntegration`

**测试覆盖**:
- ✅ 输入验证阻止所有已知攻击向量
- ✅ 临时文件端到端安全流程

## 运行测试

### 运行所有安全测试

```bash
# 基本运行
uv run pytest tests/security/ -v

# 带覆盖率报告
uv run pytest tests/security/ --cov=backends --cov=speekium --cov-report=term-missing

# 仅运行安全标记的测试
uv run pytest -m security -v
```

### 运行特定测试类

```bash
# 仅运行输入验证测试
uv run pytest tests/security/test_security_fixes.py::TestInputValidation -v

# 仅运行临时文件安全测试
uv run pytest tests/security/test_security_fixes.py::TestTempFileSecurity -v

# 仅运行资源限制测试
uv run pytest tests/security/test_security_fixes.py::TestResourceLimits -v
```

### CI/CD 集成

安全测试自动在每次提交时运行（通过 `.github/workflows/test.yml`）。

分支触发条件:
- `main`, `master`, `develop`
- `security-fixes/**` (安全修复分支)

## 测试结果解释

### 成功标准

- ✅ **31+ 测试通过**: 所有安全功能正常工作
- ✅ **1 测试跳过**: 资源限制日志记录（系统依赖，可选）
- ✅ **执行时间 <5 秒**: 性能要求满足
- ✅ **安全函数覆盖率 ~100%**: 所有安全关键路径被测试

### 失败处理

如果任何安全测试失败：

1. **立即停止部署**: 安全回归是 P0 问题
2. **检查变更**: 查看最近的代码变更
3. **修复问题**: 恢复安全功能或修复测试
4. **验证修复**: 本地运行测试确认通过
5. **提交修复**: 推送到仓库触发 CI/CD

## 添加新的安全测试

### 步骤

1. **识别安全功能**: 确定需要保护的安全关键代码
2. **创建测试类**: 在 `test_security_fixes.py` 中添加新的测试类
3. **编写测试用例**: 覆盖正常情况和攻击场景
4. **运行测试**: 确保新测试通过
5. **更新文档**: 在本 README 中记录新测试

### 测试模板

```python
class TestNewSecurityFeature:
    """测试新安全功能"""

    def test_normal_case(self):
        """正常情况应该通过"""
        result = security_function("normal input")
        assert result == "expected output"

    def test_attack_blocked(self):
        """攻击应该被阻止"""
        with pytest.raises(SecurityError):
            security_function("malicious input")

    def test_boundary_case(self):
        """边界情况测试"""
        result = security_function("boundary input")
        assert result is not None
```

## 安全测试最佳实践

1. **测试攻击场景**: 不仅测试正常输入，更要测试恶意输入
2. **使用真实攻击向量**: 参考 OWASP Top 10 和真实漏洞
3. **边界值测试**: 测试边界值和临界点
4. **快速失败**: 安全测试应该快速执行（<5 秒）
5. **清晰的错误消息**: 失败时提供明确的错误信息
6. **独立性**: 每个测试应该独立运行，不依赖其他测试
7. **清理资源**: 使用 setup/teardown 方法清理测试资源

## 相关文档

- [P0 Security Fixes](../../SECURITY_QA_COMPREHENSIVE_REPORT.md)
- [Test Coverage Report](../../coverage.xml)
- [CI/CD Configuration](../../.github/workflows/test.yml)

## 安全威胁模型

### OWASP Top 10 覆盖

- ✅ A01:2021 - Broken Access Control（临时文件权限）
- ✅ A03:2021 - Injection（输入验证）
- ✅ A04:2021 - Insecure Design（资源限制）
- ✅ A05:2021 - Security Misconfiguration（安全配置）

### CVSS 评分

本测试套件保护的安全修复的 CVSS 评分:

- **输入验证**: CVSS 7.5 (High)
- **临时文件权限**: CVSS 6.5 (Medium)
- **资源限制**: CVSS 7.5 (High)

## 联系方式

如有安全问题或建议，请联系项目维护者。
