"""Render evaluation report data without executing tools."""


def render(report: dict) -> str:
    lines = [
        "# Synthetic workflow contract evaluation",
        "",
        f"Passed: {report['passed']}. Model evaluation: not run. Budgets: pending approval.",
        "",
        "Scripted outcomes do not establish agent or scientific quality.",
        "",
        "| Case | Repetition | Passed | Calls | Attempts | Seconds |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for t in report["trials"]:
        lines.append(
            f"| {t['case_id']} | {t['repetition']} | {t['passed']} | "
            f"{t['tool_calls']} | {t['backend_attempts']} | {t['latency_seconds']:.6f} |"
        )
    return "\n".join(lines) + "\n"
