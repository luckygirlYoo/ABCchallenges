import requests
import re
from bs4 import BeautifulSoup

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

def search_naver_place_info(query):
    url = f"https://search.naver.com/search.naver?where=nexearch&query={requests.utils.quote(query)}"
    r = requests.get(url, headers=headers, timeout=5)
    html = r.text

    # 위도(latitude), 경도(longitude) 추출
    lats = re.findall(r'"y":"([0-9\.]+)"', html) or re.findall(r'"lat":"([0-9\.]+)"', html)
    lngs = re.findall(r'"x":"([0-9\.]+)"', html) or re.findall(r'"lng":"([0-9\.]+)"', html)

    lat = lats[0] if lats else None
    lng = lngs[0] if lngs else None

    # 주차, 수유실, 기저귀갈이대, 유모차 태그 검증
    has_parking      = any(k in html for k in ["주차", "주차장", "발렛", "무료주차"])
    has_nursing      = any(k in html for k in ["수유실", "수유"])
    has_diaper_table = any(k in html for k in ["기저귀갈이대", "기저귀 교환", "기저귀"])
    has_stroller     = any(k in html for k in ["유모차대여", "유모차 대여", "유모차"])

    return {
        "lat": lat,
        "lng": lng,
        "parking": has_parking,
        "nursing_room": has_nursing,
        "diaper_table": has_diaper_table,
        "stroller": has_stroller
    }

if __name__ == "__main__":
    print("서울어린이대공원:", search_naver_place_info("서울 광진구 서울어린이대공원"))
    print("캘리클럽 역삼점:", search_naver_place_info("서울 강남구 캘리클럽 역삼점"))
