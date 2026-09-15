import hashlib
import hmac
import json
import os
import secrets
import urllib.request
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

# ── SOLAPI (SMS) 설정 - sgu-pikcha-print.py와 동일한 설정/로직 ──────────────────
SOLAPI_API_KEY = os.environ.get("SOLAPI_API_KEY", "")
SOLAPI_API_SECRET = os.environ.get("SOLAPI_API_SECRET", "")
SOLAPI_SENDER_NUMBER = os.environ.get("SOLAPI_SENDER_NUMBER", "")
SOLAPI_SEND_URL = "https://api.solapi.com/messages/v4/send"


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
        if path.endswith("/waitlist/cancel") and method == "POST":
            return _handle_cancel(event)
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

    # ★ 다음 팀 호출 시점을 "촬영 완료"가 아니라 "촬영 시작"으로 당김 - 이 팀이
    #   촬영~합성~인쇄까지 진행하는 동안 다음 팀이 미리 부스로 이동할 시간을 벌어줌
    _call_next_and_notify()

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


def _call_next_and_notify() -> int | None:
    """남은 팀 중 가장 빠른 waiting 티켓을 찾아 called로 바꾸고 now_serving을 갱신 +
    그 팀에게 SMS 발송. (진입 순서를 강제하진 않음 - now_serving은 표시/안내용일 뿐)
    호출된 티켓 번호(없으면 None)를 반환."""
    next_ticket = _find_next_waiting_ticket()

    if next_ticket is None:
        table.update_item(
            Key={"ticket_number": COUNTER_KEY},
            UpdateExpression="SET now_serving = :n",
            ExpressionAttributeValues={":n": 0},
        )
        return None

    updated = table.update_item(
        Key={"ticket_number": next_ticket},
        UpdateExpression="SET #s = :called, called_at = :now",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":called": "called", ":now": datetime.now(timezone.utc).isoformat()},
        ReturnValues="ALL_NEW",
    )
    table.update_item(
        Key={"ticket_number": COUNTER_KEY},
        UpdateExpression="SET now_serving = :n",
        ExpressionAttributeValues={":n": next_ticket},
    )

    item = updated.get("Attributes", {})
    phone_number = item.get("phone_number", "")
    if phone_number:
        name = item.get("name", "")
        text = f"[Pik-Cha!] {name + '님, ' if name else ''}곧 손님 차례예요! 부스로 와주세요 :)"
        _send_sms(phone_number, text)

    print(f"➡️  대기열 진행: now_serving={next_ticket}")
    return next_ticket


def _handle_advance(event):
    """촬영(4컷 캡처) 완료 시 app.py가 호출. 방금 끝난 팀을 photographed로 표시만 한다.
    ★ 다음 팀 호출은 더 이상 여기서 안 함 - start-session(촬영 시작 시점)으로 옮겨감,
    그래야 다음 팀이 이 팀의 촬영~인쇄 시간 동안 미리 이동할 시간을 벌 수 있음."""
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

    return _response(200, {"status": "ok"})


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
        print(f"✅ [SMS] 다음팀 호출 문자 발송: to={phone_number}")
        return True
    except Exception as e:
        print(f"⚠️  [SMS] 발송 실패: {e}")
        return False


def _handle_cancel(event):
    """웨이팅 유저페이지의 '취소하기' 버튼 + 관리자 웨이팅리스트 관리 화면 둘 다에서 쓰는
    공용 취소 엔드포인트. 아직 촬영 시작 전(waiting/called)인 번호만 취소 가능 -
    이미 촬영중/완료된 번호는 취소해봐야 의미가 없으므로 막는다."""
    body = json.loads(event.get("body") or "{}")
    try:
        ticket_number = int(body.get("ticket_number"))
    except (TypeError, ValueError):
        return _response(400, {"error": "ticket_number가 필요합니다"})

    item = table.get_item(Key={"ticket_number": ticket_number}).get("Item")
    if not item:
        return _response(404, {"error": "존재하지 않는 순번입니다"})

    status = item.get("status")
    if status not in ("waiting", "called"):
        return _response(400, {"error": f"이미 진행된 순번은 취소할 수 없습니다 (status={status})"})

    table.update_item(
        Key={"ticket_number": ticket_number},
        UpdateExpression="SET #s = :canceled, canceled_at = :now",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":canceled": "canceled", ":now": datetime.now(timezone.utc).isoformat()},
    )

    print(f"🛑 웨이팅 취소: ticket_number={ticket_number}")
    return _response(200, {"ticket_number": ticket_number, "status": "canceled"})


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
