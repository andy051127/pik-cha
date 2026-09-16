// 촬영 화면 로직 (★ 웹캠 연동 버전)
//
// navigator.mediaDevices.getUserMedia로 실제 웹캠 스트림을 받아 라이브뷰로 보여주고,
// 카운트다운이 끝날 때마다 현재 비디오 프레임을 캔버스에 그려 실제 사진으로 캡처한다.
// 캡처한 사진들은 sessionStorage("pikcha_captured_photos")에 저장한 뒤 다음 화면으로 이동한다.

const cameraEl = document.getElementById("camera");
const countdownEl = document.getElementById("countdown");
const shotCurrentEl = document.getElementById("shotCurrent");
const shotTotalEl = document.getElementById("shotTotal");
const flashOverlay = document.getElementById("flashOverlay");
const cameraWrap = document.querySelector(".camera-wrap");

const TOTAL_SHOTS = 8;
const SECONDS_PER_SHOT = 5;

// ★ 규격: review_photo 프레임 슬롯과 동일한 세로 비율 175.5 : 241.8 (720 x 992)
const CAPTURE_WIDTH = 720;
const CAPTURE_HEIGHT = 992;

shotTotalEl.textContent = TOTAL_SHOTS;

const captureCanvas = document.createElement("canvas");
captureCanvas.width = CAPTURE_WIDTH;
captureCanvas.height = CAPTURE_HEIGHT;
const captureCtx = captureCanvas.getContext("2d");

let mediaStream = null;
const capturedPhotos = [];

function flash() {
  flashOverlay.classList.add("flash");
  requestAnimationFrame(() => {
    setTimeout(() => flashOverlay.classList.remove("flash"), 60);
  });
}

// 라이브뷰의 현재 프레임을, 화면에 보이는 미리보기(좌우 반전 + object-fit: cover)와
// 같은 구도로 캔버스에 그려서 캡처한다.
function capturePhoto() {
  const vw = cameraEl.videoWidth;
  const vh = cameraEl.videoHeight;
  if (!vw || !vh) return null;

  const targetRatio = CAPTURE_WIDTH / CAPTURE_HEIGHT;
  const videoRatio = vw / vh;

  let sx, sy, sw, sh;
  if (videoRatio > targetRatio) {
    sh = vh;
    sw = vh * targetRatio;
    sx = (vw - sw) / 2;
    sy = 0;
  } else {
    sw = vw;
    sh = vw / targetRatio;
    sx = 0;
    sy = (vh - sh) / 2;
  }

  captureCtx.save();
  // 미리보기가 scaleX(-1)로 거울처럼 보이므로, 저장되는 사진도 같은 구도가 되도록 좌우 반전한다.
  captureCtx.translate(CAPTURE_WIDTH, 0);
  captureCtx.scale(-1, 1);
  captureCtx.drawImage(cameraEl, sx, sy, sw, sh, 0, 0, CAPTURE_WIDTH, CAPTURE_HEIGHT);
  captureCtx.restore();

  return captureCanvas.toDataURL("image/jpeg", 0.92);
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

      const photo = capturePhoto();
      if (photo) {
        capturedPhotos[shot - 1] = { id: `shot-${shot}`, mockSrc: photo };
      }

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

function stopCamera() {
  if (mediaStream) {
    mediaStream.getTracks().forEach((track) => track.stop());
    mediaStream = null;
  }
}

function finishSession() {
  try {
    sessionStorage.setItem("pikcha_captured_photos", JSON.stringify(capturedPhotos));
  } catch (err) {
    console.warn("촬영한 사진을 저장하지 못했습니다:", err);
  }
  stopCamera();
  window.location.href = "../Review_Photos1_copy/index.html";
}

function showCameraError(err) {
  console.error("웹캠을 열 수 없습니다:", err);
  countdownEl.textContent = "-";

  const msg = document.createElement("div");
  msg.className = "camera-error";
  msg.textContent = "웹캠을 사용할 수 없습니다. 카메라 연결과 브라우저 권한을 확인해주세요.";
  cameraWrap.appendChild(msg);
}

async function startCamera() {
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 1760 }, facingMode: "user" },
      audio: false,
    });
    cameraEl.srcObject = mediaStream;
    await cameraEl.play();
    runShot(1);
  } catch (err) {
    showCameraError(err);
  }
}

window.addEventListener("beforeunload", stopCamera);

// 시작
startCamera();
