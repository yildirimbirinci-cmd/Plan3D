from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QBrush, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsPathItem


FLOOR_ENGINE = "PLAN3D_FLOOR_SIMPLE_BOUNDARY_V3"
# PLAN3D_WINDOW_ELEMENT_CONTACT_FALLBACK_V39
MIN_FLOOR_AREA_M2 = 0.0
MAX_WALL_STRIP_WIDTH_MM = 600.0


def _require_shapely():
    try:
        from shapely.geometry import LineString, MultiLineString, Polygon, box
        from shapely.ops import polygonize_full, unary_union
        from shapely import get_parts, make_valid
    except Exception as exc:
        raise RuntimeError(
            'Floor Areas requires Shapely. Run: py -3.12 -m pip install "shapely>=2,<3"'
        ) from exc

    return {
        "LineString": LineString,
        "MultiLineString": MultiLineString,
        "Polygon": Polygon,
        "box": box,
        "polygonize_full": polygonize_full,
        "unary_union": unary_union,
        "get_parts": get_parts,
        "make_valid": make_valid,
    }


def _normalize_rect(values):
    try:
        x, y, w, h = [float(value) for value in values]
    except Exception:
        return None

    x2 = x + w
    y2 = y + h

    x0, x1 = min(x, x2), max(x, x2)
    y0, y1 = min(y, y2), max(y, y2)

    if x1 - x0 <= 1.0e-9 or y1 - y0 <= 1.0e-9:
        return None

    return x0, y0, x1, y1


def _as_segment_paths(paths):
    result = []

    for path in paths or ():
        points = []

        for raw in path or ():
            try:
                points.append(
                    (
                        float(raw[0]),
                        float(raw[1]),
                    )
                )
            except Exception:
                continue

        for a, b in zip(points, points[1:]):
            if a != b:
                result.append(
                    [
                        [a[0], a[1]],
                        [b[0], b[1]],
                    ]
                )

    return result


def _polygon_parts(geometry, api):
    if geometry is None or geometry.is_empty:
        return []

    try:
        if not geometry.is_valid:
            geometry = api["make_valid"](geometry)
    except Exception:
        pass

    try:
        parts = list(api["get_parts"](geometry))
    except Exception:
        parts = [geometry]

    return [
        part
        for part in parts
        if getattr(part, "geom_type", "") == "Polygon"
        and not part.is_empty
        and float(part.area) > 0.0
    ]


def _polygonize(paths, api):
    lines = []

    for path in paths or ():
        try:
            points = [
                (float(point[0]), float(point[1]))
                for point in path
            ]
        except Exception:
            continue

        if len(points) < 2:
            continue

        try:
            line = api["LineString"](points)
        except Exception:
            continue

        if not line.is_empty and float(line.length) > 0.0:
            lines.append(line)

    if not lines:
        return [], {
            "noded": 0,
            "raw_faces": 0,
            "dangles": 0,
            "cuts": 0,
        }

    noded = api["unary_union"](
        api["MultiLineString"](lines)
    )

    polygons_gc, cuts_gc, dangles_gc, invalid_gc = (
        api["polygonize_full"](noded)
    )

    def count_parts(geometry):
        try:
            return len(list(api["get_parts"](geometry)))
        except Exception:
            return 0

    faces = [
        part
        for part in api["get_parts"](polygons_gc)
        if getattr(part, "geom_type", "") == "Polygon"
        and not part.is_empty
        and float(part.area) > 0.0
    ]

    try:
        noded_count = len(list(api["get_parts"](noded)))
    except Exception:
        noded_count = len(lines)

    return faces, {
        "noded": int(noded_count),
        "raw_faces": int(len(faces)),
        "dangles": int(count_parts(dangles_gc)),
        "cuts": int(count_parts(cuts_gc)),
    }






def _path_from_polygon(polygon):
    path = QPainterPath()
    path.setFillRule(Qt.OddEvenFill)

    def add_ring(coords):
        points = list(coords)

        if len(points) < 3:
            return

        path.moveTo(
            QPointF(
                float(points[0][0]),
                float(points[0][1]),
            )
        )

        for x, y in points[1:]:
            path.lineTo(
                QPointF(
                    float(x),
                    float(y),
                )
            )

        path.closeSubpath()

    add_ring(polygon.exterior.coords)

    for interior in polygon.interiors:
        add_ring(interior.coords)

    return path


def _clear_previous(viewport):
    scene = viewport.scene()

    for item in list(
        getattr(
            viewport,
            "_floor_area_overlay_items",
            [],
        )
        or []
    ):
        try:
            if item.scene() is scene:
                scene.removeItem(item)
        except Exception:
            pass

    viewport._floor_area_overlay_items = []


def _add_overlay(viewport, polygon):
    item = QGraphicsPathItem(
        _path_from_polygon(polygon)
    )

    fill = QColor("#F2C94C")
    fill.setAlpha(88)

    item.setBrush(QBrush(fill))
    item.setPen(QPen(Qt.NoPen))
    item.setZValue(-1000.0)

    viewport.scene().addItem(item)
    viewport._floor_area_overlay_items.append(item)


def _export_prepared_wall_paths(
    viewport,
    floor_name,
    rect_values,
    pivot,
    settings,
    units_info,
):
    """
    Single authoritative Wall source for Floor Areas.

    The Wall layer is NOT read here.
    The function reuses the exact Create 3D Model preprocessing result
    returned by plan3d_canonical_export._clean_floor().
    """
    from plan3d_canonical_export import _clean_floor

    export_floor = _clean_floor(
        viewport,
        floor_name,
        rect_values,
        pivot,
        settings,
    )

    cad_to_cm = float(
        export_floor.get(
            "cad_to_cm",
            units_info.get("to_cm", 1.0),
        )
        or 1.0
    )

    if abs(cad_to_cm) <= 1.0e-12:
        raise RuntimeError(
            "Invalid CAD scale for " + str(floor_name)
        )

    pivot_x = float(
        export_floor.get(
            "pivot_x",
            pivot.get("pivot_x", 0.0),
        )
    )
    pivot_y = float(
        export_floor.get(
            "pivot_y",
            pivot.get("pivot_y", 0.0),
        )
    )

    source_paths = []

    for export_path in list(
        export_floor.get("paths", [])
        or []
    ):
        points = []

        for raw_point in list(
            export_path.get("points", [])
            or []
        ):
            try:
                x_cm = float(raw_point[0])
                y_cm = float(raw_point[1])
            except Exception:
                continue

            points.append(
                [
                    (x_cm / cad_to_cm) + pivot_x,
                    (y_cm / cad_to_cm) + pivot_y,
                ]
            )

        if len(points) >= 2:
            source_paths.append(points)

    wall_paths = _as_segment_paths(source_paths)

    if not wall_paths:
        raise RuntimeError(
            "Create 3D export-prepared Wall geometry is empty for "
            + str(floor_name)
        )

    topology_report = dict(
        export_floor.get("topology_report", {})
        or {}
    )

    return wall_paths, topology_report, export_floor


# PLAN3D_FLOOR_INCLUDE_WINDOWS_V2
def _window_paths_in_floor(viewport, rect_values):
    try:
        rx, ry, rw, rh = [float(v) for v in rect_values]
    except Exception:
        return []

    x0 = min(rx, rx + rw)
    x1 = max(rx, rx + rw)
    y0 = min(ry, ry + rh)
    y1 = max(ry, ry + rh)

    doc = getattr(viewport, "_document", None)
    if doc is None:
        return []

    try:
        modelspace = doc.modelspace()
    except Exception:
        return []

    result = []

    def semantic_for(entity, inherited=None):
        try:
            layer = str(entity.dxf.layer)
        except Exception:
            layer = "0"

        try:
            own = str(viewport.get_layer_type(layer))
        except Exception:
            own = "Unassigned"

        if own == "Window":
            return "Window"
        if inherited == "Window":
            return "Window"
        return own

    def add_segment(a, b):
        try:
            ax, ay = float(a[0]), float(a[1])
            bx, by = float(b[0]), float(b[1])
        except Exception:
            return

        mx = (ax + bx) * 0.5
        my = (ay + by) * 0.5

        if not (x0 <= mx <= x1 and y0 <= my <= y1):
            return

        if abs(ax - bx) <= 1.0e-12 and abs(ay - by) <= 1.0e-12:
            return

        result.append([[ax, ay], [bx, by]])

    def consume(entity, inherited=None, depth=0):
        if depth > 10:
            return

        semantic = semantic_for(entity, inherited)

        try:
            dtype = str(entity.dxftype()).upper()
        except Exception:
            dtype = ""

        if dtype == "INSERT":
            child_inherited = "Window" if semantic == "Window" else None
            try:
                children = list(entity.virtual_entities())
            except Exception:
                children = []

            for child in children:
                consume(child, child_inherited, depth + 1)
            return

        if semantic != "Window":
            return

        try:
            if dtype == "LINE":
                a = entity.dxf.start
                b = entity.dxf.end
                add_segment((a.x, a.y), (b.x, b.y))
                return

            if dtype == "LWPOLYLINE":
                pts = [(float(p[0]), float(p[1])) for p in entity.get_points("xy")]
                for a, b in zip(pts, pts[1:]):
                    add_segment(a, b)
                if (
                    bool(getattr(entity, "closed", False) or getattr(entity, "is_closed", False))
                    and len(pts) >= 3
                ):
                    add_segment(pts[-1], pts[0])
                return

            if dtype == "POLYLINE":
                pts = []
                for vertex in entity.vertices:
                    p = vertex.dxf.location
                    pts.append((float(p.x), float(p.y)))
                for a, b in zip(pts, pts[1:]):
                    add_segment(a, b)
                if bool(getattr(entity, "is_closed", False)) and len(pts) >= 3:
                    add_segment(pts[-1], pts[0])
                return
        except Exception:
            return

    for entity in modelspace:
        consume(entity)

    return result


# PLAN3D_FLOOR_DOOR_CLOSURE_FROM_V4



def _symbol_opening_bridge_paths(viewport, rect_values, wall_paths, source_to_mm):
    # PLAN3D_FLOOR_SYMBOL_PATH_BRIDGE_V9
    #
    # B case is NOT a straight 1->3 problem.
    # It is a path problem: Wall point 1 -> opening-symbol point(s) -> Wall point 3.
    #
    # Door / Sliding Door CAD linework is grouped by INSERT when possible.
    # ARC/CIRCLE swing graphics are ignored.
    # A shortest straight-segment path through the opening symbol is used only
    # to bridge between two Create3D-prepared Wall vertices.
    import heapq
    import math

    try:
        rx, ry, rw, rh = [float(v) for v in rect_values]
    except Exception:
        return [], [], {"groups": 0, "door": 0, "sliding": 0, "failed": 0}

    floor_x0 = min(rx, rx + rw)
    floor_x1 = max(rx, rx + rw)
    floor_y0 = min(ry, ry + rh)
    floor_y1 = max(ry, ry + rh)

    doc = getattr(viewport, "_document", None)
    if doc is None:
        return [], [], {"groups": 0, "door": 0, "sliding": 0, "failed": 0}

    try:
        modelspace = doc.modelspace()
    except Exception:
        return [], [], {"groups": 0, "door": 0, "sliding": 0, "failed": 0}

    mm_to_source = 1.0 / max(float(source_to_mm), 1.0e-12)
    node_tol = 12.0 * mm_to_source
    wall_attach_tol = 350.0 * mm_to_source
    search_margin = 450.0 * mm_to_source
    max_wall_span = 6500.0 * mm_to_source

    def dist(a, b):
        return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))

    def semantic_for(entity, inherited=None):
        try:
            layer = str(entity.dxf.layer)
        except Exception:
            layer = "0"

        try:
            own = str(viewport.get_layer_type(layer))
        except Exception:
            own = "Unassigned"

        own_norm = own.strip().lower()

        if "sliding" in own_norm and "door" in own_norm:
            return "Sliding Door"

        if "door" in own_norm:
            return "Door"

        if inherited in {"Door", "Sliding Door"}:
            return inherited

        return own

    def straight_segments(entity):
        try:
            dtype = str(entity.dxftype()).upper()
        except Exception:
            return []

        out = []

        try:
            if dtype == "LINE":
                a = entity.dxf.start
                b = entity.dxf.end
                out.append(((float(a.x), float(a.y)), (float(b.x), float(b.y))))

            elif dtype == "LWPOLYLINE":
                pts = [(float(p[0]), float(p[1])) for p in entity.get_points("xy")]
                for a, b in zip(pts, pts[1:]):
                    out.append((a, b))
                if bool(getattr(entity, "closed", False) or getattr(entity, "is_closed", False)) and len(pts) >= 3:
                    out.append((pts[-1], pts[0]))

            elif dtype == "POLYLINE":
                pts = []
                for vertex in entity.vertices:
                    p = vertex.dxf.location
                    pts.append((float(p.x), float(p.y)))
                for a, b in zip(pts, pts[1:]):
                    out.append((a, b))
                if bool(getattr(entity, "is_closed", False)) and len(pts) >= 3:
                    out.append((pts[-1], pts[0]))

            # ARC/CIRCLE intentionally ignored.
        except Exception:
            return []

        return [
            (a, b)
            for a, b in out
            if dist(a, b) > 1.0e-12
        ]

    groups = []

    def add_group(semantic, segments):
        if semantic not in {"Door", "Sliding Door"} or not segments:
            return

        xs = []
        ys = []

        for a, b in segments:
            xs.extend((a[0], b[0]))
            ys.extend((a[1], b[1]))

        x0 = min(xs)
        x1 = max(xs)
        y0 = min(ys)
        y1 = max(ys)
        cx = (x0 + x1) * 0.5
        cy = (y0 + y1) * 0.5

        if not (floor_x0 <= cx <= floor_x1 and floor_y0 <= cy <= floor_y1):
            return

        groups.append({
            "semantic_type": semantic,
            "segments": list(segments),
            "bbox": (x0, y0, x1, y1),
        })

    def consume(entity, inherited=None, depth=0):
        if depth > 10:
            return

        semantic = semantic_for(entity, inherited)

        try:
            dtype = str(entity.dxftype()).upper()
        except Exception:
            dtype = ""

        if dtype == "INSERT":
            child_semantic = semantic if semantic in {"Door", "Sliding Door"} else None

            try:
                children = list(entity.virtual_entities())
            except Exception:
                children = []

            if child_semantic is not None:
                segments = []
                for child in children:
                    segments.extend(straight_segments(child))

                if segments:
                    add_group(child_semantic, segments)
                    return

            for child in children:
                consume(child, child_semantic, depth + 1)

            return

        if semantic in {"Door", "Sliding Door"}:
            segments = straight_segments(entity)
            if segments:
                add_group(semantic, segments)

    for entity in modelspace:
        consume(entity)

    # Create3D-prepared Wall vertices only.
    wall_vertices = []
    wall_segments = []

    def add_wall_vertex(point):
        p = (float(point[0]), float(point[1]))

        for old in wall_vertices:
            if dist(p, old) <= node_tol:
                return

        wall_vertices.append(p)

    for path in wall_paths or []:
        pts = []

        for raw in path or []:
            try:
                pts.append((float(raw[0]), float(raw[1])))
            except Exception:
                continue

        for a, b in zip(pts, pts[1:]):
            if dist(a, b) <= 1.0e-12:
                continue

            wall_segments.append((a, b))
            add_wall_vertex(a)
            add_wall_vertex(b)

    def build_graph(segments):
        nodes = []
        adjacency = {}

        def node_index(point):
            p = (float(point[0]), float(point[1]))

            for idx, old in enumerate(nodes):
                if dist(p, old) <= node_tol:
                    return idx

            nodes.append(p)
            adjacency[len(nodes) - 1] = []
            return len(nodes) - 1

        for a, b in segments:
            ia = node_index(a)
            ib = node_index(b)

            if ia == ib:
                continue

            length = dist(nodes[ia], nodes[ib])
            adjacency[ia].append((ib, length))
            adjacency[ib].append((ia, length))

        return nodes, adjacency

    def shortest_path(nodes, adjacency, start, goal):
        queue = [(0.0, start)]
        best = {start: 0.0}
        previous = {}

        while queue:
            cost, current = heapq.heappop(queue)

            if current == goal:
                break

            if cost > best.get(current, float("inf")):
                continue

            for neighbor, weight in adjacency.get(current, []):
                new_cost = cost + weight

                if new_cost < best.get(neighbor, float("inf")):
                    best[neighbor] = new_cost
                    previous[neighbor] = current
                    heapq.heappush(queue, (new_cost, neighbor))

        if goal not in best:
            return None

        indices = [goal]

        while indices[-1] != start:
            indices.append(previous[indices[-1]])

        indices.reverse()
        return [nodes[index] for index in indices]

    def dedupe_points(points):
        result = []

        for point in points:
            p = (float(point[0]), float(point[1]))

            if result and dist(result[-1], p) <= node_tol:
                continue

            result.append(p)

        return result

    bridge_paths = []
    meta = []
    stats = {
        "groups": len(groups),
        "door": 0,
        "sliding": 0,
        "failed": 0,
    }

    for group_index, group in enumerate(groups):
        semantic = group["semantic_type"]
        x0, y0, x1, y1 = group["bbox"]

        nodes, adjacency = build_graph(group["segments"])

        if len(nodes) < 2:
            stats["failed"] += 1
            continue

        nearby_walls = [
            point
            for point in wall_vertices
            if (
                x0 - search_margin <= point[0] <= x1 + search_margin
                and y0 - search_margin <= point[1] <= y1 + search_margin
            )
        ]

        if len(nearby_walls) < 2:
            stats["failed"] += 1
            continue

        attachments = []

        for wall_point in nearby_walls:
            nearest = None

            for node_idx, node_point in enumerate(nodes):
                dd = dist(wall_point, node_point)

                if dd <= wall_attach_tol and (
                    nearest is None
                    or dd < nearest[0]
                ):
                    nearest = (dd, node_idx)

            if nearest is not None:
                attachments.append({
                    "wall": wall_point,
                    "node": nearest[1],
                    "attach_distance": nearest[0],
                })

        candidates = []

        for i in range(len(attachments)):
            first = attachments[i]

            for j in range(i + 1, len(attachments)):
                second = attachments[j]

                if first["node"] == second["node"]:
                    continue

                wall_span = dist(first["wall"], second["wall"])

                if wall_span <= node_tol or wall_span > max_wall_span:
                    continue

                path = shortest_path(
                    nodes,
                    adjacency,
                    first["node"],
                    second["node"],
                )

                if not path or len(path) < 2:
                    continue

                path_length = 0.0

                for a, b in zip(path, path[1:]):
                    path_length += dist(a, b)

                full_path = dedupe_points(
                    [first["wall"]]
                    + path
                    + [second["wall"]]
                )

                if len(full_path) < 2:
                    continue

                # Prefer short attachment distances and a short symbol path.
                score = (
                    first["attach_distance"]
                    + second["attach_distance"]
                    + path_length
                )

                candidates.append({
                    "score": score,
                    "path": full_path,
                    "wall_span": wall_span,
                })

        if not candidates:
            stats["failed"] += 1
            continue

        candidates.sort(key=lambda item: item["score"])
        chosen = candidates[0]

        bridge_paths.append([
            [float(point[0]), float(point[1])]
            for point in chosen["path"]
        ])

        meta.append({
            "group_index": int(group_index),
            "semantic_type": semantic,
            "point_count": int(len(chosen["path"])),
            "wall_span_mm": float(chosen["wall_span"] * source_to_mm),
        })

        if semantic == "Door":
            stats["door"] += 1
        else:
            stats["sliding"] += 1

    print(
        "PLAN3D SYMBOL PATH BRIDGE V9 | groups=",
        stats["groups"],
        "| door_bridges=",
        stats["door"],
        "| sliding_bridges=",
        stats["sliding"],
        "| failed=",
        stats["failed"],
        flush=True,
    )

    return bridge_paths, meta, stats




class ExteriorDoorElement:
    """Physical exterior-door element from raw CAD layer KP Dış Kapılar."""

    SEMANTIC_TYPE = "Exterior Door"
    SOURCE_LAYER = "KP Dış Kapılar"

    def __init__(
        self,
        element_id,
        bbox,
        geometry_points,
        source_kind,
    ):
        self.element_id = int(element_id)
        self.bbox = tuple(float(v) for v in bbox)
        self.geometry_points = [
            (float(p[0]), float(p[1]))
            for p in geometry_points
        ]
        self.source_kind = str(source_kind)

        self.center = (
            (self.bbox[0] + self.bbox[2]) * 0.5,
            (self.bbox[1] + self.bbox[3]) * 0.5,
        )
        self.width = self.bbox[2] - self.bbox[0]
        self.height = self.bbox[3] - self.bbox[1]




class ExteriorDoorBoundaryResolver:
    # PLAN3D_FLOOR_EXTERIOR_DOOR_CONTACT_POINTS_V20
    #
    # Exterior Door is treated as a real element.
    #
    # Input:
    #   - raw CAD layer: KP Dış Kapılar ONLY
    #   - Create3D export-prepared Wall geometry ONLY
    #
    # Rule:
    #   1) Read the exterior-door element's OWN CAD endpoints.
    #   2) Project each endpoint to the nearest prepared-Wall segment.
    #   3) Keep only close contacts.
    #   4) Cluster duplicate contacts.
    #   5) Pick two wall-contact points that bracket the exterior-door object.
    #   6) Closure = snapped Wall contact A -> snapped Wall contact B.
    #
    # No insertion-center ray.
    # No generic Door semantic.
    # No interior-door layer.
    SOURCE_LAYER = ExteriorDoorElement.SOURCE_LAYER

    def __init__(self, viewport, rect_values, wall_paths, source_to_mm):
        import math

        self.math = math
        self.viewport = viewport
        self.rect_values = rect_values
        self.wall_paths = wall_paths or []
        self.source_to_mm = float(source_to_mm)
        self.mm_to_source = 1.0 / max(
            self.source_to_mm,
            1.0e-12,
        )

        self.contact_tol = 180.0 * self.mm_to_source
        self.vertex_snap_tol = 120.0 * self.mm_to_source
        self.cluster_tol = 25.0 * self.mm_to_source
        self.min_span = 300.0 * self.mm_to_source
        self.max_span = 3000.0 * self.mm_to_source
        self.center_line_tol = 500.0 * self.mm_to_source
        self.exploded_cluster_gap = 180.0 * self.mm_to_source

        self.wall_segments = []
        self.wall_vertices = []

        self._build_wall_geometry()

    def _dist(self, a, b):
        return self.math.hypot(
            float(a[0]) - float(b[0]),
            float(a[1]) - float(b[1]),
        )

    def _floor_rect(self):
        rx, ry, rw, rh = [
            float(v)
            for v in self.rect_values
        ]

        return (
            min(rx, rx + rw),
            min(ry, ry + rh),
            max(rx, rx + rw),
            max(ry, ry + rh),
        )

    def _build_wall_geometry(self):
        def add_vertex(point):
            p = (
                float(point[0]),
                float(point[1]),
            )

            for old in self.wall_vertices:
                if self._dist(p, old) <= self.cluster_tol:
                    return

            self.wall_vertices.append(p)

        for path in self.wall_paths:
            points = []

            for raw in path or []:
                try:
                    points.append(
                        (
                            float(raw[0]),
                            float(raw[1]),
                        )
                    )
                except Exception:
                    continue

            for a, b in zip(points, points[1:]):
                if self._dist(a, b) <= 1.0e-12:
                    continue

                self.wall_segments.append((a, b))
                add_vertex(a)
                add_vertex(b)

    @staticmethod
    def _bbox_from_points(points):
        if not points:
            return None

        xs = [float(p[0]) for p in points]
        ys = [float(p[1]) for p in points]

        return (
            min(xs),
            min(ys),
            max(xs),
            max(ys),
        )

    @staticmethod
    def _union_bbox(boxes):
        return (
            min(b[0] for b in boxes),
            min(b[1] for b in boxes),
            max(b[2] for b in boxes),
            max(b[3] for b in boxes),
        )

    @staticmethod
    def _bbox_center(box_value):
        return (
            (box_value[0] + box_value[2]) * 0.5,
            (box_value[1] + box_value[3]) * 0.5,
        )

    @staticmethod
    def _bboxes_near(a, b, gap):
        return not (
            a[2] + gap < b[0]
            or b[2] + gap < a[0]
            or a[3] + gap < b[1]
            or b[3] + gap < a[1]
        )

    def _entity_contact_points(self, entity):
        """
        Return actual endpoint/grip-like points from the exterior-door CAD
        geometry. Curves contribute their real endpoints, not their bbox corners.
        """
        try:
            dtype = str(entity.dxftype()).upper()
        except Exception:
            return []

        points = []

        try:
            if dtype == "LINE":
                a = entity.dxf.start
                b = entity.dxf.end
                points.extend([
                    (float(a.x), float(a.y)),
                    (float(b.x), float(b.y)),
                ])

            elif dtype == "LWPOLYLINE":
                pts = [
                    (float(p[0]), float(p[1]))
                    for p in entity.get_points("xy")
                ]
                points.extend(pts)

            elif dtype == "POLYLINE":
                for vertex in entity.vertices:
                    p = vertex.dxf.location
                    points.append(
                        (
                            float(p.x),
                            float(p.y),
                        )
                    )

            elif dtype == "ARC":
                c = entity.dxf.center
                r = float(entity.dxf.radius)
                a0 = self.math.radians(
                    float(entity.dxf.start_angle)
                )
                a1 = self.math.radians(
                    float(entity.dxf.end_angle)
                )

                points.extend([
                    (
                        float(c.x) + r * self.math.cos(a0),
                        float(c.y) + r * self.math.sin(a0),
                    ),
                    (
                        float(c.x) + r * self.math.cos(a1),
                        float(c.y) + r * self.math.sin(a1),
                    ),
                ])
        except Exception:
            return []

        return points

    def collect_elements(self):
        doc = getattr(
            self.viewport,
            "_document",
            None,
        )

        if doc is None:
            return []

        try:
            modelspace = doc.modelspace()
        except Exception:
            return []

        fx0, fy0, fx1, fy1 = self._floor_rect()

        elements = []
        exploded_records = []

        for entity in modelspace:
            try:
                raw_layer = str(entity.dxf.layer)
            except Exception:
                raw_layer = "0"

            if raw_layer != self.SOURCE_LAYER:
                continue

            try:
                dtype = str(entity.dxftype()).upper()
            except Exception:
                dtype = ""

            if dtype == "INSERT":
                try:
                    children = list(
                        entity.virtual_entities()
                    )
                except Exception:
                    children = []

                points = []

                for child in children:
                    points.extend(
                        self._entity_contact_points(child)
                    )

                bbox = self._bbox_from_points(points)

                if bbox is None:
                    continue

                cx, cy = self._bbox_center(bbox)

                if not (
                    fx0 <= cx <= fx1
                    and fy0 <= cy <= fy1
                ):
                    continue

                elements.append(
                    ExteriorDoorElement(
                        len(elements),
                        bbox,
                        points,
                        "INSERT",
                    )
                )

                continue

            points = self._entity_contact_points(entity)
            bbox = self._bbox_from_points(points)

            if bbox is None:
                continue

            exploded_records.append({
                "bbox": bbox,
                "points": points,
            })

        # Cluster exploded primitives into one physical exterior-door element.
        clusters = []

        for record in exploded_records:
            hits = []

            for index, cluster in enumerate(clusters):
                cluster_bbox = self._union_bbox(
                    [
                        item["bbox"]
                        for item in cluster
                    ]
                )

                if self._bboxes_near(
                    record["bbox"],
                    cluster_bbox,
                    self.exploded_cluster_gap,
                ):
                    hits.append(index)

            if not hits:
                clusters.append([record])
                continue

            base = hits[0]
            clusters[base].append(record)

            for index in reversed(hits[1:]):
                clusters[base].extend(
                    clusters[index]
                )
                del clusters[index]

        for cluster in clusters:
            bbox = self._union_bbox(
                [
                    item["bbox"]
                    for item in cluster
                ]
            )

            center = self._bbox_center(bbox)

            if not (
                fx0 <= center[0] <= fx1
                and fy0 <= center[1] <= fy1
            ):
                continue

            points = []

            for item in cluster:
                points.extend(item["points"])

            elements.append(
                ExteriorDoorElement(
                    len(elements),
                    bbox,
                    points,
                    "EXPLODED",
                )
            )

        return elements

    def _project_point_to_segment(self, point, a, b):
        px, py = float(point[0]), float(point[1])
        ax, ay = float(a[0]), float(a[1])
        bx, by = float(b[0]), float(b[1])

        vx = bx - ax
        vy = by - ay

        denom = vx * vx + vy * vy

        if denom <= 1.0e-18:
            return (
                (ax, ay),
                self._dist(point, (ax, ay)),
                0.0,
            )

        t = (
            (px - ax) * vx
            + (py - ay) * vy
        ) / denom

        t = max(0.0, min(1.0, t))

        projection = (
            ax + t * vx,
            ay + t * vy,
        )

        return (
            projection,
            self._dist(point, projection),
            t,
        )

    def _snap_projection_to_vertex(
        self,
        projection,
        segment_index,
    ):
        a, b = self.wall_segments[segment_index]

        nearest = min(
            (a, b),
            key=lambda candidate: self._dist(
                projection,
                candidate,
            ),
        )

        if (
            self._dist(
                projection,
                nearest,
            )
            <= self.vertex_snap_tol
        ):
            return (
                float(nearest[0]),
                float(nearest[1]),
            )

        return (
            float(projection[0]),
            float(projection[1]),
        )

    def _nearest_wall_contact(self, point):
        best = None

        for segment_index, (a, b) in enumerate(
            self.wall_segments
        ):
            projection, distance, t = (
                self._project_point_to_segment(
                    point,
                    a,
                    b,
                )
            )

            if best is None or distance < best["distance"]:
                best = {
                    "distance": distance,
                    "projection": projection,
                    "segment_index": segment_index,
                    "t": t,
                }

        if best is None:
            return None

        if best["distance"] > self.contact_tol:
            return None

        snapped = self._snap_projection_to_vertex(
            best["projection"],
            best["segment_index"],
        )

        return {
            "door_point": (
                float(point[0]),
                float(point[1]),
            ),
            "wall_point": snapped,
            "distance": float(best["distance"]),
            "segment_index": int(
                best["segment_index"]
            ),
        }

    def _cluster_contacts(self, contacts):
        clusters = []

        for contact in contacts:
            target = contact["wall_point"]
            found = None

            for cluster in clusters:
                if (
                    self._dist(
                        target,
                        cluster["wall_point"],
                    )
                    <= self.cluster_tol
                ):
                    found = cluster
                    break

            if found is None:
                clusters.append({
                    "wall_point": target,
                    "members": [contact],
                    "best_distance": contact["distance"],
                })
            else:
                found["members"].append(contact)

                if (
                    contact["distance"]
                    < found["best_distance"]
                ):
                    found["best_distance"] = contact["distance"]
                    found["wall_point"] = target

        return clusters

    def _point_segment_distance(self, point, a, b):
        projection, distance, _ = (
            self._project_point_to_segment(
                point,
                a,
                b,
            )
        )
        return distance

    def _choose_contact_pair(self, element, clusters):
        candidates = []

        for i in range(len(clusters)):
            first = clusters[i]

            for j in range(i + 1, len(clusters)):
                second = clusters[j]

                a = first["wall_point"]
                b = second["wall_point"]

                span = self._dist(a, b)

                if not (
                    self.min_span
                    <= span
                    <= self.max_span
                ):
                    continue

                # The chosen closure has to pass through/near the exterior
                # door element itself. This removes unrelated wall contacts.
                center_distance = self._point_segment_distance(
                    element.center,
                    a,
                    b,
                )

                door_scale = max(
                    element.width,
                    element.height,
                    self.center_line_tol,
                )

                if center_distance > door_scale:
                    continue

                contact_error = (
                    first["best_distance"]
                    + second["best_distance"]
                )

                # Prefer the widest valid pair through the door object,
                # while strongly preferring true/near-zero wall contacts.
                score = (
                    contact_error * 1000.0
                    + center_distance * 10.0
                    - span
                )

                candidates.append({
                    "score": score,
                    "point_a": a,
                    "point_b": b,
                    "span": span,
                    "contact_error": contact_error,
                    "center_distance": center_distance,
                })

        if not candidates:
            return None

        candidates.sort(
            key=lambda item: item["score"]
        )

        return candidates[0]

    def resolve(self):
        elements = self.collect_elements()

        bridges = []
        meta = []

        for element in elements:
            contacts = []

            for door_point in element.geometry_points:
                contact = self._nearest_wall_contact(
                    door_point
                )

                if contact is not None:
                    contacts.append(contact)

            clusters = self._cluster_contacts(
                contacts
            )

            chosen = self._choose_contact_pair(
                element,
                clusters,
            )

            if chosen is None:
                print(
                    "PLAN3D EXTERIOR DOOR CONTACT V20 | id=",
                    element.element_id,
                    "| source=",
                    element.source_kind,
                    "| raw_points=",
                    len(element.geometry_points),
                    "| wall_contacts=",
                    len(clusters),
                    "| result=NO_PAIR",
                    flush=True,
                )
                continue

            bridges.append([
                [
                    float(chosen["point_a"][0]),
                    float(chosen["point_a"][1]),
                ],
                [
                    float(chosen["point_b"][0]),
                    float(chosen["point_b"][1]),
                ],
            ])

            row = {
                "semantic_type": ExteriorDoorElement.SEMANTIC_TYPE,
                "source_layer": ExteriorDoorElement.SOURCE_LAYER,
                "element_id": int(element.element_id),
                "source_kind": element.source_kind,
                "length_mm": float(
                    chosen["span"]
                    * self.source_to_mm
                ),
                "point_a": [
                    float(chosen["point_a"][0]),
                    float(chosen["point_a"][1]),
                ],
                "point_b": [
                    float(chosen["point_b"][0]),
                    float(chosen["point_b"][1]),
                ],
                "contact_error_mm": float(
                    chosen["contact_error"]
                    * self.source_to_mm
                ),
            }

            meta.append(row)

            print(
                "PLAN3D EXTERIOR DOOR CONTACT V20 | id=",
                row["element_id"],
                "| source=",
                row["source_kind"],
                "| raw_points=",
                len(element.geometry_points),
                "| wall_contacts=",
                len(clusters),
                "| length_mm=",
                format(row["length_mm"], ".1f"),
                "| contact_error_mm=",
                format(
                    row["contact_error_mm"],
                    ".1f",
                ),
                "| A=",
                row["point_a"],
                "| B=",
                row["point_b"],
                flush=True,
            )

        print(
            "PLAN3D EXTERIOR DOOR CONTACT RESOLVER V20 | layer=",
            self.SOURCE_LAYER,
            "| elements=",
            len(elements),
            "| resolved=",
            len(bridges),
            flush=True,
        )

        return bridges, meta, {
            "source_layer": self.SOURCE_LAYER,
            "elements": len(elements),
            "resolved": len(bridges),
        }




def _local_exterior_door_only_bridges(
    viewport,
    rect_values,
    wall_paths,
    source_to_mm,
):
    # PLAN3D_FLOOR_EXTERIOR_DOOR_CONTACT_POINTS_V20
    resolver = ExteriorDoorBoundaryResolver(
        viewport,
        rect_values,
        wall_paths,
        source_to_mm,
    )
    return resolver.resolve()

# ==================================================================
# PLAN3D FLOOR CANONICAL V30
#
# ROLE CONTRACT
#
# 1) BoundaryGraph
#    - Create3D export-prepared Wall
#    - Door / Sliding Door V9 closure paths
#    - Exterior Door V20 closure paths
#    - WindowBoundary closures derived from Window elements
#
# 2) WallFootprint
#    - derived ONLY from Create3D export-prepared Wall
#    - never used to CREATE a floor candidate
#
# 3) Window
#    - V33 resolver derives closures from real prepared-Wall vertices
#    - contributes ONLY to BoundaryGraph continuity
#    - never contributes subtraction geometry to Floor
#
# 4) Floor
#    - polygonize BoundaryGraph
#    - reject faces substantially occupied by WallFootprint
#    - union only accepted Floor faces
#    - subtract WallFootprint once, at the end
#
# Raw Wall layer and Exterior Wall are never read here.
# ==================================================================


def _minimum_width_source_v30(polygon):
    try:
        rectangle = polygon.minimum_rotated_rectangle
        coords = list(rectangle.exterior.coords)
    except Exception:
        return float("inf")

    lengths = []

    for a, b in zip(coords, coords[1:]):
        dx = float(b[0]) - float(a[0])
        dy = float(b[1]) - float(a[1])
        length = (dx * dx + dy * dy) ** 0.5

        if length > 1.0e-12:
            lengths.append(length)

    return min(lengths) if lengths else float("inf")


def _cluster_paths_v30(
    paths,
    source_to_mm,
    gap_mm=220.0,
):
    """
    Group nearby Window paths into local physical elements.
    The grouping is local; distant Windows can never pair together.
    """
    if not paths:
        return []

    gap = float(gap_mm) / max(
        float(source_to_mm),
        1.0e-12,
    )

    records = []

    for path in paths:
        points = []

        for raw in path or []:
            try:
                points.append(
                    (
                        float(raw[0]),
                        float(raw[1]),
                    )
                )
            except Exception:
                continue

        if len(points) < 2:
            continue

        xs = [p[0] for p in points]
        ys = [p[1] for p in points]

        records.append({
            "path": points,
            "bbox": (
                min(xs),
                min(ys),
                max(xs),
                max(ys),
            ),
        })

    def bbox_union(cluster):
        return (
            min(item["bbox"][0] for item in cluster),
            min(item["bbox"][1] for item in cluster),
            max(item["bbox"][2] for item in cluster),
            max(item["bbox"][3] for item in cluster),
        )

    def near(a, b):
        return not (
            a[2] + gap < b[0]
            or b[2] + gap < a[0]
            or a[3] + gap < b[1]
            or b[3] + gap < a[1]
        )

    clusters = []

    for record in records:
        hits = []

        for index, cluster in enumerate(clusters):
            if near(
                record["bbox"],
                bbox_union(cluster),
            ):
                hits.append(index)

        if not hits:
            clusters.append([record])
            continue

        base = hits[0]
        clusters[base].append(record)

        for index in reversed(hits[1:]):
            clusters[base].extend(
                clusters[index]
            )
            del clusters[index]

    result = []

    for cluster in clusters:
        result.append({
            "paths": [
                item["path"]
                for item in cluster
            ],
            "bbox": bbox_union(cluster),
        })

    return result


def _flatten_segments_v30(paths):
    segments = []

    for path in paths or []:
        points = []

        for raw in path or []:
            try:
                points.append(
                    (
                        float(raw[0]),
                        float(raw[1]),
                    )
                )
            except Exception:
                continue

        for a, b in zip(points, points[1:]):
            if a == b:
                continue

            segments.append(
                (
                    a,
                    b,
                )
            )

    return segments


def _project_point_to_segment_v30(point, a, b):
    import math

    px, py = float(point[0]), float(point[1])
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])

    vx = bx - ax
    vy = by - ay
    denom = vx * vx + vy * vy

    if denom <= 1.0e-18:
        projection = (ax, ay)
        return (
            projection,
            math.hypot(
                px - ax,
                py - ay,
            ),
        )

    t = (
        (px - ax) * vx
        + (py - ay) * vy
    ) / denom

    t = max(
        0.0,
        min(
            1.0,
            t,
        ),
    )

    projection = (
        ax + t * vx,
        ay + t * vy,
    )

    return (
        projection,
        math.hypot(
            px - projection[0],
            py - projection[1],
        ),
    )




def _mutual_parallel_footprint_v30(
    paths,
    source_to_mm,
    api,
    *,
    min_width_mm,
    max_width_mm,
    min_overlap_mm,
):
    """
    V31 vertex-pair fix.

    Preserve V30 architecture. Only footprint corner construction changes.

    Rules:
      - real longitudinal overlap only;
      - no endpoint extension;
      - no large buffer/heal;
      - pair must be MUTUAL nearest valid parallel counterpart;
      - overlap points are computed independently on BOTH real prepared segments;
      - endpoint orientation is resolved by minimum non-crossing pairing;
      - self-crossing / invalid quadrilateral is rejected.
    """
    import math

    if not paths:
        return None, 0

    Polygon = api["Polygon"]
    LineString = api["LineString"]

    mm_to_source = 1.0 / max(
        float(source_to_mm),
        1.0e-12,
    )

    min_width = float(min_width_mm) * mm_to_source
    max_width = float(max_width_mm) * mm_to_source
    min_overlap = float(min_overlap_mm) * mm_to_source

    parallel_sin_tol = math.sin(
        math.radians(3.0)
    )

    segments = []

    for a, b in _flatten_segments_v30(paths):
        dx = b[0] - a[0]
        dy = b[1] - a[1]
        length = math.hypot(dx, dy)

        if length <= 1.0e-9:
            continue

        ux = dx / length
        uy = dy / length

        segments.append({
            "a": (float(a[0]), float(a[1])),
            "b": (float(b[0]), float(b[1])),
            "length": float(length),
            "u": (ux, uy),
            "n": (-uy, ux),
        })

    if len(segments) < 2:
        return None, 0

    def dot(a, b):
        return (
            float(a[0]) * float(b[0])
            + float(a[1]) * float(b[1])
        )

    def sub(a, b):
        return (
            float(a[0]) - float(b[0]),
            float(a[1]) - float(b[1]),
        )

    def dist(a, b):
        return math.hypot(
            float(a[0]) - float(b[0]),
            float(a[1]) - float(b[1]),
        )

    def point_on_segment_from_scalar(segment, scalar, axis):
        a = segment["a"]
        ta = dot(a, axis)

        return (
            a[0] + (scalar - ta) * axis[0],
            a[1] + (scalar - ta) * axis[1],
        )

    def segments_cross_strict(a, b, c, d):
        def cross(u, v):
            return u[0] * v[1] - u[1] * v[0]

        r = (
            b[0] - a[0],
            b[1] - a[1],
        )
        s = (
            d[0] - c[0],
            d[1] - c[1],
        )

        den = cross(r, s)

        if abs(den) <= 1.0e-12:
            return False

        q = (
            c[0] - a[0],
            c[1] - a[1],
        )

        t = cross(q, s) / den
        u = cross(q, r) / den

        eps = 1.0e-8

        return (
            eps < t < 1.0 - eps
            and eps < u < 1.0 - eps
        )

    candidates = {
        index: []
        for index in range(len(segments))
    }

    for i, first in enumerate(segments):
        a1 = first["a"]
        b1 = first["b"]
        u1 = first["u"]
        n1 = first["n"]

        t1a = dot(a1, u1)
        t1b = dot(b1, u1)

        first_min = min(t1a, t1b)
        first_max = max(t1a, t1b)

        for j in range(i + 1, len(segments)):
            second = segments[j]
            u2 = second["u"]

            cross_abs = abs(
                u1[0] * u2[1]
                - u1[1] * u2[0]
            )

            if cross_abs > parallel_sin_tol:
                continue

            a2 = second["a"]
            b2 = second["b"]

            d2a = dot(
                sub(a2, a1),
                n1,
            )
            d2b = dot(
                sub(b2, a1),
                n1,
            )

            if abs(d2a - d2b) > max_width * 0.08:
                continue

            lateral = (
                d2a + d2b
            ) * 0.5

            width = abs(lateral)

            if (
                width < min_width
                or width > max_width
            ):
                continue

            # Project BOTH real second-segment endpoints to first axis.
            t2a = dot(a2, u1)
            t2b = dot(b2, u1)

            second_min = min(t2a, t2b)
            second_max = max(t2a, t2b)

            overlap_start = max(
                first_min,
                second_min,
            )
            overlap_end = min(
                first_max,
                second_max,
            )

            overlap = (
                overlap_end
                - overlap_start
            )

            if overlap < min_overlap:
                continue

            overlap_ratio = (
                overlap
                / max(
                    min(
                        first["length"],
                        second["length"],
                    ),
                    1.0e-12,
                )
            )

            if overlap_ratio < 0.20:
                continue

            record = {
                "i": i,
                "j": j,
                "width": width,
                "overlap": overlap,
                "overlap_start": overlap_start,
                "overlap_end": overlap_end,
                "axis": u1,
            }

            candidates[i].append(record)
            candidates[j].append(record)

    nearest = {}

    for index, rows in candidates.items():
        if not rows:
            continue

        rows.sort(
            key=lambda row: (
                row["width"],
                -row["overlap"],
            )
        )

        nearest[index] = rows[0]

    mutual_pairs = []
    used = set()

    for index, row in nearest.items():
        other = (
            row["j"]
            if row["i"] == index
            else row["i"]
        )

        other_row = nearest.get(other)

        if other_row is None:
            continue

        other_partner = (
            other_row["j"]
            if other_row["i"] == other
            else other_row["i"]
        )

        if other_partner != index:
            continue

        key = (
            min(index, other),
            max(index, other),
        )

        if key in used:
            continue

        used.add(key)
        mutual_pairs.append(row)

    polygons = []
    rejected_cross = 0
    rejected_invalid = 0

    for pair in mutual_pairs:
        first = segments[pair["i"]]
        second = segments[pair["j"]]
        axis = pair["axis"]

        start = pair["overlap_start"]
        end = pair["overlap_end"]

        # Real overlap points on segment 1.
        p1_start = point_on_segment_from_scalar(
            first,
            start,
            axis,
        )
        p1_end = point_on_segment_from_scalar(
            first,
            end,
            axis,
        )

        # Real overlap points on segment 2.
        # Compute in first-axis scalar space, but anchor on second's real line.
        a2 = second["a"]
        t2a = dot(a2, axis)

        p2_start = (
            a2[0] + (start - t2a) * axis[0],
            a2[1] + (start - t2a) * axis[1],
        )
        p2_end = (
            a2[0] + (end - t2a) * axis[0],
            a2[1] + (end - t2a) * axis[1],
        )

        # Determine orientation using the two possible endpoint pairings.
        same_cost = (
            dist(p1_start, p2_start)
            + dist(p1_end, p2_end)
        )
        reversed_cost = (
            dist(p1_start, p2_end)
            + dist(p1_end, p2_start)
        )

        if same_cost <= reversed_cost:
            q2_start = p2_start
            q2_end = p2_end
        else:
            q2_start = p2_end
            q2_end = p2_start

        # Reject bow-tie / crossed quadrilateral.
        if (
            segments_cross_strict(
                p1_start,
                p1_end,
                q2_end,
                q2_start,
            )
            or segments_cross_strict(
                p1_end,
                q2_end,
                q2_start,
                p1_start,
            )
        ):
            rejected_cross += 1
            continue

        try:
            polygon = Polygon(
                [
                    p1_start,
                    p1_end,
                    q2_end,
                    q2_start,
                ]
            )

            if (
                polygon.is_empty
                or float(polygon.area) <= 0.0
            ):
                rejected_invalid += 1
                continue

            if not polygon.is_valid:
                polygon = api["make_valid"](polygon)

            # make_valid may return non-polygonal geometry.
            parts = _polygon_parts(
                polygon,
                api,
            )

            if not parts:
                rejected_invalid += 1
                continue

            polygons.extend(parts)
        except Exception:
            rejected_invalid += 1
            continue

    # Supplement exact narrow closed faces from the same prepared source.
    try:
        closed_faces, _ = _polygonize(
            paths,
            api,
        )
    except Exception:
        closed_faces = []

    for face in closed_faces:
        try:
            width_mm = (
                _minimum_width_source_v30(
                    face
                )
                * float(source_to_mm)
            )

            if (
                float(min_width_mm)
                <= width_mm
                <= float(max_width_mm)
            ):
                polygons.append(face)
        except Exception:
            continue

    if not polygons:
        print(
            "PLAN3D FOOTPRINT VERTEX PAIR V31 | pairs=",
            len(mutual_pairs),
            "| accepted=0",
            "| rejected_cross=",
            rejected_cross,
            "| rejected_invalid=",
            rejected_invalid,
            flush=True,
        )
        return None, 0

    try:
        merged = api["unary_union"](
            polygons
        )
    except Exception:
        return None, 0

    try:
        if not merged.is_valid:
            merged = api["make_valid"](merged)
    except Exception:
        pass

    print(
        "PLAN3D FOOTPRINT VERTEX PAIR V31 | pairs=",
        len(mutual_pairs),
        "| accepted=",
        len(polygons),
        "| rejected_cross=",
        rejected_cross,
        "| rejected_invalid=",
        rejected_invalid,
        flush=True,
    )

    return (
        merged,
        len(mutual_pairs),
    )



def _build_wall_footprint_v30(
    wall_paths,
    source_to_mm,
    api,
):
    return _mutual_parallel_footprint_v30(
        wall_paths,
        source_to_mm,
        api,
        min_width_mm=40.0,
        max_width_mm=600.0,
        min_overlap_mm=120.0,
    )




def _face_exclusion_ratio_v30(
    polygon,
    exclusion_geometry,
):
    if (
        polygon is None
        or polygon.is_empty
        or exclusion_geometry is None
    ):
        return 0.0

    try:
        area = float(
            polygon.area
        )

        if area <= 1.0e-12:
            return 0.0

        overlap = float(
            polygon.intersection(
                exclusion_geometry
            ).area
        )

        return overlap / area
    except Exception:
        return 0.0







class WindowElementResolverV33:
    """
    Resolve each Window from four REAL Create3D-prepared Wall vertices.

    Expected opening geometry:

        A1 -------- B1
        |  WINDOW   |
        A2 -------- B2

    A1/A2 = prepared-Wall vertices at one jamb.
    B1/B2 = prepared-Wall vertices at the opposite jamb.

    SAME four vertices drive both:
      - BoundaryGraph: A1->B1 and A2->B2
      - WindowFootprint: A1->B1->B2->A2

    No projected wall contact.
    No invented contact point.
    No axis-aligned bbox footprint.
    """

    def __init__(
        self,
        window_paths,
        wall_paths,
        source_to_mm,
        api,
    ):
        import math

        self.math = math
        self.window_paths = window_paths or []
        self.wall_paths = wall_paths or []
        self.source_to_mm = float(source_to_mm)
        self.api = api
        self.mm_to_source = 1.0 / max(self.source_to_mm, 1.0e-12)

        self.wall_vertex_weld_tol = 10.0 * self.mm_to_source
        self.search_margin = 350.0 * self.mm_to_source
        self.jamb_station_tol = 350.0 * self.mm_to_source
        self.min_window_span = 100.0 * self.mm_to_source
        self.max_window_span = 5000.0 * self.mm_to_source
        self.min_wall_thickness = 40.0 * self.mm_to_source
        self.max_wall_thickness = 600.0 * self.mm_to_source

        self.wall_vertices = []
        self._build_wall_vertices()

    def _dist(self, a, b):
        return self.math.hypot(
            float(a[0]) - float(b[0]),
            float(a[1]) - float(b[1]),
        )

    def _build_wall_vertices(self):
        def add(point):
            p = (float(point[0]), float(point[1]))

            for old in self.wall_vertices:
                if self._dist(p, old) <= self.wall_vertex_weld_tol:
                    return

            self.wall_vertices.append(p)

        for path in self.wall_paths:
            points = []

            for raw in path or []:
                try:
                    points.append((float(raw[0]), float(raw[1])))
                except Exception:
                    continue

            for a, b in zip(points, points[1:]):
                if self._dist(a, b) <= 1.0e-12:
                    continue
                add(a)
                add(b)

    def _clusters(self):
        return _cluster_paths_v30(
            self.window_paths,
            self.source_to_mm,
            gap_mm=220.0,
        )

    def _window_segments(self, cluster):
        result = []

        for path in cluster["paths"]:
            for a, b in zip(path, path[1:]):
                if self._dist(a, b) <= 1.0e-12:
                    continue

                result.append(
                    (
                        (float(a[0]), float(a[1])),
                        (float(b[0]), float(b[1])),
                    )
                )

        return result

    def _principal_axis(self, cluster):
        segments = self._window_segments(cluster)

        sx = 0.0
        sy = 0.0
        total = 0.0

        for a, b in segments:
            dx = b[0] - a[0]
            dy = b[1] - a[1]
            length = self.math.hypot(dx, dy)

            if length <= 1.0e-12:
                continue

            theta = self.math.atan2(dy, dx)

            sx += self.math.cos(2.0 * theta) * length
            sy += self.math.sin(2.0 * theta) * length
            total += length

        if total <= 1.0e-12:
            bbox = cluster["bbox"]

            if (bbox[2] - bbox[0]) >= (bbox[3] - bbox[1]):
                return (1.0, 0.0)

            return (0.0, 1.0)

        theta = 0.5 * self.math.atan2(sy, sx)

        return (
            self.math.cos(theta),
            self.math.sin(theta),
        )

    @staticmethod
    def _perp(axis):
        return (-float(axis[1]), float(axis[0]))

    @staticmethod
    def _dot(a, b):
        return float(a[0]) * float(b[0]) + float(a[1]) * float(b[1])

    def _to_local(self, point, center, axis, perp):
        rel = (
            float(point[0]) - float(center[0]),
            float(point[1]) - float(center[1]),
        )

        return (
            self._dot(rel, axis),
            self._dot(rel, perp),
        )

    def _window_points(self, cluster):
        result = []

        for path in cluster["paths"]:
            for raw in path:
                try:
                    point = (float(raw[0]), float(raw[1]))
                except Exception:
                    continue

                if not any(
                    self._dist(point, old) <= self.wall_vertex_weld_tol
                    for old in result
                ):
                    result.append(point)

        return result

    def _candidate_wall_vertices(self, cluster, center, axis, perp):
        window_points = self._window_points(cluster)

        if not window_points:
            return [], None

        local_window = [
            self._to_local(point, center, axis, perp)
            for point in window_points
        ]

        s_values = [p[0] for p in local_window]
        t_values = [p[1] for p in local_window]

        extents = {
            "s_min": min(s_values),
            "s_max": max(s_values),
            "t_min": min(t_values),
            "t_max": max(t_values),
        }

        result = []

        for world in self.wall_vertices:
            local = self._to_local(world, center, axis, perp)
            s, t = local

            if (
                extents["s_min"] - self.search_margin
                <= s
                <= extents["s_max"] + self.search_margin
                and extents["t_min"] - self.search_margin
                <= t
                <= extents["t_max"] + self.search_margin
            ):
                result.append({
                    "world": world,
                    "local": local,
                })

        return result, extents

    def _station_candidates(self, vertices, target_s):
        candidates = []

        for item in vertices:
            s, t = item["local"]
            error = abs(s - target_s)

            if error <= self.jamb_station_tol:
                candidates.append({
                    "world": item["world"],
                    "s": s,
                    "t": t,
                    "station_error": error,
                })

        candidates.sort(
            key=lambda row: (
                row["station_error"],
                row["t"],
            )
        )

        return candidates

    def _choose_four_vertices(self, cluster):
        bbox = cluster["bbox"]
        center = (
            (bbox[0] + bbox[2]) * 0.5,
            (bbox[1] + bbox[3]) * 0.5,
        )

        axis = self._principal_axis(cluster)
        perp = self._perp(axis)

        vertices, extents = self._candidate_wall_vertices(
            cluster,
            center,
            axis,
            perp,
        )

        if extents is None or len(vertices) < 4:
            return None

        left = self._station_candidates(vertices, extents["s_min"])
        right = self._station_candidates(vertices, extents["s_max"])

        if len(left) < 2 or len(right) < 2:
            return None

        candidates = []

        for li in range(len(left)):
            for lj in range(li + 1, len(left)):
                left_pair = sorted(
                    [left[li], left[lj]],
                    key=lambda row: row["t"],
                )

                left_thickness = abs(
                    left_pair[0]["t"] - left_pair[1]["t"]
                )

                if (
                    left_thickness < self.min_wall_thickness
                    or left_thickness > self.max_wall_thickness
                ):
                    continue

                for ri in range(len(right)):
                    for rj in range(ri + 1, len(right)):
                        right_pair = sorted(
                            [right[ri], right[rj]],
                            key=lambda row: row["t"],
                        )

                        right_thickness = abs(
                            right_pair[0]["t"] - right_pair[1]["t"]
                        )

                        if (
                            right_thickness < self.min_wall_thickness
                            or right_thickness > self.max_wall_thickness
                        ):
                            continue

                        A1 = left_pair[0]
                        A2 = left_pair[1]
                        B1 = right_pair[0]
                        B2 = right_pair[1]

                        span1 = self._dist(A1["world"], B1["world"])
                        span2 = self._dist(A2["world"], B2["world"])
                        mean_span = (span1 + span2) * 0.5

                        if (
                            mean_span < self.min_window_span
                            or mean_span > self.max_window_span
                        ):
                            continue

                        face_mismatch = (
                            abs(A1["t"] - B1["t"])
                            + abs(A2["t"] - B2["t"])
                        )

                        thickness_mismatch = abs(
                            left_thickness - right_thickness
                        )

                        station_error = (
                            A1["station_error"]
                            + A2["station_error"]
                            + B1["station_error"]
                            + B2["station_error"]
                        )

                        expected_span = abs(
                            extents["s_max"] - extents["s_min"]
                        )

                        span_error = abs(mean_span - expected_span)

                        score = (
                            station_error * 100.0
                            + face_mismatch * 100.0
                            + thickness_mismatch * 50.0
                            + span_error
                        )

                        candidates.append({
                            "score": score,
                            "A1": A1["world"],
                            "A2": A2["world"],
                            "B1": B1["world"],
                            "B2": B2["world"],
                            "span1": span1,
                            "span2": span2,
                            "wall_thickness": (
                                left_thickness + right_thickness
                            ) * 0.5,
                        })

        if not candidates:
            return None

        candidates.sort(key=lambda row: row["score"])
        return candidates[0]

    def _polygon_from_four(self, chosen):
        Polygon = self.api["Polygon"]

        A1 = chosen["A1"]
        A2 = chosen["A2"]
        B1 = chosen["B1"]
        B2 = chosen["B2"]

        try:
            polygon = Polygon([A1, B1, B2, A2])

            if polygon.is_empty or float(polygon.area) <= 0.0:
                return None

            if not polygon.is_valid:
                polygon = self.api["make_valid"](polygon)

            parts = _polygon_parts(polygon, self.api)

            if not parts:
                return None

            try:
                return self.api["unary_union"](parts)
            except Exception:
                return parts[0]
        except Exception:
            return None


    def _choose_two_contacts_v39(self, cluster):
        # PLAN3D_WINDOW_ELEMENT_CONTACT_FALLBACK_V39
        bbox = cluster["bbox"]
        center = (
            (bbox[0] + bbox[2]) * 0.5,
            (bbox[1] + bbox[3]) * 0.5,
        )

        axis = self._principal_axis(cluster)
        perp = self._perp(axis)

        points = self._window_points(cluster)
        if len(points) < 2:
            return None

        local = [
            self._to_local(point, center, axis, perp)
            for point in points
        ]

        s_values = [row[0] for row in local]
        t_values = [row[1] for row in local]

        s_min = min(s_values)
        s_max = max(s_values)
        t_mid = (min(t_values) + max(t_values)) * 0.5

        def world_from_local(s, t):
            return (
                center[0] + axis[0] * s + perp[0] * t,
                center[1] + axis[1] * s + perp[1] * t,
            )

        left_target = world_from_local(s_min, t_mid)
        right_target = world_from_local(s_max, t_mid)

        max_snap = max(
            self.search_margin * 2.0,
            self.max_wall_thickness + self.search_margin,
        )

        def nearest_on_segment(point, a, b):
            px, py = float(point[0]), float(point[1])
            ax, ay = float(a[0]), float(a[1])
            bx, by = float(b[0]), float(b[1])

            vx = bx - ax
            vy = by - ay
            vv = vx * vx + vy * vy

            if vv <= 1.0e-18:
                q = (ax, ay)
                return q, self._dist(point, q)

            u = ((px - ax) * vx + (py - ay) * vy) / vv
            u = max(0.0, min(1.0, u))

            q = (
                ax + vx * u,
                ay + vy * u,
            )

            return q, self._dist(point, q)

        def collect(target, target_s):
            candidates = []

            for path_index, path in enumerate(self.wall_paths):
                if not isinstance(path, (list, tuple)) or len(path) < 2:
                    continue

                for segment_index, (a, b) in enumerate(zip(path, path[1:])):
                    try:
                        q, distance = nearest_on_segment(target, a, b)
                    except Exception:
                        continue

                    if distance > max_snap:
                        continue

                    q_local = self._to_local(q, center, axis, perp)
                    station_error = abs(q_local[0] - target_s)

                    if station_error > max_snap:
                        continue

                    candidates.append({
                        "world": q,
                        "distance": distance,
                        "station_error": station_error,
                        "path_index": int(path_index),
                        "segment_index": int(segment_index),
                    })

            candidates.sort(
                key=lambda row: (
                    row["distance"],
                    row["station_error"],
                    row["path_index"],
                    row["segment_index"],
                )
            )
            return candidates

        left_candidates = collect(left_target, s_min)
        right_candidates = collect(right_target, s_max)

        if not left_candidates or not right_candidates:
            return None

        best = None

        for left in left_candidates[:12]:
            for right in right_candidates[:12]:
                A = left["world"]
                B = right["world"]

                span = self._dist(A, B)
                if (
                    span < self.min_window_span
                    or span > self.max_window_span
                ):
                    continue

                dx = float(B[0]) - float(A[0])
                dy = float(B[1]) - float(A[1])

                if span <= 1.0e-12:
                    continue

                alignment = abs(
                    (dx * axis[0] + dy * axis[1]) / span
                )

                if alignment < 0.85:
                    continue

                score = (
                    left["distance"]
                    + right["distance"]
                    + left["station_error"]
                    + right["station_error"]
                    + (1.0 - alignment) * max_snap
                )

                row = {
                    "score": score,
                    "A": A,
                    "B": B,
                    "span": span,
                    "left_snap": left["distance"],
                    "right_snap": right["distance"],
                    "alignment": alignment,
                }

                if best is None or row["score"] < best["score"]:
                    best = row

        return best

    def resolve(self):
        clusters = self._clusters()

        boundary_closures = []
        footprints = []
        meta = []
        fallback_count = 0

        for element_id, cluster in enumerate(clusters):
            chosen = self._choose_four_vertices(cluster)

            if chosen is None:
                fallback = self._choose_two_contacts_v39(cluster)

                if fallback is None:
                    print(
                        "PLAN3D WINDOW ELEMENT V39 | id=",
                        element_id,
                        "| result=NO_WALL_CONTACT",
                        flush=True,
                    )
                    continue

                A = fallback["A"]
                B = fallback["B"]

                boundary_closures.append([
                    [float(A[0]), float(A[1])],
                    [float(B[0]), float(B[1])],
                ])

                row = {
                    "element_id": int(element_id),
                    "mode": "WINDOW_ELEMENT_2_CONTACT_V39",
                    "A": [float(A[0]), float(A[1])],
                    "B": [float(B[0]), float(B[1])],
                    "span_mm": float(fallback["span"] * self.source_to_mm),
                    "left_snap_mm": float(fallback["left_snap"] * self.source_to_mm),
                    "right_snap_mm": float(fallback["right_snap"] * self.source_to_mm),
                    "alignment": float(fallback["alignment"]),
                    "footprint": False,
                }

                meta.append(row)
                fallback_count += 1

                print(
                    "PLAN3D WINDOW ELEMENT V39 | id=",
                    row["element_id"],
                    "| mode=2_CONTACT",
                    "| span_mm=",
                    format(row["span_mm"], ".1f"),
                    "| left_snap_mm=",
                    format(row["left_snap_mm"], ".1f"),
                    "| right_snap_mm=",
                    format(row["right_snap_mm"], ".1f"),
                    "| alignment=",
                    format(row["alignment"], ".3f"),
                    "| A=",
                    row["A"],
                    "| B=",
                    row["B"],
                    flush=True,
                )
                continue

            A1 = chosen["A1"]
            A2 = chosen["A2"]
            B1 = chosen["B1"]
            B2 = chosen["B2"]

            boundary_closures.append([
                [float(A1[0]), float(A1[1])],
                [float(B1[0]), float(B1[1])],
            ])

            boundary_closures.append([
                [float(A2[0]), float(A2[1])],
                [float(B2[0]), float(B2[1])],
            ])

            footprint = self._polygon_from_four(chosen)

            if footprint is not None:
                footprints.append(footprint)

            row = {
                "element_id": int(element_id),
                "window_id": "W" + str(int(element_id) + 1).zfill(3),
                "mode": "4_VERTEX_V33",
                "A1": [float(A1[0]), float(A1[1])],
                "A2": [float(A2[0]), float(A2[1])],
                "B1": [float(B1[0]), float(B1[1])],
                "B2": [float(B2[0]), float(B2[1])],
                "span1_mm": float(chosen["span1"] * self.source_to_mm),
                "span2_mm": float(chosen["span2"] * self.source_to_mm),
                "wall_thickness_mm": float(
                    chosen["wall_thickness"] * self.source_to_mm
                ),
                "footprint": bool(footprint is not None),
            }

            meta.append(row)

            print(
                "PLAN3D WINDOW WALL VERTEX V33 | id=",
                row["element_id"],
                "| span1_mm=",
                format(row["span1_mm"], ".1f"),
                "| span2_mm=",
                format(row["span2_mm"], ".1f"),
                "| wall_thickness_mm=",
                format(row["wall_thickness_mm"], ".1f"),
                "| footprint=",
                row["footprint"],
                "| A1=",
                row["A1"],
                "| A2=",
                row["A2"],
                "| B1=",
                row["B1"],
                "| B2=",
                row["B2"],
                flush=True,
            )

        footprint_geometry = None

        if footprints:
            try:
                footprint_geometry = self.api["unary_union"](footprints)
            except Exception:
                footprint_geometry = footprints[0]

            try:
                if not footprint_geometry.is_valid:
                    footprint_geometry = self.api["make_valid"](
                        footprint_geometry
                    )
            except Exception:
                pass

        stats = {
            "clusters": int(len(clusters)),
            "resolved": int(len(meta)),
            "boundary_closures": int(len(boundary_closures)),
            "footprints": int(len(footprints)),
            "two_contact_fallback_v39": int(fallback_count),
        }

        return (
            boundary_closures,
            footprint_geometry,
            meta,
            stats,
        )


def _resolve_windows_v33(
    window_paths,
    wall_paths,
    source_to_mm,
    api,
):
    resolver = WindowElementResolverV33(
        window_paths,
        wall_paths,
        source_to_mm,
        api,
    )

    return resolver.resolve()

def show_all_floor_areas(panel):
    """
    PLAN3D Floor Areas V30.

    Canonical role separation:
      BoundaryGraph -> only creates closed floor candidates.
      WallFootprint -> only excludes Wall area.
      Window -> only supplies V33 prepared-Wall contact closures.

    A raw polygonized face is NOT automatically Floor.
    Faces substantially occupied by WallFootprint are rejected before
    floor union. The accepted floor union is then cut once by WallFootprint.
    """
    api = _require_shapely()

    page = panel.parentWidget()
    viewport = getattr(
        page,
        "viewport",
        None,
    )

    if viewport is None:
        raise RuntimeError(
            "Viewport is not available."
        )

    if getattr(
        viewport,
        "_document",
        None,
    ) is None:
        raise RuntimeError(
            "CAD document is not loaded."
        )

    assignments = getattr(
        panel,
        "_assignments",
        {},
    )

    floor_assignments = (
        assignments.get(
            "floor_plans",
            {},
        )
        if isinstance(
            assignments,
            dict,
        )
        else {}
    )

    if not floor_assignments:
        raise RuntimeError(
            "No confirmed Floor Plan assignment is available."
        )

    floor_pivots = dict(
        getattr(
            panel,
            "_floor_pivots",
            {},
        )
        or {}
    )

    floor_settings = dict(
        getattr(
            panel,
            "_floor_settings",
            {},
        )
        or {}
    )

    from plan3d_canonical_export import _cad_unit_info

    units_info = _cad_unit_info(
        viewport
    )

    source_to_mm = (
        float(
            units_info.get(
                "to_cm",
                1.0,
            )
        )
        * 10.0
    )

    _clear_previous(
        viewport
    )

    results = {}
    _plan3d_floor_export_cache_reset_v1()
    warnings = []

    for floor_name, rect_values in floor_assignments.items():
        region = _normalize_rect(
            rect_values
        )

        if region is None:
            warnings.append(
                str(floor_name)
                + ": invalid Floor Plan bounds"
            )
            continue

        pivot = dict(
            floor_pivots.get(
                floor_name,
                {
                    "pivot_x": 0.0,
                    "pivot_y": 0.0,
                },
            )
            or {}
        )

        pivot.setdefault(
            "pivot_x",
            0.0,
        )
        pivot.setdefault(
            "pivot_y",
            0.0,
        )

        settings = dict(
            floor_settings.get(
                floor_name,
                {},
            )
            or {}
        )

        try:
            (
                wall_paths,
                wall_topology,
                export_floor,
            ) = _export_prepared_wall_paths(
                viewport,
                floor_name,
                rect_values,
                pivot,
                settings,
                units_info,
            )
        except Exception as exc:
            warning = (
                str(floor_name)
                + ": Create 3D Wall prepass failed | "
                + str(exc)
            )

            warnings.append(
                warning
            )

            print(
                "PLAN3D FLOOR V30 ERROR |",
                warning,
                flush=True,
            )
            continue

        window_paths = (
            _window_paths_in_floor(
                viewport,
                rect_values,
            )
        )

        (
            exterior_door_bridges,
            exterior_door_meta,
            exterior_door_stats,
        ) = _local_exterior_door_only_bridges(
            viewport,
            rect_values,
            wall_paths,
            source_to_mm,
        )

        (
            opening_bridge_paths,
            opening_bridge_meta,
            opening_bridge_stats,
        ) = _symbol_opening_bridge_paths(
            viewport,
            rect_values,
            wall_paths,
            source_to_mm,
        )

        (
            window_boundary_bridges,
            window_footprint,
            window_element_meta,
            window_element_stats,
        ) = _resolve_windows_v33(
            window_paths,
            wall_paths,
            source_to_mm,
            api,
        )

        # ----------------------------------------------------------
        # PRODUCT A: BoundaryGraph
        #
        # Window raw linework is NOT inserted here.
        # Only one derived Window closure per physical Window is used.
        # ----------------------------------------------------------
        boundary_paths = (
            list(wall_paths)
            + list(opening_bridge_paths)
            + list(exterior_door_bridges)
            + list(window_boundary_bridges)
        )

        raw_faces, diagnostics = (
            _polygonize(
                boundary_paths,
                api,
            )
        )

        # PLAN3D_FLOOR_SIMPLE_BOUNDARY_V3
        # export-prepared Wall + opening closures -> polygonize -> floor
        wall_pair_count = 0
        rejected_element_faces = 0
        rejected_tiny_faces = 0

        floor_candidates = []
        region_polygon = api["box"](*region)

        for raw_face in raw_faces:
            try:
                clipped = raw_face.intersection(region_polygon)
            except Exception:
                continue

            for candidate in _polygon_parts(clipped, api):
                try:
                    if float(candidate.area) <= 0.0:
                        continue
                except Exception:
                    continue

                floor_candidates.append(candidate)

        selected_floor = None

        if floor_candidates:
            try:
                selected_floor = api["unary_union"](floor_candidates)
            except Exception:
                selected_floor = None

        final_floor = selected_floor

        display_polygons = (
            _polygon_parts(
                final_floor,
                api,
            )
            if final_floor is not None
            else []
        )

        display_polygons.sort(
            key=lambda polygon: float(
                polygon.area
            ),
            reverse=True,
        )
        _plan3d_floor_export_cache_add_v1(
            floor_name,
            display_polygons,
            export_floor,
        )

        areas_m2 = [
            (
                float(polygon.area)
                * float(source_to_mm)
                * float(source_to_mm)
                / 1000000.0
            )
            for polygon in display_polygons
        ]

        total_area_m2 = sum(
            areas_m2
        )

        for polygon in display_polygons:
            _add_overlay(
                viewport,
                polygon,
            )

        results[str(floor_name)] = {
            "engine": FLOOR_ENGINE,
            "area_count": int(
                len(display_polygons)
            ),
            "area_m2": float(
                total_area_m2
            ),
            "areas_m2": [
                float(value)
                for value in areas_m2
            ],
            "wall_segment_count": int(
                len(wall_paths)
            ),
            "window_segment_count": int(
                len(window_paths)
            ),
            "wall_pair_count": int(
                wall_pair_count
            ),
            "window_element_stats": dict(
                window_element_stats
            ),
            "window_floor_subtraction": False,
            "window_floor_mode": "boundary_only_v34",
            "floor_generation_mode": "simple_boundary_v3",
            "rejected_element_faces": int(
                rejected_element_faces
            ),
            "rejected_tiny_faces": int(
                rejected_tiny_faces
            ),
            "wall_topology": dict(
                wall_topology
            ),
            **diagnostics,
        }

        print(
            "PLAN3D FLOOR SIMPLE BOUNDARY V3 |",
            floor_name,
            "| boundary_wall_segments=",
            len(wall_paths),
            "| window_vertex_clusters=",
            window_element_stats.get(
                "clusters",
                0,
            ),
            "| window_vertex_resolved=",
            window_element_stats.get(
                "resolved",
                0,
            ),
            "| wall_pairs=",
            wall_pair_count,
            "| window_vertex_elements=",
            window_element_stats.get(
                "clusters",
                0,
            ),
            "| window_vertex_footprints=",
            window_element_stats.get(
                "footprints",
                0,
            ),
            "| window_floor_subtraction=NO",
            "| rejected_element_faces=",
            rejected_element_faces,
            "| rejected_tiny_faces=",
            rejected_tiny_faces,
            "| ExteriorDoorV20=",
            exterior_door_stats.get(
                "resolved",
                0,
            ),
            "| DoorV9=",
            opening_bridge_stats.get(
                "door",
                0,
            ),
            "| SlidingDoorV9=",
            opening_bridge_stats.get(
                "sliding",
                0,
            ),
            "| floor_areas=",
            len(display_polygons),
            "| area_m2=",
            format(
                total_area_m2,
                ".2f",
            ),
            "| raw_Wall_layer_used=NO",
            "| ExteriorWall=0",
            flush=True,
        )

    try:
        viewport.viewport().update()
    except Exception:
        pass

    print(
        "PLAN3D FLOOR V30 COMPLETE | floors=",
        len(results),
        "| overlays=",
        len(
            getattr(
                viewport,
                "_floor_area_overlay_items",
                [],
            )
            or []
        ),
        "| warnings=",
        len(warnings),
        flush=True,
    )

    return {
        "engine": FLOOR_ENGINE,
        "floors": results,
        "warnings": warnings,
    }

# ============================================================
# PLAN3D_FLOOR_EXPORT_CACHE_V1
# ============================================================

def _plan3d_floor_export_cache_path_v1():
    from pathlib import Path as _P
    target = _P.cwd() / "runtime" / "max_bridge" / "floor_export_payload.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _plan3d_floor_export_cache_reset_v1():
    import json as _json
    target = _plan3d_floor_export_cache_path_v1()
    target.write_text(
        _json.dumps(
            {
                "engine": "PLAN3D_FLOOR_EXPORT_CACHE_V1",
                "floors": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _plan3d_floor_export_cache_add_v1(floor_name, polygons, export_floor):
    import json as _json

    target = _plan3d_floor_export_cache_path_v1()

    try:
        payload = _json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        payload = {
            "engine": "PLAN3D_FLOOR_EXPORT_CACHE_V1",
            "floors": [],
        }

    floors = [
        row
        for row in (payload.get("floors", []) or [])
        if str(row.get("name", "")) != str(floor_name)
    ]

    cad_to_cm = float(export_floor.get("cad_to_cm", 1.0) or 1.0)
    pivot_x = float(export_floor.get("pivot_x", 0.0) or 0.0)
    pivot_y = float(export_floor.get("pivot_y", 0.0) or 0.0)
    base_z_cm = float(export_floor.get("base_z_cm", 0.0) or 0.0)

    objects = []

    for polygon_index, polygon in enumerate(polygons or (), start=1):
        rings = []
        raw_rings = [polygon.exterior, *list(polygon.interiors)]

        for ring in raw_rings:
            try:
                coords = list(ring.coords)
            except Exception:
                coords = []

            if len(coords) >= 2 and coords[0] == coords[-1]:
                coords = coords[:-1]

            points = []

            for raw_x, raw_y in coords:
                points.append(
                    [
                        (float(raw_x) - pivot_x) * cad_to_cm,
                        (float(raw_y) - pivot_y) * cad_to_cm,
                        base_z_cm,
                    ]
                )

            if len(points) >= 3:
                rings.append(
                    {
                        "closed": True,
                        "points": points,
                    }
                )

        if rings:
            objects.append(
                {
                    "index": int(polygon_index),
                    "rings": rings,
                }
            )

    floors.append(
        {
            "name": str(floor_name),
            "safe_name": str(export_floor.get("safe_name", floor_name)),
            "pivot_x": pivot_x,
            "pivot_y": pivot_y,
            "cad_to_cm": cad_to_cm,
            "base_z_cm": base_z_cm,
            "object_count": len(objects),
            "objects": objects,
        }
    )

    target.write_text(
        _json.dumps(
            {
                "engine": "PLAN3D_FLOOR_EXPORT_CACHE_V1",
                "floors": floors,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        "PLAN3D FLOOR EXPORT CACHE V1 |",
        floor_name,
        "| objects=",
        len(objects),
        "| base_z_cm=",
        format(base_z_cm, ".3f"),
        flush=True,
    )
