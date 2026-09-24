from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QComboBox,
    QHBoxLayout,
    QToolButton,
)


SEMANTIC_TYPES = [
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


def install_panel_integrity_patch(
    CadPage,
    LayersPanel,
    EyeToggleButton,
):
    # ========================================================
    # LAYERS PANEL - AUTHORITATIVE UI IMPLEMENTATION
    # ========================================================

    LayersPanel.TYPE_COLORS = dict(TYPE_COLORS)

    def load_layers(self, viewport):
        self._viewport = viewport

        # Completely rebuild UI rows.
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

        if viewport is None:
            return

        source_names = []
        source_label = "none"

        # 1. Normal viewport API
        try:
            source_names = list(
                viewport.get_layer_names()
            )
            if source_names:
                source_label = "get_layer_names"
        except Exception as exc:
            print(
                "LAYER PANEL | get_layer_names error:",
                exc,
            )

        # 2. Existing viewport runtime dictionaries
        if not source_names:
            for attr_name in (
                "_layer_items",
                "_layer_types",
                "_layer_visibility",
                "_layer_selected",
                "_layer_states",
            ):
                value = getattr(
                    viewport,
                    attr_name,
                    None,
                )

                if isinstance(value, dict) and value:
                    source_names = list(
                        value.keys()
                    )
                    source_label = attr_name
                    break

        # 3. EZDXF document layer table fallback
        if not source_names:
            for attr_name in (
                "doc",
                "_doc",
                "document",
                "_document",
                "_ezdxf_doc",
            ):
                doc = getattr(
                    viewport,
                    attr_name,
                    None,
                )

                if doc is None:
                    continue

                try:
                    names = []

                    for layer in doc.layers:
                        try:
                            name = str(
                                layer.dxf.name
                            )
                        except Exception:
                            continue

                        if name not in names:
                            names.append(name)

                    if names:
                        source_names = names
                        source_label = (
                            attr_name + ".layers"
                        )
                        break
                except Exception:
                    pass

        # 4. Preserve any already known panel order.
        # This is especially important when reopening .p3d.
        saved_order = list(
            getattr(
                self,
                "_layer_order",
                [],
            )
        )

        if not source_names and saved_order:
            source_names = list(saved_order)
            source_label = "_layer_order"

        # Remove duplicates without changing CAD order.
        clean_names = []

        for name in source_names:
            name = str(name)

            if name not in clean_names:
                clean_names.append(name)

        source_names = clean_names

        print(
            "LAYERS SOURCE |",
            source_label,
            "| count =",
            len(source_names),
        )

        layer_names = [
            name
            for name in saved_order
            if name in source_names
        ]

        layer_names.extend(
            name
            for name in source_names
            if name not in layer_names
        )

        self._layer_order = list(layer_names)

        for layer_name in layer_names:
            row = QFrame(self.content)
            row.setObjectName("layerRow")
            row.setFixedHeight(30)

            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(
                7,
                3,
                7,
                3,
            )
            row_layout.setSpacing(7)

            # --------------------------------------------
            # Eye
            # --------------------------------------------

            eye = EyeToggleButton(row)

            try:
                visible = bool(
                    viewport.is_layer_selected(
                        layer_name
                    )
                )
            except Exception:
                visible = True

            eye.setChecked(visible)
            eye.setToolTip(
                "Show / Hide Layer"
            )

            # --------------------------------------------
            # Color swatch
            # --------------------------------------------

            swatch = QFrame(row)
            swatch.setFixedSize(7, 18)

            # --------------------------------------------
            # Name
            # --------------------------------------------

            name_label = QLabel(
                layer_name,
                row,
            )
            name_label.setObjectName(
                "layerName"
            )
            name_label.setMinimumWidth(80)

            # --------------------------------------------
            # Semantic type
            # --------------------------------------------

            type_box = QComboBox(row)
            type_box.addItems(
                SEMANTIC_TYPES
            )

            try:
                current_type = (
                    viewport.get_layer_type(
                        layer_name
                    )
                )
            except Exception:
                current_type = "Unassigned"

            if (
                current_type
                not in SEMANTIC_TYPES
            ):
                current_type = "Unassigned"

            type_box.setCurrentText(
                current_type
            )

            swatch.setStyleSheet(
                "background-color:"
                + TYPE_COLORS.get(
                    current_type,
                    TYPE_COLORS["Unassigned"],
                )
                + "; border:none;"
            )

            # --------------------------------------------
            # Signals
            # --------------------------------------------

            def on_eye_changed(
                checked,
                lname=layer_name,
            ):
                try:
                    viewport.set_layer_selected(
                        lname,
                        checked,
                    )
                except Exception as exc:
                    print(
                        "LAYER VISIBILITY ERROR |",
                        lname,
                        exc,
                    )

                try:
                    viewport.viewport().update()
                except Exception:
                    pass

            def on_type_changed(
                value,
                lname=layer_name,
                color_box=swatch,
            ):
                color_box.setStyleSheet(
                    "background-color:"
                    + TYPE_COLORS.get(
                        value,
                        TYPE_COLORS[
                            "Unassigned"
                        ],
                    )
                    + "; border:none;"
                )

                try:
                    viewport.set_layer_type(
                        lname,
                        value,
                    )
                except Exception as exc:
                    print(
                        "LAYER TYPE ERROR |",
                        lname,
                        value,
                        exc,
                    )

                try:
                    viewport.viewport().update()
                except Exception:
                    pass

            eye.toggled.connect(
                on_eye_changed
            )

            type_box.currentTextChanged.connect(
                on_type_changed
            )

            row_layout.addWidget(eye)
            row_layout.addWidget(swatch)
            row_layout.addWidget(
                name_label,
                1,
            )
            row_layout.addWidget(type_box)

            self.content_layout.addWidget(
                row
            )

        self.content_layout.addStretch(1)

        self.content.adjustSize()
        self.content.updateGeometry()
        self.scroll.setWidgetResizable(True)
        self.scroll.viewport().update()

        print(
            "LAYERS PANEL LOADED |",
            len(layer_names),
            "layers"
        )

    LayersPanel.load_layers = load_layers

    # ========================================================
    # HEADER ALIGNMENT
    # ========================================================

    def normalize_headers(page):
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

        layer_buttons = layers.findChildren(
            QToolButton
        )
        prop_buttons = props.findChildren(
            QToolButton
        )

        if (
            len(layer_buttons) < 2
            or len(prop_buttons) < 2
        ):
            return

        layer_header = (
            layer_buttons[0].parentWidget()
        )
        prop_header = (
            prop_buttons[0].parentWidget()
        )

        if (
            layer_header is None
            or prop_header is None
        ):
            return

        layer_layout = layer_header.layout()
        prop_layout = prop_header.layout()

        if (
            layer_layout is None
            or prop_layout is None
        ):
            return

        # Exact same header geometry.
        layer_header.setFixedHeight(28)
        prop_header.setFixedHeight(28)

        margins = (
            layer_layout.contentsMargins()
        )

        prop_layout.setContentsMargins(
            margins.left(),
            margins.top(),
            margins.right(),
            margins.bottom(),
        )
        prop_layout.setSpacing(
            layer_layout.spacing()
        )

        # Layers order:
        # refresh / minimize / close
        layer_min = layer_buttons[-2]
        layer_close = layer_buttons[-1]

        # Properties order:
        # minimize / close
        prop_min = prop_buttons[-2]
        prop_close = prop_buttons[-1]

        pairs = (
            (layer_min, prop_min),
            (layer_close, prop_close),
        )

        for source, target in pairs:
            target.setFixedSize(
                source.size()
            )
            target.setIconSize(
                source.iconSize()
            )
            target.setIcon(
                source.icon()
            )
            target.setText("")
            target.setObjectName(
                source.objectName()
            )
            target.setStyleSheet(
                source.styleSheet()
            )

        props.updateGeometry()
        layers.updateGeometry()

        try:
            page._position_tool_panel_dock()
        except Exception:
            pass

    # ========================================================
    # CAD PAGE HOOK
    # ========================================================

    old_init = CadPage.__init__

    def page_init(
        self,
        *args,
        **kwargs
    ):
        old_init(
            self,
            *args,
            **kwargs
        )

        def repair():
            panel = getattr(
                self,
                "layers_panel",
                None,
            )

            viewport = getattr(
                self,
                "viewport",
                None,
            )

            if (
                panel is not None
                and viewport is not None
            ):
                try:
                    names = list(
                        viewport.get_layer_names()
                    )
                except Exception:
                    names = []

                if names:
                    panel.load_layers(
                        viewport
                    )

            normalize_headers(self)

            try:
                self._position_tool_panel_dock()
            except Exception:
                pass

        # Project open/restore happens asynchronously,
        # so run after the runtime restore passes.
        QTimer.singleShot(
            0,
            repair,
        )

        QTimer.singleShot(
            150,
            repair,
        )

        QTimer.singleShot(
            400,
            repair,
        )

    CadPage.__init__ = page_init

    # ========================================================
    # SHOW LAYERS
    # ========================================================

    old_show_layers = getattr(
        CadPage,
        "show_layers_panel",
        None,
    )

    if old_show_layers is not None:

        def show_layers(
            self,
            *args,
            **kwargs
        ):
            viewport = getattr(
                self,
                "viewport",
                None,
            )

            panel = getattr(
                self,
                "layers_panel",
                None,
            )

            if (
                viewport is not None
                and panel is not None
            ):
                panel.load_layers(
                    viewport
                )

            result = old_show_layers(
                self,
                *args,
                **kwargs
            )

            QTimer.singleShot(
                0,
                lambda:
                normalize_headers(self)
            )

            return result

        CadPage.show_layers_panel = (
            show_layers
        )
