# run_optimizer: full contract

<!-- Generated from the handler docstring by simba_mcp.reference. -->

Run budget optimization on a completed model.

Finds the optimal budget allocation across channels to maximize
predicted revenue — or predicted PROFIT with objective="profit" —
within the given constraints.

PROFIT OBJECTIVE: objective="profit" requires a margin source. If the model
was built with an operating margin, it is used automatically; otherwise you
MUST pass forward_margin (e.g. 0.18 for an 18% margin) or the API returns an
error. Result fields (Revenue, ROI, ExpectedResponse) are then on the profit
basis.

IMPORTANT:
- Channel names must exactly match model results (case-sensitive, space-sensitive).
  Results are keyed by the channel's ACTIVITY COLUMN name (e.g. "search_activity"),
  not by the `channels[].name` passed to create_model.
  Call get_model_results with sections="channel_summary" first to get exact names,
  or use get_scenario_template to discover channel names and their average CPM values.
- bounds values are percentages of total_budget (0-100), not currency amounts.
- laydown_weights and period_cpm must be ARRAYS of length num_periods, not scalars.
  Wrong: {"TV": 10}. Correct: {"TV": [10, 10, 10, 10]}.
- The same channel keys must appear in all three: bounds, laydown_weights, and period_cpm.
- All period_cpm values must be positive (> 0).
- laydown_weights per channel must sum to a positive value (weights are normalized internally).

Returns 202 (async). Use get_optimizer_results to poll until status is "complete".

Args:
    model_hash: Hash of a completed model.
    total_budget: Total budget in currency units.
    num_periods: Number of periods to optimize over (matches your planning horizon).
    gamma: Uncertainty-aversion weight on the outcome spread (the
           objective is mean - gamma * spread). 0.0 = maximize expected
           return only (most aggressive); higher values penalize
           uncertainty harder (more conservative). The dashboard
           typically uses values in the 0-0.1 range.
    currency: Currency code (e.g. "USD", "GBP").
    bounds: Per-channel min/max budget allocation as PERCENTAGES (0-100).
            Every channel must appear. Example:
            {"TV_Impressions": {"lower": 5, "upper": 40},
             "Search_Clicks": {"lower": 10, "upper": 50}}
    laydown_weights: Per-channel spend timing weights. Each value is an array of
                    length num_periods. Weights are relative (normalized internally).
                    Use uniform [1, 1, ...] for even distribution across periods.
                    Example: {"TV_Impressions": [1, 1, 1, 1]}
    period_cpm: Per-channel cost-per-metric for each period. Each value is an array
               of length num_periods with positive values. Get baseline CPM from
               get_scenario_template (avg_cpu_by_channel field).
               Example: {"TV_Impressions": [10.5, 10.5, 10.5, 10.5]}
    objective: "revenue" (default) or "profit". See PROFIT OBJECTIVE above.
    forward_margin: Decimal margin in (0, 1], e.g. 0.18 = 18%. Only used with
                   objective="profit"; required when the model has no stored
                   operating margin.
    period_multiplier: Optional array of length num_periods converting KPI
                      units to revenue per period over the planning horizon
                      (mirrors the model's multiplier_column, e.g. price).
    include_historical_effect: Include carryover from historical spend in the
                              predicted response (default True).
    enable_warm_start: Warm-start the optimizer from a previous solution
                      (default True).
    optimizer_engine: "slsqp" (hardened SLSQP, default) or "marginal"
                     (water-fill engine: allocates until every funded
                     channel shows the same marginal return; exact
                     profit-hurdle semantics and the tightest optimality
                     certificates, with automatic SLSQP fallback).
    sigma_penalty: How gamma penalizes outcome spread: "std" (default),
                  "variance" or "frozen" (advanced; smoother alternatives
                  for hard-to-converge runs - leave on "std" normally).
    group_bounds: Joint constraints over channel SETS (#570),
                 e.g. [{"name": "trade", "channels": ["TV", "Search"],
                 "lower": 40, "upper": 60}] with lower/upper in % of
                 total_budget (same convention as bounds). Groups must be
                 disjoint and jointly feasible with the members'
                 per-channel bounds. Presence forces the slsqp engine.
                 Results gain GroupBounds/GroupBoundsReport columns; a
                 BINDING group's members legitimately sit off the global
                 marginal (they share the group's shadow price).
