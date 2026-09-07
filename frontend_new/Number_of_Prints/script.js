// 인화 수량 선택 화면 로직: -/+ 버튼으로 2~4 사이 값을 조절하고,
// 최솟값/최댓값에 도달하면 해당 버튼을 숨겨서 더 못 누르게 막는다.
//
// ★ 수정 사항:
//   - BACK 목적지: Select/Select_Photos -> Main (이 화면이 순서상 맨 앞이라
//     "사진 선택"으로 돌아가는 게 아니라 처음 화면으로 돌아가야 함)
//   - NEXT 누를 때 선택한 매수를 sessionStorage에 저장 (기존엔 저장 안 하고
//     그냥 넘어가서 나중에 인쇄 매수를 알 수 없었음)

const countEl = document.getElementById("count");
const minusBtn = document.getElementById("minusBtn");
const plusBtn = document.getElementById("plusBtn");
const backBtn = document.getElementById("backBtn");
const nextBtn = document.getElementById("nextBtn");

const MIN_COUNT = 2;
const MAX_COUNT = 4;
let count = 2;

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

render();

// ★ 이전 화면: Main (이 화면이 흐름상 맨 앞이므로)
backBtn.addEventListener("click", () => {
  window.location.href = "../Main/index.html";
});

// ★ 다음 화면(개인정보 입력)으로 가기 전에 선택한 매수를 저장
nextBtn.addEventListener("click", () => {
  sessionStorage.setItem("pikcha_print_quantity", String(count));
  window.location.href = "../Personal_Info/index.html";
});
