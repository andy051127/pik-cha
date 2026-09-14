"""
반셔터(AF) / 완셔터(촬영) 제어 모듈.
"""

import time
from ctypes import c_int, c_uint32, c_void_p

from .sdk import edsdk

edsdk.EdsSendCommand.restype = c_int
edsdk.EdsSendCommand.argtypes = [c_void_p, c_uint32, c_int]

# kEdsCameraCommand 상수 (버전별 API Reference로 재확인 권장)
CMD_TAKE_PICTURE = 0x00000000          # kEdsCameraCommand_TakePicture (단발 촬영)
CMD_SHUTTER_BUTTON = 0x00000004        # kEdsCameraCommand_ShutterButton

SHUTTER_DOWN_HALF = 0x00000001         # 반셔터 (AF)
SHUTTER_DOWN_FULL = 0x00000003         # 완셔터 (촬영)
SHUTTER_OFF = 0x00000000               # 버튼 해제


def take_picture_simple(camera):
    """AF 없이 바로 한 장 촬영 (가장 단순한 테스트용)."""
    err = edsdk.EdsSendCommand(camera, CMD_TAKE_PICTURE, 0)
    print(f"[SHUTTER] TakePicture 결과: {err}")
    return err


def half_press(camera):
    """반셔터 - AF 동작."""
    err = edsdk.EdsSendCommand(camera, CMD_SHUTTER_BUTTON, SHUTTER_DOWN_HALF)
    print(f"[SHUTTER] 반셔터(AF) 결과: {err}")
    return err


def full_press(camera):
    """완셔터 - 촬영."""
    err = edsdk.EdsSendCommand(camera, CMD_SHUTTER_BUTTON, SHUTTER_DOWN_FULL)
    print(f"[SHUTTER] 완셔터(촬영) 결과: {err}")
    return err


def release(camera):
    """셔터 버튼 해제. 완셔터 후 반드시 호출해야 카메라가 다음 명령을 받는다."""
    err = edsdk.EdsSendCommand(camera, CMD_SHUTTER_BUTTON, SHUTTER_OFF)
    print(f"[SHUTTER] 버튼 해제 결과: {err}")
    return err


def capture_with_af(camera, af_wait_sec: float = 1.0) -> bool:
    """
    반셔터(AF) -> 대기 -> 완셔터(촬영) -> 버튼 해제 순으로 진행.
    af_wait_sec: AF 완료를 기다리는 시간. 실제로는 StateEvent로 AF 완료를
                 확인하는 게 정확하지만, 우선 고정 딜레이로 테스트.

    반환값: 완셔터(실제 촬영)가 성공했으면 True, AF 실패(EDS_ERR_TAKE_PICTURE_AF_NG 등)로
            카메라가 촬영을 거부했으면 False.
    """
    half_press(camera)
    time.sleep(af_wait_sec)

    full_err = full_press(camera)
    time.sleep(0.5)

    release(camera)
    return full_err == 0
