"""
공연·행사 레코드의 공연장(venue) 좌표 부여
=============================================================================
왜 필요한가
-----------------------------------------------------------------------------
공연·행사 레코드는 place_or_event_name 이 '바리톤 김우진 리사이틀' 처럼
공연 제목이라 지오코딩 대상이 없다. 그런데 공연장은 이미 region 컬럼에
들어 있다 ('강동아트센터 대극장 한강', '영등포아트홀').
조회 대상 필드가 잘못돼 있었을 뿐, venue 를 새로 수집할 필요는 없다.

generate_total_family_data.py 는 원본 소스에서 전체를 재생성하므로,
이 보정을 사람이 수동으로 적용하면 재생성할 때마다 사라진다.
그래서 파이프라인 단계로 만들었다. 실행 순서:

    generate_total_family_data.py  ->  geocode_event_venues.py  ->  enrich_...

대상 판별 (source_site 라벨에 의존하지 않는다)
-----------------------------------------------------------------------------
source_site 라벨은 수집기 개정 때마다 바뀐다 (실측: 'culture.seoul URL' ->
'서울시 문화행사'). 그래서 라벨 대신 **region 값의 형태**로 판별한다.

  - region 이 시도명으로 시작하면 행정구역/주소다 -> 건드리지 않는다.
    '서울 종로구' 같은 행정구역을 지오코딩하면 구청 좌표가 잡혀
    가짜 정밀도가 된다.
  - 시도명으로 시작하지 않으면 공연장 이름이다 -> 이름으로 조회한다.

정확도 기준: 히트율이 아니라 '반환된 장소가 정말 그곳인지'
-----------------------------------------------------------------------------
카카오 키워드 검색은 엉뚱한 곳도 자신 있게 반환한다.
  '정릉천복합문화공간 DDM스케이트파크' -> '청년살이발전소'(성북구)
  (DDM 은 동대문이다)
그래서 반환된 place_name 이 쿼리와 4글자 이상 겹칠 때만 채택하고,
어느 후보도 통과하지 못하면 좌표를 비워 둔다. 가짜 값을 만들지 않는다.
괄호 안 주소는 주소검색 API 로 직접 해석해 더 정확하다.
"""
import sys, io, os, csv, json, re, time, collections
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(BASE_DIR, "..", "data")
TARGET_CSV = os.path.join(DATA_DIR, "total_family_data.csv")
TARGET_JSON = os.path.join(DATA_DIR, "total_family_data.json")
CACHE_FILE = os.path.join(DATA_DIR, "venue_geocode_cache.json")

_CFG_PATH = os.path.join(BASE_DIR, "config.json")
try:
    with open(_CFG_PATH, "r", encoding="utf-8") as _f:
        KAKAO_KEY = json.load(_f).get("api_keys", {}).get("kakao_api_key", "")
except Exception:
    KAKAO_KEY = ""

KW_URL   = "https://dapi.kakao.com/v2/local/search/keyword.json"
ADDR_URL = "https://dapi.kakao.com/v2/local/search/address.json"

COORD_RE = re.compile(r"위도:([\d.]+), 경도:([\d.]+)")

# 시도명으로 시작하면 행정구역/주소로 본다.
SIDO_PREFIXES = (
    "서울", "경기", "인천", "부산", "대구", "광주", "대전", "울산", "세종",
    "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
    "충청", "전라", "경상",
)


def _get(url, query):
    r = requests.get(
        url,
        headers={"Authorization": f"KakaoAK {KAKAO_KEY}"},
        params={"query": query, "size": 1},
        timeout=6,
    )
    if r.status_code in (401, 403):
        raise PermissionError(f"카카오 로컬 사용 불가 (HTTP {r.status_code}): {r.text[:160]}")
    if r.status_code != 200:
        return []
    return r.json().get("documents", [])


def _norm(s):
    return re.sub(r"[^가-힣A-Za-z0-9]", "", s or "")


def name_matches(query, place_name):
    """쿼리와 반환 장소명이 4글자 이상 연속 겹치면 같은 장소로 본다."""
    a, b = _norm(query), _norm(place_name)
    if not a or not b:
        return False
    if len(a) < 4:
        return a in b
    return any(a[i:i + 4] in b for i in range(len(a) - 3))


def is_venue_region(region_base):
    """region 이 공연장 이름인지(True) 행정구역·주소인지(False)."""
    v = (region_base or "").strip()
    if not v:
        return False
    return not v.startswith(SIDO_PREFIXES)


def collapse_word_repeat(s):
    """'한국공예체험박물관 한국공예체험박물관' -> '한국공예체험박물관'"""
    out = []
    for t in s.split():
        if out and (t == out[-1] or t.startswith(out[-1]) or out[-1].startswith(t)):
            if len(t) > len(out[-1]):
                out[-1] = t
            continue
        out.append(t)
    return " ".join(out)


def candidates(venue):
    """(종류, 쿼리) 후보를 우선순위대로. 종류: 'addr' | 'kw'"""
    v = collapse_word_repeat(re.sub(r"\s+", " ", (venue or "").strip()))
    if not v:
        return []
    out = []
    # 괄호 안 주소가 있으면 가장 정확하다
    for inner in re.findall(r"[(（]([^)）]*)[)）]", v):
        t = inner.strip()
        if re.search(r"(로|길|동|가)\s*\d", t) or re.search(r"(시|군|구)\s", t):
            out.append(("addr", t))
    base = re.sub(r"\s+", " ", re.sub(r"[(（][^)）]*[)）]", " ", v)).strip()
    kw = [base]
    # 콤마/슬래시로 나뉜 조각 (긴 것 우선) — 공연장이 여러 곳인 행사
    kw += sorted([p.strip() for p in re.split(r"[,/·|]", base) if len(p.strip()) >= 3],
                 key=len, reverse=True)
    w = base.split()
    if len(w) >= 2:
        kw.append(" ".join(w[:2]))
    if w:
        kw.append(w[0])
    kw += [re.sub(r"\s*(일대|인근|주변|외|등)$", "", x).strip() for x in list(kw)]
    seen = set()
    for x in kw:
        x = x.strip()
        if len(x) >= 3 and x not in seen:
            seen.add(x)
            out.append(("kw", x))
    return out


def resolve(venue):
    """(lat, lng, 채택쿼리, 반환장소명, 방식). 실패 시 전부 None."""
    for kind, q in candidates(venue):
        if kind == "addr":
            d = _get(ADDR_URL, q)
            if d:
                return d[0]["y"], d[0]["x"], q, d[0].get("address_name", ""), "addr"
        else:
            d = _get(KW_URL, q)
            if d and name_matches(q, d[0]["place_name"]):
                return d[0]["y"], d[0]["x"], q, d[0]["place_name"], "kw"
    return None, None, None, None, None


def main():
    print("=" * 70)
    print("  공연·행사 공연장(venue) 좌표 부여")
    print("=" * 70)

    if not KAKAO_KEY or KAKAO_KEY.startswith("YOUR_"):
        print("[실패] config.json 의 api_keys.kakao_api_key 가 설정되지 않았습니다.")
        sys.exit(1)
    if not os.path.exists(TARGET_CSV):
        print(f"[실패] 입력 파일 없음: {TARGET_CSV}")
        sys.exit(1)

    cache = {}
    if os.path.exists(CACHE_FILE):
        try:
            cache = json.load(io.open(CACHE_FILE, encoding="utf-8"))
        except Exception:
            cache = {}
    print(f"  좌표 캐시 {len(cache)}건 로드")

    rows = list(csv.DictReader(io.open(TARGET_CSV, encoding="utf-8-sig")))
    cols = list(rows[0].keys())

    targets = []
    for i, r in enumerate(rows):
        region = r.get("region") or ""
        if COORD_RE.search(region):
            continue                                  # 이미 좌표 있음
        if is_venue_region(region.split("|")[0].strip()):
            targets.append(i)
    print(f"  전체 {len(rows)}건 / 좌표 없고 region 이 공연장 이름인 행 {len(targets)}건")

    def save_cache():
        tmp = CACHE_FILE + ".tmp"
        json.dump(cache, io.open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, CACHE_FILE)

    hit = 0
    how = collections.Counter()
    fails = []
    for n, i in enumerate(targets, 1):
        venue = (rows[i].get("region") or "").split("|")[0].strip()
        if venue not in cache:
            try:
                cache[venue] = list(resolve(venue))
            except PermissionError as e:
                print(f"[실패] {e}")
                save_cache()
                sys.exit(1)
            except Exception as e:
                print(f"    [조회 오류] {venue!r}: {type(e).__name__}: {e}")
                cache[venue] = [None, None, None, None, None]
            if n % 100 == 0:
                save_cache()
                print(f"    {n}/{len(targets)} 처리 (채택 {hit})")
            time.sleep(0.02)
        lat, lng, q, got, kind = cache[venue]
        if lat and lng:
            hit += 1
            how[kind] += 1
            rows[i]["region"] = f"{venue} | 위도:{lat}, 경도:{lng}"
        elif len(fails) < 12:
            fails.append(venue)
    save_cache()

    print(f"\n  검증 통과 {hit}/{len(targets)}건"
          f" ({hit / max(1, len(targets)) * 100:.1f}%) · 방식 {dict(how)}")
    if fails:
        print("  검증 실패로 공란 유지 (예시):")
        for v in fails:
            print(f"    {v[:60]}")

    if not targets:
        print("  대상이 없어 파일을 수정하지 않았습니다.")
        return

    tmp = TARGET_CSV + ".tmp"
    with io.open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    # 행 수가 줄어들면 저장하지 않는다 (원본 보존)
    assert len(list(csv.DictReader(io.open(tmp, encoding="utf-8-sig")))) == len(rows)
    os.replace(tmp, TARGET_CSV)

    tmp = TARGET_JSON + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    os.replace(tmp, TARGET_JSON)

    total_coord = sum(1 for r in rows if COORD_RE.search(r.get("region") or ""))
    print(f"\n[완료] 저장 {len(rows)}건 · 전체 좌표 보유 {total_coord}건"
          f" ({total_coord / len(rows) * 100:.1f}%)")


if __name__ == "__main__":
    main()
