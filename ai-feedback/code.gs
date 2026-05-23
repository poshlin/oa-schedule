/**
 * 橘子蘋果訓練頁 AI 改進助理 — Google Apps Script
 *
 * 兩種 action：
 *   submit  — 從 Cloudflare Worker 接收 AI 整理好的建議，寫進「待審區」Sheet
 *   apply   — 從 review.html 收到 Posh 採納指令，用 GitHub API 自動 commit 修改
 *
 * 部署步驟：
 *   1. 在 Master Sheet 內：擴充功能 → Apps Script → 貼此檔案
 *   2. 專案屬性（Script Properties）填入：
 *        GITHUB_TOKEN      — 你的 GitHub Personal Access Token（需 repo 寫權限）
 *        GITHUB_REPO       — poshlin/oa-schedule
 *        REVIEW_SECRET     — 給 review.html 用的密鑰字串（自己設定）
 *   3. 部署 → 新增部署 → 類型「網路應用程式」→ 執行身分「我」→ 存取權限「任何人」
 *   4. 複製 URL → 填到 Cloudflare Worker 的 APPS_SCRIPT_URL 變數
 */

const PENDING_TAB = "待審區";
const PENDING_HEADERS = [
  "timestamp", "row_id", "reporter", "mode", "chapter_id", "category",
  "summary", "current_text", "proposed_text", "reasoning", "confidence",
  "needs_posh_decision", "needs_posh_reason", "conversation_log",
  "status", "posh_action_at", "commit_sha"
];

function getProp(key) {
  return PropertiesService.getScriptProperties().getProperty(key);
}

function getPendingSheet_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(PENDING_TAB);
  if (!sheet) {
    sheet = ss.insertSheet(PENDING_TAB);
    sheet.appendRow(PENDING_HEADERS);
    sheet.setFrozenRows(1);
  }
  return sheet;
}

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents);
    if (body.action === "submit") return _submit(body.payload);
    if (body.action === "apply")  return _apply(body);
    if (body.action === "reject") return _reject(body);
    if (body.action === "list")   return _list(body);
    return jsonResponse_({ error: "unknown action" }, 400);
  } catch (err) {
    return jsonResponse_({ error: err.message, stack: String(err) }, 500);
  }
}

function doGet(e) {
  // 給 review.html 拉清單用（GET 簡單 cache-friendly）
  try {
    const params = e.parameter || {};
    if (params.action === "list") {
      return _list({ status: params.status || "pending", secret: params.secret });
    }
    return jsonResponse_({ ok: true, service: "OA Training Feedback Apps Script" });
  } catch (err) {
    return jsonResponse_({ error: err.message }, 500);
  }
}

function _submit(payload) {
  const sheet = getPendingSheet_();
  const rowId = "REQ-" + Date.now().toString(36).toUpperCase();
  sheet.appendRow([
    payload.timestamp || new Date().toISOString(),
    rowId,
    payload.reporter || "anonymous",
    payload.mode || "",
    payload.chapter_id || "",
    payload.category || "",
    payload.summary || "",
    payload.current_text || "",
    payload.proposed_text || "",
    payload.reasoning || "",
    payload.reporter_confidence || "",
    payload.needs_posh_decision === true ? "TRUE" : "FALSE",
    payload.needs_posh_reason || "",
    payload.conversation_log || "",
    "pending",
    "",
    ""
  ]);
  return jsonResponse_({ ok: true, row_id: rowId });
}

function _list(body) {
  // 驗證 secret（避免外人抓 Sheet 內容）
  if (body.secret !== getProp("REVIEW_SECRET")) {
    return jsonResponse_({ error: "unauthorized" }, 401);
  }
  const sheet = getPendingSheet_();
  const data = sheet.getDataRange().getValues();
  if (data.length < 2) return jsonResponse_({ ok: true, items: [] });
  const headers = data[0];
  const rows = data.slice(1).map(r => {
    const obj = {};
    headers.forEach((h, i) => obj[h] = r[i]);
    return obj;
  });
  const filtered = body.status === "all"
    ? rows
    : rows.filter(r => r.status === (body.status || "pending"));
  return jsonResponse_({ ok: true, items: filtered });
}

function _reject(body) {
  if (body.secret !== getProp("REVIEW_SECRET")) {
    return jsonResponse_({ error: "unauthorized" }, 401);
  }
  const sheet = getPendingSheet_();
  const data = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (data[i][1] === body.row_id) {
      sheet.getRange(i + 1, 15).setValue("rejected");
      sheet.getRange(i + 1, 16).setValue(new Date().toISOString());
      sheet.getRange(i + 1, 17).setValue("REJECTED: " + (body.reason || ""));
      return jsonResponse_({ ok: true });
    }
  }
  return jsonResponse_({ error: "row not found" }, 404);
}

function _apply(body) {
  if (body.secret !== getProp("REVIEW_SECRET")) {
    return jsonResponse_({ error: "unauthorized" }, 401);
  }
  const sheet = getPendingSheet_();
  const data = sheet.getDataRange().getValues();
  let rowIdx = -1, rowData = null;
  for (let i = 1; i < data.length; i++) {
    if (data[i][1] === body.row_id) {
      rowIdx = i + 1;
      rowData = data[i];
      break;
    }
  }
  if (!rowData) return jsonResponse_({ error: "row not found" }, 404);

  const currentText = rowData[7];   // current_text
  const proposedText = rowData[8];  // proposed_text
  const chapterId = rowData[4];
  const rowId = rowData[1];

  // 取得 GitHub repo 內 training.html 現況
  const ghResult = updateGitHubFile_({
    path: "training.html",
    findText: currentText,
    replaceText: proposedText,
    commitMessage: `[AI feedback] ${chapterId}: ${rowData[6]}\n\n採納 ${rowId}（${rowData[2]} 回報）\n\nCo-Authored-By: ${rowData[2]} <noreply@orangeapple.co>`
  });

  // 更新 Sheet 狀態
  sheet.getRange(rowIdx, 15).setValue("applied");
  sheet.getRange(rowIdx, 16).setValue(new Date().toISOString());
  sheet.getRange(rowIdx, 17).setValue(ghResult.sha || "");

  return jsonResponse_({ ok: true, commit_sha: ghResult.sha });
}

function updateGitHubFile_({ path, findText, replaceText, commitMessage }) {
  const repo = getProp("GITHUB_REPO");
  const token = getProp("GITHUB_TOKEN");
  if (!repo || !token) throw new Error("GITHUB_REPO 或 GITHUB_TOKEN 未設定");

  const api = `https://api.github.com/repos/${repo}/contents/${path}`;
  const headers = {
    "Authorization": "token " + token,
    "Accept": "application/vnd.github+json"
  };

  // 1. 取得目前檔案內容 + SHA
  const getResp = UrlFetchApp.fetch(api, { method: "get", headers, muteHttpExceptions: true });
  const fileInfo = JSON.parse(getResp.getContentText());
  if (getResp.getResponseCode() !== 200) {
    throw new Error("GitHub get file failed: " + JSON.stringify(fileInfo));
  }
  const sha = fileInfo.sha;
  const currentContent = Utilities.newBlob(Utilities.base64Decode(fileInfo.content), "text/plain").getDataAsString();

  // 2. 確認 findText 存在
  if (currentContent.indexOf(findText) === -1) {
    throw new Error("findText not found in " + path + " — 可能已被改過、或 current_text 不夠精準。建議手動處理。");
  }

  // 3. 替換
  const newContent = currentContent.replace(findText, replaceText);
  if (newContent === currentContent) {
    throw new Error("no change after replace");
  }

  // 4. PUT 寫回（GitHub API 要 base64）
  const newBase64 = Utilities.base64Encode(Utilities.newBlob(newContent).getBytes());
  const putResp = UrlFetchApp.fetch(api, {
    method: "put",
    headers,
    contentType: "application/json",
    payload: JSON.stringify({
      message: commitMessage,
      content: newBase64,
      sha: sha
    }),
    muteHttpExceptions: true
  });
  const result = JSON.parse(putResp.getContentText());
  if (putResp.getResponseCode() < 200 || putResp.getResponseCode() >= 300) {
    throw new Error("GitHub PUT failed: " + JSON.stringify(result));
  }
  return { sha: result.commit && result.commit.sha };
}

function jsonResponse_(obj, code) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
