---
name: simba-prior-conventions
description: Construct Simba media or control prior overrides. Use before changing carryover, saturation anchors, effect-at-average coordinates or explicit control transforms.
metadata:
  version: "2"
---

# Configure prior overrides

1. Read [conventions](references/conventions.md) before constructing any override.
2. Match media priors to channels[].name and control priors to exact selected columns.
3. Select one saturation anchor and one coefficient coordinate. For generalised-log human coordinates include the required curvature pairing.
4. Preserve smart defaults for omitted fields. Do not claim those defaults are externally validated evidence.
5. Check capabilities for explicit control priors and retain all requested settings. Refused or unsupported requests must not silently fall back.
6. After creation compare resolved priors and overridden_fields to the request. Unknown fields, wrong units or inactive parameters require correction, not a claim of success.
