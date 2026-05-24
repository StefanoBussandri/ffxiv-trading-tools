// Dashboard editor overlay. The cog (revealed on hovering the page title)
// opens a draft-layout editor: toggle widgets on/off, drag to move, drag the
// corner to resize, click a tile to remove it. Save commits, Cancel discards.
(() => {
  const cog = document.querySelector('#dash-cog');
  if (!cog || !window.FTDash || !window.FTWidgets || !window.FTGrid) return;

  const G = FTGrid;
  const CLICK_THRESHOLD = 4;     // px of movement below which a press is a click

  let draft = [];                // working copy — never the live layout
  let backdrop = null;
  let canvasEl, cellsEl, tilesEl, ghostEl;
  let canvasRows = 0;
  let drag = null;

  // --- draft mutations ---

  function widgetOf(type) {
    return draft.find((w) => w.type === type);
  }

  function addWidget(type) {
    if (widgetOf(type)) return;
    const def = FTWidgets.REGISTRY[type];
    if (!def) return;
    const slot = G.findFreeSlot(draft, def.defaultW, def.defaultH);
    draft.push({ type, x: slot.x, y: slot.y, w: def.defaultW, h: def.defaultH });
  }

  function removeWidget(type) {
    const i = draft.findIndex((w) => w.type === type);
    if (i >= 0) draft.splice(i, 1);
  }

  // --- render ---

  function tileHtml(w) {
    const def = FTWidgets.REGISTRY[w.type];
    return `<div class="de-tile" data-type="${w.type}" `
      + `style="grid-column:${w.x + 1}/span ${w.w};grid-row:${w.y + 1}/span ${w.h}">`
      + `<button class="de-remove" type="button" aria-label="Remove widget" title="Remove">×</button>`
      + `<span class="de-tile-title">${def ? def.title : w.type}</span>`
      + `<div class="de-resize" title="Resize"></div></div>`;
  }

  function applyTilePos(el, w) {
    el.style.gridColumn = `${w.x + 1} / span ${w.w}`;
    el.style.gridRow = `${w.y + 1} / span ${w.h}`;
  }

  function renderPanel() {
    const panel = backdrop.querySelector('.de-panel');
    const types = FTWidgets.types().slice().sort((a, b) =>
      FTWidgets.REGISTRY[a].title.localeCompare(FTWidgets.REGISTRY[b].title));
    panel.innerHTML = types.map((type) => {
      const def = FTWidgets.REGISTRY[type];
      const on = !!widgetOf(type);
      return `<label class="de-wrow">
        <span class="de-wname">${def.title}</span>
        <input type="checkbox" class="de-wtoggle" data-type="${type}" ${on ? 'checked' : ''}>
      </label>`;
    }).join('');
  }

  // Resize the grid-row template / backing cells to fit the layout (+spare).
  function syncCanvasRows() {
    const rows = Math.max(G.gridHeight(draft) + 4, 14);
    if (rows === canvasRows) return;
    canvasRows = rows;
    const tpl = `repeat(${rows}, ${G.ROW_PX}px)`;
    cellsEl.style.gridTemplateRows = tpl;
    tilesEl.style.gridTemplateRows = tpl;
    cellsEl.innerHTML = '<div class="de-cell"></div>'.repeat(rows * G.COLS);
  }

  function renderCanvas() {
    canvasRows = 0;
    syncCanvasRows();
    tilesEl.innerHTML = draft.length
      ? draft.map(tileHtml).join('')
      : '<p class="de-canvas-hint">Toggle widgets on the left to add them to the dashboard.</p>';
  }

  function render() {
    renderPanel();
    renderCanvas();
  }

  // --- drag / resize ---

  function onTileDown(e) {
    if (e.button !== 0) return;
    const tileEl = e.target.closest('.de-tile');
    if (!tileEl || !tilesEl.contains(tileEl)) return;
    const w = widgetOf(tileEl.dataset.type);
    if (!w) return;
    e.preventDefault();
    // The × button removes the widget — no drag.
    if (e.target.closest('.de-remove')) {
      removeWidget(w.type);
      render();
      return;
    }
    drag = {
      type: w.type, w, tileEl,
      isResize: !!e.target.closest('.de-resize'),
      startX: e.clientX, startY: e.clientY,
      cw: tilesEl.getBoundingClientRect().width,
      moved: false,
    };
    if (!drag.isResize) {
      const tr = tileEl.getBoundingClientRect();
      drag.grabDX = e.clientX - tr.left;
      drag.grabDY = e.clientY - tr.top;
    }
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }

  function beginDragVisual() {
    drag.tileEl.classList.add('de-dragging');
    if (!drag.isResize) {
      const r = G.cellRect(drag.w, drag.cw);
      drag.tileEl.style.position = 'absolute';
      drag.tileEl.style.width = r.width + 'px';
      drag.tileEl.style.height = r.height + 'px';
      drag.tileEl.style.zIndex = '5';
      ghostEl.style.display = 'block';
      positionGhost(drag.w);
    }
  }

  function positionGhost(w) {
    const r = G.cellRect(w, drag.cw);
    ghostEl.style.left = r.left + 'px';
    ghostEl.style.top = r.top + 'px';
    ghostEl.style.width = r.width + 'px';
    ghostEl.style.height = r.height + 'px';
  }

  // Re-place every tile from the draft (the lifted move-tile ignores grid pos).
  function reflowTiles() {
    for (const w of draft) {
      const el = tilesEl.querySelector(`.de-tile[data-type="${w.type}"]`);
      if (el) applyTilePos(el, w);
    }
    syncCanvasRows();
  }

  function doMove(e) {
    const w = drag.w;
    const canvasRect = canvasEl.getBoundingClientRect();
    const left = e.clientX - canvasRect.left - drag.grabDX;
    const top = e.clientY - canvasRect.top - drag.grabDY;
    drag.tileEl.style.left = left + 'px';
    drag.tileEl.style.top = top + 'px';
    // Track the snapped target for the ghost + drop. Other tiles are NOT
    // pushed while dragging — collisions resolve only on release.
    w.x = Math.min(Math.max(0, G.snapX(left, drag.cw)), G.COLS - w.w);
    w.y = Math.max(0, G.snapY(top));
    positionGhost(w);
  }

  function doResize(e) {
    const w = drag.w;
    const def = FTWidgets.REGISTRY[w.type];
    const tr = drag.tileEl.getBoundingClientRect();
    const cellW = G.colWidth(drag.cw) + G.GAP;
    const cellH = G.ROW_PX + G.GAP;
    let nw = Math.min(Math.max(def.minW, Math.round((e.clientX - tr.left) / cellW)), G.COLS - w.x);
    const nh = Math.max(def.minH, Math.round((e.clientY - tr.top) / cellH));
    if (nw !== w.w || nh !== w.h) {
      w.w = nw;
      w.h = nh;
      G.resolveCollisions(draft, drag.type);
      reflowTiles();
    }
  }

  function onMove(e) {
    if (!drag) return;
    if (!drag.moved) {
      if (Math.hypot(e.clientX - drag.startX, e.clientY - drag.startY) < CLICK_THRESHOLD) return;
      drag.moved = true;
      beginDragVisual();
    }
    if (drag.isResize) doResize(e);
    else doMove(e);
  }

  function onUp() {
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onUp);
    const d = drag;
    drag = null;
    if (!d) return;
    ghostEl.style.display = 'none';
    if (!d.moved) return;   // a plain press does nothing — remove via the × button
    d.w.x = Math.min(Math.max(0, d.w.x), G.COLS - d.w.w);
    G.resolveCollisions(draft, d.type);
    renderCanvas();
  }

  // --- overlay lifecycle ---

  function buildOverlay() {
    backdrop = document.createElement('div');
    backdrop.className = 'de-backdrop';
    backdrop.innerHTML = `
      <div class="de-modal" role="dialog" aria-modal="true" aria-label="Edit dashboard" tabindex="-1">
        <header class="de-head">
          <h2>Edit dashboard</h2>
          <button class="btn small de-reset" type="button">Reset to default</button>
          <span class="spacer"></span>
          <button class="btn de-cancel" type="button">Cancel</button>
          <button class="btn primary de-save" type="button">Save</button>
        </header>
        <div class="de-body">
          <aside class="de-panel"></aside>
          <div class="de-canvas-wrap">
            <div class="de-canvas">
              <div class="de-cells" aria-hidden="true"></div>
              <div class="de-tiles"></div>
              <div class="de-ghost" aria-hidden="true"></div>
            </div>
          </div>
        </div>
      </div>`;
    document.body.appendChild(backdrop);
    document.body.classList.add('no-scroll');

    canvasEl = backdrop.querySelector('.de-canvas');
    cellsEl = backdrop.querySelector('.de-cells');
    tilesEl = backdrop.querySelector('.de-tiles');
    ghostEl = backdrop.querySelector('.de-ghost');

    backdrop.querySelector('.de-panel').addEventListener('change', (e) => {
      const cb = e.target.closest('.de-wtoggle');
      if (!cb) return;
      if (cb.checked) addWidget(cb.dataset.type);
      else removeWidget(cb.dataset.type);
      renderCanvas();
    });
    tilesEl.addEventListener('mousedown', onTileDown);
    backdrop.querySelector('.de-cancel').addEventListener('click', close);
    backdrop.querySelector('.de-save').addEventListener('click', save);
    backdrop.querySelector('.de-reset').addEventListener('click', () => {
      draft = FTWidgets.DEFAULT_LAYOUT.map((w) => ({ ...w }));
      render();
    });
    backdrop.addEventListener('mousedown', (e) => {
      if (e.target === backdrop) close();
    });
    document.addEventListener('keydown', onKey);
  }

  function onKey(e) {
    if (e.key === 'Escape' && !drag) close();
  }

  function open() {
    if (backdrop) return;
    draft = FTDash.getLayout();
    buildOverlay();
    render();
    backdrop.querySelector('.de-modal').focus();   // keyboard users land inside
  }

  function close() {
    document.removeEventListener('keydown', onKey);
    document.removeEventListener('mousemove', onMove);
    document.removeEventListener('mouseup', onUp);
    drag = null;
    if (backdrop) backdrop.remove();
    backdrop = null;
    document.body.classList.remove('no-scroll');
  }

  function save() {
    FTDash.saveLayout(draft);
    close();
  }

  cog.addEventListener('click', open);
})();
