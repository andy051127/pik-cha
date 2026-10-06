// 5초 뒤 촬영 화면으로 이동한다.
const countEl = document.getElementById("countdown-number");
const dialEl = countEl.closest(".dial");
let count = 5;
countEl.textContent = ` ${count}`;

// 숫자가 바뀔 때마다 원·숫자 튀는 모션을 다시 재생한다
function tick() {
    dialEl.classList.remove("tick");
    void dialEl.offsetWidth; // 리플로우로 애니메이션 재시작
    dialEl.classList.add("tick");
}

tick();

const timer = setInterval(() => {
    count--;
    if (count <= 0) {
        clearInterval(timer);
        location.href = "../05_take_a_picture/index.html";
        return;
    }
    countEl.textContent = ` ${count}`;
    tick();
}, 1000);
