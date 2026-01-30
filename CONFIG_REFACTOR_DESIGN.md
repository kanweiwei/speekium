# 配置管理重构设计方案

## 当前问题分析

### 问题 1: 多个独立的状态源 🔴

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────┐
│ WorkModeContext │     │ SettingsContext │     │ useTauriAPI │
│                 │     │                  │     │             │
│ config (state)   │     │ config (state)   │     │ config (state)│
│ ├─ load_config()  │     │ ├─ load_config()  │     │ ├─ load_config()│
│ └─ save_config()  │     │ └─ save_config()  │     │ └─ save_config()│
└─────────────────┘     └──────────────────┘     └─────────────┘
        │                         │                         │
        └─────────────────────┴─────────────────────────┘
                                  │
                         ┌───────────────────────┐
                         │  Rust Backend          │
                         │  ├─ load_config()     │
                         │  └─ save_config()     │
                         └───────────────────────┘
                                  │
                         ┌───────────────────────┐
                         │  Python               │
                         │  ├─ handle_config()    │
                         │  └─ handle_save_config()│
                         └───────────────────────┘
                                  │
                         ┌───────────────────────┐
                         │  config.json          │
                         └───────────────────────┘
```

**问题**：
- 每个组件都独立维护 config 状态
- 没有协调机制，可能导致竞态条件
- 配置变更需要手动同步到多个地方

### 问题 2: WorkModeContext 的重复保存 🔴

```typescript
// WorkModeContext.tsx 第 87-101 行
if (currentMode !== lastKnownMode) {
  // ...
  await invoke('save_config', { config: updatedConfig });  // ← 第1次保存
}

// WorkModeContext.tsx 第 142-166 行 (setWorkMode)
const result = await invoke('load_config');
// ...
const saveResult = await invoke('save_config', { config: updatedConfig }); // ← 第2次保存!
```

**问题**：同一个模式变更会保存两次！

### 问题 3: StrictMode 导致的双重初始化 🟡

```
StrictMode 挂载:
  第1次挂载 → useEffect → syncFromConfig() → save_config
  第2次挂载 → useEffect → syncFromConfig() → save_config (重复!)
```

### 问题 4: 轮询导致的无效检查 🟡

```typescript
// WorkModeContext 每 500ms 轮询
setInterval(syncFromConfig, 500);

// syncFromConfig 中
if (currentMode !== lastKnownMode) {
  // 保存配置
}
```

即使模式没有变化，每 500ms 也会执行一次 `get_work_mode()` 调用。

---

## 重构设计方案

### 目标

1. **单一真理来源** (Single Source of Truth)
2. **统一配置接口** (Unified Config API)
3. **防抖和批量更新** (Debounced & Batch Updates)
4. **类型安全** (Type-Safe Configuration)
5. **可观测性** (Observable Configuration Changes)

---

### 架构设计

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           新的配置架构                                        │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌────────────────────────────────────────────────────────────────────────┐   │
│  │                         ConfigStore (统一状态管理)                        │   │
│  │                                                                         │   │
│  │  ┌───────────────┐  ┌────────────────┐  ┌───────────────────┐ │   │
│  │  │  Config State  │  │  Event Emitter  │  │  Sync Mechanism   │ │   │
│  │  │               │  │                 │  │                   │ │   │
│  │  │ - config      │  │  - config:changed │  │  - loadConfig()   │ │   │
│  │  │  - loading     │  │  - config:loading │  │  │ - saveConfig()   │ │   │
│  │  │  - error       │  │  │  │  │  │                   │ │   │
│  │  └───────┬───────┘  └────────┬────────┘  └───────┬───────────┘ │   │
│  │          │                    │                 │           │   │
│  │          ▼                    ▼                 ▼           │   │
│  │  ┌────────────────────────────────────────────────────────────────┐   │
│  │  │                 Config API Layer                         │   │
│  │  │                                                                │   │
│  │  │  Methods:                                                      │   │
│  │  │  ├─ getConfig(): Record<string, any>                            │   │
│  │  │  ├─ setConfig(patch: Partial<Record<string, any>>): void        │   │
│  │  │  ├─ updateConfig(config: Record<string, any>): void            │   │
│  │  │  ├─ reloadConfig(): Promise<void>                             │   │
│  │  │  ├─ saveConfig(): Promise<void>                             │   │
│  │  │  ├─ subscribe(listener): () => Unsubscribe                   │   │
│  │  │  └─ getWorkMode(): WorkMode                                 │   │
│  │  └───────────────────────────────────────────────────────────────┘ │   │
│  └───────────────────────────────────────────────────────────────────────┘ │
│           │                           │                              │           │
│           ▼                           ▼                              ▼           │
│  ┌────────────────┐            ┌───────────────────┐           ┌──────────────┐│
│  │ WorkModeStore  │            │   SettingsStore    │           │ useConfig()  ││
│  │                │            │                    │           │              ││
│  │ - setWorkMode() │            │ - updateConfig()   │           │ - getConfig()││
│  │ - getWorkMode() │            │ - getHotkey()      │           │ - setConfig()││
│  └────────────────┘            └────────────────────┘           └──────────────┘│
│           │                           │                              │           │
└───────────┴───────────────────────┴───────────────────────────────┴───────────┘
            │                           │                              │
            ▼                           ▼                              ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                      Rust Backend (Tauri Commands)                             │
│                                                                              │
│  #[tauri::command] async fn load_config()        ← 从 Python 加载配置      │
│  #[tauri::command] async fn save_config()       ← 保存到 Python           │
│  #[tauri::command] async fn get_work_mode()     ← 获取工作模式(本地状态)   │
│  #[tauri::command] async fn set_work_mode()     ← 设置工作模式(本地状态)   │
│                                                                              │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 实现计划

### Phase 1: 创建 ConfigStore (核心层) ⏱️ 1-2 天

**文件**: `src/stores/ConfigStore.tsx`

```typescript
interface ConfigStoreState {
  config: Record<string, any> | null;
  loading: boolean;
  error: string | null;
  lastSaved: Record<string, any> | null;  // 用于检测实际变化
  savePending: boolean;
}

interface ConfigStoreActions {
  loadConfig: () => Promise<void>;
  saveConfig: (immediate?: boolean) => Promise<void>;
  updateConfig: (updates: Record<string, any>) => void;
  setWorkMode: (mode: WorkMode) => void;
  reset: () => void;
  subscribe: (listener: ConfigListener) => Unsubscribe;
}

type ConfigListener = (state: ConfigStoreState) => void;
type Unsubscribe = () => void;
```

**关键特性**：
1. **防抖保存**：默认 500ms 防抖，可配置立即保存
2. **变更检测**：比较当前配置与 `lastSaved`，避免无效保存
3. **订阅机制**：组件可订阅配置变更事件
4. **批量更新**：支持 `updateConfig({ key: value })` 批量更新

### Phase 2: 重构 WorkModeContext ⏱️ 0.5 天

**文件**: `src/contexts/WorkModeContext.tsx`

**变更**：
- 移除独立的 `save_config` 调用
- 通过 `setWorkMode` 通知 ConfigStore
- ConfigStore 统一处理保存逻辑

### Phase 3: 重构 SettingsContext ⏱️ 0.5 天

**文件**: `src/contexts/SettingsContext.tsx`

**变更**：
- 移除独立的 `debouncedSave` 逻辑
- 使用 ConfigStore 进行所有配置操作
- 简化为纯 UI 层逻辑

### Phase 4: 废弃 useTauriAPI 中的配置管理 ⏱️ 0.5 天

**文件**: `src/useTauriAPI.ts`

**变更**：
- 移除 `config` 状态
- 移除 `loadConfig`, `saveConfig` 函数
- 保留其他 API (录音、对话、TTS 等)

### Phase 5: Rust 端优化 ⏱️ 0.5 天

**文件**: `src-tauri/src/commands/mod.rs`

**变更**：
- `save_config` 添加变更检测（只保存实际变化的部分）
- 返回更详细的错误信息

---

## 配置数据结构

### Config Schema

```typescript
interface AppConfig {
  // 工作模式
  work_mode: 'conversation' | 'text-input';

  // 录音模式
  recording_mode: 'push-to-talk' | 'continuous';

  // LLM 提供商配置
  llm_providers: Array<{
    name: string;
    enabled: boolean;
    api_key?: string;
    model?: string;
    base_url?: string;
  }>;

  // TTS 配置
  tts_provider: string;
  tts_model?: string;

  // PTT 快捷键
  push_to_talk_hotkey: {
    modifiers: string[];
    key: string;
    displayName: string;
  };

  // 语言设置
  language: string;
  input_language: string;
  output_language: string;

  // 其他...
}
```

---

## 关键改进

### 1. 防止重复保存

```typescript
// ConfigStore.tsx
const saveConfig = async (immediate = false) => {
  const currentConfig = state.config;
  const lastSaved = state.lastSaved;

  // 只有配置真正变化时才保存
  if (configEqual(currentConfig, lastSaved)) {
    console.log('[ConfigStore] No changes detected, skipping save');
    return;
  }

  // 执行保存
  await invoke('save_config', { config: currentConfig });

  setLastSaved(currentConfig);
};
```

### 2. 防抖机制

```typescript
// 默认 500ms 防抖
const DEBOUNCE_MS = 500;

let saveTimeout: NodeJS.Timeout | null = null;

const debouncedSave = async () => {
  if (saveTimeout) clearTimeout(saveTimeout);
  saveTimeout = setTimeout(() => {
    saveConfig(true);  // immediate = true
  }, DEBOUNCE_MS);
};

// 任何配置变更都触发防抖保存
updateConfig({ key: value }) → debouncedSave()
```

### 3. 事件订阅

```typescript
// WorkModeContext 订阅配置变更
useEffect(() => {
  const unsubscribe = configStore.subscribe((state) => {
    if (state.config?.work_mode !== workMode) {
      setWorkModeState(state.config.work_mode);
    }
  });

  return unsubscribe;
}, []);
```

---

## 测试计划

1. **单元测试**
   - ConfigStore 逻辑测试
   - 防抖机制测试
   - 变更检测测试

2. **集成测试**
   - 多组件同时更新配置
   - 网络错误处理
   - 并发保存测试

3. **端到端测试**
   - 工作模式切换
   - 配置保存和加载
   - 应用重启后配置保持

---

## 风险评估

| 风险 | 缓解措施 |
|------|---------|
| 破坏现有功能 | 逐步迁移，保留旧代码 |
| 引入新 bug | 充分的测试覆盖 |
| 性能影响 | 优化防抖时间 |
| 向后兼容 | 渐进式重构 |

---

## 时间估算

| 阶段 | 时间 | 说明 |
|------|------|------|
| 设计和规划 | 0.5 天 | 设计文档、接口定义 |
| Phase 1: ConfigStore | 1-2 天 | 核心实现和测试 |
| Phase 2-4: 重构各组件 | 1-2 天 | 逐个重构，验证 |
| Phase 5: Rust 优化 | 0.5 天 | 后端优化 |
| 测试和验证 | 1 天 | 完整测试 |
| **总计** | **4-6 天** | |
