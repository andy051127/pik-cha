import json
import os
import base64
import boto3
from decimal import Decimal

dynamodb = boto3.resource("dynamodb")
DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "sgu-pikcha-photobooth-sessions")
table = dynamodb.Table(DYNAMODB_TABLE_NAME)

STATS_KEY = "__STATS__"

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")


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