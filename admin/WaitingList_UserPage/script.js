// 웨이팅 등록 폼 로직.
// 이 페이지는 S3 정적호스팅으로 배포되는 독립 페이지라, 부스 PC 로컬 서버가 아니라
// API Gateway를 직접 호출한다 (booth PC 카메라 플로우와는 무관).

const API_BASE = "https://nwwtnmzm3l.execute-api.ap-northeast-2.amazonaws.com/prod";

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

// 전화번호 입력 중 자동으로 010-XXXX-XXXX 형태로 하이픈을 붙여준다 (기존 Personal_Info와 동일한 규칙)
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

// ── 인원수 스테퍼 (1~8명) ──────────────────────────────────
minusBtn.addEventListener("click", () => {
  const current = parseInt(partySizeEl.textContent, 10);
  if (current > MIN_PARTY) partySizeEl.textContent = current - 1;
});
plusBtn.addEventListener("click", () => {
  const current = parseInt(partySizeEl.textContent, 10);
  if (current < MAX_PARTY) partySizeEl.textContent = current + 1;
});

// ── 등록 제출 ──────────────────────────────────────────────
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

    // 발급받은 순번을 상태조회 화면으로 그대로 넘김 - 이 화면을 닫지 않고 대기하는 게
    // 의도된 흐름이라 별도 로그인/기기간 동기화 없이 URL 쿼리스트링으로만 전달
    window.location.href = `../WaitingList_UserPage_Status/index.html?ticket=${result.ticket_number}`;
  } catch (err) {
    console.error("웨이팅 등록 요청 실패:", err);
    errorMsg.textContent = "서버에 연결할 수 없습니다.";
    submitBtn.disabled = false;
  }
});

validate();
