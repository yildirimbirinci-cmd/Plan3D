from __future__ import annotations

from pathlib import Path
import re

# PLAN3D_WALL_EXPORT_AUDIT_V1


def _dist2(a, b):
    dx = float(a[0]) - float(b[0])
    dy = float(a[1]) - float(b[1])
    return dx * dx + dy * dy


def _identity(points, tolerance):
    scale = max(float(tolerance), 1.0e-12)
    values = tuple(
        (
            int(round(float(p[0]) / scale)),
            int(round(float(p[1]) / scale)),
        )
        for p in points
    )
    if not values:
        return ()
    variants = []
    count = len(values)
    for sequence in (values, tuple(reversed(values))):
        for index in range(count):
            variants.append(sequence[index:] + sequence[:index])
    return min(variants)





# PLAN3D_WALL_TOPOLOGY_NORMALIZE_V3
def _normalize_wall_topology(source_paths, tolerance_source):
    import math

    tol = max(float(tolerance_source), 1.0e-12)
    tol2 = tol * tol
    eps = max(tol * 1.0e-7, 1.0e-12)
    right_angle_cos_limit = math.sin(math.radians(2.0))
    collinear_sin_limit = math.sin(math.radians(0.5))

    def d2(a, b):
        dx = float(a[0]) - float(b[0])
        dy = float(a[1]) - float(b[1])
        return dx * dx + dy * dy

    def length(a, b):
        return math.hypot(float(b[0]) - float(a[0]), float(b[1]) - float(a[1]))

    def unit_vec(a, b):
        vx = float(b[0]) - float(a[0])
        vy = float(b[1]) - float(a[1])
        ll = math.hypot(vx, vy)
        if ll <= eps:
            return None
        return (vx / ll, vy / ll)

    def line_intersection(a, b, c, d):
        x1, y1 = float(a[0]), float(a[1])
        x2, y2 = float(b[0]), float(b[1])
        x3, y3 = float(c[0]), float(c[1])
        x4, y4 = float(d[0]), float(d[1])

        r1x, r1y = x2 - x1, y2 - y1
        r2x, r2y = x4 - x3, y4 - y3
        den = r1x * r2y - r1y * r2x
        if abs(den) <= eps:
            return None

        qpx, qpy = x3 - x1, y3 - y1
        t = (qpx * r2y - qpy * r2x) / den
        u = (qpx * r1y - qpy * r1x) / den
        return (x1 + t * r1x, y1 + t * r1y), t, u

    def point_line_distance(p, a, b):
        vx = float(b[0]) - float(a[0])
        vy = float(b[1]) - float(a[1])
        ll = math.hypot(vx, vy)
        if ll <= eps:
            return float("inf")
        return abs(vx * (float(a[1]) - float(p[1])) - (float(a[0]) - float(p[0])) * vy) / ll

    def near_right_angle(a, b, c, d):
        u = unit_vec(a, b)
        v = unit_vec(c, d)
        if u is None or v is None:
            return False
        cosv = abs(u[0] * v[0] + u[1] * v[1])
        return cosv <= right_angle_cos_limit

    def collinear_through(node, p1, p2):
        v1 = (float(p1[0]) - float(node[0]), float(p1[1]) - float(node[1]))
        v2 = (float(p2[0]) - float(node[0]), float(p2[1]) - float(node[1]))
        l1 = math.hypot(v1[0], v1[1])
        l2 = math.hypot(v2[0], v2[1])
        if l1 <= eps or l2 <= eps:
            return False
        sinv = abs(v1[0] * v2[1] - v1[1] * v2[0]) / (l1 * l2)
        dot = v1[0] * v2[0] + v1[1] * v2[1]
        return sinv <= collinear_sin_limit and dot < 0.0

    paths = []
    closed_flags = []
    for source_path in source_paths or ():
        pts = []
        for raw in source_path or ():
            try:
                pts.append([float(raw[0]), float(raw[1])])
            except (TypeError, ValueError, IndexError):
                continue
        is_closed = bool(len(pts) >= 3 and d2(pts[0], pts[-1]) <= 1.0e-18)
        paths.append(pts)
        closed_flags.append(is_closed)

    def endpoint_incident_line(pi, vi):
        pts = paths[pi]
        if len(pts) < 2:
            return None
        if vi == 0:
            return pts[0], pts[1]
        return pts[-1], pts[-2]

    endpoints = []
    for pi, pts in enumerate(paths):
        if len(pts) < 2 or closed_flags[pi]:
            continue
        endpoints.append((pi, 0))
        endpoints.append((pi, len(pts) - 1))

    parent = list(range(len(endpoints)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(len(endpoints)):
        pi, vi = endpoints[i]
        p = paths[pi][vi]
        for j in range(i + 1, len(endpoints)):
            pj, vj = endpoints[j]
            if pi == pj:
                continue
            q = paths[pj][vj]
            if d2(p, q) <= tol2:
                union(i, j)

    groups = {}
    for i in range(len(endpoints)):
        groups.setdefault(find(i), []).append(i)

    endpoint_weld_clusters = 0
    endpoint_welded = 0
    right_angle_locked_welds = 0

    for ids in groups.values():
        if len(ids) < 2 or len({endpoints[i][0] for i in ids}) < 2:
            continue

        target = None

        for ai in range(len(ids)):
            if target is not None:
                break
            pi, vi = endpoints[ids[ai]]
            l1 = endpoint_incident_line(pi, vi)
            if l1 is None:
                continue
            for bi in range(ai + 1, len(ids)):
                pj, vj = endpoints[ids[bi]]
                if pi == pj:
                    continue
                l2 = endpoint_incident_line(pj, vj)
                if l2 is None:
                    continue
                if not near_right_angle(l1[0], l1[1], l2[0], l2[1]):
                    continue
                inter = line_intersection(l1[0], l1[1], l2[0], l2[1])
                if inter is None:
                    continue
                q = inter[0]
                if all(d2(paths[endpoints[k][0]][endpoints[k][1]], q) <= tol2 for k in ids):
                    target = q
                    right_angle_locked_welds += 1
                    break

        if target is None:
            target = (
                sum(paths[endpoints[i][0]][endpoints[i][1]][0] for i in ids) / len(ids),
                sum(paths[endpoints[i][0]][endpoints[i][1]][1] for i in ids) / len(ids),
            )

        endpoint_weld_clusters += 1
        endpoint_welded += len(ids)
        for i in ids:
            pi, vi = endpoints[i]
            paths[pi][vi][0] = target[0]
            paths[pi][vi][1] = target[1]

    split_requests = {}
    endpoint_segment_snaps = 0
    extension_snaps = 0
    right_angle_locked_snaps = 0

    for pi, pts in enumerate(paths):
        if len(pts) < 2 or closed_flags[pi]:
            continue

        for vi in (0, len(pts) - 1):
            own_line = endpoint_incident_line(pi, vi)
            if own_line is None:
                continue
            p = tuple(pts[vi])
            best = None

            for qpi, qpts in enumerate(paths):
                if len(qpts) < 2 or qpi == pi:
                    continue

                for si in range(len(qpts) - 1):
                    a = qpts[si]
                    b = qpts[si + 1]
                    inter = line_intersection(own_line[0], own_line[1], a, b)
                    if inter is None:
                        continue

                    q, own_t, target_t = inter
                    move2 = d2(p, q)
                    if move2 > tol2:
                        continue

                    seg_len = length(a, b)
                    if seg_len <= eps:
                        continue

                    ext_ratio = tol / seg_len
                    if target_t < -ext_ratio or target_t > 1.0 + ext_ratio:
                        continue

                    is_right = near_right_angle(own_line[0], own_line[1], a, b)
                    score = move2 - (tol2 * 0.10 if is_right else 0.0)

                    if best is None or score < best[0]:
                        best = (score, qpi, si, target_t, q, is_right)

            if best is None:
                continue

            _, qpi, si, target_t, q, is_right = best
            pts[vi][0], pts[vi][1] = q[0], q[1]
            endpoint_segment_snaps += 1
            if is_right:
                right_angle_locked_snaps += 1

            qpts = paths[qpi]
            if eps < target_t < 1.0 - eps:
                split_requests.setdefault((qpi, si), []).append((target_t, q))
            elif target_t <= eps:
                if d2(qpts[si], q) <= tol2:
                    qpts[si][0], qpts[si][1] = q[0], q[1]
                    extension_snaps += 1
            else:
                if d2(qpts[si + 1], q) <= tol2:
                    qpts[si + 1][0], qpts[si + 1][1] = q[0], q[1]
                    extension_snaps += 1

    for qpi in range(len(paths)):
        qpts = paths[qpi]
        reqs = [(si, vals) for (pi_key, si), vals in split_requests.items() if pi_key == qpi]
        for si, vals in sorted(reqs, key=lambda x: x[0], reverse=True):
            uniq = []
            for t, q in sorted(vals, key=lambda x: x[0]):
                if not uniq or d2(uniq[-1][1], q) > eps * eps:
                    uniq.append((t, q))
            qpts[si + 1:si + 1] = [[q[0], q[1]] for t, q in uniq]

    split_vertices_added = sum(len(v) for v in split_requests.values())

    segments = []
    for pts in paths:
        for si in range(max(0, len(pts) - 1)):
            a = (float(pts[si][0]), float(pts[si][1]))
            b = (float(pts[si + 1][0]), float(pts[si + 1][1]))
            if length(a, b) > eps:
                segments.append((a, b))

    split_ts = [set((0.0, 1.0)) for _ in segments]
    overlap_pairs = 0

    for i in range(len(segments)):
        a, b = segments[i]
        abx, aby = b[0] - a[0], b[1] - a[1]
        ab2 = abx * abx + aby * aby
        if ab2 <= eps * eps:
            continue

        for j in range(i + 1, len(segments)):
            c, d = segments[j]
            cdx, cdy = d[0] - c[0], d[1] - c[1]
            la = math.hypot(abx, aby)
            lb = math.hypot(cdx, cdy)
            if la <= eps or lb <= eps:
                continue

            sin_angle = abs(abx * cdy - aby * cdx) / (la * lb)
            if sin_angle > math.sin(math.radians(1.0)):
                continue

            if point_line_distance(c, a, b) > tol or point_line_distance(d, a, b) > tol:
                continue

            def t_on_ab(p):
                return ((p[0] - a[0]) * abx + (p[1] - a[1]) * aby) / ab2

            tc, td = t_on_ab(c), t_on_ab(d)
            lo, hi = min(tc, td), max(tc, td)
            if hi < -eps or lo > 1.0 + eps:
                continue

            overlap_lo, overlap_hi = max(0.0, lo), min(1.0, hi)
            if overlap_hi - overlap_lo <= eps:
                continue

            overlap_pairs += 1
            for t in (overlap_lo, overlap_hi):
                if eps < t < 1.0 - eps:
                    split_ts[i].add(float(t))

            dc2 = cdx * cdx + cdy * cdy
            if dc2 > eps * eps:
                for p2 in (a, b):
                    tj = ((p2[0] - c[0]) * cdx + (p2[1] - c[1]) * cdy) / dc2
                    if eps < tj < 1.0 - eps and point_line_distance(p2, c, d) <= tol:
                        split_ts[j].add(float(tj))

    atomic = []
    for idx, (a, b) in enumerate(segments):
        ts = sorted(split_ts[idx])
        for k in range(len(ts) - 1):
            t0, t1 = ts[k], ts[k + 1]
            if t1 - t0 <= eps:
                continue
            p0 = (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0)
            p1 = (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)
            if length(p0, p1) > eps:
                atomic.append((p0, p1))

    identity_scale = max(tol * 0.01, 1.0e-9)

    def qpt(p):
        return (
            int(round(float(p[0]) / identity_scale)),
            int(round(float(p[1]) / identity_scale)),
        )

    unique = {}
    node_point = {}
    for a, b in atomic:
        qa, qb = qpt(a), qpt(b)
        if qa == qb:
            continue
        key = (qa, qb) if qa <= qb else (qb, qa)
        if key not in unique:
            unique[key] = (a, b)
        node_point.setdefault(qa, a)
        node_point.setdefault(qb, b)

    duplicate_atomic_removed = max(0, len(atomic) - len(unique))
    edge_keys = set(unique.keys())

    redundant_inline_vertices_removed = 0
    changed = True

    while changed:
        changed = False
        adjacency = {}
        for u, v in edge_keys:
            adjacency.setdefault(u, set()).add(v)
            adjacency.setdefault(v, set()).add(u)

        for node, neigh in list(adjacency.items()):
            if len(neigh) != 2:
                continue

            n1, n2 = tuple(neigh)
            p = node_point[node]
            p1 = node_point[n1]
            p2 = node_point[n2]

            if not collinear_through(p, p1, p2):
                continue

            e1 = (node, n1) if node <= n1 else (n1, node)
            e2 = (node, n2) if node <= n2 else (n2, node)
            en = (n1, n2) if n1 <= n2 else (n2, n1)

            edge_keys.discard(e1)
            edge_keys.discard(e2)
            edge_keys.add(en)

            redundant_inline_vertices_removed += 1
            changed = True
            break

    normalized_segments = [(node_point[u], node_point[v]) for u, v in sorted(edge_keys)]
    result_paths = [[[a[0], a[1]], [b[0], b[1]]] for a, b in normalized_segments]

    return result_paths, {
        "endpoint_weld_clusters": endpoint_weld_clusters,
        "endpoint_welded": endpoint_welded,
        "right_angle_locked_welds": right_angle_locked_welds,
        "endpoint_segment_snaps": endpoint_segment_snaps,
        "extension_snaps": extension_snaps,
        "right_angle_locked_snaps": right_angle_locked_snaps,
        "split_vertices_added": split_vertices_added,
        "collinear_overlap_pairs": overlap_pairs,
        "duplicate_atomic_removed": duplicate_atomic_removed,
        "redundant_inline_vertices_removed": redundant_inline_vertices_removed,
        "normalized_segments": len(normalized_segments),
    }


def _cad_unit_info(viewport):
    # Reuse the bridge's installed unit reader when present.
    try:
        import plan3d_max_bridge as base
        reader = getattr(base, "_cad_unit_info", None)
        if callable(reader):
            info = reader(viewport)
            if isinstance(info, dict):
                return {
                    "code": int(info.get("code", 0)),
                    "name": str(info.get("name", "Unknown")),
                    "to_cm": float(info.get("to_cm", 1.0)),
                }
    except Exception:
        pass

    mapping = {
        0: ("Unitless", 1.0),
        1: ("Inches", 2.54),
        2: ("Feet", 30.48),
        3: ("Miles", 160934.4),
        4: ("Millimeters", 0.1),
        5: ("Centimeters", 1.0),
        6: ("Meters", 100.0),
        7: ("Kilometers", 100000.0),
        10: ("Yards", 91.44),
        14: ("Decimeters", 10.0),
        15: ("Decameters", 1000.0),
        16: ("Hectometers", 10000.0),
    }

    code = 0
    doc = getattr(viewport, "_document", None)
    if doc is not None:
        try:
            code = int(doc.header.get("$INSUNITS", 0) or 0)
        except Exception:
            code = 0

    name, to_cm = mapping.get(code, ("Unknown", 1.0))
    return {"code": code, "name": name, "to_cm": to_cm}


def _safe_name(value):
    text = re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "")).strip("_")
    return text or "Floor"


def _clean_floor(viewport, floor_name, bounds, pivot, settings):
    # PLAN3D_RAW_WALL_PASSTHROUGH_V1
    # Wall only. Exterior Wall stays excluded upstream.
    # No cleanup stage is allowed to drop valid Wall source paths.

    raw_geometry = viewport._pivot_collect_wall_geometry(bounds)
    if not raw_geometry:
        raise RuntimeError(
            "No Wall geometry found for " + str(floor_name)
        )

    units_info = _cad_unit_info(viewport)
    cad_to_cm = float(units_info["to_cm"])



    # PLAN3D_WALL_TOPOLOGY_NORMALIZE_V3
    source_to_mm = max(cad_to_cm * 10.0, 1.0e-12)
    topology_tolerance_mm = 10.0
    topology_tolerance_source = topology_tolerance_mm / source_to_mm

    raw_geometry, topology_report = _normalize_wall_topology(
        raw_geometry,
        topology_tolerance_source,
    )

    print(
        "PLAN3D WALL TOPOLOGY V3 |",
        floor_name,
        "| tolerance_mm=", topology_tolerance_mm,
        "| endpoint_welded=", topology_report.get("endpoint_welded", 0),
        "| right_angle_welds=", topology_report.get("right_angle_locked_welds", 0),
        "| endpoint_segment_snaps=", topology_report.get("endpoint_segment_snaps", 0),
        "| extension_snaps=", topology_report.get("extension_snaps", 0),
        "| right_angle_snaps=", topology_report.get("right_angle_locked_snaps", 0),
        "| overlap_pairs=", topology_report.get("collinear_overlap_pairs", 0),
        "| inline_vertices_removed=", topology_report.get("redundant_inline_vertices_removed", 0),
        "| normalized_segments=", topology_report.get("normalized_segments", 0),
        flush=True,
    )

    pivot_x = float(pivot["pivot_x"])
    pivot_y = float(pivot["pivot_y"])

    base_z = float(settings.get("floor_elevation_cm", 0.0))
    wall_height = float(settings.get("wall_height_cm", 280.0))
    slab_thickness = float(settings.get("slab_thickness_cm", 35.0))
    floor_to_floor = float(
        settings.get("floor_to_floor_cm", wall_height + slab_thickness)
    )

    paths = []
    raw_path_count = 0
    raw_segment_count = 0
    exported_segment_count = 0
    skipped_path_count = 0

    for source_path in raw_geometry:
        raw_path_count += 1

        source_points = []
        for source_point in source_path or ():
            try:
                source_points.append(
                    (
                        float(source_point[0]),
                        float(source_point[1]),
                    )
                )
            except (TypeError, ValueError, IndexError):
                continue

        if len(source_points) < 2:
            skipped_path_count += 1
            continue

        is_closed = bool(
            len(source_points) >= 3
            and _dist2(source_points[0], source_points[-1]) <= 1.0e-18
        )

        raw_segment_count += max(0, len(source_points) - 1)

        if is_closed:
            send_points = source_points[:-1]
            source_segment_count = len(send_points)
        else:
            send_points = source_points
            source_segment_count = max(0, len(send_points) - 1)

        if len(send_points) < 2:
            skipped_path_count += 1
            continue

        points = [
            (
                (float(x) - pivot_x) * cad_to_cm,
                (float(y) - pivot_y) * cad_to_cm,
                base_z,
            )
            for x, y in send_points
        ]

        paths.append(
            {
                "closed": bool(is_closed),
                "points": points,
            }
        )
        exported_segment_count += source_segment_count

    if not paths:
        raise RuntimeError(
            "No usable Wall geometry remains for " + str(floor_name)
        )

    if skipped_path_count:
        raise RuntimeError(
            "Wall export blocked: "
            + str(skipped_path_count)
            + " source Wall path(s) were invalid on "
            + str(floor_name)
        )

    report = {
        "plan3d_engine": "PLAN3D_WALL_TOPOLOGY_NORMALIZE_V3",
        "raw_wall_paths": int(raw_path_count),
        "raw_wall_segments": int(raw_segment_count),
        "exported_wall_paths": int(len(paths)),
        "exported_wall_segments": int(exported_segment_count),
        "skipped_wall_paths": int(skipped_path_count),
        "exterior_wall_exported": 0,
        "topology_tolerance_mm": float(topology_tolerance_mm),
        "endpoint_weld_clusters": int(topology_report.get("endpoint_weld_clusters", 0)),
        "endpoint_welded": int(topology_report.get("endpoint_welded", 0)),
        "endpoint_segment_snaps": int(topology_report.get("endpoint_segment_snaps", 0)),
        "split_vertices_added": int(topology_report.get("split_vertices_added", 0)),
        "collinear_overlap_pairs": int(topology_report.get("collinear_overlap_pairs", 0)),
        "duplicate_atomic_removed": int(topology_report.get("duplicate_atomic_removed", 0)),
        "normalized_segments": int(topology_report.get("normalized_segments", 0)),
    }

    print(
        "PLAN3D RAW WALL EXPORT |",
        floor_name,
        "| source_paths=", raw_path_count,
        "| source_segments=", raw_segment_count,
        "| exported_paths=", len(paths),
        "| exported_segments=", exported_segment_count,
        "| skipped_paths=", skipped_path_count,
        "| ExteriorWall=0",
        flush=True,
    )

    return {
        "name": str(floor_name),
        "safe_name": _safe_name(floor_name),
        "pivot_x": pivot_x,
        "pivot_y": pivot_y,
        "base_z_cm": base_z,
        "wall_height_cm": wall_height,
        "slab_thickness_cm": slab_thickness,
        "floor_to_floor_cm": floor_to_floor,
        "cad_unit_code": int(units_info["code"]),
        "cad_unit_name": str(units_info["name"]),
        "cad_to_cm": cad_to_cm,
        "path_count": len(paths),
        "paths": paths,
        "topology_report": report,
    }


def prepare_wall_only_transfer(panel):
    page = panel.parentWidget()
    if page is None:
        raise RuntimeError("CAD page is not available.")

    viewport = getattr(page, "viewport", None)
    if viewport is None:
        raise RuntimeError("CAD viewport is not available.")

    assignments = (
        panel._assignments.get("floor_plans", {})
        if isinstance(panel._assignments, dict)
        else {}
    )
    if not assignments:
        raise RuntimeError("No confirmed Floor Plan assignment is available.")

    pivots = dict(getattr(panel, "_floor_pivots", {}) or {})
    settings_map = dict(getattr(panel, "_floor_settings", {}) or {})

    missing = [str(name) for name in assignments if name not in pivots]
    if missing:
        raise RuntimeError("Pivot missing for floor(s): " + ", ".join(missing))

    floor_order = []
    if "Ground Floor" in assignments:
        floor_order.append("Ground Floor")

    for name in list(getattr(panel, "floor_names", []) or []):
        name = str(name)
        if name in assignments and name not in floor_order:
            floor_order.append(name)

    for name in assignments:
        if name not in floor_order:
            floor_order.append(name)

    floors = []
    for floor_name in floor_order:
        floor = _clean_floor(
            viewport,
            floor_name,
            assignments[floor_name],
            pivots[floor_name],
            dict(settings_map.get(floor_name, {})),
        )
        floors.append(floor)

    import plan3d_max_bridge as base
    make_script = getattr(base, "_make_maxscript", None)
    if not callable(make_script):
        raise RuntimeError("_make_maxscript() is not available.")

    runtime_dir = Path.cwd() / "runtime" / "max_bridge"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    pending = runtime_dir / "pending.ms"
    temp = runtime_dir / "pending.ms.tmp"

    # PLAN3D_WALL_EXPORT_LAYER_V1
    # First export stage is Wall, therefore all generated wall floor
    # spline objects are collected under one dedicated 3ds Max layer.
    # Future export stages can use their own dedicated layers.
    max_script = make_script(floors)

    wall_layer_script = r'''
-- PLAN3D_WALL_EXPORT_LAYER_V1
try
(
    local PLAN3D_LAYER_NAME = "PLAN3D_WALLS"
    local PLAN3D_LAYER = LayerManager.getLayerFromName PLAN3D_LAYER_NAME

    if PLAN3D_LAYER == undefined do
        PLAN3D_LAYER = LayerManager.newLayerFromName PLAN3D_LAYER_NAME

    local PLAN3D_LAYERED_COUNT = 0

    for obj in objects where matchPattern obj.name pattern:"PLAN3D_WALL_*" ignoreCase:true do
    (
        PLAN3D_LAYER.addNode obj
        PLAN3D_LAYERED_COUNT += 1
    )

    format "PLAN3D WALL LAYER OK | layer=% | objects=%\\n" PLAN3D_LAYER_NAME PLAN3D_LAYERED_COUNT
)
catch
(
    format "PLAN3D WALL LAYER ERROR | %\\n" (getCurrentException())
)
'''

    max_script = (
        max_script.rstrip()
        + "\n\n"
        + wall_layer_script.strip()
        + "\n"
    )

    temp.write_text(
        max_script,
        encoding="utf-8",
    )
    temp.replace(pending)

    for floor in floors:
        report = floor["topology_report"]
        print(
            "PLAN3D WALL PASSTHROUGH |",
            floor["name"],
            "| source_paths =",
            report.get("raw_wall_paths"),
            "| source_segments =",
            report.get("raw_wall_segments"),
            "| exported_paths =",
            report.get("exported_wall_paths"),
            "| exported_segments =",
            report.get("exported_wall_segments"),
            "| ExteriorWall = 0",
        )

    return {
        "floors": floors,
        "pending_script": str(pending),
        "watcher_path": str(runtime_dir / "PLAN3D_MAX_WATCHER.ms"),
    }
