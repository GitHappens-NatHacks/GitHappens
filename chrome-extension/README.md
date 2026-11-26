# ClearCursor Web Assist (Chrome / Edge / Brave Extension)

Manifest V3 browser extension bringing ClearCursor's One-Euro pointer smoothing, 180ms Click-Freeze lock, 2.5x DOM button gravity wells, and accessible reading/contrast aids directly to web pages on Windows, macOS, and Linux.

## Install Unpacked Extension (Chrome / Edge)
1. Open `chrome://extensions` (or `edge://extensions`).
2. Enable **Developer mode**.
3. Click **Load unpacked** and select this `chrome-extension/` folder.
4. Pin and click **ClearCursor Web Assist** in the browser toolbar.
5. *(Optional)* Start the ClearCursor desktop app and click **Sync App** in the popup to import your active preset (`One-Euro cutoff/beta`, `Click-Freeze`, and `Gravity Wells`), or run the extension standalone offline.

## Controls
- **Esc**: Pause virtual pointer and gravity-well interception on the current tab.
- **Alt+Shift+S**: Toggle assist on or off on the current tab.
- **Restore**: Remove all injected styling and overlays from the page.

## Run Automated Tests
```bash
npm --prefix chrome-extension test
```
