import requests
import json
import os
from datetime import datetime
import xml.etree.ElementTree as ET

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = json.load(f)

KEYS = config["api_keys"]

def is_valid_key(key_name):
    key = KEYS.get(key_name)
    return key and not key.startswith("YOUR_")

def fetch_tour_festivals():
    """
    한국관광공사 TourAPI 4.0 - 축제 및 행사 정보 수집
    """
    if not is_valid_key("tour_api_key"):
        print("[TourAPI] 유효한 API 키가 없습니다. 가상/데모 모드로 동작합니다.")
        return []
    
    key = KEYS["tour_api_key"]
    today_str = datetime.now().strftime("%Y%m%d")
    url = "http://apis.data.go.kr/B551011/KorService1/searchFestival1"
    params = {
        "serviceKey": key,
        "numOfRows": 20,
        "pageNo": 1,
        "MobileOS": "ETC",
        "MobileApp": "AppTest",
        "_type": "json",
        "listYN": "Y",
        "arrange": "A",
        "eventStartDate": today_str
    }
    
    try:
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            data = res.json()
            items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
            if isinstance(items, dict): # 단일 항목인 경우 처리
                items = [items]
            
            cleaned_festivals = []
            for item in items:
                cleaned_festivals.append({
                    "name": item.get("title"),
                    "address": item.get("addr1"),
                    "latitude": item.get("mapy"),
                    "longitude": item.get("mapx"),
                    "start_date": datetime.strptime(item.get("eventstartdate"), "%Y%m%d").strftime("%Y-%m-%d") if item.get("eventstartdate") else "",
                    "end_date": datetime.strptime(item.get("eventenddate"), "%Y%m%d").strftime("%Y-%m-%d") if item.get("eventenddate") else "",
                    "tel": item.get("tel"),
                    "source_url": item.get("firstimage") or "" # 대표 이미지 경로를 우선 소스로 저장
                })
            return cleaned_festivals
    except Exception as e:
        print(f"[TourAPI] 에러 발생: {e}")
    return []

def fetch_seoul_congestion(area_name):
    """
    서울 열린데이터 광장 - 실시간 인구 혼잡도 API
    """
    if not is_valid_key("seoul_api_key"):
        # API 키가 없으면 임의의 혼잡도 리턴
        import random
        return random.choice(["LOW", "MODERATE", "CONGESTED", "VERY_CONGESTED"])
        
    key = KEYS["seoul_api_key"]
    # 서울시 실시간 도시데이터 API는 XML 형식을 주로 사용하므로 XML 파싱 진행
    url = f"http://openapi.seoul.go.kr:8088/{key}/xml/citydata/1/5/{area_name}"
    
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            # AREA_CONGEST_LVL 요소 찾기
            lvl_elem = root.find(".//AREA_CONGEST_LVL")
            if lvl_elem is not None:
                lvl = lvl_elem.text
                # 한국어 혼잡도를 영어 코드로 매핑
                mapping = {
                    "여유": "LOW",
                    "보통": "MODERATE",
                    "약간 혼잡": "CONGESTED",
                    "혼잡": "VERY_CONGESTED"
                }
                return mapping.get(lvl, "LOW")
    except Exception as e:
        print(f"[SeoulAPI] '{area_name}' 데이터 수집 중 에러 발생: {e}")
    return "LOW"

def fetch_kakao_place_details(place_name):
    """
    Kakao Local API를 통한 상세 위경도 및 도로명 주소 확보
    """
    if not is_valid_key("kakao_api_key"):
        return None
        
    key = KEYS["kakao_api_key"]
    headers = {"Authorization": f"KakaoAK {key}"}
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    params = {"query": place_name, "size": 1}
    
    try:
        res = requests.get(url, headers=headers, params=params, timeout=5)
        if res.status_code == 200:
            documents = res.json().get("documents", [])
            if documents:
                doc = documents[0]
                return {
                    "name": doc.get("place_name"),
                    "address": doc.get("road_address_name") or doc.get("address_name"),
                    "latitude": doc.get("y"),
                    "longitude": doc.get("x"),
                    "category": doc.get("category_group_name") or doc.get("category_name")
                }
    except Exception as e:
        print(f"[KakaoAPI] '{place_name}' 상세 검색 에러: {e}")
    return None

def fetch_naver_place_details(place_name):
    """
    Naver Search Local API를 통한 상세 정보 확보
    """
    if not is_valid_key("naver_client_id") or not is_valid_key("naver_client_secret"):
        return None
        
    client_id = KEYS["naver_client_id"]
    client_secret = KEYS["naver_client_secret"]
    
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    url = "https://openapi.naver.com/v1/search/local.json"
    params = {"query": place_name, "display": 1}
    
    try:
        res = requests.get(url, headers=headers, params=params, timeout=5)
        if res.status_code == 200:
            items = res.json().get("items", [])
            if items:
                item = items[0]
                # 카카오 위경도 형태와 다른 카텍좌표계(KATECH)로 오는 경우가 있어 변환 필요할 수 있으나 기본값 전달
                return {
                    "name": item.get("title").replace("<b>", "").replace("</b>", ""),
                    "address": item.get("roadAddress") or item.get("address"),
                    "category": item.get("category")
                }
    except Exception as e:
        print(f"[NaverAPI] '{place_name}' 상세 검색 에러: {e}")
    return None

if __name__ == "__main__":
    # 기본 테스트 출력
    print("API Collector Module loaded.")
    print("Tour API Key Valid:", is_valid_key("tour_api_key"))
    print("Seoul API Key Valid:", is_valid_key("seoul_api_key"))
