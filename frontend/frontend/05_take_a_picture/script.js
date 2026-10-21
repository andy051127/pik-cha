// DSLR 라이브뷰와 촬영 상태를 로컬 백엔드에서 받는다.
const API_BASE = "http://localhost:8000";
const WS_URL = "ws://localhost:8000/ws/liveview";
const preview = document.getElementById("camera-preview");
const cameraEl = document.createElement("img");
cameraEl.alt = "카메라 미리보기";
cameraEl.style.cssText = "width:100%;height:100%;object-fit:cover;display:block;transform:scaleX(-1)"; // 거울처럼 좌우반전 (촬영본도 백엔드에서 동일하게 반전)
preview.appendChild(cameraEl);
const shotCountEl = document.getElementById("shot-count");
const timeLeftEl = document.getElementById("time-left");
const savingOverlay = document.getElementById("saving-overlay");
const savingTitle = document.getElementById("saving-title");
const savingSubtitle = document.getElementById("saving-subtitle");
let savingStartedAt = 0;
let savingMode = null;
let savingHideTimer = null;
let savingSafetyTimer = null;
let ws = null;
let reconnectTimer = null;
let finished = false;
let shootingStarted = false;

function clearSavingTimers() {
    clearTimeout(savingHideTimer);
    clearTimeout(savingSafetyTimer);
    savingHideTimer = null;
    savingSafetyTimer = null;
}

function setOverlayVisible(visible) {
    savingOverlay.classList.toggle("is-visible", visible);
    savingOverlay.setAttribute("aria-hidden", String(!visible));
}

function showSaving(title = "찰칵! 사진 저장 중…") {
    if (savingMode === "error") return;
    clearSavingTimers();
    savingMode = "saving";
    savingStartedAt = Date.now();
    savingOverlay.classList.remove("is-error");
    savingTitle.textContent = title;
    savingSubtitle.textContent = "잠시만 기다려 주세요";
    setOverlayVisible(true);
    savingSafetyTimer = setTimeout(() => hideSaving(true), 12000);
}

function hideSaving(immediate = false) {
    if (savingMode !== "saving") return;
    clearTimeout(savingHideTimer);
    const remaining = immediate ? 0 : Math.max(0, 800 - (Date.now() - savingStartedAt));
    savingHideTimer = setTimeout(() => {
        clearSavingTimers();
        savingMode = null;
        setOverlayVisible(false);
    }, remaining);
}

function showCameraError() {
    clearSavingTimers();
    savingMode = "error";
    savingOverlay.classList.add("is-error");
    savingTitle.textContent = "카메라 연결 오류";
    savingSubtitle.textContent = "스태프를 불러주세요";
    setOverlayVisible(true);
}

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
        // ★ 라이브뷰 프레임은 이제 바이너리(JPEG 바이트)로 옴 - base64+JSON 오버헤드 제거.
        //   상태 메시지(countdown 등)는 여전히 text(JSON)로 와서 둘을 구분해서 처리한다.
        if (event.data instanceof Blob) {
            const url = URL.createObjectURL(event.data);
            if (cameraEl.dataset.objectUrl) URL.revokeObjectURL(cameraEl.dataset.objectUrl);
            cameraEl.src = url;
            cameraEl.dataset.objectUrl = url;
            return;
        }
        let data;
        try { data = JSON.parse(event.data); } catch (err) { return; }
        if (data.type === "capturing") showSaving();
        if (data.type === "retrying") {
            if (savingMode !== "saving") showSaving("다시 찍는 중…");
            else savingTitle.textContent = "다시 찍는 중…";
        }
        if (data.type === "shot_saved" || data.type === "shot_failed") hideSaving();
        if (data.type === "countdown") hideSaving(true);
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
        if (!res.ok || !result.success) {
            console.error("촬영 시작 실패:", result);
            if (!res.ok) showCameraError();
        }
    } catch (err) {
        console.error("촬영 시작 요청 실패:", err);
        showCameraError();
    }
}

connectWebSocket();
