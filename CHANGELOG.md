# Changelog

All notable changes to Speekium will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Branded Speekium icon with sound wave design
- ZhipuAI (智谱AI) LLM backend support with glm-4 models
- Loading screen with animated sound wave rings and gradient background
- `ConfigManager.load()` silent parameter for reduced logging
- Contributing guide for developers

### Changed
- Hotkey unified to `Alt+3` across all platforms
- LLM provider configuration restructured to unified array format
- Recording mode now writes directly to config file for faster VAD detection
- Improved daemon health check with frontend status events
- Updated development documentation for Tauri 2.0 architecture

### Fixed
- VAD recording not stopping when switching from continuous to push-to-talk mode
- PTT overlay window display issues
- Daemon initialization timing on page refresh
- Event listener cleanup issues
- Hotkey display logic now syncs with config file

## [0.2.0] - 2026-01-17

### Added
- Bilingual screenshots support (English and Chinese)
- Tauri 2.0 desktop framework migration
- Push-to-Talk (PTT) recording mode
- Continuous VAD (Voice Activity Detection) recording mode
- Conversation history with database storage
- i18n support (English, Chinese)
- Customizable hotkeys
- Dark/Light theme switching
- Real-time streaming TTS (Edge TTS)
- Multiple LLM backends (Ollama, OpenAI, OpenRouter, ZhipuAI)

### Changed
- Migrated from pywebview to Tauri 2.0 architecture
- Unified PTT hotkey to `Alt+3`

## [0.1.0] - Earlier

### Added
- Initial release
- Basic voice recording and transcription
- LLM chat integration
- Text-to-speech output
- Configuration management

---

## Version Summary

| Version | Date | Description |
|---------|------|-------------|
| 0.2.0 | 2026-01-17 | Tauri 2.0 migration, VAD mode, bilingual support |
| 0.1.0 | Earlier | Initial pywebview release |
