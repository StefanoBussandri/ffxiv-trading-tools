const tbody = document.querySelector('#favs tbody');
const thead = document.querySelector('#favs thead');
const statusEl = document.querySelector('#status');
const refreshBtn = document.querySelector('#refresh');
const staleChk = document.querySelector('#filter-stale');
const bargainChk = document.querySelector('#filter-bargain');

let allRows = [];
let taxRate = 0;
let layout = FT.loadColumnLayout('favourites');
let baseStatus = '';  // load-time status string, restored when search clears

function setLoading(on, label) {
  statusEl.textContent = label || (on ? 'Loading' : '');
  statusEl.classList.toggle('loading', !!on);
}

function renderActions(row) {
  return `<td class="col-actions">
    <button class="star filled" data-iid="${row.itemId}" data-q="${row.quality}" title="Remove favourite">★</button>
  </td>`;
}

const ROW_CTX = { renderActions };

function rebuildHeader() {
  FT.buildThead(thead, layout);
}

async function load() {
  setLoading(true, 'Loading');
  try {
    const tax = await FT.getTaxInfo();
    taxRate = FT.effectiveTaxRate(tax, FT.loadSettings());
    const r = await fetch('/api/favourites/snapshot');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const data = await r.json();
    for (const row of data.rows) FT.recomputeProfit(row, taxRate);
    allRows = data.rows;
    renderFiltered();
    baseStatus = `${data.rows.length} favourites · ${new Date(data.ts).toLocaleTimeString()}`;
    setLoading(false, baseStatus);
  } catch (e) {
    setLoading(false, 'Error: ' + e.message);
    if (window.toast) window.toast(e.message);
  }
}

function renderFiltered() {
  let rows = allRows;
  if (staleChk?.checked) rows = rows.filter((r) => r.stale_listing);
  if (bargainChk?.checked) rows = rows.filter((r) => (r.spread_pct || 0) < 0);
  const q = (window.FTSearch && window.FTSearch.term()) || '';
  if (q) rows = rows.filter((r) => FT.matchesSearch(r, q));
  if (q) statusEl.textContent = `${rows.length} of ${allRows.length}`;
  else if (baseStatus) statusEl.textContent = baseStatus;
  render(rows);
}

function render(rows) {
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="${FT.visibleColCount(layout)}" class="empty-state">${FT.emptySearchMsg('No favourites yet. Star items from any opportunities page.')}</td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map((row) => `<tr data-iid="${row.itemId}" data-q="${row.quality}">${FT.buildRowHtml(row, layout, ROW_CTX)}</tr>`).join('');
  attachRowHandlers();
}

function attachRowHandlers() {
  for (const btn of tbody.querySelectorAll('.star')) {
    btn.addEventListener('click', async () => {
      await fetch(`/api/favourites/${btn.dataset.iid}/${btn.dataset.q}`, { method: 'DELETE' });
      load();
    });
  }
}

// Price-alert cells: any edit writes the whole rule set for that favourite.
tbody.addEventListener('change', (e) => {
  const cell = e.target.closest('.alert-cell');
  if (!cell) return;
  const tr = cell.closest('tr');
  const payload = {};
  for (const c of tr.querySelectorAll('.alert-cell')) {
    const v = c.querySelector('.alert-val').value.trim();
    payload[c.dataset.side + '_target'] = v === '' ? null : (parseInt(v, 10) || null);
    payload[c.dataset.side + '_dir'] = c.querySelector('.alert-dir').value;
  }
  fetch(`/api/favourites/${cell.dataset.iid}/${cell.dataset.q}/alert`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).then(() => {
    // Only this favourite's alerts re-evaluate — others never re-ping.
    if (window.FTAlerts) window.FTAlerts.reset(cell.dataset.iid, cell.dataset.q);
  }).catch(() => {});
});

refreshBtn?.addEventListener('click', () => {
  load();
  if (window.FTAlerts) window.FTAlerts.recheck();      // favourites rescan resets alerts
});
staleChk?.addEventListener('change', renderFiltered);
bargainChk?.addEventListener('change', renderFiltered);
window.addEventListener('ft-search-changed', renderFiltered);
// Refresh when a scan finishes (auto-rescan / first-run) — no separate poll.
window.addEventListener('ft-data-refreshed', load);
window.addEventListener('ft-settings-changed', () => { FT.invalidateTaxInfo(); load(); });
window.addEventListener('ft-columns-changed', (e) => {
  if (e.detail && e.detail.page && e.detail.page !== 'favourites') return;
  layout = FT.loadColumnLayout('favourites');
  rebuildHeader();
  renderFiltered();
});

(async () => {
  rebuildHeader();
  await load();
})();
