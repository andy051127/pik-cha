# 변환된 문서

여기에 원본 내용을 붙여넣으면 Markdown 형식으로 정리할 수 있습니다.
Pik-Cha! 현장 PC용 인쇄 워커.

[구조]
Lambda(sgu-pikcha-print)는 부스 PC(사설망)에 직접 접근할 방법이 없어서,
반대로 이 스크립트가 API를 주기적으로 폴링(pull)해서 인쇄 대기 작업을 가져옴.
프린터 1대 + 워커 1개(순차 처리)라 __PENDING_PRINTS__ 리스트 자체가 자연스러운
FIFO 큐 역할을 함. 별도 큐 서비스(SQS 등) 불필요.

[인쇄 방식]
- GDI(win32ui)로 프린터 디바이스 컨텍스트(DC)에 직접 비트맵을 그려서 인쇄 잡을 넣음.
  중간에 뷰어 프로그램이 안 끼기 때문에 인쇄 대화상자가 안 뜨고 조용히 인쇄됨.
- 용지 크기는 코드에서 DEVMODE로 'Japanese Postcard(10.0x14.8cm)'를 직접 지정 +
  방향은 가로(Landscape). Windows에 저장된 기본값에 의존하지 않음.

[여백 없이 정확히 10.0x14.8cm로 채우는 원리]
- 업로드되는 합성 이미지는 이미 용지와 같은 비율(14.8:10)로 만들어져 있음.
- 그래서 letterbox(여백 남김)나 cover(잘라냄)를 하지 않고, 물리적 용지 전체 크기
  (PHYSICALWIDTH x PHYSICALHEIGHT)에 그대로 늘려서 채움 → 비율이 같으니 왜곡·크롭 없음.
- GDI DC의 좌표 원점(0,0)은 "용지 끝"이 아니라 "인쇄 가능 영역"(드라이버가 잡아둔 여백
  안쪽)에서 시작함. 이게 여백이 남던 진짜 원인. PHYSICALOFFSETX/Y만큼 음수로 밀어서
  용지의 진짜 물리적 모서리(0,0)부터 그리게 하면 테두리 없이(borderless) 꽉 참.

실행 전:
  pip install -r requirements.txt
  아래 API_BASE(필수), PRINTER_NAME(선택) 값을 채우거나 환경변수로 지정


