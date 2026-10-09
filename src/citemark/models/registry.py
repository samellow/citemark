"""The models the bot can run on, and the guard that refuses one whose window can't hold the
request (PRD 5.2): full-context mode is only offered where the whole help center fits.

The guard takes a measured token count, from Anthropic's token-counting endpoint, not the
estimate stored on each passage. Claude counted Zulip's help center at about 329K tokens where
the estimate says about 178K (T2, T6), so an estimate would let a model through that can't fit.
"""

from __future__ import annotations

from dataclasses import dataclass


class ModelError(Exception):
    """The message is one plain sentence."""


class UnknownModel(ModelError):
    pass


class ContextTooLarge(ModelError):
    pass


@dataclass(frozen=True)
class Model:
    id: str
    context_window: int  # input and output together, in tokens
    max_output: int


# From Anthropic's Models API on 2026-10-08 (scripts/api_check.2026-10-08-*.json)
MODELS = {
    model.id: model
    for model in (
        Model("claude-haiku-4-5", 200_000, 64_000),
        Model("claude-haiku-5-5", 1_000_000, 128_000),
        Model("claude-sonnet-5-5", 1_000_000, 128_000),
        Model("claude-opus-5-5", 1_000_000, 128_000),
    )
}


def model(model_id: str) -> Model:
    try:
        return MODELS[model_id]
    except KeyError:
        known = ", ".join(MODELS)
        raise UnknownModel(f"{model_id} isn't a model Citemark knows. The ones it knows: {known}.") from None


def require_fit(model_id: str, input_tokens: int, output_tokens: int) -> None:
    """Refuse a request that, with room for the answer, is larger than the model's window."""
    found = model(model_id)
    if output_tokens > found.max_output:
        raise ContextTooLarge(f"{model_id} writes at most {found.max_output:,} tokens, not {output_tokens:,}.")
    if input_tokens + output_tokens > found.context_window:
        raise ContextTooLarge(
            f"This request is {input_tokens:,} tokens on {model_id}. With {output_tokens:,} more for the answer, "
            f"it doesn't fit the model's {found.context_window:,}-token window. "
            "Use search mode, or a model with a larger window."
        )
