from __future__ import annotations

import tempfile
import time
import math
from pathlib import Path

import ezdxf
from ezdxf import recover
from ezdxf import bbox as ezdxf_bbox
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.config import Configuration
from ezdxf.addons.drawing.pyqt import PyQtBackend

from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import QColor, QPainter, QTransform, QPen, QBrush
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem, QGraphicsScene, QGraphicsSimpleTextItem, QGraphicsView


class CadViewport(QGraphicsView):
    historyStateRequested = Signal(str)
    assignmentRegionSelected = Signal(str, str, object)
    floorPivotCommitted = Signal(str, float, float, str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._document = None
        self._source_path = None
        self._backend = None

        self._layer_items = {}
        self._layer_types = {}
        self._layer_selected = {}
        self._home_rect = QRectF()
        self._user_has_interacted = False
        self._restoring_history = False

        self._panning = False
        self._pan_start = None
        self._pan_moved = False

        self._assignment_mode = False
        self._assignment_kind = ""
        self._assignment_name = ""
        self._assignment_start = None
        self._assignment_preview = None
        self._assignment_overlay_items = []
        self._assignment_confirmed_items = []
        self._assignment_pending_items = []
        self._exterior_analysis_items = []
        self._facade_verification_items = []

        # 3Dcad pivot contract port:
        # - one CAD-source XY pivot per confirmed floor
        # - 14 px snap radius
        # - wall vertex first, wall segment second, otherwise free point
        # - Ground Floor may be marked as master reference by the panel
        self._pivot_edit_enabled = False
        self._pivot_drag_active = False
        self._pivot_floor_name = ""
        self._pivot_point_cad = None
        self._pivot_hover_cad = None
        self._pivot_snap_kind = ""
        self._pivot_reference_geometry = ()
        self._pivot_snap_radius_px = 14.0
        self._floor_pivot_records = {}

        # PLAN3D_PIVOT_MASTER_GUIDE_V3
        self._pivot_guide_geometry = ()
        self._pivot_guide_origin = None
        self._pivot_guide_floor_name = ""

        self.setScene(QGraphicsScene(self))
        self.setBackgroundBrush(QColor("#000000"))
        self.setFrameShape(QGraphicsView.NoFrame)

        self.setRenderHints(
            QPainter.Antialiasing
            | QPainter.TextAntialiasing
            | QPainter.SmoothPixmapTransform
        )

        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.scale(1.0, -1.0)

    @property
    def document(self):
        return self._document

    @property
    def source_path(self):
        return self._source_path

    def clear_drawing(self):
        self.setScene(QGraphicsScene(self))
        self._document = None
        self._source_path = None
        self._backend = None
        self._home_rect = QRectF()
        self._user_has_interacted = False

        self.resetTransform()
        self.scale(1.0, -1.0)

    def load_file(self, file_path: str):
        source_path = Path(file_path)

        if source_path.suffix.lower() == ".dwg":
            dxf_path = self._dwg_to_dxf(source_path)
        else:
            dxf_path = source_path

        try:
            doc = ezdxf.readfile(str(dxf_path))
        except Exception:
            doc, auditor = recover.readfile(str(dxf_path))

            if auditor.has_errors:
                raise RuntimeError(
                    "DXF dosyası okunurken ciddi yapı hataları bulundu."
                )

        self._document = doc
        self._source_path = source_path
        self._user_has_interacted = False

        self._render_document()

    def _render_document(self):
        if self._document is None:
            return

        doc = self._document
        layout = doc.modelspace()

        new_scene = QGraphicsScene(self)

        self._layer_items = {}

        # Preserve previous type / visibility assignments when possible.
        previous_types = dict(self._layer_types)
        previous_selected = dict(self._layer_selected)

        self._layer_types = {}
        self._layer_selected = {}

        layer_names = []

        for layer in doc.layers:
            try:
                name = str(layer.dxf.name)
            except Exception:
                continue

            if name not in layer_names:
                layer_names.append(name)

        # Also include any modelspace layer not found in the table.
        for entity in layout:
            try:
                name = str(entity.dxf.layer)
            except Exception:
                continue

            if name not in layer_names:
                layer_names.append(name)

        layer_names.sort(key=str.lower)

        for layer_name in layer_names:
            self._layer_items[layer_name] = []
            self._layer_types[layer_name] = previous_types.get(
                layer_name,
                "Unassigned",
            )
            self._layer_selected[layer_name] = previous_selected.get(
                layer_name,
                True,
            )

        context = RenderContext(doc)
        context.set_current_layout(layout)

        config = Configuration()

        backend = PyQtBackend(new_scene)

        frontend = Frontend(
            ctx=context,
            out=backend,
            config=config,
        )

        # Render each top-level CAD layer separately so every generated
        # graphics item can be mapped back to its source layer.
        for layer_name in layer_names:
            entities = []

            for entity in layout:
                try:
                    if str(entity.dxf.layer) == layer_name:
                        entities.append(entity)
                except Exception:
                    pass

            if not entities:
                continue

            before_ids = {
                id(item)
                for item in new_scene.items()
            }

            try:
                frontend.draw_entities(entities)
            except Exception:
                # Do not stop the entire drawing for one unsupported entity.
                for entity in entities:
                    try:
                        frontend.draw_entity(entity, 0)
                    except Exception:
                        pass

            after_items = [
                item
                for item in new_scene.items()
                if id(item) not in before_ids
            ]

            self._layer_items[layer_name].extend(
                after_items
            )

        try:
            backend.finalize()
        except Exception:
            pass

        self._backend = backend
        self.setScene(new_scene)

        # Apply layer visibility and semantic display colors.
        for layer_name in layer_names:
            self._apply_layer_style(layer_name)

        rect = new_scene.itemsBoundingRect()

        if rect.isValid() and rect.width() > 0 and rect.height() > 0:
            pad_x = max(
                rect.width() * 0.10,
                50.0,
            )

            pad_y = max(
                rect.height() * 0.10,
                50.0,
            )

            self._home_rect = rect.adjusted(
                -pad_x,
                -pad_y,
                pad_x,
                pad_y,
            )

            center = self._home_rect.center()

            nav_width = max(
                self._home_rect.width() * 100.0,
                100000.0,
            )

            nav_height = max(
                self._home_rect.height() * 100.0,
                100000.0,
            )

            navigation_rect = QRectF(
                center.x() - nav_width / 2.0,
                center.y() - nav_height / 2.0,
                nav_width,
                nav_height,
            )

            new_scene.setSceneRect(
                navigation_rect
            )

            self._apply_home_view()

    def analyze_assignment_regions(self, assignments):
        """Analyze confirmed Floor/Facade rectangles against CAD entities.

        Region membership is based on the center of each top-level modelspace
        entity bounding box. Semantic meaning comes only from the layer type
        assigned by the user; layer names themselves are not interpreted.
        """
        semantic_types = (
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
            "Unassigned",
        )

        result = {
            "version": 1,
            "floor_plans": {},
            "facades": {},
        }

        if self._document is None or not isinstance(assignments, dict):
            return result

        try:
            layout = self._document.modelspace()
        except Exception:
            return result

        def normalized_bounds(values):
            try:
                x, y, w, h = [float(v) for v in values]
            except Exception:
                return None

            x2 = x + w
            y2 = y + h
            return (
                min(x, x2),
                min(y, y2),
                max(x, x2),
                max(y, y2),
            )

        def entity_bounds(entity):
            try:
                box = ezdxf_bbox.extents([entity], fast=True)
                if box.has_data:
                    return (
                        float(box.extmin.x),
                        float(box.extmin.y),
                        float(box.extmax.x),
                        float(box.extmax.y),
                    )
            except Exception:
                pass

            # Lightweight fallbacks for common point/line entities.
            try:
                dxftype = entity.dxftype()

                if dxftype == "LINE":
                    a = entity.dxf.start
                    b = entity.dxf.end
                    return (
                        min(float(a.x), float(b.x)),
                        min(float(a.y), float(b.y)),
                        max(float(a.x), float(b.x)),
                        max(float(a.y), float(b.y)),
                    )

                if dxftype in {"POINT", "TEXT", "MTEXT", "INSERT"}:
                    p = entity.dxf.insert if hasattr(entity.dxf, "insert") else entity.dxf.location
                    x = float(p.x)
                    y = float(p.y)
                    return (x, y, x, y)
            except Exception:
                pass

            return None

        # Build the entity index once; the same entities may be checked against
        # several independently confirmed floor/facade regions.
        indexed = []

        for entity in layout:
            try:
                layer = str(entity.dxf.layer)
            except Exception:
                layer = "0"

            semantic_type = self._layer_types.get(layer, "Unassigned")
            if semantic_type not in semantic_types:
                semantic_type = "Unassigned"

            bounds = entity_bounds(entity)
            if bounds is None:
                continue

            xmin, ymin, xmax, ymax = bounds
            cx = (xmin + xmax) * 0.5
            cy = (ymin + ymax) * 0.5

            try:
                handle = str(entity.dxf.handle or "")
            except Exception:
                handle = ""

            try:
                dxftype = str(entity.dxftype())
            except Exception:
                dxftype = "UNKNOWN"

            indexed.append({
                "handle": handle,
                "dxftype": dxftype,
                "layer": layer,
                "semantic_type": semantic_type,
                "bbox": [xmin, ymin, xmax, ymax],
                "center": [cx, cy],
            })

        for bucket in ("floor_plans", "facades"):
            regions = assignments.get(bucket, {})
            if not isinstance(regions, dict):
                continue

            for name, rect_values in regions.items():
                bounds = normalized_bounds(rect_values)
                if bounds is None:
                    continue

                rxmin, rymin, rxmax, rymax = bounds
                counts = {key: 0 for key in semantic_types}
                layer_counts = {}
                entities = []

                for record in indexed:
                    cx, cy = record["center"]
                    if not (rxmin <= cx <= rxmax and rymin <= cy <= rymax):
                        continue

                    semantic_type = record["semantic_type"]
                    counts[semantic_type] += 1
                    layer = record["layer"]
                    layer_counts[layer] = layer_counts.get(layer, 0) + 1
                    entities.append(record)

                # Keep zero counts out of the saved project for readability.
                compact_counts = {
                    key: value
                    for key, value in counts.items()
                    if value
                }

                result[bucket][str(name)] = {
                    "bounds": [rxmin, rymin, rxmax, rymax],
                    "entity_counts": compact_counts,
                    "layer_counts": layer_counts,
                    "entity_total": len(entities),
                    "entities": entities,
                }

        return result

    def get_layer_names(self):
        return list(
            self._layer_items.keys()
        )

    def get_layer_type(self, layer_name):
        return self._layer_types.get(
            layer_name,
            "Unassigned",
        )

    def is_layer_selected(self, layer_name):
        return self._layer_selected.get(
            layer_name,
            False,
        )

    def set_layer_selected(self, layer_name, selected):
        if layer_name not in self._layer_items:
            return

        self._layer_selected[layer_name] = bool(selected)
        self._apply_layer_style(layer_name)

    def set_layer_type(self, layer_name, layer_type):
        if layer_name not in self._layer_items:
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

        self._apply_layer_style(
            layer_name
        )

    def _layer_display_color(self, layer_type):
        colors = {
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

        return QColor(
            colors.get(
                layer_type,
                "#D9D9D9",
            )
        )

    def _apply_layer_style(self, layer_name):
        layer_type = self._layer_types.get(
            layer_name,
            "Unassigned",
        )

        selected = self._layer_selected.get(
            layer_name,
            False,
        )

        if selected:
            color = self._layer_display_color(
                layer_type
            )
        else:
            color = QColor("#D9D9D9")

        for item in self._layer_items.get(
            layer_name,
            [],
        ):
            try:
                item.setVisible(True)
            except Exception:
                pass

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

    def _apply_home_view(self):
        if not self._home_rect.isValid():
            return

        self.resetTransform()
        self.scale(1.0, -1.0)

        self.fitInView(
            self._home_rect,
            Qt.KeepAspectRatio,
        )

        self.centerOn(self._home_rect.center())

    def get_view_state(self):
        center = self.mapToScene(
            self.viewport().rect().center()
        )

        return {
            "transform": QTransform(self.transform()),
            "center_x": float(center.x()),
            "center_y": float(center.y()),
        }

    def restore_view_state(self, state):
        if not state:
            return

        self._restoring_history = True

        try:
            self.setTransform(
                QTransform(state["transform"])
            )

            self.centerOn(
                float(state["center_x"]),
                float(state["center_y"]),
            )

            self._user_has_interacted = True

        finally:
            self._restoring_history = False

    def _dwg_to_dxf(self, dwg_path: Path) -> Path:
        try:
            import pythoncom
            import win32com.client
        except ImportError as exc:
            raise RuntimeError(
                "DWG açmak için pywin32 kurulu değil."
            ) from exc

        output_dir = Path(tempfile.gettempdir()) / "MAP_Plan3D"
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / f"{dwg_path.stem}_plan3d.dxf"

        try:
            if output_path.exists():
                output_path.unlink()
        except Exception:
            pass

        pythoncom.CoInitialize()

        acad = None
        document = None
        conversion_error = None

        try:
            acad = win32com.client.DispatchEx(
                "AutoCAD.Application"
            )

            acad.Visible = False

            document = acad.Documents.Open(
                str(dwg_path.resolve())
            )

            time.sleep(1.0)
            pythoncom.PumpWaitingMessages()

            document.SaveAs(
                str(output_path),
                61,
            )

            for _ in range(60):
                pythoncom.PumpWaitingMessages()

                if (
                    output_path.exists()
                    and output_path.stat().st_size > 0
                ):
                    break

                time.sleep(0.25)

            if (
                not output_path.exists()
                or output_path.stat().st_size == 0
            ):
                raise RuntimeError(
                    "AutoCAD SaveAs tamamlandı ancak DXF dosyası oluşmadı."
                )

        except Exception as exc:
            conversion_error = exc

        finally:
            if document is not None:
                try:
                    document.Close(False)
                except Exception:
                    pass

            if acad is not None:
                try:
                    acad.Quit()
                except Exception:
                    pass

            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass

        if (
            output_path.exists()
            and output_path.stat().st_size > 0
        ):
            return output_path

        if conversion_error is not None:
            raise RuntimeError(
                "DWG DXF'e dönüştürülemedi:\n"
                f"{conversion_error}"
            ) from conversion_error

        raise RuntimeError(
            "DWG DXF'e dönüştürülemedi: DXF dosyası oluşmadı."
        )

    # ============================================================
    # 3Dcad-style manual floor pivot
    # ============================================================

    def set_floor_pivot_records(self, records):
        cleaned = {}

        if isinstance(records, dict):
            for floor_name, record in records.items():
                if not isinstance(record, dict):
                    continue

                try:
                    x = float(record.get("pivot_x"))
                    y = float(record.get("pivot_y"))
                except (TypeError, ValueError):
                    continue

                cleaned[str(floor_name)] = {
                    "pivot_x": x,
                    "pivot_y": y,
                    "snap_kind": str(
                        record.get(
                            "snap_kind",
                            "",
                        )
                        or ""
                    ),
                    "master": bool(
                        record.get(
                            "master",
                            False,
                        )
                    ),
                    "bounds": list(
                        record.get(
                            "bounds",
                            [],
                        )
                        or []
                    ),
                }

        self._floor_pivot_records = cleaned
        self.viewport().update()

    def floor_pivot_records(self):
        return {
            name: dict(record)
            for name, record
            in self._floor_pivot_records.items()
        }

    def _pivot_entity_points(self, entity):
        dtype = entity.dxftype()

        try:
            if dtype == "LINE":
                return [
                    (
                        float(entity.dxf.start.x),
                        float(entity.dxf.start.y),
                    ),
                    (
                        float(entity.dxf.end.x),
                        float(entity.dxf.end.y),
                    ),
                ], False

            if dtype == "LWPOLYLINE":
                points = [
                    (
                        float(point[0]),
                        float(point[1]),
                    )
                    for point
                    in entity.get_points("xy")
                ]

                closed = bool(
                    getattr(entity, "closed", False)
                    or getattr(entity, "is_closed", False)
                )

                return points, closed

            if dtype == "POLYLINE":
                points = []

                for vertex in entity.vertices:
                    location = vertex.dxf.location
                    points.append(
                        (
                            float(location.x),
                            float(location.y),
                        )
                    )

                return points, bool(
                    getattr(entity, "is_closed", False)
                )

        except Exception:
            return [], False

        return [], False

    def _pivot_collect_wall_geometry(
        self,
        rect_values,
    ):
        """
        Layer-driven Plan3D wall/pivot geometry collector. Only semantic Wall
        geometry inside the selected floor region is eligible. Exterior Wall is
        analysis/reference geometry and is intentionally excluded.
        """
        if self._document is None:
            return ()

        try:
            x, y, w, h = [
                float(value)
                for value in rect_values
            ]
        except Exception:
            return ()

        scene_rect = QRectF(
            x,
            y,
            w,
            h,
        ).normalized()

        if (
            scene_rect.width() <= 0
            or scene_rect.height() <= 0
        ):
            return ()

        # Plan3D's PyQtBackend scene and all existing region analyzers use
        # the same XY coordinate space. Do NOT invert Y here.
        cad_x_min = float(
            scene_rect.left()
        )
        cad_x_max = float(
            scene_rect.right()
        )
        cad_y_min = float(
            scene_rect.top()
        )
        cad_y_max = float(
            scene_rect.bottom()
        )

        collected = []

        def entity_intersects_region(entity):
            try:
                box = ezdxf_bbox.extents(
                    [entity],
                    fast=True,
                )
                if not box.has_data:
                    return False

                ex0 = float(
                    box.extmin.x
                )
                ey0 = float(
                    box.extmin.y
                )
                ex1 = float(
                    box.extmax.x
                )
                ey1 = float(
                    box.extmax.y
                )

                return not (
                    ex1 < cad_x_min
                    or ex0 > cad_x_max
                    or ey1 < cad_y_min
                    or ey0 > cad_y_max
                )
            except Exception:
                return False

        def consume(entity, inherited_semantic=None):
            try:
                layer = str(
                    entity.dxf.layer
                )
            except Exception:
                layer = "0"

            semantic = (
                inherited_semantic
                or self.get_layer_type(layer)
            )

            dtype = entity.dxftype()

            if dtype == "INSERT":
                # A block insert can sit on layer 0 while its child entities
                # carry the real Wall / Exterior Wall semantic layer.
                child_inherited = (
                    semantic
                    if semantic == "Wall"
                    else None
                )

                try:
                    for virtual in entity.virtual_entities():
                        consume(
                            virtual,
                            inherited_semantic=child_inherited,
                        )
                except Exception:
                    pass
                return

            if semantic != "Wall":
                return

            if not entity_intersects_region(entity):
                return

            points, closed = self._pivot_entity_points(
                entity
            )

            if len(points) < 2:
                return

            if (
                closed
                and points[0] != points[-1]
            ):
                points.append(
                    points[0]
                )

            collected.append(
                tuple(points)
            )

        try:
            for entity in self._document.modelspace():
                consume(entity)
        except Exception:
            return ()

        return tuple(collected)

    @staticmethod
    def _pivot_nearest_point_on_segment(
        point,
        a,
        b,
    ):
        px, py = point
        ax, ay = a
        bx, by = b

        dx = bx - ax
        dy = by - ay
        length2 = (
            dx * dx
            + dy * dy
        )

        if length2 <= 1.0e-18:
            return (
                float(ax),
                float(ay),
            )

        t = (
            (
                (px - ax) * dx
                + (py - ay) * dy
            )
            / length2
        )

        t = max(
            0.0,
            min(
                1.0,
                t,
            ),
        )

        return (
            float(
                ax + dx * t
            ),
            float(
                ay + dy * t
            ),
        )

    def _pivot_pixel_distance(
        self,
        cad_point,
        viewport_point,
    ):
        screen = self.mapFromScene(
            QPointF(
                float(cad_point[0]),
                float(cad_point[1]),
            )
        )

        return math.hypot(
            float(
                screen.x()
                - viewport_point.x()
            ),
            float(
                screen.y()
                - viewport_point.y()
            ),
        )

    def _snap_floor_pivot(
        self,
        viewport_point,
    ):
        scene_point = self.mapToScene(
            viewport_point
        )

        raw = (
            float(scene_point.x()),
            float(scene_point.y()),
        )

        radius = float(
            self._pivot_snap_radius_px
        )

        geometry = tuple(
            self._pivot_reference_geometry
            or ()
        )

        # 1) wall vertex / endpoint
        best_point = None
        best_distance = (
            radius + 1.0
        )

        for points in geometry:
            for point in points:
                distance = (
                    self._pivot_pixel_distance(
                        point,
                        viewport_point,
                    )
                )

                if distance < best_distance:
                    best_distance = distance
                    best_point = point

        if (
            best_point is not None
            and best_distance <= radius
        ):
            return (
                (
                    float(best_point[0]),
                    float(best_point[1]),
                ),
                "wall_vertex",
            )

        # 2) wall segment body
        best_point = None
        best_distance = (
            radius + 1.0
        )

        for points in geometry:
            for a, b in zip(
                points,
                points[1:],
            ):
                nearest = (
                    self._pivot_nearest_point_on_segment(
                        raw,
                        a,
                        b,
                    )
                )

                distance = (
                    self._pivot_pixel_distance(
                        nearest,
                        viewport_point,
                    )
                )

                if distance < best_distance:
                    best_distance = distance
                    best_point = nearest

        if (
            best_point is not None
            and best_distance <= radius
        ):
            return (
                (
                    float(best_point[0]),
                    float(best_point[1]),
                ),
                "wall_segment",
            )

        # 3) free CAD point
        return raw, "free"

    # PLAN3D_PIVOT_MASTER_GUIDE_V3
    def _pivot_master_record(
        self,
        current_floor_name,
    ):
        records = tuple(
            (
                self._floor_pivot_records
                or {}
            ).values()
        )

        current_name = str(
            current_floor_name
            or ""
        ).strip()

        valid = []

        for record in records:
            if not isinstance(record, dict):
                continue

            floor_name = str(
                record.get(
                    "floor_name",
                    record.get(
                        "floor_label",
                        "",
                    ),
                )
                or ""
            ).strip()

            if floor_name and floor_name == current_name:
                continue

            bounds = record.get("bounds")

            if not (
                isinstance(bounds, (tuple, list))
                and len(bounds) == 4
            ):
                continue

            try:
                pivot_x = float(record.get("pivot_x"))
                pivot_y = float(record.get("pivot_y"))
            except (TypeError, ValueError):
                continue

            valid.append(
                (
                    record,
                    floor_name,
                    pivot_x,
                    pivot_y,
                )
            )

        for (
            record,
            floor_name,
            pivot_x,
            pivot_y,
        ) in valid:
            if bool(record.get("master", False)):
                return (
                    record,
                    floor_name,
                    pivot_x,
                    pivot_y,
                )

        for (
            record,
            floor_name,
            pivot_x,
            pivot_y,
        ) in valid:
            if floor_name.casefold() in {
                "ground floor",
                "giriş kat",
                "giris kat",
            }:
                return (
                    record,
                    floor_name,
                    pivot_x,
                    pivot_y,
                )

        if valid:
            return valid[0]

        return None


    def _prepare_pivot_master_guide(
        self,
        current_floor_name,
    ):
        self._pivot_guide_geometry = ()
        self._pivot_guide_origin = None
        self._pivot_guide_floor_name = ""

        master = self._pivot_master_record(
            current_floor_name
        )

        if master is None:
            return

        (
            record,
            floor_name,
            pivot_x,
            pivot_y,
        ) = master

        bounds = record.get("bounds")

        try:
            geometry = self._pivot_collect_wall_geometry(
                bounds
            )
        except Exception:
            geometry = ()

        if not geometry:
            return

        self._pivot_guide_geometry = tuple(
            geometry
        )

        self._pivot_guide_origin = (
            float(pivot_x),
            float(pivot_y),
        )

        self._pivot_guide_floor_name = str(
            floor_name
            or ""
        )


    def _clear_pivot_master_guide(
        self,
    ):
        self._pivot_guide_geometry = ()
        self._pivot_guide_origin = None
        self._pivot_guide_floor_name = ""


    def begin_floor_pivot_selection(
        self,
        floor_name,
        rect_values,
        existing_record=None,
    ):
        self.cancel_assignment_selection()

        geometry = (
            self._pivot_collect_wall_geometry(
                rect_values
            )
        )

        # Free placement must always remain available. If no wall reference
        # was collected, pivot mode still starts; snap simply stays inactive.
        self._pivot_floor_name = str(
            floor_name
            or ""
        )
        self._pivot_reference_geometry = geometry

        # PLAN3D_PIVOT_MASTER_GUIDE_V3
        self._prepare_pivot_master_guide(
            self._pivot_floor_name
        )
        self._pivot_edit_enabled = True
        self._pivot_drag_active = False
        self._pivot_hover_cad = None
        self._pivot_snap_kind = ""

        if isinstance(
            existing_record,
            dict,
        ):
            try:
                self._pivot_point_cad = (
                    float(
                        existing_record.get(
                            "pivot_x"
                        )
                    ),
                    float(
                        existing_record.get(
                            "pivot_y"
                        )
                    ),
                )
            except (TypeError, ValueError):
                self._pivot_point_cad = None
        else:
            self._pivot_point_cad = None

        self.setDragMode(
            QGraphicsView.NoDrag
        )
        self.viewport().setMouseTracking(
            True
        )
        self.viewport().setCursor(
            Qt.CrossCursor
        )
        self.viewport().update()

    def cancel_floor_pivot_selection(self):
        self._pivot_edit_enabled = False
        self._pivot_drag_active = False
        self._pivot_floor_name = ""
        self._pivot_hover_cad = None
        self._pivot_reference_geometry = ()

        if not self._panning:
            self.setDragMode(
                QGraphicsView.ScrollHandDrag
            )
            self.viewport().setMouseTracking(
                False
            )
            self.viewport().unsetCursor()

        self.viewport().update()

    def drawForeground(
        self,
        painter,
        rect,
    ):
        super().drawForeground(
            painter,
            rect,
        )

        records = dict(
            self._floor_pivot_records
            or {}
        )

        # During editing show the active hover/current point too.
        active_point = None

        if (
            self._pivot_edit_enabled
            and self._pivot_hover_cad
            is not None
        ):
            active_point = (
                self._pivot_hover_cad
            )
        elif (
            self._pivot_point_cad
            is not None
        ):
            # Keep the last clicked/committed pivot visible even before
            # Confirm Details writes it into the persistent floor records.
            active_point = (
                self._pivot_point_cad
            )

        scale = abs(
            float(
                self.transform().m11()
            )
        )

        if scale <= 1.0e-12:
            scale = 1.0

        # PLAN3D_PIVOT_MASTER_GUIDE_V3
        guide_geometry = tuple(
            getattr(
                self,
                "_pivot_guide_geometry",
                (),
            )
            or ()
        )

        guide_origin = getattr(
            self,
            "_pivot_guide_origin",
            None,
        )

        guide_target = None

        if getattr(
            self,
            "_pivot_edit_enabled",
            False,
        ):
            guide_target = (
                getattr(
                    self,
                    "_pivot_hover_cad",
                    None,
                )
                or getattr(
                    self,
                    "_pivot_point_cad",
                    None,
                )
            )

        if (
            guide_geometry
            and isinstance(
                guide_origin,
                (tuple, list),
            )
            and len(guide_origin) >= 2
            and isinstance(
                guide_target,
                (tuple, list),
            )
            and len(guide_target) >= 2
        ):
            dx = (
                float(guide_target[0])
                - float(guide_origin[0])
            )

            dy = (
                float(guide_target[1])
                - float(guide_origin[1])
            )

            guide_pen = QPen(
                QColor(
                    170,
                    170,
                    170,
                    170,
                )
            )
            guide_pen.setCosmetic(True)
            guide_pen.setWidthF(1.5)
            guide_pen.setStyle(Qt.DashLine)

            painter.setPen(
                guide_pen
            )
            painter.setBrush(
                Qt.NoBrush
            )

            for points in guide_geometry:
                if len(points) < 2:
                    continue

                for a, b in zip(
                    points,
                    points[1:],
                ):
                    painter.drawLine(
                        QPointF(
                            float(a[0]) + dx,
                            float(a[1]) + dy,
                        ),
                        QPointF(
                            float(b[0]) + dx,
                            float(b[1]) + dy,
                        ),
                    )


        axis = 28.0 / scale
        box = 8.0 / scale

        def draw_marker(point):
            # Plan3D stores the pivot in the same XY coordinate space used
            # by its CAD scene and existing region analyzers.
            center_x = float(
                point[0]
            )
            center_y = float(
                point[1]
            )

            x_pen = QPen(
                QColor(
                    220,
                    70,
                    70,
                )
            )
            x_pen.setCosmetic(
                True
            )
            x_pen.setWidth(
                2
            )
            painter.setPen(
                x_pen
            )
            painter.drawLine(
                center_x,
                center_y,
                center_x + axis,
                center_y,
            )

            y_pen = QPen(
                QColor(
                    80,
                    205,
                    115,
                )
            )
            y_pen.setCosmetic(
                True
            )
            y_pen.setWidth(
                2
            )
            painter.setPen(
                y_pen
            )
            painter.drawLine(
                center_x,
                center_y,
                center_x,
                center_y + axis,
            )

            center_pen = QPen(
                QColor(
                    225,
                    235,
                    245,
                )
            )
            center_pen.setCosmetic(
                True
            )
            center_pen.setWidth(
                1
            )
            painter.setPen(
                center_pen
            )
            painter.setBrush(
                Qt.NoBrush
            )
            painter.drawRect(
                QRectF(
                    center_x - box,
                    center_y - box,
                    box * 2.0,
                    box * 2.0,
                )
            )

        for record in records.values():
            try:
                draw_marker(
                    (
                        float(
                            record[
                                "pivot_x"
                            ]
                        ),
                        float(
                            record[
                                "pivot_y"
                            ]
                        ),
                    )
                )
            except Exception:
                continue

        if active_point is not None:
            draw_marker(
                active_point
            )

    def begin_assignment_selection(self, kind, name=""):
        self.cancel_floor_pivot_selection()
        self.cancel_assignment_selection()
        self._assignment_mode = True
        self._assignment_kind = str(kind)
        self._assignment_name = ""
        self.setCursor(Qt.CrossCursor)

    def cancel_assignment_selection(self):
        self._assignment_mode = False
        self._assignment_start = None
        self._assignment_kind = ""
        self._assignment_name = ""
        if self._assignment_preview is not None:
            try:
                scene = self.scene()
                if scene is not None:
                    scene.removeItem(self._assignment_preview)
            except Exception:
                pass
        self._assignment_preview = None
        if not self._panning:
            self.setCursor(Qt.ArrowCursor)

    def _remove_assignment_items(self, items):
        scene = self.scene()
        if scene is not None:
            for item in list(items):
                try:
                    scene.removeItem(item)
                except Exception:
                    pass
        items.clear()

    def clear_assignment_overlays(self):
        self._remove_assignment_items(self._assignment_confirmed_items)
        self._remove_assignment_items(self._assignment_pending_items)
        self._assignment_overlay_items = []

    def _draw_assignment_regions(self, assignment_data, confirmed=True):
        scene = self.scene()

        if scene is None or not isinstance(assignment_data, dict):
            return

        target_items = (
            self._assignment_confirmed_items
            if confirmed
            else self._assignment_pending_items
        )

        pen = QPen(QColor("#78AEFF"))
        pen.setWidthF(1.6 if confirmed else 1.0)
        pen.setCosmetic(True)

        if not confirmed:
            pen.setStyle(Qt.DashLine)

        def add_region(label, rect_values):
            try:
                x, y, w, h = [float(v) for v in rect_values]
            except Exception:
                return

            rect = QRectF(x, y, w, h).normalized()

            if rect.width() <= 0 or rect.height() <= 0:
                return

            if not confirmed:
                frame = QGraphicsRectItem(rect)
                frame.setPen(pen)
                frame.setBrush(QBrush(Qt.NoBrush))
                frame.setZValue(1000002)
                scene.addItem(frame)
                target_items.append(frame)

            text = QGraphicsSimpleTextItem(str(label))
            text.setBrush(
                QBrush(
                    QColor(
                        "#E7EEF8"
                        if confirmed
                        else "#9FC6FF"
                    )
                )
            )
            text.setFlag(
                QGraphicsItem.ItemIgnoresTransformations,
                True,
            )
            text.setZValue(
                1000001 if confirmed else 1000003
            )
            if confirmed:
                text.setPos(
                    rect.left(),
                    rect.bottom(),
                )
            else:
                text.setPos(
                    rect.left(),
                    rect.top(),
                )
            scene.addItem(text)
            target_items.append(text)

        for name, rect_values in assignment_data.get(
            "floor_plans",
            {},
        ).items():
            add_region(
                str(name).upper(),
                rect_values,
            )

        for name, rect_values in assignment_data.get(
            "facades",
            {},
        ).items():
            add_region(
                str(name).upper() + " FACADE",
                rect_values,
            )

        self._assignment_overlay_items = (
            list(self._assignment_confirmed_items)
            + list(self._assignment_pending_items)
        )

    def show_assignment_regions(self, assignment_data, confirmed=True):
        if confirmed:
            self._remove_assignment_items(
                self._assignment_confirmed_items
            )
            self._draw_assignment_regions(
                assignment_data,
                confirmed=True,
            )
        else:
            self._remove_assignment_items(
                self._assignment_pending_items
            )
            self._draw_assignment_regions(
                assignment_data,
                confirmed=False,
            )

        self.viewport().update()

    def show_assignment_regions_state(self, confirmed_data, pending_data=None):
        # Rebuild each overlay class independently.
        # Starting another selection can only replace the pending overlay;
        # confirmed regions remain derived from the complete confirmed dictionary.
        self._remove_assignment_items(
            self._assignment_confirmed_items
        )
        self._remove_assignment_items(
            self._assignment_pending_items
        )

        self._draw_assignment_regions(
            confirmed_data,
            confirmed=True,
        )

        if isinstance(pending_data, dict):
            self._draw_assignment_regions(
                pending_data,
                confirmed=False,
            )

        self.viewport().update()




    def find_facade_height_reference_lines(self, rect_values=None):
        # PLAN3D_FACADE_GLOBAL_DATUM_C_OLCU_V11
        #
        # AUTHORITATIVE RULE:
        # 1) Read real CAD LINE/LWPOLYLINE/POLYLINE segments on "C Ölçü".
        # 2) Keep horizontal / near-horizontal segments.
        # 3) Select ONLY the globally lowest segment.
        # 4) Its Y coordinate is the common building elevation datum Z=0.
        import unicodedata

        def norm_layer(value):
            return unicodedata.normalize(
                "NFC",
                str(value or "").strip(),
            ).casefold()

        target_layer = norm_layer("C Ölçü")

        doc = self._document
        if doc is None:
            return []

        try:
            modelspace = doc.modelspace()
        except Exception:
            return []

        def entity_points(entity):
            dtype = entity.dxftype()

            try:
                if dtype == "LINE":
                    return [
                        (
                            float(entity.dxf.start.x),
                            float(entity.dxf.start.y),
                        ),
                        (
                            float(entity.dxf.end.x),
                            float(entity.dxf.end.y),
                        ),
                    ], False

                if dtype == "LWPOLYLINE":
                    pts = [
                        (
                            float(pt[0]),
                            float(pt[1]),
                        )
                        for pt in entity.get_points("xy")
                    ]
                    closed = bool(
                        getattr(entity, "closed", False)
                        or getattr(entity, "is_closed", False)
                    )
                    return pts, closed

                if dtype == "POLYLINE":
                    pts = []
                    for vertex in entity.vertices:
                        loc = vertex.dxf.location
                        pts.append(
                            (
                                float(loc.x),
                                float(loc.y),
                            )
                        )
                    closed = bool(
                        getattr(entity, "is_closed", False)
                    )
                    return pts, closed
            except Exception:
                return [], False

            return [], False

        candidates = []

        for entity in modelspace:
            dtype = entity.dxftype()

            if dtype not in {
                "LINE",
                "LWPOLYLINE",
                "POLYLINE",
            }:
                continue

            try:
                layer = str(entity.dxf.layer)
            except Exception:
                layer = ""

            if norm_layer(layer) != target_layer:
                continue

            points, closed = entity_points(entity)

            if len(points) < 2:
                continue

            pairs = [
                (
                    points[index],
                    points[index + 1],
                )
                for index in range(
                    len(points) - 1
                )
            ]

            if (
                closed
                and len(points) > 2
                and points[0] != points[-1]
            ):
                pairs.append(
                    (
                        points[-1],
                        points[0],
                    )
                )

            try:
                handle = str(
                    entity.dxf.handle
                    or ""
                )
            except Exception:
                handle = ""

            for p0, p1 in pairs:
                x0 = float(p0[0])
                y0 = float(p0[1])
                x1 = float(p1[0])
                y1 = float(p1[1])

                dx = abs(x1 - x0)
                dy = abs(y1 - y0)

                if dx <= 1.0e-9:
                    continue

                if dy > max(
                    1.0e-9,
                    dx * 0.015,
                ):
                    continue

                if x0 <= x1:
                    start = [x0, y0]
                    end = [x1, y1]
                else:
                    start = [x1, y1]
                    end = [x0, y0]

                candidates.append(
                    {
                        "start": start,
                        "end": end,
                        "y": float(
                            (y0 + y1)
                            * 0.5
                        ),
                        "length": float(
                            (
                                (x1 - x0) ** 2
                                + (y1 - y0) ** 2
                            )
                            ** 0.5
                        ),
                        "layer": layer,
                        "handle": handle,
                    }
                )

        if not candidates:
            print(
                "PLAN3D FACADE GLOBAL DATUM V11 |",
                "layer=C Ölçü",
                "| selected=0",
                flush=True,
            )
            return []

        lowest_y = min(
            float(row["y"])
            for row in candidates
        )

        y_tol = 1.0e-6

        same_level = [
            row
            for row in candidates
            if abs(
                float(row["y"])
                - lowest_y
            ) <= y_tol
        ]

        # If the level is split into several coincident horizontal pieces,
        # choose the longest real CAD segment; then the leftmost.
        same_level.sort(
            key=lambda row: (
                -float(row["length"]),
                float(row["start"][0]),
            )
        )

        selected = dict(
            same_level[0]
        )

        selected[
            "datum_z_cm"
        ] = 0.0

        selected[
            "source"
        ] = (
            "C_OLCU_GLOBAL_LOWEST_HORIZONTAL"
        )

        print(
            "PLAN3D FACADE GLOBAL DATUM V11 |",
            "layer=C Ölçü",
            "| selected=1",
            "| y=",
            round(
                float(
                    selected["y"]
                ),
                6,
            ),
            "| start=",
            selected["start"],
            "| end=",
            selected["end"],
            flush=True,
        )

        return [
            selected
        ]


    def show_facade_height_reference_lines(self, references):
        # PLAN3D_FACADE_HEIGHT_REFERENCE_RED_V9
        # Display-only overlay. CAD source coordinates are already scene coords.

        try:
            scene = self.scene()
        except Exception:
            scene = None

        if scene is None:
            return

        for attr_name in (
            "_plan3d_facade_bottom_left_red_items_v4",
            "_plan3d_facade_bottom_left_red_items_v5",
            "_plan3d_facade_height_reference_red_items_v6",
            "_plan3d_facade_height_reference_red_items_v9",
        ):
            for item in list(
                getattr(
                    self,
                    attr_name,
                    [],
                )
                or []
            ):
                try:
                    scene.removeItem(
                        item
                    )
                except Exception:
                    pass

            try:
                setattr(
                    self,
                    attr_name,
                    [],
                )
            except Exception:
                pass

        try:
            from PySide6.QtGui import QColor, QPen
            from PySide6.QtWidgets import QGraphicsLineItem
        except Exception:
            try:
                from PyQt6.QtGui import QColor, QPen
                from PyQt6.QtWidgets import QGraphicsLineItem
            except Exception:
                return

        pen = QPen(
            QColor(
                255,
                0,
                0,
            )
        )

        pen.setWidthF(
            4.0
        )

        try:
            pen.setCosmetic(
                True
            )
        except Exception:
            pass

        created = []
        seen = set()

        for reference in list(
            references
            or []
        ):
            if not isinstance(
                reference,
                dict,
            ):
                continue

            start = reference.get(
                "start"
            )
            end = reference.get(
                "end"
            )

            if (
                not isinstance(
                    start,
                    (
                        list,
                        tuple,
                    ),
                )
                or not isinstance(
                    end,
                    (
                        list,
                        tuple,
                    ),
                )
                or len(
                    start
                )
                < 2
                or len(
                    end
                )
                < 2
            ):
                continue

            key = (
                round(
                    float(
                        start[
                            0
                        ]
                    ),
                    6,
                ),
                round(
                    float(
                        start[
                            1
                        ]
                    ),
                    6,
                ),
                round(
                    float(
                        end[
                            0
                        ]
                    ),
                    6,
                ),
                round(
                    float(
                        end[
                            1
                        ]
                    ),
                    6,
                ),
            )

            if key in seen:
                continue

            seen.add(
                key
            )

            try:
                item = (
                    QGraphicsLineItem(
                        float(
                            start[
                                0
                            ]
                        ),
                        float(
                            start[
                                1
                            ]
                        ),
                        float(
                            end[
                                0
                            ]
                        ),
                        float(
                            end[
                                1
                            ]
                        ),
                    )
                )

                item.setPen(
                    pen
                )

                item.setZValue(
                    100000000.0
                )

                scene.addItem(
                    item
                )

                created.append(
                    item
                )

            except Exception:
                pass

        self._plan3d_facade_height_reference_red_items_v9 = (
            created
        )

        print(
            "PLAN3D FACADE HEIGHT REF RED V9 |",
            "items=",
            len(
                created
            ),
            "| source_layer=C Ölçü",
            flush=True,
        )

        try:
            scene.update()
        except Exception:
            pass

        try:
            self.viewport().update()
        except Exception:
            pass


    def analyze_exterior_wall_system(self, rect_values, force_wall_source=False):
        """
        EXTERIOR WALL ANALYSIS V2.

        Important change from V1:
        openings are NOT classified as exterior merely because they are close
        to the floor-plan bounding envelope.

        A logical Window / Door / Sliding Door candidate must be geometrically
        close to an ACTUAL exterior-wall segment. The nearest real wall chain
        decides the side assignment.

        Exterior Wall semantic geometry is authoritative when available.
        Wall is used only as a fallback source.
        """
        empty = {
            "version": 2,
            "wall_source": "none",
            "dominant_angle_deg": 0.0,
            "bounds_uv": {},
            "chains": {
                "bottom": {"segments": [], "length": 0.0, "openings": []},
                "top": {"segments": [], "length": 0.0, "openings": []},
                "left": {"segments": [], "length": 0.0, "openings": []},
                "right": {"segments": [], "length": 0.0, "openings": []},
            },
            "logical_openings": [],
            "exterior_openings": [],
            "interior_or_unassigned_openings": [],
        }

        try:
            x, y, w, h = [float(v) for v in rect_values]
        except Exception:
            return empty

        rx0 = min(x, x + w)
        rx1 = max(x, x + w)
        ry0 = min(y, y + h)
        ry1 = max(y, y + h)

        region_w = max(rx1 - rx0, 1e-9)
        region_h = max(ry1 - ry0, 1e-9)
        region_min_span = min(region_w, region_h)

        doc = self._document

        if doc is None:
            return empty

        try:
            modelspace = doc.modelspace()
        except Exception:
            return empty

        def inside_region(px, py):
            return (
                rx0 <= px <= rx1
                and ry0 <= py <= ry1
            )

        def entity_bbox(entity):
            try:
                box = ezdxf_bbox.extents(
                    [entity],
                    fast=True,
                )

                if box.has_data:
                    return (
                        float(box.extmin.x),
                        float(box.extmin.y),
                        float(box.extmax.x),
                        float(box.extmax.y),
                    )
            except Exception:
                pass

            return None

        def entity_points(entity):
            dtype = entity.dxftype()

            try:
                if dtype == "LINE":
                    return [
                        (
                            float(entity.dxf.start.x),
                            float(entity.dxf.start.y),
                        ),
                        (
                            float(entity.dxf.end.x),
                            float(entity.dxf.end.y),
                        ),
                    ], False

                if dtype == "LWPOLYLINE":
                    pts = [
                        (
                            float(pt[0]),
                            float(pt[1]),
                        )
                        for pt in entity.get_points("xy")
                    ]

                    closed = bool(
                        getattr(entity, "closed", False)
                        or getattr(entity, "is_closed", False)
                    )

                    return pts, closed

                if dtype == "POLYLINE":
                    pts = []

                    for vertex in entity.vertices:
                        loc = vertex.dxf.location
                        pts.append(
                            (
                                float(loc.x),
                                float(loc.y),
                            )
                        )

                    closed = bool(
                        getattr(entity, "is_closed", False)
                    )

                    return pts, closed

            except Exception:
                return [], False

            return [], False

        def to_segments(entity):
            points, closed = entity_points(entity)

            if len(points) < 2:
                return []

            pairs = [
                (
                    points[index],
                    points[index + 1],
                )
                for index in range(
                    len(points) - 1
                )
            ]

            if (
                closed
                and len(points) > 2
                and points[0] != points[-1]
            ):
                pairs.append(
                    (
                        points[-1],
                        points[0],
                    )
                )

            try:
                handle = str(
                    entity.dxf.handle or ""
                )
            except Exception:
                handle = ""

            try:
                layer = str(
                    entity.dxf.layer
                )
            except Exception:
                layer = "0"

            semantic_type = self.get_layer_type(
                layer
            )

            result = []

            for p0, p1 in pairs:
                mx = (p0[0] + p1[0]) * 0.5
                my = (p0[1] + p1[1]) * 0.5

                if not inside_region(mx, my):
                    continue

                dx = p1[0] - p0[0]
                dy = p1[1] - p0[1]
                length = math.hypot(dx, dy)

                if length <= 1e-9:
                    continue

                result.append({
                    "handle": handle,
                    "layer": layer,
                    "semantic_type": semantic_type,
                    "start": [float(p0[0]), float(p0[1])],
                    "end": [float(p1[0]), float(p1[1])],
                    "midpoint": [float(mx), float(my)],
                    "length": float(length),
                })

            return result

        exterior_segments = []
        wall_segments = []
        raw_opening_parts = []

        for entity in modelspace:
            try:
                layer = str(entity.dxf.layer)
            except Exception:
                layer = "0"

            semantic_type = self.get_layer_type(
                layer
            )

            if semantic_type in {
                "Exterior Wall",
                "Wall",
            }:
                segments = to_segments(entity)

                if semantic_type == "Exterior Wall":
                    exterior_segments.extend(segments)
                else:
                    wall_segments.extend(segments)

                continue

            if semantic_type not in {
                "Window",
                "Door",
                "Sliding Door",
            }:
                continue

            bbox = entity_bbox(entity)

            if bbox is None:
                continue

            xmin, ymin, xmax, ymax = bbox
            cx = (xmin + xmax) * 0.5
            cy = (ymin + ymax) * 0.5

            if not inside_region(cx, cy):
                continue

            try:
                handle = str(entity.dxf.handle or "")
            except Exception:
                handle = ""

            raw_opening_parts.append({
                "handle": handle,
                "layer": layer,
                "semantic_type": semantic_type,
                "bbox": [
                    float(xmin),
                    float(ymin),
                    float(xmax),
                    float(ymax),
                ],
                "center": [
                    float(cx),
                    float(cy),
                ],
            })

        if force_wall_source:
            source_segments = wall_segments
            wall_source = (
                "Wall fallback"
                if wall_segments
                else "none"
            )
        else:
            source_segments = (
                exterior_segments
                if exterior_segments
                else wall_segments
            )

            wall_source = (
                "Exterior Wall"
                if exterior_segments
                else (
                    "Wall fallback"
                    if wall_segments
                    else "none"
                )
            )

        if not source_segments:
            result = dict(empty)
            result["wall_source"] = wall_source
            return result

        # -------------------------------------------------------------
        # Dominant orthogonal plan axes.
        # -------------------------------------------------------------
        sum_c = 0.0
        sum_s = 0.0
        total_weight = 0.0

        for segment in source_segments:
            x0, y0 = segment["start"]
            x1, y1 = segment["end"]

            angle = math.atan2(
                y1 - y0,
                x1 - x0,
            )

            weight = max(
                segment["length"],
                1e-9,
            )

            sum_c += math.cos(2.0 * angle) * weight
            sum_s += math.sin(2.0 * angle) * weight
            total_weight += weight

        theta = (
            0.5 * math.atan2(sum_s, sum_c)
            if total_weight > 0
            else 0.0
        )

        ux = math.cos(theta)
        uy = math.sin(theta)
        vx = -uy
        vy = ux

        def project(point):
            px, py = point

            return (
                px * ux + py * uy,
                px * vx + py * vy,
            )

        projected_endpoints = []

        for segment in source_segments:
            projected_endpoints.append(
                project(segment["start"])
            )
            projected_endpoints.append(
                project(segment["end"])
            )

        u_values = [
            value[0]
            for value in projected_endpoints
        ]
        v_values = [
            value[1]
            for value in projected_endpoints
        ]

        u_min = min(u_values)
        u_max = max(u_values)
        v_min = min(v_values)
        v_max = max(v_values)

        u_span = max(u_max - u_min, 1e-9)
        v_span = max(v_max - v_min, 1e-9)

        chains = {
            "bottom": [],
            "top": [],
            "left": [],
            "right": [],
        }

        # Fallback Wall geometry can contain internal walls. Keep only segments
        # close to the actual outer envelope when Exterior Wall is unavailable.
        fallback_band = 0.12

        for segment in source_segments:
            su0, sv0 = project(segment["start"])
            su1, sv1 = project(segment["end"])

            du = su1 - su0
            dv = sv1 - sv0

            midpoint_u = (su0 + su1) * 0.5
            midpoint_v = (sv0 + sv1) * 0.5

            aligned_u = abs(du) >= abs(dv)

            if aligned_u:
                dist_bottom = abs(midpoint_v - v_min)
                dist_top = abs(v_max - midpoint_v)

                side = (
                    "bottom"
                    if dist_bottom <= dist_top
                    else "top"
                )

                boundary_distance = min(
                    dist_bottom,
                    dist_top,
                )

                normalized_boundary_distance = (
                    boundary_distance / v_span
                )

                if (
                    wall_source == "Wall fallback"
                    and normalized_boundary_distance
                    > fallback_band
                ):
                    continue

                along_start = su0
                along_end = su1
                normal_position = midpoint_v

            else:
                dist_left = abs(midpoint_u - u_min)
                dist_right = abs(u_max - midpoint_u)

                side = (
                    "left"
                    if dist_left <= dist_right
                    else "right"
                )

                boundary_distance = min(
                    dist_left,
                    dist_right,
                )

                normalized_boundary_distance = (
                    boundary_distance / u_span
                )

                if (
                    wall_source == "Wall fallback"
                    and normalized_boundary_distance
                    > fallback_band
                ):
                    continue

                along_start = sv0
                along_end = sv1
                normal_position = midpoint_u

            record = dict(segment)

            record.update({
                "side": side,
                "axis_start": float(along_start),
                "axis_end": float(along_end),
                "normal_position": float(normal_position),
                "boundary_distance": float(boundary_distance),
            })

            chains[side].append(record)

        # -------------------------------------------------------------
        # OUTWARD-VISIBILITY FILTER
        #
        # V2 previously treated every segment in the Exterior Wall semantic
        # layer as an exterior-chain segment. That is why an interior door
        # could still be attached to a facade: an internal wall segment could
        # itself be present in the candidate chain.
        #
        # A chain segment is now rejected when another parallel segment lies
        # farther outward and substantially overlaps it along the same axis.
        # Only outward-exposed segments remain eligible for exterior openings.
        # -------------------------------------------------------------

        def interval_overlap_ratio(
            a0,
            a1,
            b0,
            b1,
        ):
            amin = min(a0, a1)
            amax = max(a0, a1)
            bmin = min(b0, b1)
            bmax = max(b0, b1)

            overlap = max(
                0.0,
                min(amax, bmax)
                - max(amin, bmin),
            )

            alen = max(
                amax - amin,
                1e-9,
            )

            return overlap / alen

        filtered_chains = {
            "bottom": [],
            "top": [],
            "left": [],
            "right": [],
        }

        rejected_chain_segments = []

        for side, segments in chains.items():
            # Two close parallel lines can be the two faces of the same wall.
            # They should not hide one another.
            plan_span = (
                v_span
                if side in {
                    "bottom",
                    "top",
                }
                else u_span
            )

            same_wall_band_limit = max(
                plan_span * 0.008,
                1e-9,
            )

            for segment in segments:
                hidden = False

                for other in segments:
                    if other is segment:
                        continue

                    overlap_ratio = (
                        interval_overlap_ratio(
                            segment[
                                "axis_start"
                            ],
                            segment[
                                "axis_end"
                            ],
                            other[
                                "axis_start"
                            ],
                            other[
                                "axis_end"
                            ],
                        )
                    )

                    if overlap_ratio < 0.35:
                        continue

                    normal_a = float(
                        segment[
                            "normal_position"
                        ]
                    )
                    normal_b = float(
                        other[
                            "normal_position"
                        ]
                    )

                    separation = abs(
                        normal_b
                        - normal_a
                    )

                    if (
                        separation
                        <= same_wall_band_limit
                    ):
                        continue

                    if side in {
                        "bottom",
                        "left",
                    }:
                        farther_out = (
                            normal_b
                            < normal_a
                        )
                    else:
                        farther_out = (
                            normal_b
                            > normal_a
                        )

                    if farther_out:
                        hidden = True
                        break

                if hidden:
                    rejected = dict(
                        segment
                    )
                    rejected[
                        "reject_reason"
                    ] = (
                        "occluded by farther-out parallel wall"
                    )
                    rejected_chain_segments.append(
                        rejected
                    )
                else:
                    filtered_chains[
                        side
                    ].append(
                        segment
                    )

        chains = filtered_chains

        for side, segments in chains.items():
            segments.sort(
                key=lambda item: min(
                    item["axis_start"],
                    item["axis_end"],
                )
            )

        # -------------------------------------------------------------
        # Merge CAD pieces into LOGICAL openings.
        # Same semantic type + touching/nearby bboxes are one candidate.
        # -------------------------------------------------------------
        merge_gap = region_min_span * 0.015

        def boxes_near(a, b):
            if a["semantic_type"] != b["semantic_type"]:
                return False

            ax0, ay0, ax1, ay1 = a["bbox"]
            bx0, by0, bx1, by1 = b["bbox"]

            dx = max(
                0.0,
                max(ax0, bx0)
                - min(ax1, bx1),
            )
            dy = max(
                0.0,
                max(ay0, by0)
                - min(ay1, by1),
            )

            return (
                dx <= merge_gap
                and dy <= merge_gap
            )

        unused = set(
            range(
                len(raw_opening_parts)
            )
        )
        logical_openings = []

        while unused:
            seed = unused.pop()
            group_indices = {seed}
            queue = [seed]

            while queue:
                current = queue.pop()

                for other in list(unused):
                    if boxes_near(
                        raw_opening_parts[current],
                        raw_opening_parts[other],
                    ):
                        unused.remove(other)
                        group_indices.add(other)
                        queue.append(other)

            group = [
                raw_opening_parts[index]
                for index in group_indices
            ]

            xmin = min(
                item["bbox"][0]
                for item in group
            )
            ymin = min(
                item["bbox"][1]
                for item in group
            )
            xmax = max(
                item["bbox"][2]
                for item in group
            )
            ymax = max(
                item["bbox"][3]
                for item in group
            )

            logical_openings.append({
                "semantic_type": group[0][
                    "semantic_type"
                ],
                "layer": group[0]["layer"],
                "bbox": [
                    float(xmin),
                    float(ymin),
                    float(xmax),
                    float(ymax),
                ],
                "center": [
                    float(
                        (xmin + xmax) * 0.5
                    ),
                    float(
                        (ymin + ymax) * 0.5
                    ),
                ],
                "member_handles": [
                    item["handle"]
                    for item in group
                    if item["handle"]
                ],
                "member_count": len(group),
            })

        # -------------------------------------------------------------
        # Distance from logical opening rectangle to ACTUAL wall segment.
        # Projection into the segment's tangent/normal frame lets a window
        # touching a wall score 0 even when its bbox centre is offset.
        # -------------------------------------------------------------
        wall_contact_tolerance = (
            region_min_span * 0.006
        )

        def opening_to_segment_gap(
            opening,
            segment,
        ):
            x0, y0 = segment["start"]
            x1, y1 = segment["end"]

            dx = x1 - x0
            dy = y1 - y0
            length = math.hypot(dx, dy)

            if length <= 1e-9:
                return float("inf")

            tx = dx / length
            ty = dy / length
            nx = -ty
            ny = tx

            xmin, ymin, xmax, ymax = opening["bbox"]

            corners = (
                (xmin, ymin),
                (xmin, ymax),
                (xmax, ymin),
                (xmax, ymax),
            )

            tangent_values = []
            normal_values = []

            for px, py in corners:
                rx = px - x0
                ry = py - y0

                tangent_values.append(
                    rx * tx + ry * ty
                )
                normal_values.append(
                    rx * nx + ry * ny
                )

            tang_min = min(tangent_values)
            tang_max = max(tangent_values)
            norm_min = min(normal_values)
            norm_max = max(normal_values)

            along_gap = max(
                0.0,
                -tang_max,
                tang_min - length,
            )

            if (
                norm_min <= 0.0
                <= norm_max
            ):
                normal_gap = 0.0
            else:
                normal_gap = min(
                    abs(norm_min),
                    abs(norm_max),
                )

            return math.hypot(
                along_gap,
                normal_gap,
            )

        exterior_openings = []
        rejected_openings = []
        side_openings = {
            "bottom": [],
            "top": [],
            "left": [],
            "right": [],
        }

        all_chain_segments = []

        for side, segments in chains.items():
            for segment in segments:
                all_chain_segments.append(
                    (
                        side,
                        segment,
                    )
                )

        for opening_index, opening in enumerate(
            logical_openings,
            start=1,
        ):
            candidates = []

            for side, segment in all_chain_segments:
                gap = opening_to_segment_gap(
                    opening,
                    segment,
                )

                candidates.append(
                    (
                        float(gap),
                        side,
                        segment,
                    )
                )

            candidates.sort(
                key=lambda item:
                item[0]
            )

            if not candidates:
                rejected = dict(opening)
                rejected.update({
                    "logical_id": opening_index,
                    "reason": "no exterior wall chain",
                })
                rejected_openings.append(rejected)
                continue

            best_gap, best_side, best_segment = (
                candidates[0]
            )

            second_gap = (
                candidates[1][0]
                if len(candidates) > 1
                else float("inf")
            )

            # At corners, two sides can be equally close. Reject truly ambiguous
            # candidates rather than inventing a side assignment.
            ambiguous = (
                second_gap
                <= wall_contact_tolerance
                and abs(
                    second_gap - best_gap
                )
                <= wall_contact_tolerance
                * 0.20
                and len(candidates) > 1
                and candidates[1][1]
                != best_side
            )

            if (
                best_gap
                > wall_contact_tolerance
                or ambiguous
            ):
                rejected = dict(opening)
                rejected.update({
                    "logical_id": opening_index,
                    "nearest_side": best_side,
                    "distance_to_wall": float(
                        best_gap
                    ),
                    "reason": (
                        "ambiguous corner"
                        if ambiguous
                        else "does not contact exterior wall"
                    ),
                })
                rejected_openings.append(rejected)
                continue

            if best_side in {
                "bottom",
                "top",
            }:
                along_values = [
                    project(
                        (px, py)
                    )[0]
                    for px, py in (
                        (
                            opening["bbox"][0],
                            opening["bbox"][1],
                        ),
                        (
                            opening["bbox"][2],
                            opening["bbox"][1],
                        ),
                        (
                            opening["bbox"][0],
                            opening["bbox"][3],
                        ),
                        (
                            opening["bbox"][2],
                            opening["bbox"][3],
                        ),
                    )
                ]

                chain_values = []

                for segment in chains[
                    best_side
                ]:
                    chain_values.extend([
                        segment["axis_start"],
                        segment["axis_end"],
                    ])
            else:
                along_values = [
                    project(
                        (px, py)
                    )[1]
                    for px, py in (
                        (
                            opening["bbox"][0],
                            opening["bbox"][1],
                        ),
                        (
                            opening["bbox"][2],
                            opening["bbox"][1],
                        ),
                        (
                            opening["bbox"][0],
                            opening["bbox"][3],
                        ),
                        (
                            opening["bbox"][2],
                            opening["bbox"][3],
                        ),
                    )
                ]

                chain_values = []

                for segment in chains[
                    best_side
                ]:
                    chain_values.extend([
                        segment["axis_start"],
                        segment["axis_end"],
                    ])

            if chain_values:
                chain_min = min(chain_values)
                chain_max = max(chain_values)
            else:
                chain_min = 0.0
                chain_max = 1.0

            chain_span = max(
                chain_max - chain_min,
                1e-9,
            )

            opening_axis_min = min(
                along_values
            )
            opening_axis_max = max(
                along_values
            )
            opening_axis_center = (
                opening_axis_min
                + opening_axis_max
            ) * 0.5

            record = dict(opening)
            record.update({
                "logical_id": opening_index,
                "plan_side": best_side,
                "distance_to_wall": float(
                    best_gap
                ),
                "relative_position": float(
                    max(
                        0.0,
                        min(
                            1.0,
                            (
                                opening_axis_center
                                - chain_min
                            )
                            / chain_span,
                        ),
                    )
                ),
                "projected_width": float(
                    abs(
                        opening_axis_max
                        - opening_axis_min
                    )
                ),
                "axis_position": float(
                    opening_axis_center
                ),
                "axis_start": float(
                    opening_axis_min
                ),
                "axis_end": float(
                    opening_axis_max
                ),
                "wall_segment_handle": (
                    best_segment.get(
                        "handle",
                        "",
                    )
                ),
            })

            exterior_openings.append(record)
            side_openings[
                best_side
            ].append(record)

        for side in side_openings:
            side_openings[
                side
            ].sort(
                key=lambda item:
                item[
                    "relative_position"
                ]
            )

            for order, item in enumerate(
                side_openings[
                    side
                ],
                start=1,
            ):
                item[
                    "sequence_index"
                ] = order

        output_chains = {}

        for side, segments in chains.items():
            output_chains[
                side
            ] = {
                "segments": segments,
                "segment_count": len(
                    segments
                ),
                "length": float(
                    sum(
                        segment["length"]
                        for segment
                        in segments
                    )
                ),
                "openings": side_openings[
                    side
                ],
                "opening_count": len(
                    side_openings[
                        side
                    ]
                ),
                "opening_sequence": [
                    item["semantic_type"]
                    for item
                    in side_openings[
                        side
                    ]
                ],
            }

        return {
            "version": 2,
            "wall_source": wall_source,
            "dominant_angle_deg": float(
                math.degrees(theta)
            ),
            "bounds_uv": {
                "u_min": float(u_min),
                "u_max": float(u_max),
                "v_min": float(v_min),
                "v_max": float(v_max),
            },
            "wall_contact_tolerance": float(
                wall_contact_tolerance
            ),
            "chains": output_chains,
            "rejected_chain_segments": rejected_chain_segments,
            "logical_openings": logical_openings,
            "exterior_openings": exterior_openings,
            "interior_or_unassigned_openings": rejected_openings,
        }

    def analyze_facade_matching_inputs(
        self,
        rect_values,
        floor_settings,
    ):
        """
        ALL-FLOOR FACADE OPENING DETECTOR V7.

        1) Detect every logical Window / Door / Sliding Door in the facade.
        2) Determine natural horizontal storey bands from opening centre-Y.
        3) Number of bands = number of confirmed floor plans.
        4) Map lowest band -> lowest Floor Elevation, next band -> next floor.
        5) No detected opening is discarded.
        """
        try:
            x, y, w, h = [
                float(v)
                for v in rect_values
            ]
        except Exception:
            return {
                "version": 7,
                "logical_openings": [],
                "floors": {},
                "unassigned_openings": [],
            }

        left = min(x, x + w)
        right = max(x, x + w)
        bottom = min(y, y + h)
        top = max(y, y + h)

        region_w = max(
            right - left,
            1e-9,
        )
        region_h = max(
            top - bottom,
            1e-9,
        )

        doc = self._document
        if doc is None:
            return {
                "version": 7,
                "logical_openings": [],
                "floors": {},
                "unassigned_openings": [],
            }

        try:
            modelspace = doc.modelspace()
        except Exception:
            return {
                "version": 7,
                "logical_openings": [],
                "floors": {},
                "unassigned_openings": [],
            }

        # PLAN3D_FACADE_BLOCK_WINDOW_SOURCE_V20AP
        #
        # Facade opening analysis must read the SAME current layer semantics
        # that the viewport/floor pipeline sees.
        #
        # Old behavior scanned only TOP-LEVEL modelspace entities. Therefore
        # Window geometry inside INSERT/BLOCK structures could be visibly
        # assigned as Window but still never enter facade matching.
        #
        # New behavior:
        #   - recursively expands INSERT.virtual_entities()
        #   - respects an explicit child semantic layer
        #   - layer 0 children inherit an opening semantic from their INSERT
        #   - ignores text/hatch/annotation pieces as opening geometry
        #   - falls back to INSERT bbox only if the block cannot be expanded
        #
        # No layer-name heuristics are used.
        raw = []

        opening_semantics = {
            "Window",
            "Door",
            "Sliding Door",
        }

        opening_geometry_types = {
            "LINE",
            "LWPOLYLINE",
            "POLYLINE",
            "ARC",
            "CIRCLE",
            "ELLIPSE",
            "SPLINE",
        }

        def append_opening_part(
            entity,
            semantic_type,
            layer,
            inherited_handle="",
        ):
            try:
                box = ezdxf_bbox.extents(
                    [entity],
                    fast=True,
                )

                if not box.has_data:
                    return False

                xmin = float(
                    box.extmin.x
                )
                ymin = float(
                    box.extmin.y
                )
                xmax = float(
                    box.extmax.x
                )
                ymax = float(
                    box.extmax.y
                )
            except Exception:
                return False

            cx = (
                xmin + xmax
            ) * 0.5

            cy = (
                ymin + ymax
            ) * 0.5

            if not (
                left <= cx <= right
                and bottom <= cy <= top
            ):
                return False

            try:
                handle = str(
                    entity.dxf.handle
                    or ""
                )
            except Exception:
                handle = ""

            if not handle:
                handle = str(
                    inherited_handle
                    or ""
                )

            raw.append({
                "handle":
                    handle,
                "layer":
                    str(
                        layer
                        or "0"
                    ),
                "semantic_type":
                    semantic_type,
                "bbox": [
                    xmin,
                    ymin,
                    xmax,
                    ymax,
                ],
                "center": [
                    cx,
                    cy,
                ],
            })

            return True

        def consume_opening_entity(
            entity,
            inherited_semantic=None,
            inherited_handle="",
            depth=0,
        ):
            if depth > 10:
                return 0

            try:
                layer = str(
                    entity.dxf.layer
                )
            except Exception:
                layer = "0"

            try:
                own_semantic = (
                    self.get_layer_type(
                        layer
                    )
                )
            except Exception:
                own_semantic = (
                    "Unassigned"
                )

            try:
                dtype = str(
                    entity.dxftype()
                ).upper()
            except Exception:
                dtype = ""

            try:
                own_handle = str(
                    entity.dxf.handle
                    or ""
                )
            except Exception:
                own_handle = ""

            effective_semantic = (
                own_semantic
                if own_semantic
                in opening_semantics
                else (
                    inherited_semantic
                    if (
                        layer in {
                            "",
                            "0",
                        }
                        and inherited_semantic
                        in opening_semantics
                    )
                    else None
                )
            )

            root_handle = (
                own_handle
                or inherited_handle
                or ""
            )

            if dtype == "INSERT":
                child_inherited = (
                    own_semantic
                    if own_semantic
                    in opening_semantics
                    else (
                        inherited_semantic
                        if inherited_semantic
                        in opening_semantics
                        else None
                    )
                )

                expanded = 0

                try:
                    virtual_entities = list(
                        entity.virtual_entities()
                    )
                except Exception:
                    virtual_entities = []

                for child in virtual_entities:
                    expanded += (
                        consume_opening_entity(
                            child,
                            inherited_semantic=
                                child_inherited,
                            inherited_handle=
                                root_handle,
                            depth=
                                depth + 1,
                        )
                    )

                if expanded > 0:
                    return expanded

                if (
                    effective_semantic
                    in opening_semantics
                ):
                    return int(
                        append_opening_part(
                            entity,
                            effective_semantic,
                            layer,
                            root_handle,
                        )
                    )

                return 0

            if (
                effective_semantic
                not in opening_semantics
            ):
                return 0

            if (
                dtype
                not in opening_geometry_types
            ):
                return 0

            return int(
                append_opening_part(
                    entity,
                    effective_semantic,
                    layer,
                    root_handle,
                )
            )

        for entity in modelspace:
            consume_opening_entity(
                entity
            )

        print(
            "PLAN3D FACADE BLOCK WINDOW SOURCE V20AP |",
            "raw_opening_parts=",
            len(raw),
            "| recursive_insert_support=ON",
            flush=True,
        )

        # Merge CAD pieces that belong to one logical opening.
        gap_x = region_w * 0.010
        gap_y = region_h * 0.010

        def near(a, b):
            if (
                a["semantic_type"]
                != b["semantic_type"]
            ):
                return False

            ax0, ay0, ax1, ay1 = a["bbox"]
            bx0, by0, bx1, by1 = b["bbox"]

            dx = max(
                0.0,
                max(ax0, bx0)
                - min(ax1, bx1),
            )
            dy = max(
                0.0,
                max(ay0, by0)
                - min(ay1, by1),
            )

            return (
                dx <= gap_x
                and dy <= gap_y
            )

        unused = set(
            range(len(raw))
        )
        logical = []

        while unused:
            seed = unused.pop()
            group_indices = {seed}
            queue = [seed]

            while queue:
                current = queue.pop()

                for other in list(unused):
                    if near(
                        raw[current],
                        raw[other],
                    ):
                        unused.remove(other)
                        group_indices.add(other)
                        queue.append(other)

            group = [
                raw[index]
                for index in group_indices
            ]

            xmin = min(
                item["bbox"][0]
                for item in group
            )
            ymin = min(
                item["bbox"][1]
                for item in group
            )
            xmax = max(
                item["bbox"][2]
                for item in group
            )
            ymax = max(
                item["bbox"][3]
                for item in group
            )

            logical.append({
                "semantic_type": group[0][
                    "semantic_type"
                ],
                "bbox": [
                    float(xmin),
                    float(ymin),
                    float(xmax),
                    float(ymax),
                ],
                "center": [
                    float(
                        (xmin + xmax) * 0.5
                    ),
                    float(
                        (ymin + ymax) * 0.5
                    ),
                ],
                "relative_x": float(
                    (
                        (xmin + xmax) * 0.5
                        - left
                    )
                    / region_w
                ),
                "relative_y": float(
                    (
                        (ymin + ymax) * 0.5
                        - bottom
                    )
                    / region_h
                ),
                "relative_width": float(
                    (xmax - xmin)
                    / region_w
                ),
                "cad_width": float(
                    xmax - xmin
                ),
                "axis_position": float(
                    (xmin + xmax) * 0.5
                ),
                "axis_start": float(xmin),
                "axis_end": float(xmax),
                "member_handles": [
                    item["handle"]
                    for item in group
                    if item["handle"]
                ],
                "member_count": len(group),
            })

        logical.sort(
            key=lambda item: (
                item["center"][1],
                item["center"][0],
            )
        )

        # Confirmed floors only.
        floor_records = []

        if isinstance(
            floor_settings,
            dict,
        ):
            for floor_name, values in floor_settings.items():
                values = (
                    values
                    if isinstance(values, dict)
                    else {}
                )

                try:
                    elevation = float(
                        values.get(
                            "floor_elevation_cm",
                            0.0,
                        )
                    )
                except Exception:
                    elevation = 0.0

                try:
                    wall_height = float(
                        values.get(
                            "wall_height_cm",
                            280.0,
                        )
                    )
                except Exception:
                    wall_height = 280.0

                floor_records.append({
                    "name": str(floor_name),
                    "elevation_cm": elevation,
                    "wall_height_cm": wall_height,
                })

        floor_records.sort(
            key=lambda item:
            item["elevation_cm"]
        )

        floors = {
            floor["name"]: {
                "elevation_cm": floor[
                    "elevation_cm"
                ],
                "wall_height_cm": floor[
                    "wall_height_cm"
                ],
                "openings": [],
                "opening_sequence": [],
                "window_count": 0,
                "door_count": 0,
                "sliding_door_count": 0,
            }
            for floor in floor_records
        }

        unassigned = []

        if logical and floor_records:
            band_count = min(
                len(floor_records),
                len(logical),
            )

            y_values = [
                float(
                    opening["center"][1]
                )
                for opening in logical
            ]

            # Deterministic 1D k-means initialization from vertical quantiles.
            y_sorted = sorted(y_values)

            if band_count == 1:
                centers = [
                    sum(y_values)
                    / len(y_values)
                ]
            else:
                centers = []

                for index in range(
                    band_count
                ):
                    q = (
                        index
                        / max(
                            band_count - 1,
                            1,
                        )
                    )
                    source_index = int(
                        round(
                            q
                            * (
                                len(y_sorted)
                                - 1
                            )
                        )
                    )
                    centers.append(
                        y_sorted[
                            source_index
                        ]
                    )

            assignments = [
                0
                for _ in logical
            ]

            for _iteration in range(32):
                changed = False

                for opening_index, opening in enumerate(
                    logical
                ):
                    cy = float(
                        opening[
                            "center"
                        ][1]
                    )

                    chosen = min(
                        range(
                            len(centers)
                        ),
                        key=lambda idx:
                        abs(
                            cy
                            - centers[idx]
                        ),
                    )

                    if (
                        assignments[
                            opening_index
                        ]
                        != chosen
                    ):
                        assignments[
                            opening_index
                        ] = chosen
                        changed = True

                new_centers = []

                for cluster_index in range(
                    len(centers)
                ):
                    members = [
                        float(
                            logical[
                                opening_index
                            ][
                                "center"
                            ][1]
                        )
                        for opening_index
                        in range(
                            len(logical)
                        )
                        if assignments[
                            opening_index
                        ]
                        == cluster_index
                    ]

                    if members:
                        new_centers.append(
                            sum(members)
                            / len(members)
                        )
                    else:
                        new_centers.append(
                            centers[
                                cluster_index
                            ]
                        )

                if all(
                    abs(
                        new_centers[index]
                        - centers[index]
                    )
                    <= 1e-7
                    for index in range(
                        len(centers)
                    )
                ):
                    centers = new_centers
                    break

                centers = new_centers

                if not changed:
                    break

            # Re-number clusters strictly bottom -> top.
            ordered_cluster_ids = sorted(
                range(len(centers)),
                key=lambda idx:
                centers[idx],
            )

            cluster_to_floor = {}

            for order_index, cluster_id in enumerate(
                ordered_cluster_ids
            ):
                if order_index < len(
                    floor_records
                ):
                    cluster_to_floor[
                        cluster_id
                    ] = floor_records[
                        order_index
                    ]

            for opening_index, opening in enumerate(
                logical
            ):
                cluster_id = assignments[
                    opening_index
                ]
                floor = cluster_to_floor.get(
                    cluster_id
                )

                if floor is None:
                    unassigned.append(
                        opening
                    )
                    continue

                opening[
                    "floor_name"
                ] = floor[
                    "name"
                ]
                opening[
                    "floor_band_center_y"
                ] = float(
                    centers[
                        cluster_id
                    ]
                )

                floors[
                    floor[
                        "name"
                    ]
                ][
                    "openings"
                ].append(
                    opening
                )

        elif logical:
            unassigned = list(
                logical
            )

        for floor_name, payload in floors.items():
            payload[
                "openings"
            ].sort(
                key=lambda item:
                item[
                    "axis_position"
                ]
            )

            for sequence_index, opening in enumerate(
                payload[
                    "openings"
                ],
                start=1,
            ):
                opening[
                    "sequence_index"
                ] = sequence_index

            payload[
                "opening_sequence"
            ] = [
                opening[
                    "semantic_type"
                ]
                for opening
                in payload[
                    "openings"
                ]
            ]

            # ---------------------------------------------------------
            # WINDOW / OPENING VERTICAL ANALYSIS
            #
            # Use the detected facade floor band as the drawing-space
            # reference and convert opening Y extents into the real
            # Floor Elevation + Wall Height range.
            # ---------------------------------------------------------
            floor_openings = payload[
                "openings"
            ]

            if floor_openings:
                observed_y_min = min(
                    float(
                        opening[
                            "bbox"
                        ][1]
                    )
                    for opening in floor_openings
                )
                observed_y_max = max(
                    float(
                        opening[
                            "bbox"
                        ][3]
                    )
                    for opening in floor_openings
                )

                try:
                    own_band_center = float(
                        floor_openings[
                            0
                        ].get(
                            "floor_band_center_y"
                        )
                    )
                except Exception:
                    own_band_center = (
                        observed_y_min
                        + observed_y_max
                    ) * 0.5

                other_band_centers = []

                for other_name, other_payload in floors.items():
                    if other_name == floor_name:
                        continue

                    other_openings = other_payload.get(
                        "openings",
                        [],
                    )

                    if not other_openings:
                        continue

                    try:
                        other_band_centers.append(
                            float(
                                other_openings[
                                    0
                                ].get(
                                    "floor_band_center_y"
                                )
                            )
                        )
                    except Exception:
                        pass

                if other_band_centers:
                    nearest_center_distance = min(
                        abs(
                            other_center
                            - own_band_center
                        )
                        for other_center
                        in other_band_centers
                    )

                    band_y_min = (
                        own_band_center
                        - nearest_center_distance
                        * 0.5
                    )
                    band_y_max = (
                        own_band_center
                        + nearest_center_distance
                        * 0.5
                    )

                    # Never make the band smaller than the actual openings.
                    band_y_min = min(
                        band_y_min,
                        observed_y_min,
                    )
                    band_y_max = max(
                        band_y_max,
                        observed_y_max,
                    )
                else:
                    # Single-floor facade fallback: use the full selected
                    # facade vertical range rather than the opening bbox only.
                    band_y_min = bottom
                    band_y_max = top

                band_y_span = max(
                    band_y_max
                    - band_y_min,
                    1e-9,
                )

                floor_elevation_cm = float(
                    payload.get(
                        "elevation_cm",
                        0.0,
                    )
                )
                wall_height_cm = float(
                    payload.get(
                        "wall_height_cm",
                        280.0,
                    )
                )

                payload[
                    "facade_band_y_min"
                ] = float(
                    band_y_min
                )
                payload[
                    "facade_band_y_max"
                ] = float(
                    band_y_max
                )

                for opening in floor_openings:
                    oy0 = float(
                        opening[
                            "bbox"
                        ][1]
                    )
                    oy1 = float(
                        opening[
                            "bbox"
                        ][3]
                    )

                    local_bottom_ratio = max(
                        0.0,
                        min(
                            1.0,
                            (
                                oy0
                                - band_y_min
                            )
                            / band_y_span,
                        ),
                    )
                    local_top_ratio = max(
                        0.0,
                        min(
                            1.0,
                            (
                                oy1
                                - band_y_min
                            )
                            / band_y_span,
                        ),
                    )

                    local_sill_cm = (
                        local_bottom_ratio
                        * wall_height_cm
                    )
                    local_top_cm = (
                        local_top_ratio
                        * wall_height_cm
                    )

                    opening[
                        "floor_local_sill_cm"
                    ] = float(
                        local_sill_cm
                    )
                    opening[
                        "floor_local_top_cm"
                    ] = float(
                        local_top_cm
                    )
                    opening[
                        "sill_z_cm"
                    ] = float(
                        floor_elevation_cm
                        + local_sill_cm
                    )
                    opening[
                        "top_z_cm"
                    ] = float(
                        floor_elevation_cm
                        + local_top_cm
                    )
                    opening[
                        "height_cm"
                    ] = float(
                        max(
                            0.0,
                            local_top_cm
                            - local_sill_cm,
                        )
                    )

            payload[
                "window_count"
            ] = sum(
                1
                for opening
                in payload[
                    "openings"
                ]
                if opening[
                    "semantic_type"
                ]
                == "Window"
            )
            payload[
                "door_count"
            ] = sum(
                1
                for opening
                in payload[
                    "openings"
                ]
                if opening[
                    "semantic_type"
                ]
                == "Door"
            )
            payload[
                "sliding_door_count"
            ] = sum(
                1
                for opening
                in payload[
                    "openings"
                ]
                if opening[
                    "semantic_type"
                ]
                == "Sliding Door"
            )

        return {
            "version": 7,
            "bounds": [
                float(left),
                float(bottom),
                float(right),
                float(top),
            ],
            "logical_openings": logical,
            "logical_opening_count": len(
                logical
            ),
            "raw_opening_parts": [
                dict(item)
                for item in raw
            ],
            "floors": floors,
            "floor_order": [
                floor["name"]
                for floor in floor_records
            ],
            "unassigned_openings": unassigned,
        }

    def analyze_facade_window_verticals(
        self,
        rect_values,
        floor_settings,
    ):
        result = self.analyze_facade_matching_inputs(
            rect_values,
            floor_settings,
        )

        floors = {}

        for floor_name, payload in result.get(
            "floors",
            {},
        ).items():
            windows = []

            for opening in payload.get(
                "openings",
                [],
            ):
                if opening.get(
                    "semantic_type"
                ) != "Window":
                    continue

                windows.append({
                    "sequence_index": opening.get(
                        "sequence_index"
                    ),
                    "center": opening.get(
                        "center"
                    ),
                    "cad_width": opening.get(
                        "cad_width"
                    ),
                    "sill_z_cm": opening.get(
                        "sill_z_cm"
                    ),
                    "top_z_cm": opening.get(
                        "top_z_cm"
                    ),
                    "height_cm": opening.get(
                        "height_cm"
                    ),
                    "floor_local_sill_cm": opening.get(
                        "floor_local_sill_cm"
                    ),
                    "floor_local_top_cm": opening.get(
                        "floor_local_top_cm"
                    ),
                    "bbox": opening.get(
                        "bbox"
                    ),
                    "member_handles": opening.get(
                        "member_handles",
                        [],
                    ),
                })

            floors[
                floor_name
            ] = {
                "window_count": len(
                    windows
                ),
                "windows": windows,
                "floor_elevation_cm": payload.get(
                    "elevation_cm"
                ),
                "wall_height_cm": payload.get(
                    "wall_height_cm"
                ),
                "facade_band_y_min": payload.get(
                    "facade_band_y_min"
                ),
                "facade_band_y_max": payload.get(
                    "facade_band_y_max"
                ),
            }

        return {
            "version": 1,
            "floors": floors,
        }

    def clear_facade_match_verification(self):
        scene = self.scene()

        if scene is not None:
            for item in list(
                self._facade_verification_items
            ):
                try:
                    scene.removeItem(item)
                except Exception:
                    pass

        self._facade_verification_items = []

    def clear_exterior_wall_analysis(self):
        scene = self.scene()

        if scene is not None:
            for item in list(
                self._exterior_analysis_items
            ):
                try:
                    scene.removeItem(item)
                except Exception:
                    pass

        self._exterior_analysis_items = []

    def show_exterior_wall_analysis(
        self,
        floor_name,
        analysis,
    ):
        """
        Visual debug overlay for the exterior-wall analysis.

        This is intentionally diagnostic only:
        - does not change CAD geometry
        - does not change layer colors
        - does not affect saved semantic assignments
        """
        self.clear_exterior_wall_analysis()

        if not isinstance(
            analysis,
            dict,
        ):
            return

        scene = self.scene()

        if scene is None:
            return

        chains = analysis.get(
            "chains",
            {},
        )

        if not isinstance(
            chains,
            dict,
        ):
            return

        side_colors = {
            "bottom": QColor("#00C2FF"),
            "top": QColor("#FF5A5F"),
            "left": QColor("#F2C94C"),
            "right": QColor("#A56BFF"),
        }

        side_labels = {
            "bottom": "BOTTOM",
            "top": "TOP",
            "left": "LEFT",
            "right": "RIGHT",
        }

        # Draw wall-chain segments with strong diagnostic colors.
        for side in (
            "bottom",
            "top",
            "left",
            "right",
        ):
            payload = chains.get(
                side,
                {},
            )

            if not isinstance(
                payload,
                dict,
            ):
                continue

            segments = payload.get(
                "segments",
                [],
            )

            pen = QPen(
                side_colors[side]
            )
            pen.setWidthF(3.0)
            pen.setCosmetic(True)

            label_anchor = None

            for segment in segments:
                try:
                    x0, y0 = segment[
                        "start"
                    ]
                    x1, y1 = segment[
                        "end"
                    ]
                except Exception:
                    continue

                line_item = scene.addLine(
                    float(x0),
                    float(y0),
                    float(x1),
                    float(y1),
                    pen,
                )
                line_item.setZValue(
                    1000200
                )
                self._exterior_analysis_items.append(
                    line_item
                )

                if label_anchor is None:
                    label_anchor = (
                        (
                            float(x0)
                            + float(x1)
                        )
                        * 0.5,
                        (
                            float(y0)
                            + float(y1)
                        )
                        * 0.5,
                    )

            if label_anchor is not None:
                text = QGraphicsSimpleTextItem(
                    side_labels[
                        side
                    ]
                )
                text.setBrush(
                    QBrush(
                        side_colors[
                            side
                        ]
                    )
                )
                text.setFlag(
                    QGraphicsItem.ItemIgnoresTransformations,
                    True,
                )
                text.setZValue(
                    1000202
                )
                text.setPos(
                    float(
                        label_anchor[0]
                    ),
                    float(
                        label_anchor[1]
                    ),
                )
                scene.addItem(
                    text
                )
                self._exterior_analysis_items.append(
                    text
                )

            # Draw opening markers in chain order.
            openings = payload.get(
                "openings",
                [],
            )

            for index, opening in enumerate(
                openings,
                start=1,
            ):
                try:
                    cx, cy = opening[
                        "center"
                    ]
                except Exception:
                    continue

                marker_pen = QPen(
                    QColor("#FFFFFF")
                )
                marker_pen.setWidthF(1.5)
                marker_pen.setCosmetic(
                    True
                )

                marker = scene.addEllipse(
                    float(cx) - 2.5,
                    float(cy) - 2.5,
                    5.0,
                    5.0,
                    marker_pen,
                    QBrush(
                        side_colors[
                            side
                        ]
                    ),
                )
                marker.setFlag(
                    QGraphicsItem.ItemIgnoresTransformations,
                    True,
                )
                marker.setZValue(
                    1000204
                )
                self._exterior_analysis_items.append(
                    marker
                )

                opening_label = (
                    opening.get(
                        "semantic_type",
                        "OPENING",
                    )
                    + " "
                    + str(index)
                )

                label = QGraphicsSimpleTextItem(
                    opening_label
                )
                label.setBrush(
                    QBrush(
                        QColor(
                            "#FFFFFF"
                        )
                    )
                )
                label.setFlag(
                    QGraphicsItem.ItemIgnoresTransformations,
                    True,
                )
                label.setZValue(
                    1000205
                )
                label.setPos(
                    float(cx) + 4.0,
                    float(cy) + 4.0,
                )
                scene.addItem(
                    label
                )
                self._exterior_analysis_items.append(
                    label
                )

        # Floor diagnostic title.
        title = QGraphicsSimpleTextItem(
            str(floor_name).upper()
            + " - EXTERIOR ANALYSIS"
        )
        title.setBrush(
            QBrush(
                QColor("#FFFFFF")
            )
        )
        title.setFlag(
            QGraphicsItem.ItemIgnoresTransformations,
            True,
        )
        title.setZValue(
            1000210
        )

        bounds = analysis.get(
            "bounds_uv",
            {},
        )

        # Put the title near the first available chain segment.
        title_pos = None

        for side in (
            "bottom",
            "top",
            "left",
            "right",
        ):
            payload = chains.get(
                side,
                {},
            )
            segments = (
                payload.get(
                    "segments",
                    [],
                )
                if isinstance(
                    payload,
                    dict,
                )
                else []
            )

            if segments:
                try:
                    title_pos = tuple(
                        segments[0][
                            "start"
                        ]
                    )
                except Exception:
                    title_pos = None

                if title_pos is not None:
                    break

        if title_pos is not None:
            title.setPos(
                float(
                    title_pos[0]
                ),
                float(
                    title_pos[1]
                ),
            )
            scene.addItem(
                title
            )
            self._exterior_analysis_items.append(
                title
            )

        self.viewport().update()

    def show_facade_match_verification(
        self,
        mapping_result,
        floor_results,
        facade_results,
        facade_assignments,
    ):
        """
        Draw a concise, human-readable proof view of plan-side <-> facade
        matching.

        Each matched pair gets one letter/color.
        Opening pairs use the same compact ID on plan and facade:
        A1, A2, A3...
        """
        self.clear_facade_match_verification()
        self.clear_exterior_wall_analysis()

        scene = self.scene()

        if (
            scene is None
            or not isinstance(
                mapping_result,
                dict,
            )
        ):
            return

        matches = mapping_result.get(
            "matches",
            {},
        )

        palette = [
            QColor("#00C2FF"),
            QColor("#F2C94C"),
            QColor("#A56BFF"),
            QColor("#39D98A"),
        ]

        pair_letters = [
            "A",
            "B",
            "C",
            "D",
        ]

        def add_text(
            text_value,
            x,
            y,
            color,
            z=1000602,
        ):
            item = QGraphicsSimpleTextItem(
                str(text_value)
            )
            item.setBrush(
                QBrush(color)
            )
            item.setFlag(
                QGraphicsItem.ItemIgnoresTransformations,
                True,
            )
            item.setZValue(z)
            item.setPos(
                float(x),
                float(y),
            )
            scene.addItem(item)
            self._facade_verification_items.append(
                item
            )
            return item

        for pair_index, (
            side,
            match,
        ) in enumerate(
            matches.items()
        ):
            color = palette[
                pair_index
                % len(palette)
            ]
            letter = pair_letters[
                pair_index
                % len(pair_letters)
            ]

            facade_name = str(
                match.get(
                    "facade",
                    "?",
                )
            )

            score = float(
                match.get(
                    "score",
                    0.0,
                )
            )

            # -------------------------------------------------
            # Draw this plan side on every floor.
            # -------------------------------------------------
            plan_anchor = None

            for floor_name, floor_result in floor_results.items():
                if not isinstance(
                    floor_result,
                    dict,
                ):
                    continue

                chain = (
                    floor_result.get(
                        "chains",
                        {},
                    ).get(
                        side,
                        {},
                    )
                )

                if not isinstance(
                    chain,
                    dict,
                ):
                    continue

                pen = QPen(
                    color
                )
                pen.setWidthF(
                    4.0
                )
                pen.setCosmetic(
                    True
                )

                for segment in chain.get(
                    "segments",
                    [],
                ):
                    try:
                        x0, y0 = segment[
                            "start"
                        ]
                        x1, y1 = segment[
                            "end"
                        ]
                    except Exception:
                        continue

                    line = scene.addLine(
                        float(x0),
                        float(y0),
                        float(x1),
                        float(y1),
                        pen,
                    )
                    line.setZValue(
                        1000600
                    )
                    self._facade_verification_items.append(
                        line
                    )

                    if plan_anchor is None:
                        plan_anchor = (
                            (
                                float(x0)
                                + float(x1)
                            ) * 0.5,
                            (
                                float(y0)
                                + float(y1)
                            ) * 0.5,
                        )

            if plan_anchor is not None:
                add_text(
                    (
                        letter
                        + "  "
                        + "PLAN "
                        + side.upper()
                        + "  ->  "
                        + facade_name.upper()
                        + " FACADE  "
                        + f"{score * 100.0:.0f}%"
                    ),
                    plan_anchor[0],
                    plan_anchor[1],
                    color,
                )

            # -------------------------------------------------
            # Draw facade assignment rectangle with same color.
            # -------------------------------------------------
            rect_values = (
                facade_assignments.get(
                    facade_name
                )
                if isinstance(
                    facade_assignments,
                    dict,
                )
                else None
            )

            if rect_values is not None:
                try:
                    x, y, w, h = [
                        float(v)
                        for v in rect_values
                    ]

                    rect = QRectF(
                        x,
                        y,
                        w,
                        h,
                    ).normalized()

                    pen = QPen(
                        color
                    )
                    pen.setWidthF(
                        3.0
                    )
                    pen.setCosmetic(
                        True
                    )

                    frame = QGraphicsRectItem(
                        rect
                    )
                    frame.setPen(
                        pen
                    )
                    frame.setBrush(
                        QBrush(
                            Qt.NoBrush
                        )
                    )
                    frame.setZValue(
                        1000600
                    )
                    scene.addItem(
                        frame
                    )
                    self._facade_verification_items.append(
                        frame
                    )

                    add_text(
                        (
                            letter
                            + "  "
                            + facade_name.upper()
                            + " FACADE  <-  "
                            + "PLAN "
                            + side.upper()
                            + "  "
                            + f"{score * 100.0:.0f}%"
                        ),
                        rect.left(),
                        rect.top(),
                        color,
                    )
                except Exception:
                    pass

            # -------------------------------------------------
            # Opening pair IDs: same compact marker on both sides.
            # -------------------------------------------------
            opening_pairs = match.get(
                "opening_pairs",
                [],
            )

            for opening_index, pair in enumerate(
                opening_pairs,
                start=1,
            ):
                pair_id = (
                    letter
                    + str(
                        opening_index
                    )
                )

                plan_opening = pair.get(
                    "plan",
                    {}
                )
                facade_opening = pair.get(
                    "facade_opening",
                    {},
                )

                try:
                    pcx, pcy = plan_opening[
                        "center"
                    ]

                    marker = scene.addEllipse(
                        float(pcx) - 3.5,
                        float(pcy) - 3.5,
                        7.0,
                        7.0,
                        QPen(
                            QColor(
                                "#FFFFFF"
                            ),
                            1.2,
                        ),
                        QBrush(
                            color
                        ),
                    )
                    marker.setFlag(
                        QGraphicsItem.ItemIgnoresTransformations,
                        True,
                    )
                    marker.setZValue(
                        1000603
                    )
                    self._facade_verification_items.append(
                        marker
                    )

                    add_text(
                        pair_id,
                        float(pcx) + 5.0,
                        float(pcy) + 5.0,
                        color,
                        1000604,
                    )
                except Exception:
                    pass

                try:
                    fcx, fcy = facade_opening[
                        "center"
                    ]

                    marker = scene.addRect(
                        float(fcx) - 3.5,
                        float(fcy) - 3.5,
                        7.0,
                        7.0,
                        QPen(
                            QColor(
                                "#FFFFFF"
                            ),
                            1.2,
                        ),
                        QBrush(
                            color
                        ),
                    )
                    marker.setFlag(
                        QGraphicsItem.ItemIgnoresTransformations,
                        True,
                    )
                    marker.setZValue(
                        1000603
                    )
                    self._facade_verification_items.append(
                        marker
                    )

                    add_text(
                        pair_id,
                        float(fcx) + 5.0,
                        float(fcy) + 5.0,
                        color,
                        1000604,
                    )
                except Exception:
                    pass

        self.viewport().update()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()

        if delta == 0:
            event.ignore()
            return

        self._user_has_interacted = True

        viewport_pos = event.position().toPoint()
        scene_before = self.mapToScene(
            viewport_pos
        )

        factor = (
            1.20
            if delta > 0
            else 1.0 / 1.20
        )

        self.scale(
            factor,
            factor,
        )

        # Keep the CAD point under the mouse fixed while zooming.
        scene_after = self.mapToScene(
            viewport_pos
        )

        delta_scene = (
            scene_after
            - scene_before
        )

        center_scene = self.mapToScene(
            self.viewport().rect().center()
        )

        self.centerOn(
            center_scene
            - delta_scene
        )

        event.accept()

        # View navigation is not an undoable project operation.

    def mousePressEvent(self, event):
        if (
            self._pivot_edit_enabled
            and event.button() == Qt.LeftButton
            and self._document is not None
        ):
            point, snap_kind = self._snap_floor_pivot(
                event.position().toPoint()
            )

            self._pivot_point_cad = point
            self._pivot_hover_cad = point
            self._pivot_snap_kind = snap_kind
            self._pivot_drag_active = True

            self.viewport().setCursor(
                Qt.SizeAllCursor
            )
            self.viewport().update()
            event.accept()
            return

        if self._assignment_mode and event.button() == Qt.LeftButton:
            self._assignment_start = self.mapToScene(event.position().toPoint())
            scene = self.scene()
            if scene is not None:
                self._assignment_preview = QGraphicsRectItem(QRectF(self._assignment_start, self._assignment_start))
                pen = QPen(QColor("#78AEFF"))
                pen.setWidthF(1.2)
                pen.setCosmetic(True)
                pen.setStyle(Qt.DashLine)
                self._assignment_preview.setPen(pen)
                self._assignment_preview.setBrush(QBrush(Qt.NoBrush))
                self._assignment_preview.setZValue(1000002)
                scene.addItem(self._assignment_preview)
            event.accept()
            return

        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_moved = False
            self._pan_start = event.position().toPoint()

            self._user_has_interacted = True

            self.setCursor(
                Qt.ClosedHandCursor
            )

            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._pivot_edit_enabled
            and not self._panning
            and self._document is not None
        ):
            point, snap_kind = self._snap_floor_pivot(
                event.position().toPoint()
            )

            self._pivot_hover_cad = point
            self._pivot_snap_kind = snap_kind

            if self._pivot_drag_active:
                self._pivot_point_cad = point

            self.viewport().update()
            event.accept()
            return

        if self._assignment_mode and self._assignment_start is not None:
            current = self.mapToScene(event.position().toPoint())
            if self._assignment_preview is not None:
                self._assignment_preview.setRect(QRectF(self._assignment_start, current).normalized())
            event.accept()
            return

        if (
            self._panning
            and self._pan_start is not None
        ):
            current = event.position().toPoint()

            if current != self._pan_start:
                self._pan_moved = True

                previous_scene = self.mapToScene(
                    self._pan_start
                )

                current_scene = self.mapToScene(
                    current
                )

                center_scene = self.mapToScene(
                    self.viewport().rect().center()
                )

                delta_scene = (
                    previous_scene
                    - current_scene
                )

                self.centerOn(
                    center_scene
                    + delta_scene
                )

                self._pan_start = current

            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if (
            self._pivot_edit_enabled
            and self._pivot_drag_active
            and event.button() == Qt.LeftButton
        ):
            point, snap_kind = self._snap_floor_pivot(
                event.position().toPoint()
            )

            floor_name = str(
                self._pivot_floor_name
                or ""
            )

            self._pivot_point_cad = point
            self._pivot_hover_cad = point
            self._pivot_snap_kind = snap_kind
            self._pivot_drag_active = False
            self._pivot_edit_enabled = False
            self._pivot_reference_geometry = ()
            self._clear_pivot_master_guide()

            # Keep the committed point visible. This mirrors the old 3Dcad
            # behavior: after release the pivot remains exactly at the
            # selected CAD point while the floor is waiting for confirmation.
            self.setDragMode(
                QGraphicsView.ScrollHandDrag
            )
            self.viewport().setMouseTracking(
                False
            )
            self.viewport().unsetCursor()
            self.viewport().update()

            self.floorPivotCommitted.emit(
                floor_name,
                float(point[0]),
                float(point[1]),
                str(snap_kind),
            )

            event.accept()
            return

        if self._assignment_mode and event.button() == Qt.LeftButton and self._assignment_start is not None:
            end = self.mapToScene(event.position().toPoint())
            rect = QRectF(self._assignment_start, end).normalized()
            kind = self._assignment_kind
            name = self._assignment_name
            if self._assignment_preview is not None:
                try:
                    self.scene().removeItem(self._assignment_preview)
                except Exception:
                    pass
            self._assignment_preview = None
            self._assignment_start = None
            self._assignment_mode = False
            self._assignment_kind = ""
            self._assignment_name = ""
            self.setCursor(Qt.ArrowCursor)
            if rect.width() > 0 and rect.height() > 0:
                self.assignmentRegionSelected.emit(kind, name, [rect.x(), rect.y(), rect.width(), rect.height()])
            event.accept()
            return

        if (
            event.button() == Qt.MiddleButton
            and self._panning
        ):
            self._panning = False
            self._pan_start = None

            self.setCursor(
                Qt.ArrowCursor
            )

            # View navigation is not an undoable project operation.

            self._pan_moved = False

            event.accept()
            return

        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if (
            not self._user_has_interacted
            and self._home_rect.isValid()
            and self._home_rect.width() > 0
            and self._home_rect.height() > 0
        ):
            self._apply_home_view()
