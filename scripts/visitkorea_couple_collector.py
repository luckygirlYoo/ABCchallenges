"""
대한민국 구석구석(VisitKorea, korean.visitkorea.or.kr) 커플/데이트 태그 수집기 v1.1
=============================================================================
[커플 테마 파이프라인 1단계: 원천 데이터 수집 — 두 번째 소스]

⚠️ 이 스크립트는 어떤 경우에도 git add / commit / push 를 실행하지 않는다.
   파일 생성·수정까지만 하고 멈춘다. 커밋 여부는 사람이 직접 결정한다.

v1.1 변경사항 (실행 결과 리뷰 반영)
-----------------------------------------------------------------------------
1. period 에 "상시"를 무조건 채우던 것을 제거. 이 API 에는 팝업과 달리
   '행사 기간' 개념 자체가 없고 운영시간(useTime)/휴무일(restDate)만 있다.
   실측 80건 샘플 중 useTime 이 비어있는 건 9건뿐이고 나머지는 "하절기
   08:00~21:00" 같은 시간대라, "상시"는 사실과 다른 플레이스홀더였다.
   → always_yn == 'Y' 인 경우에만 "상시", 그 외에는 공란.
     운영시간/휴무일은 버리지 않고 ai_tags 의 use_time= / rest_date= 로 보존.
2. category 를 전 건 "야경/데이트명소"로 박아넣던 것을 실제 데이터 기반
   3분류로 교체 (v1.2). 실측 결과 문화관광/체험관광/역사관광/레저스포츠/음식/
   자연관광/쇼핑까지 광범위하게 분포해(음식점·쇼핑몰·역사유적지 포함) 단일
   값은 부정확했다. 반대로 원본 대분류를 그대로 7종 쓰면 지나치게 잘아,
   아래 3개로 통합했다:
     - 야경뷰포인트 : 야경_명소 태그가 붙은 곳 (최우선 판정, 실측 150건)
     - 실내데이트   : 음식·쇼핑·체험·문화시설 등
     - 야외데이트   : 자연·역사유적·레저 등
   원본 대분류/중분류는 theme_tags 에 그대로 남으므로 나중에 더 잘게
   나눠야 하면 재수집 없이 복원할 수 있다.
3. "야경"과 "데이트"를 별도 축으로도 분리. 실측 337건 중 야경만 125건,
   데이트만 187건, 둘 다 25건으로 사실상 겹치지 않는 축이다.
   → theme_tags 에 night_view:1.0 / date_spot:1.0 을 각각 부착해서
     2단계 통합기가 독립적으로 필터링할 수 있게 했다.

무엇을 하는가
-----------------------------------------------------------------------------
1. korean.visitkorea.or.kr 의 비공식(비인증) 내부 API 를 사용한다.
   실제 사이트가 브라우저에서 호출하는 것과 동일한 두 엔드포인트를 그대로 쓴다
   (모두 POST https://korean.visitkorea.or.kr/call, 로그인/키 불필요, UA 헤더만 있으면 됨):
     - cmd=TOUR_CONTENT_LIST_VIEW : 태그(tagId)로 장소 목록 조회 (최대 cnt=100/페이지)
     - cmd=TOUR_CONTENT_BODY_DETAIL : 장소 하나의 상세정보(좌표/설명 등) 조회
2. 아래 4개 태그로 목록을 조회한다 (실측 중복 제거 후 총 337개 장소):
     - 야경_명소       tagId=ab6c42d4-4168-42dc-b2c5-b5fc0f168808  (150건)
     - 커플데이트      tagId=07e45e70-e2f3-11e8-9488-02001c6b0001  (156건)
     - 데이트장소추천  tagId=064dc4f0-b4b2-11e8-b248-02001c6b0001  (54건)
     - 연인·친구       tagId=ce504b20-2ef9-44f9-84c6-38c518700e55  (42건)
   ("연인과함께" tagId=692daa17-... 은 2,256건으로 범위가 너무 넓어(노이즈 위험)
    기본 목록에서 제외했다. 필요하면 COUPLE_TAGS 에 추가하면 된다.)
3. 목록 조회 결과의 MODIFIED_DATE 를 캐시와 비교해서, 바뀌지 않은 장소는
   상세 API(TOUR_CONTENT_BODY_DETAIL)를 호출하지 않고 캐시에 저장해둔
   행(row)을 그대로 재사용한다 (= popup_collector.py 와 동일한 설계 원칙).
4. 여러 태그에 동시에 속하는 장소(cotId 중복)는 하나로 합치고,
   어떤 태그로 수집됐는지는 ai_tags 에 source_tag_* 로 남긴다.
5. total_family_data.csv 와 동일한 14개 컬럼 스키마로
   data/visitkorea_couple_spots_raw.csv 에 저장한다.

무엇을 하지 않는가 (중요 — popup_collector.py 와 동일한 원칙)
-----------------------------------------------------------------------------
- fee_info, congestion_score, popularity_score 처럼 원본에 실측값이
  없는 필드는 절대 임의의 값으로 채우지 않는다. 공란으로 둔다.
  대신 실측된 참여 지표(conLike/conRead/conShare, 좋아요·조회·공유수)는
  ai_tags 에 원자료로만 남긴다(정규화된 점수로 만들지 않음).
- 동시 다발 요청(멀티스레드/비동기)을 쓰지 않는다. 요청 사이 sleep 을 둔다.
- overView(설명 원문)를 대량으로 그대로 복제 저장하지 않는다(길이 제한).

담당자가 실행 전 확인할 것
-----------------------------------------------------------------------------
- 이 API 는 사이트가 공식 문서로 공개한 API 가 아니라, 브라우저가 내부적으로
  호출하는 엔드포인트를 그대로 재현한 것이다. 사이트 개편 시 언제든 바뀔 수
  있으므로, 정기 실행 중 응답 구조가 달라지면(파싱 실패 로그가 쌓이면) 가장
  먼저 이 사실을 의심할 것.
  대안: 한국관광공사가 별도로 공식 제공하는 'TourAPI 4.0'(공공데이터포털,
  인증키 필요)이 있다. 안정성이 더 중요해지면 이 비공식 API 대신 TourAPI 4.0
  으로 교체하는 것을 검토할 것.
- netfunnel(대기열) 시스템이 있는 사이트다. 브라우저 접속은 몰리면 대기 페이지가
  뜨지만, 이번에 확인한 바로는 이 API 호출 자체는 영향받지 않았다. 그래도
  요청 사이 sleep 을 반드시 지킬 것.
"""
import sys, io, os, re, csv, json, time, random
from datetime import datetime
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
OUTPUT_CSV = os.path.join(DATA_DIR, "visitkorea_couple_spots_raw.csv")
CACHE_FILE = os.path.join(DATA_DIR, "visitkorea_couple_collect_cache.json")

API_URL = "https://korean.visitkorea.or.kr/call"

# ── 수집 대상 태그 ──────────────────────────────────────────────────────
# (이름, tagId, 참고용 실측 totalCount) — totalCount 는 로그 비교용일 뿐 코드 동작에 안 씀
COUPLE_TAGS = [
    ("야경_명소",      "ab6c42d4-4168-42dc-b2c5-b5fc0f168808", 150),
    ("커플데이트",      "07e45e70-e2f3-11e8-9488-02001c6b0001", 156),
    ("데이트장소추천",  "064dc4f0-b4b2-11e8-b248-02001c6b0001", 54),
    ("연인·친구",       "ce504b20-2ef9-44f9-84c6-38c518700e55", 42),
    # 범위가 넓어 기본에서 제외. 필요하면 주석 해제.
    # ("연인과함께", "692daa17-b21e-4d91-84b7-80130e0765d6", 2256),
]

# ── 카테고리 (3분류) ─────────────────────────────────────────────────────
# v1.2: 7개 세분류가 너무 잘다는 피드백을 반영해 3개로 통합하고,
# 요청대로 "야경 뷰포인트"를 독립 카테고리로 승격했다.
#
#   1) 야경뷰포인트  — 야경_명소 태그가 붙은 곳 (실측 337건 중 150건)
#   2) 실내데이트    — 음식/쇼핑/체험/문화시설 등 실내 위주 데이트 장소
#   3) 야외데이트    — 자연·공원·역사유적·레저 등 야외 위주 데이트 장소
#
# 판정 순서가 중요하다: 야경 태그가 붙어 있으면 성격과 무관하게 '야경뷰포인트'가
# 우선한다. 야경은 사용자가 명시적으로 원하는 축이고, 실측상 야경 그룹(150건)과
# 데이트 그룹(212건)의 겹침이 25건뿐이라 우선순위를 줘도 데이트 쪽 손실이 적다.
#
# ⚠️ 3분류는 '주된 성격'을 요약한 것이라 정보 손실이 있다. 원본 대분류·중분류
#    (cat1Nm/cat2Nm)는 theme_tags 에 그대로 남겨두므로, 더 잘게 나눠야 할 일이
#    생기면 재수집 없이 theme_tags 만으로 복원할 수 있다.
CATEGORY_NIGHT_VIEW = "야경뷰포인트"
CATEGORY_INDOOR = "실내데이트"
CATEGORY_OUTDOOR = "야외데이트"

# cat1Nm(대분류) → 실내/야외 판정. 실측에 나온 7종을 모두 커버한다.
CAT1_TO_INDOOR_OUTDOOR = {
    "음식":       CATEGORY_INDOOR,   # 카페·식당
    "쇼핑":       CATEGORY_INDOOR,   # 상가·시장·전문매장
    "체험관광":   CATEGORY_INDOOR,   # 기타체험·산업관광 등 실내 비중 높음
    "문화관광":   CATEGORY_INDOOR,   # 랜드마크·테마파크·문화시설
    "자연관광":   CATEGORY_OUTDOOR,  # 하천·해양·자연공원
    "역사관광":   CATEGORY_OUTDOOR,  # 역사유적지·종교성지
    "레저스포츠": CATEGORY_OUTDOOR,  # 육상/수상 레저
}
# 표에 없는 새 대분류가 나오면 야외로 몰지 않고 실내(가장 흔한 값)로 둔다.
CATEGORY_FALLBACK = CATEGORY_INDOOR

NIGHT_VIEW_TAG = "야경_명소"
DATE_TAGS = {"커플데이트", "데이트장소추천", "연인·친구"}

# ── 설정 (config.json 의 visitkorea_collector_settings 섹션에서 덮어쓸 수 있음) ──
DEFAULT_SETTINGS = {
    "request_interval_sec": 0.4,
    "max_retry": 3,
    "backoff_base_sec": 2.0,
    "content_max_chars": 300,
    "list_page_size": 100,   # 실측 확인된 API 상한
    "user_agent": (
        "ABCchallenges-WeekendData-Bot/1.0 "
        "(+internal weekend-data pipeline; contact: set-your-email-here)"
    ),
}

_CFG_PATH = os.path.join(BASE_DIR, "config.json")
try:
    with open(_CFG_PATH, "r", encoding="utf-8") as _f:
        _cfg = json.load(_f)
    SETTINGS = {**DEFAULT_SETTINGS, **_cfg.get("visitkorea_collector_settings", {})}
except Exception:
    SETTINGS = dict(DEFAULT_SETTINGS)

HTTP_HEADERS = {
    "User-Agent": SETTINGS["user_agent"],
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

CSV_FIELDS = [
    "source_site", "category", "place_or_event_name", "period",
    "target_age", "region", "fee_info", "description", "booking_url",
    "ai_tags", "crawled_at", "theme_tags", "congestion_score", "popularity_score",
]


# ─────────────────────────────────────────────────────────────────────────
# 0. 공통 HTTP 유틸 (popup_collector.py 와 동일한 정책)
# ─────────────────────────────────────────────────────────────────────────
def polite_post(data: dict):
    """rate-limit 을 지키며 POST 요청. 실패 시 지수 백오프로 재시도."""
    last_exc = None
    for attempt in range(1, SETTINGS["max_retry"] + 1):
        try:
            time.sleep(SETTINGS["request_interval_sec"] + random.uniform(0, 0.15))
            resp = requests.post(API_URL, headers=HTTP_HEADERS, data=data, timeout=15)
            if resp.status_code == 200:
                return resp
            if resp.status_code in (429, 503):
                wait = SETTINGS["backoff_base_sec"] * attempt
                print(f"  ⚠️  {resp.status_code} 응답 — {wait:.1f}초 대기 후 재시도 ({attempt}/{SETTINGS['max_retry']})")
                time.sleep(wait)
                continue
            return resp
        except requests.RequestException as e:
            last_exc = e
            wait = SETTINGS["backoff_base_sec"] * attempt
            print(f"  ⚠️  요청 실패({e}) — {wait:.1f}초 대기 후 재시도 ({attempt}/{SETTINGS['max_retry']})")
            time.sleep(wait)
    if last_exc:
        raise last_exc
    return None


# ─────────────────────────────────────────────────────────────────────────
# 1. 태그별 목록 조회 (cotId + MODIFIED_DATE + 매칭된 태그명 수집)
# ─────────────────────────────────────────────────────────────────────────
def fetch_tag_list(tag_name: str, tag_id: str):
    """
    한 태그의 전체 목록을 페이지네이션으로 끝까지 순회해 반환.
    반환: [ {cotId, title, addr1, telNo, cat1, cat2, contentType, MODIFIED_DATE, catchPhrase}, ... ]
    """
    items = []
    page = 1
    page_size = SETTINGS["list_page_size"]
    while True:
        resp = polite_post({
            "cmd": "TOUR_CONTENT_LIST_VIEW",
            "month": "All", "areaCode": "All", "sigunguCode": "All",
            "tagId": tag_id, "sortkind": 1,
            "locationx": 0, "locationy": 0,
            "page": page, "cnt": page_size,
            "typeList": "Tour",
            "stampId": "weekend-data-pipeline",
        })
        if resp is None or resp.status_code != 200:
            print(f"  ❌ [{tag_name}] page={page} 조회 실패 (status={getattr(resp,'status_code',None)})")
            break
        try:
            data = resp.json()
        except Exception as e:
            print(f"  ❌ [{tag_name}] page={page} JSON 파싱 실패: {e}")
            break

        body = data.get("body", {})
        result = body.get("result", [])
        if not result:
            break
        items.extend(result)

        total_count = body.get("totalCount", len(items))
        if len(items) >= total_count or len(result) < page_size:
            break
        page += 1

    return items


def collect_all_tag_lists():
    """
    COUPLE_TAGS 전체를 조회해 { cotId: {"lastmod": MODIFIED_DATE, "matched_tags": set(), "list_item": {...}} } 로 합친다.
    같은 장소가 여러 태그에 걸리면 matched_tags 에 전부 모은다.
    """
    merged = {}
    for tag_name, tag_id, expected_cnt in COUPLE_TAGS:
        print(f"  [태그] {tag_name} (예상 {expected_cnt}건 안팎) 조회 중...")
        items = fetch_tag_list(tag_name, tag_id)
        print(f"    → {len(items)}건 수신")
        for item in items:
            cot_id = item.get("cotId")
            if not cot_id:
                continue
            lastmod = item.get("MODIFIED_DATE") or item.get("FINAL_MODIFIED_DATE") or ""
            if cot_id not in merged:
                merged[cot_id] = {"lastmod": lastmod, "matched_tags": set(), "list_item": item}
            merged[cot_id]["matched_tags"].add(tag_name)
            # lastmod 는 더 최근 값으로 갱신(태그별로 응답 시점이 달라 값이 살짝 다를 수 있음에 대비)
            if lastmod > merged[cot_id]["lastmod"]:
                merged[cot_id]["lastmod"] = lastmod
    return merged


# ─────────────────────────────────────────────────────────────────────────
# 2. 상세 조회
# ─────────────────────────────────────────────────────────────────────────
def fetch_detail(cot_id: str):
    resp = polite_post({
        "cmd": "TOUR_CONTENT_BODY_DETAIL",
        "cotId": cot_id, "locationx": 0, "locationy": 0,
        "stampId": "weekend-data-pipeline",
    })
    if resp is None or resp.status_code != 200:
        return None
    try:
        data = resp.json()
    except Exception:
        return None
    detail = data.get("body", {}).get("detail")
    if isinstance(detail, list):
        detail = detail[0] if detail else None
    return detail


# ─────────────────────────────────────────────────────────────────────────
# 3. 캐시
# ─────────────────────────────────────────────────────────────────────────
def load_cache():
    """캐시 구조: { "<cotId>": {"lastmod": "...", "row": {...CSV_FIELDS...}} }"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────────────────────────────────
# 4. 필드 매핑 (VisitKorea 원본 → total_family_data.csv 와 동일한 14컬럼 스키마)
# ─────────────────────────────────────────────────────────────────────────
def strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s or "")


def build_region(detail: dict) -> str:
    addr = detail.get("addr1") or ""
    map_x = detail.get("mapX")  # 경도
    map_y = detail.get("mapY")  # 위도
    if map_y is not None and map_x is not None:
        return f"{addr} | 위도:{map_y}, 경도:{map_x}"
    return addr


def build_description(detail: dict) -> str:
    content = strip_html(detail.get("overView") or "")
    content = re.sub(r"\s+", " ", content).strip()
    limit = SETTINGS["content_max_chars"]
    if len(content) > limit:
        content = content[:limit].rstrip() + "…"
    return content


def build_booking_url(detail: dict, cot_id: str) -> str:
    homepage_html = detail.get("homepage") or ""
    m = re.search(r'href="([^"]+)"', homepage_html)
    if m:
        return m.group(1)
    return f"https://korean.visitkorea.or.kr/detail/ms_detail.do?cotid={cot_id}"


def build_ai_tags(detail: dict, matched_tags: set) -> str:
    weighted = []

    # 원본 tagName (파이프 구분) — 그대로 원자료로 남긴다.
    tag_name_raw = detail.get("tagName") or ""
    for t in tag_name_raw.split("|"):
        t = t.strip()
        if t:
            weighted.append(f"{t}:1.0")

    # 이 항목을 어떤 커플 태그 쿼리로 수집했는지 출처를 남긴다 (2단계 통합기가 활용).
    for mt in sorted(matched_tags):
        weighted.append(f"source_tag_{mt}:1.0")

    # 실측 참여 지표는 정규화하지 않고 원자료로만 남긴다 (정직성 원칙).
    for key, api_key in [("con_like", "conLike"), ("con_read", "conRead"), ("con_share", "conShare")]:
        v = detail.get(api_key)
        if v:
            weighted.append(f"{key}:{v}")

    # period 는 '기간' 개념이 없어 대부분 공란이 된다. 대신 원본이 실제로 갖고
    # 있는 운영시간/휴무일을 여기에 원문 그대로 보존해 정보 유실을 막는다.
    # (';' 와 ':' 가 태그 구분자이므로 값에서 제거해 파싱이 깨지지 않게 한다)
    def _sanitize(v):
        v = strip_html(v or "")
        v = re.sub(r"\s+", " ", v).strip()
        return v.replace(";", " ").replace(":", "시 ")

    use_time = _sanitize(detail.get("useTime"))
    if use_time:
        weighted.append(f"use_time={use_time[:120]}")
    rest_date = _sanitize(detail.get("restDate"))
    if rest_date:
        weighted.append(f"rest_date={rest_date[:60]}")

    return ";".join(weighted)


def build_category(detail: dict, matched_tags: set) -> str:
    """
    3분류 판정. 야경 태그가 붙어 있으면 성격과 무관하게 '야경뷰포인트'가 우선한다.
    그 외에는 원본 대분류(cat1Nm)로 실내/야외 데이트를 가른다.
    """
    if NIGHT_VIEW_TAG in matched_tags:
        return CATEGORY_NIGHT_VIEW

    cat1_nm = (detail.get("cat1Nm") or "").strip()
    return CAT1_TO_INDOOR_OUTDOOR.get(cat1_nm, CATEGORY_FALLBACK)


def build_period(detail: dict) -> str:
    """
    이 API 에는 팝업과 달리 '행사 기간(개막~폐막)' 개념이 아예 없다.
    있는 것은 운영시간(useTime)과 휴무일(restDate)뿐이다.
    v1.0 은 여기에 "상시"를 무조건 박아넣었는데, 실측해 보면 대부분 장소가
    "하절기 08:00~21:00" 처럼 계절/시간대별 운영시간을 갖고 있어(80건 샘플 중
    useTime 이 비어있는 건 9건뿐) '상시'는 사실과 다른 플레이스홀더였다.

    → 기간 개념이 없는 데이터에 가짜 기간을 넣지 않는다. always_yn == 'Y'
      (원본이 명시적으로 '상시'라고 표기한 경우)일 때만 "상시"를 쓰고,
      그 외에는 공란으로 둔다. 운영시간/휴무일 정보는 버리지 않고
      ai_tags 의 use_time / rest_date 로 원문을 보존한다.
    """
    if (detail.get("always_yn") or "").upper() == "Y":
        return "상시"
    return ""


def build_theme_tags(detail: dict, matched_tags: set) -> str:
    tags = []
    if detail.get("cat1Nm"):
        tags.append(f"{detail['cat1Nm']}:1.0")
    if detail.get("cat2Nm"):
        tags.append(f"{detail['cat2Nm']}:1.0")

    # 야경 / 데이트는 서로 독립적인 축이므로 각각 별도 태그로 남긴다.
    if NIGHT_VIEW_TAG in matched_tags:
        tags.append("night_view:1.0")
    if matched_tags & DATE_TAGS:
        tags.append("date_spot:1.0")

    tags.append("tour_spot:1.0")
    return ";".join(tags)


def detail_to_row(detail: dict, matched_tags: set, crawled_at: str) -> dict:
    return {
        "source_site":         "대한민국 구석구석(VisitKorea) | 커플/데이트 태그",
        "category":            build_category(detail, matched_tags),
        "place_or_event_name": detail.get("title") or "",
        "period":              build_period(detail),  # 기간 개념 없음 — 대개 공란. 운영시간은 ai_tags 참고
        "target_age":          "전연령",  # 원본에 연령 제한 필드 없음 — 임의 추정하지 않고 기본값
        "region":              build_region(detail),
        "fee_info":            "",  # 원본에 요금 필드 없음 — 추측해서 채우지 않는다.
        "description":         build_description(detail),
        "booking_url":         build_booking_url(detail, detail.get("cotId", "")),
        "ai_tags":             build_ai_tags(detail, matched_tags),
        "crawled_at":          crawled_at,
        "theme_tags":          build_theme_tags(detail, matched_tags),
        "congestion_score":    "",  # 실측 없음 — 공란 유지
        "popularity_score":    "",  # 실측/정규화 근거 없음 — 공란 유지 (원자료는 ai_tags 의 con_* 참고)
    }


# ─────────────────────────────────────────────────────────────────────────
# 5. 메인 파이프라인
# ─────────────────────────────────────────────────────────────────────────
def collect():
    print("=" * 75)
    print("대한민국 구석구석(VisitKorea) 커플/데이트 태그 수집기 시작")
    print("=" * 75)

    os.makedirs(DATA_DIR, exist_ok=True)
    cache = load_cache()

    print("\n[1/3] 태그별 목록 조회 (전체 페이지 순회, cotId + 변경시각 확보) ...")
    merged = collect_all_tag_lists()
    print(f"  → 중복 제거 후 총 {len(merged)}개 장소(cotId) 확인")

    if not merged:
        print("❌ 장소를 하나도 얻지 못했습니다. API 구조가 바뀌었을 수 있습니다. 중단합니다.")
        return

    # 목록의 lastmod(MODIFIED_DATE) 를 캐시와 먼저 비교해 걸러낸다.
    # (상세 요청 전에 걸러야 실제로 요청 수가 줄어든다 — popup_collector.py 와 동일 원칙)
    to_fetch = []
    reused_rows = []
    for cot_id, info in merged.items():
        cached = cache.get(cot_id)
        if cached and isinstance(cached, dict) and cached.get("lastmod") == info["lastmod"] and cached.get("row"):
            reused_rows.append(cached["row"])
        else:
            to_fetch.append(cot_id)

    print(f"  → 캐시와 변경시각 동일(스킵 대상): {len(reused_rows)}건")
    print(f"  → 신규/갱신(실제 상세 요청 대상): {len(to_fetch)}건")

    print("\n[2/3] 상세정보 수집 (신규/갱신분만 실제 요청) ...")
    rows = list(reused_rows)
    new_or_updated = 0
    failed_ids = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for i, cot_id in enumerate(to_fetch, start=1):
        detail = fetch_detail(cot_id)
        if detail is None:
            print(f"  ❌ [{i}/{len(to_fetch)}] cotId={cot_id} 상세 조회/파싱 실패")
            failed_ids.append(cot_id)
            continue

        matched_tags = merged[cot_id]["matched_tags"]
        row = detail_to_row(detail, matched_tags, now_str)
        rows.append(row)
        new_or_updated += 1
        cache[cot_id] = {"lastmod": merged[cot_id]["lastmod"], "row": row}

        if i % 50 == 0 or i == len(to_fetch):
            print(f"  [진행] {i}/{len(to_fetch)}건 요청 완료 (신규/갱신 {new_or_updated}, 실패 {len(failed_ids)})")
            save_cache(cache)  # 중간 저장 — 중단돼도 지금까지 캐시는 남는다.

    save_cache(cache)
    skipped_cached = len(reused_rows)

    print(f"\n[3/3] CSV 저장 중... ({len(rows)}건)")
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print("=" * 75)
    print(f"✅ 저장 완료: {OUTPUT_CSV}")
    print(f"   총 {len(rows)}건 (신규/갱신 {new_or_updated}건, 캐시 재사용 {skipped_cached}건, 실패 {len(failed_ids)}건)")
    if failed_ids:
        print(f"   ⚠️ 실패한 cotId 목록(최대 20개 표시): {failed_ids[:20]}")
    print("=" * 75)


if __name__ == "__main__":
    collect()
