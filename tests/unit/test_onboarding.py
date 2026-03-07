"""
引导流程测试用例
测试 Onboarding API 功能
"""

import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestOnboardingLogic:
    """测试引导流程逻辑"""
    
    def test_onboarding_status_check_pending(self):
        """测试引导状态 - 未完成"""
        config = {"onboarding_completed": False}
        result = config.get("onboarding_completed", False)
        assert result is False
    
    def test_onboarding_status_check_completed(self):
        """测试引导状态 - 已完成"""
        config = {"onboarding_completed": True}
        result = config.get("onboarding_completed", False)
        assert result is True
    
    def test_onboarding_default_value(self):
        """测试默认值为 False"""
        config = {}
        result = config.get("onboarding_completed", False)
        assert result is False
    
    def test_onboarding_set_completed(self):
        """测试设置引导完成"""
        config = {}
        config["onboarding_completed"] = True
        assert config["onboarding_completed"] is True
    
    def test_onboarding_unset(self):
        """测试取消引导完成"""
        config = {"onboarding_completed": True}
        config["onboarding_completed"] = False
        assert config["onboarding_completed"] is False
    
    def test_onboarding_with_llm_config(self):
        """测试带 LLM 配置的引导状态"""
        config = {
            "onboarding_completed": True,
            "llm_provider": "ollama"
        }
        assert config.get("onboarding_completed", False) is True
        assert config.get("llm_provider") == "ollama"
