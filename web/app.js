/* ══════════════════════════════
   주말해 앱 JavaScript
   ══════════════════════════════ */

// ── 위치 정보 전역 상태 ─────────────────────────────
let userLat = null;
let userLon = null;
let geoWatchId = null;

// ── 세그먼트별 하위 테마 정의 ──────────────────────────
const THEMES = {
  family: [
    { id: 'summer',    label: '🏖️ 여름 피서지',   emoji: '🏖️', bannerSub: '아이와 함께', bannerTitle: '여름 피서지',    color: '' },
    { id: 'healing',   label: '🌿 조용한 힐링',    emoji: '🌿', bannerSub: '힐링이 필요할 때', bannerTitle: '조용한 힐링',  color: '' },
    { id: 'theme',     label: '🎢 테마파크',       emoji: '🎢', bannerSub: '신나는 하루',  bannerTitle: '테마파크',       color: '' },
    { id: 'nature',    label: '🌳 자연·공원',      emoji: '🌳', bannerSub: '맑은 공기 속으로', bannerTitle: '자연·공원',   color: '' },
    { id: 'experience',label: '🎨 체험·교육',      emoji: '🎨', bannerSub: '배움과 즐거움',  bannerTitle: '체험·교육',    color: '' },
    { id: 'indoor',    label: '🏛️ 실내 활동',      emoji: '🏛️', bannerSub: '더위를 피해서', bannerTitle: '실내 활동',     color: '' },
  ],
  couple: [
    { id: 'popup',     label: '🎁 팝업스토어',     emoji: '🎁', bannerSub: '감성 데이트',   bannerTitle: '팝업스토어',    color: 'blue' },
    { id: 'concert',   label: '🎵 콘서트·공연',    emoji: '🎵', bannerSub: '함께 즐기는',   bannerTitle: '콘서트·공연',   color: 'blue' },
    { id: 'nightview', label: '🌃 야경·뷰포인트',  emoji: '🌃', bannerSub: '로맨틱한 밤',   bannerTitle: '야경·뷰포인트', color: 'blue' },
    { id: 'cafe',      label: '☕ 카페 거리',       emoji: '☕', bannerSub: '골목 탐험',     bannerTitle: '카페 거리',     color: 'blue' },
    { id: 'exhibition',label: '🖼️ 전시·미술관',    emoji: '🖼️', bannerSub: '문화를 즐겨요', bannerTitle: '전시·미술관',   color: 'blue' },
    { id: 'summer',    label: '🏖️ 여름 피서지',    emoji: '🏖️', bannerSub: '시원하게 데이트', bannerTitle: '여름 피서지', color: 'blue' },
  ],
  single: [
    { id: 'exhibition',label: '🖼️ 전시·미술관',    emoji: '🖼️', bannerSub: '나만의 시간',    bannerTitle: '전시·미술관',  color: 'purple' },
    { id: 'bookstore', label: '📚 독립서점',        emoji: '📚', bannerSub: '조용한 독서',    bannerTitle: '독립서점',     color: 'purple' },
    { id: 'concert',   label: '🎵 콘서트·공연',     emoji: '🎵', bannerSub: '몰입감 있는',    bannerTitle: '콘서트·공연',  color: 'purple' },
    { id: 'healing',   label: '🌿 조용한 힐링',     emoji: '🌿', bannerSub: '혼자 사색하기',  bannerTitle: '조용한 힐링',  color: 'purple' },
    { id: 'culture',   label: '🏯 역사·문화',       emoji: '🏯', bannerSub: '깊이 있게',      bannerTitle: '역사·문화',    color: 'purple' },
    { id: 'nature',    label: '🌳 자연·공원',       emoji: '🌳', bannerSub: '혼자 걷기 좋은', bannerTitle: '자연·공원',    color: 'purple' },
  ],
  food: [
    { id: 'food_near',   label: '📍 내 주변 맛집',   emoji: '📍', bannerSub: '지금 내 위치 근처', bannerTitle: '내 주변 맛집', color: 'food' },
    { id: 'food_korean', label: '🍲 한식',           emoji: '🍲', bannerSub: '따뜻한 한 끼',     bannerTitle: '한식 맛집',    color: 'food' },
    { id: 'food_western',label: '🍝 양식·이탈리안',  emoji: '🍝', bannerSub: '유럽 감성 한 상',  bannerTitle: '양식 맛집',    color: 'food' },
    { id: 'food_japanese',label: '🍣 일식',          emoji: '🍣', bannerSub: '오마카세부터 분식까지', bannerTitle: '일식 맛집', color: 'food' },
    { id: 'food_cafe',   label: '☕ 카페·디저트',    emoji: '☕', bannerSub: '달콤한 휴식',      bannerTitle: '카페·디저트',  color: 'food' },
    { id: 'food_hidden', label: '🕵️ 숨은 맛집',     emoji: '🕵️', bannerSub: '아는 사람만 아는', bannerTitle: '숨은 맛집',    color: 'food' },
  ],
};

// 테마별 카테고리-태그 매핑 (어떤 place가 이 테마에 속하는지)
const THEME_FILTER = {
  summer:       ['공원/야외', '테마파크'],
  healing:      ['공원/야외', '도서/문화', '박물관/전시'],
  theme:        ['테마파크'],
  nature:       ['공원/야외'],
  experience:   ['박물관/전시', '미술관/전시', '복합문화공간'],
  indoor:       ['복합문화공간', '미술관/전시', '박물관/전시'],
  popup:        ['팝업스토어', '복합문화공간'],
  concert:      ['팝업스토어', '복합문화공간', '미술관/전시'],
  nightview:    ['공원/야외', '문화유산/역사'],
  cafe:         ['카페/식음', '팝업스토어'],
  exhibition:   ['미술관/전시', '박물관/전시', '문화유산/역사'],
  bookstore:    ['도서/문화'],
  culture:      ['문화유산/역사', '박물관/전시'],
  // 맛집 테마
  food_near:    ['맛집/한식','맛집/양식','맛집/일식','맛집/카페·디저트','맛집/아시안','맛집/기타'],
  food_korean:  ['맛집/한식'],
  food_western: ['맛집/양식'],
  food_japanese:['맛집/일식'],
  food_cafe:    ['맛집/카페·디저트'],
  food_hidden:  ['맛집/한식','맛집/양식','맛집/일식','맛집/카페·디저트','맛집/아시안'],
};

// 이모지 썸네일 (카테고리별)
const CAT_EMOJI = {
  '공원/야외': '🌳', '팝업스토어': '🎁', '미술관/전시': '🖼️',
  '복합문화공간': '🏢', '문화유산/역사': '🏯', '박물관/전시': '🏛️',
  '도서/문화': '📚', '카페/식음': '☕', '테마파크': '🎢',
  '맛집/한식': '🍲', '맛집/양식': '🍝', '맛집/일식': '🍣',
  '맛집/카페·디저트': '☕', '맛집/아시안': '🍜', '맛집/기타': '🍽️',
};

// 혼잡도 한글
const CROWD_LABEL = { LOW: '여유', MODERATE: '보통', CONGESTED: '혼잡', VERY_CONGESTED: '매우 혼잡' };

// ── 전역 상태 ────────────────────────────────────────
let placesData = [];
let eventsData = [];
let metricsData = [];
let mergedData = [];
let currentSeg = 'family';
let currentThemeIdx = 0;
let currentPage = 1;
const PAGE_SIZE = 6;
let favorites = JSON.parse(localStorage.getItem('nh_favorites') || '[]');

// ── Haversine 거리 계산 (km) ─────────────────────────
function calcDistance(lat1, lon1, lat2, lon2) {
  if (!lat1 || !lon1 || !lat2 || !lon2) return null;
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat/2)*Math.sin(dLat/2) +
    Math.cos(lat1*Math.PI/180)*Math.cos(lat2*Math.PI/180)*
    Math.sin(dLon/2)*Math.sin(dLon/2);
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
}

function formatDist(km) {
  if (km === null) return '';
  if (km < 1) return Math.round(km * 1000) + 'm';
  return km.toFixed(1) + 'km';
}

// ── 위치 정보 요청 ───────────────────────────────────
function requestGeolocation() {
  if (!navigator.geolocation) return;
  navigator.geolocation.getCurrentPosition(
    pos => {
      userLat = pos.coords.latitude;
      userLon = pos.coords.longitude;
      if (currentSeg === 'food') renderList();
    },
    err => { console.warn('위치 정보 접근 불가:', err.message); },
    { enableHighAccuracy: true, timeout: 8000, maximumAge: 30000 }
  );
}

// ── 초기화 ───────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initDate();
  renderThemeChips();
  initEvents();
  loadData();
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
    const [p, e, m] = await Promise.all([
      fetch('../data/places.csv').then(r => r.text()),
      fetch('../data/events.csv').then(r => r.text()),
      fetch('../data/real_time_metrics.csv').then(r => r.text()),
    ]);
    placesData = parseCSV(p);
    eventsData = parseCSV(e);
    metricsData = parseCSV(m);
    mergeData();
    updateModalStats();
    renderList();
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
    return { ...pl, ev, scores, tags, crowd: mt.seoul_crowd_level || 'LOW', tmap_rank: parseInt(mt.tmap_rank) || 999 };
  });
}

// ── 테마 칩 렌더링 ───────────────────────────────────
function renderThemeChips() {
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
      updateBanner();
      renderList();
    });
  });
  updateBanner();
}

function updateBanner() {
  const t = THEMES[currentSeg][currentThemeIdx];
  document.getElementById('banner-sub').textContent   = t.bannerSub;
  document.getElementById('banner-title').textContent = t.bannerTitle;
  document.getElementById('banner-emoji').textContent = t.emoji;
  const banner = document.getElementById('theme-banner');
  banner.className = 'theme-banner' + (t.color ? ' ' + t.color : '');
}

// ── 리스트 렌더링 ────────────────────────────────────
function renderList() {
  const container = document.getElementById('place-list');
  const paginBar  = document.getElementById('pagination-bar');
  const query     = (document.getElementById('search-input')?.value || '').toLowerCase().trim();

  const theme = THEMES[currentSeg][currentThemeIdx];
  const allowedCats = THEME_FILTER[theme.id] || [];
  const isFood = currentSeg === 'food';

  let list = [...mergedData];

  // ── 맛집 탭 전용 처리 ──
  if (isFood) {
    // 맛집 카테고리만 필터
    list = list.filter(p => p.category && p.category.startsWith('맛집/'));
    if (allowedCats.length && theme.id !== 'food_near') {
      const filtered = list.filter(p => allowedCats.some(cat => p.category === cat));
      if (filtered.length) list = filtered;
    }
    // 거리 계산
    list = list.map(p => ({
      ...p,
      dist: calcDistance(userLat, userLon, parseFloat(p.latitude), parseFloat(p.longitude))
    }));
    // 내 주변 테마이면 거리순, 아니면 평점(태그에서 추출)순
    if (theme.id === 'food_near' && userLat) {
      list.sort((a, b) => (a.dist ?? 999) - (b.dist ?? 999));
    } else if (theme.id === 'food_hidden') {
      // 숨은 맛집: tmap_rank 낮은 순 (덜 알려진)
      list.sort((a, b) => b.tmap_rank - a.tmap_rank);
    } else {
      list.sort((a, b) => (b.scores.family + b.scores.couple + b.scores.single) - (a.scores.family + a.scores.couple + a.scores.single));
    }

    // 위치 없을 때 안내 배너 삽입
    if (!userLat && theme.id === 'food_near') {
      container.innerHTML = `
        <div class="geo-notice">
          <i class="fa-solid fa-location-crosshairs"></i>
          <div class="geo-notice__text">
            <strong>위치 권한이 필요합니다</strong>
            <p>내 주변 맛집을 보려면 브라우저 위치 권한을 허용해 주세요.</p>
          </div>
          <button class="geo-retry-btn" id="geo-retry-btn">권한 허용</button>
        </div>
        <p style="font-size:12px;color:var(--nh-text-sec);text-align:center;padding:0 20px 16px">위치 허용 전에도 다른 테마의 맛집을 먼저 확인하실 수 있어요.</p>`;
      document.getElementById('geo-retry-btn')?.addEventListener('click', () => { requestGeolocation(); });
      // 위치 없어도 맛집 전체를 아래에 보여줌
      list = [...mergedData].filter(p => p.category && p.category.startsWith('맛집/'));
    }
  } else {
    const scoreKey = currentSeg === 'family' ? 'family' : currentSeg === 'couple' ? 'couple' : 'single';
    // 세그먼트별 필수 필터
    if (currentSeg === 'family') {
      list = list.filter(p =>
        p.no_kids_zone !== 'TRUE' &&
        p.is_parking_available === 'TRUE' &&
        (p.is_stroller_accessible === 'TRUE' || p.has_nursing_room === 'TRUE')
      );
    } else if (currentSeg === 'couple') {
      list = list.filter(p => p.crowd !== 'VERY_CONGESTED');
    }
    // 테마 카테고리 필터
    if (allowedCats.length) {
      const filtered = list.filter(p => allowedCats.some(cat => p.category && p.category.includes(cat.replace('/야외','').replace('/전시',''))));
      if (filtered.length >= 2) list = filtered;
    }
    list.sort((a, b) => b.scores[scoreKey] - a.scores[scoreKey]);
  }

  // 검색 필터 (공통)
  if (query) {
    list = list.filter(p =>
      p.name?.toLowerCase().includes(query) ||
      p.address?.toLowerCase().includes(query) ||
      p.category?.toLowerCase().includes(query) ||
      (p.ev?.title || '').toLowerCase().includes(query) ||
      p.tags.some(t => t.toLowerCase().includes(query))
    );
  }

  // 페이지네이션
  const total = list.length;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  if (currentPage > totalPages) currentPage = totalPages;
  const paged = list.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  // 렌더
  if (!paged.length) {
    if (!isFood || userLat) {
      container.innerHTML = `
        <div class="no-results">
          <i class="fa-solid fa-magnifying-glass"></i>
          <p>해당 테마에 맞는 장소가 없어요.<br>다른 테마를 선택해 보세요.</p>
        </div>`;
      paginBar.hidden = true;
      return;
    }
  }

  const listHTML = paged.map((pl, idx) => {
    const rank = (currentPage - 1) * PAGE_SIZE + idx + 1;
    const isFav = favorites.includes(pl.place_id);
    const emoji = CAT_EMOJI[pl.category] || (isFood ? '🍽️' : '📍');
    const pills = buildPills(pl, isFood);

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
  }).join('');

  // 맛집 탭에서 위치 없을 때 안내 뒤에 목록을 추가
  if (isFood && !userLat && theme.id === 'food_near') {
    container.innerHTML += listHTML;
  } else {
    container.innerHTML = listHTML;
  }

  container.querySelectorAll('.fav-btn').forEach(btn => {
    btn.addEventListener('click', e => { e.stopPropagation(); toggleFav(btn.dataset.pid, btn); });
  });
  container.querySelectorAll('.place-item').forEach(item => {
    item.addEventListener('click', () => openDetail(item.dataset.id));
    item.addEventListener('keydown', e => { if (e.key === 'Enter') openDetail(item.dataset.id); });
  });

  if (totalPages > 1) {
    paginBar.hidden = false;
    document.getElementById('page-info').textContent = `${currentPage} / ${totalPages}`;
    document.getElementById('page-prev').disabled = currentPage <= 1;
    document.getElementById('page-next').disabled = currentPage >= totalPages;
  } else {
    paginBar.hidden = true;
  }
}

function buildPills(pl, isFood = false) {
  const pills = [];
  if (isFood) {
    // 맛집용: 거리 + 평점 + 노키즈 여부 위주
    if (pl.dist !== undefined && pl.dist !== null) {
      pills.push(`<span class="badge-pill food-dist">📍 ${formatDist(pl.dist)}</span>`);
    }
    if (pl.no_kids_zone === 'TRUE') pills.push('<span class="badge-pill red">🚫 노키즈존</span>');
    if (pl.is_parking_available === 'TRUE') pills.push('<span class="badge-pill green">🅿 주차가능</span>');
    const crowd = pl.crowd;
    const crowdClass = { LOW:'green', MODERATE:'orange', CONGESTED:'orange', VERY_CONGESTED:'red' }[crowd] || 'gray';
    pills.push(`<span class="badge-pill ${crowdClass}">${CROWD_LABEL[crowd] || crowd}</span>`);
  } else {
    if (pl.is_parking_available === 'TRUE')   pills.push('<span class="badge-pill green">🅿 주차가능</span>');
    if (pl.is_stroller_accessible === 'TRUE') pills.push('<span class="badge-pill green">👶 유모차</span>');
    if (pl.has_nursing_room === 'TRUE')       pills.push('<span class="badge-pill blue">🍼 수유실</span>');
    if (pl.no_kids_zone === 'TRUE')           pills.push('<span class="badge-pill red">🚫 노키즈존</span>');
    const crowd = pl.crowd;
    const crowdClass = { LOW:'green', MODERATE:'orange', CONGESTED:'orange', VERY_CONGESTED:'red' }[crowd] || 'gray';
    pills.push(`<span class="badge-pill ${crowdClass}">${CROWD_LABEL[crowd] || crowd}</span>`);
  }
  return pills.join('');
}

// ── 즐겨찾기 ─────────────────────────────────────────
function toggleFav(pid, btn) {
  const idx = favorites.indexOf(pid);
  if (idx >= 0) {
    favorites.splice(idx, 1);
    btn.classList.remove('active');
    btn.querySelector('i').className = 'fa-regular fa-star';
  } else {
    favorites.push(pid);
    btn.classList.add('active');
    btn.querySelector('i').className = 'fa-solid fa-star';
  }
  localStorage.setItem('nh_favorites', JSON.stringify(favorites));
}

// ── 바텀시트 상세 ────────────────────────────────────
function openDetail(placeId) {
  const pl = mergedData.find(p => p.place_id === placeId);
  if (!pl) return;
  const ev = pl.ev || {};
  const mapUrl = `https://map.kakao.com/link/search/${encodeURIComponent(pl.name)}`;
  const crowdClass = pl.crowd || 'LOW';
  const isFood = pl.category?.startsWith('맛집/');
  const emoji = CAT_EMOJI[pl.category] || (isFood ? '🍽️' : '📍');

  // 거리 계산 (상세 오픈 시점)
  const dist = calcDistance(userLat, userLon, parseFloat(pl.latitude), parseFloat(pl.longitude));

  const tagHTML = pl.tags.filter(t => !['food','한식','양식','일식','아시안','카페','디저트'].includes(t)).length
    ? `<div class="detail-tags">${pl.tags.filter(t => !['food'].includes(t)).map(t => `<span class="detail-tag">#${t}</span>`).join('')}</div>`
    : '';

  const eventHTML = ev.title ? `
    <div class="detail-divider"></div>
    <div class="detail-section-title"><i class="fa-solid fa-${isFood ? 'utensils' : 'gift'}"></i> ${isFood ? '오늘의 특선' : '주요 행사'}</div>
    <div class="detail-event-box">
      <div class="detail-event-title">${ev.title}</div>
      <div class="detail-event-desc">${ev.raw_description || ''}</div>
      <div class="detail-event-date"><i class="fa-regular fa-calendar"></i> ${ev.start_date || ''} ~ ${ev.end_date || ''}</div>
    </div>` : '';

  const distRow = (isFood && dist !== null) ? `
    <div class="crowd-row">
      <span class="crowd-label">현재 위치에서</span>
      <span class="crowd-val LOW"><i class="fa-solid fa-location-dot"></i> ${formatDist(dist)}</span>
    </div>` : '';

  document.getElementById('sheet-body').innerHTML = `
    <div class="detail-cat">${pl.category || '장소'}</div>
    <div class="detail-name">${emoji} ${pl.name}</div>
    <div class="detail-addr"><i class="fa-solid fa-location-dot" style="color:var(--nh-green)"></i>${pl.address || '-'}</div>
    <div class="detail-badges">${buildPills({ ...pl, dist }, isFood)}</div>

    <div class="detail-divider"></div>
    <div class="detail-section-title"><i class="fa-solid fa-tower-broadcast"></i> 실시간 현황</div>
    ${distRow}
    <div class="crowd-row">
      <span class="crowd-label">현재 ${isFood ? '웨이팅' : '인파'} 혼잡도</span>
      <span class="crowd-val ${crowdClass}">${CROWD_LABEL[crowdClass] || crowdClass}</span>
    </div>

    ${eventHTML}

    ${pl.tags.length ? `<div class="detail-divider"></div>
    <div class="detail-section-title"><i class="fa-solid fa-tags"></i> AI 매칭 태그</div>
    ${tagHTML}` : ''}

    <a href="${mapUrl}" target="_blank" class="map-btn"><i class="fa-solid fa-map-location-dot"></i> 카카오맵으로 길찾기</a>
  `;

  document.getElementById('detail-sheet').classList.add('open');
  document.getElementById('sheet-overlay').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeDetail() {
  document.getElementById('detail-sheet').classList.remove('open');
  document.getElementById('sheet-overlay').classList.remove('open');
  document.body.style.overflow = '';
}

// ── 모달 통계 ─────────────────────────────────────────
function updateModalStats() {
  document.getElementById('m-places').textContent = placesData.length + '개';
  document.getElementById('m-events').textContent = eventsData.length + '개';
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
      // 맛집 탭 진입 시 위치 정보 요청
      if (currentSeg === 'food') requestGeolocation();
      renderThemeChips();
      renderList();
    });
  });

  // 검색 토글
  document.getElementById('search-toggle-btn')?.addEventListener('click', () => {
    const wrap = document.getElementById('search-bar-wrap');
    const hidden = wrap.hasAttribute('hidden');
    if (hidden) { wrap.removeAttribute('hidden'); wrap.querySelector('input').focus(); }
    else { wrap.setAttribute('hidden',''); wrap.querySelector('input').value = ''; currentPage=1; renderList(); }
  });

  // 검색 입력
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

  // 갱신 버튼 & 모달 이벤트
  document.getElementById('bnav-refresh')?.addEventListener('click', () => {
    document.getElementById('refresh-modal-overlay').classList.add('open');
  });
  document.getElementById('refresh-modal-close')?.addEventListener('click', () => {
    document.getElementById('refresh-modal-overlay').classList.remove('open');
  });

  // 🔄 실시간 수집 수동 실행 버튼 이벤트
  document.getElementById('run-collect-btn')?.addEventListener('click', async () => {
    const btn = document.getElementById('run-collect-btn');
    const statusBox = document.getElementById('collect-status-box');
    const statusText = document.getElementById('collect-status-text');

    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 실시간 수집 실행 중...';
    statusBox.removeAttribute('hidden');
    statusText.style.color = 'var(--nh-green)';
    statusText.innerHTML = '⏳ 서울시 115곳 혼잡도 + 문화행사 100건 + 네이버 트렌드 수집 파이프라인 구동 중... (약 10~15초 소요)';

    try {
      const res = await fetch('/api/refresh', { method: 'POST' });
      const data = await res.json();

      if (data.success) {
        statusText.style.color = 'var(--nh-green)';
        statusText.innerHTML = `✅ ${data.status_msg || '실시간 데이터 수집 완료!'}`;
        // 데이터 다시 로드하여 최신 반영
        await loadData();
      } else {
        statusText.style.color = 'var(--nh-red)';
        statusText.innerHTML = `❌ ${data.message || '수집 실행 중 오류가 발생했습니다.'}`;
      }
    } catch (err) {
      console.error(err);
      statusText.style.color = 'var(--nh-red)';
      statusText.innerHTML = '❌ 서버 수집 요청 실패. (run_web.py가 실행 중인지 확인하세요)';
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="fa-solid fa-rotate"></i> 실시간 데이터 수집 실행';
    }
  });
}
