// Main 게이트웨이 스크립트.
// 접속 시각(한국 표준시 기준)에 따라 Main_noon 또는 Main_sunset 화면으로
// 자동 리디렉션한다. 사용자의 로컬 시간대와 무관하게 항상 KST(UTC+9)로 판별한다.

// 현재 시각을 "자정부터 몇 분 지났는지"(0~1439)의 숫자로 변환한다.
function getKstMinutesOfDay() {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Seoul",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(new Date());

  // 일부 브라우저는 자정을 "24시"로 표기하는 버그가 있어 24로 나눈 나머지로 보정한다.
  const hour = Number(parts.find((p) => p.type === "hour").value) % 24;
  const minute = Number(parts.find((p) => p.type === "minute").value);

  return hour * 60 + minute;
}

// Main Noon 노출 시간대: 07:00 ~ 15:30 (그 외 시간은 전부 Main Sunset)
const NOON_START = 7 * 60; // 07:00
const NOON_END = 15 * 60 + 30; // 15:30

const minutesNow = getKstMinutesOfDay();
const isNoon = minutesNow >= NOON_START && minutesNow <= NOON_END;

// 페이지를 그릴 필요 없이 곧바로 해당 폴더로 이동시킨다.
window.location.href = isNoon ? "./Main_noon/index.html" : "./Main_sunset/index.html";
