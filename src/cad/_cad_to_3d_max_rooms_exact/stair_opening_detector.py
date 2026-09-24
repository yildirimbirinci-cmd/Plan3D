from __future__ import annotations

import math
import re


ENGINE = "CAD3D_STAIR_OPENING_GEOMETRY_V2"


def _point(value):
    try:
        return (float(value[0]), float(value[1]))
    except Exception:
        return None


def _signed_area(points):
    if len(points) < 3:
        return 0.0

    total = 0.0

    for index, a in enumerate(points):
        b = points[(index + 1) % len(points)]
        total += a[0] * b[1] - b[0] * a[1]

    return total * 0.5


def _canonical_angle(dx, dy):
    angle = math.atan2(dy, dx)

    while angle < 0.0:
        angle += math.pi

    while angle >= math.pi:
        angle -= math.pi

    return angle


def _angle_distance(a, b):
    diff = abs(a - b)
    return min(diff, math.pi - diff)


def _excluded_item(item):
    layer = str(item.get("layer", "") or "").upper()
    entity_type = str(
        item.get("type", item.get("entity_type", "")) or ""
    ).upper()

    excluded_layer_tokens = (
        "FURN",
        "TEXT",
        "DIM",
        "HATCH",
        "GRID",
        "TITLE",
        "NOTE",
        "ANNO",
    )

    if any(token in layer for token in excluded_layer_tokens):
        return True

    if entity_type in {
        "TEXT",
        "MTEXT",
        "HATCH",
        "DIMENSION",
        "LEADER",
        "MLEADER",
    }:
        return True

    return False


def _extract_segments(geometry, source_to_mm):
    result = []

    # Broad enough for schematic and detailed stair drawings.
    minimum_mm = 120.0
    maximum_mm = 3000.0

    for source_index, item in enumerate(geometry or []):
        if not isinstance(item, dict):
            continue

        if _excluded_item(item):
            continue

        points = []

        for value in item.get("points", []) or []:
            point = _point(value)

            if point is None:
                continue

            if (
                points
                and math.hypot(
                    point[0] - points[-1][0],
                    point[1] - points[-1][1],
                )
                <= 1.0e-9
            ):
                continue

            points.append(point)

        if len(points) < 2:
            continue

        pairs = list(zip(points, points[1:]))

        if bool(item.get("closed", False)) and len(points) >= 3:
            pairs.append((points[-1], points[0]))

        for a, b in pairs:
            dx = b[0] - a[0]
            dy = b[1] - a[1]
            length_source = math.hypot(dx, dy)
            length_mm = length_source * source_to_mm

            if not (minimum_mm <= length_mm <= maximum_mm):
                continue

            result.append(
                {
                    "a": a,
                    "b": b,
                    "center": (
                        (a[0] + b[0]) * 0.5,
                        (a[1] + b[1]) * 0.5,
                    ),
                    "length_source": length_source,
                    "length_mm": length_mm,
                    "angle": _canonical_angle(dx, dy),
                    "layer": str(item.get("layer", "") or ""),
                    "source_index": int(source_index),
                }
            )

    return result


def _semantic_candidates(geometry, source_to_mm):
    stair_tokens = {
        "STAIR",
        "STAIRS",
        "STAIRCASE",
        "MERDIVEN",
        "TREPPE",
        "ESCALIER",
    }

    groups = {}

    for item in geometry or []:
        if not isinstance(item, dict):
            continue

        layer = str(item.get("layer", "") or "").strip()

        tokens = set(
            re.findall(
                r"[A-ZÇĞİÖŞÜ]+",
                layer.upper(),
            )
        )

        if not (tokens & stair_tokens):
            continue

        points = [
            point
            for point in (
                _point(value)
                for value in item.get("points", []) or []
            )
            if point is not None
        ]

        if not points:
            continue

        groups.setdefault(layer, []).extend(points)

    output = []

    for layer, points in groups.items():
        min_x = min(point[0] for point in points)
        min_y = min(point[1] for point in points)
        max_x = max(point[0] for point in points)
        max_y = max(point[1] for point in points)

        width_mm = (max_x - min_x) * source_to_mm
        height_mm = (max_y - min_y) * source_to_mm
        area_m2 = width_mm * height_mm / 1000000.0

        if not (0.40 <= area_m2 <= 40.0):
            continue

        polygon = [
            [min_x, min_y],
            [max_x, min_y],
            [max_x, max_y],
            [min_x, max_y],
        ]

        output.append(
            {
                "method": "SEMANTIC_LAYER",
                "layer": layer,
                "score": 1000.0,
                "tread_count": None,
                "polygon": polygon,
                "area_m2": area_m2,
                "center": [
                    (min_x + max_x) * 0.5,
                    (min_y + max_y) * 0.5,
                ],
            }
        )

    return output


def _cluster_for_orientation(
    segments,
    indices,
    angle,
    source_to_mm,
):
    ux = math.cos(angle)
    uy = math.sin(angle)
    nx = -uy
    ny = ux

    info = {}

    for index in indices:
        center = segments[index]["center"]

        info[index] = {
            "u": center[0] * ux + center[1] * uy,
            "n": center[0] * nx + center[1] * ny,
        }

    adjacency = {index: set() for index in indices}

    for left_pos, left_index in enumerate(indices):
        left = segments[left_index]

        for right_index in indices[left_pos + 1:]:
            right = segments[right_index]

            if math.degrees(
                _angle_distance(
                    left["angle"],
                    right["angle"],
                )
            ) > 9.0:
                continue

            short_length = max(
                min(left["length_mm"], right["length_mm"]),
                1.0e-9,
            )

            long_length = max(
                left["length_mm"],
                right["length_mm"],
            )

            if long_length / short_length > 2.0:
                continue

            delta_u_mm = abs(
                info[left_index]["u"]
                - info[right_index]["u"]
            ) * source_to_mm

            delta_n_mm = abs(
                info[left_index]["n"]
                - info[right_index]["n"]
            ) * source_to_mm

            if delta_u_mm > max(450.0, short_length * 0.65):
                continue

            if not (25.0 <= delta_n_mm <= 750.0):
                continue

            adjacency[left_index].add(right_index)
            adjacency[right_index].add(left_index)

    components = []
    visited = set()

    for seed in indices:
        if seed in visited:
            continue

        stack = [seed]
        component = []

        while stack:
            current = stack.pop()

            if current in visited:
                continue

            visited.add(current)
            component.append(current)
            stack.extend(adjacency[current] - visited)

        if len(component) >= 4:
            components.append((component, info, ux, uy, nx, ny))

    return components


def _component_candidates(segments, source_to_mm):
    if not segments:
        return []

    buckets = {}

    # 10 degree buckets with overlap by also checking angle distance
    # inside each cluster.
    for index, segment in enumerate(segments):
        degrees = math.degrees(segment["angle"])
        bucket = int(round(degrees / 10.0))
        buckets.setdefault(bucket, []).append(index)

    output = []

    for bucket_indices in buckets.values():
        if len(bucket_indices) < 4:
            continue

        mean_x = sum(
            math.cos(segments[index]["angle"] * 2.0)
            for index in bucket_indices
        )
        mean_y = sum(
            math.sin(segments[index]["angle"] * 2.0)
            for index in bucket_indices
        )

        angle = 0.5 * math.atan2(mean_y, mean_x)

        if angle < 0.0:
            angle += math.pi

        components = _cluster_for_orientation(
            segments,
            bucket_indices,
            angle,
            source_to_mm,
        )

        for component, info, ux, uy, nx, ny in components:
            if len(component) > 60:
                # Dense hatch-like patterns are not stair treads.
                continue

            n_values = sorted(
                info[index]["n"]
                for index in component
            )

            merge_tol_source = 20.0 / source_to_mm
            unique_n = []

            for value in n_values:
                if (
                    not unique_n
                    or abs(value - unique_n[-1])
                    > merge_tol_source
                ):
                    unique_n.append(value)

            if len(unique_n) < 4:
                continue

            spacings_mm = [
                (
                    unique_n[index + 1]
                    - unique_n[index]
                )
                * source_to_mm
                for index in range(len(unique_n) - 1)
            ]

            ordered = sorted(spacings_mm)
            median_spacing = ordered[len(ordered) // 2]

            if not (45.0 <= median_spacing <= 500.0):
                continue

            good_spacing_count = sum(
                1
                for value in spacings_mm
                if (
                    median_spacing * 0.40
                    <= value
                    <= median_spacing * 1.80
                )
            )

            regularity = (
                good_spacing_count
                / max(len(spacings_mm), 1)
            )

            if regularity < 0.45:
                continue

            u_values = []
            n_endpoint_values = []
            lengths_mm = []
            layers = set()

            for index in component:
                segment = segments[index]
                lengths_mm.append(segment["length_mm"])

                if segment["layer"]:
                    layers.add(segment["layer"])

                for point in (segment["a"], segment["b"]):
                    u_values.append(
                        point[0] * ux
                        + point[1] * uy
                    )
                    n_endpoint_values.append(
                        point[0] * nx
                        + point[1] * ny
                    )

            u_min = min(u_values)
            u_max = max(u_values)
            n_min = min(n_endpoint_values)
            n_max = max(n_endpoint_values)

            width_mm = (u_max - u_min) * source_to_mm
            depth_mm = (n_max - n_min) * source_to_mm

            if not (450.0 <= width_mm <= 3500.0):
                continue

            if not (400.0 <= depth_mm <= 8000.0):
                continue

            median_length_mm = sorted(lengths_mm)[
                len(lengths_mm) // 2
            ]

            center_u_values_mm = [
                info[index]["u"] * source_to_mm
                for index in component
            ]

            center_u_spread_mm = (
                max(center_u_values_mm)
                - min(center_u_values_mm)
            )

            if center_u_spread_mm > max(
                500.0,
                median_length_mm * 0.85,
            ):
                continue

            expand_u_source = (
                min(120.0, width_mm * 0.06)
                / source_to_mm
            )

            expand_n_source = (
                median_spacing * 0.75 + 50.0
            ) / source_to_mm

            u_min -= expand_u_source
            u_max += expand_u_source
            n_min -= expand_n_source
            n_max += expand_n_source

            def from_un(u_value, n_value):
                return [
                    u_value * ux + n_value * nx,
                    u_value * uy + n_value * ny,
                ]

            polygon = [
                from_un(u_min, n_min),
                from_un(u_max, n_min),
                from_un(u_max, n_max),
                from_un(u_min, n_max),
            ]

            if _signed_area(polygon) < 0.0:
                polygon.reverse()

            area_m2 = (
                (u_max - u_min)
                * source_to_mm
                * (n_max - n_min)
                * source_to_mm
                / 1000000.0
            )

            center = [
                sum(point[0] for point in polygon) / 4.0,
                sum(point[1] for point in polygon) / 4.0,
            ]

            score = (
                len(unique_n) * 12.0
                + regularity * 30.0
                - abs(median_spacing - 180.0) * 0.01
            )

            output.append(
                {
                    "method": "REPEATED_PARALLEL_TREADS_V2",
                    "score": float(score),
                    "tread_count": int(len(unique_n)),
                    "median_spacing_mm": float(median_spacing),
                    "regularity": float(regularity),
                    "width_mm": float(
                        (u_max - u_min) * source_to_mm
                    ),
                    "depth_mm": float(
                        (n_max - n_min) * source_to_mm
                    ),
                    "area_m2": float(area_m2),
                    "center": center,
                    "polygon": polygon,
                    "source_layers": sorted(layers),
                    "source_segment_count": int(len(component)),
                }
            )

    return output


def _bbox(polygon):
    xs = [float(point[0]) for point in polygon]
    ys = [float(point[1]) for point in polygon]

    return (
        min(xs),
        min(ys),
        max(xs),
        max(ys),
    )


def _bbox_iou(a, b):
    ax0, ay0, ax1, ay1 = _bbox(a)
    bx0, by0, bx1, by1 = _bbox(b)

    ix0 = max(ax0, bx0)
    iy0 = max(ay0, by0)
    ix1 = min(ax1, bx1)
    iy1 = min(ay1, by1)

    iw = max(0.0, ix1 - ix0)
    ih = max(0.0, iy1 - iy0)
    intersection = iw * ih

    area_a = max(0.0, (ax1 - ax0) * (ay1 - ay0))
    area_b = max(0.0, (bx1 - bx0) * (by1 - by0))
    union = area_a + area_b - intersection

    if union <= 1.0e-9:
        return 0.0

    return intersection / union


def detect_stair_openings(
    geometry,
    *,
    source_to_mm,
):
    source_to_mm = float(source_to_mm)

    if (
        not math.isfinite(source_to_mm)
        or source_to_mm <= 0.0
    ):
        raise RuntimeError(
            "Stair detector V2: invalid source_to_mm."
        )

    geometry = list(geometry or [])

    semantic = _semantic_candidates(
        geometry,
        source_to_mm,
    )

    segments = _extract_segments(
        geometry,
        source_to_mm,
    )

    geometric = _component_candidates(
        segments,
        source_to_mm,
    )

    # CAD3D_STAIR_SEMANTIC_PRIORITY_V48
    #
    # Geometry-only repeated-line detection is a FALLBACK, not a peer of an
    # explicit stair layer.  The previous code combined both lists and could
    # classify window/furniture parallel lines as a second stair opening even
    # when a semantic stair candidate was already present.
    #
    # General rule:
    # - if explicit semantic stair evidence exists -> use semantic only;
    # - otherwise -> use geometric repeated-tread fallback.
    candidates = (
        list(semantic)
        if semantic
        else list(geometric)
    )

    candidates.sort(
        key=lambda item: float(
            item.get("score", 0.0) or 0.0
        ),
        reverse=True,
    )

    accepted = []

    for candidate in candidates:
        polygon = candidate.get("polygon", [])

        if len(polygon) < 3:
            continue

        if any(
            _bbox_iou(
                polygon,
                previous["polygon"],
            ) >= 0.35
            for previous in accepted
        ):
            continue

        accepted.append(candidate)

        if len(accepted) >= 8:
            break

    for index, candidate in enumerate(
        accepted,
        start=1,
    ):
        candidate["stair_id"] = (
            "STAIR_"
            + str(index).zfill(2)
        )

    return {
        "engine": ENGINE,
        "geometry_item_count": len(geometry),
        "source_segment_count": len(segments),
        "semantic_candidate_count": len(semantic),
        "geometric_candidate_count": len(geometric),
        "candidate_count": len(candidates),
        "accepted_count": len(accepted),
        "accepted": accepted,
    }
