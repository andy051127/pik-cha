graph TB
    subgraph Client ["클라이언트 영역 (프론트엔드)"]
        GuestMobile["손님 스마트폰<br/>(웨이팅 등록/조회)"]
        BoothUI["부스 키오스크 PC<br/>(포트 5500 / 8000)"]
        AdminDevice["관리자/태블릿 기기<br/>(대시보드 / 관리)"]
    end

    subgraph Hardware ["하드웨어 및 상주 프로세스"]
        Camera["캐논 DSLR<br/>(EDSDK Worker)"]
        Printer["프린터 PC<br/>(GDI 인쇄 + 스풀큐 감시)"]
    end

    subgraph S3_Static ["AWS S3 (정적 웹사이트 호스팅)"]
        WaitingPages["웨이팅 시스템 6개 페이지<br/>(User / Admin / Tablet)"]
    end

    subgraph AWS ["AWS 클라우드 (API Gateway + Serverless)"]
        APIGW["API Gateway"]
        
        subgraph Lambdas ["Lambda 함수들"]
            L_Presign["sgu-pikcha-presign"]
            L_Waitlist["sgu-pikcha-waitlist"]
            L_Print["sgu-pikcha-print"]
            L_Admin["sgu-pikcha-admin"]
            L_Logger["sgu-pikcha-session-logger<br/>(S3 이벤트 트리거)"]
        end

        subgraph DB ["DynamoDB"]
            DB_Sessions["sessions 테이블"]
            DB_Waiting["waitinglist 테이블"]
        end

        S3_Bucket["AWS S3 (사진 저장소)"]
    end

    subgraph External ["외부 서비스"]
        SOLAPI["SOLAPI (문자 발송)"]
    end

    %% 연결 관계
    GuestMobile -->|HTTP| WaitingPages
    AdminDevice -->|HTTP / Basic Auth| WaitingPages
    
    BoothUI -->|직접 입력: ticket_number| Camera
    BoothUI -->|API 호출| APIGW
    
    APIGW --> L_Presign & L_Waitlist & L_Print & L_Admin
    
    L_Presign --> DB_Sessions & S3_Bucket
    L_Waitlist --> DB_Waiting
    L_Print --> DB_Sessions & SOLAPI
    L_Admin --> DB_Sessions & DB_Waiting
    
    S3_Bucket -.->|업로드 완료 이벤트| L_Logger
    L_Logger --> DB_Sessions
    
    Printer -->|5초 폴링| APIGW