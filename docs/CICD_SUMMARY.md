# CI/CD 实现总结

## ✅ 已完成的工作

### 1. GitHub Actions 工作流配置

**文件**: `.github/workflows/build.yml`

**功能**:
- ✅ 支持 macOS 和 Windows 并行构建
- ✅ 自动构建未签名版本（每次 push 到 main）
- ✅ 自动构建签名版本（tag 触发）
- ✅ macOS 公证集成
- ✅ 自动创建 GitHub Release
- ✅ 构建产物上传为 Artifacts

### 2. Tauri 配置更新

**文件**: `src-tauri/tauri.conf.json`

**新增配置**:
- 应用元信息（名称、描述、分类）
- macOS 特定配置（最低系统版本、签名身份）
- Windows 特定配置（摘要算法、时间戳服务器）

### 3. 完整文档系统

| 文档 | 大小 | 用途 |
|------|------|------|
| `docs/CICD_QUICKSTART.md` | 5.8KB | 快速入门指南 |
| `docs/CICD_SETUP.md` | 7.6KB | 详细设置指南 |
| `docs/CICD_ARCHITECTURE.md` | 16KB | 架构和技术细节 |

## 🔐 需要的环境变量

### 必需的 GitHub Secrets

| Secret 名称 | 用途 | 获取方式 |
|------------|------|----------|
| **GH_TOKEN** | GitHub Release 创建 | GitHub 自动提供 |
| **CSC_LINK** | 代码签名证书（Base64） | 从 Keychain 导出 .p12 文件 |
| **CSC_KEY_PASSWORD** | 证书密码 | 导出证书时设置的密码 |
| **APPLE_ID** | Apple ID 邮箱 | 你的 Apple 账号邮箱 |
| **APPLE_APP_SPECIFIC_PASSWORD** | Apple 专用密码 | appleid.apple.com 生成 |
| **APPLE_TEAM_ID** | Apple 开发团队 ID | developer.apple.com 查看 |

### 可选的 GitHub Secrets（仅 Windows）

| Secret 名称 | 用途 | 获取方式 |
|------------|------|----------|
| **CSC_LINK** | Windows 代码签名证书 | 从 CA 购买并导出 .pfx 文件 |
| **CSC_KEY_PASSWORD** | 证书密码 | 导出证书时设置的密码 |

## 🎯 工作流触发条件

### 1. 未签名构建（每次 push）
```bash
git push origin main
```
**结果**: 构建未签名的 macOS 和 Windows 应用

### 2. 签名构建（版本发布）
```bash
git tag v1.0.0
git push origin v1.0.0
```
**结果**:
- 构建签名应用
- macOS 自动公证
- 创建 GitHub Release
- 上传安装包

### 3. 手动触发
GitHub → Actions → Build and Release → Run workflow

## 📦 构建产物

### macOS Universal Binary
- **格式**: `.dmg` (磁盘镜像)
- **架构**: Universal (Intel + Apple Silicon)
- **大小**: ~150 MB
- **签名**: Developer ID Application
- **公证**: 自动完成

### Windows x86_64
- **格式**: `.msi` (Windows Installer)
- **架构**: x86_64 (64-bit)
- **大小**: ~120 MB
- **签名**: Authenticode
- **时间戳**: 自动添加

## 🚀 下一步操作

### Step 1: 添加 GitHub Secrets

1. 进入仓库设置页面
   ```
   https://github.com/你的用户名/speekium/settings/secrets/actions
   ```

2. 点击 "New repository secret"

3. 逐个添加以下 secrets（从表格中复制）

### Step 2: 测试未签名构建

```bash
# 创建测试提交
echo "test" >> test.txt
git add test.txt
git commit -m "test: trigger CI/CD"
git push origin main
```

4. 在 GitHub Actions 页面查看构建进度

### Step 3: 测试签名构建

```bash
# 创建测试标签
git tag v0.1.0-test
git push origin v0.1.0-test
```

### Step 4: 正式发布

```bash
# 创建正式版本标签
git tag v1.0.0
git push origin v1.0.0
```

## 📋 证书获取指南

### macOS 证书

1. **创建证书**
   ```bash
   # 打开 Xcode
   open -a Xcode

   # Xcode → Settings → Accounts → Manage Certificates
   # 点击 + → Developer ID Application
   ```

2. **导出证书**
   ```bash
   # 打开钥匙串访问
   open /Applications/Utilities/Keychain\ Access.app

   # 找到 "Developer ID Application" 证书
   # 右键 → 导出 → 保存为 .p12 文件
   # 设置密码（记住这个密码！）
   ```

3. **转换为 Base64**
   ```bash
   # macOS
   base64 -i certificate.p12 | pbcopy

   # 或 Linux
   base64 -w 0 certificate.p12
   ```

4. **添加到 GitHub Secrets**
   - Secret 名称: `CSC_LINK`
   - Secret 值: 粘贴 Base64 字符串

### Apple ID 信息

1. **Apple ID**: 你的 Apple 账号邮箱
   ```
   添加为 secret: APPLE_ID
   ```

2. **App-Specific Password**:
   - 访问 https://appleid.apple.com
   - 登录 → 安全 → 生成密码
   - 标签: "Speerium CI/CD"
   - 复制生成的密码（格式: `abcd-efgh-ijkl-mnop`）
   ```
   添加为 secret: APPLE_APP_SPECIFIC_PASSWORD
   ```

3. **Team ID**:
   - 访问 https://developer.apple.com/account
   - 在 "Membership Details" 中找到 "Team ID"
   - 格式: 10 位字符（如 `ABCD123456`）
   ```
   添加为 secret: APPLE_TEAM_ID
   ```

## ⚠️ 重要注意事项

### 安全方面
1. ✅ 永远不要将证书提交到 Git
2. ✅ 使用强密码保护证书
3. ✅ 证书每年到期，需要更新
4. ✅ 定期检查 GitHub Secrets 访问权限

### 成本方面
- **Apple Developer Program**: $99/年
- **Windows 代码签名证书**: $100-500/年（可选）
- **GitHub Actions**: 免费账户每月 2000 分钟

### 维护方面
- 证书到期前 30 天更新
- 定期测试 CI/CD 流程
- 监控构建失败情况
- 更新文档以反映变更

## 📚 文档索引

1. **快速入门**: `docs/CICD_QUICKSTART.md`
   - 快速参考指南
   - 最常用操作

2. **详细设置**: `docs/CICD_SETUP.md`
   - 完整的设置步骤
   - 故障排除
   - 常见问题解答

3. **架构文档**: `docs/CICD_ARCHITECTURE.md`
   - 技术架构详解
   - 性能指标
   - 定制化选项

## 🎉 总结

所有 CI/CD 配置已完成！你现在可以：

✅ 自动构建 macOS 和 Windows 应用
✅ 自动签名和公证 macOS 应用
✅ 自动创建 GitHub Releases
✅ 并行构建，提高效率
✅ 完整的文档支持

**下一步**: 添加 GitHub Secrets，然后推送代码测试！
