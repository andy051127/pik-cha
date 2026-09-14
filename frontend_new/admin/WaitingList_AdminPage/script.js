// 대시보드 Dashboard 카드의 "현재 대기중" 숫자를 공개 엔드포인트로 폴링.
const API_BASE = "https://nwwtnmzm3l.execute-api.ap-northeast-2.amazonaws.com/prod";
const POLL_MS = 10000;

const waitingCountEl = document.getElementById("waitingCount");

async function pollWaitingCount() {
  try {
    const res = await fetch(`${API_BASE}/waitlist/count`);
    const data = await res.json();
    if (res.ok) waitingCountEl.textContent = data.waiting_count;
  } catch (err) {
    console.error("대기팀 수 조회 실패:", err);
  }
}

pollWaitingCount();
setInterval(pollWaitingCount, POLL_MS);
