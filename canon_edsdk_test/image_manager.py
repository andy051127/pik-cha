"""
촬영된 이미지 저장 및 관리 모듈.
"""

import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict


class ImageManager:
    """촬영된 이미지를 관리하는 클래스"""

    def __init__(self, base_dir: str = "images"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        self.metadata_file = self.base_dir / "metadata.json"
        self.images_data = self._load_metadata()

    def _load_metadata(self) -> Dict:
        """기존 메타데이터 로드"""
        if self.metadata_file.exists():
            with open(self.metadata_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"images": []}

    def _save_metadata(self):
        """메타데이터 저장"""
        with open(self.metadata_file, "w", encoding="utf-8") as f:
            json.dump(self.images_data, f, indent=2, ensure_ascii=False)

    def save_image(self, image_bytes: bytes, shot_number: int = None) -> Dict:
        """
        이미지 저장.

        Args:
            image_bytes: 이미지 바이너리 데이터
            shot_number: 촬영 번호 (1-4)

        Returns:
            저장된 이미지 정보 딕셔너리
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"photo_{timestamp}.jpg"
        filepath = self.base_dir / filename

        # 이미지 저장
        with open(filepath, "wb") as f:
            f.write(image_bytes)

        # 메타데이터 기록
        image_info = {
            "id": timestamp,
            "filename": filename,
            "filepath": str(filepath),
            "shot_number": shot_number,
            "timestamp": datetime.now().isoformat(),
            "size": len(image_bytes),
        }

        self.images_data["images"].append(image_info)
        self._save_metadata()

        print(f"✅ 이미지 저장: {filename} ({len(image_bytes)} bytes)")
        return image_info

    def get_all_images(self) -> List[Dict]:
        """모든 이미지 정보 조회"""
        return self.images_data.get("images", [])

    def get_image_bytes(self, image_id: str) -> bytes:
        """이미지 바이너리 데이터 조회"""
        for img in self.images_data["images"]:
            if img["id"] == image_id:
                filepath = img["filepath"]
                with open(filepath, "rb") as f:
                    return f.read()
        return None

    def delete_image(self, image_id: str) -> bool:
        """이미지 삭제"""
        for img in self.images_data["images"]:
            if img["id"] == image_id:
                filepath = img["filepath"]
                if os.path.exists(filepath):
                    os.remove(filepath)
                self.images_data["images"].remove(img)
                self._save_metadata()
                print(f"🗑️  이미지 삭제: {img['filename']}")
                return True
        return False

    def clear_all(self):
        """모든 이미지 삭제"""
        for img in self.images_data["images"]:
            filepath = img["filepath"]
            if os.path.exists(filepath):
                os.remove(filepath)
        self.images_data["images"] = []
        self._save_metadata()
        print("🗑️  모든 이미지 삭제 완료")


if __name__ == "__main__":
    # 테스트
    manager = ImageManager()
    print(f"저장된 이미지: {len(manager.get_all_images())}개")
    for img in manager.get_all_images():
        print(f"  - {img['filename']} (shot {img['shot_number']})")
