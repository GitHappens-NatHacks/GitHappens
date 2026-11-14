# TrueCursor Web Assist (Chrome / Edge / Brave Extension)

Manifest V3 browser extension bringing TrueCursor's One-Euro pointer smoothing, 180ms Click-Freeze lock, 2.5x DOM Button Gravity Wells, and accessible reading/contrast aids directly to web pages on **Windows, macOS, and Linux**.

## Install Unpacked Extension (Chrome / Edge)
1. Open `chrome://extensions` (or `edge://extensions`).
2. Enable **Developer mode**.
3. Click **Load unpacked** and select this `chrome-extension/` folder.
4. Click the **TrueCursor Web Assist** puzzle icon in the toolbar.
5. *(Optional)* Launch the TrueCursor desktop app and click **Sync App** in the popup to pull your calibrated Medication State preset (`One-Euro cutoff/beta`, `Click-Freeze`, and `Gravity Wells`), or use the extension completely standalone offline.

## Controls
- **Esc**: Pause virtual pointer & gravity-well interception on the current tab.
- **Alt+Shift+S**: Toggle assist on/off on the current tab.
- **Restore**: Remove all injected styling and overlays cleanly.

## Run Automated Tests
```bash
npm --prefix chrome-extension test
```
