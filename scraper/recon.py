#!/usr/bin/env python3
"""偵察用：登入 corp，存下 /courses/dt 的 HTML 與截圖，給我看清楚 DOM 結構"""
import asyncio, os
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env")

SYSTEM_URL = "https://corp.orangeapple.co/"
TARGET_URL = "https://corp.orangeapple.co/courses/dt"

async def main():
    email = os.getenv("OA_EMAIL")
    pw    = os.getenv("OA_PASSWORD")
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1920, "height": 1080}, locale="zh-TW")
        page = await ctx.new_page()

        print("[1] 登入...")
        await page.goto(SYSTEM_URL, wait_until="load")
        await page.locator("input[type='email']").fill(email)
        await page.locator("input[type='password']").fill(pw)
        await page.locator("input[type='password']").press("Enter")
        await page.wait_for_load_state("load")
        print(f"    login URL: {page.url}")

        print("[2] 前往 /courses/dt...")
        await page.goto(TARGET_URL, wait_until="load")
        await page.wait_for_timeout(2000)
        print(f"    page URL: {page.url}")

        Path(SCRIPT_DIR / "recon_initial.html").write_text(await page.content(), encoding="utf-8")
        await page.screenshot(path=str(SCRIPT_DIR / "recon_initial.png"), full_page=True)
        print("    存了 recon_initial.html / .png")

        print("[3] 點臺北市 + 週末...")
        for label in ["臺北市", "週末"]:
            try:
                await page.locator(f"text={label}").first.click()
                await page.wait_for_timeout(1500)
                print(f"    ✓ 點到「{label}」")
            except Exception as e:
                print(f"    ✗ 點不到「{label}」: {e}")

        Path(SCRIPT_DIR / "recon_taipei_weekend.html").write_text(await page.content(), encoding="utf-8")
        await page.screenshot(path=str(SCRIPT_DIR / "recon_taipei_weekend.png"), full_page=True)
        print("    存了 recon_taipei_weekend.html / .png")

        # 抽出第一個 table 的結構
        table_info = await page.evaluate("""
        () => {
          const tables = Array.from(document.querySelectorAll('table'));
          return tables.map((t, i) => ({
            index: i,
            classes: t.className,
            rowCount: t.querySelectorAll('tr').length,
            firstRowText: (t.querySelector('tr')?.innerText || '').substring(0, 200)
          }));
        }
        """)
        print(f"[4] 頁面上的 table 數量: {len(table_info)}")
        for t in table_info[:5]:
            print(f"    [{t['index']}] class={t['classes']!r} rows={t['rowCount']}")
            print(f"        first row: {t['firstRowText']!r}")

        # 找 city tabs 的容器
        tabs_info = await page.evaluate("""
        () => {
          const out = {};
          for (const sel of ['nav', 'ul.nav', '.nav-tabs', '[role="tablist"]', '.tabs']) {
            const els = document.querySelectorAll(sel);
            if (els.length) out[sel] = Array.from(els).map(e => (e.innerText||'').substring(0,150));
          }
          return out;
        }
        """)
        print(f"[5] tab 容器候選：")
        for sel, contents in tabs_info.items():
            print(f"    {sel}: {len(contents)} 個")
            for c in contents[:3]:
                print(f"      → {c!r}")

        await browser.close()

asyncio.run(main())
