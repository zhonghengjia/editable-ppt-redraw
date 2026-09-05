#!/usr/bin/env python3
"""Small deterministic helpers shared by curve extraction and fidelity audit."""

from __future__ import annotations

import math
from typing import Iterable, Sequence


Point = tuple[float, float]


def is_finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def normalize_points(raw_points: Iterable[Sequence[float]]) -> list[Point]:
    points: list[Point] = []
    for item in raw_points:
        if len(item) != 2 or not all(is_finite_number(value) for value in item):
            raise ValueError("curve points must be finite [x, y] pairs")
        x, y = float(item[0]), float(item[1])
        points.append((x, y))
    if len(points) < 2:
        raise ValueError("a curve trace requires at least two points")
    points.sort(key=lambda point: point[0])
    return points


def interpolate_profile(raw_points: Iterable[Sequence[float]], count: int = 201) -> list[Point]:
    """Interpolate a single-valued x/y profile onto a fixed normalized grid."""
    if count < 3:
        raise ValueError("profile sample count must be at least 3")
    points = normalize_points(raw_points)
    collapsed: list[Point] = []
    for x, y in points:
        if collapsed and abs(x - collapsed[-1][0]) <= 1e-12:
            collapsed[-1] = (x, min(collapsed[-1][1], y))
        else:
            collapsed.append((x, y))
    if len(collapsed) < 2:
        raise ValueError("a profile requires at least two distinct x coordinates")

    result: list[Point] = []
    segment = 0
    for index in range(count):
        x = index / (count - 1)
        if x <= collapsed[0][0]:
            y = collapsed[0][1]
        elif x >= collapsed[-1][0]:
            y = collapsed[-1][1]
        else:
            while segment + 1 < len(collapsed) and collapsed[segment + 1][0] < x:
                segment += 1
            x0, y0 = collapsed[segment]
            x1, y1 = collapsed[segment + 1]
            fraction = 0.0 if abs(x1 - x0) <= 1e-12 else (x - x0) / (x1 - x0)
            y = y0 + fraction * (y1 - y0)
        result.append((x, float(y)))
    return result


def moving_average(values: Sequence[float], window: int = 5) -> list[float]:
    if not values:
        return []
    window = max(1, int(window))
    if window % 2 == 0:
        window += 1
    radius = window // 2
    result: list[float] = []
    for index in range(len(values)):
        left = max(0, index - radius)
        right = min(len(values), index + radius + 1)
        result.append(sum(values[left:right]) / (right - left))
    return result


def detect_peaks(
    profile: Sequence[Point],
    *,
    min_prominence: float = 0.08,
    min_distance_fraction: float = 0.06,
    smoothing_window: int = 5,
) -> list[dict[str, float]]:
    """Detect prominent local maxima without changing the geometry being audited."""
    if len(profile) < 3:
        return []
    xs = [float(point[0]) for point in profile]
    raw = [float(point[1]) for point in profile]
    values = moving_average(raw, smoothing_window)
    window = max(2, int(round(len(values) * 0.12)))
    candidates: list[dict[str, float]] = []
    for index in range(1, len(values) - 1):
        if not (values[index] >= values[index - 1] and values[index] > values[index + 1]):
            continue
        left_min = min(values[max(0, index - window) : index + 1])
        right_min = min(values[index : min(len(values), index + window + 1)])
        prominence = values[index] - max(left_min, right_min)
        if prominence + 1e-12 < min_prominence:
            continue
        candidates.append(
            {
                "x": xs[index],
                "y": raw[index],
                "prominence": float(prominence),
                "index": float(index),
            }
        )

    selected: list[dict[str, float]] = []
    for candidate in sorted(candidates, key=lambda item: item["prominence"], reverse=True):
        if all(abs(candidate["x"] - kept["x"]) >= min_distance_fraction for kept in selected):
            selected.append(candidate)
    selected.sort(key=lambda item: item["x"])
    for item in selected:
        item.pop("index", None)
    return selected


def valleys_between_peaks(profile: Sequence[Point], peaks: Sequence[dict[str, float]]) -> list[dict[str, float]]:
    result: list[dict[str, float]] = []
    for left, right in zip(peaks, peaks[1:]):
        candidates = [point for point in profile if left["x"] < point[0] < right["x"]]
        if not candidates:
            continue
        x, y = min(candidates, key=lambda point: point[1])
        result.append({"x": float(x), "y": float(y)})
    return result


def x_aligned_mae(source: Sequence[Point], output: Sequence[Point], count: int = 201) -> float:
    source_grid = interpolate_profile(source, count)
    output_grid = interpolate_profile(output, count)
    return sum(abs(a[1] - b[1]) for a, b in zip(source_grid, output_grid)) / count
