// 촬영 화면 로직 (★ 캐논 DSLR 백엔드 연동 버전으로 재작성)
//
// ★ 바뀐 점 (기존 웹캠 버전 대비):
//   - navigator.mediaDevices.getUserMedia (브라우저 웹캠) 제거
//   - 대신 백엔드 웹소켓(/ws/liveview)에 연결해서 DSLR 라이브뷰 프레임을 받아 표시
//   - 로컬 setInterval 카운트다운 대신, POST /api/four-cut/start로 촬영을 시작시키고
//     웹소켓으로 오는 countdown/capturing/shot_saved/sequence_complete 메시지로
//     화면을 갱신 (실제 셔터 타이밍과 화면이 정확히 일치하게)
//   - 8컷/5초 (컷 수/간격은 백엔드가 요청값을 그대로 받아 처리하는 구조라
//     하드코딩 아님. 다만 /api/fourcut/create는 정확히 4장을 골라야 하므로,
//     Select 화면에서 촬영된 8장 중 4장을 선택하게 해야 함)
//   - 캔버스로 프레임 캡처해서 sessionStorage에 dataURL로 저장하던 방식 제거.
//     실제 촬영본은 서버(/api/images)에 이미 저장되어 있으므로, 여기서는
//     촬영 완료(sequence_complete) 시 Review_Photos 화면으로 넘기면 되고
//     거기서 서버로부터 사진 목록을 새로 받아오면 된다.

const API_BASE = "http://localhost:8000";
const WS_URL = "ws://localhost:8000/ws/liveview";

const cameraEl = document.getElementById("camera"); // ★ <video> 대신 <img>로 교체됨 (index.html 참고)
const countdownEl = document.getElementById("countdown");
const shotCurrentEl = document.getElementById("shotCurrent");
const shotTotalEl = document.getElementById("shotTotal");
const flashOverlay = document.getElementById("flashOverlay");

const TOTAL_SHOTS = 8;       // 8컷
const SECONDS_PER_SHOT = 5;  // 컷당 5초 간격

// ★ 저장본 크롭 비율.
//   review_photo(Review_Photos)의 프레임 슬롯과 동일한 세로 비율(175.5 : 241.8).
//   브라우저에서 캡처하지 않고 서버가 카메라 원본을 저장하므로, 이 비율을
//   start 요청에 실어 보내서 서버가 "중앙 크롭"으로 이 비율에 맞춰 저장하게 한다.
//   → 이렇게 저장된 사진은 review_photo 프레임 슬롯에 잘림/왜곡 없이 그대로 들어간다.
const CAPTURE_ASPECT_W = 175.5;
const CAPTURE_ASPECT_H = 241.8;

let ws = null;
let wsReconnectTimer = null;

shotTotalEl.textContent = TOTAL_SHOTS;

// ── 웹소켓: 라이브뷰 프레임 + 촬영 진행상황 수신 ──────────────────
function connectWebSocket() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    return; // 중복 연결 방지
  }

  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    console.log("WebSocket 연결됨");
    if (wsReconnectTimer) {
      clearTimeout(wsReconnectTimer);
      wsReconnectTimer = null;
    }
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    handleMessage(data);
  };

  // onerror는 재연결을 걸지 않는다 - 스펙상 onclose가 뒤이어 반드시 호출되므로
  // 재연결은 onclose 한 곳에서만 처리 (양쪽에서 다 걸면 연결이 기하급수적으로 늘어남)
  ws.onerror = () => {
    console.log("WebSocket 에러 발생 (onclose에서 재연결 처리)");
  };

  ws.onclose = () => {
    if (!wsReconnectTimer) {
      wsReconnectTimer = setTimeout(() => {
        wsReconnectTimer = null;
        connectWebSocket();
      }, 3000);
    }
  };
}

function handleMessage(data) {
  switch (data.type) {
    case "frame":
      // 백엔드가 base64 JPEG를 계속 보내주는 걸 <img>에 바로 표시
      cameraEl.src = "data:image/jpeg;base64," + data.data;
      break;

    case "countdown":
      shotCurrentEl.textContent = data.shot;
      countdownEl.textContent = data.seconds;
      break;

    case "capturing":
      // 카운트다운 끝나고 실제 셔터가 눌리는 순간 - 이 타이밍에 플래시
      shotCurrentEl.textContent = data.shot;
      countdownEl.textContent = "0";
      flash();
      break;

    case "shot_saved":
    case "shot_failed":
    case "retrying":
      // 특별히 화면에서 할 일 없음. 다음 컷 카운트다운(countdown 메시지)이
      // 자동으로 이어서 온다.
      break;

    case "sequence_complete":
      // 4컷(성공/실패 여부와 무관하게) 전부 끝났다는 신호. 이제 사진 선택
      // 화면으로 넘어간다. 실제 사진 데이터는 서버에 있으므로 그냥 이동만.
      finishSession();
      break;
  }
}

// 화면을 짧게 하얗게 번쩍이는 플래시 효과 (기존 그대로 유지)
function flash() {
  flashOverlay.classList.add("flash");
  requestAnimationFrame(() => {
    setTimeout(() => flashOverlay.classList.remove("flash"), 60);
  });
}

// ── 촬영 시작 (서버에 위임) ────────────────────────────────────
async function startShooting() {
  // ★ 순번 입력 화면(Personal_Info)이 저장해둔 ticket_number를 같이 보내서,
  //   촬영이 끝나면 백엔드가 웨이팅리스트의 다음 팀을 자동으로 호출하게 함
  let ticketNumber = null;
  try {
    const ticketInfoRaw = sessionStorage.getItem("pikcha_ticket_info");
    if (ticketInfoRaw) {
      ticketNumber = JSON.parse(ticketInfoRaw).ticketNumber ?? null;
    }
  } catch (e) {
    console.log("순번 정보(pikcha_ticket_info) 읽기 실패 - 순번 없이 진행:", e.message);
  }

  try {
    const res = await fetch(`${API_BASE}/api/four-cut/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        interval: SECONDS_PER_SHOT,
        count: TOTAL_SHOTS,
        // ★ 저장본을 review_photo 프레임 슬롯 비율(175.5 : 241.8)로 중앙 크롭 저장
        aspect_w: CAPTURE_ASPECT_W,
        aspect_h: CAPTURE_ASPECT_H,
        ticket_number: ticketNumber,
      }),
    });
    const result = await res.json();
    if (!result.success) {
      console.error("촬영 시작 실패:", result);
    }
  } catch (err) {
    console.error("촬영 시작 요청 실패 (백엔드 서버가 켜져 있는지 확인):", err);
  }
}

// 4컷 완료 -> 사진 선택 화면(Review_Photos)으로 이동
// (사진은 서버 /api/images에서 새로 받아옴)
function finishSession() {
  window.location.href = "../Review_Photos/index.html";
}

connectWebSocket();
startShooting();
