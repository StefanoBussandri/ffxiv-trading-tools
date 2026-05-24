// Item detail — click a table row to expand an inline panel beneath it
// (price-history graph + data-centre listings + home-world listings).
// Click the same row again to close it. Any number of panels can be open at
// once for side-by-side comparison. Fetched data is cached until the next
// scan so reopening a row is instant.
(() => {
  if (!window.FT) return;

  const cache = new Map();     // 'iid:q' -> detail payload
  const openKeys = new Set();  // 'iid:q' for panels the user has open

  // SVG price-history graph: y-axis gridlines, axis bars, and a hover point
  // per sale (native <title> tooltip with price / date / quantity).
  function graph(history) {
    if (!history || history.length < 2) {
      return '<div class="id-graph-empty dim">Not enough sale history to chart.</div>';
    }
    const W = 760, H = 230, padL = 58, padR = 16, padT = 14, padB = 30;
    const prices = history.map((h) => h.price);
    const times = history.map((h) => h.ts);
    const minP = Math.min(...prices), maxP = Math.max(...prices);
    const minT = Math.min(...times), maxT = Math.max(...times);
    const rangeP = maxP - minP || 1, rangeT = maxT - minT || 1;
    const x = (t) => padL + (t - minT) / rangeT * (W - padL - padR);
    const y = (p) => H - padB - (p - minP) / rangeP * (H - padT - padB);

    const GRID = 4;
    let grid = '';
    for (let i = 0; i <= GRID; i++) {
      const p = minP + rangeP * i / GRID;
      const gy = y(p);
      grid += `<line class="id-grid" x1="${padL}" y1="${gy.toFixed(1)}" x2="${W - padR}" y2="${gy.toFixed(1)}"/>`;
      grid += `<text class="id-axis" x="${padL - 8}" y="${(gy + 3).toFixed(1)}" text-anchor="end">${FT.fmt(p)}</text>`;
    }
    const axes = `<line class="id-axisline" x1="${padL}" y1="${padT}" x2="${padL}" y2="${H - padB}"/>`
      + `<line class="id-axisline" x1="${padL}" y1="${H - padB}" x2="${W - padR}" y2="${H - padB}"/>`;
    const dl = (ts) => new Date(ts).toLocaleString(undefined, {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
    const xlabels = `<text class="id-axis" x="${padL}" y="${H - 10}" text-anchor="start">${dl(minT)}</text>`
      + `<text class="id-axis" x="${W - padR}" y="${H - 10}" text-anchor="end">${dl(maxT)}</text>`;
    const pts = history.map((h) => `${x(h.ts).toFixed(1)},${y(h.price).toFixed(1)}`).join(' ');
    const dots = history.map((h) => {
      const when = FT.escapeHtml(
        new Date(h.ts).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }));
      const world = h.world ? ` · ${FT.escapeHtml(h.world)}` : '';
      const tip = `<b>${FT.fmt(h.price)} gil</b><span>${when}</span>`
        + `<span>Qty ${h.quantity}${world}</span>`;
      return `<circle class="id-pt" cx="${x(h.ts).toFixed(1)}" cy="${y(h.price).toFixed(1)}" `
        + `r="3" data-tip="${tip}"></circle>`;
    }).join('');
    return `<svg class="id-graph" viewBox="0 0 ${W} ${H}">
      ${grid}${axes}
      <polyline points="${pts}" fill="none" stroke="var(--accent)" stroke-width="1.5"/>
      ${dots}${xlabels}
    </svg>`;
  }

  function listingRows(listings, withWorld) {
    const cols = withWorld ? 3 : 2;
    if (!listings || !listings.length) {
      return `<tr><td colspan="${cols}" class="dim">No active listings.</td></tr>`;
    }
    return listings.map((l) => {
      const world = withWorld ? `<td>${FT.escapeHtml(l.world || '—')}</td>` : '';
      return `<tr>${world}<td class="num">${FT.fmt(l.price)}</td>`
        + `<td class="num">${l.quantity}</td></tr>`;
    }).join('');
  }

  function detailHtml(d) {
    return `<div class="id-detail-inner">
      ${graph(d.history)}
      <div class="id-tables">
        <div class="id-tcol">
          <h3>All listings · data centre</h3>
          <div class="id-twrap"><table class="data">
            <thead><tr><th>World</th><th class="num">Price</th><th class="num">Qty</th></tr></thead>
            <tbody>${listingRows(d.listings, true)}</tbody>
          </table></div>
        </div>
        <div class="id-tcol">
          <h3>${FT.escapeHtml(d.home_world || 'Home')}</h3>
          <div class="id-twrap"><table class="data">
            <thead><tr><th class="num">Price</th><th class="num">Qty</th></tr></thead>
            <tbody>${listingRows(d.home_listings, false)}</tbody>
          </table></div>
        </div>
      </div>
    </div>`;
  }

  async function openDetail(rowTr, iid, quality) {
    const key = `${iid}:${quality}`;
    openKeys.add(key);
    const tr = document.createElement('tr');
    tr.className = 'id-detail';
    tr.innerHTML = `<td colspan="${rowTr.children.length || 1}">`
      + '<div class="id-detail-inner id-loading"><div class="spinner"></div></div></td>';
    rowTr.after(tr);

    let d = cache.get(key);
    if (!d) {
      try {
        const r = await fetch(`/api/item/${iid}?quality=${quality}`);
        if (!r.ok) throw new Error('HTTP ' + r.status);
        d = await r.json();
        cache.set(key, d);
      } catch {
        if (tr.isConnected) {
          tr.firstChild.innerHTML =
            '<div class="id-detail-inner"><p class="dim">Could not load item data.</p></div>';
        }
        return;
      }
    }
    if (tr.isConnected) tr.firstChild.innerHTML = detailHtml(d);
  }

  document.addEventListener('click', (e) => {
    if (e.target.closest('a, button, input, select')) return;
    const tr = e.target.closest('table.data tbody tr');
    if (!tr || !tr.dataset.iid) return;   // ignores .id-detail rows + nested tables
    // A row's detail panel is always the row immediately after it — toggle it.
    const next = tr.nextElementSibling;
    if (next && next.classList.contains('id-detail')) {
      next.remove();
      openKeys.delete(`${tr.dataset.iid}:${tr.dataset.q || 'nq'}`);
      return;
    }
    openDetail(tr, parseInt(tr.dataset.iid, 10), tr.dataset.q || 'nq');
  });

  // Reopen one key against the current DOM — used after a scan re-renders
  // the page table and wipes our inline detail rows.
  function reopenKey(key) {
    if (!openKeys.has(key)) return;             // user closed it in the meantime
    const [iid, q] = key.split(':');
    const dataRow = document.querySelector(
      `table.data tbody tr[data-iid="${iid}"][data-q="${q}"]`);
    if (!dataRow) return;
    const next = dataRow.nextElementSibling;
    if (next && next.classList.contains('id-detail')) return;   // already there
    openDetail(dataRow, parseInt(iid, 10), q);
  }

  // A fresh scan invalidates cached listings/history — refetch open panels.
  // Page tables re-render at different timings (sync for the market pages,
  // async for the dashboard) so we retry at a few delays.
  window.addEventListener('ft-data-refreshed', () => {
    cache.clear();
    const snapshot = [...openKeys];
    [50, 500, 2000, 5000].forEach((delay) =>
      setTimeout(() => snapshot.forEach(reopenKey), delay));
  });

  // --- graph point hover box ---
  let tipEl = null;
  function showTip(pt, cx, cy) {
    if (!tipEl) {
      tipEl = document.createElement('div');
      tipEl.className = 'id-tip';
      document.body.appendChild(tipEl);
    }
    tipEl.innerHTML = pt.dataset.tip || '';
    tipEl.classList.add('show');
    const r = tipEl.getBoundingClientRect();
    let left = cx + 14;
    let top = cy + 14;
    if (left + r.width > window.innerWidth - 8) left = cx - r.width - 14;
    if (top + r.height > window.innerHeight - 8) top = cy - r.height - 14;
    tipEl.style.left = Math.max(8, left) + 'px';
    tipEl.style.top = Math.max(8, top) + 'px';
  }
  function hideTip() {
    if (tipEl) tipEl.classList.remove('show');
  }
  document.addEventListener('pointermove', (e) => {
    const pt = (e.target instanceof Element) ? e.target.closest('.id-pt') : null;
    if (pt) showTip(pt, e.clientX, e.clientY);
    else hideTip();
  });
})();
