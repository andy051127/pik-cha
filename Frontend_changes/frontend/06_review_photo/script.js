// 서버 촬영본 8장 중 선택 순서대로 4장을 저장한다.
const API_BASE = "http://localhost:8000";
const MAX_SELECT = 4;
const thumbs = [...document.querySelectorAll("[data-photo]")];
const slots = [...document.querySelectorAll("[data-slot]")];
const nextBtn = document.getElementById("nav-next");
let photos = [];
let selection = [];

function render() {
    thumbs.forEach((thumb, index) => {
        const photo = photos[index];
        thumb.style.backgroundImage = photo ? `url("${API_BASE}/api/images/${encodeURIComponent(photo.id)}")` : "";
        thumb.style.backgroundSize = "cover";
        thumb.style.backgroundPosition = "center";
        thumb.classList.toggle("is-selected", selection.includes(index));
        thumb.setAttribute("aria-label", photo ? `사진 ${index + 1}${selection.includes(index) ? `, 선택 순서 ${selection.indexOf(index) + 1}` : ""}` : "사진 없음");
    });
    slots.forEach((slot, index) => {
        const photo = photos[selection[index]];
        slot.style.backgroundImage = photo ? `url("${API_BASE}/api/images/${encodeURIComponent(photo.id)}")` : "";
        slot.style.backgroundSize = "cover";
        slot.style.backgroundPosition = "center";
    });
    nextBtn.classList.toggle("disabled", selection.length !== MAX_SELECT);
    nextBtn.setAttribute("aria-disabled", String(selection.length !== MAX_SELECT));
}

thumbs.forEach((thumb, index) => {
    thumb.addEventListener("click", (event) => {
        event.preventDefault();
        if (!photos[index]) return;
        const position = selection.indexOf(index);
        if (position >= 0) selection.splice(position, 1);
        else if (selection.length < MAX_SELECT) selection.push(index);
        render();
    });
});

nextBtn.addEventListener("click", (event) => {
    event.preventDefault();
    if (selection.length !== MAX_SELECT) return;
    sessionStorage.setItem("pikcha_selected_photos", JSON.stringify(selection.map((index) => photos[index].id)));
    location.href = "../07_select_frame/index.html";
});

async function loadPhotos() {
    try {
        const res = await fetch(`${API_BASE}/api/images`);
        const data = await res.json();
        if (!res.ok) throw new Error("사진 목록을 불러오지 못했습니다.");
        photos = data.images || [];
    } catch (err) {
        console.error("사진 목록 로드 실패:", err);
        photos = [];
    }
    if (photos.length < 4) console.warn("선택할 사진이 4장보다 적습니다.");
    render();
}

render();
loadPhotos();
