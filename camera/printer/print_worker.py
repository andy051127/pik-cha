"""
Pik-Cha! 현장 PC용 인쇄 워커.

[구조]
Lambda(sgu-pikcha-print)는 부스 PC(사설망)에 직접 접근할 방법이 없어서,
반대로 이 스크립트가 API를 주기적으로 폴링(pull)해서 인쇄 대기 작업을 가져옴.
프린터 1대 + 워커 1개(순차 처리)라 __PENDING_PRINTS__ 리스트 자체가 자연스러운
FIFO 큐 역할을 함. 별도 큐 서비스(SQS 등) 불필요.

[인쇄 방식]
- GDI(win32ui)로 프린터 디바이스 컨텍스트(DC)에 직접 비트맵을 그려서 인쇄 잡을 넣음.
  중간에 뷰어 프로그램이 안 끼기 때문에 인쇄 대화상자가 안 뜨고 조용히 인쇄됨.
- 용지 크기는 코드에서 DEVMODE로 'Japanese Postcard(10.0x14.8cm)'를 직접 지정 +
  방향은 세로(Portrait). Windows에 저장된 기본값에 의존하지 않음.

[여백 없이 정확히 10.0x14.8cm로 채우는 원리]
- 업로드되는 합성 이미지는 이미 용지와 같은 비율(10:14.8, 세로)로 만들어져 있음.
- 그래서 letterbox(여백 남김)나 cover(잘라냄)를 하지 않고, 물리적 용지 전체 크기
  (PHYSICALWIDTH x PHYSICALHEIGHT)에 그대로 늘려서 채움 → 비율이 같으니 왜곡·크롭 없음.
- GDI DC의 좌표 원점(0,0)은 "용지 끝"이 아니라 "인쇄 가능 영역"(드라이버가 잡아둔 여백
  안쪽)에서 시작함. 이게 여백이 남던 진짜 원인. PHYSICALOFFSETX/Y만큼 음수로 밀어서
  용지의 진짜 물리적 모서리(0,0)부터 그리게 하면 테두리 없이(borderless) 꽉 참.

실행 전:
  pip install -r requirements.txt
  아래 API_BASE(필수), PRINTER_NAME(선택) 값을 채우거나 환경변수로 지정
"""

import os
import sys
import time
import tempfile
import traceback

import requests
import win32print
import win32ui
import win32gui
from PIL import Image, ImageWin

# ===== 설정 =====================================================================
API_BASE = os.environ.get(
    "PIKCHA_API_BASE",
    "https://nwwtnmzm3l.execute-api.ap-northeast-2.amazonaws.com/prod",
)
PRINTER_NAME = os.environ.get("PIKCHA_PRINTER_NAME") or win32print.GetDefaultPrinter()
POLL_INTERVAL_SEC = 5
PRINT_WAIT_TIMEOUT_SEC = 120
# ===============================================================================

# GetDeviceCaps 인덱스 (wingdi.h)
HORZRES = 8            # 인쇄 가능 영역 폭(px)
VERTRES = 10           # 인쇄 가능 영역 높이(px)
PHYSICALWIDTH = 110    # 용지 전체 폭(px)
PHYSICALHEIGHT = 111   # 용지 전체 높이(px)
PHYSICALOFFSETX = 112  # 용지 왼쪽 끝 ~ 인쇄가능영역 왼쪽 끝 여백(px)
PHYSICALOFFSETY = 113  # 용지 위쪽 끝 ~ 인쇄가능영역 위쪽 끝 여백(px)

# DEVMODE 플래그/값 (wingdi.h)
DC_PAPERS = 2
DC_PAPERNAMES = 16
DM_ORIENTATION = 0x00000001
DM_PAPERSIZE = 0x00000002
DMORIENT_PORTRAIT = 1
DMORIENT_LANDSCAPE = 2


def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ===== API 통신 =================================================================
def get_pending_jobs():
    res = requests.get(f"{API_BASE}/print-jobs", params={"status": "pending"}, timeout=10)
    res.raise_for_status()
    return res.json().get("jobs", [])


def download_image(url: str, dest_path: str):
    res = requests.get(url, timeout=30)
    res.raise_for_status()
    with open(dest_path, "wb") as f:
        f.write(res.content)


def report_complete(session_id: str):
    res = requests.post(f"{API_BASE}/print-complete", json={"session_id": session_id}, timeout=10)
    res.raise_for_status()


# ===== 인쇄 =====================================================================
def _build_devmode(printer_name: str):
    """용지를 'Japanese Postcard(10.0x14.8cm)'로 명시 지정 + 세로 방향으로 강제한
    DEVMODE를 반환. Windows에 저장된 기본값이 온전치 않아 여백이 생기는 경우를 우회."""
    hPrinter = win32print.OpenPrinter(printer_name)
    try:
        info = win32print.GetPrinter(hPrinter, 2)
        devmode = info["pDevMode"]
        port_name = info["pPortName"]

        names = win32print.DeviceCapabilities(printer_name, port_name, DC_PAPERNAMES)
        ids = win32print.DeviceCapabilities(printer_name, port_name, DC_PAPERS)
        for name, paper_id in zip(names, ids):
            if "postcard" in name.lower() or "엽서" in name:
                devmode.PaperSize = paper_id
                break

        devmode.Orientation = DMORIENT_PORTRAIT
        devmode.Fields |= DM_PAPERSIZE | DM_ORIENTATION
        return devmode
    finally:
        win32print.ClosePrinter(hPrinter)


def print_image(path: str):
    img = Image.open(path)
    if img.mode != "RGB":
        img = img.convert("RGB")

    devmode = _build_devmode(PRINTER_NAME)
    hdc_handle = win32gui.CreateDC("WINSPOOL", PRINTER_NAME, devmode)
    hDC = win32ui.CreateDCFromHandle(hdc_handle)

    try:
        phys_w = hDC.GetDeviceCaps(PHYSICALWIDTH)
        phys_h = hDC.GetDeviceCaps(PHYSICALHEIGHT)
        off_x = hDC.GetDeviceCaps(PHYSICALOFFSETX)
        off_y = hDC.GetDeviceCaps(PHYSICALOFFSETY)

        # 이미지를 물리적 용지 전체에 그대로 늘려 채움. 이미지가 이미 용지와 같은 비율
        # (10:14.8, 세로)이라 왜곡·크롭 없음. 원점을 여백만큼(-off) 밀어 용지 진짜 모서리부터
        # 그려서 테두리 없이(borderless) 정확히 10.0x14.8cm로 출력.
        left = -off_x
        top = -off_y
        right = phys_w - off_x
        bottom = phys_h - off_y

        hDC.StartDoc(os.path.basename(path))
        hDC.StartPage()
        ImageWin.Dib(img).draw(hDC.GetHandleOutput(), (left, top, right, bottom))
        hDC.EndPage()
        hDC.EndDoc()
    finally:
        hDC.DeleteDC()


def get_queue_length() -> int:
    hPrinter = win32print.OpenPrinter(PRINTER_NAME)
    try:
        jobs = win32print.EnumJobs(hPrinter, 0, -1, 1)
        return len(jobs)
    finally:
        win32print.ClosePrinter(hPrinter)


def wait_until_printed(timeout_sec: int = PRINT_WAIT_TIMEOUT_SEC) -> bool:
    """스풀 큐에 작업이 떴다가 다시 사라지면 인쇄 완료로 판단. timeout 안에 확인 못 하면
    False를 반환하지만, 호출부에서는 그래도 완료로 취급하고 넘어감(멈추는 것보단 나음)."""
    deadline = time.time() + timeout_sec
    appeared = False
    while time.time() < deadline:
        count = get_queue_length()
        if count > 0:
            appeared = True
        elif appeared:
            return True
        time.sleep(2)
    return False


# ===== 메인 루프 ================================================================
def process_job(job: dict):
    session_id = job["session_id"]
    download_url = job["download_url"]

    log(f"인쇄 시작: session_id={session_id}")

    local_path = os.path.join(tempfile.gettempdir(), f"pikcha_{session_id}.jpg")
    download_image(download_url, local_path)
    print_image(local_path)

    if not wait_until_printed():
        log(f"⚠️  인쇄 완료 확인 실패(타임아웃) — 그래도 완료 처리함: session_id={session_id}")

    report_complete(session_id)
    log(f"✅ 인쇄 완료 보고: session_id={session_id}")

    try:
        os.remove(local_path)
    except OSError:
        pass


def main():
    log(f"인쇄 워커 시작. API_BASE={API_BASE}, PRINTER_NAME={PRINTER_NAME}")
    while True:
        try:
            for job in get_pending_jobs():
                process_job(job)
        except requests.RequestException as e:
            log(f"⚠️  네트워크 오류 (다음 폴링에 재시도): {e}")
        except Exception:
            log("❌ 예상치 못한 오류:")
            traceback.print_exc()

        time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
