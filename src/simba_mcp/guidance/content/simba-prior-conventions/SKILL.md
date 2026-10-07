---
name: simba-prior-conventions
description: Construct Simba media or control prior overrides. Use before changing carryover, saturation anchors, effect-at-average coordinates or explicit control transforms.
metadata:
  version: "23"
---

# Configure prior overrides

1. Read [conventions](references/conventions.md) before constructing any override.
2. Match media priors to channels[].name and control priors to exact selected columns.
3. Select one saturation anchor and one coefficient coordinate. For generalised-log human coordinates include the required curvature pairing.
4. Preserve smart defaults for omitted fields. Do not claim those defaults are externally validated evidence.
5. Check capabilities for explicit control priors and retain all requested settings. Refused or unsupported requests must not silently fall back.
6. After creation compare resolved priors and overridden_fields to the request. Unknown fields, wrong units or inactive parameters require correction, not a claim of success.

Role availability: full/data_scientist can change priors during authorised model or recipe authoring. Narrow profiles may inspect existing evidence but stop before authoring and reconnect with full. Retain schema capability checks, exact coordinates and accepted-not-used semantics; never fit solely to repair missing prior evidence.


If the task spans unfamiliar Simba domains and workflow routing is enabled,
recommend_workflow can suggest guidance and visible tools. Skip it for a clear
workflow or already-loaded guidance. Its recommendation never authorises actions;
on fallback continue normal selection without repeating the routing call.
