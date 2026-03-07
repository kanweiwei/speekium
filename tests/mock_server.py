"""
Mock Server for Testing
提供本地 Mock 服务，用于离线测试
"""

import asyncio
from typing import AsyncIterator


class MockLLMBackend:
    """Mock LLM 后端，用于测试"""
    
    def __init__(self, system_prompt: str = "You are a helpful assistant.", response: str = "This is a mock response."):
        self.system_prompt = system_prompt
        self.response = response
        self.history = []
        self.call_count = 0
    
    def chat(self, message: str) -> str:
        """同步聊天接口"""
        self.call_count += 1
        self.history.append({"role": "user", "content": message})
        self.history.append({"role": "assistant", "content": self.response})
        return self.response
    
    async def chat_stream(self, message: str) -> AsyncIterator[str]:
        """流式聊天接口"""
        self.call_count += 1
        self.history.append({"role": "user", "content": message})
        self.history.append({"role": "assistant", "content": self.response})
        
        # 模拟流式输出
        for word in self.response.split():
            yield word + " "
            await asyncio.sleep(0.01)  # 模拟延迟
    
    def clear_history(self):
        """清空历史"""
        self.history = []
    
    def get_call_count(self) -> int:
        """获取调用次数"""
        return self.call_count


class MockTTSBackend:
    """Mock TTS 后端，用于测试"""
    
    def __init__(self, audio_data: bytes = b"RIFF...."):
        self.audio_data = audio_data
        self.call_count = 0
    
    async def speak(self, text: str) -> bytes:
        """生成语音"""
        self.call_count += 1
        return self.audio_data
    
    def get_call_count(self) -> int:
        return self.call_count


class MockASRBackend:
    """Mock ASR 后端，用于测试"""
    
    def __init__(self, transcript: str = "mock transcript"):
        self.transcript = transcript
        self.call_count = 0
    
    async def recognize(self, audio_data: bytes) -> str:
        """识别语音"""
        self.call_count += 1
        return self.transcript
    
    def get_call_count(self) -> int:
        return self.call_count


class MockVADBackend:
    """Mock VAD 后端，用于测试"""
    
    def __init__(self, has_speech: bool = True):
        self.has_speech = has_speech
        self.call_count = 0
    
    def detect(self, audio_chunk: bytes) -> bool:
        """检测语音"""
        self.call_count += 1
        return self.has_speech
    
    def get_call_count(self) -> int:
        return self.call_count


# 预配置的 Mock 响应
MOCK_RESPONSES = {
    "hello": "Hello! I'm running in mock mode.",
    "你好": "你好！我正在测试模式下运行。",
    "error": "Error: This is a mock error response.",
}


def get_mock_response(input_text: str) -> str:
    """根据输入返回预配置的 Mock 响应"""
    input_lower = input_text.lower().strip()
    
    for key, response in MOCK_RESPONSES.items():
        if key in input_lower:
            return response
    
    return f"Mock response to: {input_text}"
