// 촬영본 확인/선택 화면 로직 (★ 데모 전용 버전 - 백엔드 연결 시도 없이 항상 데모 사진 사용)
//
// 기존 버전과 차이: GET /api/images 호출 시도를 아예 제거하고, 항상
// generateDemoPhotoList()로 만든 8장의 색깔별 placeholder 사진을 사용한다.
//
// ★ 나중에 진짜 백엔드에 연결하려면, 이전에 드렸던 "서버 연동 버전"으로
//   파일을 다시 교체하면 된다 (필요하면 말씀해주세요, 다시 드릴게요).

const SVG_NS = "http://www.w3.org/2000/svg";
const MAX_SELECT = 4;
const TOTAL_OPTIONS = 8;

const OPTION_POSITIONS = [
  { x: 672, y: 161 },
  { x: 672, y: 306 },
  { x: 672, y: 451 },
  { x: 672, y: 596 },
  { x: 892, y: 161 },
  { x: 892, y: 306 },
  { x: 892, y: 451 },
  { x: 892, y: 596 },
];
const OPTION_W = 208;
const OPTION_H = 133;

const photoOptionsGroup = document.getElementById("photoOptions");
const frameSlots = [...document.querySelectorAll(".frame-slot")];
const nextBtn = document.getElementById("nextBtn");

// 데모용 사진 8장. 각 원소는 { id, mockSrc(dataURL) } 형태.
let photos = [];

// 선택한 순서를 기억하는 배열. 인덱스 0이 1번째로 고른 사진.
let selection = [];

function makeSvg(tag, attrs) {
  const el = document.createElementNS(SVG_NS, tag);
  Object.entries(attrs).forEach(([key, value]) => el.setAttribute(key, value));
  return el;
}

// 데모용 사진 8장을 캔버스로 즉석 생성
function generateDemoPhotoList() {
  const colors = ["#FF6E6E", "#FFAF76", "#FFF982", "#9BFF7D", "#7FB2FF", "#594DFF", "#CF75FF", "#FF7DD6"];
  return Array.from({ length: TOTAL_OPTIONS }, (_, i) => {
    const canvas = document.createElement("canvas");
    canvas.width = 320;
    canvas.height = 240;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = colors[i];
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#fff";
    ctx.font = "bold 56px sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(String(i + 1), canvas.width / 2, canvas.height / 2);
    return { id: `demo-${i + 1}`, mockSrc: canvas.toDataURL("image/png") };
  });
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
          preserveAspectRatio: "xMidYMid slice",
          href: photo.mockSrc,
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
      const p = photos[photoIndex];
      img.setAttribute("href", p.mockSrc);
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

  const chosenPhotos = selection.map((i) => ({ id: photos[i].id, mockSrc: photos[i].mockSrc }));
  try {
    sessionStorage.setItem("pikcha_selected_photos", JSON.stringify(chosenPhotos));
  } catch (err) {
    console.warn("선택한 사진을 저장하지 못했습니다:", err);
  }

  window.location.href = "../Select_Frame/index.html";
});

function init() {
  photos = generateDemoPhotoList();
  buildOptions();
  render();
}

init();
