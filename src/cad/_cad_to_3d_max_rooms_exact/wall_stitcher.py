from __future__ import annotations

import math

from cad._cad_to_3d_max_rooms_exact.cad_intelligence import (
    extract_segments,
    find_parallel_pairs,
    infer_cad_profile,
    semantic_category,
)


CONFIRMED_LAYER = "__WALL_CONFIRMED__"


def _line_bbox(p0, p1, pad=0.0):
    return (
        min(p0[0], p1[0]) - pad,
        min(p0[1], p1[1]) - pad,
        max(p0[0], p1[0]) + pad,
        max(p0[1], p1[1]) + pad,
    )


def _boxes_overlap(a, b):
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def _opening_boxes(source_geometry, profile):
    gaps = profile.get("gap_families") or []
    base_gap = gaps[0]["gap"] if gaps else max(profile.get("median_length", 1.0) * 0.35, 1.0)
    pad = max(base_gap * 0.18, profile.get("drawing_diagonal", 1.0) * 0.00008)
    boxes = []
    for item in source_geometry or []:
        if semantic_category(item.get("layer")) not in {"door", "window"}:
            continue
        pts = item.get("points") or []
        if not pts:
            continue
        try:
            xs = [float(p[0]) for p in pts]
            ys = [float(p[1]) for p in pts]
        except Exception:
            continue
        boxes.append((min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad))
    return boxes


def _hits_opening(p0, p1, opening_boxes, pad=0.0):
    box = _line_bbox(p0, p1, pad)
    return any(_boxes_overlap(box, ob) for ob in opening_boxes)


def _segment_key(item, tol):
    pts = item.get("points") or []
    if len(pts) != 2:
        return None
    try:
        p0 = (float(pts[0][0]), float(pts[0][1]))
        p1 = (float(pts[1][0]), float(pts[1][1]))
    except Exception:
        return None
    if p1 < p0:
        p0, p1 = p1, p0
    q = max(tol, 1e-9)
    return tuple(round(v / q) for v in (*p0, *p1))


def _dedupe(geometry, tol):
    out = []
    seen = set()
    for item in geometry:
        key = _segment_key(item, tol)
        if key is None or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _make_segment(p0, p1, tag):
    if math.hypot(p1[0] - p0[0], p1[1] - p0[1]) <= 1e-9:
        return None
    return {
        "layer": CONFIRMED_LAYER,
        "points": [p0, p1],
        "wall_kind": tag,
    }


def _oriented_endpoints(segment, ux, uy):
    p0 = (segment["x1"], segment["y1"])
    p1 = (segment["x2"], segment["y2"])
    t0 = p0[0] * ux + p0[1] * uy
    t1 = p1[0] * ux + p1[1] * uy
    return (p0, p1) if t0 <= t1 else (p1, p0)


def _has_forward_continuation(endpoint, ux, uy, source, segments, max_distance, line_tol):
    ex, ey = endpoint
    for other in segments:
        if other["id"] == source["id"]:
            continue
        dx = other["x2"] - other["x1"]
        dy = other["y2"] - other["y1"]
        olen = other["length"]
        if olen <= 1e-9:
            continue
        oux, ouy = dx / olen, dy / olen
        parallel = abs(abs(oux * ux + ouy * uy) - 1.0)
        if parallel > 0.02:
            continue
        for px, py in ((other["x1"], other["y1"]), (other["x2"], other["y2"])):
            vx, vy = px - ex, py - ey
            along = vx * ux + vy * uy
            normal = abs(vx * (-uy) + vy * ux)
            if 0.0 < along <= max_distance and normal <= line_tol:
                return True
    return False


def _endcaps(wall_geometry, source_geometry, profile):
    segments = extract_segments(wall_geometry)
    pairs = find_parallel_pairs(segments, profile.get("gap_families") or None)
    openings = _opening_boxes(source_geometry, profile)
    additions = []
    for pair in pairs:
        a = pair["a"]; b = pair["b"]
        dx = a["x2"] - a["x1"]
        dy = a["y2"] - a["y1"]
        length = a["length"]
        if length <= 1e-9:
            continue
        ux, uy = dx / length, dy / length
        a_start, a_end = _oriented_endpoints(a, ux, uy)
        b_start, b_end = _oriented_endpoints(b, ux, uy)
        gap = max(pair["gap"], 1e-9)
        align_tol = gap * 0.40
        continuation = gap * 3.0
        line_tol = gap * 0.22

        for side, pa, pb, sign in (
            ("start", a_start, b_start, -1.0),
            ("end", a_end, b_end, 1.0),
        ):
            tangent_error = abs((pb[0] - pa[0]) * ux + (pb[1] - pa[1]) * uy)
            if tangent_error > align_tol:
                continue
            dirx, diry = ux * sign, uy * sign
            if _has_forward_continuation(pa, dirx, diry, a, segments, continuation, line_tol):
                continue
            if _has_forward_continuation(pb, dirx, diry, b, segments, continuation, line_tol):
                continue
            if _hits_opening(pa, pb, openings, line_tol):
                continue
            item = _make_segment(pa, pb, "generic_end_cap")
            if item is not None:
                additions.append(item)
    return additions, len(pairs)


def stitch_wall_geometry(wall_geometry, source_geometry):
    profile = infer_cad_profile(source_geometry)
    gaps = profile.get("gap_families") or []
    base = gaps[0]["gap"] if gaps else max(profile.get("median_length", 1.0) * 0.25, 1.0)
    dedupe_tol = max(base * 0.004, profile.get("drawing_diagonal", 1.0) * 0.000005)
    current = _dedupe(list(wall_geometry), dedupe_tol)
    raw_count = len(current)
    total_added = 0
    pair_count = 0
    for _ in range(2):
        additions, pair_count = _endcaps(current, source_geometry, profile)
        before = len(current)
        current = _dedupe(current + additions, dedupe_tol)
        added = len(current) - before
        if added <= 0:
            break
        total_added += added
    return {
        "engine": "GENERIC_WALL_STITCHER_V1",
        "wall_geometry": current,
        "raw_wall_faces": raw_count,
        "stitched_wall_faces": len(current),
        "stitch_added": total_added,
        "opening_guides": len(_opening_boxes(source_geometry, profile)),
        "endcap_pairs": pair_count,
    }
