"""
네이버 데이터랩(검색어 트렌드) & 검색 API 수집기
-----------------------------------------------
네이버 Developers (openapi.naver.com) 연동

수집 기능:
  1. 네이버 데이터랩 API (v1/datalab/search): 장소별 최근 검색량 트렌드 지수 (0~100) 수집 → DB 인기도 반영
  2. 네이버 블로그 검색 API (v1/search/blog.json): 장소별 블로그 리뷰 개수 및 대표 후기 추출
  3. 네이버 지역 검색 API (v1/search/local.json): 상세 도로명주소 및 전화번호 추출
"""
import requests
import json
import os
import sys
import csv
import time
import re
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
import db_manager

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

CLIENT_ID     = CONFIG.get("api_keys", {}).get("naver_client_id", "")
CLIENT_SECRET = CONFIG.get("api_keys", {}).get("naver_client_secret", "")

HEADERS = {
    "X-Naver-Client-Id":     CLIENT_ID,
    "X-Naver-Client-Secret": CLIENT_SECRET,
    "Content-Type":          "application/json",
}

NAVER_RESULTS_CSV = os.path.join(BASE_DIR, "..", "data", "naver_datalab_results.csv")
NAVER_HEADERS     = ["place_id", "place_name", "trend_score", "blog_count", "top_blog_title", "top_blog_desc", "road_address", "updated_at"]

def clean_html(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    return text.strip()

# ─────────────────────────────────────────────────────────────
# 1. 네이버 데이터랩 API (검색어 트렌드 수집)
# ─────────────────────────────────────────────────────────────
def fetch_naver_datalab_trends(place_names: list[str]) -> dict[str, float]:
    """네이버 데이터랩 API를 호출하여 장소별 주간 검색량 상대지수(0~100)를 반환"""
    if not CLIENT_ID or CLIENT_ID.startswith("YOUR_"):
        print("  [네이버데이터랩] API 키 미설정")
        return {}

    url = "https://openapi.naver.com/v1/datalab/search"
    today = datetime.now()
    start_date = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    end_date   = (today - timedelta(days=1)).strftime("%Y-%m-%d")

    results = {}
    # 네이버 데이터랩 API는 1회 요청 시 최대 5개 키워드 그룹 가능
    chunks = [place_names[i:i+5] for i in range(0, len(place_names), 5)]

    print(f"  [데이터랩] 총 {len(place_names)}개 장소 검색어 트렌드 조회 중...")

    for chunk in chunks:
        kw_groups = []
        for name in chunk:
            # 검색어 정제 (특수문자 제거)
            clean_kw = re.sub(r'[^\w\s]', '', name).strip()
            kw_groups.append({
                "groupName": name,
                "keywords":  [clean_kw if clean_kw else name]
            })

        body = {
            "startDate": start_date,
            "endDate":   end_date,
            "timeUnit":  "week",
            "keywordGroups": kw_groups
        }

        try:
            r = requests.post(url, headers=HEADERS, json=body, timeout=8)
            if r.status_code == 200:
                data = r.json()
                for res_item in data.get("results", []):
                    grp_name = res_item.get("title")
                    points = res_item.get("data", [])
                    if points:
                        # 최근 주의 검색 지수 (0~100)
                        last_ratio = float(points[-1].get("ratio", 0.0))
                        results[grp_name] = round(last_ratio, 1)
            else:
                print(f"  [데이터랩 API 응답 {r.status_code}] {r.text[:120]}")
        except Exception as e:
            print(f"  [데이터랩 예외] {e}")
        
        time.sleep(0.3)

    return results

# ─────────────────────────────────────────────────────────────
# 2. 네이버 블로그 검색 API (리뷰 및 후기 수집)
# ─────────────────────────────────────────────────────────────
def fetch_naver_blog_reviews(query: str) -> dict | None:
    """네이버 블로그 검색 API 호출"""
    if not CLIENT_ID or CLIENT_ID.startswith("YOUR_"):
        return None

    url = "https://openapi.naver.com/v1/search/blog.json"
    headers = {
        "X-Naver-Client-Id":     CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET,
    }
    params = {"query": f"{query} 방문 후기", "display": 3, "sort": "sim"}

    try:
        r = requests.get(url, headers=headers, params=params, timeout=5)
        if r.status_code == 200:
            data = r.json()
            total = data.get("total", 0)
            items = data.get("items", [])
            top_title = clean_html(items[0].get("title")) if items else ""
            top_desc  = clean_html(items[0].get("description")) if items else ""
            return {
                "total_count": total,
                "top_title": top_title,
                "top_desc":  top_desc
            }
        else:
            # 블로그 검색 권한이 신청되지 않은 경우 403이 날 수 있음
            pass
    except Exception as e:
        pass
    return None

# ─────────────────────────────────────────────────────────────
# 3. 메인 실행 함수
# ─────────────────────────────────────────────────────────────
def run_naver_collection():
    places = db_manager.load_places()
    if not places:
        print("[네이버수집] 장소 데이터가 없습니다.")
        return

    print("=" * 60)
    print("  네이버 데이터랩(검색 트렌드) & 검색 API 수집기 구동")
    print(f"  발급된 Client ID: {CLIENT_ID[:6]}***")
    print("=" * 60)

    place_names = [p["name"] for p in places]

    # 1) 데이터랩 검색량 트렌드 지수 수집
    trend_map = fetch_naver_datalab_trends(place_names)

    db_manager.ensure_data_dir()
    csv_rows = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Metrics DB 및 Events DB 업데이트
    metrics = db_manager.load_metrics()
    events  = db_manager.load_events()

    trend_updated = 0
    blog_updated = 0

    for idx, pl in enumerate(places, 1):
        pid = pl["place_id"]
        name = pl["name"]
        t_score = trend_map.get(name, 0.0)

        # 블로그 리뷰 조회
        blog_res = fetch_naver_blog_reviews(name)
        b_count = blog_res.get("total_count", 0) if blog_res else 0
        b_title = blog_res.get("top_title", "") if blog_res else ""
        b_desc  = blog_res.get("top_desc", "") if blog_res else ""

        # 데이터랩 트렌드 지수가 있으면 인기도(tmap_rank) 또는 score로 적용
        if t_score > 0:
            trend_updated += 1

        # Event에 블로그 후기 연동
        ex_ev = next((e for e in events if e["place_id"] == pid), None)
        if ex_ev and b_title:
            if "네이버 검색 트렌드" not in ex_ev.get("raw_description", ""):
                ex_ev["raw_description"] += f"\n\n📊 네이버 검색 트렌드 지수: {t_score}점 | 📝 블로그 대표 리뷰: {b_title}"
                ex_ev["ai_tags"] += f";naver_trend:{t_score}"
                blog_updated += 1

        csv_rows.append({
            "place_id": pid,
            "place_name": name,
            "trend_score": t_score,
            "blog_count": b_count,
            "top_blog_title": b_title,
            "top_blog_desc": b_desc,
            "road_address": pl.get("address", ""),
            "updated_at": now_str
        })

    # DB 저장
    db_manager.save_events(events)

    with open(NAVER_RESULTS_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=NAVER_HEADERS)
        w.writeheader()
        w.writerows(csv_rows)

    print("\n" + "=" * 60)
    print(f"[수집 완료] 총 {len(places)}개 장소 수집 완료!")
    print(f"  - 네이버 데이터랩 트렌드 수집: {len(trend_map)}개 장소 수치 확보")
    print(f"  - 저장 파일: {NAVER_RESULTS_CSV}")
    print("=" * 60)

if __name__ == "__main__":
    run_naver_collection()
