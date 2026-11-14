import { jsPDF } from "jspdf";
import autoTable from "jspdf-autotable";
import { FileDown, FileSpreadsheet, Info, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchSessions } from "../api/client";
import type { SessionsResponse } from "../types/telemetry";

function formatStabilityBand(score: number): string {
  if (score >= 85) {
    return "Optimal Steadiness (85-100)";
  }
  if (score >= 65) {
    return "Moderate Tremor Burden (65-84)";
  }
  return "Elevated Tremor / OFF-Period Risk (<65)";
}

function formatFrequencyClinicalNote(hz: number | null): string {
  if (hz === null) {
    return "No sustained 4-7 Hz oscillation detected";
  }
  if (hz >= 4.0 && hz <= 7.0) {
    return `${hz.toFixed(2)} Hz (Classic Parkinsonian 4-7 Hz band)`;
  }
  return `${hz.toFixed(2)} Hz (Outside 4-7 Hz primary band)`;
}

export function SessionHistory() {
  const [data, setData] = useState<SessionsResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchSessions(14, 30);
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
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const trends = data?.daily_trends ?? [];
  const sessions = data?.sessions ?? [];
  const calibrations = data?.calibration_profiles ?? [];

  const totalSamples = sessions.reduce((acc, s) => acc + s.sample_count, 0);
  const meanStability =
    sessions.length > 0
      ? sessions.reduce((acc, s) => acc + s.avg_stability_score, 0) / sessions.length
      : 0;
  const meanTremorIdx =
    sessions.length > 0
      ? sessions.reduce((acc, s) => acc + s.avg_tremor_index, 0) / sessions.length
      : 0;
  const hzSessions = sessions.filter((s) => s.avg_tremor_hz !== null);
  const meanHz =
    hzSessions.length > 0
      ? hzSessions.reduce((acc, s) => acc + (s.avg_tremor_hz ?? 0), 0) / hzSessions.length
      : null;

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
    doc.setTextColor(1, 74, 53);
    doc.text("TrueCursor Clinician Motor Telemetry Report", 40, 48);

    doc.setFontSize(10);
    doc.setTextColor(61, 76, 70);
    doc.text(`Generated: ${nowLabel}   |   Reporting Window: Last 14 Days`, 40, 66);

    // Executive Summary Table
    autoTable(doc, {
      startY: 82,
      head: [["Clinical Summary Metric", "Observed Value", "Interpretation"]],
      body: [
        ["Recorded Motor Sessions", `${sessions.length} sessions (${totalSamples} FFT windows)`, "Each window averages 4s of pointer velocity spectral density."],
        ["Overall Mean Stability Score", `${meanStability.toFixed(1)} / 100`, formatStabilityBand(meanStability)],
        ["Mean 4-7 Hz Tremor Band Power", `${meanTremorIdx.toFixed(1)}% of motor energy`, "Share of 0.5-12 Hz movement energy concentrated in 4-7 Hz."],
        ["Mean Dominant Tremor Frequency", meanHz !== null ? `${meanHz.toFixed(2)} Hz` : "None detected", formatFrequencyClinicalNote(meanHz)],
        ["Active Gaze Calibration Profiles", `${calibrations.length} stored profiles`, "Affine gaze mapping accuracy measured in mean pixel error."],
      ],
      headStyles: { fillColor: [1, 74, 53], textColor: [255, 255, 255] },
      styles: { fontSize: 9, cellPadding: 6 },
    });

    // How to Read This Data Guide
    const afterSummaryY = getNextY(220, 140);
    doc.setFontSize(13);
    doc.setTextColor(1, 74, 53);
    doc.text("How to Read This Clinical Motor Report", 40, afterSummaryY);

    autoTable(doc, {
      startY: afterSummaryY + 8,
      head: [["Column / Term", "Clinical Meaning & Reference Range"]],
      body: [
        [
          "Cursor Stability Score (0-100)",
          "Composite index combining suppressed 4-7 Hz tremor power and One Euro damping benefit. Higher scores (85-100) indicate steady control; <65 suggests pronounced tremor burden.",
        ],
        [
          "4-7 Hz Tremor Power (%)",
          "Percentage of Welch spectral power (0.5-12 Hz band) occurring specifically between 4 and 7 Hz. Values >= 50% estimate an OFF-medication or high-tremor period.",
        ],
        [
          "Dominant Tremor Frequency (Hz)",
          "Peak involuntary oscillation frequency when 4-7 Hz band power reaches >= 10%. Classic resting Parkinsonian tremor falls between 4.0 and 7.0 Hz.",
        ],
        [
          "Assistance Mode Status",
          "Indicates whether One Euro stabilization & click-freeze were active ('Stabilized') vs. unassisted raw baseline movement ('Unassisted Baseline').",
        ],
        [
          "Gaze Calibration Error (px)",
          "Mean Euclidean distance error during 5- or 9-point gaze fitting. Under 65 px enables comfortable large-button hands-free selection.",
        ],
      ],
      headStyles: { fillColor: [1, 48, 90], textColor: [255, 255, 255] },
      styles: { fontSize: 8.5, cellPadding: 5 },
    });

    // Daily Trends Table
    const afterGuideY = getNextY(420, 120);
    doc.setFontSize(13);
    doc.setTextColor(1, 74, 53);
    doc.text("Daily Longitudinal Stability & 4-7 Hz Tremor Trends", 40, afterGuideY);

    autoTable(doc, {
      startY: afterGuideY + 8,
      head: [[
        "Calendar Date",
        "Sessions",
        "FFT Windows",
        "Mean Stability Score (0-100)",
        "4-7 Hz Tremor Power (%)",
        "Mean Peak Frequency",
        "Clinical Assessment",
      ]],
      body:
        trends.length > 0
          ? trends.map((t) => [
              t.date,
              String(t.session_count),
              String(t.sample_count),
              t.avg_stability_score.toFixed(1),
              `${t.avg_tremor_index.toFixed(1)}%`,
              t.avg_tremor_hz !== null ? `${t.avg_tremor_hz.toFixed(2)} Hz` : "None",
              formatStabilityBand(t.avg_stability_score),
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
        "Session Completed (Local Time)",
        "Session ID",
        "FFT Windows",
        "Stability Score (/100)",
        "4-7 Hz Tremor Power (%)",
        "Dominant Freq (Hz)",
        "Assistance Mode",
      ]],
      body:
        sessions.length > 0
          ? sessions.map((s) => [
              new Date(s.ended_at * 1000).toLocaleString(),
              s.session_id,
              String(s.sample_count),
              s.avg_stability_score.toFixed(1),
              `${s.avg_tremor_index.toFixed(1)}%`,
              s.avg_tremor_hz !== null ? `${s.avg_tremor_hz.toFixed(2)} Hz` : "None",
              s.had_stabilization ? "Stabilized (SteadyHand ON)" : "Unassisted Baseline",
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
    doc.save(`truecursor-clinician-motor-report-${stamp}.pdf`);
  };

  const exportClinicianCsv = () => {
    const header = [
      "Record Type",
      "Date / Timestamp",
      "Session or Profile ID",
      "Sample Windows / Error px",
      "Stability Score (0-100)",
      "4-7 Hz Tremor Band Power (%)",
      "Dominant Frequency (Hz)",
      "Assistance / Tracking Mode",
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
        s.avg_tremor_hz !== null ? s.avg_tremor_hz.toFixed(2) : "None",
        s.had_stabilization ? "SteadyHand Stabilized" : "Unassisted Baseline",
        formatFrequencyClinicalNote(s.avg_tremor_hz),
      ]),
      ...calibrations.map((c) => [
        "Gaze Calibration",
        new Date(c.created_at * 1000).toISOString(),
        c.name,
        `${c.error_px.toFixed(1)} px`,
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
    link.download = `truecursor-clinician-data-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-[var(--tc-ink)]">
            Clinician Motor Report &amp; Session History
          </h2>
          <p className="mt-1 text-base text-[var(--tc-ink-muted)]">
            Longitudinal 4-7 Hz Welch spectral tremor records, stability trends, and neurologist-ready PDF/CSV exports from SQLite.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-4">
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

      {error && (
        <div
          role="alert"
          className="rounded-lg border-2 border-[var(--tc-alert)] bg-[var(--tc-alert-bg)] p-5 text-base font-semibold text-[var(--tc-alert)]"
        >
          {error}
        </div>
      )}

      {/* How to Read the Clinical Data (Flattened editorial glossary, zero nested cards) */}
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
        <dl className="mt-4 grid grid-cols-1 gap-6 text-base text-[var(--tc-ink)] md:grid-cols-2">
          <div className="border-t-2 border-[var(--tc-primary)] pt-3">
            <dt className="font-bold text-[var(--tc-primary)]">Cursor Stability Score (0 to 100)</dt>
            <dd className="mt-1 text-sm text-[var(--tc-ink)]">
              Measures overall steadiness. <strong>85-100</strong> means smooth control, <strong>65-84</strong> shows mild/moderate shaking being dampened, and <strong>below 65</strong> flags heavy tremor activity.
            </dd>
          </div>
          <div className="border-t-2 border-[var(--tc-primary)] pt-3">
            <dt className="font-bold text-[var(--tc-primary)]">4-7 Hz Tremor Band Power (%) &amp; Frequency (Hz)</dt>
            <dd className="mt-1 text-sm text-[var(--tc-ink)]">
              Percentage of Welch movement energy concentrated in the <strong>4-7 Hz Parkinsonian tremor band</strong>. Readings <strong>50% or higher</strong> indicate a likely OFF-medication or high-tremor interval.
            </dd>
          </div>
          <div className="border-t-2 border-[var(--tc-primary)] pt-3">
            <dt className="font-bold text-[var(--tc-primary)]">Assistance Mode (Stabilized vs. Baseline)</dt>
            <dd className="mt-1 text-sm text-[var(--tc-ink)]">
              Shows whether One Euro smoothing and 180ms click-freeze were turned ON (<strong>Stabilized</strong>) or OFF (<strong>Unassisted Baseline</strong>) during that session window.
            </dd>
          </div>
          <div className="border-t-2 border-[var(--tc-primary)] pt-3">
            <dt className="font-bold text-[var(--tc-primary)]">Gaze Calibration Mean Error (px)</dt>
            <dd className="mt-1 text-sm text-[var(--tc-ink)]">
              Average pixel offset from the 5- or 9-point gaze wizard. Values <strong>under 65 px</strong> provide comfortable hands-free button selection.
            </dd>
          </div>
        </dl>
      </section>

      {/* Recharts Daily Stability & Tremor Charts */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <section
          aria-labelledby="daily-trend-heading"
          className="space-y-4 border-t-2 border-[var(--tc-border)] pt-5"
        >
          <h3 id="daily-trend-heading" className="text-xl font-bold text-[var(--tc-ink)]">
            Daily Average Stability Score (0-100)
          </h3>

          {trends.length === 0 ? (
            <p className="rounded-md bg-[var(--tc-surface-alt)] p-5 text-base text-[var(--tc-ink-muted)]">
              No daily stability trends recorded yet. Use the Sandbox Lab or move the pointer with 4-7 Hz simulation enabled for at least 4 seconds to store a window.
            </p>
          ) : (
            <div className="h-64 w-full rounded-lg border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-3">
              <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                <AreaChart data={trends}>
                  <CartesianGrid stroke="#CBD5CF" strokeDasharray="4 4" />
                  <XAxis dataKey="date" stroke="#3D4C46" fontSize={12} />
                  <YAxis domain={[0, 100]} stroke="#3D4C46" fontSize={12} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#FFFFFF",
                      border: "2px solid #014A35",
                      borderRadius: "6px",
                      color: "#16201C",
                      fontWeight: 600,
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="avg_stability_score"
                    name="Stability Score"
                    stroke="#014A35"
                    strokeWidth={3}
                    fill="#E3EFE9"
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
          <h3 id="tremor-trend-heading" className="text-xl font-bold text-[var(--tc-ink)]">
            Daily 4-7 Hz Tremor Power (%) Trend
          </h3>

          {trends.length === 0 ? (
            <p className="rounded-md bg-[var(--tc-surface-alt)] p-5 text-base text-[var(--tc-ink-muted)]">
              Once sessions are recorded, this chart tracks longitudinal tremor intensity across medication cycles.
            </p>
          ) : (
            <div className="h-64 w-full rounded-lg border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-3">
              <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                <LineChart data={trends}>
                  <CartesianGrid stroke="#CBD5CF" strokeDasharray="4 4" />
                  <XAxis dataKey="date" stroke="#3D4C46" fontSize={12} />
                  <YAxis domain={[0, 100]} stroke="#3D4C46" fontSize={12} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#FFFFFF",
                      border: "2px solid #8C2113",
                      borderRadius: "6px",
                      color: "#16201C",
                      fontWeight: 600,
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="avg_tremor_index"
                    name="4-7 Hz Band Power (%)"
                    stroke="#8C2113"
                    strokeWidth={3}
                    dot={{ r: 5, fill: "#8C2113" }}
                  />
                </LineChart>
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
              No completed sessions stored yet.
            </p>
          ) : (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b-2 border-[var(--tc-border)] text-[var(--tc-ink-muted)]">
                    <th className="py-3 pr-3 font-bold">Completed (Local Time)</th>
                    <th className="py-3 pr-3 font-bold">Stability (/100)</th>
                    <th className="py-3 pr-3 font-bold">4-7 Hz Power</th>
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
                        {s.avg_tremor_index.toFixed(1)}%
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
