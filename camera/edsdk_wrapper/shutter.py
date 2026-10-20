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
SHUTTER_DOWN_HALF_NONAF = 0x00010001
SHUTTER_DOWN_FULL_NONAF = 0x00010003
SHUTTER_OFF = 0x00000000               # 버튼 해제

EDS_ERR_DEVICE_BUSY = 0x81
EDS_ERR_TAKE_PICTURE_AF_NG = 0x8D01
_ERR_NAMES = {
    0: "OK",
    EDS_ERR_DEVICE_BUSY: "DEVICE_BUSY",
    EDS_ERR_TAKE_PICTURE_AF_NG: "AF_NG",
}


def _err_name(err):
    return f"0x{err:04X}({_ERR_NAMES.get(err, 'UNKNOWN')})"


def take_picture_simple(camera):
    """AF 없이 바로 한 장 촬영 (가장 단순한 테스트용)."""
    err = edsdk.EdsSendCommand(camera, CMD_TAKE_PICTURE, 0)
    print(f"[SHUTTER] TakePicture 결과: {_err_name(err)}")
    return err


def half_press(camera):
    """반셔터 - AF 동작."""
    err = edsdk.EdsSendCommand(camera, CMD_SHUTTER_BUTTON, SHUTTER_DOWN_HALF)
    print(f"[SHUTTER] 반셔터(AF) 결과: {_err_name(err)}")
    return err


def full_press(camera):
    """완셔터 - 촬영."""
    err = edsdk.EdsSendCommand(camera, CMD_SHUTTER_BUTTON, SHUTTER_DOWN_FULL)
    print(f"[SHUTTER] 완셔터(촬영) 결과: {_err_name(err)}")
    return err


def full_press_nonaf(camera):
    """Capture without requiring autofocus lock."""
    err = edsdk.EdsSendCommand(camera, CMD_SHUTTER_BUTTON, SHUTTER_DOWN_FULL_NONAF)
    print(f"[SHUTTER] 완셔터(NonAF) 결과: {_err_name(err)}")
    return err


def release(camera):
    """셔터 버튼 해제. 완셔터 후 반드시 호출해야 카메라가 다음 명령을 받는다."""
    err = edsdk.EdsSendCommand(camera, CMD_SHUTTER_BUTTON, SHUTTER_OFF)
    print(f"[SHUTTER] 버튼 해제 결과: {_err_name(err)}")
    return err


def _retry_if_busy(press, camera):
    err = press(camera)
    for _ in range(3):
        if err != EDS_ERR_DEVICE_BUSY:
            break
        time.sleep(0.3)
        err = press(camera)
    return err


def capture_with_af(camera, af_wait_sec: float = 1.0, already_half_pressed: bool = False) -> bool:
    """AF 촬영을 시도하고 실패하면 NonAF와 TakePicture로 폴백한다."""
    try:
        if not already_half_pressed:
            half_press(camera)
            time.sleep(af_wait_sec)

        if _retry_if_busy(full_press, camera) == 0:
            print("[SHUTTER] 촬영 성공 경로: AF")
            time.sleep(0.5)
            return True

        release(camera)
        time.sleep(0.3)
        if _retry_if_busy(full_press_nonaf, camera) == 0:
            print("[SHUTTER] 촬영 성공 경로: NonAF")
            time.sleep(0.5)
            return True

        release(camera)
        time.sleep(0.3)
        if take_picture_simple(camera) == 0:
            print("[SHUTTER] 촬영 성공 경로: TakePicture")
            time.sleep(0.5)
            return True

        print("[SHUTTER] 모든 촬영 경로 실패")
        return False
    finally:
        release(camera)
