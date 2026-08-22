// 개인정보 입력 화면 로직:
// 1) 전화번호 입력 중 자동으로 010-XXXX-XXXX 형태의 하이픈을 붙여준다.
// 2) 이름이 1자 이상이고 전화번호 형식이 완성되어야 NEXT를 누를 수 있다.

const nameInput = document.getElementById("nameInput");
const phoneInput = document.getElementById("phoneInput");
const backBtn = document.getElementById("backBtn");
const nextBtn = document.getElementById("nextBtn");

// 완성된 전화번호 형식(010-XXXX-XXXX)인지 검사하는 정규식
const PHONE_PATTERN = /^010-\d{4}-\d{4}$/;

// 입력값에서 숫자만 추출해 010-XXXX-XXXX 형태로 하이픈을 끼워 넣는다.
function formatPhone(value) {
  const digits = value.replace(/\D/g, "").slice(0, 11);
  if (digits.length <= 3) return digits;
  if (digits.length <= 7) return `${digits.slice(0, 3)}-${digits.slice(3)}`;
  return `${digits.slice(0, 3)}-${digits.slice(3, 7)}-${digits.slice(7)}`;
}

// 이름/전화번호가 둘 다 유효한지 확인해서 NEXT 버튼 활성화 여부를 갱신한다.
function validate() {
  const nameOk = nameInput.value.trim().length > 0;
  const phoneOk = PHONE_PATTERN.test(phoneInput.value);
  nextBtn.disabled = !(nameOk && phoneOk);
}

// 전화번호 입력할 때마다 하이픈을 자동으로 다시 맞추고 유효성을 재검사
phoneInput.addEventListener("input", () => {
  phoneInput.value = formatPhone(phoneInput.value);
  validate();
});

// 이름 입력할 때마다 유효성을 재검사
nameInput.addEventListener("input", validate);

// 이전 화면(인화 수량 선택)으로 이동
backBtn.addEventListener("click", () => {
  window.location.href = "../Number_of_Prints/index.html";
});

// 다음 화면(촬영 카운트다운)으로 이동. disabled 상태면 아무 동작도 하지 않는다.
nextBtn.addEventListener("click", () => {
  if (nextBtn.disabled) return;
  window.location.href = "../CountDown/index.html";
});

validate(); // 페이지가 막 열렸을 때(입력값 없음)의 초기 상태를 맞춘다.
