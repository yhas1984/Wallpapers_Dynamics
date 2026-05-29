from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QBrush
from PyQt5.QtCore import Qt, QRect, QPointF


def _pixmap(size, draw_func):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    draw_func(painter, size)
    painter.end()
    return QIcon(pixmap)


def icon_folder(size=24):
    def draw(p, s):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FFD93D"))
        p.drawRoundedRect(int(s*0.1), int(s*0.25), int(s*0.8), int(s*0.6), s*0.08, s*0.08)
        p.setBrush(QColor("#FFC107"))
        p.drawRoundedRect(int(s*0.1), int(s*0.18), int(s*0.4), int(s*0.15), s*0.06, s*0.06)
    return _pixmap(size, draw)


def icon_play(size=24):
    def draw(p, s):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#4CAF50"))
        p.drawEllipse(int(s*0.05), int(s*0.05), int(s*0.9), int(s*0.9))
        p.setBrush(QColor("white"))
        p.drawPolygon(*[QPointF(s*0.35, s*0.25), QPointF(s*0.35, s*0.75), QPointF(s*0.78, s*0.5)])
    return _pixmap(size, draw)


def icon_pause(size=24):
    def draw(p, s):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FF9800"))
        p.drawEllipse(int(s*0.05), int(s*0.05), int(s*0.9), int(s*0.9))
        p.setBrush(QColor("white"))
        w = s * 0.12
        p.drawRoundedRect(int(s*0.32), int(s*0.25), int(w), int(s*0.5), 2, 2)
        p.drawRoundedRect(int(s*0.56), int(s*0.25), int(w), int(s*0.5), 2, 2)
    return _pixmap(size, draw)


def icon_stop(size=24):
    def draw(p, s):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#f44336"))
        p.drawEllipse(int(s*0.05), int(s*0.05), int(s*0.9), int(s*0.9))
        p.setBrush(QColor("white"))
        m = s * 0.28
        p.drawRoundedRect(int(m), int(m), int(s-m*2), int(s-m*2), s*0.06, s*0.06)
    return _pixmap(size, draw)


def icon_mute(size=24):
    def draw(p, s):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#9E9E9E"))
        p.drawEllipse(int(s*0.05), int(s*0.05), int(s*0.9), int(s*0.9))
        p.setBrush(QColor("white"))
        p.drawRoundedRect(int(s*0.25), int(s*0.35), int(s*0.2), int(s*0.3), 2, 2)
        p.setPen(QPen(QColor("white"), s*0.06))
        p.drawLine(int(s*0.45), int(s*0.5), int(s*0.7), int(s*0.3))
        p.drawLine(int(s*0.7), int(s*0.3), int(s*0.7), int(s*0.7))
    return _pixmap(size, draw)


def icon_sound(size=24):
    def draw(p, s):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#2196F3"))
        p.drawEllipse(int(s*0.05), int(s*0.05), int(s*0.9), int(s*0.9))
        p.setBrush(QColor("white"))
        p.drawRoundedRect(int(s*0.25), int(s*0.35), int(s*0.2), int(s*0.3), 2, 2)
        p.setPen(QPen(QColor("white"), s*0.05))
        p.drawLine(int(s*0.45), int(s*0.5), int(s*0.65), int(s*0.35))
        p.drawLine(int(s*0.55), int(s*0.5), int(s*0.7), int(s*0.38))
    return _pixmap(size, draw)


def icon_reset(size=24):
    def draw(p, s):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#795548"))
        p.drawEllipse(int(s*0.05), int(s*0.05), int(s*0.9), int(s*0.9))
        p.setPen(QPen(QColor("white"), s*0.06))
        p.drawArc(int(s*0.22), int(s*0.22), int(s*0.56), int(s*0.56), 0, 270*16)
        p.setBrush(QColor("white"))
        p.drawPolygon(*[QPointF(s*0.5, s*0.1), QPointF(s*0.38, s*0.25), QPointF(s*0.62, s*0.25)])
    return _pixmap(size, draw)


def icon_close(size=24):
    def draw(p, s):
        p.setPen(QPen(QColor("#666"), s*0.08))
        m = s * 0.3
        p.drawLine(int(m), int(m), int(s-m), int(s-m))
        p.drawLine(int(s-m), int(m), int(m), int(s-m))
    return _pixmap(size, draw)


def icon_minimize(size=24):
    def draw(p, s):
        p.setPen(QPen(QColor("#666"), s*0.08))
        y = s * 0.6
        p.drawLine(int(s*0.3), int(y), int(s*0.7), int(y))
    return _pixmap(size, draw)


def icon_app(size=48):
    def draw(p, s):
        gradient = p
        p.setBrush(QColor("#6495ED"))
        p.setPen(Qt.NoPen)
        m = s * 0.08
        p.drawRoundedRect(int(m), int(m), int(s-m*2), int(s-m*2), s*0.2, s*0.2)
        p.setBrush(QColor("white"))
        p.drawPolygon(*[QPointF(s*0.35, s*0.25), QPointF(s*0.35, s*0.75), QPointF(s*0.78, s*0.5)])
    return _pixmap(size, draw)


def icon_led_active(size=12):
    def draw(p, s):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#4CAF50"))
        p.drawEllipse(1, 1, int(s-2), int(s-2))
        p.setBrush(QColor(255, 255, 255, 100))
        p.drawEllipse(int(s*0.2), int(s*0.15), int(s*0.3), int(s*0.3))
    return _pixmap(size, draw)


def icon_led_inactive(size=12):
    def draw(p, s):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#f44336"))
        p.drawEllipse(1, 1, int(s-2), int(s-2))
        p.setBrush(QColor(255, 255, 255, 100))
        p.drawEllipse(int(s*0.2), int(s*0.15), int(s*0.3), int(s*0.3))
    return _pixmap(size, draw)
