/**
 * 橘子蘋果 線上事業部 行政執行台 — Google Apps Script v1
 *
 * 一支 .gs 接四個角色：
 *   掃描器（Mac mini）  publish        每天把待辦寫進「今日待辦」分頁
 *   業務（admin.html）  submit         留判斷／申請紀錄（必須帶 Google 登入 token）
 *   保旭（admin-review）list / approve / reject
 *   執行器（Mac mini）  claim / done   讀已核准的列、回報結果
 *   Kiku（API 節點）    kiku_approved  Kiku 核准後打進來，靠 REQ 編號對回判斷區
 *
 * 安全模型（跟 ai-feedback 一樣）：
 *   submit          靠 Google ID token（驗網域 orangeapple.co）
 *   其餘全部        靠 REVIEW_SECRET
 *
 * 指令碼屬性（專案設定 → 指令碼屬性）：
 *   REVIEW_SECRET     自訂密碼字串
 *   OAUTH_CLIENT_ID   GCP OAuth 用戶端 ID（admin.html 的 Google 登入用）
 *   ALLOWED_DOMAIN    orangeapple.co（可不設，預設就是這個）
 */

const TODO_TAB  = "今日待辦";
const JUDGE_TAB = "判斷區";

const TODO_HEADERS = [
  "date", "kind", "admission_id", "student", "salesperson", "owner",
  "check", "verdict", "message", "suggested", "course_code",
  "class_id", "class_room", "stage_id", "stage_name", "extra_json"
];
const JUDGE_HEADERS = [
  "timestamp", "row_id", "email", "name", "admission_id", "student",
  "check", "action", "target_value", "reason", "kiku_subject",
  "status", "posh_at", "posh_note", "exec_at", "evidence", "error", "raw_json"
];

// 業務端頁面能送的動作。執行器只認這張表以內、且 status=approved 的列。
const ALLOWED_SUBMIT = [
  "mark_confirmed",      // 起始堂次「確認無誤」→ 小紅點追加【系統確認 …】
  "write_teacher_note",  // 小綠點備註「首堂從 L{N} 開始上」
  "mark_done",           // 退費／停課／檢定班「已處理」（不寫 Corp，隔天掃描驗收）
  "request_makeup",      // 申請補課 → 走 Kiku；核准後 rest_times +1 ＋備註
  "request_suspend",     // 申請暫停 → 走 Kiku；第一版執行器不動 Corp，只記錄
  "kiku_draft"           // 只產生 Kiku 公版、不對應 Corp 動作
];
// 送出後直接進保旭核准台的（不經 Kiku）
const DIRECT_REVIEW = ["mark_confirmed", "write_teacher_note", "mark_done"];

const COL = (headers, name) => headers.indexOf(name) + 1;   // 1-based

function getProp(k) { return PropertiesService.getScriptProperties().getProperty(k); }

function sheet_(name, headers) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(name);
  if (!sh) {
    sh = ss.insertSheet(name);
    sh.appendRow(headers);
    sh.setFrozenRows(1);
  }
  return sh;
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function requireSecret_(given) {
  const want = getProp("REVIEW_SECRET");
  if (!want || given !== want) throw new Error("unauthorized");
}

// ─── 入口 ────────────────────────────────────────────────────────────────────

function doPost(e) {
  try {
    const params = e.parameter || {};
    const body = e.postData && e.postData.contents ? JSON.parse(e.postData.contents) : {};
    const action = body.action || params.action;
    // Kiku 的 API 節點不能自訂 body 結構，secret 放在 URL 上
    const secret = body.secret || params.secret;

    switch (action) {
      case "publish":       requireSecret_(secret); return json_(publish_(body));
      case "submit":        return json_(submit_(body));
      case "list":          requireSecret_(secret); return json_(list_(body.status));
      case "approve":       requireSecret_(secret); return json_(setStatus_(body.row_id, "approved", body.note));
      case "reject":        requireSecret_(secret); return json_(setStatus_(body.row_id, "rejected", body.note));
      case "claim":         requireSecret_(secret); return json_(claim_(body.peek === true));
      case "done":          requireSecret_(secret); return json_(done_(body));
      case "kiku_approved": requireSecret_(secret); return json_(kikuApproved_(body));
      default: return json_({ error: "unknown action: " + action });
    }
  } catch (err) {
    return json_({ error: err.message });
  }
}

function doGet(e) {
  try {
    const p = e.parameter || {};
    if (p.action === "list") { requireSecret_(p.secret); return json_(list_(p.status)); }
    if (p.action === "init") { requireSecret_(p.secret); sheet_(TODO_TAB, TODO_HEADERS); sheet_(JUDGE_TAB, JUDGE_HEADERS); return json_({ ok: true, tabs: [TODO_TAB, JUDGE_TAB] }); }
    if (p.action === "claim") { requireSecret_(p.secret); return json_(claim_(true)); }   // GET 一律只看不翻
    return json_({ ok: true, service: "OA 行政執行台 Apps Script v1" });
  } catch (err) {
    return json_({ error: err.message });
  }
}

// ─── publish：掃描器寫「今日待辦」 ─────────────────────────────────────────────

function publish_(body) {
  const items = body.items || [];
  // 🔴 空清單一律拒絕：掃描失敗時把今日待辦清空，業務會以為「今天沒事」。
  //    真的要清空請帶 force:true。
  if (!items.length && !body.force) throw new Error("items 為空，拒絕清空今日待辦（要清空請帶 force:true）");
  const sh = sheet_(TODO_TAB, TODO_HEADERS);
  const lock = LockService.getScriptLock(); lock.waitLock(20000);
  try {
  // 整批覆寫：只留當天。歷史在掃描器的 runs/ 裡，不需要在 Sheet 累積。
  if (sh.getLastRow() > 1) sh.deleteRows(2, sh.getLastRow() - 1);
  if (!items.length) return { ok: true, written: 0 };
  const today = body.date || Utilities.formatDate(new Date(), "Asia/Taipei", "yyyy-MM-dd");
  const rows = items.map(it => [
    today, it.kind || "dt", String(it.admission_id || ""), it.student || "",
    it.salesperson || "", it.owner || "", it.check || "", it.verdict || "",
    it.message || "", it.suggested || "", it.course_code || "",
    String(it.class_id || ""), it.class_room || "", String(it.stage_id || ""),
    it.stage_name || "", it.extra ? JSON.stringify(it.extra) : ""
  ]);
  sh.getRange(2, 1, rows.length, TODO_HEADERS.length).setValues(rows);
  return { ok: true, written: rows.length, date: today };
  } finally { lock.releaseLock(); }
}

// ─── submit：業務留紀錄（必須 Google 登入） ─────────────────────────────────────

function verifyGoogleToken_(idToken) {
  if (!idToken) throw new Error("缺少登入憑證，請重新登入 Google");
  const r = UrlFetchApp.fetch(
    "https://oauth2.googleapis.com/tokeninfo?id_token=" + encodeURIComponent(idToken),
    { muteHttpExceptions: true });
  if (r.getResponseCode() !== 200) throw new Error("登入憑證無效或已過期，請重新登入");
  const info = JSON.parse(r.getContentText());
  const clientId = getProp("OAUTH_CLIENT_ID");
  if (clientId && info.aud !== clientId) throw new Error("憑證不是給這個執行台用的");
  const domain = getProp("ALLOWED_DOMAIN") || "orangeapple.co";
  const email = String(info.email || "").toLowerCase();
  if (!(info.hd === domain || email.endsWith("@" + domain))) {
    throw new Error("請用公司 Google 帳號（@" + domain + "）登入");
  }
  if (info.exp && Number(info.exp) * 1000 < Date.now()) throw new Error("登入已過期，請重新登入");
  return { email: email, name: info.name || email.split("@")[0] };
}

function submit_(body) {
  const who = verifyGoogleToken_(body.id_token);
  const p = body.payload || {};
  if (ALLOWED_SUBMIT.indexOf(p.action) === -1) throw new Error("不允許的動作：" + p.action);
  if (!p.admission_id) throw new Error("缺少報名編號");
  if (p.action !== "write_teacher_note" && !String(p.reason || "").trim()) {
    throw new Error("請填理由");
  }
  const sh = sheet_(JUDGE_TAB, JUDGE_HEADERS);
  // 🔴 同毫秒兩筆會撞號；撞號的第二列永遠停在 approved、每天被執行一次（稽核 2026-09-23）
  const rowId = "REQ-" + Date.now().toString(36).toUpperCase() + "-" + Utilities.getUuid().slice(0, 4).toUpperCase();
  const status = DIRECT_REVIEW.indexOf(p.action) !== -1 ? "pending" : "kiku_pending";
  const lock = LockService.getScriptLock(); lock.waitLock(10000);
  try { sh.appendRow([
    new Date().toISOString(), rowId, who.email, who.name,
    String(p.admission_id), p.student || "", p.check || "", p.action,
    p.target_value != null ? String(p.target_value) : "", p.reason || "",
    p.kiku_subject || "", status, "", "", "", "", "",
    JSON.stringify(p)
  ]); } finally { lock.releaseLock(); }
  return { ok: true, row_id: rowId, status: status, email: who.email };
}

// ─── list / approve / reject ──────────────────────────────────────────────────

function rows_() {
  const sh = sheet_(JUDGE_TAB, JUDGE_HEADERS);
  const data = sh.getDataRange().getValues();
  if (data.length < 2) return { sh, headers: JUDGE_HEADERS, items: [] };
  const headers = data[0];
  const items = data.slice(1).map((r, i) => {
    const o = { _row: i + 2 };
    headers.forEach((h, j) => o[h] = r[j] instanceof Date ? r[j].toISOString() : r[j]);
    return o;
  });
  return { sh, headers, items };
}

function list_(status) {
  const { items } = rows_();
  const want = status || "pending";
  const out = want === "all" ? items : items.filter(x => x.status === want);
  out.forEach(x => delete x._row);
  return { ok: true, items: out };
}

function setStatus_(rowId, status, note) {
  const { sh, headers, items } = rows_();
  const it = items.find(x => x.row_id === rowId);
  if (!it) throw new Error("找不到 " + rowId);
  sh.getRange(it._row, COL(headers, "status")).setValue(status);
  sh.getRange(it._row, COL(headers, "posh_at")).setValue(new Date().toISOString());
  if (note != null) sh.getRange(it._row, COL(headers, "posh_note")).setValue(String(note));
  return { ok: true, row_id: rowId, status: status };
}

// ─── claim / done：執行器 ─────────────────────────────────────────────────────

function claim_(peek) {
  // approved → executing：核准台看得到「執行中」；執行器當掉的話列會停在 executing 而不是消失。
  // executing 的列也回傳：執行器有本地帳本，已寫過的只補回報、不會重做。
  // 🔴 peek=true（執行器 dry-run 用）：只讀不翻狀態，否則 dry-run 週所有核准列都會卡在「執行中」（複審 N8）
  const lock = LockService.getScriptLock(); lock.waitLock(10000);
  try {
    const { sh, headers, items } = rows_();
    const out = items.filter(x => x.status === "approved" || x.status === "executing");
    const now = new Date().toISOString();
    out.forEach(x => {
      if (!peek && x.status === "approved") { sh.getRange(x._row, COL(headers, "status")).setValue("executing"); sh.getRange(x._row, COL(headers, "exec_at")).setValue(now); x.status = "executing"; }
      delete x._row;
    });
    return { ok: true, items: out, peek: !!peek };
  } finally { lock.releaseLock(); }
}

function done_(body) {
  const { sh, headers, items } = rows_();
  const it = items.find(x => x.row_id === body.row_id);
  if (!it) throw new Error("找不到 " + body.row_id);
  sh.getRange(it._row, COL(headers, "status")).setValue(body.ok ? "done" : "failed");
  sh.getRange(it._row, COL(headers, "exec_at")).setValue(new Date().toISOString());
  sh.getRange(it._row, COL(headers, "evidence")).setValue(String(body.evidence || ""));
  sh.getRange(it._row, COL(headers, "error")).setValue(String(body.error || ""));
  return { ok: true };
}

// ─── kiku_approved：Kiku API 節點打進來 ──────────────────────────────────────

function kikuApproved_(body) {
  // Kiku 的 bodyMapping 帶哪些欄位我們不控制，所以把整包字串化找 REQ 編號
  const flat = JSON.stringify(body);
  // 🔴 row_id 格式是 REQ-<時間36進位>-<4碼uuid>，正則必須吃到第二段，否則永遠對不上（複審 N1）
  const m = flat.match(/REQ-[A-Z0-9]{6,}(?:-[A-Z0-9]{4})?/);
  const { sh, headers, items } = rows_();
  if (m) {
    const it = items.find(x => x.row_id === m[0]);
    if (it) {
      // 🔴 交叉驗證：Kiku 那張單的內容必須含這列的學生姓名或報名編號，
      //    否則業務在理由欄貼到別人的 REQ 編號，會核准到別人的申請。
      const consistent = (it.student && flat.indexOf(String(it.student)) !== -1)
                      || (it.admission_id && flat.indexOf(String(it.admission_id)) !== -1);
      if (!consistent) {
        sh.appendRow([new Date().toISOString(), "KIKU-" + Date.now().toString(36).toUpperCase(),
          "kiku", "Kiku API 節點", it.admission_id, it.student, it.check, "kiku_mismatch", "",
          "Kiku 核准的單帶著 " + m[0] + "，但內容裡沒有該列的學生姓名或報名編號，未自動核准",
          "", "review", "", "", "", "", "", flat.slice(0, 4000)]);
        return { ok: true, matched: m[0], status: "review", note: "student/admission mismatch" };
      }
      if (it.status === "kiku_pending") {
        sh.getRange(it._row, COL(headers, "status")).setValue("approved");
        sh.getRange(it._row, COL(headers, "posh_at")).setValue(new Date().toISOString());
        sh.getRange(it._row, COL(headers, "posh_note")).setValue("Kiku 核准");
        return { ok: true, matched: m[0], status: "approved" };
      }
      return { ok: true, matched: m[0], status: it.status, note: "狀態不是 kiku_pending，未變更" };
    }
  }
  // 對不到就留一列給保旭看，絕不亂做
  sh.appendRow([
    new Date().toISOString(), "KIKU-" + Date.now().toString(36).toUpperCase(),
    "kiku", "Kiku API 節點", "", "", "", "kiku_unmatched", "",
    "Kiku 核准了一張單，但找不到對應的 REQ 編號", "", "review", "", "", "", "", "",
    flat.slice(0, 4000)
  ]);
  return { ok: true, matched: null, status: "review" };
}

// ─── 自我診斷 ────────────────────────────────────────────────────────────────

function runSelfTest() {
  const out = [];
  out.push({ name: "REVIEW_SECRET", pass: !!getProp("REVIEW_SECRET") });
  out.push({ name: "OAUTH_CLIENT_ID", pass: !!getProp("OAUTH_CLIENT_ID"),
             note: "沒設的話 submit 只驗網域、不驗 aud（先能用，建好再補）" });
  try { sheet_(TODO_TAB, TODO_HEADERS); sheet_(JUDGE_TAB, JUDGE_HEADERS);
        out.push({ name: "兩個分頁可建立/可寫", pass: true }); }
  catch (e) { out.push({ name: "分頁", pass: false, error: e.message }); }
  Logger.log(JSON.stringify(out, null, 2));
  return out;
}
