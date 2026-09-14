// 웨이팅 태블릿 디스플레이 + (스태프 대신입력용) 등록 폼 로직.
// S3 정적호스팅 독립 페이지라 API Gateway를 직접 호출.

const API_BASE = "https://nwwtnmzm3l.execute-api.ap-northeast-2.amazonaws.com/prod";
const NOW_SERVING_POLL_MS = 5000;

// ── 왼쪽 패널: 대기팀 수 공개 표시 (개인정보 없이 숫자만) ──────────
const waitingCountEl = document.getElementById("waitingCount");

async function pollWaitingCount() {
  try {
    const res = await fetch(`${API_BASE}/waitlist/count`);
    const data = await res.json();
    if (res.ok) {
      waitingCountEl.textContent = String(data.waiting_count).padStart(2, "0");
    }
  } catch (err) {
    console.error("대기팀 수 조회 실패:", err);
  }
}

pollWaitingCount();
setInterval(pollWaitingCount, NOW_SERVING_POLL_MS);

// ── 오른쪽 폼: 등록 (WaitingList_UserPage와 동일 로직) ────────────
const departmentSelect = document.getElementById("department");
const studentIdInput = document.getElementById("studentId");
const nameInput = document.getElementById("name");
const phoneInput = document.getElementById("phone");
const partySizeEl = document.getElementById("partySize");
const minusBtn = document.getElementById("minusBtn");
const plusBtn = document.getElementById("plusBtn");
const errorMsg = document.getElementById("errorMsg");
const submitBtn = document.getElementById("submitBtn");

const MIN_PARTY = 1;
const MAX_PARTY = 8;
const PHONE_PATTERN = /^010-\d{4}-\d{4}$/;

function formatPhone(value) {
  const digits = value.replace(/\D/g, "").slice(0, 11);
  if (digits.length <= 3) return digits;
  if (digits.length <= 7) return `${digits.slice(0, 3)}-${digits.slice(3)}`;
  return `${digits.slice(0, 3)}-${digits.slice(3, 7)}-${digits.slice(7)}`;
}

function validate() {
  const ok =
    departmentSelect.value.trim().length > 0 &&
    studentIdInput.value.trim().length > 0 &&
    nameInput.value.trim().length > 0 &&
    PHONE_PATTERN.test(phoneInput.value);
  submitBtn.disabled = !ok;
  return ok;
}

phoneInput.addEventListener("input", () => {
  phoneInput.value = formatPhone(phoneInput.value);
  validate();
});
studentIdInput.addEventListener("input", validate);
nameInput.addEventListener("input", validate);
departmentSelect.addEventListener("change", validate);

minusBtn.addEventListener("click", () => {
  const current = parseInt(partySizeEl.textContent, 10);
  if (current > MIN_PARTY) partySizeEl.textContent = current - 1;
});
plusBtn.addEventListener("click", () => {
  const current = parseInt(partySizeEl.textContent, 10);
  if (current < MAX_PARTY) partySizeEl.textContent = current + 1;
});

submitBtn.addEventListener("click", async () => {
  if (!validate()) return;

  submitBtn.disabled = true;
  errorMsg.textContent = "등록 중...";

  try {
    const res = await fetch(`${API_BASE}/waitlist`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        department: departmentSelect.value.trim(),
        student_id: studentIdInput.value.trim(),
        name: nameInput.value.trim(),
        phone_number: phoneInput.value.trim(),
        party_size: parseInt(partySizeEl.textContent, 10),
      }),
    });
    const result = await res.json();

    if (!res.ok) {
      errorMsg.textContent = result.error || "등록에 실패했습니다.";
      submitBtn.disabled = false;
      return;
    }

    errorMsg.textContent = `등록 완료! 순번 ${result.ticket_number}번`;
    studentIdInput.value = "";
    nameInput.value = "";
    phoneInput.value = "";
    partySizeEl.textContent = "2";
    submitBtn.disabled = false;
    pollWaitingCount();
  } catch (err) {
    console.error("웨이팅 등록 요청 실패:", err);
    errorMsg.textContent = "서버에 연결할 수 없습니다.";
    submitBtn.disabled = false;
  }
});
