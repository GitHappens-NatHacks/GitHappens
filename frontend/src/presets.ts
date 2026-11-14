import type { SettingsUpdate } from "./types/telemetry";

export type ClinicalPresetId = "mild" | "moderate" | "high" | "hands_free";

export interface ClinicalPreset {
  id: ClinicalPresetId;
  label: string;
  tagline: string;
  clinicalNote: string;
  updates: SettingsUpdate;
}

export const CLINICAL_PRESETS: ClinicalPreset[] = [
  {
    id: "mild",
    label: "Mild Tremor (Responsive)",
    tagline: "Light smoothing that stays crisp for fast, confident movement.",
    clinicalNote: "Best during ON medication periods or mild essential tremor.",
    updates: {
      profile: "mild",
      assistance_enabled: true,
      steady_hand: true,
      gaze_control: false,
      tremor_strength: 65,
      one_euro_min_cutoff: 0.95,
      one_euro_beta: 0.008,
      anti_drag: true,
      click_freeze_ms: 140,
      gravity_wells: true,
      gravity_strength: 25,
    },
  },
  {
    id: "moderate",
    label: "Moderate Tremor (Balanced)",
    tagline: "Everyday balance of steady clicking and natural pointer travel.",
    clinicalNote: "Recommended starting preset for steady web browsing and forms.",
    updates: {
      profile: "moderate",
      assistance_enabled: true,
      steady_hand: true,
      gaze_control: false,
      tremor_strength: 100,
      one_euro_min_cutoff: 0.6,
      one_euro_beta: 0.004,
      anti_drag: true,
      click_freeze_ms: 180,
      gravity_wells: true,
      gravity_strength: 38,
    },
  },
  {
    id: "high",
    label: "High Tremor (Maximum Stabilization)",
    tagline: "Deep 4-7 Hz damping, full 180ms click-freeze, and stronger magnetism.",
    clinicalNote: "Designed for OFF medication periods or pronounced resting tremors.",
    updates: {
      profile: "high",
      assistance_enabled: true,
      steady_hand: true,
      gaze_control: false,
      tremor_strength: 145,
      one_euro_min_cutoff: 0.35,
      one_euro_beta: 0.002,
      anti_drag: true,
      click_freeze_ms: 240,
      gravity_wells: true,
      gravity_strength: 55,
    },
  },
  {
    id: "hands_free",
    label: "Hands-Free (Gaze Mode)",
    tagline: "Use gentle head or eye movement with dwell or deliberate blink clicking.",
    clinicalNote: "Ideal when resting your hands or experiencing severe fatigue.",
    updates: {
      profile: "hands_free",
      assistance_enabled: true,
      steady_hand: false,
      gaze_control: true,
      gaze_dwell_ms: 1100,
      blink_select: true,
      gravity_wells: false,
    },
  },
];
