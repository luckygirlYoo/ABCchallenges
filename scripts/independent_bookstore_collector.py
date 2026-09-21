"""
독립서점 데이터 수집기 v1.1 (문화공공데이터광장 - 한국문화정보원)
=============================================================================
데이터셋: 한국문화정보원_전국 독립서점 및 운영정보
엔드포인트: https://api.kcisa.kr/openapi/API_CIA_089/request
인증:     serviceKey 파라미터 (config.json 의 kcisa_bookstore_api_key)

실제 응답 필드명 (2026-08-23 실제 호출로 확인됨):
  TITLE            서점명
  ADDRESS          주소 (우편번호 포함, 예: "(41946) 대구광역시 중구 ...")
  CONTACT_POINT    전화번호 (하이픈 없음, 예: "0534261765")
  COORDINATES      "위도 , 경도" 형태의 한 문자열 (예: "35.86561079 , 128.6083915")
  DESCRIPTION      운영시간+휴무일이 한 문자열에 뭉쳐 있음 (예: "평일개점마감시간 : 11:00~21:00...휴무일 : 월요일 휴무:")
  SUB_DESCRIPTION  특징 설명 텍스트 (예: "큐레이션 서점, 핸드드립 커피도 판매 , ") — 주차/카페/대여 등은
                   별도 Y/N 플래그가 없고 이 텍스트 안에 자연어로만 존재함
  SUBJECT_KEYWORD  분류 키워드 (예: "독립서점 , 일반")
  ISSUED_DATE      데이터 등록일
  CNTC_RESRCE_NO   내부 리소스 번호 (사용 안 함)
  ※ URL/홈페이지 필드 자체가 없음 -> booking_url은 네이버 지도 검색 링크로 대체 생성

출력: data/independent_bookstores.csv (total_single_data 스키마와 호환되는 컬럼으로 정규화)
"""
import sys, io, os, json, csv, time, argparse
from datetime import datetime
from urllib.parse import quote
import xml.etree.ElementTree as ET
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
OUTPUT_CSV = os.path.join(DATA_DIR, "independent_bookstores.csv")

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

SERVICE_KEY = CONFIG.get("api_keys", {}).get("kcisa_bookstore_api_key", "")
API_URL = "https://api.kcisa.kr/openapi/API_CIA_089/request"

CSV_FIELDS = [
    "source_site", "category", "place_or_event_name", "period",
    "target_age", "region", "fee_info", "description", "booking_url",
    "ai_tags", "crawled_at", "theme_tags", "congestion_score", "popularity_score",
]



# api.kcisa.kr(문화공공데이터광장)는 응답이 느린 편이라 read timeout=10 이 실측에서
# 자주 걸렸다(2026-08-23: "Read timed out. (read timeout=10)" 로 배치 13이 0건 실패).
# 연결 자체는 금방 되니 connect timeout은 짧게 두고, 응답 대기(read)만 넉넉히 늘린다.
# 그래도 실패하면 지수 백오프로 재시도해서 일시적인 지연/네트워크 끊김에 페이지 전체가
# 죽지 않도록 한다.
FETCH_TIMEOUT = (10, 45)     # (connect, read) 초
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2       # 2s, 4s, 8s


def fetch_page(page_no=1, num_of_rows=100, keyword=None):
    """kcisa openapi 호출. XML 응답을 그대로 반환.
    요청 형식은 사용자가 실제 발급받은 요청 예시 URL과 동일하게 맞춤:
    https://api.kcisa.kr/openapi/API_CIA_089/request?serviceKey=...&numOfRows=10&pageNo=1
    (keyword는 값이 있을 때만 포함 — 빈 문자열을 강제로 보내면 일부 공공API가 400을 반환하는 경우가 있음)

    일시적인 타임아웃/연결 오류는 최대 MAX_RETRIES회까지 지수 백오프로 재시도한다.
    """
    if not SERVICE_KEY or SERVICE_KEY == "YOUR_KCISA_API_KEY":
        raise RuntimeError("config.json의 kcisa_bookstore_api_key가 비어 있습니다.")

    params = {
        "serviceKey": SERVICE_KEY,
        "numOfRows": num_of_rows,
        "pageNo": page_no,
    }
    if keyword:
        params["keyword"] = keyword

    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.get(API_URL, params=params, timeout=FETCH_TIMEOUT)
            r.raise_for_status()
            return r.text
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last_err = e
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF_BASE ** attempt
                print(f"  [경고] {page_no}페이지 요청 실패({type(e).__name__}), "
                      f"{wait}초 후 재시도 ({attempt}/{MAX_RETRIES})...")
                time.sleep(wait)
            else:
                print(f"  [경고] {page_no}페이지 {MAX_RETRIES}회 재시도 모두 실패: {e}")
    raise last_err


def parse_items(xml_text):
    """<response><body><items><item>...</item></items></body></response> 형태를 가정.
    item 하위 태그를 전부 동적으로 dict화 -> 실제 필드명이 달라도 안전하게 수집."""
    items = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        print("[경고] XML 파싱 실패. 응답 원문 일부:", xml_text[:300])
        return items

    for item_el in root.iter("item"):
        row = {}
        for child in item_el:
            tag = child.tag
            row[tag] = (child.text or "").strip()
        if row:
            items.append(row)
    return items


def normalize(raw, now_str):
    """실제 API 응답 필드명(2026-08-23 확인됨)을 total_single_data 스키마로 변환.
    TITLE/ADDRESS/CONTACT_POINT/COORDINATES/DESCRIPTION/SUB_DESCRIPTION 사용.
    주차/카페/대여/독립출판 여부는 별도 플래그가 없어 SUB_DESCRIPTION 텍스트에서 키워드로 추정."""

    def pick(*keys, default=""):
        for k in keys:
            if k in raw and raw[k]:
                return raw[k]
        return default

    name = pick("TITLE", "title", "서점명", default="이름없음")
    if name == "이름없음":
        print(f"  [경고] 이름 필드를 못 찾음. raw keys: {list(raw.keys())}")

    address = pick("ADDRESS", "ADDR", "address", default="")
    tel = pick("CONTACT_POINT", "TEL", "tel", default="")
    oper_info = pick("DESCRIPTION", default="")       # 운영시간+휴무일이 한 문자열에 뭉쳐 있음
    feature_text = pick("SUB_DESCRIPTION", default="") # 특징 설명(카페/주차 등이 자연어로만 존재)
    keyword = pick("SUBJECT_KEYWORD", default="")

    # COORDINATES: "35.86561079 , 128.6083915" (위도 , 경도) 한 문자열을 분리
    lat, lon = "", ""
    coords = pick("COORDINATES", default="")
    if coords:
        parts = [p.strip() for p in coords.split(",")]
        if len(parts) == 2:
            lat, lon = parts[0], parts[1]

    # Y/N 플래그가 없어서 특징 설명 텍스트에서 키워드로 유무를 추정
    has_cafe = any(k in feature_text for k in ("카페", "커피"))
    has_indie_pub = ("독립출판" in feature_text) or ("독립 출판" in feature_text)
    has_parking = "주차" in feature_text
    has_rental = "대여" in feature_text

    tag_bits = ["single:0.95", "couple:0.4", "family:0.3", "독립서점"]
    if has_cafe:
        tag_bits.append("cafe:1.0")
    if has_indie_pub:
        tag_bits.append("indie_pub:1.0")

    region = f"{address} | 위도:{lat}, 경도:{lon}" if lat and lon else address

    # URL 필드가 아예 없는 API라 네이버 지도 검색 링크로 대체
    booking_url = f"https://map.naver.com/v5/search/{quote(name)}" if name != "이름없음" else (f"tel:{tel}" if tel else "")

    feature_clean = feature_text.strip(" ,")
    description_parts = [f"[{name}]"]
    if feature_clean:
        description_parts.append(feature_clean)
    if oper_info:
        description_parts.append(f"운영정보: {oper_info}")
    description_parts.append(f"전화: {tel or '정보없음'}")
    description = " / ".join(description_parts)

    return {
        "source_site":         "문화공공데이터광장 | 전국 독립서점 및 운영정보",
        "category":            "독립서점",
        "place_or_event_name": name,
        "period":              "상시",
        "target_age":          "성인 (개인 방문 적합)",
        "region":              region,
        "fee_info":            "무료입장 (도서 구매 별도)",
        "description":         description,
        "booking_url":         booking_url,
        "ai_tags":             ";".join(tag_bits),
        "crawled_at":          now_str,
        "theme_tags":          "bookstore:1.0;quiet:1.0;indoor:1.0",
        "congestion_score":    2,
        "popularity_score":    70,
    }


def collect(max_pages=20, rows_per_page=100):
    all_rows = []
    raw_samples = []  # 디버그용: 실제 API 원본 필드 구조를 몇 건만 저장
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for page in range(1, max_pages + 1):
        print(f"[진행] {page}페이지 요청 중...")
        try:
            xml_text = fetch_page(page_no=page, num_of_rows=rows_per_page)
        except RuntimeError as e:
            print(f"[중단] {e}")
            return []
        except requests.RequestException as e:
            print(f"[오류] 요청 실패: {e}")
            break

        items = parse_items(xml_text)
        if not items:
            print(f"[완료] {page}페이지에서 더 이상 데이터 없음. 수집 종료.")
            break

        if len(raw_samples) < 5:
            raw_samples.extend(items[:5 - len(raw_samples)])

        for raw in items:
            all_rows.append(normalize(raw, now_str))

        print(f"  -> 누적 {len(all_rows)}건")
        time.sleep(0.2)

    # 실제 API 원본 필드 구조를 항상 디버그 파일로 저장 (필드명 확인용)
    if raw_samples:
        debug_path = os.path.join(DATA_DIR, "independent_bookstores_debug.json")
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(debug_path, "w", encoding="utf-8") as f:
                json.dump(raw_samples, f, ensure_ascii=False, indent=2)
            print(f"[디버그] 원본 API 응답 필드 샘플 저장: {debug_path}")
        except Exception as e:
            print(f"[경고] 디버그 파일 저장 실패: {e}")

    return all_rows


def run_test_call():
    """--test: 실제 API를 1건만 호출해서 원본 XML 구조를 눈으로 확인하기 위한 모드."""
    xml_text = fetch_page(page_no=1, num_of_rows=1)
    print("=== 원본 응답 (앞부분) ===")
    print(xml_text[:2000])
    items = parse_items(xml_text)
    if items:
        print("\n=== 파싱된 첫 item의 필드명/값 ===")
        for k, v in items[0].items():
            print(f"  {k}: {v}")
        print("\n위 필드명을 확인한 뒤 normalize() 함수의 pick(...) 후보 키를 실제 필드명으로 맞춰주세요.")
    else:
        print("\n[경고] item을 찾지 못했습니다. XML 구조 자체가 다를 수 있습니다 (예: response/body 래핑 방식 차이).")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="1건만 호출해서 응답 필드명 확인")
    parser.add_argument("--max-pages", type=int, default=20)
    args = parser.parse_args()

    if args.test:
        run_test_call()
        return

    rows = collect(max_pages=args.max_pages)
    if not rows:
        print("⚠️ 수집된 결과가 없습니다.")
        return

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✅ 저장 완료: {OUTPUT_CSV} ({len(rows)}건)")


if __name__ == "__main__":
    main()
