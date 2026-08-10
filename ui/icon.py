import math
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QPen, QPainterPath
from PySide6.QtCore import Qt, QRectF, QPointF

def create_app_icon(size: int = 32) -> QIcon:
    pixmap = create_app_pixmap(size)
    return QIcon(pixmap)

def create_app_pixmap(size: int = 32) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # Background Circle (Catppuccin Base #1E1E2E)
    painter.setBrush(QColor("#1E1E2E"))
    painter.setPen(QColor("#89B4FA"))
    painter.drawEllipse(1, 1, size - 2, size - 2)
    
    # 'S' Text Logo (Catppuccin Blue #89B4FA)
    painter.setPen(QColor("#89B4FA"))
    font_size = int(size * 0.45)
    font = QFont("Segoe UI", font_size, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "S")
    
    painter.end()
    return pixmap

def create_eye_icon(show: bool = True, size: int = 24) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    color = QColor("#89B4FA") if show else QColor("#6C7086")
    pen = QPen(color, 2.0)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    
    # Eye Shape (Arc)
    rect = QRectF(2, 6, size - 4, size - 12)
    painter.drawArc(rect, 30 * 16, 120 * 16)
    painter.drawArc(rect, 210 * 16, 120 * 16)
    
    center_x = size / 2.0
    center_y = size / 2.0
    
    if show:
        # Pupil Center Circle
        painter.setBrush(color)
        painter.drawEllipse(QPointF(center_x, center_y), 3.0, 3.0)
    else:
        # Slash diagonal line
        painter.drawLine(5, size - 5, size - 5, 5)
        
    painter.end()
    return QIcon(pixmap)

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
    else:
        starts = (0.26, 0.50, 0.74)
        lengths = (0.42, 0.68, 0.54)
        for y, length in zip(starts, lengths):
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
        p1 = QPointF(center + r_outer * math.cos(angle_start), center + r_outer * math.sin(angle_start))
        p2 = QPointF(center + r_outer * math.cos(angle_mid1), center + r_outer * math.sin(angle_mid1))
        # Inner tooth trough
        p3 = QPointF(center + r_inner * math.cos(angle_mid2), center + r_inner * math.sin(angle_mid2))
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
