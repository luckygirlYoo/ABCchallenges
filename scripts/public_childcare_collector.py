"""
공공 키즈카페 및 육아종합지원센터 수집기 v3.0 (카카오 로컬 기반)
=============================================================================
왜 다시 썼는가
-----------------------------------------------------------------------------
v2.0 은 네이버 검색 HTML 에서 soup.find_all('a') 로 모든 앵커를 훑고
get_text() 로 자손 텍스트를 이어 붙여 시설명을 만들었다. 그 결과 실제
저장된 데이터 564건이 좌표 0% 였고 이름이 이런 상태였다:

    2026.07.09.마포구육아종합지원센터직원 채용 공고     <- 채용 공고
    구로구육아종합지원센터guroccic.guro.go.kr          <- URL
    allthatcompany.com>화성시육아종합지원센터           <- 검색 경로
    시립마포거점형키움센터서울형키즈카페시립노고산점아동복지시설  <- 카드 뭉침
    서울형키즈카페도봉구창1동 숲속유람선 뚜뚜, 0세 아기랑    <- 블로그 제목

place_search_collector.py 와 똑같은 원인이고, 똑같은 방식으로 해결한다.
카카오 로컬은 이 시설들을 전용 분류로 갖고 있다:
    '서울형키즈카페 종로구 혜화동점'  분류 말단 '서울형키즈카페'
    '종로구 육아종합지원센터'        분류 말단 '육아종합지원센터'
    '장난감도서관 송부점'           분류 말단 '장난감대여'

v3.0 이 달라진 점
-----------------------------------------------------------------------------
  1. 데이터 소스: 네이버 검색 HTML -> 카카오 로컬 키워드 검색 API
  2. 시설명: 정규식 정제 없이 place_name 그대로
  3. 좌표: 수집 단계에서 확보 (v2.0 은 전량 공란)
  4. 중복 제거: 이름 문자열이 아니라 카카오 장소 고유 id 기준
  5. 지역 검증: 주소 접두어로 확인 (카카오는 질의 지역 밖 결과도 반환)
  6. 인천 행정구역 개편 반영 (중구/동구 -> 제물포구·영종구, 서구 -> 서해구·검단구)
  7. 없는 사실을 주장하지 않는다: v2.0 은 전 건에 fee_info 를
     '아동 1,000~3,000원 / 보호자 무료 (공공 가성비)' 로 하드코딩했다.
     요금 정보를 주는 소스가 없으므로 비워 둔다.

출력: data/public_childcare_data.csv (스키마는 v2.0 과 동일 — 다운스트림 호환)
"""
import sys, io, os, json, csv, time, re, collections
from datetime import datetime
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(BASE_DIR, "..", "data")
OUTPUT_CSV = os.path.join(DATA_DIR, "public_childcare_data.csv")

_CFG_PATH = os.path.join(BASE_DIR, "config.json")
try:
    with open(_CFG_PATH, "r", encoding="utf-8") as _f:
        KAKAO_KEY = json.load(_f).get("api_keys", {}).get("kakao_api_key", "")
except Exception:
    KAKAO_KEY = ""

KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
KAKAO_PAGE_SIZE   = 15
KAKAO_MAX_PAGE    = 3

# 스키마는 v2.0 그대로 유지한다. generate_total_family_data.from_childcare 가
# 이 컬럼들을 읽는다.
HEADERS = [
    "source_site", "category", "place_or_event_name", "target_age",
    "region", "fee_info", "description", "booking_url",
    "theme_tags", "congestion_score", "popularity_score", "ai_tags",
    "start_date", "end_date", "crawled_at"
]

SEOUL_DISTRICTS = [
    "서울 강남구", "서울 강동구", "서울 강북구", "서울 강서구", "서울 관악구",
    "서울 광진구", "서울 구로구", "서울 금천구", "서울 노원구", "서울 도봉구",
    "서울 동대문구", "서울 동작구", "서울 마포구", "서울 서대문구", "서울 서초구",
    "서울 성동구", "서울 성북구", "서울 송파구", "서울 양천구", "서울 영등포구",
    "서울 용산구", "서울 은평구", "서울 종로구", "서울 중구", "서울 중랑구"
]

GYEONGGI_CITIES = [
    "경기 수원시", "경기 성남시", "경기 고양시", "경기 용인시", "경기 부천시",
    "경기 안산시", "경기 안양시", "경기 남양주시", "경기 화성시", "경기 평택시",
    "경기 의정부시", "경기 시흥시", "경기 파주시", "경기 김포시", "경기 광명시",
    "경기 광주시", "경기 군포시", "경기 이천시", "경기 오산시", "경기 하남시",
    "경기 양주시", "경기 구리시", "경기 안성시", "경기 포천시", "경기 의왕시",
    "경기 여주시", "경기 양평군", "경기 동두천시", "경기 가평군", "경기 과천시"
]

# 인천은 행정구역이 개편돼 카카오 주소가 새 구 이름을 쓴다.
# 옛 이름(중구/동구/서구)으로 질의하면 지역 검증이 전부 실패한다.
INCHEON_DISTRICTS = [
    "인천 제물포구", "인천 영종구", "인천 서해구", "인천 검단구",
    "인천 미추홀구", "인천 연수구", "인천 남동구", "인천 부평구", "인천 계양구"
]

ALL_REGIONS = SEOUL_DISTRICTS + GYEONGGI_CITIES + INCHEON_DISTRICTS

# 카카오에 던지는 질의 키워드. 지역별로 존재하지 않는 유형은 0건이 나오며,
# 그것 자체가 정상이다 (예: 아이러브맘카페는 일부 시군에만 있다).
QUERIES = [
    "서울형키즈카페", "맘스하트카페", "아이러브맘카페",
    "육아종합지원센터", "공동육아나눔터", "장난감도서관",
]

# 분류 말단이 이것이면 공공 육아시설로 바로 채택한다.
STRONG_LEAVES = {"서울형키즈카페", "육아종합지원센터", "장난감대여"}

# 분류 말단이 이것이면 넓은 범주라 이름 확인을 함께 요구한다.
# '아동복지시설' 에는 보육원·그룹홈 등 나들이 대상이 아닌 시설도 들어 있다.
WEAK_LEAVES = {"아동복지시설", "사회복지시설", "놀이시설", "키즈카페",
               "실내놀이터", "놀이방", "도서관", "공공도서관", "어린이도서관"}

# WEAK_LEAVES 를 채택하기 위해 이름에 있어야 하는 단어.
PUBLIC_NAME_WORDS = [
    "서울형키즈카페", "맘스하트", "아이러브맘", "육아종합지원센터",
    "공동육아", "나눔터", "장난감도서관", "장난감", "아이사랑",
    "어울림센터", "키움센터", "육아방", "돌봄센터", "보육정보",
]

# 이름에 이 단어가 있으면 제외한다. 나들이 대상이 아니거나 시설이 아닌 것.
DENY_NAME_WORDS = [
    "채용", "공고", "모집", "입찰", "위탁", "협약",
    "주차장", "장례", "납골",
]

HTTP_TIMEOUT = 6


def search_kakao(query, page=1):
    """카카오 로컬 키워드 검색 1페이지. (documents, is_end).

    실패를 삼키지 않는다. v2.0 의 `except Exception: pass` 는 차단·타임아웃을
    로그 없이 없애서 부분 수집을 정상으로 오인하게 만들었다.
    """
    r = requests.get(
        KAKAO_KEYWORD_URL,
        headers={"Authorization": f"KakaoAK {KAKAO_KEY}"},
        params={"query": query, "size": KAKAO_PAGE_SIZE, "page": page},
        timeout=HTTP_TIMEOUT,
    )
    if r.status_code in (401, 403):
        raise PermissionError(f"카카오 로컬 사용 불가 (HTTP {r.status_code}): {r.text[:160]}")
    r.raise_for_status()
    d = r.json()
    return d.get("documents", []), bool(d.get("meta", {}).get("is_end", True))


def category_leaf(category_name):
    """'가정,생활 > 유아 > 놀이시설 > 서울형키즈카페' -> '서울형키즈카페'"""
    parts = [p.strip() for p in (category_name or "").split(">") if p.strip()]
    return parts[-1] if parts else ""


def region_matches(doc, region):
    """질의한 지역에 실제로 속하는지 주소 접두어로 확인."""
    for addr in (doc.get("road_address_name"), doc.get("address_name")):
        if addr and addr.startswith(region):
            return True
    return False


def is_public_childcare(doc):
    """공공 육아시설로 채택할지 판정."""
    leaf = category_leaf(doc.get("category_name"))
    name = doc.get("place_name", "") or ""

    if any(w in name for w in DENY_NAME_WORDS):
        return False
    if leaf in STRONG_LEAVES:
        return True
    if leaf in WEAK_LEAVES:
        # 넓은 분류는 이름으로 공공 육아시설임을 확인한다.
        return any(w in name for w in PUBLIC_NAME_WORDS)
    return False


def is_sane_name(name):
    n = (name or "").strip()
    return 2 <= len(n) <= 40 and not n.isdigit()


def build_row(doc, region, now_str):
    leaf = category_leaf(doc.get("category_name"))
    addr = doc.get("road_address_name") or doc.get("address_name") or region
    lat, lng = doc.get("y"), doc.get("x")
    # 좌표 표기 규약은 웹앱의 parseLatLon() / region.split('|')[0] 과 동일하다.
    region_val = f"{addr} | 위도:{lat}, 경도:{lng}" if (lat and lng) else addr
    region_leaf = region.split()[-1] if region.split() else region

    # 주차·수유실 등은 카카오가 알려주지 않으므로 태그로 주장하지 않는다.
    tags = ["family:1.0", "baby:1.0", "public:1.0", region_leaf]
    if leaf:
        tags.append(leaf)

    return {
        "source_site":         f"카카오 로컬 | 공공육아 | {region}",
        "category":            "공공키즈카페/실내놀이터",
        "place_or_event_name": doc.get("place_name", "").strip(),
        "target_age":          "영유아 및 어린이 (0세~7세)",
        "region":              region_val,
        # 요금 정보를 주는 소스가 없다. v2.0 은 전 건에
        # '아동 1,000~3,000원 / 보호자 무료' 를 하드코딩했다. 지어내지 않는다.
        "fee_info":            "",
        # 설명문은 확인된 사실만 (분류 + 주소).
        "description":         (f"{leaf} · {addr}".strip(" ·") if leaf else addr),
        "booking_url":         doc.get("place_url", ""),
        "theme_tags":          "toddler:1.0;indoor:1.0;public:1.0",
        # 혼잡도·인기도 측정 소스가 없다. 공란 유지.
        "congestion_score":    "",
        "popularity_score":    "",
        "ai_tags":             ";".join(tags),
        "start_date":          "상시",
        "end_date":            "상시",
        "crawled_at":          now_str,
    }


def collect(regions=None, queries=None, verbose=True):
    regions = regions if regions is not None else ALL_REGIONS
    queries = queries if queries is not None else QUERIES
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    by_id = {}
    stats = {"queries": 0, "calls": 0, "raw": 0, "drop_region": 0,
             "drop_kind": 0, "drop_name": 0, "dup": 0, "failed_queries": []}

    for ri, region in enumerate(regions, 1):
        for kw in queries:
            query = f"{region} {kw}"
            stats["queries"] += 1
            try:
                for page in range(1, KAKAO_MAX_PAGE + 1):
                    docs, is_end = search_kakao(query, page)
                    stats["calls"] += 1
                    stats["raw"] += len(docs)
                    for doc in docs:
                        if not region_matches(doc, region):
                            stats["drop_region"] += 1
                            continue
                        if not is_public_childcare(doc):
                            stats["drop_kind"] += 1
                            continue
                        if not is_sane_name(doc.get("place_name")):
                            stats["drop_name"] += 1
                            continue
                        pid = doc.get("id")
                        if pid in by_id:
                            stats["dup"] += 1
                            continue
                        by_id[pid] = build_row(doc, region, now_str)
                    if is_end or not docs:
                        break
                    time.sleep(0.03)
            except PermissionError:
                raise
            except Exception as e:
                stats["failed_queries"].append(query)
                print(f"    [실패] {query!r}: {type(e).__name__}: {e}")
            time.sleep(0.03)

        if verbose and (ri % 10 == 0 or ri == len(regions)):
            print(f"  [수집 현황] {ri}/{len(regions)} 지역 완료 (시설 {len(by_id)}건)")

    return list(by_id.values()), stats


def main():
    print("=" * 70)
    print("  공공 키즈카페 & 육아종합지원센터 수집기 v3.0 (카카오 로컬)")
    print("=" * 70)

    if not KAKAO_KEY or KAKAO_KEY.startswith("YOUR_"):
        print("[실패] config.json 의 api_keys.kakao_api_key 가 설정되지 않았습니다.")
        sys.exit(1)

    print(f"  {len(ALL_REGIONS)}개 시군구 x {len(QUERIES)}개 유형 수집 시작")
    try:
        rows, stats = collect()
    except PermissionError as e:
        print(f"[실패] {e}")
        sys.exit(1)

    print("\n" + "-" * 70)
    print(f"  API 호출 {stats['calls']}회 / 원본 {stats['raw']}건")
    print(f"  제외: 지역불일치 {stats['drop_region']} · 유형불일치 {stats['drop_kind']}"
          f" · 이름이상 {stats['drop_name']} · 중복 {stats['dup']}")
    if stats["failed_queries"]:
        print(f"  [경고] {len(stats['failed_queries'])}/{stats['queries']}개 질의 실패 "
              f"→ 수집 결과가 불완전합니다: {stats['failed_queries'][:5]}")
    with_coord = sum(1 for r in rows if "위도:" in r["region"])
    leaves = collections.Counter(r["ai_tags"].split(";")[-1] for r in rows)
    print(f"  최종 {len(rows)}건 (좌표 보유 {with_coord}건)")
    print(f"  분류 말단: {dict(leaves.most_common(8))}")
    print("-" * 70)

    if not rows:
        # 수집 0건이면 기존 파일을 덮어쓰지 않는다. 예전 구현은 무조건 덮어써서
        # 대상이 일시 차단되면 기존 데이터가 조용히 사라졌다.
        # 배치(run_web.py)가 실패를 인지하도록 종료 코드 1 을 반환한다.
        print(f"[실패] 수집 0건 → 기존 파일 보존 (덮어쓰기 안 함): {OUTPUT_CSV}")
        sys.exit(1)

    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = OUTPUT_CSV + ".tmp"
    with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HEADERS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, OUTPUT_CSV)      # 원자적 교체
    print(f"[완료] CSV 저장: {OUTPUT_CSV} ({len(rows)}건)")


if __name__ == "__main__":
    main()
