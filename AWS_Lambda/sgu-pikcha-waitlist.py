import json
import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import boto3

dynamodb = boto3.resource("dynamodb")

WAITLIST_TABLE_NAME = os.environ.get("WAITLIST_TABLE_NAME", "sgu-pikcha-waitinglist")
table = dynamodb.Table(WAITLIST_TABLE_NAME)

# 인화 상태(printStatus)를 같이 보여주기 위해 세션 테이블도 참조 (session_id가 연결된 경우에만)
SESSIONS_TABLE_NAME = os.environ.get("SESSIONS_TABLE_NAME", "sgu-pikcha-photobooth-sessions")
sessions_table = dynamodb.Table(SESSIONS_TABLE_NAME)

COUNTER_KEY = 0  # ticket_number=0은 카운터 전용 예약 아이템 (실제 순번은 1번부터)
AVG_MINUTES_PER_TEAM = float(os.environ.get("AVG_MINUTES_PER_TEAM", 6))


def handler(event, context):
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method", "")
    path = event.get("path") or event.get("rawPath", "")

    try:
        if path.endswith("/waitlist") and method == "POST":
            return _handle_register(event)
        if path.endswith("/waitlist/count") and method == "GET":
            return _handle_count()
        if path.endswith("/waitlist/now-serving") and method == "GET":
            return _handle_now_serving()
        if path.endswith("/waitlist/start-session") and method == "POST":
            return _handle_start_session(event)
        if path.endswith("/waitlist/advance") and method == "POST":
            return _handle_advance(event)
        if method == "GET":
            ticket_number = _extract_ticket_number(path)
            if ticket_number is not None:
                return _handle_lookup(ticket_number)
        return _response(404, {"error": f"경로를 찾을 수 없음: {method} {path}"})
    except Exception as e:
        print(f"❌ 에러: {e}")
        return _response(500, {"error": str(e)})


def _extract_ticket_number(path: str) -> int | None:
    """".../waitlist/123" 형태에서만 123을 뽑아냄. ".../waitlist/count"는 숫자가 아니라 여기 안 걸림."""
    parts = path.rstrip("/").split("/")
    if len(parts) >= 2 and parts[-2] == "waitlist":
        try:
            return int(parts[-1])
        except ValueError:
            return None
    return None


def _issue_ticket_number() -> int:
    """카운터를 원자적으로 1 증가시키고 새 값을 반환. 동시에 여러 팀이 등록해도
    절대 번호가 겹치지 않음 (중간에 실패해도 번호가 하나 건너뛸 뿐, 중복은 안 남)."""
    resp = table.update_item(
        Key={"ticket_number": COUNTER_KEY},
        UpdateExpression="SET #c = if_not_exists(#c, :zero) + :one",
        ExpressionAttributeNames={"#c": "counter"},
        ExpressionAttributeValues={":zero": 0, ":one": 1},
        ReturnValues="UPDATED_NEW",
    )
    return int(resp["Attributes"]["counter"])


def _handle_register(event):
    body = json.loads(event.get("body") or "{}")
    department = (body.get("department") or "").strip()
    student_id = (body.get("student_id") or "").strip()
    name = (body.get("name") or "").strip()
    phone_number = (body.get("phone_number") or "").strip()
    try:
        party_size = int(body.get("party_size"))
    except (TypeError, ValueError):
        party_size = 0

    if not department or not student_id or not name or not phone_number or party_size < 1:
        return _response(400, {
            "error": "department, student_id, name, phone_number, party_size(1 이상 정수)가 모두 필요합니다"
        })

    ticket_number = _issue_ticket_number()
    now = datetime.now(timezone.utc)
    capture_date = (now + timedelta(hours=9)).strftime("%Y-%m-%d")  # KST 기준 등록 날짜 (내년 참고용 원본 데이터)

    table.put_item(Item={
        "ticket_number": ticket_number,
        "status": "waiting",
        "department": department,
        "student_id": student_id,
        "name": name,
        "party_size": party_size,
        "phone_number": phone_number,
        "created_at": now.isoformat(),
        "capture_date": capture_date,
    })

    print(f"✅ 웨이팅 등록: ticket_number={ticket_number}, name={name}, party_size={party_size}")
    return _response(200, {"ticket_number": ticket_number})


def _teams_ahead(ticket_number: int) -> int:
    """status=waiting 이면서 내 번호보다 작은 아이템 수. 취소된(canceled) 팀은
    status가 waiting이 아니게 되므로 자동으로 제외됨."""
    resp = table.scan(
        FilterExpression="#s = :waiting AND ticket_number < :mine AND ticket_number > :zero",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":waiting": "waiting", ":mine": ticket_number, ":zero": COUNTER_KEY},
        Select="COUNT",
    )
    return resp["Count"]


def _handle_count():
    """웨이팅 디스플레이 태블릿용: 현재 대기중(waiting)인 팀 수."""
    resp = table.scan(
        FilterExpression="#s = :waiting AND ticket_number > :zero",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":waiting": "waiting", ":zero": COUNTER_KEY},
        Select="COUNT",
    )
    return _response(200, {"waiting_count": resp["Count"]})


def _handle_lookup(ticket_number: int):
    resp = table.get_item(Key={"ticket_number": ticket_number})
    item = resp.get("Item")
    if not item:
        return _response(404, {"error": "존재하지 않는 순번입니다"})

    result = {
        "ticket_number": ticket_number,
        "status": item.get("status"),
        "name": item.get("name"),
        "department": item.get("department"),
        "party_size": item.get("party_size"),
    }

    if item.get("status") == "waiting":
        ahead = _teams_ahead(ticket_number)
        result["teams_ahead"] = ahead
        result["estimated_wait_minutes"] = round(ahead * AVG_MINUTES_PER_TEAM)
    else:
        result["teams_ahead"] = 0
        result["estimated_wait_minutes"] = 0

    # session_id가 연결된 경우(호출 이후 촬영 단계와 배선되면 채워짐) 인화 상태도 같이 내려줌
    session_id = item.get("session_id")
    if session_id:
        session_item = sessions_table.get_item(Key={"session_id": session_id}).get("Item") or {}
        result["print_status"] = session_item.get("printStatus")
        result["sms_sent"] = session_item.get("sms_sent", False)

    return _response(200, result)


def _handle_start_session(event):
    """순번 입력 화면에서 호출. 등록된 번호면 순서 상관없이 통과시키고(대기열 순서 강제 안 함),
    이미 completed/canceled인 번호(다 찍었거나 취소된 번호 재사용)만 막는다.
    Personal_Info가 묻던 학과/학번/이름/전화번호를 여기서 그대로 돌려줘서 재입력을 없앤다."""
    body = json.loads(event.get("body") or "{}")
    try:
        ticket_number = int(body.get("ticket_number"))
    except (TypeError, ValueError):
        return _response(400, {"error": "ticket_number가 필요합니다"})

    item = table.get_item(Key={"ticket_number": ticket_number}).get("Item")
    if not item:
        return _response(404, {"error": "등록되지 않은 순번입니다"})

    status = item.get("status")
    if status in ("completed", "canceled"):
        return _response(400, {"error": f"이미 종료된 순번입니다 (status={status})"})

    table.update_item(
        Key={"ticket_number": ticket_number},
        UpdateExpression="SET #s = :in_session, session_started_at = :now",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":in_session": "in_session",
            ":now": datetime.now(timezone.utc).isoformat(),
        },
    )

    print(f"✅ 촬영 시작: ticket_number={ticket_number}")
    return _response(200, {
        "ticket_number": ticket_number,
        "department": item.get("department"),
        "student_id": item.get("student_id"),
        "name": item.get("name"),
        "party_size": item.get("party_size"),
        "phone_number": item.get("phone_number"),
    })


def _find_next_waiting_ticket() -> int | None:
    """status=waiting 중 가장 작은 ticket_number (취소된 번호는 status가 waiting이 아니라 자동 제외)."""
    resp = table.scan(
        FilterExpression="#s = :waiting AND ticket_number > :zero",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":waiting": "waiting", ":zero": COUNTER_KEY},
        ProjectionExpression="ticket_number",
    )
    items = resp.get("Items", [])
    if not items:
        return None
    return min(int(i["ticket_number"]) for i in items)


def _handle_advance(event):
    """촬영(4컷 캡처) 완료 시 app.py가 호출. 방금 끝난 팀을 photographed로 표시하고,
    남은 팀 중 가장 빠른 waiting 티켓을 찾아 called로 바꾸고 now_serving을 갱신한다.
    (진입 순서를 강제하진 않음 - 태블릿 표시용 값일 뿐)"""
    body = json.loads(event.get("body") or "{}")
    finished_ticket_number = body.get("ticket_number")

    if finished_ticket_number is not None:
        try:
            finished_ticket_number = int(finished_ticket_number)
            table.update_item(
                Key={"ticket_number": finished_ticket_number},
                UpdateExpression="SET #s = :photographed",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":photographed": "photographed"},
            )
        except (TypeError, ValueError):
            print(f"⚠️  [advance] ticket_number 형식이 이상함: {finished_ticket_number}")

    next_ticket = _find_next_waiting_ticket()
    if next_ticket is not None:
        table.update_item(
            Key={"ticket_number": next_ticket},
            UpdateExpression="SET #s = :called, called_at = :now",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":called": "called", ":now": datetime.now(timezone.utc).isoformat()},
        )
    table.update_item(
        Key={"ticket_number": COUNTER_KEY},
        UpdateExpression="SET now_serving = :n",
        ExpressionAttributeValues={":n": next_ticket if next_ticket is not None else 0},
    )

    print(f"➡️  대기열 진행: now_serving={next_ticket}")
    return _response(200, {"now_serving": next_ticket})


def _handle_now_serving():
    """웨이팅 태블릿용 공개 조회 - 개인정보 없이 숫자 하나만."""
    item = table.get_item(Key={"ticket_number": COUNTER_KEY}).get("Item") or {}
    return _response(200, {"now_serving": int(item.get("now_serving", 0))})


def _decimal_default(obj):
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return str(obj)


def _response(status_code: int, body_dict: dict):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body_dict, default=_decimal_default),
    }
