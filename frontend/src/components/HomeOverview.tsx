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
import { useState } from "react";
import { BrandLogo } from "./BrandLogo";

interface HomeOverviewProps {
  stabilizationActive: boolean;
  onStartStabilizing: () => void;
  onOpenPlayground: () => void;
  onOpenControlDeck: () => void;
}

interface SafePhotoProps {
  src: string;
  alt: string;
  fallbackTitle: string;
}

function SafePhoto({ src, alt, fallbackTitle }: SafePhotoProps) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <div
        role="img"
        aria-label={alt}
        className="flex h-full min-h-[240px] w-full flex-col items-center justify-center rounded-2xl border-2 border-[var(--tc-border)] bg-[var(--tc-mint)] p-6 text-center"
      >
        <svg viewBox="0 0 180 110" className="h-28 w-44" aria-hidden="true">
          <rect x="8" y="8" width="164" height="94" rx="16" fill="#FFFFFF" stroke="#014A35" strokeWidth="3" />
          <circle cx="58" cy="55" r="24" fill="#E3EFE9" stroke="#014A35" strokeWidth="2.5" strokeDasharray="5 4" />
          <circle cx="58" cy="55" r="9" fill="#014A35" />
          <path d="M98 44H152M98 62H138" stroke="#16201C" strokeWidth="5" strokeLinecap="round" />
        </svg>
        <p className="mt-3 text-base font-bold text-[var(--tc-ink)]">{fallbackTitle}</p>
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      onError={() => setFailed(true)}
      className="h-full min-h-[240px] w-full rounded-2xl border-2 border-[var(--tc-border)] object-cover"
    />
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
    title: "Accidental File Drags & Slips",
    body: "Natural finger tremor during a click often looks like a swipe to your computer, dragging windows or files by mistake.",
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
    body: "Filters fast 4-7 Hz involuntary hand shaking in real time while preserving your natural, intentional arm movements.",
    icon: Hand,
  },
  {
    title: "Gentle Button Magnetism",
    body: "Silently widens everyday macOS and Windows button boundaries and steadies the click for 180ms when you press.",
    icon: Magnet,
  },
  {
    title: "Hands-Free Head & Gaze Mode",
    body: "Turn on your webcam anytime to point cleanly with gentle head movement and select by resting still or blinking.",
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
    body: "TrueCursor runs quietly in your menu bar or system tray so browsers, email, and documents all feel calm and forgiving.",
    icon: HeartHandshake,
  },
  {
    step: "Step 3",
    title: "Switch modes anytime",
    body: "Press Command+Shift+S (Mac) or Ctrl+Shift+S (Windows), or open Hands-Free Gaze whenever your hands need a rest.",
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
    <div className="space-y-10">
      {/* Hero Banner */}
      <section className="grid grid-cols-1 items-center gap-8 rounded-3xl border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-6 lg:grid-cols-12 lg:p-10">
        <div className="space-y-5 lg:col-span-7">
          <div className="flex items-center gap-4">
            <BrandLogo className="h-14 w-14 shrink-0" />
            <span className="text-lg font-bold text-[var(--tc-primary)]">
              TrueCursor Assistive Desktop
            </span>
          </div>

          <h2 className="text-3xl font-bold tracking-tight text-[var(--tc-ink)] sm:text-4xl">
            Steadier clicks and calmer computing for trembling hands.
          </h2>

          <p className="text-lg leading-relaxed text-[var(--tc-ink-muted)]">
            TrueCursor works alongside every app on your computer to smooth hand tremors, prevent accidental drags, gently guide you onto small buttons, and give you reliable hands-free gaze control whenever you want it.
          </p>

          <div className="flex flex-wrap items-center gap-4 pt-2">
            <button
              type="button"
              onClick={onStartStabilizing}
              className="inline-flex min-h-14 items-center gap-3 rounded-xl bg-[var(--tc-primary)] px-7 text-lg font-bold text-white hover:bg-[var(--tc-primary-hover)]"
            >
              <span>{stabilizationActive ? "Open Control Deck" : "Start Stabilizing"}</span>
              <ArrowRight className="h-5 w-5 shrink-0" aria-hidden="true" />
            </button>

            <button
              type="button"
              onClick={onOpenPlayground}
              className="inline-flex min-h-14 items-center gap-3 rounded-xl border-2 border-[var(--tc-border-strong)] bg-[var(--tc-surface-alt)] px-6 text-base font-bold text-[var(--tc-ink)] hover:bg-[var(--tc-mint)]"
            >
              <span>Try Sandbox Playground</span>
            </button>
          </div>
        </div>

        <div className="lg:col-span-5">
          <SafePhoto
            src="https://images.unsplash.com/photo-1516321497487-e288fb19713f?auto=format&fit=crop&w=900&q=80"
            alt="Person comfortably using a laptop with relaxed posture on a warm wooden desk"
            fallbackTitle="Calm Everyday Desktop Control"
          />
        </div>
      </section>

      {/* Who It's For */}
      <section className="grid grid-cols-1 items-center gap-8 rounded-3xl border-2 border-[var(--tc-border)] bg-[var(--tc-mint)] p-6 lg:grid-cols-12 lg:p-8">
        <div className="lg:col-span-5">
          <SafePhoto
            src="https://images.unsplash.com/photo-1576765608535-5f04d1e3f289?auto=format&fit=crop&w=900&q=80"
            alt="Caregiver and older adult smiling together while reviewing information comfortably at home"
            fallbackTitle="Built for Patients & Caregivers"
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
            Everything in TrueCursor runs locally on your computer for complete privacy. Caregivers can help pick a preset once, save clinician progress summaries as clean PDFs, and leave daily controls simple and oversized.
          </p>
          <div className="pt-2">
            <button
              type="button"
              onClick={onOpenControlDeck}
              className="inline-flex min-h-14 items-center gap-3 rounded-xl border-2 border-[var(--tc-primary)] bg-[var(--tc-surface)] px-6 text-base font-bold text-[var(--tc-primary)] hover:bg-[var(--tc-surface-alt)]"
            >
              <span>Choose Your Comfort Preset</span>
              <ArrowRight className="h-5 w-5 shrink-0" aria-hidden="true" />
            </button>
          </div>
        </div>
      </section>

      {/* The Daily Challenges We Solve */}
      <section aria-labelledby="challenges-heading" className="space-y-4">
        <div>
          <h2 id="challenges-heading" className="text-2xl font-bold text-[var(--tc-ink)]">
            The Daily Challenges We Solve
          </h2>
          <p className="mt-1 text-base text-[var(--tc-ink-muted)]">
            Why standard pointers feel exhausting when living with motor tremors.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {CHALLENGES.map((item) => {
            const Icon = item.icon;
            return (
              <div
                key={item.title}
                className="flex flex-col justify-between rounded-2xl border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-6"
              >
                <div>
                  <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--tc-alert-bg)] text-[var(--tc-alert)]">
                    <Icon className="h-6 w-6" aria-hidden="true" />
                  </div>
                  <h3 className="text-xl font-bold text-[var(--tc-ink)]">{item.title}</h3>
                  <p className="mt-2 text-base text-[var(--tc-ink-muted)]">{item.body}</p>
                </div>

                {/* Plain visual diagram per challenge */}
                <div className="mt-5 rounded-xl border border-[var(--tc-border)] bg-[var(--tc-bg)] p-3">
                  <svg viewBox="0 0 220 56" className="h-12 w-full" aria-hidden="true">
                    {item.diagram === "hitbox" ? (
                      <>
                        <rect x="64" y="10" width="92" height="36" rx="8" fill="#E3EFE9" stroke="#014A35" strokeWidth="1.5" strokeDasharray="5 3" />
                        <rect x="82" y="18" width="56" height="20" rx="5" fill="#014A35" />
                        <circle cx="72" cy="28" r="6" fill="none" stroke="#8C2113" strokeWidth="2.5" />
                        <circle cx="96" cy="28" r="5" fill="#014A35" />
                      </>
                    ) : item.diagram === "freeze" ? (
                      <>
                        <circle cx="52" cy="28" r="14" fill="#E3EFE9" stroke="#014A35" strokeWidth="2" />
                        <circle cx="52" cy="28" r="5" fill="#014A35" />
                        <path d="M72 28C96 14 114 42 140 28" stroke="#8C2113" strokeWidth="2.5" fill="none" strokeDasharray="4 3" />
                        <rect x="148" y="16" width="54" height="24" rx="6" fill="#014A35" />
                      </>
                    ) : (
                      <>
                        <path d="M16 38Q52 16 88 30T156 20T204 28" stroke="#014A35" strokeWidth="3" fill="none" />
                        <circle cx="88" cy="30" r="5" fill="#014A35" />
                        <circle cx="156" cy="20" r="5" fill="#8C2113" />
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
      <section aria-labelledby="solutions-heading" className="space-y-4">
        <div>
          <h2 id="solutions-heading" className="text-2xl font-bold text-[var(--tc-ink)]">
            How TrueCursor Helps in Real Time
          </h2>
          <p className="mt-1 text-base text-[var(--tc-ink-muted)]">
            Calm, assistive technology working quietly beneath your normal mouse or trackpad.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {SOLUTIONS.map((item) => {
            const Icon = item.icon;
            return (
              <div
                key={item.title}
                className="rounded-2xl border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-6"
              >
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--tc-mint)] text-[var(--tc-primary)]">
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
      <section
        aria-labelledby="steps-heading"
        className="rounded-3xl border-2 border-[var(--tc-border)] bg-[var(--tc-surface)] p-6 lg:p-8"
      >
        <h2 id="steps-heading" className="text-2xl font-bold text-[var(--tc-ink)]">
          How to Use in 3 Easy Steps
        </h2>

        <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-3">
          {STEPS.map((item) => {
            const Icon = item.icon;
            return (
              <div
                key={item.step}
                className="rounded-2xl border-2 border-[var(--tc-border)] bg-[var(--tc-bg)] p-5"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-bold uppercase tracking-wide text-[var(--tc-primary)]">
                    {item.step}
                  </span>
                  <Icon className="h-6 w-6 text-[var(--tc-primary)]" aria-hidden="true" />
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
