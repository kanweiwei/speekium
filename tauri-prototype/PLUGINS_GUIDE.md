# Tauri 插件配置指南

本文档说明如何在 Speekium Tauri 项目中配置和使用系统插件。

## 📋 支持的插件

### 1. 全局快捷键
**包名**: `@tauri-apps/plugin-global-shortcut`
**功能**: 注册全局快捷键（如 Cmd+Alt 录音）
**支持平台**: Windows, macOS, Linux

### 2. 系统托盘
**包名**: 内置于 `@tauri-apps/api`（无需额外安装）
**功能**: 创建系统托盘图标和菜单
**支持平台**: Windows, macOS, Linux

## 🔧 安装步骤

### 全局快捷键插件

```bash
cd tauri-prototype
npm install @tauri-apps/plugin-global-shortcut
```

### 系统托盘

系统托盘已内置在 Tauri 核心中，无需额外安装：
```bash
# 只需在 Rust 代码中启用 tray-icon 功能
# 已包含在 @tauri-apps/api 包中
```

## 📁 配置文件

### src-tauri/Cargo.toml

添加全局快捷键插件依赖：

```toml
[dependencies]
tauri = { version = "2", features = ["tray-icon"] }
tauri-plugin-global-shortcut = "2"
```

**重要**: 确保 `tauri` 依赖包含 `tray-icon` feature。

### src-tauri/tauri.conf.json

配置插件权限和功能：

```json
{
  "$schema": "https://schema.tauri.app/config/2",
  "productName": "Speerium",
  "version": "0.1.0",
  "identifier": "com.speekium.app",
  "build": {
    "beforeDevCommand": "npm run dev",
    "devUrl": "http://localhost:1420",
    "beforeBuildCommand": "npm run build",
    "frontendDist": "../dist"
  },
  "app": {
    "withGlobalTauri": true,
    "windows": [
      {
        "title": "Speerium",
        "width": 1200,
        "height": 800,
        "minWidth": 800,
        "minHeight": 600,
        "resizable": true
      }
    ],
    "security": {
      "csp": null
    }
  },
  "bundle": {
    "active": true,
    "targets": "all",
    "icon": [
      "icons/32x32.png",
      "icons/128x128.png",
      "icons/128x128@2x.png",
      "icons/icon.icns",
      "icons/icon.ico"
    ]
  },
  "plugins": {
    "global-shortcut": {
      "shortcuts": [
        {
          "id": "record-shortcut",
          "accelerator": "CmdOrCtrl+Alt",
          "description": "Start recording"
        }
      ]
    }
  }
}
```

## 💻 Rust 实现

### src-tauri/src/lib.rs

```rust
use tauri::Manager;
use tauri_plugin_global_shortcut::{Code, Modifiers, ShortcutState};

pub fn run() -> Result<(), Box<dyn std::error::Error>> {
    tauri::Builder::default()
        .setup(|app| {
            #[cfg(desktop)]
            {
                use tauri::Manager;
                use tauri_plugin_global_shortcut::{Code, Modifiers, ShortcutState};

                app.handle().plugin(
                    tauri_plugin_global_shortcut::Builder::new()
                        .with_shortcuts(["cmdorctrl+alt"])?
                        .with_handler(|app, shortcut, event| {
                            if event.state == ShortcutState::Pressed {
                                if shortcut.matches(Modifiers::COMMAND, Code::KeyA) {
                                    // Cmd/Ctrl + Alt 录音
                                    let _ = app.emit("start-recording", ());
                                }
                            }
                        })
                        .build(),
                )?;
            }

            // 系统托盘
            #[cfg(desktop)]
            {
                use tauri::tray::TrayIconBuilder;
                use tauri_plugin_tray::TrayIcon;

                let tray = TrayIconBuilder::new()
                    .icon(app.default_window_icon().unwrap().clone())
                    .menu_on_left_click(false) // 防止左键弹出菜单
                    .menu(|app| {
                        let show_window = app.window().show();
                        let quit = app.exit();
                        vec![show_window, quit]
                    })
                    .build(app)?;

                Ok(())
            }

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

## 🎨 JavaScript/TypeScript 集成

### src/useTauriAPI.ts

```typescript
import { listen } from '@tauri-apps/api/event';
import { GlobalShortcut } from '@tauri-apps/plugin-global-shortcut';
import { TrayIcon, defaultWindowIcon } from '@tauri-apps/api/tray';

export function useTauriAPI() {
  const [isRecording, setIsRecording] = useState(false);

  // 监听全局快捷键
  useEffect(() => {
    const unlisten = listen('start-recording', (event) => {
      console.log('Global shortcut triggered:', event.payload);
      handleStartRecording();
    });

    return () => {
      unlisten.then(fn => fn());
    };
  }, []);

  const handleStartRecording = async () => {
    setIsRecording(true);
    // 调用 Python 录音 API
    const result = await mockAPI.startRecording({ mode: 'push-to-talk', language: 'auto' });
    setIsRecording(false);
    return result;
  };

  return {
    isRecording,
    handleStartRecording,
  };
}
```

## 📱 从 pywebview 迁移对比

### 快捷键管理

| pywebview | Tauri (推荐) |
|-----------|------------------|
| pynput (Python 库) | Tauri plugin-global-shortcut |
| 需要单独线程 | Rust 原生集成 |
| 平台差异大 | 跨平台一致 |
| 事件循环问题 | 原生支持，无冲突 |

### 系统托盘

| pywebview | Tauri (推荐) |
|-----------|------------------|
| pystray (有 macOS 问题) | 内置 TrayIcon API |
| 需要手动管理事件循环 | 原生支持，自动管理 |
| 功能受限 | 完整功能 |

## ✅ 配置检查清单

- [ ] 已安装 `@tauri-apps/plugin-global-shortcut`
- [ ] Cargo.toml 添加 `tauri-plugin-global-shortcut` 依赖
- [ ] Cargo.toml 的 `tauri` 依赖包含 `tray-icon` feature
- [ ] lib.rs 注册全局快捷键插件
- [ ] lib.rs 创建系统托盘
- [ ] 前端监听 Tauri 事件
- [ ] 测试快捷键触发
- [ ] 测试托盘菜单功能

## 🚀 快速测试

1. **全局快捷键测试**:
   - 按下 Cmd/Ctrl + Alt
   - 验证录音功能触发
   - 检查是否有冲突

2. **系统托盘测试**:
   - 验证托盘图标显示
   - 测试右键菜单
   - 测试左键点击行为
   - 验证显示/隐藏窗口功能

3. **macOS 特别测试**:
   - 验证托盘和 pywebview 事件循环冲突已解决
   - 测试快捷键在后台是否工作

## 🐛 故障排除

### 快捷键不工作
```bash
# 检查配置
cat src-tauri/tauri.conf.json | grep shortcuts

# 检查 Rust 代码
cat src-tauri/src/lib.rs | grep plugin
```

### 托盘不显示
```bash
# 检查 tray-icon feature
grep "tray-icon" src-tauri/Cargo.toml

# 检查构建日志
npm run tauri build
```

### npm install 失败
```bash
# 尝试升级 npm
npm install -g npm@latest

# 或使用 pnpm/yarn
pnpm install @tauri-apps/plugin-global-shortcut
```

## 📚 参考资源

- [全局快捷键文档](https://v2.tauri.app/plugin/global-shortcut/)
- [系统托盘文档](https://v2.tauri.app/learn/system-tray/)
- [插件仓库](https://github.com/tauri-apps/plugins-workspace/tree/v2/plugins)
- [GitHub Issues](https://github.com/tauri-apps/tauri/issues)

---

**下一步**: 实现 Rust 代码和前端集成，然后测试完整功能。
