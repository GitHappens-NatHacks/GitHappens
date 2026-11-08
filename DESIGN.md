---
name: AccessShift AI
description: Apple-leaning clinical accessibility shell in navy and light blue
colors:
  navy: "#0B1F3A"
  navy-deep: "#050B16"
  blue: "#2F6FED"
  blue-soft: "#D6E8F8"
  blue-wash: "#E8F0FE"
  ink: "#0B1F3A"
  ash: "#3E5370"
  muted: "#5A6F8A"
  paper: "#F5F5F7"
  paper-raised: "#FFFFFF"
  mist: "#D7E0EC"
  border: "#B8C9DE"
  gaze-focus: "#2F6FED"
  booking: "#0B1F3A"
typography:
  display:
    fontFamily: "Alumni Sans, Avenir Next Condensed, Helvetica Neue, Arial, sans-serif"
    fontSize: "56px"
    fontWeight: 200
    lineHeight: 1.05
    letterSpacing: "-0.03em"
  headline:
    fontFamily: "Alumni Sans, Avenir Next Condensed, Helvetica Neue, Arial, sans-serif"
    fontSize: "44px"
    fontWeight: 200
    lineHeight: 1.1
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Albert Sans, Avenir Next, Helvetica Neue, Arial, sans-serif"
    fontSize: "28px"
    fontWeight: 200
    lineHeight: 1.25
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Albert Sans, Avenir Next, Helvetica Neue, Arial, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "0em"
  label:
    fontFamily: "Albert Sans, Avenir Next, Helvetica Neue, Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "0.02em"
rounded:
  sm: "12px"
  md: "16px"
  lg: "18px"
  xl: "22px"
  pill: "980px"
spacing:
  xs: "8px"
  sm: "16px"
  md: "24px"
  lg: "36px"
  xl: "64px"
components:
  button-primary:
    backgroundColor: "{colors.navy}"
    textColor: "{colors.paper-raised}"
    rounded: "{rounded.pill}"
    padding: "14px 24px"
    height: "48px"
  button-secondary:
    backgroundColor: "{colors.paper-raised}"
    textColor: "{colors.navy}"
    rounded: "{rounded.pill}"
    padding: "12px 20px"
    height: "46px"
  nav-button:
    backgroundColor: "transparent"
    textColor: "{colors.ash}"
    padding: "14px 18px"
    height: "48px"
  card:
    backgroundColor: "{colors.paper-raised}"
    textColor: "{colors.navy}"
    rounded: "{rounded.lg}"
    padding: "28px"
  module-cell-active:
    backgroundColor: "{colors.blue-soft}"
    textColor: "{colors.navy}"
    rounded: "{rounded.md}"
    padding: "18px"
---

# Design System: AccessShift AI

## Overview

**Creative North Star: "Apple Store paper, clinical navy"**

Large photography bands first, then ultra-light display type, then one clear action. Top-centered navigation. Cool grey paper `#F5F5F7`. Navy ink and light-blue selection only. No yellow or gold brand accents. No left sidebar.

## Colors

Navy `#0B1F3A`, bright blue `#2F6FED`, soft blue `#D6E8F8`, Apple-like paper `#F5F5F7`, white raised surfaces. Booking confirmation uses navy with a blue close button.

## Typography

Alumni Sans ExtraLight for hero and page titles (56px scale). Albert Sans for UI. Short supporting sentences under titles, max width ~720px.

## Layout

Three-zone header: brand left, centered nav, status right. Content gutters 64px. Every Dashboard and settings section opens with a wide photo hero plus a four-tile gallery (five or more images). Controls sit below imagery with generous vertical rhythm so buttons and toggles do not collide.

## Elevation & Depth

Borderless white cards on cool paper. Photography carries depth. Pill-shaped primary actions. Flat module board stays the Dashboard signature.

## Do's and Don'ts

### Do
- Lead each section with large photos from `assets/ui/`.
- Keep navy / light blue / paper across Control Center, Demo Lab, and booking.
- Center top nav; keep targets large and spaced.

### Don't
- Use yellow, gold, green, or purple as resting brand color.
- Restore a left settings rail.
- Pack controls into the first viewport above the photo band.
