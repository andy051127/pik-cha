// =====================================================================
// check-links.js — 깨진 파일 참조 검사기
// ---------------------------------------------------------------------
// 하는 일
//   1) 모든 .html 이 참조하는 CSS(<link href>), 이미지(<img src>), 이동 링크(<a href>) 가 실제 파일로 존재하는지 확인
//   2) 모든 .css 안의 url(...) 이미지 경로가 실제로 존재하는지 확인
//   (http(s):, data:, mailto:, #앵커 는 검사하지 않는다)
// 사용법 (Frontend_changes 폴더에서)
//   node tools/check-links.js
// 결과: 깨진 참조가 있으면 목록을 출력하고 종료 코드 1, 없으면 "깨진 참조 없음".
// 언제 돌리나: 폴더 이름을 바꾸거나 화면/이미지를 옮긴 뒤에 꼭 한 번.
// =====================================================================
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");          // Frontend_changes 폴더
const SKIP_DIRS = new Set([".git", ".claude", "node_modules"]);   // 검사에서 제외할 폴더
const SKIP_REF = /^(https?:|data:|mailto:|#)/;                      // 검사하지 않는 참조 형태

let htmlCount = 0, cssCount = 0, refCount = 0;
const broken = [];                                 // 깨진 참조 목록 ("파일  ->  참조")

// 참조 하나를 검사한다. file = 참조가 적힌 파일, ref = 적힌 경로(상대 경로)
function check(file, ref) {
  if (!ref || SKIP_REF.test(ref)) return;
  refCount++;
  const clean = ref.split("#")[0].split("?")[0];   // "#앵커", "?쿼리" 는 떼고 파일 경로만
  if (!fs.existsSync(path.resolve(path.dirname(file), clean))) {
    broken.push(path.relative(ROOT, file) + "  ->  " + ref);
  }
}

// 폴더를 재귀로 돌며 .html / .css 를 검사한다
function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (!SKIP_DIRS.has(entry.name)) walk(full);
      continue;
    }
    if (full.endsWith(".html")) {
      htmlCount++;
      const html = fs.readFileSync(full, "utf8");
      for (const m of html.matchAll(/(?:href|src)="([^"]*)"/g)) check(full, m[1]);   // href="..." 와 src="..."
    } else if (full.endsWith(".css")) {
      cssCount++;
      // 주석 안의 url 은 무시하고, url("...") / url(...) 안의 경로를 검사
      const css = fs.readFileSync(full, "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
      for (const m of css.matchAll(/url\(\s*["']?([^"')]+)["']?\s*\)/g)) check(full, m[1]);
    }
  }
}

walk(ROOT);

console.log(`HTML ${htmlCount}개, CSS ${cssCount}개, 참조 ${refCount}개 검사`);
if (broken.length) {
  console.log("깨진 참조:\n" + broken.join("\n"));
  process.exit(1);
}
console.log("깨진 참조 없음");
