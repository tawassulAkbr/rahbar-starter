"""Small dependency-free metrics shared by the Phase 2 offline evaluators."""

from __future__ import annotations

import math
import re
from statistics import mean
from typing import Iterable


def cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def percentile(values: Iterable[float], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def reciprocal_rank(expected: set[tuple[str, str]], retrieved: list[tuple[str, str]], k: int | None = None) -> float | None:
    if not expected:
        return None
    for index, item in enumerate(retrieved[:k], 1):
        if item in expected:
            return 1.0 / index
    return 0.0


def ndcg(expected: set[tuple[str, str]], retrieved: list[tuple[str, str]], k: int) -> float | None:
    if not expected:
        return None
    seen = set()
    gains = []
    for item in retrieved[:k]:
        gains.append(1.0 if item in expected and item not in seen else 0.0)
        seen.add(item)
    dcg = sum(gain / math.log2(index + 2) for index, gain in enumerate(gains))
    ideal_hits = min(len(expected), k)
    ideal = sum(1.0 / math.log2(index + 2) for index in range(ideal_hits))
    return dcg / ideal if ideal else 0.0


def average(values: Iterable[float | None]) -> float | None:
    usable = [value for value in values if value is not None]
    return mean(usable) if usable else None
