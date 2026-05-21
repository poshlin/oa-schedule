#!/usr/bin/env python3
"""偵察線上班 admission_status 頁面結構"""
import asyncio, os
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env")

SYSTEM_URL = "https://corp.orangeapple.co/"
TARGET_URL = "https://corp.orangeapple.co/courses/dt/admission_status"

async def main():
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1920, "height": 1080}, locale="zh-TW")
        page = await ctx.new_page()

        print("[1] 登入...")
        await page.goto(SYSTEM_URL, wait_until="load")
        await page.locator("input[type='email']").fill(os.getenv("OA_EMAIL"))
        await page.locator("input[type='password']").fill(os.getenv("OA_PASSWORD"))
        await page.locator("input[type='password']").press("Enter")
        await page.wait_for_load_state("load")

        print("[2] 前往 admission_status...")
        await page.goto(TARGET_URL, wait_until="load")
        await page.wait_for_timeout(3000)
        print(f"    URL: {page.url}")

        Path(SCRIPT_DIR / "recon_online.html").write_text(await page.content(), encoding="utf-8")
        await page.screenshot(path=str(SCRIPT_DIR / "recon_online.png"), full_page=True)

        # 統計頁面結構
        stats = await page.evaluate("""
        () => {
          const tables = document.querySelectorAll('table');
          const tabs = document.querySelectorAll('[role="tab"], .nav-tabs > li > a, a[data-toggle="tab"]');
          const panes = document.querySelectorAll('.tab-pane');
          return {
            tableCount: tables.length,
            tabCount: tabs.length,
            paneCount: panes.length,
            paneIds: Array.from(panes).map(p => p.id).filter(Boolean).slice(0, 20),
            tabLabels: Array.from(tabs).map(a => (a.innerText || '').trim()).filter(Boolean).slice(0, 30),
            firstTableHTML: tables[0] ? tables[0].outerHTML.substring(0, 2000) : '(no table)',
            firstTableRows: tables[0] ? tables[0].querySelectorAll('tr').length : 0
          };
        }
        """)
        print(f"[3] 統計：")
        print(f"    tables: {stats['tableCount']}")
        print(f"    tabs: {stats['tabCount']}")
        print(f"    panes: {stats['paneCount']}")
        print(f"    pane ids: {stats['paneIds']}")
        print(f"    tab labels (前 30): {stats['tabLabels']}")
        print(f"    first table rows: {stats['firstTableRows']}")
        print(f"    [first table HTML 截一段]:")
        print("    " + stats['firstTableHTML'].replace("\n", "\n    "))

        await browser.close()

asyncio.run(main())
