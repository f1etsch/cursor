"""Main UI app."""

from __future__ import annotations

import queue
import sys
import threading
import time
from pathlib import Path

import tkinter as tk
from tkinter import messagebox

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import config as cfg
from back.keys import key_display, key_id, keys_equal
from back.metrics import analyze_session
from back.recorder import TapRecorder
from front.chart import LiveTapChart

from pynput.keyboard import Key, KeyCode, Listener as KeyListener


class OsuStreamApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("BPM test")
        self.configure(bg=cfg.BG_MAIN)
        self.geometry("640x780")
        self.minsize(520, 720)

        self._mode = tk.StringVar(value="clicks")
        self._mouse_var = tk.BooleanVar(value=False)
        self._clicks_target = tk.StringVar(value="100")
        self._time_target = tk.StringVar(value="10")
        self._key1_spec = None
        self._key2_spec = None
        self._key1_lbl = tk.StringVar(value="—")
        self._key2_lbl = tk.StringVar(value="—")
        self._status = tk.StringVar(value="Настройте клавиши и нажмите Start.")
        self._testing = False
        self._events: list[tuple[float, int]] = []
        self._q: queue.SimpleQueue = queue.SimpleQueue()
        self._recorder: TapRecorder | None = None
        self._test_start_perf = 0.0
        self._bind_listener = None
        self._chart_window = None
        self._chart_popup = None

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _card(self, parent):
        return tk.Frame(parent, bg=cfg.BG_CARD, highlightbackground=cfg.BORDER, highlightthickness=1)

    def _build(self):
        outer = tk.Frame(self, bg=cfg.BG_MAIN)
        outer.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)
        tk.Label(outer, text="BPM test", font=(cfg.FONT_FAMILY, 18, "bold"), fg=cfg.ACCENT, bg=cfg.BG_MAIN).pack(anchor="w")

        card = self._card(outer)
        card.pack(fill=tk.X, pady=(10, 8))
        inner = tk.Frame(card, bg=cfg.BG_CARD)
        inner.pack(fill=tk.X, padx=14, pady=14)
        tk.Radiobutton(inner, text="Clicks", variable=self._mode, value="clicks", fg=cfg.TEXT, bg=cfg.BG_CARD, selectcolor=cfg.BG_INPUT).pack(anchor="w")
        tk.Radiobutton(inner, text="Time", variable=self._mode, value="time", fg=cfg.TEXT, bg=cfg.BG_CARD, selectcolor=cfg.BG_INPUT).pack(anchor="w")
        tk.Checkbutton(inner, text="Use mouse buttons (LMB=1, RMB=2)", variable=self._mouse_var, fg=cfg.TEXT, bg=cfg.BG_CARD, selectcolor=cfg.BG_INPUT).pack(anchor="w")
        self._entry_clicks = self._labeled_entry(inner, "Clicks", self._clicks_target)
        self._entry_time = self._labeled_entry(inner, "Seconds", self._time_target)
        self._row_key(inner, "Клавиша 1", self._key1_lbl, lambda: self._begin_bind(1))
        self._row_key(inner, "Клавиша 2", self._key2_lbl, lambda: self._begin_bind(2))
        self._btn_start = tk.Button(inner, text="Start", command=self._on_start_retry, fg=cfg.TEXT, bg=cfg.BTN_PRIMARY, relief=tk.FLAT)
        self._btn_start.pack(pady=(12, 0))

        tk.Label(outer, textvariable=self._status, fg=cfg.TEXT_DIM, bg=cfg.BG_MAIN, font=(cfg.FONT_FAMILY, 10)).pack(fill=tk.X, pady=(4, 8))
        res_card = self._card(outer)
        res_card.pack(fill=tk.BOTH, expand=True)
        res_inner = tk.Frame(res_card, bg=cfg.BG_CARD)
        res_inner.pack(fill=tk.BOTH, expand=True, padx=14, pady=14)

        tk.Label(res_inner, text="Результаты", fg=cfg.ACCENT, bg=cfg.BG_CARD, font=(cfg.FONT_FAMILY, 11, "bold")).pack(anchor="w")
        self._results = tk.Text(res_inner, height=8, wrap="word", font=(cfg.FONT_FAMILY, 10), fg=cfg.TEXT, bg=cfg.BG_INPUT, relief=tk.FLAT, state=tk.DISABLED)
        self._results.pack(fill=tk.X, expand=False, pady=(8, 10))
        tk.Button(res_inner, text="Открыть график в отдельном окне", command=self._open_chart_window, fg=cfg.TEXT, bg=cfg.BTN_MUTED, relief=tk.FLAT).pack(anchor="w")
        chart_host = tk.Frame(res_inner, bg=cfg.BG_CARD, height=280)
        chart_host.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        chart_host.pack_propagate(False)
        self._chart = LiveTapChart(chart_host)
        self._chart.pack(fill=tk.BOTH, expand=True)

    def _labeled_entry(self, parent, label, var):
        row = tk.Frame(parent, bg=cfg.BG_CARD)
        row.pack(fill=tk.X, pady=2)
        tk.Label(row, text=label, fg=cfg.TEXT_DIM, bg=cfg.BG_CARD).pack(side=tk.LEFT)
        e = tk.Entry(row, textvariable=var, width=12, fg=cfg.TEXT, bg=cfg.BG_INPUT, insertbackground=cfg.TEXT, relief=tk.FLAT)
        e.pack(side=tk.LEFT, padx=8)
        return e

    def _row_key(self, parent, title, var, cmd):
        row = tk.Frame(parent, bg=cfg.BG_CARD)
        row.pack(fill=tk.X, pady=4)
        tk.Label(row, text=title, fg=cfg.TEXT_DIM, bg=cfg.BG_CARD, width=10, anchor="w").pack(side=tk.LEFT)
        tk.Label(row, textvariable=var, fg=cfg.ACCENT, bg=cfg.BG_INPUT, width=14).pack(side=tk.LEFT, padx=6)
        tk.Button(row, text="Set", command=cmd, fg=cfg.TEXT, bg=cfg.BTN_MUTED, relief=tk.FLAT).pack(side=tk.LEFT)

    def _set_results_text(self, text: str) -> None:
        self._results.configure(state=tk.NORMAL)
        self._results.delete("1.0", tk.END)
        self._results.insert(tk.END, text)
        self._results.configure(state=tk.DISABLED)

    def _begin_bind(self, slot: int) -> None:
        if self._testing:
            return
        self._status.set(f"Нажмите клавишу {slot}…")
        result = []

        def on_press(key: Key | KeyCode):
            if key == Key.esc:
                result.append(None)
                return False
            kid = key_id(key)
            if kid is not None:
                result.append(kid)
                return False
            return True

        listener = KeyListener(on_press=on_press)
        self._bind_listener = listener

        def run():
            with listener:
                listener.join()
            kid = result[0] if result else None
            self.after(0, lambda: self._finish_bind(slot, kid))

        threading.Thread(target=run, daemon=True).start()

    def _finish_bind(self, slot, kid):
        self._bind_listener = None
        if kid is None:
            self._status.set("Привязка отменена.")
            return
        other = self._key2_spec if slot == 1 else self._key1_spec
        if other is not None and keys_equal(kid, other):
            messagebox.showwarning("Дубликат", "Выберите другую клавишу.")
            return
        if slot == 1:
            self._key1_spec = kid
            self._key1_lbl.set(key_display(kid))
        else:
            self._key2_spec = kid
            self._key2_lbl.set(key_display(kid))
        self._status.set("Клавиша сохранена.")

    def _parse_positive_int(self, s):
        try:
            v = int(s.strip())
            return v if v >= 1 else None
        except Exception:
            return None

    def _on_start_retry(self):
        if self._testing:
            return
        if self._key1_spec is None or self._key2_spec is None:
            messagebox.showwarning("Клавиши", "Задайте обе клавиши.")
            return
        if self._mode.get() == "clicks":
            n = self._parse_positive_int(self._clicks_target.get())
            if n is None:
                return
            self._start_test(clicks_target=n, time_limit_sec=None)
        else:
            t = self._parse_positive_int(self._time_target.get())
            if t is None:
                return
            self._start_test(clicks_target=None, time_limit_sec=float(t))

    def _start_test(self, clicks_target, time_limit_sec):
        self._testing = True
        self._events.clear()
        self._chart.clear()
        self._set_results_text("Тест идёт…")
        self._btn_start.configure(state=tk.DISABLED)
        self._entry_clicks.configure(state=tk.DISABLED)
        self._entry_time.configure(state=tk.DISABLED)
        self._test_start_perf = time.perf_counter()
        self._recorder = TapRecorder(self._key1_spec, self._key2_spec, self._mouse_var.get(), self._q)
        self._recorder.start()
        self._poll_args = (clicks_target, time_limit_sec)
        self.after(16, self._poll_session)

    def _finish_test(self):
        self._testing = False
        if self._recorder:
            self._recorder.stop()
            self._recorder = None
        while not self._q.empty():
            self._drain_one(self._q.get_nowait())
        self._btn_start.configure(state=tk.NORMAL)
        self._entry_clicks.configure(state=tk.NORMAL)
        self._entry_time.configure(state=tk.NORMAL)
        a = analyze_session(self._events)
        lines = [
            f"Нажатий: {a.tap_count}",
            f"Длительность: {a.duration_sec:.3f} s",
            f"Stream Speed (YSAS): {a.stream_speed_bpm:.2f} bpm",
            f"Unstable Rate: {a.unstable_rate:.3f}",
            f"BPM стрима (YSAS x1): {a.stream_bpm:.2f}" if a.stream_bpm is not None else "BPM стрима (YSAS x1): —",
            f"BPM джампов (YSAS x2): {a.jump_bpm:.2f}" if a.jump_bpm is not None else "BPM джампов (YSAS x2): — (bpm/2, в 2 раза меньше)",
            "",
            "Тест завершён.",
        ]
        self._set_results_text("\n".join(lines))
        self._chart.set_events(self._events)
        if self._chart_popup is not None:
            self._chart_popup.set_events(self._events)

    def _drain_one(self, item):
        if not item or item[0] != "tap":
            return
        _, slot, t = item
        self._events.append((t, slot))
        self._chart.set_events(self._events)
        if self._chart_popup is not None:
            self._chart_popup.set_events(self._events)

    def _poll_session(self):
        if not self._testing:
            return
        clicks_target, time_limit_sec = self._poll_args
        try:
            while True:
                self._drain_one(self._q.get_nowait())
        except queue.Empty:
            pass
        done = False
        if clicks_target is not None and len(self._events) >= clicks_target:
            done = True
        if time_limit_sec is not None and (time.perf_counter() - self._test_start_perf) >= time_limit_sec:
            done = True
        if done:
            self._finish_test()
        else:
            self.after(16, self._poll_session)

    def _open_chart_window(self):
        if self._chart_window is not None and self._chart_window.winfo_exists():
            self._chart_window.lift()
            return
        win = tk.Toplevel(self)
        win.title("График нажатий")
        win.geometry("960x520")
        win.minsize(700, 360)
        host = tk.Frame(win, bg=cfg.BG_MAIN)
        host.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        popup_chart = LiveTapChart(host)
        popup_chart.pack(fill=tk.BOTH, expand=True)
        popup_chart.set_events(self._events)
        self._chart_window = win
        self._chart_popup = popup_chart

        def close():
            self._chart_window = None
            self._chart_popup = None
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", close)

    def _on_close(self):
        self._testing = False
        if self._recorder:
            self._recorder.stop()
        if self._bind_listener:
            try:
                self._bind_listener.stop()
            except Exception:
                pass
        self.destroy()


def main() -> None:
    app = OsuStreamApp()
    app.mainloop()
