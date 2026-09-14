"""
라이브뷰 시작 및 프레임 획득 모듈.
"""

from ctypes import c_int, c_uint32, c_void_p, byref, sizeof, string_at

from .sdk import edsdk

# ── 프로퍼티/함수 시그니처 ─────────────────────────────────────
edsdk.EdsSetPropertyData.restype = c_int
edsdk.EdsSetPropertyData.argtypes = [c_void_p, c_uint32, c_int, c_uint32, c_void_p]

edsdk.EdsCreateMemoryStream.restype = c_int
edsdk.EdsCreateMemoryStream.argtypes = [c_uint32, c_void_p]

edsdk.EdsCreateEvfImageRef.restype = c_int
edsdk.EdsCreateEvfImageRef.argtypes = [c_void_p, c_void_p]

edsdk.EdsDownloadEvfImage.restype = c_int
edsdk.EdsDownloadEvfImage.argtypes = [c_void_p, c_void_p]

edsdk.EdsGetLength.restype = c_int
edsdk.EdsGetLength.argtypes = [c_void_p, c_void_p]

edsdk.EdsGetPointer.restype = c_int
edsdk.EdsGetPointer.argtypes = [c_void_p, c_void_p]

edsdk.EdsRelease.restype = c_int
edsdk.EdsRelease.argtypes = [c_void_p]

PROP_EVF_OUTPUT_DEVICE = 0x00000500  # kEdsPropID_Evf_OutputDevice
EVF_OUTPUT_DEVICE_PC = 2             # PC 화면으로 출력


def start_live_view(camera) -> int:
    """라이브뷰 출력을 PC로 전환. 이후 get_live_view_frame()으로 프레임 획득."""
    device = c_uint32(EVF_OUTPUT_DEVICE_PC)
    err = edsdk.EdsSetPropertyData(
        camera, PROP_EVF_OUTPUT_DEVICE, 0, sizeof(device), byref(device)
    )
    print(f"[LIVEVIEW] 시작 결과: {err}")
    return err


def stop_live_view(camera) -> int:
    """라이브뷰 출력을 끈다 (0 = 없음)."""
    device = c_uint32(0)
    err = edsdk.EdsSetPropertyData(
        camera, PROP_EVF_OUTPUT_DEVICE, 0, sizeof(device), byref(device)
    )
    print(f"[LIVEVIEW] 종료 결과: {err}")
    return err


def get_live_view_frame(camera) -> bytes | None:
    """
    라이브뷰 프레임 1장을 JPEG 바이너리(bytes)로 반환.
    반복 호출하면 스트리밍처럼 쓸 수 있음 (예: 15~30fps 루프).
    실패 시 None 반환.
    """
    stream = c_void_p()
    err = edsdk.EdsCreateMemoryStream(0, byref(stream))
    if err != 0:
        print(f"[LIVEVIEW] MemoryStream 생성 실패: {err}")
        return None

    evf_image = c_void_p()
    edsdk.EdsCreateEvfImageRef(stream, byref(evf_image))

    err = edsdk.EdsDownloadEvfImage(camera, evf_image)
    if err != 0:
        edsdk.EdsRelease(evf_image)
        edsdk.EdsRelease(stream)
        return None

    length = c_uint32()
    edsdk.EdsGetLength(stream, byref(length))

    ptr = c_void_p()
    edsdk.EdsGetPointer(stream, byref(ptr))
    frame_bytes = string_at(ptr, length.value)

    edsdk.EdsRelease(evf_image)
    edsdk.EdsRelease(stream)

    return frame_bytes
