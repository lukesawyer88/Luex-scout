"""Fetch only the main shot image (og:image) for each URL, quickly and in parallel."""
import asyncio, sys, re
from datetime import datetime, timezone
from pathlib import Path
from playwright.async_api import async_playwright

async def worker(ctx, queue, target, report):
    page = await ctx.new_page()
    while True:
        try:
            url, name = queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            og = await page.get_attribute('meta[property="og:image"]', "content", timeout=5000)
            if not og:
                raise RuntimeError("no og:image")
            r = await page.request.get(og, timeout=30000)
            ext = ".png" if "png" in r.headers.get("content-type", "") else ".jpg"
            (target / f"{name}{ext}").write_bytes(await r.body())
            report.append(f"OK    {name}  {url}")
            await asyncio.sleep(1.5)
        except Exception as e:
            report.append(f"FAIL  {name}  {url}  {type(e).__name__}")
    await page.close()

async def main(list_file, out_dir):
    entries = []
    for line in Path(list_file).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(maxsplit=1)
        entries.append((parts[0], parts[1] if len(parts) > 1 else re.sub(r"\W+", "-", parts[0])[-60:]))
    target = Path(out_dir) / ("img-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M"))
    target.mkdir(parents=True, exist_ok=True)
    queue = asyncio.Queue()
    for e in entries:
        queue.put_nowait(e)
    report = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                                    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"))
        await asyncio.gather(*(worker(ctx, queue, target, report) for _ in range(3)))
        await browser.close()
    (target / "report.txt").write_text("\n".join(sorted(report)) + "\n")
    print(f"{sum(r.startswith('OK') for r in report)} ok of {len(entries)}")

if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2]))
