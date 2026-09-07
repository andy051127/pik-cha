"""
EDSDK 초기화, 카메라 검색, 세션 열기/닫기를 담당하는 모듈.

주의:
- EDSDK.dll, EdsImage.dll 등은 이 파일 기준 상위 폴더의 dll/ 에 넣어두거나,
  DLL_PATH 를 실제 경로로 수정해서 쓰세요.
- 64bit Python이면 64bit EDSDK, 32bit Python이면 32bit EDSDK를 써야 합니다.
"""

import ctypes
from ctypes import c_void_p, c_int, c_uint32, byref, POINTER
import os

# ── DLL 경로 설정 ──────────────────────────────────────────────
DLL_PATH = os.path.join(os.path.dirname(__file__), "..", "dll", "EDSDK.dll")

edsdk = ctypes.WinDLL(DLL_PATH)

# ── 함수 시그니처 정의 ─────────────────────────────────────────
edsdk.EdsInitializeSDK.restype = c_int

edsdk.EdsGetCameraList.restype = c_int
edsdk.EdsGetCameraList.argtypes = [POINTER(c_void_p)]

edsdk.EdsGetChildCount.restype = c_int
edsdk.EdsGetChildCount.argtypes = [c_void_p, POINTER(c_uint32)]

edsdk.EdsGetChildAtIndex.restype = c_int
edsdk.EdsGetChildAtIndex.argtypes = [c_void_p, c_int, POINTER(c_void_p)]

edsdk.EdsOpenSession.restype = c_int
edsdk.EdsOpenSession.argtypes = [c_void_p]

edsdk.EdsCloseSession.restype = c_int
edsdk.EdsCloseSession.argtypes = [c_void_p]

edsdk.EdsTerminateSDK.restype = c_int

edsdk.EdsRelease.restype = c_int
edsdk.EdsRelease.argtypes = [c_void_p]

# EdsError: 0 = EDS_ERR_OK
EDS_ERR_OK = 0


def init_sdk() -> int:
    """EDSDK를 초기화한다. 프로그램 시작 시 한 번만 호출."""
    err = edsdk.EdsInitializeSDK()
    print(f"[SDK] Initialize 결과: {err} ({'OK' if err == EDS_ERR_OK else 'FAIL'})")
    return err


def terminate_sdk() -> int:
    """EDSDK 종료. 프로그램 끝날 때 호출."""
    err = edsdk.EdsTerminateSDK()
    print(f"[SDK] Terminate 결과: {err}")
    return err


def get_camera_list():
    """
    연결된 카메라 리스트를 조회하고, 첫 번째 카메라 핸들을 반환.
    카메라가 없으면 None 반환. (케이블 연결 전에는 항상 None이 정상)
    """
    camera_list = c_void_p()
    err = edsdk.EdsGetCameraList(byref(camera_list))
    if err != EDS_ERR_OK:
        print(f"[SDK] GetCameraList 실패: {err}")
        return None

    count = c_uint32()
    edsdk.EdsGetChildCount(camera_list, byref(count))
    print(f"[SDK] 연결된 카메라 수: {count.value}")

    if count.value == 0:
        edsdk.EdsRelease(camera_list)
        return None

    camera = c_void_p()
    edsdk.EdsGetChildAtIndex(camera_list, 0, byref(camera))
    edsdk.EdsRelease(camera_list)
    return camera


def open_session(camera) -> int:
    """카메라와 세션을 연다. 촬영/라이브뷰 전에 반드시 호출."""
    err = edsdk.EdsOpenSession(camera)
    print(f"[SDK] OpenSession 결과: {err}")
    return err


def close_session(camera) -> int:
    """세션을 닫는다."""
    err = edsdk.EdsCloseSession(camera)
    print(f"[SDK] CloseSession 결과: {err}")
    return err


# ── 저장 위치를 PC(Host)로 전환 ─────────────────────────────────
# 이걸 안 하면 카메라는 촬영된 사진을 SD카드에만 저장하고,
# PC로 보내달라는 이벤트(DirItemRequestTransfer)를 아예 안 보낸다.
PROP_SAVE_TO = 0x0000000B  # kEdsPropID_SaveTo
SAVE_TO_CAMERA = 1         # kEdsSaveTo_Camera
SAVE_TO_HOST = 2           # kEdsSaveTo_Host
SAVE_TO_BOTH = 3           # kEdsSaveTo_Both

edsdk.EdsSetPropertyData.restype = c_int
edsdk.EdsSetPropertyData.argtypes = [c_void_p, c_uint32, c_int, c_uint32, c_void_p]


def set_save_to_host(camera) -> int:
    """촬영된 이미지를 PC(Host)로 자동 전송하도록 설정."""
    value = c_uint32(SAVE_TO_HOST)
    err = edsdk.EdsSetPropertyData(
        camera, PROP_SAVE_TO, 0, ctypes.sizeof(value), byref(value)
    )
    print(f"[SDK] SaveTo=Host 설정 결과: {err}")
    return err


class EdsCapacity(ctypes.Structure):
    _fields_ = [
        ("numberOfFreeClusters", ctypes.c_int32),
        ("bytesPerSector", ctypes.c_int32),
        ("reset", ctypes.c_int32),  # EdsBool
    ]


edsdk.EdsSetCapacity.restype = c_int
edsdk.EdsSetCapacity.argtypes = [c_void_p, EdsCapacity]


def set_capacity(camera) -> int:
    """
    SaveTo=Host로 전환하기 전, 카메라에게 'PC에 이만큼 여유공간 있다'고
    알려주는 절차. EDSDK 공식 샘플에서 SaveTo=Host 설정 시 필수로 같이
    호출하는 함수라, 이게 없으면 SaveTo 설정이 무시되는 경우가 있다.
    """
    capacity = EdsCapacity(0x7FFFFFFF, 0x1000, 1)  # 여유공간 충분, reset=True
    err = edsdk.EdsSetCapacity(camera, capacity)
    print(f"[SDK] SetCapacity 결과: {err}")
    return err
