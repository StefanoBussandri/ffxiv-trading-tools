// Dashboard grid math — pure logic, no DOM. Shared by the live renderer
// (dashboard.js) and the editor overlay (dashboard-editor.js).
//
// Widget rect = integer cell coords { type, x, y, w, h }:
//   x  0..COLS-1     column (left edge)
//   w  1..COLS       width in columns
//   y  0..           row (top edge)
//   h  1..           height in rows
// A "layout" is an array of such rects, one per enabled widget type.
window.FTGrid = (() => {
  const COLS = 12;        // grid columns (matches the .span-* CSS system)
  const ROW_PX = 40;      // row unit height in pixels
  const GAP = 14;         // gap between cells in pixels

  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

  // --- pixel geometry (column width is fluid → needs the container width) ---

  function colWidth(containerW) {
    return (containerW - (COLS - 1) * GAP) / COLS;
  }

  // Cell rect → absolute pixel rect, for positioning a widget in the editor.
  function cellRect(w, containerW) {
    const cw = colWidth(containerW);
    return {
      left: w.x * (cw + GAP),
      top: w.y * (ROW_PX + GAP),
      width: w.w * cw + (w.w - 1) * GAP,
      height: w.h * ROW_PX + (w.h - 1) * GAP,
    };
  }

  // Pixel offset → nearest cell coordinate (snap-to-grid).
  function snapX(px, containerW) {
    return clamp(Math.round(px / (colWidth(containerW) + GAP)), 0, COLS);
  }
  function snapY(px) {
    return Math.max(0, Math.round(px / (ROW_PX + GAP)));
  }

  // --- cell-coordinate logic (no pixels) ---

  // Two rects overlap when they intersect on both axes (edges touching = OK).
  function overlaps(a, b) {
    return a.x < b.x + b.w && b.x < a.x + a.w &&
           a.y < b.y + b.h && b.y < a.y + a.h;
  }

  // Keep a rect inside the 12-column grid. w/h floored to >= 1; x kept so the
  // widget fits; y kept >= 0. Per-widget min sizes are applied by the caller
  // (the widget registry owns those) before this runs.
  function clampToGrid(rect) {
    const w = clamp(Math.round(rect.w) || 1, 1, COLS);
    const h = Math.max(1, Math.round(rect.h) || 1);
    const x = clamp(Math.round(rect.x) || 0, 0, COLS - w);
    const y = Math.max(0, Math.round(rect.y) || 0);
    return { ...rect, x, y, w, h };
  }

  // Total rows the layout occupies (for sizing the grid canvas).
  function gridHeight(layout) {
    return layout.reduce((max, w) => Math.max(max, w.y + w.h), 0);
  }

  // Push-out: after `movedType` has been placed at its new rect, shove every
  // overlapping widget straight down to clear it, cascading. Only ever moves
  // widgets down, so y strictly increases and the recursion terminates.
  // Mutates `layout` in place; returns it.
  function resolveCollisions(layout, movedType) {
    const moved = layout.find((w) => w.type === movedType);
    if (!moved) return layout;

    function push(anchor) {
      for (const o of layout) {
        if (o === anchor) continue;
        if (!overlaps(anchor, o)) continue;
        const clearY = anchor.y + anchor.h;
        if (o.y < clearY) {
          o.y = clearY;
          push(o);            // o moved — it may now hit widgets below it
        }
      }
    }
    push(moved);
    return layout;
  }

  // First free top-down, left-right slot that fits a w×h widget without
  // overlapping anything in `layout`. Used to place a newly enabled widget
  // "as near the top as it fits".
  function findFreeSlot(layout, w, h) {
    const limit = gridHeight(layout) + h + 1;
    for (let y = 0; y < limit; y++) {
      for (let x = 0; x + w <= COLS; x++) {
        const cand = { x, y, w, h };
        if (!layout.some((o) => overlaps(cand, o))) return { x, y };
      }
    }
    return { x: 0, y: gridHeight(layout) };   // fallback: append at the bottom
  }

  return {
    COLS, ROW_PX, GAP,
    colWidth, cellRect, snapX, snapY,
    overlaps, clampToGrid, gridHeight, resolveCollisions, findFreeSlot,
  };
})();
