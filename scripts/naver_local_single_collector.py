"""
싱글매니아 장소 수집기 v2.0 (NAVER API HUB - 지역 검색, 2026-08 이관 반영)
=============================================================================
목적:
  generate_single_data.py가 티켓/행사 데이터만 써서 채우지 못했던
  '독립서점 / 조용한 힐링 / 역사·문화 / 자연·공원' 4개 카테고리를
  실제 장소 데이터로 채운다.

⚠️ 2026-08 API 이관 안내:
  기존 developers.naver.com의 '검색 > 지역' 오픈API가 NAVER Cloud Platform의
  'NAVER API HUB'로 이관되어, 엔드포인트와 인증 헤더가 완전히 바뀌었다.
  - 문서: https://api.ncloud-docs.com/docs/naver-api-hub-search-local
  - 엔드포인트: https://naverapihub.apigw.ntruss.com/search/v1/local  (GET)
  - 인증 헤더: X-NCP-APIGW-API-KEY-ID / X-NCP-APIGW-API-KEY
    (예전 X-Naver-Client-Id/Secret 헤더가 아님 — 주의)
  - 응답 필드는 기존과 동일: title/link/category/description/telephone/
    address/roadAddress/mapx/mapy
  - 무료 한도: 하루 25,000건

[API 키 발급 — NCP 콘솔 쪽]
  https://console.ncloud.com → AI·NAVER API → Application 등록
  → 사용 API에서 'NAVER API HUB > 검색' 선택 → Client ID/Secret 발급
  → scripts/config.json 의 naver_hub_client_id/naver_hub_client_secret에 입력
  (참고: developers.naver.com에서 옛날 방식으로 발급받은 naver_client_id/secret와는
   완전히 다른 키 체계이므로 절대 섞어 쓰면 안 된다.)

출력: data/naver_single_places.csv (total_single_data.csv 스키마와 호환되는 컬럼으로 정규화)
"""
import sys, io, os, json, csv, time
from datetime import datetime
from urllib.parse import quote
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
OUTPUT_CSV = os.path.join(DATA_DIR, "naver_single_places.csv")

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

# NAVER API HUB(NCP) 전용 키 — developers.naver.com의 naver_client_id/secret와는 별개.
# 혹시 config.json에 아직 naver_hub_client_id가 없으면(과거 config 그대로인 경우)
# naver_client_id로도 한 번 시도해보되, 정상적으로는 hub 전용 키를 써야 한다.
NAVER_ID = CONFIG.get("api_keys", {}).get("naver_hub_client_id") or CONFIG.get("api_keys", {}).get("naver_client_id", "")
NAVER_SEC = CONFIG.get("api_keys", {}).get("naver_hub_client_secret") or CONFIG.get("api_keys", {}).get("naver_client_secret", "")

API_URL = "https://naverapihub.apigw.ntruss.com/search/v1/local"
HTTP_HEADERS = {
    "X-NCP-APIGW-API-KEY-ID": NAVER_ID,
    "X-NCP-APIGW-API-KEY": NAVER_SEC,
}

# 수도권 주요 지역 (필요 시 확장)
SEOUL_DISTRICTS = [
    "서울 강남구", "서울 마포구", "서울 종로구", "서울 용산구", "서울 성동구",
    "서울 서대문구", "서울 은평구", "서울 송파구", "서울 영등포구", "서울 중구",
    "서울 강북구", "서울 노원구", "서울 관악구", "서울 동작구", "서울 광진구",
]
GYEONGGI_CITIES = [
    "경기 수원시", "경기 성남시", "경기 고양시", "경기 용인시", "경기 파주시",
]
ALL_REGIONS = SEOUL_DISTRICTS + GYEONGGI_CITIES

# 싱글 4대 보강 테마: (검색쿼리 키워드, category, theme_tags, ai_tags 기본 single 점수)
THEMES = [
    {"query_kw": "독립서점",       "cat": "독립서점",     "theme_tag": "bookstore:1.0;quiet:1.0;indoor:1.0",  "single_score": 0.95},
    {"query_kw": "북카페",         "cat": "독립서점",     "theme_tag": "bookstore:0.8;quiet:0.9;indoor:1.0",  "single_score": 0.85},
    {"query_kw": "스터디카페",     "cat": "조용한 힐링",  "theme_tag": "healing:0.7;quiet:1.0;solo:1.0",      "single_score": 0.9},
    {"query_kw": "요가원",         "cat": "조용한 힐링",  "theme_tag": "healing:1.0;quiet:0.8;solo:0.9",      "single_score": 0.8},
    {"query_kw": "명상센터",       "cat": "조용한 힐링",  "theme_tag": "healing:1.0;quiet:1.0;solo:1.0",      "single_score": 0.85},
    {"query_kw": "고궁",           "cat": "역사·문화",    "theme_tag": "culture:1.0;history:1.0;outdoor:0.6", "single_score": 0.75},
    {"query_kw": "사찰",           "cat": "역사·문화",    "theme_tag": "culture:1.0;history:0.9;outdoor:0.7", "single_score": 0.7},
    {"query_kw": "둘레길",         "cat": "자연·공원",    "theme_tag": "nature:1.0;outdoor:1.0;walk:1.0",     "single_score": 0.8},
    {"query_kw": "수목원",         "cat": "자연·공원",    "theme_tag": "nature:1.0;outdoor:1.0;walk:0.8",     "single_score": 0.75},
]

CSV_FIELDS = [
    "source_site", "category", "place_or_event_name", "period",
    "target_age", "region", "fee_info", "description", "booking_url",
    "ai_tags", "crawled_at", "theme_tags", "congestion_score", "popularity_score",
]


def strip_html_tags(text):
    return text.replace("<b>", "").replace("</b>", "")


_FETCH_TIMEOUT = (10, 20)   # (connect, read) 초 — 기존 6초는 독립서점 API(kcisa)에서 실측된
                             # read timeout과 같은 증상을 일으키기 쉬워 늘렸다.
_MAX_RETRIES = 2
_RETRY_BACKOFF_BASE = 2     # 2s, 4s


def fetch_local_places(query, display=5):
    """NAVER API HUB 지역검색 호출. 실패 시 빈 리스트 반환.
    일시적인 타임아웃/연결 오류는 재시도하고, 그래도 실패하면 이 쿼리만 건너뛴다
    (기존에는 예외가 잡히지 않아 63개 시군구 × 9개 테마 수집 전체가 첫 실패에서 중단됐다)."""
    if not NAVER_ID or not NAVER_SEC or NAVER_ID.startswith("YOUR_"):
        raise RuntimeError(
            "config.json에 naver_hub_client_id / naver_hub_client_secret이 설정되어 있지 않습니다. "
            "https://console.ncloud.com (AI·NAVER API > Application)에서 발급 후 입력하세요."
        )
    params = {"query": query, "display": display, "start": 1, "sort": "random", "format": "json"}

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            r = requests.get(API_URL, headers=HTTP_HEADERS, params=params, timeout=_FETCH_TIMEOUT)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            if attempt < _MAX_RETRIES:
                wait = _RETRY_BACKOFF_BASE ** attempt
                print(f"  [경고] '{query}' 요청 실패({type(e).__name__}), {wait}초 후 재시도...")
                time.sleep(wait)
                continue
            print(f"  [경고] '{query}' 요청 실패({type(e).__name__}), 이 쿼리는 건너뜁니다: {e}")
            return []

        if r.status_code != 200:
            print(f"  [경고] '{query}' 요청 실패 (status={r.status_code}): {r.text[:200]}")
            return []
        return r.json().get("items", [])
    return []


def collect():
    print("=" * 65)
    print("  싱글매니아 장소 수집기 v2.0 (NAVER API HUB - 지역검색)")
    print("=" * 65)

    results = []
    seen_names = set()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for reg in ALL_REGIONS:
        for t_info in THEMES:
            query = f"{reg} {t_info['query_kw']}"
            try:
                items = fetch_local_places(query, display=5)
            except RuntimeError as e:
                print(f"[중단] {e}")
                return []

            for item in items:
                name = strip_html_tags(item.get("title", "")).strip()
                if not name or name in seen_names:
                    continue
                seen_names.add(name)

                address = item.get("roadAddress") or item.get("address") or ""
                category_raw = item.get("category", "")
                telephone = item.get("telephone", "")
                link = item.get("link", "")
                mapx, mapy = item.get("mapx", ""), item.get("mapy", "")

                results.append({
                    "source_site":         f"네이버 지역검색 API | {reg}",
                    "category":            t_info["cat"],
                    "place_or_event_name": name,
                    "period":              "상시",
                    "target_age":          "성인 (개인 방문 적합)",
                    "region":              f"{address} | 좌표:{mapx},{mapy}" if mapx else address,
                    "fee_info":            "장소 문의 (전화/홈페이지 참조)",
                    "description":         f"{reg}에 위치한 {t_info['query_kw']} 관련 장소 [{name}] ({category_raw}). "
                                            f"전화: {telephone or '정보없음'}",
                    "booking_url":         link or f"https://map.naver.com/v5/search/{quote(name)}",
                    "ai_tags":             f"single:{t_info['single_score']};couple:0.4;family:0.3;{category_raw};{t_info['query_kw']}",
                    "crawled_at":          now_str,
                    "theme_tags":          t_info["theme_tag"],
                    "congestion_score":    2,
                    "popularity_score":    70,
                })

            time.sleep(0.1)  # 초당 호출 제한 대응

        print(f"  [진행] {reg} 완료 (누적 {len(results)}건)")

    return results


def main():
    results = collect()
    if not results:
        print("⚠️ 수집된 결과가 없습니다. API 키/네트워크 상태를 확인하세요.")
        return

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n✅ 저장 완료: {OUTPUT_CSV} ({len(results)}건)")
    print("   -> generate_single_data.py 에 이 파일을 병합 소스로 추가하면")
    print("      독립서점/조용한 힐링/역사·문화/자연·공원 카테고리가 채워집니다.")


if __name__ == "__main__":
    main()
