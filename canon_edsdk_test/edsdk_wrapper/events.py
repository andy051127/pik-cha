"""
EDSDK 이벤트 콜백(ObjectEvent, StateEvent) 등록 모듈.

중요:
- 콜백 함수 객체(OBJ_EVENT_CB, STATE_EVENT_CB)는 반드시 모듈 레벨 전역 변수로
  유지해야 한다. 로컬 변수로만 두면 파이썬 GC가 수거해서 콜백 호출 시 크래시.
"""

import ctypes
from ctypes import c_int, c_uint32, c_void_p

from .sdk import edsdk
from .download import download_image

# ── 이벤트 상수 (EDSDK API Reference 기준, 버전별로 재확인 권장) ──
EDS_OBJECT_EVENT_ALL = 0x00000200      # kEdsObjectEvent_All
EDS_STATE_EVENT_ALL = 0x00000300       # kEdsStateEvent_All
EDS_OBJECT_EVENT_DIR_ITEM_REQUEST_TRANSFER = 0x00000208  # PC로 전송 요청 (SaveTo=Host일 때만 옴)
EDS_OBJECT_EVENT_DIR_ITEM_CREATED = 0x00000204            # 카메라 저장매체에 파일 생성됨

# ── 함수 시그니처 ──────────────────────────────────────────────
OBJECT_EVENT_HANDLER = ctypes.CFUNCTYPE(c_int, c_uint32, c_void_p, c_void_p)
STATE_EVENT_HANDLER = ctypes.CFUNCTYPE(c_int, c_uint32, c_uint32, c_void_p)

edsdk.EdsSetObjectEventHandler.restype = c_int
edsdk.EdsSetObjectEventHandler.argtypes = [c_void_p, c_uint32, c_void_p, c_void_p]

edsdk.EdsSetCameraStateEventHandler.restype = c_int
edsdk.EdsSetCameraStateEventHandler.argtypes = [c_void_p, c_uint32, c_void_p, c_void_p]

# 촬영 완료를 알리는 플래그. capture 시퀀스에서 이 값을 폴링/대기.
# 다운로드된 최신 파일 경로도 같이 기록해둔다.
capture_done_flag = {"done": False, "last_saved_path": None}


def _object_event_callback(event, obj, context):
    print(f"[EVENT] ObjectEvent: {hex(event)}")

    # SaveTo=Host 설정을 안 해도, DirItemCreated 시점에 이미 새로 생긴
    # 파일에 대한 참조(obj)가 전달되므로 여기서 바로 다운로드를 시도한다.
    if event in (EDS_OBJECT_EVENT_DIR_ITEM_REQUEST_TRANSFER, EDS_OBJECT_EVENT_DIR_ITEM_CREATED):
        print("[EVENT] 새 이미지 감지 -> 로컬 저장 시작")
        saved_path = download_image(obj)
        if saved_path:
            capture_done_flag["last_saved_path"] = saved_path
            capture_done_flag["done"] = True
    return 0


def _state_event_callback(event, param, context):
    print(f"[EVENT] StateEvent: {hex(event)}, param={param}")
    return 0


# 전역 참조 유지 (GC 방지)
OBJ_EVENT_CB = OBJECT_EVENT_HANDLER(_object_event_callback)
STATE_EVENT_CB = STATE_EVENT_HANDLER(_state_event_callback)


def register_event_handlers(camera):
    """카메라에 ObjectEvent, StateEvent 콜백을 등록."""
    err1 = edsdk.EdsSetObjectEventHandler(camera, EDS_OBJECT_EVENT_ALL, OBJ_EVENT_CB, None)
    err2 = edsdk.EdsSetCameraStateEventHandler(camera, EDS_STATE_EVENT_ALL, STATE_EVENT_CB, None)
    print(f"[SDK] ObjectEvent 등록: {err1}, StateEvent 등록: {err2}")
    return err1, err2
