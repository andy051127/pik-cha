// 5초 카운트다운: 매초 숫자를 1씩 줄이고, 0이 되면 다음 화면으로 이동한다.

const countEl = document.getElementById("count");

const START_COUNT = 5;
const NEXT_PAGE = "../Take_a_Picture/index.html"; // TODO: 다음 페이지 경로가 정해지면 교체

let count = START_COUNT;
countEl.textContent = count;

const timer = setInterval(() => {
  count -= 1;

  if (count <= 0) {
    clearInterval(timer);
    window.location.href = NEXT_PAGE;
    return;
  }

  countEl.textContent = count;
}, 1000);
