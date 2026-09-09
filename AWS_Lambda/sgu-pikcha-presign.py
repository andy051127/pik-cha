import json
import os
import boto3

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

S3_BUCKET_NAME = os.environ["S3_BUCKET_NAME"]
DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "sgu-pikcha-photobooth-sessions")
table = dynamodb.Table(DYNAMODB_TABLE_NAME)
UPLOAD_URL_EXPIRES_SECONDS = int(os.environ.get("UPLOAD_URL_EXPIRES_SECONDS", 300))
DOWNLOAD_URL_EXPIRES_SECONDS = int(os.environ.get("DOWNLOAD_URL_EXPIRES_SECONDS", 60 * 60 * 24))


def handler(event, context):
    method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method", "")
    path = event.get("path") or event.get("rawPath", "")

    try:
        if path.endswith("/upload-url") and method == "POST":
            return _handle_upload_url(event)
        if path.endswith("/download-url") and method == "GET":
            return _handle_download_url(event)
        return _response(404, {"error": f"경로를 찾을 수 없음: {method} {path}"})
    except Exception as e:
        print(f"❌ 에러: {e}")
        return _response(500, {"error": str(e)})


def _handle_upload_url(event):
    body = json.loads(event.get("body") or "{}")
    session_id = body.get("session_id")
    filenames = body.get("filenames", [])
    name = body.get("name", "")
    phone_number = body.get("phone_number", "")
    print_quantity = body.get("print_quantity")

    if not session_id or not filenames:
        return _response(400, {"error": "session_id, filenames가 필요합니다"})

    files = {}
    for filename in filenames:
        key = f"sessions/{session_id}/{filename}"
        upload_url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": S3_BUCKET_NAME,
                "Key": key,
                "ContentType": "image/jpeg",
            },
            ExpiresIn=UPLOAD_URL_EXPIRES_SECONDS,
        )
        files[filename] = {"upload_url": upload_url, "key": key}

    # 이름/전화번호/인쇄매수는 선택 입력값. 사진이 실제로 올라가기 전이라 세션 항목이
    # 아직 없을 수도 있어서 upsert(update_item)로 미리 만들어둠. session-logger가 이후
    # 같은 항목을 put_item이 아니라 update_item으로 건드리므로 여기 값이 덮어써지지 않음
    update_expr = "SET #name = :name, phoneNumber = :phone"
    expr_values = {":name": name, ":phone": phone_number}
    try:
        quantity_int = int(print_quantity) if print_quantity else None
    except (TypeError, ValueError):
        quantity_int = None
    if quantity_int and quantity_int > 0:
        update_expr += ", printQuantity = :quantity"
        expr_values[":quantity"] = quantity_int

    try:
        table.update_item(
            Key={"session_id": session_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames={"#name": "name"},
            ExpressionAttributeValues=expr_values,
        )
    except Exception as e:
        print(f"⚠️  name/phoneNumber/printQuantity 기록 실패 (무시): {e}")

    print(f"✅ presigned 업로드 URL {len(files)}개 발급: session_id={session_id}")
    return _response(200, {"files": files})


def _handle_download_url(event):
    params = event.get("queryStringParameters") or {}
    key = params.get("key")

    if not key or not key.startswith("sessions/"):
        return _response(400, {"error": "유효한 key가 필요합니다"})

    download_url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET_NAME, "Key": key},
        ExpiresIn=DOWNLOAD_URL_EXPIRES_SECONDS,
    )

    # 통계용: session_id를 key에서 뽑아서 "다운로드 URL 발급됨" 기록
    # (fourcut.jpg가 아직 S3 이벤트로 로그 생성 전일 수도 있어서 update_item으로
    #  없으면 새로 만들고 있으면 필드만 갱신)
    try:
        parts = key.split("/")
        if len(parts) >= 2 and parts[0] == "sessions":
            session_id = parts[1]
            table.update_item(
                Key={"session_id": session_id},
                UpdateExpression="SET download_url_issued = :v",
                ExpressionAttributeValues={":v": True},
            )
    except Exception as e:
        # 통계 기록 실패가 실제 QR 발급 자체를 막으면 안 되니 조용히 넘어감
        print(f"⚠️  download_url_issued 갱신 실패 (무시): {e}")

    print(f"✅ presigned 다운로드 URL 발급: key={key}")
    return _response(200, {"download_url": download_url})


def _response(status_code: int, body_dict: dict):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            # 나중에 프론트(브라우저)가 이 API를 직접 호출할 수도 있으니 CORS 허용해둠
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body_dict),
    }
