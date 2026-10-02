"""Shared serial ledger; unknown requests retain conservative reservations."""

import json
import math
from dataclasses import dataclass

from .models import GROK, MODEL, model_configuration


@dataclass
class Budget:
    """One serial-run ledger. Unknown requests retain their preflight reservation."""

    cap: float
    prior: float = 0.0
    charged: float = 0.0
    reserved: float = 0.0
    model: str = MODEL
    reasoning_effort: str | None = None

    def __post_init__(self):
        model_configuration(self.model, self.reasoning_effort)
        if any(
            not math.isfinite(x) or x < 0
            for x in (self.cap, self.prior, self.charged, self.reserved)
        ):
            raise ValueError("Budget amounts must be finite and nonnegative")

    def reserve(self, request):
        if request.get("model", self.model) != self.model:
            raise ValueError("Request model does not match budget pricing")
        config = model_configuration(self.model, self.reasoning_effort)
        output_limit = request.get("max_tokens", request.get("max_output_tokens"))
        if type(output_limit) is not int or output_limit <= 0:
            raise ValueError("A positive output-token limit is required before reservation")
        rates = config.get("long_context_rates_per_million", config["rates_per_million"])
        bound = (2 * len(json.dumps(request).encode()) + 20000) * rates["input"] / 1e6
        bound += output_limit * rates["output"] / 1e6
        if self.prior + self.charged + self.reserved + bound > self.cap:
            raise RuntimeError("Provider budget exhausted")
        self.reserved += bound
        return bound

    def settle(self, usage, reservation):
        names = ("input_tokens", "output_tokens")
        if any(type(usage.get(n)) is not int or usage[n] < 0 for n in names):
            raise ValueError("Missing provider usage; reservation retained")
        if self.model == GROK:
            ticks = usage.get("cost_in_usd_ticks")
            if type(ticks) is not int or ticks < 0:
                raise ValueError("Missing or invalid provider billing; reservation retained")
            return self._settle_cost(ticks / 10_000_000_000, reservation)
        cache = [
            usage.get(n, 0) for n in ("cache_read_input_tokens", "cache_creation_input_tokens")
        ]
        if any(type(n) is not int or n < 0 for n in cache):
            raise ValueError("Invalid cache usage; reservation retained")
        rates = model_configuration(self.model)["rates_per_million"]
        cost = (
            usage["input_tokens"] * rates["input"]
            + cache[0] * rates["cache_read"]
            + cache[1] * rates["cache_write"]
            + usage["output_tokens"] * rates["output"]
        ) / 1e6
        return self._settle_cost(cost, reservation)

    def _settle_cost(self, cost, reservation):
        self.charged += cost
        self.reserved -= reservation
        if cost > reservation:
            raise RuntimeError("Provider usage exceeded reservation; stop")
        return cost
