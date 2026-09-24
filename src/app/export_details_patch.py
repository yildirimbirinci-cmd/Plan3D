from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QDoubleSpinBox,
    QScrollArea,
    QMessageBox,
)


PANEL_WIDTH = 310
HEADER_HEIGHT = 34
COLLAPSED_HEIGHT = 34


def _apply_icon(button, name):
    try:
        from ui_icons import apply_window_tool_icon
        apply_window_tool_icon(button, name)
        return
    except Exception:
        pass

    if name == "minimize":
        button.setText("?")
    elif name == "close":
        button.setText("?")


class ExportDetailsPanel(QFrame):
    def __init__(self, page):
        super().__init__(page)

        self.page = page
        self._collapsed = False
        self._confirmed = False

        self.setObjectName("exportDetailsPanel")
        self.setFixedWidth(PANEL_WIDTH)

        self.setStyleSheet("""
            QFrame#exportDetailsPanel {
                background: #18191B;
                border: 1px solid #34363A;
                border-radius: 4px;
            }

            QLabel {
                color: #D7D9DD;
                background: transparent;
                border: none;
            }

            QLabel#exportDetailsTitle {
                color: #F0F1F2;
                font-weight: 600;
                font-size: 12px;
            }

            QLabel#sectionTitle {
                color: #78AEFF;
                font-weight: 600;
                padding-top: 5px;
            }

            QLineEdit,
            QDoubleSpinBox {
                min-height: 26px;
                background: #202124;
                color: #E4E5E7;
                border: 1px solid #34363A;
                border-radius: 3px;
                padding-left: 6px;
                padding-right: 6px;
            }

            QLineEdit:focus,
            QDoubleSpinBox:focus {
                border: 1px solid #4F7EAC;
            }

            QPushButton {
                min-height: 28px;
                background: #1D1E20;
                color: #E4E5E7;
                border: 1px solid #34363A;
                border-radius: 4px;
                padding: 0 10px;
            }

            QPushButton:hover {
                background: #192A3B;
                border: 1px solid #385F86;
                color: white;
            }

            QPushButton:pressed {
                background: #20364B;
                border: 1px solid #4F7EAC;
            }

            QPushButton:disabled {
                color: #66696E;
                border-color: #2B2D30;
                background: #191A1B;
            }

            QToolButton {
                background: #1D1E20;
                border: 1px solid #34363A;
                border-radius: 4px;
            }

            QToolButton:hover {
                background: #192A3B;
                border: 1px solid #385F86;
            }

            QScrollArea {
                border: none;
                background: transparent;
            }

            QScrollBar:vertical {
                width: 7px;
                background: #18191B;
            }

            QScrollBar::handle:vertical {
                background: #404348;
                min-height: 24px;
                border-radius: 3px;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ----------------------------------------------------
        # Header
        # ----------------------------------------------------

        self.header = QFrame(self)
        self.header.setFixedHeight(HEADER_HEIGHT)

        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(8, 3, 5, 3)
        header_layout.setSpacing(4)

        self.title = QLabel("Export Details", self.header)
        self.title.setObjectName("exportDetailsTitle")

        header_layout.addWidget(self.title)
        header_layout.addStretch(1)

        self.minimize_button = QToolButton(self.header)
        self.minimize_button.setFixedSize(28, 28)
        _apply_icon(self.minimize_button, "minimize")

        self.close_button = QToolButton(self.header)
        self.close_button.setFixedSize(28, 28)
        _apply_icon(self.close_button, "close")

        header_layout.addWidget(self.minimize_button)
        header_layout.addWidget(self.close_button)

        root.addWidget(self.header)

        # ----------------------------------------------------
        # Scrollable body
        # ----------------------------------------------------

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(10, 8, 10, 12)
        body_layout.setSpacing(8)

        section = QLabel("3D MODEL")
        section.setObjectName("sectionTitle")
        body_layout.addWidget(section)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)

        self.floor_name = QLineEdit()
        self.floor_name.setText("Ground Floor")

        self.floor_elevation = self._spin()
        self.floor_elevation.setValue(0.0)

        self.wall_height = self._spin()
        self.wall_height.setValue(280.0)

        self.slab_thickness = self._spin()
        self.slab_thickness.setValue(35.0)

        self.floor_to_floor = self._spin()
        self.floor_to_floor.setValue(315.0)

        form.addRow("Floor Name", self.floor_name)
        form.addRow("Floor Elevation (cm)", self.floor_elevation)
        form.addRow("Wall Height (cm)", self.wall_height)
        form.addRow("Slab Thickness (cm)", self.slab_thickness)
        form.addRow("Floor-to-Floor (cm)", self.floor_to_floor)

        body_layout.addLayout(form)
        body_layout.addSpacing(6)

        note = QLabel(
            "Only Wall geometry will be used for the current "
            "3D model generation stage."
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            "color:#9AA0A6; padding:6px 0px;"
        )
        body_layout.addWidget(note)

        self.confirm_button = QPushButton("Confirm Details")
        self.create_button = QPushButton("Create 3D Model")
        self.create_button.setEnabled(False)

        body_layout.addWidget(self.confirm_button)
        body_layout.addWidget(self.create_button)
        body_layout.addStretch(1)

        self.scroll.setWidget(body)
        root.addWidget(self.scroll, 1)

        self.minimize_button.clicked.connect(
            self.toggle_collapsed
        )
        self.close_button.clicked.connect(
            self.hide_panel
        )
        self.confirm_button.clicked.connect(
            self.confirm_details
        )
        self.create_button.clicked.connect(
            self.create_3d_model
        )

        self.floor_name.textChanged.connect(
            self._mark_dirty
        )

        for spin in (
            self.floor_elevation,
            self.wall_height,
            self.slab_thickness,
            self.floor_to_floor,
        ):
            spin.valueChanged.connect(
                self._mark_dirty
            )

        self.hide()

    def _spin(self):
        w = QDoubleSpinBox()
        w.setDecimals(2)
        w.setRange(-100000.0, 100000.0)
        w.setSingleStep(1.0)
        w.setSuffix(" cm")
        return w

    def values(self):
        return {
            "floor_name": self.floor_name.text().strip(),
            "floor_elevation_cm": float(
                self.floor_elevation.value()
            ),
            "wall_height_cm": float(
                self.wall_height.value()
            ),
            "slab_thickness_cm": float(
                self.slab_thickness.value()
            ),
            "floor_to_floor_cm": float(
                self.floor_to_floor.value()
            ),
            "confirmed": bool(
                self._confirmed
            ),
        }

    def _mark_dirty(self, *args):
        if self._confirmed:
            self._confirmed = False
            self.create_button.setEnabled(False)
            self.confirm_button.setText(
                "Confirm Details"
            )

    def confirm_details(self):
        if not self.floor_name.text().strip():
            QMessageBox.warning(
                self,
                "Export Details",
                "Floor Name is required.",
            )
            return

        if self.wall_height.value() <= 0:
            QMessageBox.warning(
                self,
                "Export Details",
                "Wall Height must be greater than 0.",
            )
            return

        self._confirmed = True
        self.create_button.setEnabled(True)
        self.confirm_button.setText(
            "Details Confirmed"
        )

        self.page._export_details = self.values()

    def create_3d_model(self):
        if not self._confirmed:
            return

        self.page._export_details = self.values()

        # The UI/state stage is complete.
        # Do not invent a Max bridge. If a verified bridge is
        # installed later this is the single hand-off point.
        bridge = getattr(
            self.page,
            "_send_wall_lines_to_max",
            None,
        )

        if callable(bridge):
            bridge(
                self.values()
            )
            return

        QMessageBox.information(
            self,
            "Create 3D Model",
            "Export details are confirmed.\n\n"
            "The 3ds Max wall export bridge has not been "
            "connected to Plan3D yet.",
        )

    def toggle_collapsed(self):
        self._collapsed = not self._collapsed

        self.scroll.setVisible(
            not self._collapsed
        )

        if self._collapsed:
            self.setFixedHeight(
                COLLAPSED_HEIGHT
            )
        else:
            self.setMinimumHeight(
                260
            )
            self.setMaximumHeight(
                16777215
            )
            self.page._position_export_details_panel()

    def hide_panel(self):
        self.hide()

    def show_panel(self):
        self.show()
        self.raise_()
        self.page._position_export_details_panel()


def _install_properties_minimize(page):
    panel = getattr(
        page,
        "properties_panel",
        None,
    )

    if panel is None:
        return

    if getattr(
        panel,
        "_plan3d_minimize_installed",
        False,
    ):
        return

    panel._plan3d_minimize_installed = True
    panel._collapsed = bool(
        getattr(
            panel,
            "_collapsed",
            False,
        )
    )

    # Find the header from the existing close button.
    buttons = panel.findChildren(
        QToolButton
    )

    if not buttons:
        return

    close_button = buttons[-1]
    header = close_button.parentWidget()

    if header is None:
        return

    layout = header.layout()

    if layout is None:
        return

    minimize = QToolButton(header)
    minimize.setFixedSize(28, 28)
    _apply_icon(minimize, "minimize")

    index = layout.indexOf(
        close_button
    )

    if index < 0:
        layout.addWidget(minimize)
    else:
        layout.insertWidget(
            index,
            minimize
        )

    panel._plan3d_minimize_button = minimize

    scroll_areas = panel.findChildren(
        QScrollArea
    )

    def toggle():
        panel._collapsed = not panel._collapsed

        for scroll in scroll_areas:
            scroll.setVisible(
                not panel._collapsed
            )

        if panel._collapsed:
            panel.setFixedHeight(
                COLLAPSED_HEIGHT
            )
        else:
            panel.setMinimumHeight(
                100
            )
            panel.setMaximumHeight(
                16777215
            )

        try:
            page._position_tool_panel_dock()
        except Exception:
            pass

    minimize.clicked.connect(
        toggle
    )


def _refresh_layers_panel(page):
    panel = getattr(
        page,
        "layers_panel",
        None,
    )
    viewport = getattr(
        page,
        "viewport",
        None,
    )

    if panel is None or viewport is None:
        return

    # Rebuild the visible layer rows from the already-loaded CAD.
    try:
        panel.load_layers(viewport)
    except Exception:
        return

    # A restored project may carry a stale hidden body state.
    collapsed = bool(
        getattr(
            panel,
            "_collapsed",
            False,
        )
    )

    if not collapsed:
        from PySide6.QtWidgets import QScrollArea

        for scroll in panel.findChildren(QScrollArea):
            scroll.setVisible(True)

    try:
        page._position_tool_panel_dock()
    except Exception:
        pass


def _normalize_tool_panel_headers(page):
    layers = getattr(
        page,
        "layers_panel",
        None,
    )
    props = getattr(
        page,
        "properties_panel",
        None,
    )

    if layers is None or props is None:
        return

    # --------------------------------------------------------
    # Read the Layers header as the authoritative layout.
    # --------------------------------------------------------
    layer_buttons = layers.findChildren(QToolButton)

    if not layer_buttons:
        return

    layer_header = layer_buttons[0].parentWidget()

    if layer_header is None:
        return

    layer_layout = layer_header.layout()

    if layer_layout is None:
        return

    header_height = max(
        30,
        layer_header.height(),
        layer_header.minimumHeight(),
    )

    margins = layer_layout.contentsMargins()

    try:
        spacing = layer_layout.spacing()
    except Exception:
        spacing = 4

    # Normalize Layers buttons too, so both headers share one
    # exact button geometry.
    for button in layer_buttons:
        button.setFixedSize(28, 28)

    layer_header.setFixedHeight(header_height)

    # --------------------------------------------------------
    # Properties header
    # --------------------------------------------------------
    prop_buttons = props.findChildren(QToolButton)

    if not prop_buttons:
        return

    prop_header = prop_buttons[0].parentWidget()

    if prop_header is None:
        return

    prop_layout = prop_header.layout()

    if prop_layout is None:
        return

    prop_header.setFixedHeight(header_height)

    prop_layout.setContentsMargins(
        margins.left(),
        margins.top(),
        margins.right(),
        margins.bottom(),
    )
    prop_layout.setSpacing(spacing)

    for button in prop_buttons:
        button.setFixedSize(28, 28)

    # Re-apply the same SVG tool icons used by Layers.
    # Properties has minimize + close.
    if len(prop_buttons) >= 2:
        try:
            _apply_icon(
                prop_buttons[-2],
                "minimize",
            )
            _apply_icon(
                prop_buttons[-1],
                "close",
            )
        except Exception:
            pass

    try:
        page._position_tool_panel_dock()
    except Exception:
        pass



def install_export_details_patch(
    MainWindow,
    CadPage,
):
    # --------------------------------------------------------
    # Layers panel:
    # every time it is opened, rebuild rows from the viewport.
    # This fixes empty Layers content after opening a .p3d.
    # --------------------------------------------------------
    old_show_layers_panel = getattr(
        CadPage,
        "show_layers_panel",
        None,
    )

    if (
        old_show_layers_panel is not None
        and not getattr(
            CadPage,
            "_plan3d_layers_restore_wrapped",
            False,
        )
    ):
        CadPage._plan3d_layers_restore_wrapped = True

        def show_layers_panel_with_refresh(
            self,
            *args,
            **kwargs
        ):
            result = old_show_layers_panel(
                self,
                *args,
                **kwargs
            )

            QTimer.singleShot(
                0,
                lambda: _refresh_layers_panel(self)
            )
            QTimer.singleShot(
                40,
                lambda: _refresh_layers_panel(self)
            )

            return result

        CadPage.show_layers_panel = (
            show_layers_panel_with_refresh
        )

    old_page_init = CadPage.__init__
    old_page_resize = getattr(
        CadPage,
        "resizeEvent",
        None,
    )

    def page_init(self, *args, **kwargs):
        old_page_init(
            self,
            *args,
            **kwargs
        )

        self.export_details_panel = (
            ExportDetailsPanel(self)
        )

        self._export_details = {
            "floor_name": "Ground Floor",
            "floor_elevation_cm": 0.0,
            "wall_height_cm": 280.0,
            "slab_thickness_cm": 35.0,
            "floor_to_floor_cm": 315.0,
            "confirmed": False,
        }

        QTimer.singleShot(
            0,
            lambda:
            _install_properties_minimize(
                self
            )
        )

        QTimer.singleShot(
            60,
            lambda:
            _refresh_layers_panel(
                self
            )
        )

        QTimer.singleShot(
            80,
            lambda:
            _normalize_tool_panel_headers(
                self
            )
        )

        QTimer.singleShot(
            160,
            lambda:
            _refresh_layers_panel(
                self
            )
        )

        QTimer.singleShot(
            180,
            lambda:
            _normalize_tool_panel_headers(
                self
            )
        )

    CadPage.__init__ = page_init

    def position_export_panel(self):
        panel = getattr(
            self,
            "export_details_panel",
            None,
        )

        viewport = getattr(
            self,
            "viewport",
            None,
        )

        if (
            panel is None
            or viewport is None
            or not panel.isVisible()
        ):
            return

        try:
            geo = viewport.geometry()
        except Exception:
            return

        margin = 8

        x = (
            geo.x()
            + geo.width()
            - panel.width()
            - margin
        )

        y = geo.y() + margin

        if panel._collapsed:
            h = COLLAPSED_HEIGHT
        else:
            h = max(
                220,
                geo.height()
                - margin * 2,
            )

        panel.setGeometry(
            x,
            y,
            PANEL_WIDTH,
            h,
        )

        panel.raise_()

    CadPage._position_export_details_panel = (
        position_export_panel
    )

    def show_export_details_panel(self):
        panel = getattr(
            self,
            "export_details_panel",
            None,
        )

        if panel is None:
            return

        panel.show_panel()

    CadPage.show_export_details_panel = (
        show_export_details_panel
    )

    def page_resize(self, event):
        if old_page_resize is not None:
            old_page_resize(
                self,
                event
            )

        self._position_export_details_panel()

    CadPage.resizeEvent = page_resize

    old_main_init = MainWindow.__init__

    def main_init(self, *args, **kwargs):
        old_main_init(
            self,
            *args,
            **kwargs
        )

        tools_menu = None

        for action in self.menuBar().actions():
            menu = action.menu()

            if menu is None:
                continue

            text = action.text().replace(
                "&",
                "",
            ).strip()

            if text == "Tools":
                tools_menu = menu
                break

        if tools_menu is None:
            return

        for action in tools_menu.actions():
            if (
                action.text().replace("&", "").strip()
                == "Export Details"
            ):
                return

        export_action = QAction(
            "Export Details",
            self,
        )

        def open_export_details():
            tabs = getattr(
                self,
                "tabs",
                None,
            )

            if tabs is None:
                return

            page = tabs.currentWidget()

            if hasattr(
                page,
                "show_export_details_panel",
            ):
                page.show_export_details_panel()

        export_action.triggered.connect(
            open_export_details
        )

        tools_menu.addAction(
            export_action
        )

        self._export_details_action = (
            export_action
        )

    MainWindow.__init__ = main_init
