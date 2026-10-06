// =====================================================================
// clean-svg.js — Figma 에서 내보낸 SVG 의 "배경 찌꺼기" 제거기
// ---------------------------------------------------------------------
// 왜 필요한가
//   Figma 에서 요소 하나를 SVG 로 내보내면, 요소 뒤에 깔려 있던
//     ① 캔버스 배경 사각형 (fill="#F5F5F5")
//     ② 화면(프레임) 크기의 흰 사각형 (1342x877 또는 402x874, fill="white")
//   이 같이 들어온다. 그대로 쓰면 코랄 배경 위에서 흰 사각형이 비쳐 보인다.
// 하는 일
//   assets/ 폴더 안의 모든 .svg 를 열어 위 두 사각형(파일의 첫 번째 줄에 있는 것만)을 지운다.
//   이미 깨끗한 파일은 건드리지 않는다. 몇 번을 돌려도 결과가 같다.
// 사용법 (Frontend_changes 폴더에서)
//   새 SVG 를 assets/ 아래에 저장한 뒤:   node tools/clean-svg.js
// =====================================================================
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");                                   // Frontend_changes 폴더
const SKIP_DIRS = new Set(["node_modules", ".git", ".claude"]);            // 건너뛸 폴더

let changed = 0;                                                           // 실제로 고친 파일 수

// ① 캔버스 배경: 파일 맨 앞쪽의 <rect width=".." height=".." fill="#F5F5F5"/> 한 줄
const CANVAS_BG = /^<rect width="[\d.]+" height="[\d.]+" fill="#F5F5F5"\/>\r?\n/m;
// ② 화면 크기(1342x877 / 402x874)의 흰 사각형. 요소가 좌표 0,0 이 아니면 transform="translate(..)" 이 붙어 있다
const FRAME_BG = /^<rect width="(1342|402)" height="(877|874)"( transform="translate\([^)]*\)")? fill="white"\/>\r?\n/m;

function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (!SKIP_DIRS.has(entry.name)) walk(full);
      continue;
    }
    // assets 폴더 안의 .svg 만 대상으로 한다
    if (!full.endsWith(".svg") || !full.includes(path.sep + "assets" + path.sep)) continue;

    const before = fs.readFileSync(full, "utf8");
    const after = before.replace(CANVAS_BG, "").replace(FRAME_BG, "");
    if (after !== before) {
      fs.writeFileSync(full, after);
      changed++;
    }
  }
}

walk(ROOT);
console.log("cleaned", changed, "files");
