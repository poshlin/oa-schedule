# 團隊主檔設定指南（給 Posh）

team.html 已建好、但**還沒接上資料**。照下面 4 步做完就會自動長出卡片。

預估時間：**首次 25 分鐘**，之後每次新增 / 修改 < 1 分鐘。

---

## Step 1：建 Sheet 分頁「團隊主檔」

打開你現有的 ai-feedback Sheet（跟「待審區」同一份）→ 底部 + → 新增分頁、命名 `團隊主檔`。

**第一列貼這 10 個欄位（順序不能變）：**

```
中文姓名	英文名	部門	職稱	標籤	照片URL	加入日期	一句話介紹	公開	排序
```

複製這一整行貼到 A1（會自動分成 10 個欄位）。

### 欄位說明

| 欄位 | 必填 | 範例 | 說明 |
|---|---|---|---|
| 中文姓名 | ✅ | 林保旭 | 顯示在卡片大字 |
| 英文名 | ✅ | Posh | 顯示在中文姓名旁邊小字、也是大頭縮寫的依據 |
| 部門 | ✅ | 線上事業部 | 用來分組顯示，建議用：`線上事業部` / `課程顧問` / `課務` / `電銷` / `管理` |
| 職稱 | ✅ | 總監 | 卡片青色那行 |
| 標籤 | ⬜ | 新人 / 6/1 報到 | 卡片左上角的小膠囊（可空白） |
| 照片URL | ⬜ | Drive 分享連結 | 沒填會顯示姓名首字大頭貼 |
| 加入日期 | ⬜ | 2021-01 | 顯示「加入 2021-01」 |
| 一句話介紹 | ⬜ | 前 TutorABC Top Sales | 30 字內最佳 |
| 公開 | ✅ | TRUE / FALSE | **打 FALSE 不會顯示**、用來下架離職同仁或暫存草稿 |
| 排序 | ⬜ | 1, 2, 3... | 數字越小越前面（沒填 = 99） |

### 樣本資料（直接複製到 Sheet 第 2 列開始）

```
林保旭	Posh	線上事業部	總監	總監	（貼 Drive 分享連結）	2021-01	前 TutorABC Top Sales、5 年程式教育領導經驗	TRUE	1
林家元	Eric	課務	主管		（貼 Drive 分享連結）		課務主管、流程跟系統他熟	TRUE	1
趙柔瑄	Catherine	電銷	組長		（貼 Drive 分享連結）		電銷組長、轉單高手	TRUE	1
```

---

## Step 2：建照片資料夾

1. 開 [Google Drive](https://drive.google.com) → 新增 → 資料夾、命名 `OA 團隊照片`
2. 右鍵資料夾 → 共用 → **「知道連結的任何人」可以「檢視」**
3. 把成員照片拖進去（建議正方形、512×512 以上、JPG 或 PNG）
4. 對每張照片右鍵 → 取得連結 → 複製
5. 把連結貼到 Sheet 對應的「照片URL」欄

> 支援的 Drive 連結格式：team.html 會自動轉成可顯示的縮圖、你不用手動處理。
>
> ⚠️ **重要**：每張照片**本身**也要設成「知道連結的任何人可檢視」（資料夾共用設定通常會繼承、但保險起見點進去檢查一下）。

---

## Step 3：發布 Sheet 成 CSV

1. 在 Sheet 介面：**檔案 → 共用 → 發布到網路**
2. 第一個下拉選 **「團隊主檔」分頁**（不要選「整份文件」）
3. 第二個下拉選 **「逗號分隔值 (.csv)」**
4. 點「發布」→ 複製出現的 URL（格式像 `https://docs.google.com/spreadsheets/d/e/.../pub?...&output=csv`）

⚠️ **這個 URL 不是 Sheet 的編輯網址、是專門給機器讀的 CSV 端點。**

---

## Step 4：把 URL 貼進 team.html

打開 [team.html on GitHub](https://github.com/poshlin/oa-schedule/edit/main/team.html) → Cmd+F 找 `PASTE_PUBLISHED_CSV_URL_HERE`，把它換成 Step 3 的 URL。

接著找 `PASTE_SHEET_EDIT_URL_HERE`、換成 Sheet 本身的編輯網址（從瀏覽器網址列複製、格式像 `https://docs.google.com/spreadsheets/d/XXX/edit`）。

下方填 commit 訊息 → Commit changes → 等 1～2 分鐘 Pages 重建。

---

## Step 5：驗證

開 <https://poshlin.github.io/oa-schedule/team.html> → 應該看到卡片網格。

**沒看到的話 debug 順序：**

1. 頁面有顯示「尚未設定資料來源」→ 表示 CSV_URL 還是 `PASTE_*`、回 Step 4
2. 顯示「載入失敗」→ 點 F12 看 Console 訊息
   - HTTP 404：CSV_URL 貼錯
   - 「沒有資料」：Sheet 第 1 列標題沒對到、或所有資料的「公開」欄都是 FALSE
3. 卡片出來但沒照片：點不出來的照片 → 那張照片的 Drive 共用權限沒開到「任何人可檢視」

---

## 之後的維護動作

| 場景 | 怎麼做 |
|---|---|
| 改某人職稱 | Sheet 改一格、存檔、60 秒後 team.html 自動更新 |
| 加新同仁 | Sheet 新增一列、照片貼 Drive → URL 填進 Sheet |
| 同仁離職 | 把那列「公開」改成 FALSE（資料保留、頁面不顯示） |
| 整批更新 | 直接編輯 Sheet、不需要 commit、不需要找 Claude |
| 新人自助填寫 | 之後做 Google Form 收 → 進「待審區」分頁 → 你打 TRUE 上線 |

**重點：完全不需要碰 GitHub 或對話 AI。Sheet 就是真相來源。**
