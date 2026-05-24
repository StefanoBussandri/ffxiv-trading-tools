const tbody = document.querySelector('#rel tbody');
const thead = document.querySelector('#rel thead');
const statusEl = document.querySelector('#status');
const refreshBtn = document.querySelector('#refresh');
const confSel = document.querySelector('#confidence');
const sourceSel = document.querySelector('#source');
const qSel = document.querySelector('#quality');

const PAGE = 'reliable';
const PAGE_STATE_DEFAULTS = {
  quality: 'both',
  source: 'all',
  confidence: 'high',
  sort_chain: [{ key: 'score', dir: 'desc' }],
};
const persisted = FT.loadPageState(PAGE, PAGE_STATE_DEFAULTS);

let layout = FT.loadColumnLayout('reliable');
const KEY_ALIAS = { updated: 'sell_upload_ts' };
let favs = new Set();
let baseStatus = '';  // load-time status string, restored when search clears

const state = {
  sort_chain: Array.isArray(persisted.sort_chain) && persisted.sort_chain.length
    ? persisted.sort_chain.slice()
    : [{ key: 'score', dir: 'desc' }],
  rows: [],
  tax_rate: 0,
  commodity: false,
  stale_only: false,
  bargain_only: false,
};

function persistState() {
  FT.savePageState(PAGE, {
    quality: qSel.value,
    source: sourceSel.value,
    confidence: confSel.value,
    sort_chain: state.sort_chain,
  });
}

function syncFiltersFromStore() {
  const f = (window.FTFilters && window.FTFilters.load()) || {};
  state.commodity = !!f.commodity;
  state.stale_only = !!f.stale_only;
  state.bargain_only = !!f.bargain_only;
}

function setLoading(on, label) {
  statusEl.textContent = label || (on ? 'Loading' : '');
  statusEl.classList.toggle('loading', !!on);
  if (refreshBtn) refreshBtn.disabled = on;
}

async function loadFavourites() {
  try {
    const r = await fetch('/api/favourites');
    const d = await r.json();
    favs = new Set(d.rows.map((f) => `${f.item_id}:${f.quality}`));
  } catch {}
}

async function load() {
  setLoading(true, 'Loading');
  try {
    const tax = await FT.getTaxInfo();
    state.tax_rate = FT.effectiveTaxRate(tax, FT.loadSettings());
    const s = FT.loadSettings();
    const params = new URLSearchParams({
      confidence: confSel.value,
      source: sourceSel.value,
      quality: qSel.value,
      top: '100',
    });
    if (s.budget) params.set('budget', s.budget);
    if (state.commodity) params.set('commodity', 'true');
    if (state.stale_only) params.set('stale_only', 'true');
    if (state.bargain_only) params.set('bargain_only', 'true');
    const r = await fetch('/api/reliable?' + params.toString());
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const data = await r.json();
    if (!data.ready) {
      tbody.innerHTML = `<tr><td colspan="${FT.visibleColCount(layout)}" class="empty-state">${data.reason || 'Collecting data — try again later.'}</td></tr>`;
      setLoading(false, 'No data yet');
      return;
    }
    state.rows = data.rows;
    for (const row of state.rows) FT.recomputeProfit(row, state.tax_rate);
    renderSorted();
    if (data.count === 0) {
      tbody.innerHTML = `<tr><td colspan="${FT.visibleColCount(layout)}" class="empty-state">No items meet the current confidence threshold. Try lowering Confidence to "All".</td></tr>`;
    }
    baseStatus = `${data.count} reliable · ${data.candidates || 0} live candidates · ${data.histories_fetched || 0} histories · window ${data.window_days}d`;
    setLoading(false, baseStatus);
  } catch (e) {
    setLoading(false, 'Error: ' + e.message);
    if (window.toast) window.toast(e.message);
  }
}

function renderSorted() {
  const maxScore = Math.max(1, ...state.rows.map((r) => r.score || 0));
  for (const r of state.rows) r.score_norm = (r.score || 0) / maxScore;
  const q = (window.FTSearch && window.FTSearch.term()) || '';
  let rows = state.rows.slice();
  if (q) rows = rows.filter((r) => FT.matchesSearch(r, q));
  rows = FT.sortRows(rows, state.sort_chain, KEY_ALIAS);
  if (q) statusEl.textContent = `${rows.length} of ${state.rows.length}`;
  else if (baseStatus) statusEl.textContent = baseStatus;
  render(rows);
}

function sparkline(series) {
  if (!series || series.length < 2) return '<span class="dim">—</span>';
  const w = 80, h = 22, pad = 2;
  const min = Math.min(...series);
  const max = Math.max(...series);
  const range = max - min || 1;
  const stepX = (w - 2 * pad) / (series.length - 1);
  const pts = series.map((v, i) => {
    const x = pad + i * stepX;
    const y = h - pad - ((v - min) / range) * (h - 2 * pad);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  const last = series[series.length - 1];
  const first = series[0];
  const color = last >= first ? 'var(--profit)' : 'var(--loss)';
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
    <polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.5" />
  </svg>`;
}

function renderActions(row) {
  const key = `${row.itemId}:${row.quality}`;
  const starred = favs.has(key) ? 'filled' : '';
  const rescanUrl = row.source === 'vendor'
    ? `/api/opportunities/vendor/rescan/${row.itemId}`
    : `/api/opportunities/cross-world/rescan/${row.itemId}`;
  return `<td class="col-actions">
    <button class="star ${starred}" data-iid="${row.itemId}" data-q="${row.quality}" title="Toggle favourite">★</button>
    <button class="row-action rescan" data-iid="${row.itemId}" data-url="${rescanUrl}" title="Rescan">↻</button>
  </td>`;
}

const ROW_CTX = { renderActions, sparkline };

function render(rows) {
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="${FT.visibleColCount(layout)}" class="empty-state">${FT.emptySearchMsg('No reliable trades matching filter.')}</td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map((row) => `<tr class="tier-${row.confidence}" data-iid="${row.itemId}" data-q="${row.quality}">${FT.buildRowHtml(row, layout, ROW_CTX)}</tr>`).join('');
  attachHandlers();
}

function attachHandlers() {
  for (const btn of tbody.querySelectorAll('.star')) {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const iid = parseInt(btn.dataset.iid, 10);
      const q = btn.dataset.q;
      const key = `${iid}:${q}`;
      if (favs.has(key)) {
        await fetch(`/api/favourites/${iid}/${q}`, { method: 'DELETE' });
        favs.delete(key); btn.classList.remove('filled');
      } else {
        await fetch('/api/favourites', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ item_id: iid, quality: q }),
        });
        favs.add(key); btn.classList.add('filled');
      }
    });
  }
  for (const btn of tbody.querySelectorAll('.rescan')) {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      btn.disabled = true;
      try {
        const r = await fetch(btn.dataset.url, { method: 'POST' });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        await load();
      } catch (err) {
        if (window.toast) window.toast(err.message);
      } finally {
        btn.disabled = false;
      }
    });
  }
}

function attachSortHandlers() {
  thead.querySelectorAll('th[data-sort]').forEach((th) => {
    th.classList.add('sortable');
    th.addEventListener('click', (e) => {
      FT.handleHeaderClick(state.sort_chain, th.dataset.sort, e.shiftKey);
      FT.renderSortChain(thead, state.sort_chain);
      persistState();
      renderSorted();
    });
  });
  FT.renderSortChain(thead, state.sort_chain);
}

function rebuildHeader() {
  FT.buildThead(thead, layout);
  attachSortHandlers();
}

// Hydrate dropdowns from persisted state.
if (qSel) qSel.value = persisted.quality;
if (sourceSel) sourceSel.value = persisted.source;
if (confSel) confSel.value = persisted.confidence;

confSel.addEventListener('change', () => { persistState(); load(); });
sourceSel.addEventListener('change', () => { persistState(); load(); });
qSel.addEventListener('change', () => { persistState(); load(); });
refreshBtn.addEventListener('click', load);
window.addEventListener('ft-settings-changed', () => { FT.invalidateTaxInfo(); load(); });

window.addEventListener('ft-columns-changed', (e) => {
  if (e.detail && e.detail.page && e.detail.page !== PAGE) return;
  layout = FT.loadColumnLayout(PAGE, 'reliable');
  rebuildHeader();
  renderSorted();
});

window.addEventListener('ft-filters-changed', () => {
  syncFiltersFromStore();
  load();
});

// Search is client-side over the loaded top-N — re-render, no refetch.
window.addEventListener('ft-search-changed', renderSorted);

// A scan finished — pull fresh reliable rows (sort + search are preserved).
window.addEventListener('ft-data-refreshed', load);

(async () => {
  syncFiltersFromStore();
  rebuildHeader();
  await loadFavourites();
  await load();
})();
