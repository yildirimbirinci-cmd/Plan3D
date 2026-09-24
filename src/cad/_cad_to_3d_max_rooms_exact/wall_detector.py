"""
Public wall detector facade.

All recognition authority lives in src.cad.architectural_graph.
This module preserves the existing detect_walls(...) contract used by the
rest of CAD_to_3D_Max.
"""

from __future__ import annotations

from cad._cad_to_3d_max_rooms_exact.architectural_graph import (
    build_architectural_wall_graph,
)


def detect_walls(
    geometry,
    cad_meta=None,
):
    return build_architectural_wall_graph(
        geometry,
        cad_meta=cad_meta,
    )
