#!/usr/bin/env python3
"""
橘子蘋果雙師班排程爬蟲
====================
登入 corp.orangeapple.co/courses/dt，抓取所有城市 × 週末/週間 的時段資料，
解析後寫回 ../index.html 中 SCHEDULE_DATA_START / SCHEDULE_DATA_END 之間的區塊。

用法：
    python3 scrape.py              # 正式跑，會更新 ../index.html
    python3 scrape.py --dry-run    # 抓資料但不寫檔，印出筆數
    python3 scrape.py --debug      # 顯示 Firefox 視窗（預設無頭）

帳密設定：
    在同資料夾建立 .env 檔案（不要 commit）：
        OA_USERNAME=your_email
        OA_PASSWORD=your_password

時段對照（與 index.html 內 time_slots 同步）：
    1 = 10:00–12:00, 2 = 13:30–15:30, 3 = 16:00–18:00,
    4 = 18:30–20:30 (實體晚間), 5 = 19:00–21:00 (線上晚間)
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
INDEX_HTML = PROJECT_DIR / "index.html"
load_dotenv(SCRIPT_DIR / ".env")

LOGIN_URL = "https://corp.orangeapple.co/users/sign_in"
TARGET_URL = "https://corp.orangeapple.co/courses/dt"

USERNAME = os.getenv("OA_USERNAME")
PASSWORD = os.getenv("OA_PASSWORD")

CITIES = ["臺北市", "新北市", "基隆市", "桃園市", "新竹市", "新竹縣",
          "苗栗縣", "臺中市", "嘉義市", "臺南市", "高雄市", "屏東縣",
          "Kuala Lumpur"]
SCHEDULE_TYPES = ["週末", "週間"]

# ---------- 對應表（教室內部名 → classrooms id） ----------
# 從 index.html 內的 OA_CLASSROOMS 取出 id/name，自動建表（簡單字串比對）
def extract_classrooms_from_index():
    html = INDEX_HTML.read_text(encoding="utf-8")
    # 找出 window.OA_CLASSROOMS = {...} 的內容，用粗略 regex
    rows = re.findall(r'\{\s*id:\s*"([^"]+)",\s*name:\s*"([^"]+)"', html)
    return [{"id": rid, "name": name} for rid, name in rows]

def normalize_classroom_id(internal_name, classrooms_idx):
    if "線上" in internal_name or "遠距" in internal_name or "橘頭" in internal_name:
        return "online"
    head = re.split(r'[｜_]', internal_name, maxsplit=1)[0].strip()
    for c in classrooms_idx:
        if c["name"].startswith(head) or head in c["name"]:
            return c["id"]
        if c["name"].replace("教室", "") == head:
            return c["id"]
    return None

# ---------- 課程類型對應 ----------
# corp 內部課程名稱 → index.html 內 COURSE_INTERNAL_TO_DISPLAY 認得的 id
# 注意：「菁英」對應的 elite 在前端會展開成 Scratch/Python/JavaScript 三種顯示
COURSE_MAP = {
    "菁英":     "elite",
    "Roblox":   "roblox",
    "麥塊":     "minecraft",
    "Minecraft":"minecraft",
    "創意積木": "creative_blocks",
    "Scratch":  "creative_blocks",  # 若 corp 有獨立列 Scratch 也歸類於此
    "數學":     "math",
    "選手班":   "competition",
}
def normalize_course(text):
    if not text:
        return None, ""
    level_match = re.search(r'[(\(]([^)\)]+)[)\)]', text)
    level = level_match.group(1).strip() if level_match else ""
    base = re.sub(r'[(\(].*?[)\)]', '', text).strip()
    for key, cid in COURSE_MAP.items():
        if key in base:
            return cid, level
    return base.lower(), level

# ---------- 瀏覽器 ----------
def make_driver(debug=False):
    opts = Options()
    if not debug:
        opts.add_argument("--headless")
    opts.add_argument("--width=1920")
    opts.add_argument("--height=1080")
    return webdriver.Firefox(options=opts)

def login(driver):
    if not USERNAME or not PASSWORD:
        sys.exit("錯誤：.env 缺少 OA_USERNAME / OA_PASSWORD")
    driver.get(LOGIN_URL)
    wait = WebDriverWait(driver, 15)
    wait.until(EC.presence_of_element_located((By.NAME, "user[email]")))
    driver.find_element(By.NAME, "user[email]").send_keys(USERNAME)
    driver.find_element(By.NAME, "user[password]").send_keys(PASSWORD)
    driver.find_element(By.NAME, "commit").click()
    wait.until(lambda d: "sign_in" not in d.current_url)
    print(f"[OK] 登入成功 → {driver.current_url}")

# ---------- 解析 ----------
def click_tab(driver, label):
    elements = driver.find_elements(
        By.XPATH,
        f"//a[normalize-space()='{label}'] | //button[normalize-space()='{label}']"
    )
    if not elements:
        print(f"[WARN] 找不到 tab：{label}")
        return False
    elements[0].click()
    time.sleep(1.2)
    return True

def parse_schedule_table(driver, city, schedule_type):
    """解析當前頁面顯示的時段表。
    預期結構：tbody > tr，每列開頭是教室名格，後面 10 個 cell 為 Sat 1-5 / Sun 1-5。
    第一次跑請用 --debug 開視窗確認 DOM 結構。
    """
    rows = []
    table_rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    for tr in table_rows:
        tds = tr.find_elements(By.TAG_NAME, "td")
        if len(tds) < 11:
            continue
        internal_name = ""
        slot_cells = []
        for td in tds:
            text = td.text.strip()
            if "教室" in text and not slot_cells and not internal_name:
                internal_name = text
            else:
                slot_cells.append(td)
        if not internal_name:
            continue
        slot_cells = slot_cells[-10:]
        for idx, cell in enumerate(slot_cells):
            content = cell.text.strip()
            if not content or content == "-":
                continue
            day = "Sat" if idx < 5 else "Sun"
            slot = (idx % 5) + 1
            lines = [l.strip() for l in content.split("\n") if l.strip()]
            course_text = lines[-1] if lines else ""
            course_id, level = normalize_course(course_text)
            rows.append({
                "city": city,
                "schedule_type": "weekend" if schedule_type == "週末" else "weekday",
                "internal_name": internal_name,
                "day": day,
                "time_slot": slot,
                "course_id": course_id,
                "course_level": level,
            })
    return rows

# ---------- 寫回 index.html ----------
def to_js_block(schedules):
    """把 schedules 列表轉成 index.html 內嵌格式的 JS 字串"""
    lines = []
    for s in schedules:
        line = (
            f'    {{ classroom_id: {json.dumps(s["classroom_id"], ensure_ascii=False)}, '
            f'course_id: {json.dumps(s.get("course_id") or "", ensure_ascii=False)}, '
            f'course_level: {json.dumps(s.get("course_level", ""), ensure_ascii=False)}, '
            f'day: {json.dumps(s["day"])}, '
            f'time_slot: {s["time_slot"]} }},'
        )
        lines.append(line)
    body = "\n".join(lines).rstrip(",")
    return (
        "\n/* SCHEDULE_DATA_START */\n"
        "window.OA_SCHEDULE = {\n"
        f'  updated_at: "{datetime.now().strftime("%Y-%m-%d %H:%M")}",\n'
        '  source: "corp.orangeapple.co/courses/dt",\n'
        "  schedules: [\n"
        f"{body}\n"
        "  ]\n"
        "};\n"
        "/* SCHEDULE_DATA_END */\n"
    )

def write_back_to_html(schedules):
    html = INDEX_HTML.read_text(encoding="utf-8")
    pattern = re.compile(
        r"/\* SCHEDULE_DATA_START \*/.*?/\* SCHEDULE_DATA_END \*/",
        re.DOTALL
    )
    if not pattern.search(html):
        sys.exit("錯誤：index.html 找不到 SCHEDULE_DATA_START/END 標記")
    new_block = to_js_block(schedules).strip()
    new_html = pattern.sub(new_block, html)
    INDEX_HTML.write_text(new_html, encoding="utf-8")
    print(f"[寫入] {INDEX_HTML}")

# ---------- 主流程 ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只抓不寫檔")
    ap.add_argument("--debug", action="store_true", help="顯示 Firefox 視窗")
    args = ap.parse_args()

    classrooms_idx = extract_classrooms_from_index()
    if not classrooms_idx:
        sys.exit("錯誤：無法從 index.html 解析教室清單，請確認檔案沒被破壞")
    print(f"[INFO] 從 index.html 取得 {len(classrooms_idx)} 個教室對應")

    driver = make_driver(debug=args.debug)
    all_schedules = []
    try:
        login(driver)
        driver.get(TARGET_URL)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )

        for city in CITIES:
            if not click_tab(driver, city):
                continue
            print(f"\n=== {city} ===")
            for sched_type in SCHEDULE_TYPES:
                if not click_tab(driver, sched_type):
                    continue
                rows = parse_schedule_table(driver, city, sched_type)
                for r in rows:
                    cid = normalize_classroom_id(r["internal_name"], classrooms_idx)
                    if not cid:
                        print(f"  [WARN] 找不到教室對應：{r['internal_name']}")
                        continue
                    all_schedules.append({
                        "classroom_id": cid,
                        "course_id": r["course_id"],
                        "course_level": r["course_level"],
                        "day": r["day"],
                        "time_slot": r["time_slot"],
                    })
                print(f"  {sched_type}: 抓到 {len(rows)} 筆")

        print(f"\n[完成] 總共 {len(all_schedules)} 筆時段")

        if args.dry_run:
            print("[DRY RUN] 不寫檔。前 3 筆預覽：")
            for s in all_schedules[:3]:
                print(f"  {s}")
            return

        write_back_to_html(all_schedules)
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
