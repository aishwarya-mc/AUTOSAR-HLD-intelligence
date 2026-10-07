"""Capture UI screenshots for the technical report.

Usage: python scripts/capture_screenshots.py [API_URL] [UI_URL] [OUT_DIR]
Requires playwright and Microsoft Edge (or change channel to "chrome").
"""
import sys
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

API = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8010"
UI = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8511"
OUT = Path(sys.argv[3] if len(sys.argv) > 3 else "submission_assets/screenshots")
OUT.mkdir(parents=True, exist_ok=True)
SAMPLES = Path(__file__).resolve().parents[1] / "data" / "sample"

# Start clean, then seed two revisions so every page has content.
for d in httpx.get(f"{API}/documents").json():
    httpx.delete(f"{API}/documents/{d['document_id']}")
httpx.post(f"{API}/documents/sample", timeout=300)
with open(SAMPLES / "sample_hld_v2.pdf", "rb") as f:
    httpx.post(f"{API}/documents", files={"file": ("sample_hld_v2.pdf", f, "application/pdf")},
               data={"version": "v2"}, timeout=300)


def idle(page, extra=1500):
    """Wait until Streamlit has finished re-running the script."""
    page.wait_for_timeout(600)
    page.wait_for_function(
        "() => !document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=60000)
    page.wait_for_timeout(extra)


def go(page, label):
    key = label.split(" ", 1)[1]  # strip the emoji
    page.locator("button", has_text=key).first.click()
    idle(page)


def shot(page, name):
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
    print("saved", name)


with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.goto(UI)
    page.wait_for_timeout(5000)
    shot(page, "01_home")

    go(page, "📄 Documents")
    shot(page, "02_documents")

    go(page, "🧩 Architecture")
    page.wait_for_timeout(6000)  # let the graph physics settle
    shot(page, "03_architecture_graph")
    page.locator("button", has_text="Component report").first.click()
    idle(page)
    shot(page, "04_component_report")
    page.locator("button", has_text="Impact analysis").first.click()
    idle(page)
    shot(page, "05_impact_analysis")

    go(page, "💬 Ask")
    page.locator("button", has_text="Which component provides IDoorStatus?").first.click()
    page.wait_for_selector("text=Architecture facts", timeout=60000)
    idle(page, 2500)
    shot(page, "06_ask_grounded")
    box = page.get_by_placeholder("Ask about components, interfaces, ports, signals, flows…")
    box.fill("What is the maximum engine torque?")
    box.press("Enter")
    page.wait_for_selector("text=was not found in the document", timeout=60000)
    idle(page, 2500)
    shot(page, "07_ask_refusal")

    go(page, "✅ Validation")
    shot(page, "08_validation")

    go(page, "🔀 Compare")
    idle(page, 3000)
    shot(page, "09_compare")

    go(page, "📑 Report")
    shot(page, "10_report")
    browser.close()
