from math import ceil, cos, pi, sin

from PySide6.QtCore import QEasingCurve, QPointF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QPainter, QPolygonF
from PySide6.QtWidgets import QWidget


class StarRating(QWidget):
    changed = Signal(str)

    def __init__(self, value="", parent=None):
        super().__init__(parent)
        self.value = float(value) if value not in ("", None) else 0.0
        self.preview = self.value
        self.fill = self.value
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Book rating")
        self.setToolTip("Hover to preview; click a full or half star to save (1–5). Delete clears; arrow keys adjust by 0.5.")
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(140)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self.animate)

    def currentData(self):
        return f"{self.value:g}" if self.value else ""

    def star_bounds(self):
        size = min(26.0, max(12.0, (self.width() - 16) / 5))
        return (self.width() - size * 5) / 2, (self.height() - size) / 2 - 7, size

    def animate(self, value):
        self.fill = float(value)
        self.update()

    def transition(self, value):
        self.preview = value
        self.animation.stop()
        self.animation.setStartValue(self.fill)
        self.animation.setEndValue(value)
        self.animation.start()
        self.update()

    def hit_rating(self, x):
        left, _, size = self.star_bounds()
        return max(1.0, min(5.0, ceil((x - left) / size * 2) / 2))

    def mouseMoveEvent(self, event):
        self.transition(self.hit_rating(event.position().x()))

    def leaveEvent(self, event):
        self.transition(self.value)
        super().leaveEvent(event)

    def commit(self, value):
        self.value = value
        self.transition(value)
        self.changed.emit(self.currentData())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.commit(self.hit_rating(event.position().x()))
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.commit(0)
        elif event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Down):
            self.commit(max(1.0, self.value - 0.5))
        elif event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Up):
            self.commit(min(5.0, max(1.0, self.value + 0.5)))
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipRect(self.rect().adjusted(2, 2, -2, -2))
        left, top, size = self.star_bounds()
        for index in range(5):
            center = left + (index + 0.5) * size
            points = QPolygonF([QPointF(center + (size * .43 if point % 2 == 0 else size * .19) * cos(-pi / 2 + point * pi / 5),
                                       top + size / 2 + (size * .43 if point % 2 == 0 else size * .19) * sin(-pi / 2 + point * pi / 5)) for point in range(10)])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#94a3b8"))
            painter.drawPolygon(points)
            painter.save()
            painter.setClipRect(round(left + index * size), round(top), round(size * max(0, min(1, self.fill - index))), round(size))
            painter.setBrush(QColor("#f59e0b"))
            painter.drawPolygon(points)
            painter.restore()
        painter.setPen(self.palette().color(self.foregroundRole()))
        label = f"{self.preview:g} / 5" if self.preview else "Not rated"
        painter.drawText(self.rect().adjusted(0, round(top + size + 2), 0, -3), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, label)
