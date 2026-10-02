# Saved-result native views and JSON fallback

All profiles expose `show_response_curves` and `show_decomposition`. Use a known model
directly without capability/schema startup discovery. These read fixed sections from
the authoritative results tool; no prediction-window access or fit is started.

Response curves retain served points, uncertainty bands, current spend and sparse-grid
disclosures. Current spend is not a recommendation. Missing values stay gaps.
Decomposition is in KPI units; keep Overlap separate as a reconciliation residual,
and preserve the fitted attribution convention and exact channel_map identity.

Clients without MCP Apps support receive the same structured JSON and serialised text.
Quote returned values and missingness from that JSON; never infer scientific acceptance
from a displayed chart. Native host rendering requires separate client verification.
If the backend refuses, preserve the structured error. If a section is absent,
retain not_returned and stop rather than fitting or fabricating chart values.
Use section=visuals-examples for exact calls in a JSON-only client.
