/* ══════════════════════════════════════════════════════════════
   주말해 Admin JavaScript v4.0
   통합 배치 파이프라인 (18단계) & 다중 데이터셋 (가족/커플/싱글) 지원
   ══════════════════════════════════════════════════════════════ */

let currentDataset = 'family'; // 'family' | 'couple' | 'single'
let allData        = [];
let filteredData   = [];
let currentTable   = 'all';
let currentPage    = 1;
const PAGE_SIZE    = 25;
let sortCol        = null;
let sortAsc        = true;
let pollInterval   = null;

// ── 데이터셋 메타 구성 ──────────────────────────────────────────
const DATASET_CONFIG = {
  family: {
    id: 'family',
    name: '가족',
    file: '../data/total_family_data.csv',
    categories: [
      { id: 'all', label: '전체 DB', icon: 'fa-table' },
      { id: '공공키즈카페', label: '공공키즈카페', icon: 'fa-landmark' },
      { id: '사설키즈카페', label: '사설키즈카페', icon: 'fa-house-chimney' },
      { id: '자연친화', label: '자연친화', icon: 'fa-leaf' },
      { id: '문화생활', label: '문화생활', icon: 'fa-masks-theater' },
      { id: '가족체험', label: '가족체험', icon: 'fa-bullseye' },
    ],
    stats: [
      { label: '총 데이터 건수', icon: 'fa-database', color: '#60A5FA', filter: () => true },
      { label: '공공키즈카페', icon: 'fa-landmark', color: '#8B5CF6', filter: r => r.category === '공공키즈카페' },
      { label: '사설키즈카페', icon: 'fa-house-chimney', color: '#22D3EE', filter: r => r.category === '사설키즈카페' || r.category === '키즈카페' },
      { label: '자연친화', icon: 'fa-leaf', color: '#4ADE80', filter: r => r.category === '자연친화' },
      { label: '문화생활', icon: 'fa-masks-theater', color: '#C084FC', filter: r => r.category === '문화생활' },
      { label: '가족체험', icon: 'fa-bullseye', color: '#FB923C', filter: r => r.category === '가족체험' },
      { label: '예매 가능', icon: 'fa-ticket', color: '#34D399', filter: r => r.booking_url && r.booking_url.startsWith('http') }
    ]
  },
  couple: {
    id: 'couple',
    name: '커플',
    file: '../data/total_couple_data.csv',
    categories: [
      { id: 'all', label: '전체 DB', icon: 'fa-table' },
      { id: '전시/미술관', label: '전시/미술관', icon: 'fa-palette' },
      { id: '감성카페', label: '감성카페', icon: 'fa-mug-saucer' },
      { id: '야경/드라이브', label: '야경/드라이브', icon: 'fa-moon' },
      { id: '액티비티', label: '액티비티', icon: 'fa-bolt' },
      { id: '힐링/스파', label: '힐링/스파', icon: 'fa-spa' },
      { id: '공연/뮤지컬', label: '공연/뮤지컬', icon: 'fa-music' },
      { id: '데이트맛집', label: '데이트맛집', icon: 'fa-utensils' },
      { id: '테마파크', label: '테마파크', icon: 'fa-icons' },
    ],
    stats: [
      { label: '총 데이터 건수', icon: 'fa-database', color: '#60A5FA', filter: () => true },
      { label: '전시/미술관', icon: 'fa-palette', color: '#C084FC', filter: r => (r.category || '').includes('전시') || (r.category || '').includes('미술관') },
      { label: '감성카페', icon: 'fa-mug-saucer', color: '#FB923C', filter: r => (r.category || '').includes('카페') },
      { label: '야경/드라이브', icon: 'fa-moon', color: '#818CF8', filter: r => (r.category || '').includes('야경') || (r.category || '').includes('드라이브') },
      { label: '액티비티/체험', icon: 'fa-bolt', color: '#F43F5E', filter: r => (r.category || '').includes('액티비티') || (r.category || '').includes('체험') || (r.category || '').includes('테마파크') },
      { label: '공연/문화', icon: 'fa-music', color: '#A78BFA', filter: r => (r.category || '').includes('공연') || (r.category || '').includes('뮤지컬') || (r.category || '').includes('연극') || (r.category || '').includes('음악') || (r.category || '').includes('무용') },
      { label: '예매 가능', icon: 'fa-ticket', color: '#34D399', filter: r => r.booking_url && r.booking_url.startsWith('http') }
    ]
  },
  single: {
    id: 'single',
    name: '싱글매니아',
    file: '../data/total_single_data.csv',
    categories: [
      { id: 'all', label: '전체 DB', icon: 'fa-table' },
      { id: '전시·미술관', label: '전시·미술관', icon: 'fa-palette' },
      { id: '독립서점·북카페', label: '독립서점·북카페', icon: 'fa-book-open' },
      { id: '콘서트·공연', label: '콘서트·공연', icon: 'fa-music' },
      { id: '조용한 힐링', label: '조용한 힐링', icon: 'fa-spa' },
      { id: '역사·문화', label: '역사·문화', icon: 'fa-landmark' },
      { id: '자연·공원', label: '자연·공원', icon: 'fa-tree' },
    ],
    stats: [
      { label: '총 데이터 건수', icon: 'fa-database', color: '#60A5FA', filter: () => true },
      { label: '전시·미술관', icon: 'fa-palette', color: '#C084FC', filter: r => (r.category || '').includes('전시') || (r.category || '').includes('미술') },
      { label: '독립서점·북카페', icon: 'fa-book-open', color: '#22D3EE', filter: r => (r.category || '').includes('서점') || (r.category || '').includes('북카페') },
      { label: '콘서트·공연', icon: 'fa-music', color: '#F43F5E', filter: r => (r.category || '').includes('콘서트') || (r.category || '').includes('공연') },
      { label: '조용한 힐링', icon: 'fa-spa', color: '#4ADE80', filter: r => (r.category || '').includes('힐링') },
      { label: '역사·문화/자연', icon: 'fa-tree', color: '#FBBF24', filter: r => (r.category || '').includes('역사') || (r.category || '').includes('문화') || (r.category || '').includes('자연') || (r.category || '').includes('공원') },
      { label: '예매 가능', icon: 'fa-ticket', color: '#34D399', filter: r => r.booking_url && r.booking_url.startsWith('http') }
    ]
  }
};

// ── CSV 파싱 ────────────────────────────────────────
function parseCSV(text) {
  const lines = text.split('\n');
  if (!lines.length || !lines[0].trim()) return { headers: [], rows: [] };
  const headers = splitCSVLine(lines[0]);
  const rows = lines.slice(1).filter(l => l.trim()).map(l => {
    const vals = splitCSVLine(l);
    const row = {};
    headers.forEach((h, i) => row[h.trim()] = (vals[i] || '').trim());
    return row;
  });
  return { headers: headers.map(h => h.trim()), rows };
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
  const cfg = DATASET_CONFIG[currentDataset];
  try {
    const res = await fetch(`${cfg.file}?t=${Date.now()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const text = await res.text();
    const { rows } = parseCSV(text);
    allData = rows;
    filteredData = rows;

    renderStats(rows);
    renderCategorySwitcher();
    applyFilter();
  } catch (err) {
    console.error(`데이터 로드 실패 (${currentDataset}):`, err);
    document.getElementById('table-body').innerHTML =
      `<tr><td colspan="9" style="color:#F87171;text-align:center;padding:24px;">데이터 로드 실패 (${cfg.name}): ${err.message}</td></tr>`;
  }
}

// ── 통계 카드 동적 렌더링 ─────────────────────────────
function renderStats(rows) {
  const grid = document.getElementById('admin-stats-grid');
  if (!grid) return;
  const cfg = DATASET_CONFIG[currentDataset];
  
  grid.innerHTML = cfg.stats.map(stat => {
    const count = rows.filter(stat.filter).length;
    return `
      <div class="stat-box" style="border-left: 3px solid ${stat.color};">
        <div class="stat-icon" style="color: ${stat.color};"><i class="fa-solid ${stat.icon}"></i></div>
        <div class="stat-info">
          <span class="stat-val">${count.toLocaleString()}</span>
          <span class="stat-lbl">${stat.label}</span>
        </div>
      </div>
    `;
  }).join('');
}

// ── 카테고리 스위처 동적 렌더링 ─────────────────────────
function renderCategorySwitcher() {
  const switcher = document.getElementById('table-switcher');
  if (!switcher) return;
  const cfg = DATASET_CONFIG[currentDataset];

  switcher.innerHTML = cfg.categories.map(cat => {
    const isActive = currentTable === cat.id ? 'active' : '';
    return `
      <button class="switcher-btn ${isActive}" data-table="${cat.id}">
        <i class="fa-solid ${cat.icon}"></i> ${cat.label}
      </button>
    `;
  }).join('');

  // 클릭 이벤트 바인딩
  switcher.querySelectorAll('.switcher-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      switcher.querySelectorAll('.switcher-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentTable = btn.dataset.table;
      sortCol = null;
      applyFilter();
    });
  });
}

// ── 18단계 배치 상태 렌더링 ─────────────────────────────
async function checkBatchStatus() {
  try {
    const res = await fetch('/api/batch_status');
    const data = await res.json();
    if (data.batch_state) {
      renderBatchState(data.batch_state);
      if (data.batch_state.is_running && !pollInterval) {
        startBatchPolling();
      }
    }
  } catch (err) {
    console.error('배치 상태 조회 실패:', err);
  }
}

function renderBatchState(bState) {
  const grid = document.getElementById('batch-steps-grid');
  const statusMsgEl = document.getElementById('batch-status-msg');
  const percentTxtEl = document.getElementById('batch-percent-txt');
  const fillEl = document.getElementById('batch-progress-fill');
  const btn = document.getElementById('admin-run-collect-btn');

  if (!grid) return;

  const steps = bState.steps || [];
  const percent = bState.overall_progress || 0;
  const isRunning = bState.is_running;

  // 헤더 및 프로그레스 바 갱신
  const completedCount = steps.filter(s => s.status === 'SUCCESS').length;
  if (statusMsgEl) statusMsgEl.textContent = bState.status_msg || '대기 중';
  if (percentTxtEl) percentTxtEl.textContent = `${percent}% (${completedCount} / ${steps.length || 18} 완료)`;
  if (fillEl) fillEl.style.width = `${percent}%`;

  // 수집 실행 버튼 상태
  if (btn) {
    if (isRunning) {
      btn.disabled = true;
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 18단계 수집 파이프라인 진행 중...';
    } else {
      btn.disabled = false;
      btn.innerHTML = '<i class="fa-solid fa-play"></i> 수집 실행 (전체 18단계 구동)';
    }
  }

  // 18개 배치 카드 렌더링
  grid.innerHTML = steps.map((s, idx) => {
    let badgeClass = 'pending';
    let badgeTxt = '<i class="fa-regular fa-clock"></i> 대기';
    let cardClass = '';

    if (s.status === 'RUNNING') {
      badgeClass = 'running';
      badgeTxt = '<i class="fa-solid fa-spinner fa-spin"></i> 진행중';
      cardClass = 'running';
    } else if (s.status === 'SUCCESS') {
      badgeClass = 'success';
      badgeTxt = '<i class="fa-solid fa-circle-check"></i> 완료';
      cardClass = 'success';
    } else if (s.status === 'ERROR') {
      badgeClass = 'error';
      badgeTxt = '<i class="fa-solid fa-circle-xmark"></i> 오류';
      cardClass = 'error';
    }

    const stepNum = String(idx + 1).padStart(2, '0');
    const cleanTitle = (s.title || '').replace(/^\[배치\s*\d+\]\s*/, '');

    return `
      <div class="batch-step-item ${cardClass}">
        <div class="step-top">
          <div class="step-title-wrap">
            <span class="step-num-badge">Step ${stepNum}</span>
            <span class="step-title">${cleanTitle}</span>
          </div>
          <span class="batch-badge ${badgeClass}">${badgeTxt}</span>
        </div>
        <div class="step-desc">${s.desc || ''}</div>
        <div class="step-script-name"><i class="fa-regular fa-file-code"></i> ${s.name || ''}</div>
        ${s.message ? `
          <div class="step-msg ${s.status}">
            <i class="fa-solid ${s.status === 'ERROR' ? 'fa-triangle-exclamation' : s.status === 'SUCCESS' ? 'fa-check' : 'fa-circle-info'}"></i>
            ${s.message}
          </div>` : ''}
      </div>
    `;
  }).join('');
}

function startBatchPolling() {
  if (pollInterval) clearInterval(pollInterval);
  pollInterval = setInterval(async () => {
    try {
      const res = await fetch('/api/batch_status');
      const data = await res.json();
      const bState = data.batch_state;
      if (bState) {
        renderBatchState(bState);

        // 전체 완료 시 (완료되었습니다. 알림창 출력)
        if (!bState.is_running && bState.overall_progress === 100) {
          clearInterval(pollInterval);
          pollInterval = null;
          alert('가족, 커플, 싱글 전체 데이터 수집 및 갱신이 완료되었습니다!');
          loadData(); // 현재 보고 있는 데이터셋 테이블 리로드
        } else if (!bState.is_running && bState.status_msg.includes('오류')) {
          clearInterval(pollInterval);
          pollInterval = null;
          alert(`⚠️ 배치 완료 (일부 오류 발생): ${bState.status_msg}`);
          loadData();
        }
      }
    } catch (err) {
      console.error('폴링 에러:', err);
    }
  }, 800);
}

// ── 필터 & 정렬 적용 ────────────────────────────────
function applyFilter() {
  const query = (document.getElementById('admin-search-input')?.value || '').toLowerCase().trim();

  let rows = [...allData];

  // 카테고리 필터
  if (currentTable !== 'all') {
    rows = rows.filter(r => {
      const cat = r.category || '';
      const theme = r.theme_ids || '';
      return cat === currentTable || cat.includes(currentTable) || theme.includes(currentTable);
    });
  }

  // 검색어 필터
  if (query) {
    rows = rows.filter(r =>
      (r.place_or_event_name || '').toLowerCase().includes(query) ||
      (r.region || '').toLowerCase().includes(query) ||
      (r.description || '').toLowerCase().includes(query) ||
      (r.recommend_reason || '').toLowerCase().includes(query) ||
      (r.source_site || '').toLowerCase().includes(query) ||
      (r.category || '').toLowerCase().includes(query)
    );
  }

  // 정렬
  if (sortCol) {
    rows.sort((a, b) => {
      const va = a[sortCol] || '';
      const vb = b[sortCol] || '';
      const na = parseFloat(va);
      const nb = parseFloat(vb);
      if (!isNaN(na) && !isNaN(nb)) return sortAsc ? na - nb : nb - na;
      return sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
    });
  }

  filteredData = rows;
  currentPage = 1;
  renderTable();
}

// ── 카테고리 뱃지 헬퍼 ──────────────────────────────
function getCategoryBadge(cat) {
  if (!cat) return '-';
  if (cat.includes('공공키즈')) return `<span class="cat-badge public">🏛️ ${cat}</span>`;
  if (cat.includes('키즈')) return `<span class="cat-badge kids">🏠 ${cat}</span>`;
  if (cat.includes('자연') || cat.includes('공원')) return `<span class="cat-badge nature">🌿 ${cat}</span>`;
  if (cat.includes('문화') || cat.includes('역사')) return `<span class="cat-badge culture">🎭 ${cat}</span>`;
  if (cat.includes('체험') || cat.includes('액티비티')) return `<span class="cat-badge experience">🎯 ${cat}</span>`;
  if (cat.includes('서점') || cat.includes('북카페')) return `<span class="cat-badge public" style="background:rgba(34,211,238,0.15);color:#22D3EE;">📚 ${cat}</span>`;
  if (cat.includes('공연') || cat.includes('콘서트') || cat.includes('뮤지컬') || cat.includes('연극') || cat.includes('음악')) return `<span class="cat-badge culture" style="background:rgba(244,63,94,0.15);color:#F43F5E;">🎵 ${cat}</span>`;
  if (cat.includes('전시') || cat.includes('미술')) return `<span class="cat-badge culture">🖼️ ${cat}</span>`;
  if (cat.includes('카페')) return `<span class="cat-badge experience">☕ ${cat}</span>`;
  if (cat.includes('맛집')) return `<span class="cat-badge nature" style="background:rgba(251,191,36,0.15);color:#FBBF24;">🍽️ ${cat}</span>`;
  if (cat.includes('야경') || cat.includes('드라이브')) return `<span class="cat-badge public" style="background:rgba(129,140,248,0.15);color:#818CF8;">🌙 ${cat}</span>`;
  if (cat.includes('힐링') || cat.includes('스파')) return `<span class="cat-badge nature">🌿 ${cat}</span>`;
  return `<span class="cat-badge public">${cat}</span>`;
}

// ── 테이블 렌더링 ─────────────────────────────────────
function renderTable() {
  const thead = document.getElementById('table-headers');
  const tbody = document.getElementById('table-body');
  const pageInfo = document.getElementById('admin-page-info');

  const COLS = [
    { key: 'category',            label: '카테고리',     width: '100px' },
    { key: 'place_or_event_name', label: '장소/행사명',   width: '170px' },
    { key: 'target_age',          label: '대상/기간',     width: '110px' },
    { key: 'region',              label: '지역',          width: '120px' },
    { key: 'fee_info',            label: '요금',          width: '100px' },
    { key: 'recommend_reason',    label: '추천이유 / 설명', width: '220px' },
    { key: 'popularity_score',    label: '인기도',        width: '75px' },
    { key: 'congestion_score',    label: '혼잡도',        width: '65px' },
    { key: 'booking_url',         label: '예매URL',       width: '80px' },
  ];

  thead.innerHTML = COLS.map(col => {
    const arrow = sortCol === col.key ? (sortAsc ? ' ▲' : ' ▼') : '';
    return `<th data-col="${col.key}" style="min-width:${col.width}">${col.label}${arrow}</th>`;
  }).join('');

  thead.querySelectorAll('th').forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.col;
      if (sortCol === col) sortAsc = !sortAsc;
      else { sortCol = col; sortAsc = true; }
      renderTable();
    });
  });

  const total = filteredData.length;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  if (currentPage > totalPages) currentPage = totalPages;
  const paged = filteredData.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  pageInfo.textContent = `${currentPage} / ${totalPages} (총 ${total.toLocaleString()}건)`;

  document.getElementById('admin-page-prev').disabled = currentPage <= 1;
  document.getElementById('admin-page-next').disabled = currentPage >= totalPages;

  if (!paged.length) {
    tbody.innerHTML = `<tr><td colspan="${COLS.length}" style="text-align:center;padding:32px;color:#64748B;">검색 결과가 없습니다.</td></tr>`;
    return;
  }

  tbody.innerHTML = paged.map(row => {
    const regionShort = (row.region || '').split('|')[0].trim().substring(0, 16);
    const recReason   = (row.recommend_reason || row.description || '').substring(0, 50);
    const feeShort    = (row.fee_info || '').substring(0, 14);
    const targetInfo  = row.target_age || row.period || row.origin || '전체';

    const pop = parseFloat(row.popularity_score) || 0;
    const popBar = `
      <div class="score-cell">
        <span style="font-size:11px;font-weight:700;color:#F1F5F9">${Math.round(pop)}</span>
        <div class="score-bar" style="display:block;margin-top:3px">
          <div class="score-bar-fill" style="width:${Math.min(pop,100)}%"></div>
        </div>
      </div>`;

    const cong = parseInt(row.congestion_score) || 1;
    const congColor = cong <= 1 ? '#4ADE80' : cong <= 2 ? '#FBBF24' : cong <= 3 ? '#F97316' : '#F87171';
    const congCell = `<span style="font-weight:700;color:${congColor}">${cong}</span>`;

    const bookingCell = row.booking_url && row.booking_url.startsWith('http')
      ? `<a href="${row.booking_url}" target="_blank">🎫 예매</a>`
      : '<span style="color:#475569">-</span>';

    return `<tr>
      <td>${getCategoryBadge(row.category)}</td>
      <td class="name-cell" title="${row.place_or_event_name || ''}">${row.place_or_event_name || '-'}</td>
      <td style="font-size:11px;color:#94A3B8" title="${targetInfo}">${targetInfo}</td>
      <td title="${row.region || ''}">${regionShort}</td>
      <td style="font-size:11px">${feeShort || '-'}</td>
      <td class="desc-cell" style="cursor:pointer" data-desc="${encodeURIComponent(row.description || '')}" data-reason="${encodeURIComponent(row.recommend_reason || '')}" data-name="${encodeURIComponent(row.place_or_event_name || '')}">
        <div style="font-size:11px;color:#38BDF8;font-weight:600">${recReason}</div>
      </td>
      <td>${popBar}</td>
      <td style="text-align:center">${congCell}</td>
      <td class="url-cell">${bookingCell}</td>
    </tr>`;
  }).join('');

  // 설명 클릭 → 모달
  tbody.querySelectorAll('td[data-desc]').forEach(td => {
    td.addEventListener('click', () => {
      const name = decodeURIComponent(td.dataset.name);
      const desc = decodeURIComponent(td.dataset.desc);
      const reason = decodeURIComponent(td.dataset.reason);
      document.getElementById('details-modal-title').textContent = name;
      document.getElementById('details-modal-desc').innerHTML = `
        ${reason ? `<div style="margin-bottom:12px;padding:10px;background:rgba(56,189,248,0.1);border-radius:8px;color:#38BDF8;font-weight:700;">${reason}</div>` : ''}
        <div>${desc || '상세 설명 없음'}</div>
      `;
      document.getElementById('details-modal').classList.add('open');
    });
  });
}

// ── CSV 내보내기 ────────────────────────────────────
function exportCSV() {
  if (!filteredData.length) return;
  const headers = Object.keys(filteredData[0] || {});
  const csvRows = [
    headers.join(','),
    ...filteredData.map(row =>
      headers.map(h => {
        const val = (row[h] || '').replace(/"/g, '""');
        return val.includes(',') || val.includes('\n') ? `"${val}"` : val;
      }).join(',')
    )
  ].join('\n');

  const blob = new Blob(['\uFEFF' + csvRows], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `total_${currentDataset}_data_${currentTable}_${new Date().toISOString().slice(0,10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── 이벤트 ──────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // 데이터 로드 & 배치 상태 초기화
  loadData();
  checkBatchStatus();

  // 데이터셋 선택기 (가족 / 커플 / 싱글)
  document.querySelectorAll('.dataset-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.dataset-tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentDataset = btn.dataset.dataset;
      currentTable = 'all';
      sortCol = null;
      loadData();
    });
  });

  // 검색
  document.getElementById('admin-search-input')?.addEventListener('input', applyFilter);

  // 페이지네이션
  document.getElementById('admin-page-prev')?.addEventListener('click', () => {
    if (currentPage > 1) { currentPage--; renderTable(); }
  });
  document.getElementById('admin-page-next')?.addEventListener('click', () => {
    const totalPages = Math.ceil(filteredData.length / PAGE_SIZE);
    if (currentPage < totalPages) { currentPage++; renderTable(); }
  });

  // 모달 닫기
  document.getElementById('details-modal-close-btn')?.addEventListener('click', () => {
    document.getElementById('details-modal').classList.remove('open');
  });
  document.getElementById('details-modal')?.addEventListener('click', e => {
    if (e.target === document.getElementById('details-modal')) {
      document.getElementById('details-modal').classList.remove('open');
    }
  });

  // CSV 내보내기
  document.getElementById('admin-export-btn')?.addEventListener('click', exportCSV);

  // 수집 실행 (18단계 전체 배치 파이프라인 시작)
  document.getElementById('admin-run-collect-btn')?.addEventListener('click', async () => {
    try {
      const res = await fetch('/api/refresh', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        startBatchPolling();
      } else {
        alert(`❌ ${data.message || '수집 실행 오류'}`);
      }
    } catch (err) {
      alert('❌ 서버 연결 실패. run_web.py가 실행 중인지 확인하세요.');
    }
  });

  // 주간 날씨 갱신
  document.getElementById('admin-weather-btn')?.addEventListener('click', async () => {
    const btn = document.getElementById('admin-weather-btn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 날씨 갱신 중...';
    try {
      const res = await fetch('/api/weather', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        alert(`✅ ${data.message}`);
      } else {
        alert(`❌ ${data.message || '날씨 갱신 오류'}`);
      }
    } catch (err) {
      alert('❌ 서버 연결 실패. run_web.py가 실행 중인지 확인하세요.');
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<i class="fa-solid fa-cloud-sun"></i> 날씨 갱신';
    }
  });
});
