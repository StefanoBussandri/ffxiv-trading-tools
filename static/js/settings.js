(() => {
  const btn = document.querySelector('#settings-btn');
  if (!btn) return;
  btn.addEventListener('click', openModal);

  const GAME_FIELDS = [
    { id: 'HOME_WORLD',           label: 'Home world',           type: 'select', source: 'worlds' },
    { id: 'DATA_CENTER',          label: 'Data center',          type: 'select', source: 'data_centers' },
    { id: 'TAX_CITY',             label: 'Tax city',             type: 'select', source: 'tax_cities' },
    { id: 'RETAINER_COUNT',       label: 'Retainer count',       type: 'number' },
    { id: 'RETAINER_MARKET_SLOTS', label: 'Slots per retainer',  type: 'number' },
  ];

  const TOOL_FIELDS = [
    { id: 'LISTING_FRESHNESS_HOURS', label: 'Listing freshness (h)', type: 'number' },
    { id: 'MIN_PROFIT_GIL',       label: 'Min profit (gil)',     type: 'number' },
    { id: 'MIN_ROI_PCT',          label: 'Min ROI %',            type: 'number', step: '0.1' },
    { id: 'MAX_ROI_PCT',          label: 'Max ROI %',            type: 'number', step: '0.1' },
    { id: 'MIN_SALES_PER_DAY',    label: 'Min sales/day',        type: 'number', step: '0.1' },
    { id: 'AUTO_RESCAN_SECONDS',  label: 'Auto-rescan interval (s)', type: 'number' },
    { id: 'MIN_RELIABLE_PROFIT_GIL', label: 'Min reliable profit (gil)', type: 'number' },
    { id: 'RELIABLE_WINDOW_DAYS', label: 'Reliable window (days)', type: 'number' },
    { id: 'TARGET_VELOCITY',      label: 'Target velocity (sales/day)', type: 'number', step: '0.1' },
    { id: 'HISTORY_RETENTION_DAYS', label: 'History retention (days)', type: 'number' },
    { id: 'STALE_DATA_HOURS', label: 'Stale data cutoff (h)', type: 'number' },
  ];

  async function loadGameSettings() {
    try {
      const r = await fetch('/api/settings/game');
      if (!r.ok) return {};
      return await r.json();
    } catch { return {}; }
  }

  async function loadOptions() {
    try {
      const r = await fetch('/api/settings/options');
      if (!r.ok) return { worlds: [], data_centers: [], tax_cities: [] };
      return await r.json();
    } catch { return { worlds: [], data_centers: [], tax_cities: [] }; }
  }

  function escapeAttr(s) { return String(s).replace(/"/g, '&quot;'); }

  function fieldsHtml(fields, game, options, tax) {
    return fields.map((f) => {
      const v = game[f.id] != null ? game[f.id] : '';
      if (f.type === 'select') {
        const items = options[f.source] || [];
        const opts = items.map((it) => {
          const val = it.name;
          const sel = String(v) === String(val) ? 'selected' : '';
          let label = val;
          if (f.source === 'tax_cities' && tax && tax.rates && tax.rates[val] != null) {
            label = `${val} (${tax.rates[val]}%)`;
          } else if (f.source === 'data_centers' && it.region) {
            label = `${val} — ${it.region}`;
          }
          const dcAttr = (f.source === 'worlds' && it.id != null) ? ` data-world-id="${it.id}"` : '';
          return `<option value="${escapeAttr(val)}"${dcAttr} ${sel}>${label}</option>`;
        }).join('');
        const dcAttr = (f.id === 'DATA_CENTER')
          ? ' data-controls="HOME_WORLD"' : '';
        return `
          <div class="field">
            <label for="game-${f.id}">${f.label}</label>
            <select id="game-${f.id}" data-game="${f.id}" data-type="text" class="styled-select"${dcAttr}>${opts}</select>
          </div>`;
      }
      const step = f.step ? `step="${f.step}"` : '';
      return `
        <div class="field">
          <label for="game-${f.id}">${f.label}</label>
          <input type="${f.type}" id="game-${f.id}" data-game="${f.id}" data-type="${f.type}" value="${v}" ${step}>
        </div>`;
    }).join('');
  }

  async function openModal() {
    const s = FT.loadSettings();
    const tax = await FT.getTaxInfo();
    const [game, options] = await Promise.all([loadGameSettings(), loadOptions()]);
    const ceiling = (game.RETAINER_COUNT || 0) * (game.RETAINER_MARKET_SLOTS || 0) || 40;

    const backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    backdrop.innerHTML = `
      <div class="modal modal-wide" role="dialog" aria-label="Settings">
        <h2>Settings</h2>

        <h3 class="section">Display</h3>
        <div class="field">
          <label for="set-budget">Budget (gil per unit)</label>
          <input type="number" id="set-budget" min="0" step="1000" value="${s.budget || ''}">
        </div>
        <div class="hint">Filters opportunities by per-unit buy price.</div>
        <div class="field">
          <label for="set-page-size">Page size</label>
          <input type="number" id="set-page-size" min="1" step="1" value="${s.page_size || ''}" placeholder="default (${ceiling})">
        </div>
        <div class="hint">Empty = retainer ceiling (${ceiling}).</div>
        <div class="field">
          <label for="set-alerts-sound">Alert sound</label>
          <input type="checkbox" id="set-alerts-sound" ${s.alerts_sound ? 'checked' : ''}>
        </div>
        <div class="field">
          <label for="set-alerts-volume">Alert volume</label>
          <input type="range" id="set-alerts-volume" min="0" max="100" step="5"
                 value="${Math.round((s.alerts_volume != null ? s.alerts_volume : 0.5) * 100)}">
        </div>
        <div class="hint">Ping when a favourite price alert triggers.</div>

        <h3 class="section">Game</h3>
        ${fieldsHtml(GAME_FIELDS, game, options, tax)}

        <h3 class="section">Tool</h3>
        ${fieldsHtml(TOOL_FIELDS, game, options, tax)}

        <h3 class="section">Server caches</h3>
        <div class="hint" style="margin-top:0;">Rebuild on-disk reference caches. Useful after game patches.</div>
        <div class="actions" style="justify-content:flex-start; margin-top:.5rem; gap:.5rem;">
          <button class="btn" id="cache-tax">Refresh tax</button>
          <button class="btn" id="cache-vendors">Rebuild vendors</button>
          <button class="btn" id="cache-icons">Rebuild icons</button>
          <button class="btn" id="cache-all">Rebuild everything</button>
        </div>

        <div class="actions">
          <button class="btn" id="set-cancel">Cancel</button>
          <button class="btn primary" id="set-save">Save &amp; reload</button>
        </div>
      </div>
    `;
    document.body.appendChild(backdrop);
    document.body.classList.add('no-scroll');
    const close = () => { backdrop.remove(); document.body.classList.remove('no-scroll'); };
    backdrop.querySelector('#set-cancel').addEventListener('click', close);
    backdrop.addEventListener('click', (e) => { if (e.target === backdrop) close(); });

    async function runRefresh(resource, label, btnEl) {
      btnEl.disabled = true;
      btnEl.classList.add('loading');
      try {
        const r = await fetch('/api/refresh?resource=' + resource, { method: 'POST' });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const d = await r.json();
        if (window.toast) window.toast(`Refreshed ${label}: ${(d.refreshed || []).join(', ') || 'ok'}`, 'info');
      } catch (err) {
        if (window.toast) window.toast(err.message);
      } finally {
        btnEl.disabled = false;
        btnEl.classList.remove('loading');
      }
    }
    backdrop.querySelector('#cache-tax').addEventListener('click', (e) => runRefresh('tax', 'tax', e.currentTarget));
    backdrop.querySelector('#cache-vendors').addEventListener('click', (e) => runRefresh('vendors', 'vendors', e.currentTarget));
    backdrop.querySelector('#cache-icons').addEventListener('click', (e) => runRefresh('icons', 'icons', e.currentTarget));
    backdrop.querySelector('#cache-all').addEventListener('click', (e) => runRefresh('all', 'all caches', e.currentTarget));

    // Alert volume slider follows the sound on/off checkbox.
    const soundChk = backdrop.querySelector('#set-alerts-sound');
    const volSlider = backdrop.querySelector('#set-alerts-volume');
    const syncVol = () => { volSlider.disabled = !soundChk.checked; };
    soundChk.addEventListener('change', syncVol);
    syncVol();
    // Releasing the slider previews the volume with a test ping.
    volSlider.addEventListener('change', () => {
      if (window.FTAlerts) window.FTAlerts.ping((parseInt(volSlider.value, 10) || 0) / 100);
    });

    // DC change → filter HOME_WORLD options to only worlds in selected DC.
    const dcSel = backdrop.querySelector('#game-DATA_CENTER');
    const worldSel = backdrop.querySelector('#game-HOME_WORLD');
    function applyWorldFilter() {
      if (!dcSel || !worldSel) return;
      const dcName = dcSel.value;
      const dc = (options.data_centers || []).find((d) => d.name === dcName);
      const allow = dc ? new Set(dc.world_ids || []) : null;
      let firstAllowed = null;
      Array.from(worldSel.options).forEach((opt) => {
        if (!opt.value) { opt.hidden = false; opt.disabled = false; return; }
        const wid = parseInt(opt.dataset.worldId || '0', 10);
        const ok = !allow || allow.has(wid);
        opt.hidden = !ok;
        opt.disabled = !ok;
        if (ok && firstAllowed == null) firstAllowed = opt.value;
      });
      if (allow && worldSel.value) {
        const cur = Array.from(worldSel.options).find((o) => o.value === worldSel.value);
        if (cur && cur.disabled) worldSel.value = firstAllowed || '';
      }
    }
    dcSel?.addEventListener('change', applyWorldFilter);
    applyWorldFilter();

    backdrop.querySelector('#set-save').addEventListener('click', async () => {
      const next = {
        budget: parseInt(backdrop.querySelector('#set-budget').value, 10) || '',
        page_size: parseInt(backdrop.querySelector('#set-page-size').value, 10) || '',
        tax_city: backdrop.querySelector('#game-TAX_CITY')?.value || '',
        alerts_sound: backdrop.querySelector('#set-alerts-sound').checked,
        alerts_volume: (parseInt(backdrop.querySelector('#set-alerts-volume').value, 10) || 0) / 100,
      };
      FT.saveSettings(next);

      // Game settings -> server
      const gamePayload = {};
      backdrop.querySelectorAll('[data-game]').forEach((inp) => {
        const key = inp.dataset.game;
        if (inp.value === '') return;
        gamePayload[key] = (inp.dataset.type === 'number') ? Number(inp.value) : inp.value;
      });
      try {
        const r = await fetch('/api/settings/game', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(gamePayload),
        });
        if (!r.ok) throw new Error('HTTP ' + r.status);
      } catch (err) {
        if (window.toast) window.toast('Game settings save failed: ' + err.message);
      }
      location.reload();
    });
  }
})();
