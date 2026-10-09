"""Reciprocal rank fusion (PRD 5.2): what both lists rank highly comes first."""

import pytest

from citemark.retrieve.rrf import fuse


def test_what_both_lists_rank_highly_comes_first():
    fused = fuse([["a", "b", "c"], ["b", "c", "d"]], k=60)
    assert [item for item, _ in fused] == ["b", "c", "a", "d"]


def test_a_score_is_the_sum_of_one_over_k_plus_rank():
    fused = dict(fuse([["a"], ["b", "a"]], k=60))
    assert fused["a"] == pytest.approx(1 / 61 + 1 / 62)
    assert fused["b"] == pytest.approx(1 / 61)


def test_a_tie_goes_to_the_earlier_list_so_the_order_never_depends_on_chance():
    assert [item for item, _ in fuse([["vector"], ["keyword"]])] == ["vector", "keyword"]


def test_nothing_found_is_an_empty_list():
    assert fuse([[], []]) == []
