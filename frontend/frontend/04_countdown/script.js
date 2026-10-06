// 5초 뒤 촬영 화면으로 이동한다.
const countEl = document.getElementById("countdown-number");
let count = 5;
countEl.textContent = ` ${count}`;
const timer = setInterval(() => {
    count--;
    if (count <= 0) {
        clearInterval(timer);
        location.href = "../05_take_a_picture/index.html";
        return;
    }
    countEl.textContent = ` ${count}`;
}, 1000);
