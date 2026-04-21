"""Live tap chart widget."""

from __future__ import annotations

import math
import tkinter as tk

import config as cfg


def _interval_series(events: list[tuple[float, int]]) -> tuple[list[float], list[float], list[bool], list[int]]:
    if len(events) < 2:
        return [], [], [], []
    t0 = events[0][0]
    xs: list[float] = []
    ys: list[float] = []
    stream: list[bool] = []
    slots: list[int] = []
    times = [e[0] for e in events]
    sl = [e[1] for e in events]
    for i in range(1, len(times)):
        dt = times[i] - times[i - 1]
        if dt <= 0:
            continue
        xs.append(times[i] - t0)
        ys.append(dt * 1000.0)
        stream.append((15.0 / dt) >= cfg.TAP_STREAM_BPM_THRESHOLD)
        slots.append(sl[i])
    return xs, ys, stream, slots


class LiveTapChart(tk.Canvas):
    def __init__(self, master: tk.Misc, **kw) -> None:
        kw.setdefault("highlightthickness", 0)
        kw.setdefault("bd", 0)
        kw.setdefault("bg", cfg.CHART_BG)
        super().__init__(master, **kw)
        self._events: list[tuple[float, int]] = []
        self._manual_zoom = False
        self._vx0 = 0.0
        self._vx1 = 1.0
        self._vy0 = 0.0
        self._vy1 = 200.0
        self._margin_l = 48
        self._margin_r = 14
        self._margin_t = 30
        self._margin_b = 36
        self._points: list[dict] = []
        self._drag_last = None
        self._rdrag_start_x = None
        self._rdrag_curr_x = None
        self._selection_stats = None
        self._hover_index = None
        self._hover_alpha = 0.0
        self._hover_anim_after = None

        self.bind("<Configure>", lambda e: self._redraw())
        self.bind("<MouseWheel>", self._on_wheel)
        self.bind("<Button-4>", lambda e: self._apply_zoom(e, 120))
        self.bind("<Button-5>", lambda e: self._apply_zoom(e, -120))
        self.bind("<Double-Button-1>", self._reset_zoom)
        self.bind("<ButtonPress-1>", self._on_lmb_down)
        self.bind("<B1-Motion>", self._on_lmb_drag)
        self.bind("<ButtonRelease-1>", lambda e: setattr(self, "_drag_last", None))
        self.bind("<ButtonPress-3>", self._on_rmb_down)
        self.bind("<B3-Motion>", self._on_rmb_drag)
        self.bind("<ButtonRelease-3>", self._on_rmb_up)
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", self._on_leave)

    def set_events(self, events: list[tuple[float, int]]) -> None:
        self._events = list(events)
        if not self._manual_zoom:
            self._fit_view_to_data()
        self._redraw()

    def clear(self) -> None:
        self._events.clear()
        self._manual_zoom = False
        self._points.clear()
        self._selection_stats = None
        self._rdrag_start_x = None
        self._rdrag_curr_x = None
        self._hover_index = None
        self._hover_alpha = 0.0
        self._fit_view_to_data()
        self._redraw()

    def _data_bounds(self):
        xs, ys, _, _ = _interval_series(self._events)
        if not xs:
            return 0.0, 1.0, 0.0, 200.0
        return 0.0, max(xs) + 1e-6, 0.0, max(ys) * 1.12 + 20.0

    def _fit_view_to_data(self) -> None:
        self._vx0, self._vx1, self._vy0, self._vy1 = self._data_bounds()

    def _reset_zoom(self, _event=None) -> None:
        self._manual_zoom = False
        self._fit_view_to_data()
        self._redraw()

    def _on_wheel(self, event) -> None:
        self._apply_zoom(event, int(getattr(event, "delta", 0)))

    def _apply_zoom(self, event, delta: int) -> None:
        if not delta:
            return
        w = max(self.winfo_width(), 80)
        h = max(self.winfo_height(), 80)
        x0 = self._margin_l
        y0 = self._margin_t
        plot_w = w - self._margin_l - self._margin_r
        plot_h = h - self._margin_t - self._margin_b
        if plot_w < 20 or plot_h < 20:
            return
        mx = float(event.x)
        my = float(event.y)
        if mx < x0 or mx > x0 + plot_w or my < y0 or my > y0 + plot_h:
            return
        step = delta / 120.0
        factor = max(0.4, min(math.exp(-0.18 * step), 2.5))
        frac_x = (mx - x0) / plot_w
        frac_y = (my - y0) / plot_h
        wx = self._vx1 - self._vx0
        wy = self._vy1 - self._vy0
        new_wx = wx * factor
        new_wy = wy * factor
        data_x = self._vx0 + frac_x * wx
        data_y_top = self._vy1 - frac_y * wy
        self._vx0 = data_x - frac_x * new_wx
        self._vx1 = data_x + (1.0 - frac_x) * new_wx
        self._vy1 = data_y_top + frac_y * new_wy
        self._vy0 = max(0.0, data_y_top - (1.0 - frac_y) * new_wy)
        self._manual_zoom = True
        self._redraw()

    def _redraw(self, _event=None) -> None:
        self.delete("all")
        w = max(self.winfo_width(), 80)
        h = max(self.winfo_height(), 80)
        x0 = self._margin_l
        y0 = self._margin_t
        plot_w = w - self._margin_l - self._margin_r
        plot_h = h - self._margin_t - self._margin_b
        self.create_text(w // 2, 14, text="Tap chart", fill=cfg.TEXT, font=(cfg.FONT_FAMILY, 10, "bold"))
        self.create_text(
            w // 2,
            26,
            text="Fast taps = stream (one color), slow taps = jump (key colors)",
            fill=cfg.TEXT_DIM,
            font=(cfg.FONT_FAMILY, 8),
        )
        self.create_rectangle(x0, y0, x0 + plot_w, y0 + plot_h, outline=cfg.CHART_GRID, width=1)

        xs, ys, streams, slots = _interval_series(self._events)
        if not xs:
            self.create_text(w // 2, h // 2, text="Waiting for taps...", fill=cfg.TEXT_DIM, font=(cfg.FONT_FAMILY, 10))
            return

        vx0, vx1, vy0, vy1 = self._vx0, self._vx1, self._vy0, self._vy1
        px = lambda t: x0 + (t - vx0) / (vx1 - vx0) * plot_w if vx1 > vx0 else x0
        py = lambda ms: y0 + plot_h - (ms - vy0) / (vy1 - vy0) * plot_h if vy1 > vy0 else y0 + plot_h
        y_base = py(vy0)
        self._points.clear()
        stress_flags = self._rhythm_stress_flags(ys)
        for t, ms, is_stream, slot, is_stressed in zip(xs, ys, streams, slots, stress_flags):
            if t < vx0 - 1e-9 or t > vx1 + 1e-9:
                continue
            cx = px(t)
            cy = py(ms)
            stem_color = "#ff2d2d" if is_stressed else (cfg.TAP_STEM_STREAM if is_stream else cfg.TAP_STEM_JUMP)
            self.create_line(cx, y_base, cx, cy, fill=stem_color, width=2)
            dot_fill = "#ff3030" if is_stressed else (cfg.TAP_DOT_STREAM if is_stream else (cfg.TAP_DOT_SLOT0 if slot == 0 else cfg.TAP_DOT_SLOT1))
            r = 5
            self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=dot_fill, outline=cfg.TEXT, width=1)
            self._points.append({"cx": cx, "cy": cy, "x": t, "ms": ms, "is_stream": is_stream})

        self._draw_selection_overlay(x0, y0, plot_w, plot_h)
        self._draw_hover_tooltip()

    def _rhythm_stress_flags(self, ys_ms: list[float]) -> list[bool]:
        flags: list[bool] = []
        for i, ms in enumerate(ys_ms):
            if i < 2:
                flags.append(False)
                continue
            prev_avg = (ys_ms[i - 1] + ys_ms[i - 2]) / 2.0
            flags.append(prev_avg > 1e-9 and abs(ms - prev_avg) / prev_avg >= 0.45)
        return flags

    def _on_lmb_down(self, event) -> None:
        self._drag_last = (float(event.x), float(event.y))

    def _on_lmb_drag(self, event) -> None:
        if self._drag_last is None:
            return
        lx, ly = self._drag_last
        nx, ny = float(event.x), float(event.y)
        w = max(self.winfo_width(), 80)
        h = max(self.winfo_height(), 80)
        plot_w = w - self._margin_l - self._margin_r
        plot_h = h - self._margin_t - self._margin_b
        if plot_w < 20 or plot_h < 20:
            return
        dx, dy = nx - lx, ny - ly
        wx = self._vx1 - self._vx0
        wy = self._vy1 - self._vy0
        self._vx0 -= dx / plot_w * wx
        self._vx1 -= dx / plot_w * wx
        self._vy0 = max(0.0, self._vy0 + dy / plot_h * wy)
        self._vy1 = max(self._vy0 + 10.0, self._vy1 + dy / plot_h * wy)
        self._drag_last = (nx, ny)
        self._manual_zoom = True
        self._redraw()

    def _on_rmb_down(self, event) -> None:
        self._rdrag_start_x = float(event.x)
        self._rdrag_curr_x = float(event.x)
        self._selection_stats = None
        self._redraw()

    def _on_rmb_drag(self, event) -> None:
        if self._rdrag_start_x is None:
            return
        self._rdrag_curr_x = float(event.x)
        self._redraw()

    def _xpix_to_time(self, xpix: float) -> float:
        w = max(self.winfo_width(), 80)
        plot_w = w - self._margin_l - self._margin_r
        frac = max(0.0, min(1.0, (xpix - self._margin_l) / max(1.0, plot_w)))
        return self._vx0 + frac * (self._vx1 - self._vx0)

    def _calc_selection_stats(self):
        if self._rdrag_start_x is None or self._rdrag_curr_x is None:
            return None
        t0 = self._xpix_to_time(min(self._rdrag_start_x, self._rdrag_curr_x))
        t1 = self._xpix_to_time(max(self._rdrag_start_x, self._rdrag_curr_x))
        bpms = [self._event_bpm(p["ms"], bool(p.get("is_stream", True))) for p in self._points if t0 <= p["x"] <= t1 and p["ms"] > 0]
        if not bpms:
            return None
        return sum(bpms) / len(bpms), max(bpms), min(bpms)

    def _on_rmb_up(self, event) -> None:
        if self._rdrag_start_x is None:
            return
        self._rdrag_curr_x = float(event.x)
        self._selection_stats = self._calc_selection_stats()
        self._redraw()

    def _draw_selection_overlay(self, x0: float, y0: float, plot_w: float, plot_h: float) -> None:
        if self._rdrag_start_x is None or self._rdrag_curr_x is None:
            return
        left = max(x0, min(x0 + plot_w, min(self._rdrag_start_x, self._rdrag_curr_x)))
        right = max(x0, min(x0 + plot_w, max(self._rdrag_start_x, self._rdrag_curr_x)))
        if right - left < 2:
            return
        self.create_rectangle(left, y0, right, y0 + plot_h, fill="#7aa2ff", outline="#9fc1ff", stipple="gray25")
        stats = self._selection_stats if self._selection_stats is not None else self._calc_selection_stats()
        if stats is None:
            return
        avg, peak, low = stats
        self.create_rectangle(left + 6, y0 + 6, min(left + 290, right - 6), y0 + 30, fill="#111419", outline="#2e3440")
        self.create_text(left + 10, y0 + 18, anchor="w", text=f"Area BPM avg {avg:.1f} peak {peak:.1f} min {low:.1f}", fill=cfg.TEXT, font=(cfg.FONT_FAMILY, 8, "bold"))

    def _on_motion(self, event) -> None:
        if not self._points:
            return
        mx, my = float(event.x), float(event.y)
        best = None
        best_d2 = 1e9
        for i, p in enumerate(self._points):
            d2 = (p["cx"] - mx) ** 2 + (p["cy"] - my) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best = i
        if best is None or best_d2 > 14.0**2:
            self._hover_index = None
            self._hover_alpha = 0.0
            self._redraw()
            return
        if best != self._hover_index:
            self._hover_index = best
            self._hover_alpha = 1.0
            self._redraw()

    def _on_leave(self, _event) -> None:
        if self._hover_index is not None:
            self._hover_index = None
            self._hover_alpha = 0.0
            self._redraw()

    def _draw_hover_tooltip(self) -> None:
        if self._hover_index is None or self._hover_index >= len(self._points):
            return
        p = self._points[self._hover_index]
        bpm = self._event_bpm(p["ms"], bool(p.get("is_stream", True)))
        x1 = p["cx"] + 10
        y1 = p["cy"] - 12
        x2 = x1 + 86
        y2 = y1 - 22
        self.create_rectangle(x1, y1, x2, y2, fill="#171c25", outline="#6f86a8")
        self.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=f"{bpm:.1f} BPM", fill=cfg.TEXT, font=(cfg.FONT_FAMILY, 8, "bold"))

    def _event_bpm(self, ms: float, is_stream: bool) -> float:
        if ms <= 0:
            return 0.0
        dt = ms / 1000.0
        base = 15.0 / dt
        return base if is_stream else (base / 2.0)
