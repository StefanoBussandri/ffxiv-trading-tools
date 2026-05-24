const tbody = document.querySelector('#hist tbody');
const thead = document.querySelector('#hist thead');
const daysEl = document.querySelector('#days');
const sourceEl = document.querySelector('#source');
const reloadBtn = document.querySelector('#reload');
const statusEl = document.querySelector('#status');

let sortChain = [{ key: 'profit_per_day', dir: 'desc' }];
let rowsCache = [];
let baseStatus = '';  // load-time status string, restored when search clears

const HIST_KEY_ALIAS = {
  profit: 'avg_profit',
  profit_per_day: 'avg_profit_per_day',
  roi_pct: 'avg_roi_pct',
  velocity: 'avg_velocity',
  appearances: 'appearances',
  updated: 'last_seen',
};

function setLoading(on, label) {
  statusEl.textContent = label || (on ? 'Loading' : '');
  statusEl.classList.toggle('loading', !!on);
}

async function load() {
  setLoading(true, 'Loading');
  const primary = sortChain[0] ? sortChain[0].key : 'profit_per_day';
  const params = new URLSearchParams({
    days: daysEl.value,
    metric: primary,
    source: sourceEl.value,
    limit: 500,
  });
  try {
    const r = await fetch('/api/history/top?' + params.toString());
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const data = await r.json();
    rowsCache = data.rows;
    renderSorted();
    baseStatus = `${data.count} rows · window ${data.days}d · primary sort ${primary}`;
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
  rows = FT.sortRows(rows, sortChain, HIST_KEY_ALIAS);
  if (q) statusEl.textContent = `${rows.length} of ${rowsCache.length}`;
  else if (baseStatus) statusEl.textContent = baseStatus;
  render(rows);
}

function render(rows) {
  tbody.innerHTML = '';
  if (!rows.length) {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td colspan="10" class="empty-state">${FT.emptySearchMsg('No history rows in this window.')}</td>`;
    tbody.appendChild(tr);
    return;
  }
  for (const row of rows) {
    const tr = document.createElement('tr');
    tr.dataset.iid = row.item_id;
    tr.dataset.q = row.quality;
    const iconUrl = row.icon_url || `/api/icon/${row.item_id}`;
    const icon = `<img class="icon" src="${iconUrl}" loading="lazy" alt="" onerror="this.outerHTML='<div class=icon></div>'">`;
    tr.innerHTML = `
      <td class="col-icon">${icon}</td>
      <td class="col-item item-name">${FT.wikiLink(row.name)}</td>
      <td class="col-q quality-${row.quality}">${row.quality.toUpperCase()}</td>
      <td class="col-source">${row.source}</td>
      <td class="col-appearances num">${row.appearances}</td>
      <td class="col-profit num ${FT.profitClass(row.avg_profit)}">${FT.fmt(row.avg_profit)}</td>
      <td class="col-roi num">${row.avg_roi_pct != null ? row.avg_roi_pct.toFixed(1) : '—'}</td>
      <td class="col-velocity num">${row.avg_velocity != null ? row.avg_velocity.toFixed(2) : '—'}</td>
      <td class="col-pday num">${FT.fmt(row.avg_profit_per_day)}</td>
      <td class="col-time dim">${FT.agoMs(row.last_seen * 1000)}</td>
    `;
    tbody.appendChild(tr);
  }
}

function attachSort() {
  thead.querySelectorAll('th[data-sort]').forEach((th) => {
    th.classList.add('sortable');
    th.addEventListener('click', (e) => {
      const prevPrimary = sortChain[0] ? sortChain[0].key : null;
      FT.handleHeaderClick(sortChain, th.dataset.sort, e.shiftKey);
      FT.renderSortChain(thead, sortChain);
      const newPrimary = sortChain[0] ? sortChain[0].key : null;
      if (newPrimary !== prevPrimary) {
        // history server-side filter depends on primary; refetch
        load();
      } else {
        renderSorted();
      }
    });
  });
  FT.renderSortChain(thead, sortChain);
}

daysEl.addEventListener('change', load);
sourceEl.addEventListener('change', load);
reloadBtn.addEventListener('click', load);
window.addEventListener('ft-search-changed', renderSorted);
window.addEventListener('ft-data-refreshed', load);

(async () => {
  attachSort();
  await load();
})();
