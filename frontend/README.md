# PIK-CHA! 프론트엔드 (HTML/CSS)

학교 포토부스 **PIK-CHA!** 의 Figma 디자인을 **순수 HTML/CSS** 로 옮긴 폴더입니다.
키오스크 화면 8개, 웨이팅·관리자 화면 6개, 인화 프레임 에셋이 들어 있습니다.

> **JavaScript 는 없습니다.** 화면 이동은 `<a href>`, hover/active 는 CSS 만 씁니다.
> 모양과 화면 흐름까지만 구현돼 있고, 실제 동작(숫자 입력, 카메라, 웨이팅 등록 등)은 JS 로 붙이면 됩니다. → [JS 연결 가이드](#5-js-연결-가이드)

- 디자인 원본: 키오스크 `frontend/` 는 Figma 파일 키 `xWwsvyTKuQtjnzA2MBzG5k` (페이지 `6:219`), 웨이팅·관리자 `admin/` 은 `nvFuZIgz74tddZfp769Gdu` (Page 1)
- 참고용 기존 코드 (이 폴더에서는 수정하지 않음): `C:\pik-cha\admin`, `C:\pik-cha\frontend_new`, `C:\pik-cha\Lambda`

---

## 1. 바로 보기

파일을 더블클릭하면 경로가 어긋날 수 있어서 로컬 서버로 봅니다. (Node.js 필요)

```bash
cd C:\pik-cha\Frontend_changes
npx http-server . -p 5173 -c-1
```

| 영역 | 시작 주소 |
|---|---|
| 키오스크 | http://localhost:5173/frontend/01_landing_main/index.html |
| 관리자 | http://localhost:5173/admin/WaitingList_AdminPage/index.html |

- 키오스크 화면(`frontend/`)은 **반응형**입니다. flex/grid 로 배치되어 가로 모니터·세로 모니터·태블릿·폰에서 각각 레이아웃이 맞춰집니다. 세로 화면이나 폭 900px 이하에서는 좌우 2단 화면(05·06·07)이 위아래 1단으로 바뀝니다.
- 관리자 화면(`admin/`)의 고정 캔버스 화면은 아직 **창 크기에 맞춰 비율을 유지한 채 확대/축소**하는 방식입니다.
- 폰트는 Google Fonts 라서 인터넷 연결이 필요합니다.

---

## 2. 폴더 구조

```
Frontend_changes/
├─ assets/              두 영역이 같이 쓰는 이미지 (로고 SVG, QR 샘플, frames/)
├─ frontend/            키오스크 화면 (반응형, Figma 기준 1342×877)
│  ├─ common.css        공통 스타일 (헤더 로고·선, 배경 원, 알약 버튼, 확대·축소)
│  └─ NN_이름/           index.html + style.css (+ 그 화면 전용 assets/)
├─ admin/               웨이팅·관리자 화면
│  ├─ admin.css         고정 캔버스 화면(메인·등록 폼·QR)의 공통 스타일
│  ├─ list.css          표 화면(웨이팅리스트 관리·인화 상태 관리)의 공통 스타일
│  └─ 화면이름/          index.html + style.css
└─ tools/               개발 보조 스크립트 (6장)
```

**새 화면을 추가할 때 지킬 규칙**
1. 화면 하나 = 폴더 하나 (`index.html` + `style.css`).
2. 공통 스타일은 `common.css` / `admin.css` / `list.css` 에, 화면 고유 스타일만 `style.css` 에.
3. 글자는 SVG 가 아니라 **HTML 텍스트 + CSS**. SVG 는 로고·이미지가 박힌 도형·아이콘에만.
4. 이미지는 두 영역이 같이 쓰면 루트 `assets/`, 한 화면에서만 쓰면 그 화면의 `assets/`.
5. 키오스크 화면은 좌표 고정(absolute) 대신 flex/grid 로 배치하고, 크기는 `clamp(최솟값, 화면 비례값, Figma 값 × var(--k))` 로 준다. (`--k` 는 Figma 프레임보다 큰 화면에서의 확대 배율, `common.css` 참고)
   관리자의 고정 캔버스 화면은 Figma 좌표 그대로 `position: absolute` (1342×877, 모바일 402×874).

---

## 3. 화면 목록

### 키오스크 (`frontend/`)

흐름: 01 메인 → 02 순번 입력 → 03 수량 → 04 카운트다운 → 05 촬영 → 06 사진 선택 → 07 프레임 선택 → 08 출력/QR → 01

| 폴더 | 화면 | Figma | 이동 |
|---|---|---|---|
| `01_landing_main` | 메인 | `40:134` | 시작하기 |
| `02_waiting_number` | 순번 입력 키패드 | `40:516` | 확인하고 계속하기 |
| `03_number_of_prints` | 수량 선택 (− 2 +) | `40:99` | 확인하고 계속하기 |
| `04_countdown` | 곧 촬영이 시작돼요 (5) | `40:490` | 자동 (JS) |
| `05_take_a_picture` | 촬영 (0/8, 남은 시간) | `40:2` | 자동 (JS) |
| `06_review_photo` | 사진 선택 (4컷 보드 + 4×2 썸네일) | `40:58` | 선택 완료 |
| `07_select_frame` | 프레임 선택 | `40:560` | 선택 완료 |
| `08_print_qr` | 출력 대기 + 다운로드 QR | `40:31` | 자동 → 01 (JS) |

### 웨이팅 · 관리자 (`admin/`)

| 폴더 | 화면 | 크기 | Figma |
|---|---|---|---|
| `WaitingList_AdminPage` | 관리자 메인 (메뉴 카드 3개) | 1342×877 | `1:605` |
| `WaitingList_UserPage` | 모바일 웨이팅 등록 폼 | 402×874 | `1:491` |
| `WaitingList_UserPage_Status` | 모바일 대기 현황 | 402×874 | `1:546` |
| `WaitingList_AdminQRPage` | 태블릿 QR + 등록 폼 | 1342×877 | `1:425` |
| `WaitingList_AdminManage` | 웨이팅리스트 관리 (표) | 창 너비에 맞춰 늘어남 | 없음* |
| `PrintStatus_AdminManage` | 인화 상태 관리 (표) | 창 너비에 맞춰 늘어남 | 없음* |

\* Figma 시안은 따로 없어서(Page 1 하단에 직접 만든 프레임 있음) 기존 `admin` 폴더의 화면을 바탕으로 색만 코랄로 바꿨습니다.

**연결 흐름**
- 관리자 메인 "등록페이지" → 태블릿 QR
- 모바일 등록 폼 버튼 → 대기 현황 → "웨이팅 취소하기" → 등록 폼
- 관리자 메인 메뉴 카드 "웨이팅리스트 관리" / "인화 상태 관리" → 각 표 화면 → "← 대시보드"로 복귀

---

## 4. 인화 프레임 에셋 (`assets/frames/`)

인화지에 들어가는 프레임입니다 (각 1100×1605, 사진 4칸이 투명하게 뚫려 있음).
파일명은 `{종류}-{모양}.svg`, 모양은 `round` / `arch` / `long`.

| 종류 | 내용 | 모양 |
|---|---|---|
| `white` `black` `blue` `pink` | 단색 | round, arch, long |
| `star` | 남색 별무늬 | round, arch, long |
| `water` | 물결(데님) | round, arch, long |
| `mint` | 민트 도트 | round, arch, long |
| `blackstar` | 검정 별 도트 | round, arch, long |
| `halloween` | 핼러윈 호박 | round, arch, long |
| `kitty` | 헬로키티 | round, arch, long |
| `shingu` | 신구대 로고 | round만 |

`frames/textures/` 에는 무늬 원본(`star`, `water`, `blackstar-dots`)이 있습니다.

> Figma 에서 `halloween`·`kitty` 프레임 6개가 `프레임 테스트 Blue_*` 로 이름이 겹쳐 있어서, 여기서는 실제 그림에 맞춰 이름을 붙였습니다.
> 에셋만 저장했고 화면에는 아직 쓰이지 않습니다 (06/07 미리보기는 회색 자리 표시).

---

## 5. JS 연결 가이드

JS 는 아래 "연결 지점"에만 붙이면 됩니다. 레이아웃을 건드릴 필요가 없습니다.
각 화면 `index.html` 맨 위 주석에도 같은 내용이 있습니다.

### 원칙
- 요소는 **`id` 또는 `data-*`** 로 찾습니다. 클래스(`.key`, `.thumb` 등)는 모양용이라 바뀔 수 있습니다.
- 상태는 **클래스**로 바꿉니다 (`.is-selected`, `.disabled`). 스타일은 이미 CSS 에 있습니다.
- **좌표는 CSS 에만** 있습니다. JS 에서 `style.left/top` 을 바꾸지 마세요.
- (관리자) 고정 캔버스 화면은 통째로 `transform: scale(--fit)` 됩니다. 좌표를 계산할 때는 `getBoundingClientRect()` 값을 `--fit` 으로 나눠야 합니다.
- 이동은 지금 `<a href>` 입니다. JS 로 제어할 때는 `location.href` 로 바꾸고 임시 링크(`.goto`)는 지웁니다.
- `<form>` 은 쓰지 않았습니다. 값은 `#dept.value` 처럼 직접 읽습니다.

### 키오스크 (`frontend/`)

| 화면 | 연결 지점 | 메모 |
|---|---|---|
| 01 메인 | `#waiting-register-btn` | |
| 02 순번 입력 | `#keypad`, `[data-key]` (`0`~`9`, `clear`, `backspace`), `#number-line`, `#error-msg`, `#nav-next` | `clear` = 지우기(전체), `backspace` = 삭제(한 글자). `#number-line` 은 Figma 에 없는 자리라 안내 문구 아래에 둠 |
| 03 수량 | `#print-count`, `[data-action="decrease\|increase"]` | 수량 2~4 |
| 04 카운트다운 | `#countdown-number` | 5→1 후 05 로 |
| 05 촬영 | `#camera-preview`, `#shot-count`, `#time-left` | 523×721 자리에 카메라 영상 |
| 06 사진 선택 | `#board`, `[data-slot="1..4"]`, `[data-photo="1..8"]`, `#nav-next` | 8장 중 4장 선택 (`.is-selected`) |
| 07 프레임 선택 | `#board`, `[data-slot]`, `.sw[data-group][data-value]`, `#nav-next` | `data-group` = `logo` / `color` / `special` / `frame`. 그룹마다 하나만 `.is-selected` |
| 08 출력/QR | `#download-qr`, `#print-timer` | QR `src` 교체, 30초 후 01 로 |

07 의 `data-value`: `logo-1..3`, `rainbow`, `bw`, `special-1..6`, `frame-white|black|blue|pink|shingu`.
프레임 이미지는 `assets/frames/{종류}-{round|arch|long}.svg` (예: `frame-white` → `white-round.svg`).

### 웨이팅 · 관리자 (`admin/`)

| 화면 | 연결 지점 |
|---|---|
| 관리자 메인 | `#waiting-now`, `#btn-register-page`, `#btn-admin`, `[data-menu="dashboard\|waiting\|print"]` |
| 모바일 등록 폼 | `#dept`, `#name`, `#head-count`, `[data-action="decrease\|increase"]`, `#btn-register` |
| 모바일 대기 현황 | `#my-rank`, `#my-info`, `#wait-eta`, `#print-status`, `#btn-cancel` |
| 태블릿 QR | `#download-qr`, `#waiting-now`, `#dept`, `#sid`, `#name`, `#phone`, `#head-count`, `[data-action]`, `#btn-register` |
| 웨이팅리스트 관리 | `#btn-refresh`, `#status-msg`, `#waitlist-body` |
| 인화 상태 관리 | `#btn-refresh`, `#status-msg`, `#print-body` |

- `#btn-register` 는 시안이 회색(비활성)입니다. 필수 입력이 끝나면 코랄(`#e16a56`)로 바꿔 활성화합니다.
- `<select id="dept">` 는 옵션이 1개뿐이라 학과 목록을 JS 로 채웁니다.
- 인원수는 1~8명, 키오스크 출력 수량은 2~4장.
- 표 화면은 `#…-body`(`<tbody>`)에 `<tr>` 을 채웁니다. `#status-msg` 는 평소 `hidden`.
  - 웨이팅리스트 관리: 상태 `<span class="status-pill status-값">`, 행 끝 `<button class="cancel-btn">`.
  - 인화 상태 관리: 인화상태 `status-pill print-pending|printed|failed`, SMS `sms-pill sms-sent|sms-unsent`, 행 끝 `.row-actions > .action-btn.reprint-btn / .resend-btn`. 행 모양 견본은 `index.html` 맨 위 주석에 있습니다.

### 상태 클래스

| 클래스 | 의미 | 정의 위치 |
|---|---|---|
| `.is-selected` | 선택됨 (06 썸네일: 코랄 테두리, 07 원: 코랄 링) | `06_review_photo/style.css`, `07_select_frame/style.css` |
| `.disabled` | 비활성 (흐리게 + 클릭 불가. 키오스크 알약 버튼 `.cta` 는 회색 배경) | `frontend/common.css`, `admin/admin.css` |
| `[hidden]` | 숨김 | 공통 css |

---

## 6. 개발 보조 스크립트 (`tools/`)

| 파일 | 용도 |
|---|---|
| `check-links.js` | HTML/CSS 의 파일 참조(링크, 이미지, `url()`)가 실제로 있는지 검사. 폴더·파일을 옮긴 뒤 `node tools/check-links.js` |
| `clean-svg.js` | Figma 에서 내보낸 SVG 의 배경 사각형 제거. 새 SVG 를 `assets/` 에 넣은 뒤 `node tools/clean-svg.js` |

---

## 7. 알아둘 점

- **폰트 (키오스크)**: 본문 `Gowun Dodum`, 키패드 숫자 `DM Sans`, 큰 숫자 `Righteous`, 촬영·출력 화면 숫자 `Noto Sans` (Thin/Bold).
- **폰트 (웨이팅·관리자)**: 본문 `Noto Sans` + `Noto Sans KR` (**Noto Sans 를 먼저** 써야 Figma 와 줄 높이가 맞음), `Special Gothic Expanded One` (PHOTOBOOTH / START in), `Righteous` (숫자·WAITING LIST), `Sora` (모바일 PHOTO BOOTH). 모두 CSS `@import` 로 불러옵니다. Figma 의 SF Compact 는 웹에서 쓸 수 없어 Noto Sans KR 로 대체했습니다.
- **모바일 상태바**: 모바일 화면 위의 시간·신호·배터리는 시안 그대로 넣은 장식용입니다 (`aria-hidden`). 실기기에서 OS 상태바와 겹치면 `.m-head .statusbar` 만 지우면 됩니다.
- **현재 한계**: 동작은 전부 없습니다 (정적 화면). 관리자 메인의 "Dashboard" 카드는 갈 화면이 없어 링크가 `#` 입니다.
- **용량**: 이미지가 박힌 프레임 SVG 는 한 개가 0.3~0.8MB 입니다 (`assets/` 전체 약 9MB).
