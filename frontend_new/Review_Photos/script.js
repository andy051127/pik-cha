// 촬영본 확인/선택 화면 로직 (★ 서버 연동 버전으로 수정).
//
// ★ 바뀐 점 (기존 버전 대비):
//   - sessionStorage("pikcha_photos")의 dataURL 배열 대신, 서버
//     GET /api/images 를 호출해서 실제 촬영된 사진 목록(id)을 받아온다.
//     화면에 표시할 때는 <image href="/api/images/{id}">로 서버에서 직접 불러온다.
//   - NEXT를 누르면 선택한 "사진 id"들을 sessionStorage("pikcha_selected_photos")에
//     저장하고 Select_Frame 화면으로 이동한다 (기존엔 TODO로 비어있던 부분).
//   - 그 외 선택/배지/보드 미리보기 로직은 원본 그대로 유지.

const API_BASE = "http://localhost:8000";
const SVG_NS = "http://www.w3.org/2000/svg";
const MAX_SELECT = 4;
const TOTAL_OPTIONS = 8;

// ★ 우측 썸네일 8칸 = 가로 4칸 x 세로 2칸 (4x2 그리드).
//   좌표는 새 디자인(Sub_사진 선택_pik-cha.svg)의 그리드 그대로.
//   각 칸은 프레임 슬롯과 동일한 세로 비율 175.5 : 241.8.
const OPTION_POSITIONS = [
  { x: 556, y: 233 },
  { x: 747, y: 233 },
  { x: 938, y: 233 },
  { x: 1129, y: 233 },
  { x: 556, y: 483 },
  { x: 747, y: 483 },
  { x: 938, y: 483 },
  { x: 1129, y: 483 },
];
const OPTION_W = 175.5;
const OPTION_H = 241.8;

const photoOptionsGroup = document.getElementById("photoOptions");
const frameSlots = [...document.querySelectorAll(".frame-slot")];
const nextBtn = document.getElementById("nextBtn");

// ★ 서버에서 받아온 사진 목록. 각 원소는 { id: "20260810_224535", ... } 형태.
let photos = [];

// 선택한 순서를 기억하는 배열. 인덱스 0이 1번째로 고른 사진(id 기준).
let selection = [];

function makeSvg(tag, attrs) {
  const el = document.createElementNS(SVG_NS, tag);
  Object.entries(attrs).forEach(([key, value]) => el.setAttribute(key, value));
  return el;
}

// ★ 서버에서 촬영본 목록을 불러온다
async function loadPhotos() {
  try {
    const res = await fetch(`${API_BASE}/api/images`);
    const data = await res.json();
    photos = data.images || [];
  } catch (err) {
    console.error("사진 목록 로드 실패:", err);
    photos = [];
  }

  // 8장이 안 채워졌을 때도 8칸 레이아웃은 볼 수 있게 빈 자리로 채움
  while (photos.length < TOTAL_OPTIONS) {
    photos.push(null);
  }
}

function buildOptions() {
  photoOptionsGroup.innerHTML = "";

  photos.slice(0, TOTAL_OPTIONS).forEach((photo, index) => {
    const pos = OPTION_POSITIONS[index];
    const g = makeSvg("g", { class: "photo-option", "data-index": index });

    g.appendChild(
      makeSvg("rect", {
        class: "option-bg",
        x: pos.x,
        y: pos.y,
        width: OPTION_W,
        height: OPTION_H,
      })
    );

    if (photo) {
      g.appendChild(
        makeSvg("image", {
          class: "option-img",
          x: pos.x,
          y: pos.y,
          width: OPTION_W,
          height: OPTION_H,
          // ★ 칸 비율(175.5 : 241.8)이 촬영본과 같으므로 slice로 꽉 채워도
          //   왜곡·잘림이 생기지 않는다.
          preserveAspectRatio: "xMidYMid slice",
          href: `${API_BASE}/api/images/${photo.id}`,
        })
      );
    } else {
      const text = makeSvg("text", {
        x: pos.x + OPTION_W / 2,
        y: pos.y + OPTION_H / 2,
        "text-anchor": "middle",
        "font-size": 14,
        fill: "#9a9a9a",
      });
      text.textContent = "사진 없음";
      g.appendChild(text);
    }

    g.appendChild(
      makeSvg("rect", {
        class: "option-stroke",
        x: pos.x,
        y: pos.y,
        width: OPTION_W,
        height: OPTION_H,
      })
    );

    const badge = makeSvg("g", { class: "option-badge" });
    badge.appendChild(makeSvg("circle", { cx: pos.x + 20, cy: pos.y + 20, r: 15, fill: "#ff4f81" }));
    const badgeText = makeSvg("text", {
      class: "badge-text",
      x: pos.x + 20,
      y: pos.y + 25,
      "text-anchor": "middle",
      "font-size": 16,
      "font-weight": 700,
      fill: "#fff",
    });
    badge.appendChild(badgeText);
    g.appendChild(badge);

    if (photo) {
      g.addEventListener("click", () => toggleSelect(index));
    }
    photoOptionsGroup.appendChild(g);
  });
}

function toggleSelect(index) {
  const existingPos = selection.indexOf(index);

  if (existingPos !== -1) {
    selection.splice(existingPos, 1);
  } else {
    if (selection.length >= MAX_SELECT) return;
    selection.push(index);
  }

  render();
}

function render() {
  photoOptionsGroup.querySelectorAll(".photo-option").forEach((el) => {
    const index = Number(el.dataset.index);
    const order = selection.indexOf(index);

    el.classList.toggle("selected", order !== -1);
    if (order !== -1) {
      el.querySelector(".badge-text").textContent = order + 1;
    }
  });

  frameSlots.forEach((slot, slotIndex) => {
    const photoIndex = selection[slotIndex];
    const img = slot.querySelector(".frame-img");

    if (photoIndex !== undefined && photos[photoIndex]) {
      img.setAttribute("href", `${API_BASE}/api/images/${photos[photoIndex].id}`);
      slot.classList.add("filled");
    } else {
      img.removeAttribute("href");
      slot.classList.remove("filled");
    }
  });

  const isComplete = selection.length === MAX_SELECT;
  nextBtn.classList.toggle("disabled", !isComplete);
}

// ★ 선택한 사진들의 id를 저장하고 Select_Frame으로 이동
nextBtn.addEventListener("click", () => {
  if (selection.length !== MAX_SELECT) return;

  const chosenPhotoIds = selection.map((i) => photos[i].id);
  try {
    sessionStorage.setItem("pikcha_selected_photos", JSON.stringify(chosenPhotoIds));
  } catch (err) {
    console.warn("선택한 사진을 저장하지 못했습니다:", err);
  }

  window.location.href = "../Select_Frame/index.html";
});

async function init() {
  await loadPhotos();
  buildOptions();
  render();
}

init();
