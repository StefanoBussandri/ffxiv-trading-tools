// Favourite price alerts. Evaluates each favourite's buy/sell thresholds
// against live prices on load and after every auto-rescan; a newly-met rule
// fires a toast + a ping. Fired alerts are remembered in sessionStorage so
// navigating between pages does not re-ping or re-toast the same alert.
(() => {
  if (!window.FT) return;

  const STORE = 'ffxiv-trader.alerts.fired.v1';
  let audioCtx = null;

  function loadFired() {
    try { return new Set(JSON.parse(sessionStorage.getItem(STORE) || '[]')); }
    catch { return new Set(); }
  }
  function saveFired(set) {
    try { sessionStorage.setItem(STORE, JSON.stringify([...set])); } catch {}
  }
  let triggered = loadFired();

  // One short beep. `volOverride` (0–1) plays at that level regardless of the
  // sound toggle — used by the settings volume slider to preview loudness.
  function ping(volOverride) {
    let vol;
    if (volOverride != null) {
      vol = volOverride;
    } else {
      const s = FT.loadSettings();
      if (!s.alerts_sound) return;
      vol = s.alerts_volume != null ? s.alerts_volume : 0.5;
    }
    vol = Math.max(0, Math.min(1, vol));
    if (vol <= 0) return;
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return;
      audioCtx = audioCtx || new Ctx();
      if (audioCtx.state === 'suspended') audioCtx.resume();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'sine';
      osc.frequency.value = 880;
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      const t = audioCtx.currentTime;
      const peak = vol * 0.3;          // gentle even at max
      gain.gain.setValueAtTime(peak, t);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.3);
      osc.start(t);
      osc.stop(t + 0.3);
    } catch { /* audio blocked — toast still shows */ }
  }

  function ruleMet(price, target, dir) {
    if (target == null || price == null) return false;
    return dir === 'above' ? price >= target : price <= target;
  }

  async function check() {
    let rows;
    try {
      const r = await fetch('/api/favourites/snapshot');
      if (!r.ok) return;
      rows = (await r.json()).rows || [];
    } catch { return; }

    const active = new Set();
    let newCount = 0;
    for (const row of rows) {
      const base = `${row.itemId}:${row.quality}`;
      const sides = [
        ['buy', 'Buy', row.buy_price, row.buy_target, row.buy_dir],
        ['sell', 'Sell', row.sell_price, row.sell_target, row.sell_dir],
      ];
      for (const [side, label, price, target, dir] of sides) {
        if (!ruleMet(price, target, dir)) continue;
        const key = `${base}:${side}`;
        active.add(key);
        if (triggered.has(key)) continue;   // already fired this session
        triggered.add(key);
        newCount += 1;
        const cmp = dir === 'above' ? '≥' : '≤';
        window.toast(
          `${row.name} — ${label} ${FT.fmt(price)} ${cmp} ${FT.fmt(target)}`,
          'alert',
        );
      }
    }
    // Keep only still-met keys, so a lapsed rule can fire again later.
    triggered = new Set([...triggered].filter((k) => active.has(k)));
    saveFired(triggered);
    // One ping per cycle — multiple simultaneous alerts never stack loudness.
    if (newCount > 0) ping();
  }

  // Forget every fired alert, then re-evaluate — used by a favourites rescan.
  function recheck() {
    triggered.clear();
    check();
  }

  // Forget only one favourite's fired state, then re-evaluate — used when its
  // alert thresholds are edited, so other alerts never re-ping.
  function reset(iid, quality) {
    triggered.delete(`${iid}:${quality}:buy`);
    triggered.delete(`${iid}:${quality}:sell`);
    check();
  }

  check();
  window.addEventListener('ft-data-refreshed', check);

  window.FTAlerts = { ping, check, recheck, reset };
})();
