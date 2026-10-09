"""The model registry's context-window guard (PRD 5.2), and the versioned prompts it runs with."""

import pytest

from citemark import prompts
from citemark.models.registry import ContextTooLarge, UnknownModel, model, require_fit


def test_a_request_that_fits_passes_and_one_that_doesnt_is_refused_with_its_numbers():
    require_fit("claude-sonnet-5-5", 329_150, 4_096)  # Zulip's whole help center, as Claude counted it in T2
    with pytest.raises(ContextTooLarge, match="265,407 tokens on claude-haiku-4-5"):
        require_fit("claude-haiku-4-5", 265_407, 4_096)


def test_the_answer_needs_room_too():
    require_fit("claude-haiku-4-5", 195_904, 4_096)  # exactly the 200,000-token window
    with pytest.raises(ContextTooLarge, match="doesn't fit the model's 200,000-token window"):
        require_fit("claude-haiku-4-5", 195_905, 4_096)
    with pytest.raises(ContextTooLarge, match="writes at most 64,000 tokens"):
        require_fit("claude-haiku-4-5", 10, 64_001)


def test_an_unknown_model_is_named_with_the_ones_known():
    with pytest.raises(UnknownModel, match="The ones it knows: claude-haiku-4-5"):
        model("claude-instant-1")


def test_a_prompt_is_loaded_by_its_versioned_name():
    text = prompts.load("rewrite.v1")
    assert text.startswith("Rewrite the customer's latest message as one standalone question")
    assert not text.endswith("\n")
    with pytest.raises(FileNotFoundError, match=r"No prompt rewrite\.v0"):
        prompts.load("rewrite.v0")
