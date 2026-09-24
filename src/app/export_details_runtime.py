from __future__ import annotations

import itertools

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ui_icons import apply_window_tool_icon


class ExportDetailsPanel(QFrame):
    PANEL_WIDTH = 310
    HEADER_HEIGHT = 28

    def __init__(self, parent=None):
        super().__init__(parent)
        self._collapsed = False
        self._confirmed = False
        self._assignments = {"floor_plans": {}, "facades": {}}
        self._analysis_results = {"version": 1, "floor_plans": {}, "facades": {}}
        self._pending_assignment = None

        # 3Dcad pivot contract port.
        # Stored in CAD source XY, one independent pivot per floor.
        self._floor_pivots = {}
        self._pending_pivot_record = None
        self.setObjectName("exportDetailsPanel")
        self.setFixedWidth(self.PANEL_WIDTH)
        self.setStyleSheet("""
            QFrame#exportDetailsPanel {
                background-color: #151515;
                border: 1px solid #343434;
            }
            QFrame#exportDetailsHeader {
                background-color: #1B1B1B;
                border: none;
                border-bottom: 1px solid #313131;
            }
            QLabel#exportDetailsTitle {
                background: transparent;
                color: #E6E6E6;
                border: none;
                font-family: "Segoe UI";
                font-size: 11px;
                font-weight: 600;
            }
            QToolButton#exportDetailsWindowButton {
                background-color: transparent;
                color: #AFAFAF;
                border: none;
            }
            QToolButton#exportDetailsWindowButton:hover {
                background-color: #2A2A2A;
                color: #FFFFFF;
            }
            QWidget#exportDetailsBody {
                background-color: #171717;
                border: none;
            }
            QLabel {
                color: #D0D0D0;
                background: transparent;
                border: none;
                font-family: "Segoe UI";
                font-size: 10px;
            }
            QLineEdit, QComboBox, QDoubleSpinBox {
                min-height: 24px;
                background: #202020;
                color: #D8D8D8;
                border: 1px solid #343434;
                padding: 0 6px;
            }
            QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #4F7EAC;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid #343434;
                background: #1D1E20;
            }
            QComboBox::down-arrow {
                width: 0px;
                height: 0px;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #BFC3C8;
            }
            QPushButton#exportDetailsButton {
                min-height: 28px;
                background: #202020;
                color: #D0D0D0;
                border: 1px solid #353535;
                padding: 5px 10px;
            }
            QPushButton#exportDetailsButton:hover {
                background: #192A3B;
                border: 1px solid #385F86;
                color: #FFFFFF;
            }
            QPushButton#exportDetailsButton:disabled {
                color: #66696E;
                border-color: #2B2D30;
                background: #191A1B;
            }
            QScrollArea#exportDetailsScroll {
                background: #171717;
                border: none;
            }
            QScrollBar:vertical {
                background: #111111;
                width: 7px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background: #484848;
                min-height: 22px;
                border-radius: 3px;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame(self)
        header.setObjectName("exportDetailsHeader")
        header.setFixedHeight(self.HEADER_HEIGHT)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(9, 0, 3, 0)
        header_layout.setSpacing(0)

        title = QLabel("Export Details", header)
        title.setObjectName("exportDetailsTitle")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.minimize_button = QToolButton(header)
        self.minimize_button.setObjectName("exportDetailsWindowButton")
        apply_window_tool_icon(self.minimize_button, "minimize", 18)
        self.minimize_button.setFixedSize(28, 28)
        self.minimize_button.clicked.connect(self.toggle_collapsed)

        self.close_button = QToolButton(header)
        self.close_button.setObjectName("exportDetailsWindowButton")
        apply_window_tool_icon(self.close_button, "close", 18)
        self.close_button.setFixedSize(28, 28)
        self.close_button.clicked.connect(self.hide)

        header_layout.addWidget(self.minimize_button)
        header_layout.addWidget(self.close_button)
        root.addWidget(header)

        self.scroll = QScrollArea(self)
        self.scroll.setObjectName("exportDetailsScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.body = QWidget()
        self.body.setObjectName("exportDetailsBody")
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(10, 10, 10, 10)
        body_layout.setSpacing(10)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)

        self.floor_names = [
            "Basement 3",
            "Basement 2",
            "Basement 1",
            "Ground Floor",
            "First Floor",
            "Second Floor",
            "Third Floor",
            "Fourth Floor",
            "Fifth Floor",
            "Sixth Floor",
            "Seventh Floor",
            "Eighth Floor",
            "Ninth Floor",
            "Tenth Floor",
            "Roof Floor",
        ]

        self._floor_settings = {}
        self._active_floor_name = "Ground Floor"
        self.floor_elevation = self._spin(0.0)
        self.wall_height = self._spin(280.0)
        self.slab_thickness = self._spin(35.0)
        self.floor_to_floor = self._spin(315.0)

        self.floor_elevation.setReadOnly(True)
        self.floor_to_floor.setReadOnly(True)
        self.floor_elevation.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.floor_to_floor.setButtonSymbols(QAbstractSpinBox.NoButtons)

        form.addRow("Floor Elevation (cm)", self.floor_elevation)
        form.addRow("Wall Height (cm)", self.wall_height)
        form.addRow("Slab Thickness (cm)", self.slab_thickness)
        form.addRow("Floor-to-Floor (cm)", self.floor_to_floor)
        body_layout.addLayout(form)

        note = QLabel("Current 3D generation source: Wall lines only.")
        note.setWordWrap(True)
        body_layout.addWidget(note)

        assignment_title = QLabel("VIEWPORT ASSIGNMENT")
        assignment_title.setStyleSheet("color:#78AEFF; font-weight:600; padding-top:4px;")
        body_layout.addWidget(assignment_title)

        assignment_form = QFormLayout()
        assignment_form.setContentsMargins(0, 0, 0, 0)
        assignment_form.setHorizontalSpacing(10)
        assignment_form.setVerticalSpacing(8)

        self.assignment_type = QComboBox()
        self.assignment_type.addItems(["Floor Plan", "Facade"])
        self.assignment_target = QComboBox()
        self.assignment_label = QLabel("Floor")

        assignment_form.addRow("Assignment Type", self.assignment_type)
        body_layout.addLayout(assignment_form)

        self.select_button = QPushButton("Select in Viewport")
        self.select_button.setObjectName("exportDetailsButton")
        body_layout.addWidget(self.select_button)

        self.facade_analysis_button = QPushButton("Facade Analysis")
        # PLAN3D_FACADE_SINGLE_BUTTON_COMPAT_FIX_V2
        # Temporary compatibility aliases for remaining legacy enable/disable references.
        self.show_analysis_button = self.facade_analysis_button
        self.validate_matching_button = self.facade_analysis_button
        self.verify_matching_button = self.facade_analysis_button
        self.window_vertical_button = self.facade_analysis_button
        self.facade_analysis_button.setObjectName("exportDetailsButton")
        body_layout.addWidget(self.facade_analysis_button)

        self.floor_area_button = QPushButton("Show Floor Areas")
        self.floor_area_button.setObjectName("exportDetailsButton")
        body_layout.addWidget(self.floor_area_button)

        self.add_pivot_button = QPushButton("Add Pivot")
        self.add_pivot_button.setObjectName("exportDetailsButton")
        self.add_pivot_button.setEnabled(False)
        body_layout.addWidget(self.add_pivot_button)

        target_form = QFormLayout()
        target_form.setContentsMargins(0, 0, 0, 0)
        target_form.setHorizontalSpacing(10)
        target_form.setVerticalSpacing(8)
        target_form.addRow(self.assignment_label, self.assignment_target)
        body_layout.addLayout(target_form)

        self.selection_status = QLabel(
            "Select an area in the viewport, then assign its name."
        )
        self.selection_status.setWordWrap(True)
        self.selection_status.setStyleSheet("color:#9AA0A6;")
        body_layout.addWidget(self.selection_status)

        self.confirm_button = QPushButton("Confirm Details")
        self.confirm_button.setObjectName("exportDetailsButton")
        self.create_button = QPushButton("Create 3D Model")
        self.create_button.setObjectName("exportDetailsButton")
        self.create_button.setEnabled(False)
        body_layout.addWidget(self.confirm_button)
        body_layout.addWidget(self.create_button)
        body_layout.addStretch()

        self.scroll.setWidget(self.body)
        root.addWidget(self.scroll, 1)

        self.assignment_type.currentTextChanged.connect(self._refresh_assignment_targets)
        self.assignment_target.currentTextChanged.connect(self._assignment_target_changed)
        self.select_button.clicked.connect(self.select_in_viewport)
        self.facade_analysis_button.clicked.connect(self.run_facade_analysis)
        self.floor_area_button.clicked.connect(self.show_floor_areas)
        self.add_pivot_button.clicked.connect(self.add_floor_pivot)
        self.confirm_button.clicked.connect(self.confirm_details)
        self.create_button.clicked.connect(self.create_model)
        for widget in (
            self.wall_height,
            self.slab_thickness,
        ):
            widget.valueChanged.connect(self.mark_dirty)

        self._refresh_assignment_targets()
        ground_index = self.assignment_target.findText("Ground Floor")
        if ground_index >= 0:
            self.assignment_target.setCurrentIndex(ground_index)

        page = self.parentWidget()
        viewport = getattr(
            page,
            "viewport",
            None,
        )

        if (
            viewport is not None
            and hasattr(
                viewport,
                "floorPivotCommitted",
            )
        ):
            viewport.floorPivotCommitted.connect(
                self._on_floor_pivot_committed
            )

        self._refresh_pivot_button_state()
        self.hide()

    def _spin(self, value):
        widget = QDoubleSpinBox()
        widget.setDecimals(2)
        widget.setRange(-100000.0, 100000.0)
        widget.setValue(value)
        widget.setSuffix(" cm")
        return widget

    def _current_floor_target(self):
        if self.assignment_type.currentText() == "Floor Plan":
            name = self.assignment_target.currentText().strip()
            if name:
                return name
        return self._active_floor_name or "Ground Floor"

    # PLAN3D_MANUAL_HEIGHT_AUTO_ELEVATION_V1
    # PLAN3D_CONFIRMED_FLOORS_VERTICAL_FIX_V2
    def _recalculate_floor_verticals(self):
        confirmed = [
            str(name or "").strip()
            for name in self._assignments.get(
                "floor_plans",
                {}
            ).keys()
            if str(name or "").strip()
        ]

        if not confirmed:
            active = str(
                self._active_floor_name
                or "Ground Floor"
            ).strip() or "Ground Floor"
            confirmed = [active]

        ordered = []

        if "Ground Floor" in confirmed:
            ordered.append("Ground Floor")

        for name in list(
            getattr(
                self,
                "floor_names",
                [],
            )
            or []
        ):
            name = str(name or "").strip()

            if (
                name
                and name in confirmed
                and name != "Ground Floor"
                and name not in ordered
            ):
                ordered.append(name)

        for name in confirmed:
            if name not in ordered:
                ordered.append(name)

        running_z = 0.0

        for name in ordered:
            values = self._floor_settings.setdefault(
                name,
                {},
            )

            try:
                wall_height = float(
                    values.get(
                        "wall_height_cm",
                        280.0,
                    )
                )
            except Exception:
                wall_height = 280.0

            try:
                slab_thickness = float(
                    values.get(
                        "slab_thickness_cm",
                        35.0,
                    )
                )
            except Exception:
                slab_thickness = 35.0

            floor_to_floor = wall_height + slab_thickness

            if name == "Ground Floor":
                elevation = 0.0
                running_z = floor_to_floor
            else:
                elevation = running_z
                running_z = elevation + floor_to_floor

            values["floor_elevation_cm"] = float(elevation)
            values["floor_to_floor_cm"] = float(floor_to_floor)

        active = str(
            self._active_floor_name
            or "Ground Floor"
        ).strip() or "Ground Floor"

        active_values = self._floor_settings.get(
            active,
            {},
        )

        self.floor_elevation.blockSignals(True)
        self.floor_to_floor.blockSignals(True)

        try:
            self.floor_elevation.setValue(
                float(
                    active_values.get(
                        "floor_elevation_cm",
                        0.0,
                    )
                )
            )
            self.floor_to_floor.setValue(
                float(
                    active_values.get(
                        "floor_to_floor_cm",
                        315.0,
                    )
                )
            )
        finally:
            self.floor_elevation.blockSignals(False)
            self.floor_to_floor.blockSignals(False)


    def _save_current_floor_settings(self):
        name = str(self._active_floor_name or "").strip()
        if not name:
            return
        self._floor_settings[name] = {
            "floor_elevation_cm": float(self.floor_elevation.value()),
            "wall_height_cm": float(self.wall_height.value()),
            "slab_thickness_cm": float(self.slab_thickness.value()),
            "floor_to_floor_cm": float(
                self.wall_height.value()
                + self.slab_thickness.value()
            ),
        }

        self._recalculate_floor_verticals()

    def _load_floor_settings(self, name):
        name = str(name or "Ground Floor").strip() or "Ground Floor"
        self._active_floor_name = name
        self._recalculate_floor_verticals()
        data = self._floor_settings.get(name, {})
        defaults = {
            "floor_elevation_cm": 0.0,
            "wall_height_cm": 280.0,
            "slab_thickness_cm": 35.0,
            "floor_to_floor_cm": 315.0,
        }
        for widget, key in ((self.floor_elevation,"floor_elevation_cm"),(self.wall_height,"wall_height_cm"),(self.slab_thickness,"slab_thickness_cm"),(self.floor_to_floor,"floor_to_floor_cm")):
            widget.blockSignals(True)
            try:
                widget.setValue(float(data.get(key, defaults[key])))
            except Exception:
                widget.setValue(defaults[key])
            widget.blockSignals(False)

    def values(self):
        self._save_current_floor_settings()
        current_floor = self._current_floor_target()
        current = dict(self._floor_settings.get(current_floor, {}))
        return {
            "floor_name": current_floor,
            "floor_elevation_cm": float(current.get("floor_elevation_cm", self.floor_elevation.value())),
            "wall_height_cm": float(current.get("wall_height_cm", self.wall_height.value())),
            "slab_thickness_cm": float(current.get("slab_thickness_cm", self.slab_thickness.value())),
            "floor_to_floor_cm": float(current.get("floor_to_floor_cm", self.floor_to_floor.value())),
            "floor_settings": {name: dict(values) for name, values in self._floor_settings.items()},
            "confirmed": bool(self._confirmed),
            "assignments": {
                "floor_plans": dict(self._assignments.get("floor_plans", {})),
                "facades": dict(self._assignments.get("facades", {})),
            },
            "analysis": dict(self._analysis_results),
            "pivots": {
                "version": 2,
                "coordinate_space": "cad_source_xy",
                "alignment_rule": "each_floor_reference_maps_to_common_xy",
                "records": {
                    name: dict(record)
                    for name, record
                    in self._floor_pivots.items()
                },
            },
        }

    def _refresh_pivot_button_state(self):
        if not hasattr(
            self,
            "add_pivot_button",
        ):
            return

        floor_mode = (
            self.assignment_type.currentText()
            == "Floor Plan"
        )

        floor_name = (
            self.assignment_target.currentText().strip()
            if self.assignment_target.count()
            else ""
        )

        pending_floor_selected = bool(
            self._pending_assignment
            and self._pending_assignment[0]
            == "floor_plans"
        )

        confirmed_floor_selected = bool(
            floor_name
            and floor_name
            in self._assignments.get(
                "floor_plans",
                {},
            )
        )

        self.add_pivot_button.setEnabled(
            floor_mode
            and (
                pending_floor_selected
                or confirmed_floor_selected
            )
        )

        has_pivot = bool(
            self._pending_pivot_record
            if pending_floor_selected
            else (
                floor_name
                and floor_name
                in self._floor_pivots
            )
        )

        self.add_pivot_button.setText(
            "Edit Pivot"
            if has_pivot
            else "Add Pivot"
        )

    def _sync_pivots_to_viewport(self):
        page = self.parentWidget()
        viewport = getattr(
            page,
            "viewport",
            None,
        )

        if (
            viewport is not None
            and hasattr(
                viewport,
                "set_floor_pivot_records",
            )
        ):
            viewport.set_floor_pivot_records(
                self._floor_pivots
            )

    def add_floor_pivot(self):
        if (
            self.assignment_type.currentText()
            != "Floor Plan"
        ):
            QMessageBox.warning(
                self,
                "Pivot",
                "Select Floor Plan as Assignment Type first.",
            )
            return

        floor_name = (
            self.assignment_target.currentText().strip()
        )

        pending_floor_selected = bool(
            self._pending_assignment
            and self._pending_assignment[0]
            == "floor_plans"
        )

        if pending_floor_selected:
            rect_values = list(
                self._pending_assignment[1]
            )
        else:
            rect_values = self._assignments.get(
                "floor_plans",
                {},
            ).get(
                floor_name
            )

        if rect_values is None:
            QMessageBox.warning(
                self,
                "Pivot",
                "Select a Floor Plan area first.",
            )
            return

        page = self.parentWidget()
        viewport = getattr(
            page,
            "viewport",
            None,
        )

        if (
            viewport is None
            or not hasattr(
                viewport,
                "begin_floor_pivot_selection",
            )
        ):
            QMessageBox.warning(
                self,
                "Pivot",
                "Viewport pivot selection is not available.",
            )
            return

        existing = (
            self._pending_pivot_record
            if pending_floor_selected
            else self._floor_pivots.get(
                floor_name
            )
        )

        try:
            viewport.begin_floor_pivot_selection(
                floor_name,
                rect_values,
                existing,
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Pivot",
                str(exc),
            )
            return

        self.selection_status.setText(
            "Pivot: click/drag on the selected floor. "
            "Snap order: wall vertex -> wall segment -> free point. "
            "Snap radius: 14 px."
        )

    def _on_floor_pivot_committed(
        self,
        floor_name,
        x,
        y,
        snap_kind,
    ):
        floor_name = str(
            floor_name
            or ""
        ).strip()

        if not floor_name:
            return

        pending_floor_selected = bool(
            self._pending_assignment
            and self._pending_assignment[0]
            == "floor_plans"
        )

        bounds = (
            list(
                self._pending_assignment[1]
            )
            if pending_floor_selected
            else list(
                self._assignments.get(
                    "floor_plans",
                    {},
                ).get(
                    floor_name,
                    [],
                )
                or []
            )
        )

        record = {
            "floor_name": floor_name,
            "pivot_x": float(x),
            "pivot_y": float(y),
            "snap_kind": str(
                snap_kind
                or ""
            ),
            "master": (
                floor_name
                == "Ground Floor"
            ),
            "bounds": bounds,
        }

        if pending_floor_selected:
            # Area has been selected but not confirmed yet.
            # Keep the pivot temporary; Confirm Details will bind it
            # to whichever floor name is current at confirmation time.
            self._pending_pivot_record = record
        else:
            self._floor_pivots[
                floor_name
            ] = record
            self._sync_pivots_to_viewport()

        page = self.parentWidget()

        if (
            page is not None
            and not pending_floor_selected
        ):
            page._export_details = (
                self.values()
            )

        self._refresh_pivot_button_state()

        self.selection_status.setText(
            "Pivot selected | "
            + floor_name
            + " | X="
            + f"{float(x):.3f}"
            + " Y="
            + f"{float(y):.3f}"
            + " | Snap="
            + str(
                snap_kind
                or "free"
            )
        )

    def _refresh_assignment_targets(self, *args):
        previous = self.assignment_target.currentText() if self.assignment_target.count() else ""
        is_facade = self.assignment_type.currentText() == "Facade"

        if not is_facade:
            self._save_current_floor_settings()

        self.assignment_target.blockSignals(True)
        self.assignment_target.clear()

        if is_facade:
            self.assignment_label.setText("Facade")
            self.assignment_target.addItems(["Front", "Rear", "Left", "Right"])
        else:
            self.assignment_label.setText("Floor")
            names = list(self.floor_names)

            for source in (
                self._floor_settings.keys(),
                self._assignments.get("floor_plans", {}).keys(),
            ):
                for saved_name in source:
                    if saved_name not in names:
                        names.append(saved_name)

            self.assignment_target.addItems(names)

        # Keep the user's current target where possible.
        preferred = previous

        if not preferred and not is_facade:
            preferred = self._active_floor_name or "Ground Floor"

        idx = self.assignment_target.findText(preferred)

        if idx < 0 and not is_facade:
            idx = self.assignment_target.findText("Ground Floor")

        if idx < 0 and self.assignment_target.count():
            idx = 0

        if idx >= 0:
            self.assignment_target.setCurrentIndex(idx)

        self.assignment_target.blockSignals(False)

        floor_mode = not is_facade

        for widget in (
            self.floor_elevation,
            self.wall_height,
            self.slab_thickness,
            self.floor_to_floor,
        ):
            widget.setEnabled(floor_mode)

        if floor_mode:
            self._assignment_target_changed(
                self.assignment_target.currentText()
            )

        self._refresh_pivot_button_state()

    def _assignment_target_changed(self, text):
        text = str(text).strip()

        if (
            self.assignment_type.currentText() == "Floor Plan"
            and text
        ):
            if self._active_floor_name != text:
                self._save_current_floor_settings()
                self._load_floor_settings(text)

        floor_analysis = (
            self._analysis_results.get(
                "floor_plans",
                {},
            )
            if isinstance(
                self._analysis_results,
                dict,
            )
            else {}
        )

        self.show_analysis_button.setEnabled(
            bool(
                text
                and text in floor_analysis
                and isinstance(
                    floor_analysis.get(
                        text
                    ),
                    dict,
                )
                and floor_analysis.get(
                    text,
                    {},
                ).get(
                    "exterior_wall_system"
                )
            )
        )

        page = self.parentWidget()

        if page is not None:
            page._export_details = self.values()

        # Only redraw.
        # Existing confirmed assignments are never modified here.
        if hasattr(self, "_render_assignment_state"):
            self._render_assignment_state()

        self._refresh_pivot_button_state()


    def _render_assignment_state(self):
        page = self.parentWidget()
        viewport = getattr(page, "viewport", None)

        if viewport is None:
            return

        pending_data = {
            "floor_plans": {},
            "facades": {},
        }

        if self._pending_assignment is not None:
            bucket, rect_values = self._pending_assignment

            name = self.assignment_target.currentText().strip()

            if not name:
                name = "PENDING"

            pending_data[bucket][name] = list(rect_values)

        if hasattr(
            viewport,
            "show_assignment_regions_state",
        ):
            viewport.show_assignment_regions_state(
                self._assignments,
                pending_data,
            )
        elif hasattr(
            viewport,
            "show_assignment_regions",
        ):
            viewport.show_assignment_regions(
                self._assignments,
                confirmed=True,
            )

    def select_in_viewport(self):
        page = self.parentWidget()
        viewport = getattr(page, "viewport", None)

        if (
            viewport is None
            or not hasattr(
                viewport,
                "begin_assignment_selection",
            )
        ):
            QMessageBox.warning(
                self,
                "Export Details",
                "Viewport selection is not available.",
            )
            return

        kind = (
            "facade"
            if self.assignment_type.currentText() == "Facade"
            else "floor_plan"
        )

        # Selection is intentionally anonymous here.
        # The user names it AFTER drawing the rectangle.
        viewport.begin_assignment_selection(
            kind,
            "",
        )

        self.selection_status.setText(
            "Drag a rectangle around the area to assign."
        )


    def accept_viewport_selection(
        self,
        kind,
        name,
        rect_values,
    ):
        bucket = (
            "facades"
            if str(kind) == "facade"
            else "floor_plans"
        )

        # Pending rectangle has NO permanent name yet.
        self._pending_assignment = (
            bucket,
            list(rect_values),
        )
        self._pending_pivot_record = None

        # Lock Floor Plan / Facade type until this rectangle
        # has been confirmed, but allow Floor/Facade NAME selection.
        self.assignment_type.setEnabled(False)

        self.confirm_button.setText(
            "Confirm Details"
        )

        if bucket == "floor_plans":
            self.selection_status.setText(
                "Area selected. Choose its Floor name, "
                "check the floor values, then Confirm Details."
            )
        else:
            self.selection_status.setText(
                "Area selected. Choose its Facade name, "
                "then Confirm Details."
            )

        # Existing confirmed regions + this pending region.
        if hasattr(self, "_render_assignment_state"):
            self._render_assignment_state()

        self._refresh_pivot_button_state()


    def load_data(self, data):
        if not isinstance(data, dict):
            return
        settings = data.get("floor_settings", {})
        self._floor_settings = {
            str(name): dict(values)
            for name, values in settings.items()
            if isinstance(values, dict)
        } if isinstance(settings, dict) else {}
        legacy_floor = str(data.get("floor_name", "Ground Floor") or "Ground Floor")
        if legacy_floor not in self._floor_settings:
            self._floor_settings[legacy_floor] = {
                "floor_elevation_cm": float(data.get("floor_elevation_cm", 0.0)),
                "wall_height_cm": float(data.get("wall_height_cm", 280.0)),
                "slab_thickness_cm": float(data.get("slab_thickness_cm", 35.0)),
                "floor_to_floor_cm": float(data.get("floor_to_floor_cm", 315.0)),
            }
        self._active_floor_name = legacy_floor
        assignments = data.get("assignments", {})
        self._assignments = {
            "floor_plans": dict(assignments.get("floor_plans", {})) if isinstance(assignments, dict) else {},
            "facades": dict(assignments.get("facades", {})) if isinstance(assignments, dict) else {},
        }

        pivots = data.get(
            "pivots",
            {},
        )

        pivot_records = (
            pivots.get(
                "records",
                {},
            )
            if isinstance(
                pivots,
                dict,
            )
            else {}
        )

        self._floor_pivots = {
            str(name): dict(record)
            for name, record
            in pivot_records.items()
            if isinstance(
                record,
                dict,
            )
        }

        analysis = data.get("analysis", {})
        self._analysis_results = dict(analysis) if isinstance(analysis, dict) else {
            "version": 1,
            "floor_plans": {},
            "facades": {},
        }
        self._pending_assignment = None
        self._pending_pivot_record = None
        self.assignment_type.setEnabled(True)
        self._confirmed = bool(data.get("confirmed", False))
        self.create_button.setEnabled(self._confirmed)
        self.confirm_button.setText("Details Confirmed" if self._confirmed else "Confirm Details")
        self.assignment_type.blockSignals(True)
        self.assignment_type.setCurrentText("Floor Plan")
        self.assignment_type.blockSignals(False)
        self._refresh_assignment_targets()
        idx = self.assignment_target.findText(legacy_floor)
        if idx >= 0:
            self.assignment_target.setCurrentIndex(idx)
        self._recalculate_floor_verticals()
        self._load_floor_settings(legacy_floor)

        loaded_floor_analysis = (
            self._analysis_results.get(
                "floor_plans",
                {},
            )
            if isinstance(
                self._analysis_results,
                dict,
            )
            else {}
        )

        self.show_analysis_button.setEnabled(
            bool(
                legacy_floor
                in loaded_floor_analysis
                and isinstance(
                    loaded_floor_analysis.get(
                        legacy_floor
                    ),
                    dict,
                )
                and loaded_floor_analysis.get(
                    legacy_floor,
                    {},
                ).get(
                    "exterior_wall_system"
                )
            )
        )

        total = len(self._assignments["floor_plans"]) + len(self._assignments["facades"])
        self.selection_status.setText(f"{total} viewport assignment(s) loaded." if total else "No viewport assignment selected.")
        if hasattr(self, "_render_assignment_state"):
            self._render_assignment_state()

        self._sync_pivots_to_viewport()
        self._refresh_pivot_button_state()

    def mark_dirty(self, *args):
        if (
            self.assignment_type.currentText()
            == "Floor Plan"
        ):
            self._save_current_floor_settings()

        page = self.parentWidget()

        if page is not None:
            page._export_details = self.values()

        # Numeric editing only updates data.
        # It never removes confirmed or pending viewport assignments.
        if hasattr(self, "_render_assignment_state"):
            self._render_assignment_state()



    def _run_region_analysis(
        self,
        bucket,
        name,
        rect_values,
    ):
        page = self.parentWidget()
        viewport = getattr(
            page,
            "viewport",
            None,
        )

        if (
            viewport is None
            or not hasattr(
                viewport,
                "analyze_assignment_region",
            )
        ):
            return {}

        try:
            result = (
                viewport.analyze_assignment_region(
                    rect_values
                )
            )

            if (
                bucket == "floor_plans"
                and hasattr(
                    viewport,
                    "analyze_exterior_wall_system",
                )
            ):
                result[
                    "exterior_wall_system"
                ] = (
                    viewport.analyze_exterior_wall_system(
                        rect_values
                    )
                )

        except Exception as exc:
            print(
                "REGION ANALYSIS ERROR |",
                name,
                exc,
            )
            return {}

        if not isinstance(
            self._analysis_results,
            dict,
        ):
            self._analysis_results = {
                "version": 1,
                "floor_plans": {},
                "facades": {},
            }

        self._analysis_results.setdefault(
            "version",
            1,
        )

        self._analysis_results.setdefault(
            "floor_plans",
            {},
        )

        self._analysis_results.setdefault(
            "facades",
            {},
        )

        analysis_bucket = (
            self._analysis_results.setdefault(
                bucket,
                {},
            )
        )

        analysis_bucket[name] = result

        return result

    def _remove_replaced_assignment(
        self,
        bucket,
        new_name,
        new_rect,
    ):
        """
        Detect an already-confirmed drawing region that is being edited.

        Re-selecting the same drawing region is treated as EDIT/REPLACE,
        not as a second independent record.

        All stale information belonging to the old region is removed:
        - old assignment name/bounds
        - old region analysis
        - old floor settings (for Floor Plan regions)

        The caller then writes the newly confirmed complete record.
        """
        try:
            nx, ny, nw, nh = [
                float(v)
                for v in new_rect
            ]
        except Exception:
            return []

        nleft = min(nx, nx + nw)
        nright = max(nx, nx + nw)
        ntop = min(ny, ny + nh)
        nbottom = max(ny, ny + nh)

        narea = max(
            0.0,
            (nright - nleft)
            * (nbottom - ntop),
        )

        if narea <= 0:
            return []

        assignment_bucket = self._assignments.setdefault(
            bucket,
            {},
        )

        replaced = []

        for old_name, old_rect in list(
            assignment_bucket.items()
        ):
            try:
                ox, oy, ow, oh = [
                    float(v)
                    for v in old_rect
                ]
            except Exception:
                continue

            oleft = min(ox, ox + ow)
            oright = max(ox, ox + ow)
            otop = min(oy, oy + oh)
            obottom = max(oy, oy + oh)

            oarea = max(
                0.0,
                (oright - oleft)
                * (obottom - otop),
            )

            if oarea <= 0:
                continue

            ix = max(
                0.0,
                min(nright, oright)
                - max(nleft, oleft),
            )
            iy = max(
                0.0,
                min(nbottom, obottom)
                - max(ntop, otop),
            )

            intersection = ix * iy
            union = narea + oarea - intersection

            iou = (
                intersection / union
                if union > 0
                else 0.0
            )

            smaller_area = min(
                narea,
                oarea,
            )

            containment = (
                intersection / smaller_area
                if smaller_area > 0
                else 0.0
            )

            # Same drawing region:
            # - substantial overlap, OR
            # - one selection almost contains the other.
            same_region = (
                iou >= 0.50
                or containment >= 0.80
            )

            if not same_region:
                continue

            replaced.append({
                "name": old_name,
                "rect": list(old_rect),
                "same_name": old_name == new_name,
            })

            assignment_bucket.pop(
                old_name,
                None,
            )

            analysis_bucket = (
                self._analysis_results.get(
                    bucket,
                    {},
                )
                if isinstance(
                    self._analysis_results,
                    dict,
                )
                else {}
            )

            if isinstance(
                analysis_bucket,
                dict,
            ):
                analysis_bucket.pop(
                    old_name,
                    None,
                )

            if bucket == "floor_plans":
                # The complete floor record will be written again from
                # the currently visible Export Details values.
                self._floor_settings.pop(
                    old_name,
                    None,
                )

                # A pivot belongs to the confirmed physical floor record.
                # Keep it only when the same floor name is being edited.
                if old_name != new_name:
                    self._floor_pivots.pop(
                        old_name,
                        None,
                    )

        return replaced

    def confirm_details(self):
        if self._pending_assignment is None:
            QMessageBox.warning(
                self,
                "Export Details",
                "Select an area in the viewport first.",
            )
            return

        bucket, rect_values = self._pending_assignment

        name = self.assignment_target.currentText().strip()

        if not name:
            QMessageBox.warning(
                self,
                "Export Details",
                "Choose a Floor or Facade name.",
            )
            return

        # Capture ALL currently edited floor values before touching
        # the previous record. These become the new authoritative values.
        new_floor_values = None

        if bucket == "floor_plans":
            if self.wall_height.value() <= 0:
                QMessageBox.warning(
                    self,
                    "Export Details",
                    "Wall Height must be greater than 0.",
                )
                return

            new_floor_values = {
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
                    self.wall_height.value()
                    + self.slab_thickness.value()
                ),
            }

        # If this is an edit of an existing drawing region, remove the
        # COMPLETE old record first. Other independent regions are untouched.
        replaced_records = self._remove_replaced_assignment(
            bucket,
            name,
            rect_values,
        )

        # Write the new authoritative assignment geometry/name.
        self._assignments.setdefault(
            bucket,
            {},
        )[name] = list(rect_values)

        # Write the complete current floor settings snapshot.
        if bucket == "floor_plans":
            self._active_floor_name = name
            self._floor_settings[name] = dict(
                new_floor_values
            )

        # Bind a pivot chosen after area selection to the final confirmed
        # floor name and bounds.
        if (
            bucket == "floor_plans"
            and isinstance(
                self._pending_pivot_record,
                dict,
            )
        ):
            pivot_record = dict(
                self._pending_pivot_record
            )
            pivot_record[
                "floor_name"
            ] = name
            pivot_record[
                "master"
            ] = (
                name
                == "Ground Floor"
            )
            pivot_record[
                "bounds"
            ] = list(
                rect_values
            )

            self._floor_pivots[
                name
            ] = pivot_record

        # Rebuild analysis from the NEW region geometry and current semantics.
        analysis = self._run_region_analysis(
            bucket,
            name,
            rect_values,
        )

        self._pending_assignment = None
        self._pending_pivot_record = None
        self.assignment_type.setEnabled(True)

        self._confirmed = (
            bool(
                self._assignments.get(
                    "floor_plans"
                )
            )
            or bool(
                self._assignments.get(
                    "facades"
                )
            )
        )

        self.create_button.setEnabled(
            self._confirmed
        )
        self.confirm_button.setText(
            "Details Confirmed"
        )

        self._sync_pivots_to_viewport()
        self._refresh_pivot_button_state()

        current_bucket = (
            self._analysis_results.get(
                bucket,
                {},
            )
            if isinstance(
                self._analysis_results,
                dict,
            )
            else {}
        )

        current_analysis = (
            current_bucket.get(
                name,
                {},
            )
            if isinstance(
                current_bucket,
                dict,
            )
            else {}
        )

        counts = (
            current_analysis.get(
                "entity_counts",
                {},
            )
            if isinstance(
                current_analysis,
                dict,
            )
            else {}
        )

        count_text = ", ".join(
            f"{key}: {value}"
            for key, value in counts.items()
            if value
        )

        exterior_system = (
            current_analysis.get(
                "exterior_wall_system",
                {},
            )
            if isinstance(
                current_analysis,
                dict,
            )
            else {}
        )

        exterior_summary = ""

        if isinstance(
            exterior_system,
            dict,
        ):
            chains = exterior_system.get(
                "chains",
                {},
            )

            chain_count = sum(
                1
                for value
                in chains.values()
                if isinstance(
                    value,
                    dict,
                )
                and value.get(
                    "segment_count",
                    0,
                )
            )

            opening_count = len(
                exterior_system.get(
                    "exterior_openings",
                    [],
                )
            )

            if chain_count:
                exterior_summary = (
                    f" Exterior chains: {chain_count},"
                    f" exterior openings: {opening_count}."
                )

        status = name + " confirmed." + exterior_summary

        if replaced_records:
            replaced_names = [
                item.get("name", "")
                for item in replaced_records
                if item.get("name")
            ]

            if replaced_names:
                status += (
                    " Updated previous region: "
                    + ", ".join(replaced_names)
                    + "."
                )

        if count_text:
            status += "  " + count_text

        status += (
            "  Select another area when ready."
        )

        self.selection_status.setText(
            status
        )

        if bucket == "floor_plans":
            self.show_analysis_button.setEnabled(
                bool(
                    current_analysis.get(
                        "exterior_wall_system"
                    )
                )
            )

        page = self.parentWidget()

        if page is not None:
            # Persist the COMPLETE current state immediately in the page cache.
            page._export_details = self.values()

        # Redraw only from the new authoritative records.
        # Old labels/bounds for the edited region disappear.
        if hasattr(
            self,
            "_render_assignment_state",
        ):
            self._render_assignment_state()





    def _score_plan_side_to_facade(
        self,
        side,
        floor_results,
        facade_result,
        reverse_facade=False,
    ):
        """
        Score one plan side against one facade by combining FLOOR-BY-FLOOR
        architectural evidence. Empty floors are ignored as evidence.
        """
        facade_floors = (
            facade_result.get(
                "floors",
                {},
            )
            if isinstance(
                facade_result,
                dict,
            )
            else {}
        )

        floor_matches = []
        all_pairs = []
        weighted_total = 0.0
        total_weight = 0.0

        for floor_name, floor_result in floor_results.items():
            if not isinstance(
                floor_result,
                dict,
            ):
                continue

            plan_payload = (
                floor_result.get(
                    "chains",
                    {},
                ).get(
                    side,
                    {},
                )
            )

            plan_openings = (
                plan_payload.get(
                    "openings",
                    [],
                )
                if isinstance(
                    plan_payload,
                    dict,
                )
                else []
            )

            facade_payload = (
                facade_floors.get(
                    floor_name,
                    {},
                )
            )

            facade_openings = (
                facade_payload.get(
                    "openings",
                    [],
                )
                if isinstance(
                    facade_payload,
                    dict,
                )
                else []
            )

            floor_match = (
                self._architectural_floor_match(
                    plan_openings,
                    facade_openings,
                    reverse_facade=reverse_facade,
                )
            )

            floor_match[
                "floor_name"
            ] = floor_name
            floor_matches.append(
                floor_match
            )

            for pair in floor_match[
                "opening_pairs"
            ]:
                enriched = dict(
                    pair
                )
                enriched[
                    "floor_name"
                ] = floor_name
                all_pairs.append(
                    enriched
                )

            # Weight each floor by the number of actual openings that provide
            # evidence. An empty floor contributes no identifying weight.
            evidence_weight = max(
                len(
                    plan_openings
                ),
                len(
                    facade_openings
                ),
            )

            if evidence_weight > 0:
                weighted_total += (
                    floor_match[
                        "score"
                    ]
                    * evidence_weight
                )
                total_weight += (
                    evidence_weight
                )

        final_score = (
            weighted_total
            / total_weight
            if total_weight > 0
            else 0.0
        )

        return {
            "score": float(
                max(
                    0.0,
                    min(
                        1.0,
                        final_score,
                    ),
                )
            ),
            "reverse_facade": bool(
                reverse_facade
            ),
            "floor_matches": floor_matches,
            "opening_pairs": all_pairs,
        }



    # PLAN3D_LAYER_POLYGON_NETWORK_V2
    # PLAN3D_FACADE_MATCHING_RESET_SINGLE_BUTTON_V1
    def run_facade_analysis(self):
        """Single clean entry point for the new facade system."""
        page = self.parentWidget()
        viewport = getattr(page, "viewport", None) if page is not None else None

        if viewport is not None:
            for name in (
                "clear_facade_match_preview",
                "clear_exterior_analysis",
                "clear_exterior_analysis_preview",
                "clear_window_vertical_preview",
            ):
                fn = getattr(viewport, name, None)
                if callable(fn):
                    try:
                        fn()
                    except Exception:
                        pass

        if not isinstance(getattr(self, "_analysis_results", None), dict):
            self._analysis_results = {}

        for key in list(self._analysis_results.keys()):
            key_text = str(key).casefold()
            if (
                "facade" in key_text
                or "matching" in key_text
                or "window_vertical" in key_text
                or "window_height" in key_text
                or "exterior_wall_system" in key_text
            ):
                self._analysis_results.pop(key, None)

        self.selection_status.setText(
            "Facade analysis reset. New facade engine will run from this button."
        )

        print(
            "PLAN3D FACADE ANALYSIS RESET V1 | single button active",
            flush=True,
        )

    def show_floor_areas(self):
        try:
            from floor_area_runtime import show_all_floor_areas

            report = show_all_floor_areas(self)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Floor Areas",
                str(exc),
            )
            return

        floors = report.get("floors", {}) if isinstance(report, dict) else {}
        warnings = report.get("warnings", []) if isinstance(report, dict) else []

        summary = []
        for floor_name, payload in floors.items():
            summary.append(
                str(floor_name)
                + ": "
                + str(payload.get("area_count", 0))
                + " area(s)"
            )

        text = "Floor areas shown"
        if summary:
            text += " | " + " ; ".join(summary)
        if warnings:
            text += " | warnings=" + str(len(warnings))
        self.selection_status.setText(text)

    # PLAN3D_WALL_ONLY_MAX_BRIDGE_V2
    def create_model(self):
        if not self._confirmed:
            QMessageBox.warning(
                self,
                "Create 3D Model",
                "Confirm Export Details first.",
            )
            return

        try:
            from plan3d_max_bridge import (
                prepare_wall_only_transfer,
            )

            result = prepare_wall_only_transfer(
                self
            )

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Create 3D Model",
                str(exc),
            )
            return

        floors = result.get(
            "floors",
            [],
        )

        floor_summary = ", ".join(
            str(item.get("name", ""))
            + "="
            + str(item.get("path_count", 0))
            + " path"
            for item in floors
        )

        self.selection_status.setText(
            "WALL ONLY prepared for 3ds Max | "
            + floor_summary
        )

        QMessageBox.information(
            self,
            "Create 3D Model",
            "Wall-only transfer prepared.\n\n"
            "Floors: "
            + str(len(floors))
            + "\n"
            + floor_summary
            + "\n\n"
            "The active 3ds Max watcher will import it automatically.",
        )


    def toggle_collapsed(self):
        self._collapsed = not self._collapsed
        self.scroll.setVisible(not self._collapsed)
        parent = self.parentWidget()
        if parent is not None and hasattr(parent, "_position_export_details_panel"):
            parent._position_export_details_panel()


def install_export_details_runtime(MainWindow, CadPage):
    old_page_init = CadPage.__init__
    old_resize = getattr(CadPage, "resizeEvent", None)

    def page_init(self, *args, **kwargs):
        old_page_init(self, *args, **kwargs)
        self.export_details_panel = ExportDetailsPanel(self)
        if not hasattr(self, "_export_details"):
            self._export_details = self.export_details_panel.values()
        viewport = getattr(self, "viewport", None)
        if viewport is not None and hasattr(viewport, "assignmentRegionSelected"):
            viewport.assignmentRegionSelected.connect(self.export_details_panel.accept_viewport_selection)

    CadPage.__init__ = page_init

    def position_export_details(self):
        panel = getattr(self, "export_details_panel", None)
        if panel is None or not panel.isVisible():
            return
        available_height = self.height()
        if hasattr(self, "status_bar"):
            available_height -= self.status_bar.height()
        if hasattr(self, "history_panel") and self.history_panel.isVisible():
            available_height -= self.history_panel.height()
        panel_height = panel.HEADER_HEIGHT if panel._collapsed else max(panel.HEADER_HEIGHT, available_height)
        panel.setGeometry(
            max(0, self.width() - panel.PANEL_WIDTH),
            0,
            panel.PANEL_WIDTH,
            panel_height,
        )
        panel.raise_()

    def show_export_details(self):
        panel = getattr(self, "export_details_panel", None)
        if panel is None:
            return
        panel.show()
        self._position_export_details_panel()
        panel.raise_()

    CadPage._position_export_details_panel = position_export_details
    CadPage.show_export_details_panel = show_export_details

    def resize_event(self, event):
        if callable(old_resize):
            old_resize(self, event)
        self._position_export_details_panel()

    CadPage.resizeEvent = resize_event

    old_main_init = MainWindow.__init__

    def main_init(self, *args, **kwargs):
        old_main_init(self, *args, **kwargs)
        tools_menu = None
        for menu_action in self.menuBar().actions():
            if menu_action.text().replace("&", "").strip() == "Tools":
                tools_menu = menu_action.menu()
                break
        if tools_menu is None:
            return
        for action in tools_menu.actions():
            if action.text().replace("&", "").strip() == "Export Details":
                return
        export_action = QAction("Export Details", self)

        def open_export_details():
            if not hasattr(self, "tabs"):
                return
            page = self.tabs.currentWidget()
            if hasattr(page, "show_export_details_panel"):
                page.show_export_details_panel()

        export_action.triggered.connect(open_export_details)
        tools_menu.addAction(export_action)
        self._export_details_action = export_action

    MainWindow.__init__ = main_init

# ============================================================
# PLAN3D_INTERIOR_DOOR_HEIGHT_UI_V1
# Per-floor user-defined interior door height.
# ============================================================

_PLAN3D_DOOR_HEIGHT_DEFAULT_CM = 210.0

_plan3d_door_height_old_init = ExportDetailsPanel.__init__
_plan3d_door_height_old_save = ExportDetailsPanel._save_current_floor_settings
_plan3d_door_height_old_load = ExportDetailsPanel._load_floor_settings
_plan3d_door_height_old_values = ExportDetailsPanel.values
_plan3d_door_height_old_load_data = ExportDetailsPanel.load_data
_plan3d_door_height_old_confirm = ExportDetailsPanel.confirm_details


def _plan3d_door_height_init_v1(self, *args, **kwargs):
    _plan3d_door_height_old_init(self, *args, **kwargs)

    self.door_height = self._spin(
        _PLAN3D_DOOR_HEIGHT_DEFAULT_CM
    )
    self.door_height.setMinimum(1.0)
    self.door_height.setMaximum(10000.0)

    # PLAN3D_INTERIOR_DOOR_HEIGHT_UI_TOP_FORM_V4
    # Put Interior Door Height directly in the main floor settings form,
    # immediately after Wall Height.
    main_form = None

    body_layout = self.body.layout()

    for layout_index in range(body_layout.count()):
        item = body_layout.itemAt(layout_index)
        candidate = item.layout()

        if not isinstance(candidate, QFormLayout):
            continue

        try:
            if candidate.labelForField(self.wall_height) is not None:
                main_form = candidate
                break
        except Exception:
            continue

    if main_form is None:
        raise RuntimeError(
            "Main floor settings form was not found."
        )

    main_form.insertRow(
        2,
        "Interior Door Height (cm)",
        self.door_height,
    )

    self.door_height.valueChanged.connect(
        self.mark_dirty
    )

    try:
        self._load_floor_settings(
            self._active_floor_name
        )
    except Exception:
        pass


def _plan3d_door_height_save_v1(self):
    _plan3d_door_height_old_save(self)

    name = str(
        self._active_floor_name
        or ""
    ).strip()

    if not name:
        return

    values = self._floor_settings.setdefault(
        name,
        {},
    )

    values[
        "door_height_cm"
    ] = float(
        self.door_height.value()
    )


def _plan3d_door_height_load_v1(self, name):
    _plan3d_door_height_old_load(
        self,
        name,
    )

    data = self._floor_settings.get(
        str(name or "").strip(),
        {},
    )

    try:
        value = float(
            data.get(
                "door_height_cm",
                _PLAN3D_DOOR_HEIGHT_DEFAULT_CM,
            )
        )
    except Exception:
        value = (
            _PLAN3D_DOOR_HEIGHT_DEFAULT_CM
        )

    self.door_height.blockSignals(
        True
    )
    try:
        self.door_height.setValue(
            value
        )
    finally:
        self.door_height.blockSignals(
            False
        )


def _plan3d_door_height_values_v1(self):
    result = _plan3d_door_height_old_values(
        self
    )

    current_floor = self._current_floor_target()

    current = self._floor_settings.setdefault(
        current_floor,
        {},
    )

    current[
        "door_height_cm"
    ] = float(
        self.door_height.value()
    )

    result[
        "door_height_cm"
    ] = float(
        current[
            "door_height_cm"
        ]
    )

    result[
        "floor_settings"
    ] = {
        name: dict(values)
        for name, values
        in self._floor_settings.items()
    }

    return result


def _plan3d_door_height_load_data_v1(
    self,
    data,
):
    _plan3d_door_height_old_load_data(
        self,
        data,
    )

    try:
        self._load_floor_settings(
            self._active_floor_name
        )
    except Exception:
        pass


def _plan3d_door_height_confirm_v1(
    self,
):
    result = _plan3d_door_height_old_confirm(
        self
    )

    try:
        self._save_current_floor_settings()
    except Exception:
        pass

    return result


ExportDetailsPanel.__init__ = (
    _plan3d_door_height_init_v1
)
ExportDetailsPanel._save_current_floor_settings = (
    _plan3d_door_height_save_v1
)
ExportDetailsPanel._load_floor_settings = (
    _plan3d_door_height_load_v1
)
ExportDetailsPanel.values = (
    _plan3d_door_height_values_v1
)
ExportDetailsPanel.load_data = (
    _plan3d_door_height_load_data_v1
)
ExportDetailsPanel.confirm_details = (
    _plan3d_door_height_confirm_v1
)

# ============================================================
# PLAN3D_INTERIOR_DOOR_HEIGHT_UI_INIT_FIX_V2
# Old ExportDetailsPanel.__init__ calls _load_floor_settings()
# before self.door_height is created by the V1 wrapper.
# ============================================================

def _plan3d_door_height_load_v2(self, name):
    _plan3d_door_height_old_load(
        self,
        name,
    )

    if not hasattr(
        self,
        "door_height",
    ):
        return

    data = self._floor_settings.get(
        str(name or "").strip(),
        {},
    )

    try:
        value = float(
            data.get(
                "door_height_cm",
                _PLAN3D_DOOR_HEIGHT_DEFAULT_CM,
            )
        )
    except Exception:
        value = _PLAN3D_DOOR_HEIGHT_DEFAULT_CM

    self.door_height.blockSignals(True)
    try:
        self.door_height.setValue(value)
    finally:
        self.door_height.blockSignals(False)


ExportDetailsPanel._load_floor_settings = _plan3d_door_height_load_v2

# ============================================================
# PLAN3D_INTERIOR_DOOR_HEIGHT_BOOTSTRAP_FIX_V3
# Guarantees self.door_height exists during the original panel
# constructor. V1 replaces this bootstrap object with the real
# QDoubleSpinBox immediately after the original init finishes.
# ============================================================

class _Plan3DDoorHeightBootstrapSignalV3:
    def connect(self, *args, **kwargs):
        return None


class _Plan3DDoorHeightBootstrapV3:
    def __init__(self, value=210.0):
        self._value = float(value)
        self.valueChanged = _Plan3DDoorHeightBootstrapSignalV3()

    def value(self):
        return float(self._value)

    def setValue(self, value):
        self._value = float(value)

    def blockSignals(self, value):
        return False

    def setEnabled(self, value):
        return None

    def setReadOnly(self, value):
        return None

    def setButtonSymbols(self, value):
        return None

    def setMinimum(self, value):
        return None

    def setMaximum(self, value):
        return None

    def setDecimals(self, value):
        return None

    def setRange(self, a, b):
        return None

    def setSuffix(self, value):
        return None


_plan3d_door_height_init_before_v3 = ExportDetailsPanel.__init__


def _plan3d_door_height_init_v3(self, *args, **kwargs):
    # Must exist before any old __init__ code or callbacks run.
    self.door_height = _Plan3DDoorHeightBootstrapV3(
        _PLAN3D_DOOR_HEIGHT_DEFAULT_CM
    )

    return _plan3d_door_height_init_before_v3(
        self,
        *args,
        **kwargs,
    )


ExportDetailsPanel.__init__ = _plan3d_door_height_init_v3


# ============================================================
# PLAN3D_EXPORT_DETAILS_ORDER_V1
# Reorder Export Details panel sections so that:
#   1) Viewport Assignment block is at the top of the panel body
#   2) Floor selector block is immediately below it
# The remaining sections keep their relative order.
# ============================================================

def _plan3d_export_details_texts_from_item_v1(item):
    texts = []

    def _walk_layout(layout):
        if layout is None:
            return
        for idx in range(layout.count()):
            _walk_item(layout.itemAt(idx))

    def _walk_widget(widget):
        if widget is None:
            return
        try:
            text_attr = getattr(widget, "text", None)
            if callable(text_attr):
                value = text_attr()
                if isinstance(value, str):
                    value = value.strip()
                    if value:
                        texts.append(value)
        except Exception:
            pass
        try:
            title_attr = getattr(widget, "windowTitle", None)
            if callable(title_attr):
                value = title_attr()
                if isinstance(value, str):
                    value = value.strip()
                    if value:
                        texts.append(value)
        except Exception:
            pass
        child_layout = None
        try:
            child_layout = widget.layout()
        except Exception:
            child_layout = None
        if child_layout is not None:
            _walk_layout(child_layout)

    def _walk_item(sub_item):
        if sub_item is None:
            return
        child_widget = sub_item.widget()
        if child_widget is not None:
            _walk_widget(child_widget)
        child_layout = sub_item.layout()
        if child_layout is not None:
            _walk_layout(child_layout)

    _walk_item(item)
    return texts


def _plan3d_export_details_insert_item_v1(layout, index, item):
    if item is None:
        return
    widget = item.widget()
    if widget is not None:
        layout.insertWidget(index, widget)
        return
    child_layout = item.layout()
    if child_layout is not None:
        layout.insertLayout(index, child_layout)
        return
    spacer = item.spacerItem()
    if spacer is not None:
        layout.insertItem(index, spacer)
        return


def _plan3d_export_details_reorder_v1(panel):
    body = getattr(panel, "body", None)
    layout = None

    if body is not None:
        try:
            layout = body.layout()
        except Exception:
            layout = None

    if layout is None:
        try:
            layout = panel.layout()
        except Exception:
            layout = None

    if layout is None:
        print(
            "PLAN3D EXPORT DETAILS ORDER V1 | skipped=no-layout",
            flush=True,
        )
        return

    top_items = []
    for i in range(layout.count()):
        top_items.append(layout.itemAt(i))

    assignment_index = None
    floor_index = None

    for idx, item in enumerate(top_items):
        texts = _plan3d_export_details_texts_from_item_v1(item)
        lower = [str(t).strip().lower() for t in texts if str(t).strip()]
        exact = set(lower)
        joined = " | ".join(lower)

        if assignment_index is None:
            if (
                "viewport assignment" in joined
                or "assignment type" in joined
                or "select in viewport" in joined
            ):
                assignment_index = idx
                continue

        if floor_index is None:
            if (
                "viewport assignment(s) loaded." in exact
                or (
                    "floor" in exact
                    and "assignment type" not in joined
                    and "select in viewport" not in joined
                )
            ):
                floor_index = idx
                continue

    if assignment_index is None and floor_index is None:
        print(
            "PLAN3D EXPORT DETAILS ORDER V1 | skipped=no-target-sections",
            flush=True,
        )
        return

    count = layout.count()
    extracted = []
    for _ in range(count):
        extracted.append(layout.takeAt(0))

    new_order = []
    for target_index in (assignment_index, floor_index):
        if target_index is None:
            continue
        if 0 <= target_index < len(extracted) and target_index not in new_order:
            new_order.append(target_index)

    for idx in range(len(extracted)):
        if idx not in new_order:
            new_order.append(idx)

    for idx in new_order:
        _plan3d_export_details_insert_item_v1(
            layout,
            layout.count(),
            extracted[idx],
        )

    print(
        "PLAN3D EXPORT DETAILS ORDER V1 | assignment_index=",
        assignment_index,
        "| floor_index=",
        floor_index,
        flush=True,
    )


_PLAN3D_EXPORT_DETAILS_ORDER_V1_ORIGINAL_INIT = ExportDetailsPanel.__init__


def _plan3d_export_details_order_v1_init(self, *args, **kwargs):
    _PLAN3D_EXPORT_DETAILS_ORDER_V1_ORIGINAL_INIT(self, *args, **kwargs)
    try:
        _plan3d_export_details_reorder_v1(self)
    except Exception as exc:
        print(
            "PLAN3D EXPORT DETAILS ORDER V1 | immediate reorder error:",
            exc,
            flush=True,
        )
    try:
        from PySide6.QtCore import QTimer

        QTimer.singleShot(
            0,
            lambda panel=self: _plan3d_export_details_reorder_v1(panel),
        )
    except Exception as exc:
        print(
            "PLAN3D EXPORT DETAILS ORDER V1 | deferred reorder unavailable:",
            exc,
            flush=True,
        )


ExportDetailsPanel.__init__ = _plan3d_export_details_order_v1_init

# ============================================================
# PLAN3D_EXPORT_DETAILS_ASSIGNMENT_ABOVE_FLOOR_V2
#
# Move only the "Assignment Type" row directly above the "Floor" row.
# No behavior/data logic changes.
# ============================================================

def _plan3d_find_form_row_v2(root_widget, label_text):
    from PySide6.QtWidgets import QFormLayout

    target = str(label_text).strip().lower()
    found = []

    def walk_layout(layout):
        if layout is None:
            return

        if isinstance(layout, QFormLayout):
            for row in range(layout.rowCount()):
                label_item = layout.itemAt(
                    row,
                    QFormLayout.ItemRole.LabelRole,
                )

                if label_item is None:
                    continue

                label_widget = label_item.widget()

                if label_widget is None:
                    continue

                text_method = getattr(
                    label_widget,
                    "text",
                    None,
                )

                if not callable(text_method):
                    continue

                try:
                    text = str(text_method()).strip().lower()
                except Exception:
                    continue

                if text == target:
                    found.append(
                        (
                            layout,
                            row,
                            label_widget,
                        )
                    )

        for index in range(layout.count()):
            item = layout.itemAt(index)

            if item is None:
                continue

            child_layout = item.layout()

            if child_layout is not None:
                walk_layout(child_layout)

            child_widget = item.widget()

            if child_widget is not None:
                try:
                    widget_layout = child_widget.layout()
                except Exception:
                    widget_layout = None

                if widget_layout is not None:
                    walk_layout(widget_layout)

    try:
        root_layout = root_widget.layout()
    except Exception:
        root_layout = None

    walk_layout(root_layout)

    return found[0] if found else None


def _plan3d_item_payload_v2(item):
    if item is None:
        return None

    widget = item.widget()

    if widget is not None:
        return widget

    layout = item.layout()

    if layout is not None:
        return layout

    return None


def _plan3d_assignment_above_floor_v2(panel):
    from PySide6.QtWidgets import QFormLayout

    body = getattr(
        panel,
        "body",
        panel,
    )

    assignment = _plan3d_find_form_row_v2(
        body,
        "Assignment Type",
    )

    floor = _plan3d_find_form_row_v2(
        body,
        "Floor",
    )

    if assignment is None:
        print(
            "PLAN3D EXPORT DETAILS ORDER V2 | Assignment Type row not found",
            flush=True,
        )
        return

    if floor is None:
        print(
            "PLAN3D EXPORT DETAILS ORDER V2 | Floor row not found",
            flush=True,
        )
        return

    assignment_form, assignment_row, _assignment_label = assignment
    floor_form, _floor_row, _floor_label = floor

    taken = assignment_form.takeRow(
        assignment_row
    )

    label_payload = _plan3d_item_payload_v2(
        taken.labelItem
    )

    field_payload = _plan3d_item_payload_v2(
        taken.fieldItem
    )

    if label_payload is None or field_payload is None:
        raise RuntimeError(
            "Assignment Type row could not be moved."
        )

    floor_after = _plan3d_find_form_row_v2(
        body,
        "Floor",
    )

    if floor_after is None:
        raise RuntimeError(
            "Floor row disappeared during reorder."
        )

    floor_form, floor_row, _floor_label = floor_after

    floor_form.insertRow(
        floor_row,
        label_payload,
        field_payload,
    )

    print(
        "PLAN3D EXPORT DETAILS ORDER V2 | Assignment Type moved above Floor",
        flush=True,
    )


_PLAN3D_EXPORT_DETAILS_ORDER_V2_PREVIOUS_INIT = (
    ExportDetailsPanel.__init__
)


def _plan3d_export_details_order_v2_init(
    self,
    *args,
    **kwargs,
):
    _PLAN3D_EXPORT_DETAILS_ORDER_V2_PREVIOUS_INIT(
        self,
        *args,
        **kwargs,
    )

    try:
        _plan3d_assignment_above_floor_v2(
            self
        )
    except Exception as exc:
        print(
            "PLAN3D EXPORT DETAILS ORDER V2 | immediate error:",
            exc,
            flush=True,
        )

    try:
        from PySide6.QtCore import QTimer

        QTimer.singleShot(
            0,
            lambda panel=self:
                _plan3d_assignment_above_floor_v2(
                    panel
                ),
        )
    except Exception as exc:
        print(
            "PLAN3D EXPORT DETAILS ORDER V2 | deferred error:",
            exc,
            flush=True,
        )


ExportDetailsPanel.__init__ = (
    _plan3d_export_details_order_v2_init
)

# ============================================================
# PLAN3D_FACADE_ANALYSIS_ALWAYS_ENABLED_V3
# Keep the new single Facade Analysis button permanently enabled.
# Legacy button references are isolated so their old setEnabled()
# calls cannot disable Facade Analysis.
# ============================================================

class _Plan3DFacadeLegacyButtonProxyV3:
    def __init__(self, target):
        self._target = target

    def setEnabled(self, _enabled):
        # Intentionally ignored.
        return None

    def setDisabled(self, _disabled):
        # Intentionally ignored.
        return None

    def __getattr__(self, name):
        return getattr(self._target, name)


_PLAN3D_FACADE_ANALYSIS_ALWAYS_ENABLED_PREV_INIT = (
    ExportDetailsPanel.__init__
)


def _plan3d_facade_analysis_always_enabled_init_v3(
    self,
    *args,
    **kwargs,
):
    _PLAN3D_FACADE_ANALYSIS_ALWAYS_ENABLED_PREV_INIT(
        self,
        *args,
        **kwargs,
    )

    button = getattr(
        self,
        "facade_analysis_button",
        None,
    )

    if button is None:
        raise RuntimeError(
            "Facade Analysis button was not found."
        )

    button.setEnabled(True)

    proxy = _Plan3DFacadeLegacyButtonProxyV3(
        button
    )

    self.show_analysis_button = proxy
    self.validate_matching_button = proxy
    self.verify_matching_button = proxy
    self.window_vertical_button = proxy

    button.setEnabled(True)

    print(
        "PLAN3D FACADE ANALYSIS V3 | button permanently enabled",
        flush=True,
    )


ExportDetailsPanel.__init__ = (
    _plan3d_facade_analysis_always_enabled_init_v3
)

# ============================================================
# PLAN3D_FACADE_BOTTOM_LEFT_EXPORT_LINE_V1
#
# Facade Analysis first diagnostic:
# - uses the SAME export-prepared Wall paths used by Create3D
# - runs for every assigned floor plan
# - finds the visually bottom-most horizontal Wall segment
# - among bottom candidates selects the visually left-most one
# - draws that complete segment RED
# - marks its visually left endpoint/corner RED
#
# No facade matching is performed yet.
# ============================================================


def _plan3d_clear_facade_bottom_left_preview_v1(viewport):
    items = list(
        getattr(
            viewport,
            "_plan3d_facade_bottom_left_items_v1",
            (),
        )
        or ()
    )

    for item in items:
        try:
            scene = item.scene()
            if scene is not None:
                scene.removeItem(item)
        except Exception:
            pass

    viewport._plan3d_facade_bottom_left_items_v1 = []

    try:
        viewport.viewport().update()
    except Exception:
        try:
            viewport.update()
        except Exception:
            pass


def _plan3d_export_wall_segments_v1(paths):
    segments = []

    for path_index, path in enumerate(
        list(paths or [])
    ):
        if not isinstance(
            path,
            (list, tuple),
        ):
            continue

        points = []

        for point in path:
            try:
                points.append(
                    (
                        float(point[0]),
                        float(point[1]),
                    )
                )
            except Exception:
                continue

        if len(points) < 2:
            continue

        for segment_index in range(
            len(points) - 1
        ):
            a = points[
                segment_index
            ]
            b = points[
                segment_index + 1
            ]

            dx = b[0] - a[0]
            dy = b[1] - a[1]

            if (
                dx * dx
                + dy * dy
            ) <= 1.0e-12:
                continue

            segments.append(
                {
                    "path_index":
                        int(path_index),
                    "segment_index":
                        int(segment_index),
                    "a":
                        a,
                    "b":
                        b,
                }
            )

    return segments




def _plan3d_find_bottom_left_export_segment_v1(
    viewport,
    wall_paths,
):
    segments = (
        _plan3d_export_wall_segments_v1(
            wall_paths
        )
    )

    if not segments:
        return None

    horizontal = []

    all_view_y = []

    for row in segments:
        ax, ay = row[
            "a"
        ]

        bx, by = row[
            "b"
        ]

        avx, avy = (
            _plan3d_scene_to_view_xy_v1(
                viewport,
                ax,
                ay,
            )
        )

        bvx, bvy = (
            _plan3d_scene_to_view_xy_v1(
                viewport,
                bx,
                by,
            )
        )

        view_dx = (
            bvx
            - avx
        )

        view_dy = (
            bvy
            - avy
        )

        mid_y = (
            avy
            + bvy
        ) * 0.5

        all_view_y.extend(
            [
                avy,
                bvy,
            ]
        )

        # Keep only clearly horizontal lines in the visible viewport.
        if abs(
            view_dx
        ) <= 1.0e-9:
            continue

        if abs(
            view_dy
        ) > max(
            2.0,
            abs(
                view_dx
            )
            * 0.04,
        ):
            continue

        horizontal.append(
            {
                **row,
                "view_a":
                    (
                        avx,
                        avy,
                    ),
                "view_b":
                    (
                        bvx,
                        bvy,
                    ),
                "view_mid_y":
                    float(
                        mid_y
                    ),
                "view_left_x":
                    float(
                        min(
                            avx,
                            bvx,
                        )
                    ),
                "view_length":
                    float(
                        abs(
                            view_dx
                        )
                    ),
            }
        )

    if not horizontal:
        return None

    min_view_y = min(
        all_view_y
    )

    max_view_y = max(
        all_view_y
    )

    visual_height = max(
        max_view_y
        - min_view_y,
        1.0,
    )

    # Visually lowest horizontal band. This is deliberately based on
    # viewport coordinates, not CAD Y sign, so zoom/Y-axis orientation
    # cannot invert the meaning of "bottom".
    bottom_y = max(
        row[
            "view_mid_y"
        ]
        for row in horizontal
    )

    band_tol = max(
        8.0,
        visual_height
        * 0.025,
    )

    bottom_candidates = [
        row
        for row in horizontal
        if (
            bottom_y
            - row[
                "view_mid_y"
            ]
        )
        <= band_tol
    ]

    if not bottom_candidates:
        return None

    # User rule:
    # among lines at the bottom, select the left-most line.
    selected = min(
        bottom_candidates,
        key=lambda row: (
            row[
                "view_left_x"
            ],
            -row[
                "view_length"
            ],
            row[
                "path_index"
            ],
            row[
                "segment_index"
            ],
        ),
    )

    avx, _avy = selected[
        "view_a"
    ]

    bvx, _bvy = selected[
        "view_b"
    ]

    if avx <= bvx:
        selected[
            "left_corner"
        ] = selected[
            "a"
        ]
    else:
        selected[
            "left_corner"
        ] = selected[
            "b"
        ]

    selected[
        "bottom_candidate_count"
    ] = len(
        bottom_candidates
    )

    selected[
        "bottom_band_tolerance_px"
    ] = float(
        band_tol
    )

    return selected


def _plan3d_draw_bottom_left_export_segment_v1(
    viewport,
    floor_name,
    selected,
):
    from PySide6.QtCore import Qt, QRectF
    from PySide6.QtGui import QColor, QPainterPath, QPen, QBrush
    from PySide6.QtWidgets import (
        QGraphicsEllipseItem,
        QGraphicsPathItem,
        QGraphicsTextItem,
    )

    scene_method = getattr(
        viewport,
        "scene",
        None,
    )

    if not callable(
        scene_method
    ):
        raise RuntimeError(
            "Facade Analysis: viewport scene unavailable."
        )

    scene = scene_method()

    if scene is None:
        raise RuntimeError(
            "Facade Analysis: viewport scene unavailable."
        )

    items = list(
        getattr(
            viewport,
            "_plan3d_facade_bottom_left_items_v1",
            (),
        )
        or ()
    )

    a = selected[
        "a"
    ]

    b = selected[
        "b"
    ]

    corner = selected[
        "left_corner"
    ]

    path = QPainterPath()

    path.moveTo(
        float(
            a[0]
        ),
        float(
            a[1]
        ),
    )

    path.lineTo(
        float(
            b[0]
        ),
        float(
            b[1]
        ),
    )

    line_item = QGraphicsPathItem(
        path
    )

    pen = QPen(
        QColor(
            "#FF0000"
        )
    )

    pen.setCosmetic(
        True
    )

    pen.setWidthF(
        5.0
    )

    line_item.setPen(
        pen
    )

    line_item.setZValue(
        4000000.0
    )

    scene.addItem(
        line_item
    )

    items.append(
        line_item
    )

    # Constant-screen-size corner marker.
    marker_radius_scene = 6.0

    try:
        p0 = viewport.mapToScene(
            0,
            0,
        )

        p1 = viewport.mapToScene(
            12,
            0,
        )

        marker_radius_scene = max(
            abs(
                float(
                    p1.x()
                )
                - float(
                    p0.x()
                )
            )
            * 0.5,
            1.0e-6,
        )

    except Exception:
        pass

    ellipse = QGraphicsEllipseItem(
        QRectF(
            float(
                corner[0]
            )
            - marker_radius_scene,
            float(
                corner[1]
            )
            - marker_radius_scene,
            marker_radius_scene
            * 2.0,
            marker_radius_scene
            * 2.0,
        )
    )

    ellipse_pen = QPen(
        QColor(
            "#FF0000"
        )
    )

    ellipse_pen.setCosmetic(
        True
    )

    ellipse_pen.setWidthF(
        2.0
    )

    ellipse.setPen(
        ellipse_pen
    )

    ellipse.setBrush(
        QBrush(
            QColor(
                "#FF0000"
            )
        )
    )

    ellipse.setZValue(
        4000001.0
    )

    scene.addItem(
        ellipse
    )

    items.append(
        ellipse
    )

    label = QGraphicsTextItem(
        str(
            floor_name
        )
        + " | BOTTOM-LEFT EXPORT WALL"
    )

    label.setDefaultTextColor(
        QColor(
            "#FF0000"
        )
    )

    label.setFlag(
        label.GraphicsItemFlag.ItemIgnoresTransformations,
        True,
    )

    label.setPos(
        float(
            corner[0]
        ),
        float(
            corner[1]
        ),
    )

    label.setZValue(
        4000002.0
    )

    scene.addItem(
        label
    )

    items.append(
        label
    )

    viewport._plan3d_facade_bottom_left_items_v1 = (
        items
    )

    try:
        scene.update()
    except Exception:
        pass

    try:
        viewport.viewport().update()
    except Exception:
        pass


def _plan3d_run_facade_bottom_left_export_line_v1(self):
    from floor_area_runtime import (
        _export_prepared_wall_paths,
    )

    from plan3d_canonical_export import (
        _cad_unit_info,
    )

    page = self.parentWidget()

    viewport = (
        getattr(
            page,
            "viewport",
            None,
        )
        if page is not None
        else None
    )

    if viewport is None:
        raise RuntimeError(
            "Facade Analysis: viewport unavailable."
        )

    _plan3d_clear_facade_bottom_left_preview_v1(
        viewport
    )

    values = self.values()

    assignments = dict(
        (
            values.get(
                "assignments",
                {},
            )
            or {}
        ).get(
            "floor_plans",
            {},
        )
        or {}
    )

    floor_settings = dict(
        values.get(
            "floor_settings",
            {},
        )
        or {}
    )

    pivot_map = dict(
        getattr(
            self,
            "_floor_pivots",
            {},
        )
        or {}
    )

    if not assignments:
        raise RuntimeError(
            "Facade Analysis: no Floor Plan assignments."
        )

    units_info = _cad_unit_info(
        viewport
    )

    results = {}

    for floor_name, rect_values in assignments.items():
        floor_name = str(
            floor_name
        )

        settings = dict(
            floor_settings.get(
                floor_name,
                {},
            )
            or {}
        )

        pivot = dict(
            pivot_map.get(
                floor_name,
                {},
            )
            or {}
        )

        (
            wall_paths,
            _wall_topology,
            _export_floor,
        ) = _export_prepared_wall_paths(
            viewport,
            floor_name,
            rect_values,
            pivot,
            settings,
            units_info,
        )

        selected = (
            _plan3d_find_bottom_left_export_segment_v1(
                viewport,
                wall_paths,
            )
        )

        if selected is None:
            print(
                "PLAN3D FACADE BOTTOM LEFT V1 |",
                floor_name,
                "| result=NO_HORIZONTAL_EXPORT_SEGMENT",
                flush=True,
            )
            continue

        _plan3d_draw_bottom_left_export_segment_v1(
            viewport,
            floor_name,
            selected,
        )

        results[
            floor_name
        ] = {
            "line_a":
                list(
                    selected[
                        "a"
                    ]
                ),
            "line_b":
                list(
                    selected[
                        "b"
                    ]
                ),
            "left_corner":
                list(
                    selected[
                        "left_corner"
                    ]
                ),
            "path_index":
                int(
                    selected[
                        "path_index"
                    ]
                ),
            "segment_index":
                int(
                    selected[
                        "segment_index"
                    ]
                ),
            "bottom_candidate_count":
                int(
                    selected[
                        "bottom_candidate_count"
                    ]
                ),
        }

        print(
            "PLAN3D FACADE BOTTOM LEFT V1 |",
            floor_name,
            "| line=",
            (
                selected[
                    "a"
                ],
                selected[
                    "b"
                ],
            ),
            "| left_corner=",
            selected[
                "left_corner"
            ],
            "| bottom_candidates=",
            selected[
                "bottom_candidate_count"
            ],
            flush=True,
        )

    self._facade_analysis_bottom_left_v1 = (
        results
    )

    self.selection_status.setText(
        "Facade Analysis: bottom-left export Wall line highlighted in red."
    )

    print(
        "PLAN3D FACADE BOTTOM LEFT V1 COMPLETE | floors=",
        len(
            results
        ),
        flush=True,
    )

    return results



# ============================================================
# PLAN3D_FACADE_DISCONNECTED_NO_OPENING_FILTER_V2
#
# Facade Analysis rule:
# - source remains Create3D export-prepared Wall paths
# - disconnected Wall components are evaluated separately
# - a disconnected component with NO Door / Window contact is excluded
# - excluded components cannot become the bottom-left facade start
# - this affects Facade Analysis selection only; Create3D Wall export is untouched
# ============================================================


def _plan3d_facade_v2_dist_point_segment(px, py, ax, ay, bx, by):
    dx = bx - ax
    dy = by - ay

    length2 = dx * dx + dy * dy

    if length2 <= 1.0e-12:
        return (
            (
                px - ax
            )
            ** 2
            + (
                py - ay
            )
            ** 2
        ) ** 0.5

    t = (
        (
            px - ax
        )
        * dx
        + (
            py - ay
        )
        * dy
    ) / length2

    t = max(
        0.0,
        min(
            1.0,
            t,
        ),
    )

    qx = ax + t * dx
    qy = ay + t * dy

    return (
        (
            px - qx
        )
        ** 2
        + (
            py - qy
        )
        ** 2
    ) ** 0.5


def _plan3d_facade_v2_dist_segment_segment(a1, a2, b1, b2):
    # CAD walls/openings here are 2D line paths. Endpoint-to-segment
    # distance is sufficient for the opening-contact gate because door/window
    # paths terminate on or very near the Wall system.
    values = [
        _plan3d_facade_v2_dist_point_segment(
            a1[0],
            a1[1],
            b1[0],
            b1[1],
            b2[0],
            b2[1],
        ),
        _plan3d_facade_v2_dist_point_segment(
            a2[0],
            a2[1],
            b1[0],
            b1[1],
            b2[0],
            b2[1],
        ),
        _plan3d_facade_v2_dist_point_segment(
            b1[0],
            b1[1],
            a1[0],
            a1[1],
            a2[0],
            a2[1],
        ),
        _plan3d_facade_v2_dist_point_segment(
            b2[0],
            b2[1],
            a1[0],
            a1[1],
            a2[0],
            a2[1],
        ),
    ]

    return min(
        values
    )


def _plan3d_facade_v2_paths_to_segments(paths):
    rows = []

    for path_index, path in enumerate(
        list(
            paths
            or []
        )
    ):
        if not isinstance(
            path,
            (list, tuple),
        ):
            continue

        points = []

        for point in path:
            try:
                points.append(
                    (
                        float(
                            point[0]
                        ),
                        float(
                            point[1]
                        ),
                    )
                )
            except Exception:
                continue

        if len(
            points
        ) < 2:
            continue

        for segment_index in range(
            len(
                points
            )
            - 1
        ):
            a = points[
                segment_index
            ]
            b = points[
                segment_index
                + 1
            ]

            if (
                (
                    b[0]
                    - a[0]
                )
                ** 2
                + (
                    b[1]
                    - a[1]
                )
                ** 2
            ) <= 1.0e-12:
                continue

            rows.append(
                {
                    "path_index":
                        int(
                            path_index
                        ),
                    "segment_index":
                        int(
                            segment_index
                        ),
                    "a":
                        a,
                    "b":
                        b,
                }
            )

    return rows


def _plan3d_facade_v2_segment_components(
    wall_segments,
    join_tolerance,
):
    count = len(
        wall_segments
    )

    adjacency = [
        set()
        for _ in range(
            count
        )
    ]

    tolerance = max(
        float(
            join_tolerance
        ),
        1.0e-9,
    )

    for i in range(
        count
    ):
        row_i = wall_segments[
            i
        ]

        for j in range(
            i + 1,
            count
        ):
            row_j = wall_segments[
                j
            ]

            distance = (
                _plan3d_facade_v2_dist_segment_segment(
                    row_i[
                        "a"
                    ],
                    row_i[
                        "b"
                    ],
                    row_j[
                        "a"
                    ],
                    row_j[
                        "b"
                    ],
                )
            )

            if distance <= tolerance:
                adjacency[
                    i
                ].add(
                    j
                )

                adjacency[
                    j
                ].add(
                    i
                )

    components = []
    seen = set()

    for start in range(
        count
    ):
        if start in seen:
            continue

        stack = [
            start
        ]

        seen.add(
            start
        )

        indices = []

        while stack:
            index = stack.pop()

            indices.append(
                index
            )

            for nxt in adjacency[
                index
            ]:
                if nxt in seen:
                    continue

                seen.add(
                    nxt
                )

                stack.append(
                    nxt
                )

        components.append(
            indices
        )

    return components


def _plan3d_facade_v2_opening_segments(
    viewport,
    rect_values,
    wall_paths,
    source_to_mm,
):
    from floor_area_runtime import (
        _window_paths_in_floor,
        _resolve_windows_v33,
        _symbol_opening_bridge_paths,
        _require_shapely,
    )

    opening_segments = []

    # WINDOW source: same physical window resolver used by the floor/window system.
    window_paths = _window_paths_in_floor(
        viewport,
        rect_values,
    )

    try:
        api = _require_shapely()

        (
            window_bridge_paths,
            _footprint,
            _window_meta,
            _window_stats,
        ) = _resolve_windows_v33(
            window_paths,
            wall_paths,
            source_to_mm,
            api,
        )

        opening_segments.extend(
            _plan3d_facade_v2_paths_to_segments(
                window_bridge_paths
            )
        )

    except Exception as exc:
        print(
            "PLAN3D FACADE FILTER V2 | window resolver warning:",
            exc,
            flush=True,
        )

    # DOOR / SLIDING DOOR source: same opening bridge system used by Floor Areas.
    try:
        (
            symbol_paths,
            symbol_meta,
            _symbol_stats,
        ) = _symbol_opening_bridge_paths(
            viewport,
            rect_values,
            wall_paths,
            source_to_mm,
        )

        for path, meta in zip(
            symbol_paths,
            symbol_meta,
        ):
            semantic = str(
                (
                    meta
                    or {}
                ).get(
                    "semantic_type",
                    "",
                )
                or ""
            )

            if semantic not in (
                "Door",
                "Sliding Door",
                "Window",
            ):
                continue

            opening_segments.extend(
                _plan3d_facade_v2_paths_to_segments(
                    [
                        path
                    ]
                )
            )

    except Exception as exc:
        print(
            "PLAN3D FACADE FILTER V2 | symbol resolver warning:",
            exc,
            flush=True,
        )

    return opening_segments


def _plan3d_facade_v2_filter_wall_components(
    wall_paths,
    opening_segments,
    source_to_mm,
):
    wall_segments = (
        _plan3d_facade_v2_paths_to_segments(
            wall_paths
        )
    )

    if not wall_segments:
        return (
            [],
            {
                "component_count":
                    0,
                "accepted_component_count":
                    0,
                "rejected_component_count":
                    0,
            },
        )

    # CAD-source tolerance derived only from unit scale.
    # 2 cm is enough to treat normal opening-wall contact as contact without
    # joining visibly separate disconnected geometry.
    cad_to_cm = max(
        float(
            source_to_mm
        )
        / 10.0,
        1.0e-12,
    )

    join_tolerance = (
        2.0
        / cad_to_cm
    )

    opening_contact_tolerance = (
        5.0
        / cad_to_cm
    )

    components = (
        _plan3d_facade_v2_segment_components(
            wall_segments,
            join_tolerance,
        )
    )

    accepted_indices = set()
    rejected = []

    for component_index, indices in enumerate(
        components
    ):
        has_opening_contact = False

        for wall_index in indices:
            wall = wall_segments[
                wall_index
            ]

            for opening in opening_segments:
                distance = (
                    _plan3d_facade_v2_dist_segment_segment(
                        wall[
                            "a"
                        ],
                        wall[
                            "b"
                        ],
                        opening[
                            "a"
                        ],
                        opening[
                            "b"
                        ],
                    )
                )

                if distance <= opening_contact_tolerance:
                    has_opening_contact = True
                    break

            if has_opening_contact:
                break

        if has_opening_contact:
            accepted_indices.update(
                indices
            )

        else:
            rejected.append(
                {
                    "component_index":
                        int(
                            component_index
                        ),
                    "segment_count":
                        int(
                            len(
                                indices
                            )
                        ),
                }
            )

    accepted_segments = [
        wall_segments[
            index
        ]
        for index in sorted(
            accepted_indices
        )
    ]

    # Return as simple 2-point paths so the existing V1 bottom-left selector
    # can consume exactly the filtered wall geometry.
    accepted_paths = [
        [
            row[
                "a"
            ],
            row[
                "b"
            ],
        ]
        for row in accepted_segments
    ]

    stats = {
        "component_count":
            int(
                len(
                    components
                )
            ),
        "accepted_component_count":
            int(
                len(
                    components
                )
                - len(
                    rejected
                )
            ),
        "rejected_component_count":
            int(
                len(
                    rejected
                )
            ),
        "accepted_segment_count":
            int(
                len(
                    accepted_segments
                )
            ),
        "rejected_components":
            rejected,
    }

    return (
        accepted_paths,
        stats,
    )


def _plan3d_run_facade_disconnected_no_opening_filter_v2(self):
    from floor_area_runtime import (
        _export_prepared_wall_paths,
    )

    from plan3d_canonical_export import (
        _cad_unit_info,
    )

    page = self.parentWidget()

    viewport = (
        getattr(
            page,
            "viewport",
            None,
        )
        if page is not None
        else None
    )

    if viewport is None:
        raise RuntimeError(
            "Facade Analysis: viewport unavailable."
        )

    _plan3d_clear_facade_bottom_left_preview_v1(
        viewport
    )

    values = self.values()

    assignments = dict(
        (
            values.get(
                "assignments",
                {},
            )
            or {}
        ).get(
            "floor_plans",
            {},
        )
        or {}
    )

    floor_settings = dict(
        values.get(
            "floor_settings",
            {},
        )
        or {}
    )

    pivot_map = dict(
        getattr(
            self,
            "_floor_pivots",
            {},
        )
        or {}
    )

    if not assignments:
        raise RuntimeError(
            "Facade Analysis: no Floor Plan assignments."
        )

    units_info = _cad_unit_info(
        viewport
    )

    source_to_mm = (
        float(
            units_info.get(
                "to_cm",
                1.0,
            )
            or 1.0
        )
        * 10.0
    )

    results = {}

    for floor_name, rect_values in assignments.items():
        floor_name = str(
            floor_name
        )

        settings = dict(
            floor_settings.get(
                floor_name,
                {},
            )
            or {}
        )

        pivot = dict(
            pivot_map.get(
                floor_name,
                {},
            )
            or {}
        )

        (
            wall_paths,
            _wall_topology,
            _export_floor,
        ) = _export_prepared_wall_paths(
            viewport,
            floor_name,
            rect_values,
            pivot,
            settings,
            units_info,
        )

        opening_segments = (
            _plan3d_facade_v2_opening_segments(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )

        (
            filtered_wall_paths,
            filter_stats,
        ) = _plan3d_facade_v2_filter_wall_components(
            wall_paths,
            opening_segments,
            source_to_mm,
        )

        selected = (
            _plan3d_find_bottom_left_export_segment_v1(
                viewport,
                filtered_wall_paths,
            )
        )

        print(
            "PLAN3D FACADE FILTER V2 |",
            floor_name,
            "| components=",
            filter_stats[
                "component_count"
            ],
            "| accepted=",
            filter_stats[
                "accepted_component_count"
            ],
            "| rejected_no_opening=",
            filter_stats[
                "rejected_component_count"
            ],
            "| opening_segments=",
            len(
                opening_segments
            ),
            flush=True,
        )

        if selected is None:
            print(
                "PLAN3D FACADE BOTTOM LEFT V2 |",
                floor_name,
                "| result=NO_ELIGIBLE_EXPORT_SEGMENT",
                flush=True,
            )
            continue

        _plan3d_draw_bottom_left_export_segment_v1(
            viewport,
            floor_name,
            selected,
        )

        results[
            floor_name
        ] = {
            "line_a":
                list(
                    selected[
                        "a"
                    ]
                ),
            "line_b":
                list(
                    selected[
                        "b"
                    ]
                ),
            "left_corner":
                list(
                    selected[
                        "left_corner"
                    ]
                ),
            "filter_stats":
                filter_stats,
        }

        print(
            "PLAN3D FACADE BOTTOM LEFT V2 |",
            floor_name,
            "| left_corner=",
            selected[
                "left_corner"
            ],
            flush=True,
        )

    self._facade_analysis_bottom_left_v2 = (
        results
    )

    self.selection_status.setText(
        "Facade Analysis: disconnected Wall components without Door/Window contact excluded."
    )

    print(
        "PLAN3D FACADE FILTER V2 COMPLETE | floors=",
        len(
            results
        ),
        flush=True,
    )

    return results



# ============================================================
# PLAN3D_FACADE_FRONT_RUN_TO_UPTURN_V3
#
# Rule:
# - start from V2 selected bottom-left eligible export Wall line
# - continue on the SAME visually-horizontal connected run
# - continue toward the right
# - stop at the first endpoint where the wall turns visually UP
# - the whole run is FRONT FACADE
# - draw the complete run RED as one facade
# ============================================================


def _plan3d_facade_v3_endpoint_key(point, tolerance):
    tol = max(
        float(tolerance),
        1.0e-9,
    )

    return (
        int(
            round(
                float(point[0])
                / tol
            )
        ),
        int(
            round(
                float(point[1])
                / tol
            )
        ),
    )


def _plan3d_facade_v3_other_endpoint(segment, point, tolerance):
    a = segment["a"]
    b = segment["b"]

    ka = _plan3d_facade_v3_endpoint_key(
        a,
        tolerance,
    )
    kb = _plan3d_facade_v3_endpoint_key(
        b,
        tolerance,
    )
    kp = _plan3d_facade_v3_endpoint_key(
        point,
        tolerance,
    )

    if ka == kp:
        return b

    if kb == kp:
        return a

    return None


def _plan3d_facade_v3_trace_front_run(
    viewport,
    filtered_wall_paths,
    selected,
    source_to_mm,
):
    segments = _plan3d_facade_v2_paths_to_segments(
        filtered_wall_paths
    )

    if not segments:
        return {
            "segments": [],
            "start_corner": None,
            "end_corner": None,
            "upturn_found": False,
        }

    cad_to_cm = max(
        float(source_to_mm)
        / 10.0,
        1.0e-12,
    )

    join_tolerance = (
        2.0
        / cad_to_cm
    )

    start_corner = tuple(
        selected[
            "left_corner"
        ]
    )

    selected_a = tuple(
        selected[
            "a"
        ]
    )

    selected_b = tuple(
        selected[
            "b"
        ]
    )

    # Identify the selected segment inside the filtered set.
    selected_index = None

    def same_point(p, q):
        return (
            (
                float(p[0])
                - float(q[0])
            )
            ** 2
            + (
                float(p[1])
                - float(q[1])
            )
            ** 2
        ) ** 0.5 <= join_tolerance

    for index, row in enumerate(
        segments
    ):
        if (
            (
                same_point(
                    row["a"],
                    selected_a,
                )
                and same_point(
                    row["b"],
                    selected_b,
                )
            )
            or (
                same_point(
                    row["a"],
                    selected_b,
                )
                and same_point(
                    row["b"],
                    selected_a,
                )
            )
        ):
            selected_index = index
            break

    if selected_index is None:
        return {
            "segments": [
                {
                    "a":
                        selected_a,
                    "b":
                        selected_b,
                }
            ],
            "start_corner":
                start_corner,
            "end_corner":
                selected_b,
            "upturn_found":
                False,
        }

    # Build endpoint -> segment adjacency.
    adjacency = {}

    for index, row in enumerate(
        segments
    ):
        for point in (
            row["a"],
            row["b"],
        ):
            key = (
                _plan3d_facade_v3_endpoint_key(
                    point,
                    join_tolerance,
                )
            )

            adjacency.setdefault(
                key,
                [],
            ).append(
                index
            )

    # Start at the selected segment's visually-left endpoint and travel
    # visually to the right.
    avx, avy = _plan3d_scene_to_view_xy_v1(
        viewport,
        selected_a[0],
        selected_a[1],
    )

    bvx, bvy = _plan3d_scene_to_view_xy_v1(
        viewport,
        selected_b[0],
        selected_b[1],
    )

    if avx <= bvx:
        current_point = selected_b
        start_corner = selected_a
    else:
        current_point = selected_a
        start_corner = selected_b

    used = {
        selected_index
    }

    run = [
        {
            "a":
                selected_a,
            "b":
                selected_b,
            "segment_index":
                selected_index,
        }
    ]

    upturn_found = False
    guard = 0

    while guard < max(
        len(segments) * 2,
        16,
    ):
        guard += 1

        current_key = (
            _plan3d_facade_v3_endpoint_key(
                current_point,
                join_tolerance,
            )
        )

        candidates = [
            index
            for index in adjacency.get(
                current_key,
                [],
            )
            if index not in used
        ]

        if not candidates:
            break

        current_vx, current_vy = (
            _plan3d_scene_to_view_xy_v1(
                viewport,
                current_point[0],
                current_point[1],
            )
        )

        horizontal_forward = []
        upward_turn = []

        for index in candidates:
            row = segments[
                index
            ]

            other = (
                _plan3d_facade_v3_other_endpoint(
                    row,
                    current_point,
                    join_tolerance,
                )
            )

            if other is None:
                continue

            ovx, ovy = (
                _plan3d_scene_to_view_xy_v1(
                    viewport,
                    other[0],
                    other[1],
                )
            )

            dx = (
                ovx
                - current_vx
            )

            dy = (
                ovy
                - current_vy
            )

            # Same facade run: visually horizontal and continuing right.
            if (
                dx > 0.0
                and abs(
                    dy
                )
                <= max(
                    2.0,
                    abs(
                        dx
                    )
                    * 0.04,
                )
            ):
                horizontal_forward.append(
                    (
                        -abs(
                            dx
                        ),
                        index,
                        other,
                    )
                )
                continue

            # Stop condition requested by user:
            # first connected segment that turns visually upward.
            if (
                dy < 0.0
                and abs(
                    dx
                )
                <= max(
                    2.0,
                    abs(
                        dy
                    )
                    * 0.04,
                )
            ):
                upward_turn.append(
                    (
                        abs(
                            dy
                        ),
                        index,
                        other,
                    )
                )

        if horizontal_forward:
            horizontal_forward.sort(
                key=lambda row:
                    row[0]
            )

            _rank, next_index, next_point = (
                horizontal_forward[
                    0
                ]
            )

            next_segment = segments[
                next_index
            ]

            run.append(
                {
                    "a":
                        tuple(
                            next_segment[
                                "a"
                            ]
                        ),
                    "b":
                        tuple(
                            next_segment[
                                "b"
                            ]
                        ),
                    "segment_index":
                        next_index,
                }
            )

            used.add(
                next_index
            )

            current_point = tuple(
                next_point
            )

            continue

        if upward_turn:
            upturn_found = True
            break

        break

    return {
        "segments":
            run,
        "start_corner":
            tuple(
                start_corner
            ),
        "end_corner":
            tuple(
                current_point
            ),
        "upturn_found":
            bool(
                upturn_found
            ),
    }


def _plan3d_draw_front_facade_run_v3(
    viewport,
    floor_name,
    trace,
):
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QPainterPath, QPen, QBrush
    from PySide6.QtWidgets import (
        QGraphicsEllipseItem,
        QGraphicsPathItem,
        QGraphicsTextItem,
    )

    scene_method = getattr(
        viewport,
        "scene",
        None,
    )

    if not callable(
        scene_method
    ):
        raise RuntimeError(
            "Facade Analysis: viewport scene unavailable."
        )

    scene = scene_method()

    if scene is None:
        raise RuntimeError(
            "Facade Analysis: viewport scene unavailable."
        )

    items = list(
        getattr(
            viewport,
            "_plan3d_facade_bottom_left_items_v1",
            (),
        )
        or ()
    )

    red = QColor(
        "#FF0000"
    )

    for row in trace.get(
        "segments",
        [],
    ):
        a = row[
            "a"
        ]
        b = row[
            "b"
        ]

        path = QPainterPath()

        path.moveTo(
            float(
                a[0]
            ),
            float(
                a[1]
            ),
        )

        path.lineTo(
            float(
                b[0]
            ),
            float(
                b[1]
            ),
        )

        item = QGraphicsPathItem(
            path
        )

        pen = QPen(
            red
        )

        pen.setCosmetic(
            True
        )

        pen.setWidthF(
            5.0
        )

        item.setPen(
            pen
        )

        item.setZValue(
            4000000.0
        )

        scene.addItem(
            item
        )

        items.append(
            item
        )

    # Mark start and end corner.
    radius = 6.0

    try:
        p0 = viewport.mapToScene(
            0,
            0,
        )

        p1 = viewport.mapToScene(
            12,
            0,
        )

        radius = max(
            abs(
                float(
                    p1.x()
                )
                - float(
                    p0.x()
                )
            )
            * 0.5,
            1.0e-6,
        )

    except Exception:
        pass

    for corner in (
        trace.get(
            "start_corner"
        ),
        trace.get(
            "end_corner"
        ),
    ):
        if corner is None:
            continue

        ellipse = (
            QGraphicsEllipseItem(
                QRectF(
                    float(
                        corner[0]
                    )
                    - radius,
                    float(
                        corner[1]
                    )
                    - radius,
                    radius
                    * 2.0,
                    radius
                    * 2.0,
                )
            )
        )

        pen = QPen(
            red
        )

        pen.setCosmetic(
            True
        )

        pen.setWidthF(
            2.0
        )

        ellipse.setPen(
            pen
        )

        ellipse.setBrush(
            QBrush(
                red
            )
        )

        ellipse.setZValue(
            4000001.0
        )

        scene.addItem(
            ellipse
        )

        items.append(
            ellipse
        )

    start = trace.get(
        "start_corner"
    )

    if start is not None:
        label = (
            QGraphicsTextItem(
                str(
                    floor_name
                )
                + " | FRONT FACADE"
            )
        )

        label.setDefaultTextColor(
            red
        )

        label.setFlag(
            label.GraphicsItemFlag.ItemIgnoresTransformations,
            True,
        )

        label.setPos(
            float(
                start[0]
            ),
            float(
                start[1]
            ),
        )

        label.setZValue(
            4000002.0
        )

        scene.addItem(
            label
        )

        items.append(
            label
        )

    viewport._plan3d_facade_bottom_left_items_v1 = (
        items
    )

    try:
        scene.update()
    except Exception:
        pass

    try:
        viewport.viewport().update()
    except Exception:
        pass


def _plan3d_run_facade_front_run_to_upturn_v3(self):
    from floor_area_runtime import (
        _export_prepared_wall_paths,
    )

    from plan3d_canonical_export import (
        _cad_unit_info,
    )

    page = self.parentWidget()

    viewport = (
        getattr(
            page,
            "viewport",
            None,
        )
        if page is not None
        else None
    )

    if viewport is None:
        raise RuntimeError(
            "Facade Analysis: viewport unavailable."
        )

    _plan3d_clear_facade_bottom_left_preview_v1(
        viewport
    )

    values = self.values()

    assignments = dict(
        (
            values.get(
                "assignments",
                {},
            )
            or {}
        ).get(
            "floor_plans",
            {},
        )
        or {}
    )

    floor_settings = dict(
        values.get(
            "floor_settings",
            {},
        )
        or {}
    )

    pivot_map = dict(
        getattr(
            self,
            "_floor_pivots",
            {},
        )
        or {}
    )

    if not assignments:
        raise RuntimeError(
            "Facade Analysis: no Floor Plan assignments."
        )

    units_info = _cad_unit_info(
        viewport
    )

    source_to_mm = (
        float(
            units_info.get(
                "to_cm",
                1.0,
            )
            or 1.0
        )
        * 10.0
    )

    results = {}

    for floor_name, rect_values in assignments.items():
        floor_name = str(
            floor_name
        )

        settings = dict(
            floor_settings.get(
                floor_name,
                {},
            )
            or {}
        )

        pivot = dict(
            pivot_map.get(
                floor_name,
                {},
            )
            or {}
        )

        (
            wall_paths,
            _wall_topology,
            _export_floor,
        ) = _export_prepared_wall_paths(
            viewport,
            floor_name,
            rect_values,
            pivot,
            settings,
            units_info,
        )

        opening_segments = (
            _plan3d_facade_v2_opening_segments(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )

        (
            filtered_wall_paths,
            filter_stats,
        ) = _plan3d_facade_v2_filter_wall_components(
            wall_paths,
            opening_segments,
            source_to_mm,
        )

        selected = (
            _plan3d_find_bottom_left_export_segment_v1(
                viewport,
                filtered_wall_paths,
            )
        )

        if selected is None:
            print(
                "PLAN3D FRONT FACADE V3 |",
                floor_name,
                "| result=NO_START_SEGMENT",
                flush=True,
            )
            continue

        trace = (
            _plan3d_facade_v3_trace_front_run(
                viewport,
                filtered_wall_paths,
                selected,
                source_to_mm,
            )
        )

        _plan3d_draw_front_facade_run_v3(
            viewport,
            floor_name,
            trace,
        )

        results[
            floor_name
        ] = {
            "facade":
                "Front",
            "segments":
                [
                    {
                        "a":
                            list(
                                row[
                                    "a"
                                ]
                            ),
                        "b":
                            list(
                                row[
                                    "b"
                                ]
                            ),
                    }
                    for row in trace.get(
                        "segments",
                        [],
                    )
                ],
            "start_corner":
                list(
                    trace[
                        "start_corner"
                    ]
                )
                if trace.get(
                    "start_corner"
                )
                is not None
                else None,
            "end_corner":
                list(
                    trace[
                        "end_corner"
                    ]
                )
                if trace.get(
                    "end_corner"
                )
                is not None
                else None,
            "upturn_found":
                bool(
                    trace.get(
                        "upturn_found",
                        False,
                    )
                ),
            "filter_stats":
                filter_stats,
        }

        print(
            "PLAN3D FRONT FACADE V3 |",
            floor_name,
            "| segments=",
            len(
                trace.get(
                    "segments",
                    [],
                )
            ),
            "| start=",
            trace.get(
                "start_corner"
            ),
            "| end=",
            trace.get(
                "end_corner"
            ),
            "| upturn_found=",
            trace.get(
                "upturn_found"
            ),
            flush=True,
        )

    self._facade_analysis_front_v3 = (
        results
    )

    self.selection_status.setText(
        "Facade Analysis: Front facade selected in red up to the first upward wall corner."
    )

    print(
        "PLAN3D FRONT FACADE V3 COMPLETE | floors=",
        len(
            results
        ),
        flush=True,
    )

    return results



# ============================================================
# PLAN3D_FACADE_OPENING_PASS_AND_WALL_SIDE_V4
#
# Fixes:
# 1) Window / Sliding Door / Exterior Door contacts are NOT corners.
#    They are stored as facade openings and traversed automatically.
# 2) Front facade outer/inner Wall lines are classified.
#
# FRONT rule:
# - outer line = visually lower wall face of the front wall band
# - inner line = nearest parallel overlapping wall face on the inward side
# - facade tracing follows OUTER wall face
# - openings create virtual continuation links between outer wall pieces
# - tracing stops only at a TRUE upward Wall turn
# ============================================================


def _plan3d_facade_v4_collect_opening_bridges(
    viewport,
    rect_values,
    wall_paths,
    source_to_mm,
):
    from floor_area_runtime import (
        _window_paths_in_floor,
        _resolve_windows_v33,
        _symbol_opening_bridge_paths,
        _require_shapely,
    )

    rows = []

    # Physical windows.
    try:
        window_paths = _window_paths_in_floor(
            viewport,
            rect_values,
        )

        api = _require_shapely()

        (
            window_bridge_paths,
            _footprint,
            window_meta,
            _window_stats,
        ) = _resolve_windows_v33(
            window_paths,
            wall_paths,
            source_to_mm,
            api,
        )

        for index, path in enumerate(
            window_bridge_paths
        ):
            points = list(
                path
                or []
            )

            if len(
                points
            ) < 2:
                continue

            try:
                a = (
                    float(
                        points[0][0]
                    ),
                    float(
                        points[0][1]
                    ),
                )

                b = (
                    float(
                        points[-1][0]
                    ),
                    float(
                        points[-1][1]
                    ),
                )

            except Exception:
                continue

            rows.append(
                {
                    "semantic_type":
                        "Window",
                    "a":
                        a,
                    "b":
                        b,
                    "source_index":
                        int(
                            index
                        ),
                }
            )

    except Exception as exc:
        print(
            "PLAN3D FACADE V4 | window bridge warning:",
            exc,
            flush=True,
        )

    # Door + Sliding Door + Exterior Door bridges.
    try:
        (
            symbol_paths,
            symbol_meta,
            _symbol_stats,
        ) = _symbol_opening_bridge_paths(
            viewport,
            rect_values,
            wall_paths,
            source_to_mm,
        )

        for index, (
            path,
            meta,
        ) in enumerate(
            zip(
                symbol_paths,
                symbol_meta,
            )
        ):
            semantic = str(
                (
                    meta
                    or {}
                ).get(
                    "semantic_type",
                    "",
                )
                or ""
            )

            semantic_cf = semantic.casefold()

            accepted = (
                semantic in (
                    "Sliding Door",
                    "Exterior Door",
                    "Door",
                    "Window",
                )
                or "sliding" in semantic_cf
                or "exterior" in semantic_cf
                or "dış" in semantic_cf
            )

            if not accepted:
                continue

            points = list(
                path
                or []
            )

            if len(
                points
            ) < 2:
                continue

            try:
                a = (
                    float(
                        points[0][0]
                    ),
                    float(
                        points[0][1]
                    ),
                )

                b = (
                    float(
                        points[-1][0]
                    ),
                    float(
                        points[-1][1]
                    ),
                )

            except Exception:
                continue

            rows.append(
                {
                    "semantic_type":
                        semantic
                        or "Door",
                    "a":
                        a,
                    "b":
                        b,
                    "source_index":
                        int(
                            index
                        ),
                }
            )

    except Exception as exc:
        print(
            "PLAN3D FACADE V4 | symbol bridge warning:",
            exc,
            flush=True,
        )

    return rows


def _plan3d_facade_v4_overlap_1d(
    a0,
    a1,
    b0,
    b1,
):
    amin = min(
        float(
            a0
        ),
        float(
            a1
        ),
    )

    amax = max(
        float(
            a0
        ),
        float(
            a1
        ),
    )

    bmin = min(
        float(
            b0
        ),
        float(
            b1
        ),
    )

    bmax = max(
        float(
            b0
        ),
        float(
            b1
        ),
    )

    return max(
        0.0,
        min(
            amax,
            bmax,
        )
        - max(
            amin,
            bmin,
        ),
    )


def _plan3d_facade_v4_front_outer_inner(
    viewport,
    filtered_wall_paths,
    selected,
    source_to_mm,
):
    segments = (
        _plan3d_facade_v2_paths_to_segments(
            filtered_wall_paths
        )
    )

    horizontal = []

    for index, row in enumerate(
        segments
    ):
        a = row[
            "a"
        ]

        b = row[
            "b"
        ]

        avx, avy = (
            _plan3d_scene_to_view_xy_v1(
                viewport,
                a[0],
                a[1],
            )
        )

        bvx, bvy = (
            _plan3d_scene_to_view_xy_v1(
                viewport,
                b[0],
                b[1],
            )
        )

        dx = (
            bvx
            - avx
        )

        dy = (
            bvy
            - avy
        )

        if abs(
            dx
        ) <= 1.0e-9:
            continue

        if abs(
            dy
        ) > max(
            2.0,
            abs(
                dx
            )
            * 0.04,
        ):
            continue

        horizontal.append(
            {
                **row,
                "index":
                    int(
                        index
                    ),
                "view_y":
                    float(
                        (
                            avy
                            + bvy
                        )
                        * 0.5
                    ),
                "view_x0":
                    float(
                        min(
                            avx,
                            bvx,
                        )
                    ),
                "view_x1":
                    float(
                        max(
                            avx,
                            bvx,
                        )
                    ),
                "scene_y":
                    float(
                        (
                            a[1]
                            + b[1]
                        )
                        * 0.5
                    ),
            }
        )

    if not horizontal:
        return {
            "outer_segments":
                [],
            "inner_segments":
                [],
            "wall_band_spacing_scene":
                None,
        }

    selected_y = None

    for row in horizontal:
        if (
            (
                abs(
                    row[
                        "a"
                    ][0]
                    - selected[
                        "a"
                    ][0]
                )
                <= 1.0e-6
                and abs(
                    row[
                        "a"
                    ][1]
                    - selected[
                        "a"
                    ][1]
                )
                <= 1.0e-6
                and abs(
                    row[
                        "b"
                    ][0]
                    - selected[
                        "b"
                    ][0]
                )
                <= 1.0e-6
                and abs(
                    row[
                        "b"
                    ][1]
                    - selected[
                        "b"
                    ][1]
                )
                <= 1.0e-6
            )
            or (
                abs(
                    row[
                        "a"
                    ][0]
                    - selected[
                        "b"
                    ][0]
                )
                <= 1.0e-6
                and abs(
                    row[
                        "a"
                    ][1]
                    - selected[
                        "b"
                    ][1]
                )
                <= 1.0e-6
                and abs(
                    row[
                        "b"
                    ][0]
                    - selected[
                        "a"
                    ][0]
                )
                <= 1.0e-6
                and abs(
                    row[
                        "b"
                    ][1]
                    - selected[
                        "a"
                    ][1]
                )
                <= 1.0e-6
            )
        ):
            selected_y = row[
                "view_y"
            ]
            break

    if selected_y is None:
        selected_y = max(
            row[
                "view_y"
            ]
            for row in horizontal
        )

    # Front exterior is the visually-lowest wall face.
    # Keep the same band as the selected V2 start line.
    cad_to_cm = max(
        float(
            source_to_mm
        )
        / 10.0,
        1.0e-12,
    )

    # Collect all overlapping parallel wall-line separations and use
    # the smallest robust separation as local wall thickness.
    separations = []

    for i, a in enumerate(
        horizontal
    ):
        for b in horizontal[
            i + 1:
        ]:
            overlap = (
                _plan3d_facade_v4_overlap_1d(
                    a[
                        "view_x0"
                    ],
                    a[
                        "view_x1"
                    ],
                    b[
                        "view_x0"
                    ],
                    b[
                        "view_x1"
                    ],
                )
            )

            shorter = min(
                a[
                    "view_x1"
                ]
                - a[
                    "view_x0"
                ],
                b[
                    "view_x1"
                ]
                - b[
                    "view_x0"
                ],
            )

            if shorter <= 1.0e-9:
                continue

            if overlap < shorter * 0.35:
                continue

            scene_sep = abs(
                a[
                    "scene_y"
                ]
                - b[
                    "scene_y"
                ]
            )

            cm_sep = (
                scene_sep
                * cad_to_cm
            )

            if (
                5.0
                <= cm_sep
                <= 80.0
            ):
                separations.append(
                    scene_sep
                )

    spacing = None

    if separations:
        separations.sort()

        # Median of the lower third: avoids choosing room-to-room distances.
        sample_count = max(
            1,
            len(
                separations
            )
            // 3,
        )

        sample = separations[
            :sample_count
        ]

        spacing = sample[
            len(
                sample
            )
            // 2
        ]

    outer = []
    inner = []

    outer_view_tol = 3.0

    for row in horizontal:
        if abs(
            row[
                "view_y"
            ]
            - selected_y
        ) <= outer_view_tol:
            outer.append(
                row
            )

    if spacing is not None:
        for out in outer:
            best = None

            for candidate in horizontal:
                # Inner side for FRONT is visually upward.
                if candidate[
                    "view_y"
                ] >= out[
                    "view_y"
                ]:
                    continue

                overlap = (
                    _plan3d_facade_v4_overlap_1d(
                        out[
                            "view_x0"
                        ],
                        out[
                            "view_x1"
                        ],
                        candidate[
                            "view_x0"
                        ],
                        candidate[
                            "view_x1"
                        ],
                    )
                )

                shorter = min(
                    out[
                        "view_x1"
                    ]
                    - out[
                        "view_x0"
                    ],
                    candidate[
                        "view_x1"
                    ]
                    - candidate[
                        "view_x0"
                    ],
                )

                if shorter <= 1.0e-9:
                    continue

                if overlap < shorter * 0.35:
                    continue

                scene_sep = abs(
                    out[
                        "scene_y"
                    ]
                    - candidate[
                        "scene_y"
                    ]
                )

                error = abs(
                    scene_sep
                    - spacing
                )

                if (
                    best is None
                    or error
                    < best[
                        0
                    ]
                ):
                    best = (
                        error,
                        candidate,
                    )

            if best is not None:
                inner.append(
                    best[
                        1
                    ]
                )

    return {
        "outer_segments":
            outer,
        "inner_segments":
            inner,
        "wall_band_spacing_scene":
            spacing,
    }


def _plan3d_facade_v4_opening_touching_point(
    opening,
    point,
    tolerance,
):
    a = opening[
        "a"
    ]

    b = opening[
        "b"
    ]

    da = (
        (
            a[0]
            - point[0]
        )
        ** 2
        + (
            a[1]
            - point[1]
        )
        ** 2
    ) ** 0.5

    db = (
        (
            b[0]
            - point[0]
        )
        ** 2
        + (
            b[1]
            - point[1]
        )
        ** 2
    ) ** 0.5

    if da <= tolerance:
        return b

    if db <= tolerance:
        return a

    return None


def _plan3d_facade_v4_trace_front(
    viewport,
    filtered_wall_paths,
    selected,
    opening_bridges,
    source_to_mm,
):
    segments = (
        _plan3d_facade_v2_paths_to_segments(
            filtered_wall_paths
        )
    )

    cad_to_cm = max(
        float(
            source_to_mm
        )
        / 10.0,
        1.0e-12,
    )

    join_tolerance = (
        5.0
        / cad_to_cm
    )

    selected_a = tuple(
        selected[
            "a"
        ]
    )

    selected_b = tuple(
        selected[
            "b"
        ]
    )

    def same_point(
        p,
        q,
    ):
        return (
            (
                p[0]
                - q[0]
            )
            ** 2
            + (
                p[1]
                - q[1]
            )
            ** 2
        ) ** 0.5 <= join_tolerance

    selected_index = None

    for index, row in enumerate(
        segments
    ):
        if (
            (
                same_point(
                    row[
                        "a"
                    ],
                    selected_a,
                )
                and same_point(
                    row[
                        "b"
                    ],
                    selected_b,
                )
            )
            or (
                same_point(
                    row[
                        "a"
                    ],
                    selected_b,
                )
                and same_point(
                    row[
                        "b"
                    ],
                    selected_a,
                )
            )
        ):
            selected_index = index
            break

    if selected_index is None:
        return {
            "wall_segments": [],
            "openings": [],
            "start_corner": None,
            "end_corner": None,
            "upturn_found": False,
        }

    adjacency = {}

    for index, row in enumerate(
        segments
    ):
        for point in (
            row[
                "a"
            ],
            row[
                "b"
            ],
        ):
            key = (
                _plan3d_facade_v3_endpoint_key(
                    point,
                    join_tolerance,
                )
            )

            adjacency.setdefault(
                key,
                [],
            ).append(
                index
            )

    avx, _avy = (
        _plan3d_scene_to_view_xy_v1(
            viewport,
            selected_a[0],
            selected_a[1],
        )
    )

    bvx, _bvy = (
        _plan3d_scene_to_view_xy_v1(
            viewport,
            selected_b[0],
            selected_b[1],
        )
    )

    if avx <= bvx:
        start_corner = selected_a
        current_point = selected_b
    else:
        start_corner = selected_b
        current_point = selected_a

    wall_run = [
        {
            "a":
                selected_a,
            "b":
                selected_b,
            "segment_index":
                int(
                    selected_index
                ),
        }
    ]

    openings_used = []
    used_wall = {
        selected_index
    }

    used_openings = set()

    upturn_found = False

    guard = 0

    while guard < max(
        len(
            segments
        )
        * 4
        + len(
            opening_bridges
        )
        * 4,
        32,
    ):
        guard += 1

        current_vx, current_vy = (
            _plan3d_scene_to_view_xy_v1(
                viewport,
                current_point[0],
                current_point[1],
            )
        )

        current_key = (
            _plan3d_facade_v3_endpoint_key(
                current_point,
                join_tolerance,
            )
        )

        connected_wall = [
            index
            for index in adjacency.get(
                current_key,
                [],
            )
            if index not in used_wall
        ]

        horizontal_forward = []
        upward_wall = []

        for index in connected_wall:
            row = segments[
                index
            ]

            other = (
                _plan3d_facade_v3_other_endpoint(
                    row,
                    current_point,
                    join_tolerance,
                )
            )

            if other is None:
                continue

            ovx, ovy = (
                _plan3d_scene_to_view_xy_v1(
                    viewport,
                    other[0],
                    other[1],
                )
            )

            dx = (
                ovx
                - current_vx
            )

            dy = (
                ovy
                - current_vy
            )

            if (
                dx > 0.0
                and abs(
                    dy
                )
                <= max(
                    2.0,
                    abs(
                        dx
                    )
                    * 0.04,
                )
            ):
                horizontal_forward.append(
                    (
                        -abs(
                            dx
                        ),
                        index,
                        other,
                    )
                )

                continue

            if (
                dy < 0.0
                and abs(
                    dx
                )
                <= max(
                    2.0,
                    abs(
                        dy
                    )
                    * 0.04,
                )
            ):
                upward_wall.append(
                    (
                        abs(
                            dy
                        ),
                        index,
                        other,
                    )
                )

        if horizontal_forward:
            horizontal_forward.sort(
                key=lambda row:
                    row[
                        0
                    ]
            )

            _rank, next_index, next_point = (
                horizontal_forward[
                    0
                ]
            )

            row = segments[
                next_index
            ]

            wall_run.append(
                {
                    "a":
                        tuple(
                            row[
                                "a"
                            ]
                        ),
                    "b":
                        tuple(
                            row[
                                "b"
                            ]
                        ),
                    "segment_index":
                        int(
                            next_index
                        ),
                }
            )

            used_wall.add(
                next_index
            )

            current_point = tuple(
                next_point
            )

            continue

        # Before accepting an upward wall as a corner, check whether the
        # current endpoint belongs to a facade opening. If yes, hop across
        # the opening and continue on the opposite wall piece.
        opening_candidates = []

        for opening_index, opening in enumerate(
            opening_bridges
        ):
            if opening_index in used_openings:
                continue

            other = (
                _plan3d_facade_v4_opening_touching_point(
                    opening,
                    current_point,
                    join_tolerance,
                )
            )

            if other is None:
                continue

            ovx, ovy = (
                _plan3d_scene_to_view_xy_v1(
                    viewport,
                    other[0],
                    other[1],
                )
            )

            dx = (
                ovx
                - current_vx
            )

            dy = (
                ovy
                - current_vy
            )

            # Opening continuation must move predominantly right on the
            # current FRONT facade. It may have a small vertical offset.
            if (
                dx > 0.0
                and abs(
                    dy
                )
                <= max(
                    6.0,
                    abs(
                        dx
                    )
                    * 0.35,
                )
            ):
                opening_candidates.append(
                    (
                        -abs(
                            dx
                        ),
                        opening_index,
                        opening,
                        other,
                    )
                )

        if opening_candidates:
            opening_candidates.sort(
                key=lambda row:
                    row[
                        0
                    ]
            )

            (
                _rank,
                opening_index,
                opening,
                other,
            ) = opening_candidates[
                0
            ]

            openings_used.append(
                {
                    "semantic_type":
                        opening[
                            "semantic_type"
                        ],
                    "a":
                        tuple(
                            opening[
                                "a"
                            ]
                        ),
                    "b":
                        tuple(
                            opening[
                                "b"
                            ]
                        ),
                }
            )

            used_openings.add(
                opening_index
            )

            current_point = tuple(
                other
            )

            continue

        # Only now is a connected upward Wall a true facade corner.
        if upward_wall:
            upturn_found = True
            break

        break

    return {
        "wall_segments":
            wall_run,
        "openings":
            openings_used,
        "start_corner":
            tuple(
                start_corner
            ),
        "end_corner":
            tuple(
                current_point
            ),
        "upturn_found":
            bool(
                upturn_found
            ),
    }


def _plan3d_draw_front_facade_v4(
    viewport,
    floor_name,
    trace,
    wall_sides,
):
    from PySide6.QtGui import QColor, QPainterPath, QPen
    from PySide6.QtWidgets import (
        QGraphicsPathItem,
        QGraphicsTextItem,
    )

    scene = viewport.scene()

    if scene is None:
        raise RuntimeError(
            "Facade Analysis: viewport scene unavailable."
        )

    items = list(
        getattr(
            viewport,
            "_plan3d_facade_bottom_left_items_v1",
            (),
        )
        or ()
    )

    red = QColor(
        "#FF0000"
    )

    # Outer wall face: authoritative FRONT facade.
    for row in trace.get(
        "wall_segments",
        [],
    ):
        path = QPainterPath()

        path.moveTo(
            float(
                row[
                    "a"
                ][0]
            ),
            float(
                row[
                    "a"
                ][1]
            ),
        )

        path.lineTo(
            float(
                row[
                    "b"
                ][0]
            ),
            float(
                row[
                    "b"
                ][1]
            ),
        )

        item = QGraphicsPathItem(
            path
        )

        pen = QPen(
            red
        )

        pen.setCosmetic(
            True
        )

        pen.setWidthF(
            5.0
        )

        item.setPen(
            pen
        )

        item.setZValue(
            4100000.0
        )

        scene.addItem(
            item
        )

        items.append(
            item
        )

    # Opening spans: same facade color, dashed only to make the opening
    # readable while preserving one facade color.
    for opening in trace.get(
        "openings",
        [],
    ):
        path = QPainterPath()

        path.moveTo(
            float(
                opening[
                    "a"
                ][0]
            ),
            float(
                opening[
                    "a"
                ][1]
            ),
        )

        path.lineTo(
            float(
                opening[
                    "b"
                ][0]
            ),
            float(
                opening[
                    "b"
                ][1]
            ),
        )

        item = QGraphicsPathItem(
            path
        )

        pen = QPen(
            red
        )

        pen.setCosmetic(
            True
        )

        pen.setWidthF(
            4.0
        )

        from PySide6.QtCore import Qt

        pen.setStyle(
            Qt.PenStyle.DashLine
        )
        # PLAN3D_FACADE_V4_QPEN_DASH_FIX_V1

        item.setPen(
            pen
        )

        item.setZValue(
            4100001.0
        )

        scene.addItem(
            item
        )

        items.append(
            item
        )

    start = trace.get(
        "start_corner"
    )

    if start is not None:
        label = QGraphicsTextItem(
            str(
                floor_name
            )
            + " | FRONT FACADE | OUTER WALL"
        )

        label.setDefaultTextColor(
            red
        )

        label.setFlag(
            label.GraphicsItemFlag.ItemIgnoresTransformations,
            True,
        )

        label.setPos(
            float(
                start[0]
            ),
            float(
                start[1]
            ),
        )

        label.setZValue(
            4100002.0
        )

        scene.addItem(
            label
        )

        items.append(
            label
        )

    viewport._plan3d_facade_bottom_left_items_v1 = (
        items
    )

    try:
        scene.update()
    except Exception:
        pass

    try:
        viewport.viewport().update()
    except Exception:
        pass


def _plan3d_run_facade_opening_pass_wall_side_v4(self):
    from floor_area_runtime import (
        _export_prepared_wall_paths,
    )

    from plan3d_canonical_export import (
        _cad_unit_info,
    )

    page = self.parentWidget()

    viewport = (
        getattr(
            page,
            "viewport",
            None,
        )
        if page is not None
        else None
    )

    if viewport is None:
        raise RuntimeError(
            "Facade Analysis: viewport unavailable."
        )

    _plan3d_clear_facade_bottom_left_preview_v1(
        viewport
    )

    values = self.values()

    assignments = dict(
        (
            values.get(
                "assignments",
                {},
            )
            or {}
        ).get(
            "floor_plans",
            {},
        )
        or {}
    )

    floor_settings = dict(
        values.get(
            "floor_settings",
            {},
        )
        or {}
    )

    pivot_map = dict(
        getattr(
            self,
            "_floor_pivots",
            {},
        )
        or {}
    )

    if not assignments:
        raise RuntimeError(
            "Facade Analysis: no Floor Plan assignments."
        )

    units_info = _cad_unit_info(
        viewport
    )

    source_to_mm = (
        float(
            units_info.get(
                "to_cm",
                1.0,
            )
            or 1.0
        )
        * 10.0
    )

    results = {}

    for floor_name, rect_values in assignments.items():
        floor_name = str(
            floor_name
        )

        settings = dict(
            floor_settings.get(
                floor_name,
                {},
            )
            or {}
        )

        pivot = dict(
            pivot_map.get(
                floor_name,
                {},
            )
            or {}
        )

        (
            wall_paths,
            _wall_topology,
            _export_floor,
        ) = _export_prepared_wall_paths(
            viewport,
            floor_name,
            rect_values,
            pivot,
            settings,
            units_info,
        )

        opening_segments_for_filter = (
            _plan3d_facade_v2_opening_segments(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )

        (
            filtered_wall_paths,
            filter_stats,
        ) = _plan3d_facade_v2_filter_wall_components(
            wall_paths,
            opening_segments_for_filter,
            source_to_mm,
        )

        selected = (
            _plan3d_find_bottom_left_export_segment_v1(
                viewport,
                filtered_wall_paths,
            )
        )

        if selected is None:
            print(
                "PLAN3D FACADE V4 |",
                floor_name,
                "| result=NO_START_SEGMENT",
                flush=True,
            )
            continue

        wall_sides = (
            _plan3d_facade_v4_front_outer_inner(
                viewport,
                filtered_wall_paths,
                selected,
                source_to_mm,
            )
        )

        opening_bridges = (
            _plan3d_facade_v4_collect_opening_bridges(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )

        trace = (
            _plan3d_facade_v4_trace_front(
                viewport,
                filtered_wall_paths,
                selected,
                opening_bridges,
                source_to_mm,
            )
        )

        _plan3d_draw_front_facade_v4(
            viewport,
            floor_name,
            trace,
            wall_sides,
        )

        results[
            floor_name
        ] = {
            "facade":
                "Front",
            "outer_wall_segments":
                [
                    {
                        "a":
                            list(
                                row[
                                    "a"
                                ]
                            ),
                        "b":
                            list(
                                row[
                                    "b"
                                ]
                            ),
                    }
                    for row in trace.get(
                        "wall_segments",
                        [],
                    )
                ],
            "inner_wall_segments":
                [
                    {
                        "a":
                            list(
                                row[
                                    "a"
                                ]
                            ),
                        "b":
                            list(
                                row[
                                    "b"
                                ]
                            ),
                    }
                    for row in wall_sides.get(
                        "inner_segments",
                        [],
                    )
                ],
            "openings":
                [
                    {
                        "semantic_type":
                            row[
                                "semantic_type"
                            ],
                        "a":
                            list(
                                row[
                                    "a"
                                ]
                            ),
                        "b":
                            list(
                                row[
                                    "b"
                                ]
                            ),
                    }
                    for row in trace.get(
                        "openings",
                        [],
                    )
                ],
            "start_corner":
                list(
                    trace[
                        "start_corner"
                    ]
                )
                if trace.get(
                    "start_corner"
                )
                is not None
                else None,
            "end_corner":
                list(
                    trace[
                        "end_corner"
                    ]
                )
                if trace.get(
                    "end_corner"
                )
                is not None
                else None,
            "upturn_found":
                bool(
                    trace.get(
                        "upturn_found",
                        False,
                    )
                ),
            "wall_band_spacing_scene":
                wall_sides.get(
                    "wall_band_spacing_scene"
                ),
            "filter_stats":
                filter_stats,
        }

        opening_types = [
            row[
                "semantic_type"
            ]
            for row in trace.get(
                "openings",
                [],
            )
        ]

        print(
            "PLAN3D FRONT FACADE V4 |",
            floor_name,
            "| outer_wall_segments=",
            len(
                trace.get(
                    "wall_segments",
                    [],
                )
            ),
            "| inner_wall_segments=",
            len(
                wall_sides.get(
                    "inner_segments",
                    [],
                )
            ),
            "| openings=",
            opening_types,
            "| upturn_found=",
            trace.get(
                "upturn_found"
            ),
            flush=True,
        )

    self._facade_analysis_front_v4 = (
        results
    )

    self.selection_status.setText(
        "Facade Analysis: Front facade uses outer Wall face and passes through Window/Sliding/Exterior Door openings."
    )

    print(
        "PLAN3D FRONT FACADE V4 COMPLETE | floors=",
        len(
            results
        ),
        flush=True,
    )

    return results



# ============================================================
# PLAN3D_FACADE_PROJECT_OPENINGS_TO_OUTER_FACE_V5
#
# Fix for V4:
# Opening bridge geometry does not necessarily lie on the OUTER wall face.
# Therefore Window / Sliding Door / Exterior Door openings are projected
# to the selected FRONT outer wall face before tracing.
#
# Result:
# - a window jamb vertical is NOT treated as facade corner
# - opening span is crossed virtually on the OUTER face
# - FRONT continues until a real upward exterior-wall turn
# - inner/outer pair is still recorded separately
# ============================================================


def _plan3d_facade_v5_window_openings(
    viewport,
    rect_values,
    wall_paths,
    source_to_mm,
):
    from floor_area_runtime import (
        _window_paths_in_floor,
        _resolve_windows_v33,
        _require_shapely,
    )

    rows = []

    try:
        window_paths = _window_paths_in_floor(
            viewport,
            rect_values,
        )

        api = _require_shapely()

        (
            _bridge_paths,
            _footprint,
            window_meta,
            _stats,
        ) = _resolve_windows_v33(
            window_paths,
            wall_paths,
            source_to_mm,
            api,
        )

    except Exception as exc:
        print(
            "PLAN3D FACADE V5 | window resolver warning:",
            exc,
            flush=True,
        )
        return rows

    for index, meta in enumerate(
        list(
            window_meta
            or []
        )
    ):
        points = []

        if not isinstance(
            meta,
            dict,
        ):
            continue

        # V33 physical wall contacts.
        for key in (
            "A1",
            "A2",
            "B1",
            "B2",
            "A",
            "B",
        ):
            value = meta.get(
                key
            )

            if not (
                isinstance(
                    value,
                    (list, tuple),
                )
                and len(
                    value
                )
                >= 2
            ):
                continue

            try:
                points.append(
                    (
                        float(
                            value[0]
                        ),
                        float(
                            value[1]
                        ),
                    )
                )
            except Exception:
                continue

        if len(
            points
        ) < 2:
            continue

        xs = [
            p[0]
            for p in points
        ]

        ys = [
            p[1]
            for p in points
        ]

        x_span = (
            max(
                xs
            )
            - min(
                xs
            )
        )

        y_span = (
            max(
                ys
            )
            - min(
                ys
            )
        )

        if x_span <= y_span:
            continue

        rows.append(
            {
                "semantic_type":
                    "Window",
                "x0":
                    float(
                        min(
                            xs
                        )
                    ),
                "x1":
                    float(
                        max(
                            xs
                        )
                    ),
                "y0":
                    float(
                        min(
                            ys
                        )
                    ),
                "y1":
                    float(
                        max(
                            ys
                        )
                    ),
                "source_index":
                    int(
                        index
                    ),
            }
        )

    return rows


def _plan3d_facade_v5_symbol_openings(
    viewport,
    rect_values,
    wall_paths,
    source_to_mm,
):
    from floor_area_runtime import (
        _symbol_opening_bridge_paths,
    )

    rows = []

    try:
        (
            paths,
            metadata,
            _stats,
        ) = _symbol_opening_bridge_paths(
            viewport,
            rect_values,
            wall_paths,
            source_to_mm,
        )

    except Exception as exc:
        print(
            "PLAN3D FACADE V5 | symbol bridge warning:",
            exc,
            flush=True,
        )
        return rows

    for index, (
        path,
        meta,
    ) in enumerate(
        zip(
            paths,
            metadata,
        )
    ):
        semantic = str(
            (
                meta
                or {}
            ).get(
                "semantic_type",
                "",
            )
            or ""
        )

        semantic_cf = (
            semantic.casefold()
        )

        if not (
            semantic in (
                "Sliding Door",
                "Exterior Door",
                "Door",
            )
            or "sliding" in semantic_cf
            or "exterior" in semantic_cf
            or "dış" in semantic_cf
        ):
            continue

        points = []

        for point in list(
            path
            or []
        ):
            try:
                points.append(
                    (
                        float(
                            point[0]
                        ),
                        float(
                            point[1]
                        ),
                    )
                )
            except Exception:
                continue

        if len(
            points
        ) < 2:
            continue

        xs = [
            p[0]
            for p in points
        ]

        ys = [
            p[1]
            for p in points
        ]

        x_span = (
            max(
                xs
            )
            - min(
                xs
            )
        )

        y_span = (
            max(
                ys
            )
            - min(
                ys
            )
        )

        # FRONT facade openings must advance in X.
        if x_span <= y_span:
            continue

        rows.append(
            {
                "semantic_type":
                    semantic
                    or "Door",
                "x0":
                    float(
                        min(
                            xs
                        )
                    ),
                "x1":
                    float(
                        max(
                            xs
                        )
                    ),
                "y0":
                    float(
                        min(
                            ys
                        )
                    ),
                "y1":
                    float(
                        max(
                            ys
                        )
                    ),
                "source_index":
                    int(
                        index
                    ),
            }
        )

    return rows


def _plan3d_facade_v5_openings(
    viewport,
    rect_values,
    wall_paths,
    source_to_mm,
):
    rows = []

    rows.extend(
        _plan3d_facade_v5_window_openings(
            viewport,
            rect_values,
            wall_paths,
            source_to_mm,
        )
    )

    rows.extend(
        _plan3d_facade_v5_symbol_openings(
            viewport,
            rect_values,
            wall_paths,
            source_to_mm,
        )
    )

    # Geometry dedupe, but preserve semantic type.
    deduped = []
    seen = set()

    for row in rows:
        key = (
            str(
                row[
                    "semantic_type"
                ]
            ),
            round(
                float(
                    row[
                        "x0"
                    ]
                ),
                4,
            ),
            round(
                float(
                    row[
                        "x1"
                    ]
                ),
                4,
            ),
            round(
                float(
                    row[
                        "y0"
                    ]
                ),
                4,
            ),
            round(
                float(
                    row[
                        "y1"
                    ]
                ),
                4,
            ),
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        deduped.append(
            row
        )

    return deduped


def _plan3d_facade_v5_trace_front_outer_face(
    viewport,
    filtered_wall_paths,
    selected,
    wall_sides,
    openings,
    source_to_mm,
):
    segments = (
        _plan3d_facade_v2_paths_to_segments(
            filtered_wall_paths
        )
    )

    cad_to_cm = max(
        float(
            source_to_mm
        )
        / 10.0,
        1.0e-12,
    )

    join_tolerance = (
        5.0
        / cad_to_cm
    )

    wall_band_spacing = (
        wall_sides.get(
            "wall_band_spacing_scene"
        )
    )

    if wall_band_spacing is None:
        wall_band_spacing = (
            35.0
            / cad_to_cm
        )

    opening_y_tolerance = max(
        float(
            wall_band_spacing
        )
        * 1.75,
        12.0
        / cad_to_cm,
    )

    selected_a = tuple(
        selected[
            "a"
        ]
    )

    selected_b = tuple(
        selected[
            "b"
        ]
    )

    def distance(
        p,
        q,
    ):
        return (
            (
                float(
                    p[0]
                )
                - float(
                    q[0]
                )
            )
            ** 2
            + (
                float(
                    p[1]
                )
                - float(
                    q[1]
                )
            )
            ** 2
        ) ** 0.5

    def same_point(
        p,
        q,
    ):
        return (
            distance(
                p,
                q,
            )
            <= join_tolerance
        )

    selected_index = None

    for index, row in enumerate(
        segments
    ):
        if (
            (
                same_point(
                    row[
                        "a"
                    ],
                    selected_a,
                )
                and same_point(
                    row[
                        "b"
                    ],
                    selected_b,
                )
            )
            or (
                same_point(
                    row[
                        "a"
                    ],
                    selected_b,
                )
                and same_point(
                    row[
                        "b"
                    ],
                    selected_a,
                )
            )
        ):
            selected_index = (
                index
            )
            break

    if selected_index is None:
        return {
            "wall_segments":
                [],
            "openings":
                [],
            "start_corner":
                None,
            "end_corner":
                None,
            "upturn_found":
                False,
        }

    adjacency = {}

    for index, row in enumerate(
        segments
    ):
        for point in (
            row[
                "a"
            ],
            row[
                "b"
            ],
        ):
            key = (
                _plan3d_facade_v3_endpoint_key(
                    point,
                    join_tolerance,
                )
            )

            adjacency.setdefault(
                key,
                [],
            ).append(
                index
            )

    avx, _avy = (
        _plan3d_scene_to_view_xy_v1(
            viewport,
            selected_a[0],
            selected_a[1],
        )
    )

    bvx, _bvy = (
        _plan3d_scene_to_view_xy_v1(
            viewport,
            selected_b[0],
            selected_b[1],
        )
    )

    if avx <= bvx:
        start_corner = (
            selected_a
        )

        current_point = (
            selected_b
        )
    else:
        start_corner = (
            selected_b
        )

        current_point = (
            selected_a
        )

    outer_y = float(
        (
            selected_a[1]
            + selected_b[1]
        )
        * 0.5
    )

    wall_run = [
        {
            "a":
                selected_a,
            "b":
                selected_b,
            "segment_index":
                int(
                    selected_index
                ),
        }
    ]

    used_wall = {
        selected_index
    }

    used_openings = set()

    opening_run = []

    upturn_found = False

    guard = 0

    while guard < max(
        len(
            segments
        )
        * 5
        + len(
            openings
        )
        * 5,
        64,
    ):
        guard += 1

        current_vx, current_vy = (
            _plan3d_scene_to_view_xy_v1(
                viewport,
                current_point[0],
                current_point[1],
            )
        )

        current_key = (
            _plan3d_facade_v3_endpoint_key(
                current_point,
                join_tolerance,
            )
        )

        connected_wall = [
            index
            for index in adjacency.get(
                current_key,
                [],
            )
            if index not in used_wall
        ]

        horizontal_forward = []
        upward_wall = []

        for index in connected_wall:
            row = segments[
                index
            ]

            other = (
                _plan3d_facade_v3_other_endpoint(
                    row,
                    current_point,
                    join_tolerance,
                )
            )

            if other is None:
                continue

            ovx, ovy = (
                _plan3d_scene_to_view_xy_v1(
                    viewport,
                    other[0],
                    other[1],
                )
            )

            dx = (
                ovx
                - current_vx
            )

            dy = (
                ovy
                - current_vy
            )

            if (
                dx > 0.0
                and abs(
                    dy
                )
                <= max(
                    2.0,
                    abs(
                        dx
                    )
                    * 0.04,
                )
            ):
                horizontal_forward.append(
                    (
                        -abs(
                            dx
                        ),
                        index,
                        tuple(
                            other
                        ),
                    )
                )

                continue

            if (
                dy < 0.0
                and abs(
                    dx
                )
                <= max(
                    2.0,
                    abs(
                        dy
                    )
                    * 0.04,
                )
            ):
                upward_wall.append(
                    (
                        abs(
                            dy
                        ),
                        index,
                        tuple(
                            other
                        ),
                    )
                )

        if horizontal_forward:
            horizontal_forward.sort(
                key=lambda item:
                    item[
                        0
                    ]
            )

            _rank, next_index, next_point = (
                horizontal_forward[
                    0
                ]
            )

            row = segments[
                next_index
            ]

            wall_run.append(
                {
                    "a":
                        tuple(
                            row[
                                "a"
                            ]
                        ),
                    "b":
                        tuple(
                            row[
                                "b"
                            ]
                        ),
                    "segment_index":
                        int(
                            next_index
                        ),
                }
            )

            used_wall.add(
                next_index
            )

            current_point = (
                tuple(
                    next_point
                )
            )

            outer_y = (
                (
                    wall_run[
                        -1
                    ][
                        "a"
                    ][1]
                    + wall_run[
                        -1
                    ][
                        "b"
                    ][1]
                )
                * 0.5
            )

            continue

        # Project every eligible opening to the current OUTER face.
        opening_candidates = []

        for opening_index, opening in enumerate(
            openings
        ):
            if opening_index in used_openings:
                continue

            x0 = float(
                opening[
                    "x0"
                ]
            )

            x1 = float(
                opening[
                    "x1"
                ]
            )

            if x1 <= x0:
                continue

            opening_y0 = float(
                opening[
                    "y0"
                ]
            )

            opening_y1 = float(
                opening[
                    "y1"
                ]
            )

            if (
                outer_y
                < opening_y0
                - opening_y_tolerance
                or outer_y
                > opening_y1
                + opening_y_tolerance
            ):
                continue

            current_x = float(
                current_point[
                    0
                ]
            )

            # Current wall endpoint may be on either wall face/jamb.
            # Match by X, then project the whole opening span to outer_y.
            left_error = abs(
                current_x
                - x0
            )

            right_error = abs(
                current_x
                - x1
            )

            if (
                left_error
                <= join_tolerance
                * 3.0
            ):
                target_x = (
                    x1
                )

                start_x = (
                    x0
                )

            elif (
                right_error
                <= join_tolerance
                * 3.0
            ):
                # We only trace visually to the right.
                continue

            else:
                continue

            if target_x <= current_x:
                continue

            opening_candidates.append(
                (
                    target_x
                    - current_x,
                    opening_index,
                    opening,
                    (
                        start_x,
                        outer_y,
                    ),
                    (
                        target_x,
                        outer_y,
                    ),
                )
            )

        if opening_candidates:
            opening_candidates.sort(
                key=lambda item:
                    item[
                        0
                    ]
            )

            (
                _span,
                opening_index,
                opening,
                projected_a,
                projected_b,
            ) = opening_candidates[
                0
            ]

            opening_run.append(
                {
                    "semantic_type":
                        opening[
                            "semantic_type"
                        ],
                    "a":
                        projected_a,
                    "b":
                        projected_b,
                    "source_bounds": {
                        "x0":
                            opening[
                                "x0"
                            ],
                        "x1":
                            opening[
                                "x1"
                            ],
                        "y0":
                            opening[
                                "y0"
                            ],
                        "y1":
                            opening[
                                "y1"
                            ],
                    },
                }
            )

            used_openings.add(
                opening_index
            )

            current_point = (
                projected_b
            )

            # After crossing an opening, snap to an actual wall endpoint
            # at the projected target X on the same outer face.
            best_snap = None

            for index, row in enumerate(
                segments
            ):
                if index in used_wall:
                    continue

                for point in (
                    row[
                        "a"
                    ],
                    row[
                        "b"
                    ],
                ):
                    px = float(
                        point[
                            0
                        ]
                    )

                    py = float(
                        point[
                            1
                        ]
                    )

                    error = (
                        abs(
                            px
                            - projected_b[
                                0
                            ]
                        )
                        + abs(
                            py
                            - outer_y
                        )
                    )

                    if (
                        abs(
                            px
                            - projected_b[
                                0
                            ]
                        )
                        <= join_tolerance
                        * 3.0
                        and abs(
                            py
                            - outer_y
                        )
                        <= opening_y_tolerance
                    ):
                        if (
                            best_snap is None
                            or error
                            < best_snap[
                                0
                            ]
                        ):
                            best_snap = (
                                error,
                                tuple(
                                    point
                                ),
                            )

            if best_snap is not None:
                current_point = (
                    best_snap[
                        1
                    ]
                )

            continue

        # Only after all opening continuations fail may an upward Wall
        # terminate the FRONT facade.
        if upward_wall:
            upturn_found = True
            break

        break

    return {
        "wall_segments":
            wall_run,
        "openings":
            opening_run,
        "start_corner":
            tuple(
                start_corner
            ),
        "end_corner":
            tuple(
                current_point
            ),
        "upturn_found":
            bool(
                upturn_found
            ),
        "outer_y":
            float(
                outer_y
            ),
    }


def _plan3d_run_facade_project_openings_to_outer_face_v5(self):
    from floor_area_runtime import (
        _export_prepared_wall_paths,
    )

    from plan3d_canonical_export import (
        _cad_unit_info,
    )

    page = self.parentWidget()

    viewport = (
        getattr(
            page,
            "viewport",
            None,
        )
        if page is not None
        else None
    )

    if viewport is None:
        raise RuntimeError(
            "Facade Analysis: viewport unavailable."
        )

    _plan3d_clear_facade_bottom_left_preview_v1(
        viewport
    )

    values = self.values()

    assignments = dict(
        (
            values.get(
                "assignments",
                {},
            )
            or {}
        ).get(
            "floor_plans",
            {},
        )
        or {}
    )

    floor_settings = dict(
        values.get(
            "floor_settings",
            {},
        )
        or {}
    )

    pivot_map = dict(
        getattr(
            self,
            "_floor_pivots",
            {},
        )
        or {}
    )

    if not assignments:
        raise RuntimeError(
            "Facade Analysis: no Floor Plan assignments."
        )

    units_info = _cad_unit_info(
        viewport
    )

    source_to_mm = (
        float(
            units_info.get(
                "to_cm",
                1.0,
            )
            or 1.0
        )
        * 10.0
    )

    results = {}

    for floor_name, rect_values in assignments.items():
        floor_name = str(
            floor_name
        )

        settings = dict(
            floor_settings.get(
                floor_name,
                {},
            )
            or {}
        )

        pivot = dict(
            pivot_map.get(
                floor_name,
                {},
            )
            or {}
        )

        (
            wall_paths,
            _wall_topology,
            _export_floor,
        ) = _export_prepared_wall_paths(
            viewport,
            floor_name,
            rect_values,
            pivot,
            settings,
            units_info,
        )

        opening_segments_for_filter = (
            _plan3d_facade_v2_opening_segments(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )

        (
            filtered_wall_paths,
            filter_stats,
        ) = _plan3d_facade_v2_filter_wall_components(
            wall_paths,
            opening_segments_for_filter,
            source_to_mm,
        )

        selected = (
            _plan3d_find_bottom_left_export_segment_v1(
                viewport,
                filtered_wall_paths,
            )
        )

        if selected is None:
            print(
                "PLAN3D FRONT FACADE V5 |",
                floor_name,
                "| result=NO_START_SEGMENT",
                flush=True,
            )
            continue

        wall_sides = (
            _plan3d_facade_v4_front_outer_inner(
                viewport,
                filtered_wall_paths,
                selected,
                source_to_mm,
            )
        )

        openings = (
            _plan3d_facade_v5_openings(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )

        trace = (
            _plan3d_facade_v5_trace_front_outer_face(
                viewport,
                filtered_wall_paths,
                selected,
                wall_sides,
                openings,
                source_to_mm,
            )
        )

        _plan3d_draw_front_facade_v4(
            viewport,
            floor_name,
            trace,
            wall_sides,
        )

        results[
            floor_name
        ] = {
            "facade":
                "Front",
            "outer_wall_segments":
                [
                    {
                        "a":
                            list(
                                row[
                                    "a"
                                ]
                            ),
                        "b":
                            list(
                                row[
                                    "b"
                                ]
                            ),
                    }
                    for row in trace.get(
                        "wall_segments",
                        [],
                    )
                ],
            "inner_wall_segments":
                [
                    {
                        "a":
                            list(
                                row[
                                    "a"
                                ]
                            ),
                        "b":
                            list(
                                row[
                                    "b"
                                ]
                            ),
                    }
                    for row in wall_sides.get(
                        "inner_segments",
                        [],
                    )
                ],
            "openings":
                [
                    {
                        "semantic_type":
                            row[
                                "semantic_type"
                            ],
                        "a":
                            list(
                                row[
                                    "a"
                                ]
                            ),
                        "b":
                            list(
                                row[
                                    "b"
                                ]
                            ),
                    }
                    for row in trace.get(
                        "openings",
                        [],
                    )
                ],
            "start_corner":
                list(
                    trace[
                        "start_corner"
                    ]
                )
                if trace.get(
                    "start_corner"
                )
                is not None
                else None,
            "end_corner":
                list(
                    trace[
                        "end_corner"
                    ]
                )
                if trace.get(
                    "end_corner"
                )
                is not None
                else None,
            "upturn_found":
                bool(
                    trace.get(
                        "upturn_found",
                        False,
                    )
                ),
            "wall_band_spacing_scene":
                wall_sides.get(
                    "wall_band_spacing_scene"
                ),
            "filter_stats":
                filter_stats,
        }

        print(
            "PLAN3D FRONT FACADE V5 |",
            floor_name,
            "| outer_wall_segments=",
            len(
                trace.get(
                    "wall_segments",
                    [],
                )
            ),
            "| inner_wall_segments=",
            len(
                wall_sides.get(
                    "inner_segments",
                    [],
                )
            ),
            "| openings_crossed=",
            [
                row[
                    "semantic_type"
                ]
                for row in trace.get(
                    "openings",
                    [],
                )
            ],
            "| upturn_found=",
            trace.get(
                "upturn_found"
            ),
            flush=True,
        )

    self._facade_analysis_front_v5 = (
        results
    )

    self.selection_status.setText(
        "Facade Analysis: Front outer Wall face crosses facade openings before stopping at the real corner."
    )

    print(
        "PLAN3D FRONT FACADE V5 COMPLETE | floors=",
        len(
            results
        ),
        flush=True,
    )

    return results



# ============================================================
# PLAN3D_FACADE_OUTER_FROM_FLOOR_BOUNDARY_V6
#
# OUTER / INNER wall classification is no longer inferred from
# "visually lower" parallel lines.
#
# It is checked against the SAME floor-boundary idea:
#   export-prepared Wall
#   + Window closures
#   + Door / Sliding Door / Exterior Door closures
#   -> polygonize
#   -> union
#   -> FLOOR EXTERIOR BOUNDARY
#
# A Wall segment is OUTER only if it lies on / touches this
# generated floor exterior boundary. Parallel Wall lines that do
# not touch the floor exterior boundary are INNER.
# ============================================================


def _plan3d_facade_v6_floor_boundary(
    viewport,
    rect_values,
    wall_paths,
    source_to_mm,
):
    from floor_area_runtime import (
        _require_shapely,
        _polygonize,
        _polygon_parts,
        _window_paths_in_floor,
        _resolve_windows_v33,
        _symbol_opening_bridge_paths,
    )

    api = _require_shapely()

    boundary_paths = list(
        wall_paths
        or []
    )

    # Same Window closure principle used by Floor Areas.
    try:
        window_paths = _window_paths_in_floor(
            viewport,
            rect_values,
        )

        (
            window_bridges,
            _window_footprint,
            _window_meta,
            _window_stats,
        ) = _resolve_windows_v33(
            window_paths,
            wall_paths,
            source_to_mm,
            api,
        )

        boundary_paths.extend(
            list(
                window_bridges
                or []
            )
        )

    except Exception as exc:
        print(
            "PLAN3D FACADE V6 | floor window closure warning:",
            exc,
            flush=True,
        )

    # Same Door / Sliding Door / Exterior Door closure principle.
    try:
        (
            symbol_bridges,
            _symbol_meta,
            _symbol_stats,
        ) = _symbol_opening_bridge_paths(
            viewport,
            rect_values,
            wall_paths,
            source_to_mm,
        )

        boundary_paths.extend(
            list(
                symbol_bridges
                or []
            )
        )

    except Exception as exc:
        print(
            "PLAN3D FACADE V6 | floor symbol closure warning:",
            exc,
            flush=True,
        )

    (
        raw_faces,
        _diagnostics,
    ) = _polygonize(
        boundary_paths,
        api,
    )

    polygons = []

    for face in list(
        raw_faces
        or []
    ):
        for polygon in _polygon_parts(
            face,
            api,
        ):
            try:
                if float(
                    polygon.area
                ) <= 0.0:
                    continue
            except Exception:
                continue

            polygons.append(
                polygon
            )

    if not polygons:
        return None

    try:
        floor_union = api[
            "unary_union"
        ](
            polygons
        )
    except Exception:
        return None

    return floor_union


def _plan3d_facade_v6_outer_wall_paths(
    wall_paths,
    floor_geometry,
    source_to_mm,
):
    from floor_area_runtime import (
        _require_shapely,
    )

    api = _require_shapely()

    LineString = api[
        "LineString"
    ]

    cad_to_cm = max(
        float(
            source_to_mm
        )
        / 10.0,
        1.0e-12,
    )

    # Small tolerance only for numeric welding / polygonization noise.
    tolerance = (
        2.0
        / cad_to_cm
    )

    try:
        exterior_boundary = (
            floor_geometry.boundary
        )
    except Exception:
        return (
            [],
            [],
        )

    outer_paths = []
    inner_paths = []

    for row in _plan3d_facade_v2_paths_to_segments(
        wall_paths
    ):
        a = row[
            "a"
        ]

        b = row[
            "b"
        ]

        try:
            line = LineString(
                [
                    a,
                    b,
                ]
            )
        except Exception:
            continue

        try:
            length = float(
                line.length
            )

            if length <= 1.0e-9:
                continue

            # A true outside wall face follows the generated Floor exterior.
            buffered_boundary = (
                exterior_boundary.buffer(
                    tolerance
                )
            )

            overlap = (
                line.intersection(
                    buffered_boundary
                )
            )

            overlap_length = float(
                getattr(
                    overlap,
                    "length",
                    0.0,
                )
                or 0.0
            )

            midpoint = line.interpolate(
                0.5,
                normalized=True,
            )

            midpoint_distance = float(
                midpoint.distance(
                    exterior_boundary
                )
            )

            is_outer = (
                overlap_length
                >= length
                * 0.60
                and midpoint_distance
                <= tolerance
            )

        except Exception:
            is_outer = False

        target = (
            outer_paths
            if is_outer
            else inner_paths
        )

        target.append(
            [
                tuple(
                    a
                ),
                tuple(
                    b
                ),
            ]
        )

    return (
        outer_paths,
        inner_paths,
    )


def _plan3d_facade_v6_front_outer_inner(
    viewport,
    filtered_wall_paths,
    floor_geometry,
    source_to_mm,
):
    (
        outer_paths,
        inner_paths,
    ) = _plan3d_facade_v6_outer_wall_paths(
        filtered_wall_paths,
        floor_geometry,
        source_to_mm,
    )

    outer_segments = (
        _plan3d_facade_v2_paths_to_segments(
            outer_paths
        )
    )

    inner_segments = (
        _plan3d_facade_v2_paths_to_segments(
            inner_paths
        )
    )

    return {
        "outer_paths":
            outer_paths,
        "inner_paths":
            inner_paths,
        "outer_segments":
            outer_segments,
        "inner_segments":
            inner_segments,
        "wall_band_spacing_scene":
            None,
    }


def _plan3d_run_facade_outer_from_floor_boundary_v6(self):
    from floor_area_runtime import (
        _export_prepared_wall_paths,
    )

    from plan3d_canonical_export import (
        _cad_unit_info,
    )

    page = self.parentWidget()

    viewport = (
        getattr(
            page,
            "viewport",
            None,
        )
        if page is not None
        else None
    )

    if viewport is None:
        raise RuntimeError(
            "Facade Analysis: viewport unavailable."
        )

    _plan3d_clear_facade_bottom_left_preview_v1(
        viewport
    )

    values = self.values()

    assignments = dict(
        (
            values.get(
                "assignments",
                {},
            )
            or {}
        ).get(
            "floor_plans",
            {},
        )
        or {}
    )

    floor_settings = dict(
        values.get(
            "floor_settings",
            {},
        )
        or {}
    )

    pivot_map = dict(
        getattr(
            self,
            "_floor_pivots",
            {},
        )
        or {}
    )

    if not assignments:
        raise RuntimeError(
            "Facade Analysis: no Floor Plan assignments."
        )

    units_info = _cad_unit_info(
        viewport
    )

    source_to_mm = (
        float(
            units_info.get(
                "to_cm",
                1.0,
            )
            or 1.0
        )
        * 10.0
    )

    results = {}

    for floor_name, rect_values in assignments.items():
        floor_name = str(
            floor_name
        )

        settings = dict(
            floor_settings.get(
                floor_name,
                {},
            )
            or {}
        )

        pivot = dict(
            pivot_map.get(
                floor_name,
                {},
            )
            or {}
        )

        (
            wall_paths,
            _wall_topology,
            _export_floor,
        ) = _export_prepared_wall_paths(
            viewport,
            floor_name,
            rect_values,
            pivot,
            settings,
            units_info,
        )

        opening_segments_for_filter = (
            _plan3d_facade_v2_opening_segments(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )

        (
            filtered_wall_paths,
            filter_stats,
        ) = _plan3d_facade_v2_filter_wall_components(
            wall_paths,
            opening_segments_for_filter,
            source_to_mm,
        )

        floor_geometry = (
            _plan3d_facade_v6_floor_boundary(
                viewport,
                rect_values,
                filtered_wall_paths,
                source_to_mm,
            )
        )

        if floor_geometry is None:
            print(
                "PLAN3D FRONT FACADE V6 |",
                floor_name,
                "| result=NO_FLOOR_BOUNDARY",
                flush=True,
            )
            continue

        wall_sides = (
            _plan3d_facade_v6_front_outer_inner(
                viewport,
                filtered_wall_paths,
                floor_geometry,
                source_to_mm,
            )
        )

        outer_paths = list(
            wall_sides.get(
                "outer_paths",
                [],
            )
            or []
        )

        # IMPORTANT:
        # start selection is now allowed ONLY from Floor-exterior Wall lines.
        selected = (
            _plan3d_find_bottom_left_export_segment_v1(
                viewport,
                outer_paths,
            )
        )

        if selected is None:
            print(
                "PLAN3D FRONT FACADE V6 |",
                floor_name,
                "| result=NO_OUTER_START_SEGMENT",
                "| outer_segments=",
                len(
                    wall_sides.get(
                        "outer_segments",
                        [],
                    )
                ),
                flush=True,
            )
            continue

        openings = (
            _plan3d_facade_v5_openings(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )

        # Trace ONLY on floor-confirmed exterior Wall lines.
        trace = (
            _plan3d_facade_v5_trace_front_outer_face(
                viewport,
                outer_paths,
                selected,
                wall_sides,
                openings,
                source_to_mm,
            )
        )

        _plan3d_draw_front_facade_v4(
            viewport,
            floor_name,
            trace,
            wall_sides,
        )

        results[
            floor_name
        ] = {
            "facade":
                "Front",
            "outer_source":
                "FLOOR_EXTERIOR_BOUNDARY_V6",
            "outer_wall_segments":
                [
                    {
                        "a":
                            list(
                                row[
                                    "a"
                                ]
                            ),
                        "b":
                            list(
                                row[
                                    "b"
                                ]
                            ),
                    }
                    for row in trace.get(
                        "wall_segments",
                        [],
                    )
                ],
            "inner_wall_segment_count":
                int(
                    len(
                        wall_sides.get(
                            "inner_segments",
                            [],
                        )
                    )
                ),
            "floor_outer_wall_segment_count":
                int(
                    len(
                        wall_sides.get(
                            "outer_segments",
                            [],
                        )
                    )
                ),
            "openings":
                [
                    {
                        "semantic_type":
                            row[
                                "semantic_type"
                            ],
                        "a":
                            list(
                                row[
                                    "a"
                                ]
                            ),
                        "b":
                            list(
                                row[
                                    "b"
                                ]
                            ),
                    }
                    for row in trace.get(
                        "openings",
                        [],
                    )
                ],
            "start_corner":
                list(
                    trace[
                        "start_corner"
                    ]
                )
                if trace.get(
                    "start_corner"
                )
                is not None
                else None,
            "end_corner":
                list(
                    trace[
                        "end_corner"
                    ]
                )
                if trace.get(
                    "end_corner"
                )
                is not None
                else None,
            "upturn_found":
                bool(
                    trace.get(
                        "upturn_found",
                        False,
                    )
                ),
            "filter_stats":
                filter_stats,
        }

        print(
            "PLAN3D FRONT FACADE V6 |",
            floor_name,
            "| outer_source=FLOOR_EXTERIOR_BOUNDARY",
            "| floor_outer_segments=",
            len(
                wall_sides.get(
                    "outer_segments",
                    [],
                )
            ),
            "| inner_segments=",
            len(
                wall_sides.get(
                    "inner_segments",
                    [],
                )
            ),
            "| traced_front_segments=",
            len(
                trace.get(
                    "wall_segments",
                    [],
                )
            ),
            "| openings_crossed=",
            [
                row[
                    "semantic_type"
                ]
                for row in trace.get(
                    "openings",
                    [],
                )
            ],
            "| upturn_found=",
            trace.get(
                "upturn_found"
            ),
            flush=True,
        )

    self._facade_analysis_front_v6 = (
        results
    )

    self.selection_status.setText(
        "Facade Analysis: outer Wall verified against generated Floor exterior boundary."
    )

    print(
        "PLAN3D FRONT FACADE V6 COMPLETE | floors=",
        len(
            results
        ),
        flush=True,
    )

    return results



# ============================================================
# PLAN3D_FACADE_OUTER_FROM_ACTUAL_FLOOR_OVERLAY_V7
#
# V6 error:
#   Floor boundary itself is the INNER wall face because the floor
#   is trimmed to the inside of the wall.
#
# V7 rule:
#   1) Run the REAL Show Floor Areas engine.
#   2) Read the ACTUAL polygons drawn in viewport._floor_area_overlay_items.
#   3) Wall line touching that floor polygon boundary = INNER wall face.
#   4) Find its nearest parallel overlapping Wall counterpart.
#   5) Counterpart must NOT itself be a floor boundary.
#   6) That counterpart = OUTER wall face.
#   7) FRONT facade start/tracing uses only these confirmed OUTER faces.
#
# This is a control relationship:
# FLOOR EDGE -> INNER WALL -> PARALLEL COUNTERPART -> OUTER WALL
# ============================================================




def _plan3d_facade_v7_parallel_pair(
    inner,
    candidate,
    source_to_mm,
):
    import math

    a0 = inner[
        "a"
    ]

    a1 = inner[
        "b"
    ]

    b0 = candidate[
        "a"
    ]

    b1 = candidate[
        "b"
    ]

    adx = float(
        a1[0]
    ) - float(
        a0[0]
    )

    ady = float(
        a1[1]
    ) - float(
        a0[1]
    )

    bdx = float(
        b1[0]
    ) - float(
        b0[0]
    )

    bdy = float(
        b1[1]
    ) - float(
        b0[1]
    )

    alen = math.hypot(
        adx,
        ady,
    )

    blen = math.hypot(
        bdx,
        bdy,
    )

    if (
        alen <= 1.0e-9
        or blen <= 1.0e-9
    ):
        return None

    aux = adx / alen
    auy = ady / alen

    bux = bdx / blen
    buy = bdy / blen

    parallel = abs(
        aux * bux
        + auy * buy
    )

    if parallel < 0.995:
        return None

    nx = -auy
    ny = aux

    d0 = (
        (
            float(
                b0[0]
            )
            - float(
                a0[0]
            )
        )
        * nx
        + (
            float(
                b0[1]
            )
            - float(
                a0[1]
            )
        )
        * ny
    )

    d1 = (
        (
            float(
                b1[0]
            )
            - float(
                a0[0]
            )
        )
        * nx
        + (
            float(
                b1[1]
            )
            - float(
                a0[1]
            )
        )
        * ny
    )

    separation = abs(
        (
            d0
            + d1
        )
        * 0.5
    )

    separation_mm = (
        separation
        * float(
            source_to_mm
        )
    )

    if not (
        40.0
        <= separation_mm
        <= 600.0
    ):
        return None

    at0 = (
        float(
            a0[0]
        )
        * aux
        + float(
            a0[1]
        )
        * auy
    )

    at1 = (
        float(
            a1[0]
        )
        * aux
        + float(
            a1[1]
        )
        * auy
    )

    bt0 = (
        float(
            b0[0]
        )
        * aux
        + float(
            b0[1]
        )
        * auy
    )

    bt1 = (
        float(
            b1[0]
        )
        * aux
        + float(
            b1[1]
        )
        * auy
    )

    overlap = max(
        0.0,
        min(
            max(
                at0,
                at1,
            ),
            max(
                bt0,
                bt1,
            ),
        )
        - max(
            min(
                at0,
                at1,
            ),
            min(
                bt0,
                bt1,
            ),
        ),
    )

    min_len = min(
        alen,
        blen,
    )

    if (
        min_len <= 1.0e-9
        or overlap
        < min_len
        * 0.35
    ):
        return None

    return {
        "separation":
            float(
                separation
            ),
        "separation_mm":
            float(
                separation_mm
            ),
        "overlap":
            float(
                overlap
            ),
    }


def _plan3d_facade_v7_outer_from_floor(
    wall_paths,
    floor_geometry,
    source_to_mm,
):
    from floor_area_runtime import (
        _require_shapely,
    )

    api = _require_shapely()

    LineString = api[
        "LineString"
    ]

    cad_to_cm = max(
        float(
            source_to_mm
        )
        / 10.0,
        1.0e-12,
    )

    # Tight tolerance: floor overlay boundary is exact CAD geometry.
    boundary_tol = (
        2.0
        / cad_to_cm
    )

    segments = (
        _plan3d_facade_v2_paths_to_segments(
            wall_paths
        )
    )

    try:
        floor_boundary = (
            floor_geometry.boundary
        )
    except Exception:
        return {
            "inner_segments":
                [],
            "outer_segments":
                [],
            "pairs":
                [],
        }

    records = []

    for index, row in enumerate(
        segments
    ):
        try:
            line = LineString(
                [
                    row[
                        "a"
                    ],
                    row[
                        "b"
                    ],
                ]
            )

            length = float(
                line.length
            )

            if length <= 1.0e-9:
                continue

            midpoint = (
                line.interpolate(
                    0.5,
                    normalized=True,
                )
            )

            boundary_distance = float(
                midpoint.distance(
                    floor_boundary
                )
            )

            overlap_geometry = (
                line.intersection(
                    floor_boundary.buffer(
                        boundary_tol
                    )
                )
            )

            boundary_overlap = float(
                getattr(
                    overlap_geometry,
                    "length",
                    0.0,
                )
                or 0.0
            )

        except Exception:
            continue

        records.append(
            {
                **row,
                "record_index":
                    int(
                        index
                    ),
                "length":
                    float(
                        length
                    ),
                "boundary_distance":
                    float(
                        boundary_distance
                    ),
                "boundary_overlap":
                    float(
                        boundary_overlap
                    ),
            }
        )

    # Floor edge = INNER wall face.
    inner = [
        row
        for row in records
        if (
            row[
                "boundary_distance"
            ]
            <= boundary_tol
            and row[
                "boundary_overlap"
            ]
            >= row[
                "length"
            ]
            * 0.35
        )
    ]

    pair_rows = []
    outer_indices = set()

    for inner_row in inner:
        candidates = []

        for candidate in records:
            if (
                candidate[
                    "record_index"
                ]
                == inner_row[
                    "record_index"
                ]
            ):
                continue

            pair = (
                _plan3d_facade_v7_parallel_pair(
                    inner_row,
                    candidate,
                    source_to_mm,
                )
            )

            if pair is None:
                continue

            # Critical rule:
            # If the parallel counterpart is ALSO on the floor boundary,
            # this is normally an interior wall between two floor regions.
            # It is NOT an exterior-wall pair.
            if (
                candidate[
                    "boundary_distance"
                ]
                <= boundary_tol
                and candidate[
                    "boundary_overlap"
                ]
                >= candidate[
                    "length"
                ]
                * 0.25
            ):
                continue

            candidates.append(
                (
                    pair[
                        "separation"
                    ],
                    -pair[
                        "overlap"
                    ],
                    candidate[
                        "record_index"
                    ],
                    candidate,
                    pair,
                )
            )

        if not candidates:
            continue

        candidates.sort(
            key=lambda item:
                (
                    item[
                        0
                    ],
                    item[
                        1
                    ],
                    item[
                        2
                    ],
                )
        )

        (
            _sep,
            _overlap_rank,
            candidate_index,
            outer_row,
            pair,
        ) = candidates[
            0
        ]

        outer_indices.add(
            candidate_index
        )

        pair_rows.append(
            {
                "inner":
                    inner_row,
                "outer":
                    outer_row,
                "separation_mm":
                    float(
                        pair[
                            "separation_mm"
                        ]
                    ),
                "overlap":
                    float(
                        pair[
                            "overlap"
                        ]
                    ),
            }
        )

    outer = [
        row
        for row in records
        if row[
            "record_index"
        ]
        in outer_indices
    ]

    return {
        "inner_segments":
            inner,
        "outer_segments":
            outer,
        "pairs":
            pair_rows,
    }


def _plan3d_draw_floor_outer_control_v7(
    viewport,
    floor_name,
    classification,
):
    from PySide6.QtGui import (
        QColor,
        QPainterPath,
        QPen,
    )

    from PySide6.QtWidgets import (
        QGraphicsPathItem,
    )

    scene = viewport.scene()

    if scene is None:
        return

    items = list(
        getattr(
            viewport,
            "_plan3d_facade_bottom_left_items_v1",
            (),
        )
        or ()
    )

    # Thin magenta = floor-confirmed INNER face.
    inner_pen = QPen(
        QColor(
            "#FF4FD8"
        )
    )

    inner_pen.setCosmetic(
        True
    )

    inner_pen.setWidthF(
        2.0
    )

    for row in classification.get(
        "inner_segments",
        [],
    ):
        path = QPainterPath()

        path.moveTo(
            float(
                row[
                    "a"
                ][0]
            ),
            float(
                row[
                    "a"
                ][1]
            ),
        )

        path.lineTo(
            float(
                row[
                    "b"
                ][0]
            ),
            float(
                row[
                    "b"
                ][1]
            ),
        )

        item = QGraphicsPathItem(
            path
        )

        item.setPen(
            inner_pen
        )

        item.setZValue(
            4099990.0
        )

        scene.addItem(
            item
        )

        items.append(
            item
        )

    viewport._plan3d_facade_bottom_left_items_v1 = (
        items
    )


def _plan3d_run_facade_actual_floor_overlay_v7(self):
    from floor_area_runtime import (
        _export_prepared_wall_paths,
        show_all_floor_areas,
    )

    from plan3d_canonical_export import (
        _cad_unit_info,
    )

    page = self.parentWidget()

    viewport = (
        getattr(
            page,
            "viewport",
            None,
        )
        if page is not None
        else None
    )

    if viewport is None:
        raise RuntimeError(
            "Facade Analysis: viewport unavailable."
        )

    # FIRST: generate the REAL floor areas. Do not recreate floor geometry
    # inside Facade Analysis.
    floor_result = (
        show_all_floor_areas(
            self
        )
    )

    print(
        "PLAN3D FACADE V7 | actual Show Floor Areas executed | engine=",
        (
            floor_result
            or {}
        ).get(
            "engine",
            "UNKNOWN",
        )
        if isinstance(
            floor_result,
            dict,
        )
        else "UNKNOWN",
        flush=True,
    )

    _plan3d_clear_facade_bottom_left_preview_v1(
        viewport
    )

    values = self.values()

    assignments = dict(
        (
            values.get(
                "assignments",
                {},
            )
            or {}
        ).get(
            "floor_plans",
            {},
        )
        or {}
    )

    floor_settings = dict(
        values.get(
            "floor_settings",
            {},
        )
        or {}
    )

    pivot_map = dict(
        getattr(
            self,
            "_floor_pivots",
            {},
        )
        or {}
    )

    units_info = _cad_unit_info(
        viewport
    )

    source_to_mm = (
        float(
            units_info.get(
                "to_cm",
                1.0,
            )
            or 1.0
        )
        * 10.0
    )

    results = {}

    for floor_name, rect_values in assignments.items():
        floor_name = str(
            floor_name
        )

        floor_geometry = (
            _plan3d_facade_v7_actual_floor_geometry(
                viewport,
                rect_values,
            )
        )

        if floor_geometry is None:
            print(
                "PLAN3D FRONT FACADE V7 |",
                floor_name,
                "| result=NO_ACTUAL_FLOOR_OVERLAY",
                flush=True,
            )
            continue

        settings = dict(
            floor_settings.get(
                floor_name,
                {},
            )
            or {}
        )

        pivot = dict(
            pivot_map.get(
                floor_name,
                {},
            )
            or {}
        )

        (
            wall_paths,
            _wall_topology,
            _export_floor,
        ) = _export_prepared_wall_paths(
            viewport,
            floor_name,
            rect_values,
            pivot,
            settings,
            units_info,
        )

        opening_segments_for_filter = (
            _plan3d_facade_v2_opening_segments(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )

        (
            filtered_wall_paths,
            filter_stats,
        ) = _plan3d_facade_v2_filter_wall_components(
            wall_paths,
            opening_segments_for_filter,
            source_to_mm,
        )

        classification = (
            _plan3d_facade_v7_outer_from_floor(
                filtered_wall_paths,
                floor_geometry,
                source_to_mm,
            )
        )

        outer_paths = [
            [
                tuple(
                    row[
                        "a"
                    ]
                ),
                tuple(
                    row[
                        "b"
                    ]
                ),
            ]
            for row in classification.get(
                "outer_segments",
                [],
            )
        ]

        _plan3d_draw_floor_outer_control_v7(
            viewport,
            floor_name,
            classification,
        )

        selected = (
            _plan3d_find_bottom_left_export_segment_v1(
                viewport,
                outer_paths,
            )
        )

        if selected is None:
            print(
                "PLAN3D FRONT FACADE V7 |",
                floor_name,
                "| result=NO_FLOOR_CONFIRMED_OUTER_START",
                "| inner=",
                len(
                    classification.get(
                        "inner_segments",
                        [],
                    )
                ),
                "| outer=",
                len(
                    classification.get(
                        "outer_segments",
                        [],
                    )
                ),
                flush=True,
            )
            continue

        openings = (
            _plan3d_facade_v5_openings(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )

        trace = (
            _plan3d_facade_v5_trace_front_outer_face(
                viewport,
                outer_paths,
                selected,
                {
                    "wall_band_spacing_scene":
                        None,
                },
                openings,
                source_to_mm,
            )
        )

        _plan3d_draw_front_facade_v4(
            viewport,
            floor_name,
            trace,
            {
                "inner_segments":
                    classification.get(
                        "inner_segments",
                        [],
                    ),
            },
        )

        results[
            floor_name
        ] = {
            "facade":
                "Front",
            "outer_source":
                "ACTUAL_SHOW_FLOOR_AREAS_OVERLAY_V7",
            "inner_wall_segment_count":
                len(
                    classification.get(
                        "inner_segments",
                        [],
                    )
                ),
            "outer_wall_segment_count":
                len(
                    classification.get(
                        "outer_segments",
                        [],
                    )
                ),
            "wall_pair_count":
                len(
                    classification.get(
                        "pairs",
                        [],
                    )
                ),
            "front_segment_count":
                len(
                    trace.get(
                        "wall_segments",
                        [],
                    )
                ),
            "openings_crossed":
                [
                    row[
                        "semantic_type"
                    ]
                    for row in trace.get(
                        "openings",
                        [],
                    )
                ],
            "upturn_found":
                bool(
                    trace.get(
                        "upturn_found",
                        False,
                    )
                ),
            "filter_stats":
                filter_stats,
        }

        print(
            "PLAN3D FRONT FACADE V7 |",
            floor_name,
            "| floor_control=ACTUAL_VIEWPORT_FLOOR_OVERLAY",
            "| inner_faces=",
            len(
                classification.get(
                    "inner_segments",
                    [],
                )
            ),
            "| outer_faces=",
            len(
                classification.get(
                    "outer_segments",
                    [],
                )
            ),
            "| paired=",
            len(
                classification.get(
                    "pairs",
                    [],
                )
            ),
            "| front_segments=",
            len(
                trace.get(
                    "wall_segments",
                    [],
                )
            ),
            "| openings=",
            [
                row[
                    "semantic_type"
                ]
                for row in trace.get(
                    "openings",
                    [],
                )
            ],
            "| upturn_found=",
            trace.get(
                "upturn_found"
            ),
            flush=True,
        )

    self._facade_analysis_front_v7 = (
        results
    )

    self.selection_status.setText(
        "Facade Analysis: floor edge identifies INNER wall; parallel opposite face is OUTER wall."
    )

    print(
        "PLAN3D FRONT FACADE V7 COMPLETE | floors=",
        len(
            results
        ),
        flush=True,
    )

    return results



# ============================================================
# PLAN3D_FACADE_FRONT_OUTER_FROM_FLOOR_EDGE_V8
#
# Corrected rule:
# - run REAL Show Floor Areas only as a hidden control source
# - read the actual floor polygon
# - identify its visually-bottom horizontal boundary = INNER face
# - for each such floor-edge segment, find the nearest parallel
#   overlapping export-prepared Wall line on the OUTSIDE side
# - that parallel counterpart = OUTER face
# - hide the floor overlay immediately after geometry is read
# - FRONT facade is traced only on these floor-confirmed OUTER lines
# ============================================================


def _plan3d_facade_v8_hide_floor_overlay(viewport):
    items = list(
        getattr(
            viewport,
            "_floor_area_overlay_items",
            [],
        )
        or []
    )

    for item in items:
        try:
            scene = item.scene()
            if scene is not None:
                scene.removeItem(item)
        except Exception:
            pass

    try:
        viewport._floor_area_overlay_items = []
    except Exception:
        pass

    try:
        viewport.viewport().update()
    except Exception:
        try:
            viewport.update()
        except Exception:
            pass


def _plan3d_facade_v8_floor_horizontal_edges(
    viewport,
    floor_geometry,
):
    rows = []

    geometries = []

    geom_type = getattr(
        floor_geometry,
        "geom_type",
        "",
    )

    if geom_type == "Polygon":
        geometries = [
            floor_geometry
        ]

    elif geom_type == "MultiPolygon":
        geometries = list(
            floor_geometry.geoms
        )

    else:
        try:
            geometries = [
                geom
                for geom in floor_geometry.geoms
                if getattr(
                    geom,
                    "geom_type",
                    "",
                )
                == "Polygon"
            ]
        except Exception:
            geometries = []

    for polygon_index, polygon in enumerate(
        geometries
    ):
        try:
            coords = list(
                polygon.exterior.coords
            )
        except Exception:
            continue

        for index in range(
            len(
                coords
            )
            - 1
        ):
            a = (
                float(
                    coords[
                        index
                    ][0]
                ),
                float(
                    coords[
                        index
                    ][1]
                ),
            )

            b = (
                float(
                    coords[
                        index
                        + 1
                    ][0]
                ),
                float(
                    coords[
                        index
                        + 1
                    ][1]
                ),
            )

            avx, avy = (
                _plan3d_scene_to_view_xy_v1(
                    viewport,
                    a[0],
                    a[1],
                )
            )

            bvx, bvy = (
                _plan3d_scene_to_view_xy_v1(
                    viewport,
                    b[0],
                    b[1],
                )
            )

            dx = (
                bvx
                - avx
            )

            dy = (
                bvy
                - avy
            )

            if abs(
                dx
            ) <= 1.0e-9:
                continue

            if abs(
                dy
            ) > max(
                2.0,
                abs(
                    dx
                )
                * 0.04,
            ):
                continue

            rows.append(
                {
                    "polygon_index":
                        int(
                            polygon_index
                        ),
                    "a":
                        a,
                    "b":
                        b,
                    "view_y":
                        float(
                            (
                                avy
                                + bvy
                            )
                            * 0.5
                        ),
                    "view_x0":
                        float(
                            min(
                                avx,
                                bvx,
                            )
                        ),
                    "view_x1":
                        float(
                            max(
                                avx,
                                bvx,
                            )
                        ),
                }
            )

    return rows


def _plan3d_facade_v8_front_outer_paths(
    viewport,
    wall_paths,
    floor_geometry,
    source_to_mm,
):
    floor_edges = (
        _plan3d_facade_v8_floor_horizontal_edges(
            viewport,
            floor_geometry,
        )
    )

    if not floor_edges:
        return (
            [],
            [],
        )

    # Use the actual floor geometry to define the FRONT side:
    # visually bottom-most horizontal floor boundary.
    bottom_y = max(
        row[
            "view_y"
        ]
        for row in floor_edges
    )

    all_y = [
        row[
            "view_y"
        ]
        for row in floor_edges
    ]

    visual_span = max(
        max(
            all_y
        )
        - min(
            all_y
        ),
        1.0,
    )

    band_tol = max(
        8.0,
        visual_span
        * 0.03,
    )

    front_inner_edges = [
        row
        for row in floor_edges
        if (
            bottom_y
            - row[
                "view_y"
            ]
        )
        <= band_tol
    ]

    wall_segments = (
        _plan3d_facade_v2_paths_to_segments(
            wall_paths
        )
    )

    horizontal_walls = []

    for row in wall_segments:
        a = row[
            "a"
        ]

        b = row[
            "b"
        ]

        avx, avy = (
            _plan3d_scene_to_view_xy_v1(
                viewport,
                a[0],
                a[1],
            )
        )

        bvx, bvy = (
            _plan3d_scene_to_view_xy_v1(
                viewport,
                b[0],
                b[1],
            )
        )

        dx = (
            bvx
            - avx
        )

        dy = (
            bvy
            - avy
        )

        if abs(
            dx
        ) <= 1.0e-9:
            continue

        if abs(
            dy
        ) > max(
            2.0,
            abs(
                dx
            )
            * 0.04,
        ):
            continue

        horizontal_walls.append(
            {
                **row,
                "view_y":
                    float(
                        (
                            avy
                            + bvy
                        )
                        * 0.5
                    ),
                "view_x0":
                    float(
                        min(
                            avx,
                            bvx,
                        )
                    ),
                "view_x1":
                    float(
                        max(
                            avx,
                            bvx,
                        )
                    ),
            }
        )

    cad_to_cm = max(
        float(
            source_to_mm
        )
        / 10.0,
        1.0e-12,
    )

    min_sep_scene = (
        4.0
        / cad_to_cm
    )

    max_sep_scene = (
        60.0
        / cad_to_cm
    )

    outer = []
    pair_debug = []

    for inner in front_inner_edges:
        candidates = []

        inner_len = max(
            inner[
                "view_x1"
            ]
            - inner[
                "view_x0"
            ],
            1.0e-9,
        )

        for wall in horizontal_walls:
            overlap = max(
                0.0,
                min(
                    inner[
                        "view_x1"
                    ],
                    wall[
                        "view_x1"
                    ],
                )
                - max(
                    inner[
                        "view_x0"
                    ],
                    wall[
                        "view_x0"
                    ],
                ),
            )

            wall_len = max(
                wall[
                    "view_x1"
                ]
                - wall[
                    "view_x0"
                ],
                1.0e-9,
            )

            if overlap < min(
                inner_len,
                wall_len,
            ) * 0.30:
                continue

            # FRONT outside is visually BELOW the floor edge.
            view_sep = (
                wall[
                    "view_y"
                ]
                - inner[
                    "view_y"
                ]
            )

            if view_sep <= 0.0:
                continue

            scene_sep = (
                (
                    (
                        wall[
                            "a"
                        ][0]
                        + wall[
                            "b"
                        ][0]
                    )
                    * 0.5
                    - (
                        inner[
                            "a"
                        ][0]
                        + inner[
                            "b"
                        ][0]
                    )
                    * 0.5
                )
                ** 2
                + (
                    (
                        wall[
                            "a"
                        ][1]
                        + wall[
                            "b"
                        ][1]
                    )
                    * 0.5
                    - (
                        inner[
                            "a"
                        ][1]
                        + inner[
                            "b"
                        ][1]
                    )
                    * 0.5
                )
                ** 2
            ) ** 0.5

            if not (
                min_sep_scene
                <= scene_sep
                <= max_sep_scene
            ):
                continue

            candidates.append(
                (
                    float(
                        scene_sep
                    ),
                    -float(
                        overlap
                    ),
                    wall,
                )
            )

        if not candidates:
            continue

        candidates.sort(
            key=lambda item:
                (
                    item[
                        0
                    ],
                    item[
                        1
                    ],
                )
        )

        separation, _overlap_rank, chosen = (
            candidates[
                0
            ]
        )

        outer.append(
            [
                tuple(
                    chosen[
                        "a"
                    ]
                ),
                tuple(
                    chosen[
                        "b"
                    ]
                ),
            ]
        )

        pair_debug.append(
            {
                "inner_a":
                    inner[
                        "a"
                    ],
                "inner_b":
                    inner[
                        "b"
                    ],
                "outer_a":
                    chosen[
                        "a"
                    ],
                "outer_b":
                    chosen[
                        "b"
                    ],
                "separation_cm":
                    float(
                        separation
                        * cad_to_cm
                    ),
            }
        )

    # Dedupe identical outer Wall segments.
    deduped = []
    seen = set()

    for path in outer:
        a = path[
            0
        ]

        b = path[
            1
        ]

        key1 = (
            round(
                a[0],
                5,
            ),
            round(
                a[1],
                5,
            ),
            round(
                b[0],
                5,
            ),
            round(
                b[1],
                5,
            ),
        )

        key2 = (
            key1[
                2
            ],
            key1[
                3
            ],
            key1[
                0
            ],
            key1[
                1
            ],
        )

        key = min(
            key1,
            key2,
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        deduped.append(
            path
        )

    return (
        deduped,
        pair_debug,
    )


def _plan3d_run_facade_front_outer_floor_edge_v8(self):
    from floor_area_runtime import (
        _export_prepared_wall_paths,
        show_all_floor_areas,
    )

    from plan3d_canonical_export import (
        _cad_unit_info,
    )

    page = self.parentWidget()

    viewport = (
        getattr(
            page,
            "viewport",
            None,
        )
        if page is not None
        else None
    )

    if viewport is None:
        raise RuntimeError(
            "Facade Analysis: viewport unavailable."
        )

    # Generate the REAL floor polygons first.
    show_all_floor_areas(
        self
    )

    values = self.values()

    assignments = dict(
        (
            values.get(
                "assignments",
                {},
            )
            or {}
        ).get(
            "floor_plans",
            {},
        )
        or {}
    )

    floor_settings = dict(
        values.get(
            "floor_settings",
            {},
        )
        or {}
    )

    pivot_map = dict(
        getattr(
            self,
            "_floor_pivots",
            {},
        )
        or {}
    )

    units_info = _cad_unit_info(
        viewport
    )

    source_to_mm = (
        float(
            units_info.get(
                "to_cm",
                1.0,
            )
            or 1.0
        )
        * 10.0
    )

    # Read floor geometry BEFORE hiding the overlay.
    floor_geometries = {}

    for floor_name, rect_values in assignments.items():
        floor_geometries[
            str(
                floor_name
            )
        ] = (
            _plan3d_facade_v7_actual_floor_geometry(
                viewport,
                rect_values,
            )
        )

    # Floor is CONTROL DATA only. Do not leave it visible.
    _plan3d_facade_v8_hide_floor_overlay(
        viewport
    )

    _plan3d_clear_facade_bottom_left_preview_v1(
        viewport
    )

    results = {}

    for floor_name, rect_values in assignments.items():
        floor_name = str(
            floor_name
        )

        floor_geometry = (
            floor_geometries.get(
                floor_name
            )
        )

        if floor_geometry is None:
            print(
                "PLAN3D FRONT FACADE V8 |",
                floor_name,
                "| result=NO_FLOOR_CONTROL_GEOMETRY",
                flush=True,
            )
            continue

        settings = dict(
            floor_settings.get(
                floor_name,
                {},
            )
            or {}
        )

        pivot = dict(
            pivot_map.get(
                floor_name,
                {},
            )
            or {}
        )

        (
            wall_paths,
            _wall_topology,
            _export_floor,
        ) = _export_prepared_wall_paths(
            viewport,
            floor_name,
            rect_values,
            pivot,
            settings,
            units_info,
        )

        opening_segments_for_filter = (
            _plan3d_facade_v2_opening_segments(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )

        (
            filtered_wall_paths,
            filter_stats,
        ) = _plan3d_facade_v2_filter_wall_components(
            wall_paths,
            opening_segments_for_filter,
            source_to_mm,
        )

        (
            outer_paths,
            pair_debug,
        ) = _plan3d_facade_v8_front_outer_paths(
            viewport,
            filtered_wall_paths,
            floor_geometry,
            source_to_mm,
        )

        selected = (
            _plan3d_find_bottom_left_export_segment_v1(
                viewport,
                outer_paths,
            )
        )

        if selected is None:
            print(
                "PLAN3D FRONT FACADE V8 |",
                floor_name,
                "| result=NO_FLOOR_CONFIRMED_FRONT_OUTER",
                "| paired_outer=",
                len(
                    outer_paths
                ),
                flush=True,
            )
            continue

        openings = (
            _plan3d_facade_v5_openings(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )

        trace = (
            _plan3d_facade_v5_trace_front_outer_face(
                viewport,
                outer_paths,
                selected,
                {
                    "wall_band_spacing_scene":
                        None,
                },
                openings,
                source_to_mm,
            )
        )

        _plan3d_draw_front_facade_v4(
            viewport,
            floor_name,
            trace,
            {
                "inner_segments":
                    [],
            },
        )

        results[
            floor_name
        ] = {
            "facade":
                "Front",
            "outer_source":
                "ACTUAL_FLOOR_EDGE_PARALLEL_COUNTERPART_V8",
            "paired_outer_count":
                len(
                    outer_paths
                ),
            "pair_debug":
                pair_debug,
            "front_segment_count":
                len(
                    trace.get(
                        "wall_segments",
                        [],
                    )
                ),
            "openings_crossed":
                [
                    row[
                        "semantic_type"
                    ]
                    for row in trace.get(
                        "openings",
                        [],
                    )
                ],
            "filter_stats":
                filter_stats,
        }

        print(
            "PLAN3D FRONT FACADE V8 |",
            floor_name,
            "| floor_control=ACTUAL_SHOW_FLOOR_AREAS",
            "| paired_outer=",
            len(
                outer_paths
            ),
            "| front_segments=",
            len(
                trace.get(
                    "wall_segments",
                    [],
                )
            ),
            "| openings=",
            [
                row[
                    "semantic_type"
                ]
                for row in trace.get(
                    "openings",
                    [],
                )
            ],
            "| pairs_cm=",
            [
                round(
                    float(
                        row[
                            "separation_cm"
                        ]
                    ),
                    2,
                )
                for row in pair_debug
            ],
            flush=True,
        )

    self._facade_analysis_front_v8 = (
        results
    )

    self.selection_status.setText(
        "Facade Analysis: floor edge used only as hidden control; red line is its outside parallel Wall face."
    )

    print(
        "PLAN3D FRONT FACADE V8 COMPLETE | floors=",
        len(
            results
        ),
        flush=True,
    )

    return results



# ============================================================
# PLAN3D_FACADE_CAD_SCENE_Y_FIX_V9
#
# Root fix:
# CadGraphicsView draws CAD source coordinates as scene=(x, -y).
# Previous facade diagnostics treated CAD y and scene y as identical.
#
# V9 corrects BOTH conversions:
#   CAD -> scene/view : (x, -y)
#   floor overlay scene -> CAD : (x, -y)
#
# V8 then uses the real Show Floor Areas geometry in the SAME CAD
# coordinate system as export-prepared Wall paths.
# ============================================================






# V8 already owns the active Facade Analysis entry point.
# It calls _plan3d_facade_v7_actual_floor_geometry and
# _plan3d_scene_to_view_xy_v1 dynamically, so these corrected
# definitions are consumed automatically.

# ============================================================
# PLAN3D_FACADE_FLOOR_OVERLAY_EXTRACT_V10
#
# V9 still returned NO_FLOOR_CONTROL_GEOMETRY because the real
# Floor overlay items are not guaranteed to be QGraphicsPathItem.
#
# V10 reads actual floor overlays robustly:
# - QGraphicsPolygonItem -> polygon()
# - QGraphicsPathItem    -> path().toSubpathPolygons()
# - child graphics items recursively
# - local item coordinates -> scene using item.mapToScene()
# - scene -> CAD using (x, -y)
#
# Existing V8 facade logic remains active and consumes this function.
# ============================================================


def _plan3d_facade_v10_item_polygons_scene(item):
    polygons = []

    def map_point(qpoint):
        try:
            scene_point = item.mapToScene(
                qpoint
            )
            return (
                float(
                    scene_point.x()
                ),
                float(
                    scene_point.y()
                ),
            )
        except Exception:
            try:
                return (
                    float(
                        qpoint.x()
                    ),
                    float(
                        qpoint.y()
                    ),
                )
            except Exception:
                return None

    polygon_method = getattr(
        item,
        "polygon",
        None,
    )

    if callable(
        polygon_method
    ):
        try:
            qpolygon = polygon_method()
            points = []

            try:
                count = qpolygon.count()
            except Exception:
                count = len(
                    qpolygon
                )

            for index in range(
                count
            ):
                try:
                    mapped = map_point(
                        qpolygon[
                            index
                        ]
                    )
                except Exception:
                    mapped = None

                if mapped is not None:
                    points.append(
                        mapped
                    )

            if len(
                points
            ) >= 3:
                polygons.append(
                    points
                )
        except Exception:
            pass

    path_method = getattr(
        item,
        "path",
        None,
    )

    if callable(
        path_method
    ):
        try:
            path = path_method()

            for qpolygon in path.toSubpathPolygons():
                points = []

                try:
                    count = qpolygon.count()
                except Exception:
                    count = len(
                        qpolygon
                    )

                for index in range(
                    count
                ):
                    try:
                        mapped = map_point(
                            qpolygon[
                                index
                            ]
                        )
                    except Exception:
                        mapped = None

                    if mapped is not None:
                        points.append(
                            mapped
                        )

                if len(
                    points
                ) >= 3:
                    polygons.append(
                        points
                    )
        except Exception:
            pass

    try:
        children = list(
            item.childItems()
        )
    except Exception:
        children = []

    for child in children:
        polygons.extend(
            _plan3d_facade_v10_item_polygons_scene(
                child
            )
        )

    return polygons


def _plan3d_facade_v7_actual_floor_geometry(
    viewport,
    rect_values,
):
    from floor_area_runtime import (
        _require_shapely,
    )

    api = _require_shapely()

    try:
        from shapely.geometry import Polygon
    except Exception:
        return None

    try:
        rx, ry, rw, rh = [
            float(
                value
            )
            for value in rect_values
        ]
    except Exception:
        return None

    x0 = min(
        rx,
        rx + rw,
    )
    x1 = max(
        rx,
        rx + rw,
    )
    y0 = min(
        ry,
        ry + rh,
    )
    y1 = max(
        ry,
        ry + rh,
    )

    region = api[
        "box"
    ](
        x0,
        y0,
        x1,
        y1,
    )

    overlay_items = list(
        getattr(
            viewport,
            "_floor_area_overlay_items",
            [],
        )
        or []
    )

    polygons = []
    raw_polygon_count = 0
    item_types = []

    for item in overlay_items:
        try:
            item_types.append(
                type(
                    item
                ).__name__
            )
        except Exception:
            item_types.append(
                "UNKNOWN"
            )

        scene_polygons = (
            _plan3d_facade_v10_item_polygons_scene(
                item
            )
        )

        raw_polygon_count += len(
            scene_polygons
        )

        for scene_points in scene_polygons:
            # Graphics scene -> CAD source coordinates.
            cad_points = [
                (
                    float(
                        sx
                    ),
                    -float(
                        sy
                    ),
                )
                for sx, sy in scene_points
            ]

            if len(
                cad_points
            ) < 3:
                continue

            try:
                polygon = Polygon(
                    cad_points
                )

                if not polygon.is_valid:
                    polygon = api[
                        "make_valid"
                    ](
                        polygon
                    )

            except Exception:
                continue

            for part in api[
                "get_parts"
            ](
                polygon
            ):
                if getattr(
                    part,
                    "geom_type",
                    "",
                ) != "Polygon":
                    continue

                if part.is_empty:
                    continue

                try:
                    clipped = part.intersection(
                        region
                    )
                except Exception:
                    continue

                for clipped_part in api[
                    "get_parts"
                ](
                    clipped
                ):
                    if getattr(
                        clipped_part,
                        "geom_type",
                        "",
                    ) != "Polygon":
                        continue

                    if clipped_part.is_empty:
                        continue

                    try:
                        area = float(
                            clipped_part.area
                        )
                    except Exception:
                        area = 0.0

                    if area <= 1.0e-9:
                        continue

                    polygons.append(
                        clipped_part
                    )

    print(
        "PLAN3D FACADE V10 FLOOR OVERLAY |",
        "items=",
        len(
            overlay_items
        ),
        "| types=",
        item_types,
        "| raw_polygons=",
        raw_polygon_count,
        "| clipped_polygons=",
        len(
            polygons
        ),
        flush=True,
    )

    if not polygons:
        return None

    try:
        merged = api[
            "unary_union"
        ](
            polygons
        )
    except Exception:
        merged = polygons[
            0
        ]

    try:
        bounds = tuple(
            round(
                float(
                    value
                ),
                3,
            )
            for value in merged.bounds
        )
    except Exception:
        bounds = None

    print(
        "PLAN3D FACADE V10 FLOOR CONTROL |",
        "cad_bounds=",
        bounds,
        flush=True,
    )

    return merged


# V8 remains the active run_facade_analysis implementation and resolves
# this function name at runtime. No button/signal changes are required.

# ============================================================
# PLAN3D_FACADE_USE_EXISTING_VISIBLE_FLOORS_V12
#
# Corrected contract:
# - Facade Analysis DOES NOT generate floors.
# - User first uses the existing "Show Floor Areas" button.
# - Facade Analysis then reads the ALREADY VISIBLE floor graphics.
# - Those visible floor polygons are control geometry only.
# - Floor boundary = INNER wall face.
# - Nearest parallel export-prepared Wall line on the outside = OUTER.
#
# This fixes the previous mistake where Facade Analysis tried to
# create/hide/reconstruct floor geometry by itself.
# ============================================================


def _plan3d_facade_v12_candidate_floor_item_lists(panel, page, viewport):
    candidates = []

    for owner_name, owner in (
        ("panel", panel),
        ("page", page),
        ("viewport", viewport),
    ):
        if owner is None:
            continue

        try:
            values = vars(owner)
        except Exception:
            continue

        for attr_name, value in values.items():
            name_cf = str(attr_name).casefold()

            if "floor" not in name_cf:
                continue

            if not (
                "overlay" in name_cf
                or "area" in name_cf
                or "preview" in name_cf
                or "item" in name_cf
            ):
                continue

            if isinstance(
                value,
                (list, tuple),
            ) and value:
                candidates.append(
                    (
                        owner_name,
                        str(attr_name),
                        list(value),
                    )
                )

    return candidates


def _plan3d_facade_v12_item_scene_polygons(item):
    polygons = []

    def _map_point(point):
        try:
            mapped = item.mapToScene(
                point
            )
            return (
                float(
                    mapped.x()
                ),
                float(
                    mapped.y()
                ),
            )
        except Exception:
            try:
                return (
                    float(
                        point.x()
                    ),
                    float(
                        point.y()
                    ),
                )
            except Exception:
                return None

    polygon_fn = getattr(
        item,
        "polygon",
        None,
    )

    if callable(
        polygon_fn
    ):
        try:
            polygon = polygon_fn()
            points = []

            try:
                count = polygon.count()
            except Exception:
                count = len(
                    polygon
                )

            for index in range(
                count
            ):
                try:
                    point = _map_point(
                        polygon[
                            index
                        ]
                    )
                except Exception:
                    point = None

                if point is not None:
                    points.append(
                        point
                    )

            if len(
                points
            ) >= 3:
                polygons.append(
                    points
                )
        except Exception:
            pass

    path_fn = getattr(
        item,
        "path",
        None,
    )

    if callable(
        path_fn
    ):
        try:
            path = path_fn()

            for polygon in path.toSubpathPolygons():
                points = []

                try:
                    count = polygon.count()
                except Exception:
                    count = len(
                        polygon
                    )

                for index in range(
                    count
                ):
                    try:
                        point = _map_point(
                            polygon[
                                index
                            ]
                        )
                    except Exception:
                        point = None

                    if point is not None:
                        points.append(
                            point
                        )

                if len(
                    points
                ) >= 3:
                    polygons.append(
                        points
                    )
        except Exception:
            pass

    try:
        child_items = list(
            item.childItems()
        )
    except Exception:
        child_items = []

    for child in child_items:
        polygons.extend(
            _plan3d_facade_v12_item_scene_polygons(
                child
            )
        )

    return polygons


def _plan3d_facade_v12_visible_floor_geometry(
    panel,
    page,
    viewport,
    rect_values,
):
    from floor_area_runtime import (
        _require_shapely,
    )

    api = _require_shapely()

    try:
        from shapely.geometry import Polygon
    except Exception:
        return None, None

    try:
        rx, ry, rw, rh = [
            float(
                value
            )
            for value in rect_values
        ]
    except Exception:
        return None, None

    x0 = min(
        rx,
        rx + rw,
    )
    x1 = max(
        rx,
        rx + rw,
    )
    y0 = min(
        ry,
        ry + rh,
    )
    y1 = max(
        ry,
        ry + rh,
    )

    region = api[
        "box"
    ](
        x0,
        y0,
        x1,
        y1,
    )

    candidates = (
        _plan3d_facade_v12_candidate_floor_item_lists(
            panel,
            page,
            viewport,
        )
    )

    if not candidates:
        return None, None

    best = None

    for owner_name, attr_name, items in candidates:
        polygons = []
        raw_count = 0

        for item in items:
            scene_polygons = (
                _plan3d_facade_v12_item_scene_polygons(
                    item
                )
            )

            raw_count += len(
                scene_polygons
            )

            for scene_points in scene_polygons:
                # CAD scene convention: scene=(x,-y).
                cad_points = [
                    (
                        float(
                            point[0]
                        ),
                        -float(
                            point[1]
                        ),
                    )
                    for point in scene_points
                ]

                if len(
                    cad_points
                ) < 3:
                    continue

                try:
                    polygon = Polygon(
                        cad_points
                    )

                    if not polygon.is_valid:
                        polygon = api[
                            "make_valid"
                        ](
                            polygon
                        )
                except Exception:
                    continue

                for part in api[
                    "get_parts"
                ](
                    polygon
                ):
                    if getattr(
                        part,
                        "geom_type",
                        "",
                    ) != "Polygon":
                        continue

                    if part.is_empty:
                        continue

                    try:
                        clipped = (
                            part.intersection(
                                region
                            )
                        )
                    except Exception:
                        continue

                    for clipped_part in api[
                        "get_parts"
                    ](
                        clipped
                    ):
                        if getattr(
                            clipped_part,
                            "geom_type",
                            "",
                        ) != "Polygon":
                            continue

                        if clipped_part.is_empty:
                            continue

                        try:
                            area = float(
                                clipped_part.area
                            )
                        except Exception:
                            area = 0.0

                        if area <= 1.0e-9:
                            continue

                        polygons.append(
                            clipped_part
                        )

        if not polygons:
            continue

        try:
            merged = api[
                "unary_union"
            ](
                polygons
            )
        except Exception:
            merged = polygons[
                0
            ]

        try:
            area = float(
                merged.area
            )
        except Exception:
            area = 0.0

        candidate = {
            "owner":
                owner_name,
            "attr":
                attr_name,
            "raw_polygons":
                int(
                    raw_count
                ),
            "clipped_polygons":
                int(
                    len(
                        polygons
                    )
                ),
            "area":
                float(
                    area
                ),
            "geometry":
                merged,
        }

        if (
            best is None
            or candidate[
                "area"
            ]
            > best[
                "area"
            ]
        ):
            best = candidate

    if best is None:
        return None, None

    return (
        best[
            "geometry"
        ],
        {
            key:
                value
            for key, value in best.items()
            if key != "geometry"
        },
    )


def _plan3d_run_facade_existing_visible_floors_v12(self):
    from floor_area_runtime import (
        _export_prepared_wall_paths,
    )

    from plan3d_canonical_export import (
        _cad_unit_info,
    )

    page = self.parentWidget()

    viewport = (
        getattr(
            page,
            "viewport",
            None,
        )
        if page is not None
        else None
    )

    if viewport is None:
        raise RuntimeError(
            "Facade Analysis: viewport unavailable."
        )

    _plan3d_clear_facade_bottom_left_preview_v1(
        viewport
    )

    values = self.values()

    assignments = dict(
        (
            values.get(
                "assignments",
                {},
            )
            or {}
        ).get(
            "floor_plans",
            {},
        )
        or {}
    )

    floor_settings = dict(
        values.get(
            "floor_settings",
            {},
        )
        or {}
    )

    pivot_map = dict(
        getattr(
            self,
            "_floor_pivots",
            {},
        )
        or {}
    )

    if not assignments:
        raise RuntimeError(
            "Facade Analysis: no Floor Plan assignments."
        )

    units_info = _cad_unit_info(
        viewport
    )

    source_to_mm = (
        float(
            units_info.get(
                "to_cm",
                1.0,
            )
            or 1.0
        )
        * 10.0
    )

    results = {}

    for floor_name, rect_values in assignments.items():
        floor_name = str(
            floor_name
        )

        (
            floor_geometry,
            floor_info,
        ) = (
            _plan3d_facade_v12_visible_floor_geometry(
                self,
                page,
                viewport,
                rect_values,
            )
        )

        if floor_geometry is None:
            print(
                "PLAN3D FRONT FACADE V12 |",
                floor_name,
                "| result=VISIBLE_FLOOR_NOT_FOUND",
                flush=True,
            )
            continue

        settings = dict(
            floor_settings.get(
                floor_name,
                {},
            )
            or {}
        )

        pivot = dict(
            pivot_map.get(
                floor_name,
                {},
            )
            or {}
        )

        (
            wall_paths,
            _wall_topology,
            _export_floor,
        ) = _export_prepared_wall_paths(
            viewport,
            floor_name,
            rect_values,
            pivot,
            settings,
            units_info,
        )

        opening_segments_for_filter = (
            _plan3d_facade_v2_opening_segments(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )

        (
            filtered_wall_paths,
            filter_stats,
        ) = (
            _plan3d_facade_v2_filter_wall_components(
                wall_paths,
                opening_segments_for_filter,
                source_to_mm,
            )
        )

        (
            outer_paths,
            pair_debug,
        ) = (
            _plan3d_facade_v8_front_outer_paths(
                viewport,
                filtered_wall_paths,
                floor_geometry,
                source_to_mm,
            )
        )

        selected = (
            _plan3d_find_bottom_left_export_segment_v1(
                viewport,
                outer_paths,
            )
        )

        if selected is None:
            print(
                "PLAN3D FRONT FACADE V12 |",
                floor_name,
                "| result=NO_OUTER_PAIR",
                "| floor_source=",
                floor_info,
                "| paired_outer=",
                len(
                    outer_paths
                ),
                flush=True,
            )
            continue

        openings = (
            _plan3d_facade_v5_openings(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )

        trace = (
            _plan3d_facade_v5_trace_front_outer_face(
                viewport,
                outer_paths,
                selected,
                {
                    "wall_band_spacing_scene":
                        None,
                },
                openings,
                source_to_mm,
            )
        )

        _plan3d_draw_front_facade_v4(
            viewport,
            floor_name,
            trace,
            {
                "inner_segments":
                    [],
            },
        )

        results[
            floor_name
        ] = {
            "facade":
                "Front",
            "floor_control":
                floor_info,
            "paired_outer":
                int(
                    len(
                        outer_paths
                    )
                ),
            "front_segments":
                int(
                    len(
                        trace.get(
                            "wall_segments",
                            [],
                        )
                    )
                ),
            "openings_crossed":
                [
                    row[
                        "semantic_type"
                    ]
                    for row in trace.get(
                        "openings",
                        [],
                    )
                ],
            "pair_debug":
                pair_debug,
            "filter_stats":
                filter_stats,
        }

        print(
            "PLAN3D FRONT FACADE V12 |",
            floor_name,
            "| floor_source=",
            floor_info,
            "| paired_outer=",
            len(
                outer_paths
            ),
            "| front_segments=",
            len(
                trace.get(
                    "wall_segments",
                    [],
                )
            ),
            "| openings=",
            [
                row[
                    "semantic_type"
                ]
                for row in trace.get(
                    "openings",
                    [],
                )
            ],
            flush=True,
        )

    self._facade_analysis_front_v12 = (
        results
    )

    self.selection_status.setText(
        "Facade Analysis: existing visible Floor Areas are used as control; no floor generation is performed."
    )

    print(
        "PLAN3D FACADE V12 COMPLETE | floors=",
        len(
            results
        ),
        flush=True,
    )

    return results



# ============================================================
# PLAN3D_FACADE_VISIBLE_FLOOR_TRUE_OUTER_V13
#
# VERIFIED against current Plan3D sources:
# - floor_area_runtime._add_overlay stores real floor polygons in
#   viewport._floor_area_overlay_items as QGraphicsPathItem.
# - floor_area_runtime._path_from_polygon writes polygon X/Y directly.
# - CadGraphicsView current Plan3D code maps CAD point as QPointF(x, y).
#
# Therefore previous V9 Y-negation was wrong for this project.
#
# Rule:
#   visible floor boundary = INNER face reference
#   nearest parallel prepared-Wall face across wall thickness = candidate OUTER
#   floor must exist on INNER side and must NOT exist beyond candidate OUTER
#   => internal partition pairs are rejected
# ============================================================


def _plan3d_scene_to_view_xy_v1(viewport, x, y):
    from PySide6.QtCore import QPointF

    point = QPointF(
        float(x),
        float(y),
    )

    try:
        mapped = viewport.mapFromScene(
            point
        )
        return (
            float(mapped.x()),
            float(mapped.y()),
        )
    except Exception:
        return (
            float(x),
            float(y),
        )


def _plan3d_facade_v13_visible_floor_geometry(
    viewport,
    rect_values,
):
    from floor_area_runtime import (
        _require_shapely,
    )

    api = _require_shapely()

    try:
        from shapely.geometry import Polygon
    except Exception:
        return None

    try:
        rx, ry, rw, rh = [
            float(v)
            for v in rect_values
        ]
    except Exception:
        return None

    region = api["box"](
        min(rx, rx + rw),
        min(ry, ry + rh),
        max(rx, rx + rw),
        max(ry, ry + rh),
    )

    items = list(
        getattr(
            viewport,
            "_floor_area_overlay_items",
            [],
        )
        or []
    )

    polygons = []

    for item in items:
        try:
            path = item.path()
        except Exception:
            continue

        try:
            subpaths = path.toSubpathPolygons()
        except Exception:
            continue

        for qpolygon in subpaths:
            points = []

            try:
                count = qpolygon.count()
            except Exception:
                count = len(qpolygon)

            for index in range(count):
                try:
                    p = qpolygon[index]
                    # Current Floor overlay is already in CAD/scene X,Y.
                    points.append(
                        (
                            float(p.x()),
                            float(p.y()),
                        )
                    )
                except Exception:
                    continue

            if len(points) < 3:
                continue

            try:
                polygon = Polygon(points)

                if not polygon.is_valid:
                    polygon = api["make_valid"](
                        polygon
                    )
            except Exception:
                continue

            for part in api["get_parts"](
                polygon
            ):
                if (
                    getattr(
                        part,
                        "geom_type",
                        "",
                    )
                    != "Polygon"
                    or part.is_empty
                ):
                    continue

                try:
                    clipped = part.intersection(
                        region
                    )
                except Exception:
                    continue

                for clipped_part in api["get_parts"](
                    clipped
                ):
                    if (
                        getattr(
                            clipped_part,
                            "geom_type",
                            "",
                        )
                        != "Polygon"
                        or clipped_part.is_empty
                    ):
                        continue

                    if float(
                        clipped_part.area
                    ) <= 1.0e-9:
                        continue

                    polygons.append(
                        clipped_part
                    )

    if not polygons:
        print(
            "PLAN3D FACADE V13 FLOOR | visible_items=",
            len(items),
            "| clipped_polygons=0",
            flush=True,
        )
        return None

    try:
        merged = api["unary_union"](
            polygons
        )
    except Exception:
        merged = polygons[0]

    print(
        "PLAN3D FACADE V13 FLOOR | visible_items=",
        len(items),
        "| clipped_polygons=",
        len(polygons),
        "| bounds=",
        tuple(
            round(float(v), 3)
            for v in merged.bounds
        ),
        flush=True,
    )

    return merged


def _plan3d_facade_v13_outer_paths(
    wall_paths,
    floor_geometry,
    source_to_mm,
):
    import math

    from floor_area_runtime import (
        _require_shapely,
    )

    api = _require_shapely()

    try:
        from shapely.geometry import LineString, Point
    except Exception:
        return [], [], []

    segments = (
        _plan3d_facade_v2_paths_to_segments(
            wall_paths
        )
    )

    mm_to_source = (
        1.0
        / max(
            float(source_to_mm),
            1.0e-12,
        )
    )

    boundary_tol = (
        12.0
        * mm_to_source
    )

    min_wall = (
        40.0
        * mm_to_source
    )

    max_wall = (
        600.0
        * mm_to_source
    )

    sample_offset = (
        80.0
        * mm_to_source
    )

    try:
        boundary = (
            floor_geometry.boundary
        )
    except Exception:
        return [], [], []

    records = []

    for index, row in enumerate(
        segments
    ):
        a = (
            float(row["a"][0]),
            float(row["a"][1]),
        )

        b = (
            float(row["b"][0]),
            float(row["b"][1]),
        )

        dx = (
            b[0]
            - a[0]
        )

        dy = (
            b[1]
            - a[1]
        )

        length = math.hypot(
            dx,
            dy,
        )

        if length <= 1.0e-9:
            continue

        try:
            line = LineString(
                [a, b]
            )

            midpoint = line.interpolate(
                0.5,
                normalized=True,
            )

            boundary_distance = float(
                midpoint.distance(
                    boundary
                )
            )

            boundary_overlap = float(
                line.intersection(
                    boundary.buffer(
                        boundary_tol
                    )
                ).length
            )
        except Exception:
            continue

        records.append(
            {
                "index":
                    int(index),
                "a":
                    a,
                "b":
                    b,
                "dx":
                    dx,
                "dy":
                    dy,
                "length":
                    length,
                "ux":
                    dx / length,
                "uy":
                    dy / length,
                "mx":
                    (a[0] + b[0]) * 0.5,
                "my":
                    (a[1] + b[1]) * 0.5,
                "boundary_distance":
                    boundary_distance,
                "boundary_overlap":
                    boundary_overlap,
            }
        )

    # A prepared Wall face that follows the visible floor perimeter
    # is the INNER face reference.
    inner_records = [
        row
        for row in records
        if (
            row[
                "boundary_distance"
            ]
            <= boundary_tol
            and row[
                "boundary_overlap"
            ]
            >= row[
                "length"
            ]
            * 0.25
        )
    ]

    outer_indices = set()
    pairs = []

    for inner in inner_records:
        candidates = []

        iu = (
            inner["ux"],
            inner["uy"],
        )

        inormal = (
            -iu[1],
            iu[0],
        )

        inner_t0 = (
            inner["a"][0] * iu[0]
            + inner["a"][1] * iu[1]
        )

        inner_t1 = (
            inner["b"][0] * iu[0]
            + inner["b"][1] * iu[1]
        )

        inner_min = min(
            inner_t0,
            inner_t1,
        )

        inner_max = max(
            inner_t0,
            inner_t1,
        )

        for candidate in records:
            if (
                candidate["index"]
                == inner["index"]
            ):
                continue

            parallel = abs(
                inner["ux"]
                * candidate["ux"]
                + inner["uy"]
                * candidate["uy"]
            )

            if parallel < 0.995:
                continue

            cmx = candidate["mx"]
            cmy = candidate["my"]

            signed_sep = (
                (
                    cmx
                    - inner["mx"]
                )
                * inormal[0]
                + (
                    cmy
                    - inner["my"]
                )
                * inormal[1]
            )

            separation = abs(
                signed_sep
            )

            if not (
                min_wall
                <= separation
                <= max_wall
            ):
                continue

            candidate_t0 = (
                candidate["a"][0]
                * iu[0]
                + candidate["a"][1]
                * iu[1]
            )

            candidate_t1 = (
                candidate["b"][0]
                * iu[0]
                + candidate["b"][1]
                * iu[1]
            )

            candidate_min = min(
                candidate_t0,
                candidate_t1,
            )

            candidate_max = max(
                candidate_t0,
                candidate_t1,
            )

            overlap = max(
                0.0,
                min(
                    inner_max,
                    candidate_max,
                )
                - max(
                    inner_min,
                    candidate_min,
                ),
            )

            if overlap < min(
                inner["length"],
                candidate["length"],
            ) * 0.30:
                continue

            # Unit direction from INNER face toward candidate.
            direction_sign = (
                1.0
                if signed_sep >= 0.0
                else -1.0
            )

            nx = (
                inormal[0]
                * direction_sign
            )

            ny = (
                inormal[1]
                * direction_sign
            )

            # Floor must exist on the opposite side of INNER.
            inside_probe = Point(
                inner["mx"]
                - nx * sample_offset,
                inner["my"]
                - ny * sample_offset,
            )

            # Floor must NOT exist beyond the candidate face.
            outside_probe = Point(
                candidate["mx"]
                + nx * sample_offset,
                candidate["my"]
                + ny * sample_offset,
            )

            try:
                inner_side_has_floor = bool(
                    floor_geometry.buffer(
                        boundary_tol
                    ).covers(
                        inside_probe
                    )
                )

                outside_has_floor = bool(
                    floor_geometry.buffer(
                        boundary_tol
                    ).covers(
                        outside_probe
                    )
                )
            except Exception:
                continue

            if not inner_side_has_floor:
                continue

            if outside_has_floor:
                # Internal partition: floor exists on both sides.
                continue

            candidates.append(
                (
                    separation,
                    -overlap,
                    candidate["index"],
                    candidate,
                )
            )

        if not candidates:
            continue

        candidates.sort(
            key=lambda item:
                (
                    item[0],
                    item[1],
                    item[2],
                )
        )

        separation, _rank, candidate_index, outer = (
            candidates[0]
        )

        outer_indices.add(
            candidate_index
        )

        pairs.append(
            {
                "inner":
                    inner,
                "outer":
                    outer,
                "separation_mm":
                    float(
                        separation
                        * source_to_mm
                    ),
            }
        )

    outer_paths = []

    for row in records:
        if row["index"] not in outer_indices:
            continue

        outer_paths.append(
            [
                [
                    float(row["a"][0]),
                    float(row["a"][1]),
                ],
                [
                    float(row["b"][0]),
                    float(row["b"][1]),
                ],
            ]
        )

    return (
        outer_paths,
        inner_records,
        pairs,
    )


def _plan3d_run_facade_visible_floor_true_outer_v13(self):
    from floor_area_runtime import (
        _export_prepared_wall_paths,
    )

    from plan3d_canonical_export import (
        _cad_unit_info,
    )

    page = self.parentWidget()

    viewport = (
        getattr(
            page,
            "viewport",
            None,
        )
        if page is not None
        else None
    )

    if viewport is None:
        raise RuntimeError(
            "Facade Analysis: viewport unavailable."
        )

    _plan3d_clear_facade_bottom_left_preview_v1(
        viewport
    )

    values = self.values()

    assignments = dict(
        (
            values.get(
                "assignments",
                {},
            )
            or {}
        ).get(
            "floor_plans",
            {},
        )
        or {}
    )

    floor_settings = dict(
        values.get(
            "floor_settings",
            {},
        )
        or {}
    )

    pivot_map = dict(
        getattr(
            self,
            "_floor_pivots",
            {},
        )
        or {}
    )

    if not assignments:
        raise RuntimeError(
            "Facade Analysis: no Floor Plan assignments."
        )

    # Existing visible Floor Areas are mandatory control data.
    visible_items = list(
        getattr(
            viewport,
            "_floor_area_overlay_items",
            [],
        )
        or []
    )

    if not visible_items:
        self.selection_status.setText(
            "Facade Analysis: first use Show Floor Areas."
        )

        print(
            "PLAN3D FACADE V13 | result=NO_VISIBLE_FLOOR_AREAS",
            flush=True,
        )

        return {}

    units_info = _cad_unit_info(
        viewport
    )

    source_to_mm = (
        float(
            units_info.get(
                "to_cm",
                1.0,
            )
            or 1.0
        )
        * 10.0
    )

    results = {}

    for floor_name, rect_values in assignments.items():
        floor_name = str(
            floor_name
        )

        floor_geometry = (
            _plan3d_facade_v13_visible_floor_geometry(
                viewport,
                rect_values,
            )
        )

        if floor_geometry is None:
            print(
                "PLAN3D FRONT FACADE V13 |",
                floor_name,
                "| result=NO_FLOOR_GEOMETRY_IN_RECT",
                flush=True,
            )
            continue

        settings = dict(
            floor_settings.get(
                floor_name,
                {},
            )
            or {}
        )

        pivot = dict(
            pivot_map.get(
                floor_name,
                {},
            )
            or {}
        )

        (
            wall_paths,
            _wall_topology,
            _export_floor,
        ) = _export_prepared_wall_paths(
            viewport,
            floor_name,
            rect_values,
            pivot,
            settings,
            units_info,
        )

        opening_segments_for_filter = (
            _plan3d_facade_v2_opening_segments(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )

        (
            filtered_wall_paths,
            filter_stats,
        ) = (
            _plan3d_facade_v2_filter_wall_components(
                wall_paths,
                opening_segments_for_filter,
                source_to_mm,
            )
        )

        (
            outer_paths,
            inner_records,
            wall_pairs,
        ) = _plan3d_facade_v13_outer_paths(
            filtered_wall_paths,
            floor_geometry,
            source_to_mm,
        )

        selected = (
            _plan3d_find_bottom_left_export_segment_v1(
                viewport,
                outer_paths,
            )
        )

        if selected is None:
            print(
                "PLAN3D FRONT FACADE V13 |",
                floor_name,
                "| result=NO_CONFIRMED_OUTER",
                "| floor_inner_faces=",
                len(
                    inner_records
                ),
                "| outer_pairs=",
                len(
                    wall_pairs
                ),
                flush=True,
            )
            continue

        openings = (
            _plan3d_facade_v5_openings(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )

        trace = (
            _plan3d_facade_v5_trace_front_outer_face(
                viewport,
                outer_paths,
                selected,
                {
                    "wall_band_spacing_scene":
                        None,
                },
                openings,
                source_to_mm,
            )
        )

        _plan3d_draw_front_facade_v4(
            viewport,
            floor_name,
            trace,
            {
                "inner_segments":
                    [],
            },
        )

        results[floor_name] = {
            "facade":
                "Front",
            "floor_control":
                "VISIBLE_FLOOR_AREAS",
            "inner_face_count":
                int(
                    len(
                        inner_records
                    )
                ),
            "outer_pair_count":
                int(
                    len(
                        wall_pairs
                    )
                ),
            "front_segment_count":
                int(
                    len(
                        trace.get(
                            "wall_segments",
                            [],
                        )
                    )
                ),
            "openings_crossed":
                [
                    row[
                        "semantic_type"
                    ]
                    for row in trace.get(
                        "openings",
                        [],
                    )
                ],
            "filter_stats":
                filter_stats,
        }

        print(
            "PLAN3D FRONT FACADE V13 |",
            floor_name,
            "| floor_control=VISIBLE_FLOOR_AREAS",
            "| inner_faces=",
            len(
                inner_records
            ),
            "| outer_pairs=",
            len(
                wall_pairs
            ),
            "| pair_mm=",
            [
                round(
                    float(
                        pair[
                            "separation_mm"
                        ]
                    ),
                    1,
                )
                for pair in wall_pairs
            ],
            "| front_segments=",
            len(
                trace.get(
                    "wall_segments",
                    [],
                )
            ),
            "| openings=",
            [
                row[
                    "semantic_type"
                ]
                for row in trace.get(
                    "openings",
                    [],
                )
            ],
            flush=True,
        )

    self._facade_analysis_front_v13 = (
        results
    )

    self.selection_status.setText(
        "Facade Analysis: visible floor boundary -> inner face -> verified outside parallel Wall face."
    )

    print(
        "PLAN3D FACADE V13 COMPLETE | floors=",
        len(
            results
        ),
        flush=True,
    )

    return results



# ============================================================
# PLAN3D_FACADE_FORCE_VISIBLE_RED_OUTER_V14
#
# Purpose:
# Facade Analysis MUST always show the resolved FRONT outer wall
# segments in RED when visible Floor Areas exist.
#
# This version bypasses the old V13 pair-selection bottleneck.
# It directly compares:
#   visible floor exterior boundary
#   vs export-prepared Wall segments
#
# Candidate OUTER segment requirements:
# - horizontal
# - overlaps the front floor boundary in X
# - lies OUTSIDE the floor polygon
# - distance to floor boundary is wall-thickness range
#
# The accepted segments are drawn directly in RED.
# ============================================================


def _plan3d_facade_v14_floor_front_edges(viewport, floor_geometry):
    rows = []

    polygons = []

    geom_type = getattr(
        floor_geometry,
        "geom_type",
        "",
    )

    if geom_type == "Polygon":
        polygons = [floor_geometry]
    elif geom_type == "MultiPolygon":
        polygons = list(
            floor_geometry.geoms
        )
    else:
        try:
            polygons = [
                geom
                for geom in floor_geometry.geoms
                if getattr(
                    geom,
                    "geom_type",
                    "",
                ) == "Polygon"
            ]
        except Exception:
            polygons = []

    for polygon in polygons:
        try:
            coords = list(
                polygon.exterior.coords
            )
        except Exception:
            continue

        for index in range(
            len(coords) - 1
        ):
            a = (
                float(coords[index][0]),
                float(coords[index][1]),
            )
            b = (
                float(coords[index + 1][0]),
                float(coords[index + 1][1]),
            )

            avx, avy = (
                _plan3d_scene_to_view_xy_v1(
                    viewport,
                    a[0],
                    a[1],
                )
            )

            bvx, bvy = (
                _plan3d_scene_to_view_xy_v1(
                    viewport,
                    b[0],
                    b[1],
                )
            )

            dx = bvx - avx
            dy = bvy - avy

            if abs(dx) <= 1.0e-9:
                continue

            if abs(dy) > max(
                2.0,
                abs(dx) * 0.04,
            ):
                continue

            rows.append(
                {
                    "a": a,
                    "b": b,
                    "view_y":
                        float(
                            (avy + bvy) * 0.5
                        ),
                    "view_x0":
                        float(
                            min(avx, bvx)
                        ),
                    "view_x1":
                        float(
                            max(avx, bvx)
                        ),
                }
            )

    if not rows:
        return []

    # FRONT = visually lowest horizontal floor boundary band.
    bottom_y = max(
        row["view_y"]
        for row in rows
    )

    span = max(
        max(
            row["view_y"]
            for row in rows
        )
        - min(
            row["view_y"]
            for row in rows
        ),
        1.0,
    )

    band_tolerance = max(
        6.0,
        span * 0.02,
    )

    return [
        row
        for row in rows
        if (
            bottom_y - row["view_y"]
        ) <= band_tolerance
    ]


def _plan3d_facade_v14_direct_outer_paths(
    viewport,
    wall_paths,
    floor_geometry,
    source_to_mm,
):
    from floor_area_runtime import (
        _require_shapely,
    )

    api = _require_shapely()

    try:
        from shapely.geometry import LineString, Point
    except Exception:
        return [], []

    front_edges = (
        _plan3d_facade_v14_floor_front_edges(
            viewport,
            floor_geometry,
        )
    )

    if not front_edges:
        return [], []

    cad_to_mm = max(
        float(source_to_mm),
        1.0e-12,
    )

    min_sep = (
        20.0
        / cad_to_mm
    )

    max_sep = (
        800.0
        / cad_to_mm
    )

    outside_probe = (
        15.0
        / cad_to_mm
    )

    try:
        floor_buffer = (
            floor_geometry.buffer(
                outside_probe
            )
        )
    except Exception:
        floor_buffer = floor_geometry

    segments = (
        _plan3d_facade_v2_paths_to_segments(
            wall_paths
        )
    )

    accepted = []
    diagnostics = []

    for edge_index, edge in enumerate(
        front_edges
    ):
        candidates = []

        edge_x0 = edge["view_x0"]
        edge_x1 = edge["view_x1"]
        edge_len = max(
            edge_x1 - edge_x0,
            1.0e-9,
        )

        edge_mid_x = (
            (edge["a"][0] + edge["b"][0])
            * 0.5
        )
        edge_mid_y = (
            (edge["a"][1] + edge["b"][1])
            * 0.5
        )

        for seg_index, row in enumerate(
            segments
        ):
            a = tuple(row["a"])
            b = tuple(row["b"])

            avx, avy = (
                _plan3d_scene_to_view_xy_v1(
                    viewport,
                    a[0],
                    a[1],
                )
            )

            bvx, bvy = (
                _plan3d_scene_to_view_xy_v1(
                    viewport,
                    b[0],
                    b[1],
                )
            )

            dx = bvx - avx
            dy = bvy - avy

            if abs(dx) <= 1.0e-9:
                continue

            if abs(dy) > max(
                2.0,
                abs(dx) * 0.04,
            ):
                continue

            seg_x0 = min(avx, bvx)
            seg_x1 = max(avx, bvx)
            seg_len = max(
                seg_x1 - seg_x0,
                1.0e-9,
            )

            overlap = max(
                0.0,
                min(
                    edge_x1,
                    seg_x1,
                )
                - max(
                    edge_x0,
                    seg_x0,
                ),
            )

            if overlap < min(
                edge_len,
                seg_len,
            ) * 0.20:
                continue

            seg_mid_x = (
                (a[0] + b[0])
                * 0.5
            )
            seg_mid_y = (
                (a[1] + b[1])
                * 0.5
            )

            try:
                line = LineString(
                    [a, b]
                )

                distance = float(
                    line.distance(
                        floor_geometry.boundary
                    )
                )
            except Exception:
                continue

            if not (
                min_sep
                <= distance
                <= max_sep
            ):
                continue

            try:
                midpoint_inside_floor = bool(
                    floor_buffer.covers(
                        Point(
                            seg_mid_x,
                            seg_mid_y,
                        )
                    )
                )
            except Exception:
                midpoint_inside_floor = False

            # Candidate OUTER face must be outside the visible floor.
            if midpoint_inside_floor:
                continue

            # FRONT outside must be visually below the floor edge.
            _smvx, smvy = (
                _plan3d_scene_to_view_xy_v1(
                    viewport,
                    seg_mid_x,
                    seg_mid_y,
                )
            )

            if smvy <= edge["view_y"]:
                continue

            candidates.append(
                (
                    distance,
                    -overlap,
                    seg_index,
                    [a, b],
                )
            )

        if not candidates:
            diagnostics.append(
                {
                    "edge":
                        edge_index,
                    "candidates":
                        0,
                }
            )
            continue

        candidates.sort(
            key=lambda item:
                (
                    item[0],
                    item[1],
                    item[2],
                )
        )

        best_distance = candidates[0][0]

        # Keep all collinear pieces at the same outer-wall offset.
        distance_tolerance = max(
            5.0 / cad_to_mm,
            best_distance * 0.12,
        )

        chosen = [
            item
            for item in candidates
            if abs(
                item[0]
                - best_distance
            ) <= distance_tolerance
        ]

        for _distance, _rank, _seg_index, path in chosen:
            accepted.append(
                path
            )

        diagnostics.append(
            {
                "edge":
                    edge_index,
                "candidates":
                    len(candidates),
                "selected":
                    len(chosen),
                "distance_mm":
                    float(
                        best_distance
                        * cad_to_mm
                    ),
            }
        )

    # Dedupe paths.
    deduped = []
    seen = set()

    for path in accepted:
        a = path[0]
        b = path[1]

        key1 = (
            round(float(a[0]), 5),
            round(float(a[1]), 5),
            round(float(b[0]), 5),
            round(float(b[1]), 5),
        )

        key2 = (
            key1[2],
            key1[3],
            key1[0],
            key1[1],
        )

        key = min(
            key1,
            key2,
        )

        if key in seen:
            continue

        seen.add(key)
        deduped.append(path)

    return (
        deduped,
        diagnostics,
    )


def _plan3d_facade_v14_draw_red(
    viewport,
    floor_name,
    paths,
):
    from PySide6.QtGui import (
        QColor,
        QPainterPath,
        QPen,
    )

    from PySide6.QtWidgets import (
        QGraphicsPathItem,
    )

    scene = viewport.scene()

    if scene is None:
        return 0

    items = list(
        getattr(
            viewport,
            "_plan3d_facade_bottom_left_items_v1",
            [],
        )
        or []
    )

    pen = QPen(
        QColor(
            "#FF0000"
        )
    )

    pen.setCosmetic(True)
    pen.setWidthF(4.0)

    count = 0

    for path_points in paths:
        if len(path_points) < 2:
            continue

        painter_path = QPainterPath()

        first = path_points[0]

        painter_path.moveTo(
            float(first[0]),
            float(first[1]),
        )

        for point in path_points[1:]:
            painter_path.lineTo(
                float(point[0]),
                float(point[1]),
            )

        item = QGraphicsPathItem(
            painter_path
        )

        item.setPen(pen)
        item.setZValue(5000000.0)

        scene.addItem(item)
        items.append(item)
        count += 1

    viewport._plan3d_facade_bottom_left_items_v1 = (
        items
    )

    try:
        viewport.viewport().update()
    except Exception:
        try:
            viewport.update()
        except Exception:
            pass

    return count


def _plan3d_run_facade_force_visible_red_outer_v14(self):
    from floor_area_runtime import (
        _export_prepared_wall_paths,
    )

    from plan3d_canonical_export import (
        _cad_unit_info,
    )

    page = self.parentWidget()

    viewport = (
        getattr(
            page,
            "viewport",
            None,
        )
        if page is not None
        else None
    )

    if viewport is None:
        raise RuntimeError(
            "Facade Analysis: viewport unavailable."
        )

    _plan3d_clear_facade_bottom_left_preview_v1(
        viewport
    )

    values = self.values()

    assignments = dict(
        (
            values.get(
                "assignments",
                {},
            )
            or {}
        ).get(
            "floor_plans",
            {},
        )
        or {}
    )

    floor_settings = dict(
        values.get(
            "floor_settings",
            {},
        )
        or {}
    )

    pivot_map = dict(
        getattr(
            self,
            "_floor_pivots",
            {},
        )
        or {}
    )

    visible_floor_items = list(
        getattr(
            viewport,
            "_floor_area_overlay_items",
            [],
        )
        or []
    )

    if not visible_floor_items:
        self.selection_status.setText(
            "Facade Analysis: Show Floor Areas first."
        )

        print(
            "PLAN3D FACADE V14 | NO_VISIBLE_FLOOR_AREAS",
            flush=True,
        )
        return {}

    units_info = _cad_unit_info(
        viewport
    )

    source_to_mm = (
        float(
            units_info.get(
                "to_cm",
                1.0,
            )
            or 1.0
        )
        * 10.0
    )

    results = {}

    total_red = 0

    for floor_name, rect_values in assignments.items():
        floor_name = str(
            floor_name
        )

        floor_geometry = (
            _plan3d_facade_v13_visible_floor_geometry(
                viewport,
                rect_values,
            )
        )

        if floor_geometry is None:
            print(
                "PLAN3D FACADE V14 |",
                floor_name,
                "| floor_geometry=NONE",
                flush=True,
            )
            continue

        settings = dict(
            floor_settings.get(
                floor_name,
                {},
            )
            or {}
        )

        pivot = dict(
            pivot_map.get(
                floor_name,
                {},
            )
            or {}
        )

        (
            wall_paths,
            _wall_topology,
            _export_floor,
        ) = _export_prepared_wall_paths(
            viewport,
            floor_name,
            rect_values,
            pivot,
            settings,
            units_info,
        )

        (
            red_paths,
            diagnostics,
        ) = _plan3d_facade_v14_direct_outer_paths(
            viewport,
            wall_paths,
            floor_geometry,
            source_to_mm,
        )

        drawn = _plan3d_facade_v14_draw_red(
            viewport,
            floor_name,
            red_paths,
        )

        total_red += drawn

        results[floor_name] = {
            "red_outer_paths":
                int(
                    len(red_paths)
                ),
            "drawn":
                int(drawn),
            "diagnostics":
                diagnostics,
        }

        print(
            "PLAN3D FRONT FACADE V14 |",
            floor_name,
            "| red_outer_paths=",
            len(red_paths),
            "| drawn=",
            drawn,
            "| diagnostics=",
            diagnostics,
            flush=True,
        )

    self._facade_analysis_front_v14 = results

    self.selection_status.setText(
        f"Facade Analysis: {total_red} red outer-wall segment(s) drawn."
    )

    print(
        "PLAN3D FACADE V14 COMPLETE | red_drawn=",
        total_red,
        flush=True,
    )

    return results



# ============================================================
# PLAN3D_FACADE_WALL_PRIMARY_FLOOR_VALIDATE_V15
#
# AUTHORITATIVE RULE:
#   Wall is the primary geometry.
#   Floor is ONLY a validation/reference geometry.
#
# Pipeline:
#   1) use export-prepared Wall segments only
#   2) find parallel overlapping Wall pairs
#   3) use visible Floor Areas only to decide which face is INNER
#   4) opposite face becomes OUTER
#   5) facade selection/tracing uses OUTER Wall only
#
# Floor geometry is NEVER used as:
#   - facade path
#   - wall replacement
#   - start segment source
#   - exported facade geometry
# ============================================================


def _plan3d_facade_v15_wall_pairs(
    wall_paths,
    source_to_mm,
):
    import math

    segments = (
        _plan3d_facade_v2_paths_to_segments(
            wall_paths
        )
    )

    records = []

    for index, row in enumerate(
        segments
    ):
        a = (
            float(row["a"][0]),
            float(row["a"][1]),
        )
        b = (
            float(row["b"][0]),
            float(row["b"][1]),
        )

        dx = b[0] - a[0]
        dy = b[1] - a[1]

        length = math.hypot(
            dx,
            dy,
        )

        if length <= 1.0e-9:
            continue

        records.append(
            {
                "index": int(index),
                "a": a,
                "b": b,
                "dx": dx,
                "dy": dy,
                "length": length,
                "ux": dx / length,
                "uy": dy / length,
                "mx": (a[0] + b[0]) * 0.5,
                "my": (a[1] + b[1]) * 0.5,
            }
        )

    min_sep = (
        40.0
        / max(
            float(source_to_mm),
            1.0e-12,
        )
    )

    max_sep = (
        600.0
        / max(
            float(source_to_mm),
            1.0e-12,
        )
    )

    pairs = []

    for i, first in enumerate(
        records
    ):
        for second in records[
            i + 1:
        ]:
            parallel = abs(
                first["ux"] * second["ux"]
                + first["uy"] * second["uy"]
            )

            if parallel < 0.995:
                continue

            # Normal of first segment.
            nx = -first["uy"]
            ny = first["ux"]

            signed_sep = (
                (
                    second["mx"]
                    - first["mx"]
                )
                * nx
                + (
                    second["my"]
                    - first["my"]
                )
                * ny
            )

            separation = abs(
                signed_sep
            )

            if not (
                min_sep
                <= separation
                <= max_sep
            ):
                continue

            first_t0 = (
                first["a"][0] * first["ux"]
                + first["a"][1] * first["uy"]
            )
            first_t1 = (
                first["b"][0] * first["ux"]
                + first["b"][1] * first["uy"]
            )

            second_t0 = (
                second["a"][0] * first["ux"]
                + second["a"][1] * first["uy"]
            )
            second_t1 = (
                second["b"][0] * first["ux"]
                + second["b"][1] * first["uy"]
            )

            overlap = max(
                0.0,
                min(
                    max(first_t0, first_t1),
                    max(second_t0, second_t1),
                )
                - max(
                    min(first_t0, first_t1),
                    min(second_t0, second_t1),
                ),
            )

            if overlap < min(
                first["length"],
                second["length"],
            ) * 0.30:
                continue

            pairs.append(
                {
                    "first": first,
                    "second": second,
                    "separation": float(
                        separation
                    ),
                    "separation_mm": float(
                        separation
                        * source_to_mm
                    ),
                    "overlap": float(
                        overlap
                    ),
                }
            )

    return pairs


def _plan3d_facade_v15_classify_pair_with_floor(
    pair,
    floor_geometry,
    source_to_mm,
):
    from shapely.geometry import Point

    first = pair["first"]
    second = pair["second"]

    dx = first["ux"]
    dy = first["uy"]

    nx = -dy
    ny = dx

    midpoint_dx = (
        second["mx"]
        - first["mx"]
    )
    midpoint_dy = (
        second["my"]
        - first["my"]
    )

    sign = (
        1.0
        if (
            midpoint_dx * nx
            + midpoint_dy * ny
        ) >= 0.0
        else -1.0
    )

    nx *= sign
    ny *= sign

    # Probe just outside each wall face.
    # We are not using floor as geometry; only asking:
    # "which side contains interior floor?"
    probe_cm = 5.0

    probe = (
        probe_cm
        * 10.0
        / max(
            float(source_to_mm),
            1.0e-12,
        )
    )

    try:
        first_inside_probe = Point(
            first["mx"] - nx * probe,
            first["my"] - ny * probe,
        )

        second_inside_probe = Point(
            second["mx"] + nx * probe,
            second["my"] + ny * probe,
        )

        first_has_floor = bool(
            floor_geometry.covers(
                first_inside_probe
            )
        )

        second_has_floor = bool(
            floor_geometry.covers(
                second_inside_probe
            )
        )
    except Exception:
        return None

    # Exactly one face must point toward the floor/interior.
    if (
        first_has_floor
        and not second_has_floor
    ):
        return {
            "inner": first,
            "outer": second,
        }

    if (
        second_has_floor
        and not first_has_floor
    ):
        return {
            "inner": second,
            "outer": first,
        }

    return None


def _plan3d_facade_v15_outer_paths(
    wall_paths,
    floor_geometry,
    source_to_mm,
):
    pairs = (
        _plan3d_facade_v15_wall_pairs(
            wall_paths,
            source_to_mm,
        )
    )

    outer_records = {}
    classified_pairs = []

    for pair in pairs:
        classification = (
            _plan3d_facade_v15_classify_pair_with_floor(
                pair,
                floor_geometry,
                source_to_mm,
            )
        )

        if classification is None:
            continue

        outer = classification[
            "outer"
        ]

        outer_records[
            outer["index"]
        ] = outer

        classified_pairs.append(
            {
                "inner":
                    classification[
                        "inner"
                    ],
                "outer":
                    outer,
                "separation_mm":
                    pair[
                        "separation_mm"
                    ],
                "overlap":
                    pair[
                        "overlap"
                    ],
            }
        )

    outer_paths = [
        [
            [
                float(row["a"][0]),
                float(row["a"][1]),
            ],
            [
                float(row["b"][0]),
                float(row["b"][1]),
            ],
        ]
        for row in outer_records.values()
    ]

    return (
        outer_paths,
        classified_pairs,
        pairs,
    )


def _plan3d_run_facade_wall_primary_floor_validate_v15(self):
    from floor_area_runtime import (
        _export_prepared_wall_paths,
    )

    from plan3d_canonical_export import (
        _cad_unit_info,
    )

    page = self.parentWidget()

    viewport = (
        getattr(
            page,
            "viewport",
            None,
        )
        if page is not None
        else None
    )

    if viewport is None:
        raise RuntimeError(
            "Facade Analysis: viewport unavailable."
        )

    _plan3d_clear_facade_bottom_left_preview_v1(
        viewport
    )

    values = self.values()

    assignments = dict(
        (
            values.get(
                "assignments",
                {},
            )
            or {}
        ).get(
            "floor_plans",
            {},
        )
        or {}
    )

    floor_settings = dict(
        values.get(
            "floor_settings",
            {},
        )
        or {}
    )

    pivot_map = dict(
        getattr(
            self,
            "_floor_pivots",
            {},
        )
        or {}
    )

    if not assignments:
        raise RuntimeError(
            "Facade Analysis: no Floor Plan assignments."
        )

    visible_floor_items = list(
        getattr(
            viewport,
            "_floor_area_overlay_items",
            [],
        )
        or []
    )

    if not visible_floor_items:
        self.selection_status.setText(
            "Facade Analysis: Show Floor Areas first."
        )

        print(
            "PLAN3D FACADE V15 | result=NO_VISIBLE_FLOOR_AREAS",
            flush=True,
        )

        return {}

    units_info = _cad_unit_info(
        viewport
    )

    source_to_mm = (
        float(
            units_info.get(
                "to_cm",
                1.0,
            )
            or 1.0
        )
        * 10.0
    )

    results = {}

    for floor_name, rect_values in assignments.items():
        floor_name = str(
            floor_name
        )

        # Floor is read ONLY as validation reference.
        floor_geometry = (
            _plan3d_facade_v13_visible_floor_geometry(
                viewport,
                rect_values,
            )
        )

        if floor_geometry is None:
            print(
                "PLAN3D FRONT FACADE V15 |",
                floor_name,
                "| result=NO_FLOOR_REFERENCE",
                flush=True,
            )
            continue

        settings = dict(
            floor_settings.get(
                floor_name,
                {},
            )
            or {}
        )

        pivot = dict(
            pivot_map.get(
                floor_name,
                {},
            )
            or {}
        )

        (
            wall_paths,
            _wall_topology,
            _export_floor,
        ) = _export_prepared_wall_paths(
            viewport,
            floor_name,
            rect_values,
            pivot,
            settings,
            units_info,
        )

        opening_segments_for_filter = (
            _plan3d_facade_v2_opening_segments(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )

        (
            filtered_wall_paths,
            filter_stats,
        ) = (
            _plan3d_facade_v2_filter_wall_components(
                wall_paths,
                opening_segments_for_filter,
                source_to_mm,
            )
        )

        (
            outer_paths,
            classified_pairs,
            all_pairs,
        ) = _plan3d_facade_v15_outer_paths(
            filtered_wall_paths,
            floor_geometry,
            source_to_mm,
        )

        selected = (
            _plan3d_find_bottom_left_export_segment_v1(
                viewport,
                outer_paths,
            )
        )

        if selected is None:
            print(
                "PLAN3D FRONT FACADE V15 |",
                floor_name,
                "| result=NO_OUTER_WALL",
                "| wall_pairs=",
                len(all_pairs),
                "| floor_validated_pairs=",
                len(classified_pairs),
                flush=True,
            )
            continue

        openings = (
            _plan3d_facade_v5_openings(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )

        trace = (
            _plan3d_facade_v5_trace_front_outer_face(
                viewport,
                outer_paths,
                selected,
                {
                    "wall_band_spacing_scene":
                        None,
                },
                openings,
                source_to_mm,
            )
        )

        # Draw ONLY Wall-derived facade geometry.
        _plan3d_draw_front_facade_v4(
            viewport,
            floor_name,
            trace,
            {
                "inner_segments":
                    [],
            },
        )

        results[
            floor_name
        ] = {
            "facade":
                "Front",
            "geometry_source":
                "EXPORT_PREPARED_WALL",
            "floor_usage":
                "VALIDATION_ONLY",
            "wall_pair_count":
                int(
                    len(
                        all_pairs
                    )
                ),
            "floor_validated_pair_count":
                int(
                    len(
                        classified_pairs
                    )
                ),
            "outer_wall_segment_count":
                int(
                    len(
                        outer_paths
                    )
                ),
            "front_segment_count":
                int(
                    len(
                        trace.get(
                            "wall_segments",
                            [],
                        )
                    )
                ),
            "openings_crossed":
                [
                    row[
                        "semantic_type"
                    ]
                    for row in trace.get(
                        "openings",
                        [],
                    )
                ],
            "filter_stats":
                filter_stats,
        }

        print(
            "PLAN3D FRONT FACADE V15 |",
            floor_name,
            "| source=EXPORT_PREPARED_WALL",
            "| floor=VALIDATION_ONLY",
            "| wall_pairs=",
            len(
                all_pairs
            ),
            "| validated_pairs=",
            len(
                classified_pairs
            ),
            "| outer_segments=",
            len(
                outer_paths
            ),
            "| front_segments=",
            len(
                trace.get(
                    "wall_segments",
                    [],
                )
            ),
            "| openings=",
            [
                row[
                    "semantic_type"
                ]
                for row in trace.get(
                    "openings",
                    [],
                )
            ],
            flush=True,
        )

    self._facade_analysis_front_v15 = (
        results
    )

    self.selection_status.setText(
        "Facade Analysis: Wall is primary; Floor Areas are validation only."
    )

    print(
        "PLAN3D FACADE V15 COMPLETE | floors=",
        len(
            results
        ),
        flush=True,
    )

    return results



# ============================================================
# PLAN3D_FACADE_WALL_PAIR_MULTI_FLOOR_VALIDATE_V16
#
# Fix for floors where V15 finds no OUTER wall.
#
# Changes:
# 1) DO NOT run the old disconnected/opening component filter before
#    outer-wall classification. That filter can delete a legitimate
#    floor with few/no facade openings.
# 2) Wall is still the only facade geometry source.
# 3) Floor is validation only.
# 4) Each parallel Wall pair is checked with MULTIPLE sample points
#    and MULTIPLE probe distances instead of one midpoint/5cm probe.
# 5) Detached stray geometry naturally fails because no floor exists
#    consistently on either architectural side of its Wall pair.
# ============================================================


def _plan3d_facade_v16_wall_pairs(
    wall_paths,
    source_to_mm,
):
    import math

    segments = _plan3d_facade_v2_paths_to_segments(
        wall_paths
    )

    records = []

    for index, row in enumerate(segments):
        a = (
            float(row["a"][0]),
            float(row["a"][1]),
        )
        b = (
            float(row["b"][0]),
            float(row["b"][1]),
        )

        dx = b[0] - a[0]
        dy = b[1] - a[1]
        length = math.hypot(dx, dy)

        if length <= 1.0e-9:
            continue

        records.append(
            {
                "index": int(index),
                "a": a,
                "b": b,
                "dx": dx,
                "dy": dy,
                "length": length,
                "ux": dx / length,
                "uy": dy / length,
                "mx": (a[0] + b[0]) * 0.5,
                "my": (a[1] + b[1]) * 0.5,
            }
        )

    mm_per_source = max(
        float(source_to_mm),
        1.0e-12,
    )

    min_sep = 20.0 / mm_per_source
    max_sep = 800.0 / mm_per_source

    pairs = []

    for i, first in enumerate(records):
        for second in records[i + 1:]:
            parallel = abs(
                first["ux"] * second["ux"]
                + first["uy"] * second["uy"]
            )

            if parallel < 0.992:
                continue

            nx = -first["uy"]
            ny = first["ux"]

            signed_sep = (
                (second["mx"] - first["mx"]) * nx
                + (second["my"] - first["my"]) * ny
            )

            separation = abs(signed_sep)

            if not (
                min_sep
                <= separation
                <= max_sep
            ):
                continue

            first_t0 = (
                first["a"][0] * first["ux"]
                + first["a"][1] * first["uy"]
            )
            first_t1 = (
                first["b"][0] * first["ux"]
                + first["b"][1] * first["uy"]
            )

            second_t0 = (
                second["a"][0] * first["ux"]
                + second["a"][1] * first["uy"]
            )
            second_t1 = (
                second["b"][0] * first["ux"]
                + second["b"][1] * first["uy"]
            )

            overlap_start = max(
                min(first_t0, first_t1),
                min(second_t0, second_t1),
            )
            overlap_end = min(
                max(first_t0, first_t1),
                max(second_t0, second_t1),
            )
            overlap = max(
                0.0,
                overlap_end - overlap_start,
            )

            if overlap <= 1.0e-9:
                continue

            # Accept shorter split wall segments too.
            if overlap < min(
                first["length"],
                second["length"],
            ) * 0.10:
                continue

            pairs.append(
                {
                    "first": first,
                    "second": second,
                    "signed_sep": float(signed_sep),
                    "separation": float(separation),
                    "separation_mm": float(
                        separation * source_to_mm
                    ),
                    "overlap_start": float(
                        overlap_start
                    ),
                    "overlap_end": float(
                        overlap_end
                    ),
                    "overlap": float(overlap),
                }
            )

    return pairs


def _plan3d_facade_v16_pair_floor_scores(
    pair,
    floor_geometry,
    source_to_mm,
):
    from shapely.geometry import Point

    first = pair["first"]
    second = pair["second"]

    ux = first["ux"]
    uy = first["uy"]

    nx = -uy
    ny = ux

    if pair["signed_sep"] < 0.0:
        nx = -nx
        ny = -ny

    mm_per_source = max(
        float(source_to_mm),
        1.0e-12,
    )

    probe_distances = [
        15.0 / mm_per_source,
        40.0 / mm_per_source,
        80.0 / mm_per_source,
        150.0 / mm_per_source,
    ]

    # Sample across the actual pair overlap, not only at segment midpoint.
    overlap_start = pair["overlap_start"]
    overlap_end = pair["overlap_end"]
    overlap_len = max(
        overlap_end - overlap_start,
        1.0e-9,
    )

    sample_fractions = (
        0.12,
        0.30,
        0.50,
        0.70,
        0.88,
    )

    score_first_side = 0
    score_second_side = 0
    total = 0

    # first outer-side candidate = away from second = -normal
    # second outer-side candidate = away from first  = +normal
    for fraction in sample_fractions:
        t = (
            overlap_start
            + overlap_len * fraction
        )

        # Reconstruct a point on first's center line from its direction.
        # p = a + u * (t - dot(a,u))
        first_a_t = (
            first["a"][0] * ux
            + first["a"][1] * uy
        )

        base_x = (
            first["a"][0]
            + ux * (
                t - first_a_t
            )
        )
        base_y = (
            first["a"][1]
            + uy * (
                t - first_a_t
            )
        )

        # Corresponding point on second face.
        second_x = (
            base_x
            + nx * pair["separation"]
        )
        second_y = (
            base_y
            + ny * pair["separation"]
        )

        for probe in probe_distances:
            total += 1

            first_probe = Point(
                base_x - nx * probe,
                base_y - ny * probe,
            )

            second_probe = Point(
                second_x + nx * probe,
                second_y + ny * probe,
            )

            try:
                if floor_geometry.covers(
                    first_probe
                ):
                    score_first_side += 1
            except Exception:
                pass

            try:
                if floor_geometry.covers(
                    second_probe
                ):
                    score_second_side += 1
            except Exception:
                pass

    return {
        "first_floor_score":
            int(score_first_side),
        "second_floor_score":
            int(score_second_side),
        "total":
            int(total),
    }


def _plan3d_facade_v16_outer_paths(
    wall_paths,
    floor_geometry,
    source_to_mm,
):
    pairs = _plan3d_facade_v16_wall_pairs(
        wall_paths,
        source_to_mm,
    )

    outer_records = {}
    validated = []

    for pair in pairs:
        scores = (
            _plan3d_facade_v16_pair_floor_scores(
                pair,
                floor_geometry,
                source_to_mm,
            )
        )

        first_score = scores[
            "first_floor_score"
        ]
        second_score = scores[
            "second_floor_score"
        ]
        total = max(
            scores["total"],
            1,
        )

        # We need a clear architectural side:
        # floor on one outside side, not on both.
        min_positive = max(
            2,
            int(total * 0.15),
        )

        if (
            first_score >= min_positive
            and second_score <= max(
                1,
                int(first_score * 0.35),
            )
        ):
            # Floor lies beyond first -> first is INNER, second OUTER.
            inner = pair["first"]
            outer = pair["second"]

        elif (
            second_score >= min_positive
            and first_score <= max(
                1,
                int(second_score * 0.35),
            )
        ):
            # Floor lies beyond second -> second is INNER, first OUTER.
            inner = pair["second"]
            outer = pair["first"]

        else:
            continue

        outer_records[
            outer["index"]
        ] = outer

        validated.append(
            {
                "inner": inner,
                "outer": outer,
                "separation_mm":
                    float(
                        pair[
                            "separation_mm"
                        ]
                    ),
                "first_floor_score":
                    int(first_score),
                "second_floor_score":
                    int(second_score),
                "sample_total":
                    int(total),
            }
        )

    outer_paths = [
        [
            [
                float(row["a"][0]),
                float(row["a"][1]),
            ],
            [
                float(row["b"][0]),
                float(row["b"][1]),
            ],
        ]
        for row in outer_records.values()
    ]

    return (
        outer_paths,
        validated,
        pairs,
    )


def _plan3d_run_facade_wall_pair_multi_floor_validate_v16(self):
    from floor_area_runtime import (
        _export_prepared_wall_paths,
    )

    from plan3d_canonical_export import (
        _cad_unit_info,
    )

    page = self.parentWidget()

    viewport = (
        getattr(
            page,
            "viewport",
            None,
        )
        if page is not None
        else None
    )

    if viewport is None:
        raise RuntimeError(
            "Facade Analysis: viewport unavailable."
        )

    _plan3d_clear_facade_bottom_left_preview_v1(
        viewport
    )

    values = self.values()

    assignments = dict(
        (
            values.get(
                "assignments",
                {},
            )
            or {}
        ).get(
            "floor_plans",
            {},
        )
        or {}
    )

    floor_settings = dict(
        values.get(
            "floor_settings",
            {},
        )
        or {}
    )

    pivot_map = dict(
        getattr(
            self,
            "_floor_pivots",
            {},
        )
        or {}
    )

    visible_floor_items = list(
        getattr(
            viewport,
            "_floor_area_overlay_items",
            [],
        )
        or []
    )

    if not visible_floor_items:
        self.selection_status.setText(
            "Facade Analysis: Show Floor Areas first."
        )
        print(
            "PLAN3D FACADE V16 | result=NO_VISIBLE_FLOOR_AREAS",
            flush=True,
        )
        return {}

    units_info = _cad_unit_info(
        viewport
    )

    source_to_mm = (
        float(
            units_info.get(
                "to_cm",
                1.0,
            )
            or 1.0
        )
        * 10.0
    )

    results = {}

    for floor_name, rect_values in assignments.items():
        floor_name = str(
            floor_name
        )

        floor_geometry = (
            _plan3d_facade_v13_visible_floor_geometry(
                viewport,
                rect_values,
            )
        )

        if floor_geometry is None:
            print(
                "PLAN3D FRONT FACADE V16 |",
                floor_name,
                "| result=NO_FLOOR_REFERENCE",
                flush=True,
            )
            continue

        settings = dict(
            floor_settings.get(
                floor_name,
                {},
            )
            or {}
        )

        pivot = dict(
            pivot_map.get(
                floor_name,
                {},
            )
            or {}
        )

        (
            wall_paths,
            _wall_topology,
            _export_floor,
        ) = _export_prepared_wall_paths(
            viewport,
            floor_name,
            rect_values,
            pivot,
            settings,
            units_info,
        )

        # IMPORTANT:
        # Do NOT pre-filter by Door/Window contact here.
        # Wall is primary, Floor validates architectural inside/outside.
        (
            outer_paths,
            validated_pairs,
            all_pairs,
        ) = _plan3d_facade_v16_outer_paths(
            wall_paths,
            floor_geometry,
            source_to_mm,
        )

        selected = (
            _plan3d_find_bottom_left_export_segment_v1(
                viewport,
                outer_paths,
            )
        )

        if selected is None:
            print(
                "PLAN3D FRONT FACADE V16 |",
                floor_name,
                "| result=NO_OUTER_WALL",
                "| wall_pairs=",
                len(all_pairs),
                "| validated_pairs=",
                len(validated_pairs),
                flush=True,
            )
            continue

        openings = (
            _plan3d_facade_v5_openings(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )

        trace = (
            _plan3d_facade_v5_trace_front_outer_face(
                viewport,
                outer_paths,
                selected,
                {
                    "wall_band_spacing_scene":
                        None,
                },
                openings,
                source_to_mm,
            )
        )

        _plan3d_draw_front_facade_v4(
            viewport,
            floor_name,
            trace,
            {
                "inner_segments":
                    [],
            },
        )

        results[
            floor_name
        ] = {
            "facade": "Front",
            "geometry_source":
                "EXPORT_PREPARED_WALL",
            "floor_usage":
                "VALIDATION_ONLY_MULTI_SAMPLE",
            "wall_pair_count":
                int(
                    len(all_pairs)
                ),
            "validated_pair_count":
                int(
                    len(validated_pairs)
                ),
            "outer_segment_count":
                int(
                    len(outer_paths)
                ),
            "front_segment_count":
                int(
                    len(
                        trace.get(
                            "wall_segments",
                            [],
                        )
                    )
                ),
        }

        print(
            "PLAN3D FRONT FACADE V16 |",
            floor_name,
            "| source=EXPORT_PREPARED_WALL",
            "| floor=VALIDATION_ONLY_MULTI_SAMPLE",
            "| wall_pairs=",
            len(all_pairs),
            "| validated_pairs=",
            len(validated_pairs),
            "| outer_segments=",
            len(outer_paths),
            "| front_segments=",
            len(
                trace.get(
                    "wall_segments",
                    [],
                )
            ),
            "| pair_mm=",
            [
                round(
                    float(
                        row[
                            "separation_mm"
                        ]
                    ),
                    1,
                )
                for row in validated_pairs[:20]
            ],
            flush=True,
        )

    self._facade_analysis_front_v16 = (
        results
    )

    self.selection_status.setText(
        "Facade Analysis: Wall primary; Floor validates both sides with multi-sample checks."
    )

    print(
        "PLAN3D FACADE V16 COMPLETE | floors=",
        len(results),
        flush=True,
    )

    return results



# ============================================================
# PLAN3D_FACADE_SIDE_FROM_FRONT_CORNER_V17
#
# Rule requested by user:
# FRONT facade faces visually DOWN.
#
# At a FRONT corner:
#   continuation visually UP   -> RIGHT facade -> GREEN
#   continuation visually DOWN -> LEFT facade  -> YELLOW
#
# Geometry source remains export-prepared Wall.
# Floor remains validation only, exactly as V16.
# ============================================================


def _plan3d_facade_v17_near(a, b, tol):
    return (
        (
            float(a[0]) - float(b[0])
        ) ** 2
        + (
            float(a[1]) - float(b[1])
        ) ** 2
    ) ** 0.5 <= tol


def _plan3d_facade_v17_other_endpoint(row, point, tol):
    a = tuple(row["a"])
    b = tuple(row["b"])

    if _plan3d_facade_v17_near(
        a,
        point,
        tol,
    ):
        return b

    if _plan3d_facade_v17_near(
        b,
        point,
        tol,
    ):
        return a

    return None


def _plan3d_facade_v17_trace_vertical_side(
    viewport,
    outer_paths,
    start_point,
    direction,
    source_to_mm,
):
    segments = (
        _plan3d_facade_v2_paths_to_segments(
            outer_paths
        )
    )

    cad_to_cm = max(
        float(source_to_mm) / 10.0,
        1.0e-12,
    )

    join_tol = (
        5.0 / cad_to_cm
    )

    current = tuple(
        start_point
    )

    used = set()
    run = []

    guard = 0

    while guard < max(
        len(segments) * 3,
        32,
    ):
        guard += 1

        cvx, cvy = (
            _plan3d_scene_to_view_xy_v1(
                viewport,
                current[0],
                current[1],
            )
        )

        candidates = []

        for index, row in enumerate(
            segments
        ):
            if index in used:
                continue

            other = (
                _plan3d_facade_v17_other_endpoint(
                    row,
                    current,
                    join_tol,
                )
            )

            if other is None:
                continue

            ovx, ovy = (
                _plan3d_scene_to_view_xy_v1(
                    viewport,
                    other[0],
                    other[1],
                )
            )

            dx = (
                ovx - cvx
            )
            dy = (
                ovy - cvy
            )

            # Side facade must continue vertically.
            if abs(dy) <= 1.0e-9:
                continue

            if abs(dx) > max(
                2.0,
                abs(dy) * 0.04,
            ):
                continue

            if (
                direction == "UP"
                and dy >= 0.0
            ):
                continue

            if (
                direction == "DOWN"
                and dy <= 0.0
            ):
                continue

            candidates.append(
                (
                    -abs(dy),
                    index,
                    tuple(other),
                    row,
                )
            )

        if not candidates:
            break

        candidates.sort(
            key=lambda item: item[0]
        )

        _rank, index, other, row = (
            candidates[0]
        )

        run.append(
            {
                "a":
                    tuple(row["a"]),
                "b":
                    tuple(row["b"]),
                "segment_index":
                    int(index),
            }
        )

        used.add(index)
        current = tuple(other)

        # Stop at the next real corner:
        # if any unused connected horizontal outer-wall segment exists.
        cvx, cvy = (
            _plan3d_scene_to_view_xy_v1(
                viewport,
                current[0],
                current[1],
            )
        )

        corner_found = False

        for test_index, test_row in enumerate(
            segments
        ):
            if test_index in used:
                continue

            test_other = (
                _plan3d_facade_v17_other_endpoint(
                    test_row,
                    current,
                    join_tol,
                )
            )

            if test_other is None:
                continue

            tvx, tvy = (
                _plan3d_scene_to_view_xy_v1(
                    viewport,
                    test_other[0],
                    test_other[1],
                )
            )

            tdx = tvx - cvx
            tdy = tvy - cvy

            if (
                abs(tdx) > 1.0e-9
                and abs(tdy)
                <= max(
                    2.0,
                    abs(tdx) * 0.04,
                )
            ):
                corner_found = True
                break

        if corner_found:
            break

    return {
        "segments":
            run,
        "start":
            tuple(start_point),
        "end":
            tuple(current),
        "direction":
            direction,
    }


def _plan3d_facade_v17_draw_side(
    viewport,
    floor_name,
    side_name,
    trace,
):
    from PySide6.QtGui import (
        QColor,
        QPainterPath,
        QPen,
    )
    from PySide6.QtWidgets import (
        QGraphicsPathItem,
        QGraphicsSimpleTextItem,
    )

    scene = viewport.scene()

    if scene is None:
        return 0

    items = list(
        getattr(
            viewport,
            "_plan3d_facade_bottom_left_items_v1",
            [],
        )
        or []
    )

    if side_name == "RIGHT":
        color = QColor(
            "#00FF00"
        )
        label = "RIGHT FACADE"
    else:
        color = QColor(
            "#FFFF00"
        )
        label = "LEFT FACADE"

    pen = QPen(
        color
    )
    pen.setCosmetic(
        True
    )
    pen.setWidthF(
        4.0
    )

    count = 0

    for row in trace.get(
        "segments",
        [],
    ):
        path = QPainterPath()

        a = row["a"]
        b = row["b"]

        path.moveTo(
            float(a[0]),
            float(a[1]),
        )
        path.lineTo(
            float(b[0]),
            float(b[1]),
        )

        item = QGraphicsPathItem(
            path
        )
        item.setPen(
            pen
        )
        item.setZValue(
            5000001.0
        )

        scene.addItem(
            item
        )
        items.append(
            item
        )
        count += 1

    if count:
        end = trace.get(
            "end"
        )

        if end is not None:
            text = QGraphicsSimpleTextItem(
                f"{floor_name} | {label}"
            )
            text.setBrush(
                color
            )
            text.setPos(
                float(end[0]),
                float(end[1]),
            )
            text.setZValue(
                5000002.0
            )
            scene.addItem(
                text
            )
            items.append(
                text
            )

    viewport._plan3d_facade_bottom_left_items_v1 = (
        items
    )

    return count


def _plan3d_run_facade_side_from_front_corner_v17(self):
    from floor_area_runtime import (
        _export_prepared_wall_paths,
    )

    from plan3d_canonical_export import (
        _cad_unit_info,
    )

    page = self.parentWidget()

    viewport = (
        getattr(
            page,
            "viewport",
            None,
        )
        if page is not None
        else None
    )

    if viewport is None:
        raise RuntimeError(
            "Facade Analysis: viewport unavailable."
        )

    _plan3d_clear_facade_bottom_left_preview_v1(
        viewport
    )

    values = self.values()

    assignments = dict(
        (
            values.get(
                "assignments",
                {},
            )
            or {}
        ).get(
            "floor_plans",
            {},
        )
        or {}
    )

    floor_settings = dict(
        values.get(
            "floor_settings",
            {},
        )
        or {}
    )

    pivot_map = dict(
        getattr(
            self,
            "_floor_pivots",
            {},
        )
        or {}
    )

    visible_floor_items = list(
        getattr(
            viewport,
            "_floor_area_overlay_items",
            [],
        )
        or []
    )

    if not visible_floor_items:
        self.selection_status.setText(
            "Facade Analysis: Show Floor Areas first."
        )
        print(
            "PLAN3D FACADE V17 | result=NO_VISIBLE_FLOOR_AREAS",
            flush=True,
        )
        return {}

    units_info = _cad_unit_info(
        viewport
    )

    source_to_mm = (
        float(
            units_info.get(
                "to_cm",
                1.0,
            )
            or 1.0
        )
        * 10.0
    )

    results = {}

    for floor_name, rect_values in assignments.items():
        floor_name = str(
            floor_name
        )

        floor_geometry = (
            _plan3d_facade_v13_visible_floor_geometry(
                viewport,
                rect_values,
            )
        )

        if floor_geometry is None:
            print(
                "PLAN3D FRONT FACADE V17 |",
                floor_name,
                "| result=NO_FLOOR_REFERENCE",
                flush=True,
            )
            continue

        settings = dict(
            floor_settings.get(
                floor_name,
                {},
            )
            or {}
        )

        pivot = dict(
            pivot_map.get(
                floor_name,
                {},
            )
            or {}
        )

        (
            wall_paths,
            _wall_topology,
            _export_floor,
        ) = _export_prepared_wall_paths(
            viewport,
            floor_name,
            rect_values,
            pivot,
            settings,
            units_info,
        )

        (
            outer_paths,
            validated_pairs,
            all_pairs,
        ) = _plan3d_facade_v16_outer_paths(
            wall_paths,
            floor_geometry,
            source_to_mm,
        )

        selected = (
            _plan3d_find_bottom_left_export_segment_v1(
                viewport,
                outer_paths,
            )
        )

        if selected is None:
            print(
                "PLAN3D FRONT FACADE V17 |",
                floor_name,
                "| result=NO_OUTER_WALL",
                "| wall_pairs=",
                len(all_pairs),
                "| validated_pairs=",
                len(validated_pairs),
                flush=True,
            )
            continue

        openings = (
            _plan3d_facade_v5_openings(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )

        front = (
            _plan3d_facade_v5_trace_front_outer_face(
                viewport,
                outer_paths,
                selected,
                {
                    "wall_band_spacing_scene":
                        None,
                },
                openings,
                source_to_mm,
            )
        )

        _plan3d_draw_front_facade_v4(
            viewport,
            floor_name,
            front,
            {
                "inner_segments":
                    [],
            },
        )

        start_corner = front.get(
            "start_corner"
        )
        end_corner = front.get(
            "end_corner"
        )

        right_trace = {
            "segments": []
        }
        left_trace = {
            "segments": []
        }

        # Check BOTH FRONT corners.
        # Any UP continuation is RIGHT facade.
        # Any DOWN continuation is LEFT facade.
        corner_candidates = [
            point
            for point in (
                start_corner,
                end_corner,
            )
            if point is not None
        ]

        right_runs = []
        left_runs = []

        for corner in corner_candidates:
            up_trace = (
                _plan3d_facade_v17_trace_vertical_side(
                    viewport,
                    outer_paths,
                    corner,
                    "UP",
                    source_to_mm,
                )
            )

            down_trace = (
                _plan3d_facade_v17_trace_vertical_side(
                    viewport,
                    outer_paths,
                    corner,
                    "DOWN",
                    source_to_mm,
                )
            )

            if up_trace.get(
                "segments"
            ):
                right_runs.append(
                    up_trace
                )

            if down_trace.get(
                "segments"
            ):
                left_runs.append(
                    down_trace
                )

        if right_runs:
            right_trace = max(
                right_runs,
                key=lambda row:
                    len(
                        row.get(
                            "segments",
                            [],
                        )
                    ),
            )

        if left_runs:
            left_trace = max(
                left_runs,
                key=lambda row:
                    len(
                        row.get(
                            "segments",
                            [],
                        )
                    ),
            )

        right_drawn = (
            _plan3d_facade_v17_draw_side(
                viewport,
                floor_name,
                "RIGHT",
                right_trace,
            )
        )

        left_drawn = (
            _plan3d_facade_v17_draw_side(
                viewport,
                floor_name,
                "LEFT",
                left_trace,
            )
        )

        results[
            floor_name
        ] = {
            "front_segments":
                len(
                    front.get(
                        "wall_segments",
                        [],
                    )
                ),
            "right_segments":
                len(
                    right_trace.get(
                        "segments",
                        [],
                    )
                ),
            "left_segments":
                len(
                    left_trace.get(
                        "segments",
                        [],
                    )
                ),
            "right_drawn":
                int(
                    right_drawn
                ),
            "left_drawn":
                int(
                    left_drawn
                ),
        }

        print(
            "PLAN3D FACADE V17 |",
            floor_name,
            "| FRONT=RED",
            "| RIGHT=GREEN(up)=",
            len(
                right_trace.get(
                    "segments",
                    [],
                )
            ),
            "| LEFT=YELLOW(down)=",
            len(
                left_trace.get(
                    "segments",
                    [],
                )
            ),
            flush=True,
        )

    self._facade_analysis_v17 = (
        results
    )

    self.selection_status.setText(
        "Facade Analysis: Front=red, upward continuation=Right/green, downward continuation=Left/yellow."
    )

    print(
        "PLAN3D FACADE V17 COMPLETE | floors=",
        len(results),
        flush=True,
    )

    return results



# ============================================================
# PLAN3D_FACADE_PERIMETER_CONTINUITY_LAYER_INDEPENDENT_V18
#
# AUTHORITATIVE CONTINUITY RULES
#
# 1) Building walk direction:
#       FRONT  : LEFT -> RIGHT
#       RIGHT  : UP
#       REAR   : RIGHT -> LEFT
#       LEFT   : DOWN
#       CLOSE  : back to FRONT
#
# 2) Exterior-wall layer NEVER decides:
#       - stop
#       - turn
#       - continuation
#
#    Layer is not consulted during facade walking.
#
# 3) Every facade direction preserves the FRONT/red continuity rules:
#       - use only validated OUTER export-prepared Wall geometry
#       - continue across opening gaps
#       - do not treat Window / Sliding Door / Exterior Door jambs
#         as facade corners
#       - stop/turn only at a real OUTER-wall geometric corner
#
# 4) Colors:
#       FRONT = RED
#       RIGHT = GREEN
#       LEFT  = YELLOW
#    REAR is traced/stored but not assigned a new display color here.
# ============================================================


def _plan3d_facade_v18_segment_records(
    viewport,
    outer_paths,
):
    rows = []

    for index, row in enumerate(
        _plan3d_facade_v2_paths_to_segments(
            outer_paths
        )
    ):
        a = tuple(
            row["a"]
        )
        b = tuple(
            row["b"]
        )

        avx, avy = _plan3d_scene_to_view_xy_v1(
            viewport,
            a[0],
            a[1],
        )
        bvx, bvy = _plan3d_scene_to_view_xy_v1(
            viewport,
            b[0],
            b[1],
        )

        dx = bvx - avx
        dy = bvy - avy

        if abs(dx) >= abs(dy):
            orientation = "H"
        else:
            orientation = "V"

        rows.append(
            {
                "index": int(index),
                "a": a,
                "b": b,
                "av": (float(avx), float(avy)),
                "bv": (float(bvx), float(bvy)),
                "orientation": orientation,
            }
        )

    return rows


def _plan3d_facade_v18_other_endpoint(
    row,
    point,
    tol,
):
    if _plan3d_facade_v17_near(
        row["a"],
        point,
        tol,
    ):
        return row["b"]

    if _plan3d_facade_v17_near(
        row["b"],
        point,
        tol,
    ):
        return row["a"]

    return None


def _plan3d_facade_v18_forward_score(
    viewport,
    current,
    target,
    direction,
):
    cvx, cvy = _plan3d_scene_to_view_xy_v1(
        viewport,
        current[0],
        current[1],
    )

    tvx, tvy = _plan3d_scene_to_view_xy_v1(
        viewport,
        target[0],
        target[1],
    )

    dx = tvx - cvx
    dy = tvy - cvy

    if direction == "RIGHT":
        primary = dx
        lateral = abs(dy)
    elif direction == "LEFT":
        primary = -dx
        lateral = abs(dy)
    elif direction == "UP":
        primary = -dy
        lateral = abs(dx)
    else:  # DOWN
        primary = dy
        lateral = abs(dx)

    return (
        float(primary),
        float(lateral),
    )


def _plan3d_facade_v18_trace_direction(
    viewport,
    outer_paths,
    start_point,
    direction,
    source_to_mm,
    used_global=None,
):
    rows = _plan3d_facade_v18_segment_records(
        viewport,
        outer_paths,
    )

    cad_to_cm = max(
        float(source_to_mm) / 10.0,
        1.0e-12,
    )

    join_tol = (
        5.0 / cad_to_cm
    )

    # Gap pass is intentionally geometric and layer-independent.
    # It allows the same continuity behavior as FRONT across openings.
    max_opening_gap = (
        350.0 / cad_to_cm
    )

    axis_tol = (
        12.0 / cad_to_cm
    )

    current = tuple(
        start_point
    )

    used = set(
        used_global
        or ()
    )

    run = []
    virtual_gaps = []

    guard = 0

    while guard < max(
        len(rows) * 5,
        64,
    ):
        guard += 1

        direct = []

        for row in rows:
            index = row["index"]

            if index in used:
                continue

            other = _plan3d_facade_v18_other_endpoint(
                row,
                current,
                join_tol,
            )

            if other is None:
                continue

            primary, lateral = _plan3d_facade_v18_forward_score(
                viewport,
                current,
                other,
                direction,
            )

            if primary <= 0.0:
                continue

            if lateral > max(
                2.0,
                abs(primary) * 0.04,
            ):
                continue

            direct.append(
                (
                    -primary,
                    lateral,
                    index,
                    row,
                    tuple(other),
                )
            )

        if direct:
            direct.sort(
                key=lambda item:
                    (
                        item[0],
                        item[1],
                        item[2],
                    )
            )

            _rank, _lat, index, row, other = direct[0]

            run.append(
                {
                    "a": tuple(row["a"]),
                    "b": tuple(row["b"]),
                    "segment_index": int(index),
                }
            )

            used.add(
                index
            )
            current = tuple(
                other
            )
            continue

        # No directly connected segment.
        # Before declaring a corner, try to bridge a collinear opening gap.
        cvx, cvy = _plan3d_scene_to_view_xy_v1(
            viewport,
            current[0],
            current[1],
        )

        gap_candidates = []

        for row in rows:
            index = row["index"]

            if index in used:
                continue

            for endpoint_name in (
                "a",
                "b",
            ):
                endpoint = tuple(
                    row[
                        endpoint_name
                    ]
                )

                evx, evy = _plan3d_scene_to_view_xy_v1(
                    viewport,
                    endpoint[0],
                    endpoint[1],
                )

                if direction in (
                    "RIGHT",
                    "LEFT",
                ):
                    lateral_scene = abs(
                        evy - cvy
                    )
                else:
                    lateral_scene = abs(
                        evx - cvx
                    )

                # Convert CAD/source axis tolerance through actual source coords.
                if direction in (
                    "RIGHT",
                    "LEFT",
                ):
                    axis_delta_source = abs(
                        endpoint[1]
                        - current[1]
                    )
                else:
                    axis_delta_source = abs(
                        endpoint[0]
                        - current[0]
                    )

                if axis_delta_source > axis_tol:
                    continue

                primary, _lateral = _plan3d_facade_v18_forward_score(
                    viewport,
                    current,
                    endpoint,
                    direction,
                )

                if primary <= 0.0:
                    continue

                source_gap = (
                    (
                        endpoint[0]
                        - current[0]
                    ) ** 2
                    + (
                        endpoint[1]
                        - current[1]
                    ) ** 2
                ) ** 0.5

                if source_gap > max_opening_gap:
                    continue

                gap_candidates.append(
                    (
                        source_gap,
                        lateral_scene,
                        index,
                        row,
                        endpoint,
                    )
                )

        if gap_candidates:
            gap_candidates.sort(
                key=lambda item:
                    (
                        item[0],
                        item[1],
                        item[2],
                    )
            )

            gap_distance, _lat, index, row, endpoint = (
                gap_candidates[0]
            )

            virtual_gaps.append(
                {
                    "a": tuple(current),
                    "b": tuple(endpoint),
                    "gap_source": float(gap_distance),
                }
            )

            current = tuple(
                endpoint
            )
            continue

        # No forward continuation, not even through a valid collinear gap.
        # This is the real geometric corner / end.
        break

    return {
        "segments": run,
        "virtual_gaps": virtual_gaps,
        "start": tuple(start_point),
        "end": tuple(current),
        "direction": str(direction),
        "used_segment_indices": sorted(
            int(index)
            for index in used
        ),
    }


def _plan3d_facade_v18_draw_gaps(
    viewport,
    gaps,
    color_hex,
):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import (
        QColor,
        QPainterPath,
        QPen,
    )
    from PySide6.QtWidgets import (
        QGraphicsPathItem,
    )

    scene = viewport.scene()

    if scene is None:
        return 0

    items = list(
        getattr(
            viewport,
            "_plan3d_facade_bottom_left_items_v1",
            [],
        )
        or []
    )

    pen = QPen(
        QColor(
            color_hex
        )
    )
    pen.setCosmetic(
        True
    )
    pen.setWidthF(
        3.0
    )
    pen.setStyle(
        Qt.PenStyle.DashLine
    )

    count = 0

    for gap in gaps:
        path = QPainterPath()

        a = gap["a"]
        b = gap["b"]

        path.moveTo(
            float(a[0]),
            float(a[1]),
        )
        path.lineTo(
            float(b[0]),
            float(b[1]),
        )

        item = QGraphicsPathItem(
            path
        )
        item.setPen(
            pen
        )
        item.setZValue(
            5000001.0
        )

        scene.addItem(
            item
        )
        items.append(
            item
        )
        count += 1

    viewport._plan3d_facade_bottom_left_items_v1 = (
        items
    )

    return count


def _plan3d_run_facade_perimeter_continuity_v18(self):
    from floor_area_runtime import (
        _export_prepared_wall_paths,
    )

    from plan3d_canonical_export import (
        _cad_unit_info,
    )

    page = self.parentWidget()

    viewport = (
        getattr(
            page,
            "viewport",
            None,
        )
        if page is not None
        else None
    )

    if viewport is None:
        raise RuntimeError(
            "Facade Analysis: viewport unavailable."
        )

    _plan3d_clear_facade_bottom_left_preview_v1(
        viewport
    )

    values = self.values()

    assignments = dict(
        (
            values.get(
                "assignments",
                {},
            )
            or {}
        ).get(
            "floor_plans",
            {},
        )
        or {}
    )

    floor_settings = dict(
        values.get(
            "floor_settings",
            {},
        )
        or {}
    )

    pivot_map = dict(
        getattr(
            self,
            "_floor_pivots",
            {},
        )
        or {}
    )

    visible_floor_items = list(
        getattr(
            viewport,
            "_floor_area_overlay_items",
            [],
        )
        or []
    )

    if not visible_floor_items:
        self.selection_status.setText(
            "Facade Analysis: Show Floor Areas first."
        )
        print(
            "PLAN3D FACADE V18 | result=NO_VISIBLE_FLOOR_AREAS",
            flush=True,
        )
        return {}

    units_info = _cad_unit_info(
        viewport
    )

    source_to_mm = (
        float(
            units_info.get(
                "to_cm",
                1.0,
            )
            or 1.0
        )
        * 10.0
    )

    results = {}

    for floor_name, rect_values in assignments.items():
        floor_name = str(
            floor_name
        )

        floor_geometry = (
            _plan3d_facade_v13_visible_floor_geometry(
                viewport,
                rect_values,
            )
        )

        if floor_geometry is None:
            print(
                "PLAN3D FACADE V18 |",
                floor_name,
                "| result=NO_FLOOR_REFERENCE",
                flush=True,
            )
            continue

        settings = dict(
            floor_settings.get(
                floor_name,
                {},
            )
            or {}
        )

        pivot = dict(
            pivot_map.get(
                floor_name,
                {},
            )
            or {}
        )

        (
            wall_paths,
            _wall_topology,
            _export_floor,
        ) = _export_prepared_wall_paths(
            viewport,
            floor_name,
            rect_values,
            pivot,
            settings,
            units_info,
        )

        (
            outer_paths,
            validated_pairs,
            all_pairs,
        ) = _plan3d_facade_v16_outer_paths(
            wall_paths,
            floor_geometry,
            source_to_mm,
        )

        selected = (
            _plan3d_find_bottom_left_export_segment_v1(
                viewport,
                outer_paths,
            )
        )

        if selected is None:
            print(
                "PLAN3D FACADE V18 |",
                floor_name,
                "| result=NO_OUTER_WALL",
                "| wall_pairs=",
                len(
                    all_pairs
                ),
                "| validated_pairs=",
                len(
                    validated_pairs
                ),
                flush=True,
            )
            continue

        # FRONT: always LEFT -> RIGHT.
        selected_a = tuple(
            selected["a"]
        )
        selected_b = tuple(
            selected["b"]
        )

        avx, _avy = _plan3d_scene_to_view_xy_v1(
            viewport,
            selected_a[0],
            selected_a[1],
        )
        bvx, _bvy = _plan3d_scene_to_view_xy_v1(
            viewport,
            selected_b[0],
            selected_b[1],
        )

        if avx <= bvx:
            front_start = selected_a
        else:
            front_start = selected_b

        front = _plan3d_facade_v18_trace_direction(
            viewport,
            outer_paths,
            front_start,
            "RIGHT",
            source_to_mm,
        )

        # Draw FRONT wall pieces RED using existing renderer contract.
        front_for_draw = {
            "wall_segments":
                list(
                    front.get(
                        "segments",
                        []
                    )
                ),
            "openings": [],
            "start_corner":
                tuple(
                    front.get(
                        "start"
                    )
                ),
            "end_corner":
                tuple(
                    front.get(
                        "end"
                    )
                ),
            "upturn_found": False,
        }

        _plan3d_draw_front_facade_v4(
            viewport,
            floor_name,
            front_for_draw,
            {
                "inner_segments":
                    [],
            },
        )

        _plan3d_facade_v18_draw_gaps(
            viewport,
            front.get(
                "virtual_gaps",
                [],
            ),
            "#FF0000",
        )

        # RIGHT: FRONT right corner -> UP.
        right = _plan3d_facade_v18_trace_direction(
            viewport,
            outer_paths,
            front["end"],
            "UP",
            source_to_mm,
            used_global=front.get(
                "used_segment_indices",
                [],
            ),
        )

        _plan3d_facade_v17_draw_side(
            viewport,
            floor_name,
            "RIGHT",
            right,
        )

        _plan3d_facade_v18_draw_gaps(
            viewport,
            right.get(
                "virtual_gaps",
                [],
            ),
            "#00FF00",
        )

        # REAR: RIGHT end -> LEFT.
        used_after_right = set(
            front.get(
                "used_segment_indices",
                [],
            )
        )
        used_after_right.update(
            right.get(
                "used_segment_indices",
                [],
            )
        )

        rear = _plan3d_facade_v18_trace_direction(
            viewport,
            outer_paths,
            right["end"],
            "LEFT",
            source_to_mm,
            used_global=used_after_right,
        )

        # LEFT: REAR end -> DOWN.
        used_after_rear = set(
            used_after_right
        )
        used_after_rear.update(
            rear.get(
                "used_segment_indices",
                [],
            )
        )

        left = _plan3d_facade_v18_trace_direction(
            viewport,
            outer_paths,
            rear["end"],
            "DOWN",
            source_to_mm,
            used_global=used_after_rear,
        )

        _plan3d_facade_v17_draw_side(
            viewport,
            floor_name,
            "LEFT",
            left,
        )

        _plan3d_facade_v18_draw_gaps(
            viewport,
            left.get(
                "virtual_gaps",
                [],
            ),
            "#FFFF00",
        )

        results[
            floor_name
        ] = {
            "walk_order":
                [
                    "FRONT_LEFT_TO_RIGHT",
                    "RIGHT_UP",
                    "REAR_RIGHT_TO_LEFT",
                    "LEFT_DOWN",
                ],
            "layer_controls_continuity":
                False,
            "geometry_source":
                "EXPORT_PREPARED_WALL_OUTER",
            "floor_usage":
                "VALIDATION_ONLY",
            "front_segments":
                len(
                    front.get(
                        "segments",
                        [],
                    )
                ),
            "front_gaps":
                len(
                    front.get(
                        "virtual_gaps",
                        [],
                    )
                ),
            "right_segments":
                len(
                    right.get(
                        "segments",
                        [],
                    )
                ),
            "right_gaps":
                len(
                    right.get(
                        "virtual_gaps",
                        [],
                    )
                ),
            "rear_segments":
                len(
                    rear.get(
                        "segments",
                        [],
                    )
                ),
            "rear_gaps":
                len(
                    rear.get(
                        "virtual_gaps",
                        [],
                    )
                ),
            "left_segments":
                len(
                    left.get(
                        "segments",
                        [],
                    )
                ),
            "left_gaps":
                len(
                    left.get(
                        "virtual_gaps",
                        [],
                    )
                ),
        }

        print(
            "PLAN3D FACADE V18 |",
            floor_name,
            "| WALK=FRONT->RIGHT->REAR->LEFT",
            "| LAYER_CONTINUITY=IGNORED",
            "| FRONT(red)=",
            len(
                front.get(
                    "segments",
                    [],
                )
            ),
            "+gaps",
            len(
                front.get(
                    "virtual_gaps",
                    [],
                )
            ),
            "| RIGHT(green)=",
            len(
                right.get(
                    "segments",
                    [],
                )
            ),
            "+gaps",
            len(
                right.get(
                    "virtual_gaps",
                    [],
                )
            ),
            "| REAR=",
            len(
                rear.get(
                    "segments",
                    [],
                )
            ),
            "+gaps",
            len(
                rear.get(
                    "virtual_gaps",
                    [],
                )
            ),
            "| LEFT(yellow)=",
            len(
                left.get(
                    "segments",
                    [],
                )
            ),
            "+gaps",
            len(
                left.get(
                    "virtual_gaps",
                    [],
                )
            ),
            flush=True,
        )

    self._facade_analysis_v18 = (
        results
    )

    self.selection_status.setText(
        "Facade Analysis: Front->Right->Rear->Left; layer cannot stop/turn continuity."
    )

    print(
        "PLAN3D FACADE V18 COMPLETE | floors=",
        len(
            results
        ),
        flush=True,
    )

    return results



# ============================================================
# PLAN3D_FACADE_ARBITRARY_ANGLE_PERIMETER_V19
#
# EXPERIMENTAL CONTINUITY RULE
#
# - No 90 degree requirement.
# - Outer perimeter continuity is primary.
# - At a real outer-wall vertex, any angle is allowed.
# - Layer NEVER controls stop/turn.
# - Openings/gaps do not terminate the perimeter.
#
# Walk order remains:
#   FRONT -> RIGHT -> REAR -> LEFT -> FRONT
#
# Classification uses the oriented segment heading in viewport:
#   rightward sector  -> FRONT  (RED)
#   upward sector     -> RIGHT  (GREEN)
#   leftward sector   -> REAR
#   downward sector   -> LEFT   (YELLOW)
#
# Angled walls are assigned to the sector their heading points toward.
# ============================================================


def _plan3d_facade_v19_heading_sector(
    viewport,
    a,
    b,
):
    import math

    avx, avy = _plan3d_scene_to_view_xy_v1(
        viewport,
        a[0],
        a[1],
    )

    bvx, bvy = _plan3d_scene_to_view_xy_v1(
        viewport,
        b[0],
        b[1],
    )

    dx = float(
        bvx - avx
    )
    dy = float(
        bvy - avy
    )

    if abs(dx) <= 1.0e-9 and abs(dy) <= 1.0e-9:
        return None, None

    angle = math.degrees(
        math.atan2(
            dy,
            dx,
        )
    )

    # Screen coordinates:
    #   RIGHT = 0 deg
    #   UP    = -90 deg
    #   LEFT  = +/-180 deg
    #   DOWN  = +90 deg
    if -45.0 <= angle < 45.0:
        sector = "FRONT"
    elif -135.0 <= angle < -45.0:
        sector = "RIGHT"
    elif angle >= 135.0 or angle < -135.0:
        sector = "REAR"
    else:
        sector = "LEFT"

    return (
        sector,
        float(angle),
    )


def _plan3d_facade_v19_other(
    row,
    point,
    tol,
):
    a = tuple(
        row["a"]
    )
    b = tuple(
        row["b"]
    )

    if _plan3d_facade_v17_near(
        a,
        point,
        tol,
    ):
        return b

    if _plan3d_facade_v17_near(
        b,
        point,
        tol,
    ):
        return a

    return None


def _plan3d_facade_v19_turn_delta(
    viewport,
    current,
    previous,
    candidate,
):
    import math

    pvx, pvy = _plan3d_scene_to_view_xy_v1(
        viewport,
        previous[0],
        previous[1],
    )

    cvx, cvy = _plan3d_scene_to_view_xy_v1(
        viewport,
        current[0],
        current[1],
    )

    nvx, nvy = _plan3d_scene_to_view_xy_v1(
        viewport,
        candidate[0],
        candidate[1],
    )

    incoming = math.atan2(
        cvy - pvy,
        cvx - pvx,
    )

    outgoing = math.atan2(
        nvy - cvy,
        nvx - cvx,
    )

    delta = math.degrees(
        outgoing - incoming
    )

    while delta <= -180.0:
        delta += 360.0

    while delta > 180.0:
        delta -= 360.0

    return float(
        delta
    )


def _plan3d_facade_v19_walk_outer_perimeter(
    viewport,
    outer_paths,
    start_segment,
    source_to_mm,
):
    rows = (
        _plan3d_facade_v2_paths_to_segments(
            outer_paths
        )
    )

    cad_to_cm = max(
        float(
            source_to_mm
        )
        / 10.0,
        1.0e-12,
    )

    join_tol = (
        5.0
        / cad_to_cm
    )

    max_gap = (
        350.0
        / cad_to_cm
    )

    start_a = tuple(
        start_segment["a"]
    )
    start_b = tuple(
        start_segment["b"]
    )

    avx, _avy = _plan3d_scene_to_view_xy_v1(
        viewport,
        start_a[0],
        start_a[1],
    )

    bvx, _bvy = _plan3d_scene_to_view_xy_v1(
        viewport,
        start_b[0],
        start_b[1],
    )

    if avx <= bvx:
        start = start_a
        current = start_b
    else:
        start = start_b
        current = start_a

    previous = tuple(
        start
    )

    used = set()
    walked = []
    gaps = []

    start_index = None

    for index, row in enumerate(
        rows
    ):
        if (
            (
                _plan3d_facade_v17_near(
                    row["a"],
                    start_a,
                    join_tol,
                )
                and _plan3d_facade_v17_near(
                    row["b"],
                    start_b,
                    join_tol,
                )
            )
            or (
                _plan3d_facade_v17_near(
                    row["a"],
                    start_b,
                    join_tol,
                )
                and _plan3d_facade_v17_near(
                    row["b"],
                    start_a,
                    join_tol,
                )
            )
        ):
            start_index = index
            break

    if start_index is None:
        return {
            "segments": [],
            "gaps": [],
            "closed": False,
        }

    first_sector, first_angle = (
        _plan3d_facade_v19_heading_sector(
            viewport,
            start,
            current,
        )
    )

    walked.append(
        {
            "a": tuple(start),
            "b": tuple(current),
            "segment_index": int(
                start_index
            ),
            "sector": first_sector,
            "angle": first_angle,
        }
    )

    used.add(
        start_index
    )

    guard = 0

    while guard < max(
        len(rows) * 8,
        128,
    ):
        guard += 1

        direct = []

        for index, row in enumerate(
            rows
        ):
            if index in used:
                continue

            other = (
                _plan3d_facade_v19_other(
                    row,
                    current,
                    join_tol,
                )
            )

            if other is None:
                continue

            delta = (
                _plan3d_facade_v19_turn_delta(
                    viewport,
                    current,
                    previous,
                    other,
                )
            )

            # Reject U-turn/backtracking. Any architectural angle is allowed.
            if abs(
                abs(delta) - 180.0
            ) <= 5.0:
                continue

            # Perimeter rule:
            # prefer the continuation requiring the smallest heading change.
            direct.append(
                (
                    abs(delta),
                    index,
                    tuple(other),
                    row,
                    delta,
                )
            )

        if direct:
            direct.sort(
                key=lambda item:
                    (
                        item[0],
                        item[1],
                    )
            )

            _turn_rank, index, other, row, delta = (
                direct[0]
            )

            sector, angle = (
                _plan3d_facade_v19_heading_sector(
                    viewport,
                    current,
                    other,
                )
            )

            walked.append(
                {
                    "a": tuple(current),
                    "b": tuple(other),
                    "segment_index": int(index),
                    "sector": sector,
                    "angle": angle,
                    "turn_delta": float(delta),
                }
            )

            used.add(
                index
            )

            previous = tuple(
                current
            )
            current = tuple(
                other
            )

            if (
                len(walked) > 3
                and _plan3d_facade_v17_near(
                    current,
                    start,
                    join_tol,
                )
            ):
                return {
                    "segments": walked,
                    "gaps": gaps,
                    "closed": True,
                    "start": tuple(start),
                    "end": tuple(current),
                }

            continue

        # Opening/gap continuation:
        # choose the nearest unused endpoint whose heading is closest
        # to the incoming perimeter heading. No layer check.
        gap_candidates = []

        for index, row in enumerate(
            rows
        ):
            if index in used:
                continue

            for endpoint in (
                tuple(row["a"]),
                tuple(row["b"]),
            ):
                distance = (
                    (
                        endpoint[0]
                        - current[0]
                    ) ** 2
                    + (
                        endpoint[1]
                        - current[1]
                    ) ** 2
                ) ** 0.5

                if distance <= join_tol:
                    continue

                if distance > max_gap:
                    continue

                delta = (
                    _plan3d_facade_v19_turn_delta(
                        viewport,
                        current,
                        previous,
                        endpoint,
                    )
                )

                if abs(
                    abs(delta) - 180.0
                ) <= 5.0:
                    continue

                gap_candidates.append(
                    (
                        abs(delta),
                        distance,
                        index,
                        endpoint,
                    )
                )

        if gap_candidates:
            gap_candidates.sort(
                key=lambda item:
                    (
                        item[0],
                        item[1],
                        item[2],
                    )
            )

            _turn_rank, distance, _index, endpoint = (
                gap_candidates[0]
            )

            gaps.append(
                {
                    "a": tuple(current),
                    "b": tuple(endpoint),
                    "gap_source": float(
                        distance
                    ),
                }
            )

            previous = tuple(
                current
            )
            current = tuple(
                endpoint
            )
            continue

        break

    return {
        "segments": walked,
        "gaps": gaps,
        "closed": False,
        "start": tuple(start),
        "end": tuple(current),
    }




def _plan3d_run_facade_arbitrary_angle_perimeter_v19(self):
    from floor_area_runtime import (
        _export_prepared_wall_paths,
    )

    from plan3d_canonical_export import (
        _cad_unit_info,
    )

    page = self.parentWidget()

    viewport = (
        getattr(
            page,
            "viewport",
            None,
        )
        if page is not None
        else None
    )

    if viewport is None:
        raise RuntimeError(
            "Facade Analysis: viewport unavailable."
        )

    _plan3d_clear_facade_bottom_left_preview_v1(
        viewport
    )

    values = self.values()

    assignments = dict(
        (
            values.get(
                "assignments",
                {},
            )
            or {}
        ).get(
            "floor_plans",
            {},
        )
        or {}
    )

    floor_settings = dict(
        values.get(
            "floor_settings",
            {},
        )
        or {}
    )

    pivot_map = dict(
        getattr(
            self,
            "_floor_pivots",
            {},
        )
        or {}
    )

    visible_floor_items = list(
        getattr(
            viewport,
            "_floor_area_overlay_items",
            [],
        )
        or []
    )

    if not visible_floor_items:
        self.selection_status.setText(
            "Facade Analysis: Show Floor Areas first."
        )

        print(
            "PLAN3D FACADE V19 | result=NO_VISIBLE_FLOOR_AREAS",
            flush=True,
        )

        return {}

    units_info = _cad_unit_info(
        viewport
    )

    source_to_mm = (
        float(
            units_info.get(
                "to_cm",
                1.0,
            )
            or 1.0
        )
        * 10.0
    )

    results = {}

    for floor_name, rect_values in assignments.items():
        floor_name = str(
            floor_name
        )

        floor_geometry = (
            _plan3d_facade_v13_visible_floor_geometry(
                viewport,
                rect_values,
            )
        )

        if floor_geometry is None:
            print(
                "PLAN3D FACADE V19 |",
                floor_name,
                "| result=NO_FLOOR_REFERENCE",
                flush=True,
            )
            continue

        settings = dict(
            floor_settings.get(
                floor_name,
                {},
            )
            or {}
        )

        pivot = dict(
            pivot_map.get(
                floor_name,
                {},
            )
            or {}
        )

        (
            wall_paths,
            _wall_topology,
            _export_floor,
        ) = _export_prepared_wall_paths(
            viewport,
            floor_name,
            rect_values,
            pivot,
            settings,
            units_info,
        )

        (
            outer_paths,
            validated_pairs,
            all_pairs,
        ) = _plan3d_facade_v16_outer_paths(
            wall_paths,
            floor_geometry,
            source_to_mm,
        )

        selected = (
            _plan3d_find_bottom_left_export_segment_v1(
                viewport,
                outer_paths,
            )
        )

        if selected is None:
            print(
                "PLAN3D FACADE V19 |",
                floor_name,
                "| result=NO_OUTER_WALL",
                "| wall_pairs=",
                len(all_pairs),
                "| validated_pairs=",
                len(validated_pairs),
                flush=True,
            )
            continue

        walked = (
            _plan3d_facade_v19_walk_outer_perimeter(
                viewport,
                outer_paths,
                selected,
                source_to_mm,
            )
        )

        counts = (
            _plan3d_facade_v19_draw_sector_paths(
                viewport,
                floor_name,
                walked,
            )
        )

        # Gap color follows previous segment sector when possible.
        gaps = walked.get(
            "gaps",
            [],
        )

        for gap in gaps:
            sector, _angle = (
                _plan3d_facade_v19_heading_sector(
                    viewport,
                    gap["a"],
                    gap["b"],
                )
            )

            color = {
                "FRONT": "#FF0000",
                "RIGHT": "#00FF00",
                "LEFT": "#FFFF00",
            }.get(
                sector
            )

            if color is not None:
                _plan3d_facade_v18_draw_gaps(
                    viewport,
                    [
                        gap
                    ],
                    color,
                )

        results[
            floor_name
        ] = {
            "closed":
                bool(
                    walked.get(
                        "closed",
                        False,
                    )
                ),
            "counts":
                counts,
            "gap_count":
                len(
                    gaps
                ),
            "layer_controls_continuity":
                False,
            "angle_requirement":
                "NONE",
        }

        print(
            "PLAN3D FACADE V19 |",
            floor_name,
            "| ANGLE_REQUIREMENT=NONE",
            "| LAYER_CONTINUITY=IGNORED",
            "| CLOSED=",
            walked.get(
                "closed",
                False,
            ),
            "| FRONT=",
            counts.get(
                "FRONT",
                0,
            ),
            "| RIGHT=",
            counts.get(
                "RIGHT",
                0,
            ),
            "| REAR=",
            counts.get(
                "REAR",
                0,
            ),
            "| LEFT=",
            counts.get(
                "LEFT",
                0,
            ),
            "| gaps=",
            len(
                gaps
            ),
            flush=True,
        )

    self._facade_analysis_v19 = (
        results
    )

    self.selection_status.setText(
        "Facade Analysis: arbitrary-angle outer perimeter walk active."
    )

    print(
        "PLAN3D FACADE V19 COMPLETE | floors=",
        len(
            results
        ),
        flush=True,
    )

    return results



# ============================================================
# PLAN3D_FACADE_REAR_BLUE_V20
#
# Rule:
# FRONT = RED
# RIGHT = GREEN
# REAR  = BLUE
# LEFT  = YELLOW
# ============================================================


def _plan3d_facade_v19_draw_sector_paths(
    viewport,
    floor_name,
    walked,
):
    from PySide6.QtGui import (
        QColor,
        QPainterPath,
        QPen,
    )
    from PySide6.QtWidgets import (
        QGraphicsPathItem,
    )

    scene = viewport.scene()

    if scene is None:
        return {
            "FRONT": 0,
            "RIGHT": 0,
            "REAR": 0,
            "LEFT": 0,
        }

    items = list(
        getattr(
            viewport,
            "_plan3d_facade_bottom_left_items_v1",
            [],
        )
        or []
    )

    colors = {
        "FRONT": "#FF0000",
        "RIGHT": "#00FF00",
        "REAR": "#0000FF",
        "LEFT": "#FFFF00",
    }

    counts = {
        "FRONT": 0,
        "RIGHT": 0,
        "REAR": 0,
        "LEFT": 0,
    }

    for row in walked.get(
        "segments",
        [],
    ):
        sector = row.get(
            "sector"
        )

        counts[sector] = counts.get(
            sector,
            0,
        ) + 1

        color_hex = colors.get(
            sector
        )

        if color_hex is None:
            continue

        pen = QPen(
            QColor(
                color_hex
            )
        )

        pen.setCosmetic(
            True
        )
        pen.setWidthF(
            4.0
        )

        path = QPainterPath()

        path.moveTo(
            float(
                row["a"][0]
            ),
            float(
                row["a"][1]
            ),
        )

        path.lineTo(
            float(
                row["b"][0]
            ),
            float(
                row["b"][1]
            ),
        )

        item = QGraphicsPathItem(
            path
        )

        item.setPen(
            pen
        )
        item.setZValue(
            5000001.0
        )

        scene.addItem(
            item
        )
        items.append(
            item
        )

    viewport._plan3d_facade_bottom_left_items_v1 = (
        items
    )

    return counts


def _plan3d_run_facade_arbitrary_angle_perimeter_v20(self):
    result = (
        _plan3d_run_facade_arbitrary_angle_perimeter_v19(
            self
        )
    )

    data = getattr(
        self,
        "_facade_analysis_v19",
        {},
    )

    print(
        "PLAN3D FACADE V20 | COLORS=FRONT_RED,RIGHT_GREEN,REAR_BLUE,LEFT_YELLOW",
        flush=True,
    )

    self._facade_analysis_v20 = (
        data
    )

    self.selection_status.setText(
        "Facade Analysis: Front=red, Right=green, Rear=blue, Left=yellow."
    )

    return result



# ============================================================
# PLAN3D_FACADE_EXTERIOR_DOOR_STRAIGHT_PASS_V20F
#
# RULE:
# Exterior Door is NOT a facade corner.
#
# When facade walk reaches an Exterior Door area:
# - keep current facade direction
# - continue straight across the entire exterior-door region
# - keep extending in the same direction until:
#     a) a real export-prepared Wall surface/segment is reached, or
#     b) a real wall corner is reached
# - Exterior Door graphics/layer do not create a corner
#
# Baseline:
# - exact V20 facade state
# - Wall = geometry source
# - Floor is not substituted for Wall
# ============================================================


def _plan3d_facade_v20f_vec(a, b):
    import math

    dx = float(b[0]) - float(a[0])
    dy = float(b[1]) - float(a[1])

    length = math.hypot(dx, dy)

    if length <= 1.0e-9:
        return None

    return (
        dx / length,
        dy / length,
        length,
    )


def _plan3d_facade_v20f_dot(a, b):
    return (
        float(a[0]) * float(b[0])
        + float(a[1]) * float(b[1])
    )


def _plan3d_facade_v20f_distance_point_to_ray(
    origin,
    direction,
    point,
):
    vx = float(point[0]) - float(origin[0])
    vy = float(point[1]) - float(origin[1])

    t = (
        vx * float(direction[0])
        + vy * float(direction[1])
    )

    if t < 0.0:
        return None

    px = (
        float(origin[0])
        + float(direction[0]) * t
    )
    py = (
        float(origin[1])
        + float(direction[1]) * t
    )

    dx = float(point[0]) - px
    dy = float(point[1]) - py

    dist = (
        dx * dx
        + dy * dy
    ) ** 0.5

    return (
        float(dist),
        float(t),
    )


def _plan3d_facade_v20f_collect_exterior_door_bridges(
    viewport,
    rect_values,
    wall_paths,
    source_to_mm,
):
    rows = []

    # Try the existing symbol-opening resolver already used by the
    # floor/export system. We only keep Exterior Door metadata.
    try:
        from floor_area_runtime import (
            _symbol_opening_bridge_paths,
        )

        (
            paths,
            metadata,
            _stats,
        ) = _symbol_opening_bridge_paths(
            viewport,
            rect_values,
            wall_paths,
            source_to_mm,
        )

        for path, meta in zip(
            list(paths or []),
            list(metadata or []),
        ):
            semantic = str(
                (meta or {}).get(
                    "semantic_type",
                    "",
                )
                or ""
            )

            folded = semantic.casefold()

            if (
                "exterior" not in folded
                and "dış" not in folded
            ):
                continue

            if (
                "door" not in folded
                and "kapı" not in folded
            ):
                continue

            points = []

            for point in list(path or []):
                try:
                    points.append(
                        (
                            float(point[0]),
                            float(point[1]),
                        )
                    )
                except Exception:
                    continue

            if len(points) < 2:
                continue

            rows.append(
                {
                    "a": tuple(points[0]),
                    "b": tuple(points[-1]),
                }
            )

    except Exception as exc:
        print(
            "PLAN3D FACADE V20F | Exterior Door resolver warning:",
            exc,
            flush=True,
        )

    return rows


def _plan3d_facade_v20f_near(
    a,
    b,
    tol,
):
    return (
        (
            float(a[0]) - float(b[0])
        ) ** 2
        + (
            float(a[1]) - float(b[1])
        ) ** 2
    ) ** 0.5 <= tol


def _plan3d_facade_v20f_find_straight_resume(
    current,
    previous,
    wall_paths,
    source_to_mm,
):
    incoming = _plan3d_facade_v20f_vec(
        previous,
        current,
    )

    if incoming is None:
        return None

    direction = (
        incoming[0],
        incoming[1],
    )

    cad_to_cm = max(
        float(source_to_mm) / 10.0,
        1.0e-12,
    )

    ray_tol = (
        35.0 / cad_to_cm
    )

    min_forward = (
        10.0 / cad_to_cm
    )

    max_forward = (
        600.0 / cad_to_cm
    )

    candidates = []

    for row in _plan3d_facade_v2_paths_to_segments(
        wall_paths
    ):
        for endpoint in (
            tuple(row["a"]),
            tuple(row["b"]),
        ):
            hit = (
                _plan3d_facade_v20f_distance_point_to_ray(
                    current,
                    direction,
                    endpoint,
                )
            )

            if hit is None:
                continue

            dist, t = hit

            if t < min_forward:
                continue

            if t > max_forward:
                continue

            if dist > ray_tol:
                continue

            candidates.append(
                (
                    float(t),
                    float(dist),
                    tuple(endpoint),
                )
            )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            item[0],
            item[1],
        )
    )

    return candidates[0][2]


def _plan3d_facade_v20f_exterior_door_pass(
    current,
    previous,
    door_bridges,
    wall_paths,
    source_to_mm,
):
    cad_to_cm = max(
        float(source_to_mm) / 10.0,
        1.0e-12,
    )

    contact_tol = (
        30.0 / cad_to_cm
    )

    for bridge in door_bridges:
        a = tuple(bridge["a"])
        b = tuple(bridge["b"])

        if not (
            _plan3d_facade_v20f_near(
                current,
                a,
                contact_tol,
            )
            or _plan3d_facade_v20f_near(
                current,
                b,
                contact_tol,
            )
        ):
            continue

        resume = (
            _plan3d_facade_v20f_find_straight_resume(
                current,
                previous,
                wall_paths,
                source_to_mm,
            )
        )

        if resume is None:
            continue

        return {
            "a": tuple(current),
            "b": tuple(resume),
            "semantic_type": "Exterior Door",
        }

    return None


_PLAN3D_FACADE_V20F_BASE_WALK = (
    _plan3d_facade_v19_walk_outer_perimeter
)


def _plan3d_facade_v20f_walk(
    viewport,
    outer_paths,
    wall_paths,
    start_segment,
    source_to_mm,
    door_bridges,
):
    result = _PLAN3D_FACADE_V20F_BASE_WALK(
        viewport,
        outer_paths,
        start_segment,
        source_to_mm,
    )

    # Keep exact V20 behavior if it already succeeds.
    if result.get(
        "closed",
        False,
    ):
        return result

    segments = list(
        result.get(
            "segments",
            [],
        )
        or []
    )

    if not segments:
        return result

    last = segments[-1]

    previous = tuple(last["a"])
    current = tuple(last["b"])

    bridge = (
        _plan3d_facade_v20f_exterior_door_pass(
            current,
            previous,
            door_bridges,
            wall_paths,
            source_to_mm,
        )
    )

    if bridge is None:
        return result

    gaps = list(
        result.get(
            "gaps",
            [],
        )
        or []
    )

    gaps.append(
        {
            "a": tuple(bridge["a"]),
            "b": tuple(bridge["b"]),
            "semantic_type": "Exterior Door",
        }
    )

    result["gaps"] = gaps
    result["end"] = tuple(
        bridge["b"]
    )

    print(
        "PLAN3D FACADE V20F | Exterior Door straight-pass |",
        "A=",
        bridge["a"],
        "| B=",
        bridge["b"],
        flush=True,
    )

    return result


def _plan3d_run_facade_exterior_door_straight_pass_v20f(
    self,
):
    from floor_area_runtime import (
        _export_prepared_wall_paths,
    )

    from plan3d_canonical_export import (
        _cad_unit_info,
    )

    page = self.parentWidget()

    viewport = (
        getattr(
            page,
            "viewport",
            None,
        )
        if page is not None
        else None
    )

    if viewport is None:
        raise RuntimeError(
            "Facade Analysis: viewport unavailable."
        )

    _plan3d_clear_facade_bottom_left_preview_v1(
        viewport
    )

    values = self.values()

    assignments = dict(
        (
            values.get(
                "assignments",
                {},
            )
            or {}
        ).get(
            "floor_plans",
            {},
        )
        or {}
    )

    floor_settings = dict(
        values.get(
            "floor_settings",
            {},
        )
        or {}
    )

    pivot_map = dict(
        getattr(
            self,
            "_floor_pivots",
            {},
        )
        or {}
    )

    units_info = _cad_unit_info(
        viewport
    )

    source_to_mm = (
        float(
            units_info.get(
                "to_cm",
                1.0,
            )
            or 1.0
        )
        * 10.0
    )

    results = {}

    for floor_name, rect_values in assignments.items():
        floor_name = str(
            floor_name
        )

        settings = dict(
            floor_settings.get(
                floor_name,
                {},
            )
            or {}
        )

        pivot = dict(
            pivot_map.get(
                floor_name,
                {},
            )
            or {}
        )

        (
            wall_paths,
            _wall_topology,
            _export_floor,
        ) = _export_prepared_wall_paths(
            viewport,
            floor_name,
            rect_values,
            pivot,
            settings,
            units_info,
        )

        floor_geometry = (
            _plan3d_facade_v13_visible_floor_geometry(
                viewport,
                rect_values,
            )
        )

        if floor_geometry is None:
            continue

        (
            outer_paths,
            validated_pairs,
            all_pairs,
        ) = _plan3d_facade_v16_outer_paths(
            wall_paths,
            floor_geometry,
            source_to_mm,
        )

        selected = (
            _plan3d_find_bottom_left_export_segment_v1(
                viewport,
                outer_paths,
            )
        )

        if selected is None:
            continue

        door_bridges = (
            _plan3d_facade_v20f_collect_exterior_door_bridges(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )

        walked = (
            _plan3d_facade_v20f_walk(
                viewport,
                outer_paths,
                wall_paths,
                selected,
                source_to_mm,
                door_bridges,
            )
        )

        counts = (
            _plan3d_facade_v19_draw_sector_paths(
                viewport,
                floor_name,
                walked,
            )
        )

        for gap in walked.get(
            "gaps",
            [],
        ):
            sector, _angle = (
                _plan3d_facade_v19_heading_sector(
                    viewport,
                    gap["a"],
                    gap["b"],
                )
            )

            color = {
                "FRONT": "#FF0000",
                "RIGHT": "#00FF00",
                "REAR": "#0000FF",
                "LEFT": "#FFFF00",
            }.get(
                sector
            )

            if color is not None:
                _plan3d_facade_v18_draw_gaps(
                    viewport,
                    [gap],
                    color,
                )

        results[floor_name] = {
            "counts": counts,
            "exterior_door_bridges":
                len(
                    door_bridges
                ),
            "closed":
                bool(
                    walked.get(
                        "closed",
                        False,
                    )
                ),
        }

        print(
            "PLAN3D FACADE V20F |",
            floor_name,
            "| EXTERIOR_DOOR_STRAIGHT_PASS=ON",
            "| exterior_door_bridges=",
            len(
                door_bridges
            ),
            "| FRONT=",
            counts.get(
                "FRONT",
                0,
            ),
            "| RIGHT=",
            counts.get(
                "RIGHT",
                0,
            ),
            "| REAR=",
            counts.get(
                "REAR",
                0,
            ),
            "| LEFT=",
            counts.get(
                "LEFT",
                0,
            ),
            flush=True,
        )

    self._facade_analysis_v20f = (
        results
    )

    self.selection_status.setText(
        "Facade Analysis: Exterior Door areas are crossed straight until Wall/corner."
    )

    return results



# ============================================================
# PLAN3D_FACADE_EXTERIOR_DOOR_FLOOR_BOUNDARY_PASS_V20G
#
# USER RULE:
# When facade reaches an Exterior Door area:
#   1) follow the DOOR AREA along the FLOOR BOUNDARY,
#   2) continue on that floor boundary until it touches a Wall,
#   3) at Wall contact, continue with the Wall line while remaining
#      on the same floor-boundary route.
#
# IMPORTANT:
# - Exterior Door does NOT create a corner by itself.
# - No straight ray through the door.
# - The synthetic continuation is derived from floor boundary ONLY
#   between the two real Exterior Door wall contacts.
# - Existing V20 wall walk remains unchanged outside door regions.
# ============================================================


def _plan3d_facade_v20g_exterior_rings(
    floor_geometry,
):
    rings = []

    if floor_geometry is None:
        return rings

    geom_type = str(
        getattr(
            floor_geometry,
            "geom_type",
            "",
        )
    )

    if geom_type == "Polygon":
        try:
            rings.append(
                floor_geometry.exterior
            )
        except Exception:
            pass

    elif geom_type == "MultiPolygon":
        for poly in list(
            getattr(
                floor_geometry,
                "geoms",
                [],
            )
            or []
        ):
            try:
                rings.append(
                    poly.exterior
                )
            except Exception:
                pass

    return rings


def _plan3d_facade_v20g_ring_path_between(
    ring,
    a,
    b,
):
    from shapely.geometry import (
        LineString,
        Point,
    )
    from shapely.ops import substring

    line = LineString(
        list(
            ring.coords
        )
    )

    if line.length <= 1.0e-9:
        return None

    pa = Point(
        float(a[0]),
        float(a[1]),
    )
    pb = Point(
        float(b[0]),
        float(b[1]),
    )

    da = float(
        line.project(pa)
    )
    db = float(
        line.project(pb)
    )

    if abs(
        da - db
    ) <= 1.0e-9:
        return None

    lo = min(
        da,
        db,
    )
    hi = max(
        da,
        db,
    )

    direct = substring(
        line,
        lo,
        hi,
    )

    # Complementary arc on a closed exterior ring.
    part1 = substring(
        line,
        hi,
        float(line.length),
    )
    part2 = substring(
        line,
        0.0,
        lo,
    )

    complement_coords = []

    for geom in (
        part1,
        part2,
    ):
        coords = list(
            getattr(
                geom,
                "coords",
                [],
            )
            or []
        )

        if not coords:
            continue

        if (
            complement_coords
            and coords[0]
            == complement_coords[-1]
        ):
            coords = coords[1:]

        complement_coords.extend(
            coords
        )

    complement = None

    if len(
        complement_coords
    ) >= 2:
        complement = LineString(
            complement_coords
        )

    candidates = [
        geom
        for geom in (
            direct,
            complement,
        )
        if geom is not None
        and getattr(
            geom,
            "length",
            0.0,
        ) > 1.0e-9
    ]

    if not candidates:
        return None

    chosen = min(
        candidates,
        key=lambda geom:
            float(
                geom.length
            ),
    )

    coords = [
        (
            float(x),
            float(y),
        )
        for x, y in list(
            chosen.coords
        )
    ]

    if len(coords) < 2:
        return None

    # Orient from a-side toward b-side.
    d_start_a = (
        (
            coords[0][0] - float(a[0])
        ) ** 2
        + (
            coords[0][1] - float(a[1])
        ) ** 2
    ) ** 0.5

    d_end_a = (
        (
            coords[-1][0] - float(a[0])
        ) ** 2
        + (
            coords[-1][1] - float(a[1])
        ) ** 2
    ) ** 0.5

    if d_end_a < d_start_a:
        coords.reverse()

    return coords


def _plan3d_facade_v20g_floor_boundary_path(
    floor_geometry,
    a,
    b,
):
    from shapely.geometry import Point

    rings = (
        _plan3d_facade_v20g_exterior_rings(
            floor_geometry
        )
    )

    if not rings:
        return None

    pa = Point(
        float(a[0]),
        float(a[1]),
    )
    pb = Point(
        float(b[0]),
        float(b[1]),
    )

    ranked = []

    for ring in rings:
        try:
            score = (
                float(
                    ring.distance(
                        pa
                    )
                )
                + float(
                    ring.distance(
                        pb
                    )
                )
            )
        except Exception:
            continue

        ranked.append(
            (
                score,
                ring,
            )
        )

    if not ranked:
        return None

    ranked.sort(
        key=lambda item:
            item[0]
    )

    for _score, ring in ranked:
        coords = (
            _plan3d_facade_v20g_ring_path_between(
                ring,
                a,
                b,
            )
        )

        if coords:
            return coords

    return None


def _plan3d_facade_v20g_door_boundary_paths(
    viewport,
    rect_values,
    wall_paths,
    floor_geometry,
    source_to_mm,
):
    door_rows = (
        _plan3d_facade_v20f_collect_exterior_door_bridges(
            viewport,
            rect_values,
            wall_paths,
            source_to_mm,
        )
    )

    synthetic_paths = []
    accepted = 0

    for door in door_rows:
        a = tuple(
            door["a"]
        )
        b = tuple(
            door["b"]
        )

        coords = (
            _plan3d_facade_v20g_floor_boundary_path(
                floor_geometry,
                a,
                b,
            )
        )

        if not coords:
            continue

        # Break the floor-boundary arc into real walkable segments.
        for index in range(
            len(coords) - 1
        ):
            p1 = tuple(
                coords[index]
            )
            p2 = tuple(
                coords[index + 1]
            )

            if (
                abs(
                    p2[0] - p1[0]
                )
                + abs(
                    p2[1] - p1[1]
                )
            ) <= 1.0e-9:
                continue

            synthetic_paths.append(
                [
                    p1,
                    p2,
                ]
            )

        accepted += 1

    return (
        synthetic_paths,
        int(accepted),
        int(
            len(
                door_rows
            )
        ),
    )


def _plan3d_run_facade_exterior_door_floor_boundary_v20g(
    self,
):
    from floor_area_runtime import (
        _export_prepared_wall_paths,
    )

    from plan3d_canonical_export import (
        _cad_unit_info,
    )

    page = self.parentWidget()

    viewport = (
        getattr(
            page,
            "viewport",
            None,
        )
        if page is not None
        else None
    )

    if viewport is None:
        raise RuntimeError(
            "Facade Analysis: viewport unavailable."
        )

    _plan3d_clear_facade_bottom_left_preview_v1(
        viewport
    )

    values = self.values()

    assignments = dict(
        (
            values.get(
                "assignments",
                {},
            )
            or {}
        ).get(
            "floor_plans",
            {},
        )
        or {}
    )

    floor_settings = dict(
        values.get(
            "floor_settings",
            {},
        )
        or {}
    )

    pivot_map = dict(
        getattr(
            self,
            "_floor_pivots",
            {},
        )
        or {}
    )

    units_info = _cad_unit_info(
        viewport
    )

    source_to_mm = (
        float(
            units_info.get(
                "to_cm",
                1.0,
            )
            or 1.0
        )
        * 10.0
    )

    results = {}

    for floor_name, rect_values in assignments.items():
        floor_name = str(
            floor_name
        )

        floor_geometry = (
            _plan3d_facade_v13_visible_floor_geometry(
                viewport,
                rect_values,
            )
        )

        if floor_geometry is None:
            print(
                "PLAN3D FACADE V20G |",
                floor_name,
                "| result=NO_FLOOR_REFERENCE",
                flush=True,
            )
            continue

        settings = dict(
            floor_settings.get(
                floor_name,
                {},
            )
            or {}
        )

        pivot = dict(
            pivot_map.get(
                floor_name,
                {},
            )
            or {}
        )

        (
            wall_paths,
            _wall_topology,
            _export_floor,
        ) = _export_prepared_wall_paths(
            viewport,
            floor_name,
            rect_values,
            pivot,
            settings,
            units_info,
        )

        (
            outer_paths,
            validated_pairs,
            all_pairs,
        ) = _plan3d_facade_v16_outer_paths(
            wall_paths,
            floor_geometry,
            source_to_mm,
        )

        (
            door_boundary_paths,
            accepted_doors,
            detected_doors,
        ) = _plan3d_facade_v20g_door_boundary_paths(
            viewport,
            rect_values,
            wall_paths,
            floor_geometry,
            source_to_mm,
        )

        # Door area is traversed by the actual FLOOR BOUNDARY.
        # Once that boundary reaches the opposite Wall contact,
        # the normal V20 outer-wall walk continues.
        walk_paths = list(
            outer_paths
            or []
        ) + list(
            door_boundary_paths
            or []
        )

        selected = (
            _plan3d_find_bottom_left_export_segment_v1(
                viewport,
                walk_paths,
            )
        )

        if selected is None:
            print(
                "PLAN3D FACADE V20G |",
                floor_name,
                "| result=NO_FRONT_START",
                flush=True,
            )
            continue

        walked = (
            _plan3d_facade_v19_walk_outer_perimeter(
                viewport,
                walk_paths,
                selected,
                source_to_mm,
            )
        )

        counts = (
            _plan3d_facade_v19_draw_sector_paths(
                viewport,
                floor_name,
                walked,
            )
        )

        for gap in walked.get(
            "gaps",
            [],
        ):
            sector, _angle = (
                _plan3d_facade_v19_heading_sector(
                    viewport,
                    gap["a"],
                    gap["b"],
                )
            )

            color = {
                "FRONT": "#FF0000",
                "RIGHT": "#00FF00",
                "REAR": "#0000FF",
                "LEFT": "#FFFF00",
            }.get(
                sector
            )

            if color is not None:
                _plan3d_facade_v18_draw_gaps(
                    viewport,
                    [gap],
                    color,
                )

        results[
            floor_name
        ] = {
            "counts":
                counts,
            "detected_exterior_doors":
                int(
                    detected_doors
                ),
            "floor_boundary_door_paths":
                int(
                    accepted_doors
                ),
            "door_boundary_segments":
                int(
                    len(
                        door_boundary_paths
                    )
                ),
            "closed":
                bool(
                    walked.get(
                        "closed",
                        False,
                    )
                ),
        }

        print(
            "PLAN3D FACADE V20G |",
            floor_name,
            "| EXTERIOR_DOOR_FLOOR_BOUNDARY=ON",
            "| detected_doors=",
            detected_doors,
            "| accepted_door_paths=",
            accepted_doors,
            "| boundary_segments=",
            len(
                door_boundary_paths
            ),
            "| FRONT=",
            counts.get(
                "FRONT",
                0,
            ),
            "| RIGHT=",
            counts.get(
                "RIGHT",
                0,
            ),
            "| REAR=",
            counts.get(
                "REAR",
                0,
            ),
            "| LEFT=",
            counts.get(
                "LEFT",
                0,
            ),
            "| closed=",
            walked.get(
                "closed",
                False,
            ),
            flush=True,
        )

    self._facade_analysis_v20g = (
        results
    )

    self.selection_status.setText(
        "Facade Analysis: Exterior Door follows floor boundary to Wall, then Wall continues."
    )

    return results



# ============================================================
# PLAN3D_FACADE_EXTERIOR_DOOR_FOLLOW_FLOOR_TO_WALL_V20H
#
# EXACT RULE:
# - Facade reaches Exterior Door area.
# - Follow the FLOOR LINE through that door area.
# - Continue on the FLOOR LINE until it touches a Wall.
# - At Wall contact, continue by following the Wall line.
# ============================================================


def _plan3d_facade_v20h_wall_union(
    wall_paths,
):
    from shapely.geometry import LineString
    from shapely.ops import unary_union

    lines = []

    for row in _plan3d_facade_v2_paths_to_segments(
        wall_paths
    ):
        a = tuple(row["a"])
        b = tuple(row["b"])

        try:
            lines.append(
                LineString(
                    [
                        a,
                        b,
                    ]
                )
            )
        except Exception:
            pass

    if not lines:
        return None

    return unary_union(
        lines
    )


def _plan3d_facade_v20h_floor_rings(
    floor_geometry,
):
    rings = []

    if floor_geometry is None:
        return rings

    geom_type = str(
        getattr(
            floor_geometry,
            "geom_type",
            "",
        )
    )

    if geom_type == "Polygon":
        try:
            rings.append(
                floor_geometry.exterior
            )
        except Exception:
            pass

    elif geom_type == "MultiPolygon":
        for poly in list(
            getattr(
                floor_geometry,
                "geoms",
                [],
            )
            or []
        ):
            try:
                rings.append(
                    poly.exterior
                )
            except Exception:
                pass

    return rings


def _plan3d_facade_v20h_full_direction_path(
    ring,
    start_point,
    reverse=False,
):
    from shapely.geometry import (
        LineString,
        Point,
    )
    from shapely.ops import substring

    line = LineString(
        list(
            ring.coords
        )
    )

    if line.length <= 1.0e-9:
        return None

    start = float(
        line.project(
            Point(
                float(start_point[0]),
                float(start_point[1]),
            )
        )
    )

    part1 = substring(
        line,
        start,
        float(line.length),
    )

    part2 = substring(
        line,
        0.0,
        start,
    )

    coords = []

    for geom in (
        part1,
        part2,
    ):
        part = list(
            getattr(
                geom,
                "coords",
                [],
            )
            or []
        )

        if not part:
            continue

        if (
            coords
            and part[0] == coords[-1]
        ):
            part = part[1:]

        coords.extend(
            part
        )

    if len(coords) < 2:
        return None

    path = LineString(
        coords
    )

    if reverse:
        path = LineString(
            list(
                reversed(
                    list(
                        path.coords
                    )
                )
            )
        )

        # Re-project the requested start onto the reversed ring and rotate again.
        rline = path
        rstart = float(
            rline.project(
                Point(
                    float(start_point[0]),
                    float(start_point[1]),
                )
            )
        )

        rpart1 = substring(
            rline,
            rstart,
            float(rline.length),
        )

        rpart2 = substring(
            rline,
            0.0,
            rstart,
        )

        rcoords = []

        for geom in (
            rpart1,
            rpart2,
        ):
            part = list(
                getattr(
                    geom,
                    "coords",
                    [],
                )
                or []
            )

            if not part:
                continue

            if (
                rcoords
                and part[0] == rcoords[-1]
            ):
                part = part[1:]

            rcoords.extend(
                part
            )

        if len(rcoords) < 2:
            return None

        path = LineString(
            rcoords
        )

    return path


def _plan3d_facade_v20h_line_parts(
    geometry,
):
    if geometry is None:
        return []

    geom_type = str(
        getattr(
            geometry,
            "geom_type",
            "",
        )
    )

    if geom_type == "LineString":
        return [geometry]

    if geom_type == "MultiLineString":
        return list(
            geometry.geoms
        )

    if geom_type == "GeometryCollection":
        rows = []

        for geom in geometry.geoms:
            rows.extend(
                _plan3d_facade_v20h_line_parts(
                    geom
                )
            )

        return rows

    return []


def _plan3d_facade_v20h_intersection_positions(
    path,
    geometry,
):
    from shapely.geometry import Point

    positions = []

    if geometry is None:
        return positions

    geom_type = str(
        getattr(
            geometry,
            "geom_type",
            "",
        )
    )

    if geom_type == "Point":
        positions.append(
            float(
                path.project(
                    geometry
                )
            )
        )

    elif geom_type == "MultiPoint":
        for point in geometry.geoms:
            positions.append(
                float(
                    path.project(
                        point
                    )
                )
            )

    elif geom_type in (
        "LineString",
        "LinearRing",
    ):
        coords = list(
            geometry.coords
        )

        if coords:
            positions.append(
                float(
                    path.project(
                        Point(
                            coords[0]
                        )
                    )
                )
            )
            positions.append(
                float(
                    path.project(
                        Point(
                            coords[-1]
                        )
                    )
                )
            )

    elif geom_type in (
        "MultiLineString",
        "GeometryCollection",
    ):
        for geom in geometry.geoms:
            positions.extend(
                _plan3d_facade_v20h_intersection_positions(
                    path,
                    geom,
                )
            )

    return positions


def _plan3d_facade_v20h_trace_floor_to_wall(
    current,
    floor_geometry,
    wall_paths,
    source_to_mm,
):
    from shapely.geometry import Point
    from shapely.ops import substring

    wall_union = (
        _plan3d_facade_v20h_wall_union(
            wall_paths
        )
    )

    if wall_union is None:
        return None

    rings = (
        _plan3d_facade_v20h_floor_rings(
            floor_geometry
        )
    )

    if not rings:
        return None

    point = Point(
        float(current[0]),
        float(current[1]),
    )

    ranked_rings = []

    for ring in rings:
        try:
            ranked_rings.append(
                (
                    float(
                        ring.distance(
                            point
                        )
                    ),
                    ring,
                )
            )
        except Exception:
            pass

    if not ranked_rings:
        return None

    ranked_rings.sort(
        key=lambda item:
            item[0]
    )

    ring = ranked_rings[0][1]

    cad_to_cm = max(
        float(source_to_mm) / 10.0,
        1.0e-12,
    )

    contact_tol = (
        2.0 / cad_to_cm
    )

    wall_buffer = wall_union.buffer(
        contact_tol,
        cap_style=2,
        join_style=2,
    )

    direction_candidates = []

    for reverse in (
        False,
        True,
    ):
        path = (
            _plan3d_facade_v20h_full_direction_path(
                ring,
                current,
                reverse=reverse,
            )
        )

        if path is None:
            continue

        free_geometry = path.difference(
            wall_buffer
        )

        free_parts = (
            _plan3d_facade_v20h_line_parts(
                free_geometry
            )
        )

        if not free_parts:
            continue

        free_rows = []

        for free_part in free_parts:
            coords = list(
                free_part.coords
            )

            if len(coords) < 2:
                continue

            start_pos = float(
                path.project(
                    Point(
                        coords[0]
                    )
                )
            )

            end_pos = float(
                path.project(
                    Point(
                        coords[-1]
                    )
                )
            )

            if end_pos < start_pos:
                start_pos, end_pos = (
                    end_pos,
                    start_pos,
                )

            free_rows.append(
                (
                    start_pos,
                    end_pos,
                )
            )

        if not free_rows:
            continue

        free_rows.sort(
            key=lambda item:
                item[0]
        )

        # The first floor-boundary portion that actually leaves Wall.
        free_start, free_end = (
            free_rows[0]
        )

        intersections = (
            _plan3d_facade_v20h_intersection_positions(
                path,
                path.intersection(
                    wall_union
                ),
            )
        )

        hit_positions = sorted(
            pos
            for pos in intersections
            if pos > (
                free_end
                - contact_tol
            )
        )

        if not hit_positions:
            continue

        hit_pos = hit_positions[0]

        if hit_pos <= 1.0e-9:
            continue

        direction_candidates.append(
            (
                float(
                    free_start
                ),
                float(
                    hit_pos
                ),
                path,
            )
        )

    if not direction_candidates:
        return None

    # Follow the boundary direction that leaves the current Wall first.
    direction_candidates.sort(
        key=lambda item:
            (
                item[0],
                item[1],
            )
    )

    _free_start, hit_pos, path = (
        direction_candidates[0]
    )

    traced = substring(
        path,
        0.0,
        hit_pos,
    )

    coords = [
        (
            float(x),
            float(y),
        )
        for x, y in list(
            getattr(
                traced,
                "coords",
                [],
            )
            or []
        )
    ]

    if len(coords) < 2:
        return None

    return coords


def _plan3d_facade_v20h_near_door(
    current,
    door_rows,
    source_to_mm,
):
    cad_to_cm = max(
        float(source_to_mm) / 10.0,
        1.0e-12,
    )

    tol = (
        30.0 / cad_to_cm
    )

    for row in door_rows:
        if (
            _plan3d_facade_v17_near(
                current,
                tuple(
                    row["a"]
                ),
                tol,
            )
            or _plan3d_facade_v17_near(
                current,
                tuple(
                    row["b"]
                ),
                tol,
            )
        ):
            return True

    return False


def _plan3d_facade_v20h_paths_from_coords(
    coords,
):
    paths = []

    for index in range(
        len(coords) - 1
    ):
        a = tuple(
            coords[index]
        )
        b = tuple(
            coords[index + 1]
        )

        if (
            abs(
                b[0] - a[0]
            )
            + abs(
                b[1] - a[1]
            )
        ) <= 1.0e-9:
            continue

        paths.append(
            [
                a,
                b,
            ]
        )

    return paths


def _plan3d_run_facade_exterior_door_follow_floor_to_wall_v20h(
    self,
):
    from floor_area_runtime import (
        _export_prepared_wall_paths,
    )

    from plan3d_canonical_export import (
        _cad_unit_info,
    )

    page = self.parentWidget()

    viewport = (
        getattr(
            page,
            "viewport",
            None,
        )
        if page is not None
        else None
    )

    if viewport is None:
        raise RuntimeError(
            "Facade Analysis: viewport unavailable."
        )

    _plan3d_clear_facade_bottom_left_preview_v1(
        viewport
    )

    values = self.values()

    assignments = dict(
        (
            values.get(
                "assignments",
                {},
            )
            or {}
        ).get(
            "floor_plans",
            {},
        )
        or {}
    )

    floor_settings = dict(
        values.get(
            "floor_settings",
            {},
        )
        or {}
    )

    pivot_map = dict(
        getattr(
            self,
            "_floor_pivots",
            {},
        )
        or {}
    )

    units_info = _cad_unit_info(
        viewport
    )

    source_to_mm = (
        float(
            units_info.get(
                "to_cm",
                1.0,
            )
            or 1.0
        )
        * 10.0
    )

    results = {}

    for floor_name, rect_values in assignments.items():
        floor_name = str(
            floor_name
        )

        floor_geometry = (
            _plan3d_facade_v13_visible_floor_geometry(
                viewport,
                rect_values,
            )
        )

        if floor_geometry is None:
            continue

        settings = dict(
            floor_settings.get(
                floor_name,
                {},
            )
            or {}
        )

        pivot = dict(
            pivot_map.get(
                floor_name,
                {},
            )
            or {}
        )

        (
            wall_paths,
            _wall_topology,
            _export_floor,
        ) = _export_prepared_wall_paths(
            viewport,
            floor_name,
            rect_values,
            pivot,
            settings,
            units_info,
        )

        (
            outer_paths,
            _validated_pairs,
            _all_pairs,
        ) = _plan3d_facade_v16_outer_paths(
            wall_paths,
            floor_geometry,
            source_to_mm,
        )

        door_rows = (
            _plan3d_facade_v20f_collect_exterior_door_bridges(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )

        walk_paths = list(
            outer_paths
            or []
        )

        selected = (
            _plan3d_find_bottom_left_export_segment_v1(
                viewport,
                walk_paths,
            )
        )

        if selected is None:
            continue

        floor_added = 0
        walked = None

        # Re-run only when the current stop is an Exterior Door and
        # the exact floor-boundary-to-wall continuation was added.
        for _iteration in range(
            max(
                len(
                    door_rows
                )
                + 1,
                1,
            )
        ):
            walked = (
                _plan3d_facade_v19_walk_outer_perimeter(
                    viewport,
                    walk_paths,
                    selected,
                    source_to_mm,
                )
            )

            if walked.get(
                "closed",
                False,
            ):
                break

            segments = list(
                walked.get(
                    "segments",
                    [],
                )
                or []
            )

            if not segments:
                break

            current = tuple(
                segments[-1]["b"]
            )

            if not _plan3d_facade_v20h_near_door(
                current,
                door_rows,
                source_to_mm,
            ):
                break

            coords = (
                _plan3d_facade_v20h_trace_floor_to_wall(
                    current,
                    floor_geometry,
                    wall_paths,
                    source_to_mm,
                )
            )

            if not coords:
                break

            added_paths = (
                _plan3d_facade_v20h_paths_from_coords(
                    coords
                )
            )

            if not added_paths:
                break

            walk_paths.extend(
                added_paths
            )

            floor_added += len(
                added_paths
            )

        if walked is None:
            continue

        counts = (
            _plan3d_facade_v19_draw_sector_paths(
                viewport,
                floor_name,
                walked,
            )
        )

        for gap in walked.get(
            "gaps",
            [],
        ):
            sector, _angle = (
                _plan3d_facade_v19_heading_sector(
                    viewport,
                    gap["a"],
                    gap["b"],
                )
            )

            color = {
                "FRONT": "#FF0000",
                "RIGHT": "#00FF00",
                "REAR": "#0000FF",
                "LEFT": "#FFFF00",
            }.get(
                sector
            )

            if color is not None:
                _plan3d_facade_v18_draw_gaps(
                    viewport,
                    [gap],
                    color,
                )

        results[
            floor_name
        ] = {
            "counts":
                counts,
            "exterior_doors":
                int(
                    len(
                        door_rows
                    )
                ),
            "floor_boundary_segments_added":
                int(
                    floor_added
                ),
            "closed":
                bool(
                    walked.get(
                        "closed",
                        False,
                    )
                ),
        }

        print(
            "PLAN3D FACADE V20H |",
            floor_name,
            "| EXTERIOR_DOOR_FOLLOW_FLOOR_TO_WALL=ON",
            "| exterior_doors=",
            len(
                door_rows
            ),
            "| floor_segments_added=",
            floor_added,
            "| closed=",
            walked.get(
                "closed",
                False,
            ),
            flush=True,
        )

    self._facade_analysis_v20h = (
        results
    )

    self.selection_status.setText(
        "Facade Analysis: Exterior Door follows floor line until Wall contact, then Wall continues."
    )

    return results



# ============================================================
# PLAN3D_FACADE_EXTERIOR_DOOR_EXACT_FLOOR_TRACE_V20I
#
# EXACT USER RULE:
# 1) Facade reaches Exterior Door area.
# 2) Follow the connected FLOOR BOUNDARY from that exact point.
# 3) Continue on that FLOOR BOUNDARY until it touches a Wall.
# 4) At the Wall contact point, continue with the Wall line.
#
# No shortest-path selection.
# No straight-ray continuation.
# No parallel-wall condition.
# No extra facade rule.
# ============================================================


def _plan3d_facade_v20i_distance(a, b):
    return (
        (
            float(a[0]) - float(b[0])
        ) ** 2
        + (
            float(a[1]) - float(b[1])
        ) ** 2
    ) ** 0.5


def _plan3d_facade_v20i_floor_segments(
    floor_geometry,
):
    segments = []

    def add_ring(ring):
        coords = list(
            getattr(
                ring,
                "coords",
                [],
            )
            or []
        )

        for index in range(
            len(coords) - 1
        ):
            a = (
                float(coords[index][0]),
                float(coords[index][1]),
            )
            b = (
                float(coords[index + 1][0]),
                float(coords[index + 1][1]),
            )

            if _plan3d_facade_v20i_distance(
                a,
                b,
            ) <= 1.0e-9:
                continue

            segments.append(
                {
                    "a": a,
                    "b": b,
                }
            )

    if floor_geometry is None:
        return segments

    geom_type = str(
        getattr(
            floor_geometry,
            "geom_type",
            "",
        )
    )

    if geom_type == "Polygon":
        add_ring(
            floor_geometry.exterior
        )

    elif geom_type == "MultiPolygon":
        for poly in list(
            getattr(
                floor_geometry,
                "geoms",
                [],
            )
            or []
        ):
            add_ring(
                poly.exterior
            )

    return segments


def _plan3d_facade_v20i_point_near_wall(
    point,
    wall_union,
    tol,
):
    from shapely.geometry import Point

    try:
        return bool(
            wall_union.distance(
                Point(
                    float(point[0]),
                    float(point[1]),
                )
            ) <= tol
        )
    except Exception:
        return False


def _plan3d_facade_v20i_wall_union(
    wall_paths,
):
    from shapely.geometry import LineString
    from shapely.ops import unary_union

    lines = []

    for row in _plan3d_facade_v2_paths_to_segments(
        wall_paths
    ):
        try:
            lines.append(
                LineString(
                    [
                        tuple(row["a"]),
                        tuple(row["b"]),
                    ]
                )
            )
        except Exception:
            continue

    if not lines:
        return None

    return unary_union(
        lines
    )


def _plan3d_facade_v20i_connected_floor_trace(
    start_point,
    previous_point,
    floor_geometry,
    wall_paths,
    source_to_mm,
):
    floor_segments = (
        _plan3d_facade_v20i_floor_segments(
            floor_geometry
        )
    )

    wall_union = (
        _plan3d_facade_v20i_wall_union(
            wall_paths
        )
    )

    if (
        not floor_segments
        or wall_union is None
    ):
        return None

    cad_to_cm = max(
        float(source_to_mm) / 10.0,
        1.0e-12,
    )

    join_tol = (
        6.0 / cad_to_cm
    )

    wall_tol = (
        3.0 / cad_to_cm
    )

    # Find only FLOOR BOUNDARY segments connected to the exact
    # facade stop point.
    first_candidates = []

    for index, row in enumerate(
        floor_segments
    ):
        a = tuple(row["a"])
        b = tuple(row["b"])

        da = _plan3d_facade_v20i_distance(
            start_point,
            a,
        )
        db = _plan3d_facade_v20i_distance(
            start_point,
            b,
        )

        if da <= join_tol:
            first_candidates.append(
                (
                    db,
                    index,
                    a,
                    b,
                )
            )

        elif db <= join_tol:
            first_candidates.append(
                (
                    da,
                    index,
                    b,
                    a,
                )
            )

    if not first_candidates:
        return None

    # Do not go back over the Wall line we just came from.
    filtered = []

    incoming_x = (
        float(start_point[0])
        - float(previous_point[0])
    )
    incoming_y = (
        float(start_point[1])
        - float(previous_point[1])
    )

    for distance_rank, index, near_point, next_point in first_candidates:
        outgoing_x = (
            float(next_point[0])
            - float(near_point[0])
        )
        outgoing_y = (
            float(next_point[1])
            - float(near_point[1])
        )

        backtrack = (
            incoming_x * outgoing_x
            + incoming_y * outgoing_y
        )

        filtered.append(
            (
                backtrack,
                distance_rank,
                index,
                near_point,
                next_point,
            )
        )

    # Lowest dot product would point backward; choose the connected
    # floor-boundary branch that is not the incoming Wall continuation.
    filtered.sort(
        key=lambda item:
            (
                -item[0],
                item[1],
            )
    )

    chosen = filtered[0]

    _dot, _rank, current_index, near_point, current_point = chosen

    trace = [
        tuple(start_point),
        tuple(current_point),
    ]

    used = {
        int(current_index)
    }

    # If the first reached point already touches Wall (other than the
    # starting contact), stop there.
    if (
        _plan3d_facade_v20i_point_near_wall(
            current_point,
            wall_union,
            wall_tol,
        )
        and _plan3d_facade_v20i_distance(
            current_point,
            start_point,
        ) > join_tol
    ):
        return trace

    guard = 0

    while guard < max(
        len(floor_segments) * 2,
        32,
    ):
        guard += 1

        next_rows = []

        for index, row in enumerate(
            floor_segments
        ):
            if index in used:
                continue

            a = tuple(row["a"])
            b = tuple(row["b"])

            if _plan3d_facade_v20i_distance(
                current_point,
                a,
            ) <= join_tol:
                next_rows.append(
                    (
                        index,
                        a,
                        b,
                    )
                )

            elif _plan3d_facade_v20i_distance(
                current_point,
                b,
            ) <= join_tol:
                next_rows.append(
                    (
                        index,
                        b,
                        a,
                    )
                )

        if not next_rows:
            break

        # Floor boundary is followed by connectivity only.
        next_rows.sort(
            key=lambda item:
                _plan3d_facade_v20i_distance(
                    current_point,
                    item[2],
                )
        )

        index, _near, next_point = next_rows[0]

        used.add(
            int(index)
        )

        trace.append(
            tuple(next_point)
        )

        current_point = tuple(
            next_point
        )

        if (
            _plan3d_facade_v20i_point_near_wall(
                current_point,
                wall_union,
                wall_tol,
            )
            and _plan3d_facade_v20i_distance(
                current_point,
                start_point,
            ) > join_tol
        ):
            return trace

    return None


def _plan3d_facade_v20i_paths_from_trace(
    trace,
):
    paths = []

    for index in range(
        len(trace) - 1
    ):
        a = tuple(trace[index])
        b = tuple(trace[index + 1])

        if _plan3d_facade_v20i_distance(
            a,
            b,
        ) <= 1.0e-9:
            continue

        paths.append(
            [
                a,
                b,
            ]
        )

    return paths


def _plan3d_run_facade_exterior_door_exact_floor_trace_v20i(
    self,
):
    from floor_area_runtime import (
        _export_prepared_wall_paths,
    )

    from plan3d_canonical_export import (
        _cad_unit_info,
    )

    page = self.parentWidget()

    viewport = (
        getattr(
            page,
            "viewport",
            None,
        )
        if page is not None
        else None
    )

    if viewport is None:
        raise RuntimeError(
            "Facade Analysis: viewport unavailable."
        )

    _plan3d_clear_facade_bottom_left_preview_v1(
        viewport
    )

    values = self.values()

    assignments = dict(
        (
            values.get(
                "assignments",
                {},
            )
            or {}
        ).get(
            "floor_plans",
            {},
        )
        or {}
    )

    floor_settings = dict(
        values.get(
            "floor_settings",
            {},
        )
        or {}
    )

    pivot_map = dict(
        getattr(
            self,
            "_floor_pivots",
            {},
        )
        or {}
    )

    units_info = _cad_unit_info(
        viewport
    )

    source_to_mm = (
        float(
            units_info.get(
                "to_cm",
                1.0,
            )
            or 1.0
        )
        * 10.0
    )

    results = {}

    for floor_name, rect_values in assignments.items():
        floor_name = str(
            floor_name
        )

        floor_geometry = (
            _plan3d_facade_v13_visible_floor_geometry(
                viewport,
                rect_values,
            )
        )

        if floor_geometry is None:
            continue

        settings = dict(
            floor_settings.get(
                floor_name,
                {},
            )
            or {}
        )

        pivot = dict(
            pivot_map.get(
                floor_name,
                {},
            )
            or {}
        )

        (
            wall_paths,
            _wall_topology,
            _export_floor,
        ) = _export_prepared_wall_paths(
            viewport,
            floor_name,
            rect_values,
            pivot,
            settings,
            units_info,
        )

        (
            outer_paths,
            _validated_pairs,
            _all_pairs,
        ) = _plan3d_facade_v16_outer_paths(
            wall_paths,
            floor_geometry,
            source_to_mm,
        )

        door_rows = (
            _plan3d_facade_v20f_collect_exterior_door_bridges(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )

        walk_paths = list(
            outer_paths
            or []
        )

        selected = (
            _plan3d_find_bottom_left_export_segment_v1(
                viewport,
                walk_paths,
            )
        )

        if selected is None:
            continue

        floor_added = 0
        walked = None

        for _iteration in range(
            max(
                len(door_rows) + 2,
                2,
            )
        ):
            walked = (
                _plan3d_facade_v19_walk_outer_perimeter(
                    viewport,
                    walk_paths,
                    selected,
                    source_to_mm,
                )
            )

            if walked.get(
                "closed",
                False,
            ):
                break

            segments = list(
                walked.get(
                    "segments",
                    [],
                )
                or []
            )

            if not segments:
                break

            last = segments[-1]

            previous = tuple(
                last["a"]
            )
            current = tuple(
                last["b"]
            )

            if not _plan3d_facade_v20h_near_door(
                current,
                door_rows,
                source_to_mm,
            ):
                break

            trace = (
                _plan3d_facade_v20i_connected_floor_trace(
                    current,
                    previous,
                    floor_geometry,
                    wall_paths,
                    source_to_mm,
                )
            )

            if not trace:
                break

            added = (
                _plan3d_facade_v20i_paths_from_trace(
                    trace
                )
            )

            if not added:
                break

            walk_paths.extend(
                added
            )

            floor_added += len(
                added
            )

        if walked is None:
            continue

        counts = (
            _plan3d_facade_v19_draw_sector_paths(
                viewport,
                floor_name,
                walked,
            )
        )

        for gap in walked.get(
            "gaps",
            [],
        ):
            sector, _angle = (
                _plan3d_facade_v19_heading_sector(
                    viewport,
                    gap["a"],
                    gap["b"],
                )
            )

            color = {
                "FRONT": "#FF0000",
                "RIGHT": "#00FF00",
                "REAR": "#0000FF",
                "LEFT": "#FFFF00",
            }.get(
                sector
            )

            if color is not None:
                _plan3d_facade_v18_draw_gaps(
                    viewport,
                    [gap],
                    color,
                )

        results[
            floor_name
        ] = {
            "exterior_doors":
                int(
                    len(door_rows)
                ),
            "floor_trace_segments":
                int(
                    floor_added
                ),
            "closed":
                bool(
                    walked.get(
                        "closed",
                        False,
                    )
                ),
            "counts":
                counts,
        }

        print(
            "PLAN3D FACADE V20I |",
            floor_name,
            "| EXTERIOR_DOOR_EXACT_FLOOR_TRACE=ON",
            "| exterior_doors=",
            len(door_rows),
            "| floor_trace_segments=",
            floor_added,
            "| closed=",
            walked.get(
                "closed",
                False,
            ),
            flush=True,
        )

    self._facade_analysis_v20i = (
        results
    )

    self.selection_status.setText(
        "Facade Analysis: Exterior Door follows connected floor line until Wall contact."
    )

    return results



# ============================================================
# PLAN3D_FACADE_BIDIRECTIONAL_DOOR_FLOOR_TRACE_V20K
#
# EXACT ADDITION:
# Existing rule works left -> right.
# Add the same rule for right -> left.
#
# Exterior Door:
# - if facade reaches it from left -> right, follow connected floor line
#   in that travel direction until Wall contact, then continue Wall.
# - if facade reaches it from right -> left, do the same in reverse.
#
# No other facade rule is changed.
# ============================================================


def _plan3d_facade_v20k_connected_floor_trace(
    start_point,
    previous_point,
    floor_geometry,
    wall_paths,
    source_to_mm,
):
    floor_segments = (
        _plan3d_facade_v20i_floor_segments(
            floor_geometry
        )
    )

    wall_union = (
        _plan3d_facade_v20i_wall_union(
            wall_paths
        )
    )

    if (
        not floor_segments
        or wall_union is None
    ):
        return None

    cad_to_cm = max(
        float(source_to_mm) / 10.0,
        1.0e-12,
    )

    join_tol = (
        6.0 / cad_to_cm
    )

    wall_tol = (
        3.0 / cad_to_cm
    )

    incoming_x = (
        float(start_point[0])
        - float(previous_point[0])
    )
    incoming_y = (
        float(start_point[1])
        - float(previous_point[1])
    )

    first_candidates = []

    for index, row in enumerate(
        floor_segments
    ):
        a = tuple(row["a"])
        b = tuple(row["b"])

        if _plan3d_facade_v20i_distance(
            start_point,
            a,
        ) <= join_tol:
            near_point = a
            next_point = b

        elif _plan3d_facade_v20i_distance(
            start_point,
            b,
        ) <= join_tol:
            near_point = b
            next_point = a

        else:
            continue

        outgoing_x = (
            float(next_point[0])
            - float(near_point[0])
        )
        outgoing_y = (
            float(next_point[1])
            - float(near_point[1])
        )

        directional_dot = (
            incoming_x * outgoing_x
            + incoming_y * outgoing_y
        )

        first_candidates.append(
            (
                -float(directional_dot),
                int(index),
                tuple(next_point),
            )
        )

    if not first_candidates:
        return None

    # Same rule in both travel directions:
    # choose the connected floor branch that continues the actual
    # incoming facade direction, whether that is L->R or R->L.
    first_candidates.sort(
        key=lambda item:
            (
                item[0],
                item[1],
            )
    )

    for _rank, first_index, first_point in first_candidates:
        trace = [
            tuple(start_point),
            tuple(first_point),
        ]

        used = {
            int(first_index)
        }

        current_point = tuple(
            first_point
        )

        if (
            _plan3d_facade_v20i_point_near_wall(
                current_point,
                wall_union,
                wall_tol,
            )
            and _plan3d_facade_v20i_distance(
                current_point,
                start_point,
            ) > join_tol
        ):
            return trace

        guard = 0

        while guard < max(
            len(floor_segments) * 2,
            32,
        ):
            guard += 1

            next_rows = []

            for index, row in enumerate(
                floor_segments
            ):
                if index in used:
                    continue

                a = tuple(row["a"])
                b = tuple(row["b"])

                if _plan3d_facade_v20i_distance(
                    current_point,
                    a,
                ) <= join_tol:
                    next_rows.append(
                        (
                            int(index),
                            tuple(b),
                        )
                    )

                elif _plan3d_facade_v20i_distance(
                    current_point,
                    b,
                ) <= join_tol:
                    next_rows.append(
                        (
                            int(index),
                            tuple(a),
                        )
                    )

            if not next_rows:
                break

            next_rows.sort(
                key=lambda item:
                    item[0]
            )

            index, next_point = (
                next_rows[0]
            )

            used.add(
                int(index)
            )

            trace.append(
                tuple(next_point)
            )

            current_point = tuple(
                next_point
            )

            if (
                _plan3d_facade_v20i_point_near_wall(
                    current_point,
                    wall_union,
                    wall_tol,
                )
                and _plan3d_facade_v20i_distance(
                    current_point,
                    start_point,
                ) > join_tol
            ):
                return trace

    return None


# Replace only the floor trace helper.
_plan3d_facade_v20i_connected_floor_trace = (
    _plan3d_facade_v20k_connected_floor_trace
)

# Keep the current V20I facade runner unchanged.

# ============================================================
# PLAN3D_FACADE_START_BOTH_DIRECTIONS_V20L
#
# EXACT ADDITION:
# The facade line must start from the same start segment in BOTH directions.
#
# Existing direction:
#   LEFT -> RIGHT
#
# Added direction:
#   RIGHT -> LEFT
#
# No other facade rule is changed.
# ============================================================


def _plan3d_facade_v20l_merge_walks(
    forward,
    reverse,
):
    merged = {
        "segments": [],
        "gaps": [],
        "closed": bool(
            forward.get("closed", False)
            or reverse.get("closed", False)
        ),
    }

    seen_segments = set()

    for source in (
        forward,
        reverse,
    ):
        for row in list(
            source.get(
                "segments",
                [],
            )
            or []
        ):
            a = tuple(row["a"])
            b = tuple(row["b"])

            key = tuple(
                sorted(
                    (
                        (
                            round(float(a[0]), 6),
                            round(float(a[1]), 6),
                        ),
                        (
                            round(float(b[0]), 6),
                            round(float(b[1]), 6),
                        ),
                    )
                )
            )

            if key in seen_segments:
                continue

            seen_segments.add(key)
            merged["segments"].append(
                dict(row)
            )

    seen_gaps = set()

    for source in (
        forward,
        reverse,
    ):
        for row in list(
            source.get(
                "gaps",
                [],
            )
            or []
        ):
            a = tuple(row["a"])
            b = tuple(row["b"])

            key = tuple(
                sorted(
                    (
                        (
                            round(float(a[0]), 6),
                            round(float(a[1]), 6),
                        ),
                        (
                            round(float(b[0]), 6),
                            round(float(b[1]), 6),
                        ),
                    )
                )
            )

            if key in seen_gaps:
                continue

            seen_gaps.add(key)
            merged["gaps"].append(
                dict(row)
            )

    return merged


def _plan3d_facade_v20l_walk_both_directions(
    viewport,
    outer_paths,
    selected,
    source_to_mm,
):
    # Normal existing direction.
    forward = (
        _plan3d_facade_v19_walk_outer_perimeter(
            viewport,
            outer_paths,
            selected,
            source_to_mm,
        )
    )

    # Same start segment, opposite direction.
    reversed_selected = dict(
        selected
    )

    reversed_selected["a"] = tuple(
        selected["b"]
    )
    reversed_selected["b"] = tuple(
        selected["a"]
    )

    original_scene_to_view = globals().get(
        "_plan3d_scene_to_view_xy_v1"
    )

    if original_scene_to_view is None:
        reverse = {
            "segments": [],
            "gaps": [],
            "closed": False,
        }
    else:
        def _plan3d_scene_to_view_xy_v20l_reverse(
            viewport_obj,
            x,
            y,
        ):
            vx, vy = original_scene_to_view(
                viewport_obj,
                x,
                y,
            )
            return (
                -float(vx),
                float(vy),
            )

        globals()[
            "_plan3d_scene_to_view_xy_v1"
        ] = _plan3d_scene_to_view_xy_v20l_reverse

        try:
            reverse = (
                _plan3d_facade_v19_walk_outer_perimeter(
                    viewport,
                    outer_paths,
                    reversed_selected,
                    source_to_mm,
                )
            )
        finally:
            globals()[
                "_plan3d_scene_to_view_xy_v1"
            ] = original_scene_to_view

    return _plan3d_facade_v20l_merge_walks(
        forward,
        reverse,
    )


def _plan3d_run_facade_start_both_directions_v20l(
    self,
):
    from floor_area_runtime import (
        _export_prepared_wall_paths,
    )

    from plan3d_canonical_export import (
        _cad_unit_info,
    )

    page = self.parentWidget()

    viewport = (
        getattr(
            page,
            "viewport",
            None,
        )
        if page is not None
        else None
    )

    if viewport is None:
        raise RuntimeError(
            "Facade Analysis: viewport unavailable."
        )

    _plan3d_clear_facade_bottom_left_preview_v1(
        viewport
    )

    values = self.values()

    assignments = dict(
        (
            values.get(
                "assignments",
                {},
            )
            or {}
        ).get(
            "floor_plans",
            {},
        )
        or {}
    )

    floor_settings = dict(
        values.get(
            "floor_settings",
            {},
        )
        or {}
    )

    pivot_map = dict(
        getattr(
            self,
            "_floor_pivots",
            {},
        )
        or {}
    )

    units_info = _cad_unit_info(
        viewport
    )

    source_to_mm = (
        float(
            units_info.get(
                "to_cm",
                1.0,
            )
            or 1.0
        )
        * 10.0
    )

    results = {}

    for floor_name, rect_values in assignments.items():
        floor_name = str(
            floor_name
        )

        floor_geometry = (
            _plan3d_facade_v13_visible_floor_geometry(
                viewport,
                rect_values,
            )
        )

        if floor_geometry is None:
            continue

        settings = dict(
            floor_settings.get(
                floor_name,
                {},
            )
            or {}
        )

        pivot = dict(
            pivot_map.get(
                floor_name,
                {},
            )
            or {}
        )

        (
            wall_paths,
            _wall_topology,
            _export_floor,
        ) = _export_prepared_wall_paths(
            viewport,
            floor_name,
            rect_values,
            pivot,
            settings,
            units_info,
        )

        (
            outer_paths,
            _validated_pairs,
            _all_pairs,
        ) = _plan3d_facade_v16_outer_paths(
            wall_paths,
            floor_geometry,
            source_to_mm,
        )

        selected = (
            _plan3d_find_bottom_left_export_segment_v1(
                viewport,
                outer_paths,
            )
        )

        if selected is None:
            continue

        walked = (
            _plan3d_facade_v20l_walk_both_directions(
                viewport,
                outer_paths,
                selected,
                source_to_mm,
            )
        )

        counts = (
            _plan3d_facade_v19_draw_sector_paths(
                viewport,
                floor_name,
                walked,
            )
        )

        for gap in walked.get(
            "gaps",
            [],
        ):
            sector, _angle = (
                _plan3d_facade_v19_heading_sector(
                    viewport,
                    gap["a"],
                    gap["b"],
                )
            )

            color = {
                "FRONT": "#FF0000",
                "RIGHT": "#00FF00",
                "REAR": "#0000FF",
                "LEFT": "#FFFF00",
            }.get(
                sector
            )

            if color is not None:
                _plan3d_facade_v18_draw_gaps(
                    viewport,
                    [gap],
                    color,
                )

        results[
            floor_name
        ] = {
            "counts":
                counts,
            "start_left_to_right":
                True,
            "start_right_to_left":
                True,
        }

        print(
            "PLAN3D FACADE V20L |",
            floor_name,
            "| START_LEFT_TO_RIGHT=ON",
            "| START_RIGHT_TO_LEFT=ON",
            flush=True,
        )

    self._facade_analysis_v20l = (
        results
    )

    self.selection_status.setText(
        "Facade Analysis: start line walks both left->right and right->left."
    )

    return results



# ============================================================
# PLAN3D_FACADE_REVERSE_DIRECTION_COLOR_RULES_V20M
#
# EXACT ADDITION:
#
# LEFT -> RIGHT color rule:
#   FRONT = RED
#   RIGHT = GREEN
#   REAR  = BLUE
#   LEFT  = YELLOW
#
# RIGHT -> LEFT color rule = reverse:
#   FRONT = RED
#   LEFT  = YELLOW
#   REAR  = BLUE
#   RIGHT = GREEN
#
# For the reverse walk only:
#   RIGHT <-> LEFT
# FRONT and REAR stay unchanged.
#
# No other facade rule is changed.
# ============================================================


def _plan3d_facade_v20m_reverse_sector(
    sector,
):
    if sector == "RIGHT":
        return "LEFT"

    if sector == "LEFT":
        return "RIGHT"

    return sector


def _plan3d_facade_v20m_apply_reverse_colors(
    walked,
):
    result = dict(
        walked
    )

    result["segments"] = []

    for row in list(
        walked.get(
            "segments",
            [],
        )
        or []
    ):
        item = dict(
            row
        )

        item["sector"] = (
            _plan3d_facade_v20m_reverse_sector(
                item.get(
                    "sector"
                )
            )
        )

        item["walk_direction"] = (
            "RIGHT_TO_LEFT"
        )

        result["segments"].append(
            item
        )

    result["gaps"] = [
        dict(row)
        for row in list(
            walked.get(
                "gaps",
                [],
            )
            or []
        )
    ]

    return result


def _plan3d_facade_v20m_walk_both_directions(
    viewport,
    outer_paths,
    selected,
    source_to_mm,
):
    # Existing LEFT -> RIGHT walk.
    forward = (
        _plan3d_facade_v19_walk_outer_perimeter(
            viewport,
            outer_paths,
            selected,
            source_to_mm,
        )
    )

    for row in list(
        forward.get(
            "segments",
            [],
        )
        or []
    ):
        row["walk_direction"] = (
            "LEFT_TO_RIGHT"
        )

    # Same start segment, opposite RIGHT -> LEFT walk.
    reversed_selected = dict(
        selected
    )

    reversed_selected["a"] = tuple(
        selected["b"]
    )
    reversed_selected["b"] = tuple(
        selected["a"]
    )

    original_scene_to_view = globals().get(
        "_plan3d_scene_to_view_xy_v1"
    )

    if original_scene_to_view is None:
        reverse = {
            "segments": [],
            "gaps": [],
            "closed": False,
        }

    else:
        def _plan3d_scene_to_view_xy_v20m_reverse(
            viewport_obj,
            x,
            y,
        ):
            vx, vy = original_scene_to_view(
                viewport_obj,
                x,
                y,
            )

            return (
                -float(vx),
                float(vy),
            )

        globals()[
            "_plan3d_scene_to_view_xy_v1"
        ] = (
            _plan3d_scene_to_view_xy_v20m_reverse
        )

        try:
            reverse = (
                _plan3d_facade_v19_walk_outer_perimeter(
                    viewport,
                    outer_paths,
                    reversed_selected,
                    source_to_mm,
                )
            )
        finally:
            globals()[
                "_plan3d_scene_to_view_xy_v1"
            ] = original_scene_to_view

    # Apply the reverse color rule ONLY to RIGHT -> LEFT.
    reverse = (
        _plan3d_facade_v20m_apply_reverse_colors(
            reverse
        )
    )

    return (
        _plan3d_facade_v20l_merge_walks(
            forward,
            reverse,
        )
    )


# Replace only the bidirectional walk helper.
_plan3d_facade_v20l_walk_both_directions = (
    _plan3d_facade_v20m_walk_both_directions
)

# Keep the current V20L facade runner unchanged.

# ============================================================
# PLAN3D_FACADE_TRUE_REVERSE_ORDER_V20N
#
# PURPOSE:
# Match facade drawings with floor-plan perimeter in both directions.
#
# EXACT RULE:
# - Keep the existing LEFT->RIGHT perimeter walk.
# - Build RIGHT->LEFT from the SAME perimeter chain.
# - Reverse the SEGMENT ORDER.
# - Reverse every SEGMENT DIRECTION.
# - Do NOT swap color labels artificially.
# - Recalculate color/sector from the actual reversed segment direction.
#
# Thus the reverse walk is the real geometric inverse of the
# left->right walk.
# ============================================================


def _plan3d_facade_v20n_reverse_walk(
    viewport,
    forward,
):
    reverse_segments = []

    source_segments = list(
        forward.get(
            "segments",
            [],
        )
        or []
    )

    for source_row in reversed(
        source_segments
    ):
        row = dict(
            source_row
        )

        a = tuple(
            source_row["b"]
        )
        b = tuple(
            source_row["a"]
        )

        sector, angle = (
            _plan3d_facade_v19_heading_sector(
                viewport,
                a,
                b,
            )
        )

        row["a"] = a
        row["b"] = b
        row["sector"] = sector
        row["angle"] = angle
        row["walk_direction"] = (
            "RIGHT_TO_LEFT"
        )

        reverse_segments.append(
            row
        )

    reverse_gaps = []

    for source_row in reversed(
        list(
            forward.get(
                "gaps",
                [],
            )
            or []
        )
    ):
        row = dict(
            source_row
        )

        row["a"] = tuple(
            source_row["b"]
        )
        row["b"] = tuple(
            source_row["a"]
        )
        row["walk_direction"] = (
            "RIGHT_TO_LEFT"
        )

        reverse_gaps.append(
            row
        )

    return {
        "segments": reverse_segments,
        "gaps": reverse_gaps,
        "closed": bool(
            forward.get(
                "closed",
                False,
            )
        ),
    }


def _plan3d_facade_v20n_merge_walks(
    forward,
    reverse,
):
    # Do not dedupe by undirected geometry here.
    # The same geometric segment must exist once in LTR and once in RTL
    # because both traversal directions are needed for facade matching.
    return {
        "segments": (
            list(
                forward.get(
                    "segments",
                    [],
                )
                or []
            )
            + list(
                reverse.get(
                    "segments",
                    [],
                )
                or []
            )
        ),
        "gaps": (
            list(
                forward.get(
                    "gaps",
                    [],
                )
                or []
            )
            + list(
                reverse.get(
                    "gaps",
                    [],
                )
                or []
            )
        ),
        "closed": bool(
            forward.get(
                "closed",
                False,
            )
            or reverse.get(
                "closed",
                False,
            )
        ),
        "forward": forward,
        "reverse": reverse,
    }


def _plan3d_facade_v20n_walk_both_directions(
    viewport,
    outer_paths,
    selected,
    source_to_mm,
):
    forward = (
        _plan3d_facade_v19_walk_outer_perimeter(
            viewport,
            outer_paths,
            selected,
            source_to_mm,
        )
    )

    for row in list(
        forward.get(
            "segments",
            [],
        )
        or []
    ):
        row["walk_direction"] = (
            "LEFT_TO_RIGHT"
        )

    reverse = (
        _plan3d_facade_v20n_reverse_walk(
            viewport,
            forward,
        )
    )

    return (
        _plan3d_facade_v20n_merge_walks(
            forward,
            reverse,
        )
    )


def _plan3d_run_facade_true_reverse_order_v20n(
    self,
):
    from floor_area_runtime import (
        _export_prepared_wall_paths,
    )

    from plan3d_canonical_export import (
        _cad_unit_info,
    )

    page = self.parentWidget()

    viewport = (
        getattr(
            page,
            "viewport",
            None,
        )
        if page is not None
        else None
    )

    if viewport is None:
        raise RuntimeError(
            "Facade Analysis: viewport unavailable."
        )

    _plan3d_clear_facade_bottom_left_preview_v1(
        viewport
    )

    values = self.values()

    assignments = dict(
        (
            values.get(
                "assignments",
                {},
            )
            or {}
        ).get(
            "floor_plans",
            {},
        )
        or {}
    )

    floor_settings = dict(
        values.get(
            "floor_settings",
            {},
        )
        or {}
    )

    pivot_map = dict(
        getattr(
            self,
            "_floor_pivots",
            {},
        )
        or {}
    )

    units_info = _cad_unit_info(
        viewport
    )

    source_to_mm = (
        float(
            units_info.get(
                "to_cm",
                1.0,
            )
            or 1.0
        )
        * 10.0
    )

    results = {}

    for floor_name, rect_values in assignments.items():
        floor_name = str(
            floor_name
        )

        floor_geometry = (
            _plan3d_facade_v13_visible_floor_geometry(
                viewport,
                rect_values,
            )
        )

        if floor_geometry is None:
            continue

        settings = dict(
            floor_settings.get(
                floor_name,
                {},
            )
            or {}
        )

        pivot = dict(
            pivot_map.get(
                floor_name,
                {},
            )
            or {}
        )

        (
            wall_paths,
            _wall_topology,
            _export_floor,
        ) = _export_prepared_wall_paths(
            viewport,
            floor_name,
            rect_values,
            pivot,
            settings,
            units_info,
        )

        (
            outer_paths,
            _validated_pairs,
            _all_pairs,
        ) = _plan3d_facade_v16_outer_paths(
            wall_paths,
            floor_geometry,
            source_to_mm,
        )

        selected = (
            _plan3d_find_bottom_left_export_segment_v1(
                viewport,
                outer_paths,
            )
        )

        if selected is None:
            continue

        walked = (
            _plan3d_facade_v20n_walk_both_directions(
                viewport,
                outer_paths,
                selected,
                source_to_mm,
            )
        )

        # Draw forward and reverse separately.
        forward_counts = (
            _plan3d_facade_v19_draw_sector_paths(
                viewport,
                floor_name,
                walked["forward"],
            )
        )

        reverse_counts = (
            _plan3d_facade_v19_draw_sector_paths(
                viewport,
                floor_name,
                walked["reverse"],
            )
        )

        results[
            floor_name
        ] = {
            "forward_counts":
                forward_counts,
            "reverse_counts":
                reverse_counts,
            "forward_closed":
                bool(
                    walked[
                        "forward"
                    ].get(
                        "closed",
                        False,
                    )
                ),
            "reverse_closed":
                bool(
                    walked[
                        "reverse"
                    ].get(
                        "closed",
                        False,
                    )
                ),
        }

        print(
            "PLAN3D FACADE V20N |",
            floor_name,
            "| TRUE_REVERSE_ORDER=ON",
            "| LTR_segments=",
            len(
                walked[
                    "forward"
                ].get(
                    "segments",
                    [],
                )
            ),
            "| RTL_segments=",
            len(
                walked[
                    "reverse"
                ].get(
                    "segments",
                    [],
                )
            ),
            "| forward_closed=",
            walked[
                "forward"
            ].get(
                "closed",
                False,
            ),
            "| reverse_closed=",
            walked[
                "reverse"
            ].get(
                "closed",
                False,
            ),
            flush=True,
        )

    self._facade_analysis_v20n = (
        results
    )

    self.selection_status.setText(
        "Facade Analysis: LTR and true reversed RTL perimeter sequences ready for facade matching."
    )

    return results



# ============================================================
# PLAN3D_FACADE_SLIDING_DOOR_CONTINUITY_V20O
#
# EXACT RULE:
# Sliding Door lines must NOT stop facade-matching line continuity.
#
# - Existing V20N perimeter logic stays unchanged.
# - Only Sliding Door opening bridge paths are added to the walk paths.
# - The facade line crosses the Sliding Door area and continues.
# - Same behavior is inherited by the true reverse (RTL) sequence.
# ============================================================


def _plan3d_facade_v20o_sliding_bridge_paths(
    viewport,
    rect_values,
    wall_paths,
    source_to_mm,
):
    from floor_area_runtime import (
        _symbol_opening_bridge_paths,
    )

    result = []

    try:
        paths, metadata, _stats = (
            _symbol_opening_bridge_paths(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )
    except Exception as exc:
        print(
            "PLAN3D FACADE V20O | sliding resolver warning:",
            exc,
            flush=True,
        )
        return result

    for path, meta in zip(
        list(paths or []),
        list(metadata or []),
    ):
        semantic = str(
            (meta or {}).get(
                "semantic_type",
                "",
            )
            or ""
        ).casefold()

        if (
            "sliding" not in semantic
            and "sürg" not in semantic
        ):
            continue

        points = []

        for point in list(path or []):
            try:
                points.append(
                    (
                        float(point[0]),
                        float(point[1]),
                    )
                )
            except Exception:
                continue

        if len(points) < 2:
            continue

        for index in range(
            len(points) - 1
        ):
            a = tuple(points[index])
            b = tuple(points[index + 1])

            if (
                abs(b[0] - a[0])
                + abs(b[1] - a[1])
            ) <= 1.0e-9:
                continue

            result.append(
                [
                    a,
                    b,
                ]
            )

    return result


def _plan3d_run_facade_sliding_door_continuity_v20o(
    self,
):
    from floor_area_runtime import (
        _export_prepared_wall_paths,
    )

    from plan3d_canonical_export import (
        _cad_unit_info,
    )

    page = self.parentWidget()

    viewport = (
        getattr(
            page,
            "viewport",
            None,
        )
        if page is not None
        else None
    )

    if viewport is None:
        raise RuntimeError(
            "Facade Analysis: viewport unavailable."
        )

    _plan3d_clear_facade_bottom_left_preview_v1(
        viewport
    )

    values = self.values()

    assignments = dict(
        (
            values.get(
                "assignments",
                {},
            )
            or {}
        ).get(
            "floor_plans",
            {},
        )
        or {}
    )

    floor_settings = dict(
        values.get(
            "floor_settings",
            {},
        )
        or {}
    )

    pivot_map = dict(
        getattr(
            self,
            "_floor_pivots",
            {},
        )
        or {}
    )

    units_info = _cad_unit_info(
        viewport
    )

    source_to_mm = (
        float(
            units_info.get(
                "to_cm",
                1.0,
            )
            or 1.0
        )
        * 10.0
    )

    results = {}

    for floor_name, rect_values in assignments.items():
        floor_name = str(
            floor_name
        )

        floor_geometry = (
            _plan3d_facade_v13_visible_floor_geometry(
                viewport,
                rect_values,
            )
        )

        if floor_geometry is None:
            continue

        settings = dict(
            floor_settings.get(
                floor_name,
                {},
            )
            or {}
        )

        pivot = dict(
            pivot_map.get(
                floor_name,
                {},
            )
            or {}
        )

        (
            wall_paths,
            _wall_topology,
            _export_floor,
        ) = _export_prepared_wall_paths(
            viewport,
            floor_name,
            rect_values,
            pivot,
            settings,
            units_info,
        )

        (
            outer_paths,
            _validated_pairs,
            _all_pairs,
        ) = _plan3d_facade_v16_outer_paths(
            wall_paths,
            floor_geometry,
            source_to_mm,
        )

        sliding_paths = (
            _plan3d_facade_v20o_sliding_bridge_paths(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )

        walk_paths = (
            list(
                outer_paths
                or []
            )
            + list(
                sliding_paths
                or []
            )
        )

        selected = (
            _plan3d_find_bottom_left_export_segment_v1(
                viewport,
                walk_paths,
            )
        )

        if selected is None:
            continue

        walked = (
            _plan3d_facade_v20n_walk_both_directions(
                viewport,
                walk_paths,
                selected,
                source_to_mm,
            )
        )

        forward_counts = (
            _plan3d_facade_v19_draw_sector_paths(
                viewport,
                floor_name,
                walked["forward"],
            )
        )

        reverse_counts = (
            _plan3d_facade_v19_draw_sector_paths(
                viewport,
                floor_name,
                walked["reverse"],
            )
        )

        results[
            floor_name
        ] = {
            "forward_counts":
                forward_counts,
            "reverse_counts":
                reverse_counts,
            "sliding_bridge_segments":
                int(
                    len(
                        sliding_paths
                    )
                ),
            "forward_closed":
                bool(
                    walked[
                        "forward"
                    ].get(
                        "closed",
                        False,
                    )
                ),
            "reverse_closed":
                bool(
                    walked[
                        "reverse"
                    ].get(
                        "closed",
                        False,
                    )
                ),
        }

        print(
            "PLAN3D FACADE V20O |",
            floor_name,
            "| SLIDING_DOOR_CONTINUITY=ON",
            "| sliding_bridge_segments=",
            len(
                sliding_paths
            ),
            "| LTR_segments=",
            len(
                walked[
                    "forward"
                ].get(
                    "segments",
                    [],
                )
            ),
            "| RTL_segments=",
            len(
                walked[
                    "reverse"
                ].get(
                    "segments",
                    [],
                )
            ),
            flush=True,
        )

    self._facade_analysis_v20o = (
        results
    )

    self.selection_status.setText(
        "Facade Analysis: Sliding Door does not stop facade-matching continuity."
    )

    return results



# ============================================================
# PLAN3D_FACADE_WINDOW_CONTINUITY_V20P
#
# EXACT RULE:
# Window lines must NOT stop facade-matching line continuity.
#
# - Existing V20O Sliding Door continuity stays unchanged.
# - Only Window opening bridge paths are added to the walk paths.
# - The facade line crosses the Window area and continues.
# - Same behavior applies to both LTR and true reversed RTL sequences.
# ============================================================


def _plan3d_facade_v20p_window_bridge_paths(
    viewport,
    rect_values,
    wall_paths,
    source_to_mm,
):
    from floor_area_runtime import (
        _symbol_opening_bridge_paths,
    )

    result = []

    try:
        paths, metadata, _stats = (
            _symbol_opening_bridge_paths(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )
    except Exception as exc:
        print(
            "PLAN3D FACADE V20P | window resolver warning:",
            exc,
            flush=True,
        )
        return result

    for path, meta in zip(
        list(paths or []),
        list(metadata or []),
    ):
        semantic = str(
            (meta or {}).get(
                "semantic_type",
                "",
            )
            or ""
        ).casefold()

        if "window" not in semantic and "pencere" not in semantic:
            continue

        points = []

        for point in list(path or []):
            try:
                points.append(
                    (
                        float(point[0]),
                        float(point[1]),
                    )
                )
            except Exception:
                continue

        if len(points) < 2:
            continue

        for index in range(
            len(points) - 1
        ):
            a = tuple(points[index])
            b = tuple(points[index + 1])

            if (
                abs(b[0] - a[0])
                + abs(b[1] - a[1])
            ) <= 1.0e-9:
                continue

            result.append(
                [
                    a,
                    b,
                ]
            )

    return result


def _plan3d_run_facade_window_continuity_v20p(
    self,
):
    from floor_area_runtime import (
        _export_prepared_wall_paths,
    )

    from plan3d_canonical_export import (
        _cad_unit_info,
    )

    page = self.parentWidget()

    viewport = (
        getattr(
            page,
            "viewport",
            None,
        )
        if page is not None
        else None
    )

    if viewport is None:
        raise RuntimeError(
            "Facade Analysis: viewport unavailable."
        )

    _plan3d_clear_facade_bottom_left_preview_v1(
        viewport
    )

    values = self.values()

    assignments = dict(
        (
            values.get(
                "assignments",
                {},
            )
            or {}
        ).get(
            "floor_plans",
            {},
        )
        or {}
    )

    floor_settings = dict(
        values.get(
            "floor_settings",
            {},
        )
        or {}
    )

    pivot_map = dict(
        getattr(
            self,
            "_floor_pivots",
            {},
        )
        or {}
    )

    units_info = _cad_unit_info(
        viewport
    )

    source_to_mm = (
        float(
            units_info.get(
                "to_cm",
                1.0,
            )
            or 1.0
        )
        * 10.0
    )

    results = {}

    for floor_name, rect_values in assignments.items():
        floor_name = str(
            floor_name
        )

        floor_geometry = (
            _plan3d_facade_v13_visible_floor_geometry(
                viewport,
                rect_values,
            )
        )

        if floor_geometry is None:
            continue

        settings = dict(
            floor_settings.get(
                floor_name,
                {},
            )
            or {}
        )

        pivot = dict(
            pivot_map.get(
                floor_name,
                {},
            )
            or {}
        )

        (
            wall_paths,
            _wall_topology,
            _export_floor,
        ) = _export_prepared_wall_paths(
            viewport,
            floor_name,
            rect_values,
            pivot,
            settings,
            units_info,
        )

        (
            outer_paths,
            _validated_pairs,
            _all_pairs,
        ) = _plan3d_facade_v16_outer_paths(
            wall_paths,
            floor_geometry,
            source_to_mm,
        )

        sliding_paths = (
            _plan3d_facade_v20o_sliding_bridge_paths(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )

        window_paths = (
            _plan3d_facade_v20p_window_bridge_paths(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )

        walk_paths = (
            list(
                outer_paths
                or []
            )
            + list(
                sliding_paths
                or []
            )
            + list(
                window_paths
                or []
            )
        )

        selected = (
            _plan3d_find_bottom_left_export_segment_v1(
                viewport,
                walk_paths,
            )
        )

        if selected is None:
            continue

        walked = (
            _plan3d_facade_v20n_walk_both_directions(
                viewport,
                walk_paths,
                selected,
                source_to_mm,
            )
        )

        forward_counts = (
            _plan3d_facade_v19_draw_sector_paths(
                viewport,
                floor_name,
                walked["forward"],
            )
        )

        reverse_counts = (
            _plan3d_facade_v19_draw_sector_paths(
                viewport,
                floor_name,
                walked["reverse"],
            )
        )

        results[
            floor_name
        ] = {
            "forward_counts":
                forward_counts,
            "reverse_counts":
                reverse_counts,
            "sliding_bridge_segments":
                int(
                    len(
                        sliding_paths
                    )
                ),
            "window_bridge_segments":
                int(
                    len(
                        window_paths
                    )
                ),
            "forward_closed":
                bool(
                    walked[
                        "forward"
                    ].get(
                        "closed",
                        False,
                    )
                ),
            "reverse_closed":
                bool(
                    walked[
                        "reverse"
                    ].get(
                        "closed",
                        False,
                    )
                ),
        }

        print(
            "PLAN3D FACADE V20P |",
            floor_name,
            "| WINDOW_CONTINUITY=ON",
            "| window_bridge_segments=",
            len(
                window_paths
            ),
            "| sliding_bridge_segments=",
            len(
                sliding_paths
            ),
            "| LTR_segments=",
            len(
                walked[
                    "forward"
                ].get(
                    "segments",
                    [],
                )
            ),
            "| RTL_segments=",
            len(
                walked[
                    "reverse"
                ].get(
                    "segments",
                    [],
                )
            ),
            flush=True,
        )

    self._facade_analysis_v20p = (
        results
    )

    self.selection_status.setText(
        "Facade Analysis: Window and Sliding Door do not stop facade-matching continuity."
    )

    return results



# ============================================================
# PLAN3D_FACADE_WINDOW_USE_SLIDING_REACTION_V20Q
#
# EXACT RULE:
# Window must use THE SAME continuity reaction as Sliding Door.
#
# No separate Window continuation algorithm.
# No straight blind pass.
#
# Sliding Door + Window are resolved by the SAME opening-bridge
# function and inserted into the SAME facade walk path.
# ============================================================


def _plan3d_facade_v20q_opening_bridge_paths(
    viewport,
    rect_values,
    wall_paths,
    source_to_mm,
):
    from floor_area_runtime import (
        _symbol_opening_bridge_paths,
    )

    result = []
    sliding_count = 0
    window_count = 0

    try:
        paths, metadata, _stats = (
            _symbol_opening_bridge_paths(
                viewport,
                rect_values,
                wall_paths,
                source_to_mm,
            )
        )
    except Exception as exc:
        print(
            "PLAN3D FACADE V20Q | opening resolver warning:",
            exc,
            flush=True,
        )
        return result, 0, 0

    for path, meta in zip(
        list(paths or []),
        list(metadata or []),
    ):
        semantic = str(
            (meta or {}).get(
                "semantic_type",
                "",
            )
            or ""
        ).casefold()

        is_sliding = (
            "sliding" in semantic
            or "sürg" in semantic
        )

        is_window = (
            "window" in semantic
            or "pencere" in semantic
        )

        if not (
            is_sliding
            or is_window
        ):
            continue

        points = []

        for point in list(
            path or []
        ):
            try:
                points.append(
                    (
                        float(point[0]),
                        float(point[1]),
                    )
                )
            except Exception:
                continue

        if len(points) < 2:
            continue

        added = 0

        for index in range(
            len(points) - 1
        ):
            a = tuple(
                points[index]
            )
            b = tuple(
                points[index + 1]
            )

            if (
                abs(
                    b[0] - a[0]
                )
                + abs(
                    b[1] - a[1]
                )
            ) <= 1.0e-9:
                continue

            result.append(
                [
                    a,
                    b,
                ]
            )

            added += 1

        if added:
            if is_sliding:
                sliding_count += added

            if is_window:
                window_count += added

    return (
        result,
        int(sliding_count),
        int(window_count),
    )


def _plan3d_run_facade_window_use_sliding_reaction_v20q(
    self,
):
    from floor_area_runtime import (
        _export_prepared_wall_paths,
    )

    from plan3d_canonical_export import (
        _cad_unit_info,
    )

    page = self.parentWidget()

    viewport = (
        getattr(
            page,
            "viewport",
            None,
        )
        if page is not None
        else None
    )

    if viewport is None:
        raise RuntimeError(
            "Facade Analysis: viewport unavailable."
        )

    _plan3d_clear_facade_bottom_left_preview_v1(
        viewport
    )

    values = self.values()

    assignments = dict(
        (
            values.get(
                "assignments",
                {},
            )
            or {}
        ).get(
            "floor_plans",
            {},
        )
        or {}
    )

    floor_settings = dict(
        values.get(
            "floor_settings",
            {},
        )
        or {}
    )

    pivot_map = dict(
        getattr(
            self,
            "_floor_pivots",
            {},
        )
        or {}
    )

    units_info = _cad_unit_info(
        viewport
    )

    source_to_mm = (
        float(
            units_info.get(
                "to_cm",
                1.0,
            )
            or 1.0
        )
        * 10.0
    )

    results = {}

    for floor_name, rect_values in assignments.items():
        floor_name = str(
            floor_name
        )

        floor_geometry = (
            _plan3d_facade_v13_visible_floor_geometry(
                viewport,
                rect_values,
            )
        )

        if floor_geometry is None:
            continue

        settings = dict(
            floor_settings.get(
                floor_name,
                {},
            )
            or {}
        )

        pivot = dict(
            pivot_map.get(
                floor_name,
                {},
            )
            or {}
        )

        (
            wall_paths,
            _wall_topology,
            _export_floor,
        ) = _export_prepared_wall_paths(
            viewport,
            floor_name,
            rect_values,
            pivot,
            settings,
            units_info,
        )

        (
            outer_paths,
            _validated_pairs,
            _all_pairs,
        ) = _plan3d_facade_v16_outer_paths(
            wall_paths,
            floor_geometry,
            source_to_mm,
        )

        (
            opening_paths,
            sliding_count,
            window_count,
        ) = _plan3d_facade_v20q_opening_bridge_paths(
            viewport,
            rect_values,
            wall_paths,
            source_to_mm,
        )

        # SAME PATH / SAME REACTION for Sliding Door and Window.
        walk_paths = (
            list(
                outer_paths
                or []
            )
            + list(
                opening_paths
                or []
            )
        )

        selected = (
            _plan3d_find_bottom_left_export_segment_v1(
                viewport,
                walk_paths,
            )
        )

        if selected is None:
            continue

        walked = (
            _plan3d_facade_v20n_walk_both_directions(
                viewport,
                walk_paths,
                selected,
                source_to_mm,
            )
        )

        forward_counts = (
            _plan3d_facade_v19_draw_sector_paths(
                viewport,
                floor_name,
                walked["forward"],
            )
        )

        reverse_counts = (
            _plan3d_facade_v19_draw_sector_paths(
                viewport,
                floor_name,
                walked["reverse"],
            )
        )

        results[
            floor_name
        ] = {
            "forward_counts":
                forward_counts,
            "reverse_counts":
                reverse_counts,
            "sliding_bridge_segments":
                int(
                    sliding_count
                ),
            "window_bridge_segments":
                int(
                    window_count
                ),
        }

        print(
            "PLAN3D FACADE V20Q |",
            floor_name,
            "| WINDOW_REACTION=SAME_AS_SLIDING_DOOR",
            "| sliding_segments=",
            sliding_count,
            "| window_segments=",
            window_count,
            "| LTR_segments=",
            len(
                walked[
                    "forward"
                ].get(
                    "segments",
                    [],
                )
            ),
            "| RTL_segments=",
            len(
                walked[
                    "reverse"
                ].get(
                    "segments",
                    [],
                )
            ),
            flush=True,
        )

    self._facade_analysis_v20q = (
        results
    )

    self.selection_status.setText(
        "Facade Analysis: Window uses the same continuity reaction as Sliding Door."
    )

    return results



# ============================================================
# PLAN3D_FACADE_PLAN_MATCH_V20R
#
# PURPOSE:
# Match the current floor-plan facade perimeter to the confirmed
# Front / Right / Rear / Left facade assignments.
#
# Existing facade continuity rules remain unchanged:
# - Wall perimeter = current V20Q source
# - Sliding Door does not stop continuity
# - Window uses the same continuity reaction as Sliding Door
# - LTR and true reversed RTL sequences are preserved
#
# MATCH RULE:
#   FRONT -> confirmed Facade "Front"
#   RIGHT -> confirmed Facade "Right"
#   REAR  -> confirmed Facade "Rear"
#   LEFT  -> confirmed Facade "Left"
#
# The RTL sequence is the reverse traversal of the SAME physical
# plan perimeter. Canonical facade identity is copied from the
# corresponding LTR physical segment; travel direction does not
# rename the facade.
# ============================================================


def _plan3d_facade_v20r_segment_key(a, b):
    p1 = (
        round(float(a[0]), 6),
        round(float(a[1]), 6),
    )
    p2 = (
        round(float(b[0]), 6),
        round(float(b[1]), 6),
    )

    return tuple(
        sorted(
            (
                p1,
                p2,
            )
        )
    )


def _plan3d_facade_v20r_facade_assignment(
    facade_assignments,
    wanted,
):
    wanted_fold = str(
        wanted
    ).strip().casefold()

    for name, rect in dict(
        facade_assignments
        or {}
    ).items():
        if str(
            name
        ).strip().casefold() == wanted_fold:
            return (
                str(name),
                list(rect),
            )

    return (
        None,
        None,
    )


def _plan3d_facade_v20r_group_sequences(
    walked,
):
    forward = list(
        walked.get(
            "forward",
            {}
        ).get(
            "segments",
            [],
        )
        or []
    )

    reverse = list(
        walked.get(
            "reverse",
            {}
        ).get(
            "segments",
            [],
        )
        or []
    )

    canonical_by_geometry = {}

    for row in forward:
        key = (
            _plan3d_facade_v20r_segment_key(
                row["a"],
                row["b"],
            )
        )

        canonical_by_geometry[
            key
        ] = str(
            row.get(
                "sector",
                ""
            )
            or ""
        ).upper()

    result = {
        "FRONT": {
            "ltr": [],
            "rtl": [],
        },
        "RIGHT": {
            "ltr": [],
            "rtl": [],
        },
        "REAR": {
            "ltr": [],
            "rtl": [],
        },
        "LEFT": {
            "ltr": [],
            "rtl": [],
        },
    }

    for index, row in enumerate(
        forward
    ):
        side = str(
            row.get(
                "sector",
                ""
            )
            or ""
        ).upper()

        if side not in result:
            continue

        result[
            side
        ][
            "ltr"
        ].append(
            {
                "index":
                    int(index),
                "a":
                    [
                        float(
                            row["a"][0]
                        ),
                        float(
                            row["a"][1]
                        ),
                    ],
                "b":
                    [
                        float(
                            row["b"][0]
                        ),
                        float(
                            row["b"][1]
                        ),
                    ],
            }
        )

    for index, row in enumerate(
        reverse
    ):
        key = (
            _plan3d_facade_v20r_segment_key(
                row["a"],
                row["b"],
            )
        )

        # Same physical segment = same facade identity.
        side = canonical_by_geometry.get(
            key
        )

        if side not in result:
            continue

        result[
            side
        ][
            "rtl"
        ].append(
            {
                "index":
                    int(index),
                "a":
                    [
                        float(
                            row["a"][0]
                        ),
                        float(
                            row["a"][1]
                        ),
                    ],
                "b":
                    [
                        float(
                            row["b"][0]
                        ),
                        float(
                            row["b"][1]
                        ),
                    ],
            }
        )

    return result


def _plan3d_run_facade_plan_match_v20r(
    self,
):
    from floor_area_runtime import (
        _export_prepared_wall_paths,
    )

    from plan3d_canonical_export import (
        _cad_unit_info,
    )

    page = self.parentWidget()

    viewport = (
        getattr(
            page,
            "viewport",
            None,
        )
        if page is not None
        else None
    )

    if viewport is None:
        raise RuntimeError(
            "Facade Analysis: viewport unavailable."
        )

    _plan3d_clear_facade_bottom_left_preview_v1(
        viewport
    )

    values = self.values()

    assignments = dict(
        values.get(
            "assignments",
            {},
        )
        or {}
    )

    floor_assignments = dict(
        assignments.get(
            "floor_plans",
            {},
        )
        or {}
    )

    facade_assignments = dict(
        assignments.get(
            "facades",
            {},
        )
        or {}
    )

    floor_settings = dict(
        values.get(
            "floor_settings",
            {},
        )
        or {}
    )

    pivot_map = dict(
        getattr(
            self,
            "_floor_pivots",
            {},
        )
        or {}
    )

    units_info = _cad_unit_info(
        viewport
    )

    source_to_mm = (
        float(
            units_info.get(
                "to_cm",
                1.0,
            )
            or 1.0
        )
        * 10.0
    )

    side_specs = (
        (
            "FRONT",
            "Front",
            "RED",
        ),
        (
            "RIGHT",
            "Right",
            "GREEN",
        ),
        (
            "REAR",
            "Rear",
            "BLUE",
        ),
        (
            "LEFT",
            "Left",
            "YELLOW",
        ),
    )

    match_results = {
        "version": "V20R",
        "rule":
            "canonical plan facade side -> confirmed same-name facade assignment",
        "floors": {},
    }

    for floor_name, rect_values in floor_assignments.items():
        floor_name = str(
            floor_name
        )

        floor_geometry = (
            _plan3d_facade_v13_visible_floor_geometry(
                viewport,
                rect_values,
            )
        )

        if floor_geometry is None:
            print(
                "PLAN3D FACADE MATCH V20R |",
                floor_name,
                "| result=NO_FLOOR_REFERENCE",
                flush=True,
            )
            continue

        settings = dict(
            floor_settings.get(
                floor_name,
                {},
            )
            or {}
        )

        pivot = dict(
            pivot_map.get(
                floor_name,
                {},
            )
            or {}
        )

        (
            wall_paths,
            _wall_topology,
            _export_floor,
        ) = _export_prepared_wall_paths(
            viewport,
            floor_name,
            rect_values,
            pivot,
            settings,
            units_info,
        )

        (
            outer_paths,
            _validated_pairs,
            _all_pairs,
        ) = _plan3d_facade_v16_outer_paths(
            wall_paths,
            floor_geometry,
            source_to_mm,
        )

        (
            opening_paths,
            sliding_count,
            window_count,
        ) = _plan3d_facade_v20q_opening_bridge_paths(
            viewport,
            rect_values,
            wall_paths,
            source_to_mm,
        )

        walk_paths = (
            list(
                outer_paths
                or []
            )
            + list(
                opening_paths
                or []
            )
        )

        selected = (
            _plan3d_find_bottom_left_export_segment_v1(
                viewport,
                walk_paths,
            )
        )

        if selected is None:
            print(
                "PLAN3D FACADE MATCH V20R |",
                floor_name,
                "| result=NO_START",
                flush=True,
            )
            continue

        walked = (
            _plan3d_facade_v20n_walk_both_directions(
                viewport,
                walk_paths,
                selected,
                source_to_mm,
            )
        )

        # Keep the current colored plan-perimeter visualization.
        _plan3d_facade_v19_draw_sector_paths(
            viewport,
            floor_name,
            walked[
                "forward"
            ],
        )

        grouped = (
            _plan3d_facade_v20r_group_sequences(
                walked
            )
        )

        floor_match = {
            "floor_name":
                floor_name,
            "sides": {},
            "window_bridge_segments":
                int(
                    window_count
                ),
            "sliding_bridge_segments":
                int(
                    sliding_count
                ),
        }

        for (
            side_key,
            facade_name,
            color_name,
        ) in side_specs:
            confirmed_name, facade_rect = (
                _plan3d_facade_v20r_facade_assignment(
                    facade_assignments,
                    facade_name,
                )
            )

            sequences = grouped[
                side_key
            ]

            matched = bool(
                confirmed_name is not None
                and (
                    sequences[
                        "ltr"
                    ]
                    or sequences[
                        "rtl"
                    ]
                )
            )

            floor_match[
                "sides"
            ][
                facade_name
            ] = {
                "matched":
                    matched,
                "color":
                    color_name,
                "facade_assignment":
                    confirmed_name,
                "facade_rect":
                    facade_rect,
                "plan_ltr_segments":
                    sequences[
                        "ltr"
                    ],
                "plan_rtl_segments":
                    sequences[
                        "rtl"
                    ],
            }

            print(
                "PLAN3D FACADE MATCH V20R |",
                floor_name,
                "|",
                facade_name,
                "| matched=",
                matched,
                "| LTR=",
                len(
                    sequences[
                        "ltr"
                    ]
                ),
                "| RTL=",
                len(
                    sequences[
                        "rtl"
                    ]
                ),
                "| facade_assignment=",
                confirmed_name,
                flush=True,
            )

        match_results[
            "floors"
        ][
            floor_name
        ] = floor_match

    self._analysis_results[
        "facade_plan_matching_v20r"
    ] = match_results

    self._facade_plan_matching_v20r = (
        match_results
    )

    if page is not None:
        page._export_details = (
            self.values()
        )

    matched_count = 0
    total_count = 0

    for floor_data in match_results[
        "floors"
    ].values():
        for side_data in floor_data[
            "sides"
        ].values():
            total_count += 1

            if side_data.get(
                "matched",
                False,
            ):
                matched_count += 1

    self.selection_status.setText(
        "Facade Analysis: "
        + str(
            matched_count
        )
        + "/"
        + str(
            total_count
        )
        + " floor/facade side matches."
    )

    print(
        "PLAN3D FACADE MATCH V20R COMPLETE | matched=",
        matched_count,
        "| total=",
        total_count,
        flush=True,
    )

    return match_results



# ============================================================

# ============================================================
# GROUND FLOOR OPENING PIPELINE
#
# Authoritative rules:
# - C Ölçü global lowest horizontal line is Z=0.
# - Only Ground Floor opening heights are produced here.
# - Window / Door / Sliding Door semantics come from CAD layer assignments.
# - Ground membership is decided by the opening centre relative to Z=0.
# - Heights are measured directly upward from Z=0; no facade-local datum,
#   entrance offset, lattice fit, legacy height cache, or secondary reanalysis.
# ============================================================


def _ground_opening_datum(viewport):
    finder = getattr(viewport, "find_facade_height_reference_lines", None)
    if not callable(finder):
        raise RuntimeError("Ground opening datum finder is unavailable.")

    try:
        rows = finder(None)
    except TypeError:
        rows = finder()

    rows = [
        dict(row)
        for row in list(rows or [])
        if isinstance(row, dict) and row.get("y") is not None
    ]
    if not rows:
        raise RuntimeError('No horizontal datum line found on layer "C Ölçü".')

    rows.sort(key=lambda row: float(row["y"]))
    datum = dict(rows[0])

    show = getattr(viewport, "show_facade_height_reference_lines", None)
    if callable(show):
        show([datum])

    return datum


def _ground_floor_contract(panel):
    settings_map = dict(getattr(panel, "_floor_settings", {}) or {})
    assignments = dict(getattr(panel, "_assignments", {}) or {})
    floor_plans = dict(assignments.get("floor_plans", {}) or {})

    names = []
    for source in (floor_plans.keys(), settings_map.keys()):
        for name in source:
            name = str(name)
            if name not in names:
                names.append(name)

    if not names:
        raise RuntimeError("Ground floor assignment is unavailable.")

    ranked = []
    for order, name in enumerate(names):
        settings = dict(settings_map.get(name, {}) or {})
        try:
            elevation = float(settings.get("floor_elevation_cm", 0.0) or 0.0)
        except Exception:
            elevation = 0.0
        ranked.append((abs(elevation), order, name, settings))

    ranked.sort(key=lambda row: (row[0], row[1]))
    _distance, _order, floor_name, settings = ranked[0]

    wall_height_cm = float(
        settings.get(
            "wall_height_cm",
            settings.get("floor_height_cm", 280.0),
        )
        or 280.0
    )
    floor_to_floor_cm = float(
        settings.get(
            "floor_to_floor_cm",
            wall_height_cm,
        )
        or wall_height_cm
    )
    if floor_to_floor_cm < wall_height_cm:
        floor_to_floor_cm = wall_height_cm

    return {
        "floor_name": str(floor_name),
        "wall_height_cm": float(wall_height_cm),
        "floor_to_floor_cm": float(floor_to_floor_cm),
    }

def _group_ground_openings(
    logical_openings,
    datum_y,
    cad_to_cm,
    ground_limit_cm,
):
    """Use the facade detector's logical openings; only classify Ground here."""
    allowed = {"Window", "Door", "Sliding Door"}
    tolerance_cm = 2.0
    openings = []

    for source in list(logical_openings or []):
        if not isinstance(source, dict):
            continue

        semantic = str(source.get("semantic_type", "") or "")
        if semantic not in allowed:
            continue

        bbox = source.get("bbox")
        if not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
            continue

        try:
            x0, y0, x1, y1 = [float(bbox[index]) for index in range(4)]
        except Exception:
            continue

        x0, x1 = min(x0, x1), max(x0, x1)
        y0, y1 = min(y0, y1), max(y0, y1)
        if x1 - x0 <= 1.0e-9 or y1 - y0 <= 1.0e-9:
            continue

        bottom_cm = (y0 - datum_y) * cad_to_cm
        top_cm = (y1 - datum_y) * cad_to_cm
        center_cm = (((y0 + y1) * 0.5) - datum_y) * cad_to_cm

        if center_cm < -tolerance_cm:
            continue
        if center_cm >= ground_limit_cm + tolerance_cm:
            continue
        if top_cm <= bottom_cm + 1.0e-6:
            continue

        row = dict(source)
        row.update({
            "semantic_type": semantic,
            "bbox": [x0, y0, x1, y1],
            "center": [(x0 + x1) * 0.5, (y0 + y1) * 0.5],
            "cad_width": float(x1 - x0),
            "drawing_bottom_y": float(y0),
            "drawing_top_y": float(y1),
            "floor_local_sill_cm": float(bottom_cm),
            "floor_local_top_cm": float(top_cm),
            "height_cm": float(top_cm - bottom_cm),
            "sill_z_cm": float(bottom_cm),
            "top_z_cm": float(top_cm),
            "datum_y": float(datum_y),
            "datum_source": "C Ölçü",
        })
        openings.append(row)

    openings.sort(
        key=lambda row: (
            float(row["center"][0]),
            float(row["center"][1]),
        )
    )
    return openings


def _clear_ground_opening_overlay(viewport):
    scene = viewport.scene()
    items = list(getattr(viewport, "_plan3d_ground_opening_items", []) or [])
    if scene is not None:
        for item in items:
            try:
                scene.removeItem(item)
            except Exception:
                pass
    viewport._plan3d_ground_opening_items = []


def _draw_ground_opening_overlay(viewport, result):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPen
    from PySide6.QtWidgets import QGraphicsRectItem

    _clear_ground_opening_overlay(viewport)
    scene = viewport.scene()
    if scene is None:
        return

    colors = {
        "Window": "#FF3B30",
        "Door": "#49B96E",
        "Sliding Door": "#1F7A4D",
    }
    items = []

    for _facade_name, payload in dict(result.get("facades", {}) or {}).items():
        for key, semantic in (
            ("windows", "Window"),
            ("doors", "Door"),
            ("sliding_doors", "Sliding Door"),
        ):
            pen = QPen(QColor(colors[semantic]))
            pen.setCosmetic(True)
            pen.setWidthF(3.0)
            for row in list(dict(payload or {}).get(key, []) or []):
                bbox = row.get("bbox")
                if not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
                    continue
                x0, y0, x1, y1 = [float(v) for v in bbox[:4]]
                item = QGraphicsRectItem(x0, y0, x1 - x0, y1 - y0)
                item.setPen(pen)
                item.setBrush(Qt.BrushStyle.NoBrush)
                item.setZValue(5000200.0)
                scene.addItem(item)
                items.append(item)

    viewport._plan3d_ground_opening_items = items
    print(
        "PLAN3D GROUND OPENING OVERLAY | items=",
        len(items),
        "| windows=RED | doors=GREEN | sliding=DARK_GREEN",
        flush=True,
    )

def _analyze_ground_openings(panel, viewport):
    from plan3d_canonical_export import _cad_unit_info

    datum = _ground_opening_datum(viewport)
    datum_y = float(datum["y"])

    unit_info = _cad_unit_info(viewport)
    cad_to_cm = float(unit_info.get("to_cm", 0.0) or 0.0)
    if cad_to_cm <= 1.0e-12:
        raise RuntimeError("CAD to cm scale is unavailable.")

    ground = _ground_floor_contract(panel)
    floor_name = str(ground["floor_name"])
    wall_height_cm = float(ground["wall_height_cm"])
    ground_limit_cm = float(ground["floor_to_floor_cm"])

    assignments = dict(getattr(panel, "_assignments", {}) or {})
    facade_assignments = dict(assignments.get("facades", {}) or {})
    floor_settings = dict(getattr(panel, "_floor_settings", {}) or {})

    missing = [
        name
        for name in ("Front", "Right", "Rear", "Left")
        if facade_assignments.get(name) is None
    ]
    if missing:
        raise RuntimeError(
            "Facade assignment missing: " + ", ".join(missing)
        )

    facades = {}
    totals = {"windows": 0, "doors": 0, "sliding_doors": 0}

    for facade_name in ("Front", "Right", "Rear", "Left"):
        rect_values = facade_assignments[facade_name]
        payload = viewport.analyze_facade_matching_inputs(
            rect_values,
            floor_settings,
        )
        payload = dict(payload or {})
        logical_openings = list(payload.get("logical_openings", []) or [])

        if not logical_openings:
            raise RuntimeError(
                "Facade opening detector returned no logical openings for "
                + facade_name
            )

        opening_source = _group_ground_openings(
            logical_openings,
            datum_y,
            cad_to_cm,
            ground_limit_cm,
        )

        windows = [
            dict(row)
            for row in opening_source
            if row.get("semantic_type") == "Window"
        ]
        doors = [
            dict(row)
            for row in opening_source
            if row.get("semantic_type") == "Door"
        ]
        sliding_doors = [
            dict(row)
            for row in opening_source
            if row.get("semantic_type") == "Sliding Door"
        ]

        for rows in (windows, doors, sliding_doors):
            for row in rows:
                row["facade"] = facade_name
                row["floor_name"] = floor_name

        facades[facade_name] = {
            "windows": windows,
            "doors": doors,
            "sliding_doors": sliding_doors,
        }

        totals["windows"] += len(windows)
        totals["doors"] += len(doors)
        totals["sliding_doors"] += len(sliding_doors)

        print(
            "PLAN3D GROUND OPENINGS |",
            facade_name,
            "| logical_openings=",
            len(logical_openings),
            "| windows=",
            len(windows),
            "| doors=",
            len(doors),
            "| sliding=",
            len(sliding_doors),
            flush=True,
        )

        for semantic_name, rows in (("Window", windows), ("Door", doors), ("Sliding Door", sliding_doors)):
            for index, row in enumerate(rows, start=1):
                print(
                    "PLAN3D GROUND HEIGHT |",
                    facade_name,
                    "|",
                    semantic_name,
                    index,
                    "| bottom_cm=",
                    round(float(row["floor_local_sill_cm"]), 3),
                    "| top_cm=",
                    round(float(row["floor_local_top_cm"]), 3),
                    "| height_cm=",
                    round(float(row["height_cm"]), 3),
                    flush=True,
                )

    result = {
        "engine": "GROUND_OPENING_PIPELINE",
        "scope": "GROUND_FLOOR_ONLY",
        "ground_floor_name": floor_name,
        "wall_height_cm": wall_height_cm,
        "floor_to_floor_cm": ground_limit_cm,
        "cad_to_cm": cad_to_cm,
        "datum_y": datum_y,
        "datum_line": datum,
        "datum_source": "C Ölçü",
        "facades": facades,
        "totals": totals,
    }

    if not isinstance(getattr(panel, "_analysis_results", None), dict):
        panel._analysis_results = {}
    panel._analysis_results["ground_openings"] = result
    panel._ground_openings = result

    print(
        "PLAN3D GROUND OPENING ANALYSIS COMPLETE |",
        "floor=",
        floor_name,
        "| datum_y=",
        format(datum_y, ".6f"),
        "| windows=",
        totals["windows"],
        "| doors=",
        totals["doors"],
        "| sliding=",
        totals["sliding_doors"],
        flush=True,
    )
    return result


def _run_ground_facade_analysis(self):
    page = self.parentWidget()
    viewport = getattr(page, "viewport", None) if page is not None else None
    if viewport is None:
        raise RuntimeError("Facade Analysis: viewport unavailable.")

    ground = _analyze_ground_openings(self, viewport)
    _draw_ground_opening_overlay(viewport, ground)

    if page is not None:
        page._export_details = self.values()

    totals = dict(ground.get("totals", {}) or {})
    self.selection_status.setText(
        "Facade Analysis: Ground Floor | "
        + str(int(totals.get("windows", 0)))
        + " windows | "
        + str(int(totals.get("doors", 0)))
        + " doors | "
        + str(int(totals.get("sliding_doors", 0)))
        + " sliding doors"
    )
    return ground


ExportDetailsPanel.run_facade_analysis = _run_ground_facade_analysis

print(
    "PLAN3D GROUND OPENING PIPELINE ACTIVE | "
    "datum=C_OLCU_LOWEST | floors=GROUND_ONLY | legacy_vertical_pipeline=OFF"
)

