/* ══════════════════════════════
   주말해 앱 JavaScript
   ══════════════════════════════ */

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
};

// 테마별 카테고리-태그 매핑 (어떤 place가 이 테마에 속하는지)
const THEME_FILTER = {
  summer:     ['공원/야외', '테마파크'],
  healing:    ['공원/야외', '도서/문화', '박물관/전시'],
  theme:      ['테마파크'],
  nature:     ['공원/야외'],
  experience: ['박물관/전시', '미술관/전시', '복합문화공간'],
  indoor:     ['복합문화공간', '미술관/전시', '박물관/전시'],
  popup:      ['팝업스토어', '복합문화공간'],
  concert:    ['팝업스토어', '복합문화공간', '미술관/전시'],
  nightview:  ['공원/야외', '문화유산/역사'],
  cafe:       ['카페/식음', '팝업스토어'],
  exhibition: ['미술관/전시', '박물관/전시', '문화유산/역사'],
  bookstore:  ['도서/문화'],
  culture:    ['문화유산/역사', '박물관/전시'],
};

// 이모지 썸네일 (카테고리별)
const CAT_EMOJI = {
  '공원/야외': '🌳', '팝업스토어': '🎁', '미술관/전시': '🖼️',
  '복합문화공간': '🏢', '문화유산/역사': '🏯', '박물관/전시': '🏛️',
  '도서/문화': '📚', '카페/식음': '☕', '테마파크': '🎢',
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

  // 1) 세그먼트 점수 기반 정렬
  let list = [...mergedData];
  const scoreKey = currentSeg === 'family' ? 'family' : currentSeg === 'couple' ? 'couple' : 'single';

  // 2) 세그먼트별 필수 필터
  if (currentSeg === 'family') {
    list = list.filter(p =>
      p.no_kids_zone !== 'TRUE' &&
      p.is_parking_available === 'TRUE' &&
      (p.is_stroller_accessible === 'TRUE' || p.has_nursing_room === 'TRUE')
    );
  } else if (currentSeg === 'couple') {
    list = list.filter(p => p.crowd !== 'VERY_CONGESTED');
  }

  // 3) 테마 카테고리 필터
  if (allowedCats.length) {
    list = list.filter(p => allowedCats.some(cat => p.category && p.category.includes(cat.replace('/야외','').replace('/전시',''))));
    // 결과가 너무 적으면 필터 완화 (점수 상위 순으로 전체 보여주기)
    if (list.length < 2) {
      list = [...mergedData];
      if (currentSeg === 'family') list = list.filter(p => p.no_kids_zone !== 'TRUE');
      if (currentSeg === 'couple') list = list.filter(p => p.crowd !== 'VERY_CONGESTED');
    }
  }

  // 4) 검색 필터
  if (query) {
    list = list.filter(p =>
      p.name?.toLowerCase().includes(query) ||
      p.address?.toLowerCase().includes(query) ||
      p.category?.toLowerCase().includes(query) ||
      (p.ev?.title || '').toLowerCase().includes(query) ||
      p.tags.some(t => t.toLowerCase().includes(query))
    );
  }

  // 5) 정렬
  list.sort((a, b) => b.scores[scoreKey] - a.scores[scoreKey]);

  // 6) 페이지네이션
  const total = list.length;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  if (currentPage > totalPages) currentPage = totalPages;
  const paged = list.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  // 7) 렌더
  if (!paged.length) {
    container.innerHTML = `
      <div class="no-results">
        <i class="fa-solid fa-magnifying-glass"></i>
        <p>해당 테마에 맞는 장소가 없어요.<br>다른 테마를 선택해 보세요.</p>
      </div>`;
    paginBar.hidden = true;
    return;
  }

  container.innerHTML = paged.map((pl, idx) => {
    const rank = (currentPage - 1) * PAGE_SIZE + idx + 1;
    const isFav = favorites.includes(pl.place_id);
    const emoji = CAT_EMOJI[pl.category] || '📍';
    const mapUrl = `https://map.kakao.com/link/search/${encodeURIComponent(pl.name)}`;

    const pills = buildPills(pl);

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

  // 즐겨찾기 버튼 이벤트
  container.querySelectorAll('.fav-btn').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      toggleFav(btn.dataset.pid, btn);
    });
  });

  // 아이템 클릭 → 상세 바텀시트
  container.querySelectorAll('.place-item').forEach(item => {
    item.addEventListener('click', () => openDetail(item.dataset.id));
    item.addEventListener('keydown', e => { if (e.key === 'Enter') openDetail(item.dataset.id); });
  });

  // 페이지네이션
  if (totalPages > 1) {
    paginBar.hidden = false;
    document.getElementById('page-info').textContent = `${currentPage} / ${totalPages}`;
    document.getElementById('page-prev').disabled = currentPage <= 1;
    document.getElementById('page-next').disabled = currentPage >= totalPages;
  } else {
    paginBar.hidden = true;
  }
}

function buildPills(pl) {
  const pills = [];
  if (pl.is_parking_available === 'TRUE')  pills.push('<span class="badge-pill green">🅿 주차가능</span>');
  if (pl.is_stroller_accessible === 'TRUE') pills.push('<span class="badge-pill green">👶 유모차</span>');
  if (pl.has_nursing_room === 'TRUE')       pills.push('<span class="badge-pill blue">🍼 수유실</span>');
  if (pl.no_kids_zone === 'TRUE')           pills.push('<span class="badge-pill red">🚫 노키즈존</span>');
  const crowd = pl.crowd;
  const crowdClass = { LOW:'green', MODERATE:'orange', CONGESTED:'orange', VERY_CONGESTED:'red' }[crowd] || 'gray';
  pills.push(`<span class="badge-pill ${crowdClass}">${CROWD_LABEL[crowd] || crowd}</span>`);
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
  const emoji = CAT_EMOJI[pl.category] || '📍';

  const tagHTML = pl.tags.length
    ? `<div class="detail-tags">${pl.tags.map(t => `<span class="detail-tag">#${t}</span>`).join('')}</div>`
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
    <div class="detail-badges">${buildPills(pl)}</div>

    <div class="detail-divider"></div>
    <div class="detail-section-title"><i class="fa-solid fa-tower-broadcast"></i> 실시간 현황</div>
    <div class="crowd-row">
      <span class="crowd-label">현재 인파 혼잡도</span>
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

  // 갱신 버튼
  document.getElementById('bnav-refresh')?.addEventListener('click', () => {
    document.getElementById('refresh-modal-overlay').classList.add('open');
  });
  document.getElementById('refresh-modal-close')?.addEventListener('click', () => {
    document.getElementById('refresh-modal-overlay').classList.remove('open');
  });
}
