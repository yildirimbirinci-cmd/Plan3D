from __future__ import annotations

import json
import statistics
from pathlib import Path


ENGINE = "CAD3D_WINDOW_VERTICAL_MEASUREMENTS_V1"

MAIN_ENTRANCE_DOOR_HEIGHT_CM = 210.0
STOREY_CLEAR_HEIGHT_CM = 300.0
INTERFLOOR_THICKNESS_CM = 35.0
FLOOR_TO_FLOOR_CM = (
    STOREY_CLEAR_HEIGHT_CM
    + INTERFLOOR_THICKNESS_CM
)

GROUND_REFERENCE_RULE = (
    "MAIN_ENTRANCE_DOOR_BOTTOM_V1"
)


def _number(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _door_pairs(match):
    return [
        pair
        for pair in (
            match.get(
                "opening_pairs",
                [],
            )
            or []
        )
        if pair.get("kind") == "door"
    ]


def _window_pairs(match):
    return [
        pair
        for pair in (
            match.get(
                "opening_pairs",
                [],
            )
            or []
        )
        if pair.get("kind") == "window"
    ]


def _pair_bottom(pair):
    return _number(
        pair.get(
            "elevation_bottom_y"
        )
    )


def _pair_top(pair):
    return _number(
        pair.get(
            "elevation_top_y"
        )
    )


def _pair_height(pair):
    value = _number(
        pair.get(
            "elevation_height"
        )
    )

    if value is not None:
        return abs(value)

    bottom = _pair_bottom(pair)
    top = _pair_top(pair)

    if (
        bottom is None
        or top is None
    ):
        return None

    return abs(
        top - bottom
    )


def _plan_side_widths(analysis):
    result = {}

    for facade in (
        analysis.get(
            "plan_facades",
            [],
        )
        or []
    ):
        side = facade.get("side")

        width = _number(
            facade.get(
                "expected_width"
            )
        )

        if (
            side
            and width is not None
            and width > 0.0
        ):
            result[str(side)] = width

    return result


def _choose_main_entrance(
    analysis,
):
    matches = list(
        analysis.get(
            "matches",
            [],
        )
        or []
    )

    candidates = []

    all_widths = []

    for match in matches:
        for pair in _door_pairs(match):
            width = _number(
                pair.get(
                    "plan_width"
                )
            )

            if (
                width is not None
                and width > 0.0
            ):
                all_widths.append(
                    width
                )

    if not all_widths:
        return None

    median_width = statistics.median(
        all_widths
    )

    side_widths = _plan_side_widths(
        analysis
    )

    max_side_width = max(
        side_widths.values(),
        default=0.0,
    )

    for match_index, match in enumerate(
        matches
    ):
        doors = _door_pairs(
            match
        )

        if not doors:
            continue

        side = str(
            match.get(
                "plan_side",
                "",
            )
        )

        side_width = side_widths.get(
            side,
            0.0,
        )

        for door_index, pair in enumerate(
            doors
        ):
            width = _number(
                pair.get(
                    "plan_width"
                ),
                median_width,
            )

            if width is None:
                width = median_width

            width_ratio = (
                width / median_width
                if median_width > 1.0e-9
                else 1.0
            )

            # Main entrance preference:
            # 1) normal single-door width,
            # 2) facade with one external door,
            # 3) longer exterior facade as tie breaker.
            wide_penalty = (
                100.0
                if width_ratio > 1.55
                else 0.0
            )

            door_count_penalty = (
                abs(
                    len(doors) - 1
                )
                * 20.0
            )

            width_penalty = (
                abs(
                    width_ratio - 1.0
                )
                * 10.0
            )

            long_facade_bonus = 0.0

            if (
                max_side_width > 0.0
                and side_width > 0.0
            ):
                long_facade_bonus = (
                    side_width
                    / max_side_width
                ) * 2.0

            score = (
                wide_penalty
                + door_count_penalty
                + width_penalty
                - long_facade_bonus
            )

            candidates.append(
                (
                    score,
                    match_index,
                    door_index,
                    match,
                    pair,
                )
            )

    if not candidates:
        return None

    candidates.sort(
        key=lambda row: (
            row[0],
            str(
                row[3].get(
                    "plan_side",
                    "",
                )
            ),
            int(
                row[3].get(
                    "facade_number",
                    0,
                )
                or 0
            ),
        )
    )

    (
        score,
        match_index,
        door_index,
        match,
        pair,
    ) = candidates[0]

    bottom = _pair_bottom(
        pair
    )

    top = _pair_top(
        pair
    )

    height = _pair_height(
        pair
    )

    if (
        bottom is None
        or top is None
        or height is None
        or height <= 1.0e-9
    ):
        return None

    return {
        "score":
            float(score),

        "match_index":
            int(match_index),

        "door_index":
            int(door_index),

        "facade_number":
            match.get(
                "facade_number"
            ),

        "plan_side":
            match.get(
                "plan_side"
            ),

        "plan_width":
            _number(
                pair.get(
                    "plan_width"
                )
            ),

        "elevation_bottom_y":
            bottom,

        "elevation_top_y":
            top,

        "elevation_height":
            height,
    }


def _choose_local_registration_door(
    match,
    main_plan_width,
):
    doors = _door_pairs(
        match
    )

    if not doors:
        return None

    def rank(pair):
        width = _number(
            pair.get(
                "plan_width"
            )
        )

        if (
            width is None
            or main_plan_width is None
        ):
            width_error = 0.0
        else:
            width_error = abs(
                width - main_plan_width
            )

        bottom = _pair_bottom(
            pair
        )

        return (
            width_error,
            (
                bottom
                if bottom is not None
                else float("inf")
            ),
        )

    pair = min(
        doors,
        key=rank,
    )

    bottom = _pair_bottom(
        pair
    )

    if bottom is None:
        return None

    return pair


def calculate_window_vertical_measurements(
    analysis,
):
    result = {
        "engine":
            ENGINE,

        "ok":
            False,

        "ground_reference_rule":
            GROUND_REFERENCE_RULE,

        "storey_clear_height_cm":
            STOREY_CLEAR_HEIGHT_CM,

        "interfloor_thickness_cm":
            INTERFLOOR_THICKNESS_CM,

        "floor_to_floor_cm":
            FLOOR_TO_FLOOR_CM,

        "main_entrance":
            None,

        "cm_per_drawing_unit":
            None,

        "windows":
            [],

        "unresolved":
            [],
    }

    entrance = _choose_main_entrance(
        analysis
    )

    if entrance is None:
        result[
            "error"
        ] = (
            "MAIN_ENTRANCE_DOOR_NOT_RESOLVED"
        )

        return result

    entrance_height = float(
        entrance[
            "elevation_height"
        ]
    )

    # Vertical drawing scale is calibrated by the
    # architectural 210 cm entrance-door contract.
    cm_per_unit = (
        MAIN_ENTRANCE_DOOR_HEIGHT_CM
        / entrance_height
    )

    entrance = dict(
        entrance
    )

    entrance[
        "z_cm"
    ] = 0.0

    entrance[
        "known_height_cm"
    ] = (
        MAIN_ENTRANCE_DOOR_HEIGHT_CM
    )

    entrance[
        "reference_rule"
    ] = GROUND_REFERENCE_RULE

    result[
        "main_entrance"
    ] = entrance

    result[
        "cm_per_drawing_unit"
    ] = cm_per_unit

    matches = list(
        analysis.get(
            "matches",
            [],
        )
        or []
    )

    window_counter = 0

    for match_index, match in enumerate(
        matches
    ):
        facade_number = match.get(
            "facade_number"
        )

        plan_side = match.get(
            "plan_side"
        )

        windows = _window_pairs(
            match
        )

        if not windows:
            continue

        if (
            match_index
            == entrance["match_index"]
        ):
            local_reference_y = float(
                entrance[
                    "elevation_bottom_y"
                ]
            )

            registration_source = (
                "MAIN_ENTRANCE_DOOR_BOTTOM"
            )

        else:
            registration_door = (
                _choose_local_registration_door(
                    match,
                    entrance.get(
                        "plan_width"
                    ),
                )
            )

            if registration_door is None:
                for pair_index, pair in enumerate(
                    windows
                ):
                    result[
                        "unresolved"
                    ].append(
                        {
                            "facade_number":
                                facade_number,

                            "plan_side":
                                plan_side,

                            "plan_index":
                                pair.get(
                                    "plan_index"
                                ),

                            "reason":
                                (
                                    "NO_MATCHED_DOOR_FOR_LOCAL_"
                                    "ELEVATION_REGISTRATION"
                                ),
                        }
                    )

                continue

            local_reference_y = float(
                _pair_bottom(
                    registration_door
                )
            )

            # Important:
            # this does NOT redefine Z=0.
            # It only aligns a separately positioned
            # elevation drawing to the canonical datum
            # established by the main entrance door.
            registration_source = (
                "LOCAL_FACADE_REGISTERED_TO_"
                "MAIN_ENTRANCE_DATUM_BY_MATCHED_DOOR"
            )

        storey_index = int(
            match.get(
                "storey_index",
                analysis.get(
                    "storey_index",
                    0,
                ),
            )
            or 0
        )

        storey_base_cm = (
            storey_index
            * FLOOR_TO_FLOOR_CM
        )

        for pair in windows:
            bottom = _pair_bottom(
                pair
            )

            top = _pair_top(
                pair
            )

            height_units = _pair_height(
                pair
            )

            if (
                bottom is None
                or top is None
                or height_units is None
            ):
                result[
                    "unresolved"
                ].append(
                    {
                        "facade_number":
                            facade_number,

                        "plan_side":
                            plan_side,

                        "plan_index":
                            pair.get(
                                "plan_index"
                            ),

                        "reason":
                            "WINDOW_VERTICAL_GEOMETRY_MISSING",
                    }
                )

                continue

            window_counter += 1

            bottom_z_cm = (
                (
                    bottom
                    - local_reference_y
                )
                * cm_per_unit
                + storey_base_cm
            )

            height_cm = (
                height_units
                * cm_per_unit
            )

            top_z_cm = (
                bottom_z_cm
                + height_cm
            )

            result[
                "windows"
            ].append(
                {
                    "window_id":
                        f"W{window_counter:02d}",

                    "facade_number":
                        facade_number,

                    "plan_side":
                        plan_side,

                    "plan_index":
                        pair.get(
                            "plan_index"
                        ),

                    "elevation_index":
                        pair.get(
                            "elevation_index"
                        ),

                    "storey_index":
                        storey_index,

                    "drawing_bottom_y":
                        bottom,

                    "drawing_top_y":
                        top,

                    "drawing_height":
                        height_units,

                    "window_bottom_z_cm":
                        round(
                            bottom_z_cm,
                            2,
                        ),

                    "window_height_cm":
                        round(
                            height_cm,
                            2,
                        ),

                    "window_top_z_cm":
                        round(
                            top_z_cm,
                            2,
                        ),

                    "interfloor_thickness_cm":
                        INTERFLOOR_THICKNESS_CM,

                    "ground_reference_rule":
                        GROUND_REFERENCE_RULE,

                    "registration_source":
                        registration_source,
                }
            )

    result[
        "window_count"
    ] = len(
        result["windows"]
    )

    result[
        "unresolved_count"
    ] = len(
        result["unresolved"]
    )

    result[
        "ok"
    ] = (
        result["window_count"] > 0
    )

    return result


def _write_log(
    measurements,
):
    root = Path(
        __file__
    ).resolve().parents[2]

    log_dir = (
        root
        / "logs"
    )

    log_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = (
        log_dir
        / "window_vertical_measurements.json"
    )

    path.write_text(
        json.dumps(
            measurements,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return path


def _print_report(
    measurements,
    log_path,
):
    print("")
    print(
        "=== WINDOW VERTICAL MEASUREMENTS ==="
    )

    print(
        "ENGINE :",
        measurements.get(
            "engine"
        ),
    )

    print(
        "Z=0    : MAIN ENTRANCE DOOR BOTTOM"
    )

    print(
        "SLAB   :",
        f"{INTERFLOOR_THICKNESS_CM:.2f} cm",
    )

    print(
        "FLOOR  :",
        f"{FLOOR_TO_FLOOR_CM:.2f} cm",
    )

    entrance = measurements.get(
        "main_entrance"
    )

    if entrance:
        print(
            "ENTRY  :",
            "facade=",
            entrance.get(
                "facade_number"
            ),
            "side=",
            entrance.get(
                "plan_side"
            ),
        )

    print(
        "SCALE  :",
        measurements.get(
            "cm_per_drawing_unit"
        ),
        "cm/unit",
    )

    for row in (
        measurements.get(
            "windows",
            [],
        )
        or []
    ):
        print(
            (
                f'{row["window_id"]} | '
                f'facade={row["facade_number"]} | '
                f'side={row["plan_side"]} | '
                f'sill={row["window_bottom_z_cm"]:.2f} cm | '
                f'height={row["window_height_cm"]:.2f} cm | '
                f'top={row["window_top_z_cm"]:.2f} cm'
            )
        )

    unresolved = measurements.get(
        "unresolved",
        [],
    ) or []

    if unresolved:
        print(
            "UNRESOLVED:",
            len(unresolved),
        )

        for row in unresolved:
            print(
                " -",
                row,
            )

    print(
        "LOG    :",
        str(log_path),
    )

    print(
        "=== END WINDOW VERTICAL MEASUREMENTS ==="
    )

    print("")


def attach_window_vertical_measurements(
    analysis,
):
    if not isinstance(
        analysis,
        dict,
    ):
        return analysis

    measurements = (
        calculate_window_vertical_measurements(
            analysis
        )
    )

    analysis[
        "window_vertical_measurements"
    ] = measurements

    log_path = _write_log(
        measurements
    )

    _print_report(
        measurements,
        log_path,
    )

    return analysis


def self_test():
    analysis = {
        "plan_facades": [
            {
                "side": "top",
                "expected_width": 10000.0,
            },
            {
                "side": "left",
                "expected_width": 6000.0,
            },
        ],

        "matches": [
            {
                "facade_number": 1,
                "plan_side": "top",
                "opening_pairs": [
                    {
                        "kind": "door",
                        "plan_index": 0,
                        "plan_width": 900.0,
                        "elevation_bottom_y": 1000.0,
                        "elevation_top_y": 3100.0,
                        "elevation_height": 2100.0,
                    },
                    {
                        "kind": "window",
                        "plan_index": 1,
                        "elevation_index": 10,
                        "elevation_bottom_y": 1900.0,
                        "elevation_top_y": 3400.0,
                        "elevation_height": 1500.0,
                    },
                ],
            },
            {
                "facade_number": 2,
                "plan_side": "left",
                "opening_pairs": [
                    {
                        "kind": "door",
                        "plan_index": 0,
                        "plan_width": 900.0,
                        "elevation_bottom_y": 5000.0,
                        "elevation_top_y": 7100.0,
                        "elevation_height": 2100.0,
                    },
                    {
                        "kind": "window",
                        "plan_index": 1,
                        "elevation_index": 20,
                        "elevation_bottom_y": 5900.0,
                        "elevation_top_y": 7400.0,
                        "elevation_height": 1500.0,
                    },
                ],
            },
        ],
    }

    result = (
        calculate_window_vertical_measurements(
            analysis
        )
    )

    assert result["ok"], result
    assert result["window_count"] == 2, result

    for window in result["windows"]:
        assert abs(
            window["window_bottom_z_cm"]
            - 90.0
        ) < 1.0e-6, window

        assert abs(
            window["window_height_cm"]
            - 150.0
        ) < 1.0e-6, window

        assert abs(
            window["window_top_z_cm"]
            - 240.0
        ) < 1.0e-6, window

    assert (
        result[
            "interfloor_thickness_cm"
        ]
        == 35.0
    )

    assert (
        result[
            "floor_to_floor_cm"
        ]
        == 335.0
    )

    print(
        "WINDOW VERTICAL MEASUREMENTS V1 SELF-TEST: OK"
    )

    print(
        "SILL   : 90.00 cm"
    )

    print(
        "HEIGHT : 150.00 cm"
    )

    print(
        "TOP    : 240.00 cm"
    )

    print(
        "SLAB   : 35.00 cm"
    )


if __name__ == "__main__":
    self_test()
