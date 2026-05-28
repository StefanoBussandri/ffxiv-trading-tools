# FFXIV Trader — first-run guide

Quick installer-free Windows app for spotting Universalis arbitrage on your
home world. No game files touched, no install — just a folder.

## Install

1. Download `FFXIV-Trader-vX.Y.Z-windows.zip` from the Releases page.
2. **Extract** it (right-click → Extract All). Do NOT run from inside the
   `.zip` — Windows extracts to a temp folder and the DB will vanish.
3. Drop the extracted `FFXIV-Trader` folder anywhere you can write to.
   Desktop, Documents, or `C:\Tools\` all fine. Avoid `Program Files` and
   `Program Files (x86)` — those need admin to write into.
4. Open the folder, double-click `FFXIV Trader.exe`.

### "Windows protected your PC"

The build is not code-signed (signing certs cost more than the app), so
SmartScreen blocks unsigned exes by default. To run it:

1. Click **More info**.
2. Click **Run anyway**.

This is a one-time prompt per build version.

## First launch

1. Tray icon (yellow square) appears bottom-right. Browser tab opens
   automatically pointing at `http://127.0.0.1:8000`.
2. First-run setup screen asks for:
   - **Home World** (e.g. Odin) — where your retainers live.
   - **Data Center** auto-fills from world.
   - **Tax City** — whichever city your retainers list in.
   - **Retainers** — how many you have (1–9).
   - **Budget** — gil/unit ceiling for opportunity scoring.
3. Click **Start trading**. First scan can take 30–60s while it pulls
   marketable items from Universalis. Subsequent scans are cached.

## Day-to-day

- Closing the browser tab fully exits the app after ~90s.
- Tray icon → **Open FFXIV Trader** reopens the tab if you closed it.
- Tray icon → **Quit** stops the server immediately.
- Tray icon → **Open log folder** if anything looks wrong.
- Tray icon → **About** shows version + where data + logs live.

## Things that change on you

- **All settings are editable in-app** — top-right gear icon. Home world,
  tax city, retainer count, scan interval, profit thresholds, ROI bounds.
- **No game data needed.** It does not read FFXIV files or memory. It only
  hits public APIs (Universalis, XIVAPI).

## Data location

Everything writable lives under `%LOCALAPPDATA%\FFXIVTrader\`:

- `data.db` — your settings, favourites, scan history.
- `cache\` — bundled item catalog + icon thumbnails.
- `logs\app.log` — rotating log (5 × 1 MiB). Send this if it breaks.
- `.env` — infra config (API URLs, rate limits). Don't touch unless asked.

Wiping that folder = fresh install.

## Uninstall

Double-click `Uninstall.bat` inside the extracted folder. It will:

1. Ask you to type **YES** to confirm.
2. Stop the running app.
3. Delete `%LOCALAPPDATA%\FFXIVTrader\` (settings, history, cache, logs).
4. Delete the Desktop and Start Menu shortcuts.
5. Delete the install folder itself (a couple seconds after the script
   exits — that delay is normal, the folder cannot delete itself while the
   script is still running inside it).

Manual fallback if the bat fails: quit via tray → delete the install
folder → delete `%LOCALAPPDATA%\FFXIVTrader\`.

## When something breaks

1. Tray → **Open log folder** → grab `app.log` (and `app.log.1` if recent).
2. DM the file to Stefano.
3. If the app crashed on launch, you should get a popup with the error tail
   and the log path — same drill, send the log.

## Updating

Releases auto-publish on GitHub. To update:

1. Quit running instance (tray → Quit).
2. Download new `.zip`, replace the extracted folder.
3. `%LOCALAPPDATA%\FFXIVTrader\` is untouched — settings + history carry
   over.
