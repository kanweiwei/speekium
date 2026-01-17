# Speekium Development Guide

Speekium is built with [Tauri 2.0](https://tauri.app/), combining React frontend, Rust backend, and Python daemon.

## Prerequisites

- **Node.js** 20+
- **Rust** 1.70+
- **Python** 3.10+
- **[uv](https://github.com/astral-sh/uv)** (Python package manager)
- **macOS** or **Windows** (Linux support planned)

## Quick Start

### Clone and Install

```bash
# Clone the repository
git clone https://github.com/kanweiwei/speekium.git
cd speekium

# Install frontend dependencies
npm install

# Install Python dependencies
uv sync
```

### Development Mode

```bash
# Start Tauri dev (runs frontend, Rust backend, and Python daemon)
npm run tauri:dev
```

This will:
- Start Vite dev server on `http://localhost:1420`
- Compile and run Rust backend
- Start Python daemon automatically
- Enable hot-reload for frontend changes

### Build for Production

```bash
# Build release binaries
npm run tauri:build
```

Output:
- **macOS**: `src-tauri/target/release/bundle/dmg/Speekium_[version].dmg`
- **Windows**: `src-tauri/target/release/bundle/msi/Speekium_[version]_x64_en-US.msi`

## Project Structure

```
speekium/
├── src/                    # React frontend
│   ├── components/         # UI components
│   ├── contexts/           # React contexts
│   └── main.tsx           # Entry point
├── src-tauri/             # Rust backend
│   ├── src/               # Rust source code
│   │   └── lib.rs         # Main Tauri commands
│   └── tauri.conf.json    # Tauri configuration
├── python/                # Python daemon (via worker_daemon.py)
├── speekium.py            # Main Python entry point
├── worker_daemon.py       # Daemon process
└── config_manager.py      # Configuration management
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Speekium Desktop App                     │
│                      (Tauri + React)                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
│   │   Frontend  │    │    Rust     │    │   Python    │    │
│   │   (React)   │◄──►│   Backend   │◄──►│   Daemon    │    │
│   └─────────────┘    └─────────────┘    └─────────────┘    │
│                                                │             │
│                                          ┌─────┴─────┐      │
│                                          │           │      │
│                                     ┌────▼───┐ ┌────▼───┐  │
│                                     │  VAD   │ │  ASR   │  │
│                                     │(Silero)│ │(Sense- │  │
│                                     │        │ │ Voice) │  │
│                                     └────────┘ └────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │          LLM Backends         │
              ├───────────────────────────────┤
              │ Ollama │ OpenAI │ OpenRouter  │
              │ ZhipuAI │ Custom API           │
              └───────────────────────────────┘
```

## Development Tips

### Frontend Hot-Reload

Changes to `src/` files automatically trigger hot-reload.

### Rust Backend Changes

After modifying Rust code in `src-tauri/src/`, restart the dev process:

```bash
# Stop: Ctrl+C
# Start again:
npm run tauri:dev
```

### Python Daemon Changes

After modifying Python files, the daemon auto-reloads. No restart needed.

### Debugging

**Frontend:**
- Use Chrome DevTools (included in Tauri dev window)
- `Cmd+Option+I` (macOS) or `Ctrl+Shift+I` (Windows)

**Rust Backend:**
```bash
# Enable debug output
RUST_LOG=debug npm run tauri:dev
```

**Python Daemon:**
- Check console output for daemon logs
- Logs are prefixed with `[DAEMON]`

## Tauri Commands

| Command | Description |
|---------|-------------|
| `npm run tauri:dev` | Start development mode |
| `npm run tauri:build` | Build release binaries |
| `npm run tauri info` | Show Tauri environment info |

## Adding New Tauri Commands

1. Define command in `src-tauri/src/lib.rs`:
```rust
#[tauri::command]
async fn my_command(arg: String) -> Result<String, String> {
    Ok(format!("Received: {}", arg))
}
```

2. Register in `tauri::Builder`:
```rust
.invoke_handler(tauri::generate_handler![
    my_command,
    // ... other commands
])
```

3. Call from frontend:
```typescript
import { invoke } from '@tauri-apps/api/core';
const result = await invoke<string>('my_command', { arg: 'test' });
```

## Testing

```bash
# Python tests
uv run pytest

# TypeScript type check
npx tsc --noEmit
```

## Troubleshooting

**Port 1420 already in use:**
```bash
# Kill process using the port
lsof -ti:1420 | xargs kill -9
```

**Daemon won't start:**
- Check Python dependencies: `uv sync`
- Check config file: `~/.config/speekium/config.json`

**Build fails:**
- Ensure Rust is installed: `rustc --version`
- Update Tauri CLI: `npm install -g @tauri-apps/cli`
