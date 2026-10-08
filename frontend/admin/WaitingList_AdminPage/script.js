// 관리자 화면 로직.
// · 주소 해시(#home | #waiting | #print)로 오른쪽 브라우저 창 화면을 바꾼다.
// · 웨이팅 리스트 / 사진 인화 관리 표는 Basic Auth 관리자 엔드포인트에서 불러온다.
// · 핸드폰 "현재 대기 팀"은 공개 엔드포인트를 10초마다 폴링한다.

const API_BASE = "https://nwwtnmzm3l.execute-api.ap-northeast-2.amazonaws.com/prod";
const POLL_MS = 10000;
const VIEWS = ["home", "waiting", "print"];

const stage = document.querySelector(".stage");
const statusMsg = document.getElementById("status-msg");
const waitlistBody = document.getElementById("waitlist-body");
const printBody = document.getElementById("print-body");
const reloadBtn = document.getElementById("btn-reload");
const $ = (id) => document.getElementById(id);

const STATUS_LABEL = {
  waiting: "대기중",
  called: "호출됨",
  in_session: "촬영중",
  photographed: "촬영완료",
  completed: "인화완료",
  canceled: "취소됨",
};
const ENTERED = ["in_session", "photographed", "completed"];
const PRINT_LABEL = { pending: "대기중", printed: "완료", failed: "실패" };

// ── 화면 전환 ─────────────────────────────────────────────────
function currentView() {
  const name = location.hash.slice(1);
  return VIEWS.includes(name) ? name : "home";
}

function showView() {
  const view = currentView();
  stage.dataset.view = view;
  document.querySelector(".tab-waiting").classList.toggle("is-active", view === "waiting");
  document.querySelector(".tab-print").classList.toggle("is-active", view === "print");
  setMessage("");
  loadView(view);
}

function loadView(view) {
  if (view === "waiting") loadWaitlist();
  else if (view === "print") loadSessions();
}

// ── 안내 문구 ─────────────────────────────────────────────────
function setMessage(text) {
  statusMsg.textContent = text;
  statusMsg.hidden = !text;
}

// ── 로그인 (Basic Auth 헤더를 매번 요청에 실어 보냄) ──────────────
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

// ── 공통 유틸 ─────────────────────────────────────────────────
function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

// "2026.10.6. 오후 3:17:29" (full) / "10.6. 오후 3:17" (짧게)
function formatTime(value, full = true) {
  if (!value) return "-";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "-";
  const h = d.getHours();
  const ampm = h < 12 ? "오전" : "오후";
  const hh = h % 12 || 12;
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  const date = `${d.getMonth() + 1}.${d.getDate()}.`;
  return full
    ? `${d.getFullYear()}.${date} ${ampm} ${hh}:${mm}:${ss}`
    : `${date} ${ampm} ${hh}:${mm}`;
}

function isToday(value) {
  if (!value) return false;
  const d = new Date(value);
  const now = new Date();
  return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate();
}

// ── 핸드폰 위젯 ───────────────────────────────────────────────
function renderDate() {
  const now = new Date();
  $("date-weekday").textContent = now.toLocaleDateString("ko-KR", { weekday: "long" });
  $("date-day").textContent = now.getDate();
}

async function pollWaitingCount() {
  try {
    const res = await fetch(`${API_BASE}/waitlist/count`);
    const data = await res.json();
    if (res.ok) $("phone-waiting").textContent = data.waiting_count;
  } catch (err) {
    console.error("대기팀 수 조회 실패:", err);
  }
}

// 누적 방문객 = 취소되지 않은 팀의 인원 합
function renderVisitors(items) {
  const total = items
    .filter((item) => item.status !== "canceled")
    .reduce((sum, item) => sum + (Number(item.party_size) || 0), 0);
  $("phone-visitors").textContent = total;
}

// ── 웨이팅 리스트 ─────────────────────────────────────────────
async function loadWaitlist() {
  try {
    const res = await authedFetch("/admin/waitlist");
    const data = await res.json();
    if (!res.ok) {
      setMessage(data.error || "조회에 실패했습니다.");
      return;
    }
    const items = data.waitlist || [];
    renderWaitlist(items);
    renderVisitors(items);
    $("sum-waiting").textContent = items.filter((i) => i.status === "waiting" || i.status === "called").length;
    $("sum-entered").textContent = items.filter((i) => ENTERED.includes(i.status)).length;
  } catch (err) {
    console.error(err);
    setMessage(err.message);
  }
}

function renderWaitlist(items) {
  if (items.length === 0) {
    waitlistBody.innerHTML = `<tr><td colspan="8" class="empty-row">등록된 웨이팅이 없습니다</td></tr>`;
    return;
  }

  waitlistBody.innerHTML = items.map((item) => {
    const cancelable = item.status === "waiting" || item.status === "called";
    return `
      <tr>
        <td>${item.ticket_number}</td>
        <td>${escapeHtml(item.department || "")}</td>
        <td>${escapeHtml(item.name || "")}</td>
        <td>${item.party_size ?? "-"}</td>
        <td>${escapeHtml(item.phone_number || "")}</td>
        <td><span class="pill-s status-${item.status}">${STATUS_LABEL[item.status] || escapeHtml(item.status)}</span></td>
        <td>${formatTime(item.created_at)}</td>
        <td>
          <button type="button" class="row-btn cancel-btn" data-ticket="${item.ticket_number}" ${cancelable ? "" : "disabled"}>취소</button>
        </td>
      </tr>
    `;
  }).join("");

  waitlistBody.querySelectorAll(".cancel-btn:not(:disabled)").forEach((btn) => {
    btn.addEventListener("click", () => cancelTicket(btn.dataset.ticket));
  });
}

// 취소 (공개 엔드포인트, Basic Auth 불필요)
async function cancelTicket(ticketNumber) {
  if (!window.confirm(`${ticketNumber}번을 취소할까요?`)) return;

  try {
    const res = await fetch(`${API_BASE}/waitlist/cancel`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticket_number: parseInt(ticketNumber, 10) }),
    });
    const data = await res.json();
    if (!res.ok) {
      setMessage(data.error || "취소에 실패했습니다.");
      return;
    }
    setMessage("");
    loadWaitlist();
    pollWaitingCount();
  } catch (err) {
    console.error(err);
    setMessage("서버에 연결할 수 없습니다.");
  }
}

// ── 사진 인화 관리 ────────────────────────────────────────────
async function loadSessions() {
  try {
    const res = await authedFetch("/admin/print-status");
    const data = await res.json();
    if (!res.ok) {
      setMessage(data.error || "조회에 실패했습니다.");
      return;
    }
    const items = data.sessions || [];
    renderSessions(items);
    const printed = items.filter((i) => i.printStatus === "printed");
    $("sum-print-today").textContent = printed.filter((i) => isToday(i.created_at)).length;
    $("sum-print-total").textContent = printed.length;
  } catch (err) {
    console.error(err);
    setMessage(err.message);
  }
}

function renderSessions(items) {
  if (items.length === 0) {
    printBody.innerHTML = `<tr><td colspan="9" class="empty-row">세션이 없습니다</td></tr>`;
    return;
  }

  printBody.innerHTML = items.map((item) => {
    const printStatus = item.printStatus || "pending";
    const smsSent = !!item.sms_sent;
    const sessionId = escapeHtml(item.session_id || "");
    const canReprint = !!(item.bucket && item.fourcut_key);
    const canResendSms = !!item.phoneNumber;

    return `
      <tr>
        <td>${item.ticketNumber ?? "-"}</td>
        <td title="${sessionId}">${escapeHtml((item.session_id || "").slice(0, 18))}</td>
        <td>${escapeHtml(item.name || "")}</td>
        <td>${escapeHtml(item.phoneNumber || "")}</td>
        <td>${item.printQuantity ?? 1}</td>
        <td><span class="pill-s print-${printStatus}">${PRINT_LABEL[printStatus] || escapeHtml(printStatus)}</span></td>
        <td><span class="pill-s ${smsSent ? "sms-sent" : "sms-unsent"}">${smsSent ? "발송됨" : "안 됨"}</span></td>
        <td title="${formatTime(item.created_at)}">${formatTime(item.created_at, false)}</td>
        <td>
          <div class="row-actions">
            <button type="button" class="row-btn reprint-btn" data-session="${sessionId}" ${canReprint ? "" : "disabled"}>재인쇄</button>
            <button type="button" class="row-btn resend-btn" data-session="${sessionId}" ${canResendSms ? "" : "disabled"}>SMS재발송</button>
          </div>
        </td>
      </tr>
    `;
  }).join("");

  printBody.querySelectorAll(".reprint-btn:not(:disabled)").forEach((btn) => {
    btn.addEventListener("click", () => reprint(btn.dataset.session));
  });
  printBody.querySelectorAll(".resend-btn:not(:disabled)").forEach((btn) => {
    btn.addEventListener("click", () => resendSms(btn.dataset.session));
  });
}

async function sessionAction(path, sessionId, confirmText, doneText, failText) {
  if (!window.confirm(confirmText)) return;
  try {
    const res = await authedFetch(path, {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId }),
    });
    const data = await res.json();
    if (!res.ok) {
      setMessage(data.error || failText);
      return;
    }
    setMessage(doneText);
    loadSessions();
  } catch (err) {
    console.error(err);
    setMessage(err.message);
  }
}

const reprint = (id) => sessionAction("/admin/print/reprint", id,
  "이 세션을 다시 인쇄 큐에 넣을까요?", "재인쇄 큐에 등록했습니다.", "재인쇄 요청에 실패했습니다.");
const resendSms = (id) => sessionAction("/admin/sms/resend", id,
  "SMS를 다시 보낼까요?", "SMS를 재발송했습니다.", "SMS 재발송에 실패했습니다.");

// ── 시작 ──────────────────────────────────────────────────────
reloadBtn.addEventListener("click", () => {
  reloadBtn.classList.remove("is-spinning");
  void reloadBtn.offsetWidth;               // 애니메이션 다시 시작
  reloadBtn.classList.add("is-spinning");
  setMessage("");
  loadView(currentView());
});

window.addEventListener("hashchange", showView);

renderDate();
pollWaitingCount();
setInterval(pollWaitingCount, POLL_MS);

// 이미 로그인한 상태면 웨이팅 화면이 아니어도 누적 방문객을 채운다 (로그인 창은 띄우지 않음)
if (authHeader && currentView() !== "waiting") {
  authedFetch("/admin/waitlist")
    .then((res) => (res.ok ? res.json() : null))
    .then((data) => data && renderVisitors(data.waitlist || []))
    .catch((err) => console.error(err));
}

showView();
