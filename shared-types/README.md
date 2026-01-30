# Shared Types Library

Type definitions shared across the Speekium application.

## Overview

This library provides:
- **Single Source of Truth**: Type definitions exist in one place
- **Type Safety**: Compile-time checking across frontend and backend
- **Automatic Synchronization**: Frontend and backend types are always in sync

## Building

### For Rust backend
```bash
cargo build
```

### For frontend (WebAssembly)
```bash
wasm-pack build --target web --out-dir pkg
```

## Usage

### In Rust backend
```toml
# Cargo.toml
[dependencies]
shared-types = { path = "../shared-types" }
```

```rust
use shared_types::{RecordingMode, WorkMode};

let mode = RecordingMode::PushToTalk;
```

### In frontend (TypeScript)
```typescript
import { RecordingMode, WorkMode } from '@speekium/shared-types';

const mode = RecordingMode.PushToTalk;
```

## Types

| Module | Description |
|--------|-------------|
| `models` | Data models (RecordingMode, WorkMode, AppState, etc.) |
| `events` | Event definitions for the EventBus |
| `errors` | Shared error types |

## Development

- Run tests: `cargo test`
- Format code: `cargo fmt`
- Lint: `cargo clippy`
