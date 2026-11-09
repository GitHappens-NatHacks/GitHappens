# AccessShift — Read, Steady, See

A standalone Chromium browser extension with user-controlled reading preferences, an on-page virtual pointer with One Euro smoothing, simulated tremor, and experimental color-vision filters. This is a fresh extension project, independent of the earlier Python application.

## Install — no Python, Node or build step

1. Right-click **AccessShift_Extension.zip → Extract All**. Do not open files from inside the ZIP preview.
2. Open the extracted **AccessShift_Extension** folder. You should see **manifest.json**, **popup.html**, and **demo.html** together.
3. Open your browser's extensions page:
   - Chrome: `chrome://extensions`
   - Edge: `edge://extensions`
   - Opera: `opera://extensions` (Chromium compatibility; not independently verified here).
4. Turn on **Developer mode**.
5. Choose **Load unpacked**, and select the folder containing **manifest.json**.
6. Open the extensions/puzzle menu, choose **AccessShift — Read, Steady, See**, and pin it if desired.
7. Open an ordinary webpage. Choose your settings and press **Apply to this page**.

After editing source files, return to the extensions page and choose Reload for AccessShift. Reload the webpage before applying the updated code. Remove the extension through the same extensions page when finished.

## Try the demo first

Click **Try demo ↗** in the extension. It opens a full page with the settings on the left and four exercises on the right.

Alternatively, double-click **demo.html** in the extracted folder to try it as an ordinary local webpage without installing the extension. The embedded controls apply only to the demo in this mode. This does not require an internet connection. Use Chrome or Edge if the system opens the HTML in a different application.

1. **Read:** turn on reading-friendly text. Try font choices, larger text, line/letter/word spacing, a warm/light/dark background, limited paragraph widths, and a mouse-following reading guide. Choose Apply to demo after making changes.
2. **See:** try Protan, Deutan or Tritan assistance. Compare the labeled shapes. Grayscale helps inspect whether something depends on color alone. Underlined links and outlined controls add non-color cues.
3. **SteadyHand comparison:** scroll to the motor exercise. Choose target size, simulated tremor amplitude and smoothing strength. Start a baseline trial, then a smoothed trial. Click all ten highlighted targets. The solid orange dot is active in baseline; the solid green dot is active in smoothed mode. The other dot is an outline. Complete a trial before exporting measured results.
4. **Webpage virtual pointer:** choose Steady, enable the virtual pointer, and Apply. Scroll to the ordinary form and try clicking a highlighted day button. The original Windows cursor remains visible; the green virtual dot shows the smoothed location. The benchmark canvas is excluded from page click assistance so it can run its own comparison consistently.
5. Use **Restore page** to undo the page adaptations. Restore preserves your chosen preferences for the next Apply.

**Changing a slider does not change the current page until you press Apply.** The benchmark has its own strength/amplitude controls, which lock during a trial. Applying extension preferences while a trial is running does not change its parameters. Resizing its canvas discards an incomplete trial.

## Reading preferences

The extension changes presentation rather than rewriting words. Font choices are Arial/sans serif, Verdana, the system font, and Georgia/serif. Text size ranges from 14–36 px. Line spacing, letter spacing and word spacing are independently adjustable.

These options are intended to let people with dyslexia or attention difficulties choose a more comfortable presentation. They are not a treatment, a diagnosis, or a guarantee of improved reading. There is no single font or setting that works for everyone. Disabling Reading-friendly text leaves page typography alone; the reading guide and reduced-motion option can be used separately.

The extension mainly styles paragraphs, lists and headings. It avoids changing form values or replacing page HTML. Complex layouts, icons, embedded content and unusual CSS may not adapt perfectly. Restore or reload if a page becomes awkward.

## Virtual-pointer smoothing

- This extension **does not move or smooth the Windows/system mouse cursor**.
- It filters page pointer coordinates into a separate green virtual dot. Stronger filtering reduces high-frequency jitter and adds movement delay.
- With **Click the highlighted button or link** enabled, the extension attempts to suppress the corresponding native mouse click and activate the highlighted virtual target once. A target can be selected directly or within a small 22 px proximity region. Assistance is bounded locally to avoid activating a target far behind a fast mouse movement.
- **Esc pauses** the virtual pointer. The floating toolbar lets you resume or restore. **Alt+Shift+S** toggles pause while the page has focus. These are page keyboard handlers, not global operating-system shortcuts.
- Text inputs, selects, editable areas, modified clicks, non-mouse pointers and the built-in benchmark keep native interaction. Dragging and custom widgets are outside this prototype's supported interaction scope. Filtering is page-level, not an adaptive hardware DPI change.
- Some sites use pointer-down handlers, protected user actions or custom input systems. Synthetic activation may not work, and earlier site handlers may run before the extension. Do not treat this as universal click interception. Pause or Restore for incompatible controls.
- Browser navigation, other tabs, browser toolbars and other applications are unaffected. Reapply after navigation.

**Simulated tremor is off by default.** It adds engineering test noise to the virtual coordinates, not to your physical cursor. Do not enable it for everyday assistance. The page toolbar explicitly labels DEMO tremor when enabled. The extension remembers preferences locally, so check this checkbox before applying saved settings to another page.

## Motor benchmark and honest results

The test uses the same fixed seed and noise function for both conditions. It combines several oscillations, interpolated pseudorandom motion and intermittent bursts. Starting each trial resets the filter and time origin. Actual hand trajectories and click timing still differ between trials; this is not a controlled clinical study or an exact replay of identical user motion.

Target sizes are **10, 20 or 30 px**. Both conditions use the selected tremor amplitude. Baseline hit testing uses the raw noisy point; smoothed hit testing uses its filtered point. Export includes the mode, seed, amplitude, strength, canvas size, target size, duration, hits, misses, accuracy and each click's coordinates/target. No results are fabricated or prefilled. Incomplete trials are discarded.

A simulation is useful for explaining filtering behavior; it is not evidence of benefit for Parkinson's disease, essential tremor or a particular person. Higher smoothing can make a task slower even if jitter is reduced. Compare accuracy and time together.

## Color-vision modes

**Protan, Deutan and Tritan assist** use approximate linear-RGB error redistribution. A color-vision simulation matrix estimates a difference from the original color; a simple redistribution matrix shifts that difference into other channels. Strength blends the adjustment from zero to full. The assistance rule is experimental and has not been clinically validated.

These are **assistance transforms, not simulations of a person's vision**, and not corrections that restore normal color vision. They affect the entire rendered page, including images and embedded controls. They cannot infer semantic meaning from a chart or supply missing labels. Display, visual condition, source colors and browser rendering all affect usefulness. You can reduce strength or choose Original colors.

**Grayscale** is explicitly a non-color-cue checking mode, not a colorblindness correction. The labeled demo shapes retain shape and text information in every mode. The non-color-cue toggle underlines ordinary links and outlines controls; it does not automatically label arbitrary charts.

The simulation coefficients used as a component of the experimental transform are from Machado, Oliveira & Fernandes (2009), *A Physiologically-based Model for Simulation of Color Vision Deficiency*. See the authors' supplementary page: https://www.inf.ufrgs.br/~oliveira/pubs_files/CVD_Simulation/CVD_Simulation.html . The redistribution rule here is separate prototype code, not a validated algorithm from that paper.

## Permissions, privacy and compatibility

- `activeTab`: temporary access to the page you choose through the extension action.
- `scripting`: inject the bundled local math and content scripts into that page.
- `storage`: save preferences locally in your browser.

There is no server, account, cloud model, telemetry, camera access, clipboard collection or blanket all-sites permission. Page text is not uploaded. The motor exercise exports only the results you choose to download. The extension popup explicitly applies preferences; no background site-wide adaptation happens automatically.

Browser settings pages, extension-store pages, extension pages other than the included demo, protected PDF viewers and inaccessible cross-origin frames are not supported. Shadow DOM content may not be covered. For file URLs, enable **Allow access to file URLs** in the extension's details if you want to apply it to local pages. The standalone demo can run without this extension permission because it includes its own scripts.

Reference documentation:

- Chrome content scripts: https://developer.chrome.com/docs/extensions/develop/concepts/content-scripts
- Chrome scripting/activeTab: https://developer.chrome.com/docs/extensions/reference/api/scripting
- W3C text spacing guidance: https://www.w3.org/WAI/WCAG22/Understanding/text-spacing.html
- Synthetic event limitations: https://developer.mozilla.org/en-US/docs/Web/API/Event/isTrusted

## Files

- `manifest.json` — load this folder as an unpacked Manifest V3 extension.
- `popup.html`, `popup.css`, `popup.js` — three sections and explicit Apply/Restore controls.
- `math.js` — One Euro filtering, a seeded tremor generator, color transforms and bounded settings.
- `content.js` — page styles, reading guide, color filters, virtual pointer, target selection, pause and cleanup.
- `demo.html`, `demo.css`, `demo.js` — real browser demo, fictional form and measured aiming trials.
- `tests/` — optional developer checks. Node is only needed to run tests, not to use the extension.

## Developer checks

From the `tests` directory:

```text
npm install
npm test
```

18 automated tests cover filter attenuation at several rates, intentional motion and gap handling, seeded noise, finite color matrices, preferences, DOM/source preservation, idempotent cleanup, pause/restore controls, synthetic-click recursion, popup injection, a completed baseline export, misses, incomplete-trial discard and embedded demo messaging.

JavaScript syntax and DOM logic were checked. Browser preview access was unavailable in the build environment, so this release has **not** been tested as an installed extension or with physical/trusted browser mouse input. Rendering, SVG color filters, browser-specific popup behavior and actual click redirection need a local browser check. This is a functional prototype, not a browser-store release or certified accessibility product.
