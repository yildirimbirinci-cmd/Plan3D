from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any
import math


ENGINE_NAME = "CAD3D_GEOMETRIC_WINDOW_GRAPH_V6"


# ============================================================
# LOW LEVEL GEOMETRY
# ============================================================


@dataclass(frozen=True)
class RectCandidate:
    x0: float
    y0: float
    x1: float
    y1: float

    left_support: float
    right_support: float
    bottom_support: float
    top_support: float

    left_specificity: float
    right_specificity: float
    bottom_specificity: float
    top_specificity: float

    internal_vertical_count: int
    internal_horizontal_count: int

    frame_score: float = 0.0
    nested_count: int = 0
    repetition_score: float = 0.0
    window_score: float = 0.0
    door_like: bool = False

    @property
    def width(self) -> float:
        return max(
            self.x1 - self.x0,
            1.0e-9,
        )

    @property
    def height(self) -> float:
        return max(
            self.y1 - self.y0,
            1.0e-9,
        )

    @property
    def area(self) -> float:
        return (
            self.width
            * self.height
        )

    @property
    def cx(self) -> float:
        return (
            self.x0 + self.x1
        ) * 0.5

    @property
    def cy(self) -> float:
        return (
            self.y0 + self.y1
        ) * 0.5

    @property
    def aspect(self) -> float:
        return (
            self.width
            / self.height
        )

    @property
    def bbox(self):
        return (
            self.x0,
            self.y0,
            self.x1,
            self.y1,
        )


def _clamp01(
    value: float,
) -> float:
    return max(
        0.0,
        min(
            1.0,
            float(value),
        ),
    )


def _interval_union_length(
    intervals,
) -> float:
    clean = []

    for a, b in intervals:
        a = float(a)
        b = float(b)

        if b < a:
            a, b = b, a

        if b > a:
            clean.append(
                (a, b)
            )

    if not clean:
        return 0.0

    clean.sort()

    total = 0.0

    current_a, current_b = (
        clean[0]
    )

    for a, b in clean[1:]:

        if a <= current_b:
            current_b = max(
                current_b,
                b,
            )
        else:
            total += (
                current_b
                - current_a
            )

            current_a, current_b = (
                a,
                b,
            )

    total += (
        current_b
        - current_a
    )

    return total


def _horizontal_support(
    horizontal,
    target_y: float,
    x0: float,
    x1: float,
    tolerance_y: float,
):
    width = max(
        x1 - x0,
        1.0e-9,
    )

    intervals = []
    specificity = 0.0

    for line in horizontal:

        try:
            y = float(
                line["y"]
            )

            lx0 = float(
                line["x0"]
            )

            lx1 = float(
                line["x1"]
            )

        except Exception:
            continue

        if abs(
            y - target_y
        ) > tolerance_y:
            continue

        overlap0 = max(
            x0,
            lx0,
        )

        overlap1 = min(
            x1,
            lx1,
        )

        if overlap1 <= overlap0:
            continue

        intervals.append(
            (
                overlap0,
                overlap1,
            )
        )

        source_length = max(
            lx1 - lx0,
            1.0e-9,
        )

        source_ratio = (
            source_length
            / width
        )

        local_specificity = (
            1.0
            / max(
                1.0,
                source_ratio,
            )
        )

        specificity = max(
            specificity,
            local_specificity,
        )

    coverage = (
        _interval_union_length(
            intervals
        )
        / width
    )

    return (
        _clamp01(
            coverage
        ),
        _clamp01(
            specificity
        ),
    )


def _vertical_support(
    vertical,
    target_x: float,
    y0: float,
    y1: float,
    tolerance_x: float,
):
    height = max(
        y1 - y0,
        1.0e-9,
    )

    intervals = []
    specificity = 0.0

    for line in vertical:

        try:
            x = float(
                line["x"]
            )

            ly0 = float(
                line["y0"]
            )

            ly1 = float(
                line["y1"]
            )

        except Exception:
            continue

        if abs(
            x - target_x
        ) > tolerance_x:
            continue

        overlap0 = max(
            y0,
            ly0,
        )

        overlap1 = min(
            y1,
            ly1,
        )

        if overlap1 <= overlap0:
            continue

        intervals.append(
            (
                overlap0,
                overlap1,
            )
        )

        source_length = max(
            ly1 - ly0,
            1.0e-9,
        )

        source_ratio = (
            source_length
            / height
        )

        local_specificity = (
            1.0
            / max(
                1.0,
                source_ratio,
            )
        )

        specificity = max(
            specificity,
            local_specificity,
        )

    coverage = (
        _interval_union_length(
            intervals
        )
        / height
    )

    return (
        _clamp01(
            coverage
        ),
        _clamp01(
            specificity
        ),
    )


def _contains(
    outer: RectCandidate,
    inner: RectCandidate,
    tolerance_fraction: float = 0.015,
) -> bool:
    tx = (
        outer.width
        * tolerance_fraction
    )

    ty = (
        outer.height
        * tolerance_fraction
    )

    return (
        inner.x0
        >= outer.x0 - tx
        and
        inner.x1
        <= outer.x1 + tx
        and
        inner.y0
        >= outer.y0 - ty
        and
        inner.y1
        <= outer.y1 + ty
    )


def _intersection_area(
    a: RectCandidate,
    b: RectCandidate,
) -> float:
    return (
        max(
            0.0,
            min(
                a.x1,
                b.x1,
            )
            - max(
                a.x0,
                b.x0,
            ),
        )
        *
        max(
            0.0,
            min(
                a.y1,
                b.y1,
            )
            - max(
                a.y0,
                b.y0,
            ),
        )
    )


def _iou(
    a: RectCandidate,
    b: RectCandidate,
) -> float:
    intersection = (
        _intersection_area(
            a,
            b,
        )
    )

    union = (
        a.area
        + b.area
        - intersection
    )

    if union <= 1.0e-9:
        return 0.0

    return (
        intersection
        / union
    )


# ============================================================
# CAD SEGMENT NORMALIZATION
# ============================================================


def _prepare_segments(
    geometry,
    bounds,
):
    from cad._cad_to_3d_max_rooms_exact.elevation_opening_detector import (
        _extract_axis_segments,
        _merge_horizontal,
        _merge_vertical,
        _detect_ground_line,
    )

    (
        horizontal,
        vertical,
    ) = _extract_axis_segments(
        list(
            geometry
            or []
        )
    )

    x0, y0, x1, y1 = (
        float(v)
        for v in bounds
    )

    facade_width = max(
        x1 - x0,
        1.0,
    )

    facade_height = max(
        y1 - y0,
        1.0,
    )

    horizontal = _merge_horizontal(
        horizontal,
        y_tolerance=max(
            facade_height * 0.0015,
            1.0e-7,
        ),
        gap_tolerance=max(
            facade_width * 0.0020,
            1.0e-7,
        ),
    )

    vertical = _merge_vertical(
        vertical,
        x_tolerance=max(
            facade_width * 0.0015,
            1.0e-7,
        ),
        gap_tolerance=max(
            facade_height * 0.0020,
            1.0e-7,
        ),
    )

    ground_y = _detect_ground_line(
        horizontal,
        bounds,
    )

    return (
        horizontal,
        vertical,
        float(
            ground_y
        ),
    )


# ============================================================
# GRAPH NODE COORDINATES
# ============================================================


def _cluster_coordinates(
    values,
    tolerance,
):
    values = sorted(
        float(v)
        for v in values
    )

    if not values:
        return []

    groups = [
        [
            values[0]
        ]
    ]

    for value in values[1:]:

        current = groups[-1]

        center = (
            sum(
                current
            )
            / len(
                current
            )
        )

        if abs(
            value - center
        ) <= tolerance:
            current.append(
                value
            )

        else:
            groups.append(
                [
                    value
                ]
            )

    return [
        sum(
            group
        )
        / len(
            group
        )
        for group in groups
    ]


def _graph_axes(
    horizontal,
    vertical,
    bounds,
):
    x0, y0, x1, y1 = (
        float(v)
        for v in bounds
    )

    width = max(
        x1 - x0,
        1.0,
    )

    height = max(
        y1 - y0,
        1.0,
    )

    x_tolerance = max(
        width * 0.0022,
        1.0e-7,
    )

    y_tolerance = max(
        height * 0.0022,
        1.0e-7,
    )

    xs = _cluster_coordinates(
        [
            float(
                row["x"]
            )
            for row in vertical
        ],
        x_tolerance,
    )

    ys = _cluster_coordinates(
        [
            float(
                row["y"]
            )
            for row in horizontal
        ],
        y_tolerance,
    )

    return (
        xs,
        ys,
        x_tolerance,
        y_tolerance,
    )


# ============================================================
# INTERNAL WINDOW STRUCTURE
# ============================================================


def _internal_structure(
    horizontal,
    vertical,
    x0,
    y0,
    x1,
    y1,
):
    width = max(
        x1 - x0,
        1.0e-9,
    )

    height = max(
        y1 - y0,
        1.0e-9,
    )

    vertical_count = 0
    horizontal_count = 0

    for line in vertical:

        try:
            x = float(
                line["x"]
            )

            ly0 = float(
                line["y0"]
            )

            ly1 = float(
                line["y1"]
            )

        except Exception:
            continue

        if not (
            x0 + width * 0.06
            < x
            < x1 - width * 0.06
        ):
            continue

        overlap = max(
            0.0,
            min(
                y1,
                ly1,
            )
            - max(
                y0,
                ly0,
            ),
        )

        coverage = (
            overlap / height
        )

        source_height = max(
            ly1 - ly0,
            1.0e-9,
        )

        # Mullion / sash, not a building column.
        if (
            coverage >= 0.24
            and
            source_height
            <= height * 1.35
        ):
            vertical_count += 1

    for line in horizontal:

        try:
            y = float(
                line["y"]
            )

            lx0 = float(
                line["x0"]
            )

            lx1 = float(
                line["x1"]
            )

        except Exception:
            continue

        if not (
            y0 + height * 0.06
            < y
            < y1 - height * 0.06
        ):
            continue

        overlap = max(
            0.0,
            min(
                x1,
                lx1,
            )
            - max(
                x0,
                lx0,
            ),
        )

        coverage = (
            overlap / width
        )

        source_width = max(
            lx1 - lx0,
            1.0e-9,
        )

        # Transom / sash, not long facade cladding.
        if (
            coverage >= 0.30
            and
            source_width
            <= width * 1.35
        ):
            horizontal_count += 1

    return (
        vertical_count,
        horizontal_count,
    )


# ============================================================
# CLOSED FOUR-SIDED CYCLE GENERATION
# ============================================================


def _generate_closed_cycles(
    horizontal,
    vertical,
    bounds,
):
    """
    CAD3D_SPARSE_GRAPH_CYCLE_V5

    TRUE SPARSE RECTANGLE GENERATION

    Previous versions combined arbitrary X axes with arbitrary
    Y axes. That created thousands of geometrically possible
    but architecturally nonexistent rectangles.

    V5 starts from REAL horizontal structural edges.

        horizontal edge
            ->
        left endpoint connects to vertical jamb
            +
        right endpoint connects to vertical jamb
            ->
        same jamb pair has another horizontal edge
            ->
        both vertical jambs support the complete span
            ->
        closed structural cycle

    Complexity therefore follows the actual drawing topology,
    not the Cartesian product of all X/Y axes.
    """

    bx0, by0, bx1, by1 = (
        float(v)
        for v in bounds
    )

    facade_width = max(
        bx1 - bx0,
        1.0,
    )

    facade_height = max(
        by1 - by0,
        1.0,
    )


    x_tolerance = max(
        facade_width * 0.0025,
        1.0e-7,
    )

    y_tolerance = max(
        facade_height * 0.0025,
        1.0e-7,
    )


    vertical_rows = []

    for index, line in enumerate(
        vertical or []
    ):

        try:
            x = float(
                line["x"]
            )

            y0 = float(
                line["y0"]
            )

            y1 = float(
                line["y1"]
            )

        except Exception:
            continue


        if y1 < y0:
            y0, y1 = (
                y1,
                y0,
            )


        if (
            y1 - y0
        ) <= 1.0e-9:
            continue


        vertical_rows.append(
            {
                "index":
                    int(
                        index
                    ),

                "x":
                    x,

                "y0":
                    y0,

                "y1":
                    y1,
            }
        )


    # ========================================================
    # FIND VERTICAL JAMBS CONNECTED TO A HORIZONTAL ENDPOINT
    # ========================================================

    def endpoint_verticals(
        endpoint_x,
        horizontal_y,
        horizontal_width,
    ):
        # Local tolerance adapts to the structural member.
        #
        # Small frame-thickness differences are allowed,
        # large sill overhangs are not.
        endpoint_tolerance = max(
            x_tolerance,
            horizontal_width * 0.035,
        )

        matches = []


        for row in vertical_rows:

            dx = abs(
                row[
                    "x"
                ]
                - endpoint_x
            )

            if dx > endpoint_tolerance:
                continue


            # Jamb must actually reach this horizontal.
            if not (
                row[
                    "y0"
                ]
                - y_tolerance
                <= horizontal_y
                <= row[
                    "y1"
                ]
                + y_tolerance
            ):
                continue


            matches.append(
                (
                    dx,
                    row,
                )
            )


        matches.sort(
            key=lambda item:
                item[0]
        )


        # At a frame corner there may be several almost
        # coincident CAD lines. Keep only the local nearest
        # structural alternatives.
        return [
            row
            for _, row
            in matches[:4]
        ]


    # ========================================================
    # BUILD JAMB-PAIR -> HORIZONTAL-EDGE MAP
    # ========================================================

    pair_edges = {}


    for horizontal_index, line in enumerate(
        horizontal or []
    ):

        try:
            y = float(
                line["y"]
            )

            hx0 = float(
                line["x0"]
            )

            hx1 = float(
                line["x1"]
            )

        except Exception:
            continue


        if hx1 < hx0:
            hx0, hx1 = (
                hx1,
                hx0,
            )


        horizontal_width = (
            hx1 - hx0
        )


        if horizontal_width <= 1.0e-9:
            continue


        width_fraction = (
            horizontal_width
            / facade_width
        )


        # Ignore facade-wide datum/cladding lines as direct
        # window-frame proposals.
        if not (
            0.006
            <= width_fraction
            <= 0.60
        ):
            continue


        left_matches = (
            endpoint_verticals(
                hx0,
                y,
                horizontal_width,
            )
        )

        right_matches = (
            endpoint_verticals(
                hx1,
                y,
                horizontal_width,
            )
        )


        if not left_matches:
            continue

        if not right_matches:
            continue


        for left in left_matches:

            for right in right_matches:

                if (
                    right[
                        "x"
                    ]
                    <= left[
                        "x"
                    ]
                ):
                    continue


                frame_width = (
                    right[
                        "x"
                    ]
                    - left[
                        "x"
                    ]
                )


                if frame_width <= 1.0e-9:
                    continue


                # Horizontal edge must correspond closely to
                # this jamb pair.
                left_overhang = (
                    left[
                        "x"
                    ]
                    - hx0
                ) / frame_width

                right_overhang = (
                    hx1
                    - right[
                        "x"
                    ]
                ) / frame_width


                left_inset = (
                    hx0
                    - left[
                        "x"
                    ]
                ) / frame_width

                right_inset = (
                    right[
                        "x"
                    ]
                    - hx1
                ) / frame_width


                # Large two-sided overhang = sill / ledge,
                # not frame cap.
                projecting = (
                    left_overhang >= 0.018
                    and
                    right_overhang >= 0.018
                )


                if projecting:
                    continue


                # A true frame cap should not terminate far
                # inside its jambs either.
                if (
                    left_inset > 0.08
                    or
                    right_inset > 0.08
                ):
                    continue


                key = (
                    int(
                        left[
                            "index"
                        ]
                    ),
                    int(
                        right[
                            "index"
                        ]
                    ),
                )


                pair_edges.setdefault(
                    key,
                    []
                ).append(
                    {
                        "y":
                            float(
                                y
                            ),

                        "horizontal_index":
                            int(
                                horizontal_index
                            ),

                        "x0":
                            float(
                                hx0
                            ),

                        "x1":
                            float(
                                hx1
                            ),

                        "left":
                            left,

                        "right":
                            right,
                    }
                )


    # ========================================================
    # CLUSTER DUPLICATE HORIZONTAL EDGES PER JAMB PAIR
    # ========================================================

    for key, rows in list(
        pair_edges.items()
    ):

        rows.sort(
            key=lambda row:
                row[
                    "y"
                ]
        )


        clustered = []


        for row in rows:

            if not clustered:

                clustered.append(
                    row
                )

                continue


            previous = clustered[
                -1
            ]


            if abs(
                row[
                    "y"
                ]
                - previous[
                    "y"
                ]
            ) <= y_tolerance:

                previous_width = (
                    previous[
                        "x1"
                    ]
                    - previous[
                        "x0"
                    ]
                )

                row_width = (
                    row[
                        "x1"
                    ]
                    - row[
                        "x0"
                    ]
                )


                # Prefer edge matching jamb span more closely.
                left = row[
                    "left"
                ]

                right = row[
                    "right"
                ]

                jamb_width = max(
                    right[
                        "x"
                    ]
                    - left[
                        "x"
                    ],
                    1.0e-9,
                )


                previous_error = (
                    abs(
                        previous_width
                        - jamb_width
                    )
                    / jamb_width
                )

                row_error = (
                    abs(
                        row_width
                        - jamb_width
                    )
                    / jamb_width
                )


                if row_error < previous_error:

                    clustered[
                        -1
                    ] = row


            else:

                clustered.append(
                    row
                )


        pair_edges[
            key
        ] = clustered


    # ========================================================
    # BUILD TRUE CLOSED FOUR-SIDED CYCLES
    # ========================================================

    candidates = []


    for key, edges in pair_edges.items():

        if len(
            edges
        ) < 2:
            continue


        left = edges[
            0
        ][
            "left"
        ]

        right = edges[
            0
        ][
            "right"
        ]


        x0 = float(
            left[
                "x"
            ]
        )

        x1 = float(
            right[
                "x"
            ]
        )


        width = (
            x1 - x0
        )


        if width <= 1.0e-9:
            continue


        width_fraction = (
            width
            / facade_width
        )


        if not (
            0.006
            <= width_fraction
            <= 0.58
        ):
            continue


        for bottom_index in range(
            len(
                edges
            )
        ):

            bottom = edges[
                bottom_index
            ]

            y0 = float(
                bottom[
                    "y"
                ]
            )


            for top_index in range(
                bottom_index + 1,
                len(
                    edges
                )
            ):

                top = edges[
                    top_index
                ]

                y1 = float(
                    top[
                        "y"
                    ]
                )


                height = (
                    y1 - y0
                )


                if height <= 1.0e-9:
                    continue


                height_fraction = (
                    height
                    / facade_height
                )


                if not (
                    0.020
                    <= height_fraction
                    <= 0.72
                ):
                    continue


                aspect = (
                    width
                    / height
                )


                if not (
                    0.10
                    <= aspect
                    <= 6.0
                ):
                    continue


                # =================================================
                # HARD CLOSURE TEST:
                # both real jambs must span bottom -> top.
                # =================================================

                left_overlap = max(
                    0.0,
                    min(
                        y1,
                        left[
                            "y1"
                        ],
                    )
                    - max(
                        y0,
                        left[
                            "y0"
                        ],
                    ),
                )


                right_overlap = max(
                    0.0,
                    min(
                        y1,
                        right[
                            "y1"
                        ],
                    )
                    - max(
                        y0,
                        right[
                            "y0"
                        ],
                    ),
                )


                left_support = (
                    left_overlap
                    / height
                )

                right_support = (
                    right_overlap
                    / height
                )


                if (
                    left_support < 0.82
                    or
                    right_support < 0.82
                ):
                    continue


                # =================================================
                # HORIZONTAL SUPPORT
                # =================================================

                (
                    bottom_support,
                    bottom_specificity,
                ) = _horizontal_support(
                    horizontal,
                    y0,
                    x0,
                    x1,
                    y_tolerance,
                )


                (
                    top_support,
                    top_specificity,
                ) = _horizontal_support(
                    horizontal,
                    y1,
                    x0,
                    x1,
                    y_tolerance,
                )


                if (
                    bottom_support < 0.78
                    or
                    top_support < 0.78
                ):
                    continue


                # =================================================
                # VERTICAL SPECIFICITY
                #
                # Long building columns should be weaker than
                # jambs that correspond closely to this opening.
                # =================================================

                left_source_height = max(
                    left[
                        "y1"
                    ]
                    - left[
                        "y0"
                    ],
                    1.0e-9,
                )


                right_source_height = max(
                    right[
                        "y1"
                    ]
                    - right[
                        "y0"
                    ],
                    1.0e-9,
                )


                left_specificity = (
                    1.0
                    / max(
                        1.0,
                        left_source_height
                        / height,
                    )
                )


                right_specificity = (
                    1.0
                    / max(
                        1.0,
                        right_source_height
                        / height,
                    )
                )


                # =================================================
                # INTERNAL STRUCTURAL EVIDENCE
                # =================================================

                (
                    internal_vertical_count,
                    internal_horizontal_count,
                ) = _internal_structure(
                    horizontal,
                    vertical,
                    x0,
                    y0,
                    x1,
                    y1,
                )


                side_quality = (
                    left_support
                    + right_support
                    + bottom_support
                    + top_support
                ) / 4.0


                specificity_quality = (
                    left_specificity
                    + right_specificity
                    + bottom_specificity
                    + top_specificity
                ) / 4.0


                frame_score = (
                    side_quality
                    * 4.0
                    +
                    specificity_quality
                    * 2.5
                )


                candidates.append(
                    RectCandidate(
                        x0=float(
                            x0
                        ),

                        y0=float(
                            y0
                        ),

                        x1=float(
                            x1
                        ),

                        y1=float(
                            y1
                        ),

                        left_support=float(
                            left_support
                        ),

                        right_support=float(
                            right_support
                        ),

                        bottom_support=float(
                            bottom_support
                        ),

                        top_support=float(
                            top_support
                        ),

                        left_specificity=float(
                            left_specificity
                        ),

                        right_specificity=float(
                            right_specificity
                        ),

                        bottom_specificity=float(
                            bottom_specificity
                        ),

                        top_specificity=float(
                            top_specificity
                        ),

                        internal_vertical_count=int(
                            internal_vertical_count
                        ),

                        internal_horizontal_count=int(
                            internal_horizontal_count
                        ),

                        frame_score=float(
                            frame_score
                        ),
                    )
                )


    # ========================================================
    # EXACT BBOX DEDUPE
    # ========================================================

    unique = {}


    for row in candidates:

        key = tuple(
            round(
                value,
                5,
            )
            for value
            in row.bbox
        )


        previous = unique.get(
            key
        )


        if (
            previous is None
            or row.frame_score
            > previous.frame_score
        ):

            unique[
                key
            ] = row


    result = list(
        unique.values()
    )


    print(
        "SPARSE GRAPH"
        " | jamb pairs:",
        len(
            pair_edges
        ),
        "| closed cycles:",
        len(
            result
        ),
    )


    return result


# ============================================================
# CONTAINMENT TREE + WINDOW SIGNATURE
# ============================================================



# ============================================================
# CAD3D_RAW_ELEVATION_DOOR_ENVELOPE_V3
# ============================================================

def _detect_raw_door_envelopes(
    horizontal,
    vertical,
    ground_y,
    bounds,
):
    bx0, by0, bx1, by1 = (
        float(v)
        for v in bounds
    )

    facade_width = max(
        bx1 - bx0,
        1.0,
    )

    facade_height = max(
        by1 - by0,
        1.0,
    )

    ground_tolerance = (
        facade_height
        * 0.035
    )

    top_tolerance = (
        facade_height
        * 0.025
    )

    jambs = []

    for line in vertical or []:

        try:
            x = float(
                line["x"]
            )

            y0 = float(
                line["y0"]
            )

            y1 = float(
                line["y1"]
            )

        except Exception:
            continue

        if y1 < y0:
            y0, y1 = (
                y1,
                y0,
            )

        height = (
            y1 - y0
        )

        if height <= 0.0:
            continue

        # Door jamb starts at or extremely near facade ground.
        if abs(
            y0 - ground_y
        ) > ground_tolerance:
            continue

        if (
            height
            < facade_height
            * 0.20
        ):
            continue

        jambs.append(
            {
                "x": x,
                "y0": y0,
                "y1": y1,
                "height": height,
            }
        )


    envelopes = []


    for i in range(
        len(
            jambs
        )
    ):
        left = jambs[
            i
        ]

        for j in range(
            i + 1,
            len(
                jambs
            )
        ):
            right = jambs[
                j
            ]

            if (
                right["x"]
                <= left["x"]
            ):
                continue

            width = (
                right["x"]
                - left["x"]
            )

            if width <= 0.0:
                continue


            # Their tops must describe one opening.
            top_difference = abs(
                left["y1"]
                - right["y1"]
            )

            local_height = max(
                min(
                    left["height"],
                    right["height"],
                ),
                1.0e-9,
            )

            if (
                top_difference
                > max(
                    top_tolerance,
                    local_height * 0.075,
                )
            ):
                continue


            top_y = min(
                left["y1"],
                right["y1"],
            )

            height = (
                top_y
                - ground_y
            )

            if height <= 0.0:
                continue


            aspect = (
                width / height
            )

            width_fraction = (
                width
                / facade_width
            )

            height_fraction = (
                height
                / facade_height
            )


            # Local architectural door envelope.
            if not (
                0.15
                <= aspect
                <= 1.65
            ):
                continue

            if width_fraction > 0.28:
                continue

            if height_fraction < 0.20:
                continue


            # -----------------------------------------------
            # TOP CAP
            # -----------------------------------------------

            (
                top_support,
                top_specificity,
            ) = _horizontal_support(
                horizontal,
                top_y,
                left["x"],
                right["x"],
                max(
                    facade_height
                    * 0.0025,
                    1.0e-7,
                ),
            )


            if top_support < 0.72:
                continue

            if top_specificity < 0.42:
                continue


            # -----------------------------------------------
            # INTERNAL DOOR STRUCTURE
            #
            # Not mandatory by itself, but useful evidence.
            # -----------------------------------------------

            (
                internal_v,
                internal_h,
            ) = _internal_structure(
                horizontal,
                vertical,
                left["x"],
                ground_y,
                right["x"],
                top_y,
            )


            score = (
                top_support * 3.0
                +
                top_specificity * 2.0
                +
                min(
                    internal_v,
                    4,
                )
                * 0.35
                +
                min(
                    internal_h,
                    4,
                )
                * 0.35
            )


            envelopes.append(
                {
                    "bbox": (
                        float(
                            left["x"]
                        ),
                        float(
                            ground_y
                        ),
                        float(
                            right["x"]
                        ),
                        float(
                            top_y
                        ),
                    ),

                    "score":
                        float(
                            score
                        ),

                    "internal_vertical_count":
                        int(
                            internal_v
                        ),

                    "internal_horizontal_count":
                        int(
                            internal_h
                        ),
                }
            )


    # ========================================================
    # DEDUPE DOOR ENVELOPES
    #
    # Prefer the complete outer jamb pair.
    # ========================================================

    envelopes.sort(
        key=lambda row: (
            -(
                (
                    row["bbox"][2]
                    - row["bbox"][0]
                )
                *
                (
                    row["bbox"][3]
                    - row["bbox"][1]
                )
            ),
            -row["score"],
        )
    )


    resolved = []


    for candidate in envelopes:

        cx0, cy0, cx1, cy1 = (
            candidate[
                "bbox"
            ]
        )

        candidate_area = max(
            0.0,
            cx1 - cx0,
        ) * max(
            0.0,
            cy1 - cy0,
        )

        duplicate = False


        for kept in resolved:

            kx0, ky0, kx1, ky1 = (
                kept[
                    "bbox"
                ]
            )

            intersection = (
                max(
                    0.0,
                    min(
                        cx1,
                        kx1,
                    )
                    - max(
                        cx0,
                        kx0,
                    ),
                )
                *
                max(
                    0.0,
                    min(
                        cy1,
                        ky1,
                    )
                    - max(
                        cy0,
                        ky0,
                    ),
                )
            )

            containment = (
                intersection
                / max(
                    candidate_area,
                    1.0e-9,
                )
            )

            if containment >= 0.90:
                duplicate = True
                break


        if not duplicate:
            resolved.append(
                candidate
            )


    return resolved


def _decorate_candidates(
    candidates,
    ground_y,
    bounds,
    door_envelopes=None,
):
    if not candidates:
        return []

    door_envelopes = list(
        door_envelopes
        or []
    )

    nested_counts = [
        0
        for _ in candidates
    ]


    # ========================================================
    # CONTAINMENT GRAPH
    # ========================================================

    for outer_index, outer in enumerate(
        candidates
    ):

        for inner_index, inner in enumerate(
            candidates
        ):

            if outer_index == inner_index:
                continue

            if (
                inner.area
                >= outer.area * 0.97
            ):
                continue

            if not _contains(
                outer,
                inner,
            ):
                continue

            ratio = (
                inner.area
                / outer.area
            )

            if (
                0.035
                <= ratio
                <= 0.90
            ):
                nested_counts[
                    outer_index
                ] += 1


    # ========================================================
    # REPETITION
    # ========================================================

    repetition = [
        0.0
        for _ in candidates
    ]


    for i, row in enumerate(
        candidates
    ):

        peers = 0

        for j, other in enumerate(
            candidates
        ):

            if i == j:
                continue

            ws = (
                min(
                    row.width,
                    other.width,
                )
                /
                max(
                    row.width,
                    other.width,
                )
            )

            hs = (
                min(
                    row.height,
                    other.height,
                )
                /
                max(
                    row.height,
                    other.height,
                )
            )

            aspect_similarity = (
                min(
                    row.aspect,
                    other.aspect,
                )
                /
                max(
                    row.aspect,
                    other.aspect,
                )
            )

            if (
                ws >= 0.82
                and
                hs >= 0.82
                and
                aspect_similarity >= 0.86
            ):
                peers += 1


        repetition[
            i
        ] = min(
            1.25,
            peers * 0.20,
        )


    result = []


    for index, row in enumerate(
        candidates
    ):

        nested_count = int(
            nested_counts[
                index
            ]
        )

        repetition_score = float(
            repetition[
                index
            ]
        )


        internal_score = (
            min(
                row.internal_vertical_count,
                5,
            )
            * 0.38
            +
            min(
                row.internal_horizontal_count,
                5,
            )
            * 0.32
        )


        nested_score = (
            min(
                nested_count,
                8,
            )
            * 0.34
        )


        # ====================================================
        # RAW DOOR ENVELOPE VETO
        # ====================================================

        inside_door = False


        for door in door_envelopes:

            try:
                dx0, dy0, dx1, dy1 = (
                    float(v)
                    for v in door[
                        "bbox"
                    ]
                )

            except Exception:
                continue


            intersection = (
                max(
                    0.0,
                    min(
                        row.x1,
                        dx1,
                    )
                    - max(
                        row.x0,
                        dx0,
                    ),
                )
                *
                max(
                    0.0,
                    min(
                        row.y1,
                        dy1,
                    )
                    - max(
                        row.y0,
                        dy0,
                    ),
                )
            )


            containment = (
                intersection
                / max(
                    row.area,
                    1.0e-9,
                )
            )


            door_width = max(
                dx1 - dx0,
                1.0e-9,
            )

            door_height = max(
                dy1 - dy0,
                1.0e-9,
            )


            # Candidate's center must actually lie in the
            # same local door opening.
            center_inside = (
                dx0
                <= row.cx
                <= dx1
                and
                dy0
                <= row.cy
                <= dy1
            )


            # A decorative door panel/window-like subframe is
            # substantially contained by the real door envelope.
            if (
                center_inside
                and
                containment >= 0.82
                and
                row.area
                <= (
                    door_width
                    * door_height
                    * 0.94
                )
            ):
                inside_door = True
                break


        score = (
            row.frame_score
            +
            internal_score
            +
            nested_score
            +
            repetition_score
        )


        if inside_door:
            score -= 100.0


        result.append(
            RectCandidate(
                x0=row.x0,
                y0=row.y0,
                x1=row.x1,
                y1=row.y1,

                left_support=
                    row.left_support,

                right_support=
                    row.right_support,

                bottom_support=
                    row.bottom_support,

                top_support=
                    row.top_support,

                left_specificity=
                    row.left_specificity,

                right_specificity=
                    row.right_specificity,

                bottom_specificity=
                    row.bottom_specificity,

                top_specificity=
                    row.top_specificity,

                internal_vertical_count=
                    row.internal_vertical_count,

                internal_horizontal_count=
                    row.internal_horizontal_count,

                frame_score=float(
                    row.frame_score
                ),

                nested_count=
                    nested_count,

                repetition_score=
                    repetition_score,

                window_score=float(
                    score
                ),

                door_like=bool(
                    inside_door
                ),
            )
        )


    return result


# ============================================================
# PHYSICAL WINDOW HYPOTHESES
# ============================================================


def _candidate_union_bbox(
    children,
):
    return (
        min(
            child.x0
            for child in children
        ),
        min(
            child.y0
            for child in children
        ),
        max(
            child.x1
            for child in children
        ),
        max(
            child.y1
            for child in children
        ),
    )


def _build_window_hypotheses(
    candidates,
):
    """
    Build physical-window hypotheses from DIRECT structural
    children only.

    This avoids counting every combinatorial intermediate
    rectangle in the containment graph as a window leaf.
    """

    hypotheses = []


    strong_cores = [
        row
        for row in candidates
        if (
            not row.door_like
            and
            row.frame_score >= 5.0
            and
            (
                row.internal_vertical_count
                + row.internal_horizontal_count
                + min(
                    row.nested_count,
                    3,
                )
            )
            >= 1
        )
    ]


    def direct_atomic_children(
        parent,
    ):
        raw = [
            core
            for core in strong_cores
            if (
                core is not parent
                and
                core.area
                < parent.area * 0.90
                and
                core.area
                > parent.area * 0.025
                and
                _contains(
                    parent,
                    core,
                    tolerance_fraction=0.01,
                )
            )
        ]


        # --------------------------------------------
        # Keep leaf-most meaningful structural cores.
        #
        # If A contains B and B is also a strong core,
        # A is an intermediate containment cycle,
        # not an atomic sash/leaf.
        # --------------------------------------------

        atomic = []

        for candidate in raw:

            has_meaningful_child = False

            for inner in raw:

                if inner is candidate:
                    continue

                if (
                    inner.area
                    >= candidate.area * 0.88
                ):
                    continue

                if (
                    inner.area
                    < candidate.area * 0.12
                ):
                    continue

                if _contains(
                    candidate,
                    inner,
                    tolerance_fraction=0.01,
                ):
                    has_meaningful_child = True
                    break

            if not has_meaningful_child:
                atomic.append(
                    candidate
                )


        # --------------------------------------------
        # Heavy-overlap dedupe.
        #
        # Adjacent leaves survive.
        # Duplicate/nested representations do not.
        # --------------------------------------------

        atomic.sort(
            key=lambda row: (
                -row.window_score,
                -row.area,
            )
        )

        kept = []

        for candidate in atomic:

            conflict = False

            for previous in kept:

                intersection = (
                    _intersection_area(
                        candidate,
                        previous,
                    )
                )

                min_area = max(
                    min(
                        candidate.area,
                        previous.area,
                    ),
                    1.0e-9,
                )

                overlap_fraction = (
                    intersection
                    / min_area
                )

                if overlap_fraction >= 0.55:
                    conflict = True
                    break

            if not conflict:
                kept.append(
                    candidate
                )


        # Prevent pathological family size even on highly
        # detailed drawings.
        return kept[:12]


    for parent in candidates:

        if parent.door_like:
            continue

        if parent.frame_score < 5.0:
            continue


        children = (
            direct_atomic_children(
                parent
            )
        )


        if not children:

            own_structure = (
                parent.internal_vertical_count
                + parent.internal_horizontal_count
                + min(
                    parent.nested_count,
                    3,
                )
            )

            if own_structure < 1:
                continue

            hypotheses.append(
                {
                    "frame":
                        parent,

                    "children":
                        [],

                    "score":
                        float(
                            parent.window_score
                        ),

                    "family_size":
                        1,
                }
            )

            continue


        (
            ux0,
            uy0,
            ux1,
            uy1,
        ) = _candidate_union_bbox(
            children
        )


        union_width = max(
            ux1 - ux0,
            1.0e-9,
        )

        union_height = max(
            uy1 - uy0,
            1.0e-9,
        )

        union_area = (
            union_width
            * union_height
        )


        width_ratio = (
            parent.width
            / union_width
        )

        height_ratio = (
            parent.height
            / union_height
        )

        area_ratio = (
            parent.area
            / union_area
        )


        if not (
            0.97
            <= width_ratio
            <= 1.45
        ):
            continue

        if not (
            0.97
            <= height_ratio
            <= 1.45
        ):
            continue

        if area_ratio > 1.85:
            continue


        child_area_sum = sum(
            child.area
            for child
            in children
        )

        occupancy = (
            child_area_sum
            / parent.area
        )


        if (
            len(
                children
            )
            == 1
        ):
            if occupancy < 0.24:
                continue

        elif occupancy < 0.18:
            continue


        # ====================================================
        # BOUNDED family evidence.
        #
        # Family score can help the common outer frame win,
        # but it may never explode with cycle count.
        # ====================================================

        child_evidence = min(
            10.0,
            sum(
                min(
                    2.25,
                    max(
                        0.0,
                        child.window_score
                        - 4.5,
                    ),
                )
                for child
                in children
            ),
        )


        family_bonus = min(
            8.0,
            len(
                children
            )
            * 1.55,
        )


        outer_bonus = min(
            2.0,
            min(
                parent.nested_count,
                8,
            )
            * 0.22,
        )


        compactness_bonus = min(
            1.5,
            occupancy
            * 1.8,
        )


        hypothesis_score = (
            parent.window_score
            +
            child_evidence
            +
            family_bonus
            +
            outer_bonus
            +
            compactness_bonus
        )


        hypotheses.append(
            {
                "frame":
                    parent,

                "children":
                    children,

                "score":
                    float(
                        hypothesis_score
                    ),

                "family_size":
                    int(
                        len(
                            children
                        )
                    ),
            }
        )


    unique = {}

    for hypothesis in hypotheses:

        frame = hypothesis[
            "frame"
        ]

        key = tuple(
            round(
                value,
                5,
            )
            for value
            in frame.bbox
        )

        previous = unique.get(
            key
        )

        if (
            previous is None
            or hypothesis[
                "score"
            ]
            > previous[
                "score"
            ]
        ):
            unique[
                key
            ] = hypothesis


    return list(
        unique.values()
    )


# ============================================================
# GLOBAL CONFLICT GRAPH
# ============================================================


def _hypotheses_conflict(
    a,
    b,
):
    ra = a[
        "frame"
    ]

    rb = b[
        "frame"
    ]

    intersection = (
        _intersection_area(
            ra,
            rb,
        )
    )

    if intersection <= 0.0:
        return False


    min_area = max(
        min(
            ra.area,
            rb.area,
        ),
        1.0e-9,
    )

    containment = (
        intersection
        / min_area
    )


    if containment >= 0.76:
        return True


    if _iou(
        ra,
        rb,
    ) >= 0.30:
        return True


    # Heavy geometric overlap means they cannot be two
    # independent physical windows.
    if containment >= 0.52:
        return True


    return False


def _connected_components(
    adjacency,
):
    unseen = set(
        range(
            len(
                adjacency
            )
        )
    )

    components = []

    while unseen:

        start = unseen.pop()

        stack = [
            start
        ]

        component = [
            start
        ]

        while stack:

            current = stack.pop()

            for neighbor in adjacency[
                current
            ]:

                if neighbor in unseen:
                    unseen.remove(
                        neighbor
                    )

                    stack.append(
                        neighbor
                    )

                    component.append(
                        neighbor
                    )

        components.append(
            component
        )

    return components


def _solve_component_exact(
    component,
    hypotheses,
    adjacency,
):
    local_index = {
        global_index:
            local_position
        for (
            local_position,
            global_index
        ) in enumerate(
            component
        )
    }

    count = len(
        component
    )

    weights = [
        max(
            0.0,
            float(
                hypotheses[
                    global_index
                ][
                    "score"
                ]
            ),
        )
        for global_index
        in component
    ]

    neighbor_masks = [
        0
        for _ in range(
            count
        )
    ]

    for local_position, global_index in enumerate(
        component
    ):

        mask = 0

        for neighbor_global in adjacency[
            global_index
        ]:

            neighbor_local = (
                local_index.get(
                    neighbor_global
                )
            )

            if neighbor_local is None:
                continue

            mask |= (
                1
                << neighbor_local
            )

        neighbor_masks[
            local_position
        ] = mask


    @lru_cache(
        maxsize=None
    )
    def solve(
        mask,
    ):
        if mask == 0:
            return (
                0.0,
                0,
            )


        # Pick a high-conflict node first.
        available = [
            i
            for i in range(
                count
            )
            if mask
            & (
                1 << i
            )
        ]


        vertex = max(
            available,
            key=lambda i:
                (
                    (
                        neighbor_masks[
                            i
                        ]
                        & mask
                    ).bit_count(),
                    weights[
                        i
                    ],
                )
        )


        vertex_bit = (
            1 << vertex
        )


        # EXCLUDE
        excluded_score, excluded_set = (
            solve(
                mask
                & ~vertex_bit
            )
        )


        # INCLUDE
        include_mask = (
            mask
            & ~vertex_bit
            & ~neighbor_masks[
                vertex
            ]
        )

        included_score, included_set = (
            solve(
                include_mask
            )
        )

        included_score += (
            weights[
                vertex
            ]
        )

        included_set |= (
            vertex_bit
        )


        if (
            included_score
            > excluded_score
            + 1.0e-9
        ):
            return (
                included_score,
                included_set,
            )

        return (
            excluded_score,
            excluded_set,
        )


    full_mask = (
        (1 << count)
        - 1
    )

    score, selected_mask = (
        solve(
            full_mask
        )
    )


    selected = [
        component[
            local_position
        ]
        for local_position in range(
            count
        )
        if selected_mask
        & (
            1 << local_position
        )
    ]

    return (
        score,
        selected,
    )


def _solve_component_greedy(
    component,
    hypotheses,
    adjacency,
):
    # Fallback only for unusually large local conflict groups.
    order = sorted(
        component,
        key=lambda index: (
            -float(
                hypotheses[
                    index
                ][
                    "score"
                ]
            ),
            -hypotheses[
                index
            ][
                "frame"
            ].area,
        )
    )

    selected = []

    selected_set = set()

    for index in order:

        if any(
            neighbor
            in selected_set
            for neighbor
            in adjacency[
                index
            ]
        ):
            continue

        selected.append(
            index
        )

        selected_set.add(
            index
        )

    return selected


def _global_window_selection(
    hypotheses,
):
    """
    CAD3D_GRAPH_WINDOW_PARENT_DOMINANCE_V4

    Mathematical selection model:

    1. Solve weighted set packing normally.
    2. Inspect the provisional physical windows.
    3. If 2+ selected subframes substantially fill one
       independently validated enclosing frame, they are
       partitions of ONE physical window.
    4. Replace those selected partitions with their common
       structural parent.
    5. Repeat until hierarchy is stable.

    This makes:

        outer frame
        + left/right panes
        + upper/lower panes

    a hierarchical problem rather than a pure score contest.
    """

    hypotheses = list(
        hypotheses
        or []
    )

    if not hypotheses:
        return []


    # ========================================================
    # EXACT BBOX DEDUPE
    # ========================================================

    unique = {}

    for hypothesis in hypotheses:

        frame = hypothesis[
            "frame"
        ]

        key = tuple(
            round(
                value,
                5,
            )
            for value
            in frame.bbox
        )

        previous = unique.get(
            key
        )

        if (
            previous is None
            or float(
                hypothesis[
                    "score"
                ]
            )
            > float(
                previous[
                    "score"
                ]
            )
        ):
            unique[
                key
            ] = hypothesis


    hypotheses = list(
        unique.values()
    )


    # ========================================================
    # RECTANGLE UNION AREA
    #
    # Uses true geometric union rather than SUM(area).
    # Overlapping child cycles therefore cannot artificially
    # inflate occupancy.
    # ========================================================

    def rectangle_union_area(
        frames,
    ):
        frames = list(
            frames
            or []
        )

        if not frames:
            return 0.0

        xs = sorted(
            {
                float(
                    value
                )
                for frame
                in frames
                for value
                in (
                    frame.x0,
                    frame.x1,
                )
            }
        )

        if len(xs) < 2:
            return 0.0


        total = 0.0


        for index in range(
            len(xs) - 1
        ):

            slab_x0 = xs[
                index
            ]

            slab_x1 = xs[
                index + 1
            ]

            slab_width = (
                slab_x1
                - slab_x0
            )

            if slab_width <= 0.0:
                continue


            middle_x = (
                slab_x0
                + slab_x1
            ) * 0.5


            intervals = []


            for frame in frames:

                if not (
                    frame.x0
                    < middle_x
                    < frame.x1
                ):
                    continue

                intervals.append(
                    (
                        float(
                            frame.y0
                        ),
                        float(
                            frame.y1
                        ),
                    )
                )


            if not intervals:
                continue


            intervals.sort()

            merged_length = 0.0

            current_y0 = (
                intervals[0][0]
            )

            current_y1 = (
                intervals[0][1]
            )


            for y0, y1 in intervals[1:]:

                if y0 <= current_y1:

                    current_y1 = max(
                        current_y1,
                        y1,
                    )

                else:

                    merged_length += (
                        current_y1
                        - current_y0
                    )

                    current_y0 = y0
                    current_y1 = y1


            merged_length += (
                current_y1
                - current_y0
            )


            total += (
                slab_width
                * merged_length
            )


        return float(
            total
        )


    # ========================================================
    # CONFLICT GRAPH
    # ========================================================

    count = len(
        hypotheses
    )

    adjacency = [
        set()
        for _ in range(
            count
        )
    ]


    for i in range(
        count
    ):

        for j in range(
            i + 1,
            count
        ):

            if _hypotheses_conflict(
                hypotheses[
                    i
                ],
                hypotheses[
                    j
                ],
            ):

                adjacency[
                    i
                ].add(
                    j
                )

                adjacency[
                    j
                ].add(
                    i
                )


    # ========================================================
    # PHASE 1
    # NORMAL GLOBAL WEIGHTED SET PACKING
    # ========================================================

    provisional_indices = []


    for component in _connected_components(
        adjacency
    ):

        # ====================================================
        # CAD3D_MWIS_PERFORMANCE_GUARD_V1
        #
        # Exact MWIS grows exponentially.
        # Keep exact solving only for genuinely small local
        # conflict components.
        #
        # Larger components use the deterministic greedy solver.
        # Geometry/hierarchy rules remain unchanged.
        # ====================================================

        if len(
            component
        ) <= 15:

            _, selected = (
                _solve_component_exact(
                    component,
                    hypotheses,
                    adjacency,
                )
            )

        else:

            selected = (
                _solve_component_greedy(
                    component,
                    hypotheses,
                    adjacency,
                )
            )


        provisional_indices.extend(
            selected
        )


    selected = set(
        provisional_indices
    )


    # ========================================================
    # PHASE 2
    # HIERARCHICAL PARENT DOMINANCE
    #
    # This is the missing architectural constraint.
    # ========================================================

    changed = True


    while changed:

        changed = False

        replacements = []


        for parent_index, parent_hypothesis in enumerate(
            hypotheses
        ):

            if parent_index in selected:
                continue


            parent = parent_hypothesis[
                "frame"
            ]


            # Parent itself must be a strong, independently
            # closed structural frame.
            if parent.frame_score < 5.0:
                continue


            parent_structure = (
                int(
                    parent.internal_vertical_count
                )
                +
                int(
                    parent.internal_horizontal_count
                )
                +
                min(
                    int(
                        parent.nested_count
                    ),
                    2,
                )
            )


            if parent_structure < 2:
                continue


            child_indices = []


            for child_index in selected:

                child = hypotheses[
                    child_index
                ][
                    "frame"
                ]


                if (
                    child.area
                    >= parent.area * 0.97
                ):
                    continue


                if not _contains(
                    parent,
                    child,
                    tolerance_fraction=0.012,
                ):
                    continue


                child_indices.append(
                    child_index
                )


            # One child alone is not enough to prove a
            # partitioned window family.
            if len(
                child_indices
            ) < 2:
                continue


            children = [
                hypotheses[
                    index
                ][
                    "frame"
                ]
                for index
                in child_indices
            ]


            # =================================================
            # CHILD UNION BOUNDING BOX
            # =================================================

            ux0 = min(
                child.x0
                for child
                in children
            )

            uy0 = min(
                child.y0
                for child
                in children
            )

            ux1 = max(
                child.x1
                for child
                in children
            )

            uy1 = max(
                child.y1
                for child
                in children
            )


            union_bbox_width = max(
                ux1 - ux0,
                1.0e-9,
            )

            union_bbox_height = max(
                uy1 - uy0,
                1.0e-9,
            )


            width_ratio = (
                parent.width
                / union_bbox_width
            )

            height_ratio = (
                parent.height
                / union_bbox_height
            )


            # Child partitions must geometrically span almost
            # the same physical opening as their parent.
            if not (
                0.98
                <= width_ratio
                <= 1.34
            ):
                continue


            if not (
                0.98
                <= height_ratio
                <= 1.34
            ):
                continue


            # =================================================
            # TRUE OCCUPANCY
            # =================================================

            child_union_area = (
                rectangle_union_area(
                    children
                )
            )


            occupancy = (
                child_union_area
                / max(
                    parent.area,
                    1.0e-9,
                )
            )


            # A wall containing a few separate windows has low
            # occupancy. Partitioned panes within one physical
            # window have high occupancy.
            if occupancy < 0.56:
                continue


            # =================================================
            # EDGE REACH
            #
            # Child family must reach close to all four parent
            # sides. This rejects unrelated sparse openings.
            # =================================================

            left_margin = (
                ux0
                - parent.x0
            ) / parent.width

            right_margin = (
                parent.x1
                - ux1
            ) / parent.width

            bottom_margin = (
                uy0
                - parent.y0
            ) / parent.height

            top_margin = (
                parent.y1
                - uy1
            ) / parent.height


            if (
                left_margin > 0.18
                or
                right_margin > 0.18
                or
                bottom_margin > 0.18
                or
                top_margin > 0.18
            ):
                continue


            # =================================================
            # PARENT MUST BE MEANINGFULLY LARGER THAN ANY ONE
            # CHILD.
            # =================================================

            largest_child_area = max(
                child.area
                for child
                in children
            )


            if (
                parent.area
                / max(
                    largest_child_area,
                    1.0e-9,
                )
                < 1.12
            ):
                continue


            # Architectural hierarchy confidence.
            hierarchy_score = (
                occupancy
                * 5.0
                +
                min(
                    len(
                        children
                    ),
                    6,
                )
                * 0.70
                +
                min(
                    parent_structure,
                    8,
                )
                * 0.25
                +
                float(
                    parent.frame_score
                )
                * 0.20
            )


            replacements.append(
                {
                    "parent_index":
                        parent_index,

                    "child_indices":
                        set(
                            child_indices
                        ),

                    "hierarchy_score":
                        float(
                            hierarchy_score
                        ),

                    "occupancy":
                        float(
                            occupancy
                        ),

                    "parent_area":
                        float(
                            parent.area
                        ),
                }
            )


        if not replacements:
            break


        # Best proven hierarchy first.
        #
        # More occupied and structurally stronger common frame
        # wins. Larger area only breaks genuine ties.
        replacements.sort(
            key=lambda row: (
                -row[
                    "hierarchy_score"
                ],
                -row[
                    "occupancy"
                ],
                -row[
                    "parent_area"
                ],
            )
        )


        replacement = (
            replacements[0]
        )


        # Remove physical partitions.
        selected.difference_update(
            replacement[
                "child_indices"
            ]
        )


        # Add one physical outer frame.
        selected.add(
            replacement[
                "parent_index"
            ]
        )


        changed = True


    # ========================================================
    # FINAL ORDER
    # ========================================================

    selected_indices = sorted(
        selected,
        key=lambda index: (
            hypotheses[
                index
            ][
                "frame"
            ].cx,

            hypotheses[
                index
            ][
                "frame"
            ].cy,
        )
    )


    return [
        hypotheses[
            index
        ]
        for index
        in selected_indices
    ]


# ============================================================
# SILL RESOLUTION
# ============================================================


def _resolve_sill(
    frame,
    horizontal,
):
    width = frame.width
    height = frame.height

    candidates = []

    for line in horizontal:

        try:
            y = float(
                line["y"]
            )

            x0 = float(
                line["x0"]
            )

            x1 = float(
                line["x1"]
            )

        except Exception:
            continue


        # CAD Y grows upward.
        if not (
            frame.y0
            - height * 0.18
            <= y
            < frame.y0
        ):
            continue


        line_width = max(
            x1 - x0,
            1.0e-9,
        )


        left_overhang = (
            frame.x0
            - x0
        ) / width

        right_overhang = (
            x1
            - frame.x1
        ) / width


        if (
            left_overhang < 0.008
            or
            right_overhang < 0.008
        ):
            continue


        if not (
            1.015
            <= line_width / width
            <= 2.0
        ):
            continue


        candidates.append(
            {
                "y":
                    y,

                "x0":
                    x0,

                "x1":
                    x1,
            }
        )


    if not candidates:
        return {
            "sill_top_y":
                None,

            "sill_bottom_y":
                None,
        }


    # Highest projecting line below frame = sill top.
    candidates.sort(
        key=lambda row:
            -row[
                "y"
            ]
    )

    sill_top_y = float(
        candidates[0][
            "y"
        ]
    )


    nearby = [
        row
        for row in candidates
        if (
            sill_top_y
            - row[
                "y"
            ]
        )
        <= height * 0.08
    ]


    sill_bottom_y = min(
        float(
            row[
                "y"
            ]
        )
        for row in nearby
    )


    return {
        "sill_top_y":
            sill_top_y,

        "sill_bottom_y":
            sill_bottom_y,
    }


# ============================================================
# PUBLIC DETECTOR
# ============================================================



# ============================================================
# CAD3D_PHYSICAL_OPENING_RESOLVER_V6
#
# Final architectural hierarchy:
#
# 1. Remove anything belonging to a verified door envelope.
# 2. Remove X-braced roof openings from normal windows.
# 3. Merge selected window partitions into the smallest valid
#    common structural parent.
# 4. Promote the resulting window only to a very close,
#    centered, independently closed outer frame.
#
# This stage operates AFTER sparse graph detection and global
# selection. It therefore does not generate new combinatorial
# cycles and is computationally small.
# ============================================================


def _cad3d_v6_bbox_contains(
    outer,
    inner,
    tolerance=0.0,
):
    return (
        inner.x0
        >= outer.x0 - tolerance
        and
        inner.x1
        <= outer.x1 + tolerance
        and
        inner.y0
        >= outer.y0 - tolerance
        and
        inner.y1
        <= outer.y1 + tolerance
    )


def _cad3d_v6_rect_union_area(
    frames,
):
    frames = list(
        frames
        or []
    )

    if not frames:
        return 0.0

    xs = sorted(
        {
            float(x)
            for frame in frames
            for x in (
                frame.x0,
                frame.x1,
            )
        }
    )

    if len(xs) < 2:
        return 0.0

    total = 0.0

    for i in range(
        len(xs) - 1
    ):
        sx0 = xs[i]
        sx1 = xs[i + 1]

        if sx1 <= sx0:
            continue

        mx = (
            sx0 + sx1
        ) * 0.5

        intervals = []

        for frame in frames:

            if not (
                frame.x0
                < mx
                < frame.x1
            ):
                continue

            intervals.append(
                (
                    float(frame.y0),
                    float(frame.y1),
                )
            )

        if not intervals:
            continue

        intervals.sort()

        y0, y1 = (
            intervals[0]
        )

        height = 0.0

        for a, b in intervals[1:]:

            if a <= y1:
                y1 = max(
                    y1,
                    b,
                )

            else:
                height += (
                    y1 - y0
                )

                y0, y1 = (
                    a,
                    b,
                )

        height += (
            y1 - y0
        )

        total += (
            sx1 - sx0
        ) * height

    return float(
        total
    )


def _cad3d_v6_iter_raw_segments(
    geometry,
):
    for entity in geometry or []:

        points = None

        if isinstance(
            entity,
            dict,
        ):
            points = (
                entity.get(
                    "points"
                )
                or entity.get(
                    "vertices"
                )
            )

        else:
            points = getattr(
                entity,
                "points",
                None,
            )

        if not points:
            continue

        clean = []

        for point in points:

            try:
                clean.append(
                    (
                        float(
                            point[0]
                        ),
                        float(
                            point[1]
                        ),
                    )
                )
            except Exception:
                pass

        if len(clean) < 2:
            continue

        for i in range(
            len(clean) - 1
        ):
            yield (
                clean[i],
                clean[i + 1],
            )


def _cad3d_v6_has_x_brace(
    frame,
    geometry,
):
    """
    True only when BOTH diagonal directions exist materially
    inside the opening.

    This distinguishes the X-braced roof openings visible in
    the drawing from ordinary vertical/horizontal windows.
    """

    width = max(
        frame.width,
        1.0e-9,
    )

    height = max(
        frame.height,
        1.0e-9,
    )

    positive = False
    negative = False


    inner_x0 = (
        frame.x0
        + width * 0.05
    )

    inner_x1 = (
        frame.x1
        - width * 0.05
    )

    inner_y0 = (
        frame.y0
        + height * 0.05
    )

    inner_y1 = (
        frame.y1
        - height * 0.05
    )


    for (
        p0,
        p1,
    ) in _cad3d_v6_iter_raw_segments(
        geometry
    ):

        x0, y0 = p0
        x1, y1 = p1

        dx = (
            x1 - x0
        )

        dy = (
            y1 - y0
        )

        if (
            abs(dx)
            < width * 0.18
            or
            abs(dy)
            < height * 0.18
        ):
            continue


        mx = (
            x0 + x1
        ) * 0.5

        my = (
            y0 + y1
        ) * 0.5


        if not (
            inner_x0
            <= mx
            <= inner_x1
            and
            inner_y0
            <= my
            <= inner_y1
        ):
            continue


        slope_sign = (
            dx * dy
        )


        if slope_sign > 0.0:
            positive = True

        elif slope_sign < 0.0:
            negative = True


        if (
            positive
            and negative
        ):
            return True


    return False


def _cad3d_v6_inside_door(
    frame,
    door_envelopes,
):
    for door in door_envelopes or []:

        try:
            dx0, dy0, dx1, dy1 = (
                float(v)
                for v in door[
                    "bbox"
                ]
            )
        except Exception:
            continue


        intersection = (
            max(
                0.0,
                min(
                    frame.x1,
                    dx1,
                )
                - max(
                    frame.x0,
                    dx0,
                ),
            )
            *
            max(
                0.0,
                min(
                    frame.y1,
                    dy1,
                )
                - max(
                    frame.y0,
                    dy0,
                ),
            )
        )


        containment = (
            intersection
            / max(
                frame.area,
                1.0e-9,
            )
        )


        center_inside = (
            dx0
            <= frame.cx
            <= dx1
            and
            dy0
            <= frame.cy
            <= dy1
        )


        if (
            center_inside
            and
            containment >= 0.82
        ):
            return True


    return False


def _cad3d_v6_is_ground_door_like(
    frame,
    ground_y,
    bounds,
):
    bx0, by0, bx1, by1 = (
        float(v)
        for v in bounds
    )

    facade_height = max(
        by1 - by0,
        1.0e-9,
    )

    facade_width = max(
        bx1 - bx0,
        1.0e-9,
    )


    ground_distance = abs(
        frame.y0
        - ground_y
    )


    if (
        ground_distance
        > facade_height * 0.035
    ):
        return False


    if (
        frame.height
        < facade_height * 0.18
    ):
        return False


    if (
        frame.width
        > facade_width * 0.34
    ):
        return False


    if not (
        0.16
        <= frame.aspect
        <= 2.20
    ):
        return False


    return True


def _cad3d_v6_merge_partitions(
    selected,
    candidates,
    geometry,
    door_envelopes,
):
    """
    Find the SMALLEST valid common structural parent for two
    or more currently selected partitions.

    Smallest-parent rule is critical:
    it chooses a physical window frame before any larger
    wall/facade rectangle.
    """

    current = list(
        selected
        or []
    )


    while True:

        proposals = []


        for parent in candidates or []:

            if bool(
                getattr(
                    parent,
                    "door_like",
                    False,
                )
            ):
                continue


            if (
                float(
                    parent.frame_score
                )
                < 5.0
            ):
                continue


            if _cad3d_v6_has_x_brace(
                parent,
                geometry,
            ):
                continue


            if _cad3d_v6_inside_door(
                parent,
                door_envelopes,
            ):
                continue


            children = []


            for index, hypothesis in enumerate(
                current
            ):

                child = hypothesis[
                    "frame"
                ]


                if (
                    child.area
                    >= parent.area * 0.96
                ):
                    continue


                if _cad3d_v6_bbox_contains(
                    parent,
                    child,
                    tolerance=max(
                        parent.width,
                        parent.height,
                    ) * 0.005,
                ):
                    children.append(
                        (
                            index,
                            child,
                        )
                    )


            if len(
                children
            ) < 2:
                continue


            child_frames = [
                child
                for _, child
                in children
            ]


            ux0 = min(
                child.x0
                for child
                in child_frames
            )

            uy0 = min(
                child.y0
                for child
                in child_frames
            )

            ux1 = max(
                child.x1
                for child
                in child_frames
            )

            uy1 = max(
                child.y1
                for child
                in child_frames
            )


            union_width = max(
                ux1 - ux0,
                1.0e-9,
            )

            union_height = max(
                uy1 - uy0,
                1.0e-9,
            )


            width_ratio = (
                parent.width
                / union_width
            )

            height_ratio = (
                parent.height
                / union_height
            )


            if not (
                0.98
                <= width_ratio
                <= 1.28
            ):
                continue


            if not (
                0.98
                <= height_ratio
                <= 1.28
            ):
                continue


            union_area = (
                _cad3d_v6_rect_union_area(
                    child_frames
                )
            )


            occupancy = (
                union_area
                / max(
                    parent.area,
                    1.0e-9,
                )
            )


            if occupancy < 0.50:
                continue


            left_margin = (
                ux0 - parent.x0
            ) / parent.width

            right_margin = (
                parent.x1 - ux1
            ) / parent.width

            bottom_margin = (
                uy0 - parent.y0
            ) / parent.height

            top_margin = (
                parent.y1 - uy1
            ) / parent.height


            if max(
                left_margin,
                right_margin,
                bottom_margin,
                top_margin,
            ) > 0.15:
                continue


            proposals.append(
                {
                    "parent":
                        parent,

                    "child_indices":
                        [
                            index
                            for index, _
                            in children
                        ],

                    "child_count":
                        len(
                            children
                        ),

                    "occupancy":
                        float(
                            occupancy
                        ),
                }
            )


        if not proposals:
            break


        # MOST CHILDREN first, then SMALLEST enclosing parent.
        proposals.sort(
            key=lambda row: (
                -row[
                    "child_count"
                ],
                row[
                    "parent"
                ].area,
                -row[
                    "occupancy"
                ],
            )
        )


        proposal = (
            proposals[0]
        )

        remove_indices = set(
            proposal[
                "child_indices"
            ]
        )

        children = [
            current[index][
                "frame"
            ]
            for index
            in sorted(
                remove_indices
            )
        ]


        new_current = [
            hypothesis
            for index, hypothesis
            in enumerate(
                current
            )
            if index
            not in remove_indices
        ]


        parent = proposal[
            "parent"
        ]


        new_current.append(
            {
                "frame":
                    parent,

                "children":
                    children,

                "family_size":
                    int(
                        len(
                            children
                        )
                    ),

                "score":
                    float(
                        parent.window_score
                        + min(
                            8.0,
                            len(
                                children
                            )
                            * 1.5,
                        )
                    ),

                "physical_merge_v6":
                    True,
            }
        )


        current = (
            new_current
        )


    return current


def _cad3d_v6_promote_outer_frame(
    hypothesis,
    candidates,
    geometry,
    door_envelopes,
):
    """
    Promote only through a CLOSE concentric structural ring.

    This is deliberately conservative. If the outer physical
    frame cannot be proven, the already-valid inner frame is
    retained rather than expanding to wall/trim geometry.
    """

    current = dict(
        hypothesis
    )

    frame = current[
        "frame"
    ]


    valid = []


    for outer in candidates or []:

        if outer is frame:
            continue


        if bool(
            getattr(
                outer,
                "door_like",
                False,
            )
        ):
            continue


        if (
            float(
                outer.frame_score
            )
            < 5.0
        ):
            continue


        if (
            outer.area
            <= frame.area * 1.002
        ):
            continue


        if not _cad3d_v6_bbox_contains(
            outer,
            frame,
            tolerance=0.0,
        ):
            continue


        width_ratio = (
            outer.width
            / frame.width
        )

        height_ratio = (
            outer.height
            / frame.height
        )


        # Only one nearby frame ring.
        if not (
            1.002
            <= width_ratio
            <= 1.20
        ):
            continue


        if not (
            1.002
            <= height_ratio
            <= 1.20
        ):
            continue


        center_dx = (
            abs(
                outer.cx
                - frame.cx
            )
            / frame.width
        )

        center_dy = (
            abs(
                outer.cy
                - frame.cy
            )
            / frame.height
        )


        if (
            center_dx > 0.045
            or
            center_dy > 0.045
        ):
            continue


        lm = (
            frame.x0
            - outer.x0
        ) / frame.width

        rm = (
            outer.x1
            - frame.x1
        ) / frame.width

        bm = (
            frame.y0
            - outer.y0
        ) / frame.height

        tm = (
            outer.y1
            - frame.y1
        ) / frame.height


        if max(
            lm,
            rm,
            bm,
            tm,
        ) > 0.11:
            continue


        horizontal_total = max(
            lm + rm,
            1.0e-9,
        )

        vertical_total = max(
            bm + tm,
            1.0e-9,
        )


        horizontal_asymmetry = (
            abs(
                lm - rm
            )
            / horizontal_total
        )

        vertical_asymmetry = (
            abs(
                bm - tm
            )
            / vertical_total
        )


        if horizontal_asymmetry > 0.62:
            continue

        if vertical_asymmetry > 0.68:
            continue


        if _cad3d_v6_inside_door(
            outer,
            door_envelopes,
        ):
            continue


        if _cad3d_v6_has_x_brace(
            outer,
            geometry,
        ):
            continue


        # Outer ring should preserve the same internal window
        # structure rather than become empty architectural trim.
        outer_internal = (
            int(
                outer.internal_vertical_count
            )
            +
            int(
                outer.internal_horizontal_count
            )
        )

        inner_internal = (
            int(
                frame.internal_vertical_count
            )
            +
            int(
                frame.internal_horizontal_count
            )
        )


        if (
            inner_internal >= 2
            and
            outer_internal
            < max(
                1,
                int(
                    inner_internal
                    * 0.55
                ),
            )
        ):
            continue


        valid.append(
            outer
        )


    if not valid:
        return current


    # Outermost among ONLY the tightly validated local rings.
    valid.sort(
        key=lambda row:
            -row.area
    )


    outer = valid[0]

    current[
        "frame"
    ] = outer

    current[
        "outer_frame_promoted_v6"
    ] = True

    current[
        "outer_frame_source_bbox_v6"
    ] = tuple(
        float(v)
        for v in frame.bbox
    )


    return current


def _cad3d_physical_opening_resolver_v6(
    selected,
    candidates,
    geometry,
    door_envelopes,
    ground_y,
    bounds,
):
    selected = list(
        selected
        or []
    )


    # ========================================================
    # A. HARD NEGATIVE CONSTRAINTS
    # ========================================================

    filtered = []

    suppressed_doors = 0
    suppressed_rooflights = 0


    for hypothesis in selected:

        frame = hypothesis[
            "frame"
        ]


        if _cad3d_v6_inside_door(
            frame,
            door_envelopes,
        ):
            suppressed_doors += 1
            continue


        if _cad3d_v6_is_ground_door_like(
            frame,
            ground_y,
            bounds,
        ):
            suppressed_doors += 1
            continue


        if _cad3d_v6_has_x_brace(
            frame,
            geometry,
        ):
            suppressed_rooflights += 1
            continue


        filtered.append(
            hypothesis
        )


    # ========================================================
    # B. WINDOW PARTITIONS -> PHYSICAL PARENT
    # ========================================================

    merged = (
        _cad3d_v6_merge_partitions(
            filtered,
            candidates,
            geometry,
            door_envelopes,
        )
    )


    # ========================================================
    # C. CLOSE OUTER FRAME PROMOTION
    # ========================================================

    promoted = [
        _cad3d_v6_promote_outer_frame(
            hypothesis,
            candidates,
            geometry,
            door_envelopes,
        )
        for hypothesis
        in merged
    ]


    # ========================================================
    # D. FINAL OVERLAP DEDUPE
    # ========================================================

    promoted.sort(
        key=lambda hypothesis:
            -hypothesis[
                "frame"
            ].area
    )


    final = []


    for hypothesis in promoted:

        frame = hypothesis[
            "frame"
        ]

        duplicate = False


        for kept in final:

            other = kept[
                "frame"
            ]


            intersection = (
                max(
                    0.0,
                    min(
                        frame.x1,
                        other.x1,
                    )
                    - max(
                        frame.x0,
                        other.x0,
                    ),
                )
                *
                max(
                    0.0,
                    min(
                        frame.y1,
                        other.y1,
                    )
                    - max(
                        frame.y0,
                        other.y0,
                    ),
                )
            )


            min_area = max(
                min(
                    frame.area,
                    other.area,
                ),
                1.0e-9,
            )


            if (
                intersection
                / min_area
                >= 0.80
            ):
                duplicate = True
                break


        if not duplicate:
            final.append(
                hypothesis
            )


    final.sort(
        key=lambda hypothesis: (
            hypothesis[
                "frame"
            ].cx,
            hypothesis[
                "frame"
            ].cy,
        )
    )


    print(
        "PHYSICAL OPENING V6"
        " | input:",
        len(
            selected
        ),
        "| door suppressed:",
        suppressed_doors,
        "| rooflight suppressed:",
        suppressed_rooflights,
        "| after merge:",
        len(
            merged
        ),
        "| final windows:",
        len(
            final
        ),
    )


    return final


def detect_graph_facade_windows(
    geometry,
    bounds,
    **_ignored,
):
    """
    General mathematical facade-window resolver.

    Pipeline:

    vector geometry
        -> merged axis segments
        -> geometric graph axes
        -> closed four-sided cycles
        -> containment graph
        -> window signatures
        -> physical window hypotheses
        -> door negative constraints
        -> conflict graph
        -> global weighted set packing
        -> physical windows
    """

    # CAD3D_GRAPH_TIMING_V1
    import time as _time

    _t_start = _time.perf_counter()

    geometry = list(
        geometry
        or []
    )

    if (
        not geometry
        or not bounds
    ):
        return {
            "engine":
                ENGINE_NAME,

            "entities":
                [],

            "windows":
                [],

            "window_count":
                0,

            "cycle_count":
                0,

            "hypothesis_count":
                0,
        }


    bounds = tuple(
        float(v)
        for v in bounds
    )


    (
        horizontal,
        vertical,
        ground_y,
    ) = _prepare_segments(
        geometry,
        bounds,
    )


    raw_candidates = (
        _generate_closed_cycles(
            horizontal,
            vertical,
            bounds,
        )
    )

    _t_cycles = _time.perf_counter()

    print(
        "GRAPH TIMING"
        " | cycles:",
        round(
            _t_cycles - _t_start,
            4,
        ),
        "s",
        "| count:",
        len(
            raw_candidates
        ),
    )


    door_envelopes = (
        _detect_raw_door_envelopes(
            horizontal,
            vertical,
            ground_y,
            bounds,
        )
    )


    candidates = (
        _decorate_candidates(
            raw_candidates,
            ground_y,
            bounds,
            door_envelopes=door_envelopes,
        )
    )


    hypotheses = (
        _build_window_hypotheses(
            candidates
        )
    )

    _t_hypotheses = _time.perf_counter()

    print(
        "GRAPH TIMING"
        " | hypotheses:",
        round(
            _t_hypotheses - _t_cycles,
            4,
        ),
        "s",
        "| count:",
        len(
            hypotheses
        ),
    )


    selected = (
        _global_window_selection(
            hypotheses
        )
    )


    selected = (
        _cad3d_physical_opening_resolver_v6(
            selected=selected,
            candidates=candidates,
            geometry=geometry,
            door_envelopes=door_envelopes,
            ground_y=ground_y,
            bounds=bounds,
        )
    )

    _t_selected = _time.perf_counter()

    print(
        "GRAPH TIMING"
        " | global selection:",
        round(
            _t_selected - _t_hypotheses,
            4,
        ),
        "s",
        "| selected:",
        len(
            selected
        ),
        "| total:",
        round(
            _t_selected - _t_start,
            4,
        ),
        "s",
    )


    entities = []


    for index, hypothesis in enumerate(
        selected,
        start=1,
    ):
        frame = hypothesis[
            "frame"
        ]

        sill = _resolve_sill(
            frame,
            horizontal,
        )


        entity = {
            "entity_id":
                f"GW{index:03d}",

            "kind":
                "window",

            "bbox":
                tuple(
                    float(v)
                    for v in frame.bbox
                ),

            "center":
                (
                    float(
                        frame.cx
                    ),
                    float(
                        frame.cy
                    ),
                ),

            "width":
                float(
                    frame.width
                ),

            "height":
                float(
                    frame.height
                ),

            "window_height":
                float(
                    frame.height
                ),

            "bottom_y":
                float(
                    frame.y0
                ),

            "top_y":
                float(
                    frame.y1
                ),

            "drawing_bottom_y":
                float(
                    frame.y0
                ),

            "drawing_top_y":
                float(
                    frame.y1
                ),

            "frame_bottom_y":
                float(
                    frame.y0
                ),

            "sill_top_y":
                sill[
                    "sill_top_y"
                ],

            "sill_bottom_y":
                sill[
                    "sill_bottom_y"
                ],

            "graph_window_score":
                float(
                    hypothesis[
                        "score"
                    ]
                ),

            "frame_score":
                float(
                    frame.frame_score
                ),

            "nested_count":
                int(
                    frame.nested_count
                ),

            "family_size":
                int(
                    hypothesis[
                        "family_size"
                    ]
                ),

            "internal_vertical_count":
                int(
                    frame.internal_vertical_count
                ),

            "internal_horizontal_count":
                int(
                    frame.internal_horizontal_count
                ),

            "engine":
                ENGINE_NAME,
        }


        entities.append(
            entity
        )


    return {
        "engine":
            ENGINE_NAME,

        "ground_y":
            float(
                ground_y
            ),

        "horizontal_count":
            len(
                horizontal
            ),

        "vertical_count":
            len(
                vertical
            ),

        "cycle_count":
            len(
                candidates
            ),

        "hypothesis_count":
            len(
                hypotheses
            ),

        "door_envelope_count":
            len(
                door_envelopes
            ),

        "selected_hypothesis_count":
            len(
                selected
            ),

        "entities":
            entities,

        "windows":
            entities,

        "window_count":
            len(
                entities
            ),

        "door_count":
            0,
    }


# ============================================================
# SYNTHETIC SELF TEST
# ============================================================


def self_test():
    def line(
        x0,
        y0,
        x1,
        y1,
    ):
        return {
            "layer":
                "TEST",

            "points":
                [
                    (
                        float(x0),
                        float(y0),
                    ),
                    (
                        float(x1),
                        float(y1),
                    ),
                ],
        }


    def rect(
        x0,
        y0,
        x1,
        y1,
    ):
        return [
            line(
                x0,
                y0,
                x1,
                y0,
            ),
            line(
                x1,
                y0,
                x1,
                y1,
            ),
            line(
                x1,
                y1,
                x0,
                y1,
            ),
            line(
                x0,
                y1,
                x0,
                y0,
            ),
        ]


    geometry = []

    # Ground.
    geometry.append(
        line(
            0,
            0,
            1400,
            0,
        )
    )


    # ========================================================
    # PHYSICAL WINDOW 1:
    # four leaves inside ONE outer frame.
    # ========================================================

    geometry += rect(
        100,
        120,
        500,
        420,
    )

    leaf_width = 90

    for i in range(4):

        lx0 = (
            115
            + i * 95
        )

        lx1 = (
            lx0
            + leaf_width
        )

        geometry += rect(
            lx0,
            135,
            lx1,
            405,
        )

        geometry.append(
            line(
                (
                    lx0 + lx1
                ) * 0.5,
                145,
                (
                    lx0 + lx1
                ) * 0.5,
                395,
            )
        )

        geometry.append(
            line(
                lx0 + 6,
                260,
                lx1 - 6,
                260,
            )
        )

    # Sill.
    geometry.append(
        line(
            80,
            105,
            520,
            105,
        )
    )


    # ========================================================
    # PHYSICAL WINDOW 2:
    # standalone two-light window.
    # ========================================================

    geometry += rect(
        650,
        140,
        850,
        430,
    )

    geometry += rect(
        665,
        155,
        835,
        415,
    )

    geometry.append(
        line(
            750,
            165,
            750,
            405,
        )
    )

    geometry.append(
        line(
            675,
            280,
            825,
            280,
        )
    )

    geometry.append(
        line(
            630,
            125,
            870,
            125,
        )
    )


    # ========================================================
    # DOOR:
    # outer frame reaches ground, contains decorative panels.
    # Panels must NOT become windows.
    # ========================================================

    geometry += rect(
        1000,
        0,
        1160,
        430,
    )

    geometry += rect(
        1020,
        220,
        1140,
        400,
    )

    geometry += rect(
        1020,
        30,
        1140,
        190,
    )


    result = detect_graph_facade_windows(
        geometry,
        (
            0,
            0,
            1400,
            600,
        ),
    )


    windows = result[
        "windows"
    ]


    print(
        "ENGINE:",
        result[
            "engine"
        ],
    )

    print(
        "CYCLES:",
        result[
            "cycle_count"
        ],
    )

    print(
        "HYPOTHESES:",
        result[
            "hypothesis_count"
        ],
    )

    print(
        "WINDOWS:",
        result[
            "window_count"
        ],
    )


    for window in windows:
        print(
            window[
                "entity_id"
            ],
            window[
                "bbox"
            ],
            "FAMILY:",
            window[
                "family_size"
            ],
            "SCORE:",
            round(
                window[
                    "graph_window_score"
                ],
                3,
            ),
        )


    assert (
        result[
            "window_count"
        ]
        == 2
    ), result


    wide = min(
        windows,
        key=lambda row:
            abs(
                row[
                    "center"
                ][0]
                - 300.0
            )
    )


    assert all(
        abs(
            a - b
        ) < 1.0e-6
        for a, b in zip(
            wide[
                "bbox"
            ],
            (
                100.0,
                120.0,
                500.0,
                420.0,
            ),
        )
    ), wide


    assert (
        wide[
            "family_size"
        ]
        >= 2
    ), wide


    print(
        "GRAPH WINDOW SELF TEST: OK"
    )


if __name__ == "__main__":
    self_test()
