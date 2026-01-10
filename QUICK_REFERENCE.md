# Speekium 快速参考指南

**最后更新**: 2026-01-09

---

## 🚀 快速开始

### 1. 启动开发环境

```bash
# 自动启动所有服务
./start-dev.sh

# 访问测试页面
open http://localhost:8080/test-api.html
```

### 2. 停止开发环境

```bash
# 停止所有服务
./stop-dev.sh

# 停止并清理日志
./stop-dev.sh --clean
```

---

## 📝 手动操作

### 启动后端服务器

```bash
python3 backend_server.py

# 后台运行
python3 backend_server.py > /tmp/backend.log 2>&1 &

# 查看日志
tail -f /tmp/backend.log
```

### 启动 Ollama（如果未运行）

```bash
# 启动 Ollama 服务
ollama serve

# 拉取模型（如果需要）
ollama pull qwen2.5:1.5b
```

### 测试 API 端点

```bash
# 健康检查
curl http://localhost:8008/health

# 获取配置
curl http://localhost:8008/api/config | python3 -m json.tool

# 测试聊天
curl -X POST http://localhost:8008/api/chat \
  -H "Content-Type: application/json" \
  -d '{"text": "你好"}' | python3 -m json.tool
```

---

## 🔧 Tauri 开发（需要 Node.js 20.19+）

### 升级 Node.js

```bash
# 使用 nvm（推荐）
nvm install 22.12.0
nvm use 22.12.0

# 验证版本
node --version
```

### 运行 Tauri 开发模式

```bash
cd tauri-prototype
npm run tauri dev
```

### 构建 Tauri 应用

```bash
cd tauri-prototype
npm run tauri build
```

---

## 📂 重要文件位置

### 配置文件
```
config.json                    # 运行时配置
pyproject.toml                 # Python 项目配置
tauri-prototype/package.json   # Node 依赖
tauri-prototype/src-tauri/tauri.conf.json  # Tauri 配置
```

### 核心代码
```
speekium.py                    # 核心引擎（828 行）
backends.py                    # LLM 后端（279 行）
backend_server.py              # HTTP 服务器
tauri-prototype/src/App.tsx    # 主应用
tauri-prototype/src/useTauriAPI.ts  # API Hook
```

### 文档
```
README.md                      # 项目介绍
MIGRATION_GUIDE.md             # 迁移指南
MIGRATION_STATUS.md            # 迁移状态
INTEGRATION_TEST_RESULTS.md    # 测试报告
DEVELOPMENT.md                 # 开发指南
```

### 脚本
```
start-dev.sh                   # 启动开发环境
stop-dev.sh                    # 停止开发环境
dev.sh                         # 旧版开发脚本
run.sh                         # 旧版运行脚本
```

---

## 🐛 故障排除

### 后端无法启动

**问题**: `Address already in use: 8008`

**解决**:
```bash
# 找到占用端口的进程
lsof -i :8008

# 杀死进程
kill -9 <PID>

# 或使用脚本
./stop-dev.sh
```

---

### Ollama 未运行

**问题**: `Connection refused: localhost:11434`

**解决**:
```bash
# 启动 Ollama
ollama serve

# 验证
curl http://localhost:11434/api/tags
```

---

### Node.js 版本过低

**问题**: `Vite requires Node.js version 20.19+`

**解决**:
```bash
# 使用 nvm
nvm install 22.12.0
nvm use 22.12.0

# 或下载最新版本
open https://nodejs.org/
```

---

### 麦克风权限

**问题**: `NotAllowedError: Permission denied`

**解决**:
```bash
# macOS: 系统偏好设置 → 安全性与隐私 → 隐私 → 麦克风
# 确保浏览器/Tauri 应用有麦克风权限
```

---

## 📊 端口使用

| 端口 | 服务 | 说明 |
|------|------|------|
| 8008 | Python 后端 | HTTP API 服务器 |
| 8080 | 测试服务器 | 静态文件服务 |
| 1420 | Vite Dev | 前端开发服务器 |
| 11434 | Ollama | LLM 推理服务 |

---

## 🔍 常用命令

### 查看运行状态

```bash
# 查看后端进程
ps aux | grep backend_server

# 查看端口占用
lsof -i :8008
lsof -i :8080
lsof -i :11434

# 查看日志
tail -f /tmp/speekium-backend.log
tail -f /tmp/speekium-web.log
```

### 清理环境

```bash
# 停止所有服务
./stop-dev.sh --clean

# 清理 Python 缓存
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

# 清理 Node 模块
cd tauri-prototype
rm -rf node_modules package-lock.json
npm install
```

---

## 📚 学习资源

### 官方文档
- [Tauri 官方文档](https://v2.tauri.app/)
- [React 文档](https://react.dev/)
- [TypeScript 手册](https://www.typescriptlang.org/docs/)
- [Vite 文档](https://vitejs.dev/)
- [Ollama 文档](https://ollama.ai/docs)

### 项目文档
- [MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md) - 详细迁移步骤
- [DEVELOPMENT.md](./DEVELOPMENT.md) - 开发环境设置
- [tauri-prototype/PLUGINS_GUIDE.md](./tauri-prototype/PLUGINS_GUIDE.md) - Tauri 插件使用

---

## 💡 提示和技巧

### 开发效率

1. **使用脚本**: 优先使用 `start-dev.sh` / `stop-dev.sh`
2. **查看日志**: 遇到问题先查看日志文件
3. **测试页面**: 使用 `test-api.html` 快速测试 API
4. **热重载**: Vite 支持热重载，修改代码后自动刷新

### 调试技巧

1. **Chrome DevTools**: 在浏览器中按 F12 打开开发者工具
2. **Network 标签**: 查看 API 请求和响应
3. **Console 标签**: 查看 JavaScript 错误和日志
4. **Python 日志**: 在后端代码中使用 `print()` 调试

### 性能优化

1. **模型预加载**: 首次使用会下载模型，耗时较长
2. **Ollama 缓存**: Ollama 会缓存推理结果
3. **HTTP 缓存**: 浏览器会缓存静态资源

---

## 🎯 下一步

1. **升级 Node.js** 到 20.19+ 或 22.12+
2. **测试 Tauri dev** 模式
3. **验证语音功能**（录音、ASR、TTS）
4. **集成系统托盘**
5. **添加全局快捷键**

---

## 📞 获取帮助

- **文档**: 查看项目 `docs/` 目录
- **Issues**: GitHub Issues 页面
- **日志**: 检查 `/tmp/speekium-*.log` 文件

---

**快速上手**: `./start-dev.sh` → 打开浏览器 → 测试对话功能
