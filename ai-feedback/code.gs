/**
 * 橘子蘋果訓練頁 AI 改進助理 — Google Apps Script v1.1
 * 修正：_apply + updateGitHubFile_ 加入嚴格驗證、避免空 current_text 把內容插到檔頭
 *
 * 兩種 action：
 *   submit  — 從 training.html 接收 AI 整理好的建議，寫進「待審區」Sheet
 *   apply   — 從 review.html 收到 Posh 採納指令，用 GitHub API 自動 commit 修改
 *
 * 部署步驟見 ai-feedback/README.md
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
  try {
    const params = e.parameter || {};
    if (params.action === "list") {
      return _list({ status: params.status || "pending", secret: params.secret });
    }
    return jsonResponse_({ ok: true, service: "OA Training Feedback Apps Script v1.1" });
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

  // 支援從 review.html「修改後採納」覆寫 current_text 跟 proposed_text
  const currentText = body.override_current
    ? String(body.override_current).trim()
    : String(rowData[7] || "").trim();
  const proposedText = body.override_proposed || rowData[8];
  const chapterId = rowData[4];
  const rowId = rowData[1];

  // ★ 新增驗證：current_text 必須夠長
  if (currentText.length < 15) {
    return jsonResponse_({
      error: "current_text 太短或為空（少於 15 字元），無法安全定位替換點。\n\n建議：\n1. 用「✏️ 修改後採納」手動填入完整的 current_text\n2. 或回 Sheet 把該列的 current_text 補上具體原文後再採納\n3. 純新增內容的建議、建議手動編輯 training.html，不要走自動採納"
    }, 400);
  }

  const ghResult = updateGitHubFile_({
    path: "training.html",
    findText: currentText,
    replaceText: proposedText,
    commitMessage: "[AI feedback] " + chapterId + ": " + rowData[6] + "\n\n採納 " + rowId + "（" + rowData[2] + " 回報）\n\nCo-Authored-By: " + rowData[2] + " <noreply@orangeapple.co>"
  });

  sheet.getRange(rowIdx, 15).setValue("applied");
  sheet.getRange(rowIdx, 16).setValue(new Date().toISOString());
  sheet.getRange(rowIdx, 17).setValue(ghResult.sha || "");

  return jsonResponse_({ ok: true, commit_sha: ghResult.sha });
}

function updateGitHubFile_({ path, findText, replaceText, commitMessage }) {
  const repo = getProp("GITHUB_REPO");
  const token = getProp("GITHUB_TOKEN");
  if (!repo || !token) throw new Error("GITHUB_REPO 或 GITHUB_TOKEN 未設定");

  const api = "https://api.github.com/repos/" + repo + "/contents/" + path;
  const headers = {
    "Authorization": "token " + token,
    "Accept": "application/vnd.github+json"
  };

  const getResp = UrlFetchApp.fetch(api, { method: "get", headers: headers, muteHttpExceptions: true });
  const fileInfo = JSON.parse(getResp.getContentText());
  if (getResp.getResponseCode() !== 200) {
    throw new Error("GitHub get file failed: " + JSON.stringify(fileInfo));
  }
  const sha = fileInfo.sha;
  const currentContent = Utilities.newBlob(Utilities.base64Decode(fileInfo.content), "text/plain").getDataAsString();

  if (!findText || findText.length < 15) {
    throw new Error("findText 太短（< 15 字元），無法安全替換。請填具體原文。");
  }
  const firstIdx = currentContent.indexOf(findText);
  if (firstIdx === -1) {
    throw new Error("findText 不存在於 " + path + " — 可能 AI 提供的原文有誤、或檔案已被改過。建議『修改後採納』手動處理。");
  }
  const secondIdx = currentContent.indexOf(findText, firstIdx + 1);
  if (secondIdx !== -1) {
    throw new Error("findText 在 " + path + " 內出現多次（位置 " + firstIdx + " 跟 " + secondIdx + "），不確定要替換哪一個。請『修改後採納』、把 current_text 改得更具體（加上前後文）使其唯一。");
  }

  const newContent = currentContent.substring(0, firstIdx) + replaceText + currentContent.substring(firstIdx + findText.length);
  if (newContent === currentContent) {
    throw new Error("no change after replace");
  }

  const newBase64 = Utilities.base64Encode(Utilities.newBlob(newContent).getBytes());
  const putResp = UrlFetchApp.fetch(api, {
    method: "put",
    headers: headers,
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

/**
 * 自我診斷：驗證 Properties、Sheet、GitHub API 是否都通
 */
function runSelfTest() {
  const result = { checks: [] };

  const repo = getProp("GITHUB_REPO");
  const token = getProp("GITHUB_TOKEN");
  const secret = getProp("REVIEW_SECRET");
  result.checks.push({ name: "GITHUB_REPO", pass: !!repo, value: repo || "(未設)" });
  result.checks.push({ name: "GITHUB_TOKEN", pass: !!token, value: token ? "已設(隱藏)" : "(未設)" });
  result.checks.push({ name: "REVIEW_SECRET", pass: !!secret, value: secret ? "已設(隱藏)" : "(未設)" });

  try {
    getPendingSheet_();
    result.checks.push({ name: "可寫 Sheet (待審區)", pass: true });
  } catch (e) {
    result.checks.push({ name: "可寫 Sheet", pass: false, error: e.message });
  }

  if (repo && token) {
    try {
      const r = UrlFetchApp.fetch("https://api.github.com/repos/" + repo, {
        headers: { "Authorization": "token " + token, "Accept": "application/vnd.github+json" },
        muteHttpExceptions: true
      });
      const code = r.getResponseCode();
      result.checks.push({ name: "GitHub API 連通", pass: code === 200, value: "HTTP " + code });
    } catch (e) {
      result.checks.push({ name: "GitHub API 連通", pass: false, error: e.message });
    }
  } else {
    result.checks.push({ name: "GitHub API 連通", pass: false, error: "因為 GITHUB_REPO 或 GITHUB_TOKEN 未設、所以沒試" });
  }

  Logger.log(JSON.stringify(result, null, 2));
  return result;
}
