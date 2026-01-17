# Contributing to Speekium

Thank you for your interest in contributing to Speekium! This document will help you get started.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Submitting Changes](#submitting-changes)
- [Reporting Issues](#reporting-issues)

## Code of Conduct

Please be respectful and constructive in all interactions. We aim to maintain a welcoming and inclusive community.

## Getting Started

### Prerequisites

- **Node.js** 20+
- **Rust** 1.70+
- **Python** 3.10+
- **[uv](https://github.com/astral-sh/uv)** (Python package manager)

### Setup

```bash
# Clone the repository
git clone https://github.com/kanweiwei/speekium.git
cd speekium

# Install dependencies
npm install
uv sync

# Start development mode
npm run tauri:dev
```

See [docs/development/setup.md](docs/development/setup.md) for detailed setup instructions.

## Development Workflow

### 1. Fork and Clone

```bash
# Fork the repo on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/speekium.git
cd speekium

# Add upstream remote
git remote add upstream https://github.com/kanweiwei/speekium.git
```

### 2. Create a Branch

```bash
git checkout main
git fetch upstream
git rebase upstream/main

# Create a feature branch
git checkout -b feature/your-feature-name
```

### 3. Make Changes

- Write clear, concise code
- Follow the coding standards below
- Add tests for new features
- Update documentation as needed

### 4. Test Your Changes

```bash
# Type check
npx tsc --noEmit

# Python tests
uv run pytest

# Run the app
npm run tauri:dev
```

### 5. Commit Your Changes

Use clear commit messages:

```
feat: add ZhipuAI LLM backend support
fix: resolve VAD recording not stopping on mode switch
docs: update installation guide for Windows
```

### 6. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub.

## Coding Standards

### TypeScript/React

- Use functional components with hooks
- Follow React best practices
- Use TypeScript types strictly (no `any`)
- Follow existing code style

```typescript
// Good
interface Props {
  title: string;
  count?: number;
}

export function MyComponent({ title, count = 0 }: Props) {
  return <div>{title}: {count}</div>;
}

// Bad
export function MyComponent(props: any) {
  return <div>{props.title}</div>;
}
```

### Rust

- Use `Result<T, E>` for error handling
- Prefer `String` over `&str` for Tauri command returns
- Add documentation for public functions

```rust
// Good
#[tauri::command]
async fn my_command(arg: String) -> Result<String, String> {
    let result = process(&arg)
        .map_err(|e| format!("Processing failed: {}", e))?;
    Ok(result)
}
```

### Python

- Use type hints
- Follow PEP 8 style guide
- Add docstrings for functions

```python
# Good
def process_audio(audio_data: bytes) -> dict[str, Any]:
    """Process audio data and return transcription.

    Args:
        audio_data: Raw audio bytes

    Returns:
        Dictionary with transcription text and metadata
    """
    ...
```

## Project-Specific Guidelines

### Adding New Tauri Commands

1. Define the command in `src-tauri/src/lib.rs`:

```rust
#[tauri::command]
async fn new_command(param: String) -> Result<Response, String> {
    // Implementation
}
```

2. Register in `invoke_handler`:

```rust
.invoke_handler(tauri::generate_handler![
    new_command,
    // ... other commands
])
```

3. Add TypeScript types in `src/useTauriAPI.ts` or appropriate file

4. Call from frontend:

```typescript
import { invoke } from '@tauri-apps/api/core';
const result = await invoke<Response>('new_command', { param: 'value' });
```

### Modifying Python Daemon

- The daemon lives in `worker_daemon.py`
- Changes auto-reload during development
- Add appropriate logging with `[DAEMON]` prefix

### Adding Dependencies

**Frontend (npm):**
```bash
npm install package-name
```

**Rust (Cargo):**
```toml
# src-tauri/Cargo.toml
[dependencies]
crate-name = "version"
```

**Python (uv):**
```bash
uv add package-name
```

## Submitting Changes

### Pull Request Checklist

- [ ] Code follows project coding standards
- [ ] Tests pass locally
- [ ] TypeScript compiles without errors
- [ ] Documentation updated (if applicable)
- [ ] Commit messages are clear

### PR Description Template

```markdown
## Description
Brief description of the changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Code refactoring

## Testing
How did you test these changes?

## Screenshots (if applicable)
```

## Reporting Issues

### Bug Reports

Include:
- Speekium version
- Operating system and version
- Steps to reproduce
- Expected vs actual behavior
- Logs (if applicable)

### Feature Requests

Include:
- Clear description of the feature
- Use case / problem it solves
- Possible implementation approaches (if you have ideas)

## Questions?

Feel free to:
- Open a [discussion](https://github.com/kanweiwei/speekium/discussions)
- Ask in an issue
- Chat with the community

---

Thank you for contributing to Speekium! 🎉
