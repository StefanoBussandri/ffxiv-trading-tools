// Renders tax chips into #tax-panel (inside .taxbar from partials.js).
async function loadTaxPanel() {
  const panel = document.querySelector('#tax-panel');
  const meta = document.querySelector('#tax-meta');
  if (!panel) return;
  panel.innerHTML = '<span class="dim">loading…</span>';
  if (meta) meta.innerHTML = '';
  try {
    FT.invalidateTaxInfo();
    const tax = await FT.getTaxInfo();
    const rates = tax.rates || {};
    const cheapest = new Set(tax.cheapest_cities || []);
    const settings = FT.loadSettings();
    const userCity = settings.tax_city || tax.retainer_city;

    const chips = Object.entries(rates).map(([city, pct]) => {
      const cls = ['tax-chip'];
      if (city === userCity) cls.push('home');
      else if (cheapest.has(city)) cls.push('dc-active');
      const titleParts = [];
      if (cheapest.has(city)) titleParts.push('cheapest on DC');
      if (city === userCity) titleParts.push('your retainer city');
      const title = titleParts.length ? ` title="${titleParts.join(' · ')}"` : '';
      return `<span class="${cls.join(' ')}"${title}><span class="city">${city}</span><span class="pct">${pct}%</span></span>`;
    });
    panel.innerHTML = chips.join('');

    if (meta) {
      const updatedTxt = tax.fetched_at
        ? `<span class="dim" title="${new Date(tax.fetched_at).toLocaleString()}">updated ${FT.agoMs(tax.fetched_at)}</span>`
        : '';
      meta.innerHTML = `
        ${updatedTxt}
        <button class="refresh-tiny" id="tax-refresh" title="Refresh tax rates" aria-label="Refresh tax">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="23 4 23 10 17 10"></polyline>
            <path d="M3.51 9a9 9 0 0114.85-3.36L23 10"></path>
          </svg>
        </button>
      `;
      document.querySelector('#tax-refresh')?.addEventListener('click', async (e) => {
        const btn = e.currentTarget;
        btn.disabled = true;
        try {
          const r = await fetch('/api/refresh?resource=tax', { method: 'POST' });
          if (!r.ok) throw new Error('HTTP ' + r.status);
          if (window.toast) window.toast('Tax rates refreshed', 'info');
          await loadTaxPanel();
        } catch (err) {
          if (window.toast) window.toast(err.message);
        } finally {
          btn.disabled = false;
        }
      });
    }
  } catch (e) {
    panel.innerHTML = `<span class="dim">unavailable: ${e.message}</span>`;
  }
}

loadTaxPanel();
