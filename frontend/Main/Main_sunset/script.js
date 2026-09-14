// 화면(body) 어디를 클릭하든 인화 수량 선택 화면(Number_of_Prints)으로 이동시킨다.
// "Touch to start!" 안내 문구에 대응하는 인터랙션이다.
document.body.addEventListener("click", () => {
  window.location.href = "../../Number_of_Prints/index.html";
});
