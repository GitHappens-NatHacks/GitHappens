import {
  Activity,
  ArrowRight,
  Compass,
  Eye,
  Hand,
  HeartHandshake,
  Magnet,
  MousePointerClick,
  ShieldCheck,
} from "lucide-react";
import { BrandLogo } from "./BrandLogo";

interface HomeOverviewProps {
  stabilizationActive: boolean;
  onStartStabilizing: () => void;
  onOpenPlayground: () => void;
  onOpenControlDeck: () => void;
}

function EditorialIllustration({
  variant,
  title,
  subtitle,
}: {
  variant: "workspace" | "caregiver";
  title: string;
  subtitle: string;
}) {
  return (
    <div
      role="img"
      aria-label={`${title} - ${subtitle}`}
      className="flex h-full min-h-[240px] w-full flex-col items-center justify-center rounded-xl border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-6 text-center shadow-[var(--tc-shadow)]"
    >
      {variant === "workspace" ? (
        <svg viewBox="0 0 260 150" className="h-36 w-full max-w-[260px]" aria-hidden="true">
          <rect x="16" y="14" width="228" height="122" rx="14" fill="#F8FAFC" stroke="#0F2D59" strokeWidth="2.5" />
          <path d="M36 92 C66 64, 92 108, 124 78 C150 56, 178 96, 222 64" stroke="#9F1239" strokeWidth="2.5" strokeDasharray="5 4" fill="none" />
          <path d="M36 86 C86 78, 152 72, 222 64" stroke="#1D4ED8" strokeWidth="4" strokeLinecap="round" fill="none" />
          <circle cx="222" cy="64" r="16" fill="#DBEAFE" stroke="#1D4ED8" strokeWidth="2.5" strokeDasharray="4 3" />
          <circle cx="222" cy="64" r="7" fill="#0F2D59" />
          <rect x="36" y="30" width="94" height="12" rx="6" fill="#CBD5E1" />
          <rect x="36" y="110" width="142" height="10" rx="5" fill="#E2E8F0" />
        </svg>
      ) : (
        <svg viewBox="0 0 260 150" className="h-36 w-full max-w-[260px]" aria-hidden="true">
          <rect x="16" y="14" width="228" height="122" rx="14" fill="#FFFFFF" stroke="#0F2D59" strokeWidth="2.5" />
          <rect x="34" y="34" width="90" height="82" rx="10" fill="#EFF6FF" stroke="#1D4ED8" strokeWidth="2" />
          <path d="M48 92 L68 72 L86 82 L110 56" stroke="#1D4ED8" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
          <rect x="138" y="36" width="86" height="14" rx="5" fill="#0F2D59" />
          <rect x="138" y="60" width="72" height="10" rx="5" fill="#94A3B8" />
          <rect x="138" y="78" width="84" height="10" rx="5" fill="#CBD5E1" />
          <rect x="138" y="98" width="56" height="16" rx="6" fill="#DBEAFE" stroke="#1D4ED8" strokeWidth="1.5" />
        </svg>
      )}
      <p className="mt-3 text-base font-bold text-[var(--tc-ink)]">{title}</p>
      <p className="mt-0.5 text-sm text-[var(--tc-ink-muted)]">{subtitle}</p>
    </div>
  );
}

const CHALLENGES = [
  {
    title: "Missed Clicks on Tiny Buttons",
    body: "Even mild hand tremors can push the arrow just off a small toolbar button or checkbox right as you press down.",
    icon: MousePointerClick,
    diagram: "hitbox",
  },
  {
    title: "Accidental File Drags & Double-Clicks",
    body: "Natural finger tremor during a click often looks like a swipe or double-tap to your computer, dragging windows or bouncing clicks by mistake.",
    icon: ShieldCheck,
    diagram: "freeze",
  },
  {
    title: "Medication On & Off Changes",
    body: "Comfort changes throughout the day as medication takes effect or wears off. Rigid mouse settings rarely keep pace.",
    icon: Activity,
    diagram: "preset",
  },
];

const SOLUTIONS = [
  {
    title: "Smart Tremor Smoothing",
    body: "Filters fast 4-12 Hz involuntary hand shaking (Parkinsonian & essential tremor) in delta space while preserving natural intentional movements.",
    icon: Hand,
  },
  {
    title: "Gentle Button Magnetism & Bounce Guard",
    body: "Silently widens everyday button boundaries, steadies clicks for 180ms, blocks tremor double-clicks, and dampens scroll jitter.",
    icon: Magnet,
  },
  {
    title: "Hands-Free Gaze & Physician Reports",
    body: "Switch to webcam head/eye pointing anytime, and export longitudinal tremor spectra and medication logs for your neurologist.",
    icon: Eye,
  },
];

const STEPS = [
  {
    step: "Step 1",
    title: "Pick your comfort preset",
    body: "Choose Mild, Moderate, High stabilization, or Hands-Free mode with one large tap. No technical setup required.",
    icon: Compass,
  },
  {
    step: "Step 2",
    title: "Move naturally in any app",
    body: "ClearCursor runs quietly in your menu bar or system tray so browsers, email, and documents all feel calm and forgiving.",
    icon: HeartHandshake,
  },
  {
    step: "Step 3",
    title: "Bypass or toggle anytime",
    body: "Hold Alt/Option for momentary precision bypass, press Command/Ctrl+Shift+S to pause, or export reports before clinic visits.",
    icon: Eye,
  },
];

export function HomeOverview({
  stabilizationActive,
  onStartStabilizing,
  onOpenPlayground,
  onOpenControlDeck,
}: HomeOverviewProps) {
  return (
    <div className="space-y-12">
      {/* Hero Banner */}
      <section className="grid grid-cols-1 items-center gap-8 border-b-2 border-[var(--tc-border)] pb-10 lg:grid-cols-12">
        <div className="space-y-5 lg:col-span-7">
          <div className="flex items-center gap-4">
            <BrandLogo className="h-14 w-14 shrink-0" />
            <span className="text-lg font-bold text-[var(--tc-primary)]">
              ClearCursor Assistive Desktop
            </span>
          </div>

          <h2 className="text-3xl font-bold tracking-tight text-[var(--tc-ink)] sm:text-4xl">
            Steadier clicks and calmer computing for trembling hands.
          </h2>

          <p className="max-w-2xl text-lg leading-relaxed text-[var(--tc-ink-muted)]">
            ClearCursor works silently alongside every app on macOS and Windows to smooth 4-12 Hz tremors, block accidental double-clicks and drags, magnetize small buttons, and log objective tremor telemetry for your clinician.
          </p>

          <div className="flex flex-wrap items-center gap-4 pt-2">
            <button
              type="button"
              onClick={onStartStabilizing}
              className="inline-flex min-h-14 items-center gap-3 rounded-xl bg-[var(--tc-primary)] px-7 text-lg font-semibold text-white shadow-sm transition-colors hover:bg-[var(--tc-primary-hover)]"
            >
              <span>{stabilizationActive ? "Open Control Deck" : "Start Stabilizing"}</span>
              <ArrowRight className="h-5 w-5 shrink-0" aria-hidden="true" />
            </button>

            <button
              type="button"
              onClick={onOpenPlayground}
              className="inline-flex min-h-14 items-center gap-3 rounded-xl border border-[var(--tc-border-strong)] bg-[var(--tc-surface)] px-6 text-base font-semibold text-[var(--tc-ink)] shadow-sm transition-colors hover:bg-[var(--tc-mint)]"
            >
              <span>Try Sandbox Playground</span>
            </button>
          </div>
        </div>

        <div className="lg:col-span-5">
          <EditorialIllustration
            variant="workspace"
            title="Calm Everyday Desktop Control"
            subtitle="100% local delta-space tremor filtering across every app"
          />
        </div>
      </section>

      {/* Who It's For */}
      <section className="grid grid-cols-1 items-center gap-8 rounded-xl border border-[var(--tc-border)] bg-[var(--tc-mint)] p-6 shadow-[var(--tc-shadow)] lg:grid-cols-12 lg:p-8">
        <div className="lg:col-span-5">
          <EditorialIllustration
            variant="caregiver"
            title="Built for Patients, Caregivers & Clinicians"
            subtitle="Objective motor logs paired with medication timing"
          />
        </div>

        <div className="space-y-4 lg:col-span-7">
          <h2 className="text-2xl font-bold text-[var(--tc-ink)]">
            Built for people living with Parkinson&apos;s, essential tremor, and their caregivers
          </h2>
          <p className="text-base leading-relaxed text-[var(--tc-ink)]">
            Modern websites and desktop apps pack dozens of tiny icons, close buttons, and links close together. You should not have to fight your mouse or miss important health portals just because your hands are shaking.
          </p>
          <p className="text-base leading-relaxed text-[var(--tc-ink-muted)]">
            Everything in ClearCursor runs locally on your computer with zero cloud uploads. Caregivers can set presets once, log medication times, and export neurologist-ready PDFs directly from SQLite.
          </p>
          <div className="pt-2">
            <button
              type="button"
              onClick={onOpenControlDeck}
              className="inline-flex min-h-14 items-center gap-3 rounded-lg border-2 border-[var(--tc-primary)] bg-[var(--tc-surface)] px-6 text-base font-bold text-[var(--tc-primary)] hover:bg-[var(--tc-surface-alt)]"
            >
              <span>Choose Your Comfort Preset</span>
              <ArrowRight className="h-5 w-5 shrink-0" aria-hidden="true" />
            </button>
          </div>
        </div>
      </section>

      {/* The Daily Challenges We Solve */}
      <section aria-labelledby="challenges-heading" className="space-y-6">
        <div>
          <h2 id="challenges-heading" className="text-2xl font-bold text-[var(--tc-ink)]">
            The Daily Challenges We Solve
          </h2>
          <p className="mt-1 text-base text-[var(--tc-ink-muted)]">
            Why standard pointers feel exhausting when living with motor tremors.
          </p>
        </div>

        <div className="divide-y-2 divide-[var(--tc-border)] border-y-2 border-[var(--tc-border)]">
          {CHALLENGES.map((item) => {
            const Icon = item.icon;
            return (
              <div
                key={item.title}
                className="grid grid-cols-1 items-center gap-6 py-5 md:grid-cols-12"
              >
                <div className="flex items-start gap-4 md:col-span-8">
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-md bg-[var(--tc-alert-bg)] text-[var(--tc-alert)]">
                    <Icon className="h-6 w-6" aria-hidden="true" />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold text-[var(--tc-ink)]">{item.title}</h3>
                    <p className="mt-1 text-base text-[var(--tc-ink-muted)]">{item.body}</p>
                  </div>
                </div>

                <div className="rounded-xl border border-[var(--tc-border)] bg-[var(--tc-surface)] p-3 shadow-xs md:col-span-4">
                  <svg viewBox="0 0 220 56" className="h-12 w-full" aria-hidden="true">
                    {item.diagram === "hitbox" ? (
                      <>
                        <rect x="64" y="10" width="92" height="36" rx="6" fill="#DBEAFE" stroke="#1D4ED8" strokeWidth="1.5" strokeDasharray="5 3" />
                        <rect x="82" y="18" width="56" height="20" rx="4" fill="#0F2D59" />
                        <circle cx="72" cy="28" r="6" fill="none" stroke="#9F1239" strokeWidth="2.5" />
                        <circle cx="96" cy="28" r="5" fill="#1D4ED8" />
                      </>
                    ) : item.diagram === "freeze" ? (
                      <>
                        <circle cx="52" cy="28" r="14" fill="#DBEAFE" stroke="#1D4ED8" strokeWidth="2" />
                        <circle cx="52" cy="28" r="5" fill="#0F2D59" />
                        <path d="M72 28C96 14 114 42 140 28" stroke="#9F1239" strokeWidth="2.5" fill="none" strokeDasharray="4 3" />
                        <rect x="148" y="16" width="54" height="24" rx="4" fill="#0F2D59" />
                      </>
                    ) : (
                      <>
                        <path d="M16 38Q52 16 88 30T156 20T204 28" stroke="#1D4ED8" strokeWidth="3" fill="none" />
                        <circle cx="88" cy="30" r="5" fill="#0F2D59" />
                        <circle cx="156" cy="20" r="5" fill="#9F1239" />
                      </>
                    )}
                  </svg>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* How Our App Solves It */}
      <section aria-labelledby="solutions-heading" className="space-y-6">
        <div>
          <h2 id="solutions-heading" className="text-2xl font-bold text-[var(--tc-ink)]">
            How ClearCursor Helps in Real Time
          </h2>
          <p className="mt-1 text-base text-[var(--tc-ink-muted)]">
            Calm, assistive technology working quietly beneath your normal mouse or trackpad.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-8 md:grid-cols-3 md:divide-x-2 md:divide-[var(--tc-border)]">
          {SOLUTIONS.map((item, idx) => {
            const Icon = item.icon;
            return (
              <div key={item.title} className={idx > 0 ? "md:pl-8" : ""}>
                <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-md bg-[var(--tc-mint)] text-[var(--tc-primary)]">
                  <Icon className="h-6 w-6" aria-hidden="true" />
                </div>
                <h3 className="text-xl font-bold text-[var(--tc-ink)]">{item.title}</h3>
                <p className="mt-2 text-base text-[var(--tc-ink-muted)]">{item.body}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* How to Use (3 Easy Steps) */}
      <section aria-labelledby="steps-heading" className="border-t-2 border-[var(--tc-border)] pt-8">
        <h2 id="steps-heading" className="text-2xl font-bold text-[var(--tc-ink)]">
          How to Use in 3 Easy Steps
        </h2>

        <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-3">
          {STEPS.map((item) => {
            const Icon = item.icon;
            return (
              <div
                key={item.step}
                className="border-t-2 border-[var(--tc-primary)] pt-4"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-bold uppercase tracking-wide text-[var(--tc-primary)]">
                    {item.step}
                  </span>
                  <Icon className="h-5 w-5 text-[var(--tc-primary)]" aria-hidden="true" />
                </div>
                <h3 className="mt-3 text-xl font-bold text-[var(--tc-ink)]">{item.title}</h3>
                <p className="mt-2 text-base text-[var(--tc-ink-muted)]">{item.body}</p>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
