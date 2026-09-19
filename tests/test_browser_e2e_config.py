from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_browser_e2e_harness_is_present_and_isolated():
    script = (ROOT / "scripts" / "verify_browser_e2e.ps1").read_text(encoding="utf-8")
    browser_code = (ROOT / "tests" / "browser" / "e2e.js").read_text(encoding="utf-8")

    for required in ("GetTempPath", "RAG_INGEST_ROOT", "Start-Process", "finally", "playwright-cli"):
        assert required in script
    for required in ("#modelSelect", "#healthText", "#saveButton", "#clearButton", "setViewportSize"):
        assert required in browser_code
