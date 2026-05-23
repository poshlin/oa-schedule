# L3 AI 改進助理 — 部署指南

整套架構：
```
新人 / mentor / 主管
        ↓
training.html 內的 💡 建議改進 / ⚠️ 過期錯誤 按鈕
        ↓
[Cloudflare Worker] ← Anthropic API
        ↓ AI 對話釐清、整理為 JSON
[Google Apps Script] → Master Sheet「待審區」Tab
        ↓
[review.html] ← Posh 點 ✅ 採納
        ↓
[Apps Script GitHub API] → 自動 commit + push
        ↓
GitHub Pages 自動部署、生效
```

整套部署約需 **60-90 分鐘**。以下按順序執行。

---

## ⓪ 你需要準備的帳號

1. **Anthropic API**：<https://console.anthropic.com>（信用卡開卡、最低 $5 額度）
2. **Cloudflare 帳號**（已有）
3. **GitHub 帳號**（已有）
4. **Master Sheet**（按 training-setup.md 建好的那個）

---

## ① 取得 Anthropic API Key

1. 進 <https://console.anthropic.com> 註冊登入
2. Settings → API Keys → Create Key
3. 命名 `oa-training-feedback`，複製 key（`sk-ant-...`）**只會出現一次**
4. Billing → 加入信用卡 + 充值（最低 $5，新帳號可能有免費額度）

預估成本：每次對話約 $0.05，每月 50 次對話 = ~$2.5。

---

## ② 部署 Cloudflare Worker

### 方式 A：用 Wrangler CLI（推薦）

```bash
# 1. 裝 wrangler
npm install -g wrangler

# 2. 登入 Cloudflare
wrangler login

# 3. 進到 ai-feedback 資料夾
cd /Users/posh.lin/Documents/oa-schedule/ai-feedback

# 4. 設定環境變數（會問你 key、貼進去）
wrangler secret put ANTHROPIC_API_KEY
# 貼上你的 sk-ant-... key、Enter

wrangler secret put APPS_SCRIPT_URL
# 等下一步完成 Apps Script 部署後再回來執行這條

# 5. 部署 Worker
wrangler deploy
```

部署完會印出 URL，例如：`https://oa-training-ai-feedback.posh.workers.dev`

### 方式 B：Cloudflare Dashboard（無 CLI）

1. 進 <https://dash.cloudflare.com> → Workers & Pages → Create
2. Worker Name: `oa-training-ai-feedback`
3. Deploy → Edit code → 把 `worker.js` 內容貼進去
4. Settings → Variables → 加 secret：
   - `ANTHROPIC_API_KEY` = 你的 Anthropic key
   - `APPS_SCRIPT_URL` = 待 Apps Script 部署後填回
5. Save and Deploy

---

## ③ 建立 Master Sheet 與 Apps Script

### 3a. 建 Master Sheet（如果還沒建）

依 `training-setup.md` 第二節。確保 Sheet 已存在，並開「待審區」Tab（Apps Script 第一次跑會自動建）。

### 3b. 安裝 Apps Script

1. 開啟你的 Master Sheet
2. 上方選單：**擴充功能 → Apps Script**
3. 把預設的 `myFunction` 清空，貼入 `ai-feedback/code.gs` 全部內容
4. 左側「專案設定」（⚙️）→ 「指令碼屬性」→ 新增 3 個 properties：

| Property | Value |
|----------|-------|
| `GITHUB_REPO` | `poshlin/oa-schedule` |
| `GITHUB_TOKEN` | 第 ④ 步生成的 PAT |
| `REVIEW_SECRET` | 你自訂的密碼字串（例 `oa-review-2026-xyz`）|

5. 部署：**部署 → 新增部署**
   - 類型：**網路應用程式**
   - 執行身分：**我（你的 email）**
   - 存取權限：**任何人**（這對 webhook 必要；安全性靠 REVIEW_SECRET）
6. **複製 Web App URL**（會像 `https://script.google.com/macros/s/AKfyc.../exec`）
7. 回到 Cloudflare Worker，把這個 URL 填到 `APPS_SCRIPT_URL` secret

---

## ④ 建 GitHub Personal Access Token

1. <https://github.com/settings/personal-access-tokens/new>（Fine-grained）
2. Token name: `oa-schedule-auto-commit`
3. Expiration: **90 天**（之後到期會通知）
4. Repository access: **Only select repositories** → 選 `poshlin/oa-schedule`
5. Permissions: **Repository permissions** → **Contents → Read and write**
6. Generate token → 複製（`github_pat_...`）**只會出現一次**
7. 把這個 token 填到 Apps Script 的 `GITHUB_TOKEN` property

---

## ⑤ 配置 training.html

打開 `training.html`，找到第 ~360 行附近的 `const AI_WORKER_URL`：

```js
const AI_WORKER_URL = "https://REPLACE_WITH_YOUR_WORKER.workers.dev";
const MENTOR_SHEET_URL = "https://docs.google.com/spreadsheets/d/REPLACE_WITH_YOUR_SHEET_ID/edit";
```

替換成：
- `AI_WORKER_URL` = 第 ② 步部署的 Worker URL（注意不要加 `/chat` 或 `/submit`）
- `MENTOR_SHEET_URL` = 你的 Master Sheet 連結

存檔、commit、push。

---

## ⑥ 配置 review.html

打開 `review.html`，找到第 ~85 行：

```js
const APPS_SCRIPT_URL = "https://script.google.com/macros/s/REPLACE_WITH_YOUR_DEPLOYMENT_ID/exec";
```

替換成第 ③ 步取得的 Apps Script Web App URL。

存檔、commit、push。

---

## ⑦ 第一次測試

1. **測試 Worker**：瀏覽器打開 `https://你的-worker.workers.dev/`，應看到 `{"ok":true,"service":"..."}`

2. **測試 Apps Script**：瀏覽器打開
   `https://script.google.com/macros/s/.../exec?action=list&status=pending&secret=你的REVIEW_SECRET`
   應看到 `{"ok":true,"items":[]}`

3. **完整流程測試**：
   - 開 `training.html`
   - 點任何章節的「💡 建議改進」
   - 跟 AI 對話幾輪，模擬一個改進建議
   - 點「✅ 完成」
   - 應該看到「✅ 已送出給 Posh 審核」+ 編號
   - 開 `review.html?key=你的REVIEW_SECRET`
   - 應該看到剛送出的那條
   - 點「✅ 採納並 commit」
   - 過 30 秒看 GitHub repo，應該有新 commit
   - GitHub Pages 自動部署完後，重整 training.html 應該看到改動

---

## 安全模型

- **AI Worker（Cloudflare）**：沒有 auth，所有人都能用。風險：被人惡意呼叫累積 API 費用。緩解：Cloudflare 內建 rate limit，可設每分鐘 N 次。
- **Apps Script `submit`**：沒有 auth（任何能呼叫 Worker 的人都能送）。風險：垃圾投稿。緩解：靠 review.html 把關。
- **Apps Script `apply` / `list` / `reject`**：靠 `REVIEW_SECRET` 驗證。**這個密鑰只給 Posh 一個人**。
- **GitHub PAT**：90 天到期就要重新生成。到期前 GitHub 會 email 你。

---

## 成本估算（每月）

| 服務 | 用量 | 費用 |
|------|------|------|
| Anthropic API | 50 次對話 × ~10k tokens | ~$2.5 |
| Cloudflare Worker | <100k 請求/天 | $0（免費額度內） |
| Apps Script | <2000 次執行/天 | $0 |
| GitHub | repo + PAT | $0 |
| **總計** | | **~$2.5 / 月** |

---

## 故障排除

| 現象 | 可能原因 | 處理 |
|------|---------|------|
| training.html 點建議改進 → 顯示「Worker 未配置」 | AI_WORKER_URL 還是 placeholder | 改 training.html |
| Chat 一直 loading 不回應 | Worker fetch Anthropic 失敗 | 看 Cloudflare Worker logs |
| Chat 回應但點完成沒進 Sheet | APPS_SCRIPT_URL 沒設或錯 | 重設 secret |
| review.html 顯示「unauthorized」 | REVIEW_SECRET 不對 | 清 localStorage 重輸 |
| review 點採納 → 失敗 | GITHUB_TOKEN 過期或權限不足 | 重新生 PAT |
| 採納失敗「findText not found」 | AI 寫的 current_text 跟 HTML 對不上 | 用「✏️ 修改後採納」手動調整 |

---

## 後續可以加的功能（v2）

- 對話用 streaming（更即時的打字效果）
- review.html 加 diff highlighter（紅綠對比更明顯）
- AI 提案前先自動搜尋 rules.html 防衝突
- Slack / Email 通知：有新待審項目時通知 Posh
- 統計儀表板：每月多少回報 / 採納率 / 各章節分布
