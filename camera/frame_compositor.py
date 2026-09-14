"""
투명 처리된 프레임(assets/frames/*.png) 위에 사진들을 정확한 칸 위치에
합성하는 모듈. 여러 프레임을 지원하며, 각 프레임의 칸 좌표는 이미지 안의
회색(217,217,217) 영역을 분석해서 '자동으로' 찾아낸다.

새 프레임 추가 방법:
  1. Photoshop/Figma 등에서 사진 들어갈 자리를 정확히 RGB(217,217,217)로
     채운 PNG를 만든다 (그 외 배경/테두리는 원하는 디자인).
  2. assets/frames/ 폴더에 파일로 저장한다 (예: frame_02.png).
  3. (선택) assets/frames/manifest.json 에 표시 이름을 등록한다.
     {"frame_02.png": "핑크 리본"}
  4. 끝. 서버 재시작하면 자동으로 인식되고 칸 좌표도 자동 계산된다.
"""

import os
import json
from PIL import Image
import numpy as np

FRAMES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "frames")
MANIFEST_PATH = os.path.join(FRAMES_DIR, "manifest.json")

GRAY_RGB = (217, 217, 217)
GRAY_TOL = 6
MIN_SLOT_AREA = 1500  # 이보다 작은 회색 얼룩은 텍스처 노이즈로 보고 무시


def _detect_slots(frame_img: Image.Image):
    """이미지 안에서 회색(217,217,217) 사각형 영역들을 위에서 아래 순서로 찾아 반환."""
    arr = np.array(frame_img.convert("RGBA")).astype(np.int16)
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    mask = (
        (np.abs(r - GRAY_RGB[0]) <= GRAY_TOL)
        & (np.abs(g - GRAY_RGB[1]) <= GRAY_TOL)
        & (np.abs(b - GRAY_RGB[2]) <= GRAY_TOL)
    )

    rows_with_gray = mask.any(axis=1)
    h, w = mask.shape

    # 연속된 세로 구간(칸) 찾기
    segments = []
    in_seg = False
    start = 0
    for y in range(h):
        if rows_with_gray[y] and not in_seg:
            in_seg, start = True, y
        elif not rows_with_gray[y] and in_seg:
            in_seg = False
            segments.append((start, y - 1))
    if in_seg:
        segments.append((start, h - 1))

    slots = []
    for y0, y1 in segments:
        if (y1 - y0 + 1) * w < MIN_SLOT_AREA:
            continue  # 노이즈 제거
        mid_row = mask[(y0 + y1) // 2]
        xs = np.where(mid_row)[0]
        if xs.size == 0:
            continue
        x0, x1 = int(xs.min()), int(xs.max())
        slots.append((x0, y0, x1 + 1, y1 + 1))  # (x0,y0,x1,y1) - x1/y1은 exclusive

    return slots


class FrameInfo:
    def __init__(self, frame_id, name, path):
        self.id = frame_id
        self.name = name
        self.path = path
        self._slots = None
        self._size = None

    @property
    def slots(self):
        if self._slots is None:
            self._slots = _detect_slots(Image.open(self.path))
        return self._slots

    @property
    def size(self):
        """프레임 원본 이미지의 (width, height)."""
        if self._size is None:
            self._size = Image.open(self.path).size
        return self._size

    @property
    def slot_count(self):
        return len(self.slots)


def _load_manifest() -> dict:
    if os.path.exists(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _discover_frames():
    manifest = _load_manifest()
    frames = []
    if not os.path.isdir(FRAMES_DIR):
        return frames
    for fname in sorted(os.listdir(FRAMES_DIR)):
        if not fname.lower().endswith(".png"):
            continue
        frame_id = os.path.splitext(fname)[0]
        display_name = manifest.get(fname, frame_id)
        frames.append(FrameInfo(frame_id, display_name, os.path.join(FRAMES_DIR, fname)))
    return frames


_FRAMES_CACHE = None


def list_frames():
    """등록된 모든 프레임 목록 (FrameInfo 리스트)."""
    global _FRAMES_CACHE
    if _FRAMES_CACHE is None:
        _FRAMES_CACHE = _discover_frames()
    return _FRAMES_CACHE


def reload_frames():
    """assets/frames 폴더가 런타임 중 바뀐 경우 강제로 다시 스캔."""
    global _FRAMES_CACHE
    _FRAMES_CACHE = None
    return list_frames()


def get_frame(frame_id: str):
    for f in list_frames():
        if f.id == frame_id:
            return f
    return None


def primary_aspect_ratio() -> float:
    """
    기준 프레임(첫 번째 등록된 프레임)의 슬롯 가로세로 비율(width/height).
    라이브뷰 화면비를 맞출 때 사용 - 모든 프레임의 슬롯 비율이 같다는 전제.
    """
    frames = list_frames()
    if not frames or not frames[0].slots:
        return 1.5  # 프레임이 하나도 없을 때의 안전한 기본값 (3:2)
    x0, y0, x1, y1 = frames[0].slots[0]
    return (x1 - x0) / (y1 - y0)


def _cover_resize_and_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """이미지를 (target_w, target_h) 칸에 꽉 채우도록 리사이즈 후 가운데 크롭."""
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w, new_h = round(src_w * scale), round(src_h * scale)
    resized = img.resize((new_w, new_h), Image.LANCZOS)

    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def create_framed_fourcut(photo_paths: list[str], output_path: str, frame_id: str | None = None) -> str:
    """
    photo_paths: 촬영 순서대로 사진 경로들 (프레임의 칸 개수와 같아야 함).
    output_path: 결과물 저장 경로.
    frame_id: 사용할 프레임 id. None이면 등록된 첫 번째 프레임 사용.
    """
    frames = list_frames()
    if not frames:
        raise RuntimeError("등록된 프레임이 없습니다 (assets/frames 폴더를 확인하세요)")

    frame_info = get_frame(frame_id) if frame_id else frames[0]
    if frame_info is None:
        raise ValueError(f"존재하지 않는 프레임 id: {frame_id}")

    slots = frame_info.slots
    if len(photo_paths) != len(slots):
        raise ValueError(
            f"사진 개수({len(photo_paths)})와 프레임 '{frame_info.id}'의 칸 개수({len(slots)})가 다릅니다"
        )

    frame_img = Image.open(frame_info.path).convert("RGBA")
    canvas = Image.new("RGBA", frame_img.size, (255, 255, 255, 255))

    for photo_path, (x0, y0, x1, y1) in zip(photo_paths, slots):
        slot_w, slot_h = x1 - x0, y1 - y0
        photo = Image.open(photo_path).convert("RGB")
        fitted = _cover_resize_and_crop(photo, slot_w, slot_h)
        canvas.paste(fitted, (x0, y0))

    result = Image.alpha_composite(canvas, frame_img).convert("RGB")
    result.save(output_path, "JPEG", quality=95)

    return output_path
