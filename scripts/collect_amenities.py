"""
편의시설 정보 수집 (네이버 플레이스 conveniences)
=============================================================================
어디까지 가능한지 먼저 실측했다
-----------------------------------------------------------------------------
편의시설 커버리지 8% 는 "장소명이 손상돼서" 라고 진단돼 있었다. 수집기를
카카오 로컬로 재작성해 이름을 전부 정제한 뒤 다시 재보니, 원인이 다른 데
있었다. 층화 표본(유형별 12건) 실측 결과:

    박물관·과학관·전시관   67% 네이버 플레이스 카드 있음
    키즈카페(사설)         8%
    큰 공원(도시근린공원)   8%
    서울형키즈카페(공공)    0%
    동네 어린이공원         0%
    수영장·물놀이           0%

네이버는 **주요 문화시설에만 플레이스 카드를 띄운다.** 우리 데이터는 동네
공원·소규모 키즈카페가 대부분이라, 이름을 고쳐도 조회할 정보 자체가 없다.
즉 커버리지를 크게 올릴 방법은 없다. 소스의 한계다.

그래서 이 스크립트는 **카드가 있는 유형만 조회한다.** 0% 유형에 1만 건을
던지면 수십 분을 쓰고 아무것도 얻지 못한다.

무엇을 얻는가
-----------------------------------------------------------------------------
대상 약 2,100건 중 실측 수율대로 약 300~400건에서 실제 편의시설을 확보한다.
전체 11,021건 대비 3~4% 다. **커버리지를 크게 올릴 방법은 없다** — 동네
공원·소규모 농장은 네이버에 카드 자체가 없다.
확인된 항목만 태그로 붙이고, 확인되지 않으면 **아무 주장도 하지 않는다**
(예전 코드는 카테고리만 보고 '수유실·기저귀갈이대 완비' 를 단정했다).

파이프라인 단계로 만들었다 — generate 가 전체를 재생성하므로 수동 적용은
매번 사라진다. 캐시가 있어 재실행은 저렴하다.
"""
import sys, io, os, csv, json, re, time, collections
from urllib.parse import quote
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_DIR    = os.path.join(BASE_DIR, "..", "data")
TARGET_CSV  = os.path.join(DATA_DIR, "total_family_data.csv")
TARGET_JSON = os.path.join(DATA_DIR, "total_family_data.json")
CACHE_FILE  = os.path.join(DATA_DIR, "amenity_cache.json")

HTTP_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}

# 네이버 검색 페이지에 박혀 있는 플레이스 데이터의 편의시설 배열.
_CONV_RE = re.compile(r'"conveniences"\s*:\s*\[([^\]]*)\]')

# 분류별 수율을 실측해 대상을 정했다 (분류당 12건 표본):
#     과학관 58% · 박물관 42% · 전시관 17% · 체험학습장 17%
#     수목원,식물원 17% · 주말농장 17% · 키즈카페 8%
#     농장,목장 0% · 공원 0% · 도시근린공원 0%
# 0% 분류(농장·공원 계열 4,159건)는 제외한다. 던져도 아무것도 얻지 못하고
# 수십 분을 쓴다. 키즈카페는 수율이 낮지만 이 앱에서 가장 중요한 유형이라
# 포함한다.
ELIGIBLE_LEAVES = {
    "박물관", "과학관", "미술관", "전시관", "기념관",
    "체험학습장", "체험관", "수목원,식물원", "동물원",
    "주말농장", "워터파크", "키즈카페",
}

# conveniences 어휘 -> 태그. 확인된 것만 붙인다.
# 어휘에 없는 항목(수유실·기저귀갈이대·유모차)은 애초에 검증이 불가하므로
# 태그를 만들지 않는다.
TAG_RULES = [
    ("parking:1.0",       ("주차",)),
    ("kids_facility:1.0", ("유아시설", "놀이방")),
    ("restroom:1.0",      ("화장실",)),
    ("wifi:1.0",          ("무선 인터넷", "와이파이")),
    ("group_ok:1.0",      ("단체 이용 가능",)),
    ("reservation:1.0",   ("예약",)),
    ("accessible:1.0",    ("휠체어",)),
]


def leaf_of(row):
    return (row.get("ai_tags") or "").split(";")[-1].strip()


def parse_conveniences(html):
    """편의시설 배열. 필드가 없으면 None(미확인)."""
    m = _CONV_RE.search(html)
    if not m:
        return None
    items = re.findall(r'"([^"]+)"', m.group(1))
    # 네이버 JSON 은 슬래시를 이스케이프한다 ("남/녀 화장실 구분").
    return [it.replace(chr(92) + "u002F", "/") for it in items]


_ADMIN_RE = re.compile(r"^(서울|경기|인천)\s*(\S+[시군구])")


def build_query(name, region_base):
    """네이버 질의 생성 — 장소명 단독이 기본이다.

    ⚠ region 에 도로명 전체 주소를 붙이면 카드가 뜨지 않는다.
      '서울 강남구 도산대로45길 6 호림박물관 신사분관' -> conveniences 없음
      '호림박물관 신사분관'                          -> 정상 반환
    enrich_total_family_data.build_search_query 와 같은 원칙이다
    (실측: 지역+장소명 4% vs 장소명 단독 8%).
    이름이 너무 짧아 단독으로 모호할 때만 행정구역 접두어를 보조로 붙인다.
    """
    n = (name or "").strip()
    if not n:
        return (region_base or "").strip()
    if len(n) <= 4:
        m = _ADMIN_RE.match((region_base or "").strip())
        if m:
            return f"{m.group(1)} {m.group(2)} {n}"
    return n


def fetch_conveniences(name, region_base):
    """(list | None). None 은 '카드 없음 = 미확인' 이다. 빈 리스트와 구분한다."""
    q = build_query(name, region_base)
    url = f"https://search.naver.com/search.naver?where=nexearch&query={quote(q)}"
    r = requests.get(url, headers=HTTP_HEADERS, timeout=8)
    if r.status_code != 200:
        return None
    return parse_conveniences(r.text)


def amenity_tags(convs):
    joined = " ".join(convs or [])
    out = []
    for tag, words in TAG_RULES:
        if any(w in joined for w in words):
            out.append(tag)
    return out


def merge_tags(orig, new_tags):
    """기존 ai_tags 에 확인된 편의시설 태그를 더한다 (순서 유지, 중복 제거)."""
    have = [t.strip() for t in (orig or "").split(";") if t.strip()]
    # 이전 실행이 붙인 편의시설 태그는 갈아낀다 (재실행 시 중복/구값 방지)
    managed = {t for t, _ in TAG_RULES}
    have = [t for t in have if t not in managed]
    return ";".join(dict.fromkeys(have + new_tags))


def main():
    print("=" * 70)
    print("  편의시설 수집 (네이버 플레이스 conveniences)")
    print("=" * 70)

    if not os.path.exists(TARGET_CSV):
        print(f"[실패] 입력 파일 없음: {TARGET_CSV}")
        sys.exit(1)

    cache = {}
    if os.path.exists(CACHE_FILE):
        try:
            cache = json.load(io.open(CACHE_FILE, encoding="utf-8"))
        except Exception:
            cache = {}
    print(f"  캐시 {len(cache)}건 로드")

    rows = list(csv.DictReader(io.open(TARGET_CSV, encoding="utf-8-sig")))
    cols = list(rows[0].keys())

    targets = [i for i, r in enumerate(rows) if leaf_of(r) in ELIGIBLE_LEAVES]
    print(f"  전체 {len(rows)}건 / 조회 대상(카드 있는 유형) {len(targets)}건")
    print("  ※ 동네 어린이공원·수영장·공공키즈카페는 네이버 카드가 없어 제외한다")

    def save_cache():
        tmp = CACHE_FILE + ".tmp"
        json.dump(cache, io.open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, CACHE_FILE)

    known = tagged = 0
    vocab = collections.Counter()
    failed = 0
    for n, i in enumerate(targets, 1):
        r = rows[i]
        name = r["place_or_event_name"]
        region_base = (r.get("region") or "").split("|")[0].strip()
        key = f"{region_base}_{name}"
        if key not in cache:
            try:
                cache[key] = fetch_conveniences(name, region_base)
            except Exception as e:
                failed += 1
                print(f"    [조회 오류] {name[:28]!r}: {type(e).__name__}")
                cache[key] = None
            if n % 100 == 0:
                save_cache()
                print(f"    {n}/{len(targets)} 처리 (편의시설 확보 {known})")
            time.sleep(0.05)
        convs = cache[key]
        if convs:
            known += 1
            vocab.update(convs)
            tags = amenity_tags(convs)
            if tags:
                tagged += 1
                rows[i]["ai_tags"] = merge_tags(r.get("ai_tags"), tags)
    save_cache()

    print(f"\n  편의시설 확보 {known}/{len(targets)}건 "
          f"({known / max(1, len(targets)) * 100:.1f}%) · 태그 부여 {tagged}건"
          f" · 조회 오류 {failed}건")
    if vocab:
        print("  수집된 편의시설 어휘 상위 12:")
        for k, v in vocab.most_common(12):
            print(f"    {v:5d}  {k}")

    if not targets:
        print("  대상이 없어 파일을 수정하지 않았습니다.")
        return

    tmp = TARGET_CSV + ".tmp"
    with io.open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    assert len(list(csv.DictReader(io.open(tmp, encoding="utf-8-sig")))) == len(rows)
    os.replace(tmp, TARGET_CSV)

    tmp = TARGET_JSON + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    os.replace(tmp, TARGET_JSON)

    with_amen = sum(1 for r in rows
                    if any(t in (r.get("ai_tags") or "") for t, _ in TAG_RULES))
    print(f"\n[완료] 저장 {len(rows)}건 · 편의시설 태그 보유 {with_amen}건 "
          f"({with_amen / len(rows) * 100:.1f}%)")


if __name__ == "__main__":
    main()
