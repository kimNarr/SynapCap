"""Colour tokens for every SynapCap surface.

This is the extraction step: ``DARK`` holds exactly the values that were
hard-coded across ``ui/`` before, so wiring the widgets to it is a visual
no-op.  A light palette and OS-driven switching build on top of this.

Usage::

    from theme import t
    label.setStyleSheet(f"color: {t('ink')};")

or, for a Qt style sheet with literal ``{}`` blocks, keep ``%(name)s``
placeholders and format with :func:`palette`::

    widget.setStyleSheet(QSS_TEMPLATE % palette())
"""

from __future__ import annotations

DARK: dict[str, str] = {
    # ── grounds & surfaces ───────────────────────────────────────────
    "ground": "#050608",          # widget frame, tray menu
    "ground_deep": "#020304",     # compact bar / compact frame
    "surface": "#090A0D",         # inner providers frame, settings inputs
    "hover": "#171B23",           # icon-button hover, tray selected row
    "panel": "#14151E",           # settings frame
    "panel_sunken": "#0F1017",    # settings group box / scroll gutter
    "titlebar": "#0D0E14",        # settings title bar
    "control": "#232637",         # settings inputs / buttons
    "control_edge": "#3C4156",    # settings control borders (the workhorse)
    "control_hover": "#3C4156",
    # ── lines ────────────────────────────────────────────────────────
    "line": "#272C38",
    "line_soft": "#292D3C",
    "line_strong": "#303746",     # tray menu / settings outer edges
    "separator": "#20242D",        # between provider cards
    "frame_border": "#4A5266",     # 2px widget outline
    "frame_border_deep": "#596176",  # compact outline
    "scrollbar": "#45475A",
    "scrollbar_hover": "#4A5168",
    # ── ink ──────────────────────────────────────────────────────────
    "ink": "#CDD6F4",
    "ink_bright": "#BAC2DE",       # window label in a usage tile
    "ink_mid": "#A6ADC8",
    "ink_dim": "#8087A0",          # reset countdown
    "ink_faint": "#7F849C",
    "ink_faintest": "#5B6274",     # the "/" between compact values
    # ── brand + semantic ─────────────────────────────────────────────
    "accent": "#89B4FA",
    "accent_soft": "#AFCBFF",
    "on_accent": "#11111B",        # text on an accent fill
    "usage_ok": "#89B4FA",
    "usage_warn": "#FAB387",       # 60-79 %
    "usage_crit": "#F38BA8",       # >= 80 %
    "warn_soft": "#F9E2AF",        # "waiting" badge, privacy note
    "good": "#A6E3A1",
    "danger": "#F38BA8",
    "danger_soft": "#EBA0AC",      # power / close glyphs
    "compact_value": "#F8FAFC",    # calm compact %
    # ── component specifics ──────────────────────────────────────────
    "bar_track": "#1C2130",
    "bar_track_edge": "#3A4152",
    "segment_off": "#23283A",
    "ring_track": "#2B303D",
    "skeleton": "#1A1F2A",
    "skeleton_strong": "#1B212D",
    "version_fg": "#97A0B6",
    "version_bg": "#252538",
    "version_edge": "#3A3F55",
    "cli_badge_fg": "#8397BE",
    "cli_badge_edge": "#2E3550",
    "badge_waiting_bg": "#323040",
    "badge_error_bg": "#3B2735",
    "badge_ok_bg": "#26372F",
    "spinner_track": "#2B303D",
    # ── provider brand chips ─────────────────────────────────────────
    "provider_codex_fg": "#B4BEFE",
    "provider_codex_bg": "#252B3F",
    "provider_gemini_fg": "#4285F4",
    "provider_gemini_bg": "#FFFFFF",
    "provider_claude_fg": "#FAB387",
    "provider_claude_bg": "#3A2B2B",
    "provider_fallback_fg": "#CDD6F4",
    "provider_fallback_bg": "#202531",
    # ── settings dialog specifics ────────────────────────────────────
    "settings_border": "#353C4B",   # 2px dialog outline
    "text_bright": "#FFFFFF",        # focused input / hovered button text
    "accent_bright": "#B4BEFE",      # add-provider hover edge
    "control_disabled_bg": "#12151C",
    "control_disabled_fg": "#697187",
    "preview_bg": "#1B2030",
    "preview_edge": "#5B80C7",
    "preview_hover_bg": "#252D43",
    "privacy_note_bg": "rgba(249, 226, 175, 0.06)",
    "privacy_note_edge": "rgba(249, 226, 175, 0.2)",
    # ── logo (fixed across themes; the mark carries its own contrast) ─
    "logo_mark": "#5B8DEF",
}

PALETTES: dict[str, dict[str, str]] = {"dark": DARK}

_active: dict[str, str] = dict(DARK)
_listeners: list = []


def on_change(callback) -> None:
    """Register a zero-arg callback to run whenever the palette swaps
    (e.g. an ``lru_cache.cache_clear`` or a widget rebuild)."""
    _listeners.append(callback)


def set_theme(name: str) -> None:
    """Swap the active palette. Unknown names fall back to dark."""
    _active.clear()
    _active.update(PALETTES.get(name, DARK))
    for callback in _listeners:
        callback()


def t(name: str) -> str:
    """Return the active value for a token."""
    return _active[name]


def palette() -> dict[str, str]:
    """A copy of the active palette, for ``QSS_TEMPLATE % palette()``."""
    return dict(_active)
