from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from cad._cad_to_3d_max_rooms_exact.execution_plan import CURRENT_MAX_PIPELINE


ENGINE = "CAD3D_DETERMINISTIC_EXECUTION_RESULT_CONTRACT_V1"
MAX_RESULT_ENGINE = "CAD3D_MAX_EXECUTION_RESULT_V1"

SUCCESS = "success"
FAILED = "failed"


def _check(
    name: str,
    passed: bool,
    *,
    actual: Any = None,
    expected: Any = None,
    reason: str = "",
) -> Dict[str, Any]:

    return {
        "check":
            str(
                name
            ),

        "passed":
            bool(
                passed
            ),

        "actual":
            actual,

        "expected":
            expected,

        "reason":
            str(
                reason
            ),
    }


def _operation_names(
    operations: Iterable[Mapping[str, Any]],
) -> List[str]:

    return [
        str(
            operation.get(
                "operation",
                "",
            )
            or ""
        )
        for operation in operations
    ]


def build_execution_result_contract(
    execution_plan: Mapping[str, Any],
    *,
    request_id: str = "",
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
            "execution result contract requires READY execution plan"
        )

    request_id = str(
        request_id
        or ""
    ).strip()

    operations = list(
        execution_plan.get(
            "operations",
            [],
        )
        or []
    )

    pipeline = list(
        execution_plan.get(
            "pipeline",
            [],
        )
        or []
    )

    expected_pipeline = list(
        CURRENT_MAX_PIPELINE
    )

    if pipeline != expected_pipeline:
        raise ValueError(
            "execution plan pipeline does not match CURRENT_MAX_PIPELINE"
        )

    if (
        _operation_names(
            operations
        )
        != expected_pipeline
    ):
        raise ValueError(
            "execution plan operation order is inconsistent"
        )

    unauthorized = [
        str(
            operation.get(
                "operation",
                "",
            )
            or ""
        )
        for operation in operations
        if not bool(
            operation.get(
                "authorized",
                False,
            )
        )
    ]

    if unauthorized:
        raise ValueError(
            "READY execution plan contains unauthorized operations: "
            + ", ".join(
                unauthorized
            )
        )

    expected_stages = []

    for operation in operations:
        expected_stages.append(
            {
                "sequence":
                    int(
                        operation.get(
                            "sequence"
                        )
                    ),

                "operation":
                    str(
                        operation.get(
                            "operation",
                            "",
                        )
                        or ""
                    ),

                "required":
                    True,

                "postcondition":
                    str(
                        operation.get(
                            "postcondition",
                            "",
                        )
                        or ""
                    ),
            }
        )

    return {
        "engine":
            ENGINE,

        "version":
            1,

        "request_id":
            request_id,

        "execution_plan_engine":
            str(
                execution_plan.get(
                    "engine",
                    "",
                )
                or ""
            ),

        "target_layer":
            str(
                execution_plan.get(
                    "target_layer",
                    "",
                )
                or ""
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

        "expected_pipeline":
            expected_pipeline,

        "expected_stages":
            expected_stages,

        "result_schema": {
            "engine":
                MAX_RESULT_ENGINE,

            "status": [
                SUCCESS,
                FAILED,
            ],

            "required_fields": [
                "engine",
                "request_id",
                "status",
                "stages",
                "failed_stage",
            ],

            "stage_required_fields": [
                "sequence",
                "operation",
                "success",
            ],
        },

        "success_rule":
            (
                "status=success AND request_id matches AND every "
                "required stage success=True AND failed_stage is empty"
            ),

        "failure_rule":
            (
                "status=failed AND request_id matches AND failed_stage "
                "identifies the first required failed stage"
            ),
    }


def parse_max_execution_result_text(
    text: str,
) -> Dict[str, Any]:

    result: Dict[str, Any] = {
        "engine":
            "",

        "request_id":
            "",

        "status":
            "",

        "failed_stage":
            "",

        "stages":
            [],
    }

    for raw_line in str(
        text
        or ""
    ).splitlines():

        line = raw_line.strip()

        if not line:
            continue

        if line.startswith(
            "ENGINE="
        ):
            result[
                "engine"
            ] = line[
                len(
                    "ENGINE="
                ):
            ].strip()
            continue

        if line.startswith(
            "REQUEST_ID="
        ):
            result[
                "request_id"
            ] = line[
                len(
                    "REQUEST_ID="
                ):
            ].strip()
            continue

        if line.startswith(
            "STATUS="
        ):
            result[
                "status"
            ] = line[
                len(
                    "STATUS="
                ):
            ].strip().lower()
            continue

        if line.startswith(
            "FAILED_STAGE="
        ):
            result[
                "failed_stage"
            ] = line[
                len(
                    "FAILED_STAGE="
                ):
            ].strip()
            continue

        if line.startswith(
            "STAGE="
        ):
            payload = line[
                len(
                    "STAGE="
                ):
            ]

            parts = payload.split(
                "|"
            )

            if len(
                parts
            ) != 3:
                continue

            try:
                sequence = int(
                    parts[0]
                )
            except Exception:
                sequence = None

            success_token = (
                parts[2]
                .strip()
                .lower()
            )

            success = (
                True
                if success_token
                in {
                    "1",
                    "true",
                }
                else False
                if success_token
                in {
                    "0",
                    "false",
                }
                else None
            )

            result[
                "stages"
            ].append(
                {
                    "sequence":
                        sequence,

                    "operation":
                        parts[
                            1
                        ].strip(),

                    "success":
                        success,
                }
            )

    return result


def read_max_execution_result(
    path,
) -> Dict[str, Any]:

    path = Path(
        path
    )

    if not path.exists():
        return {}

    try:
        text = path.read_text(
            encoding="utf-8-sig"
        )
    except Exception:
        return {}

    return (
        parse_max_execution_result_text(
            text
        )
    )


def validate_execution_result(
    contract: Mapping[str, Any],
    result: Mapping[str, Any],
) -> Dict[str, Any]:

    checks: List[
        Dict[str, Any]
    ] = []

    if not isinstance(
        contract,
        Mapping,
    ):
        raise TypeError(
            "contract must be a mapping"
        )

    if not isinstance(
        result,
        Mapping,
    ):
        result = {}

    expected_stages = list(
        contract.get(
            "expected_stages",
            [],
        )
        or []
    )

    expected_names = (
        _operation_names(
            expected_stages
        )
    )

    expected_request_id = str(
        contract.get(
            "request_id",
            "",
        )
        or ""
    ).strip()

    actual_request_id = str(
        result.get(
            "request_id",
            "",
        )
        or ""
    ).strip()

    checks.append(
        _check(
            "result.request_id",
            (
                bool(
                    expected_request_id
                )
                and actual_request_id
                == expected_request_id
            ),
            actual=actual_request_id,
            expected=expected_request_id,
            reason=(
                "result must belong to the exact execution request"
            ),
        )
    )

    result_engine = str(
        result.get(
            "engine",
            "",
        )
        or ""
    )

    checks.append(
        _check(
            "result.engine",
            result_engine
            == MAX_RESULT_ENGINE,
            actual=result_engine,
            expected=MAX_RESULT_ENGINE,
            reason=(
                "result must identify deterministic Max result schema"
            ),
        )
    )

    status = str(
        result.get(
            "status",
            "",
        )
        or ""
    ).strip().lower()

    checks.append(
        _check(
            "result.status",
            status
            in {
                SUCCESS,
                FAILED,
            },
            actual=status,
            expected=[
                SUCCESS,
                FAILED,
            ],
            reason=(
                "result status must be explicit"
            ),
        )
    )

    result_stages = list(
        result.get(
            "stages",
            [],
        )
        or []
    )

    result_names = (
        _operation_names(
            result_stages
        )
    )

    checks.append(
        _check(
            "result.stage_count",
            len(
                result_stages
            )
            == len(
                expected_stages
            ),
            actual=len(
                result_stages
            ),
            expected=len(
                expected_stages
            ),
            reason=(
                "one result stage is required for every plan stage"
            ),
        )
    )

    checks.append(
        _check(
            "result.stage_order",
            result_names
            == expected_names,
            actual=result_names,
            expected=expected_names,
            reason=(
                "result stage order must equal Execution Plan"
            ),
        )
    )

    sequence_valid = True
    success_values_valid = True
    stage_success = []

    for index, expected in enumerate(
        expected_stages
    ):

        if index >= len(
            result_stages
        ):
            sequence_valid = False
            success_values_valid = False
            break

        actual = result_stages[
            index
        ]

        try:
            actual_sequence = int(
                actual.get(
                    "sequence"
                )
            )
        except Exception:
            actual_sequence = None

        expected_sequence = int(
            expected.get(
                "sequence"
            )
        )

        if (
            actual_sequence
            != expected_sequence
        ):
            sequence_valid = False

        success = actual.get(
            "success"
        )

        if not isinstance(
            success,
            bool,
        ):
            success_values_valid = False
            stage_success.append(
                False
            )
        else:
            stage_success.append(
                success
            )

    checks.append(
        _check(
            "result.stage_sequences",
            sequence_valid,
            actual=[
                stage.get(
                    "sequence"
                )
                for stage
                in result_stages
            ],
            expected=[
                stage.get(
                    "sequence"
                )
                for stage
                in expected_stages
            ],
            reason=(
                "stage sequence numbers must be deterministic"
            ),
        )
    )

    checks.append(
        _check(
            "result.stage_success_values",
            success_values_valid,
            actual=[
                stage.get(
                    "success"
                )
                for stage
                in result_stages
            ],
            expected=(
                "boolean success for every stage"
            ),
            reason=(
                "every stage must state its postcondition result"
            ),
        )
    )

    failed_stage = str(
        result.get(
            "failed_stage",
            "",
        )
        or ""
    ).strip()

    all_success = bool(
        len(
            stage_success
        )
        == len(
            expected_stages
        )
        and all(
            stage_success
        )
    )

    first_failed = ""

    for index, success in enumerate(
        stage_success
    ):
        if success:
            continue

        if index < len(
            expected_names
        ):
            first_failed = (
                expected_names[
                    index
                ]
            )

        break

    if status == SUCCESS:
        status_consistent = bool(
            all_success
            and not failed_stage
        )

    elif status == FAILED:
        status_consistent = bool(
            not all_success
            and failed_stage
            and failed_stage
            == first_failed
        )

    else:
        status_consistent = False

    checks.append(
        _check(
            "result.status_consistency",
            status_consistent,
            actual={
                "status":
                    status,

                "failed_stage":
                    failed_stage,

                "first_failed_stage":
                    first_failed,

                "all_stages_success":
                    all_success,
            },
            expected=(
                "success => all pass; failed => failed_stage "
                "equals first failed stage"
            ),
            reason=(
                "overall result must agree with stage results"
            ),
        )
    )

    failed_checks = [
        item
        for item in checks
        if not bool(
            item.get(
                "passed",
                False,
            )
        )
    ]

    contract_valid = (
        len(
            failed_checks
        )
        == 0
    )

    execution_success = bool(
        contract_valid
        and status
        == SUCCESS
        and all_success
    )

    return {
        "engine":
            ENGINE,

        "request_id":
            expected_request_id,

        "contract_valid":
            contract_valid,

        "execution_success":
            execution_success,

        "status":
            status,

        "failed_stage":
            failed_stage,

        "checks":
            checks,

        "failed_checks":
            failed_checks,
    }


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

        "pipeline":
            list(
                CURRENT_MAX_PIPELINE
            ),

        "target_layer":
            "TEST_STRUCT",

        "parameters":
            {},

        "floor_context":
            {},

        "counts":
            {},

        "operations":
            operations,
    }

    contract = (
        build_execution_result_contract(
            plan,
            request_id="REQ-1",
        )
    )

    success_text = "\n".join(
        [
            "ENGINE=CAD3D_MAX_EXECUTION_RESULT_V1",
            "REQUEST_ID=REQ-1",
            "STATUS=success",
            "FAILED_STAGE=",
        ]
        + [
            (
                "STAGE="
                + str(index)
                + "|"
                + name
                + "|1"
            )
            for index, name
            in enumerate(
                CURRENT_MAX_PIPELINE,
                start=1,
            )
        ]
    )

    success_result = (
        parse_max_execution_result_text(
            success_text
        )
    )

    success_validation = (
        validate_execution_result(
            contract,
            success_result,
        )
    )

    assert (
        success_validation[
            "contract_valid"
        ]
        is True
    )

    assert (
        success_validation[
            "execution_success"
        ]
        is True
    )

    failed_lines = [
        "ENGINE=CAD3D_MAX_EXECUTION_RESULT_V1",
        "REQUEST_ID=REQ-1",
        "STATUS=failed",
        "FAILED_STAGE=bridge_doors_pairwise",
    ]

    for index, name in enumerate(
        CURRENT_MAX_PIPELINE,
        start=1,
    ):
        failed_lines.append(
            "STAGE="
            + str(
                index
            )
            + "|"
            + name
            + "|"
            + (
                "1"
                if index < 3
                else "0"
            )
        )

    failed_result = (
        parse_max_execution_result_text(
            "\n".join(
                failed_lines
            )
        )
    )

    failed_validation = (
        validate_execution_result(
            contract,
            failed_result,
        )
    )

    assert (
        failed_validation[
            "contract_valid"
        ]
        is True
    )

    assert (
        failed_validation[
            "execution_success"
        ]
        is False
    )

    wrong_id_result = (
        dict(
            success_result
        )
    )

    wrong_id_result[
        "request_id"
    ] = "OTHER"

    wrong_id_validation = (
        validate_execution_result(
            contract,
            wrong_id_result,
        )
    )

    assert (
        wrong_id_validation[
            "contract_valid"
        ]
        is False
    )

    print(
        "DETERMINISTIC EXECUTION RESULT CONTRACT V1 SELF-TEST: OK"
    )
    print(
        "REQUEST CORRELATION: OK"
    )
    print(
        "SUCCESS RESULT: OK"
    )
    print(
        "FAILED RESULT: OK"
    )
    print(
        "WRONG REQUEST ID REJECTED: OK"
    )


if __name__ == "__main__":
    _self_test()
