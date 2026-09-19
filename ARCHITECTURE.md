# Pik-Cha! 아키텍처 요약

## 구성 요소

- **camera/** — 부스 PC. FastAPI 백엔드(app.py)가 카메라(EDSDK) 제어, 라이브뷰, 4컷 촬영 담당. 포트 8000.
- **frontend/** — 부스 손님용 키오스크 화면(Main → 순번입력 → 촬영 → 사진선택 → 프레임 → QR). camera/app.py랑만 통신.
- **printer/print_worker.py** — 프린터 PC. 5초마다 인쇄 대기열 폴링해서 GDI로 인쇄.
- **Lambda/** — AWS Lambda 5개 (presign, session-logger, print, admin, waitlist). API Gateway 뒤에 있음.
- **DynamoDB** — 세션 테이블(sgu-pikcha-photobooth-sessions) + 웨이팅리스트 테이블(sgu-pikcha-waitinglist), 2개.
- **S3** — 사진 버킷(사진 원본/합성본 저장) + 정적호스팅 버킷(admin/ 페이지들), 2개로 분리됨.
- **admin/** — S3에 올라가는 독립 페이지들 (웨이팅 등록/조회, 태블릿 디스플레이, 관리자 대시보드/웨이팅관리/인화관리). API Gateway를 브라우저에서 직접 호출.
- **SOLAPI** — 인화완료 SMS 발송 서비스.

## 핵심 흐름

1. 손님이 QR로 웨이팅 등록 → 순번 발급 → 순번 확인하며 대기
2. 부스에서 순번 입력 → 이름/전화번호 자동으로 불러옴(재입력 없음) → 촬영 시작
3. 촬영 끝나면 자동으로 다음 대기팀 호출 (관리자가 수동으로 안 함)
4. 사진 선택 + 프레임 합성 → S3 업로드 → DynamoDB에 기록 → 인쇄 대기열 등록
5. print_worker.py가 대기열 가져가서 인쇄 → 인쇄 끝나면 완료 보고 → SMS 발송
6. 관리자는 admin/ 페이지에서 대기현황 보기, 웨이팅 취소, 재인쇄, SMS 재발송 가능

## 통신 방향

- 부스 PC / 프린터 PC는 사설망이라 AWS가 먼저 못 건드림 → 항상 로컬 → AWS 방향으로만 요청
- admin/ 페이지와 손님 브라우저는 AWS(API Gateway)를 직접 호출 (중간에 부스 PC 안 거침)

## 알아두면 좋은 약점

- 순번(ticket_number)과 촬영세션(session_id)이 DB로 직접 안 이어져 있음 — 프론트가 값을 들고 옮기는 방식이라 중간에 끊기면 SMS가 조용히 안 감
- S3에 올라간 사진은 자동삭제 안 됨 (무기한 보관)
- 카메라 인식 실패 시 에러 없이 조용히 가짜사진 모드로 넘어감
- admin/ 페이지 로그인은 prompt() 팝업 방식이라 정식 로그인은 아님
