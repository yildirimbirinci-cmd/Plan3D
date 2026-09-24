from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping

from cad._cad_to_3d_max_rooms_exact.execution_plan import CURRENT_MAX_PIPELINE


ENGINE = "CAD3D_DETERMINISTIC_EXECUTION_REQUEST_CONTRACT_V1"
REQUEST_PREFIX = "CAD_WALL_ONLY_V1"


def _nonempty(value: Any) -> str:
    return str(
        value
        or ""
    ).strip()


def build_execution_request_contract(
    execution_plan: Mapping[str, Any],
    *,
    request_id: str,
) -> Dict[str, Any]:

    if not isinstance(
        execution_plan,
        Mapping,
    ):
        raise TypeError(
            "execution_plan must be a mapping"
        )

    if not bool(
        execution_plan.get(
            "ready",
            False,
        )
    ):
        raise ValueError(
            "execution request requires READY execution plan"
        )

    request_id = _nonempty(
        request_id
    )

    if not request_id:
        raise ValueError(
            "request_id is required"
        )

    operations = list(
        execution_plan.get(
            "operations",
            [],
        )
        or []
    )

    operation_names = [
        _nonempty(
            operation.get(
                "operation"
            )
        )
        for operation in operations
    ]

    expected = list(
        CURRENT_MAX_PIPELINE
    )

    if operation_names != expected:
        raise ValueError(
            "execution plan operations do not match CURRENT_MAX_PIPELINE"
        )

    if any(
        not bool(
            operation.get(
                "authorized",
                False,
            )
        )
        for operation in operations
    ):
        raise ValueError(
            "execution request contains unauthorized operation"
        )

    return {
        "engine":
            ENGINE,

        "version":
            1,

        "request_id":
            request_id,

        "request_prefix":
            REQUEST_PREFIX,

        "request_header":
            REQUEST_PREFIX
            + "|"
            + request_id,

        "execution_plan_engine":
            _nonempty(
                execution_plan.get(
                    "engine"
                )
            ),

        "target_layer":
            _nonempty(
                execution_plan.get(
                    "target_layer"
                )
            ),

        "parameters":
            deepcopy(
                execution_plan.get(
                    "parameters",
                    {},
                )
                or {}
            ),

        "floor_context":
            deepcopy(
                execution_plan.get(
                    "floor_context",
                    {},
                )
                or {}
            ),

        "counts":
            deepcopy(
                execution_plan.get(
                    "counts",
                    {},
                )
                or {}
            ),

        "pipeline":
            expected,

        "operations": [
            {
                "sequence":
                    int(
                        operation.get(
                            "sequence"
                        )
                    ),

                "operation":
                    _nonempty(
                        operation.get(
                            "operation"
                        )
                    ),

                "authorized":
                    True,

                "postcondition":
                    _nonempty(
                        operation.get(
                            "postcondition"
                        )
                    ),
            }
            for operation in operations
        ],

        "correlation_rule":
            (
                "Max result REQUEST_ID must equal this request_id exactly"
            ),
    }


def validate_request_header(
    contract: Mapping[str, Any],
    header: str,
) -> bool:

    if not isinstance(
        contract,
        Mapping,
    ):
        return False

    return (
        _nonempty(
            header
        )
        == _nonempty(
            contract.get(
                "request_header"
            )
        )
    )


def _self_test() -> None:

    operations = [
        {
            "sequence":
                index,

            "operation":
                name,

            "authorized":
                True,

            "postcondition":
                "TEST "
                + name,
        }
        for index, name in enumerate(
            CURRENT_MAX_PIPELINE,
            start=1,
        )
    ]

    plan = {
        "engine":
            "CAD3D_DETERMINISTIC_EXECUTION_PLAN_V1",

        "ready":
            True,

        "target_layer":
            "TEST_STRUCT",

        "pipeline":
            list(
                CURRENT_MAX_PIPELINE
            ),

        "parameters": {
            "floor_height_cm":
                300.0,

            "door_header_height_cm":
                210.0,

            "window_sill_cm":
                90.0,
        },

        "floor_context": {
            "floor_label":
                "TEST FLOOR",

            "pivot_x_mm":
                1000.0,

            "pivot_y_mm":
                2000.0,
        },

        "counts":
            {},

        "operations":
            operations,
    }

    contract = (
        build_execution_request_contract(
            plan,
            request_id="123456789",
        )
    )

    assert (
        contract[
            "request_header"
        ]
        == "CAD_WALL_ONLY_V1|123456789"
    )

    assert (
        validate_request_header(
            contract,
            "CAD_WALL_ONLY_V1|123456789",
        )
        is True
    )

    assert (
        validate_request_header(
            contract,
            "CAD_WALL_ONLY_V1|OTHER",
        )
        is False
    )

    print(
        "DETERMINISTIC EXECUTION REQUEST CONTRACT V1 SELF-TEST: OK"
    )


if __name__ == "__main__":
    _self_test()
