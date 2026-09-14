# Canon EDSDK Python 테스트 프로젝트

캐논 EOS 800D를 Python(ctypes)으로 제어하기 위한 최소 테스트 뼈대입니다.
셔터(AF 포함), 라이브뷰까지 확인하는 걸 목표로 합니다.

## 폴더 구조

```
canon_edsdk_test/
├── main.py                   # 실행 진입점 (테스트 스크립트)
├── dll/                      # ★ EDSDK.dll 등을 여기에 넣으세요
│   └── (EDSDK.dll, EdsImage.dll 등)
├── edsdk_wrapper/
│   ├── __init__.py
│   ├── sdk.py                 # 초기화, 카메라 검색, 세션
│   ├── events.py               # ObjectEvent / StateEvent 콜백
│   ├── shutter.py              # 반셔터(AF) / 완셔터(촬영)
│   └── liveview.py             # 라이브뷰 시작 / 프레임 획득
└── README.md
```

## 사용 전 준비

1. 캐논 개발자 사이트에서 받은 EDSDK zip 안의 `EDSDK.dll`, `EdsImage.dll` 등
   DLL 파일들을 `dll/` 폴더 안에 그대로 복사하세요.
   (Windows 64bit Python이면 반드시 64bit용 EDSDK를 사용하세요.)
2. IntelliJ에서 이 폴더(`canon_edsdk_test`)를 프로젝트 루트로 열면 됩니다.
   - IntelliJ에 Python 플러그인이 설치되어 있어야 `.py` 파일 실행/디버깅이 됩니다.
3. Python 인터프리터 설정: Settings → Project → Python Interpreter 에서
   사용할 venv 또는 시스템 Python을 지정하세요. (표준 라이브러리만 쓰므로
   추가 설치 패키지는 없습니다.)

## 실행 순서

### 케이블 연결 전 (지금 바로 가능)
```bash
python main.py
```
- `EdsInitializeSDK()` 결과가 `0`(OK)로 나오는지 확인 → DLL 로드/링크 정상 여부 체크
- `카메라 수: 0` 으로 나오면 정상입니다. (여기서 스크립트가 안내 메시지 출력 후 종료)

### 케이블 연결 후
```bash
python main.py
```
- `카메라 수: 1`로 뜨면 세션 열기 → 반셔터(AF) → 완셔터(촬영) → 라이브뷰 순으로 자동 진행
- 라이브뷰 프레임은 `liveview_frame_1.jpg` ~ `_5.jpg` 로 저장되니, 열어봤을 때
  실제 카메라 화면이 찍혀 있는지 확인하세요.

## 주의사항

- `edsdk_wrapper/events.py` 안의 콜백 함수 객체(`OBJ_EVENT_CB`, `STATE_EVENT_CB`)는
  모듈 전역 변수로 유지되고 있습니다. 이 부분을 로컬 변수로 옮기면 파이썬 GC가
  콜백을 수거해서 크래시가 날 수 있으니 구조를 유지하시는 걸 권장합니다.
- 코드 안의 이벤트/커맨드 상수값(`0x00000...`)은 일반적인 EDSDK 버전 기준입니다.
  실제 다운로드받으신 EDSDK 버전의 `API Reference` PDF에서 정확한 값으로
  한 번 대조해보시는 걸 추천드립니다 (버전별로 미세하게 다를 수 있음).
- `main.py`의 반셔터 AF 대기(`af_wait_sec=1.0`)는 고정 딜레이입니다. 추후
  StateEvent 콜백으로 AF 완료 여부를 정확히 판단하도록 개선하면 더 안정적입니다.

## 다음 단계 (테스트 통과 후)

- `EdsDownloadEvfImage`/`ObjectEvent` 콜백에서 실제 촬영된 이미지를
  로컬에 저장하는 다운로드 로직 추가
- 4컷 자동 촬영 시퀀스 (카운트다운 + 컷 간 대기) 구현
- FastAPI + WebSocket으로 카운트다운/라이브뷰를 프론트엔드에 스트리밍
- S3 업로드 연동
