#!/usr/bin/env python3
"""
Speekium Socket Server - Socket-based JSON-RPC 2.0 server
Replaces stdin/stdout communication with Unix socket / Named Pipe

Supported platforms:
- macOS/Linux: Unix Domain Socket (/tmp/speekium-daemon.sock)
- Windows: Named Pipe (\\\\.\\pipe\\speekium-daemon)

Architecture:
- Command Socket: Python (server) <- Rust (client) for RPC commands
- Notification Socket: Python (client) -> Rust (server) for async events
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
    """Get command socket path based on platform"""
    if platform.system() == "Windows":
        return r"\\.\pipe\speekium-daemon"
    else:
        return "/tmp/speekium-daemon.sock"


def get_notification_socket_path() -> str:
    """Get notification socket path based on platform

    This is a separate socket where Python connects as client
    and Rust listens as server for receiving async notifications.
    """
    if platform.system() == "Windows":
        return r"\\.\pipe\speekium-notif"
    else:
        return "/tmp/speekium-notif.sock"


def cleanup_old_socket(socket_path: str) -> bool:
    """Clean up old socket file if exists

    Returns True if socket was cleaned up (stale), False if it's active or doesn't exist
    """
    if platform.system() != "Windows" and os.path.exists(socket_path):
        try:
            # Try to connect to check if socket is actually in use
            test_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            test_socket.settimeout(0.1)
            try:
                test_socket.connect(socket_path)
                # Connection succeeded = socket is active
                test_socket.close()
                logger.warning(f"socket_in_use: path={socket_path}, action=keep")
                return False
            except (TimeoutError, ConnectionRefusedError, ConnectionResetError, OSError):
                # Socket file exists but no one listening = stale
                test_socket.close()
                os.remove(socket_path)
                logger.info(f"stale_socket_removed: path={socket_path}")
                return True
        except Exception as e:
            logger.warning(f"socket_cleanup_failed: error={e}")
            # If we can't determine, try to remove it anyway
            try:
                os.remove(socket_path)
                logger.info(f"force_socket_removed: path={socket_path}")
                return True
            except OSError:
                # Socket file might be in use or already removed
                return False
    return False


# ===== JSON-RPC 2.0 Types =====


def create_response(request_id: Any, result: Any = None, error: Optional[dict] = None) -> dict:
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
    """Socket-based JSON-RPC 2.0 server with cross-platform support

    Architecture:
    - Command Socket: Python (server) <- Rust (client) for RPC commands
    - Notification Socket: Python (client) -> Rust (server) for async events
    """

    def __init__(self, socket_path: str, daemon_handler):
        """
        Initialize socket server

        Args:
            socket_path: Socket path for command server (platform-dependent)
            daemon_handler: SpeekiumDaemon instance with async handle methods
        """
        self.socket_path = socket_path
        self.daemon = daemon_handler
        self.running = False
        self.server_socket: Optional[socket.socket] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.is_windows = platform.system() == "Windows"
        # Lock to serialize config access and prevent race conditions
        self._config_lock = asyncio.Lock()
        # Cache for config responses to reduce daemon load
        self._config_cache = None
        self._config_cache_time = 0
        self._cache_ttl = 1.0  # Cache config for 1 second
        # Track connected clients for broadcasting notifications (legacy, deprecated)
        self._clients = set()
        # Maximum message size to prevent DoS (10MB)
        self._max_message_size = 10 * 1024 * 1024

        # Notification client for sending async events to Rust
        self._notification_socket: Optional[socket.socket] = None
        self._notification_socket_path = get_notification_socket_path()
        self._notification_lock = asyncio.Lock()
        self._notification_connected = False
        # Background task for maintaining notification socket connection
        self._notification_reconnect_task: Optional[asyncio.Task] = None
        # Pending notifications queue (sent when connection is restored)
        self._pending_notifications: list = []
        self._pending_notifications_max = 100  # Max pending notifications to queue

        logger.info(
            f"socket_server_initializing: socket_path={socket_path}, "
            f"notification_path={self._notification_socket_path}, platform={platform.system()}"
        )

    async def start(self):
        """Start socket server (async, blocking)"""
        try:
            # Clean up old socket
            cleanup_old_socket(self.socket_path)

            # Get event loop
            self.loop = asyncio.get_running_loop()

            # Create and bind command socket
            self._setup_socket()

            # Connect to notification socket (Rust server, Python client)
            await self._connect_notification_socket()

            # Start background reconnection task for notification socket
            self._notification_reconnect_task = asyncio.create_task(
                self._notification_maintenance_loop()
            )

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

        # IMPORTANT: Set socket to non-blocking mode for sock_accept to work
        self.server_socket.setblocking(False)

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
        # Assert that loop and server_socket are initialized
        assert self.loop is not None
        assert self.server_socket is not None
        # Accept connections loop
        logger.info("accept_loop_started")

        # Remove old reader if any
        try:
            self.loop.remove_reader(self.server_socket.fileno())
        except OSError:
            pass

        def on_readable():
            assert self.server_socket is not None
            try:
                client_socket, _ = self.server_socket.accept()
                logger.info("client_connected")
                # Track client for broadcasting
                self._clients.add(client_socket)
                # Handle client in background task
                asyncio.create_task(self._handle_client_unix(client_socket))
            except BlockingIOError:
                # No connection pending, this is fine
                pass
            except Exception as e:
                logger.error(f"accept_error: error={str(e)}")

        # Register the socket with the event loop
        self.loop.add_reader(self.server_socket.fileno(), on_readable)

        # Keep the loop running
        while self.running:
            try:
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                logger.info("accept_loop_cancelled")
                break
            except Exception as e:
                logger.error(f"accept_loop_sleep_error: error={str(e)}")
                break

        # Remove reader when stopping
        try:
            self.loop.remove_reader(self.server_socket.fileno())
        except OSError:
            pass

        logger.info("accept_loop_ended")

    async def _accept_loop_named_pipe(self):
        """Accept connections loop for Windows (TCP socket fallback)"""
        # Assert that loop and server_socket are initialized
        assert self.loop is not None
        assert self.server_socket is not None
        # Use the same TCP socket accept logic as Unix
        await self._accept_loop_unix()

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
            assert self.loop is not None
            assert self.server_socket is not None
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
        import time

        client_id = id(client_socket)
        request_count = 0
        start_time = time.time()

        logger.info(f"handle_client_started: client_id={client_id}")
        print(f"[Speekium-Python] Client connected (id={client_id})", flush=True)
        try:
            # Set socket timeout to 150 seconds to handle long operations (PTT ASR+LLM+TTS)
            # while still allowing connection cleanup if client disappears
            # This is longer than the client timeout (120s) to avoid server closing first
            client_socket.settimeout(150.0)

            # Read data
            data = b""
            logger.info(f"client_waiting_for_data: client_id={client_id}")
            while self.running:
                try:
                    chunk = client_socket.recv(8192)
                    if not chunk:
                        logger.info(
                            f"client_eof: client_id={client_id}, requests={request_count}, duration={time.time() - start_time:.2f}s"
                        )
                        print(
                            f"[Speekium-Python] Client EOF (id={client_id}, requests={request_count})",
                            flush=True,
                        )
                        break
                    data += chunk
                    logger.info(
                        f"received_chunk: client_id={client_id}, bytes={len(chunk)}, total={len(data)}"
                    )

                    # Check for message size limit to prevent DoS
                    if len(data) > self._max_message_size:
                        logger.error(
                            f"message_too_large: client_id={client_id}, size={len(data)}, max={self._max_message_size}"
                        )
                        error = create_error(
                            -32600,
                            "Message too large",
                            f"Maximum size is {self._max_message_size} bytes",
                        )
                        response = create_response(None, error=error)
                        try:
                            client_socket.sendall((json.dumps(response) + "\n").encode())
                        except Exception:
                            pass
                        break

                    # Process complete messages (newline-delimited)
                    while b"\n" in data:
                        line, data = data.split(b"\n", 1)
                        if not line:
                            continue

                        request_count += 1
                        method = "unknown"
                        try:
                            request = json.loads(line.decode())
                            method = request.get("method", "unknown")
                            logger.info(
                                f"processing_request: client_id={client_id}, req={request_count}, method={method}"
                            )
                        except json.JSONDecodeError as e:
                            logger.error(f"json_decode_error: client_id={client_id}, error={e}")
                            error = create_error(-32700, "Parse error", str(e))
                            response = create_response(None, error=error)
                            client_socket.sendall((json.dumps(response) + "\n").encode())
                            continue

                        # Process request
                        response = await self._handle_request(request)

                        # Send response
                        response_str = json.dumps(response) + "\n"
                        client_socket.sendall(response_str.encode())
                        logger.info(
                            f"response_sent: client_id={client_id}, req={request_count}, method={method}, bytes={len(response_str)}"
                        )

                except TimeoutError:
                    # Socket timeout - client hasn't sent data in 60s, check if still connected
                    logger.info(
                        f"socket_timeout: client_id={client_id}, duration={time.time() - start_time:.2f}s"
                    )
                    continue
                except Exception as e:
                    logger.error(f"client_handler_error: client_id={client_id}, error={str(e)}")
                    import traceback

                    traceback.print_exc(file=sys.stderr)
                    break

        finally:
            duration = time.time() - start_time
            # Remove client from tracking set
            self._clients.discard(client_socket)
            client_socket.close()
            logger.info(
                f"client_disconnected: client_id={client_id}, requests={request_count}, duration={duration:.2f}s"
            )
            print(
                f"[Speekium-Python] Client disconnected (id={client_id}, req={request_count}, dur={duration:.2f}s)",
                flush=True,
            )

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
                # Use lock to serialize config access - prevents race conditions
                # when multiple clients request config simultaneously
                import time as time_module

                async with self._config_lock:
                    current_time = time_module.time()
                    if (
                        self._config_cache is not None
                        and current_time - self._config_cache_time < self._cache_ttl
                    ):
                        logger.info(
                            f"config_cache_hit: age={current_time - self._config_cache_time:.2f}s"
                        )
                        result = self._config_cache
                    else:
                        result = await self.daemon.handle_config()
                        self._config_cache = result
                        self._config_cache_time = current_time
                        logger.info("config_cache_miss: caching result")
            elif method == "save_config":
                # Use lock to serialize config save and invalidate cache
                async with self._config_lock:
                    result = await self.daemon.handle_save_config(params)
                    # Clear config cache
                    self._config_cache = None
                    self._config_cache_time = 0
                    logger.info("config_cache_invalidated")
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
                    request_id, error=create_error(-32601, "Method not found", {"method": method})
                )

            return create_response(request_id, result=result)

        except Exception as e:
            logger.error(f"method_error: method={method}, error={str(e)}")
            traceback.print_exc(file=sys.stderr)
            return create_response(request_id, error=create_error(-32603, "Internal error", str(e)))

    def broadcast_notification(self, method: str, params: dict):
        """Broadcast a JSON-RPC notification to all connected clients

        This now uses the dedicated notification socket (Python->Rust)
        instead of broadcasting to command socket clients.

        Args:
            method: Notification method name (e.g., "download_progress", "ptt_event")
            params: Notification parameters
        """
        # Use the dedicated notification socket (unidirectional: Python -> Rust)
        if self._send_notification_via_socket(method, params):
            return

        # Fallback: try legacy broadcast to command socket clients
        if not self._clients:
            logger.debug(f"no_clients_to_notify: method={method}")
            return

        # Create JSON-RPC notification
        notification = {"jsonrpc": "2.0", "method": method, "params": params}
        notification_str = json.dumps(notification) + "\n"
        notification_bytes = notification_str.encode()

        # Broadcast to all clients
        failed_clients = set()
        success_count = 0

        for client in list(self._clients):
            try:
                client.sendall(notification_bytes)
                success_count += 1
            except Exception as e:
                logger.warning(f"notification_send_failed: client={id(client)}, error={str(e)}")
                failed_clients.add(client)

        # Remove failed clients
        self._clients -= failed_clients

        logger.info(
            f"notification_broadcast: method={method}, "
            f"success={success_count}, failed={len(failed_clients)}, "
            f"active_clients={len(self._clients)}"
        )

    async def _connect_notification_socket(self) -> bool:
        """Connect to the notification socket (Rust server, Python client)

        This socket is used for sending async events (PTT events, download progress)
        from Python to Rust without blocking command responses.

        Returns:
            True if connection succeeded, False otherwise
        """
        max_retries = 1200  # 120 seconds (1200 * 0.1s) - matches startup timeout
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                if self.is_windows:
                    # Windows: use TCP to localhost
                    # Read port from file if it exists
                    port_file = os.path.expanduser("~/.speekium-notification-port")
                    if os.path.exists(port_file):
                        with open(port_file, "r") as f:
                            port = int(f.read().strip())
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.connect(("127.0.0.1", port))
                    else:
                        # Fall back to direct pipe connection
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.bind(("127.0.0.1", 0))
                else:
                    # Unix socket
                    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    sock.settimeout(5.0)
                    sock.connect(self._notification_socket_path)
                    sock.settimeout(None)  # Remove timeout after connect

                self._notification_socket = sock
                self._notification_connected = True
                logger.info(f"notification_socket_connected: path={self._notification_socket_path}")
                return True

            except (FileNotFoundError, ConnectionRefusedError) as e:
                # Rust server not ready yet, retry
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    logger.warning(
                        f"notification_socket_connect_timeout: "
                        f"path={self._notification_socket_path}, "
                        f"this is OK if Rust hasn't started the notification listener yet"
                    )
                    # Don't fail - the daemon can still work without notifications
                    return False

            except Exception as e:
                logger.error(f"notification_socket_connect_error: error={e}")
                return False

        return False

    async def _send_notification_via_socket_async(self, method: str, params: dict) -> bool:
        """Send a notification via the dedicated notification socket (async with retry)

        This async version properly waits for reconnection before sending.

        Args:
            method: Notification method name (e.g., "download_progress", "ptt_event")
            params: Notification parameters

        Returns:
            True if send succeeded, False otherwise
        """
        max_retries = 3

        for attempt in range(max_retries):
            # Check if connected, try to reconnect if not
            needs_reconnect = not self._notification_connected or self._notification_socket is None
            if needs_reconnect:
                reconnected = await self._reconnect_notification_socket()
                if not reconnected:
                    logger.debug(
                        f"notification_reconnect_failed: attempt={attempt + 1}/{max_retries}"
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(0.1 * (attempt + 1))  # Exponential backoff
                        continue
                    return False

            # Socket should be connected at this point
            assert self._notification_socket is not None
            try:
                # Create JSON-RPC notification
                notification = {"jsonrpc": "2.0", "method": method, "params": params}
                notification_str = json.dumps(notification) + "\n"
                notification_bytes = notification_str.encode()

                # Send to Rust via notification socket
                self._notification_socket.sendall(notification_bytes)
                logger.debug(f"notification_sent_via_socket: method={method}")
                return True

            except (ConnectionError, BrokenPipeError, OSError) as e:
                logger.warning(
                    f"notification_socket_send_failed: error={e}, attempt={attempt + 1}/{max_retries}"
                )
                self._notification_connected = False
                # Try again if we have retries left
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.1 * (attempt + 1))
                    continue
                return False
            except Exception as e:
                logger.warning(f"notification_socket_unexpected_error: error={e}")
                self._notification_connected = False
                return False

        return False

    def _send_notification_via_socket(self, method: str, params: dict) -> bool:
        """Send a notification via the dedicated notification socket (sync wrapper)

        This is a compatibility wrapper for legacy code. For critical notifications,
        use _send_notification_via_socket_async to ensure delivery.

        Args:
            method: Notification method name (e.g., "download_progress", "ptt_event")
            params: Notification parameters

        Returns:
            True if send succeeded or queued, False otherwise
        """
        if not self._notification_connected or self._notification_socket is None:
            # Queue notification for later sending when connection is restored
            if len(self._pending_notifications) < self._pending_notifications_max:
                self._pending_notifications.append((method, params))
                logger.debug(
                    f"notification_queued: method={method}, pending={len(self._pending_notifications)}"
                )
                return True  # Return True to indicate notification was accepted
            else:
                logger.warning(
                    f"notification_queue_full: method={method}, max={self._pending_notifications_max}"
                )
                return False

        try:
            # Create JSON-RPC notification
            notification = {"jsonrpc": "2.0", "method": method, "params": params}
            notification_str = json.dumps(notification) + "\n"
            notification_bytes = notification_str.encode()

            # Send to Rust via notification socket
            self._notification_socket.sendall(notification_bytes)
            logger.debug(f"notification_sent_via_socket: method={method}")
            return True

        except (ConnectionError, BrokenPipeError, OSError) as e:
            logger.warning(f"notification_socket_send_failed: error={e}")
            self._notification_connected = False
            # Queue for retry
            if len(self._pending_notifications) < self._pending_notifications_max:
                self._pending_notifications.append((method, params))
            return False
        except Exception as e:
            logger.warning(f"notification_socket_unexpected_error: error={e}")
            self._notification_connected = False
            return False

    async def _reconnect_notification_socket(self) -> bool:
        """Attempt to reconnect to the notification socket

        Returns True if reconnection succeeded, False otherwise
        """
        if self._notification_connected:
            return True
        return await self._connect_notification_socket()

    async def _notification_maintenance_loop(self):
        """Background task to maintain notification socket connection

        Periodically checks connection status and attempts reconnection if needed.
        Also flushes any pending notifications when connection is restored.
        """
        reconnect_interval = 5.0  # Check every 5 seconds

        while self.running:
            try:
                # Check if connected, try to reconnect if not
                was_disconnected = not self._notification_connected
                if was_disconnected and await self._connect_notification_socket():
                    # Connection restored, send pending notifications
                    await self._flush_pending_notifications()

                await asyncio.sleep(reconnect_interval)
            except asyncio.CancelledError:
                logger.info("notification_maintenance_loop_cancelled")
                break
            except Exception as e:
                logger.error(f"notification_maintenance_error: error={e}")
                await asyncio.sleep(reconnect_interval)

    async def _flush_pending_notifications(self):
        """Send all pending notifications after reconnection"""
        if not self._pending_notifications:
            return

        logger.info(f"flushing_pending_notifications: count={len(self._pending_notifications)}")

        pending = self._pending_notifications.copy()
        self._pending_notifications.clear()

        for method, params in pending:
            try:
                await self._send_notification_via_socket_async(method, params)
            except Exception as e:
                logger.warning(f"pending_notification_send_failed: method={method}, error={e}")
                # Re-queue if failed
                self._pending_notifications.append((method, params))
                # Limit queue size
                if len(self._pending_notifications) > self._pending_notifications_max:
                    self._pending_notifications.pop(0)
                break

    def stop(self):
        """Stop the socket server"""
        self.running = False

        # Cancel background reconnection task
        if self._notification_reconnect_task and not self._notification_reconnect_task.done():
            self._notification_reconnect_task.cancel()
            logger.info("notification_reconnect_task_cancelled")

        # Close all client connections
        for client in list(self._clients):
            try:
                client.close()
            except Exception:
                pass
        self._clients.clear()
        logger.info(f"client_connections_closed: count={len(self._clients)}")

        if self.server_socket:
            try:
                self.server_socket.close()
                logger.info("server_socket_closed")
            except Exception as e:
                logger.warning(f"socket_close_error: error={e}")

        # Close notification socket
        if self._notification_socket:
            try:
                self._notification_socket.close()
                logger.info("notification_socket_closed")
            except Exception as e:
                logger.warning(f"notification_socket_close_error: error={e}")

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
