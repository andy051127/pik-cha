"""
카메라 안에 촬영된 이미지를 컴퓨터로 다운로드해서 저장하는 모듈.

ObjectEvent(DirItemRequestTransfer / DirItemCreated)가 발생하면, 이벤트로 전달된
directory item(obj)을 이용해 실제 파일을 로컬에 저장한다.

★ 방식 변경:
  이전엔 EdsCreateFileStream()으로 EDSDK가 직접 디스크에 파일을 쓰게 했는데,
  'DownloadComplete까지 성공(err=0)했다고 나오는데 실제 파일은 생성되지 않는'
  증상이 있었다. 이는 경로 문자열의 인코딩(ANSI/유니코드) 처리가 이 EDSDK
  빌드와 안 맞아서, 엉뚱한(깨진) 경로에 쓰였을 가능성이 높다.

  그래서 지금은 라이브뷰에서 이미 검증된 방식과 동일하게
  EdsCreateMemoryStream()으로 '메모리 버퍼'에 받은 다음,
  그 바이트를 파이썬이 직접 open(path, 'wb')로 디스크에 쓴다.
  이러면 EDSDK 쪽 경로 인코딩 문제를 완전히 우회할 수 있다.
"""

import os
import time
from ctypes import (
    c_int, c_uint32, c_void_p, byref, sizeof, Structure, c_char, string_at
)

from .sdk import edsdk

# ── 저장 폴더 설정 ─────────────────────────────────────────────
SAVE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "captured_photos")
)
os.makedirs(SAVE_DIR, exist_ok=True)
print(f"[DOWNLOAD] 저장 폴더: {SAVE_DIR}")

EDS_MAX_NAME = 256


class EdsDirectoryItemInfo(Structure):
    _fields_ = [
        ("size", c_uint32 * 2),          # EdsUInt64 (32bit x2, little-endian)
        ("isFolder", c_int),
        ("groupID", c_uint32),
        ("option", c_uint32),
        ("szFileName", c_char * EDS_MAX_NAME),
        ("format", c_uint32),
        ("dateTime", c_uint32),
    ]


# ── 함수 시그니처 ──────────────────────────────────────────────
edsdk.EdsGetDirectoryItemInfo.restype = c_int
edsdk.EdsGetDirectoryItemInfo.argtypes = [c_void_p, c_void_p]

# ★ 경로를 받는 EdsCreateFileStream 대신 메모리 스트림 생성 함수를 사용
edsdk.EdsCreateMemoryStream.restype = c_int
edsdk.EdsCreateMemoryStream.argtypes = [c_uint32, c_void_p]

edsdk.EdsDownload.restype = c_int
edsdk.EdsDownload.argtypes = [c_void_p, c_uint32, c_void_p]

edsdk.EdsDownloadComplete.restype = c_int
edsdk.EdsDownloadComplete.argtypes = [c_void_p]

edsdk.EdsGetLength.restype = c_int
edsdk.EdsGetLength.argtypes = [c_void_p, c_void_p]

edsdk.EdsGetPointer.restype = c_int
edsdk.EdsGetPointer.argtypes = [c_void_p, c_void_p]

edsdk.EdsRelease.restype = c_int
edsdk.EdsRelease.argtypes = [c_void_p]


def download_image(directory_item) -> str | None:
    """
    directory_item: ObjectEvent 콜백의 obj 인자로 전달받은 값.
    성공 시 저장된 파일 경로(str)를, 실패 시 None을 반환.
    """
    info = EdsDirectoryItemInfo()
    err = edsdk.EdsGetDirectoryItemInfo(directory_item, byref(info))
    if err != 0:
        print(f"[DOWNLOAD] DirectoryItemInfo 조회 실패: {err}")
        return None

    filename = info.szFileName.decode("utf-8", errors="ignore")
    if not filename:
        filename = f"capture_{int(time.time())}.jpg"

    save_path = os.path.join(SAVE_DIR, filename)
    print(f"[DOWNLOAD] 저장 대상 파일: {filename} -> {save_path}")

    # 1) 메모리 스트림 생성 (경로 없음 - 인코딩 문제 원천 차단)
    stream = c_void_p()
    err = edsdk.EdsCreateMemoryStream(0, byref(stream))
    if err != 0:
        print(f"[DOWNLOAD] MemoryStream 생성 실패: {err}")
        return None

    # 2) 실제 이미지 데이터를 메모리 스트림으로 다운로드
    file_size = info.size[0]
    err = edsdk.EdsDownload(directory_item, file_size, stream)
    if err != 0:
        print(f"[DOWNLOAD] Download 실패: {err}")
        edsdk.EdsRelease(stream)
        return None

    err = edsdk.EdsDownloadComplete(directory_item)
    print(f"[DOWNLOAD] DownloadComplete 결과: {err}")

    # 3) 메모리 스트림에서 실제 바이트 꺼내기
    length = c_uint32()
    edsdk.EdsGetLength(stream, byref(length))

    ptr = c_void_p()
    edsdk.EdsGetPointer(stream, byref(ptr))

    if length.value == 0 or not ptr.value:
        print(f"[DOWNLOAD] ⚠️ 메모리 스트림이 비어있음 (length={length.value})")
        edsdk.EdsRelease(stream)
        return None

    photo_bytes = string_at(ptr, length.value)
    edsdk.EdsRelease(stream)

    print(f"[DOWNLOAD] 메모리에서 {len(photo_bytes)} bytes 수신")

    # 4) 파이썬이 직접 디스크에 쓰기 (EDSDK 경로 인코딩 문제 우회)
    try:
        with open(save_path, "wb") as f:
            f.write(photo_bytes)
    except OSError as e:
        print(f"[DOWNLOAD] ⚠️ 파일 쓰기 실패: {e}")
        return None

    exists_immediately = os.path.exists(save_path)
    size_immediately = os.path.getsize(save_path) if exists_immediately else None
    print(f"[DOWNLOAD] 완료 직후 파일 존재: {exists_immediately}, 크기: {size_immediately}")

    if not exists_immediately:
        print(f"[DOWNLOAD] ⚠️ open().write()까지 했는데도 파일이 없음 -> 매우 이례적, 재확인 필요")
        return None

    print(f"[DOWNLOAD] 저장 완료: {save_path}")
    return save_path
