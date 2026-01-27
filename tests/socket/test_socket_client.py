#!/usr/bin/env python3
"""
Simple Socket Client for testing socket_server.py

Usage:
    python3 test_socket_client.py

This will send test JSON-RPC requests to the socket server.
"""

import json
import platform
import socket
import sys
import time


def get_socket_path():
    """Get socket path based on platform"""
    if platform.system() == "Windows":
        return r"\\.\pipe\speekium-daemon"
    else:
        return "/tmp/speekium-daemon.sock"


def send_request(sock, request):
    """Send JSON-RPC request and receive response"""
    request_line = json.dumps(request) + "\n"
    sock.sendall(request_line.encode("utf-8"))

    # Receive response (with timeout)
    sock.settimeout(5.0)
    buffer = b""
    while True:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buffer += chunk
            if b"\n" in buffer:
                break
        except TimeoutError:
            break

    if buffer:
        response_line = buffer.split(b"\n", 1)[0]
        return json.loads(response_line.decode("utf-8"))
    return None


def test_socket_client():
    """Test socket client with sample requests"""
    socket_path = get_socket_path()
    print(f"🔌 Connecting to {socket_path}")

    try:
        if platform.system() == "Windows":
            print("⚠️ Windows Named Pipe not implemented in test client")
            print("   Please use Rust client for Windows testing")
            return

        # Connect to Unix socket
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(socket_path)
        print("✅ Connected to socket server")

        # Test 1: Health check
        print("\n📋 Test 1: Health check")
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "health",
            "params": {},
        }
        response = send_request(sock, request)
        print(f"Response: {json.dumps(response, indent=2)}")

        # Test 2: Get config
        print("\n📋 Test 2: Get config")
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "get_config",
            "params": {},
        }
        response = send_request(sock, request)
        print(f"Response: {json.dumps(response, indent=2, ensure_ascii=False)[:500]}...")

        # Test 3: Model status
        print("\n📋 Test 3: Model status")
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "model_status",
            "params": {},
        }
        response = send_request(sock, request)
        print(f"Response: {json.dumps(response, indent=2, ensure_ascii=False)}")

        # Test 4: Unknown method (error handling)
        print("\n📋 Test 4: Unknown method (error handling)")
        request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "unknown_method",
            "params": {},
        }
        response = send_request(sock, request)
        print(f"Response: {json.dumps(response, indent=2)}")

        # Test 5: Invalid JSON-RPC (error handling)
        print("\n📋 Test 5: Invalid JSON-RPC (error handling)")
        request = {
            "id": 5,
            "method": "health",
            "params": {},
        }
        response = send_request(sock, request)
        print(f"Response: {json.dumps(response, indent=2)}")

        # Test 6: Notification (no response expected)
        print("\n📋 Test 6: Notification (no response expected)")
        request = {
            "jsonrpc": "2.0",
            "method": "set_recording_mode",
            "params": {"mode": "continuous"},
        }
        # Notification has no "id", so no response expected
        request_line = json.dumps(request) + "\n"
        sock.sendall(request_line.encode("utf-8"))
        print("Notification sent (no response expected)")

        print("\n✅ All tests completed")

    except FileNotFoundError:
        print(f"❌ Socket file not found: {socket_path}")
        print("   Make sure socket_server.py is running")
        sys.exit(1)
    except ConnectionRefusedError:
        print(f"❌ Connection refused: {socket_path}")
        print("   Make sure socket_server.py is running")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        try:
            sock.close()
            print("\n🔌 Connection closed")
        except Exception:
            pass


if __name__ == "__main__":
    test_socket_client()
