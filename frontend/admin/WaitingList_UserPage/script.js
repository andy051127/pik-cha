// 모바일 시안에는 학번/전화번호 칸이 없어 제출 시 입력받는다.
const API_BASE = "https://nwwtnmzm3l.execute-api.ap-northeast-2.amazonaws.com/prod";
const departmentSelect = document.getElementById("dept");
const nameInput = document.getElementById("name");
const partySizeEl = document.getElementById("head-count");
const submitBtn = document.getElementById("btn-register");
const errorMsg = document.getElementById("error-msg");
const PHONE_PATTERN = /^010-\d{4}-\d{4}$/;
let submitting = false;

function formatPhone(value) {
    const digits = value.replace(/\D/g, "").slice(0, 11);
    if (digits.length <= 3) return digits;
    if (digits.length <= 7) return `${digits.slice(0, 3)}-${digits.slice(3)}`;
    return `${digits.slice(0, 3)}-${digits.slice(3, 7)}-${digits.slice(7)}`;
}

function showMessage(message) {
    errorMsg.textContent = message;
    errorMsg.hidden = !message;
}

function validate() {
    const valid = !!departmentSelect.value.trim() && !!nameInput.value.trim();
    submitBtn.classList.toggle("disabled", !valid || submitting);
    return valid;
}

departmentSelect.addEventListener("change", validate);
nameInput.addEventListener("input", () => { showMessage(""); validate(); });
document.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", (event) => {
        event.preventDefault();
        const current = parseInt(partySizeEl.textContent, 10);
        partySizeEl.textContent = Math.max(1, Math.min(8, current + (button.dataset.action === "increase" ? 1 : -1)));
    });
});

submitBtn.addEventListener("click", async (event) => {
    event.preventDefault();
    if (!validate() || submitting) return;
    const studentId = window.prompt("학번을 입력하세요");
    if (studentId === null) { showMessage("학번 입력이 취소되었습니다."); return; }
    if (!studentId.trim()) { showMessage("학번을 입력해주세요."); return; }
    const enteredPhone = window.prompt("전화번호를 입력하세요 (010-XXXX-XXXX)");
    if (enteredPhone === null) { showMessage("전화번호 입력이 취소되었습니다."); return; }
    const phoneNumber = formatPhone(enteredPhone);
    if (!PHONE_PATTERN.test(phoneNumber)) { showMessage("전화번호를 확인해주세요."); return; }
    submitting = true;
    validate();
    showMessage("등록 중...");
    try {
        const res = await fetch(`${API_BASE}/waitlist`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ department: departmentSelect.value.trim(), student_id: studentId.trim(),
                name: nameInput.value.trim(), phone_number: phoneNumber,
                party_size: parseInt(partySizeEl.textContent, 10) }),
        });
        const result = await res.json();
        if (!res.ok) throw new Error(result.error || "등록에 실패했습니다.");
        location.href = `../WaitingList_UserPage_Status/index.html?ticket=${result.ticket_number}`;
    } catch (err) {
        showMessage(err.message || "서버에 연결할 수 없습니다.");
        submitting = false;
        validate();
    }
});

validate();
