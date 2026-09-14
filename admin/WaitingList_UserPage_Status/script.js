// 웨이팅 상태조회 화면 로직.
// URL의 ?ticket= 쿼리스트링으로 순번을 받아서, 그 번호의 최신 상태를 주기적으로 폴링한다.
// S3 정적호스팅 독립 페이지라 API Gateway를 직접 호출 (booth PC 로컬 서버와 무관).

const API_BASE = "https://nwwtnmzm3l.execute-api.ap-northeast-2.amazonaws.com/prod";
const POLL_INTERVAL_MS = 10000;

const ticketNumberEl = document.getElementById("ticketNumber");
const ticketDetailEl = document.getElementById("ticketDetail");
const ticketWaitEl = document.getElementById("ticketWait");
const printStatusEl = document.getElementById("printStatus");
const errorMsg = document.getElementById("errorMsg");
const cancelBtn = document.getElementById("cancelBtn");

const params = new URLSearchParams(window.location.search);
const ticketNumber = params.get("ticket");

if (!ticketNumber) {
  ticketDetailEl.textContent = "순번 정보가 없습니다. 등록 화면에서 다시 시도해주세요.";
  cancelBtn.disabled = true;
} else {
  fetchStatus();
  setInterval(fetchStatus, POLL_INTERVAL_MS);
}

function waitingStageText(data) {
  if (data.status === "waiting") {
    return `앞에 ${data.teams_ahead}팀 · 예상 대기 ${data.estimated_wait_minutes}분`;
  }
  if (data.status === "called") {
    return "지금 호출됐어요! 부스로 와주세요";
  }
  if (data.status === "in_session") {
    return "촬영 중입니다";
  }
  if (data.status === "photographed") {
    return "촬영 완료 - 인화 준비중입니다";
  }
  if (data.status === "canceled") {
    return "취소된 웨이팅입니다";
  }
  return "";
}

function printStatusText(data) {
  if (data.print_status === "printed") {
    return "인화가 완료됐어요! 문자로도 안내드렸어요 🎉";
  }
  if (data.print_status === "failed") {
    return "인화 중 문제가 발생했어요. 부스 스태프에게 문의해주세요.";
  }
  if (data.print_status === "pending") {
    return "인화 대기중입니다. 잠시만 기다려주세요.";
  }
  return "촬영 후 사진 인화 상태가 표시됩니다";
}

async function fetchStatus() {
  try {
    const res = await fetch(`${API_BASE}/waitlist/${ticketNumber}`);
    const data = await res.json();

    if (!res.ok) {
      errorMsg.textContent = data.error || "조회에 실패했습니다.";
      return;
    }
    errorMsg.textContent = "";

    ticketNumberEl.textContent = data.ticket_number;
    ticketDetailEl.textContent = `${data.department} · ${data.name} · ${data.party_size}명`;
    ticketWaitEl.textContent = waitingStageText(data);
    printStatusEl.textContent = printStatusText(data);

    // waiting/called 상태일 때만 취소 가능 - 이미 촬영 들어간 뒤엔 취소 의미 없음
    cancelBtn.disabled = !(data.status === "waiting" || data.status === "called");
  } catch (err) {
    console.error("상태 조회 실패:", err);
    errorMsg.textContent = "서버에 연결할 수 없습니다.";
  }
}

cancelBtn.addEventListener("click", async () => {
  if (cancelBtn.disabled) return;
  if (!window.confirm("정말 웨이팅을 취소할까요?")) return;

  cancelBtn.disabled = true;
  try {
    const res = await fetch(`${API_BASE}/waitlist/cancel`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticket_number: parseInt(ticketNumber, 10) }),
    });
    const data = await res.json();

    if (!res.ok) {
      errorMsg.textContent = data.error || "취소에 실패했습니다.";
      cancelBtn.disabled = false;
      return;
    }

    fetchStatus();
  } catch (err) {
    console.error("취소 요청 실패:", err);
    errorMsg.textContent = "서버에 연결할 수 없습니다.";
    cancelBtn.disabled = false;
  }
});
