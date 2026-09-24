from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from pathlib import Path
import json
import math


ENGINE = "CAD3D_FACADE_WINDOW_BUTTON_OUTER_FRAME_V6"

WIDTH_GATE = 0.18
POSITION_GATE = 0.20

PLAN_CONTEXT_X_RATIO = 0.060
PLAN_CONTEXT_Y_RATIO = 0.060


def _number(value):
    try:
        return float(value)
    except Exception:
        return None


def _point(value):
    try:
        return (
            float(value[0]),
            float(value[1]),
        )
    except Exception:
        return None


def _bbox(value):
    try:
        x0, y0, x1, y1 = (
            float(v)
            for v in value
        )
    except Exception:
        return None

    if (
        x1 <= x0
        or y1 <= y0
    ):
        return None

    return (
        x0,
        y0,
        x1,
        y1,
    )


def _center(box):
    return (
        (box[0] + box[2]) * 0.5,
        (box[1] + box[3]) * 0.5,
    )


def _area(box):
    return (
        (box[2] - box[0])
        *
        (box[3] - box[1])
    )


# ============================================================
# PLAN REGIONS
# ============================================================

def _select_plan_regions(
    analysis,
):
    regions = list(
        analysis.get(
            "regions",
            [],
        )
        or []
    )

    main = analysis.get(
        "main_plan"
    )

    if not isinstance(
        main,
        dict,
    ):
        raise RuntimeError(
            "Ana plan bolgesi bulunamadi."
        )

    main_box = _bbox(
        main.get(
            "bbox"
        )
    )

    if main_box is None:
        raise RuntimeError(
            "Ana plan bbox gecersiz."
        )

    main_id = str(
        main.get(
            "region_id",
            "",
        )
        or ""
    )

    main_area = _area(
        main_box
    )

    main_width = (
        main_box[2]
        - main_box[0]
    )

    main_height = (
        main_box[3]
        - main_box[1]
    )

    selected = []


    for region in regions:

        if not isinstance(
            region,
            dict,
        ):
            continue

        box = _bbox(
            region.get(
                "bbox"
            )
        )

        if box is None:
            continue

        region_id = str(
            region.get(
                "region_id",
                "",
            )
            or ""
        )

        if region_id == main_id:

            selected.append(
                deepcopy(
                    region
                )
            )

            continue


        semantic_count = int(
            region.get(
                "semantic_count",
                0,
            )
            or 0
        )

        if semantic_count <= 0:
            continue


        region_area = _area(
            box
        )

        width = (
            box[2]
            - box[0]
        )

        height = (
            box[3]
            - box[1]
        )


        area_ratio = (
            region_area
            / max(
                main_area,
                1.0e-9,
            )
        )

        width_ratio = (
            width
            / max(
                main_width,
                1.0e-9,
            )
        )

        height_ratio = (
            height
            / max(
                main_height,
                1.0e-9,
            )
        )


        if not (
            0.45
            <= area_ratio
            <= 1.60
        ):
            continue

        if not (
            0.55
            <= width_ratio
            <= 1.60
        ):
            continue

        if not (
            0.65
            <= height_ratio
            <= 1.35
        ):
            continue


        selected.append(
            deepcopy(
                region
            )
        )


    unique = {}

    for row in selected:

        region_id = str(
            row.get(
                "region_id",
                "",
            )
        )

        unique[
            region_id
        ] = row


    selected = list(
        unique.values()
    )


    selected.sort(
        key=lambda row: (
            float(
                row[
                    "bbox"
                ][0]
            ),
            float(
                row[
                    "bbox"
                ][1]
            ),
        )
    )


    if not selected:
        raise RuntimeError(
            "Plan bolgesi bulunamadi."
        )


    return selected


# ============================================================
# EXACT PLAN WINDOWS
# ============================================================

def _expanded_plan_bounds(
    bounds,
):
    x0, y0, x1, y1 = bounds

    width = max(
        x1 - x0,
        1.0,
    )

    height = max(
        y1 - y0,
        1.0,
    )

    px = max(
        80.0,
        width
        * PLAN_CONTEXT_X_RATIO,
    )

    py = max(
        80.0,
        height
        * PLAN_CONTEXT_Y_RATIO,
    )

    return (
        x0 - px,
        y0 - py,
        x1 + px,
        y1 + py,
    )


def _inside_original_plan(
    center,
    bounds,
):
    center = _point(
        center
    )

    if center is None:
        return False

    x0, y0, x1, y1 = bounds

    width = max(
        x1 - x0,
        1.0,
    )

    height = max(
        y1 - y0,
        1.0,
    )

    tx = max(
        80.0,
        width * 0.015,
    )

    ty = max(
        80.0,
        height * 0.015,
    )

    return (
        x0 - tx
        <= center[0]
        <= x1 + tx
        and
        y0 - ty
        <= center[1]
        <= y1 + ty
    )


def _detect_exact_plan_windows(
    window,
    regions,
):
    from cad._cad_to_3d_max_rooms_exact.cad_intelligence import (
        infer_cad_profile,
    )

    from cad._cad_to_3d_max_rooms_exact.window_detector import (
        detect_windows,
    )


    packages = []
    report = []


    for order, region in enumerate(
        regions
    ):

        source_bounds = _bbox(
            region.get(
                "bbox"
            )
        )

        if source_bounds is None:
            continue


        analysis_bounds = (
            _expanded_plan_bounds(
                source_bounds
            )
        )


        summary = (
            window.preview
            .cad_summary_for_bounds(
                analysis_bounds
            )
        )


        if not isinstance(
            summary,
            dict,
        ):
            continue


        geometry = list(
            summary.get(
                "geometry",
                [],
            )
            or []
        )


        if not geometry:
            continue


        profile = (
            infer_cad_profile(
                geometry
            )
        )


        target_layer = str(
            profile.get(
                "primary_structural_layer"
            )
            or ""
        ).strip()


        if not target_layer:
            continue


        detected = (
            detect_windows(
                geometry,
                structural_layer=
                    target_layer,
            )
        )


        windows = [
            deepcopy(
                row
            )
            for row in (
                detected.get(
                    "windows",
                    [],
                )
                or []
            )
            if _inside_original_plan(
                row.get(
                    "center"
                ),
                source_bounds,
            )
        ]


        rooflights = [
            deepcopy(
                row
            )
            for row in (
                detected.get(
                    "rooflights",
                    [],
                )
                or []
            )
            if _inside_original_plan(
                row.get(
                    "center"
                ),
                source_bounds,
            )
        ]


        if not windows:
            continue


        package = {
            "selection_index":
                int(
                    order
                ),

            "floor_name":
                "AUTO_PLAN_"
                + str(
                    order + 1
                ),

            "floor_order":
                int(
                    order
                ),

            # IMPORTANT:
            # original physical plan bounds remain the
            # coordinate reference for side/relative position.
            "source_bounds":
                source_bounds,

            "analysis_bounds":
                analysis_bounds,

            "windows":
                windows,

            "rooflights":
                rooflights,

            "target_layer":
                target_layer,

            "region_id":
                region.get(
                    "region_id"
                ),
        }


        packages.append(
            package
        )


        report.append(
            {
                "region_id":
                    region.get(
                        "region_id"
                    ),

                "floor_order":
                    order,

                "source_bounds":
                    list(
                        source_bounds
                    ),

                "analysis_bounds":
                    list(
                        analysis_bounds
                    ),

                "target_layer":
                    target_layer,

                "window_count":
                    len(
                        windows
                    ),

                "rooflight_count":
                    len(
                        rooflights
                    ),

                "windows":
                    [
                        {
                            "window_id":
                                row.get(
                                    "window_id"
                                ),

                            "center":
                                row.get(
                                    "center"
                                ),

                            "direction":
                                row.get(
                                    "direction"
                                ),

                            "width":
                                row.get(
                                    "width"
                                ),

                            "confidence":
                                row.get(
                                    "confidence"
                                ),
                        }

                        for row in windows
                    ],
            }
        )


    if not packages:

        raise RuntimeError(
            "Plan pencere motoru hic pencere bulamadi."
        )


    return (
        packages,
        report,
    )


# ============================================================
# ALL-STOREY FACADE STRUCTURAL CANDIDATES
# ============================================================

def _extract_facade_axis_lines(
    geometry,
    bounds,
):
    from cad._cad_to_3d_max_rooms_exact.elevation_opening_detector import (
        _extract_axis_segments,
        _merge_horizontal,
        _merge_vertical,
    )


    rx0, ry0, rx1, ry1 = bounds

    width = max(
        rx1 - rx0,
        1.0,
    )

    height = max(
        ry1 - ry0,
        1.0,
    )


    horizontal, vertical = (
        _extract_axis_segments(
            geometry
        )
    )


    pad_x = width * 0.015
    pad_y = height * 0.015


    horizontal = [
        row
        for row in horizontal
        if (
            ry0 - pad_y
            <= row["y"]
            <= ry1 + pad_y
            and
            row["x1"]
            >= rx0 - pad_x
            and
            row["x0"]
            <= rx1 + pad_x
        )
    ]


    vertical = [
        row
        for row in vertical
        if (
            rx0 - pad_x
            <= row["x"]
            <= rx1 + pad_x
            and
            row["y1"]
            >= ry0 - pad_y
            and
            row["y0"]
            <= ry1 + pad_y
        )
    ]


    horizontal = (
        _merge_horizontal(
            horizontal,
            y_tolerance=max(
                8.0,
                height * 0.0025,
            ),
            gap_tolerance=max(
                16.0,
                width * 0.003,
            ),
        )
    )


    vertical = (
        _merge_vertical(
            vertical,
            x_tolerance=max(
                8.0,
                width * 0.0025,
            ),
            gap_tolerance=max(
                16.0,
                height * 0.003,
            ),
        )
    )


    horizontal = [
        row
        for row in horizontal
        if (
            ry0 - pad_y
            <= row["y"]
            <= ry1 + pad_y
        )
    ]


    vertical = [
        row
        for row in vertical
        if (
            rx0 - pad_x
            <= row["x"]
            <= rx1 + pad_x
        )
    ]


    return (
        horizontal,
        vertical,
    )


def _build_all_storey_candidates(
    geometry,
    bounds,
    expected_widths,
):
    """
    Same structural principle as elevation_opening_detector,
    but deliberately WITHOUT the old ground-floor-only gate.

    A physical candidate requires:
        left vertical jamb
        right vertical jamb
        matching vertical span
        bottom horizontal support
        top horizontal support

    PLAN widths restrict the jamb-pair search.
    """

    from cad._cad_to_3d_max_rooms_exact.elevation_opening_detector import (
        _horizontal_coverage,
        _internal_structure_score,
    )


    expected_widths = [
        float(value)
        for value in expected_widths
        if (
            _number(
                value
            )
            is not None
            and float(
                value
            ) > 1.0e-9
        )
    ]


    if not expected_widths:
        return []


    rx0, ry0, rx1, ry1 = bounds

    region_width = max(
        rx1 - rx0,
        1.0,
    )

    region_height = max(
        ry1 - ry0,
        1.0,
    )


    horizontal, vertical = (
        _extract_facade_axis_lines(
            geometry,
            bounds,
        )
    )


    x_tolerance = max(
        10.0,
        region_width * 0.0025,
    )

    y_tolerance = max(
        14.0,
        region_height * 0.006,
    )


    minimum_expected = min(
        expected_widths
    )

    maximum_expected = max(
        expected_widths
    )


    min_width = max(
        100.0,
        minimum_expected
        * (
            1.0
            - WIDTH_GATE
            - 0.06
        ),
    )

    max_width = (
        maximum_expected
        * (
            1.0
            + WIDTH_GATE
            + 0.06
        )
    )


    min_height = max(
        350.0,
        region_height * 0.045,
    )

    max_height = (
        region_height
        * 0.34
    )


    usable_vertical = [
        row
        for row in vertical
        if (
            row["y1"]
            - row["y0"]
        )
        >= min_height * 0.72
    ]


    usable_vertical.sort(
        key=lambda row:
            row["x"]
    )


    candidates = []


    for i, left in enumerate(
        usable_vertical
    ):

        for right in usable_vertical[
            i + 1:
        ]:

            frame_width = (
                right["x"]
                - left["x"]
            )


            if frame_width < min_width:
                continue

            if frame_width > max_width:
                break


            # Must be dimensionally plausible for at least
            # one actual PLAN window.
            nearest_width_error = min(
                abs(
                    frame_width
                    - expected
                )
                / expected

                for expected
                in expected_widths
            )


            if (
                nearest_width_error
                > WIDTH_GATE + 0.035
            ):
                continue


            bottom_difference = abs(
                left["y0"]
                - right["y0"]
            )

            top_difference = abs(
                left["y1"]
                - right["y1"]
            )


            if (
                bottom_difference
                > y_tolerance * 2.5
                or
                top_difference
                > y_tolerance * 2.5
            ):
                continue


            bottom = (
                left["y0"]
                + right["y0"]
            ) * 0.5

            top = (
                left["y1"]
                + right["y1"]
            ) * 0.5


            frame_height = (
                top
                - bottom
            )


            if not (
                min_height
                <= frame_height
                <= max_height
            ):
                continue


            # NO GROUND FLOOR RESTRICTION HERE.


            bottom_support = (
                _horizontal_coverage(
                    horizontal,
                    bottom,
                    left["x"],
                    right["x"],
                    y_tolerance,
                )
            )


            top_support = (
                _horizontal_coverage(
                    horizontal,
                    top,
                    left["x"],
                    right["x"],
                    y_tolerance,
                )
            )


            if (
                bottom_support < 0.40
                or
                top_support < 0.40
            ):
                continue


            aspect = (
                frame_width
                / max(
                    frame_height,
                    1.0,
                )
            )


            if not (
                0.12
                <= aspect
                <= 4.5
            ):
                continue


            box = (
                float(
                    left["x"]
                ),
                float(
                    bottom
                ),
                float(
                    right["x"]
                ),
                float(
                    top
                ),
            )


            internal = (
                _internal_structure_score(
                    vertical,
                    horizontal,
                    box,
                )
            )


            score = (
                bottom_support * 2.0
                + top_support * 2.0
                + internal * 0.55
                - nearest_width_error * 3.0
            )


            candidates.append(
                {
                    "bbox":
                        box,

                    "center":
                        _center(
                            box
                        ),

                    "width":
                        float(
                            frame_width
                        ),

                    "height":
                        float(
                            frame_height
                        ),

                    "bottom_y":
                        float(
                            bottom
                        ),

                    "top_y":
                        float(
                            top
                        ),

                    "bottom_support":
                        float(
                            bottom_support
                        ),

                    "top_support":
                        float(
                            top_support
                        ),

                    "internal_score":
                        float(
                            internal
                        ),

                    "geometric_score":
                        float(
                            score
                        ),

                    "nearest_plan_width_error":
                        float(
                            nearest_width_error
                        ),
                }
            )


    # --------------------------------------------------------
    # STRUCTURAL DEDUPE
    # --------------------------------------------------------

    deduped = {}


    for row in candidates:

        box = row[
            "bbox"
        ]

        key = (
            round(
                box[0]
                / x_tolerance
            ),
            round(
                box[1]
                / y_tolerance
            ),
            round(
                box[2]
                / x_tolerance
            ),
            round(
                box[3]
                / y_tolerance
            ),
        )


        old = deduped.get(
            key
        )


        if (
            old is None
            or row[
                "geometric_score"
            ]
            > old[
                "geometric_score"
            ]
        ):
            deduped[
                key
            ] = row


    result = list(
        deduped.values()
    )


    result.sort(
        key=lambda row: (
            row["center"][1],
            row["center"][0],
            -row["geometric_score"],
        )
    )


    return result


# ============================================================
# STOREY CLUSTER
# ============================================================

def _candidate_relative_center(
    candidate,
    facade_bounds,
    reversed_order,
):
    rx0, _ry0, rx1, _ry1 = (
        facade_bounds
    )

    width = max(
        rx1 - rx0,
        1.0e-9,
    )

    rel = (
        candidate[
            "center"
        ][0]
        - rx0
    ) / width


    if reversed_order:
        rel = (
            1.0
            - rel
        )


    return float(
        rel
    )


def _is_plan_plausible(
    candidate,
    plans,
    facade_bounds,
    reversed_order,
):
    candidate_rel = (
        _candidate_relative_center(
            candidate,
            facade_bounds,
            reversed_order,
        )
    )


    for plan in plans:

        plan_width = _number(
            plan.get(
                "width"
            )
        )

        plan_rel = _number(
            plan.get(
                "relative_center"
            )
        )


        if (
            plan_width is None
            or plan_rel is None
            or plan_width
            <= 1.0e-9
        ):
            continue


        width_error = (
            abs(
                candidate[
                    "width"
                ]
                - plan_width
            )
            / plan_width
        )

        position_error = abs(
            candidate_rel
            - plan_rel
        )


        if (
            width_error
            <= WIDTH_GATE + 0.035
            and
            position_error
            <= POSITION_GATE + 0.06
        ):
            return True


    return False


def _cluster_y_levels(
    candidates,
    floor_orders,
):
    floor_orders = sorted(
        set(
            int(value)
            for value in floor_orders
        )
    )


    if not candidates:
        return {}


    if len(
        floor_orders
    ) <= 1:

        floor = (
            floor_orders[0]
            if floor_orders
            else 0
        )

        return {
            index:
                floor
            for index in range(
                len(
                    candidates
                )
            )
        }


    values = [
        float(
            row[
                "center"
            ][1]
        )
        for row in candidates
    ]


    k = min(
        len(
            floor_orders
        ),
        len(
            values
        ),
    )


    if k <= 1:

        return {
            index:
                floor_orders[0]
            for index in range(
                len(
                    candidates
                )
            )
        }


    low = min(
        values
    )

    high = max(
        values
    )


    if abs(
        high - low
    ) <= 1.0e-9:

        return {
            index:
                floor_orders[0]
            for index in range(
                len(
                    candidates
                )
            )
        }


    centers = [
        low
        + (
            high - low
        )
        * (
            index
            / (
                k - 1
            )
        )

        for index in range(
            k
        )
    ]


    assignments = [
        0
        for _ in values
    ]


    for _iteration in range(
        40
    ):

        changed = False


        for index, value in enumerate(
            values
        ):

            group = min(
                range(
                    k
                ),
                key=lambda g:
                    abs(
                        value
                        - centers[g]
                    ),
            )


            if assignments[
                index
            ] != group:

                assignments[
                    index
                ] = group

                changed = True


        new_centers = list(
            centers
        )


        for group in range(
            k
        ):

            members = [
                values[index]
                for index, assigned
                in enumerate(
                    assignments
                )
                if assigned
                == group
            ]


            if members:

                new_centers[
                    group
                ] = (
                    sum(
                        members
                    )
                    / len(
                        members
                    )
                )


        if (
            not changed
            and all(
                abs(
                    new_centers[i]
                    - centers[i]
                )
                <= 1.0e-6

                for i in range(
                    k
                )
            )
        ):
            centers = (
                new_centers
            )
            break


        centers = (
            new_centers
        )


    ordered_groups = sorted(
        range(
            k
        ),
        key=lambda group:
            centers[
                group
            ],
    )


    group_to_floor = {}


    for position, group in enumerate(
        ordered_groups
    ):

        if position < len(
            floor_orders
        ):

            group_to_floor[
                group
            ] = (
                floor_orders[
                    position
                ]
            )

        else:

            group_to_floor[
                group
            ] = (
                floor_orders[
                    -1
                ]
            )


    return {
        index:
            group_to_floor[
                assignments[
                    index
                ]
            ]

        for index in range(
            len(
                candidates
            )
        )
    }


# ============================================================
# ORDERED PLAN -> FACADE ASSIGNMENT
# ============================================================


# CAD3D_PHYSICAL_WINDOW_FAMILY_MATCH_V3

def _bbox_iou(
    a,
    b,
):
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b

    ix0 = max(
        ax0,
        bx0,
    )

    iy0 = max(
        ay0,
        by0,
    )

    ix1 = min(
        ax1,
        bx1,
    )

    iy1 = min(
        ay1,
        by1,
    )

    iw = max(
        0.0,
        ix1 - ix0,
    )

    ih = max(
        0.0,
        iy1 - iy0,
    )

    intersection = (
        iw * ih
    )

    if intersection <= 0.0:
        return 0.0

    area_a = max(
        (ax1 - ax0)
        * (ay1 - ay0),
        0.0,
    )

    area_b = max(
        (bx1 - bx0)
        * (by1 - by0),
        0.0,
    )

    union = (
        area_a
        + area_b
        - intersection
    )

    if union <= 0.0:
        return 0.0

    return (
        intersection
        / union
    )


def _minimum_axis_overlap(
    a0,
    a1,
    b0,
    b1,
):
    overlap = max(
        0.0,
        min(
            a1,
            b1,
        )
        - max(
            a0,
            b0,
        ),
    )

    minimum = max(
        min(
            a1 - a0,
            b1 - b0,
        ),
        1.0e-9,
    )

    return (
        overlap
        / minimum
    )


def _same_physical_window_candidate(
    a,
    b,
    facade_bounds,
):
    """
    Different inner/outer frame rectangles belonging to the
    SAME physical window must be one selectable family.

    This prevents:
        one real dormer
        -> two plan windows
    """

    ax, ay = a[
        "center"
    ]

    bx, by = b[
        "center"
    ]

    rx0, ry0, rx1, ry1 = (
        facade_bounds
    )

    facade_width = max(
        rx1 - rx0,
        1.0,
    )

    facade_height = max(
        ry1 - ry0,
        1.0,
    )

    x_tolerance = max(
        110.0,
        facade_width * 0.020,
    )

    y_tolerance = max(
        100.0,
        facade_height * 0.020,
    )

    if (
        abs(
            ax - bx
        ) > x_tolerance
        or
        abs(
            ay - by
        ) > y_tolerance
    ):
        return False


    abox = a[
        "bbox"
    ]

    bbox = b[
        "bbox"
    ]


    horizontal_overlap = (
        _minimum_axis_overlap(
            abox[0],
            abox[2],
            bbox[0],
            bbox[2],
        )
    )

    vertical_overlap = (
        _minimum_axis_overlap(
            abox[1],
            abox[3],
            bbox[1],
            bbox[3],
        )
    )


    return (
        horizontal_overlap >= 0.50
        and
        vertical_overlap >= 0.55
    )


def _physical_candidate_families(
    candidates,
    facade_bounds,
):
    """
    Collapse nested/alternative jamb-pair rectangles into one
    physical-window family.

    Variants are retained inside each family, so width matching
    can still select the best outer frame.
    """

    ordered = sorted(
        list(
            candidates
        ),
        key=lambda row: (
            float(
                row[
                    "center"
                ][1]
            ),
            float(
                row[
                    "center"
                ][0]
            ),
            -_area(
                row[
                    "bbox"
                ]
            ),
        ),
    )


    families = []


    for candidate in ordered:

        target = None


        for family in families:

            if any(
                _same_physical_window_candidate(
                    candidate,
                    member,
                    facade_bounds,
                )

                for member
                in family[
                    "variants"
                ]
            ):
                target = family
                break


        if target is None:

            target = {
                "family_id":
                    len(
                        families
                    ),

                "variants":
                    [],
            }

            families.append(
                target
            )


        target[
            "variants"
        ].append(
            candidate
        )


    return families


def _ordered_match(
    plans,
    candidates,
    facade_bounds,
    reversed_order,
):
    """
    V3:
        PLAN WINDOW
             ?
        ONE PHYSICAL WINDOW FAMILY
             ?
        best dimensional frame inside family

    A physical window family can never be consumed twice.
    """

    plans = sorted(
        list(
            plans
        ),
        key=lambda row:
            float(
                row.get(
                    "relative_center",
                    0.0,
                )
            ),
    )


    families = (
        _physical_candidate_families(
            candidates,
            facade_bounds,
        )
    )


    prepared_families = []


    for family in families:

        variants = []


        for candidate in family[
            "variants"
        ]:

            item = dict(
                candidate
            )

            item[
                "aligned_relative_center"
            ] = (
                _candidate_relative_center(
                    item,
                    facade_bounds,
                    reversed_order,
                )
            )

            variants.append(
                item
            )


        if not variants:
            continue


        family_position = sorted(
            float(
                row[
                    "aligned_relative_center"
                ]
            )
            for row in variants
        )


        family_position = (
            family_position[
                len(
                    family_position
                )
                // 2
            ]
        )


        prepared_families.append(
            {
                "family_id":
                    family[
                        "family_id"
                    ],

                "family_position":
                    float(
                        family_position
                    ),

                "variants":
                    variants,
            }
        )


    prepared_families.sort(
        key=lambda row:
            row[
                "family_position"
            ]
    )


    def best_family_variant(
        plan,
        family,
    ):

        plan_width = _number(
            plan.get(
                "width"
            )
        )

        plan_rel = _number(
            plan.get(
                "relative_center"
            )
        )


        if (
            plan_width is None
            or plan_rel is None
            or plan_width <= 0.0
        ):
            return None


        best = None


        for variant_index, candidate in enumerate(
            family[
                "variants"
            ]
        ):

            width_error = (
                abs(
                    candidate[
                        "width"
                    ]
                    - plan_width
                )
                / plan_width
            )


            position_error = abs(
                candidate[
                    "aligned_relative_center"
                ]
                - plan_rel
            )


            if (
                width_error
                > WIDTH_GATE
            ):
                continue


            if (
                position_error
                > POSITION_GATE
            ):
                continue


            geometry_bonus = (
                min(
                    max(
                        candidate[
                            "geometric_score"
                        ],
                        0.0,
                    ),
                    8.0,
                )
                * 0.025
            )


            # Width is dominant.
            cost = (
                width_error * 18.0
                +
                position_error * 6.0
                -
                geometry_bonus
            )


            rank = (
                float(
                    cost
                ),
                float(
                    width_error
                ),
                float(
                    position_error
                ),
                -_area(
                    candidate[
                        "bbox"
                    ]
                ),
            )


            if (
                best is None
                or rank
                < best[
                    "rank"
                ]
            ):

                best = {
                    "variant_index":
                        variant_index,

                    "candidate":
                        candidate,

                    "width_error":
                        float(
                            width_error
                        ),

                    "position_error":
                        float(
                            position_error
                        ),

                    "cost":
                        float(
                            cost
                        ),

                    "rank":
                        rank,
                }


        return best


    @lru_cache(
        maxsize=None
    )
    def solve(
        plan_index,
        family_index,
    ):

        if (
            plan_index
            >= len(
                plans
            )
            or
            family_index
            >= len(
                prepared_families
            )
        ):
            return (
                0,
                0.0,
                (),
            )


        options = []


        # Skip current plan.
        matches, cost, pairs = (
            solve(
                plan_index + 1,
                family_index,
            )
        )

        options.append(
            (
                matches,
                cost,
                pairs,
            )
        )


        # Skip current physical family.
        matches, cost, pairs = (
            solve(
                plan_index,
                family_index + 1,
            )
        )

        options.append(
            (
                matches,
                cost,
                pairs,
            )
        )


        family_match = (
            best_family_variant(
                plans[
                    plan_index
                ],
                prepared_families[
                    family_index
                ],
            )
        )


        if family_match is not None:

            matches, cost, pairs = (
                solve(
                    plan_index + 1,
                    family_index + 1,
                )
            )


            options.append(
                (
                    matches + 1,

                    cost
                    + family_match[
                        "cost"
                    ],

                    (
                        (
                            plan_index,
                            family_index,
                            family_match[
                                "variant_index"
                            ],
                            family_match[
                                "width_error"
                            ],
                            family_match[
                                "position_error"
                            ],
                            family_match[
                                "cost"
                            ],
                        ),
                    )
                    + pairs,
                )
            )


        # First maximize count.
        # Then minimize cost.
        return max(
            options,
            key=lambda value:
                (
                    value[0],
                    -value[1],
                ),
        )


    (
        _matched_count,
        _total_cost,
        pair_rows,
    ) = solve(
        0,
        0,
    )


    matches = []


    for (
        plan_index,
        family_index,
        variant_index,
        width_error,
        position_error,
        pair_cost,
    ) in pair_rows:

        family = (
            prepared_families[
                family_index
            ]
        )

        candidate = (
            family[
                "variants"
            ][
                variant_index
            ]
        )


        matches.append(
            {
                "plan":
                    plans[
                        plan_index
                    ],

                "candidate":
                    candidate,

                "physical_family_id":
                    family[
                        "family_id"
                    ],

                "physical_family_size":
                    len(
                        family[
                            "variants"
                        ]
                    ),

                "width_error":
                    float(
                        width_error
                    ),

                "position_error":
                    float(
                        position_error
                    ),

                "cost":
                    float(
                        pair_cost
                    ),
            }
        )


    return matches


def _evaluate_facade_orientation(
    plans,
    candidates,
    facade_bounds,
    reversed_order,
    floor_orders,
):
    """
    Evaluate BOTH physical facade directions.

    Do not trust inherited reversed=False when geometry and
    plan sequence prove the opposite.
    """

    plausible = [
        row
        for row in candidates
        if _is_plan_plausible(
            row,
            plans,
            facade_bounds,
            reversed_order,
        )
    ]


    cluster_map = (
        _cluster_y_levels(
            plausible,
            floor_orders,
        )
    )


    candidates_by_floor = {
        floor:
            []

        for floor
        in floor_orders
    }


    for candidate_index, row in enumerate(
        plausible
    ):

        floor = cluster_map.get(
            candidate_index
        )

        if floor is None:
            continue

        candidates_by_floor.setdefault(
            floor,
            [],
        ).append(
            row
        )


    total_matches = 0
    total_cost = 0.0

    floor_rows = []


    for floor in floor_orders:

        floor_plans = [
            row
            for row in plans
            if int(
                row.get(
                    "floor_order",
                    0,
                )
                or 0
            )
            == floor
        ]


        floor_candidates = (
            candidates_by_floor.get(
                floor,
                [],
            )
        )


        matches = (
            _ordered_match(
                floor_plans,
                floor_candidates,
                facade_bounds,
                reversed_order,
            )
        )


        total_matches += len(
            matches
        )


        total_cost += sum(
            float(
                row[
                    "cost"
                ]
            )
            for row in matches
        )


        floor_rows.append(
            {
                "floor_order":
                    floor,

                "plan_count":
                    len(
                        floor_plans
                    ),

                "candidate_count":
                    len(
                        floor_candidates
                    ),

                "physical_family_count":
                    len(
                        _physical_candidate_families(
                            floor_candidates,
                            facade_bounds,
                        )
                    ),

                "matched_count":
                    len(
                        matches
                    ),

                "cost":
                    float(
                        sum(
                            row[
                                "cost"
                            ]
                            for row
                            in matches
                        )
                    ),
            }
        )


    return {
        "reversed":
            bool(
                reversed_order
            ),

        "matched_count":
            int(
                total_matches
            ),

        "total_cost":
            float(
                total_cost
            ),

        "plausible":
            plausible,

        "candidates_by_floor":
            candidates_by_floor,

        "floor_rows":
            floor_rows,
    }


# ============================================================
# DIRECT RESOLVER
# ============================================================


def _resolve_direct_facade_windows(
    raw,
    plan_facades,
    full_geometry,
):
    """
    V3 physical facade resolver.

    Guarantees:
      1) one physical window family -> max one plan window
      2) facade orientation is solved from plan+geometry
      3) known-good width/position matches keep their priority
      4) duplicate overlay boxes are hard-rejected
    """

    elevation_facades = {
        int(
            row[
                "facade_number"
            ]
        ):
            row

        for row in (
            raw.get(
                "elevation_facades",
                [],
            )
            or []
        )

        if row.get(
            "facade_number"
        )
        is not None
    }


    side_map = {}


    raw_matches = sorted(
        list(
            raw.get(
                "matches",
                [],
            )
            or []
        ),
        key=lambda row:
            int(
                row.get(
                    "storey_index",
                    0,
                )
                or 0
            ),
    )


    for match in raw_matches:

        side = str(
            match.get(
                "plan_side",
                "",
            )
            or ""
        ).strip().lower()


        if not side:
            continue


        try:
            facade_number = int(
                match.get(
                    "facade_number"
                )
            )
        except Exception:
            continue


        if side not in side_map:

            side_map[
                side
            ] = {
                "facade_number":
                    facade_number,

                "reversed":
                    bool(
                        match.get(
                            "reversed",
                            False,
                        )
                    ),
            }


    accepted = []
    unresolved = []
    audit_facades = []


    for plan_facade in plan_facades:

        side = str(
            plan_facade.get(
                "side",
                "",
            )
            or ""
        ).strip().lower()


        plans = list(
            plan_facade.get(
                "openings",
                [],
            )
            or []
        )


        if not plans:
            continue


        registration = (
            side_map.get(
                side
            )
        )


        if registration is None:

            for plan_index, plan in enumerate(
                plans
            ):

                unresolved.append(
                    {
                        "plan_side":
                            side,

                        "plan_index":
                            plan_index,

                        "floor_order":
                            plan.get(
                                "floor_order"
                            ),

                        "plan_width":
                            plan.get(
                                "width"
                            ),

                        "reason":
                            "NO_FACADE_SIDE_REGISTRATION",
                    }
                )

            continue


        facade_number = (
            registration[
                "facade_number"
            ]
        )


        inherited_reversed = bool(
            registration[
                "reversed"
            ]
        )


        facade = elevation_facades.get(
            facade_number
        )


        if facade is None:
            continue


        facade_bounds = _bbox(
            facade.get(
                "bbox"
            )
        )


        if facade_bounds is None:
            continue


        expected_widths = [
            float(
                plan[
                    "width"
                ]
            )

            for plan in plans

            if (
                _number(
                    plan.get(
                        "width"
                    )
                )
                is not None
                and float(
                    plan[
                        "width"
                    ]
                ) > 0.0
            )
        ]


        candidates = (
            _build_all_storey_candidates(
                full_geometry,
                facade_bounds,
                expected_widths,
            )
        )


        floor_orders = sorted(
            set(
                int(
                    plan.get(
                        "floor_order",
                        0,
                    )
                    or 0
                )

                for plan in plans
            )
        )


        normal_eval = (
            _evaluate_facade_orientation(
                plans,
                candidates,
                facade_bounds,
                False,
                floor_orders,
            )
        )


        reversed_eval = (
            _evaluate_facade_orientation(
                plans,
                candidates,
                facade_bounds,
                True,
                floor_orders,
            )
        )


        inherited_eval = (
            reversed_eval
            if inherited_reversed
            else normal_eval
        )


        alternate_eval = (
            normal_eval
            if inherited_reversed
            else reversed_eval
        )


        # ----------------------------------------------------
        # Orientation rule:
        #
        # Flip only when geometry gives stronger evidence:
        #   - more unique physical windows matched, or
        #   - same count but clearly lower global cost.
        #
        # Otherwise preserve the inherited orientation.
        # ----------------------------------------------------

        if (
            alternate_eval[
                "matched_count"
            ]
            >
            inherited_eval[
                "matched_count"
            ]
        ):

            chosen_eval = (
                alternate_eval
            )

            orientation_reason = (
                "MORE_UNIQUE_WINDOWS"
            )


        elif (
            alternate_eval[
                "matched_count"
            ]
            ==
            inherited_eval[
                "matched_count"
            ]
            and
            alternate_eval[
                "total_cost"
            ]
            + 0.20
            <
            inherited_eval[
                "total_cost"
            ]
        ):

            chosen_eval = (
                alternate_eval
            )

            orientation_reason = (
                "LOWER_GLOBAL_COST"
            )


        else:

            chosen_eval = (
                inherited_eval
            )

            orientation_reason = (
                "KEEP_INHERITED"
            )


        reversed_order = bool(
            chosen_eval[
                "reversed"
            ]
        )


        plausible = (
            chosen_eval[
                "plausible"
            ]
        )


        candidates_by_floor = (
            chosen_eval[
                "candidates_by_floor"
            ]
        )


        matched_plan_keys = set()
        floor_audit = []


        for floor in floor_orders:

            floor_plans = [
                row
                for row in plans
                if int(
                    row.get(
                        "floor_order",
                        0,
                    )
                    or 0
                )
                == floor
            ]


            floor_candidates = (
                candidates_by_floor.get(
                    floor,
                    [],
                )
            )


            matches = (
                _ordered_match(
                    floor_plans,
                    floor_candidates,
                    facade_bounds,
                    reversed_order,
                )
            )


            floor_matches = []


            for match in matches:

                plan = (
                    match[
                        "plan"
                    ]
                )

                candidate = (
                    match[
                        "candidate"
                    ]
                )


                source_window_index = int(
                    plan.get(
                        "source_window_index",
                        0,
                    )
                    or 0
                )


                plan_key = (
                    int(
                        floor
                    ),
                    source_window_index,
                )


                matched_plan_keys.add(
                    plan_key
                )


                box = (
                    candidate[
                        "bbox"
                    ]
                )


                record = {
                    "kind":
                        "window",

                    "facade_number":
                        int(
                            facade_number
                        ),

                    "plan_side":
                        side,

                    "floor_order":
                        int(
                            floor
                        ),

                    "floor_name":
                        str(
                            plan.get(
                                "floor_name",
                                "",
                            )
                            or ""
                        ),

                    "source_window_index":
                        source_window_index,

                    "source_window_id":
                        plan.get(
                            "source_window_id"
                        ),

                    "plan_center":
                        deepcopy(
                            plan.get(
                                "center"
                            )
                        ),

                    "plan_width":
                        float(
                            plan[
                                "width"
                            ]
                        ),

                    "plan_relative_center":
                        float(
                            plan[
                                "relative_center"
                            ]
                        ),

                    "elevation_bbox":
                        [
                            float(v)
                            for v in box
                        ],

                    "elevation_center":
                        [
                            float(v)
                            for v in candidate[
                                "center"
                            ]
                        ],

                    "elevation_width":
                        float(
                            candidate[
                                "width"
                            ]
                        ),

                    "elevation_height":
                        float(
                            candidate[
                                "height"
                            ]
                        ),

                    "elevation_bottom_y":
                        float(
                            candidate[
                                "bottom_y"
                            ]
                        ),

                    "elevation_top_y":
                        float(
                            candidate[
                                "top_y"
                            ]
                        ),

                    "width_error_ratio":
                        float(
                            match[
                                "width_error"
                            ]
                        ),

                    "position_error_ratio":
                        float(
                            match[
                                "position_error"
                            ]
                        ),

                    "selection_cost":
                        float(
                            match[
                                "cost"
                            ]
                        ),

                    "physical_family_id":
                        int(
                            match[
                                "physical_family_id"
                            ]
                        ),

                    "physical_family_size":
                        int(
                            match[
                                "physical_family_size"
                            ]
                        ),

                    "bottom_support":
                        float(
                            candidate[
                                "bottom_support"
                            ]
                        ),

                    "top_support":
                        float(
                            candidate[
                                "top_support"
                            ]
                        ),

                    "geometric_score":
                        float(
                            candidate[
                                "geometric_score"
                            ]
                        ),

                    "facade_reversed":
                        reversed_order,

                    "orientation_reason":
                        orientation_reason,

                    "plan_guided":
                        True,

                    "direct_geometry":
                        True,

                    "candidate_source":
                        "RAW_CAD_PHYSICAL_WINDOW_FAMILY_V3",
                }


                accepted.append(
                    record
                )

                floor_matches.append(
                    record
                )


            floor_audit.append(
                {
                    "floor_order":
                        floor,

                    "plan_count":
                        len(
                            floor_plans
                        ),

                    "candidate_count":
                        len(
                            floor_candidates
                        ),

                    "physical_family_count":
                        len(
                            _physical_candidate_families(
                                floor_candidates,
                                facade_bounds,
                            )
                        ),

                    "matched_count":
                        len(
                            floor_matches
                        ),

                    "matches":
                        floor_matches,
                }
            )


        for plan_index, plan in enumerate(
            plans
        ):

            floor = int(
                plan.get(
                    "floor_order",
                    0,
                )
                or 0
            )


            source_window_index = int(
                plan.get(
                    "source_window_index",
                    plan_index,
                )
                or 0
            )


            key = (
                floor,
                source_window_index,
            )


            if key in matched_plan_keys:
                continue


            plan_width = float(
                plan.get(
                    "width",
                    0.0,
                )
                or 0.0
            )


            plan_rel = float(
                plan.get(
                    "relative_center",
                    0.0,
                )
                or 0.0
            )


            best = None


            for candidate in (
                candidates_by_floor.get(
                    floor,
                    [],
                )
            ):

                candidate_rel = (
                    _candidate_relative_center(
                        candidate,
                        facade_bounds,
                        reversed_order,
                    )
                )


                width_error = (
                    abs(
                        candidate[
                            "width"
                        ]
                        - plan_width
                    )
                    / max(
                        plan_width,
                        1.0e-9,
                    )
                )


                position_error = abs(
                    candidate_rel
                    - plan_rel
                )


                rank = (
                    width_error * 18.0
                    +
                    position_error * 6.0
                )


                if (
                    best is None
                    or rank
                    < best[
                        "rank"
                    ]
                ):

                    best = {
                        "rank":
                            float(
                                rank
                            ),

                        "width_error":
                            float(
                                width_error
                            ),

                        "position_error":
                            float(
                                position_error
                            ),

                        "bbox":
                            candidate[
                                "bbox"
                            ],

                        "width":
                            candidate[
                                "width"
                            ],
                    }


            unresolved.append(
                {
                    "facade_number":
                        facade_number,

                    "plan_side":
                        side,

                    "plan_index":
                        plan_index,

                    "floor_order":
                        floor,

                    "floor_name":
                        plan.get(
                            "floor_name"
                        ),

                    "source_window_index":
                        source_window_index,

                    "source_window_id":
                        plan.get(
                            "source_window_id"
                        ),

                    "plan_width":
                        plan_width,

                    "plan_relative_center":
                        plan_rel,

                    "facade_reversed":
                        reversed_order,

                    "best_candidate":
                        best,

                    "reason":
                        "NO_UNIQUE_PHYSICAL_WINDOW_MATCH",
                }
            )


        audit_facades.append(
            {
                "facade_number":
                    facade_number,

                "plan_side":
                    side,

                "inherited_reversed":
                    inherited_reversed,

                "chosen_reversed":
                    reversed_order,

                "orientation_reason":
                    orientation_reason,

                "normal_orientation":
                    {
                        "matched_count":
                            normal_eval[
                                "matched_count"
                            ],

                        "total_cost":
                            normal_eval[
                                "total_cost"
                            ],
                    },

                "reversed_orientation":
                    {
                        "matched_count":
                            reversed_eval[
                                "matched_count"
                            ],

                        "total_cost":
                            reversed_eval[
                                "total_cost"
                            ],
                    },

                "facade_bbox":
                    list(
                        facade_bounds
                    ),

                "plan_window_count":
                    len(
                        plans
                    ),

                "raw_structural_candidate_count":
                    len(
                        candidates
                    ),

                "plan_plausible_candidate_count":
                    len(
                        plausible
                    ),

                "floor_orders":
                    floor_orders,

                "floors":
                    floor_audit,
            }
        )


    # ========================================================
    # FINAL HARD PHYSICAL DUPLICATE GATE
    # ========================================================

    accepted.sort(
        key=lambda row: (
            int(
                row[
                    "facade_number"
                ]
            ),
            int(
                row[
                    "floor_order"
                ]
            ),
            float(
                row[
                    "selection_cost"
                ]
            ),
        )
    )


    unique = []


    for row in accepted:

        duplicate = None


        for kept in unique:

            if (
                kept[
                    "facade_number"
                ]
                !=
                row[
                    "facade_number"
                ]
                or
                kept[
                    "floor_order"
                ]
                !=
                row[
                    "floor_order"
                ]
            ):
                continue


            iou = _bbox_iou(
                tuple(
                    kept[
                        "elevation_bbox"
                    ]
                ),
                tuple(
                    row[
                        "elevation_bbox"
                    ]
                ),
            )


            if iou >= 0.55:

                duplicate = kept
                break


        if duplicate is None:

            unique.append(
                row
            )

            continue


        unresolved.append(
            {
                "facade_number":
                    row[
                        "facade_number"
                    ],

                "plan_side":
                    row[
                        "plan_side"
                    ],

                "floor_order":
                    row[
                        "floor_order"
                    ],

                "source_window_index":
                    row[
                        "source_window_index"
                    ],

                "source_window_id":
                    row[
                        "source_window_id"
                    ],

                "plan_width":
                    row[
                        "plan_width"
                    ],

                "rejected_bbox":
                    row[
                        "elevation_bbox"
                    ],

                "kept_source_window_id":
                    duplicate[
                        "source_window_id"
                    ],

                "kept_bbox":
                    duplicate[
                        "elevation_bbox"
                    ],

                "reason":
                    "PHYSICAL_WINDOW_ALREADY_USED",
            }
        )


    unique.sort(
        key=lambda row: (
            int(
                row[
                    "facade_number"
                ]
            ),
            int(
                row[
                    "floor_order"
                ]
            ),
            float(
                row[
                    "plan_relative_center"
                ]
            ),
        )
    )



    unique, _cad3d_bottom_frame_refinements = _bottom_frame_consensus_v5(
        raw,
        full_geometry,
        unique,
    )

    unique, _cad3d_pattern_completed = _complete_repeated_facade_windows_v4(
        raw,
        plan_facades,
        full_geometry,
        unique,
        audit_facades,
    )

    unique, _cad3d_outer_frame_promotions = _promote_outer_frames_v6(
        raw,
        full_geometry,
        unique,
    )

    return (
        unique,
        unresolved,
        audit_facades,
    )


# ============================================================
# BUTTON
# ============================================================

def run_facade_window_button(
    window,
):
    """
    ONE BUTTON ONLY.

    No floor-selection state.
    No floor confirmation.
    No floor assignment.
    No 3D creation.
    No Max sender.
    """

    from cad._cad_to_3d_max_rooms_exact.facade_matcher import (
        auto_analyse_dwg_facades,
    )

    from cad._cad_to_3d_max_rooms_exact.plan_guided_facade_windows import (
        build_multi_floor_plan_facades,
    )


    cad_data = (
        getattr(
            window,
            "cad_data",
            None,
        )
        or getattr(
            window.preview,
            "cad_data",
            None,
        )
    )


    if not isinstance(
        cad_data,
        dict,
    ):
        raise RuntimeError(
            "DWG verisi yok."
        )


    full_geometry = list(
        cad_data.get(
            "geometry",
            [],
        )
        or []
    )


    if not full_geometry:
        raise RuntimeError(
            "DWG geometrisi bos."
        )


    # --------------------------------------------------------
    # 1. RAW BUILDING/FACADE REGISTRATION
    # --------------------------------------------------------

    raw = (
        auto_analyse_dwg_facades(
            full_geometry
        )
    )


    # --------------------------------------------------------
    # 2. AUTOMATIC PLAN REGIONS
    # --------------------------------------------------------

    plan_regions = (
        _select_plan_regions(
            raw
        )
    )


    # --------------------------------------------------------
    # 3. SAME PLAN WINDOW DETECTOR USED BY 3D PIPELINE
    # --------------------------------------------------------

    packages, plan_report = (
        _detect_exact_plan_windows(
            window,
            plan_regions,
        )
    )


    plan_source = (
        build_multi_floor_plan_facades(
            packages
        )
    )


    plan_facades = list(
        plan_source.get(
            "plan_facades",
            [],
        )
        or []
    )


    # --------------------------------------------------------
    # 4. DIRECT CAD FACADE SEARCH
    #
    # Does NOT require RAW detector to call the entity a
    # "window".
    #
    # Does NOT have the old ground-floor-only restriction.
    # --------------------------------------------------------

    (
        accepted,
        unresolved,
        direct_audit,
    ) = (
        _resolve_direct_facade_windows(
            raw,
            plan_facades,
            full_geometry,
        )
    )


    result = deepcopy(
        raw
    )


    result[
        "plan_facades"
    ] = deepcopy(
        plan_facades
    )


    result[
        "plan_window_source"
    ] = {
        "engine":
            ENGINE,

        "source":
            "SAME_DETECT_WINDOWS_PLUS_CONTEXT",

        "source_window_count":
            int(
                plan_source.get(
                    "source_window_count",
                    0,
                )
            ),

        "mapped_window_count":
            int(
                plan_source.get(
                    "mapped_window_count",
                    0,
                )
            ),

        "rooflight_count":
            int(
                plan_source.get(
                    "rooflight_count",
                    0,
                )
            ),

        "floors":
            deepcopy(
                plan_source.get(
                    "floor_rows",
                    [],
                )
            ),
    }


    result[
        "plan_guided_facade_windows"
    ] = (
        accepted
    )


    result[
        "plan_guided_unresolved_windows"
    ] = (
        unresolved
    )


    result[
        "plan_guided_applied"
    ] = True


    result[
        "facade_window_button_engine"
    ] = ENGINE


    result[
        "direct_geometry_audit"
    ] = (
        direct_audit
    )


    source_count = sum(
        len(
            package.get(
                "windows",
                [],
            )
            or []
        )

        for package
        in packages
    )


    result[
        "plan_guided_summary"
    ] = {
        "engine":
            ENGINE,

        "source_plan_windows":
            source_count,

        "accepted":
            len(
                accepted
            ),

        "unresolved":
            len(
                unresolved
            ),

        "complete":
            bool(
                source_count > 0
                and len(
                    accepted
                )
                == source_count
            ),
    }


    # --------------------------------------------------------
    # LOGS
    # --------------------------------------------------------

    log_dir = (
        Path(__file__)
        .resolve()
        .parents[2]
        / "logs"
    )

    log_dir.mkdir(
        parents=True,
        exist_ok=True,
    )


    raw_path = (
        log_dir
        / "facade_windows_button_RAW.json"
    )

    plan_path = (
        log_dir
        / "facade_windows_button_PLAN_WINDOWS.json"
    )

    direct_path = (
        log_dir
        / "facade_windows_button_DIRECT_AUDIT.json"
    )

    result_path = (
        log_dir
        / "facade_windows_button_RESULT.json"
    )


    raw_path.write_text(
        json.dumps(
            raw,
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )


    plan_path.write_text(
        json.dumps(
            {
                "engine":
                    ENGINE,

                "plan_regions":
                    [
                        {
                            "region_id":
                                row.get(
                                    "region_id"
                                ),

                            "bbox":
                                row.get(
                                    "bbox"
                                ),

                            "semantic_count":
                                row.get(
                                    "semantic_count"
                                ),

                            "furniture_count":
                                row.get(
                                    "furniture_count"
                                ),
                        }

                        for row
                        in plan_regions
                    ],

                "plans":
                    plan_report,

                "total_windows":
                    source_count,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )


    direct_path.write_text(
        json.dumps(
            {
                "engine":
                    ENGINE,

                "facades":
                    direct_audit,

                "accepted":
                    accepted,

                "unresolved":
                    unresolved,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )


    result_path.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )


    print("")
    print(
        "=== CEPHE PENCERELERI DIRECT V2 ==="
    )

    print(
        "PLAN WINDOWS:",
        source_count,
    )

    print(
        "ACCEPTED FACADE WINDOWS:",
        len(
            accepted
        ),
    )

    print(
        "UNRESOLVED:",
        len(
            unresolved
        ),
    )

    print("")


    for facade in direct_audit:

        print(
            "FACADE",
            facade[
                "facade_number"
            ],
            "|",
            facade[
                "plan_side"
            ],
            "| PLAN:",
            facade[
                "plan_window_count"
            ],
            "| STRUCTURAL:",
            facade[
                "raw_structural_candidate_count"
            ],
            "| PLAUSIBLE:",
            facade[
                "plan_plausible_candidate_count"
            ],
        )


        for floor in facade[
            "floors"
        ]:

            print(
                "   FLOOR",
                floor[
                    "floor_order"
                ],
                "| PLAN:",
                floor[
                    "plan_count"
                ],
                "| CAND:",
                floor[
                    "candidate_count"
                ],
                "| MATCH:",
                floor[
                    "matched_count"
                ],
            )


    if unresolved:

        print("")
        print(
            "--- UNRESOLVED ---"
        )

        for row in unresolved:

            print(
                "FACADE",
                row.get(
                    "facade_number"
                ),
                "|",
                row.get(
                    "plan_side"
                ),
                "| FLOOR",
                row.get(
                    "floor_order"
                ),
                "|",
                row.get(
                    "source_window_id"
                ),
                "| WIDTH",
                row.get(
                    "plan_width"
                ),
                "|",
                row.get(
                    "reason"
                ),
            )


    print("")
    print(
        "DIRECT AUDIT:",
        direct_path,
    )

    print(
        "RESULT      :",
        result_path,
    )

    print(
        "=== END CEPHE PENCERELERI DIRECT V2 ==="
    )

    print("")


    return result


# ============================================================
# SYNTHETIC CHECK
# ============================================================

def _rect(
    x0,
    y0,
    x1,
    y1,
):
    return {
        "layer":
            "TEST",

        "points": [
            (
                x0,
                y0,
            ),
            (
                x1,
                y0,
            ),
            (
                x1,
                y1,
            ),
            (
                x0,
                y1,
            ),
            (
                x0,
                y0,
            ),
        ],
    }


def self_test():
    geometry = [
        _rect(
            1000.0,
            800.0,
            2200.0,
            2300.0,
        ),
        _rect(
            7000.0,
            800.0,
            8200.0,
            2300.0,
        ),
        _rect(
            1500.0,
            3900.0,
            2700.0,
            5400.0,
        ),
        _rect(
            6500.0,
            3900.0,
            7700.0,
            5400.0,
        ),
    ]


    candidates = (
        _build_all_storey_candidates(
            geometry,
            (
                0.0,
                0.0,
                10000.0,
                7000.0,
            ),
            [
                1200.0,
            ],
        )
    )


    if len(
        candidates
    ) < 4:

        raise AssertionError(
            "ALL STOREY candidate test failed: "
            + repr(
                candidates
            )
        )


    plausible = [
        row
        for row in candidates
        if abs(
            row[
                "width"
            ]
            - 1200.0
        )
        <= 1.0
    ]


    levels = (
        _cluster_y_levels(
            plausible,
            [
                0,
                1,
            ],
        )
    )


    floor_counts = {
        0: 0,
        1: 0,
    }


    for index, floor in (
        levels.items()
    ):

        floor_counts[
            floor
        ] = (
            floor_counts.get(
                floor,
                0,
            )
            + 1
        )


    if (
        floor_counts.get(
            0,
            0
        )
        < 2
        or
        floor_counts.get(
            1,
            0
        )
        < 2
    ):

        raise AssertionError(
            "STOREY cluster test failed: "
            + repr(
                floor_counts
            )
        )


    print(
        "FACADE DIRECT V2 SELF TEST: PASS"
    )

    print(
        "Candidates:",
        len(
            candidates
        ),
        "| floor counts:",
        floor_counts,
    )


if __name__ == "__main__":
    self_test()


# ============================================================
# CAD3D_FACADE_REPETITION_COMPLETION_V4
# ============================================================

def _median_v4(values):
    values = sorted(
        float(v)
        for v in values
    )

    if not values:
        return 0.0

    n = len(values)
    m = n // 2

    if n % 2:
        return values[m]

    return (
        values[m - 1]
        + values[m]
    ) * 0.5



# ============================================================
# CAD3D_BOTTOM_FRAME_CONSENSUS_V5
# ============================================================

def _bottom_frame_consensus_v5(
    raw,
    full_geometry,
    accepted,
):
    """
    Correct ONLY a bad lower window-frame boundary.

    Existing physical window selection is preserved.

    A correction is allowed only when:
      - same facade + same floor,
      - at least 3 dimensionally equivalent trusted windows,
      - strict majority agrees on the same bottom level,
      - current window is the outlier,
      - majority level is a real CAD horizontal line spanning
        the selected window.

    No top boundary is changed.
    No window identity is changed.
    No new window is created here.
    """

    from cad._cad_to_3d_max_rooms_exact.elevation_opening_detector import (
        _horizontal_coverage,
    )

    result = list(
        accepted
        or []
    )

    elevation_by_number = {}

    for facade in (
        raw.get(
            "elevation_facades",
            [],
        )
        or []
    ):
        try:
            number = int(
                facade.get(
                    "facade_number"
                )
            )
        except Exception:
            continue

        elevation_by_number[
            number
        ] = facade


    changes = []


    group_keys = sorted(
        set(
            (
                int(
                    row.get(
                        "facade_number",
                        -1,
                    )
                ),
                int(
                    row.get(
                        "floor_order",
                        -1,
                    )
                ),
            )
            for row in result
            if (
                bool(
                    row.get(
                        "plan_guided",
                        False,
                    )
                )
                and
                not bool(
                    row.get(
                        "pattern_completed",
                        False,
                    )
                )
            )
        )
    )


    for facade_number, floor_order in group_keys:

        facade = elevation_by_number.get(
            facade_number
        )

        if facade is None:
            continue

        facade_bounds = _bbox(
            facade.get(
                "bbox"
            )
        )

        if facade_bounds is None:
            continue


        horizontal, _vertical = (
            _extract_facade_axis_lines(
                full_geometry,
                facade_bounds,
            )
        )


        floor_rows = [
            row
            for row in result
            if (
                int(
                    row.get(
                        "facade_number",
                        -1,
                    )
                )
                == facade_number
                and
                int(
                    row.get(
                        "floor_order",
                        -1,
                    )
                )
                == floor_order
                and
                bool(
                    row.get(
                        "plan_guided",
                        False,
                    )
                )
                and
                not bool(
                    row.get(
                        "pattern_completed",
                        False,
                    )
                )
            )
        ]


        # ----------------------------------------------------
        # Build same-width window families.
        # ----------------------------------------------------

        width_groups = []


        for row in floor_rows:

            plan_width = float(
                row.get(
                    "plan_width",
                    0.0,
                )
                or 0.0
            )

            if plan_width <= 0.0:
                continue


            destination = None


            for group in width_groups:

                reference = sum(
                    float(
                        member.get(
                            "plan_width",
                            0.0,
                        )
                        or 0.0
                    )
                    for member in group
                ) / len(group)


                if (
                    abs(
                        plan_width
                        - reference
                    )
                    / max(
                        reference,
                        1.0e-9,
                    )
                    <= 0.025
                ):
                    destination = group
                    break


            if destination is None:

                destination = []

                width_groups.append(
                    destination
                )


            destination.append(
                row
            )


        for group in width_groups:

            # Strict majority means at least 3 comparable
            # windows are required.
            if len(group) < 3:
                continue


            heights = sorted(
                float(
                    row.get(
                        "elevation_height",
                        0.0,
                    )
                    or 0.0
                )
                for row in group
                if float(
                    row.get(
                        "elevation_height",
                        0.0,
                    )
                    or 0.0
                )
                > 0.0
            )

            if not heights:
                continue


            median_height = heights[
                len(heights) // 2
            ]


            level_tolerance = max(
                7.0,
                median_height * 0.006,
            )


            # ------------------------------------------------
            # Cluster existing bottom levels.
            # ------------------------------------------------

            clusters = []


            for row in sorted(
                group,
                key=lambda item:
                    float(
                        item.get(
                            "elevation_bottom_y",
                            0.0,
                        )
                    ),
            ):

                level = float(
                    row.get(
                        "elevation_bottom_y",
                        0.0,
                    )
                )


                destination = None


                for cluster in clusters:

                    mean = sum(
                        item[
                            "level"
                        ]
                        for item
                        in cluster
                    ) / len(cluster)


                    if abs(
                        level - mean
                    ) <= level_tolerance:

                        destination = cluster
                        break


                if destination is None:

                    destination = []

                    clusters.append(
                        destination
                    )


                destination.append(
                    {
                        "row":
                            row,

                        "level":
                            level,
                    }
                )


            if not clusters:
                continue


            clusters.sort(
                key=len,
                reverse=True,
            )


            winner = clusters[0]


            # Must be STRICT majority.
            if len(winner) <= (
                len(group) / 2.0
            ):
                continue


            target_bottom = sum(
                item[
                    "level"
                ]
                for item in winner
            ) / len(winner)


            for row in group:

                old_bottom = float(
                    row.get(
                        "elevation_bottom_y",
                        0.0,
                    )
                )

                old_top = float(
                    row.get(
                        "elevation_top_y",
                        0.0,
                    )
                )


                delta = abs(
                    old_bottom
                    - target_bottom
                )


                # Already belongs to majority cluster.
                if delta <= (
                    level_tolerance
                    * 1.25
                ):
                    continue


                # Never allow a large vertical jump.
                if delta > (
                    median_height
                    * 0.08
                ):
                    continue


                box = list(
                    row.get(
                        "elevation_bbox",
                        [],
                    )
                    or []
                )

                if len(box) != 4:
                    continue


                x0 = float(
                    box[0]
                )

                x1 = float(
                    box[2]
                )


                # Majority level must physically exist across
                # this exact window.
                coverage = (
                    _horizontal_coverage(
                        horizontal,
                        target_bottom,
                        x0,
                        x1,
                        level_tolerance,
                    )
                )


                if coverage < 0.90:
                    continue


                if old_top <= target_bottom:
                    continue


                old_bbox = list(
                    box
                )


                box[1] = float(
                    target_bottom
                )


                row[
                    "elevation_bbox"
                ] = box


                row[
                    "elevation_bottom_y"
                ] = float(
                    target_bottom
                )


                row[
                    "elevation_height"
                ] = (
                    old_top
                    - target_bottom
                )


                row[
                    "elevation_center"
                ] = [
                    (
                        x0 + x1
                    ) * 0.5,
                    (
                        target_bottom
                        + old_top
                    ) * 0.5,
                ]


                row[
                    "bottom_frame_refined"
                ] = True


                row[
                    "bottom_frame_rule"
                ] = (
                    "SAME_WIDTH_STRICT_MAJORITY_"
                    "REAL_HORIZONTAL_LINE_V5"
                )


                changes.append(
                    {
                        "facade_number":
                            facade_number,

                        "floor_order":
                            floor_order,

                        "source_window_id":
                            row.get(
                                "source_window_id"
                            ),

                        "old_bbox":
                            old_bbox,

                        "new_bbox":
                            list(
                                box
                            ),

                        "old_bottom":
                            old_bottom,

                        "new_bottom":
                            float(
                                target_bottom
                            ),

                        "horizontal_coverage":
                            float(
                                coverage
                            ),
                    }
                )


                print(
                    "BOTTOM FRAME REFINED"
                    f" | FACADE {facade_number}"
                    f" | FLOOR {floor_order}"
                    f" | {row.get('source_window_id')}"
                    f" | {old_bottom:.3f}"
                    f" -> {target_bottom:.3f}"
                    f" | COVERAGE {coverage:.3f}"
                )


    print(
        "BOTTOM FRAME REFINEMENTS:",
        len(
            changes
        ),
    )


    return (
        result,
        changes,
    )


def _complete_repeated_facade_windows_v4(
    raw,
    plan_facades,
    full_geometry,
    accepted,
    audit_facades,
):
    """
    Preserve every existing plan-guided winner.

    Add a facade-only physical window ONLY when:
      - same floor already has >= 2 trusted accepted windows,
      - accepted windows form one uniform dimensional family,
      - there is an abnormally large gap between adjacent winners,
      - an unused physical family exists near the exact midpoint,
      - width/height/Y-level match the trusted neighbours,
      - jamb/cap support and geometric score are strong.

    This is deliberately NOT a general facade heuristic.
    It is a missing-member detector for proven repetitive window rows.
    """

    result = list(accepted or [])
    additions = []

    elevation_by_number = {}

    for facade in (
        raw.get("elevation_facades", [])
        or []
    ):
        try:
            number = int(
                facade.get("facade_number")
            )
        except Exception:
            continue

        elevation_by_number[number] = facade


    plan_by_side = {}

    for plan_facade in (
        plan_facades
        or []
    ):
        side = str(
            plan_facade.get("side", "")
            or ""
        ).strip().lower()

        if side:
            plan_by_side[side] = plan_facade


    for facade_audit in (
        audit_facades
        or []
    ):
        try:
            facade_number = int(
                facade_audit.get(
                    "facade_number"
                )
            )
        except Exception:
            continue

        side = str(
            facade_audit.get(
                "plan_side",
                ""
            )
            or ""
        ).strip().lower()

        facade = elevation_by_number.get(
            facade_number
        )

        if facade is None:
            continue

        facade_bounds = _bbox(
            facade.get("bbox")
        )

        if facade_bounds is None:
            continue

        plan_facade = plan_by_side.get(
            side,
            {}
        )

        expected_widths = []

        for row in (
            plan_facade.get(
                "openings",
                []
            )
            or []
        ):
            try:
                width = float(
                    row.get("width", 0.0)
                    or 0.0
                )
            except Exception:
                continue

            if width > 0.0:
                expected_widths.append(
                    width
                )

        if not expected_widths:
            continue


        candidates = _build_all_storey_candidates(
            full_geometry,
            facade_bounds,
            expected_widths,
        )

        families = _physical_candidate_families(
            candidates,
            facade_bounds,
        )

        used_family_ids = set()

        for row in result:
            if (
                int(
                    row.get(
                        "facade_number",
                        -1
                    )
                )
                != facade_number
            ):
                continue

            family_id = row.get(
                "physical_family_id"
            )

            if family_id is not None:
                try:
                    used_family_ids.add(
                        int(family_id)
                    )
                except Exception:
                    pass


        facade_additions = []

        for floor_audit in (
            facade_audit.get(
                "floors",
                []
            )
            or []
        ):
            try:
                floor_order = int(
                    floor_audit.get(
                        "floor_order",
                        0
                    )
                    or 0
                )
            except Exception:
                continue


            trusted = [
                row
                for row in result
                if (
                    int(
                        row.get(
                            "facade_number",
                            -1
                        )
                    )
                    == facade_number
                    and
                    int(
                        row.get(
                            "floor_order",
                            -1
                        )
                    )
                    == floor_order
                    and
                    not bool(
                        row.get(
                            "pattern_completed",
                            False
                        )
                    )
                )
            ]


            if len(trusted) < 2:
                continue


            trusted.sort(
                key=lambda row:
                    float(
                        row.get(
                            "elevation_center",
                            [0.0, 0.0]
                        )[0]
                    )
            )


            widths = [
                float(
                    row[
                        "elevation_width"
                    ]
                )
                for row in trusted
                if float(
                    row.get(
                        "elevation_width",
                        0.0
                    )
                    or 0.0
                ) > 0.0
            ]

            heights = [
                float(
                    row[
                        "elevation_height"
                    ]
                )
                for row in trusted
                if float(
                    row.get(
                        "elevation_height",
                        0.0
                    )
                    or 0.0
                ) > 0.0
            ]

            centers_y = [
                float(
                    row[
                        "elevation_center"
                    ][1]
                )
                for row in trusted
            ]


            if (
                len(widths) < 2
                or
                len(heights) < 2
            ):
                continue


            median_width = _median_v4(
                widths
            )

            median_height = _median_v4(
                heights
            )

            median_y = _median_v4(
                centers_y
            )


            if (
                median_width <= 0.0
                or
                median_height <= 0.0
            ):
                continue


            # ------------------------------------------------
            # Missing-member completion is allowed only for
            # genuinely repetitive / same-type rows.
            # ------------------------------------------------

            width_uniformity = (
                max(widths)
                / max(
                    min(widths),
                    1.0e-9
                )
            )

            height_uniformity = (
                max(heights)
                / max(
                    min(heights),
                    1.0e-9
                )
            )


            if width_uniformity > 1.12:
                continue

            if height_uniformity > 1.12:
                continue


            floor_additions = []


            for left, right in zip(
                trusted[:-1],
                trusted[1:],
            ):
                left_x = float(
                    left[
                        "elevation_center"
                    ][0]
                )

                right_x = float(
                    right[
                        "elevation_center"
                    ][0]
                )

                gap = (
                    right_x
                    - left_x
                )


                # Normal neighbouring windows in this drawing
                # are around 2.5-3.0 window-widths apart.
                #
                # A missing central dormer produces a gap
                # slightly above 5 window-widths.
                if gap < (
                    median_width
                    * 4.15
                ):
                    continue


                target_x = (
                    left_x
                    + right_x
                ) * 0.5


                best = None


                for family in families:
                    family_id = int(
                        family.get(
                            "family_id",
                            -1
                        )
                    )

                    if family_id in used_family_ids:
                        continue

                    variants = list(
                        family.get(
                            "variants",
                            []
                        )
                        or []
                    )

                    family_size = len(
                        variants
                    )


                    # True simple dormer windows in this DWG
                    # currently appear as compact physical
                    # families, not giant nested groups.
                    if (
                        family_size < 2
                        or
                        family_size > 10
                    ):
                        continue


                    for candidate in variants:
                        try:
                            cx = float(
                                candidate[
                                    "center"
                                ][0]
                            )

                            cy = float(
                                candidate[
                                    "center"
                                ][1]
                            )

                            cw = float(
                                candidate[
                                    "width"
                                ]
                            )

                            ch = float(
                                candidate[
                                    "height"
                                ]
                            )
                        except Exception:
                            continue


                        if not (
                            left_x
                            < cx
                            < right_x
                        ):
                            continue


                        width_error = (
                            abs(
                                cw
                                - median_width
                            )
                            / median_width
                        )

                        height_error = (
                            abs(
                                ch
                                - median_height
                            )
                            / median_height
                        )

                        y_error = (
                            abs(
                                cy
                                - median_y
                            )
                            / median_height
                        )

                        midpoint_error = (
                            abs(
                                cx
                                - target_x
                            )
                            / median_width
                        )


                        if width_error > 0.08:
                            continue

                        if height_error > 0.10:
                            continue

                        if y_error > 0.16:
                            continue

                        if midpoint_error > 0.45:
                            continue


                        bottom_support = float(
                            candidate.get(
                                "bottom_support",
                                0.0
                            )
                            or 0.0
                        )

                        top_support = float(
                            candidate.get(
                                "top_support",
                                0.0
                            )
                            or 0.0
                        )

                        geometric_score = float(
                            candidate.get(
                                "geometric_score",
                                0.0
                            )
                            or 0.0
                        )


                        if bottom_support < 0.95:
                            continue

                        if top_support < 0.95:
                            continue

                        if geometric_score < 5.45:
                            continue


                        candidate_bbox = tuple(
                            candidate[
                                "bbox"
                            ]
                        )


                        overlaps_existing = False

                        for existing in result:
                            if (
                                int(
                                    existing.get(
                                        "facade_number",
                                        -1
                                    )
                                )
                                != facade_number
                                or
                                int(
                                    existing.get(
                                        "floor_order",
                                        -1
                                    )
                                )
                                != floor_order
                            ):
                                continue

                            existing_bbox = tuple(
                                existing.get(
                                    "elevation_bbox",
                                    ()
                                )
                            )

                            if len(
                                existing_bbox
                            ) != 4:
                                continue

                            if (
                                _bbox_iou(
                                    candidate_bbox,
                                    existing_bbox,
                                )
                                >= 0.20
                            ):
                                overlaps_existing = True
                                break


                        if overlaps_existing:
                            continue


                        cost = (
                            width_error * 12.0
                            +
                            height_error * 8.0
                            +
                            y_error * 6.0
                            +
                            midpoint_error * 10.0
                            -
                            min(
                                geometric_score,
                                8.0
                            )
                            * 0.03
                        )


                        rank = (
                            float(cost),
                            float(midpoint_error),
                            float(width_error),
                            float(height_error),
                            -_area(
                                candidate_bbox
                            ),
                        )


                        if (
                            best is None
                            or
                            rank < best["rank"]
                        ):
                            best = {
                                "rank":
                                    rank,

                                "family_id":
                                    family_id,

                                "family_size":
                                    family_size,

                                "candidate":
                                    candidate,

                                "width_error":
                                    width_error,

                                "height_error":
                                    height_error,

                                "y_error":
                                    y_error,

                                "midpoint_error":
                                    midpoint_error,

                                "cost":
                                    cost,
                            }


                if best is None:
                    continue


                candidate = best[
                    "candidate"
                ]

                cx = float(
                    candidate[
                        "center"
                    ][0]
                )

                cy = float(
                    candidate[
                        "center"
                    ][1]
                )

                bbox = tuple(
                    candidate[
                        "bbox"
                    ]
                )


                reversed_order = bool(
                    facade_audit.get(
                        "chosen_reversed",
                        False
                    )
                )

                relative_center = (
                    _candidate_relative_center(
                        candidate,
                        facade_bounds,
                        reversed_order,
                    )
                )


                record = {
                    "kind":
                        "window",

                    "facade_number":
                        facade_number,

                    "plan_side":
                        side,

                    "floor_order":
                        floor_order,

                    "floor_name":
                        (
                            trusted[0].get(
                                "floor_name",
                                ""
                            )
                            or ""
                        ),

                    # No fake plan-window identity is created.
                    "source_window_index":
                        -1,

                    "source_window_id":
                        (
                            f"FACADE_PATTERN_"
                            f"F{facade_number}_"
                            f"L{floor_order}_"
                            f"{len(additions)+1:02d}"
                        ),

                    "plan_center":
                        None,

                    # dimensional reference inherited only
                    # from already verified neighbouring
                    # windows on the same facade/storey
                    "plan_width":
                        median_width,

                    "plan_relative_center":
                        float(
                            relative_center
                        ),

                    "elevation_bbox":
                        [
                            float(v)
                            for v in bbox
                        ],

                    "elevation_center":
                        [
                            cx,
                            cy,
                        ],

                    "elevation_width":
                        float(
                            candidate[
                                "width"
                            ]
                        ),

                    "elevation_height":
                        float(
                            candidate[
                                "height"
                            ]
                        ),

                    "elevation_bottom_y":
                        float(
                            candidate[
                                "bottom_y"
                            ]
                        ),

                    "elevation_top_y":
                        float(
                            candidate[
                                "top_y"
                            ]
                        ),

                    "width_error_ratio":
                        float(
                            best[
                                "width_error"
                            ]
                        ),

                    "position_error_ratio":
                        float(
                            best[
                                "midpoint_error"
                            ]
                        ),

                    "selection_cost":
                        float(
                            best[
                                "cost"
                            ]
                        ),

                    "physical_family_id":
                        int(
                            best[
                                "family_id"
                            ]
                        ),

                    "physical_family_size":
                        int(
                            best[
                                "family_size"
                            ]
                        ),

                    "bottom_support":
                        float(
                            candidate.get(
                                "bottom_support",
                                0.0
                            )
                            or 0.0
                        ),

                    "top_support":
                        float(
                            candidate.get(
                                "top_support",
                                0.0
                            )
                            or 0.0
                        ),

                    "geometric_score":
                        float(
                            candidate.get(
                                "geometric_score",
                                0.0
                            )
                            or 0.0
                        ),

                    "facade_reversed":
                        reversed_order,

                    "orientation_reason":
                        facade_audit.get(
                            "orientation_reason",
                            ""
                        ),

                    # Important:
                    # existing plan-guided selections remain
                    # untouched and retain priority.
                    "plan_guided":
                        False,

                    "pattern_completed":
                        True,

                    "pattern_rule":
                        "UNIFORM_ROW_MISSING_MID_MEMBER_V4",

                    "direct_geometry":
                        True,

                    "candidate_source":
                        "RAW_CAD_REPETITION_COMPLETION_V4",

                    # Detection is being verified now.
                    # Do not silently feed this new facade-only
                    # item into sill-height execution yet.
                    "height_eligible":
                        False,
                }


                result.append(
                    record
                )

                additions.append(
                    record
                )

                floor_additions.append(
                    record
                )

                facade_additions.append(
                    record
                )

                used_family_ids.add(
                    int(
                        best[
                            "family_id"
                        ]
                    )
                )


                print(
                    "FACADE PATTERN COMPLETION"
                    f" | FACADE {facade_number}"
                    f" | FLOOR {floor_order}"
                    f" | X {cx:.3f}"
                    f" | W {record['elevation_width']:.3f}"
                    f" | H {record['elevation_height']:.3f}"
                    f" | MID ERR {best['midpoint_error']*100.0:.2f}%"
                    f" | WIDTH ERR {best['width_error']*100.0:.2f}%"
                )


            floor_audit[
                "pattern_completed_count"
            ] = len(
                floor_additions
            )

            floor_audit[
                "pattern_completed"
            ] = floor_additions


        facade_audit[
            "pattern_completed_count"
        ] = len(
            facade_additions
        )

        facade_audit[
            "pattern_completed"
        ] = facade_additions


    result.sort(
        key=lambda row: (
            int(
                row.get(
                    "facade_number",
                    0
                )
                or 0
            ),
            int(
                row.get(
                    "floor_order",
                    0
                )
                or 0
            ),
            float(
                (
                    row.get(
                        "elevation_center"
                    )
                    or [0.0, 0.0]
                )[0]
            ),
        )
    )


    print("")
    print(
        "PATTERN COMPLETED WINDOWS:",
        len(additions),
    )
    print("")


    return (
        result,
        additions,
    )


# ============================================================
# CAD3D_OUTER_FRAME_PROMOTION_V6
# ============================================================

def _median_outer_v6(values):
    values = sorted(float(v) for v in values)

    if not values:
        return 0.0

    n = len(values)

    if n % 2:
        return values[n // 2]

    return (
        values[n // 2 - 1]
        + values[n // 2]
    ) * 0.5


def _promote_outer_frames_v6(
    raw,
    full_geometry,
    accepted,
):
    """
    Fix INNER-FRAME selections without disturbing correct
    physical-window matches.

    Promotion is permitted only when:

      - row is already PLAN-guided;
      - current width error is > 5%;
      - at least two same-width sibling windows on the SAME
        facade/floor already match plan width within 2.5%;
      - those siblings agree on bottom/top frame level;
      - another real structural candidate exists at the SAME
        physical window location;
      - candidate width matches PLAN width within 3%;
      - candidate encloses the current inner frame;
      - candidate bottom/top match the trusted outer-frame row.

    Therefore this cannot jump to the dormer roof or another
    neighbouring window.
    """

    result = list(accepted or [])

    elevation_by_number = {}

    for facade in (
        raw.get("elevation_facades", [])
        or []
    ):
        try:
            number = int(
                facade.get("facade_number")
            )
        except Exception:
            continue

        elevation_by_number[number] = facade


    promotions = []


    group_keys = sorted(
        set(
            (
                int(row.get("facade_number", -1)),
                int(row.get("floor_order", -1)),
            )
            for row in result
            if (
                bool(row.get("plan_guided", False))
                and
                not bool(row.get("pattern_completed", False))
            )
        )
    )


    for facade_number, floor_order in group_keys:

        facade = elevation_by_number.get(
            facade_number
        )

        if facade is None:
            continue

        facade_bounds = _bbox(
            facade.get("bbox")
        )

        if facade_bounds is None:
            continue


        rows = [
            row
            for row in result
            if (
                int(row.get("facade_number", -1))
                == facade_number
                and
                int(row.get("floor_order", -1))
                == floor_order
                and
                bool(row.get("plan_guided", False))
                and
                not bool(row.get("pattern_completed", False))
            )
        ]


        width_groups = []


        for row in rows:

            plan_width = float(
                row.get("plan_width", 0.0)
                or 0.0
            )

            if plan_width <= 0.0:
                continue

            target = None

            for group in width_groups:

                reference = (
                    sum(
                        float(
                            item.get(
                                "plan_width",
                                0.0
                            )
                            or 0.0
                        )
                        for item in group
                    )
                    / len(group)
                )

                if (
                    abs(plan_width - reference)
                    / max(reference, 1.0e-9)
                    <= 0.025
                ):
                    target = group
                    break


            if target is None:
                target = []
                width_groups.append(target)


            target.append(row)


        for group in width_groups:

            if len(group) < 3:
                continue


            anchors = [
                row
                for row in group
                if float(
                    row.get(
                        "width_error_ratio",
                        1.0
                    )
                    or 0.0
                )
                <= 0.025
            ]


            if len(anchors) < 2:
                continue


            anchor_heights = [
                float(row["elevation_height"])
                for row in anchors
            ]

            target_height = _median_outer_v6(
                anchor_heights
            )

            target_bottom = _median_outer_v6(
                row["elevation_bottom_y"]
                for row in anchors
            )

            target_top = _median_outer_v6(
                row["elevation_top_y"]
                for row in anchors
            )


            if target_height <= 0.0:
                continue


            # Trusted siblings must themselves agree on one
            # physical outer-frame row.
            bottom_spread = (
                max(
                    float(row["elevation_bottom_y"])
                    for row in anchors
                )
                -
                min(
                    float(row["elevation_bottom_y"])
                    for row in anchors
                )
            )

            top_spread = (
                max(
                    float(row["elevation_top_y"])
                    for row in anchors
                )
                -
                min(
                    float(row["elevation_top_y"])
                    for row in anchors
                )
            )


            if bottom_spread > target_height * 0.035:
                continue

            if top_spread > target_height * 0.035:
                continue


            plan_width_reference = _median_outer_v6(
                row["plan_width"]
                for row in group
            )


            all_candidates = (
                _build_all_storey_candidates(
                    full_geometry,
                    facade_bounds,
                    [plan_width_reference],
                )
            )


            for row in group:

                old_width_error = float(
                    row.get(
                        "width_error_ratio",
                        0.0
                    )
                    or 0.0
                )


                # Correct matches are untouchable.
                if old_width_error <= 0.05:
                    continue


                old_bbox = tuple(
                    float(v)
                    for v in row[
                        "elevation_bbox"
                    ]
                )

                old_center = tuple(
                    float(v)
                    for v in row[
                        "elevation_center"
                    ]
                )

                plan_width = float(
                    row["plan_width"]
                )


                best = None


                for candidate in all_candidates:

                    candidate_bbox = tuple(
                        float(v)
                        for v in candidate[
                            "bbox"
                        ]
                    )

                    candidate_center = tuple(
                        float(v)
                        for v in candidate[
                            "center"
                        ]
                    )

                    candidate_width = float(
                        candidate[
                            "width"
                        ]
                    )


                    width_error = (
                        abs(
                            candidate_width
                            - plan_width
                        )
                        / plan_width
                    )


                    if width_error > 0.03:
                        continue


                    center_error = (
                        abs(
                            candidate_center[0]
                            - old_center[0]
                        )
                        / plan_width
                    )


                    if center_error > 0.12:
                        continue


                    bottom_error = (
                        abs(
                            candidate_bbox[1]
                            - target_bottom
                        )
                        / target_height
                    )

                    top_error = (
                        abs(
                            candidate_bbox[3]
                            - target_top
                        )
                        / target_height
                    )


                    if bottom_error > 0.055:
                        continue

                    if top_error > 0.055:
                        continue


                    # Candidate must be an OUTER frame around
                    # the currently selected inner frame.
                    x_margin = plan_width * 0.035
                    y_margin = target_height * 0.035


                    if (
                        candidate_bbox[0]
                        >
                        old_bbox[0] + x_margin
                    ):
                        continue

                    if (
                        candidate_bbox[2]
                        <
                        old_bbox[2] - x_margin
                    ):
                        continue

                    if (
                        candidate_bbox[1]
                        >
                        old_bbox[1] + y_margin
                    ):
                        continue

                    if (
                        candidate_bbox[3]
                        <
                        old_bbox[3] - y_margin
                    ):
                        continue


                    bottom_support = float(
                        candidate.get(
                            "bottom_support",
                            0.0
                        )
                        or 0.0
                    )

                    top_support = float(
                        candidate.get(
                            "top_support",
                            0.0
                        )
                        or 0.0
                    )


                    if bottom_support < 0.90:
                        continue

                    if top_support < 0.90:
                        continue


                    score = (
                        width_error * 20.0
                        +
                        center_error * 8.0
                        +
                        bottom_error * 6.0
                        +
                        top_error * 6.0
                    )


                    rank = (
                        score,
                        width_error,
                        center_error,
                        bottom_error + top_error,
                        -_area(candidate_bbox),
                    )


                    if (
                        best is None
                        or rank < best["rank"]
                    ):

                        best = {
                            "candidate":
                                candidate,

                            "rank":
                                rank,

                            "width_error":
                                width_error,

                            "center_error":
                                center_error,

                            "bottom_error":
                                bottom_error,

                            "top_error":
                                top_error,
                        }


                if best is None:

                    print(
                        "OUTER FRAME NOT FOUND"
                        f" | FACADE {facade_number}"
                        f" | FLOOR {floor_order}"
                        f" | {row.get('source_window_id')}"
                        f" | CURRENT WIDTH ERR "
                        f"{old_width_error*100.0:.2f}%"
                    )

                    continue


                candidate = best[
                    "candidate"
                ]

                new_bbox = [
                    float(v)
                    for v in candidate[
                        "bbox"
                    ]
                ]


                new_width = float(
                    candidate[
                        "width"
                    ]
                )

                new_height = float(
                    candidate[
                        "height"
                    ]
                )


                row[
                    "outer_frame_original_bbox"
                ] = list(
                    old_bbox
                )

                row[
                    "elevation_bbox"
                ] = new_bbox

                row[
                    "elevation_center"
                ] = [
                    float(
                        candidate[
                            "center"
                        ][0]
                    ),
                    float(
                        candidate[
                            "center"
                        ][1]
                    ),
                ]

                row[
                    "elevation_width"
                ] = new_width

                row[
                    "elevation_height"
                ] = new_height

                row[
                    "elevation_bottom_y"
                ] = float(
                    candidate[
                        "bottom_y"
                    ]
                )

                row[
                    "elevation_top_y"
                ] = float(
                    candidate[
                        "top_y"
                    ]
                )

                row[
                    "width_error_ratio"
                ] = float(
                    best[
                        "width_error"
                    ]
                )

                row[
                    "bottom_support"
                ] = float(
                    candidate.get(
                        "bottom_support",
                        0.0
                    )
                    or 0.0
                )

                row[
                    "top_support"
                ] = float(
                    candidate.get(
                        "top_support",
                        0.0
                    )
                    or 0.0
                )

                row[
                    "geometric_score"
                ] = float(
                    candidate.get(
                        "geometric_score",
                        0.0
                    )
                    or 0.0
                )

                row[
                    "outer_frame_promoted"
                ] = True

                row[
                    "outer_frame_rule"
                ] = (
                    "PLAN_WIDTH_PLUS_TRUSTED_"
                    "SIBLING_FRAME_V6"
                )

                row[
                    "candidate_source"
                ] = (
                    "RAW_CAD_OUTER_FRAME_"
                    "PROMOTION_V6"
                )


                promotions.append(
                    {
                        "facade_number":
                            facade_number,

                        "floor_order":
                            floor_order,

                        "source_window_id":
                            row.get(
                                "source_window_id"
                            ),

                        "old_bbox":
                            list(
                                old_bbox
                            ),

                        "new_bbox":
                            list(
                                new_bbox
                            ),

                        "old_width_error":
                            old_width_error,

                        "new_width_error":
                            float(
                                best[
                                    "width_error"
                                ]
                            ),
                    }
                )


                print(
                    "OUTER FRAME PROMOTED"
                    f" | FACADE {facade_number}"
                    f" | FLOOR {floor_order}"
                    f" | {row.get('source_window_id')}"
                    f" | WIDTH ERR "
                    f"{old_width_error*100.0:.2f}%"
                    f" -> "
                    f"{best['width_error']*100.0:.2f}%"
                )


    print(
        "OUTER FRAME PROMOTIONS:",
        len(promotions),
    )


    return (
        result,
        promotions,
    )

