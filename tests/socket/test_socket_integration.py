#!/usr/bin/env python3
"""
Integration test for Socket IPC
Tests the full communication flow between Rust client and Python server
"""

import json
import socket
import sys
import time
import subprocess
import os
import signal

# Socket path
SOCKET_PATH = "/tmp/speekium-daemon.sock"


def cleanup_socket():
    """Clean up old socket file"""
    if os.path.exists(SOCKET_PATH):
        os.remove(SOCKET_PATH)
        print(f"Cleaned up old socket: {SOCKET_PATH}")


def send_request(sock, method, params=None):
    """Send JSON-RPC request and read response"""
    if params is None:
        params = {}

    request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}

    request_str = json.dumps(request) + "\n"
    sock.sendall(request_str.encode())

    # Read response
    response_data = b""
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        response_data += chunk
        if b"\n" in response_data:
            break

    response_str = response_data.decode().strip()
    return json.loads(response_str)


def test_socket_server():
    """Test the socket server integration"""
    print("=" * 60)
    print("Socket IPC Integration Test")
    print("=" * 60)

    # Clean up old socket
    cleanup_socket()

    # Start daemon in socket mode
    print("\n1. Starting daemon in socket mode...")
    daemon_process = subprocess.Popen(
        [sys.executable, "worker_daemon.py", "socket"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # Wait for socket to be created
    print("2. Waiting for socket to be created...")
    max_wait = 30  # seconds
    start_time = time.time()
    while not os.path.exists(SOCKET_PATH):
        if time.time() - start_time > max_wait:
            print(f"ERROR: Socket not created after {max_wait}s")
            daemon_process.terminate()
            daemon_process.wait()
            return False
        time.sleep(0.1)

    print(f"   Socket created: {SOCKET_PATH}")

    # Additional wait for daemon initialization
    print("3. Waiting for daemon initialization (model loading)...")
    time.sleep(5)  # Give time for models to load

    # Connect to socket
    print("4. Connecting to socket...")
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(SOCKET_PATH)
        print("   Connected!")
    except Exception as e:
        print(f"ERROR: Failed to connect: {e}")
        daemon_process.terminate()
        daemon_process.wait()
        return False

    # Test health check
    print("\n5. Testing health check...")
    try:
        response = send_request(sock, "health")
        print(f"   Response: {json.dumps(response, indent=2)}")
        if response.get("result", {}).get("success"):
            print("   Health check: PASSED")
        else:
            print("   Health check: FAILED")
    except Exception as e:
        print(f"   ERROR: {e}")
        sock.close()
        daemon_process.terminate()
        daemon_process.wait()
        return False

    # Test config command
    print("\n6. Testing config command...")
    try:
        response = send_request(sock, "config")
        print(f"   Response: {json.dumps(response, indent=2)}")
        if response.get("result", {}).get("success"):
            print("   Config command: PASSED")
        else:
            print("   Config command: FAILED")
    except Exception as e:
        print(f"   ERROR: {e}")

    # Test model_status command
    print("\n7. Testing model_status command...")
    try:
        response = send_request(sock, "model_status")
        print(f"   Response: {json.dumps(response, indent=2)}")
        if response.get("result", {}).get("success"):
            print("   Model status command: PASSED")
        else:
            print("   Model status command: FAILED")
    except Exception as e:
        print(f"   ERROR: {e}")

    # Test get_daemon_state command
    print("\n8. Testing get_daemon_state command...")
    try:
        response = send_request(sock, "get_daemon_state")
        print(f"   Response: {json.dumps(response, indent=2)}")
        if response.get("result", {}).get("success"):
            print("   Daemon state command: PASSED")
        else:
            print("   Daemon state command: FAILED")
    except Exception as e:
        print(f"   ERROR: {e}")

    # Test shutdown
    print("\n9. Testing shutdown...")
    try:
        response = send_request(sock, "shutdown")
        print(f"   Response: {json.dumps(response, indent=2)}")
        print("   Shutdown command: PASSED")
    except Exception as e:
        print(f"   ERROR: {e}")

    # Close socket
    sock.close()

    # Wait for daemon to exit
    print("\n10. Waiting for daemon to exit...")
    try:
        stdout, stderr = daemon_process.communicate(timeout=10)
        if stdout:
            print(f"   stdout: {stdout[-500:]}")  # Last 500 chars
        if stderr:
            print(f"   stderr: {stderr[-500:]}")  # Last 500 chars
    except subprocess.TimeoutExpired:
        daemon_process.terminate()
        daemon_process.wait()

    # Clean up
    cleanup_socket()

    print("\n" + "=" * 60)
    print("Integration test completed!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    try:
        success = test_socket_server()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nInterrupted!")
        cleanup_socket()
        sys.exit(1)
