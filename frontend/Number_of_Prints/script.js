// 인화 수량 선택 화면 로직: -/+ 버튼으로 2~4 사이 값을 조절하고,
// 최솟값/최댓값에 도달하면 해당 버튼을 숨겨서 더 못 누르게 막는다.

const countEl = document.getElementById("count");
const minusBtn = document.getElementById("minusBtn");
const plusBtn = document.getElementById("plusBtn");
const backBtn = document.getElementById("backBtn");
const nextBtn = document.getElementById("nextBtn");

const MIN_COUNT = 2;
const MAX_COUNT = 4;
let count = 2;

// 현재 count 값을 화면에 반영하고, 한계값이면 해당 버튼을 비활성화(숨김)한다.
function render() {
  countEl.textContent = count;
  minusBtn.disabled = count <= MIN_COUNT;
  plusBtn.disabled = count >= MAX_COUNT;
}

minusBtn.addEventListener("click", () => {
  if (count > MIN_COUNT) {
    count -= 1;
    render();
  }
});

plusBtn.addEventListener("click", () => {
  if (count < MAX_COUNT) {
    count += 1;
    render();
  }
});

render(); // 초기 상태(2)에 맞춰 버튼 표시 여부를 한 번 맞춰준다.

// 이전 화면(사진 선택)으로 이동
backBtn.addEventListener("click", () => {
  window.location.href = "../Select/Select_Photos/index.html";
});

// 다음 화면(개인정보 입력)으로 이동
nextBtn.addEventListener("click", () => {
  // TODO: 다음 화면 연결
  window.location.href = "../Personal_Info/index.html";
});
