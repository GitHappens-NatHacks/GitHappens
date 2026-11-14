import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { fetchSessions } from "../api/client";
import type { SessionsResponse } from "../types/telemetry";

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

  const svgW = 760;
  const svgH = 240;
  const padL = 52;
  const padR = 24;
  const padT = 20;
  const padB = 40;
  const plotW = svgW - padL - padR;
  const plotH = svgH - padT - padB;

  const polylinePoints = trends
    .map((pt, idx) => {
      const x =
        trends.length === 1
          ? padL + plotW / 2
          : padL + (idx / (trends.length - 1)) * plotW;
      const y =
        padT + plotH - (Math.max(0, Math.min(100, pt.avg_stability_score)) / 100) * plotH;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-[var(--tc-ink)]">
            Session History &amp; Daily Stability Trends
          </h2>
          <p className="mt-1 text-base text-[var(--tc-ink-muted)]">
            Persisted FFT tremor snapshots and calibration accuracy records from SQLite.
          </p>
        </div>

        <button
          type="button"
          disabled={loading}
          onClick={() => void load()}
          className="inline-flex min-h-14 items-center gap-3 rounded-xl border-2 border-[var(--tc-border-strong)] bg-[var(--tc-surface)] px-6 text-base font-bold text-[var(--tc-ink)] hover:bg-[var(--tc-mint)] disabled:opacity-50"
        >
          <RefreshCw className="h-5 w-5" aria-hidden="true" />
          <span>{loading ? "Refreshing..." : "Refresh History"}</span>
        </button>
      </div>

      {error && (
        <div
          role="alert"
          className="rounded-2xl border-2 border-[var(--tc-alert)] bg-[var(--tc-alert-bg)] p-5 text-base font-semibold text-[var(--tc-alert)]"
        >
          {error}
        </div>
      )}

      {/* Daily Stability Chart */}
      <section
        aria-labelledby="daily-trend-heading"
        className="rounded-2xl border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-6"
      >
        <h3 id="daily-trend-heading" className="text-xl font-bold text-[var(--tc-ink)]">
          Daily Average Stability Score (0-100)
        </h3>

        {loading && !data ? (
          <p className="mt-6 text-base text-[var(--tc-ink-muted)]">
            Loading daily stability records...
          </p>
        ) : trends.length === 0 ? (
          <p className="mt-6 rounded-xl bg-[var(--tc-surface-alt)] p-6 text-base text-[var(--tc-ink-muted)]">
            No session tremor telemetry recorded yet. Enable 4-7 Hz simulation or move the cursor on the Control Deck for at least 4 seconds to record your first window.
          </p>
        ) : (
          <div className="mt-4">
            <svg
              viewBox={`0 0 ${svgW} ${svgH}`}
              role="img"
              aria-label="Daily average stability score chart"
              className="h-64 w-full rounded-xl border border-[var(--tc-border)] bg-[var(--tc-bg)]"
            >
              {[0, 25, 50, 75, 100].map((tick) => {
                const y = padT + plotH - (tick / 100) * plotH;
                return (
                  <g key={tick}>
                    <line
                      x1={padL}
                      y1={y}
                      x2={svgW - padR}
                      y2={y}
                      stroke="#CBD5CF"
                      strokeDasharray="4 4"
                    />
                    <text
                      x={padL - 10}
                      y={y + 5}
                      textAnchor="end"
                      fontSize="12"
                      fill="#3D4C46"
                    >
                      {tick}
                    </text>
                  </g>
                );
              })}

              {trends.length > 1 && (
                <polyline
                  fill="none"
                  stroke="#014A35"
                  strokeWidth="3.5"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                  points={polylinePoints}
                />
              )}

              {trends.map((pt, idx) => {
                const x =
                  trends.length === 1
                    ? padL + plotW / 2
                    : padL + (idx / (trends.length - 1)) * plotW;
                const y =
                  padT +
                  plotH -
                  (Math.max(0, Math.min(100, pt.avg_stability_score)) / 100) * plotH;
                const labelStep = trends.length > 7 ? Math.ceil(trends.length / 6) : 1;
                const showDate =
                  idx === 0 || idx === trends.length - 1 || idx % labelStep === 0;
                const shortDate = pt.date.length === 10 ? pt.date.slice(5) : pt.date;
                return (
                  <g key={pt.date}>
                    <circle
                      cx={x}
                      cy={y}
                      r="7"
                      fill="#014A35"
                      stroke="#FFFFFF"
                      strokeWidth="2.5"
                    />
                    {showDate && (
                      <text
                        x={x}
                        y={svgH - 12}
                        textAnchor="middle"
                        fontSize="12"
                        fontWeight="600"
                        fill="#16201C"
                      >
                        {shortDate}
                      </text>
                    )}
                  </g>
                );
              })}
            </svg>
          </div>
        )}
      </section>

      {/* Sessions Table + Saved Calibrations */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <section className="rounded-2xl border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-6">
          <h3 className="text-xl font-bold text-[var(--tc-ink)]">
            Recent Sessions
          </h3>
          {sessions.length === 0 ? (
            <p className="mt-4 text-base text-[var(--tc-ink-muted)]">
              No completed sessions stored yet.
            </p>
          ) : (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full border-collapse text-left text-base">
                <thead>
                  <tr className="border-b-2 border-[var(--tc-border)] text-[var(--tc-ink-muted)]">
                    <th className="py-3 pr-4 font-bold">Date</th>
                    <th className="py-3 pr-4 font-bold">Stability</th>
                    <th className="py-3 pr-4 font-bold">Avg Hz</th>
                    <th className="py-3 font-bold">Samples</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.map((s) => (
                    <tr key={s.session_id} className="border-b border-[var(--tc-border)]">
                      <td className="py-3 pr-4 font-medium tabular-nums">
                        {new Date(s.ended_at * 1000).toLocaleString()}
                      </td>
                      <td className="py-3 pr-4 font-bold text-[var(--tc-primary)] tabular-nums">
                        {s.avg_stability_score.toFixed(1)}
                      </td>
                      <td className="py-3 pr-4 tabular-nums">
                        {s.avg_tremor_hz !== null ? `${s.avg_tremor_hz.toFixed(2)} Hz` : "None"}
                      </td>
                      <td className="py-3 tabular-nums">{s.sample_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="rounded-2xl border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-6">
          <h3 className="text-xl font-bold text-[var(--tc-ink)]">
            Saved Calibration Profiles
          </h3>
          {calibrations.length === 0 ? (
            <p className="mt-4 text-base text-[var(--tc-ink-muted)]">
              No gaze calibration profiles saved yet.
            </p>
          ) : (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full border-collapse text-left text-base">
                <thead>
                  <tr className="border-b-2 border-[var(--tc-border)] text-[var(--tc-ink-muted)]">
                    <th className="py-3 pr-4 font-bold">Profile</th>
                    <th className="py-3 pr-4 font-bold">Source</th>
                    <th className="py-3 pr-4 font-bold">Error</th>
                    <th className="py-3 font-bold">State</th>
                  </tr>
                </thead>
                <tbody>
                  {calibrations.map((c) => (
                    <tr key={c.id} className="border-b border-[var(--tc-border)]">
                      <td className="py-3 pr-4 font-semibold">{c.name}</td>
                      <td className="py-3 pr-4 uppercase">{c.source}</td>
                      <td className="py-3 pr-4 tabular-nums">{c.error_px.toFixed(1)} px</td>
                      <td className="py-3 font-semibold">
                        {c.is_active ? "Active" : "Saved"}
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
