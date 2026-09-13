// Select_Frame 화면 로직 (★ v5 - Special Frame에 할로윈/헬로키티 추가, mint_black_star 삭제)
//
// ★ 이번 업데이트: 팀원이 준 실제 아이콘/색상 파일들을 반영.
//   - Logo 3종 (기존 2종 -> 3종으로 늘어남)
//   - Photo Color 2종 (컬러/흑백) - 실제 아이콘 이미지 사용
//   - Special Frame 6종 (mint_black_star 삭제, halloween/hello 추가) -
//     실제 패턴 이미지를 border 영역에 그대로 그림. halloween/hello는
//     완성본이 PNG가 아니라 SVG(패턴 fill + 구멍 4개짜리 path)로 왔는데,
//     다른 항목들과 똑같이 <img src="....svg">로 로드해서 Canvas에
//     drawImage하면 되므로 로직 변경 없이 그대로 섞어 쓸 수 있다.
//   - Frame 색상 5종 - 실제 파일에서 뽑아낸 정확한 색상값 사용,
//     그중 green(신구대)은 로고가 이미 박혀있는 특수 케이스라 별도 처리
//
// 사진 슬롯 좌표(2x2 격자, 실측 비율)는 이전 버전과 동일하게 유지.
// 프레임 오버레이(테두리+로고+패턴)를 실제 이미지 기반으로 합성하는 부분만
// 대폭 교체됨.

const API_BASE = "http://localhost:8000";
const CANVAS_W = 550;
const CANVAS_H = 803;

// 실측 좌표를 비율(0~1)로 환산한 사진 슬롯 (2x2 격자, 원본 1100x1605 PNG 기준)
const PHOTO_SLOTS = [
  { xf: 0.0727, yf: 0.1508, wf: 0.4082, hf: 0.3856 }, // 좌상단
  { xf: 0.5182, yf: 0.1508, wf: 0.4082, hf: 0.3856 }, // 우상단
  { xf: 0.0727, yf: 0.5495, wf: 0.4082, hf: 0.3857 }, // 좌하단
  { xf: 0.5182, yf: 0.5495, wf: 0.4082, hf: 0.3857 }, // 우하단
];

// 프레임 구조 비율값 (border/divider/band) - placeholder 오버레이 그릴 때 사용
const BORDER_F = 0.0727;      // 좌우 테두리 폭
const DIVIDER_F = 0.0400;     // 가운데 세로 구분선 폭
const TOP_BAND_F = 0.1508;    // 상단 밴드(로고) 높이
const MID_DIVIDER_F = 0.0125; // 가로 구분선 높이
const BOTTOM_BAND_START_F = 0.9352; // 하단 밴드 시작 지점

// ── 자산 정의 (실제 파일 경로) ────────────────────────────────────
const ASSET_LOGOS = [
  { id: "logo1", src: "assets/logos/logo1.png", label: "로고1" },
  { id: "logo2", src: "assets/logos/logo2.png", label: "로고2" },
  { id: "logo3", src: "assets/logos/logo3.png", label: "로고3" },
];

const PHOTO_COLOR_MODES = [
  { id: "color", src: "assets/photo_color/color.png", label: "컬러" },
  { id: "bw", src: "assets/photo_color/bw.png", label: "흑백" },
];

const ASSET_SPECIAL_FRAMES = [
  { id: "navy_star", src: "assets/special_frames/navy_star.png" },
  { id: "marble", src: "assets/special_frames/marble.png" },
  { id: "mint_white_star", src: "assets/special_frames/mint_white_star.png" },
  { id: "black_white_star", src: "assets/special_frames/black_white_star.png" },
  { id: "halloween", src: "assets/special_frames/halloween.svg" },
  { id: "hello", src: "assets/special_frames/hello.svg" },
];

// color: 실제 파일에서 추출한 평균 색상값. green은 로고가 중앙에 박혀있는
// 특수 케이스라 hasEmbeddedLogo로 표시해두고 별도 처리한다.
const ASSET_FRAME_COLORS = [
  { id: "white", src: "assets/frames/white.png", color: "#fefefe", outline: true },
  { id: "black", src: "assets/frames/black.png", color: "#000000" },
  { id: "blue", src: "assets/frames/blue.png", color: "#2983c8" },
  { id: "pink", src: "assets/frames/pink.png", color: "#eaa9a9" },
  { id: "green", src: "assets/frames/green.png", color: "#a9d36c", hasEmbeddedLogo: true },
];

// "흰색 프레임 + 로고1 + 특별프레임 없음" 조합은 팀원이 완성본으로 준 실제
// 합성 이미지를 그대로 사용 (제일 정확함). 그 외 조합은 아래에서 실시간으로
// 레이어를 겹쳐서 합성한다.
// ★ Frame 5색상 × 로고 3종(15개) + Special Frame 6종 × 로고 3종(18개) +
//   신구대(1개) = 총 34개 조합이 이제 전부 실제 완성본으로 커버됨.
//   실시간 레이어 합성(drawComposedOverlay)은 혹시 이미지 로드가 실패할
//   때만 쓰이는 최후 폴백으로 남겨둠.
const REAL_FULL_OVERLAY = {
  "white_logo1_none": "assets/frames_full/white_logo1.png",
  "white_logo2_none": "assets/frames_full/white_logo2.png",
  "white_logo3_none": "assets/frames_full/white_logo3.png",

  "black_logo1_none": "assets/frames_full/black_logo1.png",
  "black_logo2_none": "assets/frames_full/black_logo2.png",
  "black_logo3_none": "assets/frames_full/black_logo3.png",

  "blue_logo1_none": "assets/frames_full/blue_logo1.png",
  "blue_logo2_none": "assets/frames_full/blue_logo2.png",
  "blue_logo3_none": "assets/frames_full/blue_logo3.png",

  "pink_logo1_none": "assets/frames_full/pink_logo1.png",
  "pink_logo2_none": "assets/frames_full/pink_logo2.png",
  "pink_logo3_none": "assets/frames_full/pink_logo3.png",

  "white_logo1_mint_white_star": "assets/frames_full/mint_white_star_logo1.png",
  "white_logo2_mint_white_star": "assets/frames_full/mint_white_star_logo2.png",
  "white_logo3_mint_white_star": "assets/frames_full/mint_white_star_logo3.png",

  "white_logo1_navy_star": "assets/frames_full/navy_star_logo1.png",
  "white_logo2_navy_star": "assets/frames_full/navy_star_logo2.png",
  "white_logo3_navy_star": "assets/frames_full/navy_star_logo3.png",

  "white_logo1_marble": "assets/frames_full/marble_logo1.png",
  "white_logo2_marble": "assets/frames_full/marble_logo2.png",
  "white_logo3_marble": "assets/frames_full/marble_logo3.png",

  "white_logo1_black_white_star": "assets/frames_full/black_white_star_logo1.png",
  "white_logo2_black_white_star": "assets/frames_full/black_white_star_logo2.png",
  "white_logo3_black_white_star": "assets/frames_full/black_white_star_logo3.png",

  "white_logo1_halloween": "assets/frames_full/halloween_logo1.svg",
  "white_logo2_halloween": "assets/frames_full/halloween_logo2.svg",
  "white_logo3_halloween": "assets/frames_full/halloween_logo3.svg",

  "white_logo1_hello": "assets/frames_full/hello_logo1.svg",
  "white_logo2_hello": "assets/frames_full/hello_logo2.svg",
  "white_logo3_hello": "assets/frames_full/hello_logo3.svg",
};

// ★ 특별프레임을 선택했을 때, 실제 완성본이 위 REAL_FULL_OVERLAY 키에서
//   frameColorId를 "white"로 가정하고 등록되어 있어서(특별프레임 선택 시
//   실제로는 프레임색이 안 보이니 white로 통일해둠), currentOverlayKey()도
//   특별프레임이 선택된 경우엔 frameColorId를 무시하고 "white"로 맞춰 조회한다.

// ── 상태 ─────────────────────────────────────────────────────────
let selectedPhotos = [];
let state = {
  logoId: ASSET_LOGOS[0].id,
  photoColorId: PHOTO_COLOR_MODES[0].id,
  specialFrameId: null,
  frameColorId: ASSET_FRAME_COLORS[0].id,
};

const canvas = document.getElementById("previewCanvas");
canvas.width = CANVAS_W;
canvas.height = CANVAS_H;
const ctx = canvas.getContext("2d");
const nextBtn = document.getElementById("nextBtn");
const loadingOverlay = document.getElementById("loadingOverlay");

function loadSelectionFromSession() {
  try {
    const raw = JSON.parse(sessionStorage.getItem("pikcha_selected_photos") || "[]");
    // ★ Review_Photos는 사진 id를 순수 문자열 배열로 저장함
    //   (예: ["20260810_224535", ...]). 여기서는 {id, mockSrc} 객체 형태를
    //   기대하고 있었으므로, 문자열이면 객체로 정규화해준다.
    selectedPhotos = raw.map((item) =>
      typeof item === "string" ? { id: item, mockSrc: null } : item
    );
  } catch (err) {
    selectedPhotos = [];
  }
  if (selectedPhotos.length !== 4) {
    console.warn("선택된 사진이 4장이 아닙니다 - Review_Photos 화면을 거치지 않고 바로 온 것 같습니다.");
  }
}

// ── 실제 아이콘 이미지로 스와치 렌더링 ─────────────────────────────
function renderSwatches() {
  renderRow("logoRow", ASSET_LOGOS, state.logoId, (item) => {
    state.logoId = item.id;

    // ★ 신구대(green) 상태에서 로고를 새로 고르면, 로고 선택이 반영되는
    //   일반 프레임으로 돌아가야 함 (신구대는 로고 선택과 무관한 완성본이라
    //   로고를 눌러도 그대로 있으면 "신구대 + 로고 동시 선택"처럼 보여서 혼란스러움)
    if (state.frameColorId === "green") {
      state.frameColorId = ASSET_FRAME_COLORS[0].id; // 기본값(흰색)으로 복귀
    }

    renderSwatches();
    renderPreview();
  });

  renderRow("photoColorRow", PHOTO_COLOR_MODES, state.photoColorId, (item) => {
    state.photoColorId = item.id;
    renderSwatches();
    renderPreview();
  });

  // ★ Special Frame과 Frame(색상)은 상호 배타적이라, Special Frame이 선택된
  //   상태에서는 Frame 쪽 화면 표시를 꺼야 해서 selectedId를 조건부로 넘김
  renderRow("specialFrameRow", ASSET_SPECIAL_FRAMES, state.specialFrameId, (item) => {
    const isDeselecting = state.specialFrameId === item.id;
    state.specialFrameId = isDeselecting ? null : item.id;

    if (!isDeselecting) {
      // 특별 프레임을 새로 선택 -> 일반 Frame 선택 표시는 해제(상호 배타)
      // 로고가 비어있었으면(신구대 때문에) 기본값 1번으로 복귀
      if (!state.logoId) state.logoId = ASSET_LOGOS[0].id;
    }
    renderSwatches();
    renderPreview();
  });

  // ★ Special Frame이 선택되어 있으면 Frame 쪽은 아무것도 선택 안 된 것처럼 표시
  const frameSelectedId = state.specialFrameId ? null : state.frameColorId;
  renderRow("frameColorRow", ASSET_FRAME_COLORS, frameSelectedId, (item) => {
    state.frameColorId = item.id;
    state.specialFrameId = null; // Frame 선택 -> 특별 프레임 선택 해제(상호 배타)

    if (item.id === "green") {
      // ★ 신구대: 로고/특별프레임 선택 다 취소 (신구대 완성본은 로고 선택과 무관하게 항상 고정)
      state.logoId = null;
    } else if (!state.logoId) {
      // ★ 신구대에서 다른 프레임으로 돌아옴 -> 로고 기본값(1번)으로 복귀
      state.logoId = ASSET_LOGOS[0].id;
    }

    renderSwatches();
    renderPreview();
  });

  updateNextButtonState();
}

function renderRow(containerId, items, selectedId, onClick) {
  const container = document.getElementById(containerId);
  container.innerHTML = "";

  items.forEach((item) => {
    const el = document.createElement("div");
    el.className = "swatch" + (item.id === selectedId ? " selected" : "");
    if (item.outline) el.classList.add("outline");
    const img = document.createElement("img");
    img.src = item.src;
    img.alt = item.label || item.id;
    el.appendChild(img);
    el.addEventListener("click", () => onClick(item));
    container.appendChild(el);
  });
}

// ── 이미지 로드 캐시 ─────────────────────────────────────────────
const imageCache = {};
function loadImage(src) {
  if (imageCache[src]) return imageCache[src];
  const p = new Promise((resolve, reject) => {
    const img = new Image();
    // ★ 로컬 asset 파일(상대경로)이나 mockSrc(data URI)에 crossOrigin을
    //   설정하면 file:// 환경에서 로딩 자체가 실패하는 경우가 있음.
    //   실제 서버(http)에서 오는 이미지일 때만 필요한 설정이라 그때만 켠다.
    if (/^https?:\/\//i.test(src)) {
      img.crossOrigin = "anonymous";
    }
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
  imageCache[src] = p;
  return p;
}

function currentOverlayKey() {
  // 특별프레임을 선택하면 실제로는 프레임색이 화면에 안 보이므로,
  // 완성본 자산은 frameColorId를 "white"로 통일해서 등록해뒀다.
  const effectiveFrameColorId = state.specialFrameId ? "white" : state.frameColorId;
  return `${effectiveFrameColorId}_${state.logoId}_${state.specialFrameId || "none"}`;
}

// 이미지를 지정된 사각형 영역에 "cover" 방식(꽉 채우게, 비율 유지, 잘림 허용)으로 그림
function drawImageCover(img, x, y, w, h) {
  const scale = Math.max(w / img.width, h / img.height);
  const dw = img.width * scale;
  const dh = img.height * scale;
  const dx = x + (w - dw) / 2;
  const dy = y + (h - dh) / 2;
  ctx.save();
  ctx.beginPath();
  ctx.rect(x, y, w, h);
  ctx.clip();
  ctx.drawImage(img, dx, dy, dw, dh);
  ctx.restore();
}

// ── Canvas 실시간 미리보기 합성 ───────────────────────────────────
async function renderPreview() {
  ctx.clearRect(0, 0, CANVAS_W, CANVAS_H);

  // 1) 사진 4장 먼저 그림 (2x2 격자)
  for (let i = 0; i < PHOTO_SLOTS.length; i++) {
    const slotF = PHOTO_SLOTS[i];
    const slot = {
      x: slotF.xf * CANVAS_W,
      y: slotF.yf * CANVAS_H,
      w: slotF.wf * CANVAS_W,
      h: slotF.hf * CANVAS_H,
    };
    const photo = selectedPhotos[i];

    ctx.fillStyle = "#d9d9d9";
    ctx.fillRect(slot.x, slot.y, slot.w, slot.h);

    if (photo) {
      const src = photo.mockSrc || `${API_BASE}/api/images/${photo.id}`;
      try {
        const img = await loadImage(src);
        ctx.save();
        ctx.beginPath();
        ctx.rect(slot.x, slot.y, slot.w, slot.h);
        ctx.clip();
        if (state.photoColorId === "bw") ctx.filter = "grayscale(100%)";
        const scale = Math.max(slot.w / img.width, slot.h / img.height);
        const dw = img.width * scale;
        const dh = img.height * scale;
        const dx = slot.x + (slot.w - dw) / 2;
        const dy = slot.y + (slot.h - dh) / 2;
        ctx.drawImage(img, dx, dy, dw, dh);
        ctx.restore();
      } catch (err) {
        console.warn("사진 로드 실패:", src, err);
      }
    }
  }

  // 2) 프레임 오버레이 결정
  //    - 신구대(green)는 로고 선택과 무관하게 항상 자기 완성본을 그대로 씀
  //    - 그 외는 (프레임색 또는 특별프레임)+로고 조합으로 완성본을 찾음
  let overlaySrc = null;

  if (state.frameColorId === "green" && !state.specialFrameId) {
    overlaySrc = "assets/frames_full/green_standalone.png";
  } else {
    overlaySrc = REAL_FULL_OVERLAY[currentOverlayKey()] || null;
  }

  if (overlaySrc) {
    try {
      const overlayImg = await loadImage(overlaySrc);
      ctx.drawImage(overlayImg, 0, 0, CANVAS_W, CANVAS_H);
      return;
    } catch (err) {
      console.warn("완성본 오버레이 로드 실패, 레이어 합성으로 대체:", err);
    }
  }

  // 3) 완성본이 없는 조합은 실제 에셋으로 레이어 합성 (배경/패턴 + 로고)
  await drawComposedOverlay();
}

// border(테두리)/band(밴드)/divider(구분선) 영역들의 좌표를 계산
function getFrameRegions() {
  const border = BORDER_F * CANVAS_W;
  const divider = DIVIDER_F * CANVAS_W;
  const topBand = TOP_BAND_F * CANVAS_H;
  const midDivider = MID_DIVIDER_F * CANVAS_H;
  const bottomBandStart = BOTTOM_BAND_START_F * CANVAS_H;

  return {
    top: { x: 0, y: 0, w: CANVAS_W, h: topBand },
    bottom: { x: 0, y: bottomBandStart, w: CANVAS_W, h: CANVAS_H - bottomBandStart },
    left: { x: 0, y: topBand, w: border, h: bottomBandStart - topBand },
    right: { x: CANVAS_W - border, y: topBand, w: border, h: bottomBandStart - topBand },
    midV: { x: CANVAS_W / 2 - divider / 2, y: topBand, w: divider, h: bottomBandStart - topBand },
    midH: { x: border, y: CANVAS_H / 2 - midDivider / 2, w: CANVAS_W - border * 2, h: midDivider },
  };
}

async function drawComposedOverlay() {
  const regions = getFrameRegions();
  const specialFrame = ASSET_SPECIAL_FRAMES.find((f) => f.id === state.specialFrameId);
  const frameColor = ASSET_FRAME_COLORS.find((f) => f.id === state.frameColorId);
  // logoId가 비어있으면(신구대 선택 중 실제 완성본 로드 실패 등 예외 상황)
  // 안전하게 기본 로고(1번)로 대체
  const logo = ASSET_LOGOS.find((l) => l.id === state.logoId) || ASSET_LOGOS[0];

  if (specialFrame) {
    // 특별 프레임 패턴을 각 영역에 cover 방식으로 채움
    const patternImg = await loadImage(specialFrame.src).catch(() => null);
    Object.values(regions).forEach((r) => {
      if (patternImg) {
        drawImageCover(patternImg, r.x, r.y, r.w, r.h);
      } else {
        ctx.fillStyle = "#ccc";
        ctx.fillRect(r.x, r.y, r.w, r.h);
      }
    });
  } else {
    // 일반 프레임 색상 채움
    ctx.fillStyle = frameColor.color;
    Object.values(regions).forEach((r) => ctx.fillRect(r.x, r.y, r.w, r.h));

    // green(신구대)은 로고가 이미 박혀있는 특수 스와치라, 상단 밴드에
    // 그 스와치 이미지 자체를 작게 얹어서 표시 (선택한 로고와는 별개로)
    if (frameColor.hasEmbeddedLogo) {
      try {
        const badgeImg = await loadImage(frameColor.src);
        const badgeSize = regions.top.h * 0.7;
        drawImageCover(badgeImg, CANVAS_W - badgeSize - 12, (regions.top.h - badgeSize) / 2, badgeSize, badgeSize);
      } catch (err) {
        console.warn("green 배지 로드 실패:", err);
      }
    }
  }

  // 로고를 상단 밴드 중앙에 그림
  try {
    const logoImg = await loadImage(logo.src);
    const logoSize = regions.top.h * 0.75;
    drawImageCover(logoImg, (CANVAS_W - logoSize) / 2, (regions.top.h - logoSize) / 2, logoSize, logoSize);
  } catch (err) {
    console.warn("로고 로드 실패:", err);
  }
}

function updateNextButtonState() {
  nextBtn.disabled = selectedPhotos.length !== 4;
}

// ── NEXT: Canvas를 최종 이미지로 만들어 업로드 ─────────────────────
nextBtn.addEventListener("click", async () => {
  if (nextBtn.disabled) return;

  nextBtn.disabled = true;
  loadingOverlay.classList.add("show");

  canvas.toBlob(async (blob) => {
    try {
      const formData = new FormData();
      formData.append("file", blob, "fourcut_composited.jpg");
      // ★ 실제로 선택한 4장의 id도 같이 보내서, 서버가 정확히 그 사진들의
      //   원본(cut_1~4.jpg)을 S3에 같이 올릴 수 있게 함 (추측 X)
      formData.append("image_ids", JSON.stringify(selectedPhotos.map((p) => p.id)));

      // ★ Personal_Info 화면에서 입력한 이름/전화번호를 같이 보내서
      //   서버 -> AWS 쪽에서 세션 정보(DynamoDB)에 채워질 수 있게 함
      try {
        const personalInfoRaw = sessionStorage.getItem("pikcha_personal_info");
        if (personalInfoRaw) {
          const personalInfo = JSON.parse(personalInfoRaw);
          if (personalInfo && personalInfo.name) {
            formData.append("name", personalInfo.name);
          }
          if (personalInfo && personalInfo.phoneNumber) {
            formData.append("phone_number", personalInfo.phoneNumber);
          }
        }
      } catch (e) {
        console.log("개인정보(pikcha_personal_info) 읽기 실패 - 이름/전화번호 없이 진행:", e.message);
      }

      // ★ Number_of_Prints 화면에서 고른 인쇄 매수를 같이 보내서, 인쇄 워커가
      //   실제로 그 매수만큼 뽑도록 함 (안 보내면 서버 쪽에서 1장으로 처리)
      try {
        const printQuantityRaw = sessionStorage.getItem("pikcha_print_quantity");
        if (printQuantityRaw) {
          formData.append("print_quantity", printQuantityRaw);
        }
      } catch (e) {
        console.log("인쇄 매수(pikcha_print_quantity) 읽기 실패 - 1장으로 진행:", e.message);
      }

      const res = await fetch(`${API_BASE}/api/fourcut/create-composited`, {
        method: "POST",
        body: formData,
      });
      const result = await res.json();
      if (!result.success) throw new Error(result.message || "업로드 실패");

      const qrBase64 = result.s3 && result.s3.qr_base64;
      const normalizedResult = {
        mock: false,
        qrSrc: qrBase64 ? `data:image/png;base64,${qrBase64}` : null,
      };
      sessionStorage.setItem("pikcha_result", JSON.stringify(normalizedResult));
      window.location.href = "../../Print_Photo/index.html";

    } catch (err) {
      console.log("실제 업로드 실패 - 데모 QR로 대체합니다:", err.message);
      await new Promise((r) => setTimeout(r, 800));
      const demoUrl = "https://example.com/pikcha-demo";
      const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=${encodeURIComponent(demoUrl)}`;
      sessionStorage.setItem("pikcha_result", JSON.stringify({ mock: true, qrSrc: qrUrl }));
      window.location.href = "../../Print_Photo/index.html";
    }
  }, "image/jpeg", 0.92);
});

// ── 초기화 ────────────────────────────────────────────────────────
loadSelectionFromSession();
renderSwatches();
renderPreview();
