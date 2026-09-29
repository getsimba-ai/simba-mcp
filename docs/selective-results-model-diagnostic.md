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

## Status

Implementation and local verification in progress. No diagnostic result yet.
PR #58 remains draft; issue #45 remains open. No merge approval.

Architecture follows [the engineering objective](engineering.md): model settings
and budget accounting remain in `evaluation.hosts.anthropic`; the existing host
command owns session selection and orchestration; `evaluation.experiments` owns
the freeze. No additional runner, fixture copy or production guidance change.
