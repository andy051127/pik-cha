// 웨이팅리스트 관리 화면 로직.
// GET /admin/waitlist는 Basic Auth가 필요(sgu-pikcha-admin), 취소는 공개 엔드포인트
// (/waitlist/cancel, sgu-pikcha-waitlist)를 그대로 재사용한다.

const API_BASE = "https://nwwtnmzm3l.execute-api.ap-northeast-2.amazonaws.com/prod";

const statusMsg = document.getElementById("statusMsg");
const waitlistBody = document.getElementById("waitlistBody");
const refreshBtn = document.getElementById("refreshBtn");

const STATUS_LABEL = {
  waiting: "대기중",
  called: "호출됨",
  in_session: "촬영중",
  photographed: "촬영완료",
  completed: "인화완료",
  canceled: "취소됨",
};

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
    headers: { ...(options.headers || {}), Authorization: authHeader },
  });
  if (res.status === 401) {
    sessionStorage.removeItem("pikcha_admin_auth");
    authHeader = null;
    throw new Error("인증에 실패했습니다. 다시 로그인해주세요.");
  }
  return res;
}

// ── 목록 조회/렌더링 ──────────────────────────────────────────
async function loadWaitlist() {
  statusMsg.textContent = "불러오는 중...";
  try {
    const res = await authedFetch("/admin/waitlist");
    const data = await res.json();
    if (!res.ok) {
      statusMsg.textContent = data.error || "조회에 실패했습니다.";
      return;
    }
    statusMsg.textContent = "";
    renderRows(data.waitlist || []);
  } catch (err) {
    console.error(err);
    statusMsg.textContent = err.message;
  }
}

function renderRows(items) {
  if (items.length === 0) {
    waitlistBody.innerHTML = `<tr><td colspan="8" class="empty-row">등록된 웨이팅이 없습니다</td></tr>`;
    return;
  }

  waitlistBody.innerHTML = items.map((item) => {
    const cancelable = item.status === "waiting" || item.status === "called";
    const createdAt = item.created_at ? new Date(item.created_at).toLocaleString("ko-KR") : "-";
    return `
      <tr>
        <td>${item.ticket_number}</td>
        <td>${escapeHtml(item.department || "")}</td>
        <td>${escapeHtml(item.name || "")}</td>
        <td>${item.party_size ?? "-"}명</td>
        <td>${escapeHtml(item.phone_number || "")}</td>
        <td><span class="status-pill status-${item.status}">${STATUS_LABEL[item.status] || item.status}</span></td>
        <td>${createdAt}</td>
        <td>
          <button type="button" class="cancel-btn" data-ticket="${item.ticket_number}" ${cancelable ? "" : "disabled"}>
            취소
          </button>
        </td>
      </tr>
    `;
  }).join("");

  waitlistBody.querySelectorAll(".cancel-btn:not(:disabled)").forEach((btn) => {
    btn.addEventListener("click", () => cancelTicket(btn.dataset.ticket));
  });
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

// ── 취소 (공개 엔드포인트, Basic Auth 불필요) ─────────────────────
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
      statusMsg.textContent = data.error || "취소에 실패했습니다.";
      return;
    }
    loadWaitlist();
  } catch (err) {
    console.error(err);
    statusMsg.textContent = "서버에 연결할 수 없습니다.";
  }
}

refreshBtn.addEventListener("click", loadWaitlist);
loadWaitlist();
