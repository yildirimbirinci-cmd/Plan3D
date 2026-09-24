from __future__ import annotations

import math


ENGINE = "CAD3D_DETERMINISTIC_EXECUTION_PLAN_V1"

CURRENT_MAX_PIPELINE = (
    "build_wall_model",
    "connect_header_210",
    "bridge_doors_pairwise",
    "verify_header_210",
    "connect_window_sill_lower_band",
    "commit_replace_same_floor_model",
)

FIXED_DOOR_HEADER_CM = 210.0


def _check(
    name,
    passed,
    *,
    actual=None,
    expected=None,
    reason="",
):
    return {
        "check": str(name),
        "passed": bool(passed),
        "actual": actual,
        "expected": expected,
        "reason": str(reason),
    }


def _recognized(
    entity,
):
    if not isinstance(
        entity,
        dict,
    ):
        return False

    contract = (
        entity.get(
            "recognition_contract",
            {},
        )
        or {}
    )

    return bool(
        contract.get(
            "accepted",
            False,
        )
    )


def _permission(
    entity,
    operation,
):
    if not isinstance(
        entity,
        dict,
    ):
        return False

    permissions = (
        entity.get(
            "execution_permissions",
            {},
        )
        or {}
    )

    return bool(
        permissions.get(
            operation,
            False,
        )
    )


def _entity_id(
    entity,
):
    if not isinstance(
        entity,
        dict,
    ):
        return ""

    return str(
        entity.get(
            "entity_id",
            "",
        )
        or ""
    ).strip()


def _source_layer(
    entity,
):
    if not isinstance(
        entity,
        dict,
    ):
        return ""

    return str(
        entity.get(
            "source_layer",
            "",
        )
        or ""
    ).strip()


def _classification(
    entity,
):
    if not isinstance(
        entity,
        dict,
    ):
        return ""

    metadata = (
        entity.get(
            "metadata",
            {},
        )
        or {}
    )

    structural_relation = (
        entity.get(
            "structural_relation",
            {},
        )
        or {}
    )

    return str(
        metadata.get(
            "classification"
        )
        or structural_relation.get(
            "classification"
        )
        or ""
    ).strip().lower()


def _finite_float(
    value,
):
    try:
        value = float(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return None

    if not math.isfinite(
        value
    ):
        return None

    return value


def _point2(
    value,
):
    if not isinstance(
        value,
        (list, tuple),
    ):
        return None

    if len(value) < 2:
        return None

    x = _finite_float(
        value[0]
    )

    y = _finite_float(
        value[1]
    )

    if (
        x is None
        or y is None
    ):
        return None

    return (
        float(x),
        float(y),
    )


def _door_bridge_record(
    entity,
):
    geometry = (
        entity.get(
            "geometry",
            {},
        )
        or {}
    )

    metadata = (
        entity.get(
            "metadata",
            {},
        )
        or {}
    )

    jamb_a = _point2(
        geometry.get(
            "jamb_a"
        )
    )

    jamb_b = _point2(
        geometry.get(
            "jamb_b"
        )
    )

    pair_index = metadata.get(
        "bridge_pair_index"
    )

    try:
        pair_index = int(
            pair_index
        )
    except (
        TypeError,
        ValueError,
    ):
        pair_index = None

    width = _finite_float(
        geometry.get(
            "width"
        )
    )

    return {
        "entity_id":
            _entity_id(
                entity
            ),

        "bridge_pair_index":
            pair_index,

        "jamb_a":
            jamb_a,

        "jamb_b":
            jamb_b,

        "width":
            width,
    }


def compile_execution_plan(
    registry,
    *,
    target_layer,
    floor_height_cm,
    window_sill_cm,
    floor_context,
    door_header_height_cm=FIXED_DOOR_HEADER_CM,
):
    """
    Compile the EXISTING proven Max pipeline into a deterministic,
    read-only execution plan.

    This function:
    - does NOT run recognition;
    - does NOT change registry entities;
    - does NOT write Max files;
    - does NOT issue Max commands;
    - does NOT modify geometry.

    It only validates preconditions and produces an explicit plan.
    """

    registry = (
        registry
        if isinstance(
            registry,
            dict,
        )
        else {}
    )

    target_layer = str(
        target_layer
        or ""
    ).strip()

    floor_context = (
        floor_context
        if isinstance(
            floor_context,
            dict,
        )
        else {}
    )

    floor_height_cm = (
        _finite_float(
            floor_height_cm
        )
    )

    window_sill_cm = (
        _finite_float(
            window_sill_cm
        )
    )

    door_header_height_cm = (
        _finite_float(
            door_header_height_cm
        )
    )

    floor_label = str(
        floor_context.get(
            "floor_label",
            "",
        )
        or ""
    ).strip()

    pivot_x_mm = _finite_float(
        floor_context.get(
            "pivot_x_mm"
        )
    )

    pivot_y_mm = _finite_float(
        floor_context.get(
            "pivot_y_mm"
        )
    )

    # CAD3D_EXECUTION_FLOOR_CONTEXT_V1
    floor_index = floor_context.get(
        "floor_index"
    )

    if isinstance(floor_index, bool):
        floor_index = None

    elif floor_index is not None:
        try:
            floor_index = int(
                floor_index
            )
        except Exception:
            floor_index = None

    floor_kind = str(
        floor_context.get(
            "floor_kind",
            "",
        )
        or ""
    ).strip()

    floor_gap_cm = _finite_float(
        floor_context.get(
            "floor_gap_cm"
        )
    )

    base_z_cm = _finite_float(
        floor_context.get(
            "base_z_cm"
        )
    )

    pivot_snap = str(
        floor_context.get(
            "pivot_snap",
            "",
        )
        or ""
    ).strip()

    pivot_master = bool(
        floor_context.get(
            "pivot_master",
            False,
        )
    )

    walls = [
        entity
        for entity in (
            registry.get(
                "walls",
                [],
            )
            or []
        )
        if isinstance(
            entity,
            dict,
        )
    ]

    doors = [
        entity
        for entity in (
            registry.get(
                "doors",
                [],
            )
            or []
        )
        if isinstance(
            entity,
            dict,
        )
    ]

    windows = [
        entity
        for entity in (
            registry.get(
                "windows",
                [],
            )
            or []
        )
        if isinstance(
            entity,
            dict,
        )
    ]

    rooflights = [
        entity
        for entity in (
            registry.get(
                "rooflights",
                [],
            )
            or []
        )
        if isinstance(
            entity,
            dict,
        )
    ]

    entities = [
        entity
        for entity in (
            registry.get(
                "entities",
                [],
            )
            or []
        )
        if isinstance(
            entity,
            dict,
        )
    ]

    checks = []

    # ========================================================
    # REGISTRY CONTRACT
    # ========================================================

    expected_entity_count = (
        len(walls)
        + len(doors)
        + len(windows)
        + len(rooflights)
    )

    checks.append(
        _check(
            "registry.present",
            bool(
                registry
            ),
            actual=bool(
                registry
            ),
            expected=True,
            reason=(
                "execution requires a compiled architectural registry"
            ),
        )
    )

    checks.append(
        _check(
            "registry.entity_count_consistent",
            (
                len(entities)
                == expected_entity_count
            ),
            actual=len(
                entities
            ),
            expected=(
                expected_entity_count
            ),
            reason=(
                "registry entity total must equal wall + door + window + rooflight"
            ),
        )
    )

    checks.append(
        _check(
            "target_layer.present",
            bool(
                target_layer
            ),
            actual=target_layer,
            expected=(
                "exact structural layer"
            ),
            reason=(
                "wall execution requires the exact selected structural layer"
            ),
        )
    )

    # ========================================================
    # WALL PRECONDITIONS
    # ========================================================

    wall_ids = [
        _entity_id(
            entity
        )
        for entity in walls
    ]

    wall_recognition_ok = bool(
        walls
    ) and all(
        _recognized(
            entity
        )
        for entity in walls
    )

    wall_execution_ok = bool(
        walls
    ) and all(
        _permission(
            entity,
            "extrude_wall",
        )
        for entity in walls
    )

    wall_layer_ok = bool(
        walls
    ) and all(
        _source_layer(
            entity
        )
        == target_layer
        for entity in walls
    )

    checks.append(
        _check(
            "walls.present",
            len(
                walls
            ) > 0,
            actual=len(
                walls
            ),
            expected=">= 1",
            reason=(
                "current Max pipeline requires at least one wall contour"
            ),
        )
    )

    checks.append(
        _check(
            "walls.recognized",
            wall_recognition_ok,
            actual=sum(
                1
                for entity in walls
                if _recognized(
                    entity
                )
            ),
            expected=len(
                walls
            ),
            reason=(
                "every wall sent to execution must be recognized"
            ),
        )
    )

    checks.append(
        _check(
            "walls.extrude_permission",
            wall_execution_ok,
            actual=sum(
                1
                for entity in walls
                if _permission(
                    entity,
                    "extrude_wall",
                )
            ),
            expected=len(
                walls
            ),
            reason=(
                "every wall contour requires explicit extrude_wall permission"
            ),
        )
    )

    checks.append(
        _check(
            "walls.exact_structural_layer",
            wall_layer_ok,
            actual=sorted(
                {
                    _source_layer(
                        entity
                    )
                    for entity in walls
                }
            ),
            expected=[
                target_layer
            ],
            reason=(
                "execution wall entities must originate from the same exact structural layer"
            ),
        )
    )

    # ========================================================
    # HEIGHT / TOPOLOGY PRECONDITIONS
    # ========================================================

    header_is_fixed_210 = bool(
        door_header_height_cm is not None
        and abs(
            door_header_height_cm
            - FIXED_DOOR_HEADER_CM
        )
        <= 1.0e-9
    )

    floor_above_header = bool(
        floor_height_cm is not None
        and door_header_height_cm is not None
        and floor_height_cm
        > door_header_height_cm
    )

    sill_valid = bool(
        window_sill_cm is not None
        and window_sill_cm > 0.0
        and door_header_height_cm is not None
        and window_sill_cm
        < door_header_height_cm
    )

    checks.append(
        _check(
            "header.fixed_210_cm",
            header_is_fixed_210,
            actual=(
                door_header_height_cm
            ),
            expected=210.0,
            reason=(
                "current proven Max topology uses a fixed 210 cm header level"
            ),
        )
    )

    checks.append(
        _check(
            "floor_height.above_header",
            floor_above_header,
            actual=(
                floor_height_cm
            ),
            expected=(
                "> 210 cm"
            ),
            reason=(
                "wall extrusion must extend above the fixed header topology"
            ),
        )
    )

    checks.append(
        _check(
            "window_sill.valid_range",
            sill_valid,
            actual=(
                window_sill_cm
            ),
            expected=(
                "0 < sill < 210 cm"
            ),
            reason=(
                "current Max sill Connect requires a positive sill below header"
            ),
        )
    )

    # ========================================================
    # FLOOR / PIVOT PRECONDITIONS
    # ========================================================

    checks.append(
        _check(
            "floor.label_present",
            bool(
                floor_label
            ),
            actual=floor_label,
            expected=(
                "explicit confirmed floor label"
            ),
            reason=(
                "same-floor replacement and final naming require a confirmed floor"
            ),
        )
    )

    checks.append(
        _check(
            "floor.pivot_present",
            (
                pivot_x_mm is not None
                and pivot_y_mm is not None
            ),
            actual={
                "x":
                    pivot_x_mm,
                "y":
                    pivot_y_mm,
            },
            expected=(
                "finite pivot X/Y in mm"
            ),
            reason=(
                "door Bridge converts jamb coordinates relative to the user pivot"
            ),
        )
    )

    # ========================================================
    # DOOR PRECONDITIONS
    # ========================================================

    recognized_door_count = sum(
        1
        for entity in doors
        if _recognized(
            entity
        )
    )

    bridge_door_entities = [
        entity
        for entity in doors
        if _permission(
            entity,
            "bridge",
        )
    ]

    denied_door_entities = [
        entity
        for entity in doors
        if not _permission(
            entity,
            "bridge",
        )
    ]

    door_records = [
        _door_bridge_record(
            entity
        )
        for entity in bridge_door_entities
    ]

    door_records.sort(
        key=lambda record: (
            (
                record[
                    "bridge_pair_index"
                ]
                if record[
                    "bridge_pair_index"
                ]
                is not None
                else 10**9
            ),
            record[
                "entity_id"
            ],
        )
    )

    bridge_indices = [
        record[
            "bridge_pair_index"
        ]
        for record in door_records
    ]

    pair_indices_valid = all(
        isinstance(
            index,
            int,
        )
        and index >= 0
        for index in bridge_indices
    )

    pair_indices_unique = (
        len(
            bridge_indices
        )
        == len(
            set(
                bridge_indices
            )
        )
    )

    jambs_valid = all(
        (
            record[
                "jamb_a"
            ]
            is not None
            and record[
                "jamb_b"
            ]
            is not None
            and record[
                "width"
            ]
            is not None
            and record[
                "width"
            ] > 0.0
        )
        for record in door_records
    )

    # Current deterministic policy:
    # a recognized door must not silently disappear from the
    # execution plan. If Bridge permission is denied, the PLAN
    # is not fully executable.
    all_doors_bridge_authorized = (
        len(
            bridge_door_entities
        )
        == len(
            doors
        )
    )


    checks.append(
        _check(
            "floor.kind_present",
            bool(
                floor_kind
            ),
            actual=floor_kind,
            expected="explicit floor kind",
            reason=(
                "execution floor snapshot requires floor kind"
            ),
        )
    )

    checks.append(
        _check(
            "floor.gap_valid",
            (
                floor_gap_cm is not None
                and floor_gap_cm >= 0.0
            ),
            actual=floor_gap_cm,
            expected="finite floor gap >= 0 cm",
            reason=(
                "floor stacking requires a frozen current floor gap"
            ),
        )
    )

    checks.append(
        _check(
            "floor.base_z_present",
            base_z_cm is not None,
            actual=base_z_cm,
            expected="finite calculated base Z in cm",
            reason=(
                "Max floor placement requires deterministic base Z"
            ),
        )
    )

    checks.append(
        _check(
            "doors.recognized",
            (
                recognized_door_count
                == len(
                    doors
                )
            ),
            actual=(
                recognized_door_count
            ),
            expected=len(
                doors
            ),
            reason=(
                "every registry door must remain recognized at execution-plan time"
            ),
        )
    )

    checks.append(
        _check(
            "doors.bridge_permission_complete",
            all_doors_bridge_authorized,
            actual=len(
                bridge_door_entities
            ),
            expected=len(
                doors
            ),
            reason=(
                "recognized doors may not be silently omitted from full execution"
            ),
        )
    )

    checks.append(
        _check(
            "doors.bridge_pair_indices_valid",
            (
                pair_indices_valid
                and pair_indices_unique
            ),
            actual=(
                bridge_indices
            ),
            expected=(
                "unique non-negative bridge_pair_index values"
            ),
            reason=(
                "pairwise Bridge order must be deterministic"
            ),
        )
    )

    checks.append(
        _check(
            "doors.jamb_records_valid",
            jambs_valid,
            actual=len(
                [
                    record
                    for record in door_records
                    if (
                        record[
                            "jamb_a"
                        ]
                        is not None
                        and record[
                            "jamb_b"
                        ]
                        is not None
                    )
                ]
            ),
            expected=len(
                door_records
            ),
            reason=(
                "every Bridge operation requires resolved jamb A/B geometry"
            ),
        )
    )

    # ========================================================
    # WINDOW / ROOFLIGHT CONSISTENCY
    #
    # IMPORTANT:
    # Current Max pipeline does NOT yet perform individual
    # facade-window opening cuts.
    #
    # The current implemented stage is ONLY the global
    # lower-band Window Sill Connect.
    # ========================================================

    facade_windows_valid = all(
        (
            _recognized(
                entity
            )
            and _classification(
                entity
            )
            == "facade_window"
            and _permission(
                entity,
                "cut_wall_opening",
            )
        )
        for entity in windows
    )

    rooflights_valid = all(
        (
            _recognized(
                entity
            )
            and _classification(
                entity
            )
            == "rooflight"
            and not _permission(
                entity,
                "cut_wall_opening",
            )
        )
        for entity in rooflights
    )

    checks.append(
        _check(
            "windows.registry_consistent",
            facade_windows_valid,
            actual=len(
                windows
            ),
            expected=(
                "all facade windows recognized + cut permission"
            ),
            reason=(
                "registry semantics must remain valid even though current Max stage only prepares sill topology"
            ),
        )
    )

    checks.append(
        _check(
            "rooflights.wall_cut_denied",
            rooflights_valid,
            actual=len(
                rooflights
            ),
            expected=(
                "recognized rooflights with cut_wall_opening=False"
            ),
            reason=(
                "rooflights must never enter facade wall-cut execution"
            ),
        )
    )

    # ========================================================
    # FINAL READINESS
    # ========================================================

    ready = all(
        bool(
            item.get(
                "passed",
                False,
            )
        )
        for item in checks
    )

    denied_door_ids = [
        _entity_id(
            entity
        )
        for entity in denied_door_entities
    ]

    facade_window_ids = [
        _entity_id(
            entity
        )
        for entity in windows
    ]

    rooflight_ids = [
        _entity_id(
            entity
        )
        for entity in rooflights
    ]

    operations = [
        {
            "sequence":
                1,

            "operation":
                "build_wall_model",

            "authorized":
                bool(
                    wall_recognition_ok
                    and wall_execution_ok
                    and wall_layer_ok
                ),

            "entity_ids":
                wall_ids,

            "entity_count":
                len(
                    wall_ids
                ),

            "target_layer":
                target_layer,

            "floor_height_cm":
                floor_height_cm,

            "postcondition":
                (
                    "new wall model exists; "
                    "old same-floor model remains untouched"
                ),
        },

        {
            "sequence":
                2,

            "operation":
                "connect_header_210",

            "authorized":
                bool(
                    wall_execution_ok
                    and header_is_fixed_210
                    and floor_above_header
                ),

            "header_height_cm":
                door_header_height_cm,

            "postcondition":
                (
                    "all connected horizontal header edges resolve to 210 cm local height"
                ),
        },

        {
            "sequence":
                3,

            "operation":
                "bridge_doors_pairwise",

            "authorized":
                bool(
                    all_doors_bridge_authorized
                    and pair_indices_valid
                    and pair_indices_unique
                    and jambs_valid
                ),

            "strategy":
                "pairwise_batch",

            "preflight_all_before_mutation":
                True,

            "door_count":
                len(
                    door_records
                ),

            "records":
                door_records,

            "denied_door_ids":
                denied_door_ids,

            "postcondition":
                (
                    "each authorized door pair bridged independently"
                ),
        },

        {
            "sequence":
                4,

            "operation":
                "verify_header_210",

            "authorized":
                bool(
                    header_is_fixed_210
                ),

            "expected_height_cm":
                210.0,

            "postcondition":
                (
                    "numeric header Z verification passes"
                ),
        },

        {
            "sequence":
                5,

            "operation":
                "connect_window_sill_lower_band",

            "authorized":
                bool(
                    sill_valid
                ),

            "window_sill_cm":
                window_sill_cm,

            "header_height_cm":
                door_header_height_cm,

            "facade_window_ids":
                facade_window_ids,

            "rooflight_ids_excluded_from_wall_cut":
                rooflight_ids,

            "scope":
                (
                    "CURRENT MAX IMPLEMENTATION: "
                    "global lower-band sill topology only; "
                    "individual facade-window opening cuts are NOT executed here"
                ),

            "postcondition":
                (
                    "generated sill horizontal topology numerically matches requested sill height"
                ),
        },

        {
            "sequence":
                6,

            "operation":
                "commit_replace_same_floor_model",

            "authorized":
                bool(
                    ready
                ),

            "floor_label":
                floor_label,

            "transaction_policy": {
                "replace_old_only_after_success":
                    True,

                "keep_new_model_for_inspection_on_door_failure":
                    True,

                "keep_new_model_for_inspection_on_sill_failure":
                    True,
            },

            "postcondition":
                (
                    "old same-floor model replaced only after all required stages succeed"
                ),
        },
    ]

    return {
        "engine":
            ENGINE,

        "ready":
            bool(
                ready
            ),

        "pipeline":
            list(
                CURRENT_MAX_PIPELINE
            ),

        "target_layer":
            target_layer,

        "parameters": {
            "floor_height_cm":
                floor_height_cm,

            "door_header_height_cm":
                door_header_height_cm,

            "window_sill_cm":
                window_sill_cm,
        },

        "floor_context": {
            "floor_label":
                floor_label,

            "pivot_x_mm":
                pivot_x_mm,

            "pivot_y_mm":
                pivot_y_mm,

            "floor_index":
                floor_index,

            "floor_kind":
                floor_kind,

            "floor_gap_cm":
                floor_gap_cm,

            "base_z_cm":
                base_z_cm,

            "pivot_snap":
                pivot_snap,

            "pivot_master":
                pivot_master,
        },

        "counts": {
            "walls":
                len(
                    walls
                ),

            "doors":
                len(
                    doors
                ),

            "bridge_doors":
                len(
                    door_records
                ),

            "denied_doors":
                len(
                    denied_door_entities
                ),

            "facade_windows":
                len(
                    windows
                ),

            "rooflights":
                len(
                    rooflights
                ),
        },

        "checks":
            checks,

        "failed_checks": [
            item
            for item in checks
            if not bool(
                item.get(
                    "passed",
                    False,
                )
            )
        ],

        "operations":
            operations,

        "notes": {
            "individual_window_opening_cut":
                "not implemented in current Max pipeline",

            "recognition_is_not_execution_permission":
                True,
        },
    }


def assert_execution_plan_ready(
    plan,
):
    if not isinstance(
        plan,
        dict,
    ):
        raise RuntimeError(
            "Execution plan is missing."
        )

    if not bool(
        plan.get(
            "ready",
            False,
        )
    ):
        failed = [
            str(
                item.get(
                    "check"
                )
            )
            for item in (
                plan.get(
                    "failed_checks",
                    [],
                )
                or []
            )
        ]

        raise RuntimeError(
            "Execution plan rejected: "
            + ", ".join(
                failed
            )
        )

    return True


def self_test():
    registry = {
        "wall_count": 1,
        "door_count": 1,
        "window_count": 1,
        "rooflight_count": 1,
        "entity_count": 4,

        "walls": [
            {
                "entity_type":
                    "wall",

                "entity_id":
                    "WL001",

                "source_layer":
                    "TEST_STRUCT",

                "recognition_contract": {
                    "accepted":
                        True,
                },

                "execution_permissions": {
                    "extrude_wall":
                        True,
                },
            }
        ],

        "doors": [
            {
                "entity_type":
                    "door",

                "entity_id":
                    "D001",

                "recognition_contract": {
                    "accepted":
                        True,
                },

                "execution_permissions": {
                    "bridge":
                        True,
                },

                "geometry": {
                    "jamb_a":
                        (
                            0.0,
                            0.0,
                        ),

                    "jamb_b":
                        (
                            900.0,
                            0.0,
                        ),

                    "width":
                        900.0,
                },

                "metadata": {
                    "bridge_pair_index":
                        0,
                },
            }
        ],

        "windows": [
            {
                "entity_type":
                    "window",

                "entity_id":
                    "W001",

                "recognition_contract": {
                    "accepted":
                        True,
                },

                "execution_permissions": {
                    "cut_wall_opening":
                        True,
                },

                "metadata": {
                    "classification":
                        "facade_window",
                },
            }
        ],

        "rooflights": [
            {
                "entity_type":
                    "window",

                "entity_id":
                    "RL001",

                "recognition_contract": {
                    "accepted":
                        True,
                },

                "execution_permissions": {
                    "cut_wall_opening":
                        False,
                },

                "metadata": {
                    "classification":
                        "rooflight",
                },
            }
        ],
    }

    registry["entities"] = (
        registry["walls"]
        + registry["doors"]
        + registry["windows"]
        + registry["rooflights"]
    )

    plan = compile_execution_plan(
        registry,
        target_layer=(
            "TEST_STRUCT"
        ),
        floor_height_cm=(
            300.0
        ),
        window_sill_cm=(
            90.0
        ),
        floor_context={
            "floor_label":
                "TEST FLOOR",

            "pivot_x_mm":
                1000.0,

            "pivot_y_mm":
                2000.0,

            "floor_index":
                0,

            "floor_kind":
                "floor",

            "floor_gap_cm":
                0.0,

            "base_z_cm":
                0.0,

            "pivot_snap":
                "intersection",

            "pivot_master":
                True,
        },
    )

    assert plan[
        "ready"
    ] is True

    assert [
        item[
            "operation"
        ]
        for item in plan[
            "operations"
        ]
    ] == list(
        CURRENT_MAX_PIPELINE
    )

    assert plan[
        "counts"
    ][
        "bridge_doors"
    ] == 1

    assert plan[
        "counts"
    ][
        "rooflights"
    ] == 1

    assert_execution_plan_ready(
        plan
    )

    # --------------------------------------------------------
    # Recognized door with Bridge denied must NOT silently
    # disappear from a full execution plan.
    # --------------------------------------------------------

    bad_registry = {
        key: (
            list(value)
            if isinstance(
                value,
                list,
            )
            else value
        )
        for key, value in registry.items()
    }

    bad_door = dict(
        registry[
            "doors"
        ][0]
    )

    bad_door[
        "execution_permissions"
    ] = {
        "bridge":
            False,
    }

    bad_registry[
        "doors"
    ] = [
        bad_door
    ]

    bad_registry[
        "entities"
    ] = (
        bad_registry[
            "walls"
        ]
        + bad_registry[
            "doors"
        ]
        + bad_registry[
            "windows"
        ]
        + bad_registry[
            "rooflights"
        ]
    )

    rejected = compile_execution_plan(
        bad_registry,
        target_layer=(
            "TEST_STRUCT"
        ),
        floor_height_cm=(
            300.0
        ),
        window_sill_cm=(
            90.0
        ),
        floor_context={
            "floor_label":
                "TEST FLOOR",

            "pivot_x_mm":
                1000.0,

            "pivot_y_mm":
                2000.0,

            "floor_index":
                0,

            "floor_kind":
                "floor",

            "floor_gap_cm":
                0.0,

            "base_z_cm":
                0.0,

            "pivot_snap":
                "intersection",

            "pivot_master":
                True,
        },
    )

    assert rejected[
        "ready"
    ] is False

    failed_names = {
        item[
            "check"
        ]
        for item in rejected[
            "failed_checks"
        ]
    }

    assert (
        "doors.bridge_permission_complete"
        in failed_names
    )

    # --------------------------------------------------------
    # Invalid sill must be rejected.
    # --------------------------------------------------------

    bad_sill = compile_execution_plan(
        registry,
        target_layer=(
            "TEST_STRUCT"
        ),
        floor_height_cm=(
            300.0
        ),
        window_sill_cm=(
            220.0
        ),
        floor_context={
            "floor_label":
                "TEST FLOOR",

            "pivot_x_mm":
                1000.0,

            "pivot_y_mm":
                2000.0,

            "floor_index":
                0,

            "floor_kind":
                "floor",

            "floor_gap_cm":
                0.0,

            "base_z_cm":
                0.0,

            "pivot_snap":
                "intersection",

            "pivot_master":
                True,
        },
    )

    assert bad_sill[
        "ready"
    ] is False

    print(
        "DETERMINISTIC EXECUTION PLAN V1 SELF-TEST: OK"
    )

    print(
        "READY PLAN: True"
    )

    print(
        "UNRESOLVED DOOR PLAN: False"
    )

    print(
        "INVALID SILL PLAN: False"
    )

    print(
        "PIPELINE:"
    )

    for operation in (
        CURRENT_MAX_PIPELINE
    ):
        print(
            " - "
            + operation
        )


if __name__ == "__main__":
    self_test()
