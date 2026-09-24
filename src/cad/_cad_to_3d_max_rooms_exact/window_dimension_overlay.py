from __future__ import annotations

import json
from pathlib import Path


ENGINE = "CAD3D_WINDOW_DIMENSION_VIEW_V1"


def build_window_dimension_overlay(root):
    root = Path(root)

    measurement_path = (
        root
        / "logs"
        / "window_vertical_measurements.json"
    )

    facade_path = (
        root
        / "logs"
        / "facade_match_runtime.json"
    )

    if not measurement_path.exists():
        raise RuntimeError(
            "window_vertical_measurements.json bulunamad\u0131"
        )

    if not facade_path.exists():
        raise RuntimeError(
            "facade_match_runtime.json bulunamad\u0131"
        )

    measurements = json.loads(
        measurement_path.read_text(
            encoding="utf-8"
        )
    )

    facade = json.loads(
        facade_path.read_text(
            encoding="utf-8"
        )
    )

    entrance = (
        measurements.get(
            "main_entrance"
        )
        or {}
    )

    datum_y = entrance.get(
        "elevation_bottom_y"
    )

    datum_facade = entrance.get(
        "facade_number"
    )

    if datum_y is None:
        raise RuntimeError(
            "MAIN ENTRANCE BOTTOM Y bulunamad\u0131"
        )

    datum_y = float(
        datum_y
    )

    matches = list(
        facade.get(
            "matches",
            []
        )
        or []
    )

    records = []
    report = []

    def find_pair(
        facade_number,
        plan_index,
        elevation_index,
    ):
        for match in matches:
            if (
                match.get(
                    "facade_number"
                )
                != facade_number
            ):
                continue

            for pair in (
                match.get(
                    "opening_pairs",
                    []
                )
                or []
            ):
                if (
                    pair.get("kind")
                    != "window"
                ):
                    continue

                if (
                    elevation_index is not None
                    and pair.get(
                        "elevation_index"
                    )
                    == elevation_index
                ):
                    return pair

                if (
                    plan_index is not None
                    and pair.get(
                        "plan_index"
                    )
                    == plan_index
                ):
                    return pair

        return None

    for row in (
        measurements.get(
            "windows",
            []
        )
        or []
    ):
        window_id = str(
            row.get(
                "window_id",
                "W"
            )
        )

        facade_number = row.get(
            "facade_number"
        )

        pair = find_pair(
            facade_number,
            row.get(
                "plan_index"
            ),
            row.get(
                "elevation_index"
            ),
        )

        if pair is None:
            continue

        bbox = pair.get(
            "elevation_bbox"
        )

        if (
            not isinstance(
                bbox,
                (list, tuple)
            )
            or len(bbox) < 4
        ):
            continue

        x0 = float(bbox[0])
        bottom_y = float(
            pair.get(
                "elevation_bottom_y",
                bbox[1],
            )
        )

        x1 = float(bbox[2])
        top_y = float(
            pair.get(
                "elevation_top_y",
                bbox[3],
            )
        )

        width = abs(
            x1 - x0
        )

        offset = max(
            180.0,
            width * 0.22,
        )

        height_raw = abs(
            top_y - bottom_y
        )

        # Window height always uses direct CAD geometry.
        records.append(
            {
                "window_id":
                    window_id,

                "kind":
                    "height",

                "feature_x":
                    x1,

                "dimension_x":
                    x1 + offset,

                "y0":
                    bottom_y,

                "y1":
                    top_y,

                "value":
                    height_raw,

                "text":
                    f"{height_raw:.2f}",
            }
        )

        sill_raw = None

        # Sill datum is valid directly only on the
        # elevation containing the main entrance.
        if (
            facade_number
            == datum_facade
        ):
            sill_raw = abs(
                bottom_y
                - datum_y
            )

            records.append(
                {
                    "window_id":
                        window_id,

                    "kind":
                        "sill",

                    "feature_x":
                        x0,

                    "dimension_x":
                        x0 - offset,

                    "y0":
                        datum_y,

                    "y1":
                        bottom_y,

                    "value":
                        sill_raw,

                    "text":
                        f"{sill_raw:.2f}",
                }
            )

        report.append(
            {
                "window_id":
                    window_id,

                "facade_number":
                    facade_number,

                "sill_raw":
                    sill_raw,

                "height_raw":
                    height_raw,

                "bottom_y":
                    bottom_y,

                "top_y":
                    top_y,
            }
        )

    return {
        "engine":
            ENGINE,

        "datum_rule":
            "MAIN_ENTRANCE_DOOR_BOTTOM",

        "datum_facade":
            datum_facade,

        "datum_y":
            datum_y,

        "records":
            records,

        "report":
            report,
    }


def self_test():
    import tempfile

    root = Path(
        tempfile.mkdtemp()
    )

    logs = root / "logs"
    logs.mkdir()

    (
        logs
        / "window_vertical_measurements.json"
    ).write_text(
        json.dumps(
            {
                "main_entrance": {
                    "facade_number": 1,
                    "elevation_bottom_y": 1000.0,
                },
                "windows": [
                    {
                        "window_id": "W01",
                        "facade_number": 1,
                        "plan_index": 0,
                        "elevation_index": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    (
        logs
        / "facade_match_runtime.json"
    ).write_text(
        json.dumps(
            {
                "matches": [
                    {
                        "facade_number": 1,
                        "opening_pairs": [
                            {
                                "kind": "window",
                                "plan_index": 0,
                                "elevation_index": 1,
                                "elevation_bbox": [
                                    2000.0,
                                    1901.67,
                                    2700.0,
                                    3400.22,
                                ],
                                "elevation_bottom_y":
                                    1901.67,
                                "elevation_top_y":
                                    3400.22,
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = (
        build_window_dimension_overlay(
            root
        )
    )

    report = result[
        "report"
    ][0]

    assert abs(
        report["sill_raw"]
        - 901.67
    ) < 1.0e-6

    assert abs(
        report["height_raw"]
        - 1498.55
    ) < 1.0e-6

    print(
        "WINDOW DIMENSION VIEW V1 SELF-TEST: OK"
    )

    print(
        "RAW SILL   : 901.67"
    )

    print(
        "RAW HEIGHT : 1498.55"
    )


if __name__ == "__main__":
    self_test()
