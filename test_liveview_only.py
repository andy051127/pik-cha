"""
라이브뷰만 테스트하는 스크립트.
촬영 없이 즉시 라이브뷰를 시작합니다.
"""

import time
from edsdk_wrapper import sdk, liveview


def main():
    # 1. SDK 초기화
    sdk.init_sdk()

    # 2. 카메라 검색
    camera = sdk.get_camera_list()
    if camera is None:
        print("카메라가 검색되지 않았습니다.")
        sdk.terminate_sdk()
        return

    # 3. 세션 열기
    sdk.open_session(camera)

    try:
        # 라이브뷰만 테스트
        print("\n=== 라이브뷰 테스트 (프레임 5장) ===")
        err = liveview.start_live_view(camera)
        if err != 0:
            print(f"라이브뷰 시작 실패: {err}")
            print("=> EDSDK API Reference에서 에러 코드 {err} 의미 확인 필요")

        time.sleep(1)  # 라이브뷰 전환 대기

        for i in range(5):
            frame = liveview.get_live_view_frame(camera)
            if frame:
                print(f"프레임 {i + 1}: {len(frame)} bytes 수신")
                with open(f"liveview_frame_{i + 1}.jpg", "wb") as f:
                    f.write(frame)
            else:
                print(f"프레임 {i + 1}: 수신 실패")
            time.sleep(0.3)

        liveview.stop_live_view(camera)

    finally:
        sdk.close_session(camera)
        sdk.terminate_sdk()


if __name__ == "__main__":
    main()
