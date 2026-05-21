#!/usr/bin/env python3
"""
橘子蘋果開班排程爬蟲（Playwright 版）
=====================================
兩個資料源：
  1. /courses/dt                 — 實體班（雙師班總覽，按城市分頁）
  2. /courses/dt/admission_status — 線上班（按星期分頁，含麥思、艾伯特等）

把抓到的時段寫回 ../index.html 的 SCHEDULE_DATA_START/END 區塊。

用法：
    python3 scrape.py              # 正式跑（無頭）
    python3 scrape.py --dry-run    # 只抓不寫
    python3 scrape.py --debug      # 顯示 Firefox 視窗
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
DT_URL = "https://corp.orangeapple.co/courses/dt"
ADMISSION_URL = "https://corp.orangeapple.co/courses/dt/admission_status"

EMAIL = os.getenv("OA_EMAIL")
PASSWORD = os.getenv("OA_PASSWORD")

# ─── 實體班課程對應（/courses/dt 用） ─────────────────────────────────────────
COURSE_MAP = {
    "菁英":     "elite",
    "Roblox":   "roblox",
    "麥塊":     "minecraft",
    "Minecraft":"minecraft",
    "創意積木": "creative_blocks",
    "Scratch":  "creative_blocks",
    "數學":     "math",
    "選手班":   "competition",
    "艾伯特":   "aibot",
}
def normalize_course_text(text):
    if not text:
        return None, ""
    m = re.search(r'[(\(]([^)\)]+)[)\)]', text)
    level = m.group(1).strip() if m else ""
    base = re.sub(r'[(\(].*?[)\)]', '', text).strip()
    for k, cid in COURSE_MAP.items():
        if k in base:
            return cid, level
    return base.lower() or None, level

# ─── 線上班 tr class 對應（admission_status 用） ─────────────────────────────
ONLINE_COURSE_CLASS_MAP = {
    "course_aibot":   "aibot",
    "course_dt":      "elite",
    "course_math":    "math",
    "course_mc":      "minecraft",
    "course_roblox":  "roblox",
    # course_topic = 選手班，不對家長開放試聽，跳過
}
# week-N → 英文星期
WEEK_TO_DAY = {"week-1":"Mon", "week-2":"Tue", "week-3":"Wed",
               "week-4":"Thu", "week-5":"Fri", "week-6":"Sat", "week-0":"Sun"}

# ─── 教室名稱對應 ─────────────────────────────────────────────────────────────
def load_classrooms_from_index():
    html = INDEX_HTML.read_text(encoding="utf-8")
    return [{"id": rid, "name": name} for rid, name in
            re.findall(r'\{\s*id:\s*"([^"]+)",\s*name:\s*"([^"]+)"', html)]

def normalize_classroom_id(internal_name, idx):
    if any(k in internal_name for k in ("線上", "遠距", "橘頭")):
        return "online"
    head = re.split(r'[｜_]', internal_name, maxsplit=1)[0].strip()
    head = head.replace("教室", "").strip()
    for c in idx:
        cname = c["name"].replace("教室", "").strip()
        if cname == head or cname.startswith(head) or head.startswith(cname):
            return c["id"]
    for c in idx:
        if head and head[0] in c["name"]:
            return c["id"]
    return None

# ─── 登入 ────────────────────────────────────────────────────────────────────
async def login(page):
    if not EMAIL or not PASSWORD:
        sys.exit("ERROR：.env 缺少 OA_EMAIL / OA_PASSWORD")
    await page.goto(SYSTEM_URL, wait_until="load")
    await page.locator("input[type='email']").fill(EMAIL)
    await page.locator("input[type='password']").fill(PASSWORD)
    await page.locator("input[type='password']").press("Enter")
    await page.wait_for_load_state("load")
    print(f"[登入] OK → {page.url}")

# ─── 實體：/courses/dt ────────────────────────────────────────────────────────
async def scrape_physical(page):
    print(f"[實體] {DT_URL}")
    await page.goto(DT_URL, wait_until="load")
    await page.wait_for_timeout(2500)

    data = await page.evaluate("""
    () => {
      const cityMap = {};
      document.querySelectorAll('a[data-toggle="tab"], a[role="tab"]').forEach(a => {
        const href = (a.getAttribute('href') || '').replace('#', '');
        const txt = (a.innerText || '').trim();
        if (/^city-\\d+$/.test(href) && txt) cityMap[txt] = href;
      });

      const result = [];
      for (const [cityName, cityId] of Object.entries(cityMap)) {
        if (cityName === '合計') continue;
        const cityNum = cityId.split('-')[1];
        for (const stype of ['weekend', 'weekday']) {
          const pane = document.getElementById(stype + '-' + cityNum);
          if (!pane) continue;
          const table = pane.querySelector('table');
          if (!table) continue;

          const rows = Array.from(table.querySelectorAll('tbody tr'));
          for (const tr of rows) {
            const cells = Array.from(tr.children);
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
            if (!roomName) continue;

            if (stype === 'weekend' && slotCells.length >= 10) {
              const last10 = slotCells.slice(-10);
              last10.forEach((cell, i) => {
                const txt = (cell.innerText || '').trim();
                if (!txt || txt === '-') return;
                const day = i < 5 ? 'Sat' : 'Sun';
                const slot = (i % 5) + 1;
                const lines = txt.split('\\n').map(s => s.trim()).filter(Boolean);
                const courseText = lines[lines.length - 1] || '';
                result.push({
                  city: cityName, stype: 'weekend',
                  internal_name: roomName, day, slot,
                  course_text: courseText
                });
              });
            } else if (stype === 'weekday' && slotCells.length >= 25) {
              const last25 = slotCells.slice(-25);
              const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
              last25.forEach((cell, i) => {
                const txt = (cell.innerText || '').trim();
                if (!txt || txt === '-') return;
                const dayIdx = Math.floor(i / 5);
                const slot = (i % 5) + 1;
                const lines = txt.split('\\n').map(s => s.trim()).filter(Boolean);
                const courseText = lines[lines.length - 1] || '';
                result.push({
                  city: cityName, stype: 'weekday',
                  internal_name: roomName, day: days[dayIdx], slot,
                  course_text: courseText
                });
              });
            }
          }
        }
      }
      return result;
    }
    """)
    print(f"    抓到 {len(data)} 筆原始資料")
    return data

# ─── 線上：/courses/dt/admission_status ──────────────────────────────────────
async def scrape_online(page):
    print(f"[線上] {ADMISSION_URL}")
    await page.goto(ADMISSION_URL, wait_until="load")
    await page.wait_for_timeout(2500)

    data = await page.evaluate("""
    () => {
      const result = [];
      const panes = document.querySelectorAll('div[id^="week-"]');
      for (const pane of panes) {
        const weekId = pane.id;  // week-1 / week-2 / ... / week-0
        const table = pane.querySelector('table');
        if (!table) continue;
        const rows = table.querySelectorAll('tr.course');
        for (const tr of rows) {
          // 課程類別從 tr.classList 找 course_xxx
          let courseClass = '';
          for (const c of tr.classList) {
            if (c.startsWith('course_')) { courseClass = c; break; }
          }
          if (!courseClass) continue;

          // 第一格 <a> 內 text 含有：教室名 + 課程- 週X 第 N 時段 (HH:MM ~ HH:MM)
          const firstA = tr.querySelector('td a');
          if (!firstA) continue;
          const txt = (firstA.innerText || '').trim();

          // 抓時段範圍
          const timeMatch = txt.match(/(\\d{1,2}:\\d{2}\\s*~\\s*\\d{1,2}:\\d{2})/);
          if (!timeMatch) continue;
          const timeLabel = timeMatch[1].replace(/\\s+/g, ' ');

          result.push({
            week_id: weekId,
            course_class: courseClass,
            time_label: timeLabel,
            raw_text: txt
          });
        }
      }
      return result;
    }
    """)
    print(f"    抓到 {len(data)} 筆原始資料")
    return data

# ─── 寫回 index.html ─────────────────────────────────────────────────────────
def to_js_block(schedules):
    lines = []
    for s in schedules:
        # 線上有 time_label，實體有 time_slot
        parts = [
            f'classroom_id: {json.dumps(s["classroom_id"], ensure_ascii=False)}',
            f'course_id: {json.dumps(s["course_id"], ensure_ascii=False)}',
            f'course_level: {json.dumps(s.get("course_level", ""), ensure_ascii=False)}',
            f'day: {json.dumps(s["day"])}',
        ]
        if "time_label" in s:
            parts.append(f'time_label: {json.dumps(s["time_label"])}')
        else:
            parts.append(f'time_slot: {s["time_slot"]}')
        lines.append("    { " + ", ".join(parts) + " },")
    body = "\n".join(lines).rstrip(",")
    return (
        "/* SCHEDULE_DATA_START */\n"
        "window.OA_SCHEDULE = {\n"
        f'  updated_at: "{datetime.now().strftime("%Y-%m-%d %H:%M")}",\n'
        '  source: "corp.orangeapple.co/courses/dt + /admission_status",\n'
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
    INDEX_HTML.write_text(pattern.sub(to_js_block(schedules), html), encoding="utf-8")
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

            # ── 1) 實體 ─────────────────────────────────────────
            raw_physical = await scrape_physical(page)
            physical_normalized = []
            unknown_rooms = set()
            for r in raw_physical:
                cid = normalize_classroom_id(r["internal_name"], classrooms_idx)
                if not cid:
                    unknown_rooms.add(r["internal_name"])
                    continue
                if cid == "online":
                    # /courses/dt 內的線上資料不準，跳過——改用 admission_status
                    continue
                course_id, level = normalize_course_text(r["course_text"])
                if not course_id:
                    continue
                physical_normalized.append({
                    "classroom_id": cid,
                    "course_id": course_id,
                    "course_level": level,
                    "day": r["day"],
                    "time_slot": r["slot"],
                })
            print(f"    實體規範化後 {len(physical_normalized)} 筆")
            if unknown_rooms:
                print(f"    [WARN] 對應不到的實體教室 ({len(unknown_rooms)}): {sorted(unknown_rooms)[:5]}")

            # ── 2) 線上 ─────────────────────────────────────────
            raw_online = await scrape_online(page)
            online_normalized = []
            unknown_classes = set()
            for r in raw_online:
                course_id = ONLINE_COURSE_CLASS_MAP.get(r["course_class"])
                if not course_id:
                    unknown_classes.add(r["course_class"])
                    continue
                day = WEEK_TO_DAY.get(r["week_id"])
                if not day:
                    continue
                online_normalized.append({
                    "classroom_id": "online",
                    "course_id": course_id,
                    "course_level": "",
                    "day": day,
                    "time_label": r["time_label"],
                })
            print(f"    線上規範化後 {len(online_normalized)} 筆")
            if unknown_classes:
                print(f"    [INFO] 跳過的線上課程類型 ({len(unknown_classes)}): {sorted(unknown_classes)}")

            # ── 3) 合併 + 去重 ──────────────────────────────────
            all_schedules = physical_normalized + online_normalized
            seen = set()
            deduped = []
            for s in all_schedules:
                key = (s["classroom_id"], s["course_id"], s.get("course_level", ""),
                       s["day"], s.get("time_slot"), s.get("time_label"))
                if key in seen: continue
                seen.add(key)
                deduped.append(s)
            print(f"\n[結果] 總計 {len(deduped)} 筆（實體 {len(physical_normalized)} + 線上 {len(online_normalized)} 去重）")

            if args.dry_run:
                print("[DRY RUN] 前 5 筆線上預覽：")
                for s in online_normalized[:5]:
                    print(f"  {s}")
                return

            write_back_to_html(deduped)
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
