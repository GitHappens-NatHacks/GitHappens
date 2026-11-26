/**
 * ClearCursor Web Assist core math: One-Euro 2D smoothing, 180ms Click-Freeze,
 * and DOM Gravity Well solver. Shared between browser content scripts and Node tests.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  root.ClearCursorStabilizer = api;
  root.TrueCursorStabilizer = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const PRESETS = {
    mild: {
      label: "Mild Tremor",
      minCutoff: 1.0,
      beta: 0.01,
      clickFreezeMs: 140,
      gravityWells: true,
    },
    moderate: {
      label: "Moderate Tremor",
      minCutoff: 0.6,
      beta: 0.004,
      clickFreezeMs: 180,
      gravityWells: true,
    },
    high: {
      label: "High Tremor",
      minCutoff: 0.25,
      beta: 0.0015,
      clickFreezeMs: 240,
      gravityWells: true,
    },
  };

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function alpha(cutoff, dt) {
    const r = 2 * Math.PI * cutoff * dt;
    return r / (r + 1);
  }

  class OneEuroAxis {
    constructor(minCutoff = 0.6, beta = 0.004, dCutoff = 1.0) {
      this.minCutoff = minCutoff;
      this.beta = beta;
      this.dCutoff = dCutoff;
      this.prevT = null;
      this.prevRaw = 0;
      this.prevFiltered = 0;
      this.prevDx = 0;
    }

    reset() {
      this.prevT = null;
      this.prevRaw = 0;
      this.prevFiltered = 0;
      this.prevDx = 0;
    }

    filter(x, tSec) {
      if (this.prevT === null) {
        this.prevT = tSec;
        this.prevRaw = x;
        this.prevFiltered = x;
        this.prevDx = 0;
        return x;
      }

      const rawDt = tSec - this.prevT;
      if (rawDt <= 0) {
        return this.prevFiltered;
      }
      // Guard against tab suspension or multi-monitor display handoff gaps
      if (rawDt > 0.5) {
        this.prevT = tSec;
        this.prevRaw = x;
        this.prevFiltered = x;
        this.prevDx = 0;
        return x;
      }
      const dt = Math.min(rawDt, 0.1);
      const dx = (x - this.prevRaw) / dt;
      const edx = this.prevDx + alpha(this.dCutoff, dt) * (dx - this.prevDx);
      const cutoff = this.minCutoff + this.beta * Math.abs(edx);
      const filtered = this.prevFiltered + alpha(cutoff, dt) * (x - this.prevFiltered);

      this.prevT = tSec;
      this.prevRaw = x;
      this.prevFiltered = filtered;
      this.prevDx = edx;
      return filtered;
    }
  }

  class OneEuro2D {
    constructor(minCutoff = 0.6, beta = 0.004) {
      this.fx = new OneEuroAxis(minCutoff, beta);
      this.fy = new OneEuroAxis(minCutoff, beta);
    }

    configure(minCutoff, beta) {
      this.fx.minCutoff = clamp(Number(minCutoff) || 0.6, 0.05, 5.0);
      this.fy.minCutoff = this.fx.minCutoff;
      this.fx.beta = clamp(Number(beta) || 0.0, 0.0, 0.2);
      this.fy.beta = this.fx.beta;
    }

    reset() {
      this.fx.reset();
      this.fy.reset();
    }

    update(x, y, tSec) {
      return {
        x: this.fx.filter(x, tSec),
        y: this.fy.filter(y, tSec),
      };
    }
  }

  class ClickFreezeState {
    constructor(clickFreezeMs = 180, dragReleasePx = 25) {
      this.clickFreezeMs = clamp(Number(clickFreezeMs) || 180, 0, 500);
      this.dragReleasePx = clamp(Number(dragReleasePx) || 25, 8, 80);
      this.anchor = null;
      this.origin = null;
      this.pressMs = 0;
      this.dragging = false;
    }

    down(anchorPoint, rawPoint, nowMs) {
      this.anchor = { x: anchorPoint.x, y: anchorPoint.y };
      this.origin = { x: rawPoint.x, y: rawPoint.y };
      this.pressMs = nowMs;
      this.dragging = false;
    }

    move(rawPoint, nowMs) {
      if (!this.anchor || !this.origin || this.dragging) {
        return rawPoint;
      }
      const elapsed = nowMs - this.pressMs;
      const dist = Math.hypot(rawPoint.x - this.origin.x, rawPoint.y - this.origin.y);
      if (elapsed >= this.clickFreezeMs || dist >= this.dragReleasePx) {
        if (dist >= this.dragReleasePx) {
          this.dragging = true;
          return rawPoint;
        }
      }
      return this.anchor;
    }

    up() {
      const point = this.dragging ? null : this.anchor;
      this.anchor = null;
      this.origin = null;
      this.dragging = false;
      return point;
    }

    get frozen() {
      return Boolean(this.anchor && !this.dragging);
    }
  }

  /**
   * Expand candidate DOM rectangles by `expansion` and choose the nearest well.
   * Each candidate has { id, left, top, width, height }.
   */
  function findGravityTarget(px, py, candidates, expansion = 2.5) {
    if (!Array.isArray(candidates) || candidates.length === 0) {
      return null;
    }
    let best = null;
    let bestNorm = Infinity;
    for (const item of candidates) {
      if (!item || item.width <= 1 || item.height <= 1) {
        continue;
      }
      const cx = item.left + item.width * 0.5;
      const cy = item.top + item.height * 0.5;
      const halfW = Math.max(12, item.width * 0.5 * expansion);
      const halfH = Math.max(12, item.height * 0.5 * expansion);
      if (Math.abs(px - cx) <= halfW && Math.abs(py - cy) <= halfH) {
        const norm = Math.hypot((px - cx) / halfW, (py - cy) / halfH);
        if (norm < bestNorm) {
          bestNorm = norm;
          best = { ...item, cx, cy, norm };
        }
      }
    }
    return best;
  }

  function sanitizeSettings(raw) {
    const src = raw && typeof raw === "object" ? raw : {};
    const presetKey = src.preset in PRESETS ? src.preset : "moderate";
    const base = PRESETS[presetKey];
    return {
      preset: presetKey,
      pointerEnabled: src.pointerEnabled !== false,
      minCutoff: clamp(Number(src.minCutoff ?? base.minCutoff), 0.05, 5.0),
      beta: clamp(Number(src.beta ?? base.beta), 0.0, 0.2),
      clickFreezeMs: clamp(Math.round(Number(src.clickFreezeMs ?? base.clickFreezeMs)), 0, 500),
      gravityWells: src.gravityWells !== undefined ? Boolean(src.gravityWells) : base.gravityWells,
      highContrastCues: Boolean(src.highContrastCues),
      largeReadableText: Boolean(src.largeReadableText),
    };
  }

  return {
    PRESETS,
    clamp,
    OneEuroAxis,
    OneEuro2D,
    ClickFreezeState,
    findGravityTarget,
    sanitizeSettings,
  };
});
