// 색상 스와치를 클릭하면 보드(#board) 배경색이 바뀐다.
// 이미 선택된 색을 다시 누르면 흰색으로 되돌아간다(토글).

const board = document.getElementById("board");
const swatches = document.querySelectorAll(".swatch");
const nextBtn = document.getElementById("nextBtn");

swatches.forEach((swatch) => {
  swatch.addEventListener("click", () => {
    const alreadyActive = swatch.classList.contains("active");
    swatches.forEach((s) => s.classList.remove("active")); // 항상 하나만 선택되게 초기화

    if (alreadyActive) {
      // 같은 색을 다시 클릭 → 선택 취소, 보드를 흰색으로 복구
      board.setAttribute("fill", "white");
    } else {
      // 새 색상 선택 → 보드에 적용하고 해당 스와치에 active 표시(테두리) 부여
      board.setAttribute("fill", swatch.dataset.color);
      swatch.classList.add("active");
    }
  });
});

// 다음 화면(프레임 선택)으로 이동
nextBtn.addEventListener("click", () => {
  window.location.href = "../Select_Frame/index.html";
});
