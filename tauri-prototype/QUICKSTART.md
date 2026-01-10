# Speekium Tauri 迁移 - 快速开始

## 🚀 立即开始开发

### 1. 启动开发服务器

```bash
cd tauri-prototype
npm run tauri:dev
```

这将启动：
- ✅ Vite 开发服务器（前端热重载）
- ✅ Tauri 应用窗口
- ✅ Python 后端（如果已配置）

### 2. 理解项目结构

```
tauri-prototype/
├── src/                    # React 前端
│   ├── App.tsx              # 主应用
│   ├── App.css              # 样式
│   ├── useTauriAPI.ts       # Tauri API 集成
│   └── main.tsx             # 入口
├── src-tauri/             # Tauri 配置和 Rust 代码
│   ├── tauri.conf.json      # Tauri 配置
│   ├── capabilities/         # 权限配置
│   └── icons/              # 应用图标
├── src-python/             # Python 后端（将创建）
│   ├── backend_main.py      # PyTauri 入口
│   ├── audio_recorder.py    # 音频录制
│   ├── llm_backend.py      # LLM 后端
│   ├── tts_engine.py         # TTS 引擎
│   └── config_manager.py    # 配置管理
├── docs/                   # 文档
│   ├── 2026-01-08-audio-recorder-migration.md
│   ├── 2026-01-08-llm-backend-migration.md
│   ├── 2026-01-08-tts-engine-migration.md
│   ├── 2026-01-08-build-configuration.md
│   └── 2026-01-08-e2e-testing-guide.md
├── scripts/                # 构建脚本（将创建）
│   └── build_python.py       # Python 打包
└── pyproject.toml           # Python 项目配置
```

### 3. 前端快速测试

在浏览器中测试基本功能：

```typescript
// 1. 测试配置加载
import { loadConfig } from './useTauriAPI';

useEffect(() => {
  loadConfig().then(result => {
    if (result.success) {
      console.log('✅ 配置加载成功:', result.config);
    }
  });
}, []);

// 2. 测试录音（Mock 模式）
const { startRecording } = useTauriAPI();

const handleRecord = async () => {
  const result = await startRecording('continuous', 'auto');
  if (result.success) {
    console.log('✅ 录音成功:', result.text);
  }
};
```

### 4. Python 后端测试

测试后端命令：

```bash
# 进入 Python 环境
cd tauri-prototype
source .venv/bin/activate

# 测试配置管理
python -c "
import sys
sys.path.insert(0, '.')
from backend import *

async def test():
    config = await config_load(ConfigLoadRequest(), None)
    print('✅ 配置测试:', config.success)
    print('配置:', config.config)
"
```

### 5. 开发工具

推荐的 VS Code 扩展：
- ✅ **Tauri** - Tauri 官方插件
- ✅ **Python** - Python 扩展
- ✅ **ESLint** - 代码检查
- ✅ **Prettier** - 代码格式化
- ✅ **Tailwind CSS IntelliSense** - 样式自动完成

---

## 📚 学习资源

### 官方文档
- [Tauri 官方文档](https://v2.tauri.app/)
- [PyTauri 文档](https://pytauri.github.io/pytauri/)
- [React 文档](https://react.dev/)

### 项目文档
- [迁移指南](./docs/2026-01-08-migration-guide.md)
- [功能模块文档](./docs/2026-01-08-*)
- [测试指南](./docs/2026-01-08-e2e-testing-guide.md)

### 社区
- [Tauri Discord](https://discord.gg/tauri) - 90k+ 成员
- [PyTauri Discord](https://discord.gg/TaXhVp7Shw) - Python 集成支持

---

## 🎯 今日目标

### 基础目标（1-2 天）
1. ✅ 理解项目结构
2. ✅ 启动开发服务器
3. ✅ 前端基本功能测试
4. ✅ Python 后端基本测试
5. ✅ 阅读 API 文档

### 中期目标（1-2 周）
1. ⏳ 完成所有功能模块迁移
2. ⏳ 实现端到端测试
3. ⏳ 性能优化和调试
4. ⏳ 跨平台测试（Windows, macOS, Linux）

### 长期目标（1-2 月）
1. ⏳ 完整的 Tauri 2.0 功能集成
2. ⏳ 系统插件（托盘、快捷键）
3. ⏳ 自动更新和发布
4. ⏳ 移动端支持（iOS, Android）

---

## 🔧 开发工作流

### 功能开发流程

```
1. 创建功能分支
   git checkout -b feature/[feature-name]

2. 实现/迁移功能
   - 更新 Python 后端
   - 更新 React 前端
   - 添加类型定义
   - 编写测试

3. 自测
   - 运行 npm run tauri:dev
   - 手动测试功能
   - 查看控制台日志

4. 代码审查
   - 使用 LSP 检查类型错误
   - 运行 linter
   - 遵循代码规范

5. 提交 PR
   git add .
   git commit -m "feat: [description]"
   git push origin feature/[feature-name]
```

### 测试流程

```
1. 单元测试
   - 测试各个功能模块
   - 测试错误处理
   - 测试边界情况

2. 集成测试
   - 端到端流程测试
   - 性能测试
   - 压力测试

3. 跨平台测试
   - Windows 测试
   - macOS 测试
   - Linux 测试

4. 用户验收测试
   - Beta 测试
   - 收集用户反馈
   - 修复 bug
```

---

## 🚨 常见问题

### 启动问题

**问题**: npm run tauri:dev 失败
**解决**:
```bash
# 检查 Node.js 版本
node --version  # 应该 >= 20.19.0

# 检查 Rust
rustc --version

# 重新安装依赖
rm -rf node_modules
npm install

# 清理 Tauri 缓存
cd src-tauri
cargo clean
```

**问题**: Python 导入错误（pydantic, pytauri）
**解决**:
```bash
# 确保虚拟环境已激活
source .venv/bin/activate

# 验证依赖
python -c "import pydantic; print('pydantic version:', pydantic.__version__)"
python -c "import pytauri; print('pytauri imported')"

# 重新安装（如果需要）
pip install --upgrade pydantic pytauri
```

**问题**: Tauri 窗口不显示
**解决**:
```bash
# 检查 Vite 开发服务器是否运行
lsof -i :1420

# 检查端口冲突
netstat -an | grep 1420

# 检查防火墙
```

---

## 📝 开发规范

### Python 代码规范

```python
# 类型提示
from typing import List, Optional, Dict, Any

# 错误处理
import logging

logger = logging.getLogger(__name__)

# 函数文档
def my_function(param1: str, param2: int) -> str:
    """
    函数描述
    
    Args:
        param1: 参数1 说明
        param2: 参数2 说明
    
    Returns:
        返回值说明
    
    Example:
        >>> my_function("test", 123)
        'result'
    """
    try:
        # 实现逻辑
        pass
    except Exception as e:
        logger.error(f"Error in my_function: {e}")
        raise
```

### TypeScript 代码规范

```typescript
// 类型定义
interface Request {
  param1: string;
  param2: number;
}

interface Response {
  success: boolean;
  data?: any;
  error?: string;
}

// 函数定义
export async function myFunction(
  param1: Request
): Promise<Response> {
  /**
   * 函数描述
   */
  try {
    // 实现逻辑
    return { success: true, data: result };
  } catch (error) {
    console.error('Error:', error);
    return { success: false, error: String(error) };
  }
}
```

---

## 🎯 成功标准

### 功能完整性
- [ ] 所有计划的功能已实现
- [ ] 所有功能通过基本测试
- [ ] 错误处理完善
- [ ] 用户体验流畅

### 代码质量
- [ ] TypeScript 无类型错误
- [ ] Python 代码符合规范
- [ ] 代码审查通过
- [ ] 测试覆盖率 >80%

### 性能指标
- [ ] 响应时间 <3 秒
- [ ] 内存占用 <300MB
- [ ] CPU 占用 <60%
- [ ] 包体积 <50MB（Python sidecar）

### 文档完整性
- [ ] 所有 API 有文档说明
- [ ] 有快速开始指南
- [ ] 有完整的测试指南
- [ ] 有故障排除文档

---

## 💡 快速命令参考

### 开发命令
```bash
# 启动开发服务器
npm run tauri:dev

# 构建 Tauri 应用
npm run tauri:build

# 清理构建缓存
npm run clean

# 安装依赖
npm install

# 运行测试
npm test

# 格式化代码
npm run lint
npm run format
```

### Git 命令
```bash
# 查看状态
git status

# 添加文件
git add .

# 提交
git commit -m "feat: description"

# 推送到远程
git push origin main

# 查看日志
git log --oneline -10

# 创建分支
git checkout -b feature/[name]

# 合并分支
git merge feature/[name]
```

---

## 🚀 开始你的迁移之旅！

从现在开始：
1. 运行 `npm run tauri:dev` 启动开发服务器
2. 阅读 `docs/` 目录下的详细文档
3. 按照功能模块逐步实现
4. 参考测试指南确保质量

**记住**: Tauri 迁移是一个渐进过程，不必一次完成所有功能。从小处开始，逐步验证，持续迭代！

祝开发顺利！🎉
