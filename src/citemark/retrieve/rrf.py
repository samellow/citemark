"""Reciprocal rank fusion (PRD 5.2): merging rankings that score on different scales.

Each list gives an item 1 / (k + rank), and an item's scores are added up, so what both lists
place high comes first. Only ranks count, so a cosine similarity and a keyword rank never need
to be put on one scale. k = 60 is the constant from the method's paper (Cormack et al., 2009).
"""

from __future__ import annotations

from collections.abc import Hashable, Sequence


def fuse[T: Hashable](rankings: Sequence[Sequence[T]], k: int = 60) -> list[tuple[T, float]]:
    """Every item in any ranking, best first, with its fused score. A tie goes to the item with
    the better single rank, then to the earlier ranking, so the order never depends on chance."""
    scores: dict[T, float] = {}
    best: dict[T, int] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, 1):
            scores[item] = scores.get(item, 0.0) + 1 / (k + rank)
            best[item] = min(best.get(item, rank), rank)
    return sorted(scores.items(), key=lambda pair: (-pair[1], best[pair[0]]))
