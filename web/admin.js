/* ══════════════════════════════
   주말해 Admin JavaScript v3.0
   7단계 배치 파이프라인 & total_family_data.csv 기반
   ══════════════════════════════ */

let allData       = [];
let filteredData  = [];
let currentTable  = 'all';
let currentPage   = 1;
const PAGE_SIZE   = 25;
let sortCol       = null;
let sortAsc       = true;
let pollInterval  = null;

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
  try {
    const res = await fetch('../data/total_family_data.csv?t=' + Date.now());
    const text = await res.text();
    const { headers, rows } = parseCSV(text);
    allData = rows;
    filteredData = rows;

    updateStats(rows);
    applyFilter();
  } catch (err) {
    console.error('데이터 로드 실패:', err);
    document.getElementById('table-body').innerHTML =
      `<tr><td colspan="5" style="color:#F87171;text-align:center;padding:24px;">데이터 로드 실패: ${err.message}</td></tr>`;
  }
}

// ── 통계 업데이트 ─────────────────────────────────────
function updateStats(rows) {
  if (document.getElementById('admin-total-count')) document.getElementById('admin-total-count').textContent = rows.length.toLocaleString();
  if (document.getElementById('admin-public-kids-count')) document.getElementById('admin-public-kids-count').textContent = rows.filter(r => r.category === '공공키즈카페').length.toLocaleString();
  if (document.getElementById('admin-private-kids-count')) document.getElementById('admin-private-kids-count').textContent = rows.filter(r => r.category === '사설키즈카페' || r.category === '키즈카페').length.toLocaleString();
  if (document.getElementById('admin-nature-count')) document.getElementById('admin-nature-count').textContent = rows.filter(r => r.category === '자연친화').length.toLocaleString();
  if (document.getElementById('admin-culture-count')) document.getElementById('admin-culture-count').textContent = rows.filter(r => r.category === '문화생활').length.toLocaleString();
  if (document.getElementById('admin-experience-count')) document.getElementById('admin-experience-count').textContent = rows.filter(r => r.category === '가족체험').length.toLocaleString();
  if (document.getElementById('admin-ticket-count')) document.getElementById('admin-ticket-count').textContent = rows.filter(r => r.booking_url && r.booking_url.startsWith('http')).length.toLocaleString();
}

// ── 7단계 배치 상태 렌더링 ─────────────────────────────
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
  if (statusMsgEl) statusMsgEl.textContent = bState.status_msg || '대기 중';
  if (percentTxtEl) percentTxtEl.textContent = `${percent}%`;
  if (fillEl) fillEl.style.width = `${percent}%`;

  // 수집 실행 버튼 상태
  if (btn) {
    if (isRunning) {
      btn.disabled = true;
      btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 수집 파이프라인 진행 중...';
    } else {
      btn.disabled = false;
      btn.innerHTML = '<i class="fa-solid fa-play"></i> 수집 실행 (전체 배치 구동)';
    }
  }

  // 7개 배치 카드 렌더링
  grid.innerHTML = steps.map((s) => {
    let badgeClass = 'pending';
    let badgeTxt = '<i class="fa-regular fa-clock"></i> 대기';
    let cardClass = '';

    if (s.status === 'RUNNING') {
      badgeClass = 'running';
      badgeTxt = '<i class="fa-solid fa-spinner fa-spin"></i> 진행중';
      cardClass = 'running';
    } else if (s.status === 'SUCCESS') {
      badgeClass = 'success';
      badgeTxt = '<i class="fa-solid fa-circle-check"></i> 성공';
      cardClass = 'success';
    } else if (s.status === 'ERROR') {
      badgeClass = 'error';
      badgeTxt = '<i class="fa-solid fa-circle-xmark"></i> 오류';
      cardClass = 'error';
    }

    return `
      <div class="batch-step-item ${cardClass}">
        <div class="step-top">
          <span class="step-title">${s.title}</span>
          <span class="batch-badge ${badgeClass}">${badgeTxt}</span>
        </div>
        <div class="step-desc">${s.desc}</div>
        <div style="font-size:11px;font-weight:600;color:${s.status==='ERROR'?'#F87171':s.status==='RUNNING'?'#38BDF8':s.status==='SUCCESS'?'#34D399':'#64748B'};margin-top:2px;">
          ${s.message || ''}
        </div>
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
          alert('완료되었습니다.');
          loadData(); // 테이블 데이터 리로드
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

  let rows = currentTable === 'all' ? [...allData] : allData.filter(r => r.category === currentTable);

  if (query) {
    rows = rows.filter(r =>
      (r.place_or_event_name || '').toLowerCase().includes(query) ||
      (r.region || '').toLowerCase().includes(query) ||
      (r.description || '').toLowerCase().includes(query) ||
      (r.recommend_reason || '').toLowerCase().includes(query) ||
      (r.source_site || '').toLowerCase().includes(query)
    );
  }

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

// ── 테이블 렌더링 ─────────────────────────────────────
function renderTable() {
  const thead = document.getElementById('table-headers');
  const tbody = document.getElementById('table-body');
  const pageInfo = document.getElementById('admin-page-info');

  const COLS = [
    { key: 'category',            label: '카테고리',   width: '90px' },
    { key: 'place_or_event_name', label: '장소/행사명',  width: '170px' },
    { key: 'target_age',          label: '대상연령',   width: '110px' },
    { key: 'region',              label: '지역',        width: '120px' },
    { key: 'fee_info',            label: '요금',        width: '100px' },
    { key: 'recommend_reason',    label: 'LLM 추천이유', width: '220px' },
    { key: 'popularity_score',    label: '인기도',      width: '75px' },
    { key: 'congestion_score',    label: '혼잡도',      width: '65px' },
    { key: 'booking_url',         label: '예매URL',     width: '80px' },
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

  const catBadge = {
    '공공키즈카페': '<span class="cat-badge public">🏛️ 공공키즈</span>',
    '사설키즈카페': '<span class="cat-badge kids">🏠 사설키즈</span>',
    '키즈카페':     '<span class="cat-badge kids">🏠 사설키즈</span>',
    '자연친화':     '<span class="cat-badge nature">🌿 자연친화</span>',
    '문화생활':     '<span class="cat-badge culture">🎭 문화생활</span>',
    '가족체험':     '<span class="cat-badge experience">🎯 가족체험</span>',
  };

  tbody.innerHTML = paged.map(row => {
    const regionShort = (row.region || '').split('|')[0].trim().substring(0, 16);
    const recReason   = (row.recommend_reason || row.description || '').substring(0, 50);
    const feeShort    = (row.fee_info || '').substring(0, 14);

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
      <td>${catBadge[row.category] || row.category || '-'}</td>
      <td class="name-cell" title="${row.place_or_event_name || ''}">${row.place_or_event_name || '-'}</td>
      <td style="font-size:11px;color:#94A3B8">${row.target_age || '전체'}</td>
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
        <div style="margin-bottom:12px;padding:10px;background:rgba(56,189,248,0.1);border-radius:8px;color:#38BDF8;font-weight:700;">
          ${reason}
        </div>
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
  a.download = `total_family_data_${currentTable}_${new Date().toISOString().slice(0,10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── 이벤트 ──────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadData();
  checkBatchStatus();

  // 테이블 스위처
  document.querySelectorAll('.switcher-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.switcher-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentTable = btn.dataset.table;
      sortCol = null;
      applyFilter();
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

  // 수집 실행 (7단계 전체 배치 파이프라인 시작)
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
