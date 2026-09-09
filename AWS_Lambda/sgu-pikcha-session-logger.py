import json
import urllib.parse
from datetime import datetime, timezone
import os
import boto3

dynamodb = boto3.resource("dynamodb")
DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "sgu-pikcha-photobooth-sessions")
table = dynamodb.Table(DYNAMODB_TABLE_NAME)

STATS_KEY = "__STATS__"
PENDING_PRINTS_KEY = "__PENDING_PRINTS__"
RECENT_SESSIONS_LIMIT = 50


def handler(event, context):
    processed = 0
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        object_size = record["s3"]["object"].get("size", 0)

        parts = key.split("/")
        if len(parts) < 3 or parts[0] != "sessions":
            print(f"예상 밖의 key 형식이라 건너뜀: {key}")
            continue
        session_id = parts[1]

        now = datetime.now(timezone.utc)
        capture_date = now.strftime("%Y-%m-%d")

        # put_item(전체 덮어쓰기) 대신 update_item 사용: presign이 /upload-url 시점에
        # 먼저 기록해둔 name/phoneNumber/printQuantity를 여기서 덮어써버리면 안 되기 때문
        updated = table.update_item(
            Key={"session_id": session_id},
            UpdateExpression="""
                SET #bucket = :bucket,
                    fourcut_key = :key,
                    file_size_bytes = :size,
                    created_at = if_not_exists(created_at, :now),
                    capture_date = if_not_exists(capture_date, :capture_date),
                    download_url_issued = if_not_exists(download_url_issued, :false),
                    sms_sent = if_not_exists(sms_sent, :false),
                    printStatus = if_not_exists(printStatus, :pending),
                    printQuantity = if_not_exists(printQuantity, :one),
                    #name = if_not_exists(#name, :empty_str),
                    phoneNumber = if_not_exists(phoneNumber, :empty_str)
            """,
            # "bucket"은 DynamoDB 예약어라 표현식에 그대로 쓰면 ValidationException 남 —
            # put_item에서 update_item으로 바꾸면서 처음 겪은 이슈
            ExpressionAttributeNames={"#name": "name", "#bucket": "bucket"},
            ExpressionAttributeValues={
                ":bucket": bucket,
                ":key": key,
                ":size": object_size,
                ":now": now.isoformat(),
                ":capture_date": capture_date,
                ":false": False,
                ":pending": "pending",
                ":one": 1,
                ":empty_str": "",
            },
            ReturnValues="ALL_NEW",
        )
        print(f"✅ DynamoDB 기록 완료: session_id={session_id}, key={key}")

        print_quantity = int(updated.get("Attributes", {}).get("printQuantity", 1))

        _update_stats(session_id, capture_date, now, object_size)
        _add_pending_print(session_id, bucket, key, print_quantity)
        processed += 1

    return {"statusCode": 200, "body": json.dumps({"processed": processed})}


def _update_stats(session_id: str, capture_date: str, now: datetime, object_size: int):
    """__STATS__ 집계 아이템을 갱신 (admin_lambda가 GetItem 한 번으로 읽어가는 구조)"""

    table.update_item(
        Key={"session_id": STATS_KEY},
        UpdateExpression="""
            SET by_date = if_not_exists(by_date, :empty_map),
                recent_sessions = if_not_exists(recent_sessions, :empty_list),
                total_sessions = if_not_exists(total_sessions, :zero)
        """,
        ExpressionAttributeValues={
            ":empty_map": {},
            ":empty_list": [],
            ":zero": 0,
        },
    )

    new_session_entry = [{
        "session_id": session_id,
        "created_at": now.isoformat(),
        "capture_date": capture_date,
    }]

    table.update_item(
        Key={"session_id": STATS_KEY},
        UpdateExpression="""
            SET recent_sessions = list_append(:new_session, recent_sessions),
                by_date.#date = if_not_exists(by_date.#date, :zero) + :one
            ADD total_sessions :one
        """,
        ExpressionAttributeNames={"#date": capture_date},
        ExpressionAttributeValues={
            ":one": 1,
            ":zero": 0,
            ":new_session": new_session_entry,
        },
    )

    resp = table.get_item(Key={"session_id": STATS_KEY})
    recent = resp.get("Item", {}).get("recent_sessions", [])
    if len(recent) > RECENT_SESSIONS_LIMIT:
        table.update_item(
            Key={"session_id": STATS_KEY},
            UpdateExpression="SET recent_sessions = :trimmed",
            ExpressionAttributeValues={":trimmed": recent[:RECENT_SESSIONS_LIMIT]},
        )
    print(f"📊 통계 갱신 완료: session_id={session_id}")


def _add_pending_print(session_id: str, bucket: str, key: str, quantity: int = 1):
    """__PENDING_PRINTS__ 집계 아이템에 인쇄 대기 job 추가.
    print_worker.py가 GET /print-jobs로 이 리스트를 폴링해서 인쇄를 진행함.
    quantity: Number_of_Prints에서 고른 매수 - print_worker.py가 이 매수만큼 반복 인쇄."""

    table.update_item(
        Key={"session_id": PENDING_PRINTS_KEY},
        UpdateExpression="SET jobs = if_not_exists(jobs, :empty_list)",
        ExpressionAttributeValues={":empty_list": []},
    )

    new_job = [{
        "session_id": session_id,
        "bucket": bucket,
        "key": key,
        "quantity": quantity,
    }]

    table.update_item(
        Key={"session_id": PENDING_PRINTS_KEY},
        UpdateExpression="SET jobs = list_append(jobs, :new_job)",
        ExpressionAttributeValues={":new_job": new_job},
    )
    print(f"🖨️ 인쇄 대기열에 추가: session_id={session_id}")
