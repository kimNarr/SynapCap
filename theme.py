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

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

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
    "usage_calm": "#8087A0",       # < 60 % — muted, plenty of headroom
    "usage_ok": "#89B4FA",         # 60-74 % — worth noting
    "usage_warn": "#FAB387",       # 75-89 % — amber, closing in
    "usage_crit": "#F38BA8",       # >= 90 % — red, plus ▲
    "warn_soft": "#F9E2AF",        # "waiting" badge, privacy note
    "good": "#A6E3A1",
    "danger": "#F38BA8",
    "danger_soft": "#EBA0AC",      # power / close glyphs
    "compact_value": "#F8FAFC",    # calm compact %
    # ── component specifics ──────────────────────────────────────────
    "focus_tab_bg": "#10131A",
    "focus_tab_selected_bg": "#151B25",
    "focus_tab_edge": "#252B38",
    "focus_metric_bg": "#0B0D12",
    "focus_metric_edge": "#202531",
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
    "tooltip_bg": "#171A21",
    "tooltip_fg": "#F8FAFC",
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
    # ── logo ─────────────────────────────────────────────────────────
    "logo_mark": "#89B4FA",  # unified with `accent` — one blue everywhere
    "logo_text": "#EAEEF7",
    "logo_track": "#363B4D",
}

# Catppuccin Latte-inspired light surfaces.  Text and semantic colours are
# deliberately darker than the upstream pastels so normal-size copy clears
# WCAG AA contrast on the surfaces where it is used.
LIGHT: dict[str, str] = {
    # ── grounds & surfaces ───────────────────────────────────────────
    "ground": "#F7F8FB",
    "ground_deep": "#E9ECF2",
    "surface": "#FFFFFF",
    "hover": "#E1E5ED",
    "panel": "#F1F3F7",
    "panel_sunken": "#E8EBF1",
    "titlebar": "#E4E8EF",
    "control": "#E2E6EE",
    "control_edge": "#9AA3B5",
    "control_hover": "#CDD3DE",
    # ── lines ────────────────────────────────────────────────────────
    "line": "#C8CEDA",
    "line_soft": "#D2D7E0",
    "line_strong": "#AEB6C6",
    "separator": "#D8DCE5",
    "frame_border": "#7B879D",
    "frame_border_deep": "#69768D",
    "scrollbar": "#9AA3B5",
    "scrollbar_hover": "#7F899E",
    # ── ink ──────────────────────────────────────────────────────────
    "ink": "#303446",
    "ink_bright": "#292C3C",
    "ink_mid": "#4C4F69",
    "ink_dim": "#5C5F77",
    "ink_faint": "#5C5F77",
    "ink_faintest": "#6C6F85",
    # ── brand + semantic ─────────────────────────────────────────────
    "accent": "#1857C9",
    "accent_soft": "#244F9E",
    "on_accent": "#FFFFFF",
    "usage_calm": "#7C8296",       # < 60 % — muted, plenty of headroom
    "usage_ok": "#1857C9",         # 60-74 % — worth noting
    "usage_warn": "#C2410C",       # 75-89 % — burnt orange (AA on light, not the old ocher)
    "usage_crit": "#B42352",       # >= 90 % — red, plus ▲
    "warn_soft": "#805400",
    "good": "#2E6F37",
    "danger": "#B42352",
    "danger_soft": "#A6294D",
    "compact_value": "#303446",
    # ── component specifics ──────────────────────────────────────────
    "focus_tab_bg": "#EEF1F5",
    "focus_tab_selected_bg": "#F7FAFF",
    "focus_tab_edge": "#D4DAE4",
    "focus_metric_bg": "#FFFFFF",
    "focus_metric_edge": "#D8DDE6",
    "ring_track": "#C8CEDA",
    "skeleton": "#E0E4EC",
    "skeleton_strong": "#D5DAE4",
    "version_fg": "#4C4F69",
    "version_bg": "#E2E6EE",
    "version_edge": "#AEB6C6",
    "cli_badge_fg": "#315B9B",
    "cli_badge_edge": "#7E9BC7",
    "badge_waiting_bg": "#F2E8CF",
    "badge_error_bg": "#F4DDE5",
    "badge_ok_bg": "#DDECDD",
    "spinner_track": "#C8CEDA",
    "tooltip_bg": "#171A21",
    "tooltip_fg": "#F8FAFC",
    # ── provider brand chips ─────────────────────────────────────────
    "provider_codex_fg": "#4C4F69",
    "provider_codex_bg": "#E4E8F5",
    "provider_gemini_fg": "#356EDC",
    "provider_gemini_bg": "#FFFFFF",
    "provider_claude_fg": "#A84B2F",
    "provider_claude_bg": "#F3E3DE",
    "provider_fallback_fg": "#303446",
    "provider_fallback_bg": "#E2E6EE",
    # ── settings dialog specifics ────────────────────────────────────
    "settings_border": "#7B879D",
    "text_bright": "#1E2230",
    "accent_bright": "#174BAA",
    "control_disabled_bg": "#ECEEF3",
    "control_disabled_fg": "#747C8E",
    "preview_bg": "#E1E8F5",
    "preview_edge": "#6F8FC6",
    "preview_hover_bg": "#D4DFF1",
    "privacy_note_bg": "rgba(128, 84, 0, 0.08)",
    "privacy_note_edge": "rgba(128, 84, 0, 0.28)",
    # ── logo ─────────────────────────────────────────────────────────
    "logo_mark": "#1857C9",  # unified with `accent` — one blue everywhere
    "logo_text": "#303446",
    "logo_track": "#D5D9E4",
}

PALETTES: dict[str, dict[str, str]] = {"dark": DARK, "light": LIGHT}

_active: dict[str, str] = dict(DARK)
_listeners: list = []
_setting = "dark"


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


def resolve_system_theme() -> str:
    """Resolve Qt's current OS colour scheme with a conservative fallback."""
    app = QApplication.instance()
    if app is None:
        return "dark"
    scheme = app.styleHints().colorScheme()
    if scheme == Qt.ColorScheme.Light:
        return "light"
    return "dark"


def apply_theme_setting(setting: str) -> None:
    """Apply a persisted ``dark``/``light``/``auto`` preference."""
    global _setting
    _setting = setting if setting in {"dark", "light", "auto"} else "dark"
    set_theme(resolve_system_theme() if _setting == "auto" else _setting)


def current_setting() -> str:
    """Return the persisted preference rather than the resolved palette."""
    return _setting


def t(name: str) -> str:
    """Return the active value for a token."""
    return _active[name]


def palette() -> dict[str, str]:
    """A copy of the active palette, for ``QSS_TEMPLATE % palette()``."""
    return dict(_active)
