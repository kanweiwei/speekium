# Speekium 架构重新设计方案

## 执行摘要

本文档提供了 Speekium 语音助手应用的完整架构重新设计。当前架构存在多个技术债务和设计问题，包括分散的状态管理、复杂的通信机制、缺乏类型安全等。新架构旨在创建一个可维护、可扩展、类型安全的语音助手应用。

**设计日期**: 2025-01-30
**版本**: 2.0
**状态**: 草案

---

## 目录

1. [当前架构问题分析](#1-当前架构问题分析)
2. [设计原则](#2-设计原则)
3. [新架构概览](#3-新架构概览)
4. [核心组件设计](#4-核心组件设计)
5. [数据流设计](#5-数据流设计)
6. [类型系统设计](#6-类型系统设计)
7. [状态管理设计](#7-状态管理设计)
8. [通信架构设计](#8-通信架构设计)
9. [实现路线图](#9-实现路线图)

---

## 1. 当前架构问题分析

### 1.1 状态管理混乱 🔴

**问题**: 13 个全局静态变量分散在 `state.rs` 中

```rust
// 当前: 分散的全局状态
DAEMON: Mutex<Option<PythonDaemon>>
DAEMON_READY: AtomicBool
PTT_STDERR: Mutex<Option<BufReader<ChildStderr>>>
STREAMING_IN_PROGRESS: AtomicBool
PTT_PROCESSING: AtomicBool
RECORDING_ABORTED: AtomicBool
RECORDING_MODE: Mutex<RecordingMode>
WORK_MODE: Mutex<WorkMode>
APP_STATUS: Mutex<AppStatus>
CURRENT_PTT_SHORTCUT: Mutex<Option<String>>
PTT_KEY_PRESSED: AtomicBool
AUDIO_RECORDER: Mutex<Option<AudioRecorder>>
RECORDING_MODE_CHANNEL: Mutex<Option<Sender<String>>>
```

**影响**:
- 难以追踪状态变化
- 缺乏状态变更历史
- 并发访问容易出现竞态条件
- 测试困难（需要模拟全局状态）

### 1.2 类型安全缺失 🟡

**问题**: 前后端类型定义不一致

```typescript
// Frontend (TypeScript)
interface WorkMode {
  value: 'conversation' | 'text-input';
}
```

```rust
// Backend (Rust)
pub enum WorkMode {
    Conversation,
    TextInput,
}
```

**影响**:
- 需要手动转换字符串
- 类型错误在运行时才发现
- API 变更难以同步

### 1.3 通信机制复杂 🟡

**问题**: 双 Socket 架构 + stdin/stdout 复杂

```
Frontend ←→ Rust Backend ←→ Python Daemon
                ↓                    ↓
            Tauri IPC          Socket IPC (双向)
                ↓                    ↓
            Event System       stdin/stdout
```

**影响**:
- 两套通信机制并存
- 事件传递路径不清晰
- 调试困难

### 1.4 配置管理分散 🟡

**问题**: 多个配置状态源

```
ConfigStore ← 已统一
WorkModeContext ← 订阅 ConfigStore
SettingsContext ← 订阅 ConfigStore
useTauriAPI ← config 已移除，但其他 API 仍混在一起
```

**影响**:
- API 职责不清
- 难以维护

---

## 2. 设计原则

### 2.1 单一职责原则 (SRP)
每个模块只负责一个明确的功能领域

### 2.2 依赖倒置原则 (DIP)
高层模块不应依赖低层模块，两者都应依赖抽象

### 2.3 开闭原则 (OCP)
软件实体应对扩展开放，对修改关闭

### 2.4 接口隔离原则 (ISP)
客户端不应依赖它不需要的接口

### 2.5 单一真理来源 (SSOT)
每个数据项只有一个权威来源

---

## 3. 新架构概览

### 3.1 架构分层

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              Presentation Layer                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐  │
│  │                         Frontend (React + TypeScript)                          │  │
│  │  ┌────────────────────────────────────────────────────────────────────┐   │  │
│  │  │                      UI Components                                   │   │  │
│  │  │  ┌──────────────┐ ┌──────────────┐ ┌────────────────┐   │   │  │
│  │  │  │ SettingsView │ │ ChatView      │ │   WorkModeView │   │   │  │
│  │  │  └──────────────┘ └──────────────┘ └────────────────┘   │   │ │
│  │  │  ┌──────────────┐ ┌──────────────┐ ┌────────────────┐   │   │  │
│  │  │  │ HistoryView  │ │ RecordingView │ │  ThemeProvider  │   │   │  │
│  │  │  └──────────────┘ └──────────────┘ └────────────────┘   │   │ │
│  │  └───────────────────────────────────────────────────────────────┘   │  │
│  │                                                                       │  │
│  │  ┌─────────────────────────────────────────────────────────────┐   │  │
│  │  │                    State Management Layer                      │   │  │
│  │  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │   │  │
│  │  │  │ ConfigStore │  │ WorkModeStore │  │ RecordingStore  │  │   │  │
│  │  │  │ (single)    │  │ (single)     │  │ (single)      │  │   │  │
│  │  │  └─────────────┘  └──────────────┘  └───────────────────┘  │   │  │
│  │  └─────────────────────────────────────────────────────────────┘   │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            Application Layer                                     │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                         Rust Backend (Tauri)                                 │  │
│  │  ┌────────────────┐  ┌──────────────┐  ┌──────────────────────┐  │   │  │
│  │  │ Command Layer │  │ State Layer   │  │   Event System     │  │   │  │
│  │  │                │  │              │  │                      │  │   │  │
│  │  │ ┌────────────┐ │  │ ┌────────┐ │  │ ┌──────────────┐  │   │ │ │
│  │  │ │ Recording  │ │  │ │ AppState│  │  │ │ EventBridge│  │   │ │ │
│  │  │ │ Commands   │ │  │ │        │ │  │ │              │  │   │ │ │
│  │  │ └────────────┘ │  │ └────────┘ │  │ └──────────────┘  │   │ │ │
│  │  └────────────────┘  └──────────────┘  └──────────────────────┘  │   │ │
│  │                                                                       │  │
│  │  ┌────────────────────────────────────────────────────────────────┐   │  │
│  │  │                      Socket Communication Layer                 │   │  │
│  │  │  ┌────────────────┐  ┌──────────────────────────────┐ │   │ │ │
│  │  │  │ Unix Socket     │  │  Event Bus (双向)             │ │   │ │ │
│  │  │  │ (Commands)     │  │                              │ │   │ │ │
│  │  │  │                │  │  ┌──────────┐  ┌──────────────┐ │ │   │ │ │
│  │  │  └────────────────┘  └──┤ Rust    │  │  │  │  │
│  │  │                                 │  └──┤───────┘  │   │ │ │ │
│  │  │  │                           └──────────┴──────────────┘ │ │ │ │ │
│  │  │  └────────────────────────────────────────────────────────────┘ │   │ │
│  │  └─────────────────────────────────────────────────────────────────────┘   │  │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              Domain Layer (Python)                                    │
│  ┌─────────────────────────────────────────────────────────────────────────┐  │
│  │                           Speekium Daemon                                   │  │
│  │  ┌────────────────┐  ┌──────────────┐  ┌──────────────────┐  │   │  │
│  │  │  Model Layer     │  │ Service Layer  │  │  │  │ │   │ │ │
│  │  │  │                │  │              │  │  │ │ │ │ │ │
│  │  │  │ ┌──────────┐  │  │ ┌────────┐  │  │  │ │ │   │ │ │ │ │ │
│  │  │  │ │   VAD     │  │  │ │LLM    │  │  │ │ │  │ │ │ │ │ │ │ │ │ │ │ │ │ │
│  │  │  │  │   ASR     │  │  │ │TTS    │  │  │ │ │  │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │
│  │  │  │ └──────────┘  │  │ └────────┘  │  │  │ │ │ │   │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │ │
│  │  │  └────────────────┘  │  └──────────────┘  └───────────────────┘  │   │ │
│  │  └─────────────────────────────────────────────────────────────────────┘   │  │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            Infrastructure Layer                                    │
│  ┌────────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Model Files    │  │ Config File  │  │  SQLite DB      │  │
│  │  (Local)         │  │ (JSON)      │  │ (History)        │  │
│  └────────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 核心设计改进

1. **统一状态管理器** - 替代 13 个全局静态变量
2. **事件驱动架构** - 统一的事件总线，清晰的数据流
3. **类型安全通信** - 共享类型定义，自动序列化/反序列化
4. **模块化服务层** - Python 端重构为清晰的服务层

---

## 4. 核心组件设计

### 4.1 状态管理器 (AppState)

**文件**: `src-tauri/src/state/app_state.rs`

```rust
/// 统一的应用状态管理器
///
/// 设计原则:
/// 1. 单一职责：只负责状态存储和访问
/// 2. 不可变性：状态只能通过状态变更方法修改
/// 3. 可观测性：状态变更发出事件通知
/// 4. 线程安全：使用 RwLock 保证并发安全
pub struct AppState {
    inner: RwLock<AppStateInner>,
    listeners: Arc<Mutex<Vec<EventListener>>>,
    event_bus: Arc<EventBus>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppStateInner {
    // Daemon 相关
    pub daemon_status: DaemonStatus,
    pub daemon_health: HealthStatus,

    // 录音相关
    pub recording_state: RecordingState,
    pub recording_mode: RecordingMode,

    // 处理相关
    pub processing_state: ProcessingState,
    pub app_status: AppStatus,

    // 工作模式
    pub work_mode: WorkMode,

    // 用户配置
    pub user_config: UserConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct RecordingState {
    pub is_recording: bool,
    pub is_processing: bool,
    pub audio_level_db: f32,
    pub duration_seconds: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ProcessingState {
    pub stage: ProcessingStage,
    pub progress: f32,  // 0.0 - 1.0
    pub message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ProcessingStage {
    Idle,
    Connecting,
    Recording,
    AsrProcessing,
    LlmProcessing,
    TtsProcessing,
    Playing,
}

impl AppState {
    /// 获取状态的只读副本
    pub fn get_state(&self) -> AppStateInner {
        self.inner.read().clone()
    }

    /// 更新状态（带事件发出）
    pub fn update_state<F, R>(&self, updater: F) -> R
    where
        F: FnOnce(&mut AppStateInner) -> R,
    {
        let mut state = self.inner.write();
        let result = updater(&mut state);
        drop(state); // 在锁失效前发出事件

        // 发出状态变更事件
        self.event_bus.publish(Event::StateChange {
            old: None,  // 可以优化为保存旧值
            new: state.clone(),
        });

        result
    }

    /// 订阅状态变更
    pub fn subscribe(&self, listener: EventListener) -> EventSubscription {
        self.listeners.lock().push(listener);
        EventSubscription::new(self.event_bus.subscribe(listener))
    }
}
```

### 4.2 事件总线系统

**文件**: `src-tauri/src/event/bus.rs`

```rust
/// 类型安全的事件总线
///
/// 设计原则:
/// 1. 类型安全：所有事件通过 Rust enum 定义
/// 2. 单向流动：事件 → 订阅者
/// 3. 异步分发：不阻塞发送者
pub struct EventBus {
    sender: broadcast::Sender<Event>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Event {
    // 状态事件
    StateChange { old: Option<AppStateInner>, new: AppStateInner },

    // 业务事件
    RecordingStarted { mode: RecordingMode },
    RecordingStopped { reason: StopReason },

    ProcessingStarted { stage: ProcessingStage },
    ProcessingProgress { stage: ProcessingStage, progress: f32 },
    ProcessingCompleted { stage: ProcessingStage, result: ProcessingResult },

    // 配置事件
    ConfigChanged { key: String, value: serde_json::Value },
    WorkModeChanged { old: WorkMode, new: WorkMode },

    // 守护进程事件
    DaemonStatusChanged { status: DaemonStatus },
    ModelProgress { model: ModelType, stage: ProgressStage, progress: f32 },
}

#[derive(Debug, Clone)]
pub struct EventSubscription {
    _unsubscribe: broadcast::Receiver<Event>,
}
```

### 4.3 类型共享系统

**文件**: `shared-types/src/lib.rs`

```rust
/// 共享类型定义库
/// 编译为 WebAssembly (前端) 和 rlib (Rust 后端)
///
/// 优势:
/// 1. 单一真理来源：类型定义在一处
/// 2. 自动同步：前后端类型始终一致
/// 3. 编译时检查：类型错误在构建时发现
```

```rust
// shared-types/src/lib.rs

use serde::{Deserialize, Serialize};

/// 录音模式
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum RecordingMode {
    #[serde(rename = "push-to-talk")]
    PushToTalk,
    #[serde(rename = "continuous")]
    Continuous,
}

/// 工作模式
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum WorkMode {
    #[serde(rename = "conversation")]
    Conversation,
    #[serde(rename = "text-input")]
    TextInput,
}

/// 应用状态
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum AppStatus {
    #[serde(rename = "idle")]
    Idle,
    #[serde(rename = "listening")]
    Listening,
    #[serde(rename = "recording")]
    Recording,
    #[serde(rename = "asr")]
    AsrProcessing,
    #[serde(rename = "llm")]
    LlmProcessing,
    #[serde(rename = "tts")]
    TtsProcessing,
    #[serde(rename = "playing")]
    Playing,
}

/// 用户配置（仅包含需要跨端共享的部分）
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserConfig {
    pub work_mode: WorkMode,
    pub recording_mode: RecordingMode,
    pub language: String,
    pub input_language: String,
    pub output_language: String,
}
```

---

## 5. 数据流设计

### 5.1 录音流程

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  React UI   │     │ Rust Backend │     │ Python Daemon │
│             │     │              │     │              │
│ 用户点击录音  │────→│ record_audio()│────→│ handle_record │
└─────────────┘     └──────────────┘     └──────────────┘
                            │
                            ▼
                    ┌──────────────────┐
                    │   AppState       │
                    │ - 更新状态      │
                    │ - 发出事件      │
                    └──────────────────┘
                            │
                            ▼
                    前端订阅更新 UI
```

### 5.2 配置更新流程

```
┌─────────────┐     ┌──────────────┐
│  React UI   │     │ ConfigStore  │
│             │────→│              │
│ 用户修改配置 │     │              │
└─────────────┘     │ - 更新配置    │
                    │ - 防抖保存      │
                    └──────────────┘
                            │
                            ▼ (Tauri Command)
                    ┌──────────────┐
                    │ Rust Backend │
                    │ - 更新 AppState│
                    │ - 发出事件      │
                    └──────────────┘
                            │
                            ▼ (Socket)
                    ┌──────────────┐
                    │ Python Daemon │
                    │ - 读取配置文件 │
                    └──────────────┘
```

---

## 6. 类型系统设计

### 6.1 共享类型库结构

```
shared-types/
├── src/
│   ├── lib.rs           # 主类型定义
│   ├── models.rs        # 数据模型
│   ├── events.rs        # 事件定义
│   └── errors.rs        # 错误定义
├── Cargo.toml            # Rust 库配置
├── package.json          # WASM/JS 配置
└── README.md
```

### 6.2 类型同步机制

```
┌─────────────────┐    编译     ┌─────────────────┐
│  shared-types     │────────────→│  frontend       │
│  (Rust source)    │             │  (TypeScript)   │
└─────────────────┘             └─────────────────┘
        │                               │
        │       ┌───────────────┐  │
        └───────│  typeshare-cli  │──┘
                │  (代码生成工具)  │
                └───────────────────┘
```

---

## 7. 状态管理设计

### 7.1 AppState 架构

```rust
pub struct AppState {
    // 核心状态
    inner: RwLock<AppStateInner>,

    // 事件系统
    event_bus: Arc<EventBus>,

    // 历史记录（用于调试和回放）
    history: Arc<Mutex<VecDeque<StateSnapshot>>>,
}

pub struct StateSnapshot {
    timestamp: i64,
    state: AppStateInner,
    source: StateChangeSource,
}
```

### 7.2 状态变更 API

```rust
impl AppState {
    /// 获取状态快照
    pub fn snapshot(&self) -> StateSnapshot {
        StateSnapshot {
            timestamp: Utc::now().timestamp(),
            state: self.get_state(),
            source: StateChangeSource::System,
        }
    }

    /// 更新录音状态
    pub fn update_recording<F>(&self, updater: F) -> Result<(), StateError>
    where
        F: FnOnce(&mut RecordingState) -> (),
    {
        self.update_state(|state| {
            updater(&mut state.recording_state);
        })
    }

    /// 更新工作模式（带验证）
    pub fn set_work_mode(&self, mode: WorkMode) -> Result<(), StateError> {
        self.update_state(|state| {
            state.work_mode = mode;
        })
    }

    /// 获取不可变引用
    pub fn read_state<F, R>(&self, reader: F) -> R
    where
        F: FnOnce(&AppStateInner) -> R,
    {
        reader(self.inner.read().deref())
    }
}
```

---

## 8. 通信架构设计

### 8.1 统一事件系统

**目标**: 替代当前的 Tauri Events + Socket 通知 混合架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Unified Event System                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Frontend    │  │  Rust Backend │  │ Python Daemon │  │
│  │                │  │              │  │              │  │
│  │  subscribe()    │  │  emit()      │  │  emit()      │  │
│  │                │  │              │  │              │  │
│  └──────────────┘  └──────┬───────┘  └──────┬───────┘  │
│                              │                       │           │
│                              ▼                       ▼           │
│                     ┌─────────────────────────────────────────┐         │
│                     │         Event Bus (单向流)               │         │
│                     │  ┌────────────────┐  ┌──────────┐ │         │
│                     │  │   State Events  │  │  UI Events │ │         │
│                     │  │                │  │           │ │         │
│                     │  └────────────────┘  └──────────┘ │         │
│                     └─────────────────────────────────────────────┘         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 8.2 命令路由层

**文件**: `src-tauri/src/commands/router.rs`

```rust
/// 统一的命令路由器
///
/// 优势:
/// 1. 集中处理所有命令
/// 2. 统一错误处理
/// 3. 自动状态更新
/// 4. 权限检查
pub struct CommandRouter {
    state: Arc<AppState>,
    daemon_client: Arc<DaemonClient>,
}

impl CommandRouter {
    pub async fn route_command(
        &self,
        command: Command,
    ) -> Result<CommandResult, CommandError> {
        match command {
            Command::Record(args) => self.handle_record(args).await,
            Command::Chat(args) => self.handle_chat(args).await,
            Command::SaveConfig(config) => self.handle_save_config(config).await,
            Command::GetConfig => self.handle_get_config().await,
            // ... 其他命令
        }
    }
}
```

---

## 9. 实现路线图

### Phase 1: 基础设施 (Week 1-2)

**目标**: 建立类型安全和事件系统

1. **创建 shared-types 库**
   - 定义核心类型
   - 设置 WASM 编译
   - 集成到前端和后端

2. **实现 EventBus**
   - 定义事件类型
   - 实现发布/订阅机制
   - 添加事件日志

3. **实现 AppState**
   - 替换全局静态变量
   - 添加状态快照功能
   - 迁移现有代码使用新状态

### Phase 2: 服务层重构 (Week 2-3)

**目标**: 重构 Python 端为服务层

1. **创建服务抽象**
   ```python
   # speekium/services/
   ├── __init__.py
   ├── recording_service.py
   ├── llm_service.py
   ├── tts_service.py
   └── config_service.py
   ```

2. **依赖注入容器**
   ```python
   class ServiceContainer:
       def __init__(self):
           self.config_service = ConfigService()
           self.recording_service = RecordingService(self.config_service)
           # ...
   ```

3. **重构 VoiceAssistant**
   - 使用服务层而不是直接操作
   - 简化 VoiceAssistant 职责

### Phase 3: 前端重构 (Week 3-4)

**目标**: 使用共享类型和事件系统

1. **集成 shared-types**
   - 替换手动类型转换
   - 使用自动生成的类型

2. **使用事件系统**
   - 订阅 AppState 事件
   - 移除轮询逻辑

3. **重构组件**
   - 使用事件驱动更新
   - 简化状态逻辑

### Phase 4: Rust 后端重构 (Week 4-5)

**目标**: 统一后端架构

1. **实现 CommandRouter**
   - 集中所有命令处理
   - 统一错误处理
   - 自动状态更新

2. **重构全局状态**
   - 使用 AppState
   - 移除直接访问全局变量的代码

3. **更新通信层**
   - 简化 Socket 通信
   - 统一错误处理

### Phase 5: 测试和文档 (Week 5-6)

**目标**: 确保质量和可维护性

1. **单元测试**
   - AppState 测试
   - EventBus 测试
   - Service 层测试

2. **集成测试**
   - 端到端流程测试
   - Socket 通信测试

3. **文档**
   - 架构文档
   - API 文档
   - 开发指南

---

## 10. 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 破坏现有功能 | 高 | 保留旧代码，渐进迁移 |
| 引入新 bug | 中 | 完整的测试覆盖 |
| 性能影响 | 中 | 基准测试，性能监控 |
| 向后兼容 | 低 | 版本化 API，渐进式迁移 |

---

## 11. 成功指标

| 指标 | 当前值 | 目标值 |
|------|--------|--------|
| 全局静态变量 | 13 个 | 0 个 |
| 类型错误 | 0 | 0 |
| 配置重复保存 | 2 次 | 1 次 |
| 事件系统 | 2 套 | 1 套 |
| 服务层抽象 | 无 | 完整 |

---

## 12. 技术栈选型

### 12.1 前端
- **框架**: React 18 + TypeScript 5.6
- **构建**: Vite
- **状态管理**: Zustand 或 Recoil (替代当前 ConfigStore)
- **样式**: TailwindCSS + shadcn/ui
- **类型**: shared-types (WASM)

### 12.2 后端
- **语言**: Rust 1.80+
- **框架**: Tauri 2.x
- **异步**: tokio
- **序列化**: serde
- **类型**: shared-types (native)

### 12.3 Python
- **版本**: 3.10+
- **异步**: asyncio
- **类型**: pyright + mypy
- **测试**: pytest

---

## 13. 附录

### 13.1 迁移兼容性保证

1. **旧 API 标记为 deprecated**
2. **添加版本检查**
3. **提供迁移指南**

### 13.2 性能优化建议

1. **事件批量处理**: 减少事件频率
2. **状态缓存**: 减少 RwLock 争用
3. **惰性初始化**: 延迟加载非关键组件

### 13.3 测试策略

1. **单元测试**: 每个组件独立测试
2. **集成测试**: 组件间交互测试
3. **端到端测试**: 用户场景测试
4. **性能测试**: 压力测试和基准测试

---

**文档版本**: 1.0
**最后更新**: 2025-01-30
**作者**: Claude Code Architecture Analysis
