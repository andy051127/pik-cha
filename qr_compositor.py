"""
QR 이미지를 만드는 모듈.

★ presigned URL 발급 기능은 여기 없다. 학교 AWS 정책상 로컬 PC는
  Access Key를 발급받을 수 없어서(IAM Role만 허용), presigned URL은
  API Gateway 뒤의 Lambda(SafeRole-sgu-yaksok)가 대신 서명해서 내려준다.
  (aws_uploader.py가 그 Lambda를 HTTP로 호출해서 URL 문자열만 받아옴)

  이 모듈은 그렇게 받아온 URL 문자열을 QR 이미지로 바꾸는 순수 로컬 작업만 한다.
  AWS 자격증명이 전혀 필요 없다.
"""

from PIL import Image
import qrcode


def make_qr_image(data: str) -> Image.Image:
    qr = qrcode.QRCode(
        version=None,  # 데이터 길이에 맞춰 자동 크기 조정
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


def compose_qr_on_top(
    photo_path: str,
    qr_img: Image.Image,
    output_path: str,
    qr_width_ratio: float = 0.4,
    padding_ratio: float = 0.05,
) -> str:
    """
    (참고용 - 현재 기본 흐름에서는 안 씀. 나중에 '사진에 QR 합성' 방식으로
    다시 바꾸고 싶을 때를 위해 남겨둠.)
    photo_path 이미지 위쪽에 흰 여백 띠를 만들고, 그 가운데에 QR을 배치.
    """
    photo = Image.open(photo_path).convert("RGB")
    photo_w, photo_h = photo.size

    qr_target_w = max(int(photo_w * qr_width_ratio), 1)
    scale = qr_target_w / qr_img.width
    qr_target_h = max(int(qr_img.height * scale), 1)
    qr_resized = qr_img.resize((qr_target_w, qr_target_h), Image.NEAREST)

    padding = max(int(photo_w * padding_ratio), 4)
    strip_height = qr_target_h + padding * 2

    canvas = Image.new("RGB", (photo_w, strip_height + photo_h), "white")
    qr_x = (photo_w - qr_target_w) // 2
    canvas.paste(qr_resized, (qr_x, padding))
    canvas.paste(photo, (0, strip_height))

    canvas.save(output_path, "JPEG", quality=95)
    return output_path
