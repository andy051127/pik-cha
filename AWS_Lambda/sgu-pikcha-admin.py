import hashlib
import hmac
import json
import os
import base64
import secrets
import urllib.error
import urllib.request
import boto3
from datetime import datetime, timezone
from decimal import Decimal

dynamodb = boto3.resource("dynamodb")
DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "sgu-pikcha-photobooth-sessions")
table = dynamodb.Table(DYNAMODB_TABLE_NAME)

# 웨이팅리스트 관리 화면용 - sgu-pikcha-waitlist.py가 쓰는 테이블과 동일
WAITLIST_TABLE_NAME = os.environ.get("WAITLIST_TABLE_NAME", "sgu-pikcha-waitinglist")
waitlist_table = dynamodb.Table(WAITLIST_TABLE_NAME)

STATS_KEY = "__STATS__"
PENDING_PRINTS_KEY = "__PENDING_PRINTS__"
WAITLIST_COUNTER_KEY = 0
RESERVED_SESSION_KEYS = {STATS_KEY, PENDING_PRINTS_KEY}

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

# ── SOLAPI (SMS 재발송용) - sgu-pikcha-print.py의 설정/로직과 동일하게 유지 ──────
SOLAPI_API_KEY = os.environ.get("SOLAPI_API_KEY", "")
SOLAPI_API_SECRET = os.environ.get("SOLAPI_API_SECRET", "")
SOLAPI_SENDER_NUMBER = os.environ.get("SOLAPI_SENDER_NUMBER", "")
SOLAPI_SEND_URL = "https://api.solapi.com/messages/v4/send"


def handler(event, context):
    if not _check_basic_auth(event):
        return _response(
            401,
            {"error": "인증이 필요합니다"},
            extra_headers={"WWW-Authenticate": 'Basic realm="Photobooth Admin"'},
        )

    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method", "")
    path = event.get("path") or event.get("rawPath", "")

    try:
        if path.endswith("/admin/sessions") and method == "GET":
            return _handle_sessions(event)
        if path.endswith("/admin/stats") and method == "GET":
            return _handle_stats(event)
        if path.endswith("/admin/waitlist") and method == "GET":
            return _handle_admin_waitlist(event)
        if path.endswith("/admin/print-status") and method == "GET":
            return _handle_print_status()
        if path.endswith("/admin/print/reprint") and method == "POST":
            return _handle_reprint(event)
        if path.endswith("/admin/sms/resend") and method == "POST":
            return _handle_resend_sms(event)
        return _response(404, {"error": f"경로를 찾을 수 없음: {method} {path}"})
    except Exception as e:
        print(f"❌ 에러: {e}")
        return _response(500, {"error": str(e)})


def _check_basic_auth(event) -> bool:
    if not ADMIN_USERNAME or not ADMIN_PASSWORD:
        print("⚠️  ADMIN_USERNAME/ADMIN_PASSWORD 환경변수가 설정 안 됨 - 접근 전면 차단")
        return False

    headers = event.get("headers") or {}
    auth_header = headers.get("Authorization") or headers.get("authorization")
    if not auth_header or not auth_header.startswith("Basic "):
        return False

    try:
        encoded = auth_header.split(" ", 1)[1]
        decoded = base64.b64decode(encoded).decode("utf-8")
        username, _, password = decoded.partition(":")
    except Exception:
        return False

    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD


def _get_stats_item() -> dict:
    resp = table.get_item(Key={"session_id": STATS_KEY})
    return resp.get("Item", {
        "total_sessions": 0,
        "by_date": {},
        "download_issued_count": 0,
        "recent_sessions": [],
    })


def _handle_sessions(event):
    params = event.get("queryStringParameters") or {}
    limit = int(params.get("limit", 50))

    stats = _get_stats_item()
    sessions = stats.get("recent_sessions", [])[:limit]

    return _response(200, {"sessions": sessions})


def _handle_stats(event):
    stats = _get_stats_item()

    return _response(
        200,
        {
            "total_sessions": int(stats.get("total_sessions", 0)),
            "by_date": stats.get("by_date", {}),
            "download_issued_count": int(stats.get("download_issued_count", 0)),
        },
    )

def _handle_admin_waitlist(event):
    """웨이팅리스트 관리 화면용 - 전체 목록(카운터 아이템 제외)을 순번순으로 반환.
    ?status=waiting,called 처럼 콤마로 필터 가능 (안 주면 전체)."""
    params = event.get("queryStringParameters") or {}
    status_filter = params.get("status")
    wanted = set(status_filter.split(",")) if status_filter else None

    resp = waitlist_table.scan(
        FilterExpression="ticket_number > :zero",
        ExpressionAttributeValues={":zero": WAITLIST_COUNTER_KEY},
    )
    items = resp.get("Items", [])
    if wanted:
        items = [i for i in items if i.get("status") in wanted]
    items.sort(key=lambda i: int(i["ticket_number"]))

    return _response(200, {"waitlist": items})


def _handle_print_status():
    """인화 상태 관리 화면용 - 세션 테이블 전체(싱글턴 키 제외)를 최신순으로 반환."""
    resp = table.scan()
    items = [i for i in resp.get("Items", []) if i.get("session_id") not in RESERVED_SESSION_KEYS]
    items.sort(key=lambda i: i.get("created_at", ""), reverse=True)

    return _response(200, {"sessions": items})


def _handle_reprint(event):
    """인쇄가 잘못됐을 때 관리자가 수동으로 다시 인쇄 큐에 넣는다.
    print_worker.py가 쓰는 __PENDING_PRINTS__ 큐에 job을 하나 더 추가하는 것뿐이라
    프린터 쪽 코드는 전혀 안 건드려도 됨 - 다음 폴링에서 자동으로 집어감."""
    body = json.loads(event.get("body") or "{}")
    session_id = body.get("session_id")
    if not session_id:
        return _response(400, {"error": "session_id가 필요합니다"})

    session_item = table.get_item(Key={"session_id": session_id}).get("Item")
    if not session_item:
        return _response(404, {"error": "세션을 찾을 수 없습니다"})

    bucket = session_item.get("bucket")
    key = session_item.get("fourcut_key")
    if not bucket or not key:
        return _response(400, {"error": "이 세션은 아직 업로드가 완료되지 않아 재인쇄할 수 없습니다"})

    quantity = int(body.get("quantity") or session_item.get("printQuantity", 1))

    table.update_item(
        Key={"session_id": PENDING_PRINTS_KEY},
        UpdateExpression="SET jobs = if_not_exists(jobs, :empty_list)",
        ExpressionAttributeValues={":empty_list": []},
    )
    table.update_item(
        Key={"session_id": PENDING_PRINTS_KEY},
        UpdateExpression="SET jobs = list_append(jobs, :new_job)",
        ExpressionAttributeValues={
            ":new_job": [{"session_id": session_id, "bucket": bucket, "key": key, "quantity": quantity}]
        },
    )
    table.update_item(
        Key={"session_id": session_id},
        UpdateExpression="SET printStatus = :pending",
        ExpressionAttributeValues={":pending": "pending"},
    )

    print(f"🔁 재인쇄 큐 등록: session_id={session_id}, quantity={quantity}")
    return _response(200, {"status": "queued", "session_id": session_id, "quantity": quantity})


def _handle_resend_sms(event):
    """인화완료 SMS가 잘못 갔거나 안 갔을 때 관리자가 수동으로 재발송.
    sms_sent 플래그를 무시하고 강제로 다시 보낸다는 점이 print.py의 자동발송과 다름."""
    body = json.loads(event.get("body") or "{}")
    session_id = body.get("session_id")
    if not session_id:
        return _response(400, {"error": "session_id가 필요합니다"})

    session_item = table.get_item(Key={"session_id": session_id}).get("Item")
    if not session_item:
        return _response(404, {"error": "세션을 찾을 수 없습니다"})

    phone_number = session_item.get("phoneNumber", "")
    if not phone_number:
        return _response(400, {"error": "이 세션엔 전화번호가 없습니다"})

    name = session_item.get("name", "")
    text = f"[Pik-Cha!] {name + '님, ' if name else ''}사진 인화가 완료됐어요! 부스에서 수령해주세요 :)"

    if not _send_sms(phone_number, text):
        return _response(502, {"error": "SMS 발송에 실패했습니다"})

    table.update_item(
        Key={"session_id": session_id},
        UpdateExpression="SET sms_sent = :true, sms_resent_at = :now",
        ExpressionAttributeValues={":true": True, ":now": datetime.now(timezone.utc).isoformat()},
    )

    print(f"✅ [관리자] SMS 재발송: session_id={session_id}")
    return _response(200, {"status": "sent", "session_id": session_id})


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
        "message": {"to": phone_number, "from": SOLAPI_SENDER_NUMBER, "text": text, "type": "SMS"}
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


def _decimal_default(obj):
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return str(obj)

def _response(status_code: int, body_dict: dict, extra_headers: dict | None = None):
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
    }
    if extra_headers:
        headers.update(extra_headers)
    return {
        "statusCode": status_code,
        "headers": headers,
        "body": json.dumps(body_dict, default=_decimal_default),   # ← default=str → default=_decimal_default
    }