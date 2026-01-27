#!/usr/bin/env python3
"""
Quick test script for socket_server.py

This script tests the basic functionality of the Socket server
without requiring a full daemon setup.
"""

import asyncio
import json
import platform
import socket
import sys


async def test_unix_socket():
    """Test Unix socket server"""
    socket_path = "/tmp/speekium-test.sock"

    print(f"🧪 Testing Unix socket: {socket_path}")

    # Clean up old socket
    import os

    try:
        os.remove(socket_path)
    except FileNotFoundError:
        pass

    # Create test server
    server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server_socket.bind(socket_path)
    server_socket.listen(1)

    print("✅ Test server started")

    # Test connection
    async def test_client():
        await asyncio.sleep(0.1)  # Wait for server to start

        client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client_socket.connect(socket_path)

        # Send test request
        request = {"test": "data"}
        request_line = json.dumps(request) + "\n"
        client_socket.sendall(request_line.encode("utf-8"))

        # Receive response
        response = client_socket.recv(4096).decode("utf-8")
        print(f"📨 Received: {response}")

        client_socket.close()

    # Run client in background
    asyncio.create_task(test_client())

    # Accept connection
    loop = asyncio.get_event_loop()
    client_socket, _ = await loop.sock_accept(server_socket)

    # Receive request
    request = await loop.sock_recv(client_socket, 4096)
    print(f"📬 Received request: {request.decode('utf-8')}")

    # Send response
    response = {"status": "ok"}
    response_line = json.dumps(response) + "\n"
    await loop.sock_sendall(client_socket, response_line.encode("utf-8"))

    # Clean up
    client_socket.close()
    server_socket.close()
    os.remove(socket_path)

    print("✅ Unix socket test passed")


async def test_json_rpc_parsing():
    """Test JSON-RPC parsing"""
    print("\n🧪 Testing JSON-RPC parsing")

    # Import socket_server module
    try:
        from socket_server import create_response, create_error

        # Test response creation
        response = create_response(1, result={"status": "ok"})
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert response["result"]["status"] == "ok"
        print("✅ Response creation test passed")

        # Test error creation
        error = create_error(-32601, "Method not found", "test_method")
        assert error["code"] == -32601
        assert error["message"] == "Method not found"
        assert error["data"] == "test_method"
        print("✅ Error creation test passed")

        # Test error response
        error_response = create_response(1, error=error)
        assert "error" in error_response
        assert error_response["error"]["code"] == -32601
        print("✅ Error response test passed")

        # Test notification (no id)
        notification = create_response(None, result={"success": True})
        assert notification["id"] is None
        print("✅ Notification test passed")

        print("✅ JSON-RPC parsing tests passed")

    except ImportError as e:
        print(f"❌ Failed to import socket_server: {e}")
        return False

    return True


async def test_platform_detection():
    """Test platform detection"""
    print("\n🧪 Testing platform detection")

    try:
        from socket_server import get_socket_path, cleanup_old_socket

        socket_path = get_socket_path()

        if platform.system() == "Windows":
            assert socket_path == r"\\.\pipe\speekium-daemon"
            print(f"✅ Windows: Named Pipe path correct")
        else:
            assert socket_path == "/tmp/speekium-daemon.sock"
            print(f"✅ Unix: Socket path correct")

        # Test cleanup function (should not raise error)
        cleanup_old_socket(socket_path)
        print("✅ Cleanup function executed")

        print("✅ Platform detection tests passed")

    except ImportError as e:
        print(f"❌ Failed to import socket_server: {e}")
        return False

    return True


async def main():
    """Run all tests"""
    print("=" * 60)
    print("🧪 Socket Server Test Suite")
    print("=" * 60)

    tests_passed = 0
    tests_failed = 0

    # Test 1: JSON-RPC parsing
    try:
        if await test_json_rpc_parsing():
            tests_passed += 1
        else:
            tests_failed += 1
    except Exception as e:
        print(f"❌ JSON-RPC parsing test failed: {e}")
        tests_failed += 1

    # Test 2: Platform detection
    try:
        if await test_platform_detection():
            tests_passed += 1
        else:
            tests_failed += 1
    except Exception as e:
        print(f"❌ Platform detection test failed: {e}")
        tests_failed += 1

    # Test 3: Unix socket (skip on Windows)
    if platform.system() != "Windows":
        try:
            await test_unix_socket()
            tests_passed += 1
        except Exception as e:
            print(f"❌ Unix socket test failed: {e}")
            import traceback

            traceback.print_exc()
            tests_failed += 1
    else:
        print("\n⏭️  Skipping Unix socket test on Windows")

    # Summary
    print("\n" + "=" * 60)
    print(f"📊 Test Summary: {tests_passed} passed, {tests_failed} failed")
    print("=" * 60)

    if tests_failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
