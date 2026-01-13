"""
Speekium Global Hotkey Manager
Cross-platform global hotkey listener with dynamic hotkey updates
"""

import platform
import threading
from collections.abc import Callable


class HotkeyManager:
    """Global hotkey manager"""

    def __init__(self):
        self.listener = None
        self.is_running = False
        self._lock = threading.Lock()

        # Current hotkey configuration
        self.current_hotkey_config = None

        # Hotkey state
        self.modifier_pressed = False
        self.main_key_pressed = False
        self.was_triggered = False  # Prevent duplicate triggers

        # Currently active keys (for dynamic updates)
        self.active_modifier_key = None
        self.active_main_key = None

        # Callback functions
        self.on_hotkey_press = None
        self.on_hotkey_release = None

        # Detect operating system
        self.is_macos = platform.system() == "Darwin"

    def parse_hotkey_config(self, config: dict) -> tuple:
        """
        Parse hotkey configuration to pynput format

        Args:
            config: dict with structure {
                'modifiers': ['CmdOrCtrl', 'Shift'],
                'key': 'Digit1'
            }

        Returns:
            tuple: (modifier_key_name, main_key_char)
        """
        from pynput import keyboard

        modifiers = config.get('modifiers', [])
        key_code = config.get('key', 'Digit1')

        # Determine main modifier key
        modifier_key = None
        if 'CmdOrCtrl' in modifiers:
            modifier_key = keyboard.Key.cmd if self.is_macos else keyboard.Key.ctrl
        elif 'Shift' in modifiers:
            modifier_key = keyboard.Key.shift
        elif 'Alt' in modifiers:
            modifier_key = keyboard.Key.alt

        # Parse main key
        main_key_char = None
        if key_code.startswith('Digit'):
            main_key_char = key_code.replace('Digit', '')
        elif key_code.startswith('Key'):
            main_key_char = key_code.replace('Key', '').lower()
        else:
            # Special key
            main_key_char = key_code.lower()

        return (modifier_key, main_key_char)

    def start(self, hotkey_config: dict | None = None, on_press: Callable | None = None, on_release: Callable | None = None):
        """
        Start global hotkey listener

        Args:
            hotkey_config: dict with hotkey configuration
            on_press: Callback when hotkey is pressed
            on_release: Callback when hotkey is released
        """
        with self._lock:
            if self.is_running:
                print("⚠️ Hotkey listener is already running")
                return

            # Set default hotkey config if not provided
            if hotkey_config is None:
                hotkey_config = {
                    'modifiers': ['CmdOrCtrl'],
                    'key': 'Digit1',
                    'displayName': '⌘1'
                }

            self.current_hotkey_config = hotkey_config
            self.on_hotkey_press = on_press
            self.on_hotkey_release = on_release

            try:
                from pynput import keyboard

                # Parse hotkey configuration
                self.active_modifier_key, self.active_main_key = self.parse_hotkey_config(hotkey_config)

                def on_key_press(key):
                    try:
                        # Update modifier key state
                        is_modifier = False
                        if self.active_modifier_key:
                            if key == self.active_modifier_key:
                                self.modifier_pressed = True
                                is_modifier = True

                        # Update main key state
                        is_main_key = False
                        if hasattr(key, 'char') and key.char == self.active_main_key:
                            self.main_key_pressed = True
                            is_main_key = True

                        # Check complete hotkey combination
                        self._check_hotkey_combination()

                    except Exception as e:
                        print(f"⚠️ Key press error: {e}")

                def on_key_release(key):
                    try:
                        # Update modifier key state
                        released_modifier = self.active_modifier_key and key == self.active_modifier_key
                        released_main = hasattr(key, 'char') and key.char == self.active_main_key

                        if released_modifier:
                            self.modifier_pressed = False
                        elif released_main:
                            self.main_key_pressed = False

                        # Trigger release callback if modifier or main key released
                        if (released_modifier or released_main) and self.was_triggered:
                            self._check_hotkey_release()

                    except Exception as e:
                        print(f"⚠️ Key release error: {e}")

                # Create listener
                self.listener = keyboard.Listener(on_press=on_key_press, on_release=on_key_release)

                # Start listener
                self.listener.start()
                self.is_running = True

                # Note: Removed print to avoid interfering with daemon JSON responses
                # Logger will be added by the caller

            except ImportError:
                # Note: These prints only show on error
                print("❌ pynput not installed, cannot use global hotkeys")
                print("   Install with: pip install pynput")
                return
            except Exception as e:
                # Note: This print only shows on error
                print(f"❌ Failed to start hotkey listener: {e}")
                return

    def update_hotkey(self, new_hotkey_config: dict) -> tuple[bool, str | None]:
        """
        Dynamically update hotkey configuration

        Args:
            new_hotkey_config: dict with new hotkey configuration

        Returns:
            tuple[bool, str | None]: (success, error_message)
                - success: True if update succeeded, False otherwise
                - error_message: Error message if failed, None otherwise
        """
        try:
            # Save callback functions (outside lock to avoid deadlock)
            with self._lock:
                on_press = self.on_hotkey_press
                on_release = self.on_hotkey_release
                is_running = self.is_running

            # Stop and start outside lock to avoid deadlock
            if is_running:
                self.stop()

            self.start(new_hotkey_config, on_press, on_release)

            return True, None
        except Exception as e:
            return False, str(e)

    def stop(self):
        """Stop hotkey listener"""
        with self._lock:
            if self.listener:
                self.listener.stop()
                self.listener = None
            self.is_running = False
            self.modifier_pressed = False
            self.main_key_pressed = False
            self.was_triggered = False
            # Note: Removed print to avoid interfering with daemon JSON responses

    def _check_hotkey_combination(self):
        """Check if complete hotkey combination is pressed"""
        is_hotkey_active = self.modifier_pressed and self.main_key_pressed

        if is_hotkey_active and not self.was_triggered and self.on_hotkey_press:
            try:
                self.was_triggered = True
                self.on_hotkey_press()
            except Exception as e:
                print(f"⚠️ Hotkey press callback error: {e}")

    def _check_hotkey_release(self):
        """Check if hotkey is released"""
        # Trigger when any key is released
        if self.was_triggered and self.on_hotkey_release:
            try:
                self.was_triggered = False
                self.on_hotkey_release()
            except Exception as e:
                print(f"⚠️ Hotkey release callback error: {e}")

    def is_hotkey_active(self) -> bool:
        """Check if hotkey is currently active"""
        return self.modifier_pressed and self.main_key_pressed
