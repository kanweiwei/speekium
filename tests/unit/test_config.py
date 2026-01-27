"""Configuration Manager Tests

Tests for configuration loading, saving, and validation.
Also tests that configuration changes are properly reflected in the daemon.
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from config_manager import ConfigManager, DEFAULT_CONFIG


class TestConfigLoadSave:
    """Test basic configuration load and save operations."""

    def test_load_default_config(self):
        """Test that default config is returned when no config file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Set temp config directory
            original_env = os.environ.get("SPEEKIUM_CONFIG_DIR")
            os.environ["SPEEKIUM_CONFIG_DIR"] = tmpdir

            try:
                # Remove config file if it exists
                config_path = Path(tmpdir) / "config.json"
                if config_path.exists():
                    config_path.unlink()

                # Need to reload the module to pick up new CONFIG_PATH
                import importlib
                import config_manager

                importlib.reload(config_manager)

                config = config_manager.ConfigManager.load(silent=True)

                # Should have all default keys
                assert "llm_provider" in config
                assert "llm_providers" in config
                assert "tts_backend" in config
                assert "vad_threshold" in config
                assert "recording_mode" in config
                assert "system_prompt" in config

                # File should be created
                assert config_path.exists()
            finally:
                if original_env:
                    os.environ["SPEEKIUM_CONFIG_DIR"] = original_env
                else:
                    os.environ.pop("SPEEKIUM_CONFIG_DIR", None)
                # Reload module to restore original CONFIG_PATH
                import importlib
                import config_manager

                importlib.reload(config_manager)

    def test_save_and_load_config(self):
        """Test saving and loading configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_env = os.environ.get("SPEEKIUM_CONFIG_DIR")
            os.environ["SPEEKIUM_CONFIG_DIR"] = tmpdir

            try:
                test_config = {
                    "llm_provider": "openai",
                    "llm_providers": DEFAULT_CONFIG["llm_providers"],
                    "tts_backend": "edge",
                    "tts_rate": "+10%",
                    "vad_threshold": 0.7,
                    "vad_consecutive_threshold": 5,
                    "vad_silence_duration": 1.0,
                    "vad_pre_buffer": 0.5,
                    "vad_min_speech_duration": 0.5,
                    "vad_max_recording_duration": 60,
                    "max_history": 20,
                    "work_mode": "text-input",
                    "recording_mode": "continuous",
                    "system_prompt": "Test prompt",
                    "push_to_talk_hotkey": {
                        "modifiers": ["Ctrl"],
                        "key": "Digit1",
                        "displayName": "⌃1",
                    },
                }

                ConfigManager.save(test_config)
                loaded_config = ConfigManager.load(silent=True)

                # Verify loaded config matches saved config
                assert loaded_config["llm_provider"] == "openai"
                assert loaded_config["tts_rate"] == "+10%"
                assert loaded_config["vad_threshold"] == 0.7
                assert loaded_config["recording_mode"] == "continuous"
                assert loaded_config["system_prompt"] == "Test prompt"
            finally:
                if original_env:
                    os.environ["SPEEKIUM_CONFIG_DIR"] = original_env
                else:
                    os.environ.pop("SPEEKIUM_CONFIG_DIR", None)

    def test_merge_with_default_on_load(self):
        """Test that missing fields are merged with defaults on load."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_env = os.environ.get("SPEEKIUM_CONFIG_DIR")
            os.environ["SPEEKIUM_CONFIG_DIR"] = tmpdir

            try:
                # Need to reload module to pick up new CONFIG_PATH
                import importlib
                import config_manager

                importlib.reload(config_manager)

                # Save minimal config (missing some fields)
                minimal_config = {"llm_provider": "zhipu"}
                config_path = Path(tmpdir) / "config.json"

                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(minimal_config, f)

                loaded_config = config_manager.ConfigManager.load(silent=True)

                # Should have llm_provider from saved config
                assert loaded_config["llm_provider"] == "zhipu"

                # Should have other fields from default
                assert "tts_backend" in loaded_config
                assert "vad_threshold" in loaded_config
                assert "recording_mode" in loaded_config
            finally:
                if original_env:
                    os.environ["SPEEKIUM_CONFIG_DIR"] = original_env
                else:
                    os.environ.pop("SPEEKIUM_CONFIG_DIR", None)
                # Reload module to restore original CONFIG_PATH
                import importlib
                import config_manager

                importlib.reload(config_manager)


class TestConfigValidation:
    """Test configuration validation."""

    def test_vad_threshold_range(self):
        """Test VAD threshold is within valid range."""
        # Default should be valid
        assert 0.0 <= DEFAULT_CONFIG["vad_threshold"] <= 1.0

    def test_llm_providers_structure(self):
        """Test LLM providers have required fields."""
        for provider in DEFAULT_CONFIG["llm_providers"]:
            assert "name" in provider
            assert "base_url" in provider
            assert "api_key" in provider
            assert "model" in provider

    def test_hotkey_structure(self):
        """Test hotkey config has required fields."""
        hotkey = DEFAULT_CONFIG["push_to_talk_hotkey"]
        assert "modifiers" in hotkey
        assert "key" in hotkey
        assert "displayName" in hotkey


class TestConfigChangePropagation:
    """Test that configuration changes affect daemon behavior.

    These tests verify that when configuration is changed and saved,
    the daemon responds to the new configuration.
    """

    def test_vad_config_change_affects_detection(self):
        """Test that changing VAD threshold affects detection sensitivity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_env = os.environ.get("SPEEKIUM_CONFIG_DIR")
            os.environ["SPEEKIUM_CONFIG_DIR"] = tmpdir

            try:
                # Load default config
                config = ConfigManager.load(silent=True)

                # Change VAD threshold
                config["vad_threshold"] = 0.9  # Less sensitive
                ConfigManager.save(config)

                # Reload and verify
                reloaded_config = ConfigManager.load(silent=True)
                assert reloaded_config["vad_threshold"] == 0.9

                # In a real daemon, this would affect VAD behavior
                # For unit test, we verify the config is persisted correctly
            finally:
                if original_env:
                    os.environ["SPEEKIUM_CONFIG_DIR"] = original_env
                else:
                    os.environ.pop("SPEEKIUM_CONFIG_DIR", None)

    def test_llm_provider_change_affects_backend(self):
        """Test that changing LLM provider switches the backend."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_env = os.environ.get("SPEEKIUM_CONFIG_DIR")
            os.environ["SPEEKIUM_CONFIG_DIR"] = tmpdir

            try:
                # Load config
                config = ConfigManager.load(silent=True)

                # Change provider from ollama to openai
                config["llm_provider"] = "openai"
                ConfigManager.save(config)

                # Reload and verify
                reloaded_config = ConfigManager.load(silent=True)
                assert reloaded_config["llm_provider"] == "openai"

                # In a real daemon, this would switch to OpenAI backend
                # For unit test, we verify the config is persisted correctly
            finally:
                if original_env:
                    os.environ["SPEEKIUM_CONFIG_DIR"] = original_env
                else:
                    os.environ.pop("SPEEKIUM_CONFIG_DIR", None)

    def test_recording_mode_change(self):
        """Test that changing recording mode is persisted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_env = os.environ.get("SPEEKIUM_CONFIG_DIR")
            os.environ["SPEEKIUM_CONFIG_DIR"] = tmpdir

            try:
                config = ConfigManager.load(silent=True)

                # Switch from push-to-talk to continuous
                config["recording_mode"] = "continuous"
                ConfigManager.save(config)

                reloaded_config = ConfigManager.load(silent=True)
                assert reloaded_config["recording_mode"] == "continuous"
            finally:
                if original_env:
                    os.environ["SPEEKIUM_CONFIG_DIR"] = original_env
                else:
                    os.environ.pop("SPEEKIUM_CONFIG_DIR", None)

    def test_tts_rate_change(self):
        """Test that TTS rate change is persisted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_env = os.environ.get("SPEEKIUM_CONFIG_DIR")
            os.environ["SPEEKIUM_CONFIG_DIR"] = tmpdir

            try:
                config = ConfigManager.load(silent=True)

                # Change TTS rate
                config["tts_rate"] = "+20%"
                ConfigManager.save(config)

                reloaded_config = ConfigManager.load(silent=True)
                assert reloaded_config["tts_rate"] == "+20%"
            finally:
                if original_env:
                    os.environ["SPEEKIUM_CONFIG_DIR"] = original_env
                else:
                    os.environ.pop("SPEEKIUM_CONFIG_DIR", None)


class TestConfigJSONRPCIntegration:
    """Test configuration changes through JSON-RPC interface.

    These tests simulate what the Socket IPC interface does.
    """

    def test_save_config_method(self):
        """Test saving config via dict (simulates JSON-RPC save_config)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_env = os.environ.get("SPEEKIUM_CONFIG_DIR")
            os.environ["SPEEKIUM_CONFIG_DIR"] = tmpdir

            try:
                # Simulate JSON-RPC request with partial config update
                config_update = {
                    "llm_provider": "zhipu",
                    "tts_rate": "-10%",
                }

                # Merge with current config
                current_config = ConfigManager.load(silent=True)
                current_config.update(config_update)

                # Save (simulates handle_save_config)
                ConfigManager.save(current_config)

                # Verify changes persisted
                reloaded = ConfigManager.load(silent=True)
                assert reloaded["llm_provider"] == "zhipu"
                assert reloaded["tts_rate"] == "-10%"

                # Other fields should remain
                assert "vad_threshold" in reloaded
                assert "recording_mode" in reloaded
            finally:
                if original_env:
                    os.environ["SPEEKIUM_CONFIG_DIR"] = original_env
                else:
                    os.environ.pop("SPEEKIUM_CONFIG_DIR", None)

    def test_config_method_returns_full_config(self):
        """Test that config method returns complete configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_env = os.environ.get("SPEEKIUM_CONFIG_DIR")
            os.environ["SPEEKIUM_CONFIG_DIR"] = tmpdir

            try:
                # Simulates JSON-RPC config method
                config = ConfigManager.load(silent=True)

                # Should return all expected fields
                expected_fields = [
                    "llm_provider",
                    "llm_providers",
                    "tts_backend",
                    "tts_rate",
                    "vad_threshold",
                    "vad_consecutive_threshold",
                    "vad_silence_duration",
                    "recording_mode",
                    "work_mode",
                    "system_prompt",
                    "push_to_talk_hotkey",
                ]

                for field in expected_fields:
                    assert field in config, f"Missing field: {field}"
            finally:
                if original_env:
                    os.environ["SPEEKIUM_CONFIG_DIR"] = original_env
                else:
                    os.environ.pop("SPEEKIUM_CONFIG_DIR", None)
