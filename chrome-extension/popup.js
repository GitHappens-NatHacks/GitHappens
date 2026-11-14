(() => {
  const S = globalThis.TrueCursorStabilizer;
  const $ = (id) => document.getElementById(id);

  let selectedPreset = "moderate";

  function setStatus(msg) {
    $("status").textContent = msg;
  }

  function renderPresetButtons() {
    document.querySelectorAll("[data-preset]").forEach((btn) => {
      const active = btn.dataset.preset === selectedPreset;
      btn.classList.toggle("selected", active);
      btn.setAttribute("aria-pressed", String(active));
    });
  }

  function collectSettings() {
    const presetDefaults = S.PRESETS[selectedPreset] || S.PRESETS.moderate;
    return S.sanitizeSettings({
      preset: selectedPreset,
      minCutoff: presetDefaults.minCutoff,
      beta: presetDefaults.beta,
      pointerEnabled: $("pointerEnabled").checked,
      gravityWells: $("gravityWells").checked,
      highContrastCues: $("highContrastCues").checked,
      largeReadableText: $("largeReadableText").checked,
      clickFreezeMs: Number($("clickFreezeMs").value),
    });
  }

  function applySettingsToForm(raw) {
    const s = S.sanitizeSettings(raw);
    selectedPreset = s.preset;
    $("pointerEnabled").checked = s.pointerEnabled;
    $("gravityWells").checked = s.gravityWells;
    $("highContrastCues").checked = s.highContrastCues;
    $("largeReadableText").checked = s.largeReadableText;
    $("clickFreezeMs").value = String(s.clickFreezeMs);
    $("clickFreezeLabel").textContent = `${s.clickFreezeMs} ms`;
    renderPresetButtons();
  }

  async function saveLocal(settings) {
    if (globalThis.chrome?.storage?.local) {
      await chrome.storage.local.set({ truecursorPrefs: settings });
    }
  }

  async function loadLocal() {
    try {
      if (globalThis.chrome?.storage?.local) {
        const res = await chrome.storage.local.get("truecursorPrefs");
        applySettingsToForm(res.truecursorPrefs);
        return;
      }
    } catch {
      // fall through to defaults
    }
    applySettingsToForm({});
  }

  async function runOnActiveTab(actionName) {
    if (!globalThis.chrome?.tabs || !globalThis.chrome?.scripting) {
      setStatus("Open this popup inside Chrome/Edge to apply on a live tab.");
      return;
    }
    const settings = collectSettings();
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab?.id) {
        setStatus("No active browser tab selected.");
        return;
      }
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ["lib/stabilizer.js", "content.js"],
      });
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: (action, payload) => window.__trueCursorWebAssist[action](payload),
        args: [actionName, settings],
      });
      if (actionName === "apply") {
        await saveLocal(settings);
        setStatus("Applied to active tab. Press Esc anytime to pause.");
      } else {
        setStatus("Original page restored cleanly.");
      }
    } catch (err) {
      setStatus(`Cannot modify this tab (${err.message || "restricted browser page"}).`);
    }
  }

  async function syncFromDesktopBackend() {
    setStatus("Checking TrueCursor desktop backend (127.0.0.1:8000)...");
    try {
      const resp = await fetch("http://127.0.0.1:8000/api/settings", { method: "GET" });
      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}`);
      }
      const desktop = await resp.json();
      const mappedPreset =
        desktop.profile === "mild" || desktop.profile === "high" ? desktop.profile : "moderate";
      const next = S.sanitizeSettings({
        ...collectSettings(),
        preset: mappedPreset,
        minCutoff: desktop.one_euro_min_cutoff,
        beta: desktop.one_euro_beta,
        clickFreezeMs: desktop.click_freeze_ms,
        gravityWells: Boolean(desktop.gravity_wells),
      });
      applySettingsToForm(next);
      await saveLocal(next);
      setStatus(`Synced "${S.PRESETS[next.preset].label}" preset from TrueCursor desktop.`);
    } catch {
      setStatus("Desktop app offline; using local extension preferences.");
    }
  }

  document.querySelectorAll("[data-preset]").forEach((btn) => {
    btn.addEventListener("click", () => {
      selectedPreset = btn.dataset.preset;
      const p = S.PRESETS[selectedPreset];
      if (p) {
        $("clickFreezeMs").value = String(p.clickFreezeMs);
        $("clickFreezeLabel").textContent = `${p.clickFreezeMs} ms`;
      }
      renderPresetButtons();
    });
  });

  $("clickFreezeMs").addEventListener("input", () => {
    $("clickFreezeLabel").textContent = `${$("clickFreezeMs").value} ms`;
  });
  $("apply-btn").addEventListener("click", () => void runOnActiveTab("apply"));
  $("restore-btn").addEventListener("click", () => void runOnActiveTab("restore"));
  $("sync-btn").addEventListener("click", () => void syncFromDesktopBackend());

  void loadLocal();
})();
