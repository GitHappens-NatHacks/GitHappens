import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const S = require("../lib/stabilizer.js");

test("OneEuro2D dampens 5.5Hz tremor oscillation and recovers cleanly from frame gaps", () => {
  const filter = new S.OneEuro2D(0.55, 0.003);
  const rawXs = [];
  const smoothXs = [];
  for (let i = 0; i < 60; i++) {
    const t = i / 60;
    const raw = 400 + 22 * Math.sin(2 * Math.PI * 5.5 * t);
    const out = filter.update(raw, 300, t);
    if (i >= 15) {
      rawXs.push(raw - 400);
      smoothXs.push(out.x - 400);
    }
  }
  const rawRms = Math.sqrt(rawXs.reduce((a, b) => a + b * b, 0) / rawXs.length);
  const smoothRms = Math.sqrt(smoothXs.reduce((a, b) => a + b * b, 0) / smoothXs.length);
  assert.ok(smoothRms < rawRms * 0.65, `expected damping: ${smoothRms} < ${rawRms * 0.65}`);

  // External monitor / tab sleep gap (>0.5s) resets cleanly without NaN or spike
  const jumped = filter.update(900, 500, 3.0);
  assert.deepEqual(jumped, { x: 900, y: 500 });
});

test("ClickFreezeState holds anchor for <25px tremor slip and unlocks on >=25px drag", () => {
  const freeze = new S.ClickFreezeState(180, 25);
  freeze.down({ x: 200, y: 150 }, { x: 202, y: 151 }, 1000);
  assert.equal(freeze.frozen, true);

  // Small slip (<25px) stays frozen even past clickFreezeMs unless drag distance exceeded
  const locked = freeze.move({ x: 214, y: 158 }, 1090);
  assert.deepEqual(locked, { x: 200, y: 150 });
  assert.equal(freeze.frozen, true);

  // Intentional drag (>=25px) breaks freeze immediately
  const unlocked = freeze.move({ x: 235, y: 151 }, 1120);
  assert.deepEqual(unlocked, { x: 235, y: 151 });
  assert.equal(freeze.frozen, false);
  assert.equal(freeze.up(), null);
});

test("findGravityTarget expands hitboxes 2.5x and picks nearest button", () => {
  const buttons = [
    { id: "cancel", left: 100, top: 100, width: 60, height: 32 },
    { id: "confirm", left: 260, top: 100, width: 80, height: 36 },
  ];
  // Cursor sits 28px right of confirm's left edge and outside its raw height (top=72), inside 2.5x well
  const chosen = S.findGravityTarget(295, 80, buttons, 2.5);
  assert.ok(chosen);
  assert.equal(chosen.id, "confirm");

  // Far away misses all wells
  assert.equal(S.findGravityTarget(700, 600, buttons, 2.5), null);
});

test("sanitizeSettings clamps unsafe tuning values", () => {
  const cleaned = S.sanitizeSettings({
    preset: "unknown",
    minCutoff: -5,
    beta: 2.5,
    clickFreezeMs: 2000,
    gravityWells: false,
  });
  assert.equal(cleaned.preset, "moderate");
  assert.equal(cleaned.minCutoff, 0.05);
  assert.equal(cleaned.beta, 0.2);
  assert.equal(cleaned.clickFreezeMs, 500);
  assert.equal(cleaned.gravityWells, false);
});
