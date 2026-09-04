"""Render deterministic dark/light widget screenshots for the project website."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from providers import (
    AntigravityProvider,
    ClaudeProvider,
    CodexProvider,
    ModelUsage,
    UsageWindow,
)
from theme import apply_theme_setting
from ui.widget import SynapCapWidget

OUTPUT_DIR = ROOT / "docs" / "assets"


def _providers():
    return [
        CodexProvider({"id": "codex", "name": "Codex", "type": "codex"}),
        AntigravityProvider(
            {"id": "gemini", "name": "Gemini", "type": "antigravity"}
        ),
        ClaudeProvider({"id": "claude", "name": "Claude", "type": "claude"}),
    ]


def _usage() -> list[ModelUsage]:
    samples = (
        ("codex", "Codex", 62, 44, "2h 3m", "4d 20h"),
        ("gemini", "Gemini", 15, 9, "3h 41m", "5d 8h"),
        ("claude", "Claude", 55, 21, "1h 18m", "6d 15h"),
    )
    return [
        ModelUsage(
            provider_id,
            name,
            name,
            session,
            100,
            "%",
            windows=[
                UsageWindow("5시간", session, session_reset, 100 - session),
                UsageWindow("주간", weekly, weekly_reset, 100 - weekly),
            ],
        )
        for provider_id, name, session, weekly, session_reset, weekly_reset in samples
    ]


def render(theme: str, app: QApplication) -> Path:
    apply_theme_setting(theme)
    widget = SynapCapWidget(
        {
            "settings": {
                "widget_scale": "medium",
                "always_on_top": False,
                "usage_view": "ring",
                "ring_layout": "horizontal",
                "theme": theme,
            }
        },
        _providers(),
    )
    widget.update_data(_usage(), force=True)
    widget.show()
    app.processEvents()

    output = OUTPUT_DIR / f"widget-{theme}.png"
    if not widget.grab().save(str(output), "PNG"):
        raise RuntimeError(f"Could not save {output}")

    widget.close()
    widget.deleteLater()
    app.processEvents()
    return output


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    for theme in ("dark", "light"):
        print(render(theme, app).relative_to(ROOT))


if __name__ == "__main__":
    main()
