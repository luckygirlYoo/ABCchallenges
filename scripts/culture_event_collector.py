"""
공연/전시 이벤트 데이터 수집기
--------------------------------------------
수집 소스:
  1. 공공데이터포털 - 공연전시정보조회서비스 (data.go.kr) [API]
  2. 서울시 문화행사 API (data.seoul.go.kr) [API]
  3. 국립현대미술관 (mmca.go.kr) [크롤링 - robots.txt 허용]
  4. 서울시립미술관 (sema.seoul.go.kr) [크롤링 - 허용]
  5. 세종문화회관 (sejongpac.or.kr) [크롤링 - 일부 허용]
  6. 네이버 데이터랩 API [검색 트렌드 인기도]

[API 키 발급]
- 공연전시 API : data.go.kr → '공연전시정보조회서비스' 검색 → 활용신청 → tour_api_key 사용
- 서울시 문화행사: data.seoul.go.kr → seoul_api_key 사용
- 네이버 데이                               `터랩: developers.naver.com → 앱 등록 → naver_client_id, naver_client_secret
"""
import sys, io
import requests
import json
import os
import csv
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

TOUR_KEY    = CONFIG.get("api_keys", {}).get("tour_api_key", "")
SEOUL_KEY   = CONFIG.get("api_keys", {}).get("seoul_api_key", "")
NAVER_ID    = CONFIG.get("api_keys", {}).get("naver_client_id", "")
NAVER_SEC   = CONFIG.get("api_keys", {}).get("naver_client_secret", "")

today = datetime.now()
DATE_FROM = today.strftime("%Y%m%d")
DATE_TO   = (today + timedelta(days=60)).strftime("%Y%m%d")


# ─────────────────────────────────────────────────────
# 1. 공공데이터포털 — 공연전시정보조회서비스
# ─────────────────────────────────────────────────────
def fetch_culture_events_public_api(rows=100, area="서울"):
    """data.go.kr 공연전시정보 API 수집 (서울/경기 필터)"""
    if not TOUR_KEY or TOUR_KEY.startswith("YOUR_"):
        print("  [공연전시API] 키 없음 → 건너뜀")
        return []

    url = "https://apis.data.go.kr/B553457/nopenapi/rest/publicperformancedisplays/period"
    params = {
        "serviceKey": TOUR_KEY,
        "from":       DATE_FROM,
        "to":         DATE_TO,
        "rows":       rows,
        "_type":      "json",
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        items = data.get("msgBody", {}).get("perforList", [])
        print(f"  [공연전시API] {len(items)}건 수집 완료")
        results = []
        for item in items:
            title   = item.get("title", "")
            place   = item.get("place", "")
            start   = item.get("startDate", "").replace(".", "-")[:10]
            end     = item.get("endDate", "").replace(".", "-")[:10]
            genre   = item.get("genrenm", "")
            realmNm = item.get("realmName", "")
            url_link = item.get("url", "")
            thumbnail = item.get("thumbnail", "")
            results.append({
                "title": title, "place": place, "start": start,
                "end": end, "genre": genre, "realm": realmNm,
                "url": url_link, "thumbnail": thumbnail,
                "source": "공공데이터포털",
            })
        return results
    except Exception as e:
        print(f"  [공연전시API 오류] {e}")
        return []


# ─────────────────────────────────────────────────────
# 2. 서울시 문화행사 API
# ─────────────────────────────────────────────────────
def fetch_seoul_culture_events(rows=100):
    """서울시 문화행사 정보 API"""
    if not SEOUL_KEY or SEOUL_KEY.startswith("YOUR_"):
        print("  [서울문화API] 키 없음 → 건너뜀")
        return []
    url = f"http://openapi.seoul.go.kr:8088/{SEOUL_KEY}/json/culturalEventInfo/1/{rows}/"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        items = data.get("culturalEventInfo", {}).get("row", [])
        print(f"  [서울문화API] {len(items)}건 수집 완료")
        results = []
        for item in items:
            results.append({
                "title":  item.get("TITLE", ""),
                "place":  item.get("PLACE", ""),
                "start":  item.get("STRTDATE", "")[:10],
                "end":    item.get("END_DATE", "")[:10],
                "genre":  item.get("CODENAME", ""),
                "realm":  item.get("MAIN_IMG", ""),
                "url":    item.get("HMPG_ADDR", ""),
                "thumbnail": item.get("MAIN_IMG", ""),
                "source": "서울시 문화행사",
            })
        return results
    except Exception as e:
        print(f"  [서울문화API 오류] {e}")
        return []


# ─────────────────────────────────────────────────────
# 3. 국립현대미술관 크롤링 (robots.txt 허용, 비상업 목적)
# ─────────────────────────────────────────────────────
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; WeekendBot/1.0; research)"}

def crawl_mmca():
    """국립현대미술관 전시 목록 크롤링"""
    url = "https://www.mmca.go.kr/exhibitions/progressList.do"
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select(".exhibition-list li") or soup.select(".exh-list li")
        results = []
        for item in items:
            title_el = item.select_one(".title, h3, .tit")
            period_el = item.select_one(".date, .period, .term")
            title  = title_el.get_text(strip=True) if title_el else ""
            period = period_el.get_text(strip=True) if period_el else ""
            if title:
                results.append({
                    "title": title, "place": "국립현대미술관",
                    "start": today.strftime("%Y-%m-%d"),
                    "end":   (today + timedelta(days=60)).strftime("%Y-%m-%d"),
                    "genre": "전시", "realm": "미술", "url": url,
                    "thumbnail": "", "source": "MMCA",
                    "period_raw": period,
                })
        print(f"  [MMCA 크롤링] {len(results)}건 수집")
        return results
    except Exception as e:
        print(f"  [MMCA 오류] {e}")
        return []


def crawl_sema():
    """서울시립미술관 전시 목록 크롤링"""
    url = "https://sema.seoul.go.kr/kr/exhibition/exhToday"
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select(".list-gallery li, .exh-item")
        results = []
        for item in items:
            title_el = item.select_one(".tit, h3, .title")
            title = title_el.get_text(strip=True) if title_el else ""
            period_el = item.select_one(".date, .period")
            period = period_el.get_text(strip=True) if period_el else ""
            if title:
                results.append({
                    "title": title, "place": "서울시립미술관",
                    "start": today.strftime("%Y-%m-%d"),
                    "end":   (today + timedelta(days=60)).strftime("%Y-%m-%d"),
                    "genre": "전시", "realm": "미술",
                    "url": url, "thumbnail": "", "source": "SeMA",
                    "period_raw": period,
                })
        print(f"  [SeMA 크롤링] {len(results)}건 수집")
        return results
    except Exception as e:
        print(f"  [SeMA 오류] {e}")
        return []


def crawl_sac():
    """예술의전당 공연 목록 크롤링"""
    url = "https://www.sac.or.kr/site/main/show/showList"
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        items = soup.select(".performance-list li, .show-list li, .list li")
        results = []
        for item in items[:20]:  # 최대 20개
            title_el = item.select_one("h3, .tit, .title, strong")
            title = title_el.get_text(strip=True) if title_el else ""
            date_el = item.select_one(".date, .period, .term")
            date_txt = date_el.get_text(strip=True) if date_el else ""
            place_el = item.select_one(".place, .hall, .venue")
            place = (place_el.get_text(strip=True) if place_el else "예술의전당")
            if title and len(title) > 2:
                results.append({
                    "title": title, "place": place or "예술의전당",
                    "start": today.strftime("%Y-%m-%d"),
                    "end":   (today + timedelta(days=30)).strftime("%Y-%m-%d"),
                    "genre": "공연", "realm": "클래식/오페라",
                    "url": "https://www.sac.or.kr",
                    "thumbnail": "", "source": "예술의전당",
                    "period_raw": date_txt,
                })
        print(f"  [SAC 크롤링] {len(results)}건 수집")
        return results
    except Exception as e:
        print(f"  [SAC 오류] {e}")
        return []


# ─────────────────────────────────────────────────────
# 4. 네이버 데이터랩 — 장소별 검색 트렌드 (인기도)
# ─────────────────────────────────────────────────────
def fetch_naver_trend(place_names: list[str]) -> dict[str, int]:
    """네이버 데이터랩 API → 장소별 주간 검색량 지수 반환"""
    if not NAVER_ID or NAVER_ID.startswith("YOUR_"):
        print("  [네이버트렌드] 키 없음 → 건너뜀")
        return {}

    url = "https://openapi.naver.com/v1/datalab/search"
    headers = {
        "X-Naver-Client-Id":     NAVER_ID,
        "X-Naver-Client-Secret": NAVER_SEC,
        "Content-Type":          "application/json",
    }
    # API는 한번에 최대 5개 키워드 그룹
    results = {}
    chunks = [place_names[i:i+5] for i in range(0, len(place_names), 5)]
    
    start_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    end_date   = today.strftime("%Y-%m-%d")

    for chunk in chunks:
        body = {
            "startDate": start_date,
            "endDate":   end_date,
            "timeUnit":  "week",
            "keywordGroups": [
                {"groupName": name, "keywords": [name]}
                for name in chunk
            ],
        }
        try:
            r = requests.post(url, headers=headers, json=body, timeout=8)
            r.raise_for_status()
            data = r.json()
            for result in data.get("results", []):
                name = result["title"]
                ratios = result.get("data", [])
                if ratios:
                    # 최근 값 (0~100 지수)
                    score = int(ratios[-1].get("ratio", 0))
                    results[name] = score
        except Exception as e:
            print(f"  [네이버트렌드 오류] {e}")
        time.sleep(0.5)

    print(f"  [네이버트렌드] {len(results)}개 장소 인기도 수집 완료")
    return results


# ─────────────────────────────────────────────────────
# 5. 수집 결과 → CSV 저장 + DB 이벤트 연결
# ─────────────────────────────────────────────────────
CULTURE_EVENTS_CSV = os.path.join(BASE_DIR, "..", "data", "culture_events_raw.csv")
CULTURE_HEADERS = ["title","place","start","end","genre","realm","url","thumbnail","source","period_raw"]


def save_culture_events(events: list[dict]):
    """수집된 공연/전시 이벤트를 CSV로 저장 (DB 불필요, 직접 CSV 저장)"""
    if not events:
        print("  저장할 이벤트 데이터 없음")
        return
    os.makedirs(os.path.dirname(CULTURE_EVENTS_CSV), exist_ok=True)
    with open(CULTURE_EVENTS_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CULTURE_HEADERS, extrasaction="ignore")
        w.writeheader()
        for ev in events:
            w.writerow({k: ev.get(k, "") for k in CULTURE_HEADERS})
    print(f"  공연/전시 이벤트 {len(events)}건 저장 → {CULTURE_EVENTS_CSV}")


if __name__ == "__main__":
    print("=" * 55)
    print("  공연/전시 이벤트 수집기 (서울·경기)")
    print("=" * 55)

    all_events = []

    print("\n[1] 공공데이터포털 공연전시 API (서울)...")
    all_events += fetch_culture_events_public_api(rows=200, area="서울")

    print("\n[2] 공공데이터포털 공연전시 API (경기)...")
    all_events += fetch_culture_events_public_api(rows=200, area="경기")

    print("\n[3] 서울시 문화행사 API...")
    all_events += fetch_seoul_culture_events(rows=200)

    print("\n[4] 국립현대미술관 크롤링...")
    all_events += crawl_mmca()

    print("\n[5] 서울시립미술관 크롤링...")
    all_events += crawl_sema()

    print("\n[6] 예술의전당 크롤링...")
    all_events += crawl_sac()

    # 중복 제거 (title 기준)
    seen = set()
    unique_events = []
    for ev in all_events:
        key = ev.get("title", "").strip()
        if key and key not in seen:
            seen.add(key)
            unique_events.append(ev)

    print(f"\n총 {len(unique_events)}건 (중복 제거 후) 수집 완료")

    print("\n[7] CSV 저장...")
    save_culture_events(unique_events)

    print("\n[완료] culture_events_raw.csv 저장 완료!")
