import sys
from ui_icons import apply_window_tool_icon
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedLayout,
    QTabBar,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.cad.viewport import CadViewport


BG = "#000000"
TOP = "#111111"
TAB = "#171717"
TAB_ACTIVE = "#3A3A3A"
TAB_HOVER = "#242424"
SURFACE = "#212121"
HOVER = "#2B2B2B"
BORDER = "#2A2A2A"
TEXT = "#FFFFFF"
TEXT_MUTED = "#A8A8A8"

STATUS_BG = "#111111"
STATUS_BORDER = "#2A2A2A"
STATUS_HOVER = "#242424"
STATUS_ACTIVE = "#3A3A3A"

CARD = "#1A1A1A"
CARD_HOVER = "#262626"
CARD_BORDER = "#3A3A3A"
CARD_TEXT = "#F2F2F2"
CARD_SUBTEXT = "#B5B5B5"


class StartCard(QPushButton):
    def __init__(self, title, subtitle, parent=None):
        super().__init__(parent)

        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(240, 240)
        self.setObjectName("startCard")
        self.setText("")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(10)

        layout.addStretch()

        title_label = QLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setObjectName("startCardTitle")

        subtitle_label = QLabel(subtitle)
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setWordWrap(True)
        subtitle_label.setObjectName("startCardSubtitle")

        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        layout.addStretch()


class StartPage(QWidget):
    def __init__(self, on_new, on_open, parent=None):
        super().__init__(parent)

        self.setObjectName("startPage")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        root.addStretch()

        row = QHBoxLayout()
        row.setSpacing(28)
        row.setAlignment(Qt.AlignCenter)

        self.open_card = StartCard(
            "Open",
            "Open an existing Plan3D project",
        )

        self.new_card = StartCard(
            "New",
            "Start a new project from a CAD drawing",
        )

        self.open_card.clicked.connect(on_open)
        self.new_card.clicked.connect(on_new)

        row.addWidget(self.open_card)
        row.addWidget(self.new_card)

        holder = QWidget()
        holder.setLayout(row)
        holder.setSizePolicy(
            QSizePolicy.Maximum,
            QSizePolicy.Maximum,
        )

        root.addWidget(
            holder,
            alignment=Qt.AlignCenter,
        )

        root.addStretch()

        self.setStyleSheet(f"""
            QWidget#startPage {{
                background-color: {BG};
            }}

            QPushButton#startCard {{
                background-color: {CARD};
                border: 1px solid {CARD_BORDER};
                border-radius: 24px;
            }}

            QPushButton#startCard:hover {{
                background-color: {CARD_HOVER};
                border: 1px solid #4A4A4A;
            }}

            QPushButton#startCard:pressed {{
                background-color: #303030;
            }}

            QLabel#startCardTitle {{
                color: {CARD_TEXT};
                font-family: "Segoe UI";
                font-size: 30px;
                font-weight: 700;
                background: transparent;
            }}

            QLabel#startCardSubtitle {{
                color: {CARD_SUBTEXT};
                font-family: "Segoe UI";
                font-size: 14px;
                background: transparent;
            }}
        """)



class EyeToggleButton(QToolButton):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setCheckable(True)
        self.setChecked(False)
        self.setFixedSize(24, 24)
        self.setCursor(Qt.PointingHandCursor)

        self.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                border: none;
            }

            QToolButton:hover {
                background-color: #252525;
            }

            QToolButton:checked {
                background-color: #303030;
            }
        """)

    def paintEvent(self, event):
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        if self.isChecked():
            color = QColor("#E3E3E3")
        else:
            color = QColor("#707070")

        pen = QPen(color)
        pen.setWidthF(1.3)

        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        w = self.width()
        h = self.height()

        path = QPainterPath()
        path.moveTo(5, h / 2)

        path.cubicTo(
            8,
            6,
            w - 8,
            6,
            w - 5,
            h / 2
        )

        path.cubicTo(
            w - 8,
            h - 6,
            8,
            h - 6,
            5,
            h / 2
        )

        painter.drawPath(path)

        if self.isChecked():
            painter.setBrush(color)
        else:
            painter.setBrush(Qt.NoBrush)

        painter.drawEllipse(
            int(w / 2 - 2.5),
            int(h / 2 - 2.5),
            5,
            5
        )


class LayersPanel(QFrame):
    PANEL_WIDTH = 310
    HEADER_HEIGHT = 28
    COLLAPSED_HEIGHT = 28

    TYPE_COLORS = {
        "Unassigned": "#777777",
        "Wall": "#3A86FF",
        "Door": "#49B96E",
        "Window": "#F39A3D",
        "Roof": "#E05252",
    }

    def __init__(self, parent=None):
        super().__init__(parent)

        self._collapsed = False
        self._viewport = None

        self.setObjectName("layersPanel")
        self.setFixedWidth(self.PANEL_WIDTH)

        self.setStyleSheet("""
            QFrame#layersPanel {
                background-color: #151515;
                border-top: 1px solid #2B2B2B;
                border-right: 1px solid #343434;
                border-bottom: 1px solid #2B2B2B;
                border-left: none;
            }

            QFrame#layersHeader {
                background-color: #1B1B1B;
                border: none;
                border-bottom: 1px solid #313131;
            }

            QLabel#layersTitle {
                background: transparent;
                color: #E6E6E6;
                border: none;
                font-family: "Segoe UI";
                font-size: 11px;
                font-weight: 600;
            }

            QToolButton#layersWindowButton {
                background-color: transparent;
                color: #AFAFAF;
                border: none;
                font-family: "Segoe UI";
                font-size: 14px;
                font-weight: 600;
            }

            QToolButton#layersWindowButton:hover {
                background-color: #2A2A2A;
                color: #FFFFFF;
            }

            QScrollArea#layersScroll {
                background-color: #171717;
                border: none;
            }

            QWidget#layersContent {
                background-color: #171717;
            }

            QFrame#layerRow {
                background-color: #171717;
                border: none;
                border-bottom: 1px solid #242424;
            }

            QFrame#layerRow:hover {
                background-color: #1E1E1E;
            }

            QLabel#layerName {
                background: transparent;
                color: #D0D0D0;
                border: none;
                font-family: "Segoe UI";
                font-size: 10px;
            }


            QComboBox {
                background-color: #202020;
                color: #CFCFCF;
                border: 1px solid #343434;
                padding-left: 6px;
                min-height: 20px;
                font-family: "Segoe UI";
                font-size: 10px;
            }

            QComboBox:hover {
                border: 1px solid #4A4A4A;
            }

            QComboBox::drop-down {
                width: 18px;
                border: none;
                background-color: #262626;
            }

            QComboBox QAbstractItemView {
                background-color: #202020;
                color: #D0D0D0;
                border: 1px solid #3A3A3A;
                selection-background-color: #3A3A3A;
                selection-color: #FFFFFF;
            }

            QScrollBar:vertical {
                background: #111111;
                width: 7px;
                margin: 2px 1px 2px 1px;
                border: none;
            }

            QScrollBar::handle:vertical {
                background: #484848;
                min-height: 22px;
                border-radius: 3px;
            }

            QScrollBar::handle:vertical:hover {
                background: #626262;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
                border: none;
            }

            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame(self)
        header.setObjectName("layersHeader")
        header.setFixedHeight(self.HEADER_HEIGHT)

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(9, 0, 3, 0)
        header_layout.setSpacing(0)

        title = QLabel("Layers", header)
        title.setObjectName("layersTitle")

        header_layout.addWidget(title)
        header_layout.addStretch()

        self.minimize_button = QToolButton(header)
        self.minimize_button.setObjectName("layersWindowButton")
        apply_window_tool_icon(self.minimize_button, "minimize", 18)
        self.minimize_button.setFixedSize(28, 28)
        self.minimize_button.setCursor(Qt.PointingHandCursor)
        self.minimize_button.clicked.connect(self.toggle_collapsed)

        self.close_button = QToolButton(header)
        self.close_button.setObjectName("layersWindowButton")
        apply_window_tool_icon(self.close_button, "close", 18)
        self.close_button.setFixedSize(28, 28)
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.clicked.connect(self.hide)

        header_layout.addWidget(self.minimize_button)
        header_layout.addWidget(self.close_button)

        root.addWidget(header)

        self.body = QWidget(self)

        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.scroll = QScrollArea(self.body)
        self.scroll.setObjectName("layersScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.NoFrame)

        self.content = QWidget()
        self.content.setObjectName("layersContent")

        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)

        self.scroll.setWidget(self.content)

        body_layout.addWidget(self.scroll)
        root.addWidget(self.body, 1)

    def load_layers(self, viewport):
        self._viewport = viewport

        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

        if viewport is None:
            return

        for layer_name in viewport.get_layer_names():
            row = QFrame(self.content)
            row.setObjectName("layerRow")
            row.setFixedHeight(32)

            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(7, 4, 7, 4)
            row_layout.setSpacing(7)

            eye = EyeToggleButton(row)
            eye.setChecked(
                viewport.is_layer_selected(layer_name)
            )
            eye.setToolTip("Highlight Layer")

            swatch = QFrame(row)
            swatch.setFixedSize(7, 18)

            name = QLabel(layer_name, row)
            name.setObjectName("layerName")
            name.setMinimumWidth(80)

            type_box = QComboBox(row)
            type_box.addItems([
                "Unassigned",
                "Wall",
                "Door",
                "Window",
                "Roof",
            ])

            current_type = viewport.get_layer_type(
                layer_name
            )

            type_box.setCurrentText(
                current_type
            )

            swatch.setStyleSheet(
                "background-color: "
                + self.TYPE_COLORS.get(
                    current_type,
                    "#777777",
                )
                + "; border: none;"
            )

            eye.toggled.connect(
                lambda checked, ln=layer_name:
                self._viewport.set_layer_selected(
                    ln,
                    checked,
                )
            )

            def type_changed(
                value,
                ln=layer_name,
                color_box=swatch,
            ):
                if self._viewport is None:
                    return

                self._viewport.set_layer_type(
                    ln,
                    value,
                )

                color_box.setStyleSheet(
                    "background-color: "
                    + self.TYPE_COLORS.get(
                        value,
                        "#777777",
                    )
                    + "; border: none;"
                )

            type_box.currentTextChanged.connect(
                type_changed
            )

            row_layout.addWidget(eye)
            row_layout.addWidget(swatch)
            row_layout.addWidget(name, 1)
            row_layout.addWidget(type_box)

            self.content_layout.addWidget(row)

        self.content_layout.addStretch()

    def toggle_collapsed(self):
        self._collapsed = not self._collapsed

        if self._collapsed:
            self.body.hide()

            self.setMinimumHeight(
                self.COLLAPSED_HEIGHT
            )
            self.setMaximumHeight(
                self.COLLAPSED_HEIGHT
            )

            self.minimize_button.setText("+")
        else:
            self.setMinimumHeight(
                self.HEADER_HEIGHT
            )
            self.setMaximumHeight(
                16777215
            )

            self.body.show()
            self.minimize_button.setText("-")

        parent = self.parent()

        if parent is not None and hasattr(
            parent,
            "_position_layers_panel"
        ):
            parent._position_layers_panel()

        self.raise_()

    def show_panel(self):
        self.show()
        self.raise_()


class CadPage(QWidget):
    MAX_HISTORY = 25

    def __init__(self, cad_path, parent=None):
        super().__init__(parent)

        self.cad_path = str(cad_path)

        self.history = []
        self.history_index = -1
        self._restoring = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.viewport = CadViewport(self)

        self.viewport.historyStateRequested.connect(
            self.record_history
        )

        self.layers_panel = LayersPanel(self)
        self.layers_panel.hide()

        root.addWidget(
            self.viewport,
            1,
        )

        self.history_panel = QFrame(self)
        self.history_panel.setObjectName("historyPanel")
        self.history_panel.setFixedHeight(100)
        self.history_panel.hide()

        history_outer_layout = QVBoxLayout(self.history_panel)
        history_outer_layout.setContentsMargins(0, 0, 0, 0)
        history_outer_layout.setSpacing(0)

        self.history_scroll = QScrollArea(self.history_panel)
        self.history_scroll.setObjectName("historyScroll")
        self.history_scroll.setWidgetResizable(True)
        self.history_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )
        self.history_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarAsNeeded
        )
        self.history_scroll.setFrameShape(QFrame.NoFrame)

        self.history_content = QWidget()
        self.history_content.setObjectName("historyContent")

        self.history_panel_layout = QVBoxLayout(
            self.history_content
        )
        self.history_panel_layout.setContentsMargins(
            0, 0, 0, 0
        )
        self.history_panel_layout.setSpacing(0)

        self.history_scroll.setWidget(
            self.history_content
        )

        history_outer_layout.addWidget(
            self.history_scroll
        )

        self.history_panel.setStyleSheet("""
            QFrame#historyPanel {
                background-color: #151515;
                border-top: 1px solid #2A2A2A;
                border-bottom: 1px solid #2A2A2A;
            }

            QScrollArea#historyScroll {
                background-color: #151515;
                border: none;
            }

            QWidget#historyContent {
                background-color: #151515;
            }

            QPushButton {
                background-color: transparent;
                color: #C8C8C8;
                border: none;
                border-bottom: 1px solid #242424;
                text-align: left;
                padding-left: 10px;
                padding-right: 8px;
                font-family: "Segoe UI";
                font-size: 11px;
            }

            QPushButton:hover {
                background-color: #292929;
                color: #FFFFFF;
            }

            QPushButton:checked {
                background-color: #3A3A3A;
                color: #FFFFFF;
            }

            QScrollBar:vertical {
                background: #111111;
                width: 7px;
                margin: 2px 1px 2px 1px;
                border: none;
            }

            QScrollBar::handle:vertical {
                background: #484848;
                min-height: 22px;
                border-radius: 3px;
            }

            QScrollBar::handle:vertical:hover {
                background: #626262;
            }

            QScrollBar::handle:vertical:pressed {
                background: #777777;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
                background: transparent;
                border: none;
            }

            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)

        root.addWidget(self.history_panel)

        self.status_bar = QWidget(self)
        self.status_bar.setFixedHeight(22)
        self.status_bar.setObjectName("historyStatusBar")

        status_layout = QHBoxLayout(self.status_bar)
        status_layout.setContentsMargins(8, 0, 4, 0)
        status_layout.setSpacing(0)

        self.history_position = QLabel("")
        self.history_position.setObjectName(
            "historyPosition"
        )

        status_layout.addWidget(
            self.history_position
        )

        status_layout.addStretch()

        self.history_button = QToolButton(
            self.status_bar
        )

        self.history_button.setText("History")
        self.history_button.setCursor(
            Qt.PointingHandCursor
        )

        self.history_button.setFixedHeight(22)

        self.history_button.clicked.connect(
            self.show_history_menu
        )

        status_layout.addWidget(
            self.history_button
        )

        root.addWidget(
            self.status_bar
        )

        self.setStyleSheet(f"""
            QWidget#historyStatusBar {{
                background-color: {STATUS_BG};
                border-top: 1px solid {STATUS_BORDER};
            }}

            QLabel#historyPosition {{
                background: transparent;
                color: #808080;
                font-family: "Segoe UI";
                font-size: 11px;
            }}

            QToolButton {{
                background-color: transparent;
                color: #B0B0B0;
                border: none;
                padding: 0px 9px;
                font-family: "Segoe UI";
                font-size: 11px;
            }}

            QToolButton:hover {{
                background-color: {STATUS_HOVER};
                color: #FFFFFF;
            }}

            QToolButton:pressed {{
                background-color: {STATUS_ACTIVE};
            }}

            QMenu {{
                background-color: #181818;
                color: #D8D8D8;
                border: 1px solid #333333;
                padding: 3px;
            }}

            QMenu::item {{
                min-width: 220px;
                padding: 6px 12px;
                background-color: transparent;
            }}

            QMenu::item:selected {{
                background-color: #303030;
                color: #FFFFFF;
            }}

            QMenu::separator {{
                height: 1px;
                background-color: #333333;
                margin: 3px 6px;
            }}
        """)

    def load(self):
        self.viewport.load_file(self.cad_path)

        self.layers_panel.load_layers(
            self.viewport
        )

        self.history = []
        self.history_index = -1

        # TEMPORARY TEST DATA:
        # Keep 15 temporary history entries until the user requests removal.
        test_labels = [
            "Drawing View",
            "Wall Selection",
            "Layer Check",
            "Zoom In",
            "Pan View",
            "Door Analysis",
            "Window Analysis",
            "Furniture Selection",
            "Plan Area",
            "Floor Check",
            "Wall Update",
            "Furniture Placement",
            "Space Check",
            "Model Preparation",
            "Final View",
        ]

        for label in test_labels:
            self.history.append({
                "label": label,
                "state": None,
            })

        self.history_index = len(self.history) - 1

        self._update_history_text()

    @property
    def source_path(self):
        return self.viewport.source_path

    def record_history(self, label):
        if self._restoring:
            return

        entry = {
            "label": str(label),
            "state": None,
        }

        self.history.append(entry)

        if len(self.history) > self.MAX_HISTORY:
            excess = (
                len(self.history)
                - self.MAX_HISTORY
            )

            del self.history[:excess]

            self.history_index = max(
                -1,
                self.history_index - excess,
            )

        self.history_index = (
            len(self.history) - 1
        )

        self._update_history_text()

    def _update_history_text(self):
        if not self.history:
            self.history_position.setText("")
            return

        self.history_position.setText(
            f"{self.history_index + 1} / "
            f"{len(self.history)}"
        )

    def show_history_menu(self):
        if self.history_panel.isVisible():
            self.history_panel.hide()
            self.history_button.setText("History")

            if hasattr(self, "layers_panel"):
                self._position_layers_panel()

            return

        while self.history_panel_layout.count():
            item = self.history_panel_layout.takeAt(0)

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

        if self.history:
            for index, entry in enumerate(self.history):
                button = QPushButton(
                    f"{index + 1}. {entry['label']}",
                    self.history_content
                )

                button.setFixedHeight(25)
                button.setCheckable(True)

                button.setChecked(
                    index == self.history_index
                )

                button.clicked.connect(
                    lambda checked=False, i=index:
                    self._history_item_clicked(i)
                )

                self.history_panel_layout.addWidget(
                    button
                )

            self.history_panel_layout.addStretch()

        self.history_panel.show()

        if hasattr(self, "layers_panel"):
            self._position_layers_panel()

        self.history_panel.raise_()

        self.history_button.setText("History")

        # Scroll the active history entry into view.
        if self.history:
            self.history_scroll.verticalScrollBar().setValue(
                self.history_scroll.verticalScrollBar().maximum()
            )

    def _history_item_clicked(self, index):
        self.restore_history(index)

        self.history_panel.hide()
        self.history_button.setText("History")

        if hasattr(self, "layers_panel"):
            self._position_layers_panel()

    def show_layers_panel(self):
        self._position_layers_panel()
        self.layers_panel.show()
        self.layers_panel.raise_()

        if (
            hasattr(self, "history_panel")
            and self.history_panel.isVisible()
        ):
            self._position_layers_panel()

    def _position_layers_panel(self):
        if not hasattr(self, "layers_panel"):
            return

        if getattr(self.layers_panel, "_collapsed", False):
            panel_height = self.layers_panel.COLLAPSED_HEIGHT
        else:
            history_height = 0

            if (
                hasattr(self, "history_panel")
                and self.history_panel.isVisible()
            ):
                history_height = self.history_panel.height()

            status_height = 0

            if hasattr(self, "status_bar"):
                status_height = self.status_bar.height()

            panel_height = max(
                self.layers_panel.HEADER_HEIGHT,
                self.height()
                - status_height
                - history_height
            )

        self.layers_panel.setGeometry(
            0,
            0,
            self.layers_panel.PANEL_WIDTH,
            panel_height
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if hasattr(self, "layers_panel"):
            self._position_layers_panel()

            if self.layers_panel.isVisible():
                self.layers_panel.raise_()

    def history_back(self):
        if not self.history:
            return

        target = self.history_index - 1

        if target < 0:
            target = 0

        if target == self.history_index:
            return

        self.restore_history(target)

    def history_forward(self):
        if not self.history:
            return

        target = self.history_index + 1
        last_index = len(self.history) - 1

        if target > last_index:
            target = last_index

        if target == self.history_index:
            return

        self.restore_history(target)

    def restore_history(self, index):
        if (
            index < 0
            or index >= len(self.history)
        ):
            return

        # History navigation changes the active operation state only.
        # Viewport camera state (zoom/pan) must remain untouched.
        self._restoring = True

        try:
            self.history_index = index
            self._update_history_text()

            if (
                hasattr(self, "history_panel")
                and self.history_panel.isVisible()
            ):
                # Refresh selection highlight without altering viewport.
                for i in range(
                    self.history_panel_layout.count()
                ):
                    item = self.history_panel_layout.itemAt(i)
                    widget = item.widget()

                    if isinstance(widget, QPushButton):
                        widget.setChecked(
                            i == self.history_index
                        )

        finally:
            self._restoring = False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.current_project = None

        self.setWindowTitle("MAP Plan3D")
        self.resize(1400, 850)
        self.setMinimumSize(1000, 650)

        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {BG};
            }}

            QMenuBar {{
                background-color: {BG};
                color: {TEXT};
                border-bottom: 1px solid {BORDER};
                padding-left: 12px;
            }}

            QMenuBar::item {{
                background-color: transparent;
                padding: 9px 12px;
                margin: 4px 0px;
            }}

            QMenuBar::item:selected {{
                background-color: {SURFACE};
                border-radius: 6px;
            }}

            QMenu {{
                background-color: {SURFACE};
                color: {TEXT};
                border: 1px solid {BORDER};
                padding: 6px;
            }}

            QMenu::item {{
                padding: 9px 36px 9px 14px;
                background-color: transparent;
            }}

            QMenu::item:selected {{
                background-color: {HOVER};
            }}

            QMenu::separator {{
                height: 1px;
                background-color: {BORDER};
                margin: 5px 8px;
            }}

            QTabWidget::pane {{
                border: none;
                background-color: {BG};
                top: -1px;
            }}

            QTabWidget {{
                background-color: {BG};
            }}

            QTabBar {{
                background-color: {TOP};
            }}

            QTabBar::tab {{
                background-color: {TAB};
                color: {TEXT_MUTED};
                min-width: 100px;
                max-width: 220px;
                height: 22px;
                padding-left: 10px;
                padding-right: 10px;
                margin: 0px;
                border: none;
                border-right: 1px solid {BORDER};
                border-radius: 0px;
            }}

            QTabBar::tab:selected {{
                background-color: {TAB_ACTIVE};
                color: {TEXT};
                font-weight: 600;
                border-bottom: 1px solid #4A4A4A;
            }}

            QTabBar::tab:hover:!selected {{
                background-color: {TAB_HOVER};
                color: {TEXT};
            }}

            QTabBar::close-button {{
                image: none;
                subcontrol-position: right;
                width: 14px;
                height: 14px;
                margin-right: 5px;
            }}

            QMessageBox {{
                background-color: {SURFACE};
            }}

            QMessageBox QLabel {{
                color: {TEXT};
            }}
        """)

        self._build_menu()
        self._build_tabs()

    def _build_menu(self):
        menu_bar = QMenuBar(self)
        menu_bar.setContentsMargins(
            0, 0, 0, 0
        )

        self.setMenuBar(menu_bar)

        # FILE
        file_menu = QMenu(
            "File",
            self,
        )

        menu_bar.addMenu(
            file_menu
        )

        action_new = QAction(
            "New Project",
            self,
        )

        action_open = QAction(
            "Open Project",
            self,
        )

        action_save = QAction(
            "Save Project",
            self,
        )

        action_save_as = QAction(
            "Save As",
            self,
        )

        action_close_project = QAction(
            "Close Project",
            self,
        )

        action_exit = QAction(
            "Exit",
            self,
        )

        action_new.triggered.connect(
            self.new_project
        )

        action_open.triggered.connect(
            self.open_project
        )

        action_save.triggered.connect(
            self.save_project
        )

        action_save_as.triggered.connect(
            self.save_as_project
        )

        action_close_project.triggered.connect(
            self.close_current_tab
        )

        action_exit.triggered.connect(
            self.close
        )

        file_menu.addAction(
            action_new
        )

        file_menu.addAction(
            action_open
        )

        file_menu.addSeparator()

        file_menu.addAction(
            action_save
        )

        file_menu.addAction(
            action_save_as
        )

        file_menu.addSeparator()

        file_menu.addAction(
            action_close_project
        )

        file_menu.addSeparator()

        file_menu.addAction(
            action_exit
        )

        # EDIT
        edit_menu = QMenu(
            "Edit",
            self,
        )

        menu_bar.addMenu(
            edit_menu
        )

        action_undo = QAction(
            "Undo",
            self,
        )

        action_undo.setShortcut(
            "Ctrl+Z"
        )

        action_undo.triggered.connect(
            self.history_back
        )

        action_redo = QAction(
            "Redo",
            self,
        )

        action_redo.setShortcut(
            "Ctrl+X"
        )

        action_redo.triggered.connect(
            self.history_forward
        )

        edit_menu.addAction(
            action_undo
        )

        edit_menu.addAction(
            action_redo
        )

        # TOOLS
        tools_menu = QMenu(
            "Tools",
            self,
        )

        menu_bar.addMenu(
            tools_menu
        )

        action_layers = QAction(
            "Layers",
            self,
        )

        action_layers.triggered.connect(
            self.show_layers_panel
        )

        tools_menu.addAction(
            action_layers
        )

    def _build_tabs(self):
        self.tabs = QTabWidget(self)

        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.setElideMode(
            Qt.ElideRight
        )

        self.tabs.tabCloseRequested.connect(
            self.close_tab
        )

        self.tabs.currentChanged.connect(
            self.current_tab_changed
        )

        self.setCentralWidget(
            self.tabs
        )

        self.start_page = StartPage(
            on_new=self.new_project,
            on_open=self.open_project,
            parent=self,
        )

        self.tabs.addTab(
            self.start_page,
            "Start",
        )

        self.tabs.tabBar().setTabButton(
            0,
            QTabBar.RightSide,
            None,
        )

        plus_button = QToolButton(self)

        plus_button.setText("+")
        plus_button.setCursor(
            Qt.PointingHandCursor
        )

        plus_button.setFixedSize(
            24,
            22,
        )

        plus_button.setStyleSheet(f"""
            QToolButton {{
                background-color: transparent;
                color: {TEXT_MUTED};
                border: none;
                border-radius: 0px;
                font-size: 16px;
                font-weight: 400;
            }}

            QToolButton:hover {{
                background-color: {TAB_HOVER};
                color: {TEXT};
            }}

            QToolButton:pressed {{
                background-color: {TAB_ACTIVE};
            }}
        """)

        plus_button.clicked.connect(
            self.new_project
        )

        self.tabs.setCornerWidget(
            plus_button,
            Qt.TopRightCorner,
        )

    def _active_cad_page(self):
        if not hasattr(self, "tabs"):
            return None

        index = self.tabs.currentIndex()

        if index <= 0:
            return None

        page = self.tabs.widget(index)

        if not isinstance(
            page,
            CadPage
        ):
            return None

        return page

    def history_back(self):
        page = self._active_cad_page()

        if page is None:
            return

        page.history_back()

    def history_forward(self):
        page = self._active_cad_page()

        if page is None:
            return

        page.history_forward()

    def show_layers_panel(self):
        index = self.tabs.currentIndex()

        if index <= 0:
            return

        page = self.tabs.widget(
            index
        )

        if not isinstance(
            page,
            CadPage
        ):
            return

        page.show_layers_panel()

    def new_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Yeni File - CAD Çizimi Seç",
            str(Path.home() / "Desktop"),
            "CAD Çizimleri (*.dwg *.dxf);;DWG (*.dwg);;DXF (*.dxf)",
        )

        if not path:
            return

        self.open_cad_tab(
            path
        )

    def open_cad_tab(self, path):
        path = str(
            Path(path).resolve()
        )

        for index in range(
            1,
            self.tabs.count()
        ):
            page = self.tabs.widget(
                index
            )

            if (
                isinstance(page, CadPage)
                and str(
                    Path(
                        page.cad_path
                    ).resolve()
                ) == path
            ):
                self.tabs.setCurrentIndex(
                    index
                )
                return

        page = CadPage(
            path,
            self.tabs,
        )

        try:
            page.load()

        except Exception as exc:
            page.deleteLater()

            QMessageBox.critical(
                self,
                "CAD Açma Hatası",
                str(exc),
            )

            return

        page.setProperty(
            "plan3d_cad_path",
            path,
        )

        title = Path(path).stem

        index = self.tabs.addTab(
            page,
            title,
        )

        self.tabs.setTabToolTip(
            index,
            path,
        )

        self.tabs.setCurrentIndex(
            index
        )

        self.setWindowTitle(
            f"MAP Plan3D - {Path(path).name}"
        )

    def open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "File Aç",
            str(Path.home() / "Desktop"),
            "Plan3D Filesi (*.p3d)",
        )

        if not path:
            return

        try:
            lines = Path(path).read_text(
                encoding="utf-8"
            ).splitlines()

            cad_paths = []

            for line in lines:
                if line.startswith("CAD="):
                    cad_path = line[4:].strip()

                    if cad_path:
                        cad_paths.append(
                            cad_path
                        )

            if not cad_paths:
                raise RuntimeError(
                    "Bu proje dosyasında CAD yolu bulunamadı."
                )

            opened = False

            for cad_path in cad_paths:
                if Path(cad_path).exists():
                    self.open_cad_tab(
                        cad_path
                    )

                    opened = True

            if not opened:
                raise RuntimeError(
                    "Fileye bağlı CAD dosyaları bulunamadı."
                )

            self.current_project = path

        except Exception as exc:
            QMessageBox.critical(
                self,
                "File Açma Hatası",
                str(exc),
            )

    def save_project(self):
        if not self.current_project:
            self.save_as_project()
            return

        self._write_project(
            self.current_project
        )

    def save_as_project(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Fileyi Kaydet",
            str(Path.home() / "Desktop"),
            "Plan3D Filesi (*.p3d)",
        )

        if not path:
            return

        if not path.lower().endswith(
            ".p3d"
        ):
            path += ".p3d"

        self.current_project = path

        self._write_project(
            path
        )

    def _write_project(self, path):
        cad_paths = []

        for index in range(
            1,
            self.tabs.count()
        ):
            page = self.tabs.widget(
                index
            )

            if not isinstance(
                page,
                CadPage,
            ):
                continue

            if page.cad_path:
                cad_paths.append(
                    str(page.cad_path)
                )

        content = [
            "MAP Plan3D Filect"
        ]

        for cad_path in cad_paths:
            content.append(
                f"CAD={cad_path}"
            )

        Path(path).write_text(
            "\n".join(content) + "\n",
            encoding="utf-8",
        )

    def close_tab(self, index):
        if index == 0:
            return

        widget = self.tabs.widget(
            index
        )

        self.tabs.removeTab(
            index
        )

        if widget is not None:
            widget.deleteLater()

        if self.tabs.count() == 1:
            self.tabs.setCurrentIndex(
                0
            )

            self.setWindowTitle(
                "MAP Plan3D"
            )

    def close_current_tab(self):
        index = self.tabs.currentIndex()

        if index <= 0:
            return

        self.close_tab(
            index
        )

    def current_tab_changed(self, index):
        if index <= 0:
            self.setWindowTitle(
                "MAP Plan3D"
            )
            return

        page = self.tabs.widget(
            index
        )

        if not isinstance(
            page,
            CadPage,
        ):
            return

        if page.cad_path:
            self.setWindowTitle(
                f"MAP Plan3D - "
                f"{Path(page.cad_path).name}"
            )


def main():
    app = QApplication(sys.argv)

    app.setApplicationName(
        "MAP Plan3D"
    )

    window = MainWindow()
    window.show()

    sys.exit(
        app.exec()
    )



# PLAN3D_PROJECT_RUNTIME_V1
from project_runtime import install_plan3d_project_runtime

install_plan3d_project_runtime(
    MainWindow,
    CadPage,
    LayersPanel,
    EyeToggleButton,
)

from ui_theme_patch import install_plan3d_theme_patch

install_plan3d_theme_patch(
    MainWindow,
    CadPage,
    LayersPanel,
    EyeToggleButton,
)

from export_details_runtime import install_export_details_runtime

install_export_details_runtime(
    MainWindow,
    CadPage,
)

from cursor_runtime import install_plan3d_cursor_modes
install_plan3d_cursor_modes(
    MainWindow,
    CadViewport,
)
if __name__ == "__main__":
    main()
