"""
Canon EDSDK Four-Cut Photo Booth - FastAPI Backend
완전 통합 버전: 촬영 + 라이브뷰 + 갤러리 + 네컷 프레임

★ 수정 사항 (스레드 불일치 버그 픽스):
  - init_camera()가 더 이상 메인 스레드에서 sdk.init_sdk()/open_session()을
    직접 호출하지 않습니다. worker.start() 하나만 호출하면, 워커 스레드
    내부에서 초기화~세션 오픈까지 전부 처리됩니다.
  - 이전에는 세션이 메인 스레드에서 열리고 명령은 워커 스레드에서 실행되어
    EDSDK가 응답하지 않는(타임아웃) 문제가 있었습니다.
"""

from fastapi import FastAPI, WebSocket, HTTPException, File, UploadFile, Form
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import base64
import os
import shutil
import threading
import time
import json
from pathlib import Path
from PIL import Image
import io

from image_manager import ImageManager
from edsdk_worker import EdsdkWorker
from edsdk_wrapper import events
import aws_uploader
import frame_compositor

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 전역 상태
camera = None
image_manager = ImageManager()
is_shooting = False
liveview_active = False
worker = EdsdkWorker()  # 싱글톤 워커 인스턴스

# ★ 백엔드 진행상황(카운트다운/촬영완료 등)을 프론트로 실시간 전달하기 위한 상태
active_websockets: list[WebSocket] = []
main_event_loop = None  # startup에서 캡처, run_four_cut(별도 스레드)에서 사용


def broadcast_status(message: dict):
    """
    별도 스레드(run_four_cut)에서 호출해서, 연결된 모든 웹소켓 클라이언트에게
    진행상황 메시지를 보낸다. asyncio 코루틴을 다른 스레드에서 안전하게
    실행하기 위해 run_coroutine_threadsafe를 사용한다.
    """
    if main_event_loop is None:
        return
    for ws in list(active_websockets):
        try:
            asyncio.run_coroutine_threadsafe(ws.send_json(message), main_event_loop)
        except Exception as e:
            print(f"⚠️  상태 브로드캐스트 실패: {e}")


# ══════════════════════════════════════════════════════════════════
# 카메라 초기화
# ══════════════════════════════════════════════════════════════════

def init_camera():
    """카메라 초기화 (초기화~세션 오픈은 전부 워커 스레드 내부에서 처리됨)"""
    global camera
    try:
        worker.start()  # ★ 여기 안에서 init_sdk~open_session까지 전부 처리
        camera = worker.camera
        print("✅ 카메라 초기화 완료")
        return True
    except Exception as e:
        print(f"❌ 카메라 초기화 실패: {e}")
        return False


def cleanup_camera():
    """카메라 정리"""
    global camera
    if camera:
        try:
            worker.stop()  # ★ close_session/terminate도 워커 스레드 안에서 처리됨
            print("✅ 카메라 종료")
        except Exception as e:
            print(f"⚠️  카메라 종료 중 에러: {e}")


# ══════════════════════════════════════════════════════════════════
# WebSocket: 라이브뷰 스트리밍
# ══════════════════════════════════════════════════════════════════

@app.websocket("/ws/liveview")
async def websocket_liveview(websocket: WebSocket):
    """WebSocket으로 라이브뷰 프레임 스트리밍 + 촬영 진행상황 전달"""
    global liveview_active
    await websocket.accept()
    print("🔌 WebSocket 클라이언트 연결")
    active_websockets.append(websocket)

    try:
        worker.start_liveview()
        liveview_active = True
        await asyncio.sleep(0.5)

        while True:
            # ★ 예전엔 촬영 중(is_shooting)일 때 프레임 요청을 통째로 건너뛰어서
            #   촬영 내내 라이브뷰가 멈춰 있었다. 지금은 워커 큐가 셔터 명령과
            #   프레임 요청 순서를 안전하게 관리해주므로 이 제한이 필요 없다.
            #   (셔터 명령이 큐에 있는 짧은 순간엔 프레임 요청이 그 뒤에서
            #   대기했다가 처리되므로 화면이 살짝씩 멈칫할 수는 있지만 안전함)
            try:
                frame = worker.get_liveview_frame()
                if frame:
                    frame_b64 = base64.b64encode(frame).decode()
                    await websocket.send_json({"type": "frame", "data": frame_b64})
            except Exception:
                pass

            await asyncio.sleep(0.1)  # ~10fps

    except Exception as e:
        print(f"❌ WebSocket 에러: {e}")
    finally:
        liveview_active = False
        if websocket in active_websockets:
            active_websockets.remove(websocket)
        worker.stop_liveview()
        try:
            await websocket.close()
        except Exception:
            pass
        print("🔌 WebSocket 클라이언트 연결 해제")


# ══════════════════════════════════════════════════════════════════
# API: 네컷 촬영
# ══════════════════════════════════════════════════════════════════

class FourCutStartRequest(BaseModel):
    interval: int = 3
    count: int = 4

@app.post("/api/four-cut/start")
async def start_four_cut(request: FourCutStartRequest):
    """네컷 촬영 시작"""
    global is_shooting
    interval = request.interval
    count = request.count

    if not camera:
        raise HTTPException(status_code=400, detail="카메라 미연결")

    if is_shooting:
        raise HTTPException(status_code=400, detail="이미 촬영 중입니다")

    is_shooting = True

    def run_four_cut():
        global is_shooting, liveview_active
        try:
            print(f"\n{'='*50}")
            print(f"🎬 촬영 시작! (interval={interval}s, count={count})")
            print(f"{'='*50}")
            print("⚠️  라이브뷰는 활성 상태로 유지 (WebSocket에서 자동 대기)")

            image_manager.clear_all()
            time.sleep(0.5)

            for shot_num in range(1, count + 1):
                try:
                    print(f"\n{'─'*50}")
                    print(f"📸 {shot_num}/{count}번째 촬영 준비 중...")
                    print(f"{'─'*50}")

                    print(f"  1️⃣  반셔터 누르는 중...")
                    worker.half_press()
                    print(f"  ✅ 반셔터 누름 완료")

                    print(f"  2️⃣  {interval}초 카운트다운 시작...")
                    for sec in range(interval, 0, -1):
                        print(f"     ⏱️  {sec}초...", end="\r", flush=True)
                        broadcast_status({
                            "type": "countdown",
                            "shot": shot_num,
                            "count": count,
                            "seconds": sec,
                        })
                        time.sleep(1)
                    print(f"\n  ✅ 카운트다운 완료")

                    broadcast_status({"type": "capturing", "shot": shot_num, "count": count})

                    print(f"  3️⃣  반셔터 해제 중...")
                    worker.release()
                    print(f"  ✅ 반셔터 해제 완료")

                    # 촬영 직전 다운로드 플래그 초기화
                    events.capture_done_flag["done"] = False
                    events.capture_done_flag["last_saved_path"] = None

                    print(f"  4️⃣  촬영 중...")
                    # af_wait_sec을 넉넉히 줘서 AF가 실제로 잠길 시간을 확보 (초점 문제 완화)
                    capture_ok = worker.capture_with_af(af_wait_sec=1.5)

                    if not capture_ok:
                        # AF 실패(EDS_ERR_TAKE_PICTURE_AF_NG 등)로 카메라가 촬영을
                        # 거부한 경우. 실제로 사진이 안 찍혔으므로 한 번 더 시도.
                        print(f"  ⚠️  촬영 실패 (AF NG 등) - 재시도합니다...")
                        broadcast_status({"type": "retrying", "shot": shot_num, "count": count})
                        time.sleep(0.5)
                        capture_ok = worker.capture_with_af(af_wait_sec=2.0)

                    if not capture_ok:
                        print(f"  ❌ 재시도도 실패 - 이 컷은 건너뜁니다")
                        broadcast_status({"type": "shot_failed", "shot": shot_num, "count": count})
                        continue  # 다음 컷으로

                    print(f"  ✅ 촬영 명령 완료")

                    print("이미지 다운로드 대기 중...")
                    saved_path = None
                    for attempt in range(100):  # 최대 10초 대기
                        if events.capture_done_flag["done"]:
                            saved_path = events.capture_done_flag["last_saved_path"]
                            break
                        if attempt % 10 == 0 and attempt > 0:
                            print(f"  ⏳ 다운로드 콜백 대기 중... ({attempt/10:.0f}초 경과)")
                        time.sleep(0.1)

                    if saved_path:
                        photo_bytes = None
                        for retry in range(10):  # 최대 1초, 파일시스템 반영 대기
                            if os.path.exists(saved_path):
                                try:
                                    with open(saved_path, "rb") as f:
                                        photo_bytes = f.read()
                                    break
                                except (PermissionError, OSError) as e:
                                    print(f"  ⚠️  파일 열기 재시도 {retry+1}: {e}")
                            time.sleep(0.1)

                        if photo_bytes:
                            image_manager.save_image(photo_bytes, shot_number=shot_num)
                            print(f"✅ {shot_num}번째 이미지 저장됨 (실제 촬영본, {len(photo_bytes)} bytes)")
                            broadcast_status({"type": "shot_saved", "shot": shot_num, "count": count})
                        else:
                            exists_now = os.path.exists(saved_path)
                            print(f"⚠️  {shot_num}번째 이미지 파일을 끝내 열지 못함")
                            print(f"    경로: {saved_path}")
                            print(f"    현재 파일 존재 여부: {exists_now}")
                            print(f"    (Windows Defender 등 백신이 즉시 격리했을 가능성 - "
                                  f"captured_photos 폴더를 백신 예외 목록에 추가해보세요)")
                            broadcast_status({"type": "shot_failed", "shot": shot_num, "count": count})
                    else:
                        print(f"⚠️  다운로드 이벤트를 받지 못했습니다 (ObjectEvent 콜백 미수신)")
                        broadcast_status({"type": "shot_failed", "shot": shot_num, "count": count})

                except Exception as shot_error:
                    # 한 컷에서 에러가 나도 나머지 컷은 계속 진행
                    print(f"❌ {shot_num}번째 컷 처리 중 에러: {shot_error}")
                    import traceback
                    traceback.print_exc()
                    print(f"⏭️  다음 컷으로 계속 진행합니다...")
                    broadcast_status({"type": "shot_failed", "shot": shot_num, "count": count})

            print(f"\n✨ 총 {count}장 촬영 시도 완료!")
            broadcast_status({"type": "sequence_complete"})

        except Exception as e:
            print(f"❌ 촬영 시퀀스 전체 에러: {e}")
            import traceback
            traceback.print_exc()
            broadcast_status({"type": "sequence_complete", "error": str(e)})
        finally:
            is_shooting = False
            print(f"\n{'='*50}")
            print("✨ 촬영 완료! 라이브뷰 활성화됨")
            print(f"{'='*50}\n")

    thread = threading.Thread(target=run_four_cut, daemon=False)
    thread.start()

    return {"success": True, "message": "촬영 시작"}


@app.get("/api/four-cut/status")
async def four_cut_status():
    """촬영 상태 확인"""
    return {"is_shooting": is_shooting}


# ══════════════════════════════════════════════════════════════════
# API: 이미지 관리
# ══════════════════════════════════════════════════════════════════

@app.get("/api/images")
async def get_images():
    """모든 이미지 목록 조회"""
    images = image_manager.get_all_images()
    return {"images": images}


@app.get("/api/images/{image_id}")
async def get_image(image_id: str):
    """이미지 파일 다운로드"""
    images = image_manager.get_all_images()
    for img in images:
        if img["id"] == image_id:
            filepath = img["filepath"]
            return FileResponse(filepath, media_type="image/jpeg", filename=f"{image_id}.jpg")

    raise HTTPException(status_code=404, detail="이미지를 찾을 수 없습니다")


@app.delete("/api/images/{image_id}")
async def delete_image(image_id: str):
    """이미지 삭제"""
    if image_manager.delete_image(image_id):
        return {"success": True}
    else:
        raise HTTPException(status_code=404, detail="이미지를 찾을 수 없습니다")


# ══════════════════════════════════════════════════════════════════
# API: 네컷 프레임 생성
# ══════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════
# API: 프레임 목록
# ══════════════════════════════════════════════════════════════════

@app.get("/api/frames")
async def get_frames():
    """등록된 프레임 목록 (사용자가 고를 선택지). 미리보기 렌더링에 필요한
    칸 좌표(slots)와 프레임 원본 크기(width/height)도 같이 내려준다."""
    frames = frame_compositor.list_frames()
    result = []
    for f in frames:
        width, height = f.size
        result.append({
            "id": f.id,
            "name": f.name,
            "slot_count": f.slot_count,
            "thumbnail_url": f"/api/frames/{f.id}/thumbnail",
            "width": width,
            "height": height,
            "slots": [
                {"x0": x0, "y0": y0, "x1": x1, "y1": y1}
                for (x0, y0, x1, y1) in f.slots
            ],
        })
    return {"frames": result}


@app.get("/api/frames/aspect-ratio")
async def get_frame_aspect_ratio():
    """
    프레임 칸의 가로세로 비율. 프론트엔드가 라이브뷰 미리보기 화면을 이 비율로
    잘라서 보여주면, 사용자가 라이브뷰에서 본 구도 그대로 최종 네컷에 들어간다.
    (등록된 모든 프레임이 같은 칸 비율을 쓴다는 전제 - primary_aspect_ratio 참고)
    """
    return {"aspect_ratio": frame_compositor.primary_aspect_ratio()}


@app.get("/api/frames/{frame_id}/thumbnail")
async def get_frame_thumbnail(frame_id: str):
    """프레임 미리보기 이미지(투명 PNG 원본을 그대로 반환)"""
    frame = frame_compositor.get_frame(frame_id)
    if frame is None:
        raise HTTPException(status_code=404, detail="프레임을 찾을 수 없습니다")
    return FileResponse(frame.path, media_type="image/png")


# ══════════════════════════════════════════════════════════════════
# API: 네컷 프레임 생성
# ══════════════════════════════════════════════════════════════════

@app.get("/api/fourcut/result")
async def get_fourcut_result():
    """가장 최근에 생성된 네컷(프레임 합성본)을 그대로 반환 - 완료 화면 표시용"""
    output_path = Path(image_manager.base_dir) / "fourcut_result.jpg"
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="아직 생성된 네컷이 없습니다")
    return FileResponse(str(output_path), media_type="image/jpeg")


class FourcutRequest(BaseModel):
    image_ids: list
    frame_id: str | None = None  # None이면 기본(첫 번째 등록된) 프레임 사용

@app.post("/api/fourcut/create")
async def create_fourcut(request: FourcutRequest):
    """선택한 프레임 + 4개 이미지로 네컷 생성"""
    image_ids = request.image_ids
    if len(image_ids) != 4:
        raise HTTPException(status_code=400, detail="정확히 4개의 이미지를 선택하세요")

    try:
        cut_paths = []  # ★ 선택된 4장의 로컬 파일 경로 (프레임 합성 + S3 업로드용)
        all_images = image_manager.get_all_images()

        for image_id in image_ids:
            found = False
            for entry in all_images:
                if entry["id"] == image_id:
                    cut_paths.append(entry["filepath"])
                    found = True
                    break
            if not found:
                raise HTTPException(status_code=404, detail=f"이미지 {image_id}를 찾을 수 없습니다")

        output_path = Path(image_manager.base_dir) / "fourcut_result.jpg"

        # ★ 선택된 프레임 위에 4장을 정확한 칸 위치로 합성 (frame_compositor.py)
        await asyncio.to_thread(
            frame_compositor.create_framed_fourcut,
            cut_paths, str(output_path), request.frame_id,
        )

        # ★ AWS 연동 지점: 로컬 저장 끝나면 presigned URL로 S3에 업로드.
        #   Access Key 없이 API Gateway(Lambda)를 경유해서 URL만 받아오는 방식.
        #   requests는 동기(blocking) 호출이라 to_thread로 감싸서 이벤트루프를 안 막음.
        #   API_GATEWAY_URL이 설정 안 돼있으면 로컬 테스트 모드로 자동 전환됨.
        upload_result = await asyncio.to_thread(
            aws_uploader.upload_fourcut_session, cut_paths, str(output_path)
        )

        response = {
            "success": True,
            "message": "네컷 프레임 생성 완료",
            "filepath": str(output_path),
        }
        if upload_result:
            response["s3"] = upload_result
        else:
            response["s3_upload_skipped"] = True

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"프레임 생성 실패: {str(e)}")

# ══════════════════════════════════════════════════════════════════
# API: 네컷 프레임 생성 (프론트 Canvas 합성 버전)
# ══════════════════════════════════════════════════════════════════

@app.post("/api/fourcut/create-composited")
async def create_fourcut_composited(
    file: UploadFile = File(...),
    image_ids: str = Form(None),  # JSON 배열 문자열, 예: '["20260904_..." , ...]'
    name: str = Form(None),  # Personal_Info 화면에서 입력한 이름
    phone_number: str = Form(None),  # Personal_Info 화면에서 입력한 전화번호
):
    """
    ★ 프론트(Select_Frame v2)가 로고+패턴+사진+프레임색까지 Canvas로 이미
    다 합성한 최종 이미지를 그대로 받아서, S3 업로드 + QR 발급만 한다.
    frame_compositor.py(서버측 합성)는 이 경로에서는 안 쓴다.

    image_ids: 프론트가 Review_Photos에서 실제로 선택한 4장의 이미지 id를
      같이 보내주면, 그 사진들의 원본(cut_1~4.jpg)을 정확히 S3에 같이
      올릴 수 있다. 안 보내면(구버전 프론트 등) 최근 4장으로 대체한다.
    name / phone_number: Personal_Info 화면에서 입력한 값. presigned URL
      발급 요청(_request_upload_urls)에 같이 실어서 보내고, 그 값을
      DynamoDB에 실제로 저장하는 건 AWS 쪽 Lambda가 그 필드를 읽어서
      처리해줘야 한다 (session_logger_lambda.py 등, 로컬 저장소엔 없음).
    """
    output_path = Path(image_manager.base_dir) / "fourcut_result.jpg"

    # 프론트가 보낸 합성 완료 이미지를 그대로 저장
    with open(output_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    all_images = image_manager.get_all_images()

    if image_ids:
        try:
            ids = json.loads(image_ids)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="image_ids 형식이 올바르지 않습니다")

        cut_paths = []
        for iid in ids:
            found = next((img for img in all_images if img["id"] == iid), None)
            if not found:
                raise HTTPException(status_code=404, detail=f"이미지 {iid}를 찾을 수 없습니다")
            cut_paths.append(found["filepath"])
    else:
        # image_ids를 안 보낸 경우(구버전 프론트 호환) - 최근 4장으로 대체
        cut_paths = [img["filepath"] for img in all_images[-4:]]

    # ★ AWS 연동 지점: /api/fourcut/create와 완전히 동일한 업로드 로직 재사용
    upload_result = await asyncio.to_thread(
        aws_uploader.upload_fourcut_session, cut_paths, str(output_path), name, phone_number
    )

    response = {
        "success": True,
        "message": "합성본 업로드 완료",
        "filepath": str(output_path),
    }
    if upload_result:
        response["s3"] = upload_result
    else:
        response["s3_upload_skipped"] = True

    return response

# ══════════════════════════════════════════════════════════════════
# HTML 서빙
# ══════════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    """HTML 페이지"""
    html_path = Path(__file__).parent / "index.html"
    if html_path.exists():
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return {"message": "Canon EDSDK Four-Cut Photo Booth"}


# ══════════════════════════════════════════════════════════════════
# 앱 시작/종료
# ══════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup():
    """서버 시작"""
    global main_event_loop
    print("\n" + "="*50)
    print("🚀 Four-Cut Photo Booth 시작")
    print("="*50)
    main_event_loop = asyncio.get_running_loop()  # ★ 브로드캐스트용 이벤트루프 캡처
    init_camera()


@app.on_event("shutdown")
async def shutdown():
    """서버 종료"""
    cleanup_camera()
    print("\n" + "="*50)
    print("🛑 서버 종료")
    print("="*50)


if __name__ == "__main__":
    import uvicorn

    print("\n📡 http://localhost:8000")
    print("WebSocket: ws://localhost:8000/ws/liveview\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)
