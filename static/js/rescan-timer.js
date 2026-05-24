(() => {
  const host = document.querySelector('#rescan-timer');
  if (!host) return;

  let nextTs = 0;
  let inProgress = false;
  let interval = 0;
  let enabled = true;
  let lastFetch = 0;
  let bootReady = false;
  let bootTimer = 0;
  let scanProgress = null;  // { done, total } while a scan is in flight
  let lastRescanTs = -1;    // -1 = not yet observed; tracks scan completions
  let prevInProgress = false;  // edge-detect scan start/end for the favicon swap

  // While the background bootstrap loads heavy game data, the pill shows
  // "Preparing game data…" so the main pages signal loading is in progress.
  async function refreshBootStatus() {
    try {
      const r = await fetch('/api/startup/status');
      if (!r.ok) return;
      const d = await r.json();
      bootReady = !!d.ready;
      if (bootReady && bootTimer) { clearInterval(bootTimer); bootTimer = 0; }
    } catch {}
  }

  async function refreshStatus() {
    try {
      const r = await fetch('/api/refresh/status');
      if (!r.ok) return;
      const d = await r.json();
      nextTs = d.next_rescan_ts || 0;
      inProgress = !!d.in_progress;
      if (inProgress !== prevInProgress) {
        prevInProgress = inProgress;
        window.dispatchEvent(new CustomEvent(inProgress ? 'ft-scan-start' : 'ft-scan-end'));
      }
      scanProgress = d.scan_progress || null;
      interval = d.interval_seconds || 0;
      enabled = !!d.enabled;
      lastFetch = Date.now();
      // A finished scan bumps last_rescan_ts — tell the active page to reload
      // its table data in place (covers the first-run scan and auto-rescans).
      const lrt = d.last_rescan_ts || 0;
      if (lastRescanTs < 0) {
        lastRescanTs = lrt;
      } else if (lrt > lastRescanTs) {
        lastRescanTs = lrt;
        window.dispatchEvent(new CustomEvent('ft-data-refreshed'));
      }
    } catch {}
  }

  function fmt(secs) {
    if (secs <= 0) return '00:00';
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }

  function paint(label, countdown, title) {
    host.innerHTML = `<span class="dot"></span><span class="status-pill-label">${label}</span>${countdown ? `<span class="sep">·</span><span class="countdown mono">${countdown}</span>` : ''}`;
    host.title = title || '';
  }

  function tick() {
    if (!bootReady) {
      paint('Preparing game data…', '', 'Background game data is still loading — pages fill in as it finishes');
      return;
    }
    if (!enabled) {
      paint('Auto-rescan off', '', 'Set AUTO_RESCAN_SECONDS > 0 in .env');
      return;
    }
    if (inProgress) {
      const p = scanProgress;
      const label = (p && p.total)
        ? `${p.label || 'Rescanning'} ${p.done}/${p.total}`
        : 'Rescanning';
      paint(label, '', 'Scan in progress');
      // Poll fast while scanning so the count updates live.
      if (Date.now() - lastFetch > 1500) refreshStatus();
      return;
    }
    if (!nextTs) {
      paint('Waiting…', '', 'Waiting for first rescan');
      return;
    }
    const secs = Math.max(0, Math.round((nextTs - Date.now()) / 1000));
    paint('Next rescan', fmt(secs), `Auto-rescan every ${interval}s · next at ${new Date(nextTs).toLocaleTimeString()}`);
    if (secs === 0 && Date.now() - lastFetch > 5000) refreshStatus();
  }

  refreshBootStatus();
  refreshStatus();
  bootTimer = setInterval(refreshBootStatus, 3000);
  setInterval(tick, 1000);
  setInterval(refreshStatus, 30000);
})();
