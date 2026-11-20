"""Read public macOS notch geometry; never guess or request screen access."""
import sys

from PySide6.QtCore import QRect


def notch_rect() -> QRect | None:
    if sys.platform != "darwin":
        return None
    try:
        from AppKit import NSScreen

        screens = list(NSScreen.screens())
        if not screens:
            return None
        primary_frame = screens[0].frame()
        desktop_top = primary_frame.origin.y + primary_frame.size.height
        for screen in screens:
            if not screen.respondsToSelector_("safeAreaInsets"):
                continue
            inset = screen.safeAreaInsets().top
            left = screen.auxiliaryTopLeftArea()
            right = screen.auxiliaryTopRightArea()
            if inset <= 0 or left.size.width <= 0 or right.size.width <= 0:
                continue
            x = left.origin.x + left.size.width
            width = right.origin.x - x
            frame = screen.frame()
            y = desktop_top - (frame.origin.y + frame.size.height)
            if width > 0:
                return QRect(round(x), round(y), round(width), round(inset))
    except (ImportError, AttributeError, RuntimeError, TypeError, ValueError):
        # Unsupported runtime/geometry falls back to the existing menu-bar icon.
        return None
    return None
