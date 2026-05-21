# 橘子蘋果即時開班查詢

一個讓家長**不用走完整個預約流程**就能查到開班時段的靜態頁面。

- **目的**：減少 LINE@/Messenger 重複詢問「Python 在哪上？什麼時間？」
- **架構**：單一 HTML 檔（CSS / JS / 教室主檔 / SVG logo 全部內嵌）+ Selenium 爬蟲
- **部署**：Cloudflare Pages / GitHub Pages（免費、不需要工程師）

---

## 檔案結構

```
oa-schedule/
├── index.html          # ★ 家長查詢頁（公開，自帶 CSS / JS / logo / 教室主檔）
├── closest.html        # ☆ 電銷查詢工具（內部用：離家最近教室 + 推銷話術）
├── closest_data.js     # closest.html 用的 lat/lon 資料（由 prepare_geo.py 產生）
├── assets/
├── scraper/
│   ├── scrape.py       # Playwright 爬蟲（從 corp 抓開班時段寫回 index.html）
│   ├── prepare_geo.py  # 一次性：geocode 教室地址 + 全台縣市區，產生 closest_data.js
│   ├── requirements.txt
│   ├── .env.example
│   └── .env            # 實際帳密（git 不追蹤）
├── .gitignore
└── README.md
```

## 兩個頁面的差別

| 頁面 | 對象 | 路徑 | 索引 |
|------|------|------|------|
| **index.html**（家長查詢頁） | 對外，給家長從 LINE 點連結 | `/` | 公開 |
| **closest.html**（電銷工具） | 內部，電銷接電話時用 | `/closest.html` | `noindex,nofollow` |

closest.html 不從首頁連結，URL 自己保存。

> **為什麼塞一個檔？** 預覽工具、LINE 內建瀏覽器、各種怪環境都能正常顯示，不會因為載不到外部 CSS/JS 而失敗。檔案才 40KB 上下，CDN 一個 round-trip 就到家。

---

## 一、本地預覽

直接用瀏覽器開檔即可：

```bash
open /Users/posh.lin/Documents/oa-schedule/index.html
```

或用 HTTP server（部署前測試 URL 參數時建議）：

```bash
cd /Users/posh.lin/Documents/oa-schedule
python3 -m http.server 8000
# 瀏覽器打開 http://localhost:8000
```

---

## 二、部署到 Cloudflare Pages

1. 註冊 Cloudflare 帳號：<https://dash.cloudflare.com/sign-up>
2. 把 `oa-schedule/` 整個資料夾上傳到一個 GitHub repo
3. Cloudflare 控制台 → **Workers & Pages** → **Create application** → **Pages** → **Connect to Git**
4. 選 repo，**Build command 留空**，**Output directory `/`**，點 **Save and Deploy**
5. 30 秒拿到 `xxx.pages.dev` 網址
6. （可選）綁子域名 `schedule.orangeapple.co`：Custom domains → 新增即可

---

## 三、跑爬蟲取得真實資料

### 第一次設定

```bash
cd /Users/posh.lin/Documents/oa-schedule/scraper
pip3 install -r requirements.txt
cp .env.example .env
# 用編輯器打開 .env，填入 corp 後台帳密
```

### 跑爬蟲

```bash
python3 scrape.py              # 正式跑：抓資料 → 寫回 ../index.html
python3 scrape.py --dry-run    # 只抓不寫，列出筆數預覽
python3 scrape.py --debug      # 顯示 Firefox 視窗（看流程除錯用）
```

**爬蟲做什麼**：抓取每個城市 × (週末/週間) 的所有時段格 → 解析教室名、課程類型、課程階段 → 把 `index.html` 內 `/* SCHEDULE_DATA_START */` 與 `/* SCHEDULE_DATA_END */` 之間的區塊整個換成新的。其餘部分（CSS、教室主檔、UI）不動。

### 確認資料更新

```bash
grep -A 5 "updated_at" /Users/posh.lin/Documents/oa-schedule/index.html | head -10
```

### 部署更新

```bash
cd /Users/posh.lin/Documents/oa-schedule
git add index.html
git commit -m "auto: update schedule"
git push
```

Cloudflare Pages 偵測到 commit 後自動重新部署（約 30 秒）。

---

## 四、自動化排程（Mac mini）

每天凌晨爬一次、自動推到 git。

### cron（最簡單）

```bash
crontab -e
```

加入這行（每天凌晨 3 點）：

```
0 3 * * * cd /Users/posh/Documents/oa-schedule/scraper && /usr/local/bin/python3 scrape.py && cd .. && git add index.html && git commit -m "auto: update schedule $(date +\%F)" && git push >> /tmp/schedule-scraper.log 2>&1
```

> **注意**：Mac mini 路徑是 `/Users/posh/`，MacBook Air 是 `/Users/posh.lin/`。

### launchd（macOS 原生，比 cron 更可靠）

建立 `~/Library/LaunchAgents/co.orangeapple.schedule-scraper.plist`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>co.orangeapple.schedule-scraper</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/zsh</string>
        <string>-c</string>
        <string>cd /Users/posh/Documents/oa-schedule/scraper &amp;&amp; /usr/local/bin/python3 scrape.py &amp;&amp; cd .. &amp;&amp; git add index.html &amp;&amp; git commit -m "auto: update schedule $(date +%F)" &amp;&amp; git push</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict><key>Hour</key><integer>3</integer><key>Minute</key><integer>0</integer></dict>
    <key>StandardOutPath</key><string>/tmp/schedule-scraper.log</string>
    <key>StandardErrorPath</key><string>/tmp/schedule-scraper.err</string>
</dict>
</plist>
```

```bash
launchctl load ~/Library/LaunchAgents/co.orangeapple.schedule-scraper.plist
```

---

## 五、把連結放到 LINE@ / Messenger

頁面支援 URL 參數，可以給家長**已篩好的連結**：

| 場景 | URL 範例 |
|------|----------|
| 古亭教室所有開班 | `https://schedule.orangeapple.co/?classroom=guting` |
| 想學 Python | `https://schedule.orangeapple.co/?course=python` |
| 古亭的 Minecraft 課 | `https://schedule.orangeapple.co/?classroom=guting&course=minecraft` |
| 線上 Roblox | `https://schedule.orangeapple.co/?classroom=online&course=roblox` |
| 板橋的 Scratch | `https://schedule.orangeapple.co/?classroom=banqiao&course=scratch` |

可用的 `classroom` 值：見 `index.html` 內 `OA_CLASSROOMS.classrooms` 各筆的 `id`（如 `guting`、`banqiao`、`hsinchu_info` 等）
可用的 `course` 值：`scratch` / `python` / `javascript` / `creative_blocks` / `minecraft` / `roblox`

### LINE@ 自動回覆設定建議

| 關鍵字 | 自動回覆 |
|--------|---------|
| 教室 / 上課地點 | 「全台教室開班時段一覽 👉 [連結]」 |
| Python / 程式 | 「Python（菁英課）開班時段 👉 [course=elite 連結]」 |
| 時段 / 時間 | 「點這裡看所有時段 👉 [連結]」 |
| Minecraft / 麥塊 | 「Minecraft 課程時段 👉 [course=minecraft 連結]」 |

---

## 六、要先改的兩個 TODO

打開 `index.html`，搜尋以下兩處改成正式 LINE OA 連結：

1. `const BOOKING_URL = "https://lin.ee/your-line-oa-link";` （JS 區塊內，預約試聽按鈕用）
2. `<a class="bottom-cta__btn" href="https://lin.ee/your-line-oa-link"` （底部「LINE 聯絡專員」按鈕）

---

## 七、編輯教室或課程

直接打開 `index.html`，找到 `window.OA_CLASSROOMS = {...}` 區塊：

- **新增教室**：在 `classrooms` 陣列加一筆物件，照其他教室的格式（id / name / city / district / address / phone）
- **修改地址或電話**：找到對應教室那一行改即可
- **新增課程類別**：在 `courses` 陣列加一筆（id / name / description）。注意 id 要跟爬蟲的 `COURSE_MAP`（scrape.py 第 60 行附近）對得上
- **時段對照**：`time_slots` 區塊

> 時段 4（18:30–20:30）主要實體晚間用、時段 5（19:00–21:00）給線上晚間。改了之後前端會自動套用。

---

## 電銷查詢工具（closest.html）

### 用途
家長打電話來問「離我家最近的教室」時，電銷在 1 秒內可以查到最近 5 間教室、距離 / 估算車程，超過 30 分鐘自動跳推銷話術導向線上課程。

### 距離與時間怎麼算
- **距離**：Haversine 公式算直線距離（公里）
- **車程估算**：直線距離 × 2.5 ≈ 分鐘（內建「彎路修正 ×1.4 + 平均車速 24 km/h」）
- **準確度**：±30%，足以分辨「5 分 vs 50 分」。若要精準，每張結果卡都有「📍 開 Google Maps」按鈕

### 更新地理資料
所有教室與全台 ~370 個區的座標都預先 geocode 好放在 `closest_data.js`。**只有以下情況需要重跑**：

- 新增教室
- 教室地址變動
- 想擴充覆蓋的行政區

```bash
cd scraper
python3 prepare_geo.py            # 重新 geocode 所有資料
```
（執行需要 8-10 分鐘，因為 OpenStreetMap Nominatim API 限速 1 req/sec）

### 修改 30 分鐘閾值 / 推銷話術
打開 `closest.html` 改：
- 第 ~ 行 `const FAR_THRESHOLD_MIN = 30;` — 改成想要的分鐘數
- `function renderPitch` 內的 `script` 變數 — 改成想要的話術內容

---

## 故障排除

**Q：本地預覽看到空白頁或沒樣式？**
A：因為 index.html 已經自帶所有東西（CSS / JS / 資料），單檔直開就會正常。如果還是空白，按 F12 看 Console 錯誤訊息。

**Q：爬蟲跑不起來？**
A：先用 `--debug` 模式看 Firefox 視窗，確認登入流程是否正常。`pip3 install -r requirements.txt` 是否裝過。Firefox 是否安裝（公司技術棧用 Firefox，Chromium 在這台 Mac 會崩潰）。

**Q：DOM 結構解析失敗？**
A：corp 系統的 `<table>` 結構可能跟預想不同。用 `--debug` 開視窗，按 F12 看實際 HTML，調整 `scrape.py` 裡 `parse_schedule_table()` 的 selector。

**Q：時段 4/5 在頁面上看起來重疊（18:30 vs 19:00）？**
A：那是正確的——4 是實體晚間班、5 是線上晚間班。前端用「線上」標籤區分。
