"""
로컬 앱과 AWS를 연결하는 모듈.

★ 학교/기관 AWS 정책: Access Key 발급 절대 불가, IAM Role만 허용.
  그래서 이 모듈은 boto3로 AWS에 직접 인증하지 않는다. 대신:

    1. API Gateway(Lambda가 SafeRole-sgu-yaksok을 IAM Role로 사용)에
       "이 파일들 업로드할 presigned URL 줘"라고 평범한 HTTP 요청을 보낸다.
    2. Lambda가 그 Role의 권한으로 presigned PUT/GET URL을 서명해서 응답해준다.
    3. 로컬 PC는 그 URL로 순수 HTTP PUT만 하면 된다 - AWS 자격증명 전혀 필요 없음.

  실제 DynamoDB 로그 기록은 이 모듈이 하지 않는다. S3 업로드가 완료되면
  S3 Event Notification이 별도 Lambda(session_logger_lambda.py)를 트리거해서
  거기서 기록한다 (요청서에 명시된 대로, 업로드 경로와 무관하게 로그가 남도록).

환경변수:
  API_GATEWAY_URL - 발급받은 API Gateway invoke URL
                     (예: https://xxxx.execute-api.ap-northeast-2.amazonaws.com/prod)
                     비어있으면 '로컬 테스트 모드'로 동작 (AWS 없이 로컬 네트워크 QR).

필요 패키지: pip install requests python-dotenv qrcode[pil]
  (boto3는 로컬 쪽에서는 더 이상 필요 없음 - Lambda 쪽에서만 씀)
"""

import os
import io
import socket
import base64
import uuid
import requests
from datetime import datetime, timezone

import qr_compositor

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

API_GATEWAY_URL = os.environ.get("API_GATEWAY_URL", "").rstrip("/")
LOCAL_TEST_PORT = int(os.environ.get("LOCAL_TEST_PORT", 8000))
REQUEST_TIMEOUT = 10  # 초


def make_session_id() -> str:
    """예: 20260727-153012-a1b2c3"""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    short_uuid = uuid.uuid4().hex[:6]
    return f"{timestamp}-{short_uuid}"


def _get_local_lan_ip() -> str:
    """같은 와이파이의 휴대폰이 접속 가능한 이 PC의 LAN IP (로컬 테스트 모드용)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except OSError:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def _request_upload_urls(
    session_id: str,
    filenames: list[str],
    name: str | None = None,
    phone_number: str | None = None,
) -> dict | None:
    """
    API Gateway -> presign_lambda 호출해서 여러 파일의 presigned PUT URL을 한 번에 받는다.
    반환: {"files": {filename: {"upload_url":..., "key":...}, ...}} 또는 실패 시 None

    ★ name/phone_number: Personal_Info에서 입력한 값. 여기서 보내는 JSON body에
      실어 보내지만, 이 값이 실제로 DynamoDB에 저장되려면 이 요청을 받는
      presign_lambda(또는 세션을 기록하는 다른 Lambda)가 이 필드를 읽어서
      DynamoDB에 써주도록 AWS 쪽 코드도 같이 수정해야 한다.
    """
    try:
        body = {"session_id": session_id, "filenames": filenames}
        if name:
            body["name"] = name
        if phone_number:
            body["phone_number"] = phone_number
        resp = requests.post(
            f"{API_GATEWAY_URL}/upload-url",
            json=body,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        print(f"⚠️  [API] presigned 업로드 URL 요청 실패: {e}")
        return None


def _request_download_url(key: str) -> str | None:
    """API Gateway -> presign_lambda 호출해서 QR에 넣을 presigned GET URL을 받는다."""
    try:
        resp = requests.get(
            f"{API_GATEWAY_URL}/download-url",
            params={"key": key},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("download_url")
    except requests.RequestException as e:
        print(f"⚠️  [API] presigned 다운로드 URL 요청 실패: {e}")
        return None


def _put_file(upload_url: str, local_path: str, content_type: str = "image/jpeg") -> bool:
    """presigned PUT URL로 순수 HTTP 업로드 (AWS 자격증명 불필요)."""
    try:
        with open(local_path, "rb") as f:
            data = f.read()
        resp = requests.put(
            upload_url, data=data, headers={"Content-Type": content_type}, timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        print(f"✅ [S3] 업로드 완료: {local_path}")
        return True
    except (requests.RequestException, OSError) as e:
        print(f"⚠️  [S3] 업로드 실패: {e}")
        return False


def create_local_test_qr() -> dict:
    """
    API_GATEWAY_URL이 설정 안 돼있을 때 쓰는 '로컬 테스트 모드'.
    실제 업로드는 하지 않고, 같은 와이파이의 휴대폰이 이 PC에 직접 접속할 수
    있는 로컬 네트워크 주소로 QR을 만든다. AWS 설정 없이 QR 팝업/스캔 흐름을
    그대로 테스트할 수 있다.
    """
    lan_ip = _get_local_lan_ip()
    test_url = f"http://{lan_ip}:{LOCAL_TEST_PORT}/api/fourcut/result"

    qr_img = qr_compositor.make_qr_image(test_url)
    buf = io.BytesIO()
    qr_img.save(buf, format="PNG")
    qr_base64 = base64.b64encode(buf.getvalue()).decode("ascii")

    print(f"ℹ️  [로컬 테스트 모드] API_GATEWAY_URL 미설정 - QR이 로컬 네트워크 주소를 가리킵니다: {test_url}")
    print(f"    (휴대폰이 이 PC와 같은 와이파이에 있어야 스캔했을 때 사진이 보여요)")

    return {"mode": "local_test", "test_url": test_url, "qr_base64": qr_base64}


def upload_fourcut_session(
    cut_paths: list[str],
    fourcut_path: str,
    name: str | None = None,
    phone_number: str | None = None,
) -> dict | None:
    """
    한 세션의 개별 컷 4장 + 합성본 1장을 presigned URL로 S3에 업로드하고,
    다운로드용 QR도 만든다 (전부 Access Key 없이, API Gateway 경유).

    ★ API_GATEWAY_URL이 설정 안 되어 있으면 '로컬 테스트 모드'로 빠진다.

    반환값 예 (AWS 연동된 경우):
    {
        "session_id": "20260727-153012-a1b2c3",
        "cut_keys": ["sessions/.../cut_1.jpg", ...],
        "fourcut_key": "sessions/.../fourcut.jpg",
        "qr_base64": "...",              # 화면에 바로 표시할 base64
        "presigned_url": "https://...",  # QR에 들어간 실제 다운로드 링크
    }

    반환값 예 (로컬 테스트 모드):
    {
        "mode": "local_test",
        "test_url": "http://192.168.0.5:8000/api/fourcut/result",
        "qr_base64": "...",
    }

    업로드 자체가 실패하면 None. QR 발급만 실패하면 그 부분만 빠지고 나머지는 반환.
    """
    if not API_GATEWAY_URL:
        return create_local_test_qr()

    session_id = make_session_id()
    cut_filenames = [f"cut_{i}.jpg" for i in range(1, len(cut_paths) + 1)]
    all_filenames = cut_filenames + ["fourcut.jpg"]

    presign_result = _request_upload_urls(session_id, all_filenames, name, phone_number)
    if not presign_result or "files" not in presign_result:
        print("⚠️  [API] presigned URL 발급 실패 - 업로드 중단")
        return None

    files_info = presign_result["files"]

    cut_keys = []
    for path, filename in zip(cut_paths, cut_filenames):
        info = files_info.get(filename)
        if not info:
            print(f"⚠️  {filename}의 presigned URL이 응답에 없음")
            return None
        if not _put_file(info["upload_url"], path):
            return None
        cut_keys.append(info["key"])

    fourcut_info = files_info.get("fourcut.jpg")
    if not fourcut_info:
        print("⚠️  fourcut.jpg의 presigned URL이 응답에 없음")
        return None
    if not _put_file(fourcut_info["upload_url"], fourcut_path):
        return None
    fourcut_key = fourcut_info["key"]

    result = {
        "session_id": session_id,
        "cut_keys": cut_keys,
        "fourcut_key": fourcut_key,
    }

    # ★ QR: presigned 다운로드 URL은 Lambda에서 받아오고, QR 이미지 자체는 로컬에서 생성
    download_url = _request_download_url(fourcut_key)
    if download_url:
        qr_img = qr_compositor.make_qr_image(download_url)
        buf = io.BytesIO()
        qr_img.save(buf, format="PNG")
        result["qr_base64"] = base64.b64encode(buf.getvalue()).decode("ascii")
        result["presigned_url"] = download_url
        print("✅ [QR] QR 생성 완료 (사진과 합성하지 않고 화면 표시용)")
    else:
        print("⚠️  [QR] 다운로드 URL 발급 실패 - QR 없이 사진 업로드만 완료됨")

    return result
