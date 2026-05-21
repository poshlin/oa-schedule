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
    """只抓 OA_CLASSROOMS.classrooms 內的物件，用 city: 欄位辨識，避免誤抓 courses"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    return [{"id": rid, "name": name} for rid, name in
            re.findall(r'\{\s*id:\s*"([^"]+)",\s*name:\s*"([^"]+)"[^}]*city:', html)]

def _norm_room(s):
    """剝掉噪音字元 + 常見城市前綴，讓 cname「東區教室」與 corp 的「嘉義東區」對得上

    - 「教室／市／縣」一律剝掉
    - 「嘉義／台南／臺南／高雄」這類城市名作為前綴時也剝掉
      （台中/台北/新北/新竹/桃園 不剝，因為他們的教室名本身就常用該前綴）
    """
    s = s.replace("教室", "").replace("市", "").replace("縣", "").strip()
    for p in ["嘉義", "台南", "臺南", "高雄"]:
        if s.startswith(p) and len(s) > len(p):
            return s[len(p):]
    return s

def normalize_classroom_id(internal_name, idx):
    """corp 內部教室名 → classrooms.json 內 id

    對應規則（每個 part 依序試）：
      1) 完全相符（避免「新莊」對到「新莊魔力」）
      2) head.startswith(cname) 取最長（e.g. 板橋旗艦 → 板橋）
      3) cname.startswith(head) 且唯一候選

    處理的命名格式：
      a) 古亭｜本部5樓之3_A教室          （head=古亭）
      b) 新莊｜建中外語 203教室          （head=新莊 → 新莊教室）
      c) 新莊魔力｜魔力文理補習班        （head=新莊魔力 → 新莊魔力教室）
      d) 板橋旗艦｜A教室                （head=板橋旗艦 → 板橋）
      e) 台中_北屯直營_B教室             （第一段「台中」沒對到，第二段「北屯直營」→ 北屯）
      f) 嘉義東區 直營B教室              （normalize 後 = 嘉義東區 = 嘉義市東區）
      g) 基隆教室                       （head=基隆 → 基隆教室 完全相符）
    """
    if any(k in internal_name for k in ("線上", "遠距", "橘頭")):
        return "online"

    parts = [_norm_room(p) for p in re.split(r'[｜_ ]', internal_name)]
    parts = [p for p in parts if p]
    cnames = [(c, _norm_room(c["name"])) for c in idx]

    for head in parts:
        # 1) 完全相符
        for c, cname in cnames:
            if cname == head:
                return c["id"]
        # 2) head.startswith(cname) — 取最長
        best_id, best_len = None, 0
        for c, cname in cnames:
            if cname and head.startswith(cname) and len(cname) > best_len:
                best_id, best_len = c["id"], len(cname)
        if best_id:
            return best_id

    # 3) cname.startswith(head) 且唯一
    for head in parts:
        candidates = [c["id"] for c, cname in cnames if cname.startswith(head)]
        if len(candidates) == 1:
            return candidates[0]
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

      // 展開 rowspan：把每一列攤平成 N 個 cell（包含從上方 rowspan 繼承的）
      function expandRowspan(rows) {
        const spanMem = {};  // col -> { text, remaining }
        return rows.map(tr => {
          const tds = Array.from(tr.children);
          const out = [];
          let cellIdx = 0, colIdx = 0;
          while (cellIdx < tds.length || (spanMem[colIdx] && spanMem[colIdx].remaining > 0)) {
            if (spanMem[colIdx] && spanMem[colIdx].remaining > 0) {
              out.push(spanMem[colIdx].text);
              spanMem[colIdx].remaining--;
              if (spanMem[colIdx].remaining === 0) delete spanMem[colIdx];
              colIdx++;
              continue;
            }
            if (cellIdx >= tds.length) break;
            const td = tds[cellIdx];
            const span = parseInt(td.getAttribute('rowspan') || '1', 10);
            const text = (td.innerText || '').trim();
            out.push(text);
            if (span > 1) spanMem[colIdx] = { text, remaining: span - 1 };
            cellIdx++; colIdx++;
          }
          return out;
        });
      }

      const result = [];
      for (const [cityName, cityId] of Object.entries(cityMap)) {
        if (cityName === '合計') continue;
        const cityNum = cityId.split('-')[1];
        for (const stype of ['weekend', 'weekday']) {
          const pane = document.getElementById(stype + '-' + cityNum);
          if (!pane) continue;
          const table = pane.querySelector('table');
          if (!table) continue;

          // 從 thead 動態讀每個 column 對應的 (day, slot)
          // 週末表 thead：Sat. (colspan=5) Sun. (colspan=5) + 第二列 1 2 3 4 5 1 2 3 4 5
          // 週間表 thead：Mon. Tues. Weds. Thurs. Fri. (各 colspan=N) + 第二列時段號
          function parseHeadColumns(table) {
            const thead = table.querySelector('thead');
            if (!thead) return null;
            const rows = thead.querySelectorAll('tr');
            if (rows.length < 2) return null;
            const dayPerCol = [];
            Array.from(rows[0].children).forEach(th => {
              const text = (th.innerText || '').trim();
              const span = parseInt(th.getAttribute('colspan') || '1', 10);
              for (let i = 0; i < span; i++) dayPerCol.push(text);
            });
            const slotPerCol = Array.from(rows[1].children).map(th => (th.innerText || '').trim());
            const mapDay = txt => {
              if (/Sat/i.test(txt)) return 'Sat';
              if (/Sun/i.test(txt)) return 'Sun';
              if (/Mon/i.test(txt)) return 'Mon';
              if (/Tue/i.test(txt)) return 'Tue';
              if (/Wed/i.test(txt)) return 'Wed';
              if (/Thu/i.test(txt)) return 'Thu';
              if (/Fri/i.test(txt)) return 'Fri';
              return null;
            };
            return dayPerCol.map((d, i) => ({
              day: mapDay(d),
              slot: parseInt(slotPerCol[i], 10)
            })).filter(c => c.day && !isNaN(c.slot));
          }

          const colMap = parseHeadColumns(table);
          if (!colMap || colMap.length === 0) continue;
          const numSlots = colMap.length;

          const rows = Array.from(table.querySelectorAll('tbody tr'));
          const expanded = expandRowspan(rows);

          for (const row of expanded) {
            if (row.length < 2 + numSlots) continue;
            const groupName = row[0] || '';
            const roomName  = row[1] || '';
            const internalName = (groupName && groupName !== roomName)
              ? `${groupName}_${roomName}`
              : roomName;
            if (!internalName) continue;

            const slots = row.slice(-numSlots);
            slots.forEach((txt, i) => {
              if (!txt || txt === '-') return;
              const info = colMap[i];
              const lines = txt.split('\\n').map(s => s.trim()).filter(Boolean);
              const courseText = lines[lines.length - 1] || '';
              result.push({
                city: cityName, stype,
                internal_name: internalName,
                day: info.day, slot: info.slot,
                course_text: courseText
              });
            });
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
            # 對應結果統計（每個 classroom_id 拿到幾筆，方便檢查有沒有遺漏）
            from collections import Counter
            counts = Counter(s["classroom_id"] for s in physical_normalized)
            print(f"    對應結果（前 10 名）: {counts.most_common(10)}")
            zero = [c["id"] for c in classrooms_idx
                    if c["id"] not in counts and c["id"] != "online"]
            if zero:
                print(f"    [INFO] 沒對應到任何時段的教室 id: {zero}")

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
