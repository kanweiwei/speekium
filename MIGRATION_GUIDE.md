# Speekium → Tauri 迁移指南

## ✅ 原型创建完成

已成功创建 Tauri 原型，包含：
- ✅ 完整的 React + TypeScript 前端
- ✅ Mock API 模拟 PyTauri 调用
- ✅ Python 后端基础框架
- ✅ 完整的开发和构建文档
- ✅ 暗色主题 UI（与原 Speekium 一致）

## 📂 项目位置

```
/Users/kww/work/opensource/speekium/tauri-prototype/
```

## 🚀 快速启动

### 1. 查看项目
```bash
cd tauri-prototype
cat README.md
```

### 2. 启动开发服务器
```bash
npm run tauri dev
```

这将打开 Tauri 应用窗口，显示 Mock UI（不需要实际 Python 后端）。

### 3. 构建生产版本
```bash
npm run tauri build
```

## 📊 核心文件说明

### 前端文件
| 文件 | 说明 |
|------|------|
| `src/App.tsx` | 主应用组件（替代原 web/App.tsx）|
| `src/App.css` | 应用样式（暗色主题）|
| `src/useTauriAPI.ts` | Tauri API Hook（替代 web/hooks/usePywebview.ts）|

### 后端文件
| 文件 | 说明 |
|------|------|
| `backend.py` | Python 后端（PyTauri 命令）|
| `pyproject.toml` | Python 项目配置 |
| `.venv/` | Python 虚拟环境（uv 管理）|

### 配置文件
| 文件 | 说明 |
|------|------|
| `src-tauri/tauri.conf.json` | Tauri 配置（窗口大小1200x800）|
| `package.json` | Node.js 依赖 |
| `README.md` | 完整开发指南 |
| `PROTOTYPE_SUMMARY.md` | 原型创建总结 |

## 🔄 从 pywebview 迁移的关键步骤

### Step 1: 测试原型（今天）
```bash
cd tauri-prototype
npm run tauri dev
```

验证：
- [ ] 应用窗口正常打开
- [ ] UI 显示 Speekium 界面
- [ ] 点击录音按钮有状态变化
- [ ] 消息历史显示正常

### Step 2: Python 集成（2-3天）
**选项 A: 使用 PyTauri sidecar**（推荐）
```bash
# 参考 PyTauri 示例
https://github.com/pytauri/pytauri/tree/main/examples/tauri-app-wheel
```

**选项 B: 直接 Rust + Python HTTP API**（简单）
1. 在 Rust 中启动 Python 子进程
2. 通过 HTTP 调用 Python API
3. 保留现有 Python 代码（最小改动）

**选项 C: Rust 重写**（长期）
1. 将 Python 逻辑重写为 Rust
2. 使用 Rust crates for VAD/ASR/TTS
3. 最佳性能，但工作量大

### Step 3: 功能迁移（1-2周）
按优先级迁移：
1. **核心功能**（高优先级）
   - [ ] VAD 录音
   - [ ] ASR 语音识别
   - [ ] LLM 对话
   - [ ] TTS 语音合成

2. **系统集成**（中优先级）
   - [ ] 系统托盘（Tauri 插件）
   - [ ] 全局快捷键（Tauri 插件）
   - [ ] 窗口管理（多窗口、悬浮窗）

3. **UI 增强**（低优先级）
   - [ ] 设置面板
   - [ ] 主题切换
   - [ ] 动画和过渡

### Step 4: 测试和优化（3-5天）
- [ ] 跨平台测试（Windows, macOS, Linux）
- [ ] 性能测试（内存、CPU、包大小）
- [ ] 用户体验测试
- [ ] 打包和分发测试

## 📋 迁移检查清单

### 代码完整性
- [ ] 所有 pywebview API 已替换为 Tauri invoke
- [ ] React 组件已迁移
- [ ] Python 后端逻辑已集成
- [ ] 状态管理已实现

### 功能完整性
- [ ] 录音功能正常
- [ ] 语音识别正常
- [ ] 对话生成正常
- [ ] TTS 播放正常
- [ ] 配置保存/加载正常
- [ ] 历史记录正常

### 系统集成
- [ ] 托盘图标和菜单正常
- [ ] 全局快捷键正常
- [ ] 窗口显示/隐藏正常
- [ ] 自动启动正常

### 质量保证
- [ ] 无明显性能问题
- [ ] 内存占用合理（<100MB）
- [ ] 启动时间合理（<3秒）
- [ ] 无内存泄漏
- [ ] 错误处理完善

## 🎯 预期收益

### 性能提升
- 包大小：50-100MB → <10MB（**10倍提升**）
- 内存占用：~50MB → ~40-80MB
- 启动时间：<1秒 → ~1秒（持平）

### 用户体验提升
- 更好的调试工具（Rust 开发者工具）
- 完善的插件生态
- 更好的跨平台一致性
- 移动端支持潜力（Tauri 2.0）

### 开发体验提升
- 更好的热重载（Tauri 原生支持）
- 更完善的错误处理
- 更好的类型安全（Rust + TypeScript）
- 更丰富的生态系统

## ⚠️ 风险和挑战

### 技术风险
1. **PyTauri 学习曲线**
   - 解决方案：参考官方文档和示例

2. **Rust 编译时间**
   - 解决方案：使用开发模式（增量编译）

3. **Python 集成复杂度**
   - 解决方案：先使用 HTTP API 简化集成

### 业务风险
1. **迁移时间**
   - 估计：2-4周（取决于复杂度）

2. **功能回归**
   - 解决方案：完善的测试和验证

3. **用户适应**
   - 解决方案：保持 UI 一致性

## 📚 参考资源

### 官方文档
- [Tauri 2.0 文档](https://v2.tauri.app/)
- [PyTauri 文档](https://pytauri.github.io/pytauri/)
- [Tauri 插件](https://github.com/tauri-apps/plugins-workspace)

### 示例项目
- [PyTauri 示例](https://github.com/pytauri/pytauri/tree/main/examples)
- [Tauri Python sidecar](https://github.com/dieharders/example-tauri-v2-python-server-sidecar)

### 社区支持
- [Tauri Discord](https://discord.gg/tauri)（90k+ 成员）
- [PyTauri Discord](https://discord.gg/TaXhVp7Shw)
- [GitHub Issues](https://github.com/tauri-apps/tauri/issues)

## 🚧 开发工作流建议

### 分支策略
```bash
# 创建迁移分支
git checkout -b feature/tauri-migration

# 提交频繁的迭代
git commit -m "feat: add recording UI"
git commit -m "feat: integrate Python backend"
```

### 测试流程
1. 单元测试：Rust/Python 代码
2. 集成测试：Tauri + React
3. 手动测试：实际用户场景
4. 性能测试：内存、CPU、启动时间

### 发布流程
1. 构建所有平台
2. 签名和公证（macOS）
3. 创建 GitHub Release
4. 发布到包管理器（Homebrew, AUR, etc.）

## 📝 后续优化方向

### 短期（1-3个月）
- [ ] 完整 Python 集成
- [ ] 所有功能迁移完成
- [ ] 跨平台测试通过

### 中期（3-6个月）
- [ ] 移动端支持（iOS/Android）
- [ ] 性能优化
- [ ] UI/UX 增强

### 长期（6-12个月）
- [ ] 插件系统（第三方扩展）
- [ ] 云同步（可选）
- [ ] AI 能力增强

## 🎉 总结

Tauri 原型已成功创建，包含：
- ✅ 完整的前端 UI（React + TypeScript）
- ✅ Mock API 框架（可替换为真实 Python 后端）
- ✅ 完整的开发文档和指南
- ✅ 清晰的迁移路径和检查清单

**下一步行动**：
1. 运行 `npm run tauri dev` 测试原型
2. 研究最佳 Python 集成方案（PyTauri vs HTTP API）
3. 开始逐步迁移现有功能
4. 持续测试和优化

预计完成时间：**2-4周**（取决于复杂度和可用时间）

---

**创建日期**: 2026-01-08
**原型版本**: 0.1.0
**状态**: Phase 1 完成，待验证和集成
