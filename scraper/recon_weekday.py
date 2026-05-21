#!/usr/bin/env python3
"""偵察週間表結構：dump 新北市 weekday pane 的實際 thead + tbody"""
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

        # 對新北市（city-2）的 weekday pane 做完整 dump
        info = await page.evaluate("""
        () => {
          // 找出每個城市對應的 city-N pane id 與 weekday-N table 的 row 數量
          const cityMap = {};
          document.querySelectorAll('a[data-toggle="tab"], a[role="tab"]').forEach(a => {
            const href = (a.getAttribute('href') || '').replace('#', '');
            const txt = (a.innerText || '').trim();
            if (/^city-\\d+$/.test(href) && txt) cityMap[txt] = href.split('-')[1];
          });

          const results = {};
          for (const [city, num] of Object.entries(cityMap)) {
            if (city === '合計') continue;
            const wePane = document.getElementById('weekday-' + num);
            if (!wePane) { results[city] = '無 weekday pane'; continue; }
            const table = wePane.querySelector('table');
            if (!table) { results[city] = '無 table'; continue; }

            // thead 結構
            const thead = table.querySelector('thead');
            let theadDesc = '無 thead';
            if (thead) {
              const rows = Array.from(thead.querySelectorAll('tr'));
              theadDesc = rows.map((r, i) => {
                const cells = Array.from(r.children).map(td =>
                  `[${(td.innerText||'').trim()}|span=${td.getAttribute('colspan')||1}]`
                ).join(' ');
                return `tr${i}: ${cells}`;
              }).join('\\n  ');
            }

            // tbody 第一個非空 row 的 cell 數
            const tbodyRows = Array.from(table.querySelectorAll('tbody tr'));
            const firstRowCells = tbodyRows[0] ? Array.from(tbodyRows[0].children).length : 0;
            const totalRows = tbodyRows.length;

            // 找有資料的 row（slot cell 非「-」、非空）
            const dataRows = [];
            for (const tr of tbodyRows) {
              const cells = Array.from(tr.children);
              const texts = cells.map(c => (c.innerText||'').trim());
              const hasData = texts.some(t => t && t !== '-' && /\\d+\\s*\\/\\s*\\d+/.test(t));
              if (hasData) {
                dataRows.push({ cellCount: cells.length, texts: texts.map(t => t.substring(0, 30)) });
              }
            }

            results[city] = {
              thead: theadDesc,
              totalTbodyRows: totalRows,
              firstRowCellCount: firstRowCells,
              dataRows: dataRows.slice(0, 5)  // 取前 5 筆有資料的 row
            };
          }
          return results;
        }
        """)

        import json
        print(json.dumps(info, ensure_ascii=False, indent=2))
        await browser.close()

asyncio.run(main())
