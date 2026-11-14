(() => {
  if (window.__trueCursorWebAssist) {
    return;
  }
  const S = globalThis.TrueCursorStabilizer;
  if (!S) {
    throw new Error("TrueCursorStabilizer must be loaded before content.js");
  }

  const HOST_ID = "truecursor-web-assist-host";
  const STYLE_ID = "truecursor-web-assist-style";
  const INTERACTIVE_SEL =
    'button, a[href], input[type="button"], input[type="submit"], input[type="reset"], [role="button"], [role="link"], label[for]';
  const EDITABLE_SEL =
    'textarea, select, input:not([type="button"]):not([type="submit"]):not([type="reset"]), [contenteditable]:not([contenteditable="false"]), [role="textbox"]';

  let prefs = null;
  let filter = null;
  let freeze = null;
  let paused = false;
  let lastPointer = null;
  let smoothPos = null;
  let activeWell = null;
  let domCache = [];
  let cacheAt = -Infinity;
  let probeAt = -Infinity;
  let rafId = 0;
  let suppressedUntil = 0;

  let host = null;
  let shadow = null;
  let dotEl = null;
  let ringEl = null;
  let bannerText = null;
  let pauseBtn = null;
  let styleEl = null;

  function isOwnEvent(e) {
    return host && typeof e.composedPath === "function" && e.composedPath().includes(host);
  }

  function isEligible(el) {
    if (!(el instanceof Element) || !el.isConnected) {
      return false;
    }
    if (el.disabled || el.getAttribute("aria-disabled") === "true") {
      return false;
    }
    if (el.closest('[hidden],[inert],[aria-hidden="true"],[aria-disabled="true"]')) {
      return false;
    }
    const r = el.getBoundingClientRect();
    if (r.width <= 1 || r.height <= 1) {
      return false;
    }
    if (r.right <= 0 || r.bottom <= 0 || r.left >= innerWidth || r.top >= innerHeight) {
      return false;
    }
    const css = getComputedStyle(el);
    return css.visibility !== "hidden" && css.display !== "none" && css.pointerEvents !== "none";
  }

  function collectCandidates(now) {
    if (now - cacheAt > 250) {
      domCache = Array.from(document.querySelectorAll(INTERACTIVE_SEL))
        .slice(0, 600)
        .filter(isEligible)
        .map((el, idx) => {
          const r = el.getBoundingClientRect();
          return {
            id: idx,
            el,
            left: r.left,
            top: r.top,
            width: r.width,
            height: r.height,
          };
        });
      cacheAt = now;
    }
    return domCache;
  }

  function ensureOverlay() {
    if (host) {
      return;
    }
    host = document.createElement("div");
    host.id = HOST_ID;
    host.style.cssText =
      "all:initial!important;position:fixed!important;inset:0!important;pointer-events:none!important;z-index:2147483647!important;";
    shadow = host.attachShadow({ mode: "open" });
    shadow.innerHTML = `
      <style>
        :host { all: initial; }
        * { box-sizing: border-box; }
        .tc-dot {
          position: fixed;
          width: 18px;
          height: 18px;
          border-radius: 50%;
          border: 3px solid #ffffff;
          background: #0f766e;
          box-shadow: 0 0 0 2px #0f172a;
          transform: translate(-50%, -50%);
          pointer-events: none;
          display: none;
        }
        .tc-well {
          position: fixed;
          border: 3px solid #0f766e;
          outline: 2px solid #ffffff;
          border-radius: 6px;
          background: rgba(15, 118, 110, 0.10);
          pointer-events: none;
          display: none;
        }
        .tc-bar {
          position: fixed;
          bottom: 16px;
          right: 16px;
          max-width: 340px;
          background: #0f172a;
          color: #ffffff;
          border: 2px solid #ffffff;
          border-radius: 8px;
          padding: 12px;
          pointer-events: auto;
          font: 13px/1.4 system-ui, -apple-system, sans-serif;
          box-shadow: 0 8px 24px rgba(15, 23, 42, 0.25);
        }
        .tc-bar p { margin: 0 0 10px; font-weight: 600; }
        .tc-bar-actions { display: flex; gap: 8px; flex-wrap: wrap; }
        .tc-bar button {
          font: 700 13px system-ui, -apple-system, sans-serif;
          min-height: 36px;
          padding: 6px 12px;
          border-radius: 6px;
          border: 2px solid #ffffff;
          background: #ffffff;
          color: #0f172a;
          cursor: pointer;
        }
        .tc-bar button.secondary {
          background: transparent;
          color: #ffffff;
        }
      </style>
      <div class="tc-well"></div>
      <div class="tc-dot"></div>
      <div class="tc-bar" role="region" aria-label="TrueCursor Web Assist">
        <p></p>
        <div class="tc-bar-actions">
          <button type="button" class="tc-pause">Pause Assist</button>
          <button type="button" class="tc-restore secondary">Restore Page</button>
        </div>
      </div>
    `;
    dotEl = shadow.querySelector(".tc-dot");
    ringEl = shadow.querySelector(".tc-well");
    bannerText = shadow.querySelector(".tc-bar p");
    pauseBtn = shadow.querySelector(".tc-pause");
    pauseBtn.addEventListener("click", () => setPaused(!paused));
    shadow.querySelector(".tc-restore").addEventListener("click", restore);
    document.documentElement.appendChild(host);
  }

  function updateBanner() {
    if (!bannerText || !pauseBtn || !prefs) {
      return;
    }
    if (!prefs.pointerEnabled) {
      bannerText.textContent = "TrueCursor: Page visual aids active.";
      pauseBtn.style.display = "none";
      return;
    }
    pauseBtn.style.display = "inline-block";
    pauseBtn.textContent = paused ? "Resume Assist" : "Pause Assist";
    bannerText.textContent = paused
      ? "TrueCursor paused. Press Esc or Resume to reactivate."
      : `TrueCursor active (${S.PRESETS[prefs.preset].label}). Esc pauses anytime.`;
  }

  function setPaused(next) {
    paused = Boolean(next);
    freeze?.up();
    filter?.reset();
    activeWell = null;
    if (paused && dotEl && ringEl) {
      dotEl.style.display = "none";
      ringEl.style.display = "none";
    }
    updateBanner();
  }

  function onPointerMove(e) {
    if (!prefs || isOwnEvent(e)) {
      return;
    }
    if (e.pointerType && e.pointerType !== "mouse") {
      return;
    }
    lastPointer = { x: e.clientX, y: e.clientY };
  }

  function onPointerDown(e) {
    if (!prefs?.pointerEnabled || paused || isOwnEvent(e)) {
      return;
    }
    if (!e.isTrusted || e.button !== 0 || e.ctrlKey || e.metaKey || e.altKey || e.shiftKey) {
      return;
    }
    if (e.target instanceof Element && e.target.closest(EDITABLE_SEL)) {
      return;
    }
    const anchor = smoothPos || { x: e.clientX, y: e.clientY };
    freeze.down(anchor, { x: e.clientX, y: e.clientY }, performance.now());

    if (prefs.gravityWells && activeWell?.el && isEligible(activeWell.el)) {
      suppressedUntil = performance.now() + prefs.clickFreezeMs + 250;
      e.preventDefault();
      e.stopImmediatePropagation();
    }
  }

  function onPointerUp(e) {
    if (!freeze || !freeze.anchor || e.button !== 0) {
      return;
    }
    const chosenAnchor = freeze.up();
    const targetWell = activeWell;
    if (chosenAnchor && prefs?.gravityWells && targetWell?.el && isEligible(targetWell.el)) {
      suppressedUntil = performance.now() + 300;
      e.preventDefault();
      e.stopImmediatePropagation();
      targetWell.el.click();
    }
  }

  function suppressNativeClick(e) {
    if (e.isTrusted && !isOwnEvent(e) && performance.now() < suppressedUntil && e.button === 0) {
      e.preventDefault();
      e.stopImmediatePropagation();
    }
  }

  function onKeyDown(e) {
    if (!prefs || e.repeat) {
      return;
    }
    if (e.key === "Escape") {
      setPaused(true);
    } else if (e.code === "KeyS" && e.altKey && e.shiftKey) {
      e.preventDefault();
      setPaused(!paused);
    }
  }

  function invalidateLayout() {
    cacheAt = -Infinity;
    activeWell = null;
  }

  function renderFrame(now) {
    if (!prefs) {
      return;
    }
    if (prefs.pointerEnabled && !paused && lastPointer && !document.hidden) {
      let pt = lastPointer;
      if (freeze.frozen) {
        pt = freeze.move(lastPointer, now);
      }
      smoothPos = filter.update(pt.x, pt.y, now / 1000);
      let drawX = smoothPos.x;
      let drawY = smoothPos.y;

      if (prefs.gravityWells && now - probeAt > 60) {
        const cand = collectCandidates(now);
        activeWell = S.findGravityTarget(drawX, drawY, cand, 2.5);
        probeAt = now;
      }
      if (activeWell && prefs.gravityWells) {
        drawX = drawX + (activeWell.cx - drawX) * 0.35;
        drawY = drawY + (activeWell.cy - drawY) * 0.35;
        Object.assign(ringEl.style, {
          display: "block",
          left: `${activeWell.left}px`,
          top: `${activeWell.top}px`,
          width: `${activeWell.width}px`,
          height: `${activeWell.height}px`,
        });
      } else {
        ringEl.style.display = "none";
      }

      dotEl.style.display = "block";
      dotEl.style.left = `${drawX}px`;
      dotEl.style.top = `${drawY}px`;
    } else if (dotEl && ringEl) {
      dotEl.style.display = "none";
      ringEl.style.display = "none";
    }
    rafId = requestAnimationFrame(renderFrame);
  }

  const LISTENERS = [
    ["pointermove", onPointerMove, true],
    ["pointerdown", onPointerDown, true],
    ["pointerup", onPointerUp, true],
    ["click", suppressNativeClick, true],
    ["keydown", onKeyDown, true],
    ["scroll", invalidateLayout, true],
    ["resize", invalidateLayout, true],
  ];

  function apply(rawSettings) {
    restore();
    prefs = S.sanitizeSettings(rawSettings);
    filter = new S.OneEuro2D(prefs.minCutoff, prefs.beta);
    freeze = new S.ClickFreezeState(prefs.clickFreezeMs, 25);
    paused = false;
    suppressedUntil = 0;
    ensureOverlay();

    styleEl = document.createElement("style");
    styleEl.id = STYLE_ID;
    let css = "";
    if (prefs.highContrastCues) {
      css += `
        button, a[href], input, select, textarea, [role="button"] {
          outline: 2px solid #0f766e !important;
          outline-offset: 2px !important;
        }
      `;
    }
    if (prefs.largeReadableText) {
      css += `
        :where(p, li, blockquote, dd, dt) {
          font-size: max(18px, 1.15em) !important;
          line-height: 1.65 !important;
          letter-spacing: 0.02em !important;
        }
      `;
    }
    styleEl.textContent = css;
    (document.head || document.documentElement).appendChild(styleEl);

    for (const [evt, fn, cap] of LISTENERS) {
      window.addEventListener(evt, fn, { capture: cap, passive: false });
    }
    updateBanner();
    rafId = requestAnimationFrame(renderFrame);
    return { active: true, preset: prefs.preset };
  }

  function restore() {
    cancelAnimationFrame(rafId);
    for (const [evt, fn, cap] of LISTENERS) {
      window.removeEventListener(evt, fn, cap);
    }
    host?.remove();
    styleEl?.remove();
    host = shadow = dotEl = ringEl = bannerText = pauseBtn = styleEl = null;
    prefs = filter = freeze = lastPointer = smoothPos = activeWell = null;
    domCache = [];
    return { active: false };
  }

  window.__trueCursorWebAssist = Object.freeze({
    apply,
    restore,
    status: () => ({ active: Boolean(prefs), paused }),
  });
})();
