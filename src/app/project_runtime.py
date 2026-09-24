from __future__ import annotations

from ui_icons import apply_window_tool_icon

import json

from pathlib import Path

from PySide6.QtCore import Qt, QTimer

from PySide6.QtGui import QAction, QColor, QFont, QTransform

from PySide6.QtWidgets import (

    QFileDialog,

    QFrame,

    QHBoxLayout,

    QLabel,

    QMessageBox,

    QComboBox,

    QToolButton,

    QPushButton,

    QScrollArea,

    QVBoxLayout,

    QSizePolicy,

    QWidget,

)

PROJECT_FORMAT = "MAP_PLAN3D"

PROJECT_VERSION = 1

TYPE_ORDER = {

    "Wall": 0,

    "Exterior Wall": 1,

    "Facade": 2,

    "Window": 3,

    "Door": 4,

    "Sliding Door": 5,

    "Stair": 6,

    "Detail": 7,

    "Furniture": 8,

    "Roof": 9,

    "Unassigned": 10,

}

TYPE_COLORS = {

    "Unassigned": "#D9D9D9",

    "Wall": "#3A86FF",

    "Exterior Wall": "#9AA0A6",

    "Facade": "#1F4E79",

    "Window": "#F39A3D",

    "Door": "#49B96E",

    "Sliding Door": "#1F7A4D",

    "Stair": "#F2C94C",

    "Detail": "#E68AB8",

    "Furniture": "#B59A30",

    "Roof": "#E05252",

}

class ToolPanelDock(QFrame):

    PANEL_WIDTH = 310

    def __init__(self, parent=None):

        super().__init__(parent)

        self.setObjectName("toolPanelDock")

        self.setFixedWidth(self.PANEL_WIDTH)

        self.setStyleSheet("""

            QFrame#toolPanelDock {

                background-color: #151515;

                border: none;

            }

        """)

        self._panels = []

        self._open_order = []

        self.layout_root = QVBoxLayout(self)

        self.layout_root.setContentsMargins(0, 0, 0, 0)

        self.layout_root.setSpacing(0)

        self.hide()

    def register_panel(self, panel):

        if panel not in self._panels:

            self._panels.append(panel)

        panel.setParent(self)

        panel.setMinimumWidth(

            self.PANEL_WIDTH

        )

        panel.setMaximumWidth(

            self.PANEL_WIDTH

        )

        panel.setMinimumHeight(

            getattr(

                panel,

                "HEADER_HEIGHT",

                28,

            ) + 70

        )

        panel.setMaximumHeight(

            16777215

        )

        panel.setSizePolicy(

            QSizePolicy.Fixed,

            QSizePolicy.Expanding,

        )

    def open_panel(self, panel):

        if panel not in self._panels:

            self.register_panel(panel)

        # Preserve original opening order.

        if panel not in self._open_order:

            self._open_order.append(panel)

        panel.show()

        self.show()

        self.rebuild()

        self.raise_()

    def close_panel(self, panel):

        if panel in self._open_order:

            self._open_order.remove(panel)

        panel.hide()

        self.rebuild()

        if not self._open_order:

            self.hide()

    def rebuild(self):
        # Remove widgets from layout only; panel instances are persistent.
        while self.layout_root.count():
            item = self.layout_root.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(self)

        visible_panels = [
            panel for panel in self._open_order
            if panel.isVisible()
        ]

        if not visible_panels:
            self.hide()
            return

        for panel in visible_panels:
            header_height = getattr(panel, "HEADER_HEIGHT", 28)
            collapsed = bool(getattr(panel, "_collapsed", False))
            panel.setMinimumWidth(self.PANEL_WIDTH)
            panel.setMaximumWidth(self.PANEL_WIDTH)

            if collapsed:
                panel.setMinimumHeight(header_height)
                panel.setMaximumHeight(header_height)
                panel.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                self.layout_root.addWidget(panel, 0)
            else:
                panel.setMinimumHeight(header_height + 70)
                panel.setMaximumHeight(16777215)
                panel.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
                self.layout_root.addWidget(panel, 1)

        self.show()
        self.layout_root.invalidate()
        self.layout_root.activate()
        for panel in visible_panels:
            panel.updateGeometry()
            panel.update()
        self.updateGeometry()
        self.update()


class PropertiesPanel(QFrame):
    PANEL_WIDTH = 310
    HEADER_HEIGHT = 28
    COLLAPSED_HEIGHT = 28
    MIN_HEIGHT = 150

    def __init__(self, parent=None):
        super().__init__(parent)
        self._collapsed = False
        self.setObjectName("propertiesPanel")
        self.setFixedWidth(self.PANEL_WIDTH)
        self.setMinimumHeight(self.HEADER_HEIGHT + 70)
        self.setMaximumHeight(16777215)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        self.setStyleSheet("""
            QFrame#propertiesPanel { background-color: #151515; border-top: 1px solid #2B2B2B; border-right: 1px solid #343434; border-bottom: 1px solid #2B2B2B; border-left: none; }
            QFrame#propertiesHeader { background-color: #1B1B1B; border: none; border-bottom: 1px solid #313131; }
            QLabel#propertiesTitle { background: transparent; color: #E6E6E6; border: none; font-family: "Segoe UI"; font-size: 11px; font-weight: 600; }
            QToolButton#propertiesWindowButton { background-color: transparent; color: #AFAFAF; border: none; font-family: "Segoe UI"; font-size: 14px; font-weight: 600; }
            QToolButton#propertiesWindowButton:hover { background-color: #2A2A2A; color: #FFFFFF; }
            QWidget#propertiesBody { background-color: #171717; border: none; }
            QLabel#propKey { background: transparent; color: #878787; border: none; font-family: "Segoe UI"; font-size: 10px; }
            QLabel#propValue { background: transparent; color: #D2D2D2; border: none; font-family: "Segoe UI"; font-size: 10px; }
            QPushButton#propertiesActionButton { background-color: #202020; color: #D0D0D0; border: 1px solid #353535; padding: 6px 10px; font-family: "Segoe UI"; font-size: 10px; }
            QPushButton#propertiesActionButton:hover { background-color: #2A2A2A; border: 1px solid #505050; color: #FFFFFF; }
            QScrollArea#propertiesScroll { background-color: #171717; border: none; }
            QScrollBar:vertical { background: #111111; width: 7px; margin: 2px 1px 2px 1px; border: none; }
            QScrollBar::handle:vertical { background: #484848; min-height: 22px; border-radius: 3px; }
            QScrollBar::handle:vertical:hover { background: #626262; }
            QScrollBar::handle:vertical:pressed { background: #777777; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; border: none; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.header = QFrame(self)
        self.header.setObjectName("propertiesHeader")
        self.header.setFixedHeight(self.HEADER_HEIGHT)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(9, 0, 3, 0)
        header_layout.setSpacing(0)

        title = QLabel("Properties", self.header)
        title.setObjectName("propertiesTitle")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.minimize_button = QToolButton(self.header)
        self.minimize_button.setObjectName("propertiesWindowButton")
        apply_window_tool_icon(self.minimize_button, "minimize", 18)
        self.minimize_button.setFixedSize(28, 28)
        self.minimize_button.setCursor(Qt.PointingHandCursor)
        self.minimize_button.clicked.connect(self.toggle_collapsed)

        self.close_button = QToolButton(self.header)
        self.close_button.setObjectName("propertiesWindowButton")
        apply_window_tool_icon(self.close_button, "close", 18)
        self.close_button.setFixedSize(28, 28)
        self.close_button.setCursor(Qt.PointingHandCursor)
        header_layout.addWidget(self.minimize_button)
        header_layout.addWidget(self.close_button)
        root.addWidget(self.header)

        self.scroll = QScrollArea(self)
        self.scroll.setObjectName("propertiesScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.scroll.setMinimumHeight(40)

        self.body = QWidget()
        self.body.setObjectName("propertiesBody")
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(10, 10, 10, 10)
        body_layout.setSpacing(8)
        self.project_value = self._add_row(body_layout, "Project")
        self.cad_file_value = self._add_row(body_layout, "CAD File")
        self.cad_path_value = self._add_row(body_layout, "CAD Path")
        self.layer_count_value = self._add_row(body_layout, "Layer Count")
        self.visible_count_value = self._add_row(body_layout, "Visible Layers")
        self.wall_count_value = self._add_row(body_layout, "Walls")
        self.window_count_value = self._add_row(body_layout, "Windows")
        self.door_count_value = self._add_row(body_layout, "Doors")
        self.roof_count_value = self._add_row(body_layout, "Roofs")
        self.project_file_value = self._add_row(body_layout, "Project File")
        body_layout.addStretch()
        self.update_button = QPushButton("Update From Source", self.body)
        self.update_button.setObjectName("propertiesActionButton")
        body_layout.addWidget(self.update_button)
        self.scroll.setWidget(self.body)
        root.addWidget(self.scroll, 1)

    def _add_row(self, layout, key_text):
        row = QWidget(self.body)
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(2)
        key = QLabel(key_text, row)
        key.setObjectName("propKey")
        value = QLabel("-", row)
        value.setObjectName("propValue")
        value.setWordWrap(True)
        value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row_layout.addWidget(key)
        row_layout.addWidget(value)
        layout.addWidget(row)
        return value

    def set_values(self, values: dict):
        self.project_value.setText(values.get("project", "-"))
        self.cad_file_value.setText(values.get("cad_file", "-"))
        self.cad_path_value.setText(values.get("cad_path", "-"))
        self.layer_count_value.setText(values.get("layer_count", "-"))
        self.visible_count_value.setText(values.get("visible_count", "-"))
        self.wall_count_value.setText(values.get("wall_count", "-"))
        self.window_count_value.setText(values.get("window_count", "-"))
        self.door_count_value.setText(values.get("door_count", "-"))
        self.roof_count_value.setText(values.get("roof_count", "-"))
        self.project_file_value.setText(values.get("project_file", "-"))

    def toggle_collapsed(self):
        self._collapsed = not self._collapsed
        self.scroll.setVisible(not self._collapsed)
        if self._collapsed:
            self.setMinimumHeight(self.COLLAPSED_HEIGHT)
            self.setMaximumHeight(self.COLLAPSED_HEIGHT)
        else:
            self.setMinimumHeight(self.HEADER_HEIGHT + 70)
            self.setMaximumHeight(16777215)
        dock = self.parentWidget()
        if dock is not None and hasattr(dock, "rebuild"):
            dock.rebuild()



def install_plan3d_project_runtime(

    MainWindow,

    CadPage,

    LayersPanel,

    EyeToggleButton,

):

    # ========================================================

    # VIEWPORT PATCHES

    # ========================================================

    CadViewport = None

    try:

        from src.cad.viewport import CadViewport as ImportedViewport

        CadViewport = ImportedViewport

    except Exception:

        try:

            from cad.viewport import CadViewport as ImportedViewport

            CadViewport = ImportedViewport

        except Exception:

            CadViewport = None

    if CadViewport is not None:

        original_viewport_init = CadViewport.__init__

        def viewport_init(self, *args, **kwargs):

            original_viewport_init(self, *args, **kwargs)

            if not hasattr(self, "_layer_items"):

                self._layer_items = {}

            if not hasattr(self, "_layer_types"):

                self._layer_types = {}

            if not hasattr(self, "_layer_selected"):

                self._layer_selected = {}

        CadViewport.__init__ = viewport_init

        original_render = CadViewport._render_document

        def viewport_render(self):

            previous_types = dict(getattr(self, "_layer_types", {}))

            previous_selected = dict(getattr(self, "_layer_selected", {}))

            original_render(self)

            if not hasattr(self, "_layer_selected"):

                self._layer_selected = {}

            if not hasattr(self, "_layer_types"):

                self._layer_types = {}

            for layer_name in self.get_layer_names():

                self._layer_types[layer_name] = previous_types.get(

                    layer_name,

                    self._layer_types.get(layer_name, "Unassigned"),

                )

                self._layer_selected[layer_name] = previous_selected.get(

                    layer_name,

                    True,

                )

                self._apply_layer_style(layer_name)

        CadViewport._render_document = viewport_render

        def get_layer_names(self):

            return list(getattr(self, "_layer_items", {}).keys())

        def get_layer_type(self, layer_name):

            return getattr(self, "_layer_types", {}).get(layer_name, "Unassigned")

        def set_layer_type(self, layer_name, layer_type):

            if layer_name not in getattr(self, "_layer_items", {}):

                return

            allowed = {

            "Unassigned",

            "Wall",

            "Exterior Wall",

            "Facade",

            "Window",

            "Door",

            "Sliding Door",

            "Stair",

            "Detail",

            "Furniture",

            "Roof",

        }

            if layer_type not in allowed:

                layer_type = "Unassigned"

            self._layer_types[layer_name] = layer_type

            self._apply_layer_style(layer_name)

        def is_layer_selected(self, layer_name):

            return getattr(self, "_layer_selected", {}).get(layer_name, True)

        def set_layer_selected(self, layer_name, selected):

            if layer_name not in getattr(self, "_layer_items", {}):

                return

            self._layer_selected[layer_name] = bool(selected)

            self._apply_layer_style(layer_name)

        def apply_layer_style(self, layer_name):

            layer_type = self._layer_types.get(layer_name, "Unassigned")

            visible = self._layer_selected.get(layer_name, True)

            color = QColor(TYPE_COLORS.get(layer_type, "#D9D9D9"))

            for item in self._layer_items.get(layer_name, []):

                try:

                    item.setVisible(visible)

                except Exception:

                    pass

                if not visible:

                    continue

                if hasattr(item, "pen") and hasattr(item, "setPen"):

                    try:

                        pen = item.pen()

                        pen.setColor(color)

                        pen.setCosmetic(True)

                        pen.setWidthF(1.0)

                        item.setPen(pen)

                    except Exception:

                        pass

                if hasattr(item, "brush") and hasattr(item, "setBrush"):

                    try:

                        brush = item.brush()

                        if brush.style() != Qt.NoBrush:

                            brush.setColor(color)

                            item.setBrush(brush)

                    except Exception:

                        pass

        CadViewport.get_layer_names = get_layer_names

        CadViewport.get_layer_type = get_layer_type

        CadViewport.set_layer_type = set_layer_type

        CadViewport.is_layer_selected = is_layer_selected

        CadViewport.set_layer_selected = set_layer_selected

        CadViewport._apply_layer_style = apply_layer_style

    # ========================================================

    # HELPERS

    # ========================================================

    def active_page(window):

        if not hasattr(window, "tabs"):

            return None

        index = window.tabs.currentIndex()

        if index < 0:

            return None

        page = window.tabs.widget(index)

        if not isinstance(page, CadPage):

            return None

        return page

    def transform_to_dict(viewport):

        transform = viewport.transform()

        center = viewport.mapToScene(viewport.viewport().rect().center())

        return {

            "m11": transform.m11(),

            "m12": transform.m12(),

            "m13": transform.m13(),

            "m21": transform.m21(),

            "m22": transform.m22(),

            "m23": transform.m23(),

            "m31": transform.m31(),

            "m32": transform.m32(),

            "m33": transform.m33(),

            "center_x": center.x(),

            "center_y": center.y(),

        }

    def restore_transform(viewport, state):

        if not isinstance(state, dict):

            return

        try:

            transform = QTransform(

                float(state["m11"]),

                float(state["m12"]),

                float(state["m13"]),

                float(state["m21"]),

                float(state["m22"]),

                float(state["m23"]),

                float(state["m31"]),

                float(state["m32"]),

                float(state["m33"]),

            )

            viewport.setTransform(transform)

            viewport.centerOn(

                float(state["center_x"]),

                float(state["center_y"]),

            )

            viewport._user_has_interacted = True

        except Exception:

            pass

    # ========================================================

    # LAYERS PANEL PATCHES

    # ========================================================

    original_layers_init = LayersPanel.__init__

    def layers_init(self, parent=None):

        original_layers_init(self, parent)

        if not hasattr(self, "_layer_order"):

            self._layer_order = []

        if hasattr(self, "minimize_button") and not hasattr(self, "refresh_button"):

            header = self.minimize_button.parentWidget()

            header_layout = header.layout()

            self.refresh_button = QToolButton(header)

            self.refresh_button.setObjectName("layersWindowButton")

            self.refresh_button.setFixedSize(30, 28)

            self.refresh_button.setCursor(Qt.PointingHandCursor)

            self.refresh_button.setToolTip("Group Layers by Type")

            apply_window_tool_icon(self.refresh_button, "refresh", 19)

            font = self.refresh_button.font()

            font.setPointSize(max(15, font.pointSize()))

            font.setBold(True)

            self.refresh_button.setFont(font)

            index = header_layout.indexOf(self.minimize_button)

            header_layout.insertWidget(max(0, index), self.refresh_button)

            self.refresh_button.clicked.connect(self.reorder_layers)

    LayersPanel.__init__ = layers_init

    def layers_load(self, viewport):

        self._viewport = viewport

        while self.content_layout.count():

            item = self.content_layout.takeAt(0)

            widget = item.widget()

            if widget is not None:

                widget.deleteLater()

        if viewport is None:

            return

        available = list(viewport.get_layer_names())

        if self._layer_order:

            ordered = [name for name in self._layer_order if name in available]

            ordered.extend(name for name in available if name not in ordered)

            layer_names = ordered

        else:

            layer_names = available

        self._layer_order = list(layer_names)

        for layer_name in layer_names:

            row = QFrame(self.content)

            row.setObjectName("layerRow")

            row.setFixedHeight(32)

            row_layout = QHBoxLayout(row)

            row_layout.setContentsMargins(7, 4, 7, 4)

            row_layout.setSpacing(7)

            eye = EyeToggleButton(row)

            eye.setChecked(viewport.is_layer_selected(layer_name))

            eye.setToolTip("Visible")

            swatch = QFrame(row)

            swatch.setFixedSize(7, 18)

            label = QLabel(layer_name, row)

            label.setObjectName("layerName")

            label.setMinimumWidth(80)

            type_box = QComboBox(row)

            type_box.addItems(

            [

                "Unassigned",

                "Wall",

                "Exterior Wall",

                "Facade",

                "Window",

                "Door",

                "Sliding Door",

                "Stair",

                "Detail",

                "Furniture",

                "Roof",

            ]

        )

            current_type = viewport.get_layer_type(layer_name)

            type_box.setCurrentText(current_type)

            swatch.setStyleSheet(

                "background-color: "

                + TYPE_COLORS.get(current_type, "#D9D9D9")

                + "; border: none;"

            )

            eye.toggled.connect(

                lambda checked, ln=layer_name: self._viewport.set_layer_selected(

                    ln,

                    checked,

                )

            )

            def type_changed(value, ln=layer_name, color_box=swatch):

                if self._viewport is None:

                    return

                self._viewport.set_layer_type(ln, value)

                color_box.setStyleSheet(

                    "background-color: "

                    + TYPE_COLORS.get(value, "#D9D9D9")

                    + "; border: none;"

                )

                owner = self.parent()

                if owner is not None and hasattr(owner, "update_properties_panel"):

                    owner.update_properties_panel()

            type_box.currentTextChanged.connect(type_changed)

            eye.toggled.connect(

                lambda checked, owner=self.parent():

                owner.update_properties_panel()

                if owner is not None and hasattr(owner, "update_properties_panel")

                else None

            )

            row_layout.addWidget(eye)

            row_layout.addWidget(swatch)

            row_layout.addWidget(label, 1)

            row_layout.addWidget(type_box)

            self.content_layout.addWidget(row)

        self.content_layout.addStretch()

    LayersPanel.load_layers = layers_load

    def reorder_layers(self):

        if getattr(self, "_viewport", None) is None:

            return

        current_order = list(self._layer_order or self._viewport.get_layer_names())

        original_index = {

            name: index

            for index, name in enumerate(current_order)

        }

        self._layer_order = sorted(

            current_order,

            key=lambda name: (

                TYPE_ORDER.get(self._viewport.get_layer_type(name), 4),

                original_index.get(name, 999999),

            ),

        )

        self.load_layers(self._viewport)

    LayersPanel.reorder_layers = reorder_layers

    # ========================================================

    # CAD PAGE PATCHES

    # ========================================================

    original_cad_init = CadPage.__init__

    def cad_init(self, *args, **kwargs):

        original_cad_init(self, *args, **kwargs)

        self.tool_panel_dock = ToolPanelDock(self)

        # Existing Layers panel becomes a dock child.

        if hasattr(self, "layers_panel"):

            self.tool_panel_dock.register_panel(

                self.layers_panel

            )

            try:

                self.layers_panel.hide()

            except Exception:

                pass

        self.properties_panel = PropertiesPanel(

            self.tool_panel_dock

        )

        self.tool_panel_dock.register_panel(

            self.properties_panel

        )

        self.properties_panel.hide()

        self.properties_panel.close_button.clicked.connect(

            self.hide_properties_panel

        )

        self.properties_panel.update_button.clicked.connect(

            self.reload_from_source

        )

        # Rewire Layers close button to shared dock close.

        if hasattr(self, "layers_panel") and hasattr(

            self.layers_panel,

            "close_button"

        ):

            try:

                self.layers_panel.close_button.clicked.disconnect()

            except Exception:

                pass

            self.layers_panel.close_button.clicked.connect(

                self.hide_layers_panel

            )

        if hasattr(self, "layers_panel"):

            self.layers_panel.load_layers(

                self.viewport

            )

        self.update_properties_panel()

        self._position_tool_panel_dock()

    CadPage.__init__ = cad_init

    def _available_left_height(self):

        history_height = 0

        if (

            hasattr(self, "history_panel")

            and self.history_panel.isVisible()

        ):

            history_height = self.history_panel.height()

        status_height = 0

        if hasattr(self, "status_bar"):

            status_height = self.status_bar.height()

        return max(

            0,

            self.height()

            - status_height

            - history_height

        )

    def _position_tool_panel_dock(self):

        if not hasattr(self, "tool_panel_dock"):

            return

        available_height = self._available_left_height()

        self.tool_panel_dock.setGeometry(

            0,

            0,

            ToolPanelDock.PANEL_WIDTH,

            available_height,

        )

        self.tool_panel_dock.rebuild()

    def show_layers_panel(self):

        if not hasattr(self, "layers_panel"):

            return

        self.layers_panel.load_layers(

            self.viewport

        )

        self._position_tool_panel_dock()

        self.tool_panel_dock.open_panel(

            self.layers_panel

        )

    def hide_layers_panel(self):

        if not hasattr(self, "layers_panel"):

            return

        self.tool_panel_dock.close_panel(

            self.layers_panel

        )

        self._position_tool_panel_dock()

    def show_properties_panel(self):

        self.update_properties_panel()

        self._position_tool_panel_dock()

        self.tool_panel_dock.open_panel(

            self.properties_panel

        )

    def hide_properties_panel(self):

        self.tool_panel_dock.close_panel(

            self.properties_panel

        )

        self._position_tool_panel_dock()

    def update_properties_panel(self):

        if not hasattr(self, "properties_panel"):

            return

        viewport = getattr(

            self,

            "viewport",

            None,

        )

        if viewport is None:

            return

        layer_names = list(

            viewport.get_layer_names()

        )

        visible_count = 0

        wall_count = 0

        window_count = 0

        door_count = 0

        roof_count = 0

        for layer_name in layer_names:

            if viewport.is_layer_selected(

                layer_name

            ):

                visible_count += 1

            layer_type = viewport.get_layer_type(

                layer_name

            )

            if layer_type == "Wall":

                wall_count += 1

            elif layer_type == "Window":

                window_count += 1

            elif layer_type == "Door":

                door_count += 1

            elif layer_type == "Roof":

                roof_count += 1

        source_path = (

            getattr(

                self,

                "_source_cad_path",

                None,

            )

            or getattr(

                self,

                "cad_path",

                None,

            )

        )

        source_path = (

            str(source_path)

            if source_path

            else "-"

        )

        project_path = getattr(

            self,

            "_project_path",

            None,

        )

        project_path = (

            str(project_path)

            if project_path

            else "-"

        )

        if project_path != "-":

            project_name = Path(

                project_path

            ).stem

        elif source_path != "-":

            project_name = Path(

                source_path

            ).stem

        else:

            project_name = "Untitled"

        self.properties_panel.set_values({

            "project": project_name,

            "cad_file": (

                Path(source_path).name

                if source_path != "-"

                else "-"

            ),

            "cad_path": source_path,

            "layer_count": str(

                len(layer_names)

            ),

            "visible_count": str(

                visible_count

            ),

            "wall_count": str(

                wall_count

            ),

            "window_count": str(

                window_count

            ),

            "door_count": str(

                door_count

            ),

            "roof_count": str(

                roof_count

            ),

            "project_file": project_path,

        })

    def reload_from_source(self):

        source_path = (

            getattr(

                self,

                "_source_cad_path",

                None,

            )

            or getattr(

                self,

                "cad_path",

                None,

            )

        )

        if not source_path:

            return

        try:

            source_path = str(

                source_path

            )

            old_names = (

                self.viewport.get_layer_names()

            )

            saved_types = {

                name:

                self.viewport.get_layer_type(

                    name

                )

                for name in old_names

            }

            saved_selected = {

                name:

                self.viewport.is_layer_selected(

                    name

                )

                for name in old_names

            }

            saved_order = list(

                getattr(

                    self.layers_panel,

                    "_layer_order",

                    old_names,

                )

            )

            current_view = transform_to_dict(

                self.viewport

            )

            self.viewport.load_file(

                source_path

            )

            new_names = (

                self.viewport.get_layer_names()

            )

            for name in new_names:

                self.viewport.set_layer_type(

                    name,

                    saved_types.get(

                        name,

                        "Unassigned",

                    ),

                )

                self.viewport.set_layer_selected(

                    name,

                    saved_selected.get(

                        name,

                        True,

                    ),

                )

            reordered = [

                name

                for name in saved_order

                if name in new_names

            ]

            reordered.extend(

                name

                for name in new_names

                if name not in reordered

            )

            self.layers_panel._layer_order = (

                reordered

            )

            self.layers_panel.load_layers(

                self.viewport

            )

            restore_transform(

                self.viewport,

                current_view,

            )

            self.update_properties_panel()

        except Exception as exc:

            QMessageBox.critical(

                self,

                "Update From Source",

                str(exc),

            )

    original_resize = getattr(

        CadPage,

        "resizeEvent",

        None,

    )

    def cad_resize(self, event):

        if callable(original_resize):

            original_resize(

                self,

                event,

            )

        self._position_tool_panel_dock()

        if (

            hasattr(self, "tool_panel_dock")

            and self.tool_panel_dock.isVisible()

        ):

            self.tool_panel_dock.raise_()

        if (

            hasattr(self, "history_panel")

            and self.history_panel.isVisible()

        ):

            self.history_panel.raise_()

    CadPage._available_left_height = (

        _available_left_height

    )

    CadPage._position_tool_panel_dock = (

        _position_tool_panel_dock

    )

    CadPage.show_layers_panel = (

        show_layers_panel

    )

    CadPage.hide_layers_panel = (

        hide_layers_panel

    )

    CadPage.show_properties_panel = (

        show_properties_panel

    )

    CadPage.hide_properties_panel = (

        hide_properties_panel

    )

    CadPage.update_properties_panel = (

        update_properties_panel

    )

    CadPage.reload_from_source = (

        reload_from_source

    )

    CadPage.resizeEvent = (

        cad_resize

    )

    original_history_item_clicked = getattr(

        CadPage,

        "_history_item_clicked",

        None,

    )

    if callable(original_history_item_clicked):

        def cad_history_item_clicked(

            self,

            index,

            *args,

            **kwargs

        ):

            result = original_history_item_clicked(

                self,

                index,

                *args,

                **kwargs

            )

            def refresh_after_history_selection():

                if not hasattr(

                    self,

                    "tool_panel_dock"

                ):

                    return

                self._position_tool_panel_dock()

                if self.tool_panel_dock.isVisible():

                    self.tool_panel_dock.raise_()

            # _history_item_clicked hides History inside the same

            # event handler. Reflow after Qt has applied that hide.

            QTimer.singleShot(

                0,

                refresh_after_history_selection

            )

            QTimer.singleShot(

                20,

                refresh_after_history_selection

            )

            return result

        CadPage._history_item_clicked = (

            cad_history_item_clicked

        )

    original_show_history_menu = getattr(

        CadPage,

        "show_history_menu",

        None,

    )

    if callable(original_show_history_menu):

        def cad_show_history_menu(

            self,

            *args,

            **kwargs

        ):

            result = original_show_history_menu(

                self,

                *args,

                **kwargs

            )

            def refresh_dock_geometry():

                if not hasattr(

                    self,

                    "tool_panel_dock"

                ):

                    return

                available_height = (

                    self._available_left_height()

                )

                self.tool_panel_dock.setGeometry(

                    0,

                    0,

                    ToolPanelDock.PANEL_WIDTH,

                    available_height,

                )

                self.tool_panel_dock.rebuild()

                if self.tool_panel_dock.isVisible():

                    self.tool_panel_dock.raise_()

                if (

                    hasattr(self, "history_panel")

                    and self.history_panel.isVisible()

                ):

                    self.history_panel.raise_()

                self.tool_panel_dock.updateGeometry()

                self.tool_panel_dock.update()

            # Immediate update.

            refresh_dock_geometry()

            # Critical: Qt updates History visibility/layout after

            # the click handler. Recalculate again on the next event loop.

            QTimer.singleShot(

                0,

                refresh_dock_geometry

            )

            QTimer.singleShot(

                25,

                refresh_dock_geometry

            )

            return result

        CadPage.show_history_menu = (

            cad_show_history_menu

        )

    # ========================================================

    # PROJECT SERIALIZATION

    # ========================================================

    def serialize_workspace(page):

        dock_order = []

        dock = getattr(

            page,

            "tool_panel_dock",

            None,

        )

        if dock is not None:

            for panel in getattr(

                dock,

                "_open_order",

                [],

            ):

                if panel is getattr(

                    page,

                    "layers_panel",

                    None,

                ):

                    dock_order.append(

                        "layers"

                    )

                elif panel is getattr(

                    page,

                    "properties_panel",

                    None,

                ):

                    dock_order.append(

                        "properties"

                    )

        layers_collapsed = bool(

            getattr(

                getattr(

                    page,

                    "layers_panel",

                    None,

                ),

                "_collapsed",

                False,

            )

        )

        history_visible = bool(

            hasattr(

                page,

                "history_panel",

            )

            and page.history_panel.isVisible()

        )

        return {

            "dock_open_order": dock_order,

            "layers_collapsed": layers_collapsed,
            "properties_collapsed": bool(getattr(getattr(page, "properties_panel", None), "_collapsed", False)),

            "history_visible": history_visible,

        }

    def serialize_page(page):

        viewport = page.viewport

        panel = page.layers_panel

        source_path = getattr(page, "_source_cad_path", None) or getattr(page, "cad_path", None)

        layers = {}

        for name in viewport.get_layer_names():

            layers[name] = {

                "type": viewport.get_layer_type(name),

                "visible": viewport.is_layer_selected(name),

            }

        history_entries = []

        for item in getattr(page, "history", []):

            if isinstance(item, dict):

                history_entries.append({

                    "label": str(item.get("label", "")),

                })

        project_path = getattr(page, "_project_path", None)

        project_name = Path(project_path).stem if project_path else Path(str(source_path)).stem

        return {

            "format": PROJECT_FORMAT,

            "version": PROJECT_VERSION,

            "project_name": project_name,

            "source": {

                "cad": str(source_path),

            },

            "layers": layers,

            "layer_order": list(getattr(panel, "_layer_order", viewport.get_layer_names())),

            "viewport": transform_to_dict(viewport),

            "workspace": serialize_workspace(page),

            "export_details": (
                page.export_details_panel.values()
                if hasattr(page, "export_details_panel")
                and hasattr(page.export_details_panel, "values")
                else dict(getattr(page, "_export_details", {}))
            ),

            "history": {

                "index": int(getattr(page, "history_index", -1)),

                "entries": history_entries,

            },

        }

    def write_project(page, output_path):

        output_path = Path(output_path)

        if output_path.suffix.lower() != ".p3d":

            output_path = output_path.with_suffix(".p3d")

        data = serialize_page(page)

        data["project_name"] = output_path.stem

        temp_path = output_path.with_suffix(output_path.suffix + ".tmp")

        temp_path.write_text(

            json.dumps(data, ensure_ascii=False, indent=2),

            encoding="utf-8",

        )

        temp_path.replace(output_path)

        page._project_path = str(output_path)

        return output_path

    def save_project(window):

        page = active_page(window)

        if page is None:

            return

        project_path = getattr(page, "_project_path", None)

        if not project_path:

            return save_project_as(window)

        try:

            saved = write_project(page, project_path)

            index = window.tabs.indexOf(page)

            if index >= 0:

                window.tabs.setTabText(index, saved.stem)

                page.update_properties_panel()

        except Exception as exc:

            QMessageBox.critical(window, "Save Project", str(exc))

    def save_project_as(window):

        page = active_page(window)

        if page is None:

            return

        source = getattr(page, "cad_path", "Plan3D_Project")

        suggested = Path(str(source)).stem + ".p3d"

        file_path, _ = QFileDialog.getSaveFileName(

            window,

            "Save Plan3D Project As",

            suggested,

            "Plan3D Project (*.p3d)",

        )

        if not file_path:

            return

        try:

            saved = write_project(page, file_path)

            index = window.tabs.indexOf(page)

            if index >= 0:

                window.tabs.setTabText(index, saved.stem)

                page.update_properties_panel()

        except Exception as exc:

            QMessageBox.critical(window, "Save As", str(exc))

    def restore_workspace(page, workspace):
        if not isinstance(workspace, dict):
            return
        dock = getattr(page, "tool_panel_dock", None)
        if dock is None:
            return

        for panel in list(getattr(dock, "_open_order", [])):
            dock.close_panel(panel)
        dock._open_order = []

        layers = getattr(page, "layers_panel", None)
        props = getattr(page, "properties_panel", None)

        if layers is not None:
            layers._collapsed = False
            layers.body.show()
            layers.setMinimumHeight(layers.HEADER_HEIGHT + 70)
            layers.setMaximumHeight(16777215)
        if props is not None:
            props._collapsed = False
            props.scroll.show()
            props.setMinimumHeight(props.HEADER_HEIGHT + 70)
            props.setMaximumHeight(16777215)

        for name in workspace.get("dock_open_order", []):
            if name == "layers":
                page.show_layers_panel()
            elif name == "properties":
                page.show_properties_panel()

        if layers is not None and bool(workspace.get("layers_collapsed", False)):
            layers.toggle_collapsed()
        if props is not None and bool(workspace.get("properties_collapsed", False)):
            props.toggle_collapsed()

        history = getattr(page, "history_panel", None)
        if history is not None:
            target = bool(workspace.get("history_visible", False))
            if target != bool(history.isVisible()):
                page.show_history_menu()

        def reflow():
            try:
                page._position_tool_panel_dock()
            except Exception:
                pass
            try:
                if page.tool_panel_dock.isVisible():
                    page.tool_panel_dock.raise_()
            except Exception:
                pass
            try:
                if page.history_panel.isVisible():
                    page.history_panel.raise_()
            except Exception:
                pass
        QTimer.singleShot(0, reflow)
        QTimer.singleShot(30, reflow)

    def open_project_file(window, project_path):

        project_path = Path(project_path)

        try:

            data = json.loads(

                project_path.read_text(

                    encoding="utf-8"

                )

            )

        except Exception as exc:

            QMessageBox.critical(

                window,

                "Open Project",

                "Invalid project file:\n" + str(exc),

            )

            return None

        if data.get("format") != PROJECT_FORMAT:

            QMessageBox.critical(

                window,

                "Open Project",

                "This is not a Plan3D project file.",

            )

            return None

        source_data = data.get(

            "source",

            {}

        )

        # Current format

        cad_value = source_data.get(

            "cad"

        )

        # Future / managed-copy compatible fallbacks

        if not cad_value:

            cad_value = source_data.get(

                "managed_dwg"

            )

        if not cad_value:

            cad_value = source_data.get(

                "original_path"

            )

        if not cad_value:

            QMessageBox.critical(

                window,

                "Open Project",

                "No CAD path was found in this project file.",

            )

            return None

        cad_path = Path(

            str(cad_value)

        )

        if not cad_path.exists():

            QMessageBox.critical(

                window,

                "Open Project",

                "CAD file was not found:\n"

                + str(cad_path),

            )

            return None

        # Do not open same .p3d twice.

        for index in range(

            window.tabs.count()

        ):

            existing = window.tabs.widget(

                index

            )

            if isinstance(

                existing,

                CadPage

            ):

                existing_project = getattr(

                    existing,

                    "_project_path",

                    None,

                )

                if existing_project:

                    try:

                        if (

                            Path(existing_project).resolve()

                            == project_path.resolve()

                        ):

                            window.tabs.setCurrentIndex(

                                index

                            )

                            return existing

                    except Exception:

                        pass

        # ----------------------------------------------------

        # Create page

        # ----------------------------------------------------

        try:

            page = CadPage(

                str(cad_path),

                window.tabs,

            )

        except TypeError:

            page = CadPage(

                str(cad_path)

            )

        except Exception as exc:

            QMessageBox.critical(

                window,

                "Open Project",

                "CAD page could not be created:\n"

                + str(exc),

            )

            return None

        page._project_path = str(

            project_path

        )

        page._source_cad_path = str(

            cad_path

        )

        # ----------------------------------------------------

        # Explicitly ensure CAD geometry is loaded.

        # Do not assume CadPage constructor completed it.

        # ----------------------------------------------------

        viewport = page.viewport

        def scene_has_geometry():

            try:

                scene = viewport.scene()

                return (

                    scene is not None

                    and len(scene.items()) > 0

                )

            except Exception:

                return False

        if not scene_has_geometry():

            try:

                viewport.load_file(

                    str(cad_path)

                )

            except Exception as exc:

                QMessageBox.critical(

                    window,

                    "Open Project",

                    "CAD drawing could not be loaded:\n"

                    + str(exc),

                )

                page.deleteLater()

                return None

        if not scene_has_geometry():

            QMessageBox.critical(

                window,

                "Open Project",

                "The CAD file was opened, but no drawable geometry was loaded.",

            )

            page.deleteLater()

            return None

        # ----------------------------------------------------

        # Restore layer state AFTER geometry exists

        # ----------------------------------------------------

        layer_data = data.get(

            "layers",

            {}

        )

        current_layers = list(

            viewport.get_layer_names()

        )

        for name in current_layers:

            saved = layer_data.get(

                name,

                {}

            )

            viewport.set_layer_type(

                name,

                saved.get(

                    "type",

                    "Unassigned",

                ),

            )

            viewport.set_layer_selected(

                name,

                saved.get(

                    "visible",

                    True,

                ),

            )

        # ----------------------------------------------------

        # Restore layer order

        # ----------------------------------------------------

        saved_order = data.get(

            "layer_order",

            []

        )

        ordered = [

            name

            for name in saved_order

            if name in current_layers

        ]

        ordered.extend(

            name

            for name in current_layers

            if name not in ordered

        )

        page.layers_panel._layer_order = (

            ordered

        )

        page.layers_panel.load_layers(

            viewport

        )

        # ----------------------------------------------------
        # Restore Export Details / confirmed Floor-Facade assignments
        # ----------------------------------------------------

        export_data = data.get("export_details", {})
        export_panel = getattr(page, "export_details_panel", None)
        if export_panel is not None and hasattr(export_panel, "load_data"):
            try:
                export_panel.load_data(export_data)
                page._export_details = export_panel.values()
            except Exception as exc:
                print("EXPORT DETAILS RESTORE ERROR |", exc)

        # ----------------------------------------------------

        # Restore history metadata

        # ----------------------------------------------------

        history_data = data.get(

            "history",

            {}

        )

        saved_entries = history_data.get(

            "entries",

            []

        )

        if saved_entries:

            page.history = [

                {

                    "label": str(

                        entry.get(

                            "label",

                            "",

                        )

                    ),

                    "state": None,

                }

                for entry in saved_entries

            ]

            page.history_index = int(

                history_data.get(

                    "index",

                    len(page.history) - 1,

                )

            )

            page.history_index = max(

                0,

                min(

                    page.history_index,

                    len(page.history) - 1,

                ),

            )

            if hasattr(

                page,

                "_update_history_text"

            ):

                page._update_history_text()

        # ----------------------------------------------------

        # Insert tab

        # ----------------------------------------------------

        project_name = data.get(

            "project_name",

            project_path.stem,

        )

        insert_index = window.tabs.count()

        if (

            insert_index > 0

            and window.tabs.tabText(

                insert_index - 1

            ) == "+"

        ):

            insert_index -= 1

        index = window.tabs.insertTab(

            insert_index,

            page,

            project_name,

        )

        window.tabs.setCurrentIndex(

            index

        )

        # ----------------------------------------------------

        # Viewport restore

        #

        # First guarantee that drawing is visible.

        # Then restore the saved camera state only after Qt

        # has completed scene/layout creation.

        # ----------------------------------------------------

        try:

            if hasattr(

                viewport,

                "_apply_home_view"

            ):

                viewport._apply_home_view()

        except Exception:

            pass

        viewport_state = data.get(

            "viewport",

            {}

        )

        def restore_saved_view():

            if not scene_has_geometry():

                return

            if isinstance(

                viewport_state,

                dict

            ) and viewport_state:

                try:

                    restore_transform(

                        viewport,

                        viewport_state,

                    )

                except Exception:

                    try:

                        viewport._apply_home_view()

                    except Exception:

                        pass

            viewport.viewport().update()

        QTimer.singleShot(

            50,

            restore_saved_view

        )

        QTimer.singleShot(

            0,

            page.update_properties_panel,

        )

        workspace_data = data.get(

            "workspace",

            {}

        )

        QTimer.singleShot(

            70,

            lambda:

            restore_workspace(

                page,

                workspace_data,

            )

        )
        return page

    def open_project(window):

        file_path, _ = QFileDialog.getOpenFileName(

            window,

            "Open Plan3D Project",

            "",

            "Plan3D Project (*.p3d)",

        )

        if not file_path:

            return

        return open_project_file(

            window,

            file_path,

        )

    # ========================================================

    # MAIN WINDOW PATCHES

    # ========================================================

    def mainwindow_open_project(self):

        return open_project(self)

    MainWindow.open_project = mainwindow_open_project

    def show_properties_panel(window):

        page = active_page(window)

        if page is None:

            return

        page.show_properties_panel()

    MainWindow.show_properties_panel = show_properties_panel

    original_main_init = MainWindow.__init__

    def main_init(self, *args, **kwargs):

        original_main_init(self, *args, **kwargs)

        # Reconnect File actions

        for action in self.findChildren(QAction):

            text = action.text().replace("&", "").strip()

            if text == "Open Project":

                try:

                    action.triggered.disconnect()

                except Exception:

                    pass

                action.triggered.connect(

                    lambda checked=False: open_project(self)

                )

            elif text == "Save Project":

                try:

                    action.triggered.disconnect()

                except Exception:

                    pass

                action.triggered.connect(

                    lambda checked=False: save_project(self)

                )

            elif text == "Save As":

                try:

                    action.triggered.disconnect()

                except Exception:

                    pass

                action.triggered.connect(

                    lambda checked=False: save_project_as(self)

                )

        # Add Tools > Properties

        tools_menu = None

        for menu_action in self.menuBar().actions():

            text = menu_action.text().replace("&", "").strip()

            if text == "Tools":

                tools_menu = menu_action.menu()

                break

        if tools_menu is not None:

            existing = None

            for action in tools_menu.actions():

                if action.text().replace("&", "").strip() == "Properties":

                    existing = action

                    break

            if existing is None:

                properties_action = QAction("Properties", self)

                properties_action.triggered.connect(

                    lambda checked=False: self.show_properties_panel()

                )

                tools_menu.addAction(properties_action)

    MainWindow.__init__ = main_init

