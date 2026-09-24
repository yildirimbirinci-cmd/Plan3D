from __future__ import annotations

import json
import math
import statistics
from pathlib import Path


ENGINE = "CAD3D_MODEL_WINDOW_SILL_INPUT_V1"
GROUND_REFERENCE_RULE = "MAIN_ENTRANCE_DOOR_BOTTOM_V1"

_CACHE_MTIME = None
_CACHE_VALUE = None


def _root():
    return Path(
        __file__
    ).resolve().parents[2]


def resolve_from_payload(
    payload,
):
    if not isinstance(
        payload,
        dict,
    ):
        raise RuntimeError(
            "WINDOW_MEASUREMENTS_INVALID"
        )

    if payload.get(
        "ok"
    ) is not True:
        raise RuntimeError(
            "WINDOW_MEASUREMENTS_NOT_READY"
        )

    if (
        payload.get(
            "ground_reference_rule"
        )
        != GROUND_REFERENCE_RULE
    ):
        raise RuntimeError(
            "GROUND_REFERENCE_RULE_MISMATCH"
        )

    values = []

    for row in (
        payload.get(
            "windows",
            [],
        )
        or []
    ):
        if int(
            row.get(
                "storey_index",
                0,
            )
            or 0
        ) != 0:
            continue

        try:
            value = float(
                row[
                    "window_bottom_z_cm"
                ]
            )
        except Exception:
            continue

        if not math.isfinite(
            value
        ):
            continue

        if value <= 0.0:
            continue

        values.append(
            value
        )

    if not values:
        raise RuntimeError(
            "NO_RESOLVED_GROUND_FLOOR_WINDOW_SILLS"
        )

    values.sort()

    target = float(
        statistics.median(
            values
        )
    )

    return {
        "engine":
            ENGINE,

        "ground_reference_rule":
            GROUND_REFERENCE_RULE,

        "storey_index":
            0,

        "source":
            "RESOLVED_GROUND_FLOOR_WINDOWS_MEDIAN",

        "candidate_sill_cm":
            values,

        "candidate_count":
            len(values),

        "connect_target_cm":
            round(
                target,
                6,
            ),
    }


def resolve_ground_floor_model_sill_cm():
    global _CACHE_MTIME
    global _CACHE_VALUE

    source = (
        _root()
        / "logs"
        / "window_vertical_measurements.json"
    )

    if not source.exists():
        raise RuntimeError(
            "window_vertical_measurements.json bulunamad\u0131. "
            "\u00d6nce Cephe Yerle\u015ftir \u00e7al\u0131\u015ft\u0131r."
        )

    mtime = source.stat().st_mtime_ns

    if (
        _CACHE_MTIME == mtime
        and _CACHE_VALUE is not None
    ):
        return _CACHE_VALUE

    payload = json.loads(
        source.read_text(
            encoding="utf-8",
        )
    )

    result = resolve_from_payload(
        payload
    )

    target = float(
        result[
            "connect_target_cm"
        ]
    )

    audit_path = (
        _root()
        / "logs"
        / "model_window_sill_runtime.json"
    )

    audit_path.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("")
    print(
        "=== MODEL WINDOW SILL INPUT ==="
    )

    print(
        "Z=0 SOURCE : MAIN ENTRANCE DOOR BOTTOM"
    )

    print(
        "GROUND FLOOR SILL CANDIDATES :",
        result[
            "candidate_sill_cm"
        ],
    )

    print(
        "CONNECT TARGET :",
        f"{target:.2f} cm",
    )

    print(
        "MAX OPTION :",
        f"WINDOW_SILL_CM={target:.6f}",
    )

    print(
        "AUDIT :",
        str(
            audit_path
        ),
    )

    print(
        "=== END MODEL WINDOW SILL INPUT ==="
    )

    print("")

    _CACHE_MTIME = mtime
    _CACHE_VALUE = target

    return target


def self_test():
    payload = {
        "ok": True,

        "ground_reference_rule":
            GROUND_REFERENCE_RULE,

        "windows": [
            {
                "storey_index": 0,
                "window_bottom_z_cm": 70.11,
            },
            {
                "storey_index": 0,
                "window_bottom_z_cm": 67.15,
            },
            {
                "storey_index": 0,
                "window_bottom_z_cm": 70.11,
            },
            {
                "storey_index": 0,
                "window_bottom_z_cm": 70.11,
            },
            {
                "storey_index": 1,
                "window_bottom_z_cm": 90.0,
            },
        ],
    }

    result = resolve_from_payload(
        payload
    )

    assert (
        result[
            "candidate_count"
        ]
        == 4
    ), result

    assert abs(
        result[
            "connect_target_cm"
        ]
        - 70.11
    ) < 1.0e-6, result

    print(
        "MODEL WINDOW SILL INPUT V1 SELF-TEST: OK"
    )

    print(
        "CONNECT TARGET: 70.11 cm"
    )


if __name__ == "__main__":
    self_test()
