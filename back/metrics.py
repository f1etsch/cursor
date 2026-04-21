"""Session metrics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass
class SessionAnalysis:
    tap_count: int
    duration_sec: float
    stream_speed_bpm: float
    unstable_rate: float
    stream_bpm: float | None
    jump_bpm: float | None
    stream_avg_bpm: float | None
    jump_avg_bpm: float | None
    chart_times: list[float]
    chart_bpm: list[float]


def _pstdev_ms(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = sum(values) / len(values)
    v = sum((x - m) ** 2 for x in values) / len(values)
    return math.sqrt(v)


def analyze_session(events: Sequence[tuple[float, int]]) -> SessionAnalysis:
    if not events:
        return SessionAnalysis(0, 0.0, 0.0, 0.0, None, None, None, None, [], [])

    times = [e[0] for e in events]
    slots = [e[1] for e in events]
    n = len(times)
    span = times[-1] - times[0]
    if span <= 0 or n < 2:
        return SessionAnalysis(n, max(0.0, span), 0.0, 0.0, None, None, None, None, [], [])

    stream_speed = (n - 1) * 15.0 / span
    dts: list[float] = []
    stream_dts: list[float] = []
    jump_dts: list[float] = []
    chart_t: list[float] = []
    chart_b: list[float] = []

    for i in range(n - 1):
        dt = times[i + 1] - times[i]
        if dt <= 0:
            continue
        dts.append(dt)
        chart_t.append(times[i + 1] - times[0])
        chart_b.append(15.0 / dt)
        if slots[i] != slots[i + 1]:
            stream_dts.append(dt)
        else:
            jump_dts.append(dt)

    dts_ms = [d * 1000.0 for d in dts]
    ur = 10.0 * _pstdev_ms(dts_ms)

    stream_bpm = (len(stream_dts) * 15.0 / sum(stream_dts)) if stream_dts else None
    jump_bpm = (len(jump_dts) * 15.0 / sum(jump_dts)) if jump_dts else None
    stream_avg_bpm = (sum((15.0 / dt) for dt in stream_dts) / len(stream_dts)) if stream_dts else None
    jump_avg_bpm = (sum((15.0 / dt) / 2.0 for dt in jump_dts) / len(jump_dts)) if jump_dts else None

    return SessionAnalysis(
        tap_count=n,
        duration_sec=span,
        stream_speed_bpm=stream_speed,
        unstable_rate=ur,
        stream_bpm=stream_bpm,
        jump_bpm=jump_bpm,
        stream_avg_bpm=stream_avg_bpm,
        jump_avg_bpm=jump_avg_bpm,
        chart_times=chart_t,
        chart_bpm=chart_b,
    )
