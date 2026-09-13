#!/usr/bin/env python3
"""
把排程資料彙整成「每間教室目前開哪些課族」，輸出給官網縣市頁使用。

    /usr/bin/python3 export_offerings.py [--dry-run]

來源：../index.html 的 OA_CLASSROOMS + OA_SCHEDULE（由 scrape.py 更新）
輸出：~/Documents/oa-page-classroom/content/shared/course_offerings.json

鍵值用官網 locations-data 的 LocalBusiness @id 片段（如 taipei-guting），
因為那是官網端的穩定識別碼；本檔用地址比對建立對應，對不上就中止，
避免默默漏掉或錯配教室。

課族名稱一律以知識庫 OA_課程體系.md 為準：
  elite → 菁英系列（9 階段一條龍，不可寫成「Scratch／Python／JavaScript 三選一」）
"""
import argparse, json, re, subprocess, sys
from pathlib import Path
from datetime import datetime

HERE = Path(__file__).resolve().parent
SCHEDULE_HTML = HERE.parent / "index.html"
OUT = Path.home() / "Documents" / "oa-page-classroom" / "content" / "shared" / "course_offerings.json"
SSOT_HTML = Path.home() / "Documents" / "oa-page-classroom" / "index.html"

# 對外顯示名稱，一律以知識庫 OA_課程體系.md 為準。
# 🔴 elite ＝「菁英系列」9 階段主線，不是三種語言三選一。
# 🔴 roblox 必須寫「Roblox AI 遊戲設計」：「舊版 Roblox 遊戲設計課」是已停辦課程的名字
#    （OA_課程體系.md:463 的「已停辦／暫不開班」清單），且 :95 明文「三者不可混寫」
#    （常態 Roblox AI／Roblox 營隊／規劃中的 Lua 三階段）。
FAMILY = {
    "elite": "菁英系列（程式主線）",
    "minecraft": "麥塊程式班",
    "roblox": "Roblox AI 遊戲設計",
    "creative_blocks": "STEAM 創意機械積木",
    "math": "麥思數學",
    "aibot": "頑皮艾伯特",
}
ORDER = ["elite", "minecraft", "roblox", "creative_blocks", "math", "aibot"]

# 🔴 只在線上開課的課程，一律不寫進實體教室卡（依知識庫 OA_課程體系.md）：
#   - 頑皮艾伯特：「現售＝線上版；實體版已停售」（:40）。排程裡 19 筆 aibot 有 18 筆掛
#     online，唯一的實體筆是台南東寧西——那是安親班專案的特例，記憶
#     project_oa_course_age_matrix 明寫「勿寫進常態課文案」。寫上去家長會以為能報名。
#   - 麥思數學：availability = online。
ONLINE_ONLY = {"aibot", "math"}


def js_object(html, var):
    i = html.index(f"window.{var}")
    k = html.index("=", i) + 1
    while html[k] in " \n\t":
        k += 1
    opener = html[k]
    closer = "]" if opener == "[" else "}"
    depth, start = 0, k
    while True:
        if html[k] == opener:
            depth += 1
        elif html[k] == closer:
            depth -= 1
            if depth == 0:
                break
        k += 1
    out = subprocess.run(
        ["node", "-e", f"console.log(JSON.stringify({html[start:k+1]}))"],
        capture_output=True, text=True,
    )
    if out.returncode:
        sys.exit(f"解析 {var} 失敗：{out.stderr[:300]}")
    return json.loads(out.stdout)


def addr_key(region, locality, street):
    """縣市＋行政區＋街道當比對鍵；吸收「臺/台」「5樓/5F」「括號註記」等寫法差異。"""
    s = f"{region}{locality}{street}"
    s = s.replace("臺", "台")
    s = re.sub(r"[（(].*?[)）]", "", s)
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"樓之", "之", s)
    s = re.sub(r"(\d+)F", r"\1樓", s, flags=re.I)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    sched_html = SCHEDULE_HTML.read_text(encoding="utf-8")
    C = js_object(sched_html, "OA_CLASSROOMS")
    S = js_object(sched_html, "OA_SCHEDULE")

    ssot_html = SSOT_HTML.read_text(encoding="utf-8")
    graph = json.loads(
        re.search(r'<script id="locations-data" type="application/ld\+json">([\s\S]*?)</script>', ssot_html).group(1)
    )["@graph"]

    ssot = {}
    for n in graph:
        if n.get("@type") != "LocalBusiness":
            continue
        a = n["address"]
        street = a["streetAddress"]
        if street.startswith(a["addressLocality"]):
            street = street[len(a["addressLocality"]):]
        ssot[addr_key(a["addressRegion"], a["addressLocality"], street)] = {
            "frag": n["@id"].split("#")[-1],
            "short": n["_short"],
            "camp_only": bool(n.get("_isCampOnly")),
        }

    # 排程教室 id → 官網 @id 片段
    id_to_frag, unmatched = {}, []
    for r in C["classrooms"]:
        if r.get("is_online"):
            continue
        # 只處理台灣據點：縣市頁只涵蓋台灣，海外分校（吉隆坡）地址格式也不同、無從比對。
        if not re.search(r"[市縣]$", r["city"]):
            continue
        street = r["address"]
        if street.startswith(r.get("district", "")):
            street = street[len(r["district"]):]
        hit = ssot.get(addr_key(r["city"], r.get("district", ""), street))
        if hit:
            id_to_frag[r["id"]] = hit
        else:
            unmatched.append(f'{r["name"]}（{r["city"]}{r.get("district","")}{r["address"]}）')
    if unmatched:
        sys.exit("以下排程教室在官網 locations-data 找不到對應，請先確認是否已下架：\n  - " + "\n  - ".join(unmatched))

    offerings = {}
    for s in S["schedules"]:
        hit = id_to_frag.get(s["classroom_id"])
        if not hit or s["course_id"] not in FAMILY:
            continue
        if s["course_id"] in ONLINE_ONLY:
            continue
        offerings.setdefault(hit["frag"], set()).add(s["course_id"])

    data = {
        "_comment": "由 oa-schedule/scraper/export_offerings.py 產生，勿手改。更新方式：先跑 scrape.py 再跑本檔。",
        "generated_at": datetime.now().strftime("%Y-%m-%d"),
        "source": S.get("source", ""),
        "schedule_updated_at": S.get("updated_at", ""),
        "family_labels": FAMILY,
        "offerings": {
            frag: [c for c in ORDER if c in cs]
            for frag, cs in sorted(offerings.items())
        },
    }

    print(f"對應教室 {len(id_to_frag)} 間；有開班 {len(data['offerings'])} 間")
    for frag, cs in data["offerings"].items():
        print(f"  {frag:<26} {'、'.join(FAMILY[c] for c in cs)}")
    silent = sorted(h["short"] for h in id_to_frag.values() if h["frag"] not in data["offerings"])
    if silent:
        print(f"\n目前無常態班的教室（不會出現在頁面上）：{'、'.join(silent)}")

    if args.dry_run:
        print("\n[DRY RUN] 未寫檔")
        return
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n[寫入] {OUT}")


if __name__ == "__main__":
    main()
