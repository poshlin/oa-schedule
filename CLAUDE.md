# oa-schedule — Posh 的橘子蘋果線上事業部工具集

> 這個檔會被 Claude Code 自動載入。給未來 Claude 看的「進場簡報」。

## 跨裝置

- **MacBook Air**（辦公室，週一～四）：`/Users/posh.lin/Documents/oa-schedule/`
- **Mac mini**（居家，週五～日）：路徑前綴是 `/Users/posh/Documents/oa-schedule/`（同一份、iCloud 同步）
- 兩台都可改、commit、推 GitHub

## 線上部署

GitHub Pages：<https://poshlin.github.io/oa-schedule>

## 🎛 唯一入口（Posh 的祕密書籤）

**<https://poshlin.github.io/oa-schedule/console.html>**

`console.html` 是 Posh 自己的控制台、**meta robots noindex,nofollow**、沒有公開頁面連結進去。裡面有：
- 所有 Sheet / Drive / Form 連結 + 用途說明
- 4 個職務的 AI 照片 prompt（按鈕一鍵複製到剪貼簿）
- 新人入職 SOP 條列
- 對外 / 內部工具索引

**未來改任何東西、先想會不會影響 console.html 的入口性**。不要把 console.html 連到 team.html / training.html 等公開頁。

---

## 頁面地圖

| 檔案 | 對誰 | 做什麼 |
|---|---|---|
| `index.html` | 家長 | 即時開班查詢（Scratch / Python / JavaScript）、單檔內嵌教室主檔 |
| `closest.html` | 電銷 | 輸入家長地址、找最近實體教室 + 線上推薦話術 |
| `rules.html` | 內部 | 42 條業務規則索引、按角色 filter |
| `sms.html` | 電銷 | SMS 字數計算、含 maac.io 短網址換算 + 自動加【橘子蘋果】prefix |
| `training.html` | 新人 | 17 章節新人訓練、checklist + 健康度監測 |
| `team.html` | 新人 | 團隊介紹卡片牆、4 個職務分組、Sheet 即時同步 |
| `review.html` | Posh | AI feedback 審核台、訓練內容改進建議的審核介面 |
| `console.html` | **Posh only** | 所有工具入口、AI prompt 一鍵複製、SOP |

## ai-feedback/ 子目錄

L2.5 BYO AI 架構（**不是** L3 全自動）：
- 同仁在 training.html 點「💡 建議改進」→ 跳 modal → 一鍵複製 prompt
- 同仁去自己慣用的免費 AI（ChatGPT / Gemini / Claude）貼 prompt
- AI 吐 JSON、同仁貼回 modal → 自動送進 Sheet「待審區」
- Posh 在 review.html 審核 → 採納會用 GitHub API 自動 commit

關鍵檔：
- `ai-feedback/code.gs`（Apps Script，部署 ID 在 `training.html` 的 `APPS_SCRIPT_URL` 常數）
- `ai-feedback/README.md`（部署 + L3 升級路徑）
- `ai-feedback/worker.js`（Cloudflare Worker、L3 才會用、目前不用）

**重要**：`_apply` 函式有 3 層驗證（current_text ≥15 字 / 必須存在於 training.html / 必須唯一），避免空字串把 markdown 插到檔頭那種事故。

---

## 真相來源：Google Sheets

| Sheet | ID | 分頁 | 給誰讀 |
|---|---|---|---|
| 新人訓練 Master | `1m9w6mdScB34jyifewnxgpy0LItBeRN2WGkBHpg2u93E` | 訓練內容維護表 / 待審區 / 變動觸發 | training.html（讀 last_review_date）、review.html、ai-feedback code.gs |
| 團隊主檔 | `1w2T1rI0-Lb2QjfjjMLby2133NyihFqFh57zpskpUjyk` | 團隊主檔 | team.html |
| 大頭照 Form 回應 | `1G4xjth-SIdycIDzdaCGD6slBkhAVlt27_bnWrG_AvuQ` | 表單回應 1 | Posh 手動處理（沒程式讀） |

**Drive**：OA 團隊照片資料夾 `1ygzOuZhqL5FESScXmIFgJwybfrExEKfS`
**Form**：大頭照上傳 Form `1QblDwqCYOFmYoMxJUZxU_vhO2ysRrw6xe-A_fAi49Vg`

**所有 URL 都在 console.html 內**、不要在這個 CLAUDE.md 也維護一份、會 drift。

---

## 架構原則（重要）

### 1. Sheet 是真相、HTML 是視窗
任何「會變的內容」（人員、章節簽核日、規則）放 Sheet。HTML 透過發布的 CSV 端點動態讀。Posh 改 Sheet → 60 秒後 HTML 自動更新、不用 commit。

### 2. 單一檔架構
每個頁面是 self-contained HTML（CSS + JS + SVG logo 都 inline）。原因：LINE 內建瀏覽器、預覽工具會擋外部資源。

### 3. localStorage per user
training.html 有「切換使用者」功能、不同新人 checklist 進度分開存。

### 4. 向下相容欄位查找
讀 Sheet 時、欄位名同時接受新舊名稱、避免改 Sheet 標題就壞掉。例如 `team.html` 接受 `部門|職務|department`、`training.html` 接受 `章節|chapter|chapter_title`。

---

## 視覺品牌

```
--orange: #FFA300; --orange-dk: #D48500;
--red:    #FF5859; --red-dk:    #CC3344;
--teal:   #00C4B3; --teal-dk:   #008F83;
```

字體：`"微軟正黑體", "Microsoft JhengHei", "PingFang TC"`（中）+ `"Trebuchet MS"`（英數）

### 4 個職務色（team.html 用）

| 職務 | 主色 | icon |
|---|---|---|
| 總監 | `#E89400` | 👑 |
| 課程顧問 | `#5588B5` | 📚 |
| 課務 | `#5FAA7A` | 📅 |
| 電銷 | `#FF7A2E` | 💬 |

---

## Posh 怎麼工作（給 Claude 看的協作守則）

- **語言**：一律繁體中文、不夾簡體日文
- **風格**：戰略顧問語氣、結論先講、不要鋪陳
- **技術說明**：他是行銷出身、Python 腳本能改、但 JS/HTML 不熟。解釋要用比喻、別 dump 技術細節
- **AI 圖像生成**：Posh 自己跑 Gemini / ChatGPT、Claude 不要嘗試代跑（沒能力）。Claude 的工作是建系統 + 寫 prompt 包
- **大量資料**：給 TSV 讓他一次 Cmd+V 進 Sheet、別叫他一格一格填、也別用 MCP browser 慢慢點
- **改完後**：他會 Cmd+Shift+R 後反映「看不到」、十之八九是快取、不是 bug
- **驗證**：他不確定自己的判斷時、會貼整段 code 來問。要實際讀過 code 再回、不要憑印象答

---

## Posh 的雙裝置 + 知識庫

- 知識庫在 `~/Documents/Claude知識庫/`（iCloud 同步）：
  - `OA_課程體系.md`
  - `OA_月結薪資流程.md`
- 任務與 OA 業務相關時、主動讀這 2 個檔案
- 不要相信記憶庫中比知識庫舊的版本

---

## 部署流程（如果忘記）

1. 改檔 → `git add` → `git commit` → `git push`
2. GitHub Actions 自動 build Pages、約 1 分鐘
3. 驗證：`gh api repos/poshlin/oa-schedule/pages/builds/latest`、`status: built`
4. 提醒 Posh 用 Cmd+Shift+R 重整、繞過快取

## JS 驗證一條龍

```bash
node -e "
const fs=require('fs'),html=fs.readFileSync('FILENAME.html','utf-8');
const m=html.match(/<script>([\\s\\S]*?)<\\/script>/g);
let js=m.map(s=>s.replace(/<\\/?script>/g,'')).join('\\n');
try{new Function(js);console.log('[OK]');}catch(e){console.log('[ERR]',e.message);}
"
```

每次改 HTML 內的 JS、先跑這個。
