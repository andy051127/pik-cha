// DSLR 라이브뷰와 촬영 상태를 로컬 백엔드에서 받는다.
const API_BASE = "http://localhost:8000";
const WS_URL = "ws://localhost:8000/ws/liveview";
const preview = document.getElementById("camera-preview");
const cameraEl = document.createElement("img");
cameraEl.alt = "카메라 미리보기";
cameraEl.style.cssText = "width:100%;height:100%;object-fit:cover;display:block";
preview.appendChild(cameraEl);
const shotCountEl = document.getElementById("shot-count");
const timeLeftEl = document.getElementById("time-left");
let ws = null;
let reconnectTimer = null;
let finished = false;
let shootingStarted = false;

function connectWebSocket() {
    if (finished || (ws && [WebSocket.OPEN, WebSocket.CONNECTING].includes(ws.readyState))) return;
    ws = new WebSocket(WS_URL);
    ws.onopen = () => {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
        if (!shootingStarted) {
            shootingStarted = true;
            startShooting();
        }
    };
    ws.onmessage = (event) => {
        let data;
        try { data = JSON.parse(event.data); } catch (err) { return; }
        if (data.type === "frame") cameraEl.src = `data:image/jpeg;base64,${data.data}`;
        if (data.type === "countdown" || data.type === "capturing") {
            shotCountEl.textContent = `${data.shot}/8`;
            timeLeftEl.textContent = data.type === "capturing" ? "0" : data.seconds;
        }
        if (data.type === "sequence_complete") {
            finished = true;
            ws.close();
            location.href = "../06_review_photo/index.html";
        }
    };
    ws.onerror = () => console.error("라이브뷰 연결 오류");
    ws.onclose = () => {
        if (!finished && !reconnectTimer) {
            reconnectTimer = setTimeout(() => {
                reconnectTimer = null;
                connectWebSocket();
            }, 3000);
        }
    };
}

async function startShooting() {
    let ticketNumber = null;
    try {
        ticketNumber = JSON.parse(sessionStorage.getItem("pikcha_ticket_info") || "null")?.ticketNumber ?? null;
    } catch (err) {
        console.warn("순번 정보를 읽지 못했습니다:", err);
    }
    try {
        const res = await fetch(`${API_BASE}/api/four-cut/start`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ interval: 5, count: 8, aspect_w: 175.5, aspect_h: 241.8,
                ticket_number: ticketNumber }),
        });
        const result = await res.json();
        if (!res.ok || !result.success) console.error("촬영 시작 실패:", result);
    } catch (err) {
        console.error("촬영 시작 요청 실패:", err);
    }
}

connectWebSocket();
