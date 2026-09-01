import math
import sys
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap

try:
    from PySide6.QtSvg import QSvgRenderer
except ImportError:  # pragma: no cover - PySide6 desktop builds include QtSvg.
    QSvgRenderer = None


# Brand paths are pinned from Simple Icons so the packaged app never fetches
# remote assets. OpenAI: v15.21.0, Google Gemini: v16.21.0,
# Claude Code: v16.28.0 (CC0-1.0).
_PROVIDER_BRANDS = {
    "codex": {
        "path": "M22.2819 9.8211a5.9847 5.9847 0 0 0-.5157-4.9108 6.0462 6.0462 0 0 0-6.5098-2.9A6.0651 6.0651 0 0 0 4.9807 4.1818a5.9847 5.9847 0 0 0-3.9977 2.9 6.0462 6.0462 0 0 0 .7427 7.0966 5.98 5.98 0 0 0 .511 4.9107 6.051 6.051 0 0 0 6.5146 2.9001A5.9847 5.9847 0 0 0 13.2599 24a6.0557 6.0557 0 0 0 5.7718-4.2058 5.9894 5.9894 0 0 0 3.9977-2.9001 6.0557 6.0557 0 0 0-.7475-7.0729zm-9.022 12.6081a4.4755 4.4755 0 0 1-2.8764-1.0408l.1419-.0804 4.7783-2.7582a.7948.7948 0 0 0 .3927-.6813v-6.7369l2.02 1.1686a.071.071 0 0 1 .038.052v5.5826a4.504 4.504 0 0 1-4.4945 4.4944zm-9.6607-4.1254a4.4708 4.4708 0 0 1-.5346-3.0137l.142.0852 4.783 2.7582a.7712.7712 0 0 0 .7806 0l5.8428-3.3685v2.3324a.0804.0804 0 0 1-.0332.0615L9.74 19.9502a4.4992 4.4992 0 0 1-6.1408-1.6464zM2.3408 7.8956a4.485 4.485 0 0 1 2.3655-1.9728V11.6a.7664.7664 0 0 0 .3879.6765l5.8144 3.3543-2.0201 1.1685a.0757.0757 0 0 1-.071 0l-4.8303-2.7865A4.504 4.504 0 0 1 2.3408 7.872zm16.5963 3.8558L13.1038 8.364 15.1192 7.2a.0757.0757 0 0 1 .071 0l4.8303 2.7913a4.4944 4.4944 0 0 1-.6765 8.1042v-5.6772a.79.79 0 0 0-.407-.667zm2.0107-3.0231l-.142-.0852-4.7735-2.7818a.7759.7759 0 0 0-.7854 0L9.409 9.2297V6.8974a.0662.0662 0 0 1 .0284-.0615l4.8303-2.7866a4.4992 4.4992 0 0 1 6.6802 4.66zM8.3065 12.863l-2.02-1.1638a.0804.0804 0 0 1-.038-.0567V6.0742a4.4992 4.4992 0 0 1 7.3757-3.4537l-.142.0805L8.704 5.459a.7948.7948 0 0 0-.3927.6813zm1.0976-2.3654l2.602-1.4998 2.6069 1.4998v2.9994l-2.5974 1.4997-2.6067-1.4997Z",
        "foreground": "#B4BEFE",
        "background": "#252B3F",
        "fallback": "Cx",
    },
    "antigravity": {
        "path": "M11.04 19.32Q12 21.51 12 24q0-2.49.93-4.68.96-2.19 2.58-3.81t3.81-2.55Q21.51 12 24 12q-2.49 0-4.68-.93a12.3 12.3 0 0 1-3.81-2.58 12.3 12.3 0 0 1-2.58-3.81Q12 2.49 12 0q0 2.49-.96 4.68-.93 2.19-2.55 3.81a12.3 12.3 0 0 1-3.81 2.58Q2.49 12 0 12q2.49 0 4.68.96 2.19.93 3.81 2.55t2.55 3.81",
        "foreground": "#4285F4",
        "background": "#FFFFFF",
        "fallback": "G",
    },
    "claude": {
        "path": (
            "M21 10.5h3v3h-3v3h-1.5v3H18v-3h-1.5v3H15v-3H9v3H7.5v-3"
            "H6v3H4.5v-3H3v-3H0v-3h3v-6h18Zm-15 0h1.5v-3H6Zm10.5 0H18v-3h-1.5z"
        ),
        "foreground": "#FAB387",
        "background": "#3A2B2B",
        "fallback": "Cl",
    },
}


@lru_cache(maxsize=24)
def create_provider_pixmap(provider_type: str, size: int = 30) -> QPixmap:
    """Render a local, network-free brand badge for a usage provider."""
    brand = _PROVIDER_BRANDS.get(provider_type)
    if brand is None:
        brand = {
            "path": "",
            "foreground": "#CDD6F4",
            "background": "#202531",
            "fallback": "AI",
        }

    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(brand["background"]))
    radius = max(5.0, size * 0.24)
    painter.drawRoundedRect(QRectF(0, 0, size, size), radius, radius)

    if QSvgRenderer is not None and brand["path"]:
        svg = (
            '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
            f'<path fill="{brand["foreground"]}" d="{brand["path"]}"/>'
            "</svg>"
        )
        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        inset = size * 0.24
        renderer.render(
            painter,
            QRectF(inset, inset, size - (inset * 2), size - (inset * 2)),
        )
    else:
        painter.setPen(QColor(brand["foreground"]))
        painter.setFont(QFont("Segoe UI", max(7, round(size * 0.28)), QFont.Weight.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, brand["fallback"])

    painter.end()
    return pixmap


def create_provider_icon(provider_type: str, size: int = 24) -> QIcon:
    return QIcon(create_provider_pixmap(provider_type, size))


@lru_cache(maxsize=8)
def _asset_bytes(name: str) -> bytes:
    """Read an SVG/asset from the PyInstaller bundle or the repo, network-free."""
    roots: list[Path] = []
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        roots.append(Path(bundle_root))
    roots.append(Path(__file__).resolve().parents[1])

    for root in roots:
        try:
            return (root / "assets" / name).read_bytes()
        except OSError:
            continue
    return b""


def _render_svg(data: bytes, width: int, height: int) -> QPixmap | None:
    """Rasterise an SVG into a transparent pixmap, preserving its aspect ratio."""
    if not data or QSvgRenderer is None:
        return None
    renderer = QSvgRenderer(QByteArray(data))
    if not renderer.isValid():
        return None

    pixmap = QPixmap(max(1, width), max(1, height))
    pixmap.fill(QColor(0, 0, 0, 0))

    view_box = renderer.viewBoxF()
    if view_box.width() > 0 and view_box.height() > 0:
        scale = min(width / view_box.width(), height / view_box.height())
        drawn_w = view_box.width() * scale
        drawn_h = view_box.height() * scale
        target = QRectF(
            (width - drawn_w) / 2.0,
            (height - drawn_h) / 2.0,
            drawn_w,
            drawn_h,
        )
    else:
        target = QRectF(0, 0, width, height)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, target)
    painter.end()
    return pixmap


@lru_cache(maxsize=16)
def create_app_pixmap(size: int = 32) -> QPixmap:
    """The transparent gauge mark, for in-app use (compact bar, etc.)."""
    rendered = _render_svg(_asset_bytes("logo.svg"), size, size)
    if rendered is not None:
        return rendered

    # Code-drawn fallback for checkouts without the SVG assets.
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor("#5B8DEF"))
    font = QFont("Segoe UI", max(1, int(size * 0.5)), QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(
        QRectF(0, -max(1.0, size * 0.03), size, size),
        Qt.AlignmentFlag.AlignCenter,
        "S",
    )
    painter.end()
    return pixmap


@lru_cache(maxsize=16)
def create_app_icon_pixmap(size: int = 32) -> QPixmap:
    """The mark on its near-black tile — for window / tray / installer icons,
    where it must read on both light and dark system chrome."""
    rendered = _render_svg(_asset_bytes("logo-icon.svg"), size, size)
    if rendered is not None:
        return rendered
    return create_app_pixmap(size)


def create_app_icon(size: int = 32) -> QIcon:
    return QIcon(create_app_icon_pixmap(size))


@lru_cache(maxsize=12)
def create_wordmark_pixmap(width: int = 96, height: int = 30) -> QPixmap:
    """The SynapCap wordmark, scaled for title bars."""
    rendered = _render_svg(_asset_bytes("wordmark.svg"), width, height)
    if rendered is not None:
        return rendered
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor(0, 0, 0, 0))
    return pixmap


def create_status_dot_pixmap(status_type: str = "success", size: int = 12) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    if status_type in ("success", "connected", "active"):
        main_color = QColor("#A6E3A1")  # Green
        glow_color = QColor(166, 227, 161, 80)
    elif status_type in ("error", "failed"):
        main_color = QColor("#F38BA8")  # Red
        glow_color = QColor(243, 139, 168, 80)
    else:  # warning / demo / no_key
        main_color = QColor("#F9E2AF")  # Yellow
        glow_color = QColor(249, 226, 175, 80)

    center = size / 2.0

    # Outer Subtle Glow Ring
    painter.setBrush(glow_color)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(QPointF(center, center), center - 1, center - 1)

    # Inner Solid LED Circle
    painter.setBrush(main_color)
    painter.drawEllipse(QPointF(center, center), center - 3, center - 3)

    painter.end()
    return pixmap


# ==========================================
# 깔끔한 모던 백터 아이콘 생성기 (이모지 대체)
# ==========================================


def create_plus_icon(size: int = 16, color: str = "#11111B") -> QIcon:
    """플러스(+) 아이콘"""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color), 2.0)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)

    mid = size / 2.0
    offset = size * 0.28
    painter.drawLine(QPointF(mid - offset, mid), QPointF(mid + offset, mid))
    painter.drawLine(QPointF(mid, mid - offset), QPointF(mid, mid + offset))
    painter.end()
    return QIcon(pixmap)


def create_arrow_up_icon(size: int = 16, color: str = "#CDD6F4") -> QIcon:
    """위로 화살표(▲) 아이콘 (대칭 Center Y 정밀 정렬)"""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color), 1.8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)

    path = QPainterPath()
    path.moveTo(size * 0.24, size * 0.62)
    path.lineTo(size * 0.5, size * 0.38)
    path.lineTo(size * 0.76, size * 0.62)
    painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)


def create_arrow_down_icon(size: int = 16, color: str = "#CDD6F4") -> QIcon:
    """아래로 화살표(▼) 아이콘 (대칭 Center Y 정밀 정렬)"""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color), 1.8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)

    path = QPainterPath()
    path.moveTo(size * 0.24, size * 0.38)
    path.lineTo(size * 0.5, size * 0.62)
    path.lineTo(size * 0.76, size * 0.38)
    painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)


def create_trash_icon(size: int = 16, color: str = "#11111B") -> QIcon:
    """쓰레기통 삭제 아이콘"""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color), 1.8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)

    # Bucket body
    painter.drawRect(QRectF(size * 0.28, size * 0.38, size * 0.44, size * 0.48))
    # Lid top line
    painter.drawLine(QPointF(size * 0.18, size * 0.38), QPointF(size * 0.82, size * 0.38))
    # Lid handle
    painter.drawRect(QRectF(size * 0.4, size * 0.22, size * 0.2, size * 0.16))

    painter.end()
    return QIcon(pixmap)


def create_power_icon(size: int = 16, color: str = "#EBA0AC") -> QIcon:
    """프로그램 종료(Power/Quit) 전원 아이콘 (차분한 모던 톤)"""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color), 1.8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)

    # Circle Arc (Top open) with ample padding
    rect = QRectF(size * 0.18, size * 0.22, size * 0.64, size * 0.64)
    painter.drawArc(rect, 45 * 16, 270 * 16)

    # Top Vertical Line
    painter.drawLine(QPointF(size * 0.5, size * 0.12), QPointF(size * 0.5, size * 0.48))

    painter.end()
    return QIcon(pixmap)


def create_refresh_icon(size: int = 16, color: str = "#89B4FA") -> QIcon:
    """지금 새로고침(Refresh) 순환 아이콘"""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color), 1.8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)

    rect = QRectF(size * 0.18, size * 0.18, size * 0.64, size * 0.64)
    painter.drawArc(rect, 30 * 16, 290 * 16)

    # Arrow head
    path = QPainterPath()
    path.moveTo(size * 0.72, size * 0.15)
    path.lineTo(size * 0.88, size * 0.25)
    path.lineTo(size * 0.72, size * 0.38)
    painter.drawPath(path)

    painter.end()
    return QIcon(pixmap)


def create_usage_view_icon(
    target_view: str = "ring",
    size: int = 16,
    color: str = "#A6ADC8",
) -> QIcon:
    """Icon for switching between the compact bar and ring usage views."""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.7)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)

    if target_view == "ring":
        rect = QRectF(size * 0.18, size * 0.18, size * 0.64, size * 0.64)
        painter.drawEllipse(rect)
        accent_pen = QPen(QColor("#89B4FA"), 2.2)
        accent_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(accent_pen)
        painter.drawArc(rect, 90 * 16, -130 * 16)
    elif target_view == "segment":
        seg_w = size * 0.14
        for i in range(4):
            x = size * 0.16 + i * (seg_w + size * 0.06)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#89B4FA" if i < 2 else color))
            painter.drawRoundedRect(
                QRectF(x, size * 0.4, seg_w, size * 0.2), 1.5, 1.5
            )
    elif target_view == "number":
        painter.setPen(QColor(color))
        font = QFont("Segoe UI", max(6, round(size * 0.5)), QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "%")
    else:  # bar
        starts = (0.26, 0.50, 0.74)
        lengths = (0.42, 0.68, 0.54)
        for y, length in zip(starts, lengths, strict=True):
            painter.drawLine(
                QPointF(size * 0.18, size * y),
                QPointF(size * (0.18 + length), size * y),
            )

    painter.end()
    return QIcon(pixmap)


def create_settings_icon(size: int = 16, color: str = "#A6ADC8") -> QIcon:
    """누가 봐도 명확한 6-Teeth 톱니바퀴(Gear Cog) 백터 아이콘"""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color), 1.5)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)

    center = size / 2.0
    r_outer = size * 0.40
    r_inner = size * 0.28
    r_hole = size * 0.14

    teeth_count = 6
    path = QPainterPath()

    for i in range(teeth_count):
        angle_start = (i * 2 * math.pi / teeth_count) - (math.pi / (teeth_count * 2))
        angle_mid1 = angle_start + (math.pi / (teeth_count * 3))
        angle_mid2 = angle_mid1 + (math.pi / (teeth_count * 3))
        angle_end = (i + 1) * 2 * math.pi / teeth_count - (math.pi / (teeth_count * 2))

        # Outer tooth peak
        p1 = QPointF(
            center + r_outer * math.cos(angle_start), center + r_outer * math.sin(angle_start)
        )
        p2 = QPointF(
            center + r_outer * math.cos(angle_mid1), center + r_outer * math.sin(angle_mid1)
        )
        # Inner tooth trough
        p3 = QPointF(
            center + r_inner * math.cos(angle_mid2), center + r_inner * math.sin(angle_mid2)
        )
        p4 = QPointF(center + r_inner * math.cos(angle_end), center + r_inner * math.sin(angle_end))

        if i == 0:
            path.moveTo(p1)
        else:
            path.lineTo(p1)
        path.lineTo(p2)
        path.lineTo(p3)
        path.lineTo(p4)

    path.closeSubpath()
    painter.drawPath(path)

    # Center Hole Circle
    hole_rect = QRectF(center - r_hole, center - r_hole, r_hole * 2, r_hole * 2)
    painter.drawEllipse(hole_rect)

    painter.end()
    return QIcon(pixmap)


def create_close_icon(size: int = 16, color: str = "#A6ADC8") -> QIcon:
    """창 숨기기/닫기(✕) 백터 아이콘 (정밀 정렬용)"""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color), 1.8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)

    margin = size * 0.26
    painter.drawLine(QPointF(margin, margin), QPointF(size - margin, size - margin))
    painter.drawLine(QPointF(size - margin, margin), QPointF(margin, size - margin))

    painter.end()
    return QIcon(pixmap)


def create_minimize_icon(size: int = 16, color: str = "#A6ADC8") -> QIcon:
    """작업 표시줄/Dock 최소화용 가로선 아이콘."""
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color), 1.8)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.drawLine(
        QPointF(size * 0.26, size * 0.68),
        QPointF(size * 0.74, size * 0.68),
    )

    painter.end()
    return QIcon(pixmap)
