# AI workflow instructions for Simba

Workflow guidance is a set of instructions that helps an AI assistant use Simba's
MCP tools for a particular task. It explains where to start, which checks to make,
how to interpret the results, and what to do when information is missing or a
request fails.

For example, when you ask an assistant to explain an existing model's channel ROI,
the results guidance tells it to read the saved results, retain channel names and
units, and distinguish uncertainty from missing evidence. It does not need the
instructions for building a new model to answer that question.

The **MCP connection gives the assistant access to tools**. The **workflow
instructions explain how to use those tools together**. Reading instructions does
not itself fetch results, fit a model, or change anything in Simba. The assistant
makes separate tool calls to carry out your task, within your permissions and intent.

## Choose how your assistant gets the instructions

The same instructions are available in two forms. Choose the route your AI client
supports; you do not need to install both.

| Your client | How to use the guidance |
| --- | --- |
| Supports Agent Skills, such as Claude Code | Install the relevant Skill folders. A Skill is a folder containing `SKILL.md` instructions and supporting reference files. |
| Connected to Simba MCP, without installed Skills | Ask the assistant to use `get_workflow_guidance` to read the relevant instructions. No separate Skill installation is needed. |

**Connecting Simba MCP does not install Skills. Installing a Skill does not connect
Simba MCP.** Set up the connection using the [README](../README.md) first. Guidance
does not add tools to your selected profile or grant extra permissions.

Already have the relevant instructions loaded? The assistant can use them without
requesting another copy.

## Find the instructions for your task

These are the eight workflows in guidance version 22. Topic IDs are the exact values
accepted by `get_workflow_guidance`, including the spelling `optimiser`.

| What you want to do | Skill folder | MCP topic |
| --- | --- | --- |
| Prepare data, create an MMM, or recover a model fit | [simba-mmm-workflow](../skills/simba-mmm-workflow/SKILL.md) | `mmm` |
| Explain saved results, ROI, contribution, uncertainty, or diagnostics | [simba-results-analysis](../skills/simba-results-analysis/SKILL.md) | `results` |
| Set media or control priors | [simba-prior-conventions](../skills/simba-prior-conventions/SKILL.md) | `priors` |
| Set up budget optimization or compare saved optimizer and scenario runs | [simba-optimizer-runs](../skills/simba-optimizer-runs/SKILL.md) | `optimiser` |
| Create, edit, or review Studies and their runs | [simba-studies-workflow](../skills/simba-studies-workflow/SKILL.md) | `studies` |
| Build or inspect VAR models and linked long-run MMM results | [simba-var-workflow](../skills/simba-var-workflow/SKILL.md) | `var` |
| Investigate campaigns, mappings, incremental attribution, or experiment priorities | [simba-campaign-workflow](../skills/simba-campaign-workflow/SKILL.md) | `campaigns` |
| Find an existing dataset and report actual KPI or spend | [simba-data-reporting](../skills/simba-data-reporting/SKILL.md) | `reporting` |

For the tools available to each role, see [tool profiles](tool-profiles.md) and the
[role decision matrix](role-coverage.md).

## Use the instructions through MCP

With Simba MCP connected, you can ask your assistant:

> Use Simba's results workflow guidance to explain the channel ROI for my saved
> model. Keep the units and uncertainty clear, and tell me if evidence is missing.

This is an example request, not a guarantee that every client will select the tool
automatically. If needed, explicitly ask it to call `get_workflow_guidance`.

The assistant starts by calling that tool with these arguments:

```json
{"topic": "results", "section": "entrypoint"}
```

`entrypoint` means the starting instructions for that workflow. They link to detailed
sections and explain when to read them. To get interpretation details, the assistant
calls the same tool with:

```json
{"topic": "results", "section": "interpretation"}
```

When the topic is known, request it directly. When it is unclear, this call lists
available topics and section IDs:

```json
{"topic": "index"}
```

The tool reads instructions packaged with the MCP server; it makes no backend or
network request. It returns the guidance version, available section IDs, and a content
hash identifying the exact instructions. It accepts IDs, not file paths or URLs.
Unknown IDs return an error with a recovery action. Each structured response is
limited to 24,000 UTF-8 bytes, excluding MCP transport overhead. Oversized sections
are refused rather than returned as incomplete instructions.

## Install Skills in a client that supports them

From a Python environment with `simba-mcp` installed, export the Skill folders:

```shell
python -m simba_mcp.guidance --output-dir exported-skills
```

This writes folders into `exported-skills`. It does not install them in your AI client.

For Claude Code:

1. Choose a Skill from the task table above.
2. Copy its **whole folder**, including `references/`, into `.claude/skills/` in your
   project, or `~/.claude/skills/` for use across projects. For example, the results
   instructions should be at `.claude/skills/simba-results-analysis/SKILL.md`, with
   supporting files in `.claude/skills/simba-results-analysis/references/`.
3. In Claude Code, invoke `/simba-results-analysis`, then describe your task.

Each folder is independently installable. Shared prior details are included in the
export. Review existing installations before replacing them. Other Agent Skills
clients have their own installation locations and discovery behavior; follow their
documentation.

See the [Agent Skills specification](https://agentskills.io/specification) and
[Claude Code Skills documentation](https://code.claude.com/docs/en/skills) for the
client format and installation mechanism. These describe client mechanisms, not
verified completion of Simba tasks in every client.

## Examples and limits

Each workflow's starting instructions link to detailed references. Several include
example tool calls, expected fields, interpretation, and recovery steps. For example,
call `get_workflow_guidance` with
`{"topic": "optimiser", "section": "saved-examples"}` to read examples for comparing
saved optimizer runs.

Examples use synthetic fixtures and mocked backend responses. They check requests
and evidence handling; they do not prove that an AI client will complete a real task
correctly. Guidance does not replace backend validation, scientific review, or human
acceptance. Missing diagnostics remain missing evidence, and instructions never
authorize a write on their own.

For existing results, start with the known model and relevant result sections. New
data needs schema checks; model, configuration, and publication operations still
need their relevant capability and permission checks.

## Updates and troubleshooting

After upgrading `simba-mcp`, re-export and reinstall the whole Skill folders you use.
Reconnecting MCP does not refresh Skills already installed in your client.

| Problem | What to check |
| --- | --- |
| The assistant cannot find `get_workflow_guidance` | Check the connected server's version and advertised tools. |
| A Skill is not discovered | Check the folder layout and your client's Skill settings. Copying just `SKILL.md` is insufficient. |
| A topic or section is rejected | Request `{"topic": "index"}` and use the returned IDs. |
| Installed instructions differ from MCP guidance | Re-export from the intended package version and review the installed folders before replacing them. |

## For maintainers

To change packaged instructions, regenerate Skills, or review compatibility and test
coverage, see [maintaining workflow guidance](workflow-guidance-maintenance.md).
