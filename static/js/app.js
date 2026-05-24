// Cross-world + vendor opportunities page.
const ENDPOINT = window.OPP_ENDPOINT || '/api/opportunities/cross-world';
const RESCAN_URL = (id) => `${ENDPOINT}/rescan/${id}`;

const tbody = document.querySelector('#opps tbody');
const thead = document.querySelector('#opps thead');
const statusEl = document.querySelector('#status');
const refreshBtn = document.querySelector('#refresh');
const qSel = document.querySelector('#quality');
const pageInfoEl = document.querySelector('#page-info');
const prevBtn = document.querySelector('#prev-page');
const nextBtn = document.querySelector('#next-page');
const COMMODITY_MIN_VEL = 20;
const COMMODITY_MAX_MARGIN_PCT = 15;
function loadFilterState() { return (window.FTFilters && window.FTFilters.load()) || {}; }

const PAGE = (location.pathname.match(/([^/]+)\.html$/)?.[1]) || 'index';
const PAGE_STATE_DEFAULTS = {
  quality: qSel ? qSel.value : 'both',
  sort_chain: [{ key: 'profit_per_day', dir: 'desc' }],
};
const persistedState = FT.loadPageState(PAGE, PAGE_STATE_DEFAULTS);
function persistState() {
  FT.savePageState(PAGE, { quality: state.quality, sort_chain: state.sort_chain });
}

const state = {
  page: 1,
  page_size: 40,
  sort_chain: Array.isArray(persistedState.sort_chain) && persistedState.sort_chain.length
    ? persistedState.sort_chain.slice()
    : [{ key: 'profit_per_day', dir: 'desc' }],
  quality: persistedState.quality || (qSel ? qSel.value : 'both'),
  all_rows: [],
  display_rows: [],
  tax_rate: 0,
  budget: null,
  commodity: false,
  stale_only: false,
  bargain_only: false,
};
function syncFiltersFromStore() {
  const f = loadFilterState();
  state.commodity = !!f.commodity;
  state.stale_only = !!f.stale_only;
  state.bargain_only = !!f.bargain_only;
}

const SORT_KEY_ALIAS = { updated: 'sell_upload_ts' };
let favs = new Set();
let layout = FT.loadColumnLayout(PAGE, 'opps');

function renderActions(row) {
  const key = `${row.itemId}:${row.quality}`;
  const starred = favs.has(key) ? 'filled' : '';
  return `<td class="col-actions">
    <button class="star ${starred}" data-iid="${row.itemId}" data-q="${row.quality}" title="Toggle favourite">★</button>
    <button class="row-action rescan" data-iid="${row.itemId}" title="Rescan this item">↻</button>
  </td>`;
}

function rebuildHeader() {
  FT.buildThead(thead, layout);
  attachSortHandlers();
}

function applySettingsToState() {
  const s = FT.loadSettings();
  state.budget = s.budget || null;
  state.page_size = s.page_size || 40;
}

function setLoading(on, label) {
  if (statusEl) {
    statusEl.textContent = label || (on ? 'Loading' : '');
    statusEl.classList.toggle('loading', !!on);
  }
  if (refreshBtn) refreshBtn.disabled = on;
}

async function loadFavourites() {
  try {
    const r = await fetch('/api/favourites');
    const d = await r.json();
    favs = new Set(d.rows.map((f) => `${f.item_id}:${f.quality}`));
  } catch {
    favs = new Set();
  }
}

async function fetchRows(opts = {}) {
  const params = new URLSearchParams();
  params.set('page', '1');
  params.set('page_size', '10000');
  if (opts.force) params.set('force', 'true');
  if (opts.cached) params.set('cached', 'true');
  const r = await fetch(ENDPOINT + '?' + params.toString());
  if (!r.ok) throw new Error('HTTP ' + r.status);
  const data = await r.json();
  return data.rows || [];
}

async function loadAll({ force = false, keepPage = false } = {}) {
  applySettingsToState();
  const tax = await FT.getTaxInfo();
  state.tax_rate = FT.effectiveTaxRate(tax, FT.loadSettings());
  setLoading(true, force ? 'Rescanning (~40s)' : 'Loading');
  try {
    const rows = await fetchRows({ force });
    state.all_rows = rows;
    recomputeAndShow({ keepPage });
  } catch (e) {
    setLoading(false, 'Error: ' + e.message);
    if (window.toast) window.toast(e.message);
  }
}

function recomputeAndShow({ keepPage = false } = {}) {
  for (const r of state.all_rows) FT.recomputeProfit(r, state.tax_rate);
  applyClientFilters();
  if (!keepPage) state.page = 1;
  renderPage();
}

function applyClientFilters() {
  let rows = state.all_rows;
  if (state.quality !== 'both') rows = rows.filter((r) => r.quality === state.quality);
  if (state.budget) rows = rows.filter((r) => r.buy_price != null && r.buy_price <= state.budget);
  if (state.commodity) {
    rows = rows.filter((r) =>
      (r.velocity || 0) >= COMMODITY_MIN_VEL && (r.roi_pct || 0) <= COMMODITY_MAX_MARGIN_PCT);
  }
  if (state.stale_only) rows = rows.filter((r) => r.stale_listing);
  if (state.bargain_only) rows = rows.filter((r) => (r.spread_pct || 0) < 0);
  const q = (window.FTSearch && window.FTSearch.term()) || '';
  if (q) rows = rows.filter((r) => FT.matchesSearch(r, q));
  rows = FT.sortRows(rows.slice(), state.sort_chain, SORT_KEY_ALIAS);
  state.display_rows = rows;
}

function pageCount() {
  return Math.max(1, Math.ceil(state.display_rows.length / state.page_size));
}

function renderPage() {
  const total = pageCount();
  if (state.page > total) state.page = total;
  const start = (state.page - 1) * state.page_size;
  const slice = state.display_rows.slice(start, start + state.page_size);
  renderRows(slice);
  updatePagination();
  const shown = state.display_rows.length;
  const range = shown ? `${start + 1}-${start + slice.length}` : '0';
  setLoading(false, `${range} of ${shown} · page ${state.page}/${total}`);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function renderRows(rows) {
  tbody.innerHTML = '';
  if (!rows.length) {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td colspan="${FT.visibleColCount(layout)}" class="empty-state">${FT.emptySearchMsg('No opportunities matching current filters.')}</td>`;
    tbody.appendChild(tr);
    return;
  }
  const html = rows.map((row) => `<tr data-iid="${row.itemId}" data-q="${row.quality}">${FT.buildRowHtml(row, layout, { renderActions })}</tr>`).join('');
  tbody.innerHTML = html;
  attachRowHandlers();
}

function attachRowHandlers() {
  for (const btn of tbody.querySelectorAll('.star')) {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const iid = parseInt(btn.dataset.iid, 10);
      const q = btn.dataset.q;
      const key = `${iid}:${q}`;
      if (favs.has(key)) {
        await fetch(`/api/favourites/${iid}/${q}`, { method: 'DELETE' });
        favs.delete(key);
        btn.classList.remove('filled');
      } else {
        await fetch('/api/favourites', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ item_id: iid, quality: q }),
        });
        favs.add(key);
        btn.classList.add('filled');
      }
    });
  }
  for (const btn of tbody.querySelectorAll('.rescan')) {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const iid = parseInt(btn.dataset.iid, 10);
      btn.disabled = true;
      try {
        const r = await fetch(RESCAN_URL(iid), { method: 'POST' });
        if (!r.ok) throw new Error('rescan failed (' + r.status + ')');
        const d = await r.json();
        if (d.filtered_out) {
          if (window.toast) window.toast('Item ' + iid + ' no longer meets thresholds', 'info');
          state.all_rows = state.all_rows.filter((r) => r.itemId !== iid);
        } else if (d.row) {
          const idx = state.all_rows.findIndex((r) => r.itemId === iid && r.quality === d.row.quality);
          if (idx >= 0) state.all_rows[idx] = d.row;
          else state.all_rows.push(d.row);
        }
        recomputeAndShow();
        if (window.toast && !d.filtered_out) window.toast('Rescanned item ' + iid, 'info');
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
      applyClientFilters();
      state.page = 1;
      renderPage();
    });
  });
  FT.renderSortChain(thead, state.sort_chain);
}

function updatePagination() {
  const total = pageCount();
  if (pageInfoEl) pageInfoEl.textContent = `Page ${state.page} of ${total}`;
  if (prevBtn) prevBtn.disabled = state.page <= 1;
  if (nextBtn) nextBtn.disabled = state.page >= total;
}

prevBtn?.addEventListener('click', () => { if (state.page > 1) { state.page--; renderPage(); } });
nextBtn?.addEventListener('click', () => { if (state.page < pageCount()) { state.page++; renderPage(); } });
qSel?.addEventListener('change', () => {
  state.quality = qSel.value;
  persistState();
  applyClientFilters();
  state.page = 1;
  renderPage();
});
window.addEventListener('ft-filters-changed', () => {
  syncFiltersFromStore();
  applyClientFilters();
  state.page = 1;
  renderPage();
});
// Table search re-filters in memory and snaps back to page 1.
window.addEventListener('ft-search-changed', () => {
  applyClientFilters();
  state.page = 1;
  renderPage();
});
// A scan finished (first-run initial scan or an auto-rescan) — pull the fresh
// rows and re-render in place, keeping the current page, sort and search.
window.addEventListener('ft-data-refreshed', () => loadAll({ keepPage: true }));
refreshBtn?.addEventListener('click', () => loadAll({ force: true }));
window.addEventListener('ft-settings-changed', () => {
  applySettingsToState();
  FT.invalidateTaxInfo();
  FT.getTaxInfo().then((t) => {
    state.tax_rate = FT.effectiveTaxRate(t, FT.loadSettings());
    recomputeAndShow();
  });
});

window.addEventListener('ft-columns-changed', (e) => {
  if (e.detail && e.detail.page && e.detail.page !== PAGE) return;
  layout = FT.loadColumnLayout(PAGE, 'opps');
  rebuildHeader();
  renderPage();
});

(async () => {
  if (qSel && persistedState.quality) qSel.value = persistedState.quality;
  applySettingsToState();
  syncFiltersFromStore();
  rebuildHeader();
  await loadFavourites();
  await loadAll();
})();
