"""
카카오 로컬 기반 정밀 장소(Place) 수집기 v7.0
=============================================================================
왜 다시 썼는가 (P2-1)
-----------------------------------------------------------------------------
v6.0 은 네이버 검색 결과 HTML 에서 `soup.find_all('a')` 로 페이지의 모든 앵커를
훑고 `get_text()` 로 자손 텍스트를 이어 붙여 장소명을 만들었다. 그 결과:

  - 장소 카드가 뭉쳤다
      '장난감도서관 산본점' + 카테고리 '장난감대여'
        -> '군포장난감도서관산본점장난감대여'
  - 뉴스·블로그 앵커의 문장이 장소명으로 들어왔다
      '용산구육아종합지원센터와 업무협약 체결'
      '안양에는 무료 박물관과 환경'
  - 같은 장소가 표기 변형마다 별건으로 등재됐다
      '송현공원' / '동구송현공원' / '동구인천 동구의 송현공원' ...
  - 이름이 손상돼 후속 지오코딩·편의시설 조회가 대량 실패했다

원인은 정규식 정제가 부족한 게 아니라, **비구조화된 HTML 에서 상호명을
추측하려 한 접근 자체**였다. 카카오 로컬 키워드 검색은 상호명(place_name),
분류(category_name), 도로명주소, 좌표(x/y), 고유 id 를 구조화해서 준다.
추측할 필요가 없다.

v7.0 이 달라진 점
-----------------------------------------------------------------------------
  1. 데이터 소스: 네이버 검색 HTML 스크래핑 -> 카카오 로컬 키워드 검색 API
  2. 장소명: 정규식 정제 없이 place_name 그대로 사용
  3. 좌표: 수집 단계에서 확보 (이전에는 전량 공란)
  4. 중복 제거: 이름 문자열이 아니라 카카오 장소 고유 id 기준
  5. 지역 검증: 카카오는 질의 지역 밖 결과도 반환하므로 주소 접두어로 필터
     (예: '경기 안양시 어린이박물관' -> 광명/서울 결과가 섞여 나온다)
  6. 없는 사실을 주장하지 않는다: 이전에는 전 건에
     parking:1.0;nursing_room:1.0 을 하드코딩해 주차·수유실이 있다고
     단정했다. 카카오는 그 정보를 주지 않으므로 태그를 붙이지 않는다.

출력: data/place_search_results.csv (total_family_data 스키마 호환)
"""
import sys, io, os, json, csv, time, re
from datetime import datetime
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(BASE_DIR, "..", "data")
OUTPUT_CSV = os.path.join(DATA_DIR, "place_search_results.csv")

# ── 카카오 로컬 키 ──────────────────────────────────────
_CFG_PATH = os.path.join(BASE_DIR, "config.json")
try:
    with open(_CFG_PATH, "r", encoding="utf-8") as _f:
        KAKAO_KEY = json.load(_f).get("api_keys", {}).get("kakao_api_key", "")
except Exception:
    KAKAO_KEY = ""

KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
KAKAO_PAGE_SIZE   = 15   # API 상한
KAKAO_MAX_PAGE    = 3    # 15 x 3 = 45건 (카카오 키워드 검색의 사실상 상한)

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

# 인천은 행정구역이 개편돼 카카오 주소 데이터가 새 구 이름을 쓴다.
# 옛 이름으로 질의하면 지역 검증이 전부 실패해 수집이 0건이 된다
# (실측: '인천 중구 공원' -> 반환 주소가 전부 '인천 제물포구').
#   인천 중구 / 동구 -> 제물포구 · 영종구
#   인천 서구        -> 서해구 · 검단구
# 아래 목록은 카카오 주소에 실제로 존재하는 이름만 담았다 (질의로 확인).
# 강화군·옹진군은 v6.0 목록에도 없었으므로 기존 범위를 유지해 제외한다.
INCHEON_DISTRICTS = [
    "인천 제물포구", "인천 영종구", "인천 서해구", "인천 검단구",
    "인천 미추홀구", "인천 연수구", "인천 남동구", "인천 부평구", "인천 계양구"
]

ALL_REGIONS = SEOUL_DISTRICTS + GYEONGGI_CITIES + INCHEON_DISTRICTS

# ── 테마 ────────────────────────────────────────────────
# queries      : 카카오에 던지는 장소 유형 키워드들. '아기랑'/'어린이' 같은
#                수식어는 넣지 않는다. 카카오는 장소 색인이라 수식어가 붙으면
#                검색이 흐려지거나 0건이 된다 (실측: '어린이박물관' 0건,
#                '박물관' 15건 / '농장체험' 0건, '농장' 14건).
# accept_leaf  : 카카오 category_name 의 **말단만** 대조한다.
#                전체 경로에는 '여행 > 관광,명소 > ...' 처럼 광범위한 단어가
#                섞여 있어, 경로 전체에 대조하면 '화장품목장'·'공영주차장'·
#                '삼신장례문화체험관' 까지 통과한다.
THEMES = [
    {"cat": "사설키즈카페", "queries": ["키즈카페"],
     "theme_tag": "toddler:1.0;indoor:0.9;play:1.0",
     "accept_leaf": ["키즈카페", "키즈", "놀이시설", "실내놀이터", "놀이방", "놀이터"]},
    {"cat": "자연친화", "queries": ["계곡"],
     "theme_tag": "valley:1.0;nature:1.0;water:1.0",
     "accept_leaf": ["계곡", "유원지", "휴양림"],
     # 카카오가 계곡으로 분류한 것 중 상당수가 '수리골'·'진골'·'무성골' 같은
     # 시설 없는 미세 지명이다. 실제로 찾아갈 만한 곳은 이름에 '계곡'/'유원지'
     # 가 붙어 있다. 좌표는 정확하지만 나들이 대상이 아니므로 이름으로 좁힌다.
     "require_name": ["계곡", "유원지", "휴양림"]},
    {"cat": "자연친화", "queries": ["수영장", "물놀이터"],
     "theme_tag": "pool:1.0;water:1.0;outdoor:0.9",
     "accept_leaf": ["수영장", "워터파크", "물놀이"]},
    {"cat": "자연친화", "queries": ["공원", "어린이공원"],
     "theme_tag": "park:1.0;picnic:1.0;nature:1.0",
     "accept_leaf": ["공원", "놀이터", "유원지"]},
    {"cat": "자연친화", "queries": ["수목원"],
     "theme_tag": "nature:1.0;outdoor:1.0;picnic:0.8",
     "accept_leaf": ["수목원", "식물원", "생태"]},
    # 사설 미술학원 테마는 두지 않는다. 실측 추정 약 2,600건으로 전체의 26%를
    # 차지하는데, 정기 교습 상업시설이라 주말 나들이 목적과 성격이 다르다.
    # 미술 쪽 나들이 수요는 아래 박물관 테마의 accept_leaf '미술관' 이 받는다.
    {"cat": "가족체험", "queries": ["농장"],
     "theme_tag": "farm:1.0;animal:1.0;experience:1.0",
     "accept_leaf": ["농장", "목장", "주말농장", "동물원"]},
    {"cat": "가족체험", "queries": ["박물관", "과학관"],
     "theme_tag": "museum:1.0;hands_on:1.0;experience:1.0",
     "accept_leaf": ["박물관", "과학관", "미술관", "전시관", "기념관"]},
    {"cat": "가족체험", "queries": ["체험관"],
     "theme_tag": "experience:1.0;hands_on:1.0;family_time:1.0",
     "accept_leaf": ["체험학습장", "체험관", "체험"]},
]

# 분류 말단이 통과해도 가족 나들이 대상이 아닌 것들. 실측으로 걸러낸 사례:
#   '삼신장례문화체험관'(체험학습장), '화장품목장'(화장품),
#   '수목원입구노외 공영유료주차장'(공영주차장), '숙명여대 과학관'(학교부속시설)
DENY_NAME_WORDS = [
    "장례", "납골", "화장장", "추모", "묘지", "봉안",
    "정육", "주차장", "공영주차", "노외주차",
]

# 말단이 이 값과 **정확히 같을 때만** 제외한다. 부분 일치를 쓰면
# '카페' 가 '키즈카페' 에 걸려 키즈카페가 전량 사라진다 (실측으로 확인).
DENY_LEAF_EXACT = {
    "카페", "갤러리카페", "커피전문점", "정육점", "육류,고기", "장어", "오리",
    "화장품", "우유판매,유제품판매", "부동산", "학교부속시설",
}
# 말단에 부분 일치하면 제외. 오탐 위험이 없는 단어만 넣는다.
DENY_LEAF_SUBSTR = ["주차장"]

CSV_FIELDS = [
    "source_site", "category", "place_or_event_name", "period",
    "target_age", "region", "fee_info", "description", "booking_url",
    "ai_tags", "crawled_at", "theme_tags", "congestion_score", "popularity_score"
]


def search_kakao(query, page=1):
    """카카오 로컬 키워드 검색 1페이지. (documents, is_end) 반환.

    실패는 삼키지 않고 호출자에 알린다. v6.0 의 `except Exception: pass` 는
    차단·타임아웃을 로그 없이 없애서 부분 수집을 정상으로 오인하게 만들었다.
    """
    r = requests.get(
        KAKAO_KEYWORD_URL,
        headers={"Authorization": f"KakaoAK {KAKAO_KEY}"},
        params={"query": query, "size": KAKAO_PAGE_SIZE, "page": page},
        timeout=6,
    )
    if r.status_code in (401, 403):
        raise PermissionError(
            f"카카오 로컬 사용 불가 (HTTP {r.status_code}): {r.text[:160]}"
        )
    r.raise_for_status()
    d = r.json()
    return d.get("documents", []), bool(d.get("meta", {}).get("is_end", True))


def region_matches(doc, region):
    """카카오 결과가 질의한 지역에 실제로 속하는지 주소 접두어로 확인.

    카카오 키워드 검색은 지역을 강제하지 않는다. '경기 안양시 어린이박물관'
    질의에 광명·서울 결과가 섞여 나오므로 이 검증이 없으면 엉뚱한 지역의
    장소에 잘못된 region 이 붙는다.
    '경기 수원시' 처럼 하위 구가 있어도 접두어 비교로 통과한다
    ('경기 수원시 팔달구 ...').
    """
    for addr in (doc.get("road_address_name"), doc.get("address_name")):
        if addr and addr.startswith(region):
            return True
    return False


def theme_matches(doc, accept_leaf):
    """카카오 분류의 **말단**이 테마에 맞는지.

    전체 경로가 아니라 말단만 본다. 경로에는 '여행 > 관광,명소 > ...' 처럼
    광범위한 단어가 있어 경로 전체를 대조하면 무관한 장소가 대량 통과한다.
    """
    leaf = category_leaf(doc.get("category_name"))
    return any(k in leaf for k in accept_leaf)


def name_required_ok(doc, theme):
    """테마가 require_name 을 지정했으면 상호명에 그 단어가 있어야 한다.

    분류만으로는 걸러지지 않는 경우에 쓴다. 예: 카카오가 '계곡' 으로 분류한
    '수리골'·'진골' 은 시설 없는 미세 지명이라 나들이 대상이 아니다.
    """
    req = theme.get("require_name")
    if not req:
        return True
    return any(w in doc.get("place_name", "") for w in req)


def is_denied(doc):
    """분류 말단은 통과했지만 가족 나들이 대상이 아닌 장소를 걸러낸다."""
    leaf = category_leaf(doc.get("category_name"))
    name = doc.get("place_name", "")
    if leaf in DENY_LEAF_EXACT:
        return True
    if any(w in leaf for w in DENY_LEAF_SUBSTR):
        return True
    if any(w in name for w in DENY_NAME_WORDS):
        return True
    return False


def is_sane_name(name):
    """카카오 상호명은 이미 정제돼 있어 최소 확인만 한다."""
    n = (name or "").strip()
    return 2 <= len(n) <= 40 and not n.isdigit()


def category_leaf(category_name):
    """'가정,생활 > 유아 > 놀이시설 > 키즈카페' -> '키즈카페'"""
    parts = [p.strip() for p in (category_name or "").split(">") if p.strip()]
    return parts[-1] if parts else ""


def build_row(doc, region, theme, now_str):
    leaf = category_leaf(doc.get("category_name"))
    addr = doc.get("road_address_name") or doc.get("address_name") or region
    lat, lng = doc.get("y"), doc.get("x")

    # 좌표를 확보했으면 region 에 함께 담는다. 표기 형식은 웹앱의
    # parseLatLon() / region.split('|')[0] 규약과 동일하다.
    region_val = f"{addr} | 위도:{lat}, 경도:{lng}" if (lat and lng) else addr

    # 지역 말단(구/시/군) 을 태그로 쓴다.
    region_leaf = region.split()[-1] if region.split() else region

    # 주차·수유실 등 편의시설은 카카오가 알려주지 않는다. v6.0 은 전 건에
    # parking:1.0;nursing_room:1.0 을 박아 넣어 실측값처럼 보이게 했다.
    # 확인되지 않은 시설은 태그로 주장하지 않는다.
    tags = ["family:1.0", "baby:1.0", region_leaf]
    if leaf:
        tags.append(leaf)

    # 설명문은 확인된 사실만 쓴다 (분류 + 주소). 홍보 문구를 만들지 않는다.
    desc = f"{leaf} · {addr}".strip(" ·") if leaf else addr

    return {
        "source_site":         f"카카오 로컬 | {region}",
        "category":            theme["cat"],
        "place_or_event_name": doc.get("place_name", "").strip(),
        "period":              "상시",
        "target_age":          "영유아 및 어린이 (0세~9세)",
        "region":              region_val,
        # 이용료 정보를 주는 소스가 없다. 지어내지 않고 비워 둔다.
        "fee_info":            "",
        "description":         desc,
        "booking_url":         doc.get("place_url", ""),
        "ai_tags":             ";".join(tags),
        "crawled_at":          now_str,
        "theme_tags":          theme["theme_tag"],
        # 혼잡도·인기도 측정 소스가 없다. 공란 유지.
        "congestion_score":    "",
        "popularity_score":    "",
    }


def collect_places(regions=None, themes=None, verbose=True):
    """지역 x 테마 전수 수집. (rows, stats) 반환."""
    regions = regions if regions is not None else ALL_REGIONS
    themes  = themes  if themes  is not None else THEMES
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    by_id = {}                       # 카카오 장소 id -> row (중복 제거 기준)
    stats = {
        "queries": 0, "calls": 0, "raw": 0,
        "drop_region": 0, "drop_theme": 0, "drop_name_req": 0, "drop_deny": 0,
        "drop_name": 0, "dup": 0,
        "failed_queries": [],
    }

    total_q = len(regions) * sum(len(t["queries"]) for t in themes)
    for ri, region in enumerate(regions, 1):
        for theme in themes:
            for kw in theme["queries"]:
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
                            if not theme_matches(doc, theme["accept_leaf"]):
                                stats["drop_theme"] += 1
                                continue
                            if not name_required_ok(doc, theme):
                                stats["drop_name_req"] += 1
                                continue
                            if is_denied(doc):
                                stats["drop_deny"] += 1
                                continue
                            if not is_sane_name(doc.get("place_name")):
                                stats["drop_name"] += 1
                                continue
                            pid = doc.get("id")
                            if pid in by_id:
                                stats["dup"] += 1
                                continue
                            by_id[pid] = build_row(doc, region, theme, now_str)
                        if is_end or not docs:
                            break
                        time.sleep(0.03)
                except PermissionError:
                    raise                              # 키 문제는 즉시 중단
                except Exception as e:
                    stats["failed_queries"].append(query)
                    print(f"    [실패] {query!r}: {type(e).__name__}: {e}")
                time.sleep(0.03)

        if verbose and (ri % 10 == 0 or ri == len(regions)):
            print(f"  [수집 현황] {ri}/{len(regions)} 지역 완료 "
                  f"(장소 {len(by_id)}건 / 질의 {stats['queries']}/{total_q})")

    return list(by_id.values()), stats


def main():
    print("=" * 70)
    print("  카카오 로컬 기반 정밀 장소 수집기 v7.0")
    print("=" * 70)

    if not KAKAO_KEY or KAKAO_KEY.startswith("YOUR_"):
        print("[실패] config.json 의 api_keys.kakao_api_key 가 설정되지 않았습니다.")
        sys.exit(1)

    print(f"  수도권 {len(ALL_REGIONS)}개 시군구 x {len(THEMES)}개 테마 수집 시작")
    try:
        rows, stats = collect_places()
    except PermissionError as e:
        print(f"[실패] {e}")
        sys.exit(1)

    print("\n" + "-" * 70)
    print(f"  API 호출 {stats['calls']}회 / 원본 {stats['raw']}건")
    print(f"  제외: 지역불일치 {stats['drop_region']} · 테마불일치 {stats['drop_theme']}"
          f" · 이름조건 {stats['drop_name_req']} · 부적합 {stats['drop_deny']}"
          f" · 이름이상 {stats['drop_name']}"
          f" · 중복 {stats['dup']}")
    if stats["failed_queries"]:
        print(f"  [경고] {len(stats['failed_queries'])}/{stats['queries']}개 질의 실패 "
              f"→ 수집 결과가 불완전합니다: {stats['failed_queries'][:5]}")
    with_coord = sum(1 for r in rows if "위도:" in r["region"])
    print(f"  최종 {len(rows)}건 (좌표 보유 {with_coord}건)")
    print("-" * 70)

    if not rows:
        # 수집 0건이면 기존 파일을 덮어쓰지 않는다. 예전 구현은 무조건 덮어써서
        # 대상 사이트가 일시 차단되면 기존 데이터가 조용히 사라졌다.
        # 배치(run_web.py)가 실패를 인지하도록 종료 코드 1 을 반환한다.
        print(f"[실패] 수집 0건 → 기존 파일 보존 (덮어쓰기 안 함): {OUTPUT_CSV}")
        sys.exit(1)

    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = OUTPUT_CSV + ".tmp"
    with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, OUTPUT_CSV)      # 원자적 교체: 중단 시 기존 파일 보존
    print(f"[완료] CSV 저장: {OUTPUT_CSV} ({len(rows)}건)")


if __name__ == "__main__":
    main()
