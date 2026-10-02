"""Explicit provider/model configuration frozen with evaluation evidence."""

MODEL = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-5-5"
GROK = "grok-4.7"


def model_configuration(model=MODEL, reasoning_effort=None):
    """Explicit request and accounting settings, frozen with each experiment.

    Preserve historical Haiku cache overestimates. Sonnet uses a conservative
    one-hour cache-write rate; these synthetic requests do not enable caching.
    """
    if reasoning_effort is not None and (
        model != GROK or reasoning_effort not in ("low", "medium", "high", "xhigh")
    ):
        raise ValueError("Reasoning override requires a supported xAI effort level")
    if model == MODEL:
        return {
            "request": {"model": model, "max_tokens": 1200, "temperature": 0},
            "rates_per_million": {"input": 1, "output": 5, "cache_read": 1, "cache_write": 2},
        }
    if model == SONNET:
        return {
            "request": {
                "model": model,
                "max_tokens": 4096,
                "thinking": {"type": "adaptive"},
                "output_config": {"effort": "medium"},
            },
            "rates_per_million": {"input": 2, "output": 10, "cache_read": 0.2, "cache_write": 4},
        }
    if model == GROK:
        return {
            "request": {
                "model": model,
                "max_output_tokens": 4096,
                "reasoning": {"effort": reasoning_effort or "medium"},
                "store": False,
            },
            "rates_per_million": {"input": 2, "output": 6, "cache_read": 0.5, "cache_write": 0},
            "long_context_rates_per_million": {"input": 4, "output": 12, "cache_read": 1},
            "long_context_threshold": 200000,
            "billing": "provider_cost_in_usd_ticks",
        }
    raise ValueError("Unsupported evaluation model")
