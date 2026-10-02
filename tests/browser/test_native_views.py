"""Run explicitly in browser CI after installing the browser-test extra tools."""

from importlib.resources import files

import pytest

playwright = pytest.importorskip("playwright.sync_api")


def test_native_views_render_served_values_and_gaps():
    html = files("simba_mcp").joinpath("ui/charts.html").read_text(encoding="utf-8")
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.set_content('<iframe id="view" style="width:100%;height:900px"></iframe>')
        page.locator("iframe").evaluate("(frame, html) => frame.srcdoc = html", html)
        frame = page.frame_locator("iframe")
        frame.get_by_text("Waiting for result data").wait_for()

        def deliver(data):
            page.evaluate(
                "data => document.querySelector('iframe').contentWindow.postMessage({jsonrpc:'2.0',method:'ui/notifications/tool-result',params:{structuredContent:data}}, '*')",
                data,
            )

        deliver(
            {
                "response_curves": [
                    {"Spend": 0, "Search": 0},
                    {"Spend": 1, "Search": 2.666666},
                    {"Spend": 2, "Search": None},
                    {"Spend": 3, "Search": 5},
                ],
                "model_config": {"config": {"currency": "GBP"}},
            }
        )
        frame.get_by_text("How spend relates to revenue").wait_for()
        assert "GBP" in frame.locator("main").inner_text()
        frame.locator("summary").click()
        assert frame.get_by_role("cell", name="2.666666", exact=True).count() == 1
        assert frame.locator('path[data-series="Search"]').get_attribute("d").count("M") == 2
        deliver(
            {
                "contributions": [
                    {"Date": 1704067200000, "Search": 10, "Base": 5, "Overlap": -2, "Model": 13}
                ]
            }
        )
        frame.get_by_text("What contributed to the outcome").wait_for()
        assert frame.locator("option", has_text="Overlap").count() == 0
        assert frame.get_by_role("heading", name="Reconciliation: Overlap").count() == 1
        deliver(
            {
                "status": "complete",
                "run_id": "synthetic",
                "inputs": {"currency": "GBP"},
                "results": [
                    {
                        "Channel": "Search",
                        "OptimalSpend": 12,
                        "HistoricalSpend": 10,
                        "Revenue": 99,
                        "ROI": 8.25,
                        "OptimizedEvalRevenue": 30,
                        "OptimizedEvalROI": 2.5,
                    },
                    {"Channel": "Total", "OptimalSpend": 12},
                ],
            }
        )
        frame.get_by_text("Inspect the budget decision").wait_for()
        assert frame.get_by_role("heading", name="Decision quantities").count() == 1
        assert frame.get_by_role("heading", name="Comparison quantities").count() == 1
        assert frame.locator("rect").count() == 2
        assert not errors
        browser.close()


@pytest.mark.parametrize(
    ("planning_window", "expected_period"),
    [
        ({"start": "2026-01-05", "end": "2026-02-01"}, "2026-01-05 to 2026-02-01"),
        (None, "not supplied to not supplied"),
    ],
)
def test_allocation_period_uses_saved_planning_window(planning_window, expected_period):
    html = files("simba_mcp").joinpath("ui/charts.html").read_text(encoding="utf-8")
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on(
            "console",
            lambda message: errors.append(message.text) if message.type == "error" else None,
        )
        page.set_content('<iframe style="width:1280px;height:900px;border:0"></iframe>')
        page.locator("iframe").evaluate("(frame, html) => frame.srcdoc = html", html)
        frame = page.frame_locator("iframe")
        frame.get_by_text("Waiting for result data").wait_for()
        inputs = {
            "currency": "GBP",
            "start_date": "1999-01-01",
            "end_date": "1999-12-31",
        }
        if planning_window is not None:
            inputs["planning_window"] = planning_window
        page.evaluate(
            "data => document.querySelector('iframe').contentWindow.postMessage({jsonrpc:'2.0',method:'ui/notifications/tool-result',params:{structuredContent:data}}, '*')",
            {
                "status": "complete",
                "run_id": "synthetic-dated-allocation",
                "inputs": inputs,
                "results": [{"Channel": "Search", "OptimalSpend": 120}],
            },
        )
        frame.get_by_text("Inspect the budget decision").wait_for()
        text = frame.locator("main").inner_text()
        assert f"Period: {expected_period}." in text
        assert "1999" not in text
        assert "Currency: GBP." in text
        assert page.locator("iframe").evaluate("frame => frame.contentWindow.innerWidth") == 1280
        assert not errors
        browser.close()
