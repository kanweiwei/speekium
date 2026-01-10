#!/usr/bin/env python3
"""
Test script for LLM backend module
Tests both Claude and Ollama backends
"""

import asyncio
import sys
from pathlib import Path

# Add src-python to path
sys.path.insert(0, str(Path(__file__).parent / "src-python"))

from llm_backend import (
    ClaudeBackend,
    OllamaBackend,
    create_backend,
    LLMBackendManager,
    ChatMessageType,
)

SYSTEM_PROMPT = "You are a test assistant. Keep responses short and friendly."


async def test_claude_backend():
    """Test Claude backend"""
    print("\n" + "=" * 50)
    print("Testing Claude Backend")
    print("=" * 50)

    backend = ClaudeBackend(SYSTEM_PROMPT, max_history=5, logger=None)

    test_message = "Hello! Can you say hi back?"

    try:
        print(f"\n[TEST] Sending message: {test_message}")

        response_count = 0
        async for text, msg_type in backend.chat_stream_async(test_message):
            response_count += 1
            print(f"[STREAM #{response_count}] {msg_type.value}: {text}")

        print(f"[SUCCESS] Received {response_count} chunks from Claude")

        await backend.shutdown()
        return True
    except Exception as e:
        print(f"[ERROR] Claude test failed: {e}")
        await backend.shutdown()
        return False


async def test_ollama_backend():
    """Test Ollama backend"""
    print("\n" + "=" * 50)
    print("Testing Ollama Backend")
    print("=" * 50)

    try:
        backend = OllamaBackend(
            SYSTEM_PROMPT,
            model="qwen2.5:1.5b",
            base_url="http://localhost:11434",
            max_history=5,
            logger=None,
        )

        test_message = "你好！请说声你好。"

        print(f"\n[TEST] Sending message: {test_message}")

        response_count = 0
        async for text, msg_type in backend.chat_stream_async(test_message):
            response_count += 1
            print(f"[STREAM #{response_count}] {msg_type.value}: {text}")

        print(f"[SUCCESS] Received {response_count} chunks from Ollama")

        await backend.shutdown()
        return True
    except Exception as e:
        print(f"[ERROR] Ollama test failed: {e}")
        return False


async def test_backend_factory():
    """Test backend factory function"""
    print("\n" + "=" * 50)
    print("Testing Backend Factory")
    print("=" * 50)

    try:
        backend = create_backend(
            "ollama",
            SYSTEM_PROMPT,
            model="qwen2.5:1.5b",
            base_url="http://localhost:11434",
            max_history=5,
            logger=None,
        )

        print(f"[SUCCESS] Created backend: {type(backend).__name__}")

        response = await backend.chat_async("Say hello!")
        print(f"[RESPONSE] {response}")

        await backend.shutdown()
        return True
    except Exception as e:
        print(f"[ERROR] Factory test failed: {e}")
        return False


async def test_backend_manager():
    """Test LLM backend manager"""
    print("\n" + "=" * 50)
    print("Testing LLM Backend Manager")
    print("=" * 50)

    try:
        config = {
            "llm_backend": "ollama",
            "ollama_model": "qwen2.5:1.5b",
            "ollama_base_url": "http://localhost:11434",
            "max_history": 5,
        }

        manager = LLMBackendManager(config, logger=None)
        backend = manager.load_backend()

        print(f"[SUCCESS] Loaded backend: {type(backend).__name__}")

        response_count = 0
        async for text, msg_type in backend.chat_stream_async("你好，请自我介绍一下。"):
            response_count += 1
            print(f"[STREAM #{response_count}] {msg_type.value}: {text}")

        print(f"[SUCCESS] Received {response_count} chunks")

        await manager.shutdown()
        return True
    except Exception as e:
        print(f"[ERROR] Manager test failed: {e}")
        return False


async def test_conversation_history():
    """Test conversation history management"""
    print("\n" + "=" * 50)
    print("Testing Conversation History")
    print("=" * 50)

    try:
        backend = create_backend(
            "ollama",
            SYSTEM_PROMPT,
            model="qwen2.5:1.5b",
            base_url="http://localhost:11434",
            max_history=5,
            logger=None,
        )

        print("\n[TEST] First message:")
        async for text, msg_type in backend.chat_stream_async("我的名字是张三。"):
            print(f"[STREAM] {text}")

        print(f"\n[TEST] History size: {len(backend.history)}")

        print("\n[TEST] Second message (should remember name):")
        async for text, msg_type in backend.chat_stream_async("我叫什么名字？"):
            print(f"[STREAM] {text}")

        print(f"\n[TEST] History size: {len(backend.history)}")

        print("\n[TEST] Clearing history...")
        backend.clear_history()
        print(f"[TEST] History size after clear: {len(backend.history)}")

        await backend.shutdown()
        return True
    except Exception as e:
        print(f"[ERROR] History test failed: {e}")
        return False


async def main():
    """Run all tests"""
    print("=" * 50)
    print("LLM Backend Module Test Suite")
    print("=" * 50)

    tests = [
        ("Backend Factory", test_backend_factory),
        ("Ollama Backend", test_ollama_backend),
        ("Backend Manager", test_backend_manager),
        ("Conversation History", test_conversation_history),
    ]

    results = []

    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
        except KeyboardInterrupt:
            print("\n\n[INTERRUPTED] Test cancelled by user")
            break
        except Exception as e:
            print(f"\n[FATAL ERROR] {name}: {e}")
            results.append((name, False))

    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")

    total = len(results)
    passed = sum(1 for _, r in results if r)
    print(f"\nTotal: {passed}/{total} tests passed")

    return passed == total


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Test cancelled by user")
        sys.exit(1)
