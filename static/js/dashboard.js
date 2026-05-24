// Live dashboard — renders the widget grid from the saved layout.
// Grid math: dashboard-grid.js (FTGrid). Widget defs: dashboard-widgets.js.
const gridEl = document.querySelector('#dash-grid');
const loaderEl = document.querySelector('#page-loader');
const homeInfoEl = document.querySelector('#home-info');
const homeWorldEl = document.querySelector('#home-world');
const dcEl = document.querySelector('#dc');

const LAYOUT_KEY = 'ffxiv-trader.dashboard.v1';

// Each data source -> a one-shot fetch. The loader pulls only the sources the
// enabled widgets declare.
const SOURCES = {
  dashboard: () => fetch('/api/dashboard?top=10').then((r) => r.json()),
  favourites: () => fetch('/api/favourites/snapshot').then((r) => r.json()),
  reliable: () => fetch('/api/reliable/watchlist?top=5').then((r) => r.json()),
  mounts: () => fetch('/api/collectibles/mounts').then((r) => r.json()),
  minions: () => fetch('/api/collectibles/minions').then((r) => r.json()),
  history: () => fetch('/api/history/top?days=7&metric=profit_per_day&source=all&limit=50').then((r) => r.json()),
  scan_status: () => fetch('/api/refresh/status').then((r) => r.json()),
  // Full opportunity set — feeds the derived widgets (bargains, leaders, …).
  opps: async () => {
    const [cw, vd] = await Promise.all([
      fetch('/api/opportunities/cross-world?page=1&page_size=10000').then((r) => r.json()),
      fetch('/api/opportunities/vendor?page=1&page_size=10000').then((r) => r.json()),
    ]);
    return { rows: [...(cw.rows || []), ...(vd.rows || [])] };
  },
};

function setLoading(on) {
  loaderEl?.classList.toggle('hidden', !on);
}

// Saved layout, falling back to the built-in default. Unknown widget types
// (e.g. a removed widget left in an old pref) are dropped.
function loadLayout() {
  const stored = FT.prefGet(LAYOUT_KEY, null);
  const widgets = stored && Array.isArray(stored.widgets) ? stored.widgets : null;
  const base = (widgets && widgets.length) ? widgets : FTWidgets.DEFAULT_LAYOUT;
  return base
    .filter((w) => FTWidgets.REGISTRY[w.type])
    .map((w) => ({ type: w.type, x: w.x, y: w.y, w: w.w, h: w.h }));
}

function saveLayout(widgets) {
  FT.prefSet(LAYOUT_KEY, { version: 1, widgets });
}

async function fetchData(layout) {
  const needed = new Set();
  for (const w of layout) {
    const def = FTWidgets.REGISTRY[w.type];
    if (def) for (const s of def.sources || []) needed.add(s);
  }
  const data = {};
  await Promise.all([...needed].map(async (key) => {
    try { data[key] = await SOURCES[key](); }
    catch { data[key] = null; }
  }));
  return data;
}

function applyTax(data, taxRate) {
  // Recompute profit on every live row set (history rows are pre-aggregated).
  const lists = [
    data.dashboard?.top_cross_world, data.dashboard?.top_vendor, data.dashboard?.maps,
    data.favourites?.rows, data.reliable?.rows,
    data.opps?.rows, data.mounts?.rows, data.minions?.rows,
  ];
  for (const list of lists) {
    if (list) for (const r of list) FT.recomputeProfit(r, taxRate);
  }
}

function renderHomeInfo(game) {
  if (!homeInfoEl || !game) return;
  homeWorldEl.textContent = game.HOME_WORLD || '—';
  dcEl.textContent = game.DATA_CENTER || '—';
  homeInfoEl.style.display = 'inline-flex';
}

// The persisted layout, plus any transient per-widget height overrides (a
// widget asking for more room at runtime — e.g. Search showing results).
let currentLayout = [];
const runtimeHeights = {};

// Persisted layout + height overrides, with collisions pushed down. The saved
// pref is never mutated by a runtime expansion.
function effectiveLayout() {
  const layout = currentLayout.map((w) => ({ ...w }));
  for (const [type, h] of Object.entries(runtimeHeights)) {
    const w = layout.find((x) => x.type === type);
    if (w && h > w.h) {
      w.h = h;
      FTGrid.resolveCollisions(layout, type);
    }
  }
  return layout;
}

// Place every widget element from the effective layout (no content re-render).
function positionAll() {
  for (const w of effectiveLayout()) {
    const el = gridEl.querySelector(`.dash-widget[data-type="${w.type}"]`);
    if (el) {
      el.style.gridColumn = `${w.x + 1} / span ${w.w}`;
      el.style.gridRow = `${w.y + 1} / span ${w.h}`;
    }
  }
}

function renderGrid(layout, data) {
  currentLayout = layout;
  for (const k of Object.keys(runtimeHeights)) delete runtimeHeights[k];
  gridEl.innerHTML = '';
  if (!layout.length) {
    gridEl.innerHTML = '<p class="dim dash-empty">No widgets on the dashboard.</p>';
    return;
  }
  for (const w of layout) {
    const def = FTWidgets.REGISTRY[w.type];
    if (!def) continue;
    const el = document.createElement('div');
    el.className = 'dash-widget';
    el.dataset.type = w.type;
    try {
      def.render(el, data);
    } catch (e) {
      el.innerHTML = '<div class="dw-body"><p class="dim dw-empty">Widget failed to render.</p></div>';
    }
    gridEl.appendChild(el);
  }
  positionAll();
}

async function load() {
  setLoading(true);
  try {
    const layout = loadLayout();
    // Home/DC chip is fetched independently so it always shows — even if no
    // enabled widget needs the heavy /api/dashboard payload.
    const [data, tax, game] = await Promise.all([
      fetchData(layout),
      FT.getTaxInfo(),
      fetch('/api/settings/game').then((r) => r.json()).catch(() => null),
    ]);
    applyTax(data, FT.effectiveTaxRate(tax, FT.loadSettings()));
    renderHomeInfo(game);
    renderGrid(layout, data);
  } catch (e) {
    if (window.toast) window.toast(e.message);
  } finally {
    setLoading(false);
  }
}

// One shared 1s ticker — widgets with a tick() (clock, scan status) update
// live. A single interval avoids per-widget timers leaking on re-render.
setInterval(() => {
  for (const el of gridEl.querySelectorAll('.dash-widget')) {
    const def = FTWidgets.REGISTRY[el.dataset.type];
    if (def && def.tick) { try { def.tick(el); } catch {} }
  }
}, 1000);

// Exposed for the editor overlay (dashboard-editor.js): read the current
// layout (fresh copy) and commit a new one (persist + re-render the grid).
window.FTDash = {
  getLayout: loadLayout,
  saveLayout(widgets) { saveLayout(widgets); load(); },
  // A widget asks for a runtime height (rows). Larger than its persisted
  // height → override + push the widgets below down; otherwise clear it.
  // The saved layout is never changed.
  requestHeight(type, h) {
    const base = (currentLayout.find((w) => w.type === type) || {}).h || 0;
    if (h && h > base) {
      if (runtimeHeights[type] === h) return;
      runtimeHeights[type] = h;
    } else {
      if (!(type in runtimeHeights)) return;
      delete runtimeHeights[type];
    }
    positionAll();
  },
};

window.addEventListener('ft-rescan-all', load);
window.addEventListener('ft-data-refreshed', load);
window.addEventListener('ft-settings-changed', () => { FT.invalidateTaxInfo(); load(); });
window.addEventListener('ft-columns-changed', (e) => {
  if (e.detail && e.detail.page && e.detail.page !== 'dashboard') return;
  load();
});

load();
