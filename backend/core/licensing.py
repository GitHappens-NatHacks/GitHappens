"""Modular edition & capability boundary for ClearCursor open-source and commercial distributions."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class EditionCapabilities:
    edition: str
    os_pointer_stabilization: bool = True
    gravity_wells: bool = True
    gaze_control: bool = True
    clinician_reports: bool = True
    event_diary: bool = True
    per_app_exclusions: bool = True
    multi_band_psd: bool = True


def get_edition_capabilities() -> EditionCapabilities:
    """Return active build capabilities (all core and clinical modules open in community build)."""
    edition = os.environ.get("CLEARCURSOR_EDITION", "open").strip().lower() or "open"
    return EditionCapabilities(edition=edition)
