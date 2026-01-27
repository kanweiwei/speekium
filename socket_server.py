#!/usr/bin/env python3
"""
Speekium Socket Server - Socket-based JSON-RPC 2.0 server
Replaces stdin/stdout communication with Unix socket / Named Pipe

Supported platforms:
- macOS/Linux: Unix Domain Socket (/tmp/speekium-daemon.sock)
- Windows: Named Pipe (\\\\.\\pipe\\speekium-daemon)
"""

import asyncio
import json
import logging
import os
import platform
import socket
import sys
import traceback
from typing import Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ===== Platform Detection =====
def get_socket_path() -> str:
    """Get socket path based on platform"""
    if platform.system() == "Windows":
        return r"\\.\pipe\speekium-daemon"
    else:
        return "/tmp/speekium-daemon.sock"


def cleanup_old_socket(socket_path: str):
    """Clean up old socket file if exists"""
    if platform.system() != "Windows" and os.path.exists(socket_path):
        try:
            os.remove(socket_path)
            logger.info(f"old_socket_removed: path={socket_path}")
        except Exception as e:
            logger.warning(f"socket_cleanup_failed: error={e}")


# ===== JSON-RPC 2.0 Types =====


def create_response(request_id: Any, result: Any = None, error: dict = None) -> dict:
    """Create JSON-RPC 2.0 response"""
    response = {"jsonrpc": "2.0", "id": request_id}

    if error:
        response["error"] = error
    else:
        response["result"] = result

    return response


def create_error(code: int, message: str, data: Any = None) -> dict:
    """Create JSON-RPC 2.0 error object"""
    error_dict = {"code": code, "message": message}
    if data is not None:
        error_dict["data"] = data
    return error_dict


# ===== Socket Server Implementation =====
class SocketServer:
    """Socket-based JSON-RPC 2.0 server with cross-platform support"""

    def __init__(self, socket_path: str, daemon_handler):
        """
        Initialize socket server

        Args:
            socket_path: Socket path (platform-dependent)
            daemon_handler: SpeekiumDaemon instance with async handle methods
        """
        self.socket_path = socket_path
        self.daemon = daemon_handler
        self.running = False
        self.server_socket: Optional[socket.socket] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.is_windows = platform.system() == "Windows"

        logger.info(
            f"socket_server_initializing: socket_path={socket_path}, platform={platform.system()}"
        )

    async def start(self):
        """Start socket server (async, blocking)"""
        try:
            # Clean up old socket
            cleanup_old_socket(self.socket_path)

            # Get event loop
            self.loop = asyncio.get_running_loop()

            # Create and bind socket
            self._setup_socket()

            self.running = True
            logger.info(f"socket_server_started: socket_path={self.socket_path}")

            # Start accepting connections (blocking loop)
            await self._accept_loop()

        except Exception as e:
            logger.error(f"socket_server_start_failed: error={e}")
            traceback.print_exc(file=sys.stderr)
            raise

    def _setup_socket(self):
        """Create and bind socket (non-blocking, can be called synchronously)"""
        # Need event loop for later use
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop yet, will set it in start()
            self.loop = None

        if self.is_windows:
            self._setup_named_pipe()
        else:
            self._setup_unix_socket()

    def _setup_unix_socket(self):
        """Create and bind Unix domain socket (macOS/Linux)"""
        # Create Unix socket
        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        # Set socket options
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Bind to socket path
        self.server_socket.bind(self.socket_path)

        # Set permissions (user read/write only)
        os.chmod(self.socket_path, 0o600)

        # Listen for connections
        self.server_socket.listen(5)

        logger.info(f"unix_socket_listening: path={self.socket_path}")

    async def _accept_loop(self):
        """Accept connections loop (runs in background)"""
        if self.is_windows:
            await self._accept_loop_named_pipe()
        else:
            await self._accept_loop_unix()

    async def _accept_loop_unix(self):
        """Accept connections loop for Unix socket"""
        # Accept connections loop
        logger.info("accept_loop_started")
        while self.running:
            try:
                logger.debug("accept_loop: waiting for connection...")
                # Accept new connection with small timeout to allow checking self.running
                # and yielding control to other tasks
                client_socket, _ = await asyncio.wait_for(
                    self.loop.sock_accept(self.server_socket), timeout=1.0
                )

                logger.info("client_connected")

                # Handle client in background task
                asyncio.create_task(self._handle_client_unix(client_socket))

            except asyncio.TimeoutError:
                # Timeout is normal, continue accepting
                continue
            except asyncio.CancelledError:
                logger.info("accept_loop_cancelled")
                break
            except Exception as e:
                if self.running:
                    logger.error(f"accept_error: error={str(e)}")
                    import traceback

                    traceback.print_exc(file=sys.stderr)
                break
        logger.info("accept_loop_ended")

    def _setup_named_pipe(self):
        """Create TCP socket for Windows (fallback for Named Pipe)"""
        # Use TCP socket on localhost as fallback for Windows
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("127.0.0.1", 0))  # Bind to random port

        # Get actual port number
        port = self.server_socket.getsockname()[1]
        logger.info(f"tcp_socket_bound: port={port}")

        # Write port to file for client to discover
        port_file = os.path.expanduser("~/.speekium-daemon-port")
        with open(port_file, "w") as f:
            f.write(str(port))

        self.server_socket.listen(5)

    async def _start_named_pipe(self):
        """Start Named Pipe server (Windows)

        Note: Python's built-in socket module doesn't support Named Pipes directly.
        On Windows, we'll use a TCP socket on localhost as fallback.
        """
        # Use TCP socket on localhost as fallback for Windows
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("127.0.0.1", 0))  # Bind to random port

        # Get actual port number
        port = self.server_socket.getsockname()[1]
        logger.info(f"tcp_socket_listening: port={port}")

        # Write port to file for client to discover
        port_file = os.path.expanduser("~/.speekium-daemon-port")
        with open(port_file, "w") as f:
            f.write(str(port))

        self.server_socket.listen(5)

        while self.running:
            try:
                client_socket, addr = await self.loop.sock_accept(self.server_socket)
                logger.info(f"client_connected: address={addr}")
                asyncio.create_task(self._handle_client_unix(client_socket))
            except Exception as e:
                if self.running:
                    logger.error(f"accept_error: error={str(e)}")
                break

    async def _handle_client_unix(self, client_socket: socket.socket):
        """Handle Unix socket client connection"""
        logger.info("handle_client_started")
        try:
            # Set socket timeout
            client_socket.settimeout(1.0)

            # Read data
            data = b""
            while self.running:
                try:
                    chunk = client_socket.recv(4096)
                    if not chunk:
                        logger.info("client_eof")
                        break
                    data += chunk
                    logger.info(f"received_chunk: {len(chunk)} bytes, total: {len(data)}")

                    # Process complete messages (newline-delimited)
                    while b"\n" in data:
                        line, data = data.split(b"\n", 1)
                        if not line:
                            continue

                        logger.info(f"processing_line: {line.decode()[:100]}")
                        try:
                            request = json.loads(line.decode())
                        except json.JSONDecodeError as e:
                            logger.error(f"json_decode_error: error={e}")
                            error = create_error(-32700, "Parse error", str(e))
                            response = create_response(None, error=error)
                            client_socket.sendall((json.dumps(response) + "\n").encode())
                            continue

                        # Process request
                        response = await self._handle_request(request)
                        logger.info(f"response: {json.dumps(response)[:200]}")

                        # Send response
                        response_str = json.dumps(response) + "\n"
                        client_socket.sendall(response_str.encode())
                        logger.info(f"response_sent: {len(response_str)} bytes")

                except TimeoutError:
                    # Timeout is normal for checking if client is still alive
                    continue
                except Exception as e:
                    logger.error(f"client_handler_error: error={str(e)}")
                    import traceback

                    traceback.print_exc(file=sys.stderr)
                    break

        finally:
            client_socket.close()
            logger.info("client_disconnected")

    async def _handle_request(self, request: dict) -> dict:
        """Handle JSON-RPC 2.0 request"""
        # Validate request
        if not isinstance(request, dict):
            return create_response(None, error=create_error(-32600, "Invalid Request"))

        if "jsonrpc" not in request or request["jsonrpc"] != "2.0":
            return create_response(None, error=create_error(-32600, "Invalid Request"))

        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        if not isinstance(method, str):
            return create_response(request_id, error=create_error(-32600, "Invalid Request"))

        # Check if daemon is initialized
        # For health check, return "initializing" status if models not loaded
        if method == "health":
            if self.daemon.assistant is None:
                return create_response(
                    request_id,
                    result={
                        "success": True,
                        "status": "initializing",
                        "models_loaded": {"vad": False, "asr": False, "llm": False},
                    },
                )
            return create_response(request_id, result=await self.daemon.handle_health())

        # For other methods, wait for initialization
        max_wait = 60  # seconds
        wait_start = asyncio.get_event_loop().time()
        while self.daemon.assistant is None:
            if asyncio.get_event_loop().time() - wait_start > max_wait:
                return create_response(
                    request_id, error=create_error(-32603, "Initialization timeout")
                )
            await asyncio.sleep(0.5)

        # Route to handler
        try:
            if method == "record":
                result = await self.daemon.handle_record(**params)
            elif method == "chat":
                result = await self.daemon.handle_chat(**params)
            elif method == "tts":
                result = await self.daemon.handle_tts(**params)
            elif method == "config":
                result = await self.daemon.handle_config()
            elif method == "save_config":
                result = await self.daemon.handle_save_config(params)
            elif method == "model_status":
                result = await self.daemon.handle_model_status()
            elif method == "interrupt":
                result = await self.daemon.handle_interrupt(**params)
            elif method == "get_daemon_state":
                result = await self.daemon.handle_get_daemon_state()
            elif method == "set_recording_mode":
                result = await self.daemon.handle_command("set_recording_mode", params)
            elif method == "shutdown":
                result = {"success": True}
                # Stop the accept loop
                self.running = False
                # Close server socket to unblock sock_accept
                if self.server_socket:
                    try:
                        self.server_socket.close()
                    except Exception:
                        pass
                return create_response(request_id, result=result)
            else:
                return create_response(
                    request_id, error=create_error(-32601, "Method not found", method=method)
                )

            return create_response(request_id, result=result)

        except Exception as e:
            logger.error(f"method_error: method={method}, error={str(e)}")
            traceback.print_exc(file=sys.stderr)
            return create_response(request_id, error=create_error(-32603, "Internal error", str(e)))

    def stop(self):
        """Stop the socket server"""
        self.running = False

        if self.server_socket:
            try:
                self.server_socket.close()
                logger.info("server_socket_closed")
            except Exception as e:
                logger.warning(f"socket_close_error: error={e}")

        # Clean up socket file
        if not self.is_windows and os.path.exists(self.socket_path):
            try:
                os.remove(self.socket_path)
                logger.info("socket_file_removed")
            except Exception as e:
                logger.warning(f"socket_cleanup_error: error={e}")

        logger.info("socket_server_stopped")


# ===== Sync API for backward compatibility =====
def start_socket_server(socket_path: str, daemon_handler) -> SocketServer:
    """
    Start socket server (for use in existing worker_daemon)

    This is a blocking call that starts the async server.
    """
    server = SocketServer(socket_path, daemon_handler)

    # Run async server in new event loop
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        server.stop()
        logger.info("socket_server_interrupted")

    return server
