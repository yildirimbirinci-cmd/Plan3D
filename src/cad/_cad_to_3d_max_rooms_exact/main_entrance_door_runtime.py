from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


ENGINE = (
    "CAD3D_MAIN_ENTRANCE_PLAN_FIRST_FACADE_VERIFY_V1"
)


def _root():
    return Path(__file__).resolve().parents[2]


def _num(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(result):
        return None

    return result


def _median(values):
    rows = sorted(
        float(value)
        for value in values
    )

    count = len(rows)

    if not count:
        raise RuntimeError(
            "EMPTY_MEDIAN"
        )

    middle = count // 2

    if count % 2:
        return rows[middle]

    return (
        rows[middle - 1]
        + rows[middle]
    ) * 0.5


def _token(raw):
    data = {
        "full_bounds":
            raw.get(
                "full_bounds"
            ),

        "main_plan":
            (
                raw.get(
                    "main_plan"
                )
                or {}
            ).get(
                "bbox"
            ),

        "plan_facades":
            raw.get(
                "plan_facades"
            ),
    }

    blob = json.dumps(
        data,
        sort_keys=True,
        ensure_ascii=True,
        default=str,
    )

    return hashlib.sha1(
        blob.encode(
            "utf-8"
        )
    ).hexdigest()


def _plan_doors(raw):
    rows = []

    for facade in (
        raw.get(
            "plan_facades",
            [],
        )
        or []
    ):

        if not isinstance(
            facade,
            dict,
        ):
            continue

        side = str(
            facade.get(
                "side"
            )
            or ""
        ).lower()

        for index, opening in enumerate(
            facade.get(
                "openings",
                [],
            )
            or []
        ):

            if not isinstance(
                opening,
                dict,
            ):
                continue

            if (
                opening.get(
                    "kind"
                )
                != "door"
            ):
                continue

            rows.append(
                {
                    "plan_side":
                        side,

                    "plan_index":
                        index,

                    "plan_center":
                        opening.get(
                            "center"
                        ),

                    "plan_width":
                        _num(
                            opening.get(
                                "width"
                            )
                        ),

                    "plan_relative_center":
                        _num(
                            opening.get(
                                "relative_center"
                            )
                        ),

                    "plan_source":
                        opening.get(
                            "source"
                        ),
                }
            )

    return rows


def _ground_matches(raw):

    for storey in (
        raw.get(
            "storey_matches",
            [],
        )
        or []
    ):

        if not isinstance(
            storey,
            dict,
        ):
            continue

        if str(
            storey.get(
                "storey_index"
            )
        ) != "0":
            continue

        return [
            item
            for item in (
                storey.get(
                    "matches",
                    [],
                )
                or []
            )
            if isinstance(
                item,
                dict,
            )
        ]

    return [
        item
        for item in (
            raw.get(
                "matches",
                [],
            )
            or []
        )
        if (
            isinstance(
                item,
                dict,
            )
            and str(
                item.get(
                    "storey_index",
                    0,
                )
            )
            == "0"
        )
    ]


def _verified_doors(
    raw,
    plan_doors,
):
    verified = []

    matches = _ground_matches(
        raw
    )

    for door in plan_doors:

        for match in matches:

            if (
                str(
                    match.get(
                        "plan_side"
                    )
                    or ""
                ).lower()
                != door[
                    "plan_side"
                ]
            ):
                continue

            for pair in (
                match.get(
                    "opening_pairs",
                    [],
                )
                or []
            ):

                if not isinstance(
                    pair,
                    dict,
                ):
                    continue

                if (
                    pair.get(
                        "kind"
                    )
                    != "door"
                ):
                    continue

                try:
                    same_index = (
                        int(
                            pair.get(
                                "plan_index"
                            )
                        )
                        ==
                        int(
                            door[
                                "plan_index"
                            ]
                        )
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    same_index = False

                if not same_index:
                    continue

                pair_width = _num(
                    pair.get(
                        "plan_width"
                    )
                )

                plan_width = (
                    door.get(
                        "plan_width"
                    )
                )

                if (
                    pair_width
                    and plan_width
                ):
                    width_error = (
                        abs(
                            pair_width
                            - plan_width
                        )
                        / max(
                            plan_width,
                            1.0e-9,
                        )
                    )

                else:
                    width_error = 0.0

                if width_error > 0.08:
                    continue

                bottom = _num(
                    pair.get(
                        "elevation_bottom_y"
                    )
                )

                top = _num(
                    pair.get(
                        "elevation_top_y"
                    )
                )

                height = _num(
                    pair.get(
                        "elevation_height"
                    )
                )

                if (
                    height is None
                    and bottom is not None
                    and top is not None
                ):
                    height = abs(
                        top
                        - bottom
                    )

                if (
                    bottom is None
                    or top is None
                    or height is None
                    or height <= 0.0
                ):
                    continue

                verified.append(
                    {
                        **door,

                        "facade_number":
                            int(
                                match.get(
                                    "facade_number"
                                )
                            ),

                        "elevation_index":
                            pair.get(
                                "elevation_index"
                            ),

                        "elevation_bbox":
                            pair.get(
                                "elevation_bbox"
                            ),

                        "elevation_bottom_y":
                            bottom,

                        "elevation_top_y":
                            top,

                        "elevation_height":
                            height,

                        "width_error_ratio":
                            width_error,

                        "verification":
                            "EXACT_PLAN_SIDE_AND_PLAN_INDEX",
                    }
                )

    unique = {}

    for row in verified:

        key = (
            row[
                "plan_side"
            ],
            row[
                "plan_index"
            ],
            row[
                "facade_number"
            ],
        )

        if (
            key not in unique
            or
            row[
                "width_error_ratio"
            ]
            <
            unique[
                key
            ][
                "width_error_ratio"
            ]
        ):
            unique[
                key
            ] = row

    return list(
        unique.values()
    )


def _height_consensus(
    rows,
):

    if not rows:
        raise RuntimeError(
            "NO_PLAN_TO_FACADE_DOOR_VERIFICATION"
        )

    best = []

    for seed in rows:

        height = seed[
            "elevation_height"
        ]

        cluster = [
            row
            for row in rows
            if (
                abs(
                    row[
                        "elevation_height"
                    ]
                    - height
                )
                / max(
                    height,
                    1.0e-9,
                )
                <= 0.025
            )
        ]

        if len(
            cluster
        ) > len(
            best
        ):
            best = cluster

    if (
        len(rows) > 1
        and
        len(best)
        <= len(rows) / 2.0
    ):
        raise RuntimeError(
            "VERIFIED_DOOR_HEIGHTS_DISAGREE"
        )

    return (
        best,
        _median(
            row[
                "elevation_height"
            ]
            for row in best
        ),
    )


def _source_to_mm(
    window,
    raw,
):

    bounds = (
        raw.get(
            "main_plan"
        )
        or {}
    ).get(
        "bbox"
    )

    if (
        not isinstance(
            bounds,
            (list, tuple),
        )
        or len(bounds) != 4
    ):
        raise RuntimeError(
            "MAIN_PLAN_BOUNDS_MISSING_FOR_UNIT_SCALE"
        )

    preview = getattr(
        window,
        "preview",
        None,
    )

    if (
        preview is None
        or not hasattr(
            preview,
            "cad_summary_for_bounds",
        )
    ):
        raise RuntimeError(
            "PLAN_SUMMARY_API_MISSING_FOR_UNIT_SCALE"
        )

    summary = (
        preview.cad_summary_for_bounds(
            tuple(
                float(value)
                for value in bounds
            )
        )
    )

    geometry = list(
        (
            summary
            or {}
        ).get(
            "geometry",
            [],
        )
        or []
    )

    if not geometry:
        raise RuntimeError(
            "MAIN_PLAN_GEOMETRY_MISSING_FOR_UNIT_SCALE"
        )

    from cad._cad_to_3d_max_rooms_exact.cad_intelligence import (
        infer_cad_profile,
    )

    from cad._cad_to_3d_max_rooms_exact.generic_cad_cleanup import (
        build_clean_visible_polylines,
    )

    profile = infer_cad_profile(
        geometry
    )

    target_layer = str(
        profile.get(
            "primary_structural_layer"
        )
        or ""
    ).strip()

    if not target_layer:
        raise RuntimeError(
            "STRUCTURAL_LAYER_MISSING_FOR_UNIT_SCALE"
        )

    wall_source = [
        item
        for item in geometry
        if (
            isinstance(
                item,
                dict,
            )
            and
            str(
                item.get(
                    "layer"
                )
                or ""
            ).strip()
            == target_layer
            and
            len(
                item.get(
                    "points"
                )
                or []
            )
            >= 2
        )
    ]

    if not wall_source:
        raise RuntimeError(
            "STRUCTURAL_GEOMETRY_MISSING_FOR_UNIT_SCALE"
        )

    cad_meta = getattr(
        window,
        "cad_data",
        None,
    )

    if not isinstance(
        cad_meta,
        dict,
    ):
        cad_meta = getattr(
            preview,
            "cad_data",
            None,
        )

    _cleaned, report = (
        build_clean_visible_polylines(
            wall_source,
            cad_meta=cad_meta,
        )
    )

    scale = _num(
        report.get(
            "source_to_mm"
        )
    )

    if (
        scale is None
        or scale <= 0.0
    ):
        raise RuntimeError(
            "SOURCE_TO_MM_UNRESOLVED"
        )

    return (
        scale,
        {
            "source_to_mm":
                scale,

            "source_unit_token":
                report.get(
                    "source_unit_token"
                ),

            "source_unit_name":
                report.get(
                    "source_unit_name"
                ),

            "source_unit_confidence":
                report.get(
                    "source_unit_confidence"
                ),
        },
    )


def resolve_main_entrance_door(
    window,
    result,
):

    if not isinstance(
        result,
        dict,
    ):
        return result

    payload = {
        "engine":
            ENGINE,

        "ok":
            False,

        "reason":
            None,
    }

    window.current_main_entrance_door_result = (
        payload
    )

    window.detected_ground_floor_height_cm = (
        None
    )

    try:

        raw_path = (
            _root()
            / "logs"
            / "facade_windows_button_RAW.json"
        )

        if not raw_path.exists():
            raise RuntimeError(
                "FACADE_WINDOWS_RAW_RESULT_MISSING"
            )

        raw = json.loads(
            raw_path.read_text(
                encoding="utf-8-sig"
            )
        )

        if not isinstance(
            raw,
            dict,
        ):
            raise RuntimeError(
                "FACADE_WINDOWS_RAW_RESULT_INVALID"
            )

        analysis_token = _token(
            raw
        )

        plan_doors = _plan_doors(
            raw
        )

        if not plan_doors:
            raise RuntimeError(
                "NO_EXTERIOR_PLAN_DOORS"
            )

        verified = (
            _verified_doors(
                raw,
                plan_doors,
            )
        )

        (
            consensus,
            height_units,
        ) = _height_consensus(
            verified
        )

        (
            source_to_mm,
            unit_info,
        ) = _source_to_mm(
            window,
            raw,
        )

        raw_height_cm = (
            height_units
            * source_to_mm
            / 10.0
        )

        # Architectural noise is normalized
        # to the nearest 0.5 cm.
        ground_floor_height_cm = (
            round(
                raw_height_cm
                * 2.0
            )
            / 2.0
        )

        if not (
            100.0
            <= ground_floor_height_cm
            <= 600.0
        ):
            raise RuntimeError(
                "GROUND_FLOOR_HEIGHT_OUT_OF_RANGE"
            )

        selected = min(
            consensus,
            key=lambda row: (
                row[
                    "width_error_ratio"
                ],
                row[
                    "plan_index"
                ],
            ),
        )

        ground_y = _median(
            row[
                "elevation_bottom_y"
            ]
            for row in consensus
        )

        top_y = _median(
            row[
                "elevation_top_y"
            ]
            for row in consensus
        )

        payload = {
            "engine":
                ENGINE,

            "ok":
                True,

            "analysis_token":
                analysis_token,

            "plan_exterior_door_count":
                len(
                    plan_doors
                ),

            "verified_facade_door_count":
                len(
                    verified
                ),

            "height_consensus_count":
                len(
                    consensus
                ),

            "plan_doors":
                plan_doors,

            "verified_doors":
                verified,

            "selected_door":
                selected,

            "ground_reference_y":
                ground_y,

            "ground_reference_rule":
                "PLAN_FIRST_VERIFIED_ENTRANCE_DOOR_BOTTOM_Z0_V1",

            "door_top_y":
                top_y,

            "door_height_units":
                height_units,

            "ground_floor_height_raw_cm":
                raw_height_cm,

            "ground_floor_height_cm":
                ground_floor_height_cm,

            "unit_info":
                unit_info,

            "source":
                "PLAN_FIRST_FACADE_VERIFIED_DOOR_HEIGHT",
        }

        result[
            "main_entrance_door_result"
        ] = payload

        result[
            "main_entrance_door"
        ] = selected

        result[
            "detected_ground_floor_height_cm"
        ] = ground_floor_height_cm

        result[
            "ground_reference_y"
        ] = ground_y

        result[
            "ground_reference_rule"
        ] = payload[
            "ground_reference_rule"
        ]

        result[
            "main_entrance_analysis_token"
        ] = analysis_token

        window.current_main_entrance_door_result = (
            payload
        )

        window.detected_ground_floor_height_cm = (
            ground_floor_height_cm
        )

        print("")
        print(
            "=== MAIN ENTRANCE DOOR PLAN -> FACADE V1 ==="
        )

        print(
            "PLAN EXTERIOR DOORS:",
            len(
                plan_doors
            ),
        )

        print(
            "VERIFIED FACADE DOORS:",
            len(
                verified
            ),
        )

        print(
            "HEIGHT CONSENSUS:",
            len(
                consensus
            ),
        )

        print(
            "PLAN SIDE:",
            selected[
                "plan_side"
            ],
            "| FACADE:",
            selected[
                "facade_number"
            ],
        )

        print(
            "BOTTOM Z0 Y:",
            round(
                ground_y,
                3,
            ),
            "| TOP Y:",
            round(
                top_y,
                3,
            ),
        )

        print(
            "HEIGHT UNITS:",
            round(
                height_units,
                3,
            ),
            "| SOURCE TO MM:",
            source_to_mm,
        )

        print(
            "GROUND FLOOR HEIGHT RAW:",
            round(
                raw_height_cm,
                3,
            ),
            "cm",
        )

        print(
            "GROUND FLOOR HEIGHT:",
            ground_floor_height_cm,
            "cm",
        )

        print(
            "=== END MAIN ENTRANCE DOOR ==="
        )
        print("")

    except Exception as exc:

        payload[
            "reason"
        ] = str(
            exc
        )

        result[
            "main_entrance_door_result"
        ] = payload

        result[
            "detected_ground_floor_height_cm"
        ] = None

        window.current_main_entrance_door_result = (
            payload
        )

        window.detected_ground_floor_height_cm = (
            None
        )

        print("")
        print(
            "=== MAIN ENTRANCE DOOR PLAN -> FACADE V1 ==="
        )

        print(
            "NOT RESOLVED:",
            str(
                exc
            ),
        )

        print(
            "GROUND FLOOR HEIGHT: MANUAL VALUE PRESERVED"
        )

        print(
            "=== END MAIN ENTRANCE DOOR ==="
        )
        print("")

    log_dir = (
        _root()
        / "logs"
    )

    log_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        log_dir
        / "main_entrance_door_RESULT.json"
    ).write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    (
        log_dir
        / "facade_windows_button_RESULT.json"
    ).write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    return result


def self_test():

    raw = {
        "plan_facades": [
            {
                "side":
                    "bottom",

                "openings": [
                    {
                        "kind":
                            "door",

                        "width":
                            900.0,
                    },
                    {
                        "kind":
                            "door",

                        "width":
                            900.0,
                    },
                ],
            },
        ],

        "storey_matches": [
            {
                "storey_index":
                    0,

                "matches": [
                    {
                        "facade_number":
                            1,

                        "plan_side":
                            "bottom",

                        "opening_pairs": [
                            {
                                "kind":
                                    "door",

                                "plan_index":
                                    0,

                                "plan_width":
                                    900.0,

                                "elevation_bottom_y":
                                    1000.0,

                                "elevation_top_y":
                                    3700.0,

                                "elevation_height":
                                    2700.0,
                            },
                            {
                                "kind":
                                    "door",

                                "plan_index":
                                    1,

                                "plan_width":
                                    900.0,

                                "elevation_bottom_y":
                                    1000.0,

                                "elevation_top_y":
                                    3700.0,

                                "elevation_height":
                                    2700.0,
                            },
                        ],
                    },
                ],
            },
        ],
    }

    doors = _plan_doors(
        raw
    )

    verified = (
        _verified_doors(
            raw,
            doors,
        )
    )

    cluster, height = (
        _height_consensus(
            verified
        )
    )

    assert len(
        doors
    ) == 2

    assert len(
        verified
    ) == 2

    assert len(
        cluster
    ) == 2

    assert height == 2700.0

    print(
        "MAIN ENTRANCE PLAN FIRST FACADE VERIFY V1 SELF TEST: OK"
    )


if __name__ == "__main__":
    self_test()
