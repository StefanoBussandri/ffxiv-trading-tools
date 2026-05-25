// Columns + filters popover. Opens from a button in each page's controls bar.
// Filters are stored per-page (server-side, via FT prefs) and broadcast via 'ft-filters-changed'.
// Columns use the shared layout in common.js.
(() => {
  const btn = document.querySelector('#cols-filters-btn');
  if (!btn) return;

  const CTX = btn.dataset.context || 'opps';
  const PAGE_KEY = (location.pathname.match(/([^/]+)\.html$/)?.[1]) || 'index';
  const FILTERS_KEY = `ffxiv-trader.filters.${PAGE_KEY}.v1`;

  const FILTER_DEFS_BY_CTX = {
    opps: [
      { id: 'commodity',   label: 'Commodity (velocity ≥20 & ROI ≤15%)' },
      { id: 'stale_only',  label: 'Stale listings only' },
      { id: 'bargain_only', label: 'Bargain (spread < 0)' },
    ],
    reliable: [
      { id: 'commodity',   label: 'Commodity (velocity ≥20 & ROI ≤15%)' },
      { id: 'stale_only',  label: 'Stale listings only' },
      { id: 'bargain_only', label: 'Bargain (z-score < −1)' },
    ],
    favourites: [
      { id: 'stale_only',  label: 'Stale listings only' },
      { id: 'bargain_only', label: 'Bargain (spread < 0)' },
    ],
    collectibles: [
      { id: 'profitable_only', label: 'Profitable only (profit > 0)' },
      { id: 'stale_only',  label: 'Stale listings only' },
      { id: 'bargain_only', label: 'Bargain (spread < 0)' },
    ],
    history: [],
  };
  const FILTER_DEFS = (CTX in FILTER_DEFS_BY_CTX)
    ? FILTER_DEFS_BY_CTX[CTX]
    : FILTER_DEFS_BY_CTX.opps;

  function loadFilters() {
    const stored = FT.prefGet(FILTERS_KEY, {});
    return (stored && typeof stored === 'object') ? stored : {};
  }
  function saveFilters(state) {
    FT.prefSet(FILTERS_KEY, state);
    window.dispatchEvent(new CustomEvent('ft-filters-changed', { detail: state }));
  }
  window.FTFilters = { load: loadFilters, save: saveFilters, key: FILTERS_KEY };

  btn.addEventListener('click', openPopover);

  function columnRowHtml(col, i, total) {
    const def = FT.COLUMN_DEFS[col.id];
    if (!def) return '';
    const lockedAttr = def.locked ? 'disabled checked' : (col.visible ? 'checked' : '');
    const label = def.label || `(${col.id})`;
    return `
      <div class="col-row" data-id="${col.id}">
        <label><input type="checkbox" class="col-vis" ${lockedAttr}> ${label}</label>
        <span class="spacer"></span>
        <button class="btn small" data-act="up" ${i === 0 ? 'disabled' : ''}>↑</button>
        <button class="btn small" data-act="down" ${i === total - 1 ? 'disabled' : ''}>↓</button>
      </div>`;
  }

  function openPopover() {
    if (document.querySelector('.popover-backdrop')) return;
    const layout = FT.loadColumnLayout(PAGE_KEY, CTX);
    const filters = loadFilters();
    const colRowsHtml = layout.map((c, i) => columnRowHtml(c, i, layout.length)).join('');
    const filterRowsHtml = FILTER_DEFS.map((f) =>
      `<label class="filter-row"><input type="checkbox" data-filter="${f.id}" ${filters[f.id] ? 'checked' : ''}> ${f.label}</label>`,
    ).join('');

    const filtersBlock = FILTER_DEFS.length
      ? `<h3 class="section" style="margin-top:0;border-top:0;">Filters</h3>
         <div class="filter-list">${filterRowsHtml}</div>
         <h3 class="section">Columns</h3>`
      : `<h3 class="section" style="margin-top:0;border-top:0;">Columns</h3>`;

    const back = document.createElement('div');
    back.className = 'popover-backdrop';
    back.innerHTML = `
      <div class="popover" role="dialog" aria-label="Columns &amp; filters">
        ${filtersBlock}
        <div class="hint" style="margin-top:0;">Toggle visibility and reorder with ↑↓.</div>
        <div id="cf-col-list" class="col-list">${colRowsHtml}</div>
        <div class="actions">
          <button class="btn small" id="cf-reset" type="button">Reset columns</button>
          <span style="flex:1;"></span>
          <button class="btn" id="cf-close" type="button">Close</button>
          <button class="btn primary" id="cf-apply" type="button">Apply</button>
        </div>
      </div>`;
    document.body.appendChild(back);
    document.body.classList.add('no-scroll');

    const colList = back.querySelector('#cf-col-list');
    function rerenderColList(cur) {
      colList.innerHTML = cur.map((c, i) => columnRowHtml(c, i, cur.length)).join('');
    }
    function readColList() {
      return Array.from(colList.querySelectorAll('.col-row')).map((row) => {
        const id = row.dataset.id;
        const def = FT.COLUMN_DEFS[id];
        const chk = row.querySelector('.col-vis');
        return { id, visible: def?.locked ? true : chk.checked };
      });
    }
    colList.addEventListener('click', (e) => {
      const b = e.target.closest('button[data-act]');
      if (!b) return;
      const cur = readColList();
      const row = b.closest('.col-row');
      const idx = Array.from(colList.children).indexOf(row);
      const j = idx + (b.dataset.act === 'up' ? -1 : 1);
      if (j < 0 || j >= cur.length) return;
      [cur[idx], cur[j]] = [cur[j], cur[idx]];
      rerenderColList(cur);
    });
    back.querySelector('#cf-reset').addEventListener('click', () =>
      rerenderColList((FT.DEFAULT_LAYOUTS[CTX] || FT.DEFAULT_LAYOUT).map((c) => ({ ...c }))));

    function close() { back.remove(); document.body.classList.remove('no-scroll'); }
    back.querySelector('#cf-close').addEventListener('click', close);
    back.addEventListener('click', (e) => { if (e.target === back) close(); });
    back.querySelector('#cf-apply').addEventListener('click', () => {
      FT.saveColumnLayout(readColList(), PAGE_KEY);
      const fstate = {};
      back.querySelectorAll('input[data-filter]').forEach((inp) => {
        fstate[inp.dataset.filter] = inp.checked;
      });
      saveFilters(fstate);
      close();
    });
  }
})();
