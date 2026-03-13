"""Tests for the pricing / cost estimation module."""
import pytest
from app.services.pricing import estimate_cost, get_model_pricing, TOKEN_PRICING


class TestGetModelPricing:
    def test_exact_match_sonnet(self):
        pricing = get_model_pricing("claude-sonnet-4-6")
        assert pricing is not None
        assert pricing["input"] == 3.0 / 1_000_000
        assert pricing["output"] == 15.0 / 1_000_000

    def test_exact_match_opus(self):
        pricing = get_model_pricing("claude-opus-4-6")
        assert pricing is not None
        assert pricing["input"] == 15.0 / 1_000_000
        assert pricing["output"] == 75.0 / 1_000_000

    def test_exact_match_haiku(self):
        pricing = get_model_pricing("claude-haiku-4-5")
        assert pricing is not None
        assert pricing["input"] == 0.80 / 1_000_000
        assert pricing["output"] == 4.0 / 1_000_000

    def test_proxy_prefix(self):
        pricing = get_model_pricing("cliproxy/claude-sonnet-4-6")
        assert pricing is not None
        assert pricing["input"] == 3.0 / 1_000_000

    def test_unknown_model_returns_none(self):
        pricing = get_model_pricing("gpt-4-turbo")
        assert pricing is None

    def test_empty_string_returns_none(self):
        pricing = get_model_pricing("")
        assert pricing is None

    def test_none_like_string(self):
        pricing = get_model_pricing("unknown-model-xyz")
        assert pricing is None


class TestEstimateCost:
    def test_sonnet_cost(self):
        # 1000 input + 500 output at sonnet rates
        cost = estimate_cost("claude-sonnet-4-6", 1000, 500)
        expected = (1000 * 3.0 / 1_000_000) + (500 * 15.0 / 1_000_000)
        assert abs(cost - expected) < 1e-10

    def test_opus_cost(self):
        cost = estimate_cost("claude-opus-4-6", 2000, 1000)
        expected = (2000 * 15.0 / 1_000_000) + (1000 * 75.0 / 1_000_000)
        assert abs(cost - expected) < 1e-10

    def test_haiku_cost(self):
        cost = estimate_cost("claude-haiku-4-5", 5000, 2000)
        expected = (5000 * 0.80 / 1_000_000) + (2000 * 4.0 / 1_000_000)
        assert abs(cost - expected) < 1e-10

    def test_unknown_model_returns_zero(self):
        cost = estimate_cost("gpt-4-turbo", 1000, 500)
        assert cost == 0.0

    def test_empty_model_returns_zero(self):
        cost = estimate_cost("", 1000, 500)
        assert cost == 0.0

    def test_zero_tokens_returns_zero(self):
        cost = estimate_cost("claude-sonnet-4-6", 0, 0)
        assert cost == 0.0

    def test_proxy_model_cost(self):
        cost = estimate_cost("cliproxy/claude-sonnet-4-6", 1000, 500)
        expected = (1000 * 3.0 / 1_000_000) + (500 * 15.0 / 1_000_000)
        assert abs(cost - expected) < 1e-10

    def test_with_version_suffix(self):
        """Models with date suffixes should still match."""
        cost = estimate_cost("claude-sonnet-4-5-20250929", 1000, 500)
        expected = (1000 * 3.0 / 1_000_000) + (500 * 15.0 / 1_000_000)
        assert abs(cost - expected) < 1e-10
