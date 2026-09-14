// 인쇄 대기 + QR 표시 화면 로직.
//
// 하는 일:
//   1) Select_Frame이 sessionStorage("pikcha_result")에 저장해둔 생성 결과
//      (POST /api/fourcut/create의 응답)를 읽어서 QR 이미지를 표시한다.
//   2) 30초 카운트다운을 하고, 0이 되면 자동으로 Main으로 돌아가
//      다음 손님을 위해 화면을 초기화한다.
//
// ★ 인쇄 자체(PrintWorker)는 이 화면과 무관하게 이미 자동으로 진행 중이다
//   (S3에 사진이 업로드되는 순간 백엔드가 자동으로 인쇄 대기열에 등록함).
//   이 화면은 그냥 "인쇄되는 동안 QR을 보여주는" 역할만 한다.

const COUNTDOWN_SECONDS = 30;

const qrImageEl = document.getElementById("qrImage");
const countEl = document.getElementById("count");

function loadResult() {
  try {
    const result = JSON.parse(sessionStorage.getItem("pikcha_result") || "null");
    // ★ Select_Frame이 저장하는 실제 형태는 { mock, qrSrc } 이고,
    //   qrSrc에는 이미 완성된 data URI(또는 외부 QR 이미지 URL)가 들어있음.
    const qrSrc = result && result.qrSrc;

    if (qrSrc) {
      qrImageEl.src = qrSrc;
    } else {
      // QR이 없는 경우(S3 미설정 등) - 화면이 비어보이지 않게 최소한의 안내
      qrImageEl.alt = "QR을 표시할 수 없습니다";
    }
  } catch (err) {
    console.error("결과 데이터를 읽지 못했습니다:", err);
  }
}

function startCountdown() {
  let remaining = COUNTDOWN_SECONDS;
  countEl.textContent = remaining;

  const timer = setInterval(() => {
    remaining -= 1;

    if (remaining <= 0) {
      clearInterval(timer);
      resetToMain();
      return;
    }

    countEl.textContent = remaining;
  }, 1000);
}

// 다음 손님을 위해 세션 데이터를 정리하고 처음 화면으로 돌아간다.
function resetToMain() {
  sessionStorage.removeItem("pikcha_result");
  sessionStorage.removeItem("pikcha_selected_photos");
  sessionStorage.removeItem("pikcha_personal_info");
  sessionStorage.removeItem("pikcha_ticket_info");
  sessionStorage.removeItem("pikcha_print_quantity");

  window.location.href = "../Main/index.html";
}

loadResult();
startCountdown();
