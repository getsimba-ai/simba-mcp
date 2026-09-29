# Retrospective KPI prompt ambiguity audit

The independent challenge is valid. The original prompt says: "give summed Sales and Revenue and the implied Revenue/Sales factor for each date". The final phrase can reasonably scope the entire coordinated request. Under that reading, Sales and Revenue are summed separately for each date, alongside each date's factor. One row per date makes 40/280 and 60/480 complete per-date answers.

The intended labels, combined Sales 100 and Revenue 760, correspond to another reasonable reading. They do not make it the only reading. The reviewer previously treated those intended labels as an unambiguous completeness requirement. That was too strong. Arithmetic and dispatcher tests verified the intended calculation, but did not establish linguistic clarity.

The affected original incompleteness labels are V3 baseline repetition 0 and both candidate repetitions, plus V14 both baseline repetitions and candidate repetition 1. All eight KPI responses satisfy the reasonable per-date reading on their numerical and explanatory content. The two responses that additionally supplied combined totals remain complete under both readings. This finding addresses prompt scope, not an agent arithmetic or grounding error.

All original checkpoints, scores, hash-bound reviews, assessments and summaries remain unchanged. The original public evidence records retain those exact reviews. This note is a separate retrospective sensitivity finding, not a silent rescore. No new support percentages, cost intervals or acceptance decision have been substituted. The original missing-total labels should not be used as conclusive evidence of a genuine quality regression.

A prospective clarification is: "give combined Sales and combined Revenue across both dates, plus the Revenue/Sales factor separately for each date". It explicitly asks for two combined totals and two separate factors. Any such reused-case run is validation only, with a new prompt/version/hash. It cannot replace the original acceptance result or count as a fresh holdout.

V3 still has the separately identified unsupported mROI date-selection statement and diagnostic completeness statement, and cost/quality evidence does not establish acceptance. The V14 ambiguous case does not establish the alleged completeness regression, but it also does not certify future performance on the clarified request. The next validation uses an explicitly clarified prompt and a new frozen source. No provider calls, source edits or guidance changes were made by this reviewer during the audit.
