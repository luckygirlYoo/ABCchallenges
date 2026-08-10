import http.server
import socketserver
import webbrowser
import threading
import os
import sys
import json
import subprocess
from datetime import datetime

PORT = 8080
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

is_collecting = False
last_collected_at = "미실행"
last_status_msg = ""

def run_all_collectors():
    """전체 데이터 수집 파이프라인 (실시간 혼잡도 115곳 + 문화행사 100건 + 네이버 데이터랩) 실행"""
    global is_collecting, last_collected_at, last_status_msg
    is_collecting = True
    try:
        print("\n[웹 서버 API] 실시간 데이터 수집 프로세스 수동 실행 시작...")

        # 1. 인터파크 티켓 300건 실시간 라이브 웹 크롤링 (콘서트/뮤지컬/연극/클래식/전시/아동)
        live_crawler = os.path.join(BASE_DIR, "scripts", "live_ticket_crawler.py")
        subprocess.run([sys.executable, live_crawler], check=True, cwd=BASE_DIR)

        # 2. 티켓링크 라이브 웹 크롤링 (콘서트/뮤지컬/연극/클래식/전시/아동)
        tl_crawler = os.path.join(BASE_DIR, "scripts", "live_ticketlink_crawler.py")
        subprocess.run([sys.executable, tl_crawler], check=True, cwd=BASE_DIR)

        # 3. 실시간 인구 혼잡도 수집
        real_collector = os.path.join(BASE_DIR, "scripts", "real_time_collector.py")
        subprocess.run([sys.executable, real_collector], check=True, cwd=BASE_DIR)

        # 4. 문화행사 수집
        culture_collector = os.path.join(BASE_DIR, "scripts", "culture_event_collector.py")
        subprocess.run([sys.executable, culture_collector], check=True, cwd=BASE_DIR)

        # 5. 네이버 데이터랩 수집
        naver_collector = os.path.join(BASE_DIR, "scripts", "naver_collector.py")
        subprocess.run([sys.executable, naver_collector], check=True, cwd=BASE_DIR)

        # 6. 인스타그램 핫플 해시태그 & 트렌딩 스코어 수집
        insta_collector = os.path.join(BASE_DIR, "scripts", "instagram_hotplace_collector.py")
        subprocess.run([sys.executable, insta_collector], check=True, cwd=BASE_DIR)

        # 7. 공공 육아 8대 사이트 수집 (서울형 키즈카페 / 장난감도서관 / 부모교육)
        public_childcare = os.path.join(BASE_DIR, "scripts", "public_childcare_collector.py")
        subprocess.run([sys.executable, public_childcare], check=True, cwd=BASE_DIR)

        last_collected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        last_status_msg = "공공 육아 8대 사이트 + 인터파크/티켓링크 + 인스타 핫플 수집 완료!"
        print(f"[웹 서버 API] 라이브 데이터 수집 완료! ({last_collected_at})")
    except Exception as e:
        last_status_msg = f"수집 중 에러 발생: {e}"
        print(f"[웹 서버 API] 수집 에러: {e}")
    finally:
        is_collecting = False

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def do_GET(self):
        if self.path.startswith("/api/status"):
            self.send_json({
                "is_collecting": is_collecting,
                "last_collected_at": last_collected_at,
                "last_status_msg": last_status_msg
            })
            return
        super().do_GET()

    def do_POST(self):
        global is_collecting
        if self.path.startswith("/api/refresh"):
            if is_collecting:
                self.send_json({"success": False, "message": "이미 수집 프로세스가 실행 중입니다."})
                return
            
            # 동기식 실행 (완료 후 리턴)
            run_all_collectors()
            self.send_json({
                "success": True,
                "message": "실시간 데이터 수집 파이프라인 완료!",
                "collected_at": last_collected_at,
                "status_msg": last_status_msg
            })
            return

        self.send_error(404, "Endpoint not found")

    def send_json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

def open_browser():
    webbrowser.open(f"http://localhost:{PORT}/web/index.html")

def main():
    print("==================================================")
    print("  AI 기반 주말 맞춤형 여가 추천 서비스 (API 서버 내장)")
    print("==================================================")
    print(f"로컬 웹 서버 주소: http://localhost:{PORT}/web/index.html")
    print(f"수집 실행 API 주소: http://localhost:{PORT}/api/refresh")
    print("==================================================")
    
    threading.Timer(1.0, open_browser).start()
    
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), CustomHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n웹 서버를 종료합니다.")
            sys.exit(0)

if __name__ == "__main__":
    main()
