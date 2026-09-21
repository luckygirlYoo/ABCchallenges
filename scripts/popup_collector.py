"""
팝가(Popga, popga.co.kr) 팝업스토어 원천 수집기 v1.2
=============================================================================
[커플 테마 파이프라인 1단계: 원천 데이터 수집]

⚠️ 이 스크립트는 어떤 경우에도 git add / commit / push 를 실행하지 않는다.
   파일 생성·수정까지만 하고 멈춘다. 커밋 여부는 사람이 직접 결정한다.

v1.2 변경사항 (실행 결과 리뷰 반영)
-----------------------------------------------------------------------------
1. couple_signal 이진 플래그(70건/2842건, 커버리지 지나치게 좁음) →
   STRONG/SOFT 2단계 가중치 점수(couple_score)로 교체. 팝업 도메인에서는
   "데이트/커플/연인" 같은 직접 단어보다 전시·포토존·감성카페류가 실제
   커플 수요와 더 크게 겹치는데, 이진 키워드 매칭으로는 그걸 못 잡았음.
   ⚠️ 이 키워드 세트도 1차 추정치이며 generate_total_couple_data.py 설계
   시 실측 데이터로 재검토가 필요함(하단 STRONG/SOFT 목록 주석 참고).
2. region 의 주소 앞머리를 정규화(서울특별시→서울 등). 실측 200건 샘플에서
   같은 "서울"이 "서울"/"서울특별시" 두 문자열로 나뉘어 집계되는 문제 확인.
3. place_or_event_name 끝에 붙는 "@지역"/" - 지역" 접미사를 제거하되,
   지역명 화이트리스트에 없는 단어(예: "- 빵빵랜드" 같은 서브타이틀)는
   절대 지우지 않음 — 실측으로 지역이 아닌 dash 접미사 사례를 확인했음.

무엇을 하는가
-----------------------------------------------------------------------------
1. https://popga.co.kr/sitemap.xml → 하위 sitemap 들을 순회해
   /popup/{id} 상세페이지 URL과 각 URL의 <lastmod> 를 함께 얻는다
   (현재 약 2,800여건).
2. sitemap 의 lastmod 를 캐시(data/popup_collect_cache.json)와 먼저 비교한다.
   같으면 그 항목은 **상세페이지를 아예 요청하지 않고** 캐시에 저장해둔
   행(row)을 그대로 재사용한다. 다르거나 캐시에 없는 항목만 실제로 요청한다.
3. 실제로 요청하는 상세페이지는 requests 로 그냥 GET 한다 (로그인/인증/
   API 키 불필요). 이 사이트는 Next.js SSR 이라 상세 데이터(JSON)가 HTML
   응답 안에 그대로 포함되어 있다 (self.__next_f.push(...) 스트리밍
   페이로드 안). → 브라우저 자동화(Playwright/Selenium) 없이 순수 HTTP
   요청만으로 수집 가능.
4. total_family_data.csv 와 동일한 14개 컬럼 스키마로
   data/popup_couple_events_raw.csv 에 저장한다.

무엇을 하지 않는가 (중요)
-----------------------------------------------------------------------------
- 팝업을 "커플용/비커플용"으로 걸러내지 않는다. 전부 수집하고,
  ai_tags 에 couple_signal:1.0 같은 신호만 덧붙인다. 최종 커플 테마
  포함 여부 판단은 이후 별도 작성될 generate_total_couple_data.py 가 한다.
- fee_info, congestion_score, popularity_score 처럼 원본에 실측값이
  없는 필드는 절대 임의의 값(랜덤/추측)으로 채우지 않는다. 공란으로 둔다.
  (과거 이 프로젝트가 congestion_score 를 randint 로 채웠다가
   enrich_total_family_data.py 에서 걷어낸 전례가 있음 — 반복하지 말 것)
- 동시 다발 요청(멀티스레드/비동기)을 쓰지 않는다. 요청 사이 sleep 을 둔다.
- content(설명 원문)를 대량으로 그대로 복제 저장하지 않는다(길이 제한).

담당자가 실행 전 확인할 것
-----------------------------------------------------------------------------
- popga.co.kr 이용약관상 이런 형태의 자동 수집·내부 서비스 활용이
  문제되지 않는지 사람이 한 번은 직접 확인할 것 (코드가 대신 판단하지 않음).
- config.json 에 popup_collector_settings 섹션이 없으면 DEFAULT_SETTINGS 로
  동작한다. 필요시 config.json.example 을 참고해 옵션을 추가할 것
  (config.json 자체는 커밋하지 않는다).
"""
import sys, io, os, re, csv, json, time, random
from datetime import datetime
from urllib.parse import urljoin
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")
OUTPUT_CSV = os.path.join(DATA_DIR, "popup_couple_events_raw.csv")
CACHE_FILE = os.path.join(DATA_DIR, "popup_collect_cache.json")

# ── 캐시 스키마 버전 ─────────────────────────────────────────────────────
# 캐시가 원본 스냅샷이 아니라 '가공된 결과(row)'를 담고 있기 때문에, 매핑/파싱
# 로직을 고쳐도 과거에 생성된 row 에는 소급되지 않는다. 실제로 v1.2 의 ai_tags
# 콜론 버그(태그명에 ':' 가 있으면 가중치가 안 붙던 문제)를 고쳤을 때, 이미
# 캐시에 박혀 있던 25건(AMPLE:N 팝업, ONF:MY SELF, 승리의 여신:니케,
# 붕괴: 스타레일 전시 등)은 sitemap lastmod 가 안 바뀌어 재요청 대상이 아니라
# 버그가 있는 채로 계속 CSV 로 나갔다.
#
# → 두 종류의 버전을 따로 둔다.
#
#   ROW_SCHEMA_VERSION : row 를 만드는 매핑/파싱 로직의 버전.
#       올리면 캐시에 저장된 원본 spot 으로 row 만 다시 만든다.
#       ⚡ 네트워크 요청 없음(로컬 재생성). 로직만 고쳤을 때 쓴다.
#
#   FETCH_SCHEMA_VERSION : 무엇을 어떻게 '가져오는지'의 버전.
#       올리면 원본 spot 자체를 못 믿는다는 뜻이므로 전량 재요청한다.
#       수집 대상/원본 필드 구성이 바뀌었을 때만 올린다.
#
# 규칙: 매핑 함수(build_*/clean_title/compute_couple_score 등)를 고치면
#       ROW_SCHEMA_VERSION 을 반드시 올릴 것.
ROW_SCHEMA_VERSION = 3      # v3: ai_tags 콜론 가중치 수정 + 카테고리 기반 신호
FETCH_SCHEMA_VERSION = 1    # v1: sitemap + 상세페이지 SSR JSON 전체 저장

SITE_ROOT = "https://popga.co.kr"
SITEMAP_INDEX = f"{SITE_ROOT}/sitemap.xml"

# 이번 실행을 식별하는 값. lastmod 가 없는 항목이 영구 캐시히트되는 것을 막는
# 센티널로 쓴다(매 실행 값이 달라져 캐시 비교가 항상 불일치 → 항상 재요청).
RUN_ID = datetime.now().strftime("%Y%m%d%H%M%S")

# ── 설정 (config.json 의 popup_collector_settings 섹션에서 덮어쓸 수 있음) ──
DEFAULT_SETTINGS = {
    "request_interval_sec": 0.4,   # 요청 사이 최소 대기 (부하 최소화)
    "max_retry": 3,                # 실패 시 재시도 횟수
    "backoff_base_sec": 2.0,       # 재시도 시 대기(지수 백오프 기본값)
    "content_max_chars": 300,      # description 저장 시 원문 길이 제한(저작권 유의)
    "user_agent": (
        "ABCchallenges-WeekendData-Bot/1.0 "
        "(+internal weekend-data pipeline; contact: set-your-email-here)"
    ),
}

_CFG_PATH = os.path.join(BASE_DIR, "config.json")
try:
    with open(_CFG_PATH, "r", encoding="utf-8") as _f:
        _cfg = json.load(_f)
    SETTINGS = {**DEFAULT_SETTINGS, **_cfg.get("popup_collector_settings", {})}
except Exception:
    # config.json 이 없거나 섹션이 없어도 기본값으로 정상 동작해야 한다.
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

# ── 커플·데이트 연관성 신호 ─────────────────────────────────────────────
# v1.3: 키워드 매칭만으로는 팝업 도메인을 못 잡는다는 게 실측으로 확인됐다.
#   - 12개 키워드 중 4개(프로포즈/허니문/커플룩/커플이벤트)는 적중 0건.
#     팝업 업계가 그런 어휘를 애초에 쓰지 않는다.
#   - "2인"은 "2인분/2인용/작가 2인전"에도 걸려 오탐이 잦아 제거했다.
# 반면 원본 categories[].name 은 신호가 훨씬 풍부하고 안정적이다
# (250건 샘플: 패션 80, 애니/캐릭터 52, F&B 37, 실내 팝업 36,
#  카페/디저트/베이커리 24, 뷰티 22 ...).
# → 카테고리 기반 신호를 주 신호로 쓰고, 키워드는 보조로만 쓴다.
#
# ⚠️ 이 가중치는 1차 추정치다. generate_total_couple_data.py 설계 시
#    실제 결과 CSV 를 놓고 재검토가 필요하다.

# 직접적 어휘 — 실측 적중이 있는 것만 남김
STRONG_COUPLE_KEYWORDS = [
    "데이트", "커플", "연인", "기념일", "웨딩", "발렌타인", "화이트데이",
    # 제거됨(적중 0건): 프로포즈, 허니문, 커플룩, 커플이벤트
    # 제거됨(오탐): "2인" — "2인분/2인용", "작가 2인전" 등에 걸림
]
# 간접적 어휘 (분위기·체험 성격)
SOFT_COUPLE_KEYWORDS = [
    "포토존", "감성", "무드", "야경", "루프탑", "인생샷", "플라워", "캔들",
]
# 원본 카테고리 기반 신호 — 커플/데이트 수요와 실제로 맞물리는 카테고리.
# 카테고리는 사이트가 직접 분류해 붙인 값이라 자유 텍스트 키워드보다 안정적이다.
CATEGORY_COUPLE_WEIGHTS = {
    "카페/디저트/베이커리": 0.6,
    "F&B": 0.4,
    "식사/레스토랑": 0.5,
    "주류": 0.5,
    "실내 팝업": 0.3,      # 날씨 무관 데이트 가능
    "전시": 0.5,
    "예술/미술": 0.5,
    "일러스트/디자인": 0.4,
    "문구/아트": 0.3,
    "주얼리/시계": 0.5,
    "향수": 0.4,
    "뷰티": 0.2,
    "리빙/인테리어": 0.2,
    "애니/캐릭터": 0.2,    # 동반 관람 수요
    "엔터테인먼트": 0.3,
    "여행/취미/여가": 0.3,
}
STRONG_WEIGHT = 1.0
SOFT_WEIGHT = 0.3

# 가족 동반 성격이 강해 커플 테마와 상충하는 카테고리 (감점 아닌 '표시'용)
FAMILY_ORIENTED_CATEGORIES = {"키즈/반려동물", "패밀리/키즈"}

# ── title 접미사 정리용 지역명 화이트리스트 ─────────────────────────────
# "OO 팝업 @성수", "OO 팝업 - 대구" 처럼 제목 끝에 지역명이 붙는 경우가
# 있는 반면, "OO 팝업 - 빵빵랜드", "OO 팝업 - 퇴사게임천국" 처럼 지역이
# 아니라 팝업 자체의 서브타이틀/테마명이 " - " 뒤에 붙는 경우도 실측으로
# 확인됐다(둘 다 같은 " - X" 패턴이라 문자열 위치만으로는 구분 불가).
# → 뒤에 오는 단어가 아래 화이트리스트에 있을 때만 "지역 접미사"로 보고
#   제거한다. 목록에 없는 단어는 절대 추측해서 지우지 않는다(안전 기본값).
LOCATION_SUFFIX_WHITELIST = {
    # 광역시도
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
    "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
    # 서울/수도권 팝업 핫플레이스 상권명
    "홍대", "강남", "성수", "잠실", "여의도", "명동", "이태원", "신촌",
    "종로", "압구정", "청담", "한남", "서울숲", "합정", "연남", "망원",
    "을지로", "동대문", "신사", "가로수길", "코엑스", "건대", "왕십리",
    "광화문", "잠실새내", "성수동", "홍대/신촌",
    # 경기/기타 주요 도시
    "수원", "고양", "판교", "하남", "분당", "일산", "안산", "부천",
    "성남", "용인", "평택", "화성", "인천공항",
}

# ── 주소 앞머리 정규화 (정식 행정명 → 프로젝트 표준 약칭) ───────────────
# 원본 데이터가 "서울특별시"/"서울" 을 섞어서 준다(실측: 200건 샘플 중
# 서울 165건, 서울특별시 4건 — 같은 지역인데 다른 문자열로 집계됨).
# 기존 프로젝트(place_search_collector.py 등)가 써온 약칭으로 통일한다.
ADDRESS_PREFIX_NORMALIZE = {
    "서울특별시": "서울",
    "부산광역시": "부산",
    "대구광역시": "대구",
    "인천광역시": "인천",
    "광주광역시": "광주",
    "대전광역시": "대전",
    "울산광역시": "울산",
    "세종특별자치시": "세종",
    "경기도": "경기",
    "강원특별자치도": "강원",
    "강원도": "강원",
    "충청북도": "충북",
    "충청남도": "충남",
    "전북특별자치도": "전북",
    "전라북도": "전북",
    "전라남도": "전남",
    "경상북도": "경북",
    "경상남도": "경남",
    "제주특별자치도": "제주",
    "제주도": "제주",
}


# ─────────────────────────────────────────────────────────────────────────
# 0. 공통 HTTP 유틸 (재시도 + 백오프 + rate limit)
# ─────────────────────────────────────────────────────────────────────────
def polite_get(url, **kwargs):
    """rate-limit 을 지키며 GET 요청. 실패 시 지수 백오프로 재시도."""
    last_exc = None
    for attempt in range(1, SETTINGS["max_retry"] + 1):
        try:
            time.sleep(SETTINGS["request_interval_sec"] + random.uniform(0, 0.15))
            resp = requests.get(url, headers=HTTP_HEADERS, timeout=15, **kwargs)
            if resp.status_code == 200:
                return resp
            if resp.status_code in (429, 503):
                wait = SETTINGS["backoff_base_sec"] * attempt
                print(f"  ⚠️  {resp.status_code} 응답 — {wait:.1f}초 대기 후 재시도 ({attempt}/{SETTINGS['max_retry']})")
                time.sleep(wait)
                continue
            # 403/404 등은 재시도해도 의미 없는 경우가 많으므로 바로 반환
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
# 1. sitemap 순회 → 전체 popup id 목록
# ─────────────────────────────────────────────────────────────────────────
def get_all_popup_ids():
    """
    sitemap.xml (인덱스) → 하위 sitemap N개를 순회해 /popup/{id} → lastmod 맵을 얻는다.

    ⚠️ 캐시 스킵 판단을 "상세페이지를 받아본 뒤"가 아니라 "받기 전"에 할 수 있어야
    실제로 요청 수가 줄어든다. sitemap 의 <lastmod> 는 실측으로 상세페이지의
    lastUpdatedAt(KST) 을 UTC 로 바꾼 값과 정확히 일치한다
    (예: lastUpdatedAt '2026-08-26 21:54:48' KST == lastmod '2026-08-26T12:54:48.000Z').
    그래서 상세페이지를 열지 않고도 sitemap 만으로 "바뀐 항목"을 골라낼 수 있다.

    반환: { popup_id(int): lastmod(str) }
    """
    id_to_lastmod = {}
    resp = polite_get(SITEMAP_INDEX)
    if resp is None or resp.status_code != 200:
        print(f"❌ sitemap 인덱스 조회 실패: status={getattr(resp, 'status_code', None)}")
        return {}

    sub_sitemaps = re.findall(r"<loc>(https://popga\.co\.kr/sitemap/\d+\.xml)</loc>", resp.text)
    print(f"  하위 sitemap {len(sub_sitemaps)}개 발견")

    for sm_url in sub_sitemaps:
        sm_resp = polite_get(sm_url)
        if sm_resp is None or sm_resp.status_code != 200:
            print(f"  ⚠️  {sm_url} 조회 실패, 건너뜀")
            continue
        # <url><loc>.../popup/{id}</loc><lastmod>...</lastmod>...</url> 블록 단위로 파싱.
        # /popup/{id}/review/... , /popup/{id}/shop/... 은 상세 페이지가 아니라
        # 리뷰/굿즈 하위 페이지라 스키마가 다르므로 제외한다 (별도 수집기 대상).
        for block in re.findall(r"<url>.*?</url>", sm_resp.text, re.DOTALL):
            m_loc = re.search(r"<loc>https://popga\.co\.kr/popup/(\d+)</loc>", block)
            if not m_loc:
                continue
            m_lastmod = re.search(r"<lastmod>([^<]+)</lastmod>", block)
            popup_id = int(m_loc.group(1))
            # ⚠️ lastmod 가 없으면 빈 문자열로 두면 안 된다. 캐시에 ""로 저장되고
            #    다음 실행에서 "" == "" 로 항상 캐시 히트가 되어 그 항목은 두 번
            #    다시 상세페이지를 안 보게 된다(영구 스킵).
            #    현재 popga sitemap 은 전 건 lastmod 를 주지만(실측 2,846건 중
            #    누락 0건), 사이트가 바뀔 수 있으므로 방어한다.
            #    → 센티널을 넣어 매 실행 값이 달라지게 만들어 항상 재요청되게 한다.
            lastmod = m_lastmod.group(1) if m_lastmod else f"__NO_LASTMOD__{RUN_ID}"
            id_to_lastmod[popup_id] = lastmod

    return id_to_lastmod


# ─────────────────────────────────────────────────────────────────────────
# 2. 상세페이지 HTML → 임베드된 spot JSON 파싱
# ─────────────────────────────────────────────────────────────────────────
def _extract_next_f_payload(html: str) -> str:
    """
    Next.js RSC 스트리밍 페이로드( self.__next_f.push([1,"...이스케이프된 문자열..."]) )
    조각들을 모두 이어붙여 하나의 (이스케이프가 풀린) 텍스트로 반환한다.
    """
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)\s*(?:</script>|$)', html, re.DOTALL)
    joined = "".join(chunks)
    try:
        # 이 문자열 자체가 JS 문자열 리터럴의 내용물이므로, 파이썬 json 파서로
        # 큰따옴표로 감싸 디코딩하면 \", \r\n, \uXXXX 등 이스케이프가 정확히 풀린다.
        return json.loads(f'"{joined}"')
    except Exception:
        # 파싱이 안 되면 최소한의 수동 언이스케이프로 폴백
        return joined.replace('\\"', '"')


def _extract_balanced_object(text: str, obj_start: int):
    """text[obj_start] 가 '{' 라고 가정하고, 중괄호 균형을 맞춰 대응하는 '}' 까지 잘라 반환."""
    depth = 0
    in_str = False
    esc = False
    i = obj_start
    while i < len(text):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return text[obj_start:i + 1]
        i += 1
    return None


def parse_spot_detail(html: str, spot_id: int):
    """
    상세페이지 HTML → 팝업 상세 dict.
    실측 확인된 마커: '"data":{"id":<spot_id>,...}' 형태로 정확히 한 번 등장한다.
    이 마커를 못 찾으면(레이아웃이 바뀌었거나 없는 id) None 을 반환한다.
    """
    payload = _extract_next_f_payload(html)
    marker = f'"data":{{"id":{spot_id},'
    marker_idx = payload.find(marker)
    if marker_idx == -1:
        return None
    obj_start = marker_idx + len('"data":')  # marker_idx 는 "data": 의 " 위치
    raw_obj = _extract_balanced_object(payload, obj_start)
    if raw_obj is None:
        return None
    try:
        return json.loads(raw_obj)
    except json.JSONDecodeError as e:
        print(f"  ⚠️  spot {spot_id} JSON 파싱 실패: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────
# 3. 캐시 (lastUpdatedAt 기반 증분 수집)
# ─────────────────────────────────────────────────────────────────────────
def _slim_spot(spot: dict) -> dict:
    """
    캐시에 저장할 원본 spot 을 '매핑에 실제로 쓰이는 필드'로만 줄인다.
    전체 spot 은 약 2.8KB 인데 그중 절반 가까이가 이미지 파일 목록
    (files/relatedSpotFiles)이라 row 생성에 전혀 쓰이지 않는다.
    2,846건 기준 약 8MB → 약 2MB 로 줄어든다.

    ⚠️ 매핑 함수에서 새로운 spot 필드를 쓰기 시작하면 여기에도 추가하고
       ROW_SCHEMA_VERSION 을 올려야 한다. (없으면 재생성 시 값이 비어버림)
    """
    keep = (
        "id", "title", "subTitle", "content", "categories", "tags",
        "openDate", "closeDate", "latitude", "longitude",
        "address", "roadAddress", "website",
        "ageRestrictionType", "ageRestrictionMinAge", "recentPickCount",
    )
    return {k: spot.get(k) for k in keep if k in spot}


def _with_verified_at(ai_tags: str, now_str: str) -> str:
    """
    ai_tags 에 verified_at=<시각> 을 넣거나 갱신한다.
    crawled_at(실제 페이지를 받아온 시각)은 건드리지 않고, '이번 실행에서 여전히
    유효함을 확인한 시각'을 따로 기록해 다운스트림 신선도 필터가 캐시 재사용
    행을 부당하게 탈락시키지 않도록 한다.
    """
    parts = [p for p in (ai_tags or "").split(";") if p and not p.startswith("verified_at=")]
    parts.append(f"verified_at={now_str}")
    return ";".join(parts)


def load_cache():
    """
    캐시 구조: { "<popup_id>": {"lastmod": "<sitemap lastmod>", "row": {...CSV_FIELDS...}} }
    lastmod 가 sitemap 최신값과 같으면 상세페이지를 다시 요청하지 않고
    캐시에 저장해둔 row 를 그대로 재사용한다 (= 실제로 요청 수가 줄어든다).
    """
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
# 4. 필드 매핑 (popga 원본 → total_family_data.csv 와 동일한 14컬럼 스키마)
# ─────────────────────────────────────────────────────────────────────────
def compute_couple_score(spot: dict):
    """
    (couple_score, strong_hits, soft_hits, cat_hits) 반환.
    - strong 키워드 1개당 1.0점, soft 키워드 1개당 0.3점
    - 원본 카테고리는 CATEGORY_COUPLE_WEIGHTS 의 개별 가중치만큼 가산
    실측값이 아니라 텍스트/카테고리 매칭으로 계산한 파생 신호다.
    """
    haystack = " ".join([
        spot.get("title") or "",
        spot.get("subTitle") or "",
        spot.get("content") or "",
        " ".join(spot.get("tags") or []),
    ])
    strong_hits = [kw for kw in STRONG_COUPLE_KEYWORDS if kw in haystack]
    soft_hits = [kw for kw in SOFT_COUPLE_KEYWORDS if kw in haystack]

    cat_names = [c.get("name", "") for c in (spot.get("categories") or [])]
    cat_hits = [c for c in cat_names if c in CATEGORY_COUPLE_WEIGHTS]

    score = (
        len(strong_hits) * STRONG_WEIGHT
        + len(soft_hits) * SOFT_WEIGHT
        + sum(CATEGORY_COUPLE_WEIGHTS[c] for c in cat_hits)
    )
    return round(score, 2), strong_hits, soft_hits, cat_hits


def build_target_age(spot: dict) -> str:
    restriction = spot.get("ageRestrictionType")
    min_age = spot.get("ageRestrictionMinAge")
    if restriction == "ALL" or restriction is None:
        return "전연령"
    if min_age:
        return f"{min_age}세 이상"
    return str(restriction)


def normalize_address(addr: str) -> str:
    """주소 맨 앞 행정명을 프로젝트 표준 약칭으로 통일 (예: 서울특별시 → 서울)."""
    if not addr:
        return addr
    parts = addr.split(" ", 1)
    head = parts[0]
    rest = parts[1] if len(parts) > 1 else ""
    normalized_head = ADDRESS_PREFIX_NORMALIZE.get(head, head)
    return f"{normalized_head} {rest}".strip() if rest else normalized_head


def build_region(spot: dict) -> str:
    addr = spot.get("roadAddress") or spot.get("address") or ""
    addr = normalize_address(addr)
    lat = spot.get("latitude")
    lng = spot.get("longitude")
    if lat is not None and lng is not None:
        return f"{addr} | 위도:{lat}, 경도:{lng}"
    return addr


def build_description(spot: dict) -> str:
    content = (spot.get("content") or "").strip()
    content = re.sub(r"\s+", " ", content)
    limit = SETTINGS["content_max_chars"]
    if len(content) > limit:
        content = content[:limit].rstrip() + "…"
    return content


def build_ai_tags(spot: dict) -> str:
    weighted = []

    # 원본 태그는 항상 ':1.0' 을 덧붙인다.
    # ⚠️ v1.2 까지는 `f"{t}:1.0" if ":" not in t else t` 였는데, 태그 이름 자체에
    #    콜론이 있는 경우(실측: 'Re:제로부터 시작하는 이세계 생활',
    #    '승리의 여신:니케', '붕괴: 스타레일 전시', 'ONF:MY SELF' 등 26종)
    #    가중치가 안 붙어, 다운스트림이 rsplit(':',1) 로 파싱하면 태그명이
    #    'Re' 로 잘리고 가중치가 '제로부터...' 가 되는 조용한 오류가 났다.
    #    → 콜론 유무와 무관하게 항상 ':1.0' 을 붙인다.
    #    → 파싱하는 쪽은 반드시 rsplit(':', 1) 을 쓸 것 (split 아님).
    for t in (spot.get("tags") or []):
        t = str(t).strip()
        if t:
            weighted.append(f"{t}:1.0")

    score, strong_hits, soft_hits, cat_hits = compute_couple_score(spot)
    if score > 0:
        weighted.append(f"couple_score:{score}")
    if strong_hits:
        weighted.append("couple_signal_strong:1.0")
    elif soft_hits or cat_hits:
        weighted.append("couple_signal_soft:1.0")

    cat_names = [c.get("name", "") for c in (spot.get("categories") or [])]
    if any(c in FAMILY_ORIENTED_CATEGORIES for c in cat_names):
        # 커플 테마와 상충할 수 있음을 표시만 한다(여기서 제외하지 않음).
        weighted.append("family_oriented:1.0")

    restriction = spot.get("ageRestrictionType")
    if restriction and restriction != "ALL":
        weighted.append("adult_only:1.0")

    pick_count = spot.get("recentPickCount")
    if pick_count:
        # 정규화된 인기도 점수가 아니라 "원자료"로만 남긴다 (정직성 원칙).
        weighted.append(f"pick_count:{pick_count}")

    return ";".join(weighted)


def build_theme_tags(spot: dict) -> str:
    cat_names = [c.get("name", "") for c in (spot.get("categories") or [])]
    tags = [f"{name}:1.0" for name in cat_names if name]
    tags.append("popup:1.0")
    return ";".join(tags)


def clean_title(title: str) -> str:
    """
    제목 끝에 붙은 '@지역' 또는 ' - 지역' 접미사를 지역명일 때만 제거한다.
    '팝업 - 빵빵랜드'처럼 지역이 아닌 서브타이틀/테마명은 절대 건드리지 않는다
    (LOCATION_SUFFIX_WHITELIST 에 없는 단어는 그대로 둔다 — 안전 기본값).
    """
    if not title:
        return title

    m = re.search(r"^(.*?)\s*@\s*(\S+)\s*$", title)
    if m and m.group(2) in LOCATION_SUFFIX_WHITELIST:
        return m.group(1).strip()

    m = re.search(r"^(.*?)\s-\s(\S+)\s*$", title)
    if m and m.group(2) in LOCATION_SUFFIX_WHITELIST:
        return m.group(1).strip()

    return title.strip()


def build_period(spot: dict) -> str:
    open_d = spot.get("openDate") or ""
    close_d = spot.get("closeDate") or ""
    if open_d and close_d:
        return f"{open_d} ~ {close_d}"
    return open_d or close_d or ""


def build_booking_url(spot: dict) -> str:
    website = spot.get("website") or {}
    if website.get("instagram"):
        return website["instagram"]
    return f"{SITE_ROOT}/popup/{spot.get('id')}"


def spot_to_row(spot: dict, crawled_at: str) -> dict:
    return {
        "source_site":         "팝가(Popga) | 팝업스토어",
        "category":            "팝업스토어",
        "place_or_event_name": clean_title(spot.get("title") or ""),
        "period":              build_period(spot),
        "target_age":          build_target_age(spot),
        "region":              build_region(spot),
        "fee_info":            "",  # 원본에 가격 필드 없음 — 추측해서 채우지 않는다.
        "description":         build_description(spot),
        "booking_url":         build_booking_url(spot),
        "ai_tags":             build_ai_tags(spot),
        "crawled_at":          crawled_at,
        "theme_tags":          build_theme_tags(spot),
        "congestion_score":    "",  # 실측 없음 — 공란 유지
        "popularity_score":    "",  # 실측/정규화 근거 없음 — 공란 유지 (원자료는 ai_tags 의 pick_count 참고)
    }


# ─────────────────────────────────────────────────────────────────────────
# 5. 메인 파이프라인
# ─────────────────────────────────────────────────────────────────────────
def collect():
    print("=" * 75)
    print("팝가(Popga) 팝업스토어 원천 수집기 시작")
    print("=" * 75)

    os.makedirs(DATA_DIR, exist_ok=True)
    cache = load_cache()

    print("\n[1/3] sitemap.xml 에서 전체 popup id + lastmod 수집 중...")
    id_to_lastmod = get_all_popup_ids()
    print(f"  → 총 {len(id_to_lastmod)}개 popup id 확인")

    if not id_to_lastmod:
        print("❌ popup id 를 하나도 얻지 못했습니다. sitemap 구조가 바뀌었을 수 있습니다. 중단합니다.")
        return

    # sitemap 의 lastmod 를 캐시와 먼저 비교해, "바뀌지 않은 항목"은 이 시점에
    # 걸러낸다. 상세페이지를 받아본 뒤에 비교하면 요청 수가 전혀 줄지 않으므로
    # (이전 버전의 문제) 반드시 요청 이전에 걸러야 한다.
    #
    # 판정은 3단계다:
    #   (a) 그대로 재사용   : lastmod 동일 + 두 스키마 버전 모두 일치
    #   (b) 로컬 row 재생성 : lastmod 동일 + row 로직만 구버전인데 원본 spot 이 있음
    #                        → 네트워크 요청 없이 spot_to_row() 만 다시 돌린다
    #   (c) 실제 재요청     : 그 외 전부 (신규/변경/원본 없음/fetch 스키마 변경)
    to_fetch = []
    reused_rows = []
    regenerated = 0
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for spot_id, lastmod in id_to_lastmod.items():
        cached = cache.get(str(spot_id))

        # 구버전 캐시는 값이 그냥 문자열이었다(딕셔너리가 아님).
        # 에러 내지 말고 "캐시 없음"으로 취급해 새로 요청한다.
        if not (cached and isinstance(cached, dict)):
            to_fetch.append(spot_id)
            continue

        if cached.get("lastmod") != lastmod:
            to_fetch.append(spot_id)
            continue
        if cached.get("fetch_v") != FETCH_SCHEMA_VERSION:
            to_fetch.append(spot_id)
            continue

        if cached.get("row_v") == ROW_SCHEMA_VERSION and cached.get("row"):
            row = dict(cached["row"])
        elif cached.get("spot"):
            # (b) 매핑 로직만 바뀐 경우 — 원본이 있으니 요청 없이 다시 만든다.
            row = spot_to_row(cached["spot"], cached.get("row", {}).get("crawled_at") or now_str)
            cached["row"] = row
            cached["row_v"] = ROW_SCHEMA_VERSION
            regenerated += 1
        else:
            # 원본 spot 이 없는 옛 캐시 → 재생성 불가, 재요청해야 한다.
            to_fetch.append(spot_id)
            continue

        # crawled_at 은 '실제로 페이지를 받아온 시각'이므로 그대로 둔다.
        # 다만 그것만 있으면 다운스트림의 '최근 N일 내 수집분만' 같은 신선도
        # 필터에서 재사용 행이 통째로 탈락한다. → verified_at(이번 실행에서
        # 여전히 유효함을 확인한 시각)을 ai_tags 에 따로 남긴다.
        row["ai_tags"] = _with_verified_at(row.get("ai_tags", ""), now_str)
        reused_rows.append(row)
        cache[str(spot_id)]["row"] = row

    print(f"  → 캐시와 lastmod 동일(스킵 대상): {len(reused_rows)}건")
    if regenerated:
        print(f"     └ 그중 매핑 로직 변경으로 로컬 재생성(요청 없음): {regenerated}건")
    print(f"  → 신규/갱신(실제 요청 대상): {len(to_fetch)}건")

    print("\n[2/3] 상세페이지 수집 (신규/갱신분만 실제 요청) ...")
    rows = list(reused_rows)
    new_or_updated = 0
    failed_ids = []
    recovered_from_cache = 0

    def _fallback_to_cache(spot_id):
        """
        요청/파싱 실패 시 캐시에 남아있는 직전 성공 row 로 대체한다.
        ⚠️ lastmod 는 갱신하지 않는다 — 다음 실행에서 다시 시도해야 하기 때문.
        이게 없으면 lastmod 가 바뀌어 재요청 대상이 된 항목이 일시적 네트워크
        오류를 만났을 때, 캐시에 멀쩡한 데이터가 있는데도 CSV 에서 통째로
        사라진다.

        row 가 구버전 스키마면 원본 spot 으로 다시 만들어서 넘긴다.
        FETCH_SCHEMA_VERSION 을 올린 실행에서 요청이 실패하면 구버전 row 가
        그대로 CSV 로 나가는데, 데이터가 낡은 건 어쩔 수 없어도 스키마까지
        낡으면 다운스트림 파서가 깨진다. 원본이 있으면 형식만이라도 맞춘다.
        """
        nonlocal recovered_from_cache
        cached = cache.get(str(spot_id))
        if not (cached and isinstance(cached, dict)):
            return False

        row = cached.get("row")
        if cached.get("row_v") != ROW_SCHEMA_VERSION and cached.get("spot"):
            row = spot_to_row(
                cached["spot"],
                (row or {}).get("crawled_at") or now_str,
            )
            cached["row"] = row
            cached["row_v"] = ROW_SCHEMA_VERSION

        if not row:
            return False

        rows.append(row)
        recovered_from_cache += 1
        return True

    for i, spot_id in enumerate(to_fetch, start=1):
        detail_url = f"{SITE_ROOT}/popup/{spot_id}"
        resp = polite_get(detail_url)
        if resp is None or resp.status_code != 200:
            recovered = _fallback_to_cache(spot_id)
            note = " (캐시의 직전 데이터로 대체)" if recovered else ""
            print(f"  ❌ [{i}/{len(to_fetch)}] id={spot_id} 요청 실패 (status={getattr(resp,'status_code',None)}){note}")
            failed_ids.append(spot_id)
            continue

        spot = parse_spot_detail(resp.text, spot_id)
        if spot is None:
            recovered = _fallback_to_cache(spot_id)
            note = " (캐시의 직전 데이터로 대체)" if recovered else ""
            print(f"  ⚠️  [{i}/{len(to_fetch)}] id={spot_id} 파싱 실패{note}")
            failed_ids.append(spot_id)
            continue

        row = spot_to_row(spot, now_str)
        rows.append(row)
        new_or_updated += 1
        # 원본 spot 도 함께 저장한다. 이게 있어야 나중에 매핑 로직만 바뀌었을 때
        # 네트워크 요청 없이 row 를 다시 만들 수 있다(ROW_SCHEMA_VERSION 참고).
        cache[str(spot_id)] = {
            "row_v": ROW_SCHEMA_VERSION,
            "fetch_v": FETCH_SCHEMA_VERSION,
            "lastmod": id_to_lastmod[spot_id],
            "spot": _slim_spot(spot),
            "row": row,
        }

        if i % 100 == 0 or i == len(to_fetch):
            print(f"  [진행] {i}/{len(to_fetch)}건 요청 완료 (신규/갱신 {new_or_updated}, 실패 {len(failed_ids)})")
            save_cache(cache)  # 중간 저장 — 중단돼도 지금까지 캐시는 남는다.

    # 4) 캐시 정리 — 이제 캐시가 row 전체(항목당 수백 바이트)를 담으므로,
    #    사이트에서 내려간 팝업의 죽은 항목이 계속 쌓이면 파일이 무한히 커진다.
    #    현재 sitemap 에 없는 키는 제거한다. (CSV 는 어차피 sitemap 기준으로만
    #    만들어지므로 데이터 정확성에는 영향 없고, 순수하게 파일 크기 문제다.)
    live_keys = {str(i) for i in id_to_lastmod}
    stale_keys = [k for k in cache if k not in live_keys]
    for k in stale_keys:
        del cache[k]

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
    if recovered_from_cache:
        print(f"   ↩️  실패했지만 캐시의 직전 데이터로 살린 건: {recovered_from_cache}건 (다음 실행에서 재시도됨)")
    if stale_keys:
        print(f"   🧹 sitemap 에서 사라져 캐시에서 정리한 항목: {len(stale_keys)}건")
    if failed_ids:
        print(f"   ⚠️ 실패한 id 목록(최대 20개 표시): {failed_ids[:20]}")
    print("=" * 75)


if __name__ == "__main__":
    collect()
