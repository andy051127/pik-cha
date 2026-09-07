"""
캐논 EDSDK 동작 테스트 스크립트.

케이블 연결 전 : init_sdk(), get_camera_list()까지만 실행해서
                 DLL 로드/링크가 정상인지 확인 (카메라 수 0이 정상).

케이블 연결 후 : 전체 순서대로 실행해서
                 세션 열기 -> AF/촬영 -> 라이브뷰까지 검증.
"""

import time

from edsdk_wrapper import sdk, events, shutter, liveview


def main():
    # 1. SDK 초기화
    sdk.init_sdk()

    # 2. 카메라 검색
    camera = sdk.get_camera_list()
    if camera is None:
        print("\n카메라가 검색되지 않았습니다.")
        print("- 케이블 미연결 상태라면 정상입니다 (여기까지가 테스트 범위).")
        print("- 케이블 연결했는데도 안 뜨면: 카메라 전원 확인, USB 포트 변경, ")
        print("  카메라 통신모드가 'PC 연결'로 되어있는지 확인해보세요.")
        sdk.terminate_sdk()
        return

    # 3. 세션 열기
    sdk.open_session(camera)

    # 4. 이벤트 콜백 등록
    events.register_event_handlers(camera)

    try:
        # 5. AF + 촬영 테스트
        print("\n=== 반셔터(AF) + 완셔터(촬영) 테스트 ===")
        shutter.capture_with_af(camera, af_wait_sec=1.0)

        # 촬영 이벤트가 콜백으로 들어오는지 잠깐 대기하며 확인
        time.sleep(3)
        if events.capture_done_flag["done"]:
            print("촬영 이벤트 수신 확인됨 (다운로드 로직 연결 지점)")
        else:
            print("촬영 이벤트가 아직 안 왔습니다. 카메라 상태/이벤트 상수값을 확인하세요.")

        # 6. 라이브뷰 테스트
        print("\n=== 라이브뷰 테스트 (프레임 5장) ===")
        time.sleep(2)  # 카메라가 라이브뷰 모드로 전환될 시간 확보
        liveview.start_live_view(camera)
        time.sleep(1)  # 라이브뷰 전환 대기

        for i in range(5):
            frame = liveview.get_live_view_frame(camera)
            if frame:
                print(f"프레임 {i + 1}: {len(frame)} bytes 수신")
                # 필요하면 파일로 저장해서 실제 이미지인지 확인
                with open(f"liveview_frame_{i + 1}.jpg", "wb") as f:
                    f.write(frame)
            else:
                print(f"프레임 {i + 1}: 수신 실패")
            time.sleep(0.2)

        liveview.stop_live_view(camera)

    finally:
        # 7. 정리
        sdk.close_session(camera)
        sdk.terminate_sdk()


if __name__ == "__main__":
    main()
