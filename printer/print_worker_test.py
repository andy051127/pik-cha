"""
Pik-Cha! 인쇄 워커 - 프린터 없이 SMS 파이프라인만 테스트하기 위한 사본.

원본(print_worker.py)의 실제 GDI 인쇄(win32print/win32ui/win32gui)를 전부 빼고,
받은 이미지를 그냥 PDF로 저장하는 것으로 대체했다. 목적은 프린터/pywin32 없이도
"인쇄완료 보고(report_complete) -> Lambda의 /print-complete -> SOLAPI SMS 발송"
파이프라인이 제대로 도는지만 확인하는 것.

★ 이건 테스트용 사본일 뿐 - 실제 인쇄 로직은 원본 print_worker.py를 계속 써야 함.
  테스트 끝나면 이 파일은 지워도 됨 (Lambda/DynamoDB 쪽엔 영향 없음).

실행 전: pip install requests pillow  (win32 계열 라이브러리 불필요)
"""

import os
import sys
import time
import tempfile
import traceback

import requests
from PIL import Image

# ===== 설정 =====================================================================
API_BASE = os.environ.get(
    "PIKCHA_API_BASE",
    "https://nwwtnmzm3l.execute-api.ap-northeast-2.amazonaws.com/prod/",
)
POLL_INTERVAL_SEC = 5
MAX_RETRIES_PER_JOB = 3  # 같은 작업이 이 횟수만큼 연속 실패하면 서버에 실패 신고 후 포기

# ★ 실제 인쇄 대신 PDF를 저장해둘 폴더
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "print_test_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
# ===============================================================================

# session_id별 연속 실패 횟수. 재시도 한도를 넘긴 작업은 report_failed()로 서버 pending
# 큐에서 제거되게 신고하므로, 신고에 성공하면 더 이상 폴링 결과에도 나타나지 않는다.
_job_failure_counts: dict[str, int] = {}


def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ===== API 통신 (원본과 동일 - 여기가 테스트 대상) ================================
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


def report_failed(session_id: str, error: str):
    res = requests.post(
        f"{API_BASE}/print-failed",
        json={"session_id": session_id, "error": error},
        timeout=10,
    )
    res.raise_for_status()


# ===== "인쇄" 대신 PDF 저장 =======================================================
def save_as_pdf(path: str, session_id: str, copies: int = 1) -> list[str]:
    """실제 GDI 인쇄 대신 PDF로 저장. copies장만큼 파일을 따로 만들어서
    인쇄 매수(quantity) 반영도 눈으로 확인할 수 있게 함."""
    img = Image.open(path)
    if img.mode != "RGB":
        img = img.convert("RGB")

    saved_paths = []
    for i in range(1, copies + 1):
        pdf_path = os.path.join(OUTPUT_DIR, f"{session_id}_copy{i}.pdf")
        img.save(pdf_path, "PDF", resolution=100.0)
        saved_paths.append(pdf_path)
        log(f"🖨️→📄 [테스트] PDF 저장: {pdf_path}")

    return saved_paths


# ===== 메인 루프 ================================================================
def process_job(job: dict):
    session_id = job["session_id"]
    download_url = job["download_url"]
    quantity = max(1, int(job.get("quantity", 1)))

    log(f"인쇄(목업) 시작: session_id={session_id}, quantity={quantity}")

    local_path = os.path.join(tempfile.gettempdir(), f"pikcha_{session_id}.jpg")
    download_image(download_url, local_path)
    save_as_pdf(local_path, session_id, copies=quantity)

    # ★ 실제 프린터 스풀 큐가 없어서 대기(wait_until_printed) 없이 바로 완료 처리.
    #   이 report_complete 호출이 Lambda의 /print-complete -> SMS 발송을 트리거함 -
    #   지금 확인하려는 게 바로 이 부분.
    report_complete(session_id)
    log(f"✅ 인쇄(목업) 완료 보고 ({quantity}장): session_id={session_id}")

    try:
        os.remove(local_path)
    except OSError:
        pass


def _record_failure(session_id: str, error: str):
    count = _job_failure_counts[session_id] = _job_failure_counts.get(session_id, 0) + 1
    log(f"⚠️  작업 실패 (session_id={session_id}, {count}/{MAX_RETRIES_PER_JOB}회): {error}")
    if count >= MAX_RETRIES_PER_JOB:
        _give_up_on_job(session_id, error)


def _give_up_on_job(session_id: str, error: str):
    """재시도 한도를 넘긴 작업을 서버에 실패로 신고해서 pending 큐(__PENDING_PRINTS__)에서
    제거되게 함. 신고 자체가 네트워크 문제로 실패하면 다음 폴링에서 다시 시도한다."""
    try:
        report_failed(session_id, error)
        log(f"🛑 반복 실패로 인쇄 포기, 서버에 실패 처리 완료: session_id={session_id}")
        _job_failure_counts.pop(session_id, None)
    except requests.RequestException as e:
        log(f"⚠️  실패 신고 중 네트워크 오류(다음 폴링에 재시도): session_id={session_id}, {e}")


def process_pending_jobs():
    """대기 중인 작업을 하나씩 처리. 한 작업이 실패해도 나머지 작업은 계속 처리되도록
    작업 단위로 예외를 잡는다."""
    for job in get_pending_jobs():
        session_id = job["session_id"]

        if _job_failure_counts.get(session_id, 0) >= MAX_RETRIES_PER_JOB:
            _give_up_on_job(session_id, "반복 실패")
            continue

        try:
            process_job(job)
            _job_failure_counts.pop(session_id, None)
        except requests.RequestException as e:
            _record_failure(session_id, str(e))
        except Exception as e:
            log(f"❌ 예상치 못한 오류 (session_id={session_id}):")
            traceback.print_exc()
            _record_failure(session_id, str(e))


def main():
    log(f"[테스트 모드 - PDF 저장] 인쇄 워커 시작. API_BASE={API_BASE}")
    log(f"[테스트 모드] PDF 저장 위치: {OUTPUT_DIR}")
    while True:
        try:
            process_pending_jobs()
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
