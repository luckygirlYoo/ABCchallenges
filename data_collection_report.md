# 데이터 수집 및 2차 실시간 보강 파이프라인 리포트 v4.5

> 마지막 업데이트: 2026-08-22  
> 서비스명: **주말해 (주말에 어디가?)** - AI 기반 아빠 맞춤형 여가 추천 서비스

---

## 1. 파이프라인 전체 구조 (7단계 배치 시스템)

관리자 페이지(`http://localhost:8080/web/admin.html`)에서 **[수집 실행]** 버튼을 클릭하면 비동기 멀티스레드 배치 엔진이 아래 7단계 파이프라인을 순차 구동하고, 프로그레스 바(0~100%) 및 실시간 배치 상태 뱃지(`✅ 성공`, `🌀 진행중`)를 갱신합니다.

```
[수집 실행] 버튼 클릭 (관리자 센터)
    ↓  POST /api/refresh (비동기 쓰레드 파이프라인 구동)
    ↓
    1. culture_event_collector.py    서울·경기 공공 문화행사 API + 미술관 수집 (200건)
    2. live_ticket_crawler.py        인터파크 티켓 라이브 랭킹 수집 (300건)
    3. live_ticketlink_crawler.py    티켓링크 라이브 전수 크롤링 & 가족/어린이 태깅 (353건)
    4. public_childcare_collector.py 서울형키즈카페/맘스하트/아이러브맘/육아센터 동적 라이브 전수 수집 (564건)
    5. naver_search_collector.py     수도권 63개 시군구 × 3개 테마 네이버 장소 정밀 클렌징 수집 (370건)
    ↓
    6. generate_total_family_data.py 가족/어린이/아동 전용 필터링 및 1차 통합 → total_family_data.csv (1,262건)
    ↓
    7. enrich_total_family_data.py   네이버 실검증 편의시설(주차/수유실/기저귀갈이대/유모차) + WGS84 좌표 연동 2차 보강
    ↓
    🎉 최종 1,235건 고품질 위치검증 맞춤형 데이터 확정!
```

---

## 2. 스크립트별 상세 수집 및 보강 로직

### 1) `scripts/culture_event_collector.py`
- **수집 소스**: 서울시 문화행사 API, 국립현대미술관, 서울시립미술관, 예술의전당
- **수집 범위**: 서울 + 경기 공공 문화행사 (200건)
- **출력 파일**: `data/culture_events_raw.csv`

### 2) `scripts/live_ticket_crawler.py`
- **수집 소스**: 인터파크 티켓 (콘서트, 뮤지컬, 연극, 클래식, 전시, 아동)
- **수집 범위**: 라이브 랭킹 실시간 추출 (300건)
- **출력 파일**: `data/live_interpark_tickets.csv`

### 3) `scripts/live_ticketlink_crawler.py` (v4.0 전수 수집기)
- **수집 소스**: 티켓링크 (Ticketlink) 공식 라이브 API (`/search/getSearchList`)
- **가족/어린이 전용 태깅**: `family:1.0;baby:1.0;toddler:1.0;가족어린이동반` 및 `category="가족/어린이"` 자동 부착 (353건)
- **출력 파일**: `data/live_ticketlink_tickets.csv`

### 4) `scripts/public_childcare_collector.py` (v2.0 동적 전수 수집기)
- **수집 소스**: 하드코딩 완전 폐지 → 서울형 키즈카페(25개구 동별 지점), 동작구 맘스하트카페, 경기도 31개 시군 아이러브맘카페, 지자체 육아종합지원센터 & 장난감도서관 실시간 동적 수집 (564건)
- **출력 파일**: `data/public_childcare_data.csv`

### 5) `scripts/naver_search_collector.py` (v4.0 정밀 장소 클렌징 수집기)
- **수집 방식**: 수도권 63개 시군구 × 3개 테마 네이버 플레이스 사업자 카드(Place Card) 정밀 추출 (370건)
- **노이즈 필터링**: 블로그 포스팅 제목, 뉴스 기사, 맘카페 질문글, 해시태그(`#`), "새 창 열림", "더보기" 등 잡음 100% 제거
- **출력 파일**: `data/naver_search_results.csv`

### 6) `scripts/generate_total_family_data.py`
- **역할**: 1~5번 수집 소스 통합, **성인 전용 공연 제외 및 순수 가족/어린이/아동 공연 정밀 추출**, 중복 제거
- **출력 파일**: `data/total_family_data.csv`, `data/total_family_data.json` (1,262건)

### 7) `scripts/enrich_total_family_data.py` ⭐ (v2.0 실시간 네이버 검증 & WGS84 좌표 엔진)
- **네이버 실시간 검색 기반 편의시설 검증**:
  - 각 장소별 네이버 실시간 검색 결과 및 플레이스 정보를 스캔하여 `parking:1.0` (주차), `nursing_room:1.0` (수유실), `diaper_table:1.0` (기저귀갈이대), `stroller:1.0` (유모차)를 실검증 부착
- **WGS84 위도(lat) / 경도(lng) 좌표 정밀 추출 및 카카오맵 연동**:
  - 네이버 지적도/플레이스 좌표 데이터에서 위도/경도를 추출하여 `region` 컬럼에 자동 연동
  - 예시: `"서울 광진구 능동로 216 | 위도:37.548305, 경도:126.866500"` → 카카오맵/네이버맵 길찾기 완전 지원
- **LLM 기반 추천 이유 및 아빠 설명 부착**:
  - `recommend_reason`: 실검증 편의시설 기반 아이콘 메시지 (예: *🅿️ 실시간 네이버 검증 주차 가능 & 🍼 수유실·기저귀갈이대 완비로 아기와 방문 최적*)
- **출력 파일**: `data/total_family_data.csv`, `data/total_family_data.json` (최종 1,235건)

---

## 3. 최종 출력 데이터 스키마 (`total_family_data.csv` & `.json`)

| 컬럼명 | 설명 | 데이터 예시 |
|--------|------|------|
| `source_site` | 데이터 출처 | `서울시 우리동네키즈OK / 공공 포털` |
| `category` | 4대 카테고리 | `키즈카페` / `자연친화` / `문화생활` / `가족체험` |
| `place_or_event_name` | 노이즈 제거된 정밀 상호명 | `서울형키즈카페종로구혜화동점` |
| `period` | 운영 기간 | `상시` / `2026-09-01 ~ 2026-10-30` |
| `target_age` | 대상 연령 | `영유아 및 어린이 (0세~7세)` |
| `region` | **주소 + WGS84 위경도 좌표** | `서울 종로구 \| 위도:37.485305, 경도:126.866500` |
| `fee_info` | 이용 요금 | `아동 1,000~3,000원 / 보호자 무료 (공공 가성비)` |
| `description` | LLM 생성 아빠 맞춤 장소 설명 | `[서울형키즈카페종로구혜화동점]는 서울 종로구 지역에 위치한...` |
| `booking_url` | 예약/정보 URL | `https://icare.seoul.go.kr` |
| `ai_tags` | **네이버 실검증 편의시설 태그** | `family:1.0;parking:1.0;nursing_room:1.0;diaper_table:1.0;stroller:1.0;...` |
| `crawled_at` | 수집/보강 시각 | `2026-08-22 18:40:10` |
| `theme_tags` | 테마 태그 | `toddler:1.0;indoor:0.9;play:1.0` |
| `congestion_score` | 혼잡도 점수 (1~5) | `2` |
| `popularity_score` | 인기도 점수 (0~100) | `85` |
| `recommend_reason` | **실검증 LLM 추천 이유** | `🅿️ 실시간 네이버 검증 주차 가능 & 🍼 수유실·기저귀갈이대 완비로 아기와 방문 최적` |
