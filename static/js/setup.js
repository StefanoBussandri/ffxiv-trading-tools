// First-run setup screen. Standalone — does NOT load common.js, so the
// boot-guard redirect never loops back here. Populates the server dropdowns,
// shows background-load progress, and posts /api/setup.
(() => {
  const $ = (id) => document.getElementById(id);
  const dcSel = $('data_center');
  const worldSel = $('home_world');
  const taxSel = $('tax_city');
  const form = $('setup-form');
  const submitBtn = $('setup-submit');
  const errEl = $('setup-error');
  const progressEl = $('setup-progress');

  let options = { worlds: [], data_centers: [], tax_cities: [] };

  function opt(value, label) {
    const o = document.createElement('option');
    o.value = value;
    o.textContent = label;
    return o;
  }

  // Already configured (e.g. someone typed /setup.html by hand) → go home.
  fetch('/api/setup/status')
    .then((r) => r.json())
    .then((d) => { if (d && d.configured) location.replace('/'); })
    .catch(() => {});

  async function loadOptions() {
    try {
      const r = await fetch('/api/settings/options');
      if (r.ok) options = await r.json();
    } catch { /* leave empty — validation keeps submit from saving junk */ }

    dcSel.appendChild(opt('', 'Select…'));
    for (const dc of options.data_centers || []) {
      dcSel.appendChild(opt(dc.name, dc.region ? `${dc.name} (${dc.region})` : dc.name));
    }
    worldSel.appendChild(opt('', 'Select…'));
    for (const w of options.worlds || []) {
      const o = opt(w.name, w.name);
      o.dataset.worldId = w.id;
      worldSel.appendChild(o);
    }
    taxSel.appendChild(opt('', 'Select…'));
    for (const c of options.tax_cities || []) {
      taxSel.appendChild(opt(c.name, c.name));
    }
    applyWorldFilter();
  }

  // DC change → only worlds on that DC stay selectable. Mirrors settings.js.
  function applyWorldFilter() {
    const dc = (options.data_centers || []).find((d) => d.name === dcSel.value);
    const allow = dc ? new Set(dc.world_ids || []) : null;
    for (const o of worldSel.options) {
      if (!o.value) { o.hidden = false; o.disabled = false; continue; }
      const wid = parseInt(o.dataset.worldId || '0', 10);
      const ok = !allow || allow.has(wid);
      o.hidden = !ok;
      o.disabled = !ok;
    }
    const cur = Array.from(worldSel.options).find((o) => o.value === worldSel.value);
    if (cur && cur.disabled) worldSel.value = '';
  }
  dcSel.addEventListener('change', applyWorldFilter);

  // --- Background-load progress indicator ---
  const STEP_LABELS = {
    items: 'item names', vendors: 'vendors', maps: 'maps',
    mounts: 'mounts', minions: 'minions', icons: 'icons',
  };
  async function pollProgress() {
    try {
      const r = await fetch('/api/startup/status');
      if (r.ok) {
        const data = await r.json();
        if (data.error) {
          progressEl.innerHTML = `<span class="bad">${data.error}</span>`;
          return; // blocking-phase failure — needs a restart, stop polling
        }
        if (data.ready) {
          progressEl.innerHTML = '<span class="ok">Game data ready ✓</span>';
          return;
        }
        const parts = Object.entries(data.steps || {}).map(([k, st]) => {
          const lbl = STEP_LABELS[k] || k;
          if (st === 'done') return `<span class="ok">${lbl} ✓</span>`;
          if (st === 'failed') return `<span class="bad">${lbl} ✗</span>`;
          return `<span class="wait">${lbl}</span>`;
        });
        progressEl.innerHTML = 'Loading game data… ' + parts.join(' ');
      }
    } catch { /* transient — retry below */ }
    setTimeout(pollProgress, 1500);
  }

  // --- Submit ---
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errEl.textContent = '';
    const payload = {
      data_center: dcSel.value,
      home_world: worldSel.value,
      tax_city: taxSel.value,
      retainer_count: parseInt($('retainer_count').value, 10),
      budget: parseInt($('budget').value, 10),
    };
    if (!payload.data_center || !payload.home_world || !payload.tax_city) {
      errEl.textContent = 'Pick a data center, home world and tax city.';
      return;
    }
    if (!(payload.retainer_count > 0) || !(payload.budget > 0)) {
      errEl.textContent = 'Retainers and budget must be positive numbers.';
      return;
    }
    const dc = (options.data_centers || []).find((d) => d.name === payload.data_center);
    const w = (options.worlds || []).find((x) => x.name === payload.home_world);
    if (dc && w && Array.isArray(dc.world_ids) && !dc.world_ids.includes(w.id)) {
      errEl.textContent = 'That home world is not on the selected data center.';
      return;
    }
    submitBtn.disabled = true;
    submitBtn.textContent = 'Saving…';
    try {
      const r = await fetch('/api/setup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      location.replace('/');
    } catch (err) {
      errEl.textContent = 'Could not save settings — ' + err.message;
      submitBtn.disabled = false;
      submitBtn.textContent = 'Start trading';
    }
  });

  loadOptions();
  pollProgress();
})();
