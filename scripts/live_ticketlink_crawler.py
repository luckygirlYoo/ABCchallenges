"""
티켓링크 (Ticketlink) 라이브 데이터 크롤러 v4.0
-----------------------------------------------------------------------------
수집 대상: 티켓링크 전체 라이브 상품 (인터파크 태깅 방식 적용)
태깅 분류: 가족/어린이/아동 상품은 'family:1.0;baby:1.0' 전용 태그 부착
"""
import requests
import json
import os
import sys
import io
import csv
import re
from datetime import datetime, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "..", "data", "live_ticketlink_tickets.csv")

HEADERS = [
    "source", "category", "product_id", "title", "venue", "start_date", "end_date",
    "target_age", "price_info", "booking_url", "image_url", "ai_tags", "crawled_at"
]

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.ticketlink.co.kr/"
}

SWEEP_PATTERNS = (
    [str(i) for i in range(10)] +
    [chr(c) for c in range(ord('a'), ord('z')+1)] +
    ['ㄱ','ㄴ','ㄷ','ㄹ','ㅁ','ㅂ','ㅅ','ㅇ','ㅈ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ'] +
    ['가','나','다','라','마','바','사','아','자','차','카','타','파','하'] +
    ['전시','공연','뮤지컬','콘서트','행사','어린이','티켓','예매','페스티벌','스포츠','클래식','국악','무용','연극','체험'] +
    ['서울','경기','인천','부산','대구','광주','대전','울산','세종','강원','충북','충남','전북','전남','경북','경남','제주']
)

KIDS_KEYWORDS = [
    "어린이", "아동", "키즈", "유아", "가족", "뽀로로", "티니핑", "하츄핑", "핑크퐁",
    "타요", "카봇", "브레드이발소", "캐치", "인형극", "동화", "아기", "아동극", "가족극"
]

def parse_price(grade_price_list):
    if not grade_price_list or not isinstance(grade_price_list, list):
        return "티켓링크 예매가 참조"
    prices = [p.get("salePrice") for p in grade_price_list if p.get("salePrice") is not None]
    if not prices:
        return "티켓링크 예매가 참조"
    min_p, max_p = min(prices), max(prices)
    if min_p == max_p:
        return f"{min_p:,}원"
    return f"{min_p:,}원 ~ {max_p:,}원"

def extract_target_age(title, sub_title, cat_name):
    combined = f"{title} {sub_title} {cat_name}"
    
    if any(k in combined for k in ["19세", "청소년 관람불가", "19금", "성인전용"]):
        return "19세 이상 (청소년 관람불가)"
    if "15세" in combined:
        return "15세 이상 관람가"
    if "12세" in combined:
        return "12세 이상 관람가"
    if any(k in combined for k in ["8세", "초등학생"]):
        return "8세 이상 (초등학생 이상)"
    if "24개월" in combined:
        return "24개월 이상 관람가"
    if any(k in combined for k in ["36개월", "3세"]):
        return "36개월 이상 (3세 이상)"
    if any(k in combined for k in ["4세", "5세", "6세", "7세"]):
        return "미취학 아동 (4~7세)"
        
    if any(k in combined for k in KIDS_KEYWORDS):
        return "전체 관람가 (가족/어린이 동반)"
    if any(k in combined for k in ["전시", "미술", "박물관", "체험", "팝업"]):
        return "전체 관람가 (전 연령)"
    if any(k in combined for k in ["콘서트", "페스티벌", "클래식", "오페라", "무용"]):
        return "8세 이상 (전체/초등 이상)"
    if "연극" in combined or "뮤지컬" in combined:
        return "8세 이상 관람가"
        
    return "전체 관람가"

def generate_ai_tags(title, sub_title, cat_name, loc_name, is_kids):
    tags = []
    if is_kids:
        tags.append("family:1.0;baby:1.0;toddler:1.0;가족어린이동반")
    elif "전시" in cat_name or "미술" in title:
        tags.append("family:0.8;couple:1.0;single:0.9;exhibition:1.0")
    else:
        tags.append("family:0.3;couple:1.0;single:0.9")
        
    tags.append("티켓링크")
    if cat_name: tags.append(cat_name)
    if loc_name: tags.append(loc_name)
    
    return ";".join(tags)

def crawl_ticketlink_all() -> list[dict]:
    print("  [티켓링크 크롤러 v4.0] 가족/어린이/아동 전용 태깅 수집 시작...")
    
    unique_items = {}
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    api_url = "https://www.ticketlink.co.kr/search/getSearchList"

    for query in SWEEP_PATTERNS:
        try:
            r = requests.get(api_url, headers=HTTP_HEADERS, params={"query": query}, timeout=6)
            if r.status_code == 200:
                raw_list = r.json().get("coexResultList", [])
                for item in raw_list:
                    pid = item.get("productId")
                    if not pid or pid in unique_items:
                        continue

                    title    = item.get("productName", "").strip()
                    sub_title= item.get("subTitle", "").strip()
                    place    = item.get("placeName", "").strip()
                    hall     = item.get("hallName", "").strip()
                    venue    = f"{place} {hall}".strip() or "티켓링크 지정 전시장"

                    start_raw = item.get("startDate", "")
                    end_raw   = item.get("endDate", "")
                    start_date = start_raw[:10] if start_raw else now_str[:10]
                    end_date   = end_raw[:10] if end_raw else (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")

                    price_str  = parse_price(item.get("grade_price_list"))
                    img_url    = item.get("imageUrl", "")
                    loc_name   = item.get("locationName", "")
                    raw_cat    = item.get("productClassName", "공연")
                    
                    combined_text = f"{title} {sub_title} {raw_cat}"
                    is_kids = any(k in combined_text for k in KIDS_KEYWORDS)
                    
                    cat_name = "가족/어린이" if is_kids else raw_cat
                    target_age = extract_target_age(title, sub_title, raw_cat)
                    ai_tags    = generate_ai_tags(title, sub_title, raw_cat, loc_name, is_kids)

                    unique_items[pid] = {
                        "source":      "티켓링크",
                        "category":    cat_name,
                        "product_id":  str(pid),
                        "title":       title,
                        "venue":       venue,
                        "start_date":  start_date,
                        "end_date":    end_date,
                        "target_age":  target_age,
                        "price_info":  price_str,
                        "booking_url": f"https://www.ticketlink.co.kr/product/{pid}",
                        "image_url":   img_url,
                        "ai_tags":     ai_tags,
                        "crawled_at":  now_str
                    }
        except Exception:
            pass

    results = list(unique_items.values())
    print(f"  [티켓링크 크롤러 v4.0] 총 {len(results)}건 수집 완료!")
    return results

def run_ticketlink_crawler():
    print("=" * 65)
    print("  티켓링크 (Ticketlink) 크롤러 (가족/어린이/아동 태깅 전용) v4.0")
    print("=" * 65)

    items = crawl_ticketlink_all()

    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADERS)
        w.writeheader()
        w.writerows(items)

    print(f"  [완료] 티켓링크 CSV 저장: {CSV_PATH}")
    print(f"  [완료] 총 {len(items)}건 저장 완료!")
    print("=" * 65)

if __name__ == "__main__":
    run_ticketlink_crawler()
