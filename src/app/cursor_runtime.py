from __future__ import annotations

from PySide6.QtCore import Qt, QPoint, QObject, QEvent
from PySide6.QtGui import QColor, QCursor, QPainter, QPen, QPixmap, QPolygon
from PySide6.QtWidgets import QApplication


_OUTSIDE_CURSOR = None
_VIEWPORT_CURSOR = None
_CURSOR_FILTERS = []


def _make_outside_cursor() -> QCursor:
    """
    Option 2 - smaller:
    compact white CAD-style arrow + small blue guide square.
    """
    size = 28
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)

    arrow = QPolygon([
        QPoint(3, 2),
        QPoint(3, 19),
        QPoint(7, 15),
        QPoint(11, 24),
        QPoint(15, 22),
        QPoint(11, 14),
        QPoint(18, 14),
    ])

    pen = QPen(QColor("#F2F4F6"), 1.5)
    pen.setCosmetic(True)
    p.setPen(pen)
    p.setBrush(QColor("#111315"))
    p.drawPolygon(arrow)

    guide = QPen(QColor("#2FA8FF"), 1.5)
    guide.setCosmetic(True)
    p.setPen(guide)
    p.setBrush(Qt.NoBrush)
    p.drawRect(19, 16, 5, 5)

    p.end()
    return QCursor(pm, 3, 2)


def _make_viewport_cursor() -> QCursor:
    """
    Option 3:
    CAD crosshair + blue pick box.
    """
    size = 38
    c = size // 2
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)

    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)

    white = QPen(QColor("#F2F4F6"), 1.25)
    white.setCosmetic(True)
    p.setPen(white)

    gap = 6
    arm = 15

    p.drawLine(c, c - arm, c, c - gap)
    p.drawLine(c, c + gap, c, c + arm)
    p.drawLine(c - arm, c, c - gap, c)
    p.drawLine(c + gap, c, c + arm, c)

    blue = QPen(QColor("#21A8F6"), 1.7)
    blue.setCosmetic(True)
    p.setPen(blue)
    p.setBrush(Qt.NoBrush)
    p.drawRect(c - 5, c - 5, 10, 10)

    p.end()
    return QCursor(pm, c, c)


def outside_cursor() -> QCursor:
    global _OUTSIDE_CURSOR
    if _OUTSIDE_CURSOR is None:
        _OUTSIDE_CURSOR = _make_outside_cursor()
    return _OUTSIDE_CURSOR


def viewport_cursor() -> QCursor:
    global _VIEWPORT_CURSOR
    if _VIEWPORT_CURSOR is None:
        _VIEWPORT_CURSOR = _make_viewport_cursor()
    return _VIEWPORT_CURSOR


class _ViewportCursorFilter(QObject):
    """
    QGraphicsView receives mouse input through its internal viewport QWidget.
    Installing the cursor on that child fixes the previous issue where
    Option 3 never became visible.
    """

    def __init__(self, view):
        super().__init__(view)
        self.view = view

    def eventFilter(self, obj, event):
        et = event.type()

        if et == QEvent.Enter:
            if not bool(getattr(self.view, "_assignment_mode", False)):
                obj.setCursor(viewport_cursor())
                self.view.setCursor(viewport_cursor())

        elif et == QEvent.Leave:
            if not bool(getattr(self.view, "_assignment_mode", False)):
                obj.unsetCursor()
                self.view.unsetCursor()

        elif et == QEvent.MouseButtonPress:
            try:
                if event.button() == Qt.MiddleButton:
                    obj.setCursor(Qt.ClosedHandCursor)
                    self.view.setCursor(Qt.ClosedHandCursor)
            except Exception:
                pass

        elif et == QEvent.MouseButtonRelease:
            try:
                if event.button() == Qt.MiddleButton:
                    if bool(getattr(self.view, "_assignment_mode", False)):
                        obj.setCursor(Qt.CrossCursor)
                        self.view.setCursor(Qt.CrossCursor)
                    else:
                        obj.setCursor(viewport_cursor())
                        self.view.setCursor(viewport_cursor())
            except Exception:
                pass

        return False


def _apply_viewport_cursor(view):
    child = view.viewport()

    if child is not None:
        child.setMouseTracking(True)
        child.setCursor(viewport_cursor())

        filt = _ViewportCursorFilter(view)
        child.installEventFilter(filt)

        # Keep Python reference alive.
        _CURSOR_FILTERS.append(filt)
        view._plan3d_cursor_filter = filt

    view.setMouseTracking(True)
    view.setCursor(viewport_cursor())


def install_plan3d_cursor_modes(MainWindow, CadViewport):
    """
    Outside CAD viewport -> Option 2.
    Inside CAD viewport  -> Option 3.
    Active assignment selection may temporarily use its own cursor.
    """

    old_main_init = MainWindow.__init__

    def main_init(self, *args, **kwargs):
        old_main_init(self, *args, **kwargs)
        self.setCursor(outside_cursor())

    MainWindow.__init__ = main_init

    old_view_init = CadViewport.__init__

    def viewport_init(self, *args, **kwargs):
        old_view_init(self, *args, **kwargs)
        _apply_viewport_cursor(self)

    CadViewport.__init__ = viewport_init

    # Preserve dedicated selection cursor, then restore Option 3
    # after assignment mode finishes.
    old_cancel = getattr(CadViewport, "cancel_assignment_selection", None)

    if callable(old_cancel):
        def cancel_assignment_selection(self, *args, **kwargs):
            result = old_cancel(self, *args, **kwargs)

            try:
                self.setCursor(viewport_cursor())
                vp = self.viewport()
                if vp is not None:
                    vp.setCursor(viewport_cursor())
            except Exception:
                pass

            return result

        CadViewport.cancel_assignment_selection = cancel_assignment_selection
