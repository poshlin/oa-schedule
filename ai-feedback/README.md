# AI 改進建議系統 — 部署指南

## 兩種路線可選

### 🟢 L2.5（推薦）— BYO AI：用使用者自己的免費 AI

使用者點按鈕 → 複製 prompt → 貼到 ChatGPT / Gemini / Claude.ai → 對話 → 把結果貼回 → Posh 在 review.html 審核 → 一鍵 commit。

- 月費：**$0**
- 部署：**~25 分鐘**
- 要配置：Apps Script + GitHub PAT
- AI 品質：看使用者用哪個（基本上都夠用）

### 🟡 L3（進階）— 內嵌 AI Chat：訓練頁直接內嵌對話

使用者點按鈕 → 訓練頁內彈出側欄跟 Claude API 對話 → 完成後自動送 Posh。

- 月費：~$2.5（Anthropic API）
- 部署：~90 分鐘
- 要配置：Anthropic API key + Cloudflare Worker + Apps Script + GitHub PAT
- AI 品質：穩定（統一用 Claude Sonnet 4.5）
- 適合：規模 20+ 人 / 想要無痛 UX

**這份指南先講 L2.5。L3 升級在文末附錄。**

---

## L2.5 架構

```
使用者（mentor / 課程顧問 / 主管）
   ↓ 點訓練頁的「💡 建議改進」或「⚠️ 過期錯誤」
[training.html BYO 對話視窗]
   ↓ 複製 prompt
[使用者自己的 ChatGPT / Gemini / Claude.ai]
   ↓ 自然對話釐清 → AI 給 JSON
   ↓ 使用者複製 JSON 貼回
[training.html 預覽 + 編輯 + 送出]
   ↓ POST /submit
[Google Apps Script]
   ↓ 寫 Master Sheet「待審區」Tab
[review.html ← Posh 看]
   ↓ ✅ 採納 / ❌ 拒絕 / ✏️ 修改後採納
[Apps Script + GitHub PAT]
   ↓ 自動 commit + push
GitHub Pages 自動部署
```

---

## ① 建 Master Sheet（如果還沒）

依 `training-setup.md` 第二節建好你的 Master Sheet。「待審區」Tab 不用先建，Apps Script 第一次跑會自動建。

## ② 建 GitHub Personal Access Token

1. <https://github.com/settings/personal-access-tokens/new>（Fine-grained）
2. Token name: `oa-schedule-auto-commit`
3. Expiration: **90 天**（之後到期會通知重新生成）
4. Repository access: **Only select repositories** → 選 `poshlin/oa-schedule`
5. Permissions: **Repository permissions → Contents → Read and write**
6. Generate token → 複製 `github_pat_...`（**只會出現一次，記得存起來**）

## ③ 安裝 Apps Script

1. 開啟你的 Master Sheet
2. 上方選單：**擴充功能 → Apps Script**
3. 把預設的 `myFunction` 清空，貼入 `ai-feedback/code.gs` 全部內容
4. 左側齒輪 ⚙️「專案設定」→「指令碼屬性」→ 新增 3 個：

| Property | Value |
|----------|-------|
| `GITHUB_REPO` | `poshlin/oa-schedule` |
| `GITHUB_TOKEN` | 第 ② 步生成的 PAT |
| `REVIEW_SECRET` | 你自訂的密碼字串（例 `oa-review-2026-xyz`）|

5. **部署 → 新增部署**
   - 類型：**網路應用程式**
   - 執行身分：**我（你的 email）**
   - 存取權限：**任何人**（這對 webhook 必要；安全性靠 REVIEW_SECRET）
6. **複製 Web App URL**（會像 `https://script.google.com/macros/s/AKfyc.../exec`）

## ④ 把 URL 填回 HTML

### 4a. training.html

打開 `training.html`，找到第 ~360 行：

```js
const APPS_SCRIPT_URL = "https://script.google.com/macros/s/REPLACE_WITH_YOUR_DEPLOYMENT_ID/exec";
const MENTOR_SHEET_URL = "https://docs.google.com/spreadsheets/d/REPLACE_WITH_YOUR_SHEET_ID/edit";
```

兩個 URL 都填進去，存檔。

### 4b. review.html

打開 `review.html`，找到第 ~85 行：

```js
const APPS_SCRIPT_URL = "https://script.google.com/macros/s/REPLACE_WITH_YOUR_DEPLOYMENT_ID/exec";
```

填同樣的 Apps Script URL，存檔。

### 4c. commit + push

```bash
cd /Users/posh.lin/Documents/oa-schedule
git add training.html review.html
git commit -m "config: 填入 Apps Script URL + Master Sheet URL"
git push
```

GitHub Pages 約 1 分鐘自動部署。

## ⑤ 第一次測試

1. **Apps Script 端**：瀏覽器打開
   `https://script.google.com/macros/s/.../exec?action=list&status=pending&secret=你的REVIEW_SECRET`
   應看到 `{"ok":true,"items":[]}`

2. **使用者端**：打開 `training.html`，點任一章節的「💡 建議改進」
   - 應該彈出 BYO modal
   - Step 1 複製 prompt
   - Step 2 開 AI（你常用的）、貼上 prompt、對話
   - 對話結尾叫 AI 「OK 整理出來吧」AI 會給 JSON code block
   - 複製整段、貼回 Step 3
   - 點「🔍 解析 + 預覽」應該成功
   - 點「✅ 送 Posh 審核」應該看到「已送出 + 編號」

3. **Posh 端**：打開 `review.html?key=你的REVIEW_SECRET`
   - 應看到剛送出的那條
   - 點「✅ 採納並 commit」確認
   - 約 1-2 分鐘後 GitHub Pages 自動部署、頁面內容更新

---

## 安全模型

| 端點 | 誰能用 | 防護 |
|------|-------|------|
| Apps Script `submit` | 任何人（從訓練頁可送） | 內容靠 review 把關；垃圾訊息可批次刪 |
| Apps Script `list` `apply` `reject` | **僅 Posh** | `REVIEW_SECRET` 驗證 |
| GitHub PAT | Apps Script 內部 | 90 天到期、最小權限 |

**REVIEW_SECRET 不要分享給任何人**——拿到的人可以 commit 代碼。

---

## 故障排除

| 現象 | 可能原因 | 處理 |
|------|---------|------|
| BYO modal 跳出「Apps Script 未配置」 | URL 還是 placeholder | 改 `training.html` 第 ~360 行 |
| 「🔍 解析 + 預覽」失敗 | AI 沒給 JSON code block | 回 AI 說「請以 ```json``` 重新輸出」；或在 fallback 表單手動填 |
| 「✅ 送 Posh 審核」失敗 | Apps Script URL 錯 / 未部署 / 權限非「任何人」| 重看第 ③ 步 |
| review.html 顯示「unauthorized」| REVIEW_SECRET 不對 | 清 localStorage 重輸 |
| review 點採納 → 失敗「findText not found」 | AI 給的 `current_text` 跟 HTML 對不上（可能 AI 編造 / 文字略有差） | 用「✏️ 修改後採納」手動微調 |
| review 點採納 → 失敗「GITHUB_TOKEN」 | PAT 過期或權限不對 | 重新生 PAT、更新 Apps Script property |
| 對話完 AI 不肯給 JSON | Prompt 沒被完整貼到 AI | 重新複製整段 prompt 貼進去 |

---

## 附錄：L3 升級路線（如果你想要無痛 UX）

如果使用者覺得「BYO 流程太麻煩」、或同事不願意每次切視窗，可以升級成 L3 — 訓練頁內嵌 AI chat widget，使用者一個視窗內完成所有事。

L3 額外要做的：

1. **註冊 Anthropic API**：<https://console.anthropic.com>，最低 $5 開卡，每月約 $2.5
2. **部署 Cloudflare Worker**：用 `ai-feedback/worker.js` + `wrangler.toml`
   ```bash
   cd ai-feedback
   npm install -g wrangler
   wrangler login
   wrangler secret put ANTHROPIC_API_KEY   # 貼 Anthropic key
   wrangler secret put APPS_SCRIPT_URL     # 貼 ③ 步的 URL
   wrangler deploy
   ```
3. **替換 training.html chat widget**：把 BYO modal 換成 chat widget。具體 code 在 git history（之前版本 v1.0），可以還原。

L3 部分的 code 還在 repo 內（`worker.js`、`wrangler.toml`），隨時可以接上。

---

## 我每月要做什麼

| 頻率 | 動作 | 時間 |
|------|------|------|
| 每週 | 開 `review.html`、處理待審 | 10-15 分鐘 |
| 每月 | 看 Master Sheet「訓練內容維護表」Tab，掃健康度燈號 | 30 分鐘 |
| 每季 | 檢視 `RULES`、`CHAPTERS` 的章節結構是否仍合理 | 1 小時 |
| 每年 | 整體版本回顧、看看哪些章節常被建議改、是不是教材本身要重寫 | 半天 |
| 90 天前 | 重新生 GitHub PAT | 5 分鐘 |

整體 ROI：**每月 ~1 小時投入，換來新人訓練系統自己會進化**。
