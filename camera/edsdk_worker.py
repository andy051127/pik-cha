"""
EDSDK 초기화(Initialize~OpenSession)부터 모든 명령(셔터/라이브뷰)까지
'단 하나의 워커 스레드' 안에서만 실행되도록 강제하는 모듈.

핵심 포인트 2가지:
1. EDSDK는 세션을 연 스레드와 명령을 보내는 스레드가 반드시 같아야 한다.
   그래서 start()를 호출하면, 초기화~세션열기까지 전부 워커 스레드 내부에서
   처리하고, 이후의 모든 명령도 큐를 통해 그 스레드로만 전달한다.
2. EDSDK는 내부적으로 Windows 메시지(COM 콜백)를 통해 ObjectEvent/StateEvent를
   전달한다. 워커 스레드가 큐에서 대기만 하고 있으면 이 메시지가 전혀
   처리되지 않아서, 촬영 후 '실제 이미지 다운로드' 콜백이 영영 안 올 수 있다.
   그래서 큐를 기다리는 동안 주기적으로 Windows 메시지를 pump 해준다.

app.py 쪽 호출부는 그대로 유지 가능:
    worker.start()
    worker.camera
    worker.half_press()
    worker.release()
    worker.capture_with_af(af_wait_sec=1.0)
    worker.start_liveview()
    worker.stop_liveview()
    worker.get_liveview_frame()
    worker.stop()
"""

import ctypes
from ctypes import wintypes
import queue
import threading

from edsdk_wrapper import sdk, events, shutter, liveview

user32 = ctypes.windll.user32

PM_REMOVE = 0x0001


class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt_x", wintypes.LONG),
        ("pt_y", wintypes.LONG),
    ]


def _pump_windows_messages():
    """대기 중인 Windows 메시지를 처리해서 EDSDK 콜백(ObjectEvent 등)이 오도록 한다."""
    msg = _MSG()
    while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


class EdsdkWorker:
    def __init__(self):
        self._queue: "queue.Queue" = queue.Queue()
        self._thread: threading.Thread | None = None
        self._running = False
        self.camera = None
        self.ready = threading.Event()
        self.init_error = None

    # ── 시작/종료 ──────────────────────────────────────────────
    def start(self):
        if self._thread is not None:
            print("[WORKER] 이미 시작됨")
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="EdsdkWorker")
        self._thread.start()
        print("🧵 EDSDK 워커 스레드 시작")

        if not self.ready.wait(timeout=10):
            raise RuntimeError("[WORKER] EDSDK 초기화 타임아웃")
        if self.init_error:
            raise self.init_error

    def stop(self):
        if not self._running:
            return
        self._running = False
        self._queue.put(None)  # 종료 신호
        if self._thread:
            self._thread.join(timeout=5)
        self._thread = None
        self.ready.clear()

    # ── 워커 스레드 본체: 초기화도 여기서, 명령 처리도 여기서 ──
    def _run(self):
        try:
            sdk.init_sdk()
            camera = sdk.get_camera_list()
            if camera is None:
                raise RuntimeError("카메라를 찾을 수 없습니다 (케이블/전원/PC연결모드 확인)")

            sdk.open_session(camera)
            events.register_event_handlers(camera)

            self.camera = camera
        except Exception as e:
            self.init_error = e
            self.ready.set()
            return

        self.ready.set()
        print("▶️  워커 루프 시작")

        while self._running:
            # 큐를 기다리는 동안 Windows 메시지도 계속 pump 해줘야
            # ObjectEvent(다운로드 요청) 콜백이 실제로 들어온다.
            _pump_windows_messages()

            try:
                item = self._queue.get(timeout=0.05)
            except queue.Empty:
                continue

            if item is None:  # 종료 신호
                break

            func, args, kwargs, result_holder, done_event = item
            try:
                result_holder["value"] = func(self.camera, *args, **kwargs)
            except Exception as e:
                result_holder["error"] = e
            finally:
                done_event.set()

            # 명령 처리 직후에도 한 번 더 pump (촬영 직후 이벤트가 바로 올 수 있음)
            _pump_windows_messages()

        try:
            sdk.close_session(self.camera)
            sdk.terminate_sdk()
        except Exception as e:
            print(f"[WORKER] 종료 중 에러 (무시 가능): {e}")

    # ── 내부 공통 호출 함수 ────────────────────────────────────
    def _call(self, func, *args, timeout: float = 10.0, **kwargs):
        if not self.ready.is_set():
            raise RuntimeError("[WORKER] 아직 초기화되지 않았습니다. start()를 먼저 호출하세요.")
        if self.init_error:
            raise self.init_error

        result_holder = {}
        done_event = threading.Event()
        self._queue.put((func, args, kwargs, result_holder, done_event))

        if not done_event.wait(timeout=timeout):
            raise TimeoutError(f"[WORKER] '{func.__name__}' 호출이 {timeout}초 내에 끝나지 않음")

        if "error" in result_holder:
            raise result_holder["error"]
        return result_holder.get("value")

    # ── app.py 호환 인터페이스 ─────────────────────────────────
    def half_press(self):
        return self._call(shutter.half_press)

    def release(self):
        return self._call(shutter.release)

    def capture_with_af(self, af_wait_sec: float = 1.0):
        return self._call(shutter.capture_with_af, af_wait_sec=af_wait_sec, timeout=15.0)

    def start_liveview(self):
        return self._call(liveview.start_live_view)

    def stop_liveview(self):
        return self._call(liveview.stop_live_view)

    def get_liveview_frame(self):
        return self._call(liveview.get_live_view_frame, timeout=2.0)
