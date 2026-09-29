# Selective results: stronger-model diagnostic

This is model-selection validation, not final acceptance. The previous candidate
comparison failed the supported-answer and unsupported-claim gates. Its original
scores remain unchanged. Cases used to select a model or guidance are now validation
cases; final acceptance requires a fresh independently reviewed packet.

## Frozen protocol

- Existing synthetic runner and candidate guidance, unchanged from the failed run.
- Cases A and E are passing controls; D, F and H are the three failing cases.
- Two repetitions per case, ten candidate-only sessions, no retries or fallback.
- Model `claude-sonnet-5-5`, adaptive thinking, medium effort, 4,096 maximum output
  tokens including thinking. No temperature override. Historical Haiku used
  temperature zero and 1,200 maximum output tokens, so this compares configurations.
- Prior accounted spend US$25.372478, including US$0.289594 retained for older
  interrupted usage. Additional diagnostic limit US$3, enforced by a cumulative
  run cap of US$28.372478. The overall authorised cap remains US$40.
- Input US$2 and output US$10 per million tokens. Cache reads US$0.20 and cache
  writes conservatively US$4 per million. Requests do not enable caching.
- Independent review of every numerical answer, explanatory claim and call,
  using the previous semantic standards and answer/trajectory hashes. No tuning.
- Compare descriptively with the ten corresponding historical Haiku candidate
  sessions. Do not infer population reliability from ten reused synthetic sessions.

Model availability was checked through the provider's Models API before the run.
Request parameters and rates follow the official [Sonnet 5.5
documentation](https://platform.claude.com/docs/en/models/sonnet-5-5/overview)
and [pricing](https://platform.claude.com/docs/en/about-claude/pricing), checked
29 September 2026. Source, fixtures, calibration, guidance and model configuration
are frozen by the existing experiment implementation before the first paid request.

## Reviewed result

All ten sessions completed at source `650c1e241fa0e234cdbc241f420a7abf3928cd3d`.
The separate agent reviewed every final answer and call, with complete hash-bound
coverage. [Synthetic answers, trajectories and reviews](selective-results-model-diagnostic-evidence.json)
retain the original automatic scores separately from semantic adjudication.

| Measure | Sonnet 5.5 | Historical Haiku 4.5, same cases |
| --- | ---: | ---: |
| Supported answers | 9/10 | 4/10 |
| Answers with unsupported claims | 1 | 6 |
| Required evidence retrieved | 10/10 | 10/10 |
| Unnecessary calls | 0 | 0 |
| Unauthorised attempts / actual reads | 0 / 0 | 0 / 0 |
| Provider cost | US$2.027546 | US$0.763278 |

Both repetitions of D, F and H are supported under the same semantic review
standards. Control A remains supported, but control E regresses once: its answer
correctly defines current spend as mean spend over active periods, then claims
the evidence does not say whether it is per period or a total. Returned
`spend_convention=mean_active_period` contradicts that additional caveat.

The F reviews distinguish unresolved possible explanations and modelled KPI
effects from asserted raw weather values or unique channel synergy. H restates
the supplied missing-artefact contract while explicitly declining to infer
unread values. Review rationales preserve these boundaries, including imprecise
but non-dispositive caveats; they are not a change to the previous rubric.

Sonnet costs 2.66 times as much on this selected packet. Its 90% supported-answer
rate and one unsupported answer still fall short of the agreed 95% and zero-claim
requirements. The observed improvement is useful diagnostic evidence, but ten
reused, failure-selected sessions do not establish population reliability, a
cost-saving workflow or final acceptance. No significance claim is made.

Next, develop a focused evidence-interpretation rule on validation material:
honour explicit metadata and qualify only what the supplied evidence leaves
unknown. Test the whole answer for contradictory or unsupported additions.
Freeze the selected configuration before commissioning fresh independent
acceptance cases. This recommendation has not been implemented or evaluated;
no further paid run has started.

The run stayed below its US$3 limit. Cumulative accounted spend is
**US$27.400024**, including the retained US$0.289594 interrupted allowance.
**US$12.599976** remains under the US$40 total cap. No reservation remains.

504 tests collected locally pass, as do lint, formatting and generated-reference
checks. All four CI jobs, including wheel and scripted workflow checks, pass at
implementation head `650c1e2`. PR #58 remains draft; issue #45 remains open.
**Do not merge.**

Architecture follows [the engineering objective](engineering.md): model settings
and budget accounting remain in `evaluation.hosts.anthropic`; the existing host
command owns session selection and orchestration; `evaluation.experiments` owns
the freeze. No additional runner, fixture copy or production guidance change.
