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

# ── 7단계 배치 상태 정의 ─────────────────────────────────
BATCH_STEPS_TEMPLATE = [
    {
        "id": "step1",
        "name": "culture_event_collector.py",
        "title": "[배치 1] 공공 문화행사 API & 미술관 수집",
        "script": "scripts/culture_event_collector.py",
        "desc": "서울·경기 공공 문화행사 API 및 미술관/전시장 수집",
        "status": "PENDING",
        "message": "대기 중"
    },
    {
        "id": "step2",
        "name": "live_ticket_crawler.py",
        "title": "[배치 2] 인터파크 티켓 라이브 크롤링",
        "script": "scripts/live_ticket_crawler.py",
        "desc": "인터파크 콘서트/뮤지컬/전시/아동 실시간 예매 수집",
        "status": "PENDING",
        "message": "대기 중"
    },
    {
        "id": "step3",
        "name": "live_ticketlink_crawler.py",
        "title": "[배치 3] 티켓링크 전수 크롤링 & 대상연령 파싱",
        "script": "scripts/live_ticketlink_crawler.py",
        "desc": "티켓링크 전체 라이브 상품 전수 수집 및 target_age 파싱",
        "status": "PENDING",
        "message": "대기 중"
    },
    {
        "id": "step4",
        "name": "public_childcare_collector.py",
        "title": "[배치 4] 공공 키즈카페 & 육아 공간 수집",
        "script": "scripts/public_childcare_collector.py",
        "desc": "서울형 키즈카페 및 지자체 공공 육아 포털 데이터 수집",
        "status": "PENDING",
        "message": "대기 중"
    },
    {
        "id": "step5",
        "name": "place_search_collector.py",
        "title": "[배치 5] 카카오 로컬 시군구×테마 장소 수집",
        "script": "scripts/place_search_collector.py",
        "desc": "수도권 63개 시군구 × 8개 테마 카카오 로컬 장소 수집 (좌표 포함)",
        "status": "PENDING",
        "message": "대기 중"
    },
    {
        "id": "step6",
        "name": "generate_total_family_data.py",
        "title": "[배치 6] total_family_data 1차 데이터 통합",
        "script": "scripts/generate_total_family_data.py",
        "desc": "수집된 5개 소스 통합, 중복 제거 및 CSV/JSON 1차 생성",
        "status": "PENDING",
        "message": "대기 중"
    },
    {
        "id": "step7",
        "name": "enrich_total_family_data.py",
        "title": "[배치 7] LLM & 편의시설 2차 보강",
        "script": "scripts/enrich_total_family_data.py",
        "desc": "주차/수유실/기저귀갈이대 태그, 혼잡도/인기도 및 LLM 추천이유 생성",
        "status": "PENDING",
        "message": "대기 중"
    }
]

batch_state = {
    "is_running": False,
    "overall_progress": 0,
    "current_step_id": None,
    "status_msg": "대기 중",
    "steps": json.loads(json.dumps(BATCH_STEPS_TEMPLATE))
}

def execute_batch_pipeline():
    """배치 스크립트 7개를 순차 실행하고 실시간 상태를 갱신하는 비동기 쓰레드"""
    global is_collecting, last_collected_at, last_status_msg, batch_state
    is_collecting = True
    batch_state["is_running"] = True
    batch_state["status_msg"] = "배치 파이프라인 구동 중..."
    
    total_steps = len(batch_state["steps"])
    has_error = False

    for i, step in enumerate(batch_state["steps"]):
        script_path = os.path.join(BASE_DIR, step["script"])
        step["status"] = "RUNNING"
        step["message"] = "진행 중..."
        batch_state["current_step_id"] = step["id"]
        batch_state["overall_progress"] = int((i / total_steps) * 100)
        batch_state["status_msg"] = f"{step['title']} 실행 중..."
        print(f"\n▶ [{i+1}/{total_steps}] {step['title']} 실행 시작...")

        try:
            subprocess.run([sys.executable, script_path], check=True, cwd=BASE_DIR)
            step["status"] = "SUCCESS"
            step["message"] = "성공"
            print(f"✅ [{i+1}/{total_steps}] {step['title']} 완료!")
        except Exception as e:
            step["status"] = "ERROR"
            step["message"] = f"오류: {e}"
            has_error = True
            print(f"❌ [{i+1}/{total_steps}] {step['title']} 오류 발생: {e}")

    batch_state["overall_progress"] = 100
    batch_state["is_running"] = False
    batch_state["current_step_id"] = None

    if not has_error:
        last_collected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        last_status_msg = "완료되었습니다."
        batch_state["status_msg"] = "완료되었습니다."
        print(f"\n🎉 [배치 파이프라인] 모든 7개 배치가 성공적으로 완료되었습니다! ({last_collected_at})")
    else:
        last_status_msg = "일부 배치 실행 중 오류가 발생했습니다."
        batch_state["status_msg"] = "일부 배치 실행 중 오류가 발생했습니다."
        print(f"\n⚠️ [배치 파이프라인] 에러가 발생했습니다.")
        
    is_collecting = False

class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def do_GET(self):
        if self.path.startswith("/api/batch_status") or self.path.startswith("/api/status"):
            self.send_json({
                "is_collecting": is_collecting,
                "last_collected_at": last_collected_at,
                "last_status_msg": last_status_msg,
                "batch_state": batch_state
            })
            return
        super().do_GET()

    def do_POST(self):
        global is_collecting, batch_state
        if self.path.startswith("/api/refresh"):
            if is_collecting or batch_state["is_running"]:
                self.send_json({"success": False, "message": "이미 수집 배치 프로세스가 실행 중입니다."})
                return
            
            # 7단계 배치 상태 리셋
            batch_state["is_running"] = True
            batch_state["overall_progress"] = 0
            batch_state["current_step_id"] = "step1"
            batch_state["status_msg"] = "수집 및 보강 배치 파이프라인을 시작합니다..."
            batch_state["steps"] = json.loads(json.dumps(BATCH_STEPS_TEMPLATE))

            # 백그라운드 비동기 쓰레드로 배치 실행
            threading.Thread(target=execute_batch_pipeline, daemon=True).start()

            self.send_json({
                "success": True,
                "message": "수집 및 보강 배치 파이프라인이 시작되었습니다.",
                "batch_state": batch_state
            })
            return

        if self.path.startswith("/api/weather"):
            try:
                weather_script = os.path.join(BASE_DIR, "scripts", "fetch_weather.py")
                subprocess.run([sys.executable, weather_script], check=True, cwd=BASE_DIR)
                self.send_json({"success": True, "message": "주간 날씨 갱신 완료! (data/weather.csv 저장됨)"})
            except Exception as e:
                self.send_json({"success": False, "message": f"날씨 갱신 실패: {e}"})
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
    webbrowser.open(f"http://localhost:{PORT}/web/admin.html")

def main():
    print("==================================================")
    print("  AI 기반 주말 맞춤형 여가 추천 서비스 (API 서버 내장)")
    print("==================================================")
    print(f"로컬 웹 서버 주소: http://localhost:{PORT}/web/index.html")
    print(f"관리자 페이지 주소: http://localhost:{PORT}/web/admin.html")
    print(f"배치 상태 API: http://localhost:{PORT}/api/batch_status")
    print("==================================================")
    
    threading.Timer(1.0, open_browser).start()
    
    with ThreadedHTTPServer(("", PORT), CustomHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n웹 서버를 종료합니다.")
            sys.exit(0)

if __name__ == "__main__":
    main()
