## 실행방법 ##
pikcha root 디렉토리 기준
# 프론트 서버
cd frontend/frontend
python -m http.server 5500
# 카메라
cd camera
python app.py
# 프린터
cd printer
python print_worker.py

## URL ##
-- [S3]

{예약유저페이지} http://sgu-pikcha-admin.s3-website.ap-northeast-2.amazonaws.com/WaitingList_UserPage/index.html

{테블릿}: http://sgu-pikcha-admin.s3-website.ap-northeast-2.amazonaws.com/WaitingList_AdminQRPage/index.html

{관리자대시보드}: http://sgu-pikcha-admin.s3-website.ap-northeast-2.amazonaws.com/WaitingList_AdminPage/index.html

-- [프론트]
http://localhost:5500/01_landing_main/