// Dashboard widget registry. Each entry describes one widget type:
//   title              label shown in the editor + left panel
//   defaultW/H, minW/H grid size in cells
//   sources            data sets the loader must fetch for this widget
//   render(el, data)   fills the live .dash-widget element
//
// FTWidgets.DEFAULT_LAYOUT reproduces the pre-modular dashboard.
window.FTWidgets = (() => {
  // Read-only row context for the dashboard tables — blank actions, a dash
  // for any sparkline column.
  const DASH_CTX = {
    renderActions: () => '<td class="col-actions"></td>',
    sparkline: () => '<span class="dim">—</span>',
  };

  function head(title, link) {
    return `<div class="dw-head"><h3>${title}</h3>`
      + (link ? `<a class="dw-more" href="${link}">view all &rarr;</a>` : '')
      + '</div>';
  }

  function kpi(label, value, opts = {}) {
    return `<div class="dw-kpi">
      <div class="dw-kpi-label">${label}</div>
      <div class="dw-kpi-value${opts.accent ? ' accent' : ''}">${value}</div>
      ${opts.foot ? `<div class="dw-kpi-foot">${opts.foot}</div>` : ''}
    </div>`;
  }

  function emptyBody(msg) {
    return `<div class="dw-body"><p class="dim dw-empty">${msg}</p></div>`;
  }

  // Per-widget sort chains, keyed by widget type. They survive data refreshes
  // so a chosen sort sticks until reload. Default: most profitable first.
  const sortChains = {};
  const SORT_ALIAS = { updated: 'sell_upload_ts' };

  function chainFor(type, dflt) {
    if (!sortChains[type]) sortChains[type] = dflt.map((c) => ({ ...c }));
    return sortChains[type];
  }

  // Paint sort arrows + wire header clicks to re-sort and repaint.
  function wireSort(thead, chain, repaint) {
    FT.renderSortChain(thead, chain);
    thead.querySelectorAll('th[data-sort]').forEach((th) => {
      th.addEventListener('click', (e) => {
        FT.handleHeaderClick(chain, th.dataset.sort, e.shiftKey);
        repaint();
      });
    });
  }

  // Sortable table using the SOURCE page's saved column layout, so the widget
  // mirrors the columns + order the user picked on that page.
  function paintTable(el, type, rows, page, ctx) {
    const body = el.querySelector('.dw-body');
    const layout = FT.loadColumnLayout(page, ctx);
    const chain = chainFor(type, [{ key: 'profit', dir: 'desc' }]);
    function paint() {
      const sorted = FT.sortRows(rows.slice(), chain, SORT_ALIAS);
      const thead = document.createElement('thead');
      FT.buildThead(thead, layout);
      body.innerHTML = `<table class="data">${thead.outerHTML}<tbody>`
        + sorted.map((r) => `<tr data-iid="${r.itemId}" data-q="${r.quality}">${FT.buildRowHtml(r, layout, DASH_CTX)}</tr>`).join('')
        + '</tbody></table>';
      wireSort(body.querySelector('thead'), chain, paint);
    }
    paint();
  }

  function tableWidget(el, title, link, rows, page, ctx, type) {
    el.innerHTML = head(title, link) + '<div class="dw-body table-wrap"></div>';
    if (!rows || !rows.length) {
      el.querySelector('.dw-body').innerHTML = '<p class="dim dw-empty">No rows.</p>';
      return;
    }
    paintTable(el, type, rows, page, ctx);
  }

  // mm:ss from a second count.
  function fmtMMSS(secs) {
    if (!(secs > 0)) return '00:00';
    const m = Math.floor(secs / 60), s = secs % 60;
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }

  // Compact "icon · name · value" list — for the narrow leader/filter widgets.
  function compactList(rows, valueFn) {
    if (!rows || !rows.length) return emptyBody('No items.');
    const items = rows.map((r) => {
      const cell = FT.renderItemCell(r);
      return `<li class="dw-li">${cell.icon}`
        + `<span class="dw-li-name item-name">${cell.name}</span>`
        + `<span class="dw-li-val">${valueFn(r)}</span></li>`;
    }).join('');
    return `<div class="dw-body"><ul class="dw-list">${items}</ul></div>`;
  }

  // Filter + sort + top-N over a row set (used by the derived widgets).
  function deriveTop(rows, filterFn, sortKey, dir, n) {
    const out = (rows || []).filter(filterFn);
    out.sort((a, b) => {
      const d = (a[sortKey] || 0) - (b[sortKey] || 0);
      return dir === 'asc' ? d : -d;
    });
    return out.slice(0, n);
  }

  // Sortable history table — its own compact column set (the history page has
  // no column picker to mirror).
  const HIST_COLS = [
    { key: 'appearances', label: 'Seen', cls: 'col-appearances num' },
    { key: 'avg_profit', label: 'Avg Profit', cls: 'col-profit num' },
    { key: 'avg_roi_pct', label: 'Avg ROI%', cls: 'col-roi num' },
  ];
  function paintHistory(el, type, rows) {
    const body = el.querySelector('.dw-body');
    const chain = chainFor(type, [{ key: 'avg_profit', dir: 'desc' }]);
    function paint() {
      const sorted = FT.sortRows(rows.slice(), chain, {});
      const ths = HIST_COLS.map((c) =>
        `<th class="${c.cls} sortable" data-sort="${c.key}">${c.label} <span class="arrow"></span></th>`).join('');
      const trs = sorted.map((r) => {
        const iconUrl = r.icon_url || `/api/icon/${r.item_id}`;
        return `<tr data-iid="${r.item_id}" data-q="${r.quality || 'nq'}">
          <td class="col-icon"><img class="icon" src="${iconUrl}" loading="lazy" alt="" onerror="this.outerHTML='<div class=icon></div>'"></td>
          <td class="col-item item-name">${FT.wikiLink(r.name)}</td>
          <td class="col-appearances num">${r.appearances}</td>
          <td class="col-profit num ${FT.profitClass(r.avg_profit)}">${FT.fmt(r.avg_profit)}</td>
          <td class="col-roi num">${r.avg_roi_pct != null ? r.avg_roi_pct.toFixed(1) : '—'}</td>
        </tr>`;
      }).join('');
      body.innerHTML = `<table class="data"><thead><tr>
        <th class="col-icon"></th><th class="col-item">Item</th>${ths}
      </tr></thead><tbody>${trs}</tbody></table>`;
      wireSort(body.querySelector('thead'), chain, paint);
    }
    paint();
  }

  // --- Registry ---
  const REGISTRY = {
    kpi_reliable: {
      title: 'Reliable trades', defaultW: 2, defaultH: 2, minW: 2, minH: 2,
      sources: ['reliable'],
      render(el, d) {
        const rel = d.reliable;
        const n = rel && rel.ready ? rel.count : 0;
        el.innerHTML = kpi('Reliable trades', FT.fmt(n));
      },
    },
    kpi_cross: {
      title: 'Cross-world opps', defaultW: 2, defaultH: 2, minW: 2, minH: 2,
      sources: ['dashboard'],
      render(el, d) {
        el.innerHTML = kpi('Cross-world opps', FT.fmt(d.dashboard?.stats?.cross_world_total));
      },
    },
    kpi_vendor: {
      title: 'Vendor flips', defaultW: 2, defaultH: 2, minW: 2, minH: 2,
      sources: ['dashboard'],
      render(el, d) {
        el.innerHTML = kpi('Vendor flips', FT.fmt(d.dashboard?.stats?.vendor_total));
      },
    },
    kpi_favourites: {
      title: 'Favourites count', defaultW: 2, defaultH: 2, minW: 2, minH: 2,
      sources: ['favourites'],
      render(el, d) {
        el.innerHTML = kpi('Favourites', (d.favourites?.rows || []).length, { accent: true });
      },
    },
    kpi_maps: {
      title: 'Maps tracked', defaultW: 2, defaultH: 2, minW: 2, minH: 2,
      sources: ['dashboard'],
      render(el, d) {
        el.innerHTML = kpi('Maps tracked', (d.dashboard?.maps || []).length);
      },
    },
    kpi_ceiling: {
      title: 'Listing ceiling', defaultW: 2, defaultH: 2, minW: 2, minH: 2,
      sources: ['dashboard'],
      render(el, d) {
        el.innerHTML = kpi('Listing ceiling', FT.fmt(d.dashboard?.listings_ceiling),
          { foot: '20 per retainer' });
      },
    },
    reliable_watch: {
      title: 'Reliable watchlist', defaultW: 12, defaultH: 8, minW: 4, minH: 4,
      sources: ['reliable'],
      render(el, d) {
        const rel = d.reliable;
        el.innerHTML = head('Reliable watchlist', '/reliable.html')
          + '<div class="dw-body table-wrap"></div>';
        const body = el.querySelector('.dw-body');
        if (!rel) {
          body.innerHTML = '<p class="dim dw-empty">Could not load reliable data.</p>';
        } else if (!rel.ready) {
          body.innerHTML = `<p class="dim dw-empty">${rel.reason || 'Collecting data — try again later.'}</p>`;
        } else if (!rel.rows || !rel.rows.length) {
          body.innerHTML = '<p class="dim dw-empty">No high-confidence trades yet.</p>';
        } else {
          paintTable(el, 'reliable_watch', rel.rows, 'reliable', 'reliable');
        }
      },
    },
    top_cross: {
      title: 'Top cross-world', defaultW: 6, defaultH: 8, minW: 4, minH: 4,
      sources: ['dashboard'],
      render(el, d) {
        tableWidget(el, 'Top cross-world', '/index.html',
          d.dashboard?.top_cross_world, 'index', 'opps', 'top_cross');
      },
    },
    top_vendor: {
      title: 'Top vendor flips', defaultW: 6, defaultH: 8, minW: 4, minH: 4,
      sources: ['dashboard'],
      render(el, d) {
        tableWidget(el, 'Top vendor flips', '/vendor.html',
          d.dashboard?.top_vendor, 'vendor', 'opps', 'top_vendor');
      },
    },
    favourites: {
      title: 'Favourites', defaultW: 6, defaultH: 8, minW: 4, minH: 4,
      sources: ['favourites'],
      render(el, d) {
        tableWidget(el, 'Favourites', '/favourites.html',
          d.favourites?.rows, 'favourites', 'favourites', 'favourites');
      },
    },
    maps: {
      title: 'Maps', defaultW: 6, defaultH: 8, minW: 4, minH: 4,
      sources: ['dashboard'],
      render(el, d) {
        tableWidget(el, 'Maps', '/maps.html',
          d.dashboard?.maps, 'maps', 'opps', 'maps');
      },
    },
    mounts: {
      title: 'Mounts', defaultW: 6, defaultH: 8, minW: 4, minH: 4,
      sources: ['mounts'],
      render(el, d) {
        tableWidget(el, 'Mounts', '/mounts.html',
          d.mounts?.rows, 'mounts', 'collectibles', 'mounts');
      },
    },
    minions: {
      title: 'Minions', defaultW: 6, defaultH: 8, minW: 4, minH: 4,
      sources: ['minions'],
      render(el, d) {
        tableWidget(el, 'Minions', '/minions.html',
          d.minions?.rows, 'minions', 'collectibles', 'minions');
      },
    },
    history: {
      title: 'History', defaultW: 6, defaultH: 8, minW: 4, minH: 4,
      sources: ['history'],
      render(el, d) {
        el.innerHTML = head('History', '/history.html')
          + '<div class="dw-body table-wrap"></div>';
        const rows = d.history?.rows;
        if (!rows || !rows.length) {
          el.querySelector('.dw-body').innerHTML = '<p class="dim dw-empty">No history rows.</p>';
        } else {
          paintHistory(el, 'history', rows);
        }
      },
    },
    bargains: {
      title: 'Bargains', defaultW: 4, defaultH: 6, minW: 3, minH: 4,
      sources: ['opps'],
      render(el, d) {
        const rows = deriveTop(d.opps?.rows,
          (r) => r.spread_pct != null && r.spread_pct < 0, 'spread_pct', 'asc', 20);
        el.innerHTML = head('Bargains', null)
          + compactList(rows, (r) => `<span class="profit-pos">${r.spread_pct.toFixed(1)}%</span>`);
      },
    },
    stale: {
      title: 'Stale listings', defaultW: 4, defaultH: 6, minW: 3, minH: 4,
      sources: ['opps'],
      render(el, d) {
        const rows = deriveTop(d.opps?.rows,
          (r) => !!r.stale_listing, 'profit_per_day', 'desc', 20);
        el.innerHTML = head('Stale listings', null)
          + compactList(rows, (r) => FT.fmt(r.profit));
      },
    },
    roi_leaders: {
      title: 'ROI leaders', defaultW: 3, defaultH: 6, minW: 3, minH: 4,
      sources: ['opps'],
      render(el, d) {
        const rows = deriveTop(d.opps?.rows,
          (r) => r.roi_pct != null, 'roi_pct', 'desc', 20);
        el.innerHTML = head('ROI leaders', null)
          + compactList(rows, (r) => `${r.roi_pct.toFixed(0)}%`);
      },
    },
    velocity_leaders: {
      title: 'Velocity leaders', defaultW: 3, defaultH: 6, minW: 3, minH: 4,
      sources: ['opps'],
      render(el, d) {
        const rows = deriveTop(d.opps?.rows,
          (r) => r.velocity != null, 'velocity', 'desc', 20);
        el.innerHTML = head('Velocity leaders', null)
          + compactList(rows, (r) => `${r.velocity.toFixed(1)}/d`);
      },
    },
    profit_potential: {
      title: 'Profit potential', defaultW: 3, defaultH: 2, minW: 2, minH: 2,
      sources: ['opps'],
      render(el, d) {
        const rows = d.opps?.rows || [];
        const sum = rows.reduce((a, r) => a + Math.max(0, r.profit_per_day || 0), 0);
        el.innerHTML = kpi('Profit potential / day', FT.fmt(sum),
          { accent: true, foot: 'summed gil/day across all opps' });
      },
    },
    scan_status: {
      title: 'Scan status', defaultW: 3, defaultH: 3, minW: 3, minH: 2,
      sources: ['scan_status'],
      render(el, d) {
        const s = d.scan_status || {};
        el.dataset.nextTs = s.next_rescan_ts || 0;
        el.dataset.lastTs = s.last_rescan_ts || 0;
        el.dataset.enabled = s.enabled ? '1' : '';
        el.dataset.inProgress = s.in_progress ? '1' : '';
        el.innerHTML = head('Scan status', null) + `<div class="dw-body">
          <div class="dw-stat-line"><span>Status</span><b class="dw-scan-state"></b></div>
          <div class="dw-stat-line"><span>Next rescan</span><b class="dw-scan-next"></b></div>
          <div class="dw-stat-line"><span>Last scan</span><b class="dw-scan-last"></b></div>
        </div>`;
        this.tick(el);
      },
      tick(el) {
        const inProg = el.dataset.inProgress === '1';
        const enabled = el.dataset.enabled === '1';
        const nextTs = +el.dataset.nextTs || 0;
        const lastTs = +el.dataset.lastTs || 0;
        const state = el.querySelector('.dw-scan-state');
        const next = el.querySelector('.dw-scan-next');
        const last = el.querySelector('.dw-scan-last');
        if (!state) return;
        state.textContent = inProg ? 'Rescanning…' : 'Idle';
        if (!enabled) next.textContent = 'off';
        else if (inProg) next.textContent = '—';
        else if (nextTs > Date.now()) next.textContent = fmtMMSS(Math.round((nextTs - Date.now()) / 1000));
        else next.textContent = 'due';
        last.textContent = lastTs ? new Date(lastTs).toLocaleTimeString() : '—';
      },
    },
    clock: {
      title: 'Clock', defaultW: 2, defaultH: 2, minW: 2, minH: 2,
      sources: ['scan_status'],
      render(el, d) {
        el.dataset.nextTs = (d.scan_status && d.scan_status.next_rescan_ts) || 0;
        el.innerHTML = `<div class="dw-clock">
          <div class="dw-clock-time">--:--:--</div>
          <div class="dw-clock-sub"></div>
        </div>`;
        this.tick(el);
      },
      tick(el) {
        const t = el.querySelector('.dw-clock-time');
        const sub = el.querySelector('.dw-clock-sub');
        if (!t) return;
        t.textContent = new Date().toLocaleTimeString();
        const nextTs = +el.dataset.nextTs || 0;
        sub.textContent = nextTs > Date.now()
          ? `Next scan in ${fmtMMSS(Math.round((nextTs - Date.now()) / 1000))}`
          : 'Next scan due';
      },
    },
    notes: {
      title: 'Notes', defaultW: 3, defaultH: 4, minW: 2, minH: 2,
      sources: [],
      render(el) {
        const txt = FT.prefGet('ffxiv-trader.dashboard.notes.v1', '');
        el.innerHTML = head('Notes', null)
          + `<div class="dw-body"><textarea class="dw-notes" placeholder="Jot targets, reminders…">`
          + FT.escapeHtml(typeof txt === 'string' ? txt : '') + `</textarea></div>`;
        const ta = el.querySelector('.dw-notes');
        let timer = 0;
        ta.addEventListener('input', () => {
          clearTimeout(timer);
          timer = setTimeout(() => FT.prefSet('ffxiv-trader.dashboard.notes.v1', ta.value), 400);
        });
      },
    },
    search: {
      title: 'Search', defaultW: 4, defaultH: 2, minW: 3, minH: 2,
      sources: ['opps'],
      render(el, d) {
        const rows = (d.opps && d.opps.rows) || [];
        const type = el.dataset.type;
        el.innerHTML = `<div class="dw-search">
          <input type="search" class="dw-search-input" placeholder="Search items…">
          <div class="dw-search-results"></div>
        </div>`;
        const input = el.querySelector('.dw-search-input');
        const out = el.querySelector('.dw-search-results');
        let timer = 0;

        // A result count -> requested widget height. Base 2 rows for the
        // input; ~2 result lines fit per grid row. The grid pushes the
        // widgets below down to make room (handled by FTDash.requestHeight).
        function run() {
          const q = input.value.trim();
          if (!q) {
            out.innerHTML = '';
            if (window.FTDash) window.FTDash.requestHeight(type, 0);
            return;
          }
          const hits = rows.filter((r) => FT.matchesSearch(r, q)).slice(0, 30);
          out.innerHTML = hits.length
            ? hits.map((r) => {
              const c = FT.renderItemCell(r);
              return `<div class="dw-sr">${c.icon}`
                + `<span class="dw-sr-name item-name">${c.name}</span>`
                + `<span class="dw-sr-val">${FT.fmt(r.profit)}</span></div>`;
            }).join('')
            : `<div class="dw-sr-empty dim">No items match "${FT.escapeHtml(q)}"</div>`;
          const extra = Math.ceil((hits.length || 1) / 2);
          if (window.FTDash) window.FTDash.requestHeight(type, 2 + extra);
        }

        input.addEventListener('input', () => {
          clearTimeout(timer);
          timer = setTimeout(run, 80);
        });
      },
    },
    profit_calc: {
      title: 'Profit calculator', defaultW: 2, defaultH: 6, minW: 2, minH: 4,
      sources: [],
      render(el) {
        el.innerHTML = head('Profit calculator', null) + `<div class="dw-body dw-calc">
          <label class="dw-calc-field">Buy / unit
            <input type="number" class="dw-calc-buy" min="0" placeholder="0"></label>
          <label class="dw-calc-field">Quantity
            <input type="number" class="dw-calc-qty" min="1" value="1"></label>
          <label class="dw-calc-field">Sell / unit
            <input type="number" class="dw-calc-sell" min="0" placeholder="0"></label>
          <div class="dw-calc-out">
            <div class="dw-calc-row"><span>Net profit</span><b class="dw-calc-net">—</b></div>
            <div class="dw-calc-row"><span>Per unit</span><b class="dw-calc-unit">—</b></div>
            <div class="dw-calc-row"><span>ROI</span><b class="dw-calc-roi">—</b></div>
          </div>
        </div>`;
        let taxRate = 0;
        const buy = el.querySelector('.dw-calc-buy');
        const qty = el.querySelector('.dw-calc-qty');
        const sell = el.querySelector('.dw-calc-sell');
        const netEl = el.querySelector('.dw-calc-net');
        const unitEl = el.querySelector('.dw-calc-unit');
        const roiEl = el.querySelector('.dw-calc-roi');
        function calc() {
          const b = parseFloat(buy.value) || 0;
          const q = Math.max(1, parseInt(qty.value, 10) || 1);
          const s = parseFloat(sell.value) || 0;
          const unit = s * (1 - taxRate) - b;
          const net = unit * q;
          netEl.textContent = FT.fmt(net);
          netEl.className = 'dw-calc-net ' + FT.profitClass(net);
          unitEl.textContent = FT.fmt(unit);
          roiEl.textContent = b > 0 ? `${(unit / b * 100).toFixed(1)}%` : '—';
        }
        el.addEventListener('input', calc);
        FT.getTaxInfo().then((tax) => {
          // Tax of the city the retainer is in (ignores any UI override).
          taxRate = FT.effectiveTaxRate(tax, {});
          calc();
        });
        calc();
      },
    },
  };

  // Default layout — just the six KPI tiles across the top row. Every other
  // widget is opt-in via the editor.
  const DEFAULT_LAYOUT = [
    { type: 'kpi_reliable',   x: 0,  y: 0, w: 2, h: 2 },
    { type: 'kpi_cross',      x: 2,  y: 0, w: 2, h: 2 },
    { type: 'kpi_vendor',     x: 4,  y: 0, w: 2, h: 2 },
    { type: 'kpi_favourites', x: 6,  y: 0, w: 2, h: 2 },
    { type: 'kpi_maps',       x: 8,  y: 0, w: 2, h: 2 },
    { type: 'kpi_ceiling',    x: 10, y: 0, w: 2, h: 2 },
  ];

  return {
    REGISTRY,
    DEFAULT_LAYOUT,
    get: (type) => REGISTRY[type] || null,
    types: () => Object.keys(REGISTRY),
  };
})();
