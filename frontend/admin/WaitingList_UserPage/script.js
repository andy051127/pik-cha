// 모바일 웨이팅 등록 폼: 학과 · 학번 · 이름 · 전화번호 · 인원수를 받아 등록한다.
const API_BASE = "https://nwwtnmzm3l.execute-api.ap-northeast-2.amazonaws.com/prod";
const departmentSelect = document.getElementById("dept");
const studentIdInput = document.getElementById("sid");
const nameInput = document.getElementById("name");
const phoneInput = document.getElementById("phone");
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
    const valid = !!departmentSelect.value.trim() && !!studentIdInput.value.trim()
        && !!nameInput.value.trim() && PHONE_PATTERN.test(phoneInput.value);
    submitBtn.classList.toggle("disabled", !valid || submitting);
    return valid;
}

departmentSelect.addEventListener("change", validate);
studentIdInput.addEventListener("input", () => { showMessage(""); validate(); });
nameInput.addEventListener("input", () => { showMessage(""); validate(); });
phoneInput.addEventListener("input", () => {
    phoneInput.value = formatPhone(phoneInput.value);
    showMessage("");
    validate();
});
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
    submitting = true;
    validate();
    showMessage("등록 중...");
    try {
        const res = await fetch(`${API_BASE}/waitlist`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ department: departmentSelect.value.trim(), student_id: studentIdInput.value.trim(),
                name: nameInput.value.trim(), phone_number: phoneInput.value.trim(),
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
