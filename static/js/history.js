const tbody = document.querySelector('#hist tbody');
const thead = document.querySelector('#hist thead');
const daysEl = document.querySelector('#days');
const sourceEl = document.querySelector('#source');
const reloadBtn = document.querySelector('#reload');
const statusEl = document.querySelector('#status');

const PAGE = 'history';
const PAGE_STATE_DEFAULTS = {
  days: 7,
  source: 'all',
  sort_chain: [{ key: 'profit_per_day', dir: 'desc' }],
};
const persisted = FT.loadPageState(PAGE, PAGE_STATE_DEFAULTS);

let layout = FT.loadColumnLayout(PAGE, 'history');
let rowsCache = [];
let baseStatus = '';

// Sort keys (shared with opps for header consistency) → server-side sort
// columns. The server picks rows by the primary metric, so changing the
// primary key refetches.
const HIST_KEY_ALIAS = {
  profit: 'avg_profit',
  profit_per_day: 'avg_profit_per_day',
  roi_pct: 'avg_roi_pct',
  velocity: 'avg_velocity',
  appearances: 'appearances',
  updated: 'last_seen',
};

const VALID_METRICS = new Set(['profit', 'profit_per_day', 'roi_pct', 'velocity', 'appearances']);

const state = {
  sort_chain: Array.isArray(persisted.sort_chain) && persisted.sort_chain.length
    ? persisted.sort_chain.slice()
    : [{ key: 'profit_per_day', dir: 'desc' }],
};

function persistState() {
  FT.savePageState(PAGE, {
    days: parseInt(daysEl.value, 10) || 7,
    source: sourceEl.value,
    sort_chain: state.sort_chain,
  });
}

function setLoading(on, label) {
  statusEl.textContent = label || (on ? 'Loading' : '');
  statusEl.classList.toggle('loading', !!on);
}

async function load() {
  setLoading(true, 'Loading');
  const primaryKey = state.sort_chain[0] ? state.sort_chain[0].key : 'profit_per_day';
  const metric = VALID_METRICS.has(primaryKey) ? primaryKey : 'profit_per_day';
  const params = new URLSearchParams({
    days: daysEl.value,
    metric,
    source: sourceEl.value,
    limit: 500,
  });
  try {
    const r = await fetch('/api/history/top?' + params.toString());
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const data = await r.json();
    // Normalize for shared column renderers (item / icon use camelCase).
    rowsCache = data.rows.map((row) => ({ ...row, itemId: row.item_id }));
    renderSorted();
    baseStatus = `${data.count} rows · window ${data.days}d · primary sort ${metric}`;
    setLoading(false, baseStatus);
  } catch (e) {
    setLoading(false, 'Error: ' + e.message);
    if (window.toast) window.toast(e.message);
  }
}

function renderSorted() {
  let rows = rowsCache.slice();
  const q = (window.FTSearch && window.FTSearch.term()) || '';
  if (q) rows = rows.filter((r) => FT.matchesSearch(r, q));
  rows = FT.sortRows(rows, state.sort_chain, HIST_KEY_ALIAS);
  if (q) statusEl.textContent = `${rows.length} of ${rowsCache.length}`;
  else if (baseStatus) statusEl.textContent = baseStatus;
  render(rows);
}

function render(rows) {
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="${FT.visibleColCount(layout)}" class="empty-state">${FT.emptySearchMsg('No history rows in this window.')}</td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map((row) =>
    `<tr data-iid="${row.itemId}" data-q="${row.quality}">${FT.buildRowHtml(row, layout)}</tr>`,
  ).join('');
}

function rebuildHeader() {
  FT.buildThead(thead, layout);
  attachSort();
}

function attachSort() {
  thead.querySelectorAll('th[data-sort]').forEach((th) => {
    th.classList.add('sortable');
    th.addEventListener('click', (e) => {
      const prevPrimary = state.sort_chain[0] ? state.sort_chain[0].key : null;
      FT.handleHeaderClick(state.sort_chain, th.dataset.sort, e.shiftKey);
      FT.renderSortChain(thead, state.sort_chain);
      persistState();
      const newPrimary = state.sort_chain[0] ? state.sort_chain[0].key : null;
      if (newPrimary !== prevPrimary && VALID_METRICS.has(newPrimary || '')) {
        // Server picks rows by primary metric — refetch to pull a fresh top-N.
        load();
      } else {
        renderSorted();
      }
    });
  });
  FT.renderSortChain(thead, state.sort_chain);
}

// Hydrate filters from persisted state.
if (persisted.days != null) daysEl.value = persisted.days;
if (persisted.source) sourceEl.value = persisted.source;

daysEl.addEventListener('change', () => { persistState(); load(); });
sourceEl.addEventListener('change', () => { persistState(); load(); });
reloadBtn.addEventListener('click', load);
window.addEventListener('ft-search-changed', renderSorted);
window.addEventListener('ft-data-refreshed', load);
window.addEventListener('ft-columns-changed', (e) => {
  if (e.detail && e.detail.page && e.detail.page !== PAGE) return;
  layout = FT.loadColumnLayout(PAGE, 'history');
  rebuildHeader();
  renderSorted();
});

(async () => {
  rebuildHeader();
  await load();
})();
