// 순번을 확인하고 촬영 세션에 필요한 정보를 저장한다.
const API_BASE = "http://localhost:8000";
const numberLine = document.getElementById("number-line");
const nextBtn = document.getElementById("nav-next");
const errorMsg = document.getElementById("error-msg");
let digits = "";
let submitting = false;

function showMessage(message) {
    errorMsg.textContent = message;
    errorMsg.hidden = !message;
}

function render() {
    numberLine.textContent = digits;
    numberLine.style.fontSize = "48px";
    numberLine.style.lineHeight = "0";
    numberLine.style.color = "var(--coral)";
    nextBtn.classList.toggle("disabled", !digits || submitting);
    nextBtn.setAttribute("aria-disabled", String(!digits || submitting));
}

document.querySelectorAll("#keypad [data-key]").forEach((key) => {
    key.addEventListener("click", (event) => {
        event.preventDefault();
        if (submitting) return;
        digits = key.dataset.key === "backspace" ? digits.slice(0, -1) : digits + key.dataset.key;
        showMessage("");
        render();
    });
});

nextBtn.addEventListener("click", async (event) => {
    event.preventDefault();
    if (!digits || submitting) return;
    const ticketNumber = parseInt(digits, 10);
    if (!Number.isInteger(ticketNumber)) {
        showMessage("순번을 숫자로 입력해주세요.");
        return;
    }
    submitting = true;
    showMessage("확인 중...");
    render();
    try {
        const res = await fetch(`${API_BASE}/api/waitlist/start-session`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ticket_number: ticketNumber }),
        });
        const result = await res.json();
        if (!res.ok) throw new Error(result.detail || "순번 확인에 실패했습니다.");
        sessionStorage.setItem("pikcha_personal_info", JSON.stringify({
            name: result.name || "", phoneNumber: result.phone_number || "",
        }));
        sessionStorage.setItem("pikcha_ticket_info", JSON.stringify({
            ticketNumber: result.ticket_number,
            department: result.department || "",
            studentId: result.student_id || "",
        }));
        location.href = "../03_number_of_prints/index.html";
    } catch (err) {
        showMessage(err.message || "서버에 연결할 수 없습니다.");
        submitting = false;
        render();
    }
});

render();
