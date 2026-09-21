/* ══════════════════════════════
   주말해 앱 JavaScript v2.0
   total_family_data.csv 기반
   ══════════════════════════════ */

// ── 위치 정보 전역 상태 ─────────────────────────────
let userLat = null;
let userLon = null;

// ── 세그먼트별 하위 테마 정의 ──────────────────────────
const THEMES = {
  family: [], // family는 4카테고리 서브탭으로 대체 (하위 테마 칩 없음)
  couple: [
    { id: 'concert',   label: '🎵 공연·콘서트', emoji: '🎵', bannerSub: '함께 즐기는',   bannerTitle: '공연·콘서트', color: 'blue' },
    { id: 'popup',     label: '🎁 팝업스토어',  emoji: '🎁', bannerSub: '감성 데이트',   bannerTitle: '팝업스토어',  color: 'blue' },
    { id: 'exhibition',label: '🖼️ 전시·미술관', emoji: '🖼️', bannerSub: '문화를 즐겨요', bannerTitle: '전시·미술관', color: 'blue' },
    { id: 'outdoor',   label: '🌃 야경·나들이', emoji: '🌃', bannerSub: '로맨틱한 밤',   bannerTitle: '야경·나들이', color: 'blue' },
  ],
  single: [
    { id: 'exhibition',label: '🖼️ 전시·미술관',    emoji: '🖼️', bannerSub: '나만의 시간',    bannerTitle: '전시·미술관',  color: 'purple' },
    { id: 'bookstore', label: '📚 독립서점',        emoji: '📚', bannerSub: '조용한 독서',    bannerTitle: '독립서점',     color: 'purple' },
    { id: 'concert',   label: '🎵 콘서트·공연',     emoji: '🎵', bannerSub: '몰입감 있는',    bannerTitle: '콘서트·공연',  color: 'purple' },
    { id: 'healing',   label: '🌿 조용한 힐링',     emoji: '🌿', bannerSub: '혼자 사색하기',  bannerTitle: '조용한 힐링',  color: 'purple' },
    { id: 'culture',   label: '🏯 역사·문화',       emoji: '🏯', bannerSub: '깊이 있게',      bannerTitle: '역사·문화',    color: 'purple' },
    { id: 'nature',    label: '🌳 자연·공원',       emoji: '🌳', bannerSub: '혼자 걷기 좋은', bannerTitle: '자연·공원',    color: 'purple' },
  ],
};

// 5카테고리 이모지 & 색상
const FAMILY_CAT_CONFIG = {
  '전체':      { emoji: '🏷️', bannerSub: '아이와 함께', bannerTitle: '가족 나들이', color: '' },
  '공공키즈카페': { emoji: '🏛️', bannerSub: '지자체 공식 지정', bannerTitle: '공공 키즈카페', color: '' },
  '사설키즈카페': { emoji: '🏠', bannerSub: '실내 프리미엄 놀이', bannerTitle: '사설 키즈카페', color: '' },
  '자연친화':   { emoji: '🌿', bannerSub: '계곡·공원·수영장·모래놀이', bannerTitle: '자연친화 명소', color: '' },
  '문화생활':   { emoji: '🎭', bannerSub: '배움과 감성', bannerTitle: '문화생활', color: '' },
  '가족체험':   { emoji: '🎯', bannerSub: '미술·농장·박물관', bannerTitle: '가족체험', color: '' },
};

// 혼잡도 한글
const CROWD_LABEL = { LOW: '여유', MODERATE: '보통', CONGESTED: '혼잡', VERY_CONGESTED: '매우 혼잡', UNKNOWN: '정보 없음' };

// ── 전역 상태 ────────────────────────────────────────
let familyData    = [];  // total_family_data.csv 로드 결과
let singleData    = [];  // total_single_data.csv 로드 결과 (싱글매니아 탭 전용)
let mergedData    = [];  // 기존 places+events 병합 (맛집용 폴백)
let coupleData    = [];  // total_couple_data.csv (커플 탭 전용)
let placesData    = [];
let eventsData    = [];
let metricsData   = [];
let congestionData = [];  // 서울시 실시간 도시데이터 인파 혼잡도 관측지점
let currentSeg    = 'family';
let currentThemeIdx = 0;
let currentFamilyCat = '전체'; // 4카테고리 현재 선택
let currentSort   = 'recommend'; // 정렬 기준
let currentPage   = 1;
const PAGE_SIZE   = 8;
let currentView   = 'home';
let favorites     = JSON.parse(localStorage.getItem('nh_favorites') || '[]');

let weatherData   = [];
const REGION_COORDS = {
    "서울": {lat: 37.5665, lon: 126.9780}, "인천": {lat: 37.4563, lon: 126.7052},
    "대전": {lat: 36.3504, lon: 127.3845}, "대구": {lat: 35.8714, lon: 128.6014},
    "광주": {lat: 35.1595, lon: 126.8526}, "부산": {lat: 35.1796, lon: 129.0756},
    "울산": {lat: 35.5384, lon: 129.3114}, "세종": {lat: 36.4800, lon: 127.2890},
    "수원": {lat: 37.2636, lon: 127.0286}, "춘천": {lat: 37.8813, lon: 127.7298},
    "청주": {lat: 36.6424, lon: 127.4890}, "천안": {lat: 36.8151, lon: 127.1139},
    "전주": {lat: 35.8242, lon: 127.1480}, "목포": {lat: 34.8118, lon: 126.3922},
    "포항": {lat: 36.0190, lon: 129.3435}, "창원": {lat: 35.2279, lon: 128.6811},
    "제주": {lat: 33.4996, lon: 126.5312}
};

// ── Haversine 거리 계산 (km) ─────────────────────────
function calcDistance(lat1, lon1, lat2, lon2) {
  if (!lat1 || !lon1 || !lat2 || !lon2 || isNaN(lat2) || isNaN(lon2)) return null;
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat/2)*Math.sin(dLat/2) +
    Math.cos(lat1*Math.PI/180)*Math.cos(lat2*Math.PI/180)*
    Math.sin(dLon/2)*Math.sin(dLon/2);
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
}

function formatDist(km) {
  if (km === null || km === undefined) return '';
  if (km < 1) return Math.round(km * 1000) + 'm';
  return km.toFixed(1) + 'km';
}

// ── 위도/경도 파싱 (region 컬럼) ─────────────────────
function parseLatLon(regionStr) {
  if (!regionStr) return { lat: null, lon: null };
  const latMatch = regionStr.match(/위도[:\s]*([\d.]+)/);
  const lonMatch = regionStr.match(/경도[:\s]*([\d.]+)/);
  return {
    lat: latMatch ? parseFloat(latMatch[1]) : null,
    lon: lonMatch ? parseFloat(lonMatch[1]) : null,
  };
}

// ── 인파 혼잡도: 가장 가까운 관측지점 ────────────────
// 서울시 실시간 도시데이터는 관측지점 121곳에만 제공된다. 전체 장소에
// 값을 만들어 붙이지 않고, 반경 안에 관측지점이 있을 때만 '인근 관측지점
// 기준' 으로 지점명·거리·측정시각을 함께 보여준다.
const CONGEST_RADIUS_KM = 1.0;
const CONGEST_CLASS = {
  '여유': 'LOW', '보통': 'MODERATE', '약간 붐빔': 'CONGESTED', '붐빔': 'VERY_CONGESTED'
};
// '한산한 곳' 정렬용 순서. 관측지점이 없는 항목은 순위를 매기지 않는다.
const CONGEST_ORDER = { '여유': 1, '보통': 2, '약간 붐빔': 3, '붐빔': 4 };

function congestOrderOf(item) {
  const { lat, lon } = parseLatLon(item.region);
  const near = findNearestCongestion(lat, lon);
  return near ? (CONGEST_ORDER[near.area.congest_lvl] || null) : null;
}

// 무료 판정 — 측정된 요금 정보만 근거로 쓴다.
// 티켓링크는 실제 가격을 주며 '0원' 이 무료를 뜻한다(17건).
// 공공 공원이라서 무료일 것이라는 식의 추론은 하지 않는다.
function isFreeItem(item) {
  const f = (item.fee_info || '').trim();
  if (!f) return false;
  if (/무료/.test(f)) return true;
  return /^0\s*원?$/.test(f.replace(/,/g, ''));
}

function findNearestCongestion(lat, lon) {
  if (lat === null || lon === null || !congestionData.length) return null;
  let best = null;
  for (const a of congestionData) {
    const alat = parseFloat(a.lat), alon = parseFloat(a.lng);
    if (!Number.isFinite(alat) || !Number.isFinite(alon)) continue;
    const d = calcDistance(lat, lon, alat, alon);
    if (d === null) continue;
    if (!best || d < best.dist) best = { dist: d, area: a };
  }
  if (!best || best.dist > CONGEST_RADIUS_KM) return null;
  return best;
}

// ── 위치 정보 요청 ───────────────────────────────────
function requestGeolocation(callback) {
  if (!navigator.geolocation) { if (callback) callback(false); return; }
  navigator.geolocation.getCurrentPosition(
    pos => {
      userLat = pos.coords.latitude;
      userLon = pos.coords.longitude;
      document.getElementById('geo-banner').style.display = 'none';
      updateGeoBtnState(true);
      if (callback) callback(true);
      else renderList();
      updateWeatherBanner();
    },
    err => {
      console.warn('위치 정보 접근 불가:', err.message);
      document.getElementById('geo-banner').style.display = 'block';
      updateGeoBtnState(false);
      if (callback) callback(false);
      updateWeatherBanner();
    },
    { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 }
  );
}

function updateGeoBtnState(active) {
  const btn = document.getElementById('location-btn');
  if (!btn) return;
  btn.style.color = active ? 'var(--nh-green)' : '';
  btn.title = active ? `📍 위치 활성화됨 (lat:${userLat?.toFixed(3)})` : '위치 허용';
}

// ── RecommendScore 계산 ──────────────────────────────
// scoreType: 'family' (기본) 또는 'single'
function calcRecommendScore(item, scoreType = 'family') {
  // 1) 기본 점수 — scoreType 에 따라 family 또는 single ai_tags 값 사용
  const baseScore = parseScoreByKey(item.ai_tags, scoreType);

  // 2) popularity (0~100 → 0~2)
  const popScore = ((parseFloat(item.popularity_score) || 50) / 100) * 2.0;

  // 3) freshness bonus (기간 내 진행 중)
  let freshness = 0;
  if (item.period && item.period !== '상시') {
    const parts = item.period.split('~');
    if (parts.length === 2) {
      const end = new Date(parts[1].trim());
      const now = new Date();
      const diffDays = (end - now) / (1000 * 60 * 60 * 24);
      if (diffDays >= 0 && diffDays <= 7) freshness = 1.5; // 마감 7일 이내
      else if (diffDays >= 0) freshness = 1.0;             // 진행 중
    }
  } else if (item.period === '상시') {
    freshness = 0.8;
  }

  // 4) distance bonus
  let distBonus = 0;
  if (userLat && userLon) {
    const { lat, lon } = parseLatLon(item.region);
    const dist = calcDistance(userLat, userLon, lat, lon);
    if (dist !== null) {
      if (dist <= 5)  distBonus = 2.0;
      else if (dist <= 15) distBonus = 1.0;
      else if (dist <= 30) distBonus = 0.5;
    }
  }

  // 5) congestion penalty — 서울시 실시간 관측값이 있을 때만 적용한다.
  const congOrder = congestOrderOf(item);
  const penalty = congOrder === null ? 0 : congOrder * 0.2;

  // 6) free bonus
  const freeBonus = isFreeItem(item) ? 0.5 : 0;

  // 7) instagram hot bonus
  const instaBonus = /Instagram 핫플/.test(item.source_site || '') ? 0.3 : 0;

  return (baseScore * 3.0) + popScore + freshness + distBonus - penalty + freeBonus + instaBonus;
}

// ai_tags 에서 특정 키 점수 파싱 (예: 'family', 'single', 'couple')
function parseScoreByKey(aiTags, key) {
  if (!aiTags) return 0.1;
  const m = String(aiTags).match(new RegExp(key + ':([\\d.]+)'));
  return m ? parseFloat(m[1]) : 0.1;
}

function parseFamilyScore(aiTags) {
  return parseScoreByKey(aiTags, 'family');
}

// ── 초기화 ───────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initDate();
  initEvents();
  loadData();
  // 조용하게 위치 먼저 시도
  requestGeolocation(ok => {
    if (!ok) document.getElementById('geo-banner').style.display = 'block';
  });
});

function initDate() {
  const el = document.getElementById('header-date');
  if (!el) return;
  const d = new Date();
  el.textContent = d.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric', weekday: 'short' });
}

// ── CSV 파싱 ─────────────────────────────────────────
function parseCSV(text) {
  const lines = text.split('\n');
  if (!lines.length || !lines[0].trim()) return [];
  const headers = splitCSVLine(lines[0]);
  return lines.slice(1).filter(l => l.trim()).map(l => {
    const vals = splitCSVLine(l);
    const row = {};
    headers.forEach((h, i) => row[h.trim()] = (vals[i] || '').trim());
    return row;
  });
}
function splitCSVLine(line) {
  const r = []; let inQ = false; let cur = '';
  for (const ch of line) {
    if (ch === '"') inQ = !inQ;
    else if (ch === ',' && !inQ) { r.push(cur); cur = ''; }
    else cur += ch;
  }
  r.push(cur);
  return r;
}

// ── 데이터 로드 ──────────────────────────────────────
async function loadData() {
  try {
    // 1) total_family_data.csv 로드 (가족 탭 전용) - 캐시 방지
    const familyRes = await fetch('../data/total_family_data.csv?t=' + Date.now());
    const familyText = await familyRes.text();
    familyData = parseCSV(familyText);

    // 2) 커플/싱글/맛집 탭용 기존 데이터 로드 (파일 없으면 빈 배열)
    try {
      const [p, e, m] = await Promise.all([
        fetch('../data/places.csv?t=' + Date.now()).then(r => r.ok ? r.text() : ''),
        fetch('../data/events.csv?t=' + Date.now()).then(r => r.ok ? r.text() : ''),
        fetch('../data/real_time_metrics.csv?t=' + Date.now()).then(r => r.ok ? r.text() : ''),
      ]);
      placesData  = p ? parseCSV(p) : [];
      eventsData  = e ? parseCSV(e) : [];
      metricsData = m ? parseCSV(m) : [];
    } catch(e) { console.warn("레거시 데이터 로드 스킵:", e); }

    // 2-1. 서울시 실시간 인파 혼잡도 (관측지점 121곳). 없으면 조용히 건너뛴다.
    try {
      const cRes = await fetch('../data/seoul_congestion.csv?t=' + Date.now());
      if (cRes.ok) congestionData = parseCSV(await cRes.text());
    } catch(e) { console.warn("혼잡도 데이터 로드 스킵:", e); }

    // 2-2. 커플 통합 데이터 (커플 탭 전용). 없으면 조용히 건너뛴다.
    try {
      const cpRes = await fetch('../data/total_couple_data.csv?t=' + Date.now());
      if (cpRes.ok) coupleData = parseCSV(await cpRes.text());
    } catch (e) { console.warn('커플 데이터 로드 스킵:', e); }

    // 2-3. 싱글매니아 통합 데이터 (싱글 탭 전용). 없으면 조용히 건너뛴다.
    try {
      const singleRes = await fetch('../data/total_single_data.csv?t=' + Date.now());
      if (singleRes.ok) singleData = parseCSV(await singleRes.text());
    } catch (e) { console.warn('싱글 데이터 로드 스킵:', e); }

    // 3) 주간 날씨 로드
    try {
      const wRes = await fetch('../data/weather.csv?t=' + Date.now());
      if (wRes.ok) weatherData = parseCSV(await wRes.text());
    } catch(e) { console.warn("날씨 데이터 로드 실패", e); }

    mergeData();

    updateSortChipAvailability();
    renderThemeChips();
    renderList();
    updateTicker();
    updateFavBadge();
    updateWeatherBanner();
  } catch (err) {
    console.error(err);
    document.getElementById('place-list').innerHTML = `
      <div class="no-results">
        <i class="fa-solid fa-circle-exclamation" style="color:#E53935"></i>
        <p>데이터 로드 실패.<br>python run_web.py 로 서버를 실행한 후 새로고침 해주세요.</p>
      </div>`;
  }
}

function mergeData() {
  mergedData = placesData.map(pl => {
    const ev = eventsData.find(e => e.place_id === pl.place_id) || {};
    const mt = metricsData.find(m => m.place_id === pl.place_id) || {};
    let scores = { family: 0.1, couple: 0.1, single: 0.1 };
    let tags = [];
    if (ev.ai_tags) {
      ev.ai_tags.split(';').forEach(part => {
        if (part.startsWith('family:')) scores.family = parseFloat(part.split(':')[1]) || 0;
        else if (part.startsWith('couple:')) scores.couple = parseFloat(part.split(':')[1]) || 0;
        else if (part.startsWith('single:')) scores.single = parseFloat(part.split(':')[1]) || 0;
        else if (part.trim()) tags.push(part.trim());
      });
    }
    // 측정값이 없으면 '여유'(LOW)로 단정하지 않고 UNKNOWN 으로 둔다.
    return { ...pl, ev, scores, tags, crowd: mt.seoul_crowd_level || 'UNKNOWN',
             crowd_measured_at: mt.updated_at || '', tmap_rank: parseInt(mt.tmap_rank) || 999 };
  });
}

// ── 정렬 칩 가용성 ───────────────────────────────────
// 근거 데이터가 없는 정렬 옵션은 숨긴다. 눌러도 빈 목록만 나오는 버튼을
// 남겨두면 사용자는 '결과가 없다' 가 아니라 '고장났다' 로 받아들인다.
function updateSortChipAvailability() {
  const rules = [
    ['sort-free',  familyData.some(isFreeItem)],
    ['sort-quiet', congestionData.length > 0],
  ];
  for (const [id, ok] of rules) {
    const el = document.getElementById(id);
    if (el) el.style.display = ok ? '' : 'none';
  }
}

// ── 테마 칩 렌더링 ───────────────────────────────────
function renderThemeChips() {
  const isFamilyTab = currentSeg === 'family';
  const themeWrap = document.getElementById('theme-chips-wrap');
  const familyCatTabs = document.getElementById('family-category-tabs');
  const sortBar = document.getElementById('sort-bar');

  if (isFamilyTab) {
    // family: 4카테고리 탭 + 정렬 칩 보임, 기존 테마 칩 숨김
    themeWrap.style.display = 'none';
    familyCatTabs.style.display = 'flex';
    sortBar.style.display = 'flex';
    // 배너 업데이트
    const cfg = FAMILY_CAT_CONFIG[currentFamilyCat] || FAMILY_CAT_CONFIG['전체'];
    document.getElementById('banner-sub').textContent = cfg.bannerSub;
    document.getElementById('banner-title').textContent = cfg.bannerTitle;
    document.getElementById('banner-emoji').textContent = cfg.emoji;
    document.getElementById('theme-banner').className = 'theme-banner';
  } else {
    // 다른 탭: 기존 테마 칩 보임
    familyCatTabs.style.display = 'none';
    sortBar.style.display = currentSeg === 'food' ? 'none' : 'flex';
    themeWrap.style.display = 'block';
    const themes = THEMES[currentSeg];
    const wrap = document.getElementById('theme-chips');
    wrap.innerHTML = themes.map((t, i) =>
      `<button class="theme-chip${i === currentThemeIdx ? ' active' : ''}" data-idx="${i}">${t.label}</button>`
    ).join('');
    wrap.querySelectorAll('.theme-chip').forEach(btn => {
      btn.addEventListener('click', () => {
        currentThemeIdx = parseInt(btn.dataset.idx);
        currentPage = 1;
        renderThemeChips();
        renderList();
      });
    });
    // 배너 업데이트
    const t = themes[currentThemeIdx];
    if (t) {
      document.getElementById('banner-sub').textContent = t.bannerSub;
      document.getElementById('banner-title').textContent = t.bannerTitle;
      document.getElementById('banner-emoji').textContent = t.emoji;
      document.getElementById('theme-banner').className = 'theme-banner' + (t.color ? ' ' + t.color : '');
    }
  }
}

// ── 리스트 렌더링 ────────────────────────────────────
function renderList() {
  const container = document.getElementById('place-list');
  const paginBar  = document.getElementById('pagination-bar');
  const query     = (document.getElementById('search-input')?.value || '').toLowerCase().trim();

  let list = [];

  if (currentSeg === 'family') {
    // ★ 가족 탭: total_family_data.csv 사용
    list = [...familyData];

    // 4카테고리 필터
    if (currentFamilyCat !== '전체') {
      list = list.filter(item => item.category === currentFamilyCat);
    }

    // 검색 필터
    if (query) {
      list = list.filter(item =>
        (item.place_or_event_name || '').toLowerCase().includes(query) ||
        (item.region || '').toLowerCase().includes(query) ||
        (item.description || '').toLowerCase().includes(query) ||
        (item.ai_tags || '').toLowerCase().includes(query)
      );
    }

    // 거리 계산
    list = list.map(item => {
      const { lat, lon } = parseLatLon(item.region);
      const dist = calcDistance(userLat, userLon, lat, lon);
      return { ...item, _lat: lat, _lon: lon, _dist: dist };
    });

    // 정렬 적용
    list = applySortFamily(list);

  } else if (currentSeg === 'food') {
    // 맛집 탭: 기존 mergedData 사용
    list = [...mergedData].filter(p => p.category && p.category.startsWith('맛집/'));
    const theme = THEMES.food[currentThemeIdx];
    if (theme && theme.id !== 'food_near') {
      const allowedCats = { food_korean:['맛집/한식'], food_western:['맛집/양식'], food_japanese:['맛집/일식'], food_cafe:['맛집/카페·디저트'] }[theme.id] || [];
      if (allowedCats.length) {
        const filtered = list.filter(p => allowedCats.includes(p.category));
        if (filtered.length) list = filtered;
      }
    }
    list = list.map(p => ({ ...p, _dist: calcDistance(userLat, userLon, parseFloat(p.latitude), parseFloat(p.longitude)) }));
    if (theme?.id === 'food_near' && userLat) {
      list.sort((a, b) => (a._dist ?? 999) - (b._dist ?? 999));
    } else {
      list.sort((a, b) => b.scores.family - a.scores.family);
    }
    if (query) {
      list = list.filter(p => (p.name || '').toLowerCase().includes(query) || (p.address || '').toLowerCase().includes(query));
    }
  } else if (currentSeg === 'couple') {
    // 데이터가 없으면 기존 동작으로 조용히 폴백한다 (화면이 깨지지 않게)
    if (!coupleData.length) {
      list = [...mergedData];
      list.sort((a, b) => b.scores.couple - a.scores.couple);
    } else {
      list = [...coupleData];

      // 테마 필터 — theme_ids 는 ';' 구분 다중값이다
      const theme = THEMES.couple[currentThemeIdx];
      if (theme) {
        const filtered = list.filter(item =>
          (item.theme_ids || '').split(';').includes(theme.id));
        if (filtered.length) list = filtered;
      }

      // 검색 필터 (family 분기와 같은 방식)
      if (query) {
        list = list.filter(item =>
          (item.place_or_event_name || '').toLowerCase().includes(query) ||
          (item.region || '').toLowerCase().includes(query) ||
          (item.description || '').toLowerCase().includes(query) ||
          (item.ai_tags || '').toLowerCase().includes(query)
        );
      }

      // 거리 계산 — family 분기의 map 패턴을 그대로 따를 것
      list = list.map(item => {
        const { lat, lon } = parseLatLon(item.region);
        return { ...item, _lat: lat, _lon: lon,
                 _dist: calcDistance(userLat, userLon, lat, lon) };
      });

      list = applySortCouple(list);
    }
  } else if (currentSeg === 'single') {
    // 싱글매니아 탭: total_single_data.csv 전용 (없으면 빈 화면)
    list = [...singleData];

    // 테마 필터 — THEMES.single의 theme.id → 카테고리명 매핑
    const SINGLE_THEME_CAT = {
      exhibition: '전시·미술관',
      bookstore:  '독립서점',
      concert:    '콘서트·공연',
      healing:    '조용한힐링',
      culture:    '역사·문화',
      nature:     '자연·공원',
    };
    const singleTheme = THEMES.single[currentThemeIdx];
    if (singleTheme && SINGLE_THEME_CAT[singleTheme.id]) {
      const filtered = list.filter(item => item.category === SINGLE_THEME_CAT[singleTheme.id]);
      if (filtered.length) list = filtered;
    }

    // 검색 필터
    if (query) {
      list = list.filter(item =>
        (item.place_or_event_name || '').toLowerCase().includes(query) ||
        (item.region || '').toLowerCase().includes(query) ||
        (item.description || '').toLowerCase().includes(query) ||
        (item.ai_tags || '').toLowerCase().includes(query)
      );
    }

    // 거리 계산
    list = list.map(item => {
      const { lat, lon } = parseLatLon(item.region);
      return { ...item, _lat: lat, _lon: lon,
               _dist: calcDistance(userLat, userLon, lat, lon) };
    });

    // 정렬 (family와 같은 로직, 단 single 점수 기준 추천순)
    list = applySortFamily(list, 'single');

  } else {
    // food 탭 등 나머지: 기존 mergedData 사용 (맛집 등)
    list = [...mergedData].filter(p => p.category && p.category.startsWith('맛집/'));
  }

  // 페이지네이션
  const total = list.length;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  if (currentPage > totalPages) currentPage = totalPages;
  const paged = list.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  // 렌더
  if (!paged.length) {
    container.innerHTML = `
      <div class="no-results">
        <i class="fa-solid fa-magnifying-glass"></i>
        <p>해당 조건에 맞는 장소가 없어요.<br>다른 카테고리나 정렬을 선택해 보세요.</p>
      </div>`;
    paginBar.hidden = true;
    return;
  }

  if (currentSeg === 'couple' && coupleData.length) {
    container.innerHTML = paged.map((item, idx) => renderCoupleCard(item, idx)).join('');
    // 즐겨찾기 key 는 family 와 동일하게 encodeURIComponent(place_or_event_name) 이므로 toggleFavFamily 재사용
    container.querySelectorAll('.fav-btn').forEach(btn => {
      btn.addEventListener('click', e => { e.stopPropagation(); toggleFavFamily(btn.dataset.key, btn); });
    });
    container.querySelectorAll('.place-item').forEach(item => {
      item.addEventListener('click', () => openDetailCouple(item.dataset.key));
      item.addEventListener('keydown', e => { if (e.key === 'Enter') openDetailCouple(item.dataset.key); });
    });
  } else if (currentSeg === 'family' || currentSeg === 'single') {
    container.innerHTML = paged.map((item, idx) => renderFamilyCard(item, idx)).join('');
    // 이벤트 바인딩
    container.querySelectorAll('.fav-btn').forEach(btn => {
      btn.addEventListener('click', e => { e.stopPropagation(); toggleFavFamily(btn.dataset.key, btn); });
    });
    container.querySelectorAll('.place-item').forEach(item => {
      item.addEventListener('click', () => openDetailFamily(item.dataset.key));
      item.addEventListener('keydown', e => { if (e.key === 'Enter') openDetailFamily(item.dataset.key); });
    });
  } else {
    container.innerHTML = paged.map((pl, idx) => renderLegacyCard(pl, idx)).join('');
    container.querySelectorAll('.fav-btn').forEach(btn => {
      btn.addEventListener('click', e => { e.stopPropagation(); toggleFav(btn.dataset.pid, btn); });
    });
    container.querySelectorAll('.place-item').forEach(item => {
      item.addEventListener('click', () => openDetail(item.dataset.id));
      item.addEventListener('keydown', e => { if (e.key === 'Enter') openDetail(item.dataset.id); });
    });
  }

  if (totalPages > 1) {
    paginBar.hidden = false;
    document.getElementById('page-info').textContent = `${currentPage} / ${totalPages}`;
    document.getElementById('page-prev').disabled = currentPage <= 1;
    document.getElementById('page-next').disabled = currentPage >= totalPages;
  } else {
    paginBar.hidden = true;
  }
}

// ── 정렬 로직 (family/single 탭 공용) ──────────────────
// scoreType: 'family' (기본) 또는 'single'
function applySortFamily(list, scoreType = 'family') {
  switch (currentSort) {
    case 'recommend':
      return list.map(item => ({ ...item, _score: calcRecommendScore(item, scoreType) }))
                 .sort((a, b) => b._score - a._score);
    case 'popular':
      return list.sort((a, b) => (parseFloat(b.popularity_score) || 0) - (parseFloat(a.popularity_score) || 0));
    case 'deadline':
      return list.filter(item => item.period && item.period !== '상시')
        .sort((a, b) => {
          const endA = new Date((a.period.split('~')[1] || '').trim());
          const endB = new Date((b.period.split('~')[1] || '').trim());
          return endA - endB;
        }).concat(list.filter(item => !item.period || item.period === '상시'));
    case 'distance':
      if (!userLat) return list; // 위치 없으면 그대로
      return list.sort((a, b) => (a._dist ?? 99999) - (b._dist ?? 99999));
    case 'quiet': {
      // 서울시 실시간 관측값으로 정렬한다. 예전에는 congestion_score
      // (전 건 공란) || 5 라서 전 항목이 같은 값이 되어 정렬이 무작동이었다.
      // 관측지점이 없는 항목은 순서를 만들지 않고 뒤로 보낸다.
      const withLv = [], without = [];
      for (const it of list) {
        const o = congestOrderOf(it);
        (o === null ? without : withLv).push({ it, o });
      }
      withLv.sort((a, b) => a.o - b.o);
      return withLv.map(x => x.it).concat(without.map(x => x.it));
    }
    case 'free':
      return list.filter(isFreeItem).concat(list.filter(it => !isFreeItem(it)));
    default:
      return list;
  }
}

// ── 카드 렌더 (family 탭, total_family_data.csv) ─────
function renderFamilyCard(item, idx) {
  const rank = (currentPage - 1) * PAGE_SIZE + idx + 1;
  const key = encodeURIComponent(item.place_or_event_name || String(idx));
  const isFav = favorites.includes(key);

  // 카테고리 이모지
  const catEmoji = { '공공키즈카페': '🏛️', '사설키즈카페': '🏠', '키즈카페': '🏠', '자연친화': '🌿', '문화생활': '🎭', '가족체험': '🎯' }[item.category] || '📍';
  const catClass = { '공공키즈카페': 'cat-public', '사설키즈카페': 'cat-kids', '키즈카페': 'cat-kids', '자연친화': 'cat-nature', '문화생활': 'cat-culture', '가족체험': 'cat-experience' }[item.category] || '';

  // 배지 생성
  const badges = [];
  const familyScore = parseFamilyScore(item.ai_tags);
  if (familyScore >= 0.9) badges.push('<span class="badge-pill green">👨‍👩‍👧 가족 최적</span>');
  if (isFreeItem(item)) badges.push('<span class="badge-pill free">💚 무료</span>');
  if (/Instagram/.test(item.source_site || '')) badges.push('<span class="badge-pill insta">📸 인스타 핫플</span>');

  // 마감 임박 배지
  if (item.period && item.period !== '상시') {
    const parts = item.period.split('~');
    if (parts.length === 2) {
      const end = new Date(parts[1].trim());
      const diff = (end - new Date()) / (1000 * 60 * 60 * 24);
      if (diff >= 0 && diff <= 7) badges.push(`<span class="badge-pill soon">⏰ 마감 ${Math.ceil(diff)}일</span>`);
    }
  }

  // 인터파크/티켓링크 배지
  if (/인터파크|티켓링크/.test(item.source_site || '')) badges.push('<span class="badge-pill ticket">🎫 예매 가능</span>');

  // 거리 배지
  if (item._dist !== null && item._dist !== undefined) {
    const distLabel = item._dist <= 5 ? `🟢 ${formatDist(item._dist)}` : item._dist <= 15 ? `🟡 ${formatDist(item._dist)}` : `🔵 ${formatDist(item._dist)}`;
    badges.push(`<span class="badge-pill dist">${distLabel}</span>`);
  }

  // 혼잡도 점 — 측정값 없으면 UNKNOWN
  const crowdRaw = parseInt(item.congestion_score);
  const crowdScore = Number.isFinite(crowdRaw) ? crowdRaw : null;
  const crowdClass = crowdScore === null ? 'UNKNOWN'
    : crowdScore <= 1 ? 'LOW' : crowdScore <= 2 ? 'MODERATE' : crowdScore <= 3 ? 'CONGESTED' : 'VERY_CONGESTED';

  // 지역명 (region에서 위도/경도 제거)
  const regionDisplay = (item.region || '').split('|')[0].trim();

  return `
  <div class="place-item" data-key="${key}" role="button" tabindex="0" aria-label="${item.place_or_event_name} 상세 보기">
    <span class="place-item__rank${rank <= 3 ? ' top' : ''}">${rank}</span>
    <div class="place-item__info">
      <div class="place-item__name">${item.place_or_event_name || '-'}</div>
      <div class="place-item__meta">
        <span class="place-item__addr">${regionDisplay}</span>
        <span class="place-item__cat">${item.category || ''}</span>
        <span class="crowd-dot ${crowdClass}" title="혼잡도: ${CROWD_LABEL[crowdClass] || ''}"></span>
      </div>
      <div class="place-item__badges">${badges.join('')}</div>
    </div>
    <div class="place-item__thumb ${catClass}">
      ${catEmoji}
      <button class="fav-btn${isFav ? ' active' : ''}" data-key="${key}" aria-label="즐겨찾기">
        <i class="fa-${isFav ? 'solid' : 'regular'} fa-star"></i>
      </button>
    </div>
  </div>`;
}

// ── 레거시 카드 렌더 (커플/싱글/맛집) ───────────────
const CAT_EMOJI = {
  '공원/야외': '🌳', '팝업스토어': '🎁', '미술관/전시': '🖼️',
  '복합문화공간': '🏢', '문화유산/역사': '🏯', '박물관/전시': '🏛️',
  '도서/문화': '📚', '카페/식음': '☕', '테마파크': '🎢',
  '맛집/한식': '🍲', '맛집/양식': '🍝', '맛집/일식': '🍣',
  '맛집/카페·디저트': '☕', '맛집/아시안': '🍜', '맛집/기타': '🍽️',
};

function renderLegacyCard(pl, idx) {
  const rank = (currentPage - 1) * PAGE_SIZE + idx + 1;
  const isFav = favorites.includes(pl.place_id);
  const isFood = pl.category?.startsWith('맛집/');
  const emoji = CAT_EMOJI[pl.category] || (isFood ? '🍽️' : '📍');
  const pills = buildPillsLegacy(pl, isFood);
  return `
  <div class="place-item" data-id="${pl.place_id}" role="button" tabindex="0" aria-label="${pl.name} 상세 보기">
    <span class="place-item__rank${rank <= 3 ? ' top' : ''}">${rank}</span>
    <div class="place-item__info">
      <div class="place-item__name">${pl.name}</div>
      <div class="place-item__meta">
        <span class="place-item__addr">${pl.address || '-'}</span>
        <span class="place-item__cat">${pl.category || ''}</span>
        <span class="crowd-dot ${pl.crowd}" title="${CROWD_LABEL[pl.crowd] || ''}"></span>
      </div>
      <div class="place-item__badges">${pills}</div>
    </div>
    <div class="place-item__thumb">
      ${emoji}
      <button class="fav-btn${isFav ? ' active' : ''}" data-pid="${pl.place_id}" aria-label="즐겨찾기">
        <i class="fa-${isFav ? 'solid' : 'regular'} fa-star"></i>
      </button>
    </div>
  </div>`;
}

function buildPillsLegacy(pl, isFood = false) {
  const pills = [];
  if (isFood) {
    if (pl._dist !== undefined && pl._dist !== null) pills.push(`<span class="badge-pill food-dist">📍 ${formatDist(pl._dist)}</span>`);
    if (pl.no_kids_zone === 'TRUE') pills.push('<span class="badge-pill red">🚫 노키즈존</span>');
    if (pl.is_parking_available === 'TRUE') pills.push('<span class="badge-pill green">🅿 주차가능</span>');
  } else {
    if (pl.is_parking_available === 'TRUE')   pills.push('<span class="badge-pill green">🅿 주차가능</span>');
    if (pl.is_stroller_accessible === 'TRUE') pills.push('<span class="badge-pill green">👶 유모차</span>');
    if (pl.has_nursing_room === 'TRUE')       pills.push('<span class="badge-pill blue">🍼 수유실</span>');
    if (pl.no_kids_zone === 'TRUE')           pills.push('<span class="badge-pill red">🚫 노키즈존</span>');
  }
  const crowdClass = { LOW:'green', MODERATE:'orange', CONGESTED:'orange', VERY_CONGESTED:'red' }[pl.crowd] || 'gray';
  pills.push(`<span class="badge-pill ${crowdClass}">${CROWD_LABEL[pl.crowd] || pl.crowd}</span>`);
  return pills.join('');
}

// ── 즐겨찾기 (통합 key = encoded place_or_event_name) ──
function toggleFavFamily(key, btn) {
  const idx = favorites.indexOf(key);
  let isNowFav = false;
  if (idx >= 0) {
    favorites.splice(idx, 1);
    isNowFav = false;
  } else {
    favorites.push(key);
    isNowFav = true;
  }
  localStorage.setItem('nh_favorites', JSON.stringify(favorites));

  // 화면 내의 동일한 data-key 버튼 일괄 상태 갱신
  try {
    document.querySelectorAll(`.fav-btn[data-key="${CSS.escape(key)}"]`).forEach(b => {
      if (isNowFav) {
        b.classList.add('active');
        b.querySelector('i').className = 'fa-solid fa-star';
      } else {
        b.classList.remove('active');
        b.querySelector('i').className = 'fa-regular fa-star';
      }
    });
  } catch (e) {}

  updateFavBadge();
  updateTicker();
  if (currentView === 'fav') renderFavPage();
}

// ── 즐겨찾기 (레거시, key = place_id) ──────────────
function toggleFav(pid, btn) {
  const idx = favorites.indexOf(pid);
  let isNowFav = false;
  if (idx >= 0) {
    favorites.splice(idx, 1);
    isNowFav = false;
  } else {
    favorites.push(pid);
    isNowFav = true;
  }
  localStorage.setItem('nh_favorites', JSON.stringify(favorites));

  try {
    document.querySelectorAll(`.fav-btn[data-pid="${CSS.escape(pid)}"]`).forEach(b => {
      if (isNowFav) {
        b.classList.add('active');
        b.querySelector('i').className = 'fa-solid fa-star';
      } else {
        b.classList.remove('active');
        b.querySelector('i').className = 'fa-regular fa-star';
      }
    });
  } catch (e) {}

  updateFavBadge();
  updateTicker();
  if (currentView === 'fav') renderFavPage();
}

function updateFavBadge() {
  const badge = document.getElementById('bnav-fav-badge');
  if (!badge) return;
  const count = favorites.length;
  if (count > 0) {
    badge.textContent = count > 99 ? '99+' : count;
    badge.removeAttribute('hidden');
  } else {
    badge.setAttribute('hidden', '');
  }
}

// ══════════════════════════════════════════
// ★ 상세 바텀시트 (family / single / couple 통합 조회)
// ══════════════════════════════════════════
function openDetailFamily(key) {
  const item = familyData.find(d => encodeURIComponent(d.place_or_event_name) === key)
            || singleData.find(d => encodeURIComponent(d.place_or_event_name) === key)
            || coupleData.find(d => encodeURIComponent(d.place_or_event_name) === key);
  if (!item) return;

  const catEmoji = getCategoryEmoji(item.category);
  const { lat, lon } = parseLatLon(item.region);
  const dist = calcDistance(userLat, userLon, lat, lon);
  const isFav = favorites.includes(key);
  const regionDisplay = (item.region || '').split('|')[0].trim();

  // 예매 버튼 여부
  const hasTicket = /인터파크|티켓링크/.test(item.source_site || '') || (item.booking_url && item.booking_url.startsWith('http'));
  const ticketUrl = item.booking_url || item.source_site || '';

  // AI 태그 파싱
  const tagParts = (item.ai_tags || '').split(';').filter(t => !/(family|couple|single|baby|father|mother):/i.test(t) && t.trim());

  // 혼잡도 — 서울시 실시간 도시데이터 관측지점이 반경 안에 있을 때만 표시한다.
  // congestion_score 컬럼은 측정 소스가 없어 전 건 공란이므로 쓰지 않는다.
  const near = findNearestCongestion(lat, lon);
  const crowdClass = near ? (CONGEST_CLASS[near.area.congest_lvl] || 'UNKNOWN') : 'UNKNOWN';

  // 카카오맵 연동
  const searchName = (regionDisplay + ' ' + (item.place_or_event_name || '')).trim();
  const mapUrl = `https://map.kakao.com/link/search/${encodeURIComponent(searchName)}`;

  document.getElementById('sheet-body').innerHTML = `
    <div class="detail-cat">${item.category || '장소'}</div>
    <div class="detail-name">${catEmoji} ${item.place_or_event_name || '-'}</div>
    <div class="detail-addr"><i class="fa-solid fa-location-dot" style="color:var(--nh-green)"></i>${regionDisplay}</div>
    <div class="detail-badges">
      ${isFreeItem(item) ? '<span class="badge-pill free">💚 무료</span>' : ''}
      ${dist !== null ? `<span class="badge-pill dist">📍 ${formatDist(dist)}</span>` : ''}
      ${/인스타|Instagram/.test(item.source_site || '') ? '<span class="badge-pill insta">📸 인스타 핫플</span>' : ''}
      ${hasTicket ? '<span class="badge-pill ticket">🎫 예매 가능</span>' : ''}
    </div>

    <div class="detail-divider"></div>
    <div class="detail-section-title"><i class="fa-solid fa-circle-info"></i> 상세 정보</div>
    <div class="detail-event-box">
      <div class="detail-event-title">💰 이용 요금: ${item.fee_info || '정보 없음'}</div>
      <div class="detail-event-desc">${item.description || '설명 정보가 없습니다.'}</div>
      ${item.period ? `<div class="detail-event-date"><i class="fa-regular fa-calendar"></i> 기간: ${item.period}</div>` : ''}
      ${item.target_age ? `<div class="detail-event-date"><i class="fa-solid fa-child"></i> 대상: ${item.target_age}</div>` : ''}
    </div>

    <div class="detail-divider"></div>
    <div class="detail-section-title"><i class="fa-solid fa-tower-broadcast"></i> 인파 현황</div>
    ${dist !== null ? `<div class="crowd-row"><span class="crowd-label">내 위치에서</span><span class="crowd-val LOW">📍 ${formatDist(dist)}</span></div>` : ''}
    <div class="crowd-row">
      <span class="crowd-label">인파 혼잡도</span>
      <span class="crowd-val ${crowdClass}">${near ? near.area.congest_lvl : '정보 없음'}</span>
    </div>
    ${near ? `
    <div class="crowd-row">
      <span class="crowd-label">관측지점</span>
      <span class="crowd-val LOW" style="font-weight:500">${near.area.area_nm} · ${formatDist(near.dist)}</span>
    </div>
    ${near.area.ppltn_min ? `<div class="crowd-row"><span class="crowd-label">추정 인원</span><span class="crowd-val LOW" style="font-weight:500">${Number(near.area.ppltn_min).toLocaleString()}~${Number(near.area.ppltn_max).toLocaleString()}명</span></div>` : ''}
    ${near.area.rate_age_0_9 ? `<div class="crowd-row"><span class="crowd-label">0~9세 비율</span><span class="crowd-val LOW" style="font-weight:500">${near.area.rate_age_0_9}%</span></div>` : ''}
    <div class="crowd-row">
      <span class="crowd-label" style="font-size:11px;opacity:.7">서울시 실시간 도시데이터 · ${near.area.measured_at || ''} 측정</span>
      <span></span>
    </div>` : `
    <div class="crowd-row">
      <span class="crowd-label" style="font-size:11px;opacity:.7">이 지역에는 서울시 인파 관측지점(반경 1km)이 없습니다</span>
      <span></span>
    </div>`}

    ${tagParts.length ? `
    <div class="detail-divider"></div>
    <div class="detail-section-title"><i class="fa-solid fa-tags"></i> AI 매칭 태그</div>
    <div class="detail-tags">${tagParts.slice(0, 8).map(t => `<span class="detail-tag">#${t.replace(/['"]/g,'').trim()}</span>`).join('')}</div>` : ''}

    <div style="display:flex;gap:8px;margin-top:18px;">
      <button class="detail-fav-btn" id="detail-fav-btn" style="
        flex:0 0 auto; width:50px; height:50px; border-radius:var(--radius-md);
        background:${isFav ? '#FFEBEE' : 'var(--nh-bg-sub)'};
        border:1.5px solid ${isFav ? 'var(--nh-red)' : 'var(--nh-border)'};
        color:${isFav ? 'var(--nh-red)' : 'var(--nh-text-third)'};
        cursor:pointer; font-size:20px; display:flex; align-items:center; justify-content:center;
        transition:all 0.2s;">
        <i class="fa-${isFav ? 'solid' : 'regular'} fa-star"></i>
      </button>
      <a href="${mapUrl}" target="_blank" class="map-btn" style="flex:1">
        <i class="fa-solid fa-map-location-dot"></i> 카카오맵 길찾기
      </a>
      ${hasTicket ? `<a href="${ticketUrl}" target="_blank" class="ticket-btn" style="flex:1">
        <i class="fa-solid fa-ticket"></i> 예매하기
      </a>` : ''}
    </div>
  `;

  document.getElementById('detail-fav-btn')?.addEventListener('click', () => {
    toggleFavFamily(key, null);
    const newFav = favorites.includes(key);
    const btn = document.getElementById('detail-fav-btn');
    if (btn) {
      btn.style.background = newFav ? '#FFEBEE' : 'var(--nh-bg-sub)';
      btn.style.borderColor = newFav ? 'var(--nh-red)' : 'var(--nh-border)';
      btn.style.color = newFav ? 'var(--nh-red)' : 'var(--nh-text-third)';
      btn.querySelector('i').className = `fa-${newFav ? 'solid' : 'regular'} fa-star`;
    }
  });

  document.getElementById('detail-sheet').classList.add('open');
  document.getElementById('sheet-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
}

// ── 상세 바텀시트 (레거시) ───────────────────────────
function openDetail(placeId) {
  const pl = mergedData.find(p => p.place_id === placeId);
  if (!pl) return;
  const ev = pl.ev || {};
  const mapUrl = `https://map.kakao.com/link/search/${encodeURIComponent(pl.name)}`;
  const crowdClass = pl.crowd || 'UNKNOWN';
  const isFood = pl.category?.startsWith('맛집/');
  const emoji = CAT_EMOJI[pl.category] || (isFood ? '🍽️' : '📍');
  const dist = calcDistance(userLat, userLon, parseFloat(pl.latitude), parseFloat(pl.longitude));
  const isFav = favorites.includes(pl.place_id);

  const tagHTML = pl.tags.length
    ? `<div class="detail-divider"></div><div class="detail-section-title"><i class="fa-solid fa-tags"></i> AI 매칭 태그</div>
       <div class="detail-tags">${pl.tags.filter(t => !['food'].includes(t)).map(t => `<span class="detail-tag">#${t}</span>`).join('')}</div>`
    : '';

  const eventHTML = ev.title ? `
    <div class="detail-divider"></div>
    <div class="detail-section-title"><i class="fa-solid fa-gift"></i> 주요 행사</div>
    <div class="detail-event-box">
      <div class="detail-event-title">${ev.title}</div>
      <div class="detail-event-desc">${ev.raw_description || ''}</div>
      <div class="detail-event-date"><i class="fa-regular fa-calendar"></i> ${ev.start_date || ''} ~ ${ev.end_date || ''}</div>
    </div>` : '';

  document.getElementById('sheet-body').innerHTML = `
    <div class="detail-cat">${pl.category || '장소'}</div>
    <div class="detail-name">${emoji} ${pl.name}</div>
    <div class="detail-addr"><i class="fa-solid fa-location-dot" style="color:var(--nh-green)"></i>${pl.address || '-'}</div>
    <div class="detail-badges">${buildPillsLegacy({ ...pl, _dist: dist }, isFood)}</div>

    <div class="detail-divider"></div>
    <div class="detail-section-title"><i class="fa-solid fa-tower-broadcast"></i> 현황</div>
    ${dist !== null ? `<div class="crowd-row"><span class="crowd-label">내 위치에서</span><span class="crowd-val LOW">📍 ${formatDist(dist)}</span></div>` : ''}
    <div class="crowd-row">
      <span class="crowd-label">인파 혼잡도${pl.crowd_measured_at ? ` <small style="opacity:.6">(${pl.crowd_measured_at.slice(0,10)} 측정)</small>` : ''}</span>
      <span class="crowd-val ${crowdClass}">${CROWD_LABEL[crowdClass] || crowdClass}</span>
    </div>

    ${eventHTML}
    ${tagHTML}

    <div style="display:flex;gap:8px;margin-top:18px;">
      <button class="detail-fav-btn" id="detail-fav-btn" style="
        flex:0 0 auto; width:50px; height:50px; border-radius:var(--radius-md);
        background:${isFav ? '#FFEBEE' : 'var(--nh-bg-sub)'};
        border:1.5px solid ${isFav ? 'var(--nh-red)' : 'var(--nh-border)'};
        color:${isFav ? 'var(--nh-red)' : 'var(--nh-text-third)'};
        cursor:pointer; font-size:20px; display:flex; align-items:center; justify-content:center;
        transition:all 0.2s;">
        <i class="fa-${isFav ? 'solid' : 'regular'} fa-star"></i>
      </button>
      <a href="${mapUrl}" target="_blank" class="map-btn" style="flex:1;margin-top:0"><i class="fa-solid fa-map-location-dot"></i> 카카오맵으로 길찾기</a>
    </div>
  `;

  document.getElementById('detail-fav-btn')?.addEventListener('click', () => {
    toggleFav(pl.place_id, null);
    const newFav = favorites.includes(pl.place_id);
    const btn = document.getElementById('detail-fav-btn');
    if (btn) {
      btn.style.background = newFav ? '#FFEBEE' : 'var(--nh-bg-sub)';
      btn.style.borderColor = newFav ? 'var(--nh-red)' : 'var(--nh-border)';
      btn.style.color = newFav ? 'var(--nh-red)' : 'var(--nh-text-third)';
      btn.querySelector('i').className = `fa-${newFav ? 'solid' : 'regular'} fa-star`;
    }
  });

  document.getElementById('detail-sheet').classList.add('open');
  document.getElementById('sheet-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeDetail() {
  document.getElementById('detail-sheet').classList.remove('open');
  document.getElementById('sheet-overlay').classList.remove('open');
  document.body.style.overflow = '';
}

// ── 카테고리 이모지 헬퍼 ──────────────────────────────
function getCategoryEmoji(cat) {
  if (!cat) return '📍';
  if (cat.includes('키즈')) return '🏠';
  if (cat.includes('자연') || cat.includes('공원')) return '🌿';
  if (cat.includes('문화') || cat.includes('역사')) return '🎭';
  if (cat.includes('체험') || cat.includes('액티비티')) return '🎯';
  if (cat.includes('서점') || cat.includes('독립서점') || cat.includes('북카페')) return '📚';
  if (cat.includes('공연') || cat.includes('콘서트') || cat.includes('뮤지컬') || cat.includes('연극') || cat.includes('음악')) return '🎵';
  if (cat.includes('전시') || cat.includes('미술관')) return '🖼️';
  if (cat.includes('카페')) return '☕';
  if (cat.includes('맛집')) return '🍽️';
  if (cat.includes('야경') || cat.includes('드라이브')) return '🌃';
  if (cat.includes('힐링') || cat.includes('스파')) return '🌿';
  return '📍';
}

// ══════════════════════════════════════════
// ★ 즐겨찾기 화면 (가족/커플/싱글 통합 렌더)
// ══════════════════════════════════════════
function renderFavPage() {
  const favList = document.getElementById('fav-list');
  const scheduleCard = document.getElementById('fav-schedule-card');

  // 전체 데이터(가족, 커플, 싱글)에서 중복 없이 즐겨찾기 항목 수집
  const allFavData = [...familyData, ...coupleData, ...singleData];
  const favSet = new Set(favorites);
  const seenNames = new Set();
  const favUnifiedItems = [];

  allFavData.forEach(d => {
    const key = encodeURIComponent(d.place_or_event_name);
    if (favSet.has(key) && !seenNames.has(d.place_or_event_name)) {
      seenNames.add(d.place_or_event_name);
      favUnifiedItems.push(d);
    }
  });

  // 레거시 맛집/장소 즐겨찾기 (place_id 기반)
  const favLegacyPlaces = mergedData.filter(p => favSet.has(p.place_id) && !seenNames.has(p.name));

  const allFavItems = [...favUnifiedItems, ...favLegacyPlaces];

  // 일정 요약 카드
  const withPeriod = favUnifiedItems.filter(d => d.period && d.period !== '상시');
  if (withPeriod.length > 0) {
    scheduleCard.innerHTML = withPeriod.slice(0, 3).map(item => {
      const catEmoji = getCategoryEmoji(item.category);
      const parts = item.period.split('~');
      const endDate = parts[1]?.trim() || '';
      const today = new Date();
      const end = new Date(endDate);
      const diff = (end - today) / (1000 * 60 * 60 * 24);
      const badgeType = diff >= 0 && diff <= 7 ? 'booking' : 'viewing';
      const badgeText = diff >= 0 && diff <= 7 ? `D-${Math.ceil(diff)}` : '관람 중';
      return `
        <div class="fav-schedule-item">
          <div class="fav-schedule-icon">${catEmoji}</div>
          <div class="fav-schedule-info">
            <div class="fav-schedule-name">${item.place_or_event_name}</div>
            <div class="fav-schedule-date"><i class="fa-regular fa-calendar"></i>${item.period}</div>
          </div>
          <span class="fav-schedule-badge ${badgeType}">${badgeText}</span>
        </div>`;
    }).join('');
  } else {
    scheduleCard.innerHTML = '';
  }

  if (allFavItems.length === 0) {
    favList.innerHTML = `
      <div class="fav-empty">
        <div class="fav-empty__icon">⭐</div>
        <div class="fav-empty__title">즐겨찾기한 장소가 없어요</div>
        <p class="fav-empty__desc">장소 카드의 ☆ 버튼을 눌러<br>마음에 드는 장소를 저장해 보세요.</p>
        <button class="fav-go-btn" id="fav-go-home-btn">추천 장소 보러 가기</button>
      </div>`;
    document.getElementById('fav-go-home-btn')?.addEventListener('click', switchToHome);
    return;
  }

  favList.innerHTML = [
    ...favUnifiedItems.map((item, idx) => {
      if (item.origin || item.region_group) {
        return renderCoupleCard(item, idx);
      }
      return renderFamilyCard(item, idx);
    }),
    ...favLegacyPlaces.map((pl, idx) => renderLegacyCard(pl, favUnifiedItems.length + idx)),
  ].join('');

  favList.querySelectorAll('.fav-btn[data-key]').forEach(btn => {
    btn.addEventListener('click', e => { e.stopPropagation(); toggleFavFamily(btn.dataset.key, btn); });
  });
  favList.querySelectorAll('.fav-btn[data-pid]').forEach(btn => {
    btn.addEventListener('click', e => { e.stopPropagation(); toggleFav(btn.dataset.pid, btn); });
  });
  favList.querySelectorAll('.place-item[data-key]').forEach(item => {
    item.addEventListener('click', () => {
      const isCouple = coupleData.some(c => encodeURIComponent(c.place_or_event_name) === item.dataset.key);
      if (isCouple) openDetailCouple(item.dataset.key);
      else openDetailFamily(item.dataset.key);
    });
  });
  favList.querySelectorAll('.place-item[data-id]').forEach(item => {
    item.addEventListener('click', () => openDetail(item.dataset.id));
  });
}

// ── 뷰 전환 ─────────────────────────────────────────
function switchToHome() {
  currentView = 'home';
  document.getElementById('view-home').removeAttribute('hidden');
  document.getElementById('view-fav').setAttribute('hidden', '');
  document.getElementById('bnav-home').classList.add('active');
  document.getElementById('bnav-fav').classList.remove('active');
}

function switchToFav() {
  currentView = 'fav';
  document.getElementById('view-fav').removeAttribute('hidden');
  document.getElementById('view-home').setAttribute('hidden', '');
  document.getElementById('search-bar-wrap').setAttribute('hidden', '');
  document.getElementById('bnav-fav').classList.add('active');
  document.getElementById('bnav-home').classList.remove('active');
  renderFavPage();
}

// ══════════════════════════════════════════
// ★ 상단 알림 티커
// ══════════════════════════════════════════
function updateTicker() {
  const track = document.getElementById('ticker-track');
  if (!track) return;

  let tickerItems = [];
  const allFavData = [...familyData, ...coupleData, ...singleData];
  const favItems = allFavData.filter(d => favorites.includes(encodeURIComponent(d.place_or_event_name)) && d.period && d.period !== '상시');

  if (favItems.length > 0) {
    tickerItems = favItems.slice(0, 5).map(item => ({
      text: `📅 ⭐ ${item.place_or_event_name} | ${item.period}`,
      key: encodeURIComponent(item.place_or_event_name),
    }));
  } else {
    // 임박 행사 최신 5건
    const upcoming = familyData
      .filter(d => d.period && d.period !== '상시')
      .slice(0, 5);
    if (upcoming.length > 0) {
      tickerItems = upcoming.map(item => ({
        text: `📅 ${item.place_or_event_name} | ${item.period}`,
        key: null,
      }));
    } else {
      tickerItems = [{ text: '⭐ 장소에 즐겨찾기를 추가하면 일정 알림이 표시됩니다', key: null }];
    }
  }

  const itemsHTML = tickerItems.map(item =>
    `<span class="ticker-item" data-key="${item.key || ''}">${item.text}</span>`
  ).join('');
  track.innerHTML = itemsHTML + itemsHTML;

  track.querySelectorAll('.ticker-item[data-key]').forEach(el => {
    el.addEventListener('click', () => {
      if (el.dataset.key) {
        const isCouple = coupleData.some(c => encodeURIComponent(c.place_or_event_name) === el.dataset.key);
        if (isCouple) openDetailCouple(el.dataset.key);
        else openDetailFamily(el.dataset.key);
      }
    });
  });

  const totalChars = tickerItems.reduce((sum, i) => sum + i.text.length, 0);
  const duration = Math.max(15, Math.min(60, totalChars * 0.35));
  track.style.animationDuration = `${duration}s`;
}

// ══════════════════════════════════════════
// ★ 공유하기
// ══════════════════════════════════════════
function openShareSheet() {
  const allFavData = [...familyData, ...coupleData, ...singleData];
  const favSet = new Set(favorites);
  const seen = new Set();
  allFavData.forEach(d => {
    const key = encodeURIComponent(d.place_or_event_name);
    if (favSet.has(key)) seen.add(d.place_or_event_name);
  });
  mergedData.forEach(p => {
    if (favSet.has(p.place_id)) seen.add(p.name);
  });
  const favCount = seen.size || favorites.length;

  const desc = document.getElementById('share-desc');
  if (favCount === 0) {
    desc.textContent = '즐겨찾기한 장소가 없어요. 장소를 추가한 후 공유해 보세요!';
  } else {
    desc.textContent = `즐겨찾기 장소 ${favCount}곳을 친구에게 공유해 보세요!`;
  }
  document.getElementById('share-sheet').classList.add('open');
  document.getElementById('share-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeShareSheet() {
  document.getElementById('share-sheet').classList.remove('open');
  document.getElementById('share-overlay').classList.remove('open');
  document.body.style.overflow = '';
}

function buildShareText() {
  const allFavData = [...familyData, ...coupleData, ...singleData];
  const favSet = new Set(favorites);
  const seen = new Set();
  const favItems = [];
  allFavData.forEach(d => {
    const key = encodeURIComponent(d.place_or_event_name);
    if (favSet.has(key) && !seen.has(d.place_or_event_name)) {
      seen.add(d.place_or_event_name);
      favItems.push(d);
    }
  });
  mergedData.forEach(p => {
    if (favSet.has(p.place_id) && !seen.has(p.name)) {
      seen.add(p.name);
      favItems.push({ place_or_event_name: p.name, category: p.category });
    }
  });
  if (favItems.length === 0) return '주말해 앱에서 AI 맞춤 여가 장소를 추천받아 보세요! 🌿';
  const list = favItems.slice(0, 5).map((d, i) => `${i + 1}. ${d.place_or_event_name} (${d.category || '명소'})`).join('\n');
  return `🌿 주말해 — 내 즐겨찾기 장소\n\n${list}\n\n👉 주말해: ${window.location.origin}/web/index.html`;
}

function shareKakao() {
  const text = buildShareText();
  const shareUrl = `${window.location.origin}/web/index.html`;
  // iOS Safari / 모바일 환경: Web Share API 우선 사용
  // (kakaolink:// 커스텀 스킴은 카카오 JS SDK 없이는 동작 안 하고 Safari에서 오류 발생)
  if (navigator.share) {
    navigator.share({
      title: '🌿 주말해 — 내 즐겨찾기',
      text: text,
      url: shareUrl,
    }).then(() => {
      // 사용자가 카카오톡 선택 시 자동 전달됨
    }).catch(err => {
      // 사용자가 취소했거나 오류 — 클립보드 폴백
      if (err.name !== 'AbortError') {
        copyToClipboard(text, '카카오톡 공유 준비 완료! 클립보드에 복사되었습니다.');
      }
    });
  } else {
    // 데스크톱: 클립보드 복사 후 카카오톡 PC 버전 URL 스킴 시도
    copyToClipboard(text, '카카오톡 공유용 텍스트가 클립보드에 복사되었습니다. 카카오톡에 붙여넣어 주세요.');
  }
}

function shareInstagram() {
  const text = buildShareText();
  const a = document.createElement('a'); a.href = 'instagram://app';
  try { a.click(); setTimeout(() => copyToClipboard(text, 'Instagram을 열었습니다! 스토리 작성 시 붙여넣어 주세요.'), 1200); }
  catch { copyToClipboard(text, 'Instagram 앱이 없습니다. 클립보드에 복사되었습니다.'); }
}

function copyLink() { copyToClipboard(buildShareText()); }

function copyToClipboard(text, message = '클립보드에 복사되었습니다!') {
  const toast = document.getElementById('copy-toast');
  navigator.clipboard.writeText(text).then(() => {
    if (toast) { toast.innerHTML = `<i class="fa-solid fa-circle-check"></i> ${message}`; toast.removeAttribute('hidden'); setTimeout(() => toast.setAttribute('hidden', ''), 3000); }
  }).catch(() => {
    const ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); document.body.removeChild(ta);
    if (toast) { toast.innerHTML = `<i class="fa-solid fa-circle-check"></i> ${message}`; toast.removeAttribute('hidden'); setTimeout(() => toast.setAttribute('hidden', ''), 3000); }
  });
}

function shareMore() {
  const text = buildShareText();
  if (navigator.share) navigator.share({ title: '🌿 주말해 — 내 즐겨찾기', text, url: `${window.location.origin}/web/index.html` }).catch(() => {});
  else copyToClipboard(text, '공유 기능이 지원되지 않아 클립보드에 복사되었습니다.');
}

// ── 이벤트 핸들러 ─────────────────────────────────────
function initEvents() {
  // 세그먼트 탭
  document.querySelectorAll('.seg-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.seg-tab').forEach(b => { b.classList.remove('active'); b.setAttribute('aria-selected','false'); });
      btn.classList.add('active');
      btn.setAttribute('aria-selected','true');
      currentSeg = btn.dataset.seg;
      currentThemeIdx = 0;
      currentPage = 1;
      renderThemeChips();
      renderList();
    });
  });

  // 4카테고리 서브탭 (family)
  document.querySelectorAll('.fcat-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.fcat-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFamilyCat = btn.dataset.cat;
      currentPage = 1;
      renderThemeChips(); // 배너 업데이트
      renderList();
    });
  });

  // 정렬 칩
  document.querySelectorAll('.sort-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      document.querySelectorAll('.sort-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      currentSort = chip.dataset.sort;
      // 거리순 선택 시 위치 요청
      if (currentSort === 'distance' && !userLat) {
        requestGeolocation(ok => { if (ok) renderList(); else alert('위치 권한을 허용해야 거리순 정렬이 가능합니다.'); });
        return;
      }
      currentPage = 1;
      renderList();
    });
  });

  // 위치 버튼
  document.getElementById('location-btn')?.addEventListener('click', () => {
    requestGeolocation(ok => {
      if (ok) { renderList(); }
    });
  });

  // 위치 허용 배너 버튼
  document.getElementById('geo-allow-btn')?.addEventListener('click', () => {
    requestGeolocation(ok => { if (ok) renderList(); });
  });

  // 검색 토글
  document.getElementById('search-toggle-btn')?.addEventListener('click', () => {
    if (currentView === 'fav') switchToHome();
    const wrap = document.getElementById('search-bar-wrap');
    const hidden = wrap.hasAttribute('hidden');
    if (hidden) { wrap.removeAttribute('hidden'); wrap.querySelector('input').focus(); }
    else { wrap.setAttribute('hidden',''); wrap.querySelector('input').value = ''; currentPage=1; renderList(); }
  });

  document.getElementById('search-input')?.addEventListener('input', () => { currentPage = 1; renderList(); });
  document.getElementById('search-clear-btn')?.addEventListener('click', () => {
    document.getElementById('search-input').value = '';
    currentPage = 1; renderList();
  });

  // 페이지네이션
  document.getElementById('page-prev')?.addEventListener('click', () => { if (currentPage > 1) { currentPage--; renderList(); } });
  document.getElementById('page-next')?.addEventListener('click', () => { currentPage++; renderList(); });

  // 바텀시트 닫기
  document.getElementById('sheet-close-btn')?.addEventListener('click', closeDetail);
  document.getElementById('sheet-overlay')?.addEventListener('click', closeDetail);

  // 하단 내비게이션 및 헤더 즐겨찾기 버튼
  document.getElementById('bnav-home')?.addEventListener('click', () => { if (currentView !== 'home') switchToHome(); });
  document.getElementById('bnav-fav')?.addEventListener('click', () => { if (currentView !== 'fav') switchToFav(); });
  document.getElementById('header-fav-btn')?.addEventListener('click', () => { if (currentView !== 'fav') switchToFav(); });

  // 공유하기
  document.getElementById('fav-share-btn')?.addEventListener('click', openShareSheet);
  document.getElementById('share-close-btn')?.addEventListener('click', closeShareSheet);
  document.getElementById('share-overlay')?.addEventListener('click', closeShareSheet);
  document.getElementById('share-kakao')?.addEventListener('click', shareKakao);
  // share-allone 제거됨
  document.getElementById('share-instagram')?.addEventListener('click', shareInstagram);
  document.getElementById('share-copy')?.addEventListener('click', copyLink);
  document.getElementById('share-more-btn')?.addEventListener('click', shareMore);

  // 갱신 관련 코드는 관리자 페이지로 이동되어 사용자 뷰에서 제거됨
}

// ══════════════════════════════════════════
// ★ 커플 탭 (total_couple_data.csv)
// ══════════════════════════════════════════

// RecommendScore 와 달리 family: 태그나 추정 couple_score 를 쓰지 않는다.
// 실측된 인기도/마감/거리/혼잡도/무료 여부만으로 계산한다.
function calcCoupleScore(item) {
  // 1) popularity (0~100 → 0~2)
  const popRaw = parseFloat(item.popularity_score);
  const popScore = Number.isFinite(popRaw) ? (popRaw / 100) * 2.0 : 0;

  // 2) 마감/진행 상태 — end_date 기준 (period 문자열 파싱 아님)
  let freshness = 0;
  if (item.end_date) {
    const end = new Date(item.end_date);
    const diffDays = (end - new Date()) / (1000 * 60 * 60 * 24);
    if (diffDays >= 0 && diffDays <= 7) freshness = 1.5;      // 마감 7일 이내
    else if (diffDays >= 0) freshness = 1.0;                  // 진행 중
  } else {
    freshness = 0.8; // 상설
  }

  // 3) 거리 보너스
  let distBonus = 0;
  if (userLat && userLon) {
    const { lat, lon } = parseLatLon(item.region);
    const dist = calcDistance(userLat, userLon, lat, lon);
    if (dist !== null) {
      if (dist <= 5) distBonus = 2.0;
      else if (dist <= 15) distBonus = 1.0;
      else if (dist <= 30) distBonus = 0.5;
    }
  }

  // 4) 혼잡도 감점 — 실측값이 있을 때만
  const congOrder = congestOrderOf(item);
  const penalty = congOrder === null ? 0 : congOrder * 0.2;

  // 5) 무료 보너스
  const freeBonus = isFreeItem(item) ? 0.5 : 0;

  return popScore + freshness + distBonus - penalty + freeBonus;
}

// 정렬 칩 6종. applySortFamily 와 동작을 맞추되 deadline 은 end_date 컬럼을 쓴다.
function applySortCouple(list) {
  switch (currentSort) {
    case 'recommend':
      return list.map(item => ({ ...item, _score: calcCoupleScore(item) }))
                 .sort((a, b) => b._score - a._score);
    case 'popular':
      return list.sort((a, b) => (parseFloat(b.popularity_score) || 0) - (parseFloat(a.popularity_score) || 0));
    case 'deadline':
      return list.filter(item => item.end_date)
        .sort((a, b) => new Date(a.end_date) - new Date(b.end_date))
        .concat(list.filter(item => !item.end_date));
    case 'distance':
      if (!userLat) return list;
      return list.sort((a, b) => (a._dist ?? 99999) - (b._dist ?? 99999));
    case 'quiet': {
      const withLv = [], without = [];
      for (const it of list) {
        const o = congestOrderOf(it);
        (o === null ? without : withLv).push({ it, o });
      }
      withLv.sort((a, b) => a.o - b.o);
      return withLv.map(x => x.it).concat(without.map(x => x.it));
    }
    case 'free':
      return list.filter(isFreeItem).concat(list.filter(it => !isFreeItem(it)));
    default:
      return list;
  }
}

const COUPLE_THEME_EMOJI = { concert: '🎵', popup: '🎁', exhibition: '🖼️', outdoor: '🌃' };

// renderFamilyCard 의 HTML 구조·클래스를 그대로 재사용한다. 새 CSS 클래스는 만들지 않는다.
function renderCoupleCard(item, idx) {
  const rank = (currentPage - 1) * PAGE_SIZE + idx + 1;
  const key = encodeURIComponent(item.place_or_event_name || String(idx));
  const isFav = favorites.includes(key);

  const firstTheme = (item.theme_ids || '').split(';')[0];
  const catEmoji = COUPLE_THEME_EMOJI[firstTheme] || '📍';

  // 배지 생성 — family 최적 배지는 넣지 않는다 (커플 탭이다)
  const badges = [];
  if (isFreeItem(item)) badges.push('<span class="badge-pill free">💚 무료</span>');
  const popRaw = parseFloat(item.popularity_score);
  if (Number.isFinite(popRaw) && popRaw >= 80) badges.push('<span class="badge-pill ticket">🔥 인기</span>');
  if (item.end_date) {
    const diff = (new Date(item.end_date) - new Date()) / (1000 * 60 * 60 * 24);
    if (diff >= 0 && diff <= 7) badges.push(`<span class="badge-pill soon">⏰ 마감 ${Math.ceil(diff)}일</span>`);
  }

  // 거리 배지
  if (item._dist !== null && item._dist !== undefined) {
    const distLabel = item._dist <= 5 ? `🟢 ${formatDist(item._dist)}` : item._dist <= 15 ? `🟡 ${formatDist(item._dist)}` : `🔵 ${formatDist(item._dist)}`;
    badges.push(`<span class="badge-pill dist">${distLabel}</span>`);
  }

  // 혼잡도 점 — 측정값 없으면 UNKNOWN
  const crowdRaw = parseInt(item.congestion_score);
  const crowdScore = Number.isFinite(crowdRaw) ? crowdRaw : null;
  const crowdClass = crowdScore === null ? 'UNKNOWN'
    : crowdScore <= 1 ? 'LOW' : crowdScore <= 2 ? 'MODERATE' : crowdScore <= 3 ? 'CONGESTED' : 'VERY_CONGESTED';

  const regionDisplay = (item.region || '').split('|')[0].trim();

  return `
  <div class="place-item" data-key="${key}" role="button" tabindex="0" aria-label="${item.place_or_event_name} 상세 보기">
    <span class="place-item__rank${rank <= 3 ? ' top' : ''}">${rank}</span>
    <div class="place-item__info">
      <div class="place-item__name">${item.place_or_event_name || '-'}</div>
      <div class="place-item__meta">
        <span class="place-item__addr">${regionDisplay}</span>
        <span class="place-item__cat">${item.category || ''}</span>
        <span class="crowd-dot ${crowdClass}" title="혼잡도: ${CROWD_LABEL[crowdClass] || ''}"></span>
      </div>
      <div class="place-item__badges">${badges.join('')}</div>
    </div>
    <div class="place-item__thumb">
      ${catEmoji}
      <button class="fav-btn${isFav ? ' active' : ''}" data-key="${key}" aria-label="즐겨찾기">
        <i class="fa-${isFav ? 'solid' : 'regular'} fa-star"></i>
      </button>
    </div>
  </div>`;
}

// openDetailFamily 구조를 그대로 본뜬다.
function openDetailCouple(key) {
  const item = coupleData.find(d => encodeURIComponent(d.place_or_event_name) === key);
  if (!item) return;

  const firstTheme = (item.theme_ids || '').split(';')[0];
  const catEmoji = COUPLE_THEME_EMOJI[firstTheme] || '📍';
  const { lat, lon } = parseLatLon(item.region);
  const dist = calcDistance(userLat, userLon, lat, lon);
  const isFav = favorites.includes(key);
  const regionDisplay = (item.region || '').split('|')[0].trim();

  const hasTicket = !!(item.booking_url && item.booking_url.startsWith('http'));

  // 혼잡도 — 서울시 실시간 관측지점이 반경 안에 있을 때만 표시한다.
  const near = findNearestCongestion(lat, lon);
  const crowdClass = near ? (CONGEST_CLASS[near.area.congest_lvl] || 'UNKNOWN') : 'UNKNOWN';

  // 인기도 — popularity_src 가 있을 때만 근거와 함께 표시한다.
  // 소스마다 척도가 달라(예: VisitKorea 조회수 vs KOPIS 예매순위) 근거 없이 보여주면
  // 사용자가 소스 간 비교가 가능하다고 오해한다.
  const popRaw = parseFloat(item.popularity_score);
  const popularityHTML = Number.isFinite(popRaw)
    ? `<div class="detail-event-date"><i class="fa-solid fa-fire"></i> 인기도 ${popRaw}점${item.popularity_src ? ` (${item.popularity_src} 기준)` : ''}</div>`
    : '';

  const searchName = (regionDisplay + ' ' + (item.place_or_event_name || '')).trim();
  const mapUrl = `https://map.kakao.com/link/search/${encodeURIComponent(searchName)}`;

  document.getElementById('sheet-body').innerHTML = `
    <div class="detail-cat">${item.category || '장소'}</div>
    <div class="detail-name">${catEmoji} ${item.place_or_event_name || '-'}</div>
    <div class="detail-addr"><i class="fa-solid fa-location-dot" style="color:var(--nh-green)"></i>${regionDisplay}</div>
    <div class="detail-badges">
      ${isFreeItem(item) ? '<span class="badge-pill free">💚 무료</span>' : ''}
      ${dist !== null ? `<span class="badge-pill dist">📍 ${formatDist(dist)}</span>` : ''}
      ${hasTicket ? '<span class="badge-pill ticket">🎫 예매 가능</span>' : ''}
    </div>

    <div class="detail-divider"></div>
    <div class="detail-section-title"><i class="fa-solid fa-circle-info"></i> 상세 정보</div>
    <div class="detail-event-box">
      <div class="detail-event-title">💰 이용 요금: ${item.fee_info || '정보 없음'}</div>
      <div class="detail-event-desc">${item.description || '설명 정보가 없습니다.'}</div>
      ${item.period ? `<div class="detail-event-date"><i class="fa-regular fa-calendar"></i> 기간: ${item.period}</div>` : ''}
      ${item.target_age ? `<div class="detail-event-date"><i class="fa-solid fa-child"></i> 관람 연령: ${item.target_age}</div>` : ''}
      ${popularityHTML}
      <div class="detail-event-date"><i class="fa-solid fa-database"></i> 출처: ${item.origin || item.source_site || '정보 없음'}</div>
    </div>

    <div class="detail-divider"></div>
    <div class="detail-section-title"><i class="fa-solid fa-tower-broadcast"></i> 인파 현황</div>
    ${dist !== null ? `<div class="crowd-row"><span class="crowd-label">내 위치에서</span><span class="crowd-val LOW">📍 ${formatDist(dist)}</span></div>` : ''}
    <div class="crowd-row">
      <span class="crowd-label">인파 혼잡도</span>
      <span class="crowd-val ${crowdClass}">${near ? near.area.congest_lvl : '정보 없음'}</span>
    </div>
    ${near ? `
    <div class="crowd-row">
      <span class="crowd-label">관측지점</span>
      <span class="crowd-val LOW" style="font-weight:500">${near.area.area_nm} · ${formatDist(near.dist)}</span>
    </div>` : `
    <div class="crowd-row">
      <span class="crowd-label" style="font-size:11px;opacity:.7">이 지역에는 서울시 인파 관측지점(반경 1km)이 없습니다</span>
      <span></span>
    </div>`}

    <div style="display:flex;gap:8px;margin-top:18px;">
      <button class="detail-fav-btn" id="detail-fav-btn" style="
        flex:0 0 auto; width:50px; height:50px; border-radius:var(--radius-md);
        background:${isFav ? '#FFEBEE' : 'var(--nh-bg-sub)'};
        border:1.5px solid ${isFav ? 'var(--nh-red)' : 'var(--nh-border)'};
        color:${isFav ? 'var(--nh-red)' : 'var(--nh-text-third)'};
        cursor:pointer; font-size:20px; display:flex; align-items:center; justify-content:center;
        transition:all 0.2s;">
        <i class="fa-${isFav ? 'solid' : 'regular'} fa-star"></i>
      </button>
      <a href="${mapUrl}" target="_blank" class="map-btn" style="flex:1">
        <i class="fa-solid fa-map-location-dot"></i> 카카오맵 길찾기
      </a>
      ${hasTicket ? `<a href="${item.booking_url}" target="_blank" class="ticket-btn" style="flex:1">
        <i class="fa-solid fa-ticket"></i> 예매하기
      </a>` : ''}
    </div>
  `;

  document.getElementById('detail-fav-btn')?.addEventListener('click', () => {
    toggleFavFamily(key, null);
    const newFav = favorites.includes(key);
    const btn = document.getElementById('detail-fav-btn');
    if (btn) {
      btn.style.background = newFav ? '#FFEBEE' : 'var(--nh-bg-sub)';
      btn.style.borderColor = newFav ? 'var(--nh-red)' : 'var(--nh-border)';
      btn.style.color = newFav ? 'var(--nh-red)' : 'var(--nh-text-third)';
      btn.querySelector('i').className = `fa-${newFav ? 'solid' : 'regular'} fa-star`;
    }
  });

  document.getElementById('detail-sheet').classList.add('open');
  document.getElementById('sheet-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
}

// ── 날씨 배너 업데이트 ─────────────────────────────────
function updateWeatherBanner() {
  if (!weatherData.length) return;
  const banner = document.getElementById('weather-banner');
  if (!banner) return;
  
  let closestRegion = "서울"; // 기본값
  if (userLat && userLon) {
    let minD = Infinity;
    for (const r in REGION_COORDS) {
      const c = REGION_COORDS[r];
      const d = calcDistance(userLat, userLon, c.lat, c.lon);
      if (d !== null && d < minD) {
        minD = d; closestRegion = r;
      }
    }
  }

  const todayStr = new Date().toISOString().split('T')[0];
  const w = weatherData.find(x => x.region === closestRegion && x.date >= todayStr) 
         || weatherData.find(x => x.region === closestRegion);
         
  if (w) {
    document.getElementById('w-region').textContent = closestRegion;
    document.getElementById('w-status').innerHTML = `<strong>${w.status}</strong> (${Math.round(w.min_temp)}°~${Math.round(w.max_temp)}°)`;
    
    const dustEl = document.getElementById('w-dust');
    dustEl.textContent = w.dust || '정보없음';
    dustEl.className = '';
    if (w.dust === '좋음') dustEl.classList.add('dust-good');
    else if (w.dust === '보통') dustEl.classList.add('dust-normal');
    else dustEl.classList.add('dust-bad');
    
    banner.removeAttribute('hidden');
  }
}
