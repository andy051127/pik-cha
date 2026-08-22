// 화면(body) 어디를 클릭하든 사진 선택 화면(Select_Photos)으로 이동시킨다.
// "Touch to start!" 안내 문구에 대응하는 인터랙션이다.
document.body.addEventListener("click", () => {
  window.location.href = "../../Select/Select_Photos/index.html";
});
