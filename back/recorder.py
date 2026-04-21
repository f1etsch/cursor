"""Low-level tap recorder (keyboard + optional mouse)."""

from __future__ import annotations

import queue
import threading
import time

from pynput import mouse
from pynput.keyboard import KeyCode, Listener as KeyListener
from pynput.mouse import Button, Listener as MouseListener


class TapRecorder:
    def __init__(self, key1_spec, key2_spec, use_mouse: bool, out_q: queue.SimpleQueue) -> None:
        self.key1_spec = key1_spec
        self.key2_spec = key2_spec
        self.use_mouse = use_mouse
        self.out_q = out_q
        self._running = False
        self._key_listener: KeyListener | None = None
        self._mouse_listener: MouseListener | None = None
        self._thread: threading.Thread | None = None

    def _slot_for_key(self, key) -> int | None:
        if isinstance(key, KeyCode):
            kid = ("vk", key.vk) if key.vk is not None else ("char", key.char.lower() if key.char else None)
        else:
            value = getattr(getattr(key, "value", None), "vk", None)
            kid = ("vk", value) if value is not None else ("name", str(key))
        if kid == self.key1_spec:
            return 0
        if kid == self.key2_spec:
            return 1
        return None

    def start(self) -> None:
        self._running = True

        def on_press(key):
            if not self._running:
                return False
            slot = self._slot_for_key(key)
            if slot is not None:
                self.out_q.put(("tap", slot, time.perf_counter()))
            return True

        def on_click(_x, _y, button, pressed):
            if not self._running or not self.use_mouse or not pressed:
                return True
            if button == Button.left:
                self.out_q.put(("tap", 0, time.perf_counter()))
            elif button == Button.right:
                self.out_q.put(("tap", 1, time.perf_counter()))
            return True

        self._key_listener = KeyListener(on_press=on_press)
        self._key_listener.start()

        if self.use_mouse:
            self._mouse_listener = mouse.Listener(on_click=on_click)
            self._mouse_listener.start()

    def stop(self) -> None:
        self._running = False
        if self._key_listener:
            self._key_listener.stop()
        if self._mouse_listener:
            self._mouse_listener.stop()
