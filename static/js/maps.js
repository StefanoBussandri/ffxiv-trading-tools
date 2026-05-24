const tbody = document.querySelector('#maps tbody');
const thead = document.querySelector('#maps thead');
const statusEl = document.querySelector('#status');
const refreshBtn = document.querySelector('#refresh');

const PAGE = 'maps';
const PAGE_STATE_DEFAULTS = { sort_chain: [{ key: 'profit_per_day', dir: 'desc' }] };
const persistedState = FT.loadPageState(PAGE, PAGE_STATE_DEFAULTS);
function persistState() {
  FT.savePageState(PAGE, { sort_chain: state.sort_chain });
}

const state = {
  sort_chain: Array.isArray(persistedState.sort_chain) && persistedState.sort_chain.length
    ? persistedState.sort_chain.slice()
    : [{ key: 'profit_per_day', dir: 'desc' }],
  rows: [],
  tax_rate: 0,
  stale_only: false,
  bargain_only: false,
};
function syncFiltersFromStore() {
  const f = (window.FTFilters && window.FTFilters.load()) || {};
  state.stale_only = !!f.stale_only;
  state.bargain_only = !!f.bargain_only;
}

const MAPS_KEY_ALIAS = { updated: 'sell_upload_ts' };
let baseStatus = '';  // load-time status string, restored when search clears

function setLoading(on, label) {
  statusEl.textContent = label || (on ? 'Loading' : '');
  statusEl.classList.toggle('loading', !!on);
}

async function load() {
  setLoading(true, 'Loading');
  try {
    const tax = await FT.getTaxInfo();
    state.tax_rate = FT.effectiveTaxRate(tax, FT.loadSettings());
    const r = await fetch('/api/maps');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const data = await r.json();
    state.rows = data.rows;
    for (const row of state.rows) FT.recomputeProfit(row, state.tax_rate);
    renderSorted();
    baseStatus = `${data.count} maps · ${new Date(data.ts).toLocaleTimeString()}`;
    setLoading(false, baseStatus);
  } catch (e) {
    setLoading(false, 'Error: ' + e.message);
    if (window.toast) window.toast(e.message);
  }
}

function renderSorted() {
  let rows = state.rows.slice();
  if (state.stale_only) rows = rows.filter((r) => r.stale_listing);
  if (state.bargain_only) rows = rows.filter((r) => (r.spread_pct || 0) < 0);
  const q = (window.FTSearch && window.FTSearch.term()) || '';
  if (q) rows = rows.filter((r) => FT.matchesSearch(r, q));
  rows = FT.sortRows(rows, state.sort_chain, MAPS_KEY_ALIAS);
  if (q) statusEl.textContent = `${rows.length} of ${state.rows.length}`;
  else if (baseStatus) statusEl.textContent = baseStatus;
  render(rows);
}

let layout = FT.loadColumnLayout(PAGE, 'opps');
const ROW_CTX = { renderActions: () => '<td class="col-actions"></td>' };

function rebuildHeader() {
  FT.buildThead(thead, layout);
  attachSort();
}

function render(rows) {
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="${FT.visibleColCount(layout)}" class="empty-state">${FT.emptySearchMsg('No maps.')}</td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map((row) => `<tr data-iid="${row.itemId}" data-q="${row.quality}">${FT.buildRowHtml(row, layout, ROW_CTX)}</tr>`).join('');
}

window.addEventListener('ft-columns-changed', (e) => {
  if (e.detail && e.detail.page && e.detail.page !== PAGE) return;
  layout = FT.loadColumnLayout(PAGE, 'opps');
  rebuildHeader();
  renderSorted();
});

function attachSort() {
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

window.addEventListener('ft-filters-changed', () => { syncFiltersFromStore(); renderSorted(); });
window.addEventListener('ft-search-changed', renderSorted);
window.addEventListener('ft-data-refreshed', load);
refreshBtn?.addEventListener('click', load);
window.addEventListener('ft-settings-changed', () => { FT.invalidateTaxInfo(); load(); });

(async () => {
  syncFiltersFromStore();
  rebuildHeader();
  await load();
})();
