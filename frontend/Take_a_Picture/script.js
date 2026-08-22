// 촬영 화면 로직:
// 1) 웹캠을 켜고 10초 카운트다운을 반복한다(총 8회).
// 2) 매 회 카운트다운이 끝나면 현재 프레임을 캡처하고 플래시 효과를 준다.
// 3) 8회 촬영이 모두 끝나면 캡처된 사진들을 sessionStorage에 저장하고
//    Review_Photos 화면으로 자동 이동한다.

const cameraEl = document.getElementById("camera");
const countdownEl = document.getElementById("countdown");
const shotCurrentEl = document.getElementById("shotCurrent");
const flashOverlay = document.getElementById("flashOverlay");
const captureCanvas = document.getElementById("captureCanvas");

const TOTAL_SHOTS = 8;
const SECONDS_PER_SHOT = 10;

let shotIndex = 1; // 현재 몇 번째 촬영인지(1~8)
let remaining = SECONDS_PER_SHOT; // 이번 촬영까지 남은 초
let timer = null;
let mediaStream = null; // 웹캠 스트림. 카메라를 못 켜면 null로 유지된다.
const capturedPhotos = []; // 촬영된 사진들의 dataURL 목록

// 웹캠 접근 권한을 요청하고 <video>에 실시간 스트림을 연결한다.
// 카메라를 사용할 수 없어도(권한 거부, file:// 등) 예외만 잡고 카운트다운은 계속 진행한다.
async function startCamera() {
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ video: true });
    cameraEl.srcObject = mediaStream;
  } catch (err) {
    console.warn("카메라를 사용할 수 없습니다:", err);
  }
}

// 현재 비디오 프레임을 캔버스에 그려서 이미지(dataURL)로 저장한다.
// 좌우 반전(거울 모드)된 미리보기와 동일하게 보이도록 캔버스도 좌우 반전해서 그린다.
function capturePhoto() {
  if (!mediaStream || !cameraEl.videoWidth) return;

  captureCanvas.width = cameraEl.videoWidth;
  captureCanvas.height = cameraEl.videoHeight;
  const ctx = captureCanvas.getContext("2d");
  ctx.translate(captureCanvas.width, 0);
  ctx.scale(-1, 1);
  ctx.drawImage(cameraEl, 0, 0, captureCanvas.width, captureCanvas.height);
  capturedPhotos.push(captureCanvas.toDataURL("image/png"));
}

// 화면을 짧게 하얗게 번쩍이는 플래시 효과
function flash() {
  flashOverlay.classList.add("flash");
  requestAnimationFrame(() => {
    setTimeout(() => flashOverlay.classList.remove("flash"), 60);
  });
}

// 10초 카운트다운을 시작한다. 1초마다 숫자를 줄이고, 0이 되면 이번 촬영을 마무리한다.
function startCountdown() {
  remaining = SECONDS_PER_SHOT;
  countdownEl.textContent = remaining;

  timer = setInterval(() => {
    remaining -= 1;

    if (remaining >= 1) {
      countdownEl.textContent = remaining;
      return;
    }

    clearInterval(timer);
    onShotComplete();
  }, 1000);
}

// 한 번의 촬영(10초)이 끝났을 때 호출된다.
// 사진을 캡처하고 플래시를 터뜨린 뒤, 마지막 촬영이면 세션을 종료하고
// 아니면 다음 촬영 번호로 넘어가 카운트다운을 다시 시작한다.
function onShotComplete() {
  capturePhoto();
  flash();

  if (shotIndex >= TOTAL_SHOTS) {
    finishSession();
    return;
  }

  shotIndex += 1;
  shotCurrentEl.textContent = shotIndex;
  startCountdown();
}

// 8회 촬영이 모두 끝났을 때: 카메라를 끄고, 촬영본을 저장한 뒤 다음 화면으로 이동한다.
function finishSession() {
  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop());
  }

  try {
    // Review_Photos 화면이 같은 키로 읽어서 촬영본 목록을 보여준다.
    sessionStorage.setItem("pikcha_photos", JSON.stringify(capturedPhotos));
  } catch (err) {
    console.warn("촬영한 사진을 저장하지 못했습니다:", err);
  }

  window.location.href = "../Review_Photos/index.html";
}

startCamera();
startCountdown();
