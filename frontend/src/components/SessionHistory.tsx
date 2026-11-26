import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";
import { FileDown, FileSpreadsheet, Info, Pill, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { createClinicalEvent, deleteClinicalEvent, fetchSessions } from "../api/client";
import type { ClinicalEventType, SessionsResponse } from "../types/telemetry";

function formatStabilityBand(score: number): string {
  if (score >= 85) {
    return "Optimal Steadiness (85-100)";
  }
  if (score >= 65) {
    return "Moderate Tremor Burden (65-84)";
  }
  return "Elevated Tremor Burden (<65)";
}

function formatFrequencyClinicalNote(hz: number | null): string {
  if (hz === null) {
    return "No sustained 4-12 Hz oscillation detected";
  }
  if (hz >= 4.0 && hz < 6.0) {
    return `${hz.toFixed(2)} Hz (4-6 Hz resting tremor band)`;
  }
  if (hz >= 6.0 && hz <= 12.0) {
    return `${hz.toFixed(2)} Hz (6-12 Hz action / postural band)`;
  }
  return `${hz.toFixed(2)} Hz (Outside 4-12 Hz primary band)`;
}

const DATE_WINDOWS = [
  { days: 7, label: "7 Days" },
  { days: 14, label: "14 Days" },
  { days: 30, label: "30 Days" },
  { days: 90, label: "90 Days" },
];

export function SessionHistory() {
  const [days, setDays] = useState<number>(14);
  const [includeSimulated, setIncludeSimulated] = useState<boolean>(false);
  const [data, setData] = useState<SessionsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Clinical Event Diary state
  const [eventType, setEventType] = useState<ClinicalEventType>("medication");
  const [eventLabel, setEventLabel] = useState<string>("");
  const [eventDosage, setEventDosage] = useState<string>("");
  const [eventSeverity, setEventSeverity] = useState<string>("");
  const [eventNotes, setEventNotes] = useState<string>("");
  const [savingEvent, setSavingEvent] = useState<boolean>(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchSessions(days, 50, includeSimulated);
      setData(res);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load SQLite session history."
      );
    } finally {
      setLoading(false);
    }
  }, [days, includeSimulated]);

  useEffect(() => {
    void load();
  }, [load]);

  const trends = data?.daily_trends ?? [];
  const sessions = data?.sessions ?? [];
  const hourly = data?.hourly_profile ?? [];
  const events = data?.clinical_events ?? [];
  const calibrations = data?.calibration_profiles ?? [];
  const functional = data?.functional_summary;
  const simulatedCount = data?.simulated_sample_count ?? 0;

  const totalSamples = sessions.reduce((acc, s) => acc + s.sample_count, 0);
  const meanStability =
    sessions.length > 0
      ? sessions.reduce((acc, s) => acc + s.avg_stability_score, 0) / sessions.length
      : 0;
  const meanTremorIdx =
    sessions.length > 0
      ? sessions.reduce((acc, s) => acc + s.avg_tremor_index, 0) / sessions.length
      : 0;
  const meanRestingPct = functional?.avg_resting_band_pct ?? 0;
  const meanActionPct = functional?.avg_action_band_pct ?? 0;
  const meanRmsMm = functional?.avg_rms_amplitude_mm ?? 0;
  const hzSessions = sessions.filter((s) => s.avg_tremor_hz !== null);
  const meanHz =
    hzSessions.length > 0
      ? hzSessions.reduce((acc, s) => acc + (s.avg_tremor_hz ?? 0), 0) / hzSessions.length
      : null;

  const handleQuickEvent = async (
    type: ClinicalEventType,
    label: string,
    severity?: number
  ) => {
    setSavingEvent(true);
    try {
      await createClinicalEvent({
        event_type: type,
        label,
        severity: severity ?? null,
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save diary entry.");
    } finally {
      setSavingEvent(false);
    }
  };

  const handleSubmitEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!eventLabel.trim()) {
      return;
    }
    setSavingEvent(true);
    try {
      await createClinicalEvent({
        event_type: eventType,
        label: eventLabel.trim(),
        dosage: eventDosage.trim(),
        severity: eventSeverity ? Number(eventSeverity) : null,
        notes: eventNotes.trim(),
      });
      setEventLabel("");
      setEventDosage("");
      setEventSeverity("");
      setEventNotes("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save diary entry.");
    } finally {
      setSavingEvent(false);
    }
  };

  const handleDeleteEvent = async (eventId: number) => {
    try {
      await deleteClinicalEvent(eventId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete diary entry.");
    }
  };

  const exportClinicianPdf = () => {
    const doc = new jsPDF({ orientation: "portrait", unit: "pt", format: "letter" });
    const nowLabel = new Date().toLocaleString();

    const getNextY = (fallback: number, minSpaceNeeded = 96): number => {
      const current = (doc as unknown as { lastAutoTable?: { finalY: number } }).lastAutoTable?.finalY ?? fallback;
      if (current + minSpaceNeeded > 740) {
        doc.addPage();
        return 48;
      }
      return current + 24;
    };

    doc.setFontSize(18);
    doc.setTextColor(15, 45, 89);
    doc.text("ClearCursor Clinician Motor Telemetry Report", 40, 46);

    doc.setFontSize(10);
    doc.setTextColor(66, 82, 110);
    doc.text(
      `Generated: ${nowLabel}   |   Window: Last ${days} Days   |   Source: ${includeSimulated ? "Includes Simulated Demos" : "Real Usage Only"}`,
      40,
      64
    );
    doc.setFontSize(8.5);
    doc.text(
      "Assistive Wellness Telemetry Disclaimer: Metrics reflect cursor displacement spectra and click-protection counts to support clinical discussion; not a standalone medical diagnostic device.",
      40,
      78,
      { maxWidth: 532 }
    );

    // Executive Summary Table
    autoTable(doc, {
      startY: 96,
      head: [["Clinical Summary Metric", "Observed Value", "Interpretation"]],
      body: [
        [
          "Recorded Motor Sessions",
          `${sessions.length} sessions (${totalSamples} FFT windows)`,
          "Each window summarizes 2.5-4s of active pointer displacement spectral density.",
        ],
        [
          "Overall Mean Stability Score",
          `${meanStability.toFixed(1)} / 100`,
          formatStabilityBand(meanStability),
        ],
        [
          "Mean RMS Tremor Amplitude",
          `${meanRmsMm.toFixed(2)} mm`,
          "4-12 Hz bandpassed RMS displacement calibrated by active display DPI.",
        ],
        [
          "Multi-Band Tremor Power (4-12 Hz)",
          `${meanTremorIdx.toFixed(1)}% total (4-6 Hz: ${meanRestingPct.toFixed(1)}% | 6-12 Hz: ${meanActionPct.toFixed(1)}%)`,
          "Separates lower-frequency resting band (4-6 Hz) from action/essential tremor band (6-12 Hz).",
        ],
        [
          "Mean Dominant Tremor Frequency",
          meanHz !== null ? `${meanHz.toFixed(2)} Hz` : "None detected",
          formatFrequencyClinicalNote(meanHz),
        ],
        [
          "Everyday Functional Protections",
          `${functional?.total_click_rescues ?? 0} slip-clicks rescued, ${functional?.total_drags_prevented ?? 0} drags blocked, ${functional?.total_bounces_blocked ?? 0} bounces prevented`,
          "Objective counts of involuntary tremor actions intercepted before hitting OS controls.",
        ],
      ],
      headStyles: { fillColor: [15, 45, 89], textColor: [255, 255, 255] },
      styles: { fontSize: 8.5, cellPadding: 5 },
    });

    // Embedded Vector Charts (when running with full jsPDF canvas vector primitives)
    const rawDoc = doc as unknown as {
      rect?: (x: number, y: number, w: number, h: number, style?: string) => void;
      line?: (x1: number, y1: number, x2: number, y2: number) => void;
      setDrawColor?: (r: number, g: number, b: number) => void;
      setFillColor?: (r: number, g: number, b: number) => void;
      setLineWidth?: (w: number) => void;
    };
    const hasVectorApi =
      typeof rawDoc.rect === "function" &&
      typeof rawDoc.line === "function" &&
      typeof rawDoc.setDrawColor === "function" &&
      typeof rawDoc.setFillColor === "function";

    let cursorY = getNextY(290, 150);
    if (hasVectorApi && (trends.length > 0 || hourly.length > 0)) {
      doc.setFontSize(12);
      doc.setTextColor(15, 45, 89);
      doc.text("Visual Longitudinal & Diurnal Telemetry Charts", 40, cursorY);

      const chartTop = cursorY + 10;
      const chartH = 92;
      const leftChartX = 40;
      const chartW = 250;
      const rightChartX = 322;

      // Left Chart: Daily Stability Score (0-100)
      rawDoc.setDrawColor!(203, 213, 225);
      rawDoc.setFillColor!(248, 250, 252);
      rawDoc.rect!(leftChartX, chartTop, chartW, chartH, "FD");
      doc.setFontSize(8.5);
      doc.setTextColor(15, 45, 89);
      doc.text("Daily Stability Score (0-100)", leftChartX + 8, chartTop + 13);

      if (trends.length >= 1) {
        const plotX = leftChartX + 14;
        const plotY = chartTop + 22;
        const plotW = chartW - 28;
        const plotH = chartH - 34;
        rawDoc.setDrawColor!(29, 78, 216);
        rawDoc.setLineWidth?.(1.6);
        const pts = trends.map((t, idx) => {
          const px = trends.length === 1 ? plotX + plotW / 2 : plotX + (idx / (trends.length - 1)) * plotW;
          const py = plotY + plotH - (Math.max(0, Math.min(100, t.avg_stability_score)) / 100) * plotH;
          return [px, py] as const;
        });
        for (let i = 1; i < pts.length; i += 1) {
          rawDoc.line!(pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1]);
        }
        rawDoc.setFillColor!(29, 78, 216);
        for (const [px, py] of pts) {
          rawDoc.rect!(px - 2, py - 2, 4, 4, "F");
        }
      }

      // Right Chart: Time-of-Day Diurnal Tremor Index (%)
      rawDoc.setDrawColor!(203, 213, 225);
      rawDoc.setFillColor!(248, 250, 252);
      rawDoc.rect!(rightChartX, chartTop, chartW, chartH, "FD");
      doc.setFontSize(8.5);
      doc.setTextColor(159, 18, 57);
      doc.text("Time-of-Day 4-12 Hz Tremor Power (%)", rightChartX + 8, chartTop + 13);

      if (hourly.length >= 1) {
        const plotX = rightChartX + 12;
        const plotY = chartTop + 22;
        const plotW = chartW - 24;
        const plotH = chartH - 34;
        const barW = Math.max(4, Math.min(14, plotW / 24 - 1));
        rawDoc.setFillColor!(159, 18, 57);
        for (const h of hourly) {
          const bx = plotX + (h.hour / 23) * (plotW - barW);
          const bh = (Math.max(0, Math.min(100, h.avg_tremor_index)) / 100) * plotH;
          rawDoc.rect!(bx, plotY + plotH - bh, barW, bh, "F");
        }
      }
      cursorY = chartTop + chartH + 24;
    }

    // How to Read This Data Guide
    if (cursorY + 130 > 740) {
      doc.addPage();
      cursorY = 48;
    }
    doc.setFontSize(13);
    doc.setTextColor(15, 45, 89);
    doc.text("How to Read This Clinical Motor Report", 40, cursorY);

    autoTable(doc, {
      startY: cursorY + 8,
      head: [["Column / Term", "Clinical Meaning & Reference Range"]],
      body: [
        [
          "Cursor Stability Score (0-100)",
          "Composite index combining 4-12 Hz tremor burden, RMS displacement, and suppression ratio. 85-100 indicates steady control; <65 flags elevated tremor activity.",
        ],
        [
          "4-6 Hz Resting vs 6-12 Hz Action (%)",
          "Share of 0.5-15 Hz pointer spectral energy in the classic resting tremor band (4-6 Hz) vs. postural/kinetic essential tremor band (6-12 Hz).",
        ],
        [
          "RMS Tremor Amplitude (mm)",
          "Root-mean-square 4-12 Hz oscillatory displacement converted to physical millimeters using display DPI.",
        ],
        [
          "Medication & Symptom Diary",
          "Patient-entered timestamps for medication doses, tremor flares, and fatigue, aligned to evaluate ON/OFF timing patterns.",
        ],
      ],
      headStyles: { fillColor: [1, 48, 90], textColor: [255, 255, 255] },
      styles: { fontSize: 8.5, cellPadding: 5 },
    });

    // Medication & Symptom Event Diary Table
    if (events.length > 0) {
      const afterGuideY = getNextY(420, 120);
      doc.setFontSize(13);
      doc.setTextColor(15, 45, 89);
      doc.text("Medication & Symptom Event Diary", 40, afterGuideY);
      autoTable(doc, {
        startY: afterGuideY + 8,
        head: [["Timestamp (Local)", "Type", "Label", "Dosage", "Severity", "Notes"]],
        body: events.map((ev) => [
          new Date(ev.timestamp * 1000).toLocaleString(),
          ev.event_type,
          ev.label,
          ev.dosage || "-",
          ev.severity !== null ? `${ev.severity}/5` : "-",
          ev.notes || "-",
        ]),
        headStyles: { fillColor: [15, 45, 89], textColor: [255, 255, 255] },
        styles: { fontSize: 8, cellPadding: 4 },
      });
    }

    // Daily Trends Table
    const afterDiaryY = getNextY(480, 120);
    doc.setFontSize(13);
    doc.setTextColor(1, 74, 53);
    doc.text("Daily Longitudinal Stability & Multi-Band Tremor Trends", 40, afterDiaryY);

    autoTable(doc, {
      startY: afterDiaryY + 8,
      head: [[
        "Date",
        "Sessions",
        "Windows",
        "Stability (/100)",
        "4-6 Hz / 6-12 Hz",
        "RMS (mm)",
        "Peak Freq",
      ]],
      body:
        trends.length > 0
          ? trends.map((t) => [
              t.date,
              String(t.session_count),
              String(t.sample_count),
              t.avg_stability_score.toFixed(1),
              `${(t.avg_resting_band_pct ?? 0).toFixed(0)}% / ${(t.avg_action_band_pct ?? 0).toFixed(0)}%`,
              `${(t.avg_rms_amplitude_mm ?? 0).toFixed(2)} mm`,
              t.avg_tremor_hz !== null ? `${t.avg_tremor_hz.toFixed(2)} Hz` : "None",
            ])
          : [["No daily trends recorded yet", "-", "-", "-", "-", "-", "-"]],
      headStyles: { fillColor: [1, 74, 53], textColor: [255, 255, 255] },
      styles: { fontSize: 8.5, cellPadding: 5 },
    });

    // Session-by-Session Motor Log
    const afterDailyY = getNextY(560, 120);
    doc.setFontSize(13);
    doc.setTextColor(1, 74, 53);
    doc.text("Session-by-Session Motor Telemetry Log", 40, afterDailyY);

    autoTable(doc, {
      startY: afterDailyY + 8,
      head: [[
        "Completed (Local Time)",
        "Windows",
        "Stability (/100)",
        "4-12 Hz Power",
        "RMS (mm)",
        "Peak Freq",
        "Mode",
      ]],
      body:
        sessions.length > 0
          ? sessions.map((s) => [
              new Date(s.ended_at * 1000).toLocaleString(),
              String(s.sample_count),
              s.avg_stability_score.toFixed(1),
              `${s.avg_tremor_index.toFixed(1)}%`,
              `${(s.avg_rms_amplitude_mm ?? 0).toFixed(2)} mm`,
              s.avg_tremor_hz !== null ? `${s.avg_tremor_hz.toFixed(2)} Hz` : "None",
              s.had_stabilization ? "Stabilized" : "Baseline",
            ])
          : [["No completed sessions stored yet", "-", "-", "-", "-", "-", "-"]],
      headStyles: { fillColor: [1, 74, 53], textColor: [255, 255, 255] },
      styles: { fontSize: 8.5, cellPadding: 5 },
    });

    if (calibrations.length > 0) {
      const afterSessY = getNextY(660, 110);
      doc.setFontSize(13);
      doc.setTextColor(1, 74, 53);
      doc.text("Stored Gaze Calibration Profiles", 40, afterSessY);
      autoTable(doc, {
        startY: afterSessY + 8,
        head: [["Profile Name", "Tracking Source", "Mean Fit Error (px)", "Status", "Created At"]],
        body: calibrations.map((c) => [
          c.name,
          c.source.toUpperCase(),
          `${c.error_px.toFixed(1)} px`,
          c.is_active ? "Active Profile" : "Archived",
          new Date(c.created_at * 1000).toLocaleString(),
        ]),
        headStyles: { fillColor: [1, 74, 53], textColor: [255, 255, 255] },
        styles: { fontSize: 8.5, cellPadding: 5 },
      });
    }

    const stamp = new Date().toISOString().slice(0, 10);
    doc.save(`clearcursor-clinician-motor-report-${stamp}.pdf`);
  };

  const exportClinicianCsv = () => {
    const header = [
      "Record Type",
      "Date / Timestamp",
      "Session or Event ID",
      "Sample Windows / Dosage / Error",
      "Stability Score (0-100)",
      "4-12 Hz Tremor Power (%)",
      "4-6 Hz Resting (%)",
      "6-12 Hz Action (%)",
      "RMS Amplitude (mm)",
      "Dominant Frequency (Hz)",
      "Mode / Category",
      "Clinical Note",
    ];
    const rows: string[][] = [
      ...trends.map((t) => [
        "Daily Trend",
        t.date,
        `${t.session_count} sessions`,
        `${t.sample_count} windows`,
        t.avg_stability_score.toFixed(1),
        t.avg_tremor_index.toFixed(1),
        (t.avg_resting_band_pct ?? 0).toFixed(1),
        (t.avg_action_band_pct ?? 0).toFixed(1),
        (t.avg_rms_amplitude_mm ?? 0).toFixed(2),
        t.avg_tremor_hz !== null ? t.avg_tremor_hz.toFixed(2) : "None",
        "Aggregated",
        formatStabilityBand(t.avg_stability_score),
      ]),
      ...sessions.map((s) => [
        "Session Summary",
        new Date(s.ended_at * 1000).toISOString(),
        s.session_id,
        `${s.sample_count} windows`,
        s.avg_stability_score.toFixed(1),
        s.avg_tremor_index.toFixed(1),
        (s.avg_resting_band_pct ?? 0).toFixed(1),
        (s.avg_action_band_pct ?? 0).toFixed(1),
        (s.avg_rms_amplitude_mm ?? 0).toFixed(2),
        s.avg_tremor_hz !== null ? s.avg_tremor_hz.toFixed(2) : "None",
        s.had_stabilization ? "SteadyHand Stabilized" : "Unassisted Baseline",
        formatFrequencyClinicalNote(s.avg_tremor_hz),
      ]),
      ...events.map((ev) => [
        "Clinical Event",
        new Date(ev.timestamp * 1000).toISOString(),
        String(ev.id),
        ev.dosage || (ev.severity ? `Severity ${ev.severity}/5` : ""),
        "",
        "",
        "",
        "",
        "",
        "",
        ev.event_type,
        `${ev.label}${ev.notes ? ` - ${ev.notes}` : ""}`,
      ]),
      ...calibrations.map((c) => [
        "Gaze Calibration",
        new Date(c.created_at * 1000).toISOString(),
        c.name,
        `${c.error_px.toFixed(1)} px`,
        "",
        "",
        "",
        "",
        "",
        "",
        c.source.toUpperCase(),
        c.is_active ? "Active Calibration Profile" : "Saved Calibration Profile",
      ]),
    ];

    const csvEscape = (cell: string) => {
      const str = String(cell);
      const safe = /^[=+\-@\t\r]/.test(str) ? `'${str}` : str;
      return `"${safe.replace(/"/g, '""')}"`;
    };
    const csv = [header, ...rows].map((row) => row.map(csvEscape).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `clearcursor-clinician-data-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-[var(--tc-ink)]">
            Clinician Motor Report &amp; Medication Diary
          </h2>
          <p className="mt-1 text-base text-[var(--tc-ink-muted)]">
            Longitudinal 4-12 Hz multi-band Welch tremor spectra, RMS displacement, diurnal patterns, and neurologist-ready PDF/CSV exports.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={exportClinicianPdf}
            className="inline-flex min-h-14 items-center gap-3 rounded-lg bg-[var(--tc-primary)] px-6 text-base font-bold text-white hover:bg-[var(--tc-primary-hover)]"
          >
            <FileDown className="h-5 w-5" aria-hidden="true" />
            <span>Export Clinician Report (PDF)</span>
          </button>

          <button
            type="button"
            onClick={exportClinicianCsv}
            className="inline-flex min-h-14 items-center gap-3 rounded-lg border-2 border-[var(--tc-primary)] bg-[var(--tc-mint)] px-5 text-base font-bold text-[var(--tc-primary)] hover:bg-[var(--tc-surface-alt)]"
          >
            <FileSpreadsheet className="h-5 w-5" aria-hidden="true" />
            <span>Export CSV Data</span>
          </button>

          <button
            type="button"
            disabled={loading}
            onClick={() => void load()}
            className="inline-flex min-h-14 items-center gap-3 rounded-lg border-2 border-[var(--tc-border-strong)] bg-[var(--tc-surface)] px-5 text-base font-bold text-[var(--tc-ink)] hover:bg-[var(--tc-mint)] disabled:opacity-50"
          >
            <RefreshCw className="h-5 w-5" aria-hidden="true" />
            <span>{loading ? "Refreshing..." : "Refresh"}</span>
          </button>
        </div>
      </div>

      {/* Date Window Selector & Simulation Filter */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] px-5 py-3.5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="mr-2 text-sm font-bold text-[var(--tc-ink)]">Report Window:</span>
          {DATE_WINDOWS.map((w) => (
            <button
              key={w.days}
              type="button"
              aria-pressed={days === w.days}
              onClick={() => setDays(w.days)}
              className={`min-h-10 rounded-lg border px-3.5 text-sm font-bold ${
                days === w.days
                  ? "border-[var(--tc-primary)] bg-[var(--tc-primary)] text-white"
                  : "border-[var(--tc-border-strong)] bg-[var(--tc-bg)] text-[var(--tc-ink)] hover:bg-[var(--tc-mint)]"
              }`}
            >
              {w.label}
            </button>
          ))}
        </div>

        <label className="inline-flex cursor-pointer items-center gap-2.5 text-sm font-semibold text-[var(--tc-ink)]">
          <input
            type="checkbox"
            checked={includeSimulated}
            onChange={(e) => setIncludeSimulated(e.target.checked)}
            className="h-4 w-4 accent-[var(--tc-primary)]"
          />
          <span>
            Include Demo/Simulated Data
            {!includeSimulated && simulatedCount > 0
              ? ` (${simulatedCount} demo windows excluded)`
              : ""}
          </span>
        </label>
      </div>

      {error && (
        <div
          role="alert"
          className="rounded-lg border-2 border-[var(--tc-alert)] bg-[var(--tc-alert-bg)] p-5 text-base font-semibold text-[var(--tc-alert)]"
        >
          {error}
        </div>
      )}

      {/* Functional Protection Summary Strip */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <div className="rounded-lg border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-4">
          <p className="text-xs font-bold uppercase text-[var(--tc-ink-muted)]">Mean RMS Amplitude</p>
          <p className="mt-1 text-2xl font-bold text-[var(--tc-ink)] tabular-nums">
            {meanRmsMm.toFixed(2)} mm
          </p>
        </div>
        <div className="rounded-lg border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-4">
          <p className="text-xs font-bold uppercase text-[var(--tc-ink-muted)]">Slip-Clicks Rescued</p>
          <p className="mt-1 text-2xl font-bold text-[var(--tc-primary)] tabular-nums">
            {functional?.total_click_rescues ?? 0}
          </p>
        </div>
        <div className="rounded-lg border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-4">
          <p className="text-xs font-bold uppercase text-[var(--tc-ink-muted)]">Accidental Drags Blocked</p>
          <p className="mt-1 text-2xl font-bold text-[var(--tc-primary)] tabular-nums">
            {functional?.total_drags_prevented ?? 0}
          </p>
        </div>
        <div className="rounded-lg border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-4">
          <p className="text-xs font-bold uppercase text-[var(--tc-ink-muted)]">Double-Click Bounces Stopped</p>
          <p className="mt-1 text-2xl font-bold text-[var(--tc-primary)] tabular-nums">
            {functional?.total_bounces_blocked ?? 0}
          </p>
        </div>
      </div>

      {/* How to Read the Clinical Data */}
      <section
        aria-labelledby="how-to-read-heading"
        className="rounded-lg border-2 border-[var(--tc-border)] bg-[var(--tc-mint)] p-6"
      >
        <div className="flex items-center gap-3">
          <Info className="h-6 w-6 shrink-0 text-[var(--tc-primary)]" aria-hidden="true" />
          <h3 id="how-to-read-heading" className="text-xl font-bold text-[var(--tc-ink)]">
            How to Read This Clinical Motor Data
          </h3>
        </div>
        <p className="mt-2 text-xs font-semibold text-[var(--tc-ink-muted)]">
          Non-Diagnostic Assistive Telemetry: Metrics summarize real-world mouse displacement spectra to support discussions with your physician or occupational therapist; ClearCursor is not a diagnostic medical device.
        </p>
        <dl className="mt-4 grid grid-cols-1 gap-6 text-base text-[var(--tc-ink)] md:grid-cols-2">
          <div className="border-t-2 border-[var(--tc-primary)] pt-3">
            <dt className="font-bold text-[var(--tc-primary)]">Cursor Stability Score (0 to 100)</dt>
            <dd className="mt-1 text-sm text-[var(--tc-ink)]">
              Measures overall steadiness. <strong>85-100</strong> means smooth control, <strong>65-84</strong> shows mild/moderate shaking being dampened, and <strong>below 65</strong> flags heavy tremor activity.
            </dd>
          </div>
          <div className="border-t-2 border-[var(--tc-primary)] pt-3">
            <dt className="font-bold text-[var(--tc-primary)]">4-6 Hz Resting vs 6-12 Hz Action Bands</dt>
            <dd className="mt-1 text-sm text-[var(--tc-ink)]">
              Separates lower-frequency resting tremor energy (<strong>4-6 Hz</strong>) from kinetic/postural essential tremor energy (<strong>6-12 Hz</strong>) alongside physical RMS amplitude in millimeters.
            </dd>
          </div>
        </dl>
      </section>

      {/* Medication & Symptom Event Diary */}
      <section
        aria-labelledby="diary-heading"
        className="rounded-lg border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-6"
      >
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <Pill className="h-6 w-6 text-[var(--tc-primary)]" aria-hidden="true" />
            <h3 id="diary-heading" className="text-xl font-bold text-[var(--tc-ink)]">
              Medication &amp; Symptom Diary
            </h3>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={savingEvent}
              onClick={() => void handleQuickEvent("medication", "Medication Dose Taken")}
              className="min-h-11 rounded-lg border-2 border-[var(--tc-primary)] bg-[var(--tc-mint)] px-3.5 text-sm font-bold text-[var(--tc-primary)] hover:bg-[#DCE8FD]"
            >
              + Medication Taken
            </button>
            <button
              type="button"
              disabled={savingEvent}
              onClick={() => void handleQuickEvent("flare", "Tremor Flare", 4)}
              className="min-h-11 rounded-lg border-2 border-[var(--tc-alert)] bg-[var(--tc-alert-bg)] px-3.5 text-sm font-bold text-[var(--tc-alert)]"
            >
              + Tremor Flare
            </button>
            <button
              type="button"
              disabled={savingEvent}
              onClick={() => void handleQuickEvent("fatigue", "Hand Fatigue", 3)}
              className="min-h-11 rounded-lg border-2 border-[var(--tc-border-strong)] bg-[var(--tc-surface-alt)] px-3.5 text-sm font-bold text-[var(--tc-ink)]"
            >
              + Fatigue
            </button>
          </div>
        </div>

        <form onSubmit={(e) => void handleSubmitEvent(e)} className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-12">
          <select
            aria-label="Event type"
            value={eventType}
            onChange={(e) => setEventType(e.target.value as ClinicalEventType)}
            className="min-h-12 rounded-lg border-2 border-[var(--tc-border-strong)] bg-[var(--tc-bg)] px-3 text-sm font-semibold md:col-span-2"
          >
            <option value="medication">Medication</option>
            <option value="flare">Tremor Flare</option>
            <option value="symptom">Symptom</option>
            <option value="fatigue">Fatigue</option>
            <option value="note">Clinical Note</option>
          </select>
          <input
            type="text"
            value={eventLabel}
            onChange={(e) => setEventLabel(e.target.value)}
            placeholder="Label (e.g. Carbidopa-Levodopa)"
            className="min-h-12 rounded-lg border-2 border-[var(--tc-border-strong)] bg-[var(--tc-bg)] px-3 text-sm md:col-span-3"
          />
          <input
            type="text"
            value={eventDosage}
            onChange={(e) => setEventDosage(e.target.value)}
            placeholder="Dosage (optional)"
            className="min-h-12 rounded-lg border-2 border-[var(--tc-border-strong)] bg-[var(--tc-bg)] px-3 text-sm md:col-span-2"
          />
          <select
            aria-label="Severity"
            value={eventSeverity}
            onChange={(e) => setEventSeverity(e.target.value)}
            className="min-h-12 rounded-lg border-2 border-[var(--tc-border-strong)] bg-[var(--tc-bg)] px-3 text-sm md:col-span-2"
          >
            <option value="">Severity (opt.)</option>
            <option value="1">1 - Very Mild</option>
            <option value="2">2 - Mild</option>
            <option value="3">3 - Moderate</option>
            <option value="4">4 - Marked</option>
            <option value="5">5 - Severe</option>
          </select>
          <input
            type="text"
            value={eventNotes}
            onChange={(e) => setEventNotes(e.target.value)}
            placeholder="Notes (optional)"
            className="min-h-12 rounded-lg border-2 border-[var(--tc-border-strong)] bg-[var(--tc-bg)] px-3 text-sm md:col-span-2"
          />
          <button
            type="submit"
            disabled={savingEvent || !eventLabel.trim()}
            className="inline-flex min-h-12 items-center justify-center gap-1.5 rounded-lg bg-[var(--tc-primary)] px-4 text-sm font-bold text-white hover:bg-[var(--tc-primary-hover)] disabled:opacity-50 md:col-span-1"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            <span>Log</span>
          </button>
        </form>

        {events.length > 0 && (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full border-collapse text-left text-sm">
              <thead>
                <tr className="border-b-2 border-[var(--tc-border)] text-[var(--tc-ink-muted)]">
                  <th className="py-2 pr-3 font-bold">Time</th>
                  <th className="py-2 pr-3 font-bold">Type</th>
                  <th className="py-2 pr-3 font-bold">Label</th>
                  <th className="py-2 pr-3 font-bold">Dosage / Severity</th>
                  <th className="py-2 pr-3 font-bold">Notes</th>
                  <th className="py-2 font-bold">Action</th>
                </tr>
              </thead>
              <tbody>
                {events.map((ev) => (
                  <tr key={ev.id} className="border-b border-[var(--tc-border)]">
                    <td className="py-2 pr-3 tabular-nums">{new Date(ev.timestamp * 1000).toLocaleString()}</td>
                    <td className="py-2 pr-3 font-semibold uppercase">{ev.event_type}</td>
                    <td className="py-2 pr-3 font-bold">{ev.label}</td>
                    <td className="py-2 pr-3">{ev.dosage || (ev.severity ? `${ev.severity}/5` : "-")}</td>
                    <td className="py-2 pr-3 text-[var(--tc-ink-muted)]">{ev.notes || "-"}</td>
                    <td className="py-2">
                      <button
                        type="button"
                        aria-label={`Delete event ${ev.label}`}
                        onClick={() => void handleDeleteEvent(ev.id)}
                        className="rounded p-1 text-[var(--tc-alert)] hover:bg-[var(--tc-alert-bg)]"
                      >
                        <Trash2 className="h-4 w-4" aria-hidden="true" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Recharts Daily Stability, Multi-Band & Diurnal Charts */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <section
          aria-labelledby="daily-trend-heading"
          className="space-y-4 border-t-2 border-[var(--tc-border)] pt-5"
        >
          <h3 id="daily-trend-heading" className="text-lg font-bold text-[var(--tc-ink)]">
            Daily Stability Score (0-100)
          </h3>

          {trends.length === 0 ? (
            <p className="rounded-md bg-[var(--tc-surface-alt)] p-5 text-sm text-[var(--tc-ink-muted)]">
              No daily stability trends recorded in this window yet.
            </p>
          ) : (
            <div className="h-60 w-full rounded-lg border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-3">
              <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                <AreaChart data={trends}>
                  <defs>
                    <linearGradient id="tcDailyStabilityGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#1D4ED8" stopOpacity={0.30} />
                      <stop offset="95%" stopColor="#1D4ED8" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="date" stroke="#42526E" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis domain={[0, 100]} stroke="#42526E" fontSize={11} tickLine={false} axisLine={false} />
                  <ReferenceLine y={85} stroke="#0F2D59" strokeDasharray="5 4" strokeOpacity={0.55} />
                  <Tooltip />
                  <Area
                    type="monotone"
                    dataKey="avg_stability_score"
                    name="Stability Score"
                    stroke="#1D4ED8"
                    strokeWidth={3}
                    fill="url(#tcDailyStabilityGrad)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>

        <section
          aria-labelledby="tremor-trend-heading"
          className="space-y-4 border-t-2 border-[var(--tc-border)] pt-5"
        >
          <h3 id="tremor-trend-heading" className="text-lg font-bold text-[var(--tc-ink)]">
            Resting (4-6 Hz) vs Action (6-12 Hz)
          </h3>

          {trends.length === 0 ? (
            <p className="rounded-xl bg-[var(--tc-surface-alt)] p-5 text-sm text-[var(--tc-ink-muted)]">
              Spectral bands populate automatically during everyday pointer movement.
            </p>
          ) : (
            <div className="h-60 w-full rounded-xl border border-[var(--tc-border)] bg-[var(--tc-surface)] p-3 shadow-[var(--tc-shadow)]">
              <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                <BarChart data={trends}>
                  <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="date" stroke="#42526E" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis domain={[0, 100]} stroke="#42526E" fontSize={11} tickLine={false} axisLine={false} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="avg_resting_band_pct" name="4-6 Hz Resting (%)" fill="#0F2D59" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="avg_action_band_pct" name="6-12 Hz Action (%)" fill="#9F1239" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>

        <section
          aria-labelledby="diurnal-heading"
          className="space-y-4 border-t-2 border-[var(--tc-border)] pt-5"
        >
          <h3 id="diurnal-heading" className="text-lg font-bold text-[var(--tc-ink)]">
            Time-of-Day Diurnal Pattern (0-23h)
          </h3>

          {hourly.length === 0 ? (
            <p className="rounded-xl bg-[var(--tc-surface-alt)] p-5 text-sm text-[var(--tc-ink-muted)]">
              Hourly tremor distribution appears once sessions are recorded across the day.
            </p>
          ) : (
            <div className="h-60 w-full rounded-xl border border-[var(--tc-border)] bg-[var(--tc-surface)] p-3 shadow-[var(--tc-shadow)]">
              <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                <BarChart data={hourly}>
                  <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="label" stroke="#42526E" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis domain={[0, 100]} stroke="#42526E" fontSize={11} tickLine={false} axisLine={false} />
                  <Tooltip />
                  <Bar dataKey="avg_tremor_index" name="4-12 Hz Tremor (%)" fill="#1D4ED8" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>
      </div>

      {/* Descriptive Sessions & Calibrations Tables */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <section className="rounded-lg border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-6">
          <h3 className="text-xl font-bold text-[var(--tc-ink)]">
            Recorded Motor Telemetry Sessions
          </h3>
          {sessions.length === 0 ? (
            <p className="mt-4 text-base text-[var(--tc-ink-muted)]">
              No completed real-world sessions stored yet in this window.
            </p>
          ) : (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b-2 border-[var(--tc-border)] text-[var(--tc-ink-muted)]">
                    <th className="py-3 pr-3 font-bold">Completed (Local Time)</th>
                    <th className="py-3 pr-3 font-bold">Stability (/100)</th>
                    <th className="py-3 pr-3 font-bold">4-12 Hz / RMS</th>
                    <th className="py-3 pr-3 font-bold">Peak Freq</th>
                    <th className="py-3 font-bold">Mode / Windows</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.map((s) => (
                    <tr key={s.session_id} className="border-b border-[var(--tc-border)]">
                      <td className="py-3 pr-3 font-medium tabular-nums">
                        {new Date(s.ended_at * 1000).toLocaleString()}
                      </td>
                      <td className="py-3 pr-3 font-bold text-[var(--tc-primary)] tabular-nums">
                        {s.avg_stability_score.toFixed(1)}
                      </td>
                      <td className="py-3 pr-3 tabular-nums">
                        {s.avg_tremor_index.toFixed(1)}% ({(s.avg_rms_amplitude_mm ?? 0).toFixed(2)} mm)
                      </td>
                      <td className="py-3 pr-3 tabular-nums">
                        {s.avg_tremor_hz !== null ? `${s.avg_tremor_hz.toFixed(2)} Hz` : "None"}
                      </td>
                      <td className="py-3 tabular-nums">
                        {s.had_stabilization ? "Stabilized" : "Baseline"} ({s.sample_count})
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="rounded-lg border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-6">
          <h3 className="text-xl font-bold text-[var(--tc-ink)]">
            Saved Gaze Calibration Accuracy Records
          </h3>
          {calibrations.length === 0 ? (
            <p className="mt-4 text-base text-[var(--tc-ink-muted)]">
              No gaze calibration profiles saved yet.
            </p>
          ) : (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b-2 border-[var(--tc-border)] text-[var(--tc-ink-muted)]">
                    <th className="py-3 pr-3 font-bold">Profile Name</th>
                    <th className="py-3 pr-3 font-bold">Tracking Input</th>
                    <th className="py-3 pr-3 font-bold">Mean Fit Error</th>
                    <th className="py-3 font-bold">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {calibrations.map((c) => (
                    <tr key={c.id} className="border-b border-[var(--tc-border)]">
                      <td className="py-3 pr-3 font-semibold">{c.name}</td>
                      <td className="py-3 pr-3 uppercase">{c.source}</td>
                      <td className="py-3 pr-3 tabular-nums">{c.error_px.toFixed(1)} px</td>
                      <td className="py-3 font-semibold">
                        {c.is_active ? "Active" : "Archived"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
