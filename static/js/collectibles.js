// Mounts / minions page — shared script. window.FT_KIND picks the catalogue.
const KIND = window.FT_KIND;                     // 'mounts' | 'minions'
const ENDPOINT = `/api/collectibles/${KIND}`;
const RESCAN_URL = (id) => `${ENDPOINT}/rescan/${id}`;

const tbody = document.querySelector('#collectibles tbody');
const thead = document.querySelector('#collectibles thead');
const statusEl = document.querySelector('#status');
const refreshBtn = document.querySelector('#refresh');

const PAGE = KIND;
const PAGE_STATE_DEFAULTS = { sort_chain: [{ key: 'profit', dir: 'desc' }] };
const persistedState = FT.loadPageState(PAGE, PAGE_STATE_DEFAULTS);
function persistState() {
  FT.savePageState(PAGE, { sort_chain: state.sort_chain });
}

const state = {
  sort_chain: Array.isArray(persistedState.sort_chain) && persistedState.sort_chain.length
    ? persistedState.sort_chain.slice()
    : [{ key: 'profit', dir: 'desc' }],
  rows: [],
  tax_rate: 0,
  profitable_only: false,
  stale_only: false,
  bargain_only: false,
};
function syncFiltersFromStore() {
  const f = (window.FTFilters && window.FTFilters.load()) || {};
  state.profitable_only = !!f.profitable_only;
  state.stale_only = !!f.stale_only;
  state.bargain_only = !!f.bargain_only;
}

const KEY_ALIAS = { updated: 'sell_upload_ts' };
let baseStatus = '';  // load-time status string, restored when search clears
let favs = new Set();
let layout = FT.loadColumnLayout(KIND, 'collectibles');

function setLoading(on, label) {
  statusEl.textContent = label || (on ? 'Loading' : '');
  statusEl.classList.toggle('loading', !!on);
}

function renderActions(row) {
  const key = `${row.itemId}:${row.quality}`;
  const starred = favs.has(key) ? 'filled' : '';
  return `<td class="col-actions">
    <button class="star ${starred}" data-iid="${row.itemId}" data-q="${row.quality}" title="Toggle favourite">★</button>
    <button class="row-action rescan" data-iid="${row.itemId}" title="Rescan this item">↻</button>
  </td>`;
}
const ROW_CTX = { renderActions };

async function loadFavourites() {
  try {
    const r = await fetch('/api/favourites');
    const d = await r.json();
    favs = new Set(d.rows.map((f) => `${f.item_id}:${f.quality}`));
  } catch {
    favs = new Set();
  }
}

async function load() {
  setLoading(true, 'Loading');
  try {
    const tax = await FT.getTaxInfo();
    state.tax_rate = FT.effectiveTaxRate(tax, FT.loadSettings());
    const r = await fetch(ENDPOINT);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const data = await r.json();
    state.rows = data.rows;
    for (const row of state.rows) FT.recomputeProfit(row, state.tax_rate);
    renderSorted();
    baseStatus = `${data.count} ${KIND} · ${new Date(data.ts).toLocaleTimeString()}`;
    setLoading(false, baseStatus);
  } catch (e) {
    setLoading(false, 'Error: ' + e.message);
    if (window.toast) window.toast(e.message);
  }
}

function renderSorted() {
  let rows = state.rows.slice();
  if (state.profitable_only) rows = rows.filter((r) => (r.profit || 0) > 0);
  if (state.stale_only) rows = rows.filter((r) => r.stale_listing);
  if (state.bargain_only) rows = rows.filter((r) => (r.spread_pct || 0) < 0);
  const q = (window.FTSearch && window.FTSearch.term()) || '';
  if (q) rows = rows.filter((r) => FT.matchesSearch(r, q));
  rows = FT.sortRows(rows, state.sort_chain, KEY_ALIAS);
  if (q) statusEl.textContent = `${rows.length} of ${state.rows.length}`;
  else if (baseStatus) statusEl.textContent = baseStatus;
  render(rows);
}

function rebuildHeader() {
  FT.buildThead(thead, layout);
  attachSort();
}

function render(rows) {
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="${FT.visibleColCount(layout)}" class="empty-state">${FT.emptySearchMsg(`No ${KIND}.`)}</td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map((row) => `<tr data-iid="${row.itemId}" data-q="${row.quality}">${FT.buildRowHtml(row, layout, ROW_CTX)}</tr>`).join('');
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
        if (d.row) {
          FT.recomputeProfit(d.row, state.tax_rate);
          const idx = state.rows.findIndex((x) => x.itemId === iid);
          if (idx >= 0) state.rows[idx] = d.row;
          else state.rows.push(d.row);
          renderSorted();
          if (window.toast) window.toast('Rescanned item ' + iid, 'info');
        }
      } catch (err) {
        if (window.toast) window.toast(err.message);
      } finally {
        btn.disabled = false;
      }
    });
  }
}

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

window.addEventListener('ft-columns-changed', (e) => {
  if (e.detail && e.detail.page && e.detail.page !== KIND) return;
  layout = FT.loadColumnLayout(KIND, 'collectibles');
  rebuildHeader();
  renderSorted();
});
window.addEventListener('ft-filters-changed', () => { syncFiltersFromStore(); renderSorted(); });
window.addEventListener('ft-search-changed', renderSorted);
window.addEventListener('ft-settings-changed', () => { FT.invalidateTaxInfo(); load(); });
window.addEventListener('ft-rescan-all', () => { load(); });
window.addEventListener('ft-data-refreshed', load);
refreshBtn?.addEventListener('click', load);

(async () => {
  syncFiltersFromStore();
  rebuildHeader();
  await loadFavourites();
  await load();
})();
