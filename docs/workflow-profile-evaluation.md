# Optional role views: scope and paired evaluation

Status: paired role evaluation complete. Revised recommendation: pursue optional
marketer and reviewer presets, retaining full as the default and the data scientist
view. This supersedes the earlier proposal to defer based on workflow subsets.
Those subsets were too narrow for jobs that span workflows. Owner acceptance and
production implementation remain open; this PR does not close #44.

This evaluates optional starting views for issue #44. The production server still
exposes its full catalogue. A job title neither grants backend permissions nor
prevents someone choosing the full view for a broader task.

## Roles are jobs across workflows

| Starting view | Responsibilities and included capabilities | Work that needs the full view |
| --- | --- | --- |
| Data scientist | All 81 tools: data, modelling, VAR, priors, incrementality, planning, every Studies authoring/launch/recovery/quality capability and governance action exposed by MCP | None excluded by this view; backend permissions still apply |
| Marketer (planning and reporting) | 37 tools: find models/projects/studies, inspect results and uncertainty, review assessments/policies/champion status, compare candidates, inspect experiment evidence, record/import incrementality results, prepare and run scenarios/optimisation, poll exact saved runs, annotate and pin plans | Fit or revise models, author recipes/policies, change study governance, manage ingestion/pipeline schedules |
| Scientific reviewer | 38 tools: inspect the same commercial and Studies evidence, inspect data/schema and recipe authoring provenance, assess runs/validation pairs, declare evidence use and record evidence-bound recommendations | Author or fit models/recipes, change policy rules, administer data pipelines, create new marketing plans or experiment records |

The reviewer is an active scientific review role, not a view-only executive. A
recommendation is not acceptance or promotion. Some inspections/comparisons append
access audit events; this view is not guaranteed read-only. Marketers also need to
understand Studies quality and provenance, so these are included rather than hidden
behind a separate scientific workflow. Data scientists retain the entire Studies
lifecycle, including reviewing and interpreting commercial outputs.

Role names describe a starting point, not a hierarchy. A marketer who also builds
models can choose full. An analyst who authors quality rules can choose full. We
have not introduced executive, administrator or agency-specific presets without
measured jobs for them. Exact ordered memberships come from canonical registered
tool objects and are recorded in the evidence, with no copied schemas.

## Test design and proposed gates

Use the existing Messages API host with `claude-haiku-4-5-20251001`. Compare the full
compact eager catalogue against one role's compact eager catalogue. The model,
system instruction, task prompt, fixtures, tool definitions and grading stay the
same within each pair; only visible tools differ. Five fresh sessions per task and
arm, alternating arm order, produce 110 sessions across 11 role/task combinations.
No native tool search is used in either arm, and no real backend or fit is called.

| Role | Paired jobs |
| --- | --- |
| Marketer (planning and reporting) | Selected model evidence; exact profit optimiser settings; missing Studies evidence; combined model/Studies evidence; full planning lifecycle from status and template through submission and pending/completed polling; failed saved-scenario recovery without relaunch |
| Reviewer | Selected model evidence; missing Studies evidence; combined model/Studies evidence; incompatible candidate comparison; recommendation bound to a saved passing evaluation without claiming acceptance |

The planning case distinguishes decision ROI from fitted-convention ROI and
objective marginal return from posterior mROI. The failure case returns HTTP 200
with failed run status, to test that the agent reads the result body. Comparison
must preserve incompatible units and avoid ranking candidates. These are tool-use
and evidence-interpretation tests, not independent scientific validation of an MMM.

Passing requires exact requested facts, completion of all authorised mock steps,
no unexpected errors and no unintended writes. Strict bare JSON is measured
separately from facts. A rejected invalid write remains a failure. Backend refusal
remains an error even when its handling matches the fixture. Omitted tools cannot
execute silently against the underlying full server.

Proposed exploratory gate: lower provider cost with no additional in-scope failures
against the paired baseline; inspect latency separately. These are evaluation
criteria, not owner-approved release thresholds or a claim of statistical
non-inferiority. Five repetitions of synthetic tasks do not establish performance
across users, models or clients. Keep all failures in the evidence.

## Results

The [public evidence record](role-profile-evidence.json) contains frozen source
hashes, canonical catalogue definition hashes, exact prompts/fixtures, every provider
response, selected tool names, per-turn usage, failures and aggregate calculations.
The source digest is recorded because testing used the uncommitted implementation
on base `8f47221`. Both comparison cohorts used the same frozen source.

| Measure | Full, marketer tasks | Marketer view | Full, reviewer tasks | Reviewer view |
| --- | ---: | ---: | ---: | ---: |
| Tools visible | 81 | 37 | 81 | 38 |
| Functional/evidence passes | 25/30 | 30/30 | 20/25 | 25/25 |
| Provider input tokens | 2,893,473 | 1,201,373 | 2,162,113 | 825,312 |
| Provider output tokens | 9,372 | 9,288 | 6,469 | 6,276 |
| Calculated provider cost | US$2.940333 | US$1.247813 | US$2.194458 | US$0.856692 |
| Median session seconds | 3.476 | 3.354 | 3.621 | 3.728 |
| Provider turns | 80 | 80 | 60 | 60 |
| Ordinary tool calls | 65 | 65 | 45 | 45 |
| Unexpected errors / unintended writes | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Strict bare-JSON answers | 0/30 | 0/30 | 0/25 | 0/25 |

The marketer view used 58.5% fewer input tokens and cost 57.6% less. The reviewer
view used 61.8% fewer input tokens and cost 61.0% less. No pair passed with full and
failed with its role view. Provider turns and tool calls were unchanged. Latency
was mixed: the reviewer median was slightly slower, so there is no general speed
claim.

All ten baseline failures were repeated instances of the existing combined-task
error: returning the missing-evidence reason `not_collected` as the holdout status,
when the saved status was `not_evaluated`. The role views returned the correct
status in all ten corresponding sessions. This is one repeated failure mode, not
ten independent scientific discoveries, and it does not prove roles solve evidence
interpretation generally. The defect remains relevant to full-catalogue workflows.
Every other task passed in both arms. All answers failed strict bare-JSON formatting;
the facts grader accepted fenced JSON, consistently with the previous host trial.

The 110 completed sessions cost US$7.239296. A preliminary session was interrupted
by a local evidence-file replacement error after US$0.036578 of known usage; it was
preserved and excluded from completed-pair scores. Output was moved outside the
synced folder before restarting. New known usage totals US$7.275874. Cumulative
accounting is US$14.686062 against the authorised US$50 cap, including the earlier
US$1 unknown-usage reserve. No outstanding reservation remains in these two runs.

The results support investing in optional role presets and overturn the earlier
blanket deferral recommendation. They meet the proposed exploratory cost/correctness
gate on these jobs. They do not approve a production release: remaining scope
coverage, real client selection/fallback and the implementation gates below remain
explicit, together with owner agreement on roles and numerical release thresholds.

## Fallback and coverage boundaries

The evaluation checks that data scientist and full selections are exactly the
canonical catalogue, selection lists do not alter registration, unknown names fail,
and an omitted model-creation operation cannot dispatch through the marketer view.
An explicit new full-view task then executes the same synthetic model-creation
operation. There is no runtime enable-tools action and no automatic replay or
catalogue mutation. Real uncertain writes must be reconciled before a new task.

This tests host-side selection and dispatch, not a production profile endpoint.
Production startup selection, multi-caller credential isolation, stdio/HTTP profile
configuration and a user-facing fallback remain implementation gates. Claude
Desktop, Claude Code and other clients have not been certified by this test.

The paired jobs do not cover every included operation. Incrementality creation and
import, scenario submission, saved-run curation, data/provenance inspection,
assessment/pair assessment and holdout-use declaration need further representative
coverage before claiming complete role support. Nor do these prompts test open-ended
business-question discovery, long conversations or realistic datasets. The current
full catalogue remains available throughout.

## Reproduce and structure

Supply `ANTHROPIC_API_KEY` through the environment and use the existing host command:

```shell
python -m simba_mcp.evaluation.hosts --role-comparison marketer --samples 5 --mode eager --cap-usd YOUR_TOTAL_CAP --prior-usd YOUR_ACCOUNTED_SPEND --output NEW_EVIDENCE_PATH.json
```

Run `reviewer` serially with the previous output's `prior + charged + reserved` as
its prior. The command refuses to overwrite evidence. Choose an approved cap;
examples do not authorise spend. Provider errors stop the run without replay. Store
raw evidence privately because it includes the full catalogue text; the public
record replaces it with names and definition hashes and uses synthetic tasks only.

Following the [engineering objective](engineering.md), `evaluation.hosts.roles`
owns experimental membership, `scenarios` owns job fixtures and `__main__` owns
comparison orchestration/evidence. They reuse `anthropic` for the provider and
budget, `evaluation.runner` for strict mock dispatch, and canonical contracts/tools.
Production modules do not import role selection. New tools automatically remain in
full/data scientist; additions to narrower views require an explicit job-scope review. No second provider runner, schema
registry, dependency or production configuration was added.

The [earlier offline workflow measurements](workflow-profile-evidence.json) remain
historical evidence only. Their missing mixed-domain operation explains why those
particular candidates were inadequate; it does not justify rejecting role views.
Keep #44 open until its owner decision and applicable implementation gates are met.

Verification: 355 tests passed; repository Ruff checks and formatting passed; source
distribution and wheel built successfully. Public evidence was checked for raw
catalogue text, credentials and private identifiers before publication.
