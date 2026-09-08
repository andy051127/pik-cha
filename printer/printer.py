import json
import os
from datetime import datetime, timezone
import boto3

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "sgu-pikcha-photobooth-sessions")
table = dynamodb.Table(DYNAMODB_TABLE_NAME)
DOWNLOAD_URL_EXPIRES_SECONDS = int(os.environ.get("DOWNLOAD_URL_EXPIRES_SECONDS", 300))

PENDING_PRINTS_KEY = "__PENDING_PRINTS__"


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
    table.update_item(
        Key={"session_id": session_id},
        UpdateExpression="SET printStatus = :printed, printedAt = :now",
        ExpressionAttributeValues={":printed": "printed", ":now": now.isoformat()},
    )

    _remove_pending_job(session_id)

    print(f"🖨️ 인쇄 완료 처리: session_id={session_id}")
    return _response(200, {"status": "ok"})


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
