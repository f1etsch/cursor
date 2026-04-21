"""Keyboard key utilities."""

from __future__ import annotations

from pynput.keyboard import Key, KeyCode


def key_id(key: Key | KeyCode):
    if isinstance(key, KeyCode):
        if key.vk is not None:
            return ("vk", int(key.vk))
        if key.char:
            return ("char", key.char.lower())
        return None
    if isinstance(key, Key):
        vk = getattr(key, "value", None)
        vk_num = getattr(vk, "vk", None)
        if vk_num is not None:
            return ("vk", int(vk_num))
        return ("name", str(key))
    return None


def keys_equal(a, b) -> bool:
    return a == b


def key_display(k) -> str:
    if not k:
        return "—"
    t, v = k
    if t == "vk":
        return f"VK {v}"
    if t == "char":
        return str(v).upper()
    return str(v)
