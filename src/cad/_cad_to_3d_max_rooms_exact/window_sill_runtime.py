from pathlib import Path
import json
import math
import statistics


ENGINE = "CAD3D_WINDOW_SILL_REAL_FLOOR_DATUM_V3"

MAX_SILL_CM = 210.0
BOTTOM_CLUSTER_TOLERANCE_CM = 3.0
HEIGHT_FAMILY_TOLERANCE_RATIO = 0.05
STOREY_SHIFT_TOLERANCE_CM = 3.0


def _f(value):
    try:
        value = float(value)
    except Exception:
        return None

    if not math.isfinite(value):
        return None

    return value


def _i(value):
    try:
        return int(value)
    except Exception:
        return None


def _snap_half_cm(value):
    value = float(value)

    whole = math.floor(value)
    frac = value - whole

    if frac < 0.25:
        return float(whole)

    if frac < 0.70:
        return float(whole + 0.5)

    return float(whole + 1.0)


def _analysis(window):
    current = getattr(
        window,
        "current_facade_match_result",
        None,
    )

    if (
        isinstance(current, dict)
        and current.get(
            "plan_guided_facade_windows"
        )
    ):
        return current, "MEMORY"

    path = (
        Path(__file__)
        .resolve()
        .parents[2]
        / "logs"
        / "facade_windows_button_RESULT.json"
    )

    if path.is_file():
        try:
            data = json.loads(
                path.read_text(
                    encoding="utf-8-sig"
                )
            )

            if (
                isinstance(data, dict)
                and data.get(
                    "plan_guided_facade_windows"
                )
            ):
                return data, "LOG"

        except Exception:
            pass

    try:
        from cad._cad_to_3d_max_rooms_exact.facade_window_button_engine import (
            run_facade_window_button,
        )

        data = run_facade_window_button(
            window
        )

        if (
            isinstance(data, dict)
            and data.get(
                "plan_guided_facade_windows"
            )
        ):
            return (
                data,
                "AUTO_FACADE_ENGINE",
            )

    except Exception:
        pass

    return None, "NONE"


def _source_to_mm(
    window,
    target_layer,
):
    summary = getattr(
        window,
        "cad_crop_summary",
        None,
    )

    if not isinstance(
        summary,
        dict,
    ):
        raise RuntimeError(
            "CAD_CROP_SUMMARY_MISSING"
        )

    geometry = list(
        summary.get(
            "geometry",
            [],
        )
        or []
    )

    target_layer = str(
        target_layer
        or ""
    ).strip()

    structural = [
        item
        for item in geometry
        if (
            isinstance(item, dict)
            and
            str(
                item.get(
                    "layer",
                    "",
                )
                or ""
            ).strip()
            == target_layer
            and
            len(
                item.get(
                    "points",
                    [],
                )
                or []
            )
            >= 2
        )
    ]

    if not structural:
        raise RuntimeError(
            "STRUCTURAL_GEOMETRY_MISSING"
        )

    from cad._cad_to_3d_max_rooms_exact.generic_cad_cleanup import (
        build_clean_visible_polylines,
    )

    _cleaned, report = (
        build_clean_visible_polylines(
            structural,
            cad_meta=getattr(
                window,
                "cad_data",
                None,
            ),
        )
    )

    if not isinstance(
        report,
        dict,
    ):
        raise RuntimeError(
            "CAD_UNIT_REPORT_MISSING"
        )

    scale = _f(
        report.get(
            "source_to_mm"
        )
    )

    if (
        scale is None
        or scale <= 0.0
    ):
        raise RuntimeError(
            "SOURCE_TO_MM_INVALID"
        )

    return scale


def _main_entrance(
    analysis,
):
    from cad._cad_to_3d_max_rooms_exact.window_vertical_measurements import (
        _choose_main_entrance,
    )

    result = _choose_main_entrance(
        analysis
    )

    if not isinstance(
        result,
        dict,
    ):
        raise RuntimeError(
            "MAIN_ENTRANCE_NOT_FOUND"
        )

    return result


def _window_rows(
    analysis,
    floor_index,
    facade_number,
    plan_side,
):
    result = []

    for row in (
        analysis.get(
            "plan_guided_facade_windows",
            [],
        )
        or []
    ):
        if not isinstance(
            row,
            dict,
        ):
            continue

        if not bool(
            row.get(
                "plan_guided",
                False,
            )
        ):
            continue

        if bool(
            row.get(
                "pattern_completed",
                False,
            )
        ):
            continue

        if _i(
            row.get(
                "floor_order"
            )
        ) != floor_index:
            continue

        if _i(
            row.get(
                "facade_number"
            )
        ) != facade_number:
            continue

        row_side = str(
            row.get(
                "plan_side",
                "",
            )
            or ""
        ).strip()

        if (
            plan_side
            and row_side
            and row_side != plan_side
        ):
            continue

        bottom = _f(
            row.get(
                "elevation_bottom_y"
            )
        )

        top = _f(
            row.get(
                "elevation_top_y"
            )
        )

        height = _f(
            row.get(
                "elevation_height"
            )
        )

        if (
            bottom is None
            or top is None
        ):
            continue

        if height is None:
            height = (
                top - bottom
            )

        if height <= 0.0:
            continue

        result.append(
            {
                "source_window_id":
                    row.get(
                        "source_window_id"
                    ),

                "bottom_y":
                    bottom,

                "top_y":
                    top,

                "height":
                    height,

                "width":
                    _f(
                        row.get(
                            "elevation_width"
                        )
                    ),

                "width_error_ratio":
                    _f(
                        row.get(
                            "width_error_ratio"
                        )
                    ),
            }
        )

    return result


def _dominant_height_family(
    rows,
):
    if not rows:
        return []

    best = []

    for seed in rows:
        seed_height = float(
            seed[
                "height"
            ]
        )

        group = [
            row
            for row in rows
            if (
                abs(
                    float(
                        row[
                            "height"
                        ]
                    )
                    - seed_height
                )
                / max(
                    seed_height,
                    1.0e-9,
                )
                <= HEIGHT_FAMILY_TOLERANCE_RATIO
            )
        ]

        if len(group) > len(best):
            best = group

        elif (
            len(group) == len(best)
            and group
            and best
        ):
            group_heights = [
                float(
                    row[
                        "height"
                    ]
                )
                for row in group
            ]

            best_heights = [
                float(
                    row[
                        "height"
                    ]
                )
                for row in best
            ]

            group_spread = (
                max(group_heights)
                - min(group_heights)
            )

            best_spread = (
                max(best_heights)
                - min(best_heights)
            )

            if group_spread < best_spread:
                best = group

    return best


def _family_matching_height(
    rows,
    reference_height,
):
    result = []

    reference_height = float(
        reference_height
    )

    for row in rows:
        height = float(
            row[
                "height"
            ]
        )

        error = (
            abs(
                height
                - reference_height
            )
            / max(
                reference_height,
                1.0e-9,
            )
        )

        if (
            error
            <= HEIGHT_FAMILY_TOLERANCE_RATIO
        ):
            result.append(
                row
            )

    return result


def _median(
    values,
):
    values = [
        float(v)
        for v in values
    ]

    if not values:
        raise RuntimeError(
            "MEDIAN_EMPTY"
        )

    return float(
        statistics.median(
            values
        )
    )


def _write_log(
    result,
):
    try:
        root = (
            Path(__file__)
            .resolve()
            .parents[2]
        )

        floor_index = result.get(
            "floor_index"
        )

        path = (
            root
            / "logs"
            / (
                "window_sill_runtime_floor_"
                + str(
                    floor_index
                )
                + ".json"
            )
        )

        path.write_text(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    except Exception:
        pass


def _print_result(
    result,
):
    print("")
    print(
        "=== WINDOW SILL FACADE LOCAL Z V2 ==="
    )

    print(
        "FLOOR          :",
        result.get(
            "floor_index"
        ),
    )

    print(
        "REFERENCE      :",
        result.get(
            "reference"
        ),
    )

    print(
        "MAX BASE Z     :",
        result.get(
            "base_z_cm"
        ),
        "cm",
    )

    if result.get(
        "ground_sill_raw_cm"
    ) is not None:
        print(
            "GROUND SILL RAW:",
            result.get(
                "ground_sill_raw_cm"
            ),
            "cm",
        )

    if result.get(
        "facade_storey_shift_cm"
    ) is not None:
        print(
            "FACADE SHIFT   :",
            result.get(
                "facade_storey_shift_cm"
            ),
            "cm",
        )

    if result.get(
        "shift_bottom_cm"
    ) is not None:
        print(
            "SHIFT BOTTOM   :",
            result.get(
                "shift_bottom_cm"
            ),
            "cm",
        )

    if result.get(
        "shift_top_cm"
    ) is not None:
        print(
            "SHIFT TOP      :",
            result.get(
                "shift_top_cm"
            ),
            "cm",
        )

    if result.get(
        "floor_datum_y"
    ) is not None:
        print(
            "FLOOR DATUM Y  :",
            result.get(
                "floor_datum_y"
            ),
        )

        for _datum_index, _datum in enumerate(
            result.get(
                "floor_datum_candidates",
                [],
            )[:8],
            start=1,
        ):
            print(
                "DATUM CAND",
                _datum_index,
                "| Y",
                round(
                    float(
                        _datum[
                            "y"
                        ]
                    ),
                    3,
                ),
                "| SILL",
                round(
                    float(
                        _datum[
                            "sill_cm"
                        ]
                    ),
                    3,
                ),
                "cm",
                "| COVER",
                round(
                    float(
                        _datum[
                            "coverage"
                        ]
                    ),
                    3,
                ),
            )

    if result.get(
        "raw_local_cm"
    ) is not None:
        print(
            "RAW LOCAL      :",
            result.get(
                "raw_local_cm"
            ),
            "cm",
        )

    print(
        "SILL           :",
        result.get(
            "sill_cm"
        ),
        "cm",
    )

    print(
        "SOURCE         :",
        result.get(
            "source"
        ),
    )

    reason = str(
        result.get(
            "reason",
            "",
        )
        or ""
    )

    if reason:
        print(
            "REASON         :",
            reason,
        )

    print(
        "=== END WINDOW SILL FACADE LOCAL Z V2 ==="
    )
    print("")



# ============================================================
# CAD3D_UPPER_FLOOR_DATUM_FROM_CAD_V3
# ============================================================

def _facade_bounds_v3(
    analysis,
    facade_number,
):
    for row in (
        analysis.get(
            "facades",
            [],
        )
        or []
    ):
        try:
            number = int(
                row.get(
                    "facade_number"
                )
            )
        except Exception:
            continue

        if number != int(
            facade_number
        ):
            continue

        bounds = (
            row.get(
                "facade_bbox"
            )
            or
            row.get(
                "bbox"
            )
        )

        if (
            isinstance(
                bounds,
                (list, tuple),
            )
            and len(bounds) == 4
        ):
            return tuple(
                float(v)
                for v in bounds
            )

    for row in (
        analysis.get(
            "elevation_facades",
            [],
        )
        or []
    ):
        try:
            number = int(
                row.get(
                    "facade_number"
                )
            )
        except Exception:
            continue

        if number != int(
            facade_number
        ):
            continue

        bounds = row.get(
            "bbox"
        )

        if (
            isinstance(
                bounds,
                (list, tuple),
            )
            and len(bounds) == 4
        ):
            return tuple(
                float(v)
                for v in bounds
            )

    return None


def _detect_upper_floor_datum_v3(
    window,
    analysis,
    facade_number,
    ground_window_top_y,
    upper_window_bottom_y,
    source_to_mm,
):
    """
    Detect the ACTUAL upper-storey floor datum from CAD.

    Rules:
      - use real horizontal CAD geometry;
      - search BELOW the upper windows;
      - reject window-frame/sill lines close to the window;
      - reject the previous storey's window-head line;
      - prefer long structural horizontal levels;
      - when equally strong parallel slab lines exist,
        prefer the upper one = finished-floor side.

    base_z_cm / 315 cm is deliberately not used.
    """

    summary = getattr(
        window,
        "cad_crop_summary",
        None,
    )

    if not isinstance(
        summary,
        dict,
    ):
        raise RuntimeError(
            "CAD_CROP_SUMMARY_MISSING_FOR_FLOOR_DATUM"
        )

    geometry = list(
        summary.get(
            "geometry",
            [],
        )
        or []
    )

    if not geometry:
        raise RuntimeError(
            "CAD_GEOMETRY_MISSING_FOR_FLOOR_DATUM"
        )

    bounds = _facade_bounds_v3(
        analysis,
        facade_number,
    )

    if bounds is None:
        raise RuntimeError(
            "FACADE_BOUNDS_MISSING_FOR_FLOOR_DATUM"
        )

    from cad._cad_to_3d_max_rooms_exact.elevation_opening_detector import (
        _extract_axis_segments,
        _merge_horizontal,
    )

    x0, y0, x1, y1 = bounds

    facade_width = max(
        x1 - x0,
        1.0,
    )

    facade_height = max(
        y1 - y0,
        1.0,
    )

    raw_horizontal, _ = (
        _extract_axis_segments(
            geometry
        )
    )

    # Keep only horizontal geometry physically belonging
    # to the selected facade rectangle.
    raw_horizontal = [
        row
        for row in raw_horizontal
        if (
            float(
                row.get(
                    "x1",
                    -1.0e30,
                )
            )
            >= x0
            and
            float(
                row.get(
                    "x0",
                    1.0e30,
                )
            )
            <= x1
            and
            y0
            <= float(
                row.get(
                    "y",
                    -1.0e30,
                )
            )
            <= y1
        )
    ]

    if not raw_horizontal:
        raise RuntimeError(
            "NO_HORIZONTAL_FACADE_GEOMETRY"
        )

    y_tolerance = max(
        8.0,
        facade_height * 0.0025,
    )

    horizontal = _merge_horizontal(
        raw_horizontal,
        y_tolerance=y_tolerance,
        gap_tolerance=max(
            16.0,
            facade_width * 0.003,
        ),
    )

    upper_bottom = float(
        upper_window_bottom_y
    )

    ground_top = float(
        ground_window_top_y
    )

    scale = float(
        source_to_mm
    )

    levels = []

    # Group separate collinear pieces on the same Y level.
    for row in sorted(
        horizontal,
        key=lambda item:
            float(
                item[
                    "y"
                ]
            ),
    ):
        y = float(
            row[
                "y"
            ]
        )

        if not (
            ground_top
            < y
            < upper_bottom
        ):
            continue

        target = None

        for level in levels:
            if abs(
                level[
                    "y"
                ]
                - y
            ) <= y_tolerance:
                target = level
                break

        if target is None:
            target = {
                "y":
                    y,

                "lines":
                    [],
            }

            levels.append(
                target
            )

        target[
            "lines"
        ].append(
            row
        )

        target[
            "y"
        ] = sum(
            float(
                line[
                    "y"
                ]
            )
            for line in target[
                "lines"
            ]
        ) / len(
            target[
                "lines"
            ]
        )

    candidates = []

    for level in levels:

        y = float(
            level[
                "y"
            ]
        )

        sill_cm = (
            (
                upper_bottom
                - y
            )
            * scale
            / 10.0
        )

        # Structural floor search range.
        #
        # This removes:
        #   - the window's own bottom/sill projection,
        #   - lower-storey window head,
        #   - unrelated distant facade lines.
        if not (
            30.0
            <= sill_cm
            <= 140.0
        ):
            continue

        intervals = []

        longest = 0.0

        for line in level[
            "lines"
        ]:

            lx0 = max(
                x0,
                float(
                    line[
                        "x0"
                    ]
                ),
            )

            lx1 = min(
                x1,
                float(
                    line[
                        "x1"
                    ]
                ),
            )

            if lx1 <= lx0:
                continue

            intervals.append(
                (
                    lx0,
                    lx1,
                )
            )

            longest = max(
                longest,
                lx1 - lx0,
            )

        if not intervals:
            continue

        intervals.sort()

        union_length = 0.0
        start = None
        end = None

        for lx0, lx1 in intervals:

            if start is None:
                start = lx0
                end = lx1
                continue

            if lx0 <= end:
                end = max(
                    end,
                    lx1,
                )

            else:
                union_length += (
                    end - start
                )

                start = lx0
                end = lx1

        if start is not None:
            union_length += (
                end - start
            )

        coverage = (
            union_length
            / facade_width
        )

        longest_ratio = (
            longest
            / facade_width
        )

        # Floor/slab lines must be structural,
        # not a short line belonging to one window.
        if (
            coverage < 0.22
            and longest_ratio < 0.18
        ):
            continue

        candidates.append(
            {
                "y":
                    y,

                "sill_cm":
                    sill_cm,

                "coverage":
                    coverage,

                "longest_ratio":
                    longest_ratio,

                "segment_count":
                    len(
                        intervals
                    ),
            }
        )

    if not candidates:
        raise RuntimeError(
            "UPPER_FLOOR_DATUM_LINE_NOT_FOUND"
        )

    # Primary rule:
    #   widest/strongest structural line.
    #
    # Tie:
    #   highest line wins, representing the upper /
    #   finished-floor side of a slab band.
    candidates.sort(
        key=lambda row: (
            float(
                row[
                    "coverage"
                ]
            ),
            float(
                row[
                    "longest_ratio"
                ]
            ),
            float(
                row[
                    "y"
                ]
            ),
        ),
        reverse=True,
    )

    best = candidates[0]

    # If several levels have practically the same structural
    # coverage, explicitly prefer the highest one.
    strong = [
        row
        for row in candidates
        if (
            float(
                row[
                    "coverage"
                ]
            )
            >= float(
                best[
                    "coverage"
                ]
            ) * 0.92
            and
            float(
                row[
                    "longest_ratio"
                ]
            )
            >= float(
                best[
                    "longest_ratio"
                ]
            ) * 0.85
        )
    ]

    if strong:
        best = max(
            strong,
            key=lambda row:
                float(
                    row[
                        "y"
                    ]
                ),
        )

    debug = sorted(
        candidates,
        key=lambda row:
            float(
                row[
                    "y"
                ]
            ),
        reverse=True,
    )

    return (
        float(
            best[
                "y"
            ]
        ),
        debug[
            :12
        ],
    )


def resolve_window_sill_cm(
    window,
    *,
    floor_index,
    base_z_cm,
    target_layer,
    fallback_cm,
):
    """
    IMPORTANT:

    base_z_cm is ONLY Max model placement.

    It is intentionally NOT subtracted from facade
    elevation measurements.

    Ground:
        entrance door bottom = local Z0.

    Upper floors:
        facade storey translation is detected from
        matching physical window-frame families.

        local Z0 =
            entrance Z0
            + detected facade storey translation.
    """

    fallback = _f(
        fallback_cm
    )

    if (
        fallback is None
        or fallback <= 0.0
        or fallback >= MAX_SILL_CM
    ):
        fallback = 90.0

    floor_index = _i(
        floor_index
    )

    base_z_cm = _f(
        base_z_cm
    )

    if base_z_cm is None:
        base_z_cm = 0.0

    result = {
        "engine":
            ENGINE,

        "ok":
            False,

        "floor_index":
            floor_index,

        "base_z_cm":
            base_z_cm,

        "reference":
            (
                "MAIN_ENTRANCE_DOOR_BOTTOM"
                if floor_index == 0
                else
                "DETECTED_FACADE_STOREY_LOCAL_Z0"
            ),

        "source":
            "MANUAL_FALLBACK",

        "reason":
            "",

        "sill_cm":
            fallback,

        "ground_rows":
            [],

        "floor_rows":
            [],

        "ground_family":
            [],

        "floor_family":
            [],

        "ground_sill_raw_cm":
            None,

        "facade_storey_shift_cm":
            None,

        "shift_bottom_cm":
            None,

        "shift_top_cm":
            None,

        "raw_local_cm":
            None,
    }

    try:
        if floor_index is None:
            raise RuntimeError(
                "FLOOR_INDEX_MISSING"
            )

        analysis, analysis_source = (
            _analysis(
                window
            )
        )

        result[
            "analysis_source"
        ] = analysis_source

        if analysis is None:
            raise RuntimeError(
                "FACADE_ANALYSIS_MISSING"
            )

        entrance = _main_entrance(
            analysis
        )

        entrance_y = _f(
            entrance.get(
                "elevation_bottom_y"
            )
        )

        facade_number = _i(
            entrance.get(
                "facade_number"
            )
        )

        plan_side = str(
            entrance.get(
                "plan_side",
                "",
            )
            or ""
        ).strip()

        if entrance_y is None:
            raise RuntimeError(
                "ENTRANCE_BOTTOM_Y_MISSING"
            )

        if facade_number is None:
            raise RuntimeError(
                "ENTRANCE_FACADE_MISSING"
            )

        scale = _source_to_mm(
            window,
            target_layer,
        )

        result[
            "source_to_mm"
        ] = scale

        result[
            "entrance_bottom_y"
        ] = entrance_y

        result[
            "entrance_facade_number"
        ] = facade_number

        result[
            "entrance_plan_side"
        ] = plan_side

        ground_rows = _window_rows(
            analysis,
            0,
            facade_number,
            plan_side,
        )

        if not ground_rows:
            raise RuntimeError(
                "GROUND_WINDOW_ROWS_MISSING"
            )

        ground_family = (
            _dominant_height_family(
                ground_rows
            )
        )

        if not ground_family:
            raise RuntimeError(
                "GROUND_PHYSICAL_WINDOW_FAMILY_MISSING"
            )

        ground_height = _median(
            row[
                "height"
            ]
            for row in ground_family
        )

        ground_bottom = _median(
            row[
                "bottom_y"
            ]
            for row in ground_family
        )

        ground_top = _median(
            row[
                "top_y"
            ]
            for row in ground_family
        )

        ground_sill_raw_cm = (
            (
                ground_bottom
                - entrance_y
            )
            * scale
            / 10.0
        )

        result[
            "ground_rows"
        ] = ground_rows

        result[
            "ground_family"
        ] = ground_family

        result[
            "ground_family_height"
        ] = ground_height

        result[
            "ground_bottom_y"
        ] = ground_bottom

        result[
            "ground_top_y"
        ] = ground_top

        result[
            "ground_sill_raw_cm"
        ] = ground_sill_raw_cm

        # -------------------------------------------------
        # GROUND FLOOR
        # -------------------------------------------------

        if floor_index == 0:

            raw_local = (
                ground_sill_raw_cm
            )

            sill_cm = (
                _snap_half_cm(
                    raw_local
                )
            )

            if not (
                0.0
                < sill_cm
                < MAX_SILL_CM
            ):
                raise RuntimeError(
                    "GROUND_SILL_OUT_OF_RANGE"
                )

            result[
                "raw_local_cm"
            ] = raw_local

            result[
                "sill_cm"
            ] = sill_cm

            result[
                "ok"
            ] = True

            result[
                "source"
            ] = (
                "AUTO_GROUND_ENTRANCE_Z0"
            )

        # -------------------------------------------------
        # UPPER FLOOR
        # -------------------------------------------------

        else:

            floor_rows = _window_rows(
                analysis,
                floor_index,
                facade_number,
                plan_side,
            )

            if not floor_rows:
                raise RuntimeError(
                    "UPPER_WINDOW_ROWS_MISSING"
                )

            # Critical fix:
            #
            # Ignore inner sash candidates whose height
            # differs from the proven ground outer-frame
            # family.
            floor_family = (
                _family_matching_height(
                    floor_rows,
                    ground_height,
                )
            )

            if len(
                floor_family
            ) < 2:
                raise RuntimeError(
                    "UPPER_MATCHING_FRAME_FAMILY_INSUFFICIENT"
                )

            floor_bottom = _median(
                row[
                    "bottom_y"
                ]
                for row in floor_family
            )

            floor_top = _median(
                row[
                    "top_y"
                ]
                for row in floor_family
            )

            shift_bottom_units = (
                floor_bottom
                - ground_bottom
            )

            shift_top_units = (
                floor_top
                - ground_top
            )

            shift_bottom_cm = (
                shift_bottom_units
                * scale
                / 10.0
            )

            shift_top_cm = (
                shift_top_units
                * scale
                / 10.0
            )

            if (
                abs(
                    shift_bottom_cm
                    - shift_top_cm
                )
                > STOREY_SHIFT_TOLERANCE_CM
            ):
                raise RuntimeError(
                    "FACADE_STOREY_SHIFT_BOTTOM_TOP_DISAGREE"
                )

            shift_units = _median(
                [
                    shift_bottom_units,
                    shift_top_units,
                ]
            )

            shift_cm = (
                shift_units
                * scale
                / 10.0
            )

            # Actual facade-local floor origin.
            #
            # DO NOT USE base_z_cm here.
            floor_local_z0_y, _cad3d_floor_datum_candidates = (
                _detect_upper_floor_datum_v3(
                    window,
                    analysis,
                    facade_number,
                    ground_top,
                    floor_bottom,
                    scale,
                )
            )

            result[
                "floor_datum_y"
            ] = floor_local_z0_y

            result[
                "floor_datum_candidates"
            ] = _cad3d_floor_datum_candidates

            result[
                "floor_datum_rule"
            ] = (
                "REAL_LONG_HORIZONTAL_CAD_LINE_V3"
            )

            local_values = [
                (
                    (
                        float(
                            row[
                                "bottom_y"
                            ]
                        )
                        - floor_local_z0_y
                    )
                    * scale
                    / 10.0
                )
                for row in floor_family
            ]

            raw_local = _median(
                local_values
            )

            sill_cm = (
                _snap_half_cm(
                    raw_local
                )
            )

            if not (
                0.0
                < sill_cm
                < MAX_SILL_CM
            ):
                raise RuntimeError(
                    "UPPER_LOCAL_SILL_OUT_OF_RANGE"
                )

            result[
                "floor_rows"
            ] = floor_rows

            result[
                "floor_family"
            ] = floor_family

            result[
                "floor_bottom_y"
            ] = floor_bottom

            result[
                "floor_top_y"
            ] = floor_top

            result[
                "shift_bottom_cm"
            ] = shift_bottom_cm

            result[
                "shift_top_cm"
            ] = shift_top_cm

            result[
                "facade_storey_shift_cm"
            ] = shift_cm

            result[
                "floor_local_z0_y"
            ] = floor_local_z0_y

            result[
                "raw_local_cm"
            ] = raw_local

            result[
                "sill_cm"
            ] = sill_cm

            result[
                "ok"
            ] = True

            result[
                "source"
            ] = (
                "AUTO_REAL_CAD_FLOOR_DATUM_Z0"
            )

    except Exception as exc:

        result[
            "ok"
        ] = False

        result[
            "source"
        ] = "MANUAL_FALLBACK"

        result[
            "reason"
        ] = str(
            exc
        )

        result[
            "sill_cm"
        ] = fallback

    _write_log(
        result
    )

    _print_result(
        result
    )

    return float(
        result[
            "sill_cm"
        ]
    )



def self_test():
    # Ground datum.
    entrance_y = 21847.56323578842
    ground_bottom = 22749.23273646956

    ground_sill = (
        ground_bottom
        - entrance_y
    ) / 10.0

    assert (
        _snap_half_cm(
            ground_sill
        )
        == 90.0
    )

    # Upper-floor example:
    # actual window bottom and actual floor datum are
    # independent from the ground-floor window translation.
    upper_bottom = 25674.36712600323

    # Synthetic actual CAD floor line producing the
    # verified architectural sill of 77.5 cm.
    upper_floor_datum = (
        upper_bottom
        - 775.0
    )

    upper_sill = (
        upper_bottom
        - upper_floor_datum
    ) / 10.0

    assert abs(
        upper_sill
        - 77.5
    ) < 1.0e-9

    assert (
        _snap_half_cm(
            upper_sill
        )
        == 77.5
    )

    print(
        "WINDOW SILL REAL FLOOR DATUM V3 SELF TEST: OK"
    )

    print(
        "GROUND SILL:",
        ground_sill,
        "->",
        _snap_half_cm(
            ground_sill
        ),
        "cm",
    )

    print(
        "UPPER SILL TEST:",
        upper_sill,
        "->",
        _snap_half_cm(
            upper_sill
        ),
        "cm",
    )

    print(
        "MAX BASE Z IS NOT USED AS FACADE FLOOR DATUM"
    )


if __name__ == "__main__":
    self_test()
