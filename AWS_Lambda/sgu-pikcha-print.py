import hashlib
import hmac
import json
import os
import secrets
import urllib.request
from datetime import datetime, timezone
import boto3

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "sgu-pikcha-photobooth-sessions")
table = dynamodb.Table(DYNAMODB_TABLE_NAME)
DOWNLOAD_URL_EXPIRES_SECONDS = int(os.environ.get("DOWNLOAD_URL_EXPIRES_SECONDS", 300))

PENDING_PRINTS_KEY = "__PENDING_PRINTS__"

# ── SOLAPI (SMS) 설정 ──────────────────────────────────────────
SOLAPI_API_KEY = os.environ.get("SOLAPI_API_KEY", "")
SOLAPI_API_SECRET = os.environ.get("SOLAPI_API_SECRET", "")
SOLAPI_SENDER_NUMBER = os.environ.get("SOLAPI_SENDER_NUMBER", "")  # 사전등록 승인된 발신번호
SOLAPI_SEND_URL = "https://api.solapi.com/messages/v4/send"


def handler(event, context):
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method", "")
    path = event.get("path") or event.get("rawPath", "")

    try:
        if path.endswith("/print-jobs") and method == "GET":
            return _handle_print_jobs()
        if path.endswith("/print-complete") and method == "POST":
            return _handle_print_complete(event)
        if path.endswith("/print-failed") and method == "POST":
            return _handle_print_failed(event)
        return _response(404, {"error": f"경로를 찾을 수 없음: {method} {path}"})
    except Exception as e:
        print(f"❌ 에러: {e}")
        return _response(500, {"error": str(e)})


def _handle_print_jobs():
    """print_worker.py가 폴링하는 엔드포인트. __PENDING_PRINTS__ 리스트를 읽어서
    각 job마다 즉석에서 presigned 다운로드 URL을 발급해 같이 내려줌."""
    resp = table.get_item(Key={"session_id": PENDING_PRINTS_KEY})
    jobs = resp.get("Item", {}).get("jobs", [])

    result = []
    for job in jobs:
        download_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": job["bucket"], "Key": job["key"]},
            ExpiresIn=DOWNLOAD_URL_EXPIRES_SECONDS,
        )
        result.append({
            "session_id": job["session_id"],
            "download_url": download_url,
            "quantity": int(job.get("quantity", 1)),
        })

    return _response(200, {"jobs": result})


def _remove_pending_job(session_id: str):
    """__PENDING_PRINTS__.jobs에서 이 session_id만 제거하고 다시 씀."""
    resp = table.get_item(Key={"session_id": PENDING_PRINTS_KEY})
    jobs = resp.get("Item", {}).get("jobs", [])
    remaining = [j for j in jobs if j.get("session_id") != session_id]

    table.update_item(
        Key={"session_id": PENDING_PRINTS_KEY},
        UpdateExpression="SET jobs = :remaining",
        ExpressionAttributeValues={":remaining": remaining},
    )


def _handle_print_complete(event):
    body = json.loads(event.get("body") or "{}")
    session_id = body.get("session_id")
    if not session_id:
        return _response(400, {"error": "session_id가 필요합니다"})

    now = datetime.now(timezone.utc)
    # ReturnValues=ALL_NEW로 갱신 직후 값을 그대로 받아옴 - phoneNumber/sms_sent
    # 조회하려고 get_item을 따로 또 부를 필요 없음
    updated = table.update_item(
        Key={"session_id": session_id},
        UpdateExpression="SET printStatus = :printed, printedAt = :now",
        ExpressionAttributeValues={":printed": "printed", ":now": now.isoformat()},
        ReturnValues="ALL_NEW",
    )

    _remove_pending_job(session_id)

    _notify_print_complete(session_id, updated.get("Attributes", {}))

    print(f"🖨️ 인쇄 완료 처리: session_id={session_id}")
    return _response(200, {"status": "ok"})


def _notify_print_complete(session_id: str, session_item: dict):
    """인화 완료 SMS 발송. 이미 보냈거나(sms_sent) 전화번호가 없으면 건너뜀.
    SMS 발송 실패가 인쇄완료 처리 자체를 실패시키면 안 되므로 예외를 삼킨다
    (재발송은 관리자페이지의 SMS 재발송 기능으로 커버 예정)."""
    if session_item.get("sms_sent"):
        return

    phone_number = session_item.get("phoneNumber", "")
    if not phone_number:
        print(f"ℹ️  [SMS] 전화번호 없음 - 발송 건너뜀: session_id={session_id}")
        return

    name = session_item.get("name", "")
    text = f"[Pik-Cha!] {name + '님, ' if name else ''}사진 인화가 완료됐어요! 부스에서 수령해주세요 :)"

    if _send_sms(phone_number, text):
        table.update_item(
            Key={"session_id": session_id},
            UpdateExpression="SET sms_sent = :true, sms_sent_at = :now",
            ExpressionAttributeValues={":true": True, ":now": datetime.now(timezone.utc).isoformat()},
        )
        print(f"✅ [SMS] 인화완료 문자 발송: session_id={session_id}")


def _solapi_auth_header() -> str:
    date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    salt = secrets.token_hex(16)
    signature = hmac.new(
        SOLAPI_API_SECRET.encode("utf-8"), (date + salt).encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return f"HMAC-SHA256 apiKey={SOLAPI_API_KEY}, date={date}, salt={salt}, signature={signature}"


def _send_sms(phone_number: str, text: str) -> bool:
    if not SOLAPI_API_KEY or not SOLAPI_API_SECRET or not SOLAPI_SENDER_NUMBER:
        print("⚠️  [SMS] SOLAPI_API_KEY/SECRET/SENDER_NUMBER 환경변수 미설정 - 발송 건너뜀")
        return False

    payload = json.dumps({
        "message": {
            "to": phone_number,
            "from": SOLAPI_SENDER_NUMBER,
            "text": text,
            "type": "SMS",
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        SOLAPI_SEND_URL,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": _solapi_auth_header(),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
        return True
    except Exception as e:
        print(f"⚠️  [SMS] 발송 실패: {e}")
        return False


def _handle_print_failed(event):
    """print_worker.py가 재시도 한도를 넘긴 복구 불가능한 작업을 신고하는 엔드포인트.
    상태를 'failed'로 남기고 pending 큐에서 제거해서 무한 재시도를 막는다."""
    body = json.loads(event.get("body") or "{}")
    session_id = body.get("session_id")
    error = body.get("error", "")
    if not session_id:
        return _response(400, {"error": "session_id가 필요합니다"})

    now = datetime.now(timezone.utc)
    table.update_item(
        Key={"session_id": session_id},
        UpdateExpression="SET printStatus = :failed, printFailedAt = :now, printError = :error",
        ExpressionAttributeValues={
            ":failed": "failed",
            ":now": now.isoformat(),
            ":error": error,
        },
    )

    _remove_pending_job(session_id)

    print(f"⚠️ 인쇄 실패 처리: session_id={session_id}, error={error}")
    return _response(200, {"status": "ok"})


def _response(status_code: int, body_dict: dict):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body_dict),
    }
