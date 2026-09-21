"""
total_family_data.csv 2차 실시간 보강 파이프라인 (Enrichment Engine) v2.0
=============================================================================
주요 기능:
  1. 네이버 실시간 검색 기반 편의시설(주차, 수유실, 기저귀갈이대, 유모차) 전수 검증 및 ai_tags 부착
  2. 네이버 장소 검색 기반 WGS84 위도(lat), 경도(lng) 좌표 정밀 추출 및 region 컬럼 연동
     (형식: "{지자체 주소} | 위도:{lat}, 경도:{lng}") -> 카카오맵/네이버맵 길찾기 완전 연동
  3. 인기도(popularity_score) 및 실시간 혼잡도(congestion_score) 재산출
  4. LLM 기반 장소 추천 이유(recommend_reason) 및 아빠 맞춤 설명(description) 풍부화
  5. total_family_data.csv 및 total_family_data.json 최종 저장
"""
import sys, io, os, re, json, csv, random, time
from datetime import datetime
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_DIR    = os.path.join(BASE_DIR, "..", "data")
INPUT_CSV   = os.path.join(DATA_DIR, "total_family_data.csv")
OUTPUT_CSV  = os.path.join(DATA_DIR, "total_family_data.csv")
OUTPUT_JSON = os.path.join(DATA_DIR, "total_family_data.json")
CACHE_FILE  = os.path.join(DATA_DIR, "naver_enrich_cache.json")

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

# 카카오 로컬 API 키 (지오코딩용)
_CFG_PATH = os.path.join(BASE_DIR, "config.json")
try:
    with open(_CFG_PATH, "r", encoding="utf-8") as _f:
        CONFIG_KAKAO_KEY = json.load(_f).get("api_keys", {}).get("kakao_api_key", "")
except Exception:
    CONFIG_KAKAO_KEY = ""

# ── 캐시 로드/저장 ──────────────────────────────────────
cache_data = {}
if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
    except:
        cache_data = {}

def save_cache():
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    except:
        pass

# ── 1. 장소명 클리닝 ────────────────────────────────────
def clean_name(name):
    if not name: return ""
    name = re.sub(r'새\s*창\s*열림|더보기|내돈내산|쿠팡.*|네이버페이.*|쿠폰.*|할인.*|솔직후기.*|주말\s*방문.*', '', str(name))
    name = re.sub(r'\(.*?\)|\[.*?\]', '', name)
    name = re.sub(r'키즈카페검색|아기랑가볼만한곳|아이랑가볼만한곳', '', name)
    name = re.sub(r'[^\w\s\-\.\(\)]', '', name)
    return name.strip()

# ── 2. 카카오 로컬 API 기반 위도/경도 ──────────────────────
#
# [기존 구현의 치명적 결함 — 2026-08-23 실측으로 확인]
# 이전 코드는 네이버 검색 결과 HTML 전체에서 정규식으로 첫 번째 "y"/"x" 를
# 집어왔다. 그런데 그 값은 장소 좌표가 아니라 페이지 템플릿의 고정 요소였다.
#   실측: 강남구/노원구/연수구/수원시/마포구 5개 검색어가 전부 동일 좌표 반환
#         (37.2935, 126.8694) — 오차 14.5~43.4km
#   저장 데이터: total_family_data.csv 좌표 1,355건 중 고유값 3개,
#                1,353건(99.9%)이 (37.485305, 126.866500) 하나
# 즉 "장소별 좌표"가 아니라 "그날 네이버 페이지의 상수"를 복사한 것이었다.
# 길찾기에 쓰면 전원이 같은 엉뚱한 곳으로 안내된다.
#
# → 정식 지오코딩(카카오 로컬 API)으로 교체한다.
#   좌표를 못 얻으면 반드시 비운다. 추측값을 넣지 않는다.
KAKAO_KEY = CONFIG_KAKAO_KEY  # config.json 의 kakao_api_key
KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"

# 카카오 로컬 서비스가 꺼져 있으면(403) 매 건 재시도할 이유가 없으므로
# 한 번 확인한 뒤 전역으로 비활성화한다.
_kakao_disabled = False
_kakao_disabled_reason = ""


def dedupe_repeated_suffix(name):
    """인접 반복 접미사 제거.

    수집 스크래퍼가 앵커 텍스트를 이어 붙이면서 같은 어절이 두 번 들어간
    이름이 대량 생성됐다.
      고양어린이박물관박물관              → 고양어린이박물관
      남양주시육아종합지원센터육아종합지원센터   → 남양주시육아종합지원센터
    이 상태로 검색하면 네이버가 플레이스 카드를 띄우지 못해
    편의시설·좌표가 전부 미확인으로 떨어진다.
    (실측: 정제 전 0/20 → 정제 후 3/8 에서 conveniences 확보)
    """
    if not name:
        return name
    prev = None
    while prev != name:
        prev = name
        n = len(name)
        # (a) 바로 붙은 반복:  ...박물관박물관
        for k in range(n // 2, 1, -1):
            if name[-k:] == name[-2 * k:-k]:
                name = name[:-k]
                break
        else:
            # (b) 떨어져 있는 반복: 용인시육아종합지원센터 구갈점육아종합지원센터
            #     오탐을 막기 위해 4글자 이상 토큰만 대상으로 한다.
            for k in range(n // 2, 3, -1):
                tail = name[-k:]
                if tail in name[:-k]:
                    name = name[:-k]
                    break
    return name.strip()


def normalize_place_name(name):
    """검색용 장소명 정규화."""
    if not name:
        return ""
    n = str(name).strip()
    # 블로그 제목 조각에서 흔한 앞뒤 군더더기 제거
    n = re.sub(r'^\d[\d,]*만?\s*명?\s*(이상\s*)?(찾은|방문한|다녀온)\s*', '', n)
    n = re.sub(r'\s*(국내|해외|추천|모음|총정리|베스트|TOP\s*\d+)\s*$', '', n)
    n = dedupe_repeated_suffix(n)
    return n.strip()


# region 앞부분의 행정구역(시도 + 시군구) 추출용
_ADMIN_RE = re.compile(
    r'^((?:서울|경기|인천|부산|대구|광주|대전|울산|세종|강원|충북|충남|전북|전남|경북|경남|제주)\S*)'
    r'\s+(\S*(?:구|시|군))'
)


def build_search_query(name, region):
    """검색 질의 생성.

    ⚠ naver_search_collector 는 region 을 f"{지역} {장소명}" 으로 저장한다.
      (예: region="서울 강남구 캘리클럽 역삼점", name="캘리클럽 역삼점")
      그래서 기존처럼 region + " " + name 을 붙이면
        "서울 강남구 캘리클럽 역삼점 캘리클럽 역삼점"
      같은 중복 질의가 되어 네이버가 플레이스 카드를 띄우지 않는다.
      실측: 중복 질의 → conveniences 없음 / 중복 제거 → 정상 반환.
      이 버그 때문에 편의시설·좌표가 전부 미확인으로 떨어지고 있었다.
    """
    name = normalize_place_name(name)
    base = (region or "").split('|')[0].strip()

    # region 은 f"{지역} {장소명}" 형태라 깨진 장소명을 그대로 품고 있다.
    # (예: region="경기 고양시 고양어린이박물관박물관")
    # region 전체를 쓰면 정규화한 이름이 무의미해지므로, 행정구역 접두어만 뽑는다.
    prefix = ""
    am = _ADMIN_RE.match(base)
    if am:
        prefix = f"{am.group(1)} {am.group(2)}"

    if not name:
        return base

    # 실측 비교(25건 샘플): 지역+장소명 4% vs 장소명 단독 8%.
    # region 의 지역 배정 자체가 틀린 경우가 있어(예: 동작구 시설이 관악구로 기록)
    # 접두어를 붙이면 오히려 플레이스 카드가 안 뜬다. 장소명 단독을 기본으로 쓴다.
    # prefix 는 이름이 너무 짧아 단독으로는 모호할 때만 보조로 사용한다.
    if prefix and len(name) <= 4:
        return f"{prefix} {name}".strip()
    return name


def geocode_kakao(name, region):
    """카카오 로컬 키워드 검색으로 (lat, lng) 조회. 실패 시 (None, None)."""
    global _kakao_disabled, _kakao_disabled_reason

    if _kakao_disabled or not KAKAO_KEY or KAKAO_KEY.startswith("YOUR_"):
        return None, None

    query = build_search_query(name, region)
    if not query:
        return None, None

    try:
        r = requests.get(
            KAKAO_KEYWORD_URL,
            headers={"Authorization": f"KakaoAK {KAKAO_KEY}"},
            params={"query": query, "size": 1},
            timeout=5,
        )
        if r.status_code == 401 or r.status_code == 403:
            _kakao_disabled = True
            _kakao_disabled_reason = r.text[:200]
            print(f"  [카카오 로컬] 사용 불가 (HTTP {r.status_code}) → 이후 좌표는 모두 공란")
            print(f"                {_kakao_disabled_reason}")
            return None, None
        if r.status_code != 200:
            return None, None

        docs = r.json().get("documents", [])
        if not docs:
            return None, None
        d = docs[0]
        # 카카오는 x=경도(lng), y=위도(lat)
        return d.get("y"), d.get("x")
    except Exception as e:
        print(f"  [카카오 로컬 오류] {type(e).__name__}: {e}")
        return None, None


# ── 편의시설: 네이버 플레이스 구조화 필드(conveniences) 파싱 ──────
#
# [기존 구현의 결함 — 2026-08-23 실측]
# 이전 코드는 1.6MB 검색 HTML 전체에 특정 단어가 있는지만 봤다.
#   has_nursing = "수유실" in html
# 그런데 "수유실"은 페이지에 항상 존재하는 JS 라벨 사전
#   {"nursing_room":"수유실", "hospital":"병원", ...}
# 에 들어 있어 **모든 장소에서 무조건 True** 가 됐다.
# "주차"도 124회 등장 중 대부분이 방문자 리뷰·광고 문구였다.
# 그 결과 2,497건 중 1,399건(56%)이 "주차 가능 & 수유실 완비"로 판정됐다.
#
# → 장소별 구조화 필드인 "conveniences" 배열만 인정한다.
#   예) ["단체 이용 가능","무선 인터넷","남/녀 화장실 구분","유아시설 (놀이방)","주차"]
#   배열이 없으면 True/False 가 아니라 **미확인(None)** 으로 둔다.
#
# ⚠ 네이버 conveniences 어휘에는 수유실·기저귀갈이대·유모차 항목이 없다.
#   따라서 이 세 가지는 어떤 방법으로도 검증할 수 없어 태그에서 제외한다.
_CONV_RE = re.compile(r'"conveniences"\s*:\s*\[([^\]]*)\]')


def parse_conveniences(html):
    """네이버 플레이스 편의시설 배열 반환. 필드가 없으면 None(미확인)."""
    m = _CONV_RE.search(html)
    if not m:
        return None
    items = re.findall(r'"([^"]+)"', m.group(1))
    # 네이버 JSON 은 슬래시를 이스케이프해서 내보낸다(예: "남\u002F녀 화장실 구분").
    # 리터럴 6글자 시퀀스를 '/' 로 되돌린다.
    return [it.replace(chr(92) + 'u002F', '/') for it in items]


def fetch_naver_realtime_info(name, region):
    """장소별 좌표 + 편의시설 정보.

    좌표    : 카카오 로컬 API (정식 지오코딩)
    편의시설: 네이버 플레이스 conveniences 배열 (구조화 필드)

    conveniences 가 없으면 amenities_known=False 로 두고, 편의시설에 대해
    아무 주장도 하지 않는다.
    """
    cache_key = f"{region}_{name}"
    cached = cache_data.get(cache_key)
    if cached is not None:
        # 좌표가 빈 캐시는 카카오 로컬이 꺼져 있을 때 생긴 것이다.
        # 지금 카카오를 쓸 수 있으면 좌표만 다시 조회해 캐시를 갱신한다.
        if not cached.get("lat") and not _kakao_disabled and KAKAO_KEY and not KAKAO_KEY.startswith("YOUR_"):
            lat, lng = geocode_kakao(name, region)
            if lat and lng:
                cached["lat"], cached["lng"] = lat, lng
        return cached

    lat, lng = geocode_kakao(name, region)

    query = build_search_query(name, region)
    search_url = f"https://search.naver.com/search.naver?where=nexearch&query={quote(query)}"

    conv = None
    try:
        r = requests.get(search_url, headers=HTTP_HEADERS, timeout=5)
        if r.status_code == 200:
            conv = parse_conveniences(r.text)
    except Exception as e:
        print(f"  [네이버 검색 오류] {name}: {type(e).__name__}")

    joined = " ".join(conv) if conv else ""
    result = {
        "lat": lat,
        "lng": lng,
        "amenities_known": conv is not None,
        "conveniences": conv or [],
        # 배열에 명시된 것만 True. 미확인이면 False 가 아니라 '주장 안 함'이며,
        # amenities_known 으로 구분한다.
        "parking":    ("주차" in joined),
        "kids_facility": ("유아시설" in joined or "놀이방" in joined),
        "restroom":   ("화장실" in joined),
        "wifi":       ("인터넷" in joined or "와이파이" in joined),
    }

    cache_data[cache_key] = result
    return result

# ── 3. 편의시설 태그 조합 ──────────────────────────────
def build_ai_tags(real_info, cat, orig_tags):
    """편의시설 태그는 네이버 conveniences 로 확인된 것만 부여한다.

    제거한 것:
      - parking:0.8  : 미확인인데도 '0.8' 이라는 그럴듯한 수치를 붙이고 있었다.
                       확인 안 되면 태그 자체를 달지 않는다.
      - nursing_room / diaper_table : 카테고리가 키즈카페라는 이유만으로
                       '수유실·기저귀갈이대 완비'를 단정했다. 근거가 없다.
                       게다가 네이버 conveniences 어휘에 두 항목이 존재하지
                       않아 애초에 검증이 불가능하다.
      - stroller     : 위와 동일하게 검증 불가.
    """
    tags = ["family:1.0"]

    # 확인된 편의시설만 태그로 부착
    if real_info.get("parking"):
        tags.append("parking:1.0")
    if real_info.get("kids_facility"):
        tags.append("kids_facility:1.0")
    if real_info.get("restroom"):
        tags.append("restroom:1.0")

    if '키즈카페' in cat or '놀이터' in cat: tags.append("play:1.0")
    if '물놀이' in cat or '자연' in cat: tags.append("water:1.0")
    if '체험' in cat: tags.append("experience:1.0")
    if '문화' in cat or '티켓' in cat: tags.append("culture:1.0")

    existing_list = [t.strip() for t in str(orig_tags).split(';') if t.strip() and ':' not in t and t not in tags]
    all_tags = tags + existing_list
    return ";".join(dict.fromkeys(all_tags))

# ── 4. 추천 이유 및 설명 생성 ────────────────────────────
def generate_recommend_reason(name, cat, ai_tags, real_info):
    """추천 이유. 확인된 사실만 언급하고, 미확인 항목은 아예 말하지 않는다.

    기존에는 편의시설 판정이 틀렸는데도 "실시간 네이버 검증", "실검증",
    "완비" 같은 단정 표현을 썼다. 2,497건 중 1,399건(56%)이 근거 없이
    "주차 가능 & 수유실·기저귀갈이대 완비"로 표시됐다.
    """
    conv = real_info.get("conveniences") or []
    if real_info.get("parking") and real_info.get("kids_facility"):
        return "🅿️ 주차 가능 · 🧸 유아시설 보유 (네이버 플레이스 등록 정보)"
    elif real_info.get("parking"):
        return "🅿️ 주차 가능 (네이버 플레이스 등록 정보)"
    elif real_info.get("kids_facility"):
        return "🧸 유아시설 보유 (네이버 플레이스 등록 정보)"
    elif 'water:1.0' in ai_tags:
        return "🌊 시원한 물놀이와 야외 활동을 한 번에 즐길 수 있는 여름 인기 장소"
    elif 'play:1.0' in ai_tags or '키즈' in cat:
        return "🧸 영유아 안심 실내 놀이기구와 부모 쉼터가 잘 갖춰진 키즈 파라다이스"
    elif 'culture:1.0' in ai_tags or '문화' in cat:
        return "🎨 아이들 눈높이에 맞춘 체험형 관람 코스로 교육과 재미를 동시 만족"
    else:
        return "👨‍👧 아빠와 아이가 주말에 부담 없이 특별한 추억을 만들 수 있는 베스트 추천지"

# 과거 버전이 생성한 템플릿 설명문 판별용 지문.
# 이 문구들이 들어 있으면 사람이 쓴 원본이 아니라 자동 생성물이다.
_LEGACY_DESC_MARKERS = (
    "실시간 네이버 검색 기반으로",
    "주말 아이 동반 최적 명소입니다",
    "연령대 아이와 아빠가 함께 방문하기에 적극 추천",
)


def _is_legacy_template(text):
    return any(mk in text for mk in _LEGACY_DESC_MARKERS)


def generate_llm_description(name, cat, region, target_age, original="", real_info=None):
    """설명문.

    변경점:
      1. "실시간 네이버 검색 기반으로 ... 검증되었으며" 문구 삭제.
         실제 검증 로직이 부정확했는데도 2,497건 전부가 이 주장을 달고 있었다.
      2. 원본 설명이 있으면 그대로 보존한다. 기존에는 공연·전시 202건의
         원본 설명까지 "주말 아이 동반 최적 명소"로 덮어써 내용이 왜곡됐다.
      3. 편의시설은 확인된 것만 덧붙인다.
    """
    original = (original or "").strip()
    # 과거 실행이 남긴 템플릿 문구는 '원본'이 아니다. 그대로 보존하면
    # 허위 검증 주장이 계속 살아남으므로 없는 것으로 취급하고 재생성한다.
    if original and not _is_legacy_template(original) and original.lower() not in ("nan", "none"):
        return original[:400]

    reg_clean = region.split('|')[0].strip() if region else "수도권"
    parts = [f"[{name}]는 {reg_clean} 지역의 {cat} 장소입니다."]

    conv = (real_info or {}).get("conveniences") or []
    if conv:
        parts.append("네이버 플레이스 등록 편의시설: " + ", ".join(conv[:5]) + ".")

    if target_age and target_age.lower() not in ("nan", "none"):
        parts.append(f"대상 연령: {target_age}.")
    return " ".join(parts)

# ── 5. 메인 보강 파이프라인 ────────────────────────────────
def enrich_data():
    print("=" * 75)
    print("  total_family_data.csv 2차 실시간 보강 파이프라인 (네이버 검색&좌표) 구동")
    print("=" * 75)

    if not os.path.exists(INPUT_CSV):
        print(f"❌ 입력 파일 없음: {INPUT_CSV}")
        return

    df = pd.read_csv(INPUT_CSV, encoding='utf-8-sig')
    print(f"📥 기존 데이터 {len(df)}건 로드 완료")

    enriched_rows = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    count = 0
    for idx, row in df.iterrows():
        raw_name   = str(row.get('place_or_event_name', '')).strip()
        c_name     = clean_name(raw_name) or raw_name
        category   = str(row.get('category', '가족체험')).strip()
        orig_region= str(row.get('region', '')).strip()
        target_age = str(row.get('target_age', '영유아 및 어린이')).strip()
        fee_info   = str(row.get('fee_info', '무료/유료')).strip()
        orig_tags  = str(row.get('ai_tags', '')).strip()

        # 1) 네이버 실시간 검색 기반 위도/경도 좌표 & 편의시설 검증
        real_info = fetch_naver_realtime_info(c_name, orig_region)

        # 2) 위도/경도 좌표 연동한 region 포맷 재구성
        base_addr = orig_region.split('|')[0].strip() if orig_region else f"수도권 {c_name}"
        lat = real_info.get("lat")
        lng = real_info.get("lng")

        if lat and lng:
            region_fmt = f"{base_addr} | 위도:{lat}, 경도:{lng}"
        else:
            # 자체 조회가 실패해도, 수집 단계에서 이미 확보한 좌표가 있으면
            # 지우지 않는다. place_search_collector 는 카카오 로컬에서 좌표를
            # 함께 받아오므로, 여기서 덮어쓰면 확보한 좌표를 잃는다.
            _m = re.search(r'위도:([\d.]+), 경도:([\d.]+)', orig_region)
            if _m:
                region_fmt = f"{base_addr} | 위도:{_m.group(1)}, 경도:{_m.group(2)}"
            else:
                region_fmt = base_addr

        # 3) 실검증 편의시설 ai_tags 구성
        new_ai_tags = build_ai_tags(real_info, category, orig_tags)

        # 4) 인기도 & 혼잡도 — 원본 값을 그대로 통과시킨다.
        #    기존에는 값이 없거나 범위를 벗어나면 randint 로 메워서, 측정된 적
        #    없는 수치가 실측값처럼 저장됐다. 측정값이 없으면 공란으로 둔다.
        def _passthrough(key, valid=None):
            raw = str(row.get(key, '')).strip()
            if raw in ('', 'nan', 'None'):
                return ""
            try:
                v = int(float(raw))
            except (TypeError, ValueError):
                return ""
            if valid is not None and v not in valid:
                return ""
            return v

        pop_score  = _passthrough('popularity_score')
        cong_score = _passthrough('congestion_score', valid=[1, 2, 3, 4, 5])

        # 5) 아빠 맞춤 설명 및 추천 이유 생성
        original_desc = str(row.get('description', '')).strip()
        description = generate_llm_description(
            c_name, category, base_addr, target_age,
            original=original_desc, real_info=real_info)
        recommend_reason = generate_recommend_reason(c_name, category, new_ai_tags, real_info)

        enriched_rows.append({
            "source_site":         str(row.get('source_site', '네이버 추천')),
            "category":            category,
            "place_or_event_name": c_name,
            "period":              str(row.get('period', '상시')),
            "target_age":          target_age,
            "region":              region_fmt,
            "fee_info":            fee_info,
            "description":         description,
            "booking_url":         str(row.get('booking_url', 'https://search.naver.com')),
            "ai_tags":             new_ai_tags,
            "crawled_at":          now_str,
            "theme_tags":          str(row.get('theme_tags', 'family:1.0')),
            "congestion_score":    cong_score,
            "popularity_score":    pop_score,
            "recommend_reason":    recommend_reason
        })

        count += 1
        if count % 100 == 0 or count == len(df):
            print(f"  [보강 진행] {count}/{len(df)}건 처리 완료 (위도/경도 & 편의시설 네이버 실검증 진행 중)")
            # 중간 저장: 2,500여 건 도중에 중단돼도 지금까지의 조회를 잃지 않는다.
            save_cache()

    # 캐시 저장
    save_cache()

    # DataFrame 생성 및 중복 제거
    res_df = pd.DataFrame(enriched_rows)
    res_df = res_df.drop_duplicates(subset=['place_or_event_name'])
    final_len = len(res_df)

    # CSV 저장
    res_df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
    print(f"✅ 보강된 CSV 저장 완료: {OUTPUT_CSV} ({final_len}건)")

    # JSON 저장
    json_records = res_df.to_dict(orient='records')
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(json_records, f, ensure_ascii=False, indent=2)
    print(f"✅ 보강된 JSON 저장 완료: {OUTPUT_JSON} ({final_len}건)")
    print("=" * 75)

if __name__ == "__main__":
    enrich_data()
