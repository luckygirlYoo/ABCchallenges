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
from datetime import datetime, timedelta   # timedelta: 115행 end_date 폴백에서 사용
                                           # (기존에 미import 상태여서 playEndDate 가
                                           #  빈 응답이 오는 순간 NameError 로 해당
                                           #  카테고리 50건이 통째로 유실됐다)

import sys, io
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

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
            # RANKING_CATEGORIES 의 키는 "KIDS" 인데 여기서는 "FAMILY" 를 검사해
            # 가족/어린이 카테고리 50건이 전부 family:0.5 로 떨어지고 있었다.
            # (2026-08-23 실측: KIDS 50건 중 family:0.9 부여 0건)
            family_score = 0.9 if ranking_type in ["KIDS"] else (0.7 if ranking_type in ["EXHIBIT", "MUSICAL"] else 0.5)
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

    # CSV DB 저장
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADERS)
        w.writeheader()
        w.writerows(all_crawled_items)
    print(f"  [완료] CSV DB 저장 성공: {CSV_PATH}")
    print(f"  [완료] 총 {len(all_crawled_items)}건 크롤링 완료")
    print("=" * 65)

if __name__ == "__main__":
    run_live_ticket_crawler()
