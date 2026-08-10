"""
인터파크 티켓 (Interpark Tickets) 공식 실시간 웹 크롤러 & 엑셀 DB 자동 생성기
-----------------------------------------------------------------------------
실시간 크롤링 수집 카테고리:
  1. CONCERT  : 대형 콘서트, 락 페스티벌, 인디 공연
  2. MUSICAL  : 대형/중소형 뮤지컬
  3. DRAMA    : 대학로 인기 연극 및 정극
  4. CLASSIC  : 클래식 음악회, 오페라, 무용, 국악
  5. EXHIBIT  : 미술관/박물관 전시회, 미디어아트, 팝업스토어
  6. FAMILY   : 영유아/어린이 뮤지컬, 캐릭터쇼(티니핑/번개맨/뽀로로), 가족 극장

출력:
  - data/live_interpark_tickets.xlsx (엑셀 DB)
  - data/live_interpark_tickets.csv  (CSV DB)
  - 서비스 추천 DB (places.csv / events.csv / real_time_metrics.csv) 자동 동기화
"""
import requests
import json
import os
import sys
import csv
import re
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
import db_manager

EXCEL_PATH = os.path.join(BASE_DIR, "..", "data", "live_interpark_tickets.xlsx")
CSV_PATH   = os.path.join(BASE_DIR, "..", "data", "live_interpark_tickets.csv")

HEADERS = [
    "category", "goods_code", "title", "venue", "start_date", "end_date",
    "price_info", "booking_percent", "rank", "booking_url", "image_url", "ai_tags", "crawled_at"
]

# 인터파크 실시간 API 6대 카테고리 매핑
RANKING_CATEGORIES = {
    "CONCERT": "콘서트/페스티벌",
    "MUSICAL": "뮤지컬",
    "DRAMA":   "연극",
    "CLASSIC": "클래식/음악회",
    "EXHIBIT": "전시/행사",
    "KIDS":    "가족/어린이/아동"
}

def clean_date_str(d_str):
    """20260801 형태를 2026-08-01 형태로 변환"""
    if not d_str:
        return ""
    d_str = re.sub(r'[^\d]', '', str(d_str))
    if len(d_str) == 8:
        return f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:8]}"
    return d_str

def fetch_interpark_live_ranking(ranking_type: str, category_label: str) -> list[dict]:
    """인터파크 공식 실시간 랭킹 API 호출 및 크롤링 파싱"""
    url = f"https://tickets.interpark.com/api/ranking?period=D&page=1&pageSize=50&rankingTypes={ranking_type}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://tickets.interpark.com/contents/ranking"
    }

    try:
        r = requests.get(url, headers=headers, timeout=8)
        if r.status_code != 200:
            print(f"  [인터파크 API 오류 {r.status_code}] {ranking_type}")
            return []

        data = r.json()

        # 응답 구조 처리: dict 반환 시 concert, musical, drama 키 또는 list
        items = []
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, list) and len(v) > 0:
                    items = v
                    break
        elif isinstance(data, list):
            items = data

        results = []
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for item in items:
            goods_code = str(item.get("goodsCode", ""))
            title      = item.get("goodsName", "").strip()
            venue      = item.get("placeName", "").strip()
            start_d    = clean_date_str(item.get("playStartDate", ""))
            end_d      = clean_date_str(item.get("playEndDate", ""))
            price_info = item.get("salesPriceGrade", "") or "상세 페이지 참조"
            b_percent  = f"{item.get('bookingPercent', 0)}%"
            rank_num   = item.get("rank", 99)
            rel_url    = item.get("url", "")
            img_url    = item.get("imageUrl", "")

            # 예매 Full URL 구성
            full_url = f"https://tickets.interpark.com{rel_url}" if rel_url.startswith("/") else (rel_url or f"https://tickets.interpark.com/goods/{goods_code}")

            # 세그먼트 매칭 AI 태그 자동 생성
            family_score = 0.9 if ranking_type in ["FAMILY"] else (0.7 if ranking_type in ["EXHIBIT", "MUSICAL"] else 0.5)
            couple_score = 0.95 if ranking_type in ["CONCERT", "MUSICAL", "CLASSIC", "EXHIBIT"] else 0.6
            single_score = 0.9 if ranking_type in ["CONCERT", "DRAMA", "CLASSIC"] else 0.6

            tags = f"family:{family_score};couple:{couple_score};single:{single_score};{category_label};인터파크실시간"

            if title:
                results.append({
                    "category":        category_label,
                    "goods_code":      goods_code,
                    "title":           title,
                    "venue":           venue or "상세장소 참조",
                    "start_date":      start_d or datetime.now().strftime("%Y-%m-%d"),
                    "end_date":        end_d or (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d"),
                    "price_info":      price_info,
                    "booking_percent": b_percent,
                    "rank":            rank_num,
                    "booking_url":     full_url,
                    "image_url":       img_url,
                    "ai_tags":         tags,
                    "crawled_at":      now_str
                })

        print(f"  [인터파크 {category_label}] {len(results)}개 라이브 크롤링 성공!")
        return results

    except Exception as e:
        print(f"  [인터파크 {category_label} 예외] {e}")
        return []

def run_live_ticket_crawler():
    """인터파크 6대 카테고리 전체 라이브 크롤링 및 엑셀 DB 저장 + 추천 서비스 DB 동기화"""
    print("=" * 65)
    print("  인터파크 티켓 공식 실시간 웹 크롤러 (Interpark Ticket Live)")
    print("=" * 65)

    all_crawled_items = []

    for r_type, c_label in RANKING_CATEGORIES.items():
        items = fetch_interpark_live_ranking(r_type, c_label)
        all_crawled_items.extend(items)

    print("\n" + "=" * 65)
    print(f"[크롤링 총계] 실시간 크롤링 완료: 총 {len(all_crawled_items)}개 라이브 공연/전시/콘서트 추출!")
    print("=" * 65)

    if not all_crawled_items:
        print("크롤링 데이터가 없습니다.")
        return

    # 1. CSV DB 저장
    db_manager.ensure_data_dir()
    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADERS)
        w.writeheader()
        w.writerows(all_crawled_items)
    print(f"  [완료] CSV DB 저장 성공: {CSV_PATH}")

    # 2. 엑셀 DB (.xlsx) 저장
    try:
        import pandas as pd
        df = pd.DataFrame(all_crawled_items)
        df.to_excel(EXCEL_PATH, index=False, engine='openpyxl')
        print(f"  [완료] 엑셀 DB (.xlsx) 저장 성공: {EXCEL_PATH}")
    except Exception as e:
        print(f"  [엑셀 저장 예외] {e}")

    # 3. 추천 서비스 POI DB (places.csv / events.csv) 자동 동기화
    places = db_manager.load_places()
    sync_count = 0

    for item in all_crawled_items:
        v_name = item["venue"]
        if not v_name or len(v_name) < 2:
            continue

        # 장소가 DB에 없으면 신규 POI 장소로 자동 생성
        matched_pl = next((p for p in places if v_name in p["name"] or p["name"] in v_name), None)
        if not matched_pl:
            cat_mapping = {
                "콘서트/페스티벌": "복합문화공간",
                "뮤지컬":       "복합문화공간",
                "연극":         "복합문화공간",
                "클래식/음악회":   "복합문화공간",
                "전시/행사":     "미술관/전시",
                "가족/어린이/아동":"어린이/체험"
            }
            pid = db_manager.add_or_update_place(
                name=v_name,
                category=cat_mapping.get(item["category"], "복합문화공간"),
                address=f"서울/경기 {v_name}",
                latitude=37.5665,
                longitude=126.9780,
                is_parking=True,
                is_stroller=True,
                has_nursing=True,
                no_kids=False
            )
            db_manager.update_real_time_metric(place_id=pid, tmap_rank=999, seoul_crowd_level="LOW")
            places = db_manager.load_places() # refresh
        else:
            pid = matched_pl["place_id"]

        # 이벤트 등록
        db_manager.add_or_update_event(
            place_id=pid,
            title=item["title"],
            start_date=item["start_date"],
            end_date=item["end_date"],
            source_url=item["booking_url"],
            raw_description=f"[인터파크 예매 랭킹 {item['rank']}위] {item['category']} | 관람료: {item['price_info']} | 예매율: {item['booking_percent']}",
            ai_tags=item["ai_tags"]
        )
        sync_count += 1

    print(f"  [완료] 추천 서비스 DB (places.csv / events.csv) {sync_count}개 크롤링 항목 자동 반영 완료!")
    print("=" * 65)

if __name__ == "__main__":
    run_live_ticket_crawler()
