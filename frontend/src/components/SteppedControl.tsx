import { Minus, Plus } from "lucide-react";

interface SteppedControlProps {
  id: string;
  label: string;
  description: string;
  value: number;
  min: number;
  max: number;
  step: number;
  unit?: string;
  decimals?: number;
  onChange: (nextValue: number) => void;
}

export function SteppedControl({
  id,
  label,
  description,
  value,
  min,
  max,
  step,
  unit = "",
  decimals = 0,
  onChange,
}: SteppedControlProps) {
  const clampAndRound = (raw: number): number => {
    const clamped = Math.max(min, Math.min(max, raw));
    const factor = Math.pow(10, decimals);
    return Math.round(clamped * factor) / factor;
  };

  const formatted = decimals > 0 ? value.toFixed(decimals) : String(Math.round(value));

  return (
    <div className="rounded-2xl border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-5">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-4">
        <div>
          <label
            htmlFor={id}
            className="block text-lg font-bold text-[var(--tc-ink)]"
          >
            {label}
          </label>
          <p className="mt-1 text-base text-[var(--tc-ink-muted)]">
            {description}
          </p>
        </div>
        <div
          aria-live="polite"
          className="rounded-xl border-2 border-[var(--tc-border)] bg-[var(--tc-surface-alt)] px-4 py-2 text-lg font-bold text-[var(--tc-ink)] tabular-nums"
        >
          {formatted}
          {unit ? ` ${unit}` : ""}
        </div>
      </div>

      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={() => onChange(clampAndRound(value - step))}
          disabled={value <= min}
          aria-label={`Decrease ${label} by ${step}${unit ? ` ${unit}` : ""}`}
          className="inline-flex min-h-14 min-w-14 shrink-0 items-center justify-center rounded-xl border-2 border-[var(--tc-border-strong)] bg-[var(--tc-surface-alt)] text-[var(--tc-ink)] hover:bg-[var(--tc-mint)] disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Minus className="h-6 w-6" aria-hidden="true" />
        </button>

        <input
          id={id}
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          aria-valuetext={`${formatted}${unit ? ` ${unit}` : ""}`}
          onChange={(e) => onChange(clampAndRound(Number(e.target.value)))}
          className="tc-slider"
        />

        <button
          type="button"
          onClick={() => onChange(clampAndRound(value + step))}
          disabled={value >= max}
          aria-label={`Increase ${label} by ${step}${unit ? ` ${unit}` : ""}`}
          className="inline-flex min-h-14 min-w-14 shrink-0 items-center justify-center rounded-xl border-2 border-[var(--tc-border-strong)] bg-[var(--tc-surface-alt)] text-[var(--tc-ink)] hover:bg-[var(--tc-mint)] disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Plus className="h-6 w-6" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
