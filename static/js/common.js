// Shared utilities.
window.FT = (() => {
  // --- Server-backed preference store (replaces localStorage) ---
  // Hydrated once, synchronously, at script load so FT and every page script
  // can read prefs synchronously. Localhost single-user app + tiny payload, so
  // a one-shot blocking GET is acceptable. Writes are async (best-effort).
  const _prefs = {};
  (function hydrateBoot() {
    try {
      const xhr = new XMLHttpRequest();
      xhr.open('GET', '/api/boot', false);
      xhr.send();
      if (xhr.status !== 200) return;
      const data = JSON.parse(xhr.responseText || '{}');
      // First-run guard: never configured → bounce to the setup screen.
      // setup.html does not load this script, so there is no redirect loop.
      if (data && data.configured === false) {
        location.replace('/setup.html');
        return;
      }
      const prefs = (data && data.prefs) || {};
      for (const k of Object.keys(prefs)) _prefs[k] = prefs[k];
    } catch (e) { /* no prefs yet — pages fall back to defaults */ }
  })();
  function prefGet(key, dflt) {
    const raw = (key in _prefs) ? _prefs[key] : null;
    if (raw == null) return dflt;
    try { return JSON.parse(raw); } catch { return dflt; }
  }
  function prefSet(key, value) {
    const raw = JSON.stringify(value);
    _prefs[key] = raw;
    try {
      fetch('/api/ui-prefs', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key, value: raw }),
      }).catch(() => {});
    } catch (e) { /* best-effort */ }
  }

  const fmtNum = new Intl.NumberFormat();
  const fmt = (n) => (n == null ? '—' : fmtNum.format(Math.round(n)));
  const fmt2 = (n) => (n == null ? '—' : (Math.round(n * 100) / 100).toLocaleString());
  const agoMs = (ts) => {
    if (!ts) return '?';
    let s = Math.max(0, Math.floor((Date.now() - ts) / 1000));
    const d = Math.floor(s / 86400); s -= d * 86400;
    const h = Math.floor(s / 3600);  s -= h * 3600;
    const m = Math.floor(s / 60);    s -= m * 60;
    if (d > 0) return `${d}d ${h}h`;
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
  };
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
  }

  // --- Per-page table search (search.js wires the #search input) ---
  // Searchable text per row: item name + source + item ID.
  function _searchText(row) {
    const id = (row.itemId != null) ? row.itemId
      : (row.item_id != null) ? row.item_id : '';
    return [row.name, row.source, row.source_detail, id]
      .filter((v) => v != null && v !== '')
      .join(' ')
      .toLowerCase();
  }
  // The terms a query expands to: a "quoted" query is one literal phrase;
  // an unquoted query is whitespace-split tokens.
  function _searchTerms(query) {
    const q = (query || '').trim();
    if (!q) return [];
    const quoted = q.match(/^"(.*)"$/);
    if (quoted) {
      const p = quoted[1].trim();
      return p ? [p] : [];
    }
    return q.split(/\s+/).filter(Boolean);
  }
  // Unquoted = token-AND substring over the searchable text.
  // "quoted" = literal contiguous phrase, matched against the item name only.
  function matchesSearch(row, query) {
    const q = (query || '').trim();
    if (!q) return true;
    const quoted = q.match(/^"(.*)"$/);
    if (quoted) {
      const phrase = quoted[1].trim().toLowerCase();
      return !phrase || String(row.name || '').toLowerCase().includes(phrase);
    }
    const hay = _searchText(row);
    return q.toLowerCase().split(/\s+/).every((tok) => hay.includes(tok));
  }
  // Item-name HTML with matched terms wrapped in <b class="search-hl">.
  // Splits the RAW name on a terms-regex, then escapes each piece — XSS-safe
  // regardless of name or query content.
  function highlightName(name) {
    const raw = name || '';
    const term = (window.FTSearch && window.FTSearch.term()) || '';
    const terms = _searchTerms(term);
    if (!raw || !terms.length) return escapeHtml(raw);
    const pat = terms
      .map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
      .join('|');
    const re = new RegExp(`(${pat})`, 'gi');
    return raw.split(re).map((piece, i) => (
      (i % 2 === 1) ? `<b class="search-hl">${escapeHtml(piece)}</b>` : escapeHtml(piece)
    )).join('');
  }
  // Empty-table message: explains a zero result when a search is active.
  function emptySearchMsg(fallback) {
    const q = (window.FTSearch && window.FTSearch.term()) || '';
    return q ? `No items match "${escapeHtml(q)}"` : fallback;
  }

  // Small copy-to-clipboard button, sized to the surrounding text (1em).
  // Sits left of an item name so the name can be pasted into the in-game
  // market board search. A delegated listener (below) does the copy.
  const COPY_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
  function copyButton(name) {
    if (!name) return '';
    return `<button class="copy-name" type="button" data-name="${escapeHtml(name)}" title="Copy item name" aria-label="Copy item name">${COPY_SVG}</button>`;
  }

  const wikiLink = (name) =>
    `${copyButton(name)}<a href="https://ffxiv.consolegameswiki.com/wiki/${encodeURIComponent(name.replace(/ /g, '_'))}" target="_blank" rel="noopener">${highlightName(name)}</a>`;

  const SETTINGS_DEFAULTS = {
    budget: 500000,
    page_size: '',
    retainer_count: '',
    tax_city: '',
    alerts_sound: true,
    alerts_volume: 0.5,
  };
  const SETTINGS_KEY = 'ffxiv-trader.settings.v1';
  function loadSettings() {
    const stored = prefGet(SETTINGS_KEY, {});
    return { ...SETTINGS_DEFAULTS, ...(stored && typeof stored === 'object' ? stored : {}) };
  }
  function saveSettings(s) {
    prefSet(SETTINGS_KEY, s);
  }

  let _taxInfo = null;
  async function getTaxInfo() {
    if (_taxInfo) return _taxInfo;
    try {
      const r = await fetch('/api/tax-rates');
      _taxInfo = await r.json();
    } catch {
      _taxInfo = { rates: {}, retainer_city: null };
    }
    return _taxInfo;
  }
  function invalidateTaxInfo() { _taxInfo = null; }

  function effectiveTaxRate(taxInfo, settings) {
    const city = (settings && settings.tax_city) || taxInfo.retainer_city;
    return (taxInfo.rates && taxInfo.rates[city]) ? taxInfo.rates[city] / 100 : 0;
  }

  function recomputeProfit(row, taxRate) {
    if (row.sell_price && row.buy_price) {
      const profit = Math.round(row.sell_price * (1 - taxRate) - row.buy_price);
      row.profit = profit;
      row.roi_pct = row.buy_price > 0 ? Math.round(profit / row.buy_price * 10000) / 100 : null;
      row.profit_per_day = row.velocity ? Math.round(profit * row.velocity * 100) / 100 : null;
    }
    return row;
  }

  function setActiveNav() {
    const path = location.pathname.replace(/^\//, '') || 'index.html';
    document.querySelectorAll('nav.main-nav a').forEach((a) => {
      const href = a.getAttribute('href').replace(/^\//, '');
      if (href === path || (path === '' && href === 'index.html')) a.classList.add('active');
    });
  }

  // Name = Universalis link. Tiny "wiki" link reveals on row hover.
  function renderItemCell(row) {
    const icon = row.icon_url
      ? `<img class="icon" src="${row.icon_url}" loading="lazy" alt="">`
      : `<div class="icon" aria-hidden="true"></div>`;
    if (!row.name) return { icon, name: '—' };
    const safe = highlightName(row.name);
    const uniHref = row.itemId ? `https://universalis.app/market/${row.itemId}` : null;
    const wikiHref = `https://ffxiv.consolegameswiki.com/wiki/${encodeURIComponent(row.name.replace(/ /g, '_'))}`;
    const nameHtml = uniHref
      ? `<a class="uni-name" href="${uniHref}" target="_blank" rel="noopener" title="Open on Universalis">${safe}</a>`
      : safe;
    const wikiHtml = `<a class="wiki-link" href="${wikiHref}" target="_blank" rel="noopener" title="Open on Wiki">wiki ↗</a>`;
    return { icon, name: `${copyButton(row.name)}${nameHtml}${wikiHtml}` };
  }
  // Kept as legacy helper but no longer used in renderItemCell.
  function universalisLink(itemId) {
    return `<a class="uni-name" href="https://universalis.app/market/${itemId}" target="_blank" rel="noopener" title="Open on Universalis">Universalis</a>`;
  }

  function profitClass(p) {
    if (p == null) return '';
    return p > 0 ? 'profit-pos' : p < 0 ? 'profit-neg' : '';
  }

  // Editable price-alert cell for the favourites table: a below/above select
  // plus a target input. favourites.js wires the change handler.
  function alertCell(side, r) {
    const dir = r[side + '_dir'] || 'below';
    const target = r[side + '_target'];
    const opt = (v, lbl) => `<option value="${v}"${dir === v ? ' selected' : ''}>${lbl}</option>`;
    return `<td class="col-alert"><span class="alert-cell" data-iid="${r.itemId}" `
      + `data-q="${r.quality}" data-side="${side}">`
      + `<select class="alert-dir" title="Trigger below or above the target">`
      + `${opt('below', '≤')}${opt('above', '≥')}</select>`
      + `<input type="number" class="alert-val" min="0" `
      + `value="${target != null ? target : ''}" placeholder="off"></span></td>`;
  }

  // --- Multi-column sort ---
  // sort_chain = [{key, dir}], max 3 entries.
  // Bucket non-final 'updated' keys to the hour so secondary keys can break ties.
  const MAX_SORT_LEVELS = 3;
  const HOUR_MS = 3600 * 1000;

  function sortValue(row, key, bucket, keyAlias) {
    const k = (keyAlias && keyAlias[key]) || key;
    let v = row[k];
    if (v == null || v === '') return null;
    if (bucket && (key === 'updated' || k === 'sell_upload_ts' || k === 'last_seen')) {
      // last_seen is unix seconds; sell_upload_ts is ms — both bucket to hour
      const ms = k === 'last_seen' ? v * 1000 : v;
      return Math.floor(ms / HOUR_MS) * HOUR_MS;
    }
    return v;
  }

  // Works for numbers and text. Text sorts alphabetically (case-insensitive,
  // natural-number aware). Missing values always sort last, regardless of dir.
  function compareWithChain(a, b, chain, keyAlias) {
    for (let i = 0; i < chain.length; i++) {
      const { key, dir } = chain[i];
      const isFinal = i === chain.length - 1;
      const av = sortValue(a, key, !isFinal, keyAlias);
      const bv = sortValue(b, key, !isFinal, keyAlias);
      const aNull = av == null;
      const bNull = bv == null;
      if (aNull && bNull) continue;
      if (aNull) return 1;
      if (bNull) return -1;
      let cmp;
      if (typeof av === 'string' || typeof bv === 'string') {
        cmp = String(av).localeCompare(String(bv), undefined, { sensitivity: 'base', numeric: true });
      } else {
        cmp = av < bv ? -1 : av > bv ? 1 : 0;
      }
      if (cmp !== 0) return dir === 'asc' ? cmp : -cmp;
    }
    return 0;
  }

  // Sort rows by a sort chain. One key = a plain sort. Two+ keys BLEND: each
  // row is ranked per key, the ranks are summed, and rows sort by that sum —
  // a row that scores well on every key beats one that only tops a single
  // key. (Lexicographic would just show the leader of key 1.)
  function sortRows(rows, chain, keyAlias) {
    if (!Array.isArray(chain) || chain.length <= 1) {
      return rows.sort((a, b) => compareWithChain(a, b, chain || [], keyAlias));
    }
    const rank = new Map();
    for (const r of rows) rank.set(r, 0);
    for (const level of chain) {
      const ordered = rows.slice().sort(
        (a, b) => compareWithChain(a, b, [level], keyAlias));
      ordered.forEach((r, i) => rank.set(r, rank.get(r) + i));
    }
    return rows.sort((a, b) => {
      const d = rank.get(a) - rank.get(b);
      return d !== 0 ? d : compareWithChain(a, b, chain, keyAlias);
    });
  }

  function handleHeaderClick(chain, key, shiftKey) {
    const idx = chain.findIndex((s) => s.key === key);
    if (shiftKey) {
      if (idx >= 0) {
        // Already in the chain — shift-click removes it; the remaining
        // columns renumber automatically. Keep at least one sort column.
        if (chain.length > 1) chain.splice(idx, 1);
      } else if (chain.length < MAX_SORT_LEVELS) {
        chain.push({ key, dir: 'desc' });
      }
    } else {
      if (chain.length === 1 && chain[0].key === key) {
        chain[0].dir = chain[0].dir === 'desc' ? 'asc' : 'desc';
      } else {
        chain.length = 0;
        chain.push({ key, dir: 'desc' });
      }
    }
    return chain;
  }

  function renderSortChain(thead, chain) {
    thead.querySelectorAll('th[data-sort]').forEach((th) => {
      const key = th.dataset.sort;
      const idx = chain.findIndex((s) => s.key === key);
      const arrow = th.querySelector('.arrow');
      let badge = th.querySelector('.sort-badge');
      if (!badge) {
        badge = document.createElement('span');
        badge.className = 'sort-badge';
        th.appendChild(badge);
      }
      if (idx >= 0) {
        th.classList.add('sort-active');
        if (arrow) arrow.textContent = chain[idx].dir === 'desc' ? '▼' : '▲';
        badge.textContent = chain.length > 1 ? String(idx + 1) : '';
      } else {
        th.classList.remove('sort-active');
        if (arrow) arrow.textContent = '';
        badge.textContent = '';
      }
    });
  }

  // --- Column system ---
  const COLUMN_DEFS = {
    icon:       { label: '', title: 'Item icon', locked: true, cls: 'col-icon',
                  render: (r) => `<td class="col-icon">${renderItemCell(r).icon}</td>` },
    item:       { label: 'Item', title: 'Item name. Click name = open on Universalis. Hover row reveals wiki link.', locked: true, sort: 'name', cls: 'col-item',
                  render: (r) => `<td class="col-item"><span class="item-name">${renderItemCell(r).name}</span></td>` },
    q:          { label: 'Q', title: 'Quality: HQ or NQ — tracked separately', cls: 'col-q',
                  render: (r) => `<td class="col-q quality-${r.quality}">${(r.quality||'').toUpperCase() || '—'}</td>` },
    buy_world:  { label: 'Buy World', title: 'Cheapest rival world to buy from on your DC', sort: 'buy_world', cls: 'col-world',
                  render: (r) => `<td class="col-world">${escapeHtml(r.buy_world || '—')}</td>` },
    buy_price:  { label: 'Buy', title: 'Best buy price (per unit) on rival world. "est" = no live listing, estimated from recent sales.', sort: 'buy_price', cls: 'col-price num',
                  render: (r) => `<td class="col-price num">${fmt(r.buy_price)}${r.buy_price_estimated ? ' <span class="src-tag" title="No live listing — estimated from the smallest recent sale">est</span>' : ''}</td>` },
    sell_world: { label: 'Sell World', title: 'Your home world (where you list to sell)', sort: 'sell_world', cls: 'col-world',
                  render: (r) => `<td class="col-world">${escapeHtml(r.sell_world || '—')}</td>` },
    sell_price: { label: 'Sell', title: 'Current best sell listing on home world. "est" = no live listing, estimated from the most recent sale.', sort: 'sell_price', cls: 'col-price num',
                  render: (r) => `<td class="col-price num">${fmt(r.sell_price)}${r.sell_price_estimated ? ' <span class="src-tag" title="No live listing — estimated from the most recent sale">est</span>' : ''}</td>` },
    profit:     { label: 'Profit', title: 'sell × (1 − tax) − buy. Tax depends on retainer city.', sort: 'profit', cls: 'col-profit num',
                  render: (r) => `<td class="col-profit num ${profitClass(r.profit)}">${fmt(r.profit)}${r.data_stale ? ' <span class="stale-badge" title="Market data is older than your stale-data cutoff — prices may be wrong">!</span>' : ''}</td>` },
    roi_pct:    { label: 'ROI%', title: 'Return on investment: profit / buy × 100', sort: 'roi_pct', cls: 'col-roi num',
                  render: (r) => `<td class="col-roi num">${r.roi_pct != null ? r.roi_pct.toFixed(1) : '—'}</td>` },
    velocity:   { label: 'Sales/d', title: 'Average sales per day on your home world', sort: 'velocity', cls: 'col-velocity num',
                  render: (r) => {
                    if (r.velocity) return `<td class="col-velocity num">${r.velocity.toFixed(2)}</td>`;
                    if (r.velocity_dc) return `<td class="col-velocity num dim" title="No home-world sales — showing DC velocity">${r.velocity_dc.toFixed(2)} <span class="src-tag">DC</span></td>`;
                    return `<td class="col-velocity num">—</td>`;
                  } },
    profit_per_day: { label: 'Profit/d', title: 'profit × sales/day — theoretical revenue if you flip every sale', sort: 'profit_per_day', cls: 'col-pday num',
                      render: (r) => `<td class="col-pday num">${fmt(r.profit_per_day)}</td>` },
    spread_pct: { label: 'Spread%', title: '(sell listing − recent actual sale) / recent sale × 100. Negative = listed below recent sales (cheap); positive = above (harder to sell).', sort: 'spread_pct', cls: 'col-spread num',
                  render: (r) => `<td class="col-spread num ${profitClass(-r.spread_pct)}">${r.spread_pct != null ? r.spread_pct.toFixed(1) : '—'}</td>` },
    top_depth:  { label: 'Depth', title: 'Quantity in cheapest current listing on home world. Low = thin market.', sort: 'top_depth', cls: 'col-depth num',
                  render: (r) => `<td class="col-depth num">${r.top_depth != null ? r.top_depth : '—'}${r.stale_listing ? ' <span class="badge stale" title="Top listing &gt;7d old">stale</span>' : ''}</td>` },
    undercut_gap: { label: 'Gap%', title: '(2nd cheapest − cheapest) / cheapest × 100. Big gap = safe to undercut by 1 gil; tiny gap = bot war.', sort: 'undercut_gap', cls: 'col-gap num',
                    render: (r) => `<td class="col-gap num">${r.undercut_gap != null ? r.undercut_gap.toFixed(1) : '—'}</td>` },
    recent_purchase_ts: { label: 'Last Sale', title: 'Time since the most recent actual sale on home world', sort: 'recent_purchase_ts', cls: 'col-time',
                          render: (r) => {
                            if (r.recent_purchase_ts) return `<td class="col-time dim">${agoMs(r.recent_purchase_ts)}</td>`;
                            if (r.recent_purchase_dc_ts) return `<td class="col-time dim" title="No home-world sale — showing DC last sale">${agoMs(r.recent_purchase_dc_ts)} <span class="src-tag">DC</span></td>`;
                            return `<td class="col-time dim">—</td>`;
                          } },
    updated:    { label: 'Updated', title: 'Time since rival/home world last uploaded to Universalis', sort: 'updated', cls: 'col-time',
                  render: (r) => {
                    const minTs = r.buy_upload_ts > 0
                      ? Math.min(r.buy_upload_ts, r.sell_upload_ts)
                      : r.sell_upload_ts;
                    return `<td class="col-time dim">${agoMs(minTs)}</td>`;
                  } },
    actions:    { label: '', title: 'Star / per-row rescan', locked: true, cls: 'col-actions',
                  render: (r, ctx) => (ctx && ctx.renderActions) ? ctx.renderActions(r) : '<td class="col-actions"></td>' },

    // --- Favourites-only: per-item price alert config ---
    fav_buy_alert:  { label: 'Buy alert', title: 'Alert when the buy price crosses this value', cls: 'col-alert',
                      render: (r) => alertCell('buy', r) },
    fav_sell_alert: { label: 'Sell alert', title: 'Alert when the sell price crosses this value', cls: 'col-alert',
                      render: (r) => alertCell('sell', r) },

    // --- Mount / minion (collectibles) column def ---
    mm_source:  { label: 'Source', title: 'How the collectible is obtained besides the market board', sort: 'source', cls: 'col-src',
                  render: (r) => `<td class="col-src" title="${escapeHtml(r.source_detail || '')}">${escapeHtml(r.source || '—')}</td>` },

    // --- Reliable-only column defs ---
    rel_source: { label: 'Source', title: 'cross-world or vendor', sort: 'source', cls: 'col-src',
                  render: (r) => `<td class="col-src">${escapeHtml(r.source || '—')}</td>` },
    rel_confidence: { label: 'Conf', title: 'Confidence tier (high / medium / low) derived from coverage + variance', cls: 'col-conf',
                      render: (r) => `<td class="col-conf"><span class="conf-badge conf-${r.confidence}">${(r.confidence||'').toUpperCase()}</span></td>` },
    rel_score:  { label: 'Score', title: 'Normalized score (Wilson lower-bound × profit signal). Higher = more reliable.', sort: 'score', cls: 'col-pday num',
                  render: (r) => `<td class="col-pday num">${(r.score_norm != null ? r.score_norm : 0).toFixed(3)}</td>` },
    rel_coverage: { label: 'Coverage', title: 'appearances/total_scans (% = Wilson lower bound)', sort: 'wilson_lb', cls: 'col-coverage',
                    render: (r) => {
                      const pct = Math.round((r.wilson_lb || 0) * 100);
                      return `<td class="col-coverage">${r.appearances||0}/${r.total_scans||0} <span class="dim">(${pct}%)</span></td>`;
                    } },
    vwap_profit: { label: 'VWAP Profit', title: 'Volume-weighted average profit over the window', sort: 'vwap_profit', cls: 'col-profit num',
                   render: (r) => `<td class="col-profit num ${profitClass(r.vwap_profit)}">${fmt(r.vwap_profit)}</td>` },
    unweighted_mean_profit: { label: 'Mean', title: 'Unweighted mean profit', sort: 'unweighted_mean_profit', cls: 'col-profit num',
                              render: (r) => `<td class="col-profit num dim">${fmt(r.unweighted_mean_profit)}</td>` },
    cv_profit:  { label: 'CV', title: 'Coefficient of variation (stdev / mean). Lower = steadier profit.', sort: 'cv_profit', cls: 'col-roi num',
                  render: (r) => `<td class="col-roi num">${r.cv_profit != null ? r.cv_profit.toFixed(3) : '—'}</td>` },
    sortino:    { label: 'Sortino', title: 'Sortino ratio — return per unit of downside risk. Higher = better.', sort: 'sortino', cls: 'col-roi num',
                  render: (r) => `<td class="col-roi num">${r.sortino != null ? r.sortino.toFixed(2) : '—'}</td>` },
    z_score:    { label: 'Z', title: 'Z-score of current profit vs historical distribution. Negative = bargain.', sort: 'z_score', cls: 'col-roi num',
                  render: (r) => `<td class="col-roi num ${profitClass(-r.z_score)}">${r.z_score != null ? r.z_score.toFixed(2) : '—'}</td>` },
    mean_velocity: { label: 'Sales/d', title: 'Average sales per day across the window', sort: 'mean_velocity', cls: 'col-velocity num',
                     render: (r) => {
                       const v = r.mean_velocity;
                       if (v) return `<td class="col-velocity num">${v.toFixed(2)}</td>`;
                       if (r.velocity_dc) return `<td class="col-velocity num dim" title="No home-world sales — showing DC velocity">${r.velocity_dc.toFixed(2)} <span class="src-tag">DC</span></td>`;
                       return `<td class="col-velocity num">—</td>`;
                     } },
    demand_pressure: { label: 'Dem', title: 'Demand pressure — buy-side activity vs supply', sort: 'demand_pressure', cls: 'col-roi num',
                       render: (r) => `<td class="col-roi num">${r.demand_pressure != null ? r.demand_pressure.toFixed(2) : '—'}</td>` },
    rel_trend:  { label: 'Trend', title: 'Profit history sparkline over the window', cls: 'col-spark',
                  render: (r, ctx) => `<td class="col-spark">${(ctx && ctx.sparkline) ? ctx.sparkline(r.profit_series) : ''}</td>` },
  };

  const DEFAULT_LAYOUT_OPPS = [
    { id: 'icon',               visible: true },
    { id: 'item',               visible: true },
    { id: 'q',                  visible: true },
    { id: 'buy_world',          visible: true },
    { id: 'buy_price',          visible: true },
    { id: 'sell_world',         visible: true },
    { id: 'sell_price',         visible: true },
    { id: 'profit',             visible: true },
    { id: 'roi_pct',            visible: true },
    { id: 'velocity',           visible: true },
    { id: 'profit_per_day',     visible: false },
    { id: 'spread_pct',         visible: false },
    { id: 'top_depth',          visible: false },
    { id: 'undercut_gap',       visible: true },
    { id: 'recent_purchase_ts', visible: true },
    { id: 'updated',            visible: true },
    { id: 'actions',            visible: true },
  ];

  const DEFAULT_LAYOUT_RELIABLE = [
    { id: 'icon',                  visible: true },
    { id: 'item',                  visible: true },
    { id: 'q',                     visible: true },
    { id: 'rel_source',            visible: false },
    { id: 'rel_confidence',        visible: true },
    { id: 'rel_score',             visible: true },
    { id: 'rel_coverage',          visible: true },
    { id: 'vwap_profit',           visible: true },
    { id: 'unweighted_mean_profit', visible: false },
    { id: 'cv_profit',             visible: false },
    { id: 'sortino',               visible: false },
    { id: 'z_score',               visible: false },
    { id: 'mean_velocity',         visible: true },
    { id: 'demand_pressure',       visible: false },
    { id: 'top_depth',             visible: false },
    { id: 'buy_world',             visible: true },
    { id: 'buy_price',             visible: true },
    { id: 'sell_world',            visible: true },
    { id: 'sell_price',            visible: true },
    { id: 'rel_trend',             visible: false },
    { id: 'recent_purchase_ts',    visible: false },
    { id: 'updated',               visible: true },
    { id: 'actions',               visible: true },
  ];

  // Mirrors opps default so favourites looks like cross-world by default.
  // User can customize independently via the favourites column popover.
  const DEFAULT_LAYOUT_FAVOURITES = [
    { id: 'icon',               visible: true },
    { id: 'item',               visible: true },
    { id: 'q',                  visible: true },
    { id: 'buy_world',          visible: true },
    { id: 'buy_price',          visible: true },
    { id: 'sell_world',         visible: true },
    { id: 'sell_price',         visible: true },
    { id: 'profit',             visible: true },
    { id: 'roi_pct',            visible: true },
    { id: 'velocity',           visible: true },
    { id: 'fav_buy_alert',      visible: true },
    { id: 'fav_sell_alert',     visible: true },
    { id: 'profit_per_day',     visible: false },
    { id: 'spread_pct',         visible: false },
    { id: 'top_depth',          visible: false },
    { id: 'undercut_gap',       visible: true },
    { id: 'recent_purchase_ts', visible: true },
    { id: 'updated',            visible: true },
    { id: 'actions',            visible: true },
  ];

  // Mounts + minions: fixed, focused column set. Profit-relevant opps columns
  // (ROI, velocity, etc.) are available but hidden by default.
  const DEFAULT_LAYOUT_COLLECTIBLES = [
    { id: 'icon',           visible: true },
    { id: 'item',           visible: true },
    { id: 'mm_source',      visible: true },
    { id: 'buy_world',      visible: true },
    { id: 'buy_price',      visible: true },
    { id: 'sell_world',     visible: true },
    { id: 'sell_price',     visible: true },
    { id: 'profit',         visible: true },
    { id: 'roi_pct',        visible: false },
    { id: 'velocity',       visible: false },
    { id: 'profit_per_day', visible: false },
    { id: 'spread_pct',     visible: false },
    { id: 'updated',        visible: false },
    { id: 'actions',        visible: true },
  ];

  const DEFAULT_LAYOUTS = {
    opps: DEFAULT_LAYOUT_OPPS,
    reliable: DEFAULT_LAYOUT_RELIABLE,
    favourites: DEFAULT_LAYOUT_FAVOURITES,
    collectibles: DEFAULT_LAYOUT_COLLECTIBLES,
  };
  // Column layouts are stored per PAGE, not per context — every page keeps its
  // own column setup. Bump version when any default layout changes.
  const COLUMN_LAYOUT_VERSION = 3;
  const columnLayoutKey = (page) => `ffxiv-trader.column-layout.page.${page}.v${COLUMN_LAYOUT_VERSION}`;

  function defaultLayoutFor(ctx) {
    return (DEFAULT_LAYOUTS[ctx] || DEFAULT_LAYOUT_OPPS).map((c) => ({ ...c }));
  }

  // page = localStorage key (unique per page); ctx = which default column set
  // to seed from / validate against. ctx defaults to page when omitted.
  function loadColumnLayout(page, ctx) {
    ctx = ctx || page || 'opps';
    const defaults = defaultLayoutFor(ctx);
    try {
      const stored = prefGet(columnLayoutKey(page || ctx), null);
      if (!Array.isArray(stored)) return defaults;
      const allowedIds = new Set(defaults.map((d) => d.id));
      const seen = new Set();
      const out = [];
      for (const item of stored) {
        if (!item || !allowedIds.has(item.id) || seen.has(item.id)) continue;
        if (!COLUMN_DEFS[item.id]) continue;
        seen.add(item.id);
        out.push({ id: item.id, visible: !!item.visible });
      }
      for (const def of defaults) {
        if (!seen.has(def.id)) out.push({ ...def });
      }
      for (const item of out) {
        if (COLUMN_DEFS[item.id]?.locked) item.visible = true;
      }
      return out;
    } catch {
      return defaults;
    }
  }

  function saveColumnLayout(layout, page) {
    prefSet(columnLayoutKey(page), layout);
    window.dispatchEvent(new CustomEvent('ft-columns-changed', { detail: { page } }));
  }

  function resolveLayout(layout, available) {
    const allow = available ? new Set(available) : null;
    return layout
      .filter((c) => c.visible !== false)
      .filter((c) => !allow || allow.has(c.id))
      .map((c) => ({ id: c.id, def: COLUMN_DEFS[c.id] }))
      .filter((c) => !!c.def);
  }

  // --- Per-page UI state (sort, dropdowns) ---
  const pageStateKey = (page) => `ffxiv-trader.uistate.${page}.v1`;
  function loadPageState(page, defaults = {}) {
    const stored = prefGet(pageStateKey(page), {});
    return { ...defaults, ...(stored && typeof stored === 'object' ? stored : {}) };
  }
  function savePageState(page, state) {
    prefSet(pageStateKey(page), state);
  }

  function buildThead(theadEl, layout, available) {
    const cols = resolveLayout(layout, available);
    const tr = document.createElement('tr');
    for (const { id, def } of cols) {
      const th = document.createElement('th');
      if (def.cls) th.className = def.cls;
      if (def.title) th.title = def.title;
      if (def.sort) {
        th.setAttribute('data-sort', def.sort);
        th.classList.add('sortable');
        th.innerHTML = `${def.label} <span class="arrow"></span>`;
      } else {
        th.innerHTML = def.label;
      }
      tr.appendChild(th);
    }
    theadEl.innerHTML = '';
    theadEl.appendChild(tr);
    return cols;
  }

  function buildRowHtml(row, layout, ctx, available) {
    const cols = resolveLayout(layout, available);
    return cols.map(({ def }) => def.render(row, ctx)).join('');
  }

  function visibleColCount(layout, available) {
    return resolveLayout(layout, available).length;
  }

  // Copy an item name to the clipboard from any .copy-name button.
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.copy-name');
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();   // never let it open a row's item detail panel
    try { navigator.clipboard.writeText(btn.dataset.name || ''); } catch {}
    btn.classList.add('copied');
    setTimeout(() => btn.classList.remove('copied'), 1000);
  });

  return {
    fmt, fmt2, agoMs, wikiLink, escapeHtml,
    matchesSearch, highlightName, emptySearchMsg,
    prefGet, prefSet,
    loadSettings, saveSettings,
    getTaxInfo, invalidateTaxInfo, effectiveTaxRate, recomputeProfit,
    setActiveNav, renderItemCell, profitClass, universalisLink,
    compareWithChain, sortRows, handleHeaderClick, renderSortChain, MAX_SORT_LEVELS,
    COLUMN_DEFS,
    DEFAULT_LAYOUT: DEFAULT_LAYOUT_OPPS,
    DEFAULT_LAYOUT_OPPS, DEFAULT_LAYOUT_RELIABLE, DEFAULT_LAYOUT_FAVOURITES,
    DEFAULT_LAYOUT_COLLECTIBLES, DEFAULT_LAYOUTS,
    loadColumnLayout, saveColumnLayout, buildThead, buildRowHtml, visibleColCount,
    loadPageState, savePageState,
  };
})();

document.addEventListener('DOMContentLoaded', FT.setActiveNav);
