---
name: simba-results-analysis
description: Read and interpret existing Simba MMM results, channel contribution, ROI, uncertainty and diagnostics. Use for results questions without loading model-building instructions.
metadata:
  version: "2"
---

# Analyse saved results

1. Start with the known model identifier and get_model_results, requesting only needed sections and bounds. Do not call capability/schema discovery merely to read an existing result.
2. Read [interpretation](references/interpretation.md) before quoting contribution, ROI, intervals or windowed statistics.
3. Resolve channel identity from an explicit channel_map. Reuse a sufficient map already in evidence; otherwise batch channel_map with channel_summary and the needed sections. Preserve units and distinguish contribution, ROI and marginal ROI.
4. Missing sections or diagnostics mean missing evidence. Retrieve the relevant evidence or qualify the answer; never invent a result.
5. On oversized results narrow sections, channels or dates deliberately. On a transient read failure follow the refusal guidance with backoff. Do not start a fit to repair a results read.
6. Report the saved model, window, evidence and limitations. Reading prediction evidence can create access-audit records; guidance does not certify untouched holdouts.

For advanced parameters or sections not covered here, read the [full tool contract](references/tool-reference.md) before calling.
