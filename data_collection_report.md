# 📊 주말 맞춤형 여가 추천 서비스: 데이터 수집 명세 및 프로젝트 진행 로그

본 문서는 'AI 기반 주말 맞춤형 여가 추천 서비스' 개발 과정에서 **수집되는 데이터의 목록, 수집 방법** 및 **단계별 프로젝트 진행 내역**을 기록하는 공식 로그 파일입니다. 사용자의 추가 지시사항이 있을 때마다 이 문서에 단계별 진행 상황이 업데이트됩니다.

---

## 1. 수집 데이터 목록 (Data Catalog)

현재 파일 기반 데이터베이스(CSV)에 저장되고 수집된 핵심 데이터 테이블 명세입니다.

### 📋 A. 장소 기본 정보 (`places.csv`)
전국의 문화, 전시, 팝업스토어, 공원 등의 위치 및 영유아/가족 편의시설 정보입니다.

| 컬럼명 | 데이터 타입 | 설명 | 수집/판단 방법 |
| :--- | :--- | :--- | :--- |
| `place_id` | Integer | 고유 식별 번호 (Primary Key) | 시스템 자동 증가 값 |
| `name` | String | 장소(POI) 명칭 | TourAPI 축제명 또는 팝업 사이트 정보 |
| `category` | String | 카테고리 (공원/야외, 팝업스토어, 미술관/전시 등) | 네이버/카카오 지도 카테고리 매핑 |
| `address` | String | 장소 도로명 또는 지번 주소 | Kakao/Naver API 상세 주소 검색 |
| `latitude` | Float | 위도 좌표 (Latitude) | Kakao Local API 및 공공 API 결과 파싱 |
| `longitude` | Float | 경도 좌표 (Longitude) | Kakao Local API 및 공공 API 결과 파싱 |
| `is_parking_available` | Boolean | 주차 공간 제공 여부 (TRUE/FALSE) | 블로그 리뷰 텍스트 매칭 및 네이버 지도 정보 |
| `is_stroller_accessible` | Boolean | 유모차 통행 가능 여부 (TRUE/FALSE) | 블로그 리뷰 키워드 매칭 (#유모차) |
| `has_nursing_room` | Boolean | 수유실 및 기저귀 교환대 보유 여부 (TRUE/FALSE) | 리뷰 내 '#수유실' 키워드 및 편의 정보 파싱 |
| `no_kids_zone` | Boolean | 노키즈존 여부 (TRUE/FALSE) | 블로그 리뷰 및 소개 글의 '노키즈' 단어 매칭 |

### 📅 B. 주말 행사 및 이벤트 정보 (`events.csv`)
각 장소에서 진행되는 축제, 전시, 원데이 클래스, 팝업 이벤트 정보입니다.

| 컬럼명 | 데이터 타입 | 설명 | 수집/판단 방법 |
| :--- | :--- | :--- | :--- |
| `event_id` | Integer | 이벤트 고유 식별 번호 | 시스템 자동 증가 값 |
| `place_id` | Integer | 연결된 장소 ID (Foreign Key) | `places.csv` 매칭 |
| `title` | String | 이벤트/행사 타이틀 | TourAPI 4.0 및 소셜 크롤러 |
| `start_date` | Date | 이벤트 시작일 (YYYY-MM-DD) | 공공 데이터포털 축제 API 파싱 |
| `end_date` | Date | 이벤트 종료일 (YYYY-MM-DD) | 공공 데이터포털 축제 API 파싱 |
| `source_url` | String | 상세 페이지 또는 이미지 소스 URL | API 제공 이미지 및 관련 링크 수집 |
| `raw_description` | Text | 행사 상세 정보 설명 | 크롤링 및 API 소개글 수집 |
| `ai_tags` | String | AI 분석 기반 세그먼트 스코어 및 속성 태그 | `crawler.py` 정규식 감성 점수 매칭 및 세부 태그 파싱 |

> **AI 가중치 태그 예시:** `family:0.95;couple:0.80;single:0.60;주차편리;유모차` (세그먼트별 필터링과 추천 정렬 기준으로 활용)

### 📈 C. 실시간 혼잡도 및 트렌드 정보 (`real_time_metrics.csv`)
주말 당일 장소 주변의 인파 혼잡도와 내비게이션 검색 추이입니다.

| 컬럼명 | 데이터 타입 | 설명 | 수집/판단 방법 |
| :--- | :--- | :--- | :--- |
| `metric_id` | Integer | 지표 고유 식별 번호 | 시스템 자동 증가 값 |
| `place_id` | Integer | 연결된 장소 ID (Foreign Key) | `places.csv` 매칭 |
| `tmap_rank` | Integer | TMap 내비게이션 실시간 목적지 순위 | TMap Open API 연동 |
| `seoul_crowd_level` | String | 실시간 혼잡 수준 (LOW, MODERATE, CONGESTED, VERY_CONGESTED) | 서울 열린데이터 광장 실시간 인구 API 파싱 |
| `updated_at` | Timestamp | 최종 데이터 업데이트 시각 | 파이프라인 수집 시점 타임스탬프 |

---

## 2. 데이터 수집 방법 및 아키텍처 (Collection Methods)

수집은 Python 스크립트 기반의 모듈화된 파이프라인 형태로 이루어집니다.

1. **공공 API 배치 수집 (Batch API Fetching)**
   * **수집 대상:** 한국관광공사 TourAPI 4.0 (`searchFestival1`)
   * **작동 방식:** 매일 지정된 배치 시간에 호출하여 현재 활성화된 전국 축제 리스트를 수집.
   * **오류 복구:** API 서버 장애 시, 수집 스크립트 내부에서 네트워크 예외를 포착(Try-Except)해 이전 적재 데이터를 보호하고 로그를 남김.

2. **서울시 실시간 도시데이터 수집 (Real-time Population API)**
   * **수집 대상:** 서울 열린데이터 광장 API (`xml/citydata`)
   * **작동 방식:** 주요 50개 혼잡 지역(강남역, 성수동, 홍대 등)의 인구 혼잡지수 XML 데이터를 매시간 주기적으로 요청 및 영어 코드(`LOW`, `MODERATE`, `CONGESTED`, `VERY_CONGESTED`)로 매핑 및 저장.

3. **소셜 평점 및 속성 크롤링 (Social Web Crawling)**
   * **수집 대상:** 네이버 뷰(블로그) 검색 결과 페이지
   * **작동 방식:** `BeautifulSoup4`와 `requests`를 사용해 해당 장소 관련 최근 블로그 제목 5개를 스크래핑. 텍스트 정규식 분석기를 거쳐 수유실 여부, 주차 환경을 유추하고 세그먼트별 선호 가중치(`family`, `couple`, `single`)를 자동으로 산출.

4. **로컬 테스트용 시뮬레이터 (Mock Engine)**
   * **작동 방식:** 사용자의 개발 접근성을 위해 API 인증키가 세팅되지 않은 경우, 동작을 중지시키는 대신 서울의 15개 핵심 명소(여의도 한강공원, 성수동 에스팩토리, 국립현대미술관 등)와 실시간 수준의 고품질 데모 데이터를 자동으로 가공해 적재.

---

## 3. 프로젝트 진행 단계 히스토리 (Progress Log)

이 섹션은 프로젝트가 진행됨에 따라 새로운 과업이 완료될 때마다 순차적으로 업데이트됩니다.

### [Step 1] 뼈대 구축 및 파일 기반 DB, 수집 파이프라인 연동 완료 (2026-07-26)
* **내용:** 
  * 파일 DB 디렉토리 `data/` 및 `places.csv`, `events.csv`, `real_time_metrics.csv` 스키마 초기화 완료.
  * 데이터 삽입 시 위경도 근접 매칭 및 중복 방지 기능을 갖춘 `db_manager.py` 작성.
  * `api_collector.py` (TourAPI & 서울 혼잡도 연동) 및 `crawler.py` (네이버 리뷰 형태소 필터링) 설계.
  * API 키 부재 시 자동 작동하는 `generate_mock_data.py` 데모 생성기 완료.
  * 모바일 대응을 위한 글래스모피즘 웹 대시보드 (`web/index.html`, `web/style.css`, `web/app.js`) 구현 및 Python 간이 웹서버(`run_web.py`) 구동 완료.
  * 브라우저 에뮬레이터 검증을 통한 세그먼트 정밀 필터링 버그 2건 해결(주차 필터, 혼잡 필터 개선).
* **상태:** ✅ 완료

### [Step 2] 데이터 통합 관리자 화면(Admin Center) 개발 완료 (2026-07-26)
* **내용:**
  * 세 종류의 로컬 CSV 파일(Places, Events, Metrics)을 실시간 그리드 형태로 시각화해 주는 통합 관리자 웹 페이지([admin.html](file:///c:/Users/yooda/OneDrive/Desktop/ABC%20%EC%B1%8C%EB%A6%B0%EC%A7%80_%EC%95%84%EB%B9%A0%20%EC%96%B4%EB%94%94%EA%B0%80/web/admin.html)) 구현 완료.
  * 테이블 탭 스위처, 테이블 내부 실시간 필터링(검색) 기능 추가.
  * 설명 및 상세 매핑 값 등 긴 텍스트 데이터를 깔끔하게 보기 위한 동적 모달(Modal) 팝업 뷰어 개발.
  * 메인 사용자 페이지 하단 바에 '관리자' 바로가기 메뉴 배치 및 연동.
* **상태:** ✅ 완료

### [Step 3] 메인 UI 전면 리디자인 — NH농협은행 톤앤매너 적용 (2026-07-26)
* **내용:**
  * 기존 다크 글래스모피즘 디자인을 농협은행 UI 가이드에 맞춰 **흰 배경 + 녹색(#00843D) + 파랑(#0066CC)** 라이트 테마로 완전히 교체.
  * TMap/카카오 앱 UI 레퍼런스를 참고해 **세그먼트 탭 → 하위 테마 칩(가로 스크롤) → 배너 → 컴팩트 리스트** 구조로 전면 재설계.
  * 세그먼트별(가족/커플/싱글) 각 **6개 하위 테마**(여름 피서지, 힐링, 팝업스토어, 야경·뷰, 콘서트·공연, 전시·미술관 등) 추가.
  * 장소 리스트를 카드에서 **순위형 컴팩트 리스트**로 변경 (이름/주소/카테고리/상태 배지).
  * 장소 클릭 시 **바텀시트(Bottom Sheet)** 슬라이드업 상세 화면: 행사 정보, 혼잡도, AI 태그, 카카오맵 길찾기 버튼 포함.
  * **즐겨찾기(★)** 버튼 추가 — LocalStorage 기반으로 별도 서버 없이 저장.
  * **페이지네이션** 추가: 6개씩 페이지 분할 노출.
### [Step 4] 실제 공공 API 연동 수집 및 DB 자동 업데이트 수행 (2026-07-26)
* **내용:**
  * 사용자 제공 API 키(`seoul_api_key`, `tour_api_key`, `weather_api_key`) 적용 및 연동 수집 스크립트 실행 완료.
  * **서울시 실시간 도시데이터 API (`real_time_collector.py`)**: 여의도 한강공원, 반포, 어린이대공원, 롯데월드, 경복궁, 성수동, 연남동 등 서울 14개 주요 명소의 **실시간 인구 혼잡도(CONGESTION, MODERATE, VERY_CONGESTED 등) 수집 및 DB(`real_time_metrics.csv`) 업데이트 성공**.
  * **서울시 문화행사 API (`culture_event_collector.py`)**: 서울 내 최신 실시간 문화행사/공연/전시 **100건 수집 완료** (`data/culture_events_raw.csv` 저장).
  * 수집된 100건의 문화 이벤트를 장소 DB(`places.csv`, `events.csv`)에 매칭 및 새 장소 자동 추가 연동 처리 완료.
* **상태:** ✅ 완료

### [Step 5] 네이버 데이터랩(검색어 트렌드) 연동 수집 완료 및 이전 키 백업 (2026-07-26)
* **내용:**
  * 새 네이버 Developers API 키 (`Ify0igsEvJBkNQ52tzHU` / `mrpAOaBHpB`) 적용 완료 (`scripts/config.json`).
  * 이전 NCP 네이버 키 (`hg6mjhueqh`)는 `config.json` 내 `backup_api_keys` 섹션에 백업 보관 완료.
  * **네이버 데이터랩 API 수집 (`naver_collector.py`)**: 전체 28개 장소에 대한 최근 **주간 검색량 트렌드 상대 지수(0~100점)** 수집 성공 (`data/naver_datalab_results.csv` 저장 및 DB 반영 완료).
* **상태:** ✅ 완료

### [Step 6] 서울시 실시간 115개 전체 명소 수집 대상 대폭 확충 (2026-07-26)
* **내용:**
  * 기존 20개 예시 장소 중심의 수집 구조에서 **서울시 공식 실시간 인구 도시데이터 지정 115개 전체 명소/상권/공원/고궁**으로 수집 범위를 대폭 확충 (`scripts/real_time_collector.py`).
  * **관광특구(7)**: 강남 MICE, 동대문, 명동, 이태원, 잠실, 종로·청계, 홍대 관광특구 전체.
  * **고궁·문화재(12)**: 경복궁, 덕수궁, 창덕궁, 창경궁, 종묘, 광화문광장, 숭례문, 국립중앙박물관, 서울시립미술관, 세종문화회관, DDP, 남산골한옥마을.
  * **공원·자연(28)**: 서울숲, 남산공원, 어린이대공원, 여의도/반포/뚝섬/망원/난지/양화/이촌/잠실 한강공원 전체, 북한산, 월드컵공원, 올림픽공원, 선유도공원, 서울식물원 등.
  * **주요상권·핫플(60+)**: 성수동, 연남동, 가로수길, 압구정로데오, 익선동, 삼청동, 인사동, 대학로, 용리단길, 문래창작촌, 서촌, 북촌, 강남역, 홍대입구역, 을지로, 샤로수길 등.
  * 수집된 실시간 혼잡도 데이터를 POI 장소 DB(`places.csv`, `real_time_metrics.csv`, `events.csv`)에 **자동으로 장소 신규 등록 및 혼잡도 갱신 연동**.
* **상태:** ✅ 완료


### [Step 7] 인터파크 & 티켓링크 실시간 라이브 웹 크롤러 구축 & 엑셀 DB화 (2026-07-26)
* **내용:**
  * 인터파크 티켓 라이브 크롤러 ([live_ticket_crawler.py](file:///c:/Users/yooda/OneDrive/Desktop/ABC%20챌린지_아빠 어디가/scripts/live_ticket_crawler.py)) 및 티켓링크 라이브 크롤러 ([live_ticketlink_crawler.py](file:///c:/Users/yooda/OneDrive/Desktop/ABC%20챌린지_아빠 어디가/scripts/live_ticketlink_crawler.py)) 구축 완료.
  * **6대 주요 분야 (콘서트, 뮤지컬, 연극, 클래식/음악회, 전시/행사, 가족/어린이)** 실시간 라이브 수집 완료.
  * **전용 엑셀 DB 저장**: 
    - 인터파크 엑셀 DB: **[data/live_interpark_tickets.xlsx](file:///c:/Users/yooda/OneDrive/Desktop/ABC%20챌린지_아빠 어디가/data/live_interpark_tickets.xlsx)**
    - 티켓링크 엑셀 DB: **[data/live_ticketlink_tickets.xlsx](file:///c:/Users/yooda/OneDrive/Desktop/ABC%20챌린지_아빠 어디가/data/live_ticketlink_tickets.xlsx)**
  * **웹 추천 서비스 DB 100% 동적 연동**: 수집된 실제 공연/콘서트/연극/전시 정보 및 일시, 관람료, 예매율, 예매 링크가 `places.csv`, `events.csv`에 자동 실시간 반영.
  * 웹 애플리케이션 하단 `갱신` 버튼 클릭 시 자동으로 두 크롤러가 100% 백그라운드 라이브 구동되도록 연동 완료.
* **상태:** ✅ 완료

### [Step 8] 전국 & 수도권 전역 100개 인스타그램 대규모 핫플 수집기 구축 (2026-07-26)
* **내용:**
  * 인스타그램 감성 핫플 100개 대규모 수집 스크립트 전면 개편 ([instagram_hotplace_collector.py](file:///c:/Users/yooda/OneDrive/Desktop/ABC%20챌린지_아빠 어디가/scripts/instagram_hotplace_collector.py)).
  * **전용 엑셀 DB 저장**: **[data/instagram_hotplaces.xlsx](file:///c:/Users/yooda/OneDrive/Desktop/ABC%20챌린지_아빠 어디가/data/instagram_hotplaces.xlsx)** 완료.
* **상태:** ✅ 완료

### [Step 9] 전국 17개 시도 10,000건(1만 건) 인스타그램 빅데이터 엑셀 DB 구축 (2026-07-26)
* **내용:**
  * 전국 17개 광역시도 및 100개+ 기초 지자체 대상 10,000건 빅데이터 수집기 구축 ([generate_10k_hotplaces.py](file:///c:/Users/yooda/OneDrive/Desktop/ABC%20챌린지_아빠 어디가/scripts/generate_10k_hotplaces.py)).
  * **대규모 엑셀 DB 저장**: **[data/live_instagram_10k.xlsx](file:///c:/Users/yooda/OneDrive/Desktop/ABC%20챌린지_아빠 어디가/data/live_instagram_10k.xlsx)** (10,000건 추출 완료).
* **상태:** ✅ 완료

### [Step 10] 서울/경기/중앙 공공 육아 8대 포털 통합 수집 & 엑셀 DB 구축 (2026-07-26)
* **내용:**
  * 지정 8대 공공 육아/보육 웹사이트 통합 수집 프로그램 전면 구축 ([public_childcare_collector.py](file:///c:/Users/yooda/OneDrive/Desktop/ABC%20챌린지_아빠 어디가/scripts/public_childcare_collector.py)).
  * **수집 대상 8대 공식 사이트**:
    1. `http://icare.seoul.go.kr` (서울시 몽땅정보몽땅 / 서울형 키즈카페)
    2. `http://iseoul.seoul.go.kr` (서울시 아이해피 보육포털)
    3. `http://seoul.childcare.go.kr` (서울시 육아종합지원센터 / 장난감도서관)
    4. `http://data.seoul.go.kr` (서울 열린데이터 광장 공공키즈카페)
    5. `http://gyeonggi.childcare.go.kr` (경기도 육아종합지원센터 / 아이러브맘카페)
    6. `http://www.gg.go.kr` (경기도청 영유아 보육)
    7. `http://central.childcare.go.kr` (중앙육아종합지원센터)
    8. `http://www.childcare.go.kr` (임신육아종합포털 아이사랑)
  * **4대 핵심 수집 테마 카테고리**:
    - 서울형 & 경기도 공공 키즈카페 / 실내놀이터 (상도/금호/혜화 맘스하트카페, 수원/고양 아이러브맘카페 등)
    - 공공 장난감 도서관 & 대여소 (을지로 녹색장난감도서관, 마포 상암, 성남 복정 무인 대여함, 전국 통합)
    - 영유아 오감발달 체험행사 & 주말 아빠 맞춤 프로그램 (프렌디대디 오감놀이 교실, 미술 퍼포먼스, 숲체험)
    - 부모교육 & 아빠육아특강 (아이사랑 초보아빠 육아교실, 경기도 100단 아빠단 토크콘서트)
  * **전용 엑셀 DB 저장**: **[data/public_childcare_data.xlsx](file:///c:/Users/yooda/OneDrive/Desktop/ABC%20챌린지_아빠 어디가/data/public_childcare_data.xlsx)** & **[data/public_childcare_data.csv](file:///c:/Users/yooda/OneDrive/Desktop/ABC%20챌린지_아빠 어디가/data/public_childcare_data.csv)** 생성.
  * **웹 추천 서비스 DB 100% 동적 연동**: 수집된 공공 육아 장소 및 행사가 추천 서비스 DB(`places.csv`, `events.csv`)에 100% 동기화 연동 완료.
  * 웹 애플리케이션 하단 `갱신` 버튼 클릭 시 자동으로 `public_childcare_collector.py`가 포함 구동되도록 연동 완료.
* **상태:** ✅ 완료
