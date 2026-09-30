import sys, io, os
try:
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
except Exception:
    pass
import http.server
import socketserver
import webbrowser
import threading
import json
import subprocess
from datetime import datetime

PORT = int(os.environ.get("PORT", 8080))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

is_collecting = False
last_collected_at = "미실행"
last_status_msg = ""

# ── 15단계 배치 상태 정의 (1~8 원천수집 → 9~11 가족통합 → 12 커플통합 → 13~15 가족 후처리) ──
BATCH_STEPS_TEMPLATE = [
    # ── 1단계: 원천 데이터 수집 (가족·커플·싱글 10개 소스 전수 수집) ──
    {
        "id": "step1",
        "name": "culture_event_collector.py",
        "title": "[배치 1] 공공 문화행사 API & 미술관 수집",
        "script": "scripts/culture_event_collector.py",
        "desc": "서울·경기 공공 문화행사 API 및 미술관/전시장 수집 (가족·커플·싱글 공용 소스)",
        "status": "PENDING",
        "message": "대기 중"
    },
    {
        "id": "step2",
        "name": "live_ticket_crawler.py",
        "title": "[배치 2] 인터파크 티켓 라이브 크롤링",
        "script": "scripts/live_ticket_crawler.py",
        "desc": "인터파크 콘서트/뮤지컬/전시/아동 실시간 예매 수집 (가족·커플·싱글 공용 소스)",
        "status": "PENDING",
        "message": "대기 중"
    },
    {
        "id": "step3",
        "name": "live_ticketlink_crawler.py",
        "title": "[배치 3] 티켓링크 전수 크롤링 & 대상연령 파싱",
        "script": "scripts/live_ticketlink_crawler.py",
        "desc": "티켓링크 전체 라이브 상품 전수 수집 및 target_age 파싱 (가족·커플·싱글 공용 소스)",
        "status": "PENDING",
        "message": "대기 중"
    },
    {
        "id": "step4",
        "name": "public_childcare_collector.py",
        "title": "[배치 4] 공공 키즈카페 & 육아 공간 수집",
        "script": "scripts/public_childcare_collector.py",
        "desc": "서울형 키즈카페 및 지자체 공공 육아 포털 데이터 수집 (가족 전용 소스)",
        "status": "PENDING",
        "message": "대기 중"
    },
    {
        "id": "step5",
        "name": "place_search_collector.py",
        "title": "[배치 5] 카카오 로컬 시군구×테마 장소 수집",
        "script": "scripts/place_search_collector.py",
        "desc": "수도권 63개 시군구 × 8개 테마 카카오 로컬 장소 수집 (가족 전용 소스, 좌표 포함)",
        "status": "PENDING",
        "message": "대기 중"
    },
    {
        "id": "step6",
        "name": "kopis_performance_collector.py",
        "title": "[배치 6] KOPIS 공연예술 수집",
        "script": "scripts/kopis_performance_collector.py",
        "desc": "KOPIS 공연목록·상세·시설·예매상황판 수집 (커플 전용 소스, 좌표·예매순위 자체 보유)",
        "status": "PENDING",
        "message": "대기 중"
    },
    {
        "id": "step7",
        "name": "popup_collector.py",
        "title": "[배치 7] 팝업스토어 수집 (팝가)",
        "script": "scripts/popup_collector.py",
        "desc": "popga.co.kr 팝업스토어 전수 수집 (커플 전용 소스)",
        "status": "PENDING",
        "message": "대기 중"
    },
    {
        "id": "step8",
        "name": "visitkorea_couple_collector.py",
        "title": "[배치 8] 커플/데이트 명소 수집 (대한민국 구석구석)",
        "script": "scripts/visitkorea_couple_collector.py",
        "desc": "야경·커플데이트·연인 태그 기반 명소 수집 (커플 전용 소스)",
        "status": "PENDING",
        "message": "대기 중"
    },
    {
        "id": "step9",
        "name": "naver_local_single_collector.py",
        "title": "[배치 9] 싱글매니아 라이프스타일 장소 수집",
        "script": "scripts/naver_local_single_collector.py",
        "desc": "독립서점/북카페/아트숍/명상센터/고궁/사찰/갤러리 등 네이버 로컬 API 수집 (싱글 전용 소스)",
        "status": "PENDING",
        "message": "대기 중"
    },
    {
        "id": "step10",
        "name": "independent_bookstore_collector.py",
        "title": "[배치 10] 독립서점 공공데이터 수집",
        "script": "scripts/independent_bookstore_collector.py",
        "desc": "문화공공데이터광장 전국 독립서점 및 운영정보 API 수집 (싱글 전용 소스)",
        "status": "PENDING",
        "message": "대기 중"
    },
    # ── 2단계: 실시간 정보 및 부가 데이터 수집 ──
    {
        "id": "step11",
        "name": "collect_seoul_congestion.py",
        "title": "[배치 11] 서울시 실시간 인파 혼잡도 수집",
        "script": "scripts/collect_seoul_congestion.py",
        "desc": "관측지점 121곳의 실시간 혼잡도·인구·연령비 수집 (가족·커플·싱글 공통 사용)",
        "status": "PENDING",
        "message": "대기 중"
    },
    {
        "id": "step12",
        "name": "collect_amenities.py",
        "title": "[배치 12] 편의시설 수집 (네이버 플레이스)",
        "script": "scripts/collect_amenities.py",
        "desc": "카드가 있는 유형만 조회해 확인된 편의시설 태그 부여",
        "status": "PENDING",
        "message": "대기 중"
    },
    # ── 3단계: 가족 1차 통합, 좌표 보정 & LLM 태그 보강 ──
    {
        "id": "step13",
        "name": "generate_total_family_data.py",
        "title": "[배치 13] total_family_data 1차 데이터 통합",
        "script": "scripts/generate_total_family_data.py",
        "desc": "수집된 5개 소스 통합, 중복 제거 및 CSV/JSON 1차 생성",
        "status": "PENDING",
        "message": "대기 중"
    },
    {
        "id": "step14",
        "name": "geocode_event_venues.py",
        "title": "[배치 14] 공연·행사 공연장 좌표 부여 & 캐시 갱신",
        "script": "scripts/geocode_event_venues.py",
        "desc": "공연 제목 대신 region 의 공연장명으로 좌표 조회 (반환 장소명 검증). venue_geocode_cache.json 을 갱신하여 커플 통합 단계에 공유",
        "status": "PENDING",
        "message": "대기 중"
    },
    {
        "id": "step15",
        "name": "dedupe_places.py",
        "title": "[배치 15] 좌표 기반 장소 중복 제거",
        "script": "scripts/dedupe_places.py",
        "desc": "같은 좌표·유사 이름의 장소 병합 (행사는 병합하지 않음)",
        "args": ["--apply"],
        "status": "PENDING",
        "message": "대기 중"
    },
    {
        "id": "step16",
        "name": "enrich_total_family_data.py",
        "title": "[배치 16] LLM & 설명/태그 보강",
        "script": "scripts/enrich_total_family_data.py",
        "desc": "편의시설 태그 및 설명/추천이유 LLM 보강",
        "args": ["--batch-mode"],
        "status": "PENDING",
        "message": "대기 중"
    },
    # ── 4단계: 커플 & 싱글매니아 최종 데이터셋 통합 ──
    {
        "id": "step17",
        "name": "generate_total_couple_data.py",
        "title": "[배치 17] total_couple_data 데이터 통합",
        "script": "scripts/generate_total_couple_data.py",
        "desc": "KOPIS·팝업·커플명소 + 티켓링크/인터파크/문화행사 6개 소스를 커플 탭용으로 최종 통합",
        "args": ["--batch-mode"],
        "status": "PENDING",
        "message": "대기 중"
    },
    {
        "id": "step18",
        "name": "enrich_total_single_data.py",
        "title": "[배치 18] total_single_data 데이터 통합 & LLM 보강",
        "script": "scripts/enrich_total_single_data.py",
        "desc": "싱글매니아 6대 카테고리로 분류·필터링 후 CSV/JSON/XLSX 최종 통합 생성 및 LLM 보강",
        "args": ["--batch-mode"],
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

stop_requested = False

def execute_batch_pipeline(start_step_id=None, single_step_id=None):
    """배치 스크립트를 순차 또는 부분/단일 실행하고 실시간 상태를 갱신하는 비동기 쓰레드"""
    global is_collecting, last_collected_at, last_status_msg, batch_state, stop_requested
    is_collecting = True
    stop_requested = False
    batch_state["is_running"] = True

    steps = batch_state["steps"]
    total_steps = len(steps)
    has_error = False

    if single_step_id:
        target_indices = [i for i, s in enumerate(steps) if s["id"] == single_step_id]
        start_idx = target_indices[0] if target_indices else 0
        end_idx = start_idx + 1
        batch_state["status_msg"] = f"[{steps[start_idx]['title']}] 단일 단계 실행 중..."
    elif start_step_id:
        target_indices = [i for i, s in enumerate(steps) if s["id"] == start_step_id]
        start_idx = target_indices[0] if target_indices else 0
        end_idx = total_steps
        batch_state["status_msg"] = f"[{steps[start_idx]['title']}]부터 배치 파이프라인 구동 중..."
        # start_idx부터 끝까지 상태 PENDING으로 초기화
        for k in range(start_idx, total_steps):
            steps[k]["status"] = "PENDING"
            steps[k]["message"] = "대기 중"
    else:
        start_idx = 0
        end_idx = total_steps
        batch_state["status_msg"] = "배치 파이프라인 전체 구동 중..."
        batch_state["steps"] = json.loads(json.dumps(BATCH_STEPS_TEMPLATE))
        steps = batch_state["steps"]

    for i in range(start_idx, end_idx):
        if stop_requested:
            print("⏹️ 사용자에 의해 배치 중지됨.")
            batch_state["status_msg"] = "사용자에 의해 배치가 중지되었습니다."
            break

        step = steps[i]
        script_path = os.path.join(BASE_DIR, step["script"])
        step["status"] = "RUNNING"
        step["message"] = "진행 중..."
        batch_state["current_step_id"] = step["id"]
        batch_state["overall_progress"] = int(((i + 1) / total_steps) * 100)
        batch_state["status_msg"] = f"{step['title']} 실행 중..."
        print(f"\n▶ [{i+1}/{total_steps}] {step['title']} 실행 시작...")

        try:
            cmd = [sys.executable, script_path] + list(step.get("args", []))
            subprocess.run(cmd, check=True, cwd=BASE_DIR)
            step["status"] = "SUCCESS"
            step["message"] = "성공"
            print(f"✅ [{i+1}/{total_steps}] {step['title']} 완료!")
        except Exception as e:
            step["status"] = "ERROR"
            step["message"] = f"오류: {e}"
            has_error = True
            print(f"❌ [{i+1}/{total_steps}] {step['title']} 오류 발생: {e}")
            if not single_step_id:
                batch_state["status_msg"] = f"[{step['title']}] 오류 발생으로 중단됨."
                break

    batch_state["is_running"] = False
    batch_state["current_step_id"] = None
    is_collecting = False

    if not has_error and not stop_requested:
        last_collected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if single_step_id:
            last_status_msg = f"[{steps[start_idx]['title']}] 단일 실행이 완료되었습니다."
        else:
            last_status_msg = "완료되었습니다."
            batch_state["overall_progress"] = 100
        batch_state["status_msg"] = last_status_msg
    elif stop_requested:
        last_status_msg = "배치가 사용자에 의해 중지되었습니다."
        batch_state["status_msg"] = last_status_msg
    else:
        last_status_msg = "일부 배치 실행 중 오류가 발생했습니다."

class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def end_headers(self):
        # JS, CSS 파일은 캐시 금지 (개발/갱신 시 즉시 반영)
        path = self.path.split('?')[0]
        if path.endswith('.js') or path.endswith('.css'):
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
        super().end_headers()

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
        global is_collecting, batch_state, stop_requested
        if self.path.startswith("/api/stop"):
            stop_requested = True
            batch_state["status_msg"] = "배치 중지 요청됨..."
            self.send_json({"success": True, "message": "배치 중지 요청이 전달되었습니다."})
            return

        if self.path.startswith("/api/refresh") or self.path.startswith("/api/run_step"):
            if is_collecting or batch_state["is_running"]:
                self.send_json({"success": False, "message": "이미 수집 배치 프로세스가 실행 중입니다."})
                return

            mode = "full"
            start_step = None
            single_step = None

            if "?" in self.path:
                from urllib.parse import parse_qs, urlparse
                query_params = parse_qs(urlparse(self.path).query)
                mode = query_params.get("mode", ["full"])[0]
                start_step = query_params.get("start_step", [None])[0]
                single_step = query_params.get("step_id", [None])[0]

            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                try:
                    raw_body = self.rfile.read(content_length).decode('utf-8')
                    body = json.loads(raw_body)
                    mode = body.get("mode", mode)
                    start_step = body.get("start_step", start_step)
                    single_step = body.get("step_id", single_step)
                except Exception:
                    pass

            if self.path.startswith("/api/run_step"):
                if not single_step and start_step:
                    single_step = start_step

            if mode == "resume" and not start_step:
                for s in batch_state["steps"]:
                    if s["status"] in ("ERROR", "PENDING"):
                        start_step = s["id"]
                        break

            threading.Thread(
                target=execute_batch_pipeline,
                kwargs={"start_step_id": start_step, "single_step_id": single_step},
                daemon=True
            ).start()

            msg = "배치가 시작되었습니다."
            if single_step:
                msg = f"단계 ({single_step}) 단일 실행이 시작되었습니다."
            elif start_step:
                msg = f"단계 ({start_step})부터 배치가 시작되었습니다."

            self.send_json({
                "success": True,
                "message": msg,
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
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

def open_browser():
    try:
        webbrowser.open(f"http://localhost:{PORT}/web/admin.html")
    except Exception:
        pass

def main():
    print("==================================================")
    print("  AI 기반 주말 맞춤형 여가 추천 서비스 (API 서버 내장)")
    print("==================================================")
    print(f"서버 바인딩 포트: {PORT}")
    print(f"로컬 웹 서버 주소: http://localhost:{PORT}/web/index.html")
    print(f"관리자 페이지 주소: http://localhost:{PORT}/web/admin.html")
    print(f"배치 상태 API: http://localhost:{PORT}/api/batch_status")
    print("==================================================")
    
    if os.environ.get("PORT") is None:
        threading.Timer(1.0, open_browser).start()
    
    with ThreadedHTTPServer(("", PORT), CustomHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n웹 서버를 종료합니다.")
            sys.exit(0)

if __name__ == "__main__":
    main()
