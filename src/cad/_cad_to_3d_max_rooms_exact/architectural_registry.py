from __future__ import annotations


ENGINE = "CAD3D_ARCHITECTURAL_REGISTRY_V1"


def _classification(entity):
    metadata = (
        entity.get("metadata", {})
        or {}
    )

    structural_relation = (
        entity.get(
            "structural_relation",
            {},
        )
        or {}
    )

    value = (
        metadata.get("classification")
        or structural_relation.get(
            "classification"
        )
        or ""
    )

    return str(
        value
    ).strip().lower()


def build_architectural_registry(
    *,
    wall_entities=None,
    door_entities=None,
    window_entities=None,
):
    """
    Read-only architectural entity registry.

    No detector is executed here.
    No geometry is modified here.
    No execution permission is granted here.

    Existing ArchitecturalEntity dictionaries are collected
    and indexed only.
    """

    walls = [
        dict(entity)
        for entity in (
            wall_entities
            or []
        )
        if isinstance(
            entity,
            dict,
        )
    ]

    doors = [
        dict(entity)
        for entity in (
            door_entities
            or []
        )
        if isinstance(
            entity,
            dict,
        )
    ]

    all_window_entities = [
        dict(entity)
        for entity in (
            window_entities
            or []
        )
        if isinstance(
            entity,
            dict,
        )
    ]

    windows = []
    rooflights = []

    for entity in (
        all_window_entities
    ):
        classification = (
            _classification(
                entity
            )
        )

        if classification == "rooflight":
            rooflights.append(
                entity
            )
        else:
            windows.append(
                entity
            )

    entities = (
        list(walls)
        + list(doors)
        + list(windows)
        + list(rooflights)
    )

    duplicate_ids = []
    seen_ids = set()

    for entity in entities:
        entity_id = str(
            entity.get(
                "entity_id",
                "",
            )
            or ""
        ).strip()

        if not entity_id:
            continue

        if entity_id in seen_ids:
            duplicate_ids.append(
                entity_id
            )

        seen_ids.add(
            entity_id
        )

    if duplicate_ids:
        raise ValueError(
            "Duplicate architectural entity IDs: "
            + ", ".join(
                sorted(
                    set(
                        duplicate_ids
                    )
                )
            )
        )

    by_id = {}

    for entity in entities:
        entity_id = str(
            entity.get(
                "entity_id",
                "",
            )
            or ""
        ).strip()

        if entity_id:
            by_id[
                entity_id
            ] = entity

    recognized_count = sum(
        1
        for entity in entities
        if bool(
            (
                entity.get(
                    "recognition_contract",
                    {},
                )
                or {}
            ).get(
                "accepted",
                False,
            )
        )
    )

    wall_extrude_count = sum(
        1
        for entity in walls
        if bool(
            (
                entity.get(
                    "execution_permissions",
                    {},
                )
                or {}
            ).get(
                "extrude_wall",
                False,
            )
        )
    )

    door_bridge_count = sum(
        1
        for entity in doors
        if bool(
            (
                entity.get(
                    "execution_permissions",
                    {},
                )
                or {}
            ).get(
                "bridge",
                False,
            )
        )
    )

    window_cut_count = sum(
        1
        for entity in windows
        if bool(
            (
                entity.get(
                    "execution_permissions",
                    {},
                )
                or {}
            ).get(
                "cut_wall_opening",
                False,
            )
        )
    )

    rooflight_cut_count = sum(
        1
        for entity in rooflights
        if bool(
            (
                entity.get(
                    "execution_permissions",
                    {},
                )
                or {}
            ).get(
                "cut_wall_opening",
                False,
            )
        )
    )

    return {
        "engine":
            ENGINE,

        "wall_count":
            len(
                walls
            ),

        "door_count":
            len(
                doors
            ),

        "window_count":
            len(
                windows
            ),

        "rooflight_count":
            len(
                rooflights
            ),

        "entity_count":
            len(
                entities
            ),

        "recognized_count":
            int(
                recognized_count
            ),

        "wall_extrude_count":
            int(
                wall_extrude_count
            ),

        "door_bridge_count":
            int(
                door_bridge_count
            ),

        "window_cut_count":
            int(
                window_cut_count
            ),

        "rooflight_cut_count":
            int(
                rooflight_cut_count
            ),

        "walls":
            walls,

        "doors":
            doors,

        "windows":
            windows,

        "rooflights":
            rooflights,

        "entities":
            entities,

        "by_id":
            by_id,
    }


def self_test():
    wall = {
        "entity_type": "wall",
        "entity_id": "WL001",
        "recognition_contract": {
            "accepted": True,
        },
        "execution_permissions": {
            "extrude_wall": True,
        },
        "metadata": {},
    }

    door = {
        "entity_type": "door",
        "entity_id": "D001",
        "recognition_contract": {
            "accepted": True,
        },
        "execution_permissions": {
            "bridge": True,
        },
        "metadata": {},
    }

    window = {
        "entity_type": "window",
        "entity_id": "W001",
        "recognition_contract": {
            "accepted": True,
        },
        "execution_permissions": {
            "cut_wall_opening": True,
        },
        "metadata": {
            "classification":
                "facade_window",
        },
    }

    rooflight = {
        "entity_type": "window",
        "entity_id": "RL001",
        "recognition_contract": {
            "accepted": True,
        },
        "execution_permissions": {
            "cut_wall_opening": False,
        },
        "metadata": {
            "classification":
                "rooflight",
        },
    }

    result = (
        build_architectural_registry(
            wall_entities=[
                wall
            ],
            door_entities=[
                door
            ],
            window_entities=[
                window,
                rooflight,
            ],
        )
    )

    assert result[
        "wall_count"
    ] == 1

    assert result[
        "door_count"
    ] == 1

    assert result[
        "window_count"
    ] == 1

    assert result[
        "rooflight_count"
    ] == 1

    assert result[
        "entity_count"
    ] == 4

    assert result[
        "recognized_count"
    ] == 4

    assert result[
        "wall_extrude_count"
    ] == 1

    assert result[
        "door_bridge_count"
    ] == 1

    assert result[
        "window_cut_count"
    ] == 1

    assert result[
        "rooflight_cut_count"
    ] == 0

    print(
        "ARCHITECTURAL REGISTRY V1 SELF-TEST: OK"
    )


if __name__ == "__main__":
    self_test()
