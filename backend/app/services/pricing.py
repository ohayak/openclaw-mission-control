"""
Token pricing lookup and cost estimation.

Prices are in USD per token. When the proxy reports cost = 0, we estimate
from tokens × model rate.
"""
from __future__ import annotations

# Pricing: USD per token (input/output)
TOKEN_PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-6": {
        "input": 15.0 / 1_000_000,
        "output": 75.0 / 1_000_000,
    },
    "claude-sonnet-4-6": {
        "input": 3.0 / 1_000_000,
        "output": 15.0 / 1_000_000,
    },
    "claude-sonnet-4-5-20250929": {
        "input": 3.0 / 1_000_000,
        "output": 15.0 / 1_000_000,
    },
    "claude-sonnet-4-5": {
        "input": 3.0 / 1_000_000,
        "output": 15.0 / 1_000_000,
    },
    "claude-haiku-4-5": {
        "input": 0.80 / 1_000_000,
        "output": 4.0 / 1_000_000,
    },
    "claude-haiku-3-5": {
        "input": 0.80 / 1_000_000,
        "output": 4.0 / 1_000_000,
    },
    # Proxy model names (cliproxy/...)
    "cliproxy/claude-sonnet-4-6": {
        "input": 3.0 / 1_000_000,
        "output": 15.0 / 1_000_000,
    },
    "cliproxy/claude-opus-4-6": {
        "input": 15.0 / 1_000_000,
        "output": 75.0 / 1_000_000,
    },
    "cliproxy/claude-haiku-4-5": {
        "input": 0.80 / 1_000_000,
        "output": 4.0 / 1_000_000,
    },
}


def get_model_pricing(model: str) -> dict[str, float] | None:
    """Return pricing dict for a model, or None if unknown."""
    if not model:
        return None

    # Exact match
    if model in TOKEN_PRICING:
        return TOKEN_PRICING[model]

    # Partial/prefix match (handle version suffixes like -20250929)
    model_lower = model.lower()
    for key, pricing in TOKEN_PRICING.items():
        if model_lower.startswith(key.lower()) or key.lower().startswith(model_lower):
            return pricing

    # Strip prefix like "cliproxy/" and retry
    if "/" in model:
        base = model.split("/", 1)[1]
        return get_model_pricing(base)

    return None


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Estimate USD cost from token counts and model pricing.
    Returns 0.0 for unknown models.
    """
    pricing = get_model_pricing(model)
    if not pricing:
        return 0.0
    return (input_tokens * pricing["input"]) + (output_tokens * pricing["output"])
