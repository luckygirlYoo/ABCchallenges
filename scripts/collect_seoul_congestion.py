"""
서울시 실시간 도시데이터 기반 인파 혼잡도 수집기
=============================================================================
왜 필요한가
-----------------------------------------------------------------------------
이 프로젝트에는 혼잡도 실측 소스가 없었다. 그래서 예전 코드는
`randint(1,3)` 으로 congestion_score 를 만들어 실측값처럼 저장했고,
그 값을 웹앱이 '현재 혼잡도' 로 표시했다. 난수는 제거했지만(공란 처리)
실제 데이터가 없는 상태는 그대로였다.

서울시 열린데이터광장의 **실시간 도시데이터 인구현황**
(`citydata_ppltn`) 이 121개 주요 장소의 실시간 인파 혼잡도를 준다.
이미 보유한 seoul_api_key 로 바로 호출된다 (신규 키 발급 불필요).

    어린이대공원  약간 붐빔  4,000~4,500명  0~9세 1.6%  2026-08-23 18:35

설계
-----------------------------------------------------------------------------
혼잡도는 몇 분 단위로 바뀌므로 total_family_data.csv 에 박아 넣지 않는다.
별도 파일(data/seoul_congestion.csv)로 두고, 웹앱이 좌표 근접으로 조인한다.
이 수집기만 다시 돌리면 최신 혼잡도가 반영되고 본 데이터는 건드리지 않는다.

API 가 area 좌표를 주지 않으므로 카카오 로컬로 지오코딩해 캐시한다
(관측지점 목록은 거의 바뀌지 않으므로 캐시가 계속 유효하다).

정직성
-----------------------------------------------------------------------------
관측지점은 121곳뿐이고 전부 서울(+서울대공원)이다. 우리 데이터 11,021건
대부분은 관측지점이 없다. 없는 곳에 값을 만들어 붙이지 않는다.
웹앱에서도 '이 장소의 혼잡도' 가 아니라 '인근 관측지점 기준' 으로
관측지점 이름·거리·측정시각을 함께 보여준다.
"""
import sys, io, os, json, csv, time, re
from datetime import datetime
import urllib.request, urllib.parse, urllib.error
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(BASE_DIR, "..", "data")
OUTPUT_CSV = os.path.join(DATA_DIR, "seoul_congestion.csv")
GEO_CACHE  = os.path.join(DATA_DIR, "seoul_area_coords.json")

_CFG_PATH = os.path.join(BASE_DIR, "config.json")
try:
    with open(_CFG_PATH, "r", encoding="utf-8") as _f:
        _keys = json.load(_f).get("api_keys", {})
except Exception:
    _keys = {}
SEOUL_KEY = _keys.get("seoul_api_key", "")
KAKAO_KEY = _keys.get("kakao_api_key", "")

PPLTN_URL = "http://openapi.seoul.go.kr:8088/{key}/json/citydata_ppltn/1/5/{code}"
KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"

# 관측지점 코드 범위. 중간에 결번이 있고(POI022, POI028 등) 끝은 POI131 부근이다.
POI_MAX = 140

FIELDS = [
    "area_cd", "area_nm", "lat", "lng",
    "congest_lvl", "congest_msg", "ppltn_min", "ppltn_max",
    "rate_age_0_9", "resnt_rate", "measured_at",
    "fcst_time", "fcst_congest_lvl", "collected_at",
]


def fetch_area(code):
    """관측지점 1곳의 실시간 인구현황. 없으면 None."""
    url = PPLTN_URL.format(key=SEOUL_KEY, code=code)
    with urllib.request.urlopen(url, timeout=15) as r:
        d = json.load(r)
    rows = d.get("SeoulRtd.citydata_ppltn") or []
    return rows[0] if rows else None


def _norm(s):
    return re.sub(r"[^가-힣A-Za-z0-9]", "", s or "")


def geocode_area(name):
    """관측지점 이름 -> (lat, lng). 반환 장소명 검증을 통과해야 채택."""
    if not KAKAO_KEY or KAKAO_KEY.startswith("YOUR_"):
        return None, None
    # '국립중앙박물관·용산가족공원' 처럼 두 지점이 묶인 이름은 앞부분을 먼저 시도
    cands = [name] + [p.strip() for p in name.split("·") if len(p.strip()) >= 3]
    seen = set()
    for q in cands:
        if q in seen:
            continue
        seen.add(q)
        try:
            r = requests.get(
                KAKAO_KEYWORD_URL,
                headers={"Authorization": f"KakaoAK {KAKAO_KEY}"},
                params={"query": f"서울 {q}", "size": 1},
                timeout=6,
            )
            if r.status_code != 200:
                continue
            docs = r.json().get("documents", [])
        except Exception:
            continue
        if not docs:
            continue
        got = docs[0]["place_name"]
        a, b = _norm(q), _norm(got)
        # 반환 장소명이 질의와 3글자 이상 겹칠 때만 채택 (엉뚱한 매칭 방지)
        if len(a) >= 3 and any(a[i:i + 3] in b for i in range(len(a) - 2)):
            return docs[0]["y"], docs[0]["x"]
    return None, None


def main():
    print("=" * 70)
    print("  서울시 실시간 도시데이터 인파 혼잡도 수집")
    print("=" * 70)

    if not SEOUL_KEY or SEOUL_KEY.startswith("YOUR_"):
        print("[실패] config.json 의 api_keys.seoul_api_key 가 설정되지 않았습니다.")
        sys.exit(1)

    coords = {}
    if os.path.exists(GEO_CACHE):
        try:
            coords = json.load(io.open(GEO_CACHE, encoding="utf-8"))
        except Exception:
            coords = {}
    print(f"  관측지점 좌표 캐시 {len(coords)}건 로드")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out, missing, geo_fail = [], 0, []
    for i in range(1, POI_MAX + 1):
        code = f"POI{i:03d}"
        try:
            row = fetch_area(code)
        except Exception as e:
            missing += 1
            continue
        if not row:
            missing += 1
            continue

        name = row.get("AREA_NM") or ""
        if name not in coords:
            lat, lng = geocode_area(name)
            coords[name] = [lat, lng]
            time.sleep(0.03)
        lat, lng = coords[name]
        if not (lat and lng):
            geo_fail.append(name)

        fcst = row.get("FCST_PPLTN") or []
        f0 = fcst[0] if isinstance(fcst, list) and fcst else {}

        out.append({
            "area_cd": row.get("AREA_CD") or code,
            "area_nm": name,
            "lat": lat or "",
            "lng": lng or "",
            "congest_lvl": row.get("AREA_CONGEST_LVL") or "",
            "congest_msg": row.get("AREA_CONGEST_MSG") or "",
            "ppltn_min": row.get("AREA_PPLTN_MIN") or "",
            "ppltn_max": row.get("AREA_PPLTN_MAX") or "",
            "rate_age_0_9": row.get("PPLTN_RATE_0") or "",
            "resnt_rate": row.get("RESNT_PPLTN_RATE") or "",
            "measured_at": row.get("PPLTN_TIME") or "",
            "fcst_time": f0.get("FCST_TIME", ""),
            "fcst_congest_lvl": f0.get("FCST_CONGEST_LVL", ""),
            "collected_at": now,
        })
        if len(out) % 30 == 0:
            print(f"    {len(out)}개 관측지점 수집")

    json.dump(coords, io.open(GEO_CACHE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    with_coord = sum(1 for r in out if r["lat"])
    print(f"\n  관측지점 {len(out)}개 (결번/빈응답 {missing})")
    print(f"  좌표 확보 {with_coord}개 / 지오코딩 실패 {len(geo_fail)}개")
    if geo_fail:
        print(f"    실패 지점: {geo_fail[:8]}")
    lv = {}
    for r in out:
        lv[r["congest_lvl"]] = lv.get(r["congest_lvl"], 0) + 1
    print(f"  혼잡도 분포: {lv}")
    if out:
        print(f"  측정 시각: {out[0]['measured_at']}")

    if not out:
        # 0건이면 기존 파일을 덮어쓰지 않고 실패를 알린다.
        print(f"[실패] 수집 0건 → 기존 파일 보존: {OUTPUT_CSV}")
        sys.exit(1)

    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = OUTPUT_CSV + ".tmp"
    with io.open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(out)
    os.replace(tmp, OUTPUT_CSV)
    print(f"[완료] CSV 저장: {OUTPUT_CSV} ({len(out)}건)")


if __name__ == "__main__":
    main()
