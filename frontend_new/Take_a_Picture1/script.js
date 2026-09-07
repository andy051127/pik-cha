// 촬영 화면 로직 (★ 데모 전용 버전 - 백엔드 연결 시도 없이 항상 데모로 동작)
//
// 기존 버전과 차이: 웹소켓 연결/재시도/타임아웃 로직을 전부 제거하고,
// 라이브뷰 자리에는 항상 데모 이미지를, 카운트다운은 항상 로컬 타이머로
// 진행한다. 백엔드가 켜져 있어도 무시하고 데모로만 동작한다.
//
// ★ 나중에 진짜 백엔드(캐논 카메라)에 연결하려면, 이전에 드렸던
//   "웹소켓 연동 버전"으로 파일을 다시 교체하면 된다 (필요하면 말씀해주세요,
//   다시 드릴게요).

const cameraEl = document.getElementById("camera");
const countdownEl = document.getElementById("countdown");
const shotCurrentEl = document.getElementById("shotCurrent");
const shotTotalEl = document.getElementById("shotTotal");
const flashOverlay = document.getElementById("flashOverlay");

const TOTAL_SHOTS = 8;
const SECONDS_PER_SHOT = 5;

shotTotalEl.textContent = TOTAL_SHOTS;

// 데모용 라이브뷰 placeholder 이미지 (캔버스로 즉석 생성)
// ★ 규격: review_photo 프레임 슬롯과 동일한 세로 비율 175.5 : 241.8 (720 x 992)
function generateDemoImage(label) {
  const canvas = document.createElement("canvas");
  canvas.width = 720;
  canvas.height = 992;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#333333";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#ffffff";
  ctx.font = "bold 40px sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(label, canvas.width / 2, canvas.height / 2);
  return canvas.toDataURL("image/png");
}

function flash() {
  flashOverlay.classList.add("flash");
  requestAnimationFrame(() => {
    setTimeout(() => flashOverlay.classList.remove("flash"), 60);
  });
}

function runShot(shot) {
  shotCurrentEl.textContent = shot;
  let seconds = SECONDS_PER_SHOT;
  countdownEl.textContent = seconds;

  const timer = setInterval(() => {
    seconds -= 1;

    if (seconds <= 0) {
      clearInterval(timer);
      countdownEl.textContent = "0";
      flash();

      setTimeout(() => {
        if (shot >= TOTAL_SHOTS) {
          finishSession();
        } else {
          runShot(shot + 1);
        }
      }, 500);
      return;
    }

    countdownEl.textContent = seconds;
  }, 1000);
}

function finishSession() {
  window.location.href = "../Review_Photos1/index.html";
}

// 시작
cameraEl.src = generateDemoImage("DEMO");
runShot(1);
