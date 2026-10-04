// 업로드 결과의 QR을 보여주고 30초 후 다음 손님을 준비한다.
const qrImageEl = document.getElementById("download-qr");
const countEl = document.getElementById("print-timer");
try {
    const result = JSON.parse(sessionStorage.getItem("pikcha_result") || "null");
    if (result && result.qrSrc) qrImageEl.src = result.qrSrc;
    else qrImageEl.alt = "QR을 표시할 수 없습니다";
} catch (err) {
    console.error("결과 데이터를 읽지 못했습니다:", err);
}

let remaining = 30;
countEl.textContent = remaining;
const timer = setInterval(() => {
    remaining--;
    if (remaining <= 0) {
        clearInterval(timer);
        ["pikcha_result", "pikcha_selected_photos", "pikcha_personal_info",
            "pikcha_ticket_info", "pikcha_print_quantity"].forEach((key) => sessionStorage.removeItem(key));
        location.href = "../01_landing_main/index.html";
        return;
    }
    countEl.textContent = remaining;
}, 1000);
