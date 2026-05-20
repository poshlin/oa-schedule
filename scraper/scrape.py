#!/usr/bin/env python3
"""
橘子蘋果雙師班排程爬蟲（Playwright 版）
=====================================
登入 corp.orangeapple.co/courses/dt，抓取所有城市 × 週末/週間 的開班時段，
把結果寫回 ../index.html 中 SCHEDULE_DATA_START / SCHEDULE_DATA_END 區塊。

用法：
    python3 scrape.py              # 正式跑（無頭）
    python3 scrape.py --dry-run    # 只抓不寫
    python3 scrape.py --debug      # 顯示 Firefox 視窗

設定：在同資料夾 .env 內填入
    OA_EMAIL=your_email
    OA_PASSWORD=your_password
"""

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import async_playwright

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
INDEX_HTML = PROJECT_DIR / "index.html"
load_dotenv(SCRIPT_DIR / ".env")

SYSTEM_URL = "https://corp.orangeapple.co/"
TARGET_URL = "https://corp.orangeapple.co/courses/dt"

EMAIL = os.getenv("OA_EMAIL")
PASSWORD = os.getenv("OA_PASSWORD")

# ─── 課程類型對應：corp 內部 → index.html 內 COURSE_INTERNAL_TO_DISPLAY 認得的 id ─
COURSE_MAP = {
    "菁英":     "elite",
    "Roblox":   "roblox",
    "麥塊":     "minecraft",
    "Minecraft":"minecraft",
    "創意積木": "creative_blocks",
    "Scratch":  "creative_blocks",
    "數學":     "math",
    "選手班":   "competition",
}
def normalize_course(text):
    if not text:
        return None, ""
    m = re.search(r'[(\(]([^)\)]+)[)\)]', text)
    level = m.group(1).strip() if m else ""
    base = re.sub(r'[(\(].*?[)\)]', '', text).strip()
    for k, cid in COURSE_MAP.items():
        if k in base:
            return cid, level
    return base.lower() or None, level

# ─── 教室名稱對應：corp 內部「古亭｜本部5樓之3_A教室」→ index.html classroom id ─
def load_classrooms_from_index():
    html = INDEX_HTML.read_text(encoding="utf-8")
    # 解析 OA_CLASSROOMS.classrooms 內每筆 id 與 name
    return [{"id": rid, "name": name} for rid, name in
            re.findall(r'\{\s*id:\s*"([^"]+)",\s*name:\s*"([^"]+)"', html)]

def normalize_classroom_id(internal_name, idx):
    """從『古亭｜本部5樓之3_A教室』推回 'guting' id"""
    if any(k in internal_name for k in ("線上", "遠距", "橘頭")):
        return "online"
    head = re.split(r'[｜_]', internal_name, maxsplit=1)[0].strip()
    head = head.replace("教室", "").strip()
    for c in idx:
        cname = c["name"].replace("教室", "").strip()
        if cname == head or cname.startswith(head) or head.startswith(cname):
            return c["id"]
    # 模糊比對：拿 head 第一個字元在所有 name 中找
    for c in idx:
        if head and head[0] in c["name"]:
            return c["id"]
    return None

# ─── 登入 + 抓資料 ─────────────────────────────────────────────────────────────
async def login(page):
    if not EMAIL or not PASSWORD:
        sys.exit("ERROR：.env 缺少 OA_EMAIL / OA_PASSWORD")
    await page.goto(SYSTEM_URL, wait_until="load")
    await page.locator("input[type='email']").fill(EMAIL)
    await page.locator("input[type='password']").fill(PASSWORD)
    await page.locator("input[type='password']").press("Enter")
    await page.wait_for_load_state("load")
    print(f"[登入] OK → {page.url}")

async def extract_all_schedules(page):
    """
    一次抓取所有城市 × 週末/週間 的時段資料。
    結構：每個城市對應一個 #city-N tab pane，內含 #weekend-N 和 #weekday-N，
    各自有一個 table。
    """
    data = await page.evaluate("""
    () => {
      // 1) 找出城市 tab 連結 → {city_name: city-N id}
      const cityMap = {};
      document.querySelectorAll('a[data-toggle="tab"], a[role="tab"]').forEach(a => {
        const href = (a.getAttribute('href') || '').replace('#', '');
        const txt = (a.innerText || '').trim();
        if (/^city-\\d+$/.test(href) && txt) {
          cityMap[txt] = href;
        }
      });

      // 2) 逐城市抓 weekend / weekday 表格
      const result = [];
      for (const [cityName, cityId] of Object.entries(cityMap)) {
        if (cityName === '合計') continue;  // 跳過總和分頁
        const cityPane = document.getElementById(cityId);
        if (!cityPane) continue;
        const cityNum = cityId.split('-')[1];

        for (const stype of ['weekend', 'weekday']) {
          const pane = document.getElementById(stype + '-' + cityNum);
          if (!pane) continue;
          const table = pane.querySelector('table');
          if (!table) continue;

          // 解析 table：找出每一列的教室名與 10 個時段格
          const rows = Array.from(table.querySelectorAll('tbody tr'));
          for (const tr of rows) {
            const cells = Array.from(tr.children);
            // 找含「教室」的 td 作為教室名
            let roomName = '';
            const slotCells = [];
            for (const td of cells) {
              const text = (td.innerText || '').trim();
              if (!roomName && text.includes('教室') && !text.match(/\\d+\\s*\\/\\s*\\d+/)) {
                roomName = text;
              } else {
                slotCells.push(td);
              }
            }
            if (!roomName || slotCells.length < 10) continue;

            // 取最後 10 格作為 Sat1-5 / Sun1-5（週末）或 Mon1-5 / ... 5天x5時段（週間）
            const last10 = slotCells.slice(-10);
            const last25 = slotCells.slice(-25);  // 週間表是 5天 × 5時段

            if (stype === 'weekend') {
              last10.forEach((cell, i) => {
                const txt = (cell.innerText || '').trim();
                if (!txt || txt === '-') return;
                const day = i < 5 ? 'Sat' : 'Sun';
                const slot = (i % 5) + 1;
                // 最後一行通常是課程類型
                const lines = txt.split('\\n').map(s => s.trim()).filter(Boolean);
                const courseText = lines[lines.length - 1] || '';
                result.push({
                  city: cityName,
                  stype: 'weekend',
                  internal_name: roomName,
                  day, slot,
                  course_text: courseText,
                  raw: txt
                });
              });
            } else {
              // weekday: 5 天 (Mon-Fri) × 5 時段
              const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
              last25.forEach((cell, i) => {
                const txt = (cell.innerText || '').trim();
                if (!txt || txt === '-') return;
                const dayIdx = Math.floor(i / 5);
                const slot = (i % 5) + 1;
                const lines = txt.split('\\n').map(s => s.trim()).filter(Boolean);
                const courseText = lines[lines.length - 1] || '';
                result.push({
                  city: cityName,
                  stype: 'weekday',
                  internal_name: roomName,
                  day: days[dayIdx],
                  slot,
                  course_text: courseText,
                  raw: txt
                });
              });
            }
          }
        }
      }
      return result;
    }
    """)
    return data

# ─── 寫回 index.html ───────────────────────────────────────────────────────────
def to_js_block(schedules):
    lines = []
    for s in schedules:
        lines.append(
            f'    {{ classroom_id: {json.dumps(s["classroom_id"], ensure_ascii=False)}, '
            f'course_id: {json.dumps(s["course_id"], ensure_ascii=False)}, '
            f'course_level: {json.dumps(s.get("course_level", ""), ensure_ascii=False)}, '
            f'day: {json.dumps(s["day"])}, '
            f'time_slot: {s["time_slot"]} }},'
        )
    body = "\n".join(lines).rstrip(",")
    return (
        "/* SCHEDULE_DATA_START */\n"
        "window.OA_SCHEDULE = {\n"
        f'  updated_at: "{datetime.now().strftime("%Y-%m-%d %H:%M")}",\n'
        '  source: "corp.orangeapple.co/courses/dt",\n'
        "  schedules: [\n"
        f"{body}\n"
        "  ]\n"
        "};\n"
        "/* SCHEDULE_DATA_END */"
    )

def write_back_to_html(schedules):
    html = INDEX_HTML.read_text(encoding="utf-8")
    pattern = re.compile(r"/\* SCHEDULE_DATA_START \*/.*?/\* SCHEDULE_DATA_END \*/", re.DOTALL)
    if not pattern.search(html):
        sys.exit("ERROR：index.html 找不到 SCHEDULE_DATA_START/END 標記")
    new_html = pattern.sub(to_js_block(schedules), html)
    INDEX_HTML.write_text(new_html, encoding="utf-8")
    print(f"[寫入] {INDEX_HTML}")

# ─── 主流程 ──────────────────────────────────────────────────────────────────
async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    classrooms_idx = load_classrooms_from_index()
    print(f"[INFO] 從 index.html 取得 {len(classrooms_idx)} 個教室對應")

    async with async_playwright() as pw:
        browser = await pw.firefox.launch(headless=not args.debug)
        ctx = await browser.new_context(viewport={"width": 1920, "height": 1080}, locale="zh-TW")
        page = await ctx.new_page()
        try:
            await login(page)
            print(f"[前往] {TARGET_URL}")
            await page.goto(TARGET_URL, wait_until="load")
            await page.wait_for_timeout(2500)

            raw = await extract_all_schedules(page)
            print(f"[抓到] 原始時段 {len(raw)} 筆")

            # 規範化
            normalized = []
            unknown_rooms = set()
            unknown_courses = set()
            for r in raw:
                cid = normalize_classroom_id(r["internal_name"], classrooms_idx)
                if not cid:
                    unknown_rooms.add(r["internal_name"])
                    continue
                course_id, level = normalize_course(r["course_text"])
                if not course_id:
                    unknown_courses.add(r["course_text"])
                    continue
                normalized.append({
                    "classroom_id": cid,
                    "course_id": course_id,
                    "course_level": level,
                    "day": r["day"],
                    "time_slot": r["slot"],
                })

            if unknown_rooms:
                print(f"[WARN] 對應不到 classroom_id 的教室名 ({len(unknown_rooms)} 個)：")
                for n in sorted(unknown_rooms)[:10]:
                    print(f"        {n!r}")
            if unknown_courses:
                print(f"[WARN] 對應不到 course_id 的課程名 ({len(unknown_courses)} 個)：")
                for n in sorted(unknown_courses)[:10]:
                    print(f"        {n!r}")

            # 去重（相同 classroom_id + course_id + course_level + day + slot）
            seen = set()
            deduped = []
            for s in normalized:
                key = (s["classroom_id"], s["course_id"], s["course_level"], s["day"], s["time_slot"])
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(s)

            print(f"[結果] 規範化後 {len(deduped)} 筆（去重後）")

            if args.dry_run:
                print("[DRY RUN] 不寫檔。前 5 筆預覽：")
                for s in deduped[:5]:
                    print(f"  {s}")
                return

            write_back_to_html(deduped)
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
