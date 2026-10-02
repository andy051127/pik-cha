// 순번 입력 화면 로직 (구 Personal_Info 대체):
// 1) 숫자 키패드로 순번을 입력받고, 최소 1자리 이상이면 NEXT를 누를 수 있게 한다.
// 2) NEXT를 누르면 로컬 백엔드(/api/waitlist/start-session)에 순번을 보내서
//    서버(DynamoDB 웨이팅리스트)에 실제 등록된 번호인지 확인한다.
// 3) 성공하면 학과/학번/이름/전화번호를 돌려받아 sessionStorage에 저장한다.
//    이름/전화번호는 기존 pikcha_personal_info 키/형태 그대로 써서 Select_Frame이
//    수정 없이 그대로 읽어 쓸 수 있게 한다.
// 4) 실패(없는 순번/이미 종료된 순번)하면 에러 메시지를 보여주고 다시 시도하게 한다.

const API_BASE = "http://localhost:8000";
const MAX_DIGITS = 6;

const ticketLabelWrap = document.getElementById("ticketLabelWrap");
const ticketDisplay = document.getElementById("ticketDisplay");
const errorMsg = document.getElementById("errorMsg");
const keyBtns = document.querySelectorAll(".key-btn");
const backspaceBtn = document.getElementById("backspaceBtn");
const backBtn = document.getElementById("backBtn");
const nextBtn = document.getElementById("nextBtn");

let value = "";

// 입력이 없으면 "순번" 안내 문구를, 입력이 시작되면 숫자를 같은 자리에 중앙 정렬로 보여준다.
function render() {
  ticketDisplay.textContent = value;
  ticketLabelWrap.classList.toggle("has-value", value.length > 0);
  nextBtn.disabled = value.length === 0;
}

function addDigit(digit) {
  if (value.length >= MAX_DIGITS) return;
  value += digit;
  errorMsg.textContent = "";
  render();
}

function removeDigit() {
  value = value.slice(0, -1);
  errorMsg.textContent = "";
  render();
}

keyBtns.forEach((btn) => {
  btn.addEventListener("click", () => addDigit(btn.dataset.digit));
});

backspaceBtn.addEventListener("click", removeDigit);

// ★ 물리 키보드 지원: 숫자키(메인/넘패드)와 Backspace를 화면 키패드와 동일하게 처리한다.
document.addEventListener("keydown", (e) => {
  if (e.key >= "0" && e.key <= "9") {
    addDigit(e.key);
  } else if (e.key === "Backspace") {
    removeDigit();
  } else if (e.key === "Enter" && !nextBtn.disabled) {
    nextBtn.click();
  }
});

backBtn.addEventListener("click", () => {
  window.location.href = "../Number_of_Prints/index.html";
});

nextBtn.addEventListener("click", async () => {
  if (nextBtn.disabled) return;

  const ticketNumber = parseInt(value, 10);
  if (!Number.isInteger(ticketNumber)) {
    errorMsg.textContent = "순번을 숫자로 입력해주세요.";
    return;
  }

  nextBtn.disabled = true;
  errorMsg.textContent = "확인 중...";

  try {
    const res = await fetch(`${API_BASE}/api/waitlist/start-session`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticket_number: ticketNumber }),
    });
    const result = await res.json();

    if (!res.ok) {
      errorMsg.textContent = result.detail || "순번 확인에 실패했습니다.";
      nextBtn.disabled = false;
      return;
    }

    // ★ Select_Frame이 그대로 쓸 수 있도록 기존 키/형태(name, phoneNumber) 유지
    sessionStorage.setItem(
      "pikcha_personal_info",
      JSON.stringify({
        name: result.name || "",
        phoneNumber: result.phone_number || "",
      })
    );

    // 순번 자체는 촬영 시작(/api/four-cut/start) 때 필요해서 따로 저장
    sessionStorage.setItem(
      "pikcha_ticket_info",
      JSON.stringify({
        ticketNumber: result.ticket_number,
        department: result.department || "",
        studentId: result.student_id || "",
      })
    );

    window.location.href = "../CountDown/index.html";
  } catch (err) {
    console.error("순번 확인 요청 실패 (백엔드 서버가 켜져 있는지 확인):", err);
    errorMsg.textContent = "서버에 연결할 수 없습니다.";
    nextBtn.disabled = false;
  }
});

render(); // 페이지가 막 열렸을 때(입력값 없음)의 초기 상태를 맞춘다.
