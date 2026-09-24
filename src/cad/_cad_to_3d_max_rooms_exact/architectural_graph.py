"""
CAD3D Architectural Wall Graph V2

Purpose
-------
Recognize architectural walls as WALL OBJECTS, not as layers and not as
isolated parallel-line coincidences.

Recognition authority:
- layer name: 0
- layer group: 0
- geometry + topology: full authority

Core model:
1) extract neutral CAD segments;
2) form opposing-face WallBand candidates;
3) reject frame/stair/furniture-like bands with corridor/object evidence;
4) infer repeated wall-thickness families;
5) build a DIRECT structural graph from real finite contacts only;
6) elect the building-scale wall core;
7) bridge ONLY verified door/window/glazing openings;
8) grow shorter interior partitions from the accepted wall core;
9) reconstruct canonical wall-mass polygons.

Public API:
    build_architectural_wall_graph(geometry, cad_meta=None)
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict, deque
from statistics import median


ENGINE = "CAD3D_ARCHITECTURAL_WALL_GRAPH_V2"


# =============================================================================
# Geometry utilities
# =============================================================================

def _finite(value, default=None):
    try:
        value = float(value)
    except Exception:
        return default
    return value if math.isfinite(value) else default


def _source_to_mm(cad_meta):
    if isinstance(cad_meta, dict):
        value = _finite(cad_meta.get("source_to_mm"), None)
        if value is not None and value > 0.0:
            return value
    return 1.0


def _entity_kind(item):
    return str(
        item.get(
            "type",
            item.get(
                "entity_type",
                item.get("kind", ""),
            ),
        )
        or ""
    ).upper()


def _entity_points(item):
    result = []

    for value in list(item.get("points", []) or []):
        if not isinstance(value, (list, tuple)) or len(value) < 2:
            continue

        x_value = _finite(value[0], None)
        y_value = _finite(value[1], None)

        if x_value is None or y_value is None:
            continue

        point = (x_value, y_value)

        if result and math.hypot(
            point[0] - result[-1][0],
            point[1] - result[-1][1],
        ) <= 1.0e-9:
            continue

        result.append(point)

    if len(result) >= 2 and math.hypot(
        result[0][0] - result[-1][0],
        result[0][1] - result[-1][1],
    ) <= 1.0e-9:
        result.pop()

    return result


def _angle_delta(a, b):
    value = abs(float(a) - float(b)) % math.pi
    return min(value, math.pi - value)


def _point_segment_distance(point, a, b):
    vx = b[0] - a[0]
    vy = b[1] - a[1]
    length2 = vx * vx + vy * vy

    if length2 <= 1.0e-12:
        return math.hypot(
            point[0] - a[0],
            point[1] - a[1],
        )

    t = (
        (point[0] - a[0]) * vx
        + (point[1] - a[1]) * vy
    ) / length2

    t = max(0.0, min(1.0, t))

    projection = (
        a[0] + t * vx,
        a[1] + t * vy,
    )

    return math.hypot(
        point[0] - projection[0],
        point[1] - projection[1],
    )


def _drawing_bounds(segments):
    xs = []
    ys = []

    for row in segments:
        xs.extend((row["a"][0], row["b"][0]))
        ys.extend((row["a"][1], row["b"][1]))

    if not xs or not ys:
        return None

    return (
        min(xs),
        min(ys),
        max(xs),
        max(ys),
    )


def _point_in_box(point, bounds, margin=0.0):
    x0, y0, x1, y1 = bounds

    return (
        point[0] >= x0 - margin
        and point[0] <= x1 + margin
        and point[1] >= y0 - margin
        and point[1] <= y1 + margin
    )


# =============================================================================
# Neutral source decomposition
# =============================================================================

def _extract_source_geometry(
    geometry,
    source_to_mm,
):
    straight_segments = []
    arc_like = []

    annotation_types = (
        "TEXT",
        "MTEXT",
        "DIMENSION",
        "LEADER",
        "MLEADER",
        "HATCH",
        "SOLID",
    )

    arc_types = (
        "ARC",
        "CIRCLE",
        "ELLIPSE",
    )

    for item_index, item in enumerate(geometry or []):
        if not isinstance(item, dict):
            continue

        kind = _entity_kind(item)
        points = _entity_points(item)

        if any(token in kind for token in annotation_types):
            continue

        if any(token in kind for token in arc_types):
            bounds = None

            if points:
                xs = [point[0] for point in points]
                ys = [point[1] for point in points]

                bounds = (
                    min(xs),
                    min(ys),
                    max(xs),
                    max(ys),
                )

            else:
                cx = _finite(item.get("center_x"), None)
                cy = _finite(item.get("center_y"), None)
                radius = _finite(
                    item.get(
                        "radius",
                        item.get("r"),
                    ),
                    None,
                )

                if (
                    cx is not None
                    and cy is not None
                    and radius is not None
                    and radius > 0.0
                ):
                    bounds = (
                        cx - radius,
                        cy - radius,
                        cx + radius,
                        cy + radius,
                    )

            arc_like.append(
                {
                    "item_index": int(item_index),
                    "kind": kind,
                    "layer": str(item.get("layer", "") or ""),
                    "points": points,
                    "bounds": bounds,
                }
            )

            continue

        # Curved splines are not straight wall faces.
        if "SPLINE" in kind:
            continue

        if len(points) < 2:
            continue

        point_pairs = list(
            zip(
                points,
                points[1:],
            )
        )

        if (
            bool(item.get("closed", False))
            and len(points) >= 3
        ):
            point_pairs.append(
                (
                    points[-1],
                    points[0],
                )
            )

        for segment_index, (a, b) in enumerate(
            point_pairs
        ):
            dx = b[0] - a[0]
            dy = b[1] - a[1]
            length_source = math.hypot(dx, dy)

            if length_source <= 1.0e-9:
                continue

            length_mm = length_source * source_to_mm

            # Numerical/micro-detail guard only.
            if length_mm < 45.0:
                continue

            ux = dx / length_source
            uy = dy / length_source

            straight_segments.append(
                {
                    "id": len(straight_segments),
                    "item_index": int(item_index),
                    "segment_index": int(segment_index),
                    "layer": str(item.get("layer", "") or ""),
                    "kind": kind,
                    "a": a,
                    "b": b,
                    "mx": (a[0] + b[0]) * 0.5,
                    "my": (a[1] + b[1]) * 0.5,
                    "ux": ux,
                    "uy": uy,
                    "angle": math.atan2(uy, ux) % math.pi,
                    "length_source": length_source,
                    "length_mm": length_mm,
                }
            )

    return straight_segments, arc_like


# =============================================================================
# WallBand candidate construction
# =============================================================================

def _orientation_buckets(
    segments,
    step=math.radians(5.0),
):
    count = max(
        1,
        int(round(math.pi / step)),
    )

    buckets = defaultdict(list)

    for row in segments:
        bucket = (
            int(
                round(
                    row["angle"] / step
                )
            )
            % count
        )

        buckets[bucket].append(row)

    return buckets, step, count


def _project_range(
    segment,
    ux,
    uy,
):
    return sorted(
        (
            segment["a"][0] * ux
            + segment["a"][1] * uy,
            segment["b"][0] * ux
            + segment["b"][1] * uy,
        )
    )


def _build_wall_band_candidates(
    segments,
    source_to_mm,
):
    """
    Local opposing-face candidates only.
    No candidate is a wall yet.
    """

    buckets, step, bucket_count = (
        _orientation_buckets(
            segments
        )
    )

    max_angle = math.radians(4.5)

    candidates = []
    seen = set()

    for bucket, rows in list(buckets.items()):
        nearby = []

        for offset in (-1, 0, 1):
            nearby.extend(
                buckets.get(
                    (bucket + offset)
                    % bucket_count,
                    [],
                )
            )

        for a in rows:
            for b in nearby:
                if b["id"] <= a["id"]:
                    continue

                key = (
                    int(a["id"]),
                    int(b["id"]),
                )

                if key in seen:
                    continue

                seen.add(key)

                if _angle_delta(
                    a["angle"],
                    b["angle"],
                ) > max_angle:
                    continue

                bux = b["ux"]
                buy = b["uy"]

                if (
                    a["ux"] * bux
                    + a["uy"] * buy
                ) < 0.0:
                    bux = -bux
                    buy = -buy

                mux = a["ux"] + bux
                muy = a["uy"] + buy
                magnitude = math.hypot(
                    mux,
                    muy,
                )

                if magnitude <= 1.0e-9:
                    continue

                ux = mux / magnitude
                uy = muy / magnitude
                nx = -uy
                ny = ux

                a_range = _project_range(
                    a,
                    ux,
                    uy,
                )
                b_range = _project_range(
                    b,
                    ux,
                    uy,
                )

                t0 = max(
                    a_range[0],
                    b_range[0],
                )
                t1 = min(
                    a_range[1],
                    b_range[1],
                )

                overlap_source = (
                    t1 - t0
                )

                if overlap_source <= 1.0e-9:
                    continue

                overlap_mm = (
                    overlap_source
                    * source_to_mm
                )

                a_offset = (
                    a["mx"] * nx
                    + a["my"] * ny
                )
                b_offset = (
                    b["mx"] * nx
                    + b["my"] * ny
                )

                gap_source = abs(
                    b_offset - a_offset
                )
                gap_mm = (
                    gap_source
                    * source_to_mm
                )

                # Broad architectural search range.
                if (
                    gap_mm < 45.0
                    or gap_mm > 900.0
                ):
                    continue

                if overlap_mm < max(
                    320.0,
                    gap_mm * 1.55,
                ):
                    continue

                overlap_ratio = (
                    overlap_mm
                    / max(
                        1.0e-9,
                        min(
                            a["length_mm"],
                            b["length_mm"],
                        ),
                    )
                )

                if overlap_ratio < 0.34:
                    continue

                candidates.append(
                    {
                        "id": len(candidates),
                        "a": a,
                        "b": b,
                        "ux": ux,
                        "uy": uy,
                        "nx": nx,
                        "ny": ny,
                        "a_offset": a_offset,
                        "b_offset": b_offset,
                        "gap_source": gap_source,
                        "gap_mm": gap_mm,
                        "t0": t0,
                        "t1": t1,
                        "overlap_source": overlap_source,
                        "overlap_mm": overlap_mm,
                        "overlap_ratio": overlap_ratio,
                        "aspect": (
                            overlap_mm
                            / max(
                                gap_mm,
                                1.0e-9,
                            )
                        ),
                    }
                )

    return candidates


# =============================================================================
# Negative object evidence: frame / stair / furniture rejection
# =============================================================================

def _corridor_evidence(
    pair,
    all_segments,
    source_to_mm,
):
    """
    Architectural wall bands are usually relatively clean between faces.

    Strong negative evidence:
    - nested long parallel segments inside the band;
    - repeated central perpendicular cross-lines;
    - high internal line density.

    This explicitly separates walls from window frames, mullions, cabinetry
    and stair tread/riser systems.
    """

    ux = pair["ux"]
    uy = pair["uy"]
    nx = pair["nx"]
    ny = pair["ny"]

    t0 = pair["t0"]
    t1 = pair["t1"]
    run_source = max(
        1.0e-9,
        t1 - t0,
    )

    offset0 = min(
        pair["a_offset"],
        pair["b_offset"],
    )
    offset1 = max(
        pair["a_offset"],
        pair["b_offset"],
    )

    face_ids = {
        int(pair["a"]["id"]),
        int(pair["b"]["id"]),
    }

    nested_parallel = 0
    central_cross = 0
    internal_count = 0
    nested_overlap_mm = 0.0

    for segment in all_segments:
        if int(segment["id"]) in face_ids:
            continue

        midpoint_t = (
            segment["mx"] * ux
            + segment["my"] * uy
        )

        if (
            midpoint_t
            < t0 - run_source * 0.08
            or midpoint_t
            > t1 + run_source * 0.08
        ):
            continue

        midpoint_offset = (
            segment["mx"] * nx
            + segment["my"] * ny
        )

        margin_source = max(
            pair["gap_source"] * 0.08,
            8.0 / source_to_mm,
        )

        if not (
            midpoint_offset
            > offset0 + margin_source
            and midpoint_offset
            < offset1 - margin_source
        ):
            continue

        internal_count += 1

        delta = _angle_delta(
            pair["a"]["angle"],
            segment["angle"],
        )

        if delta <= math.radians(6.0):
            other_range = _project_range(
                segment,
                ux,
                uy,
            )

            overlap = (
                min(
                    t1,
                    other_range[1],
                )
                - max(
                    t0,
                    other_range[0],
                )
            )

            if overlap <= 0.0:
                continue

            overlap_mm = (
                overlap
                * source_to_mm
            )

            if overlap_mm >= max(
                180.0,
                pair["overlap_mm"] * 0.22,
            ):
                nested_parallel += 1
                nested_overlap_mm += overlap_mm

        elif delta >= math.radians(55.0):
            central_t0 = (
                t0 + run_source * 0.18
            )
            central_t1 = (
                t1 - run_source * 0.18
            )

            if (
                midpoint_t >= central_t0
                and midpoint_t <= central_t1
                and segment["length_mm"]
                >= max(
                    110.0,
                    pair["gap_mm"] * 0.48,
                )
            ):
                central_cross += 1

    internal_density = (
        internal_count
        / max(
            1.0,
            pair["overlap_mm"]
            / 1000.0,
        )
    )

    purity = (
        1.0
        / (
            1.0
            + nested_parallel * 1.10
            + central_cross * 0.48
            + min(
                2.5,
                internal_density * 0.16,
            )
            + min(
                2.5,
                nested_overlap_mm
                / max(
                    pair["overlap_mm"],
                    1.0,
                )
                * 0.45,
            )
        )
    )

    pair["nested_parallel_count"] = (
        int(nested_parallel)
    )
    pair["central_cross_count"] = (
        int(central_cross)
    )
    pair["internal_line_count"] = (
        int(internal_count)
    )
    pair["internal_density"] = (
        float(internal_density)
    )
    pair["corridor_purity"] = (
        float(purity)
    )

    return purity


# =============================================================================
# Thickness families + local pair confidence
# =============================================================================

def _cluster_thickness_families(
    pairs,
):
    ordered = sorted(
        pairs,
        key=lambda row: row["gap_mm"],
    )

    families = []

    for pair in ordered:
        selected = None

        for family in families:
            center = float(
                median(
                    row["gap_mm"]
                    for row in family
                )
            )

            tolerance = max(
                14.0,
                center * 0.085,
            )

            if abs(
                pair["gap_mm"]
                - center
            ) <= tolerance:
                selected = family
                break

        if selected is None:
            families.append(
                [pair]
            )
        else:
            selected.append(
                pair
            )

    return families


def _score_thickness_families(
    families,
    drawing_bounds,
    source_to_mm,
):
    x0, y0, x1, y1 = (
        drawing_bounds
    )

    width = max(
        x1 - x0,
        1.0e-9,
    )
    height = max(
        y1 - y0,
        1.0e-9,
    )

    diagonal_mm = (
        math.hypot(
            width,
            height,
        )
        * source_to_mm
    )

    rows = []

    for family_index, family in enumerate(
        families
    ):
        orientations = set()
        spatial_bins = set()
        degree = Counter()
        weighted_run_mm = 0.0

        for pair in family:
            degree[
                int(pair["a"]["id"])
            ] += 1
            degree[
                int(pair["b"]["id"])
            ] += 1

            orientations.add(
                int(
                    round(
                        pair["a"]["angle"]
                        / math.radians(15.0)
                    )
                )
                % 12
            )

            cx = (
                pair["a"]["mx"]
                + pair["b"]["mx"]
            ) * 0.5
            cy = (
                pair["a"]["my"]
                + pair["b"]["my"]
            ) * 0.5

            gx = max(
                0,
                min(
                    3,
                    int(
                        4
                        * (cx - x0)
                        / width
                    ),
                ),
            )
            gy = max(
                0,
                min(
                    3,
                    int(
                        4
                        * (cy - y0)
                        / height
                    ),
                ),
            )

            spatial_bins.add(
                (gx, gy)
            )

            weighted_run_mm += (
                pair["overlap_mm"]
                * pair.get(
                    "corridor_purity",
                    1.0,
                )
            )

        degree_values = list(
            degree.values()
        )

        median_degree = (
            float(
                median(
                    degree_values
                )
            )
            if degree_values
            else 0.0
        )

        gap_mm = float(
            median(
                pair["gap_mm"]
                for pair in family
            )
        )

        support_ratio = (
            weighted_run_mm
            / max(
                diagonal_mm,
                1.0,
            )
        )

        spatial_coverage = (
            len(spatial_bins)
            / 16.0
        )

        # Wall thicknesses repeat across the architectural plan and across
        # multiple directions/locations. Furniture/frame spacing can repeat,
        # but is strongly weakened by purity and ambiguity.
        score = (
            2.20
            * min(
                1.0,
                support_ratio
                / 1.00,
            )
            + 1.55
            * min(
                1.0,
                len(orientations)
                / 2.0,
            )
            + 1.35
            * min(
                1.0,
                spatial_coverage
                / 0.32,
            )
            + 0.75
            * min(
                1.0,
                len(family)
                / 18.0,
            )
            - 1.00
            * min(
                1.0,
                max(
                    0.0,
                    median_degree - 2.0,
                )
                / 3.0,
            )
        )

        row = {
            "family_index":
                int(family_index),
            "gap_mm":
                gap_mm,
            "pair_count":
                len(family),
            "orientation_count":
                len(orientations),
            "spatial_coverage":
                spatial_coverage,
            "support_ratio":
                support_ratio,
            "median_pair_degree":
                median_degree,
            "score":
                score,
        }

        rows.append(
            row
        )

        for pair in family:
            pair[
                "family_index"
            ] = int(
                family_index
            )
            pair[
                "family_gap_mm"
            ] = gap_mm
            pair[
                "family_support_ratio"
            ] = support_ratio
            pair[
                "family_spatial_coverage"
            ] = spatial_coverage
            pair[
                "family_score"
            ] = score

    return rows


def _score_local_pairs(
    pairs,
    drawing_bounds,
    source_to_mm,
):
    x0, y0, x1, y1 = (
        drawing_bounds
    )

    drawing_diagonal_mm = (
        math.hypot(
            x1 - x0,
            y1 - y0,
        )
        * source_to_mm
    )

    degree = Counter()

    for pair in pairs:
        degree[
            (
                int(
                    pair[
                        "family_index"
                    ]
                ),
                int(
                    pair[
                        "a"
                    ][
                        "id"
                    ]
                ),
            )
        ] += 1

        degree[
            (
                int(
                    pair[
                        "family_index"
                    ]
                ),
                int(
                    pair[
                        "b"
                    ][
                        "id"
                    ]
                ),
            )
        ] += 1

    for pair in pairs:
        ambiguity = max(
            degree[
                (
                    int(
                        pair[
                            "family_index"
                        ]
                    ),
                    int(
                        pair[
                            "a"
                        ][
                            "id"
                        ]
                    ),
                )
            ],
            degree[
                (
                    int(
                        pair[
                            "family_index"
                        ]
                    ),
                    int(
                        pair[
                            "b"
                        ][
                            "id"
                        ]
                    ),
                )
            ],
        )

        thickness_ratio = (
            pair["gap_mm"]
            / max(
                drawing_diagonal_mm,
                1.0,
            )
        )

        # Large band thickness relative to the whole plan is more likely to be
        # furniture/frame spacing than an architectural wall.
        thickness_penalty = min(
            1.5,
            max(
                0.0,
                thickness_ratio - 0.025,
            )
            / 0.025,
        )

        local_score = (
            1.55
            * min(
                1.0,
                pair["overlap_ratio"],
            )
            + 1.45
            * min(
                1.0,
                pair["aspect"]
                / 5.0,
            )
            + 2.10
            * pair[
                "corridor_purity"
            ]
            + 0.80
            * min(
                1.0,
                pair[
                    "family_support_ratio"
                ]
                / 0.75,
            )
            + 0.45
            * min(
                1.0,
                pair[
                    "family_spatial_coverage"
                ]
                / 0.25,
            )
            - 0.60
            * max(
                0,
                ambiguity - 1,
            )
            - 0.70
            * thickness_penalty
        )

        pair[
            "ambiguity_degree"
        ] = int(
            ambiguity
        )
        pair[
            "thickness_ratio"
        ] = float(
            thickness_ratio
        )
        pair[
            "local_score"
        ] = float(
            local_score
        )


# =============================================================================
# Direct structural relations
# =============================================================================

def _centerline(
    pair,
):
    offset = (
        pair["a_offset"]
        + pair["b_offset"]
    ) * 0.5

    return (
        (
            pair["ux"] * pair["t0"]
            + pair["nx"] * offset,
            pair["uy"] * pair["t0"]
            + pair["ny"] * offset,
        ),
        (
            pair["ux"] * pair["t1"]
            + pair["nx"] * offset,
            pair["uy"] * pair["t1"]
            + pair["ny"] * offset,
        ),
    )


def _direct_relation(
    left,
    right,
    source_to_mm,
):
    """
    Architectural DIRECT-contact relation between two WallBand objects.

    V2 originally tested raw centerline endpoint proximity.  That is not
    geometrically correct for real wall junctions: at an L/T junction the
    centerline of one wall commonly terminates at the FACE of the other wall,
    so the two raw centerlines do not physically meet.

    This version evaluates the FINITE WALL BANDS themselves:

    - collinear continuation:
        same axis + same centerline + end gap no larger than the local
        wall-thickness contact envelope;

    - L/T junction:
        centerline intersection may lie inside a finite end-extension equal to
        roughly half the physical wall thickness.  This represents the actual
        band overlap at a corner/T junction.

    The extension is derived only from the two measured wall thicknesses.
    It is intentionally far smaller than a door/window opening, therefore this
    DIRECT relation cannot bridge architectural openings and cannot create a
    structural seed across empty space.
    """

    left_line = _centerline(
        left
    )
    right_line = _centerline(
        right
    )

    delta = _angle_delta(
        left["a"]["angle"],
        right["a"]["angle"],
    )

    left_half_source = (
        max(
            45.0,
            float(
                left[
                    "gap_mm"
                ]
            )
            * 0.56,
        )
        / source_to_mm
    )

    right_half_source = (
        max(
            45.0,
            float(
                right[
                    "gap_mm"
                ]
            )
            * 0.56,
        )
        / source_to_mm
    )

    def _line_unit(line):
        dx = (
            line[1][0]
            - line[0][0]
        )
        dy = (
            line[1][1]
            - line[0][1]
        )
        length = math.hypot(
            dx,
            dy,
        )

        if length <= 1.0e-9:
            return None

        return (
            dx / length,
            dy / length,
            length,
        )

    def _extended_line(
        line,
        extension,
    ):
        unit = _line_unit(
            line
        )

        if unit is None:
            return line

        ux, uy, _length = (
            unit
        )

        return (
            (
                line[0][0]
                - ux * extension,
                line[0][1]
                - uy * extension,
            ),
            (
                line[1][0]
                + ux * extension,
                line[1][1]
                + uy * extension,
            ),
        )

    def _segment_intersection(
        a0,
        a1,
        b0,
        b1,
    ):
        ax = (
            a1[0]
            - a0[0]
        )
        ay = (
            a1[1]
            - a0[1]
        )
        bx = (
            b1[0]
            - b0[0]
        )
        by = (
            b1[1]
            - b0[1]
        )

        denominator = (
            ax * by
            - ay * bx
        )

        if abs(
            denominator
        ) <= 1.0e-12:
            return None

        qx = (
            b0[0]
            - a0[0]
        )
        qy = (
            b0[1]
            - a0[1]
        )

        ta = (
            qx * by
            - qy * bx
        ) / denominator

        tb = (
            qx * ay
            - qy * ax
        ) / denominator

        tolerance = 1.0e-7

        if (
            ta
            < -tolerance
            or ta
            > 1.0 + tolerance
            or tb
            < -tolerance
            or tb
            > 1.0 + tolerance
        ):
            return None

        return (
            a0[0]
            + ta * ax,
            a0[1]
            + ta * ay,
        )

    # ------------------------------------------------------------------
    # Same-axis finite wall continuation.
    # ------------------------------------------------------------------
    if delta <= math.radians(
        7.0
    ):
        left_unit = _line_unit(
            left_line
        )

        if left_unit is None:
            return None

        ux, uy, _length = (
            left_unit
        )
        nx = -uy
        ny = ux

        left_offset = (
            left_line[0][0]
            * nx
            + left_line[0][1]
            * ny
        )
        right_offset = (
            right_line[0][0]
            * nx
            + right_line[0][1]
            * ny
        )

        lateral_mm = (
            abs(
                left_offset
                - right_offset
            )
            * source_to_mm
        )

        lateral_tolerance_mm = max(
            35.0,
            min(
                float(
                    left[
                        "gap_mm"
                    ]
                ),
                float(
                    right[
                        "gap_mm"
                    ]
                ),
            )
            * 0.28,
        )

        if (
            lateral_mm
            > lateral_tolerance_mm
        ):
            return None

        left_range = sorted(
            (
                left_line[0][0]
                * ux
                + left_line[0][1]
                * uy,
                left_line[1][0]
                * ux
                + left_line[1][1]
                * uy,
            )
        )

        right_range = sorted(
            (
                right_line[0][0]
                * ux
                + right_line[0][1]
                * uy,
                right_line[1][0]
                * ux
                + right_line[1][1]
                * uy,
            )
        )

        if (
            left_range[1]
            >= right_range[0]
            and right_range[1]
            >= left_range[0]
        ):
            axial_gap_source = 0.0

        else:
            axial_gap_source = min(
                abs(
                    left_range[1]
                    - right_range[0]
                ),
                abs(
                    right_range[1]
                    - left_range[0]
                ),
            )

        contact_limit_source = max(
            left_half_source,
            right_half_source,
        )

        if (
            axial_gap_source
            <= contact_limit_source
        ):
            return "collinear_end"

        return None

    # Nearly-parallel but non-collinear systems are not a junction.
    if delta < math.radians(
        18.0
    ):
        return None

    # ------------------------------------------------------------------
    # L/T/X physical band contact.
    #
    # Extend each CENTERLINE only by roughly half its own measured wall
    # thickness.  If the extended finite runs intersect, the actual wall
    # BANDS physically meet.
    # ------------------------------------------------------------------
    left_extended = (
        _extended_line(
            left_line,
            left_half_source,
        )
    )

    right_extended = (
        _extended_line(
            right_line,
            right_half_source,
        )
    )

    intersection = (
        _segment_intersection(
            left_extended[0],
            left_extended[1],
            right_extended[0],
            right_extended[1],
        )
    )

    if intersection is not None:
        return "branch_end"

    # CAD fragmentation can leave the intersection a few millimetres outside
    # the finite segment.  Allow only a very small drafting tolerance, never an
    # opening-sized jump.
    drafting_tolerance_source = (
        max(
            20.0,
            min(
                70.0,
                min(
                    float(
                        left[
                            "gap_mm"
                        ]
                    ),
                    float(
                        right[
                            "gap_mm"
                        ]
                    ),
                )
                * 0.20,
            ),
        )
        / source_to_mm
    )

    minimum_distance = min(
        _point_segment_distance(
            point,
            right_extended[0],
            right_extended[1],
        )
        for point
        in left_extended
    )

    minimum_distance = min(
        minimum_distance,
        min(
            _point_segment_distance(
                point,
                left_extended[0],
                left_extended[1],
            )
            for point
            in right_extended
        ),
    )

    if (
        minimum_distance
        <= drafting_tolerance_source
    ):
        return "branch_end"

    return None



def _build_direct_graph(
    pairs,
    source_to_mm,
):
    adjacency = defaultdict(set)
    relations = {}

    for pair in pairs:
        adjacency[
            pair["id"]
        ]

    # Spatially simple O(n^2) relation stage; candidate count is already
    # strongly reduced by wall-object evidence.
    for index, left in enumerate(pairs):
        left_line = _centerline(
            left
        )
        left_mid = (
            (
                left_line[0][0]
                + left_line[1][0]
            )
            * 0.5,
            (
                left_line[0][1]
                + left_line[1][1]
            )
            * 0.5,
        )

        for right in pairs[
            index + 1:
        ]:
            right_line = _centerline(
                right
            )
            right_mid = (
                (
                    right_line[0][0]
                    + right_line[1][0]
                )
                * 0.5,
                (
                    right_line[0][1]
                    + right_line[1][1]
                )
                * 0.5,
            )

            search_mm = (
                (
                    left["overlap_mm"]
                    + right["overlap_mm"]
                )
                * 0.55
                + 1100.0
            )

            if (
                math.hypot(
                    left_mid[0] - right_mid[0],
                    left_mid[1] - right_mid[1],
                )
                * source_to_mm
                > search_mm
            ):
                continue

            relation = _direct_relation(
                left,
                right,
                source_to_mm,
            )

            if relation is None:
                relation = _direct_relation(
                    right,
                    left,
                    source_to_mm,
                )

            if relation is None:
                continue

            adjacency[
                left["id"]
            ].add(
                right["id"]
            )
            adjacency[
                right["id"]
            ].add(
                left["id"]
            )

            relations[
                (
                    min(
                        left["id"],
                        right["id"],
                    ),
                    max(
                        left["id"],
                        right["id"],
                    ),
                )
            ] = relation

    return adjacency, relations


# =============================================================================
# Structural-core election
# =============================================================================

def _connected_components(
    pairs,
    adjacency,
):
    by_id = {
        pair["id"]:
            pair
        for pair in pairs
    }

    visited = set()
    components = []

    for pair in pairs:
        root = (
            pair["id"]
        )

        if root in visited:
            continue

        queue = deque(
            [root]
        )
        visited.add(
            root
        )

        ids = []

        while queue:
            current = (
                queue.popleft()
            )
            ids.append(
                current
            )

            for neighbor in adjacency.get(
                current,
                (),
            ):
                if neighbor in visited:
                    continue

                visited.add(
                    neighbor
                )
                queue.append(
                    neighbor
                )

        components.append(
            [
                by_id[
                    pair_id
                ]
                for pair_id
                in ids
            ]
        )

    return components


def _component_metrics(
    component,
    adjacency,
    drawing_bounds,
    source_to_mm,
):
    x0, y0, x1, y1 = (
        drawing_bounds
    )

    width = max(
        x1 - x0,
        1.0e-9,
    )
    height = max(
        y1 - y0,
        1.0e-9,
    )

    diagonal_mm = (
        math.hypot(
            width,
            height,
        )
        * source_to_mm
    )

    ids = {
        pair["id"]
        for pair in component
    }

    points = []
    orientations = set()
    weighted_run_mm = 0.0

    for pair in component:
        line = _centerline(
            pair
        )
        points.extend(
            line
        )

        orientations.add(
            int(
                round(
                    pair[
                        "a"
                    ][
                        "angle"
                    ]
                    / math.radians(15.0)
                )
            )
            % 12
        )

        weighted_run_mm += (
            pair["overlap_mm"]
            * pair[
                "corridor_purity"
            ]
        )

    xs = [
        point[0]
        for point in points
    ]
    ys = [
        point[1]
        for point in points
    ]

    x_span_ratio = (
        (
            max(xs)
            - min(xs)
        )
        / width
    )
    y_span_ratio = (
        (
            max(ys)
            - min(ys)
        )
        / height
    )

    degrees = [
        len(
            [
                neighbor
                for neighbor in adjacency.get(
                    pair["id"],
                    (),
                )
                if neighbor in ids
            ]
        )
        for pair in component
    ]

    connected_ratio = (
        sum(
            1
            for value in degrees
            if value > 0
        )
        / max(
            1,
            len(degrees),
        )
    )

    branching_ratio = (
        sum(
            1
            for value in degrees
            if value >= 2
        )
        / max(
            1,
            len(degrees),
        )
    )

    mean_purity = (
        sum(
            pair[
                "corridor_purity"
            ]
            for pair in component
        )
        / max(
            1,
            len(component),
        )
    )

    mean_local_score = (
        sum(
            pair[
                "local_score"
            ]
            for pair in component
        )
        / max(
            1,
            len(component),
        )
    )

    total_run_ratio = (
        weighted_run_mm
        / max(
            diagonal_mm,
            1.0,
        )
    )

    score = (
        2.50
        * min(
            1.0,
            max(
                x_span_ratio,
                y_span_ratio,
            )
            / 0.46,
        )
        + 1.55
        * min(
            1.0,
            min(
                x_span_ratio,
                y_span_ratio,
            )
            / 0.20,
        )
        + 1.60
        * min(
            1.0,
            connected_ratio
            / 0.70,
        )
        + 1.20
        * min(
            1.0,
            branching_ratio
            / 0.25,
        )
        + 1.35
        * min(
            1.0,
            len(
                orientations
            )
            / 2.0,
        )
        + 1.60
        * min(
            1.0,
            total_run_ratio
            / 0.95,
        )
        + 1.65
        * mean_purity
        + 0.55
        * min(
            1.0,
            mean_local_score
            / 4.0,
        )
    )

    return {
        "pair_count":
            len(component),
        "x_span_ratio":
            x_span_ratio,
        "y_span_ratio":
            y_span_ratio,
        "max_axis_span_ratio":
            max(
                x_span_ratio,
                y_span_ratio,
            ),
        "min_axis_span_ratio":
            min(
                x_span_ratio,
                y_span_ratio,
            ),
        "orientation_count":
            len(
                orientations
            ),
        "connected_ratio":
            connected_ratio,
        "branching_ratio":
            branching_ratio,
        "mean_purity":
            mean_purity,
        "mean_local_score":
            mean_local_score,
        "total_run_ratio":
            total_run_ratio,
        "score":
            score,
    }


def _select_structural_core(
    pairs,
    adjacency,
    drawing_bounds,
    source_to_mm,
):
    rows = []

    for component_index, component in enumerate(
        _connected_components(
            pairs,
            adjacency,
        )
    ):
        metrics = _component_metrics(
            component,
            adjacency,
            drawing_bounds,
            source_to_mm,
        )

        seed = (
            metrics[
                "pair_count"
            ]
            >= 3
            and metrics[
                "mean_purity"
            ]
            >= 0.58
            and metrics[
                "mean_local_score"
            ]
            >= 2.65
            and metrics[
                "connected_ratio"
            ]
            >= 0.45
            and metrics[
                "total_run_ratio"
            ]
            >= 0.16
            and (
                metrics[
                    "max_axis_span_ratio"
                ]
                >= 0.34
                or (
                    metrics[
                        "x_span_ratio"
                    ]
                    >= 0.18
                    and metrics[
                        "y_span_ratio"
                    ]
                    >= 0.18
                )
            )
            and (
                metrics[
                    "orientation_count"
                ]
                >= 2
                or metrics[
                    "max_axis_span_ratio"
                ]
                >= 0.52
            )
        )

        rows.append(
            {
                "component_index":
                    int(
                        component_index
                    ),
                "component":
                    component,
                "metrics":
                    metrics,
                "seed":
                    bool(seed),
            }
        )

    seeds = [
        row
        for row in rows
        if row[
            "seed"
        ]
    ]

    if not seeds:
        return [], rows

    seeds.sort(
        key=lambda row: (
            row[
                "metrics"
            ][
                "score"
            ],
            row[
                "metrics"
            ][
                "total_run_ratio"
            ],
        ),
        reverse=True,
    )

    top_score = (
        seeds[0][
            "metrics"
        ][
            "score"
        ]
    )

    accepted = [
        row
        for row in seeds
        if row[
            "metrics"
        ][
            "score"
        ]
        >= top_score
        - 1.45
    ]

    return (
        accepted,
        rows,
    )


# =============================================================================
# Opening evidence
# =============================================================================

def _opening_bounds(
    left,
    right,
    source_to_mm,
):
    left_line = _centerline(
        left
    )
    right_line = _centerline(
        right
    )

    rows = []

    for lp in left_line:
        for rp in right_line:
            rows.append(
                (
                    math.hypot(
                        lp[0] - rp[0],
                        lp[1] - rp[1],
                    ),
                    lp,
                    rp,
                )
            )

    rows.sort(
        key=lambda row: row[0]
    )

    if not rows:
        return None

    _distance, p0, p1 = (
        rows[0]
    )

    half_width_source = (
        max(
            left["gap_mm"],
            right["gap_mm"],
        )
        * 0.85
        / source_to_mm
    )

    return (
        min(
            p0[0],
            p1[0],
        )
        - half_width_source,
        min(
            p0[1],
            p1[1],
        )
        - half_width_source,
        max(
            p0[0],
            p1[0],
        )
        + half_width_source,
        max(
            p0[1],
            p1[1],
        )
        + half_width_source,
    )


def _opening_geometry_evidence(
    left,
    right,
    straight_segments,
    arc_like,
    source_to_mm,
):
    bounds = _opening_bounds(
        left,
        right,
        source_to_mm,
    )

    if bounds is None:
        return {
            "supported":
                False,
            "kind":
                "unknown",
        }

    wall_angle = (
        left["a"]["angle"]
    )

    margin = (
        max(
            left["gap_mm"],
            right["gap_mm"],
        )
        * 0.30
        / source_to_mm
    )

    door_score = 0
    frame_parallel = 0
    frame_cross = 0

    for arc in arc_like:
        arc_bounds = (
            arc.get(
                "bounds"
            )
        )

        if not (
            isinstance(
                arc_bounds,
                (list, tuple),
            )
            and len(
                arc_bounds
            )
            == 4
        ):
            continue

        ax0, ay0, ax1, ay1 = (
            arc_bounds
        )
        bx0, by0, bx1, by1 = (
            bounds
        )

        if not (
            ax1 < bx0
            or ax0 > bx1
            or ay1 < by0
            or ay0 > by1
        ):
            door_score += 3

    for segment in straight_segments:
        midpoint = (
            segment["mx"],
            segment["my"],
        )

        if not _point_in_box(
            midpoint,
            bounds,
            margin,
        ):
            continue

        delta = _angle_delta(
            wall_angle,
            segment["angle"],
        )

        if (
            delta
            <= math.radians(8.0)
            and segment[
                "length_mm"
            ]
            <= 2400.0
        ):
            frame_parallel += 1

        elif (
            delta
            >= math.radians(65.0)
            and segment[
                "length_mm"
            ]
            <= 1400.0
        ):
            frame_cross += 1

    window_score = (
        frame_parallel
        + frame_cross
        + (
            2
            if (
                frame_parallel
                >= 2
                and frame_cross
                >= 2
            )
            else 0
        )
    )

    if door_score >= 3:
        return {
            "supported":
                True,
            "kind":
                "door_like",
            "door_score":
                int(
                    door_score
                ),
            "window_score":
                int(
                    window_score
                ),
            "bounds":
                bounds,
        }

    if (
        frame_parallel >= 2
        and frame_cross >= 2
        and window_score >= 6
    ):
        return {
            "supported":
                True,
            "kind":
                "window_or_glazing_like",
            "door_score":
                int(
                    door_score
                ),
            "window_score":
                int(
                    window_score
                ),
            "bounds":
                bounds,
        }

    return {
        "supported":
            False,
        "kind":
            "unverified_gap",
        "door_score":
            int(
                door_score
            ),
        "window_score":
            int(
                window_score
            ),
        "bounds":
            bounds,
    }


def _opening_continuation_relation(
    candidate,
    structural,
    straight_segments,
    arc_like,
    source_to_mm,
):
    """
    Opening continuation is NEVER used to elect the structural seed.

    It is only allowed AFTER structural walls are known.
    """

    if _angle_delta(
        candidate["a"]["angle"],
        structural["a"]["angle"],
    ) > math.radians(7.0):
        return None

    candidate_line = _centerline(
        candidate
    )
    structural_line = _centerline(
        structural
    )

    # Centerlines must be genuinely aligned.
    sux = (
        structural_line[1][0]
        - structural_line[0][0]
    )
    suy = (
        structural_line[1][1]
        - structural_line[0][1]
    )
    slength = math.hypot(
        sux,
        suy,
    )

    if slength <= 1.0e-9:
        return None

    sux /= slength
    suy /= slength

    snx = -suy
    sny = sux

    candidate_mid = (
        (
            candidate_line[0][0]
            + candidate_line[1][0]
        )
        * 0.5,
        (
            candidate_line[0][1]
            + candidate_line[1][1]
        )
        * 0.5,
    )

    structural_offset = (
        structural_line[0][0]
        * snx
        + structural_line[0][1]
        * sny
    )
    candidate_offset = (
        candidate_mid[0]
        * snx
        + candidate_mid[1]
        * sny
    )

    lateral_mm = (
        abs(
            candidate_offset
            - structural_offset
        )
        * source_to_mm
    )

    thickness_mm = max(
        candidate[
            "gap_mm"
        ],
        structural[
            "gap_mm"
        ],
    )

    if lateral_mm > max(
        35.0,
        thickness_mm * 0.34,
    ):
        return None

    endpoint_rows = []

    for cp in candidate_line:
        for sp in structural_line:
            endpoint_rows.append(
                (
                    math.hypot(
                        cp[0] - sp[0],
                        cp[1] - sp[1],
                    ),
                    cp,
                    sp,
                )
            )

    endpoint_rows.sort(
        key=lambda row: row[0]
    )

    if not endpoint_rows:
        return None

    opening_mm = (
        endpoint_rows[0][0]
        * source_to_mm
    )

    if not (
        opening_mm
        >= max(
            420.0,
            thickness_mm
            * 1.55,
        )
        and opening_mm
        <= max(
            2200.0,
            thickness_mm
            * 9.0,
        )
    ):
        return None

    evidence = (
        _opening_geometry_evidence(
            candidate,
            structural,
            straight_segments,
            arc_like,
            source_to_mm,
        )
    )

    if not evidence.get(
        "supported",
        False,
    ):
        return None

    return {
        "kind":
            "opening_continuation",
        "point":
            endpoint_rows[
                0
            ][
                1
            ],
        "span_mm":
            float(
                opening_mm
            ),
        "opening":
            evidence,
    }


# =============================================================================
# Partition growth
# =============================================================================

def _same_thickness_family(
    pair,
    accepted_family_gaps,
):
    return any(
        abs(
            pair[
                "family_gap_mm"
            ]
            - gap
        )
        <= max(
            20.0,
            max(
                pair[
                    "family_gap_mm"
                ],
                gap,
            )
            * 0.20,
        )
        for gap
        in accepted_family_gaps
    )


def _grow_structural_graph(
    graph_pairs,
    seed_rows,
    straight_segments,
    arc_like,
    source_to_mm,
):
    accepted = {}

    for row in seed_rows:
        for pair in row[
            "component"
        ]:
            accepted[
                pair["id"]
            ] = pair

    if not accepted:
        return [], 0, []

    accepted_family_gaps = []

    for pair in accepted.values():
        gap = float(
            pair[
                "family_gap_mm"
            ]
        )

        if not any(
            abs(
                gap - existing
            )
            <= max(
                14.0,
                existing * 0.10,
            )
            for existing
            in accepted_family_gaps
        ):
            accepted_family_gaps.append(
                gap
            )

    promoted_count = 0
    openings = []
    changed = True

    while changed:
        changed = False

        for pair in graph_pairs:
            if pair[
                "id"
            ] in accepted:
                continue

            # Strong local wall object.
            if (
                pair[
                    "corridor_purity"
                ]
                < 0.58
                or pair[
                    "local_score"
                ]
                < 2.70
                or pair[
                    "aspect"
                ]
                < 2.15
                or pair[
                    "overlap_mm"
                ]
                < max(
                    700.0,
                    pair[
                        "gap_mm"
                    ]
                    * 3.25,
                )
            ):
                continue

            direct_relations = []
            opening_relations = []

            for structural in accepted.values():
                direct = _direct_relation(
                    pair,
                    structural,
                    source_to_mm,
                )

                if direct is not None:
                    direct_relations.append(
                        (
                            direct,
                            structural,
                        )
                    )

                    continue

                opening = (
                    _opening_continuation_relation(
                        pair,
                        structural,
                        straight_segments,
                        arc_like,
                        source_to_mm,
                    )
                )

                if opening is not None:
                    opening_relations.append(
                        (
                            opening,
                            structural,
                        )
                    )

            if not (
                direct_relations
                or opening_relations
            ):
                continue

            same_family = (
                _same_thickness_family(
                    pair,
                    accepted_family_gaps,
                )
            )

            direct_branch_count = sum(
                1
                for relation, _structural
                in direct_relations
                if relation
                == "branch_end"
            )

            direct_any_count = (
                len(
                    direct_relations
                )
            )

            promote = False

            if same_family:
                promote = (
                    direct_any_count >= 1
                    or len(
                        opening_relations
                    )
                    >= 1
                )

            else:
                # New interior thickness:
                # must physically branch into the existing wall graph and must
                # have family support elsewhere in the plan.
                globally_supported = (
                    pair[
                        "family_support_ratio"
                    ]
                    >= 0.18
                    or pair[
                        "family_spatial_coverage"
                    ]
                    >= 0.125
                )

                promote = (
                    direct_branch_count
                    >= 1
                    and globally_supported
                    and pair[
                        "overlap_mm"
                    ]
                    >= max(
                        900.0,
                        pair[
                            "gap_mm"
                        ]
                        * 3.75,
                    )
                )

            if not promote:
                continue

            accepted[
                pair[
                    "id"
                ]
            ] = pair

            promoted_count += 1

            for relation, structural in opening_relations:
                openings.append(
                    {
                        "candidate_pair_id":
                            int(
                                pair[
                                    "id"
                                ]
                            ),
                        "structural_pair_id":
                            int(
                                structural[
                                    "id"
                                ]
                            ),
                        "span_mm":
                            float(
                                relation[
                                    "span_mm"
                                ]
                            ),
                        **dict(
                            relation[
                                "opening"
                            ]
                        ),
                    }
                )

            gap = float(
                pair[
                    "family_gap_mm"
                ]
            )

            if not any(
                abs(
                    gap
                    - existing
                )
                <= max(
                    14.0,
                    existing
                    * 0.10,
                )
                for existing
                in accepted_family_gaps
            ):
                accepted_family_gaps.append(
                    gap
                )

            changed = True

    return (
        list(
            accepted.values()
        ),
        promoted_count,
        openings,
    )


# =============================================================================
# Wall mass reconstruction
# =============================================================================

def _wall_band_polygon(
    pair,
    source_to_mm,
):
    # Small geometric closure for corners/Ts only.
    # Never large enough to bridge a real door/window opening.
    extension = (
        pair[
            "gap_mm"
        ]
        * 0.44
        / source_to_mm
    )

    t0 = (
        pair["t0"]
        - extension
    )
    t1 = (
        pair["t1"]
        + extension
    )

    return [
        (
            pair["ux"] * t0
            + pair["nx"]
            * pair[
                "a_offset"
            ],
            pair["uy"] * t0
            + pair["ny"]
            * pair[
                "a_offset"
            ],
        ),
        (
            pair["ux"] * t1
            + pair["nx"]
            * pair[
                "a_offset"
            ],
            pair["uy"] * t1
            + pair["ny"]
            * pair[
                "a_offset"
            ],
        ),
        (
            pair["ux"] * t1
            + pair["nx"]
            * pair[
                "b_offset"
            ],
            pair["uy"] * t1
            + pair["ny"]
            * pair[
                "b_offset"
            ],
        ),
        (
            pair["ux"] * t0
            + pair["nx"]
            * pair[
                "b_offset"
            ],
            pair["uy"] * t0
            + pair["ny"]
            * pair[
                "b_offset"
            ],
        ),
    ]


def _union_wall_mass(
    pairs,
    source_to_mm,
):
    from PySide6.QtCore import (
        QPointF,
        Qt,
    )
    from PySide6.QtGui import (
        QPainterPath,
        QPolygonF,
    )

    wall_path = QPainterPath()
    wall_path.setFillRule(
        Qt.FillRule.WindingFill
    )

    for pair in pairs:
        polygon = (
            _wall_band_polygon(
                pair,
                source_to_mm,
            )
        )

        path = QPainterPath()

        path.addPolygon(
            QPolygonF(
                [
                    QPointF(
                        float(
                            point[0]
                        ),
                        float(
                            point[1]
                        ),
                    )
                    for point
                    in polygon
                ]
            )
        )

        path.closeSubpath()

        wall_path = (
            wall_path.united(
                path
            )
        )

    wall_path = (
        wall_path.simplified()
    )

    polygons = []

    for polygon in wall_path.toSubpathPolygons():
        ring = []

        for index in range(
            polygon.count()
        ):
            point = (
                float(
                    polygon[
                        index
                    ].x()
                ),
                float(
                    polygon[
                        index
                    ].y()
                ),
            )

            if ring and math.hypot(
                point[0]
                - ring[-1][0],
                point[1]
                - ring[-1][1],
            ) <= 1.0e-9:
                continue

            ring.append(
                point
            )

        if (
            len(ring) >= 2
            and math.hypot(
                ring[0][0]
                - ring[-1][0],
                ring[0][1]
                - ring[-1][1],
            )
            <= 1.0e-9
        ):
            ring.pop()

        if len(ring) >= 3:
            polygons.append(
                ring
            )

    return polygons


# =============================================================================
# Public API
# =============================================================================

def build_architectural_wall_graph(
    geometry,
    cad_meta=None,
):
    geometry = [
        item
        for item in list(
            geometry
            or []
        )
        if isinstance(
            item,
            dict,
        )
    ]

    if not geometry:
        raise RuntimeError(
            "Architectural Wall Graph V2: CAD geometry is empty."
        )

    source_to_mm = (
        _source_to_mm(
            cad_meta
        )
    )

    (
        straight_segments,
        arc_like,
    ) = _extract_source_geometry(
        geometry,
        source_to_mm,
    )

    if len(
        straight_segments
    ) < 4:
        raise RuntimeError(
            "Architectural Wall Graph V2: insufficient straight geometry."
        )

    drawing_bounds = (
        _drawing_bounds(
            straight_segments
        )
    )

    candidates = (
        _build_wall_band_candidates(
            straight_segments,
            source_to_mm,
        )
    )

    if not candidates:
        raise RuntimeError(
            "Architectural Wall Graph V2: no opposing-face candidates."
        )

    for pair in candidates:
        _corridor_evidence(
            pair,
            straight_segments,
            source_to_mm,
        )

    # Weak frame/stair/furniture-like bands never enter the graph.
    family_input = [
        pair
        for pair in candidates
        if (
            pair[
                "corridor_purity"
            ]
            >= 0.38
            and pair[
                "aspect"
            ]
            >= 1.75
        )
    ]

    if not family_input:
        raise RuntimeError(
            "Architectural Wall Graph V2: all candidates failed object evidence."
        )

    families = (
        _cluster_thickness_families(
            family_input
        )
    )

    family_audit = (
        _score_thickness_families(
            families,
            drawing_bounds,
            source_to_mm,
        )
    )

    _score_local_pairs(
        family_input,
        drawing_bounds,
        source_to_mm,
    )

    # Strong wall-object pairs only.
    graph_pairs = [
        pair
        for pair in family_input
        if (
            pair[
                "corridor_purity"
            ]
            >= 0.52
            and pair[
                "local_score"
            ]
            >= 2.50
            and pair[
                "aspect"
            ]
            >= 2.00
        )
    ]

    if not graph_pairs:
        raise RuntimeError(
            "Architectural Wall Graph V2: no strong wall objects."
        )

    # CRITICAL: seed graph uses DIRECT contacts only.
    direct_adjacency, direct_relations = (
        _build_direct_graph(
            graph_pairs,
            source_to_mm,
        )
    )

    seed_rows, component_rows = (
        _select_structural_core(
            graph_pairs,
            direct_adjacency,
            drawing_bounds,
            source_to_mm,
        )
    )

    if not seed_rows:
        raise RuntimeError(
            "Architectural Wall Graph V2: no structural wall core."
        )

    (
        accepted_pairs,
        promoted_count,
        openings,
    ) = _grow_structural_graph(
        graph_pairs,
        seed_rows,
        straight_segments,
        arc_like,
        source_to_mm,
    )

    if not accepted_pairs:
        raise RuntimeError(
            "Architectural Wall Graph V2: accepted wall graph is empty."
        )

    wall_polygons = (
        _union_wall_mass(
            accepted_pairs,
            source_to_mm,
        )
    )

    if not wall_polygons:
        raise RuntimeError(
            "Architectural Wall Graph V2: wall graph produced no wall mass."
        )

    layer_weight = Counter()
    source_item_indexes = set()

    for pair in accepted_pairs:
        for segment in (
            pair["a"],
            pair["b"],
        ):
            source_item_indexes.add(
                int(
                    segment[
                        "item_index"
                    ]
                )
            )

            layer = str(
                segment.get(
                    "layer",
                    "",
                )
                or ""
            )

            if layer:
                layer_weight[
                    layer
                ] += segment[
                    "length_mm"
                ]

    provenance_layers = [
        layer
        for layer, _weight
        in layer_weight.most_common()
    ]

    compatibility_primary_layer = (
        provenance_layers[0]
        if provenance_layers
        else None
    )

    selected_family_gaps = sorted(
        {
            round(
                float(
                    pair[
                        "family_gap_mm"
                    ]
                ),
                4,
            )
            for pair
            in accepted_pairs
        }
    )

    closed_wall_paths = [
        (
            True,
            [
                [
                    float(
                        point[0]
                    ),
                    float(
                        point[1]
                    ),
                ]
                for point
                in polygon
            ],
        )
        for polygon
        in wall_polygons
    ]

    wall_source_geometry = [
        {
            "type":
                "LWPOLYLINE",
            "entity_type":
                "LWPOLYLINE",
            "kind":
                "LWPOLYLINE",
            "layer":
                "CAD3D_WALL_GEOMETRY",
            "closed":
                True,
            "points":
                [
                    [
                        float(
                            point[0]
                        ),
                        float(
                            point[1]
                        ),
                    ]
                    for point
                    in polygon
                ],
        }
        for polygon
        in wall_polygons
    ]

    component_audit = [
        {
            "component_index":
                int(
                    row[
                        "component_index"
                    ]
                ),
            "seed":
                bool(
                    row[
                        "seed"
                    ]
                ),
            **dict(
                row[
                    "metrics"
                ]
            ),
        }
        for row
        in component_rows
    ]

    result = {
        "engine":
            ENGINE,
        "authority":
            "WALL_OBJECT_OPENING_JUNCTION_GRAPH_V2",
        "layer_name_decision_weight":
            0.0,
        "layer_group_decision_weight":
            0.0,
        "source_to_mm":
            float(
                source_to_mm
            ),
        "source_segment_count":
            len(
                straight_segments
            ),
        "candidate_pair_count":
            len(
                candidates
            ),
        "strong_pair_count":
            len(
                graph_pairs
            ),
        "gap_family_count":
            len(
                families
            ),
        "direct_relation_count":
            len(
                direct_relations
            ),
        "structural_component_count":
            len(
                seed_rows
            ),
        "promoted_partition_pair_count":
            int(
                promoted_count
            ),
        "selected_pair_count":
            len(
                accepted_pairs
            ),
        "selected_family_gaps_mm":
            selected_family_gaps,
        "opening_count":
            len(
                openings
            ),
        "openings":
            openings,
        "closed_wall_count":
            len(
                closed_wall_paths
            ),
        "closed_wall_paths":
            closed_wall_paths,
        "wall_source_geometry":
            wall_source_geometry,
        "source_item_indexes":
            sorted(
                source_item_indexes
            ),
        "contributing_layers_provenance":
            provenance_layers,
        "compatibility_primary_layer":
            compatibility_primary_layer,
        "family_audit":
            family_audit,
        "component_audit":
            component_audit,
    }

    print(
        "ARCHITECTURAL WALL GRAPH V2",
        "| SEGMENTS:",
        result[
            "source_segment_count"
        ],
        "| CANDIDATES:",
        result[
            "candidate_pair_count"
        ],
        "| STRONG:",
        result[
            "strong_pair_count"
        ],
        "| FAMILIES:",
        result[
            "gap_family_count"
        ],
        "| DIRECT REL:",
        result[
            "direct_relation_count"
        ],
        "| CORE:",
        result[
            "structural_component_count"
        ],
        "| PROMOTED:",
        result[
            "promoted_partition_pair_count"
        ],
        "| OPENINGS:",
        result[
            "opening_count"
        ],
        "| ACCEPTED:",
        result[
            "selected_pair_count"
        ],
        "| THICKNESS MM:",
        [
            round(
                value,
                2,
            )
            for value
            in result[
                "selected_family_gaps_mm"
            ]
        ],
        "| CLOSED:",
        result[
            "closed_wall_count"
        ],
        "| LAYER-NAME WEIGHT: 0",
        "| LAYER-GROUP WEIGHT: 0",
    )

    return result
