# 行政執行台 — 部署指南（給 Posh）

三個角色、一份 Sheet、一支 Apps Script、兩個靜態頁：

```
掃描器（Mac mini 07:00）──publish──▶ Sheet「今日待辦」──CSV──▶ admin.html（業務，Google 登入）
                                                                    │ submit（帶 Google token）
                                                                    ▼
                                                            Sheet「判斷區」
                                                     ┌──────────┴──────────┐
                              admin-review.html（你，?key=）          Kiku（申請類）
                                   核准／退回                    核准 → API 節點 → kiku_approved
                                                     └──────────┬──────────┘
                                                        status = approved
                                                                ▼
                                                  executor.py（Mac mini）→ Corp → done/failed
```

設計說明在 `~/Documents/OA_業務行政減負_2026-09-20/16_*.md`、`17_*.md`。

---

## 你要做的一次性設定（約 30 分鐘）

### ① 建 Sheet（2 分鐘）

新建一份 Google Sheet，命名「線上事業部 行政執行台」。分頁不用先建，Apps Script 第一次跑會自動建「今日待辦」「判斷區」。

### ② 裝 Apps Script（10 分鐘）

1. Sheet 上方 **擴充功能 → Apps Script**，清空預設內容，貼入 `admin/code.gs` 全部
2. 左側 ⚙️ **專案設定 → 指令碼屬性**，新增：

| 屬性 | 值 |
|---|---|
| `REVIEW_SECRET` | 你自訂的密碼字串（例 `oa-admin-2026-xxxx`）。**Mac mini 的 .env 與 Kiku API 節點都會用到** |
| `OAUTH_CLIENT_ID` | 第 ③ 步拿到的用戶端 ID（可以晚點補；沒設時 submit 只驗網域） |

3. **部署 → 新增部署**：類型「網路應用程式」、執行身分「我」、存取權限「**任何人**」（跟 ai-feedback 一樣，安全靠 secret 與 token）
4. 複製 **Web App URL**（`https://script.google.com/macros/s/…/exec`）
5. 驗證：瀏覽器開 `<URL>?action=list&secret=<你的REVIEW_SECRET>` → 應看到 `{"ok":true,"items":[]}`
6. 在 Apps Script 編輯器跑一次 `runSelfTest`，看執行記錄全部 pass

### ③ 建 Google 登入用戶端 ID（10 分鐘）—— 🔴 開放給業務之前一定要做完

業務端頁面用 Google 登入，每一筆送出都帶著 Google 驗證過的公司信箱。
`OAUTH_CLIENT_ID` 沒設的期間，Apps Script 只驗信箱網域、不驗「這個憑證是不是簽給我們這個網站的」，
自己測可以，**不要在這個狀態開放給業務用**。

1. <https://console.cloud.google.com/apis/credentials> → 選（或新建）一個專案
2. 若第一次：**OAuth 同意畫面** → 使用者類型「內部」（只限 orangeapple.co）→ 應用程式名稱「橘子蘋果行政執行台」→ 儲存
3. **建立憑證 → OAuth 用戶端 ID** → 類型「網頁應用程式」
   - 已授權的 JavaScript 來源：`https://poshlin.github.io`
   - 已授權的重新導向 URI：不用填
4. 複製 **用戶端 ID**（`xxxx.apps.googleusercontent.com`）
5. 填回兩處：Apps Script 指令碼屬性 `OAUTH_CLIENT_ID`、`admin.html` 的 `OAUTH_CLIENT_ID` 常數

### ④ 發布「今日待辦」成 CSV（2 分鐘）

先讓兩個分頁長出來：瀏覽器開 `<Web App URL>?action=init&secret=<你的REVIEW_SECRET>` → 回 `{"ok":true,"tabs":[…]}`。

然後跟 team.html 一樣：Sheet **檔案 → 共用 → 發布到網路** → 分頁選「今日待辦」、格式「逗號分隔值 (.csv)」→ 發布 → 複製 URL → 填進 `admin.html` 與 `admin-review.html` 的 `TODO_CSV_URL`。

🔴 `--publish` **只在全掃時生效**（`--limit`／`--class`／`--cert-only` 會拒絕發布），掃描有失敗項或一筆都沒掃到時也不發布、保留上一份——避免把業務的清單洗成不完整的版本。

### ⑤ 把 URL 填回頁面

| 檔案 | 常數 |
|---|---|
| `admin.html` | `APPS_SCRIPT_URL`、`TODO_CSV_URL`、`OAUTH_CLIENT_ID` |
| `admin-review.html` | `APPS_SCRIPT_URL`、`TODO_CSV_URL` |

改完 commit → push → 1 分鐘後 Pages 更新。

### ⑥ Mac mini 的 `~/oa-admin-scan/.env` 加兩行

🔴 是 **`~/oa-admin-scan/.env`**（排程實際讀的那份），不是 `~/Documents/daily_report_skill/.env`。

```
ADMIN_SCRIPT_URL=https://script.google.com/macros/s/…/exec
ADMIN_SECRET=<你的REVIEW_SECRET>
```

然後重跑 `sh ~/Documents/OA_業務行政減負_2026-09-20/scanner/setup_macmini.sh`（會保留這兩行，不會洗掉）。
之後要開真寫入，再加一行 `EXECUTOR_APPLY=1`。

---

## 給 CEO 的工單：在 Kiku 流程末端加一個 API 節點

**要改哪裡**：kikuflow「特殊個案」流程（v22）與「課程轉移」流程（v7），在「保旭核准」節點之後、結束之前，各加一個 **API 節點**。

**改成什麼**：

| 設定 | 值 |
|---|---|
| URL | `https://script.google.com/macros/s/…/exec?action=kiku_approved&secret=<REVIEW_SECRET>` |
| Method | POST |
| bodyMapping | 全部欄位（至少要含「主旨」與「申請理由／備註」那一欄，因為 REQ 編號寫在理由裡） |
| responseMapping | 不用 |

**怎麼驗收**：業務在執行台生一張補課單（理由裡有 `REQ-xxxx`）→ 貼進 Kiku 送出 → 保旭在 Kiku 核准 → 30 秒內 Sheet「判斷區」那一列的 status 從 `kiku_pending` 變成 `approved`、posh_note 顯示「Kiku 核准」。

Apps Script 會交叉驗證：Kiku 送來的內容必須含該列的學生姓名或報名編號，否則只列「待複核」不放行（防止業務在理由欄貼到別人的 REQ 編號）。

**節點建好之前**：申請會停在「Kiku 待核」。你在 Kiku 核准後，到核准台的「Kiku 待核」分頁按「核准」手動放行即可。

kikuflow 手冊對應頁：<https://kikuflow.com/manual/workflow/api-ai-node-behavior>（官方範例就是接 Google Apps Script）。

---

## 第一次端到端測試

1. Mac mini：`python3 scan.py --limit 3 --publish` → Sheet「今日待辦」有資料
2. 你用公司 Google 帳號開 `admin.html` → 登入 → 選「我是誰」→ 看到清單 → 對一筆按「確認無誤」填理由 → Sheet「判斷區」多一列，email 是你的
3. 開 `admin-review.html?key=<REVIEW_SECRET>` → 看到那列 → 按核准 → status 變 `approved`
4. Mac mini：`python3 executor.py`（預設 dry-run）→ 印出「我會做什麼」，**包括每張表單會回送幾個欄位、有沒有多值欄位** → 你看過沒問題 → `python3 executor.py --apply` → Corp 小紅點多一行、判斷區 status 變 `done`、evidence 有時間與內容

核准台會多看到「執行中」分頁：執行器一 claim 就把列標成 executing，執行完才變 done／failed。停在 executing 超過一天＝執行器沒跑完，去看 `runs/executor_last.json`。

`run_log.tsv` 最後一欄有 `exec=N`（執行器退出碼：0 成功／2 有失敗／4 沒跑起來）。

## 安全模型

| 端點 | 誰能用 | 防護 |
|---|---|---|
| `submit` | 登入公司 Google 帳號的人 | Google ID token（驗網域，有設 OAUTH_CLIENT_ID 時再驗 aud） |
| `publish` `claim` `done` | Mac mini | `REVIEW_SECRET`（在 .env） |
| `list` `approve` `reject` | 你 | `REVIEW_SECRET`（`?key=`，存 localStorage） |
| `kiku_approved` | Kiku API 節點 | `REVIEW_SECRET`（在 URL 上） |

執行器只做三種 Corp 動作（追加小紅點標記／補課 +1 ＋備註／追加小綠點備註），全部「只追加不覆蓋」，寫完讀回驗證；`assessments/delete` 永遠在黑名單。

補課 +1 的冪等鍵：執行器會在備註多留一行「（執行台 REQ-xxxx）」，同一張申請絕不 +1 兩次；本地還有一份帳本 `runs/executed_ledger.json`，Corp 寫成功但回報失敗時只補回報、不重做。

已知限制：Apps Script 回給 Kiku 的永遠是 HTTP 200（平台限制），對不上的單會以「待複核」列出現在核准台，不會有錯誤碼。
