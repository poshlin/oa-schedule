#!/usr/bin/env python3
"""偵察台南市週間表，找出 tainan_dongning aibot 那筆從哪來"""
import asyncio, os
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env")

async def main():
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1920, "height": 1080}, locale="zh-TW")
        page = await ctx.new_page()
        await page.goto("https://corp.orangeapple.co/", wait_until="load")
        await page.locator("input[type='email']").fill(os.getenv("OA_EMAIL"))
        await page.locator("input[type='password']").fill(os.getenv("OA_PASSWORD"))
        await page.locator("input[type='password']").press("Enter")
        await page.wait_for_load_state("load")
        await page.goto("https://corp.orangeapple.co/courses/dt", wait_until="load")
        await page.wait_for_timeout(2500)

        info = await page.evaluate("""
        () => {
          // 我們要看臺南市，先找 city-N
          const cityMap = {};
          document.querySelectorAll('a[data-toggle="tab"], a[role="tab"]').forEach(a => {
            const href = (a.getAttribute('href') || '').replace('#', '');
            const txt = (a.innerText || '').trim();
            if (/^city-\\d+$/.test(href) && txt) cityMap[txt] = href.split('-')[1];
          });
          const targetCities = ['臺南市', '新北市', '臺中市'];
          const out = {};
          for (const city of targetCities) {
            const num = cityMap[city];
            if (!num) continue;
            const pane = document.getElementById('weekday-' + num);
            if (!pane) continue;
            const table = pane.querySelector('table');
            if (!table) continue;

            // 展開 rowspan
            function expand(rows) {
              const mem = {};
              return rows.map(tr => {
                const tds = Array.from(tr.children);
                const r = [];
                let ci = 0, li = 0;
                while (li < tds.length || (mem[ci] && mem[ci].rem > 0)) {
                  if (mem[ci] && mem[ci].rem > 0) {
                    r.push(mem[ci].t); mem[ci].rem--;
                    if (mem[ci].rem === 0) delete mem[ci];
                    ci++; continue;
                  }
                  if (li >= tds.length) break;
                  const td = tds[li];
                  const sp = parseInt(td.getAttribute('rowspan')||'1',10);
                  const t = (td.innerText||'').trim();
                  r.push(t);
                  if (sp > 1) mem[ci] = { t, rem: sp - 1 };
                  li++; ci++;
                }
                return r;
              });
            }

            const rows = expand(Array.from(table.querySelectorAll('tbody tr')));
            // 只列有資料的 row（任一 slot 有 N/N/N 數字）
            const dataRows = rows
              .filter(r => r.slice(2).some(t => /\\d+\\s*\\/\\s*\\d+\\s*\\/\\s*\\d+/.test(t)))
              .map(r => ({
                group: r[0],
                room: r[1],
                slots: r.slice(2).map(t => t || '-')
              }));
            out[city] = dataRows;
          }
          return out;
        }
        """)

        import json
        print(json.dumps(info, ensure_ascii=False, indent=2))
        await browser.close()

asyncio.run(main())
