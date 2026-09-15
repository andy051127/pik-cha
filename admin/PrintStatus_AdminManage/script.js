// 인화 상태 관리 화면 로직. 전부 Basic Auth 필요한 관리자 엔드포인트.

const API_BASE = "https://nwwtnmzm3l.execute-api.ap-northeast-2.amazonaws.com/prod";

const statusMsg = document.getElementById("statusMsg");
const sessionsBody = document.getElementById("sessionsBody");
const refreshBtn = document.getElementById("refreshBtn");

const PRINT_LABEL = { pending: "대기중", printed: "완료", failed: "실패" };

// ── 로그인 (Basic Auth 헤더, admin/WaitingList_AdminManage와 동일 패턴) ──────
let authHeader = sessionStorage.getItem("pikcha_admin_auth");

function promptLogin() {
  const username = window.prompt("관리자 아이디");
  if (username === null) return false;
  const password = window.prompt("비밀번호");
  if (password === null) return false;
  authHeader = "Basic " + btoa(`${username}:${password}`);
  sessionStorage.setItem("pikcha_admin_auth", authHeader);
  return true;
}

async function authedFetch(path, options = {}) {
  if (!authHeader) {
    if (!promptLogin()) throw new Error("로그인이 필요합니다");
  }
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...(options.headers || {}), Authorization: authHeader, "Content-Type": "application/json" },
  });
  if (res.status === 401) {
    sessionStorage.removeItem("pikcha_admin_auth");
    authHeader = null;
    throw new Error("인증에 실패했습니다. 다시 로그인해주세요.");
  }
  return res;
}

// ── 목록 조회/렌더링 ──────────────────────────────────────────
async function loadSessions() {
  statusMsg.textContent = "불러오는 중...";
  try {
    const res = await authedFetch("/admin/print-status");
    const data = await res.json();
    if (!res.ok) {
      statusMsg.textContent = data.error || "조회에 실패했습니다.";
      return;
    }
    statusMsg.textContent = "";
    renderRows(data.sessions || []);
  } catch (err) {
    console.error(err);
    statusMsg.textContent = err.message;
  }
}

function renderRows(items) {
  if (items.length === 0) {
    sessionsBody.innerHTML = `<tr><td colspan="9" class="empty-row">세션이 없습니다</td></tr>`;
    return;
  }

  sessionsBody.innerHTML = items.map((item) => {
    const printStatus = item.printStatus || "pending";
    const smsSent = !!item.sms_sent;
    const createdAt = item.created_at ? new Date(item.created_at).toLocaleString("ko-KR") : "-";
    const shortId = (item.session_id || "").slice(0, 18);
    const canReprint = !!(item.bucket && item.fourcut_key);
    const canResendSms = !!item.phoneNumber;

    return `
      <tr>
        <td>${item.ticketNumber ?? "-"}</td>
        <td title="${escapeHtml(item.session_id || "")}">${escapeHtml(shortId)}</td>
        <td>${escapeHtml(item.name || "")}</td>
        <td>${escapeHtml(item.phoneNumber || "")}</td>
        <td>${item.printQuantity ?? 1}</td>
        <td><span class="status-pill print-${printStatus}">${PRINT_LABEL[printStatus] || printStatus}</span></td>
        <td><span class="sms-pill ${smsSent ? "sms-sent" : "sms-unsent"}">${smsSent ? "발송됨" : "안 됨"}</span></td>
        <td>${createdAt}</td>
        <td>
          <div class="row-actions">
            <button type="button" class="action-btn reprint-btn" data-session="${item.session_id}" ${canReprint ? "" : "disabled"}>재인쇄</button>
            <button type="button" class="action-btn resend-btn" data-session="${item.session_id}" ${canResendSms ? "" : "disabled"}>SMS재발송</button>
          </div>
        </td>
      </tr>
    `;
  }).join("");

  sessionsBody.querySelectorAll(".reprint-btn:not(:disabled)").forEach((btn) => {
    btn.addEventListener("click", () => reprint(btn.dataset.session));
  });
  sessionsBody.querySelectorAll(".resend-btn:not(:disabled)").forEach((btn) => {
    btn.addEventListener("click", () => resendSms(btn.dataset.session));
  });
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

// ── 액션 ──────────────────────────────────────────────────────
async function reprint(sessionId) {
  if (!window.confirm("이 세션을 다시 인쇄 큐에 넣을까요?")) return;
  try {
    const res = await authedFetch("/admin/print/reprint", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId }),
    });
    const data = await res.json();
    if (!res.ok) {
      statusMsg.textContent = data.error || "재인쇄 요청에 실패했습니다.";
      return;
    }
    statusMsg.textContent = "재인쇄 큐에 등록했습니다.";
    loadSessions();
  } catch (err) {
    console.error(err);
    statusMsg.textContent = err.message;
  }
}

async function resendSms(sessionId) {
  if (!window.confirm("SMS를 다시 보낼까요?")) return;
  try {
    const res = await authedFetch("/admin/sms/resend", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId }),
    });
    const data = await res.json();
    if (!res.ok) {
      statusMsg.textContent = data.error || "SMS 재발송에 실패했습니다.";
      return;
    }
    statusMsg.textContent = "SMS를 재발송했습니다.";
    loadSessions();
  } catch (err) {
    console.error(err);
    statusMsg.textContent = err.message;
  }
}

refreshBtn.addEventListener("click", loadSessions);
loadSessions();
