"""
좌표 + 이름 유사도 기반 장소 중복 제거
=============================================================================
왜 필요한가
-----------------------------------------------------------------------------
장소명이 손상된 소스가 섞여 있어 같은 장소가 여러 건으로 등재된다.
예: 송현공원 1곳이 '송현공원' / '동구송현공원' / '동구인천 동구의 송현공원'
등 6건. 기존 drop_duplicates(subset=['place_or_event_name']) 는 이름이
다르므로 잡지 못한다. 좌표가 있으면 같은 장소인지 판정할 수 있다.

generate_total_family_data.py 가 원본에서 전체를 재생성하므로 이 보정을
수동으로 적용하면 재생성마다 사라진다. 그래서 파이프라인 단계로 만들었다.

    generate_total_family_data.py -> geocode_event_venues.py
      -> dedupe_places.py -> enrich_total_family_data.py

★ 행사(공연/전시)는 절대 병합하지 않는다
-----------------------------------------------------------------------------
같은 공연장에서 열리는 서로 다른 공연은 좌표가 같고 이름도 유사하다.
행사까지 병합하면 실제로 다른 공연이 사라진다 (실측으로 확인한 오병합):
    'MAC 모닝 콘서트 #1 / #2 / #3 / #5'   -> 회차별 다른 공연
    '체홉 낭독극 [세자매]' vs '[바냐 아저씨]'  -> 다른 작품
    '마티네콘서트 #2.엘가' vs '#3.베버'      -> 다른 공연
그래서 period == '상시' 인 행(장소)만 대상으로 한다.

판정 규칙 (보수적)
-----------------------------------------------------------------------------
  1. period 가 '상시' 이고 좌표가 있는 행만 후보
  2. 좌표가 완전히 같은 것끼리만 비교
  3. 그 안에서도 정규화 이름이 같거나 / 포함관계거나 / 유사도 0.85 이상일 때만 병합
     -> 같은 좌표라도 이름이 다르면 별개 장소로 남긴다 (지오코딩 오병합 방어)
  4. 대표 1건을 남기고, 대표의 빈 칸은 나머지에서 채운다 (정보 손실 방지)
     단 recommend_reason 은 미확인 주장이라 전파하지 않는다

--apply 없이 실행하면 dry-run 이다.
"""
import sys, io, os, csv, json, re, difflib, collections

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

APPLY = "--apply" in sys.argv

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_DIR    = os.path.join(BASE_DIR, "..", "data")
TARGET_CSV  = os.path.join(DATA_DIR, "total_family_data.csv")
TARGET_JSON = os.path.join(DATA_DIR, "total_family_data.json")

COORD_RE = re.compile(r"위도:([\d.]+), 경도:([\d.]+)")
REGION_PREFIX_RE = re.compile(r"^(서울시?|서울특별시|경기도?|인천시?|인천광역시)")
PARTICLES = ("는", "은", "이", "가", "을", "를", "와", "과", "의", "에", "도")
# 미확인 주장이라 대표 레코드로 전파하지 않는 컬럼
NO_PROPAGATE = {"recommend_reason"}


def dedupe_repeated_suffix(name):
    """인접 반복 접미사 제거. '남양주시육아종합지원센터육아종합지원센터' -> '...센터'"""
    if not name:
        return name
    prev = None
    while prev != name:
        prev = name
        n = len(name)
        for k in range(n // 2, 1, -1):
            if name[n - k:] == name[n - 2 * k:n - k]:
                name = name[:n - k]
                break
    return name


def norm(name):
    s = dedupe_repeated_suffix((name or "").strip())
    s = re.sub(r"[\s\-·,.()\[\]]+", "", s)
    s = REGION_PREFIX_RE.sub("", s)
    for p in sorted(PARTICLES, key=len, reverse=True):
        if len(s) > len(p) + 3 and s.endswith(p):
            s = s[:-len(p)]
            break
    return s


def digits_conflict(a, b):
    """숫자만 다른 이름은 별개 지점으로 본다.

    '자양4동1호점' 과 '자양4동2호점' 은 한 글자만 달라 유사도가 매우 높지만
    서로 다른 지점이다 ('제1어린이공원'/'제2어린이공원' 도 같다).
    숫자를 뺀 나머지가 같은데 숫자열이 다르면 병합하지 않는다.
    """
    da, db = re.findall(r"\d+", a), re.findall(r"\d+", b)
    if da == db:
        return False
    return re.sub(r"\d+", "", a) == re.sub(r"\d+", "", b)


def same_place(a, b):
    if not a or not b:
        return False
    if a == b:
        return True
    if digits_conflict(a, b):
        return False
    if a in b or b in a:
        # 너무 짧은 쪽이 우연히 포함되는 것 방어.
        # '서울형'(3자) 같은 잘린 조각은 막고, '송현공원'(4자) in
        # '동구송현공원' 처럼 실제 같은 장소인 포함관계는 통과시킨다.
        return min(len(a), len(b)) >= 4
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.85


def is_place_row(r):
    """행사가 아닌 '장소' 행인지. 행사는 병합하면 서로 다른 공연이 사라진다."""
    return (r.get("period") or "").strip() == "상시"


def main():
    if not os.path.exists(TARGET_CSV):
        print(f"[실패] 입력 파일 없음: {TARGET_CSV}")
        sys.exit(1)

    rows = list(csv.DictReader(io.open(TARGET_CSV, encoding="utf-8-sig")))
    cols = list(rows[0].keys())

    groups = collections.defaultdict(list)
    n_event = n_nocoord = 0
    for i, r in enumerate(rows):
        if not is_place_row(r):
            n_event += 1
            continue
        m = COORD_RE.search(r.get("region") or "")
        if not m:
            n_nocoord += 1
            continue
        groups[(m.group(1), m.group(2))].append(i)

    print("=" * 70)
    print(f"  {'[APPLY]' if APPLY else '[DRY-RUN]'} 장소 중복 제거")
    print("=" * 70)
    print(f"  입력 {len(rows)}건 · 행사 제외 {n_event}건 · 좌표없어 제외 {n_nocoord}건")
    print(f"  대상 {sum(len(v) for v in groups.values())}건 / 고유좌표 {len(groups)}개")

    def pick_rep(idxs):
        """대표: 정규화 이름의 최빈형 중 원본 이름이 가장 짧은 것."""
        cnt = collections.Counter(norm(rows[i]["place_or_event_name"]) for i in idxs)
        best = cnt.most_common(1)[0][0]
        cand = [i for i in idxs if norm(rows[i]["place_or_event_name"]) == best] or list(idxs)
        return min(cand, key=lambda i: len(rows[i]["place_or_event_name"]))

    drop, merges, kept_apart, filled_cells = set(), [], 0, 0
    for idxs in groups.values():
        if len(idxs) < 2:
            continue
        clusters = []
        for i in idxs:
            ni = norm(rows[i]["place_or_event_name"])
            for c in clusters:
                if any(same_place(ni, norm(rows[j]["place_or_event_name"])) for j in c):
                    c.append(i)
                    break
            else:
                clusters.append([i])
        if len(clusters) > 1:
            kept_apart += 1
        for c in clusters:
            if len(c) < 2:
                continue
            rep = pick_rep(c)
            others = [i for i in c if i != rep]
            for col in cols:
                if col in NO_PROPAGATE:
                    continue
                if not (rows[rep].get(col) or "").strip():
                    for i in others:
                        v = (rows[i].get(col) or "").strip()
                        if v:
                            rows[rep][col] = v
                            filled_cells += 1
                            break
            merges.append((rows[rep]["place_or_event_name"],
                           [rows[i]["place_or_event_name"] for i in others]))
            drop.update(others)

    print(f"\n  병합 클러스터 {len(merges)}개 · 제거 {len(drop)}건"
          f" -> 결과 {len(rows) - len(drop)}건")
    print(f"  같은 좌표지만 이름이 달라 별개로 남긴 그룹 {kept_apart}개")
    print(f"  대표의 빈 칸을 중복본에서 채운 셀 {filled_cells}개")
    print("\n  병합 예시:")
    for rep, others in merges[:10]:
        print(f"    남김: {rep[:44]}")
        for o in others:
            print(f"      제거: {o[:46]}")

    if not APPLY:
        print("\n  (dry-run — 파일을 수정하지 않았습니다. --apply 로 실제 적용)")
        return
    if not drop:
        print("\n  제거할 중복이 없어 파일을 수정하지 않았습니다.")
        return

    out = [r for i, r in enumerate(rows) if i not in drop]
    tmp = TARGET_CSV + ".tmp"
    with io.open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(out)
    assert len(list(csv.DictReader(io.open(tmp, encoding="utf-8-sig")))) == len(out)
    os.replace(tmp, TARGET_CSV)

    tmp = TARGET_JSON + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    os.replace(tmp, TARGET_JSON)
    print(f"\n[완료] 저장 {len(out)}건 (CSV/JSON)")


if __name__ == "__main__":
    main()
