// Renders shared topbar + taxbar shells into placeholders.
// MUST load before tax.js, rescan-timer.js, settings.js so their selectors exist.
// Markup mirrored in static/components/topbar.html and taxbar.html for reference.
(() => {
  const NAV = [
    ['dashboard',   '/dashboard.html', 'Dashboard'],
    ['reliable',    '/reliable.html',  'Reliable'],
    ['cross-world', '/index.html',     'Cross-world'],
    ['vendor',      '/vendor.html',    'Vendor'],
    ['maps',        '/maps.html',      'Maps'],
    ['mounts',      '/mounts.html',    'Mounts'],
    ['minions',     '/minions.html',   'Minions'],
    ['favourites',   '/favourites.html', 'Favourites'],
    ['history',     '/history.html',   'History'],
  ];

  const SVG_RESCAN = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"></path></svg>`;

  const SVG_SETTINGS = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>`;

  function topbarInner(activeKey) {
    const links = NAV.map(([key, href, label]) => {
      const cls = activeKey === key ? ' class="active"' : '';
      return `<a href="${href}" data-nav="${key}"${cls}>${label}</a>`;
    }).join('');
    return `
      <div class="brand">
        <img class="mark" src="/img/favicon.svg" alt="" width="22" height="22">
        <div class="name"><b>ffxiv</b>-trader</div>
      </div>
      <nav class="main-nav nav">${links}</nav>
      <div class="toolbar-r">
        <div id="rescan-timer" class="status-pill"><span class="dot"></span><span class="status-pill-label">Loading…</span></div>
        <button class="icon-btn" id="topbar-rescan" title="Force rescan all">${SVG_RESCAN}</button>
        <button class="icon-btn" id="settings-btn" title="Settings">${SVG_SETTINGS}</button>
      </div>
    `;
  }

  function taxbarInner() {
    return `
      <span class="label">Retainer tax</span>
      <span id="tax-panel" class="tax-chips"><span class="dim">loading…</span></span>
      <span class="meta" id="tax-meta"></span>
    `;
  }

  // Render topbar(s).
  document.querySelectorAll('[data-component="topbar"]').forEach((host) => {
    host.classList.add('topbar');
    host.innerHTML = topbarInner(host.dataset.active || '');
  });

  // Render taxbar(s).
  document.querySelectorAll('[data-component="taxbar"]').forEach((host) => {
    host.classList.add('taxbar');
    host.innerHTML = taxbarInner();
  });

  // Wire topbar rescan-all icon.
  const rescanAllBtn = document.getElementById('topbar-rescan');
  rescanAllBtn?.addEventListener('click', async () => {
    rescanAllBtn.disabled = true;
    try {
      const r = await fetch('/api/refresh?resource=all', { method: 'POST' });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      if (window.toast) window.toast('Rescan started', 'info');
      window.dispatchEvent(new CustomEvent('ft-rescan-all'));
    } catch (e) {
      if (window.toast) window.toast(e.message);
    } finally {
      rescanAllBtn.disabled = false;
    }
  });

  // Favicon: yellow "ff" mark idle, green "ff" while a rescan runs.
  // ft-scan-start / ft-scan-end are dispatched by rescan-timer.js.
  let favLink = document.querySelector('link[rel~="icon"]');
  if (!favLink) {
    favLink = document.createElement('link');
    favLink.rel = 'icon';
    document.head.appendChild(favLink);
  }
  favLink.type = 'image/svg+xml';
  favLink.href = '/img/favicon.svg';
  window.addEventListener('ft-scan-start', () => { favLink.href = '/img/favicon-scan.svg'; });
  window.addEventListener('ft-scan-end',   () => { favLink.href = '/img/favicon.svg'; });
})();
