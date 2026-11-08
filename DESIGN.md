---
name: AccessShift AI
description: Soft clinical control console for adaptive accessibility settings
colors:
  primary: "#684BE2"
  primary-deep: "#5537CB"
  primary-soft: "#F0EDFF"
  primary-ink: "#5038D4"
  logo-mark: "#7456EB"
  hero-start: "#4932AF"
  hero-mid: "#6550DE"
  hero-end: "#9276F1"
  success: "#156F5A"
  success-soft: "#E8F7F0"
  success-ink: "#18785F"
  warning-ink: "#966222"
  warning-soft: "#FFF0D9"
  ink: "#18233C"
  ink-strong: "#202B46"
  ink-muted: "#61708A"
  ink-subtle: "#75819A"
  sidebar: "#151A30"
  sidebar-border: "#272C48"
  sidebar-nav: "#C6CEE3"
  sidebar-nav-active: "#2D2C54"
  nav-accent: "#AE9AFF"
  focus-ring: "#8C72FF"
  surface: "#FFFFFF"
  canvas: "#F6F7FB"
  inner-surface: "#F2F3FD"
  border: "#E4E8F2"
  border-strong: "#D6DDEF"
  gaze-amber: "#FFD54F"
  gaze-ink: "#0B1F1A"
  booking-green: "#0F7A4A"
typography:
  display:
    fontFamily: "Segoe UI, Helvetica Neue, Arial, sans-serif"
    fontSize: "30px"
    fontWeight: 800
    lineHeight: 1.15
    letterSpacing: "0em"
  headline:
    fontFamily: "Segoe UI, Helvetica Neue, Arial, sans-serif"
    fontSize: "25px"
    fontWeight: 800
    lineHeight: 1.2
    letterSpacing: "0em"
  title:
    fontFamily: "Segoe UI, Helvetica Neue, Arial, sans-serif"
    fontSize: "18px"
    fontWeight: 800
    lineHeight: 1.25
    letterSpacing: "0em"
  body:
    fontFamily: "Segoe UI, Helvetica Neue, Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: "0em"
  label:
    fontFamily: "Segoe UI, Helvetica Neue, Arial, sans-serif"
    fontSize: "10px"
    fontWeight: 800
    lineHeight: 1.3
    letterSpacing: "1px"
rounded:
  sm: "10px"
  md: "11px"
  lg: "14px"
  xl: "17px"
  hero: "20px"
  pill: "11px"
  switch: "12px"
spacing:
  xs: "6px"
  sm: "12px"
  md: "18px"
  lg: "28px"
  xl: "34px"
  sidebar: "246px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.surface}"
    rounded: "{rounded.md}"
    padding: "12px 18px"
    height: "42px"
    typography: "{typography.body}"
  button-primary-hover:
    backgroundColor: "{colors.primary-deep}"
    textColor: "{colors.surface}"
    rounded: "{rounded.md}"
    padding: "12px 18px"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "#465676"
    rounded: "{rounded.md}"
    padding: "10px 15px"
    height: "42px"
  button-secondary-hover:
    backgroundColor: "#F5F2FF"
    textColor: "#4F33BD"
    rounded: "{rounded.md}"
    padding: "10px 15px"
  button-hero:
    backgroundColor: "{colors.surface}"
    textColor: "#4F34C7"
    rounded: "{rounded.md}"
    padding: "11px 17px"
  button-preset:
    backgroundColor: "{colors.surface}"
    textColor: "#25314D"
    rounded: "15px"
    padding: "17px"
  button-preset-checked:
    backgroundColor: "#F5F0FF"
    textColor: "#4F34BB"
    rounded: "15px"
    padding: "17px"
  nav-button:
    backgroundColor: "transparent"
    textColor: "{colors.sidebar-nav}"
    rounded: "{rounded.sm}"
    padding: "11px 12px"
    height: "40px"
  nav-button-active:
    backgroundColor: "{colors.sidebar-nav-active}"
    textColor: "{colors.surface}"
    rounded: "{rounded.sm}"
    padding: "11px 12px"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink-strong}"
    rounded: "{rounded.xl}"
    padding: "20px"
  inner-card:
    backgroundColor: "{colors.inner-surface}"
    textColor: "{colors.ink-strong}"
    rounded: "{rounded.lg}"
    padding: "12px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "#243450"
    rounded: "{rounded.sm}"
    padding: "11px 13px"
  input-focus:
    backgroundColor: "{colors.surface}"
    textColor: "#243450"
    rounded: "{rounded.sm}"
    padding: "11px 13px"
  pill:
    backgroundColor: "{colors.primary-soft}"
    textColor: "#5340C7"
    rounded: "{rounded.sm}"
    padding: "5px 11px"
  good-pill:
    backgroundColor: "#E6F8EF"
    textColor: "{colors.success-ink}"
    rounded: "{rounded.pill}"
    padding: "6px 11px"
  hero:
    backgroundColor: "{colors.hero-mid}"
    textColor: "{colors.surface}"
    rounded: "{rounded.hero}"
    padding: "20px"
---

# Design System: AccessShift AI

## Overview

**Creative North Star: "The Adaptive Care Console"**

AccessShift AI's shipped shell is a soft clinical control console: a dark indigo navigation rail against a cool lilac-gray canvas, white card surfaces, and a violet accent used for brand, selection, and primary actions. Density is comfortable for settings work (wide content gutters, roomy cards, 40–42px controls) rather than dense data tables. The aesthetic is native desktop PySide6 chrome, not a marketing site: QSS object names (`primaryButton`, `card`, `navButton`) carry the look.

Depth comes from tonal contrast (sidebar vs canvas vs white cards) and hairline borders, not drop shadows. Profile modes temporarily override the shell: GazeControl enlarges targets with high-contrast black borders and amber dwell highlight; calibration uses a near-black fullscreen stage; booking success floods the dialog with solid green. Those modes are interaction overlays on the Adaptive Care Console, not alternate brand worlds.

**Key Characteristics:**
- Cool lilac-gray canvas (`#F6F7FB`) with white cards and a midnight sidebar (`#151A30`)
- Single violet accent family for primary actions, focus, and selection
- Soft radii (10–20px) and 1px cool borders; flat surfaces at rest
- One UI sans stack across roles; heavy weights (750–800) for titles and labels
- Accessibility-first focus rings (`#8C72FF` / `#C4B8FF`) and large minimum control heights

## Colors

A cool violet-on-paper palette with teal success and amber gaze overlays.

### Primary
- **Console Violet** (`#684BE2`): Primary buttons, slider fills, brand actions. Hover deepens to `#5537CB`. Soft fill `#F0EDFF` for pills and secondary hover washes. Ink numbers use `#5038D4`. Logo tile uses `#7456EB`. Hero cards wash `#4932AF` → `#6550DE` → `#9276F1`.

### Secondary
- **Care Teal** (`#156F5A` / `#18785F`): Status badges, good pills, booking success relative tones. Soft grounds `#E8F7F0` / `#E6F8EF`. Full-bleed booking dialog uses `#0F7A4A`.

### Tertiary
- **Gaze Amber** (`#FFD54F`): Live dwell / target highlight while GazeControl is applied; pairs with near-black gaze ink (`#0B1F1A`) and thick borders. Not used as a resting brand accent in the shell.

### Neutral
- **Ink Navy** (`#18233C`): Page titles and appRoot text.
- **Body Slate** (`#61708A` / `#67758F`): Descriptions and body copy.
- **Canvas Mist** (`#F6F7FB`): Main workspace background.
- **Card White** (`#FFFFFF`): Cards, top bar, footer, inputs.
- **Inner Lilac** (`#F2F3FD`): Nested cards on light surfaces.
- **Hairline Cool** (`#E4E8F2` / `#E7EAF2`): Card and chrome borders.
- **Sidebar Midnight** (`#151A30`): Left rail; nav text `#C6CEE3`; active rail `#2D2C54` with `#AE9AFF` leading edge.

### Named Rules
**The One Violet Rule.** Resting chrome uses at most one violet accent family per view (primary button, selected preset, or nav edge). Soft lavender fills support it; they do not compete as a second brand hue.

**The Mode Overlay Rule.** Gaze amber, calibration near-black, and booking green are temporary full-context overrides. After the mode ends, the console palette returns unchanged.

## Typography

**Display Font:** Segoe UI (with Helvetica Neue, Arial, sans-serif)
**Body Font:** Segoe UI (with Helvetica Neue, Arial, sans-serif)
**Label/Mono Font:** Same stack; labels use weight 800 and letter-spacing rather than a separate family

**Character:** A single native UI sans, weighted hard for section hierarchy. Titles read as product chrome, not editorial display type.

### Hierarchy
- **Display** (800, 30px, tight): `pageTitle` on settings pages.
- **Headline** (800, 25px): `heroTitle` inside gradient hero cards.
- **Title** (800, 18px / 750, 14px): `sectionTitle` and `cardTitle`.
- **Body** (400–650, 12–13px): `pageDescription`, `bodyText`, button labels at 12px / weight 750.
- **Label** (800, 9–11px, letter-spacing ~0.7–1.1px, often uppercase): top bar, side sections, pills, micro copy.

### Named Rules
**The Weight Ladder Rule.** Hierarchy is carried by weight and size on one family. Do not introduce a second display face for product chrome.

## Layout

Desktop shell: fixed 246px sidebar + flexible workspace. Default window about 1220×810; minimum 940×650. Top bar and footer share 33px horizontal inset; scroll content uses 34 / 29 / 34 / 38 margins with 18px section spacing. Cards default to 20px internal padding and 12px stack spacing; preference rows use ~19×16 padding. Stat grids space ~12–13px. Controls target ≥40px height (buttons 42px, nav 40px). SmartInterface / portal demo surfaces may scale type and padding from accessibility preferences; the console tokens above remain the default shell.

## Elevation & Depth

Flat by default. Separation uses background steps (sidebar → canvas → white card → inner lilac) and 1px cool borders. Card hover only shifts border color (`#D5D8EF`); no drop shadows appear in the shell QSS.

### Named Rules
**The Border-Not-Shadow Rule.** Surfaces stay flat. Depth is tonal and edged, never offset-shadowed.

## Shapes

Soft continuous rounding: inputs and pills ~10–11px, buttons 11px, inner cards 14px, primary cards 17px, hero 20px, logo mark 13px, preset tiles 15px. Switch track ~11.5px radius on a 48×27 control. Borders are 1px at rest; focus and selected presets use 2px violet strokes. Gaze targets thicken to 3–6px black borders while gaze mode is on.

## Components

### Buttons
- **Shape:** Soft rectangle (11px radius); minimum height 42px
- **Primary:** White text on `#684BE2`; hover `#5537CB`
- **Secondary:** White fill, `#D6DDEF` border, slate text; hover lavender wash and violet text
- **Hero:** White fill on gradient hero; text `#4F34C7`; hover `#F0EDFF`
- **Preset:** Large left-aligned tiles (15px radius, 17px pad, ≥91px tall when used as profile choices); checked border `#7050E6` on `#F5F0FF`
- **Hover / Focus:** Focus ring 2px `#8C72FF` (nav focus `#C4B8FF`); disabled `#F0F2F8` / `#A1AAC0`

### Chips
- **Style:** Soft pills: violet (`#F0EDFF` / `#5340C7`), good (`#E6F8EF` / `#18785F`), warning (`#FFF0D9` / `#966222`)
- **State:** Status and meta only; not primary navigation

### Cards / Containers
- **Corner Style:** 17px outer cards; 14px inner; 20px hero
- **Background:** White or inner lilac; hero uses the violet gradient
- **Shadow Strategy:** None; border `#E4E8F2`
- **Border:** 1px cool; hover lightens border only
- **Internal Padding:** 18–20px typical; preference rows 19×16

### Inputs / Fields
- **Style:** White fill, `#D6DDEB` border, 10px radius, 11×13 padding, 13px type
- **Focus:** 2px `#7154E5` border
- **Combo / Slider:** Matching radius; slider groove 6px `#E6E8F3`, handle 18px `#6B4DE4`

### Navigation
- Dark sidebar; transparent nav buttons with 10px radius and left accent edge. Hover `#242B47`; checked `#2D2C54` with 3px `#AE9AFF` leading bar. Section labels are 10px uppercase muted slate on the rail.

### Switch
- 48×27 track; off `#D6DCEA`, on `#674BE8`; white thumb; focus outline `#8E79EF`.

### Gaze Target Button (signature overlay)
- White fill, 3px `#0B1F1A` border, 12px radius, 22px / weight 700, min height 96px. Property `gazeTarget=true` fills `#FFD54F` with 6px border. Restores shell styles when gaze mode ends.

### Booking Confirmation (signature overlay)
- Full dialog `#0F7A4A`; light text; white close button 14px radius, min height 64px, 20px type.

## Do's and Don'ts

### Do:
- **Do** keep the midnight sidebar / mist canvas / white card sandwich for new shell pages.
- **Do** use Console Violet for primary actions and 2px violet focus rings on interactive controls.
- **Do** keep resting surfaces flat with 1px cool borders and the soft radius scale (10–20px).
- **Do** enlarge targets and apply gaze amber only while GazeControl (or equivalent dwell UI) is active.

### Don't:
- **Don't** introduce a second resting brand hue beside the violet family and teal status.
- **Don't** add drop shadows to cards or chrome to fake depth.
- **Don't** leave gaze, calibration, or booking-green styles applied after those modes end.
- **Don't** shrink primary controls below ~40px height in the shell.
