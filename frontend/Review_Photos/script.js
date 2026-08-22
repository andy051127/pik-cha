// 촬영본 확인/선택 화면 로직:
// - Take_a_Picture가 sessionStorage에 저장한 촬영본 8장을 오른쪽 그리드에 그린다.
// - 사진을 클릭한 순서대로 selection 배열에 쌓이고, 그 순서대로 왼쪽 보드 4칸이 채워진다.
// - 이미 선택한 사진을 다시 클릭하면 선택이 취소되고 뒤 순서들이 앞으로 당겨진다.
// - 정확히 4장을 골라야 NEXT를 누를 수 있다.

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

// Take_a_Picture 화면이 저장해 둔 촬영본(dataURL 배열)을 불러온다.
let photos = [];
try {
  photos = JSON.parse(sessionStorage.getItem("pikcha_photos") || "[]");
} catch (err) {
  photos = [];
}
// 촬영본이 없을 때(예: 이 페이지로 바로 진입)도 8칸 레이아웃을 볼 수 있도록
// null로 채운 빈 자리표시자 8개를 대신 사용한다.
if (photos.length === 0) {
  photos = new Array(TOTAL_OPTIONS).fill(null);
}

// 선택한 순서를 기억하는 배열. 인덱스 0이 1번째로 고른 사진.
let selection = [];

// SVG 네임스페이스로 태그를 만들고 속성을 한 번에 설정하는 헬퍼
// (HTML의 document.createElement로는 SVG 요소를 만들 수 없어서 별도 함수가 필요하다)
function makeSvg(tag, attrs) {
  const el = document.createElementNS(SVG_NS, tag);
  Object.entries(attrs).forEach(([key, value]) => el.setAttribute(key, value));
  return el;
}

// 오른쪽 8칸(사진/배경사각형/선택테두리/순서배지)을 SVG로 동적 생성한다.
// 사진이 없는 칸은 "사진 없음" 텍스트로 대체한다.
function buildOptions() {
  photoOptionsGroup.innerHTML = "";

  photos.slice(0, TOTAL_OPTIONS).forEach((dataUrl, index) => {
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

    if (dataUrl) {
      g.appendChild(
        makeSvg("image", {
          class: "option-img",
          x: pos.x,
          y: pos.y,
          width: OPTION_W,
          height: OPTION_H,
          preserveAspectRatio: "xMidYMid slice",
          href: dataUrl,
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

    g.addEventListener("click", () => toggleSelect(index));
    photoOptionsGroup.appendChild(g);
  });
}

// 사진 하나(index)를 선택/선택취소한다.
// 이미 골랐던 사진이면 배열에서 빼서 취소하고, 아니면 맨 뒤에 추가한다(4장까지만).
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

// selection 배열을 화면에 반영한다: 오른쪽 그리드의 선택 표시/순서 배지,
// 왼쪽 보드 4칸의 사진 채우기, NEXT 버튼 활성화 여부를 모두 다시 계산한다.
function render() {
  // 오른쪽 옵션: 선택 여부 + 몇 번째로 골랐는지 배지 갱신
  photoOptionsGroup.querySelectorAll(".photo-option").forEach((el) => {
    const index = Number(el.dataset.index);
    const order = selection.indexOf(index);

    el.classList.toggle("selected", order !== -1);
    if (order !== -1) {
      el.querySelector(".badge-text").textContent = order + 1;
    }
  });

  // 왼쪽 보드 4칸: 선택한 순서대로 채움
  frameSlots.forEach((slot, slotIndex) => {
    const photoIndex = selection[slotIndex];
    const img = slot.querySelector(".frame-img");

    if (photoIndex !== undefined && photos[photoIndex]) {
      img.setAttribute("href", photos[photoIndex]);
      slot.classList.add("filled");
    } else {
      img.removeAttribute("href");
      slot.classList.remove("filled");
    }
  });

  const isComplete = selection.length === MAX_SELECT;
  nextBtn.classList.toggle("disabled", !isComplete);
}

// 4장이 모두 선택된 상태에서 NEXT를 누르면, 선택한 사진들을 저장한다.
nextBtn.addEventListener("click", () => {
  if (selection.length !== MAX_SELECT) return;

  const chosenPhotos = selection.map((i) => photos[i]);
  try {
    sessionStorage.setItem("pikcha_selected_photos", JSON.stringify(chosenPhotos));
  } catch (err) {
    console.warn("선택한 사진을 저장하지 못했습니다:", err);
  }

  // TODO: 다음 화면 경로가 정해지면 여기에 연결
  console.log("선택한 사진(선택 순서):", chosenPhotos.length);
});

buildOptions(); // 오른쪽 8칸을 실제 사진으로 채운다
render(); // 초기 상태(선택 0장)에 맞춰 화면을 한 번 정리한다
