"""Screenshot every URL in a list file.

Each line of the list: URL, optionally followed by a space and a short name.
Blank lines and lines starting with # are ignored.
Output: <out>/<batch>/<name>-top.jpg (first screen) and <name>-full.jpg
(full page, capped in height), plus report.txt with any failures.
"""
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

MAX_FULL_HEIGHT = 7000
COOKIE_TEXTS = ["Accept all", "Accept All", "Accept", "I agree", "Agree", "Allow all",
                "Got it", "OK", "Accept cookies", "Allow cookies"]


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "page"


def dismiss_popups(page):
    for label in COOKIE_TEXTS:
        try:
            btn = page.get_by_role("button", name=label, exact=True)
            if btn.count() and btn.first.is_visible():
                btn.first.click(timeout=1500)
                page.wait_for_timeout(500)
                return
        except Exception:
            pass


def load_lazy_content(page):
    height = page.evaluate("document.body.scrollHeight")
    y = 0
    while y < min(height, MAX_FULL_HEIGHT):
        y += 700
        page.evaluate(f"window.scrollTo(0, {y})")
        page.wait_for_timeout(250)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(800)


def main(list_file, out_dir):
    lines = [l.strip() for l in Path(list_file).read_text().splitlines()]
    entries = []
    for line in lines:
        if not line or line.startswith("#"):
            continue
        parts = line.split(maxsplit=1)
        url = parts[0]
        name = slug(parts[1]) if len(parts) > 1 else slug(re.sub(r"^https?://(www\.)?", "", url))
        entries.append((url, name))

    batch = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    target = Path(out_dir) / batch
    target.mkdir(parents=True, exist_ok=True)
    report = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1,
            locale="en-GB",
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"),
        )
        for url, name in entries:
            page = context.new_page()
            started = time.time()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                try:
                    page.wait_for_load_state("networkidle", timeout=12000)
                except Exception:
                    pass
                page.wait_for_timeout(1500)
                dismiss_popups(page)
                page.screenshot(path=str(target / f"{name}-top.jpg"), type="jpeg", quality=75)
                load_lazy_content(page)
                height = min(page.evaluate("document.body.scrollHeight"), MAX_FULL_HEIGHT)
                page.screenshot(path=str(target / f"{name}-full.jpg"), type="jpeg", quality=65,
                                full_page=True,
                                clip={"x": 0, "y": 0, "width": 1440, "height": max(height, 900)})
                try:
                    hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
                    (target / f"{name}-links.txt").write_text("\n".join(dict.fromkeys(hrefs)) + "\n")
                except Exception:
                    pass
                report.append(f"OK    {name}  {url}  ({time.time() - started:.0f}s)  title: {page.title()}")
            except Exception as exc:
                report.append(f"FAIL  {name}  {url}  {type(exc).__name__}: {str(exc)[:200]}")
            finally:
                page.close()
        browser.close()

    (target / "report.txt").write_text("\n".join(report) + "\n")
    print("\n".join(report))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
