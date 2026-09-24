from __future__ import annotations

from pathlib import Path
import math
import re


MARKER = "PLAN3D_WALL_ONLY_MAX_BRIDGE_V2"


def _safe_name(value):
    text = str(value or "").strip()
    text = re.sub(r"[^A-Za-z0-9_]+", "_", text)
    return text.strip("_") or "Floor"


def _is_closed(points):
    if len(points) < 3:
        return False

    a = points[0]
    b = points[-1]

    return (
        abs(float(a[0]) - float(b[0])) <= 1.0e-6
        and abs(float(a[1]) - float(b[1])) <= 1.0e-6
    )


def _mxs_float(value):
    value = float(value)

    if not math.isfinite(value):
        value = 0.0

    return f"{value:.6f}"



# PLAN3D_CAD_MAX_UNIT_ADAPTER_V1
_DXF_TO_CM = {
    0: 1.0, 1: 2.54, 2: 30.48, 3: 160934.4,
    4: 0.1, 5: 1.0, 6: 100.0, 7: 100000.0,
    10: 91.44, 14: 10.0, 15: 1000.0, 16: 10000.0,
}

def _cad_unit_info(viewport):
    doc = getattr(viewport, "_document", None)
    code = 0
    if doc is not None:
        try:
            code = int(doc.header.get("$INSUNITS", 0) or 0)
        except Exception:
            code = 0
    names = {
        0: "Unitless", 1: "Inches", 2: "Feet", 3: "Miles",
        4: "Millimeters", 5: "Centimeters", 6: "Meters",
        7: "Kilometers", 10: "Yards", 14: "Decimeters",
        15: "Decameters", 16: "Hectometers",
    }
    return {
        "code": code,
        "name": names.get(code, "Unknown"),
        "to_cm": float(_DXF_TO_CM.get(code, 1.0)),
    }


def _collect_floor_payload(
    viewport,
    floor_name,
    bounds,
    pivot,
    settings,
):
    geometry = viewport._pivot_collect_wall_geometry(
        bounds
    )

    if not geometry:
        return None

    cad_units = _cad_unit_info(viewport)
    cad_to_cm = float(cad_units["to_cm"])

    pivot_x = float(pivot["pivot_x"])
    pivot_y = float(pivot["pivot_y"])

    base_z = float(
        settings.get(
            "floor_elevation_cm",
            0.0,
        )
    )

    wall_height = float(
        settings.get(
            "wall_height_cm",
            280.0,
        )
    )

    slab_thickness = float(
        settings.get(
            "slab_thickness_cm",
            35.0,
        )
    )

    floor_to_floor = float(
        settings.get(
            "floor_to_floor_cm",
            wall_height + slab_thickness,
        )
    )

    paths = []

    for source_points in geometry:
        points = []

        for source_point in source_points:
            try:
                points.append(
                    (
                        (float(source_point[0]) - pivot_x) * cad_to_cm,
                        (float(source_point[1]) - pivot_y) * cad_to_cm,
                        base_z,
                    )
                )
            except (
                TypeError,
                ValueError,
                IndexError,
            ):
                continue

        if len(points) < 2:
            continue

        closed = _is_closed(points)

        if closed:
            points = points[:-1]

        if len(points) < 2:
            continue

        paths.append(
            {
                "closed": bool(closed),
                "points": points,
            }
        )

    if not paths:
        return None

    return {
        "name": str(floor_name),
        "safe_name": _safe_name(floor_name),
        "pivot_x": pivot_x,
        "pivot_y": pivot_y,
        "base_z_cm": base_z,
        "wall_height_cm": wall_height,
        "slab_thickness_cm": slab_thickness,
        "floor_to_floor_cm": floor_to_floor,
        "cad_unit_name": str(cad_units["name"]),
        "cad_to_cm": float(cad_to_cm),
        "path_count": len(paths),
        "paths": paths,
    }


def _make_maxscript(floors):
    lines = [
        "-- PLAN3D WALL ONLY MAX BRIDGE V2",
        'undo "Plan3D Wall Import" on (',
        "    local created = #()",
        '    local PLAN3D_CM = units.decodeValue "1cm"',
        '    format "PLAN3D MAX UNIT | cmToSystem=%\\n" PLAN3D_CM',
        '    try(format "PLAN3D MAX UNIT | SystemType=% | SystemScale=%\\n" units.SystemType units.SystemScale)catch()',
        '    try(format "PLAN3D MAX UNIT | DisplayType=%\\n" units.DisplayType)catch()',
    ]

    for floor in floors:
        safe = floor["safe_name"]
        object_name = "PLAN3D_WALL_" + safe

        lines.append("")
        lines.append(
            f'    -- FLOOR: {floor["name"]}'
        )
        lines.append(
            f'    local oldObj_{safe} = getNodeByName "{object_name}"'
        )
        lines.append(
            f'    if oldObj_{safe} != undefined do delete oldObj_{safe}'
        )
        lines.append(
            f'    local shp_{safe} = splineShape name:"{object_name}"'
        )

        for path_index, path in enumerate(
            floor["paths"],
            start=1,
        ):
            lines.append(
                f"    addNewSpline shp_{safe}"
            )
            lines.append(
                f"    local sp_{safe}_{path_index} = numSplines shp_{safe}"
            )

            for x, y, z in path["points"]:
                lines.append(
                    "    addKnot "
                    f"shp_{safe} "
                    f"sp_{safe}_{path_index} "
                    "#corner #line "
                    "[("
                    + _mxs_float(x)
                    + "*PLAN3D_CM),("
                    + _mxs_float(y)
                    + "*PLAN3D_CM),("
                    + _mxs_float(z)
                    + "*PLAN3D_CM)]"
                )

            if path["closed"]:
                lines.append(
                    f"    close shp_{safe} sp_{safe}_{path_index}"
                )

        lines.append(
            f"    updateShape shp_{safe}"
        )

        lines.append(
            f"    -- PLAN3D_SPLINE_TOPOLOGY_GUARD_V2"
        )

        lines.append(
            f'    local PLAN3D_WELD_EPS_{safe} = units.decodeValue "0.001cm"'
        )

        lines.append(
            f"    for ss = 1 to (numSplines shp_{safe}) do ("
        )

        lines.append(
            f"        local kc = numKnots shp_{safe} ss"
        )

        lines.append(
            f"        if kc > 0 do setKnotSelection shp_{safe} ss (for kk = 1 to kc collect kk) keep:true"
        )

        lines.append(
            f"    )"
        )

        lines.append(
            f"    weldSpline shp_{safe} PLAN3D_WELD_EPS_{safe}"
        )

        lines.append(
            f"    updateShape shp_{safe}"
        )

        lines.append(
            f"    local PLAN3D_OPEN_COUNT_{safe} = 0"
        )

        lines.append(
            f"    for ss = 1 to (numSplines shp_{safe}) do if not (isClosed shp_{safe} ss) do PLAN3D_OPEN_COUNT_{safe} += 1"
        )

        lines.append(
            f"    if PLAN3D_OPEN_COUNT_{safe} > 0 do ("
        )

        lines.append(
            '        format "PLAN3D OPEN WALL SPLINES KEPT | '
            + str(floor["name"])
            + ' | openSplines=%\n" PLAN3D_OPEN_COUNT_'
            + safe
        )

        lines.append(
            f"    )"
        )

        lines.append(
            '    format "PLAN3D WALL SPLINES READY | '
            + str(floor["name"])
            + ' | splines=% | open=%\n" (numSplines shp_'
            + safe
            + ') PLAN3D_OPEN_COUNT_'
            + safe
        )

        lines.append(
            f"    append created shp_{safe}"
        )
        lines.append(
            f'    format "PLAN3D FLOOR OK | {floor["name"]} | paths={floor["path_count"]} | Z={floor["base_z_cm"]:.3f} cm\\n"'
        )

    lines.extend(
        [
            "",
                "    if created.count > 0 do select created",
            "    completeRedraw()",
            '    format "PLAN3D WALL ONLY COMPLETE | objects=%\\n" created.count',
            ")",
        ]
    )

    return "\n".join(lines) + "\n"



# PLAN3D_CANONICAL_WALL_EXPORT_OVERRIDE_V4
from plan3d_canonical_export import prepare_wall_only_transfer as _prepare_base_wall_transfer

# ============================================================
# PLAN3D_PROJECT_PARENT_LAYER_V1
# Max layer hierarchy:
#
# <ProjectName>
#     PLAN3D_WALLS
#
# ProjectName comes from the saved .p3d filename.
# ============================================================

from pathlib import Path as _Plan3DPath

_plan3d_prepare_wall_only_transfer_before_project_layer = _prepare_base_wall_transfer




def _plan3d_mxs_string(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
    )




def _prepare_wall_with_project_layer(panel):
    result = _plan3d_prepare_wall_only_transfer_before_project_layer(panel)

    project_name = _plan3d_project_name_from_panel(panel)

    pending_path = None

    if isinstance(result, dict):
        pending_path = (
            result.get("pending_script")
            or result.get("pending_path")
        )

    if not pending_path:
        pending_path = (
            _Plan3DPath.cwd()
            / "runtime"
            / "max_bridge"
            / "pending.ms"
        )

    _plan3d_add_project_layer_hierarchy(
        pending_path,
        project_name,
    )

    if isinstance(result, dict):
        result["project_layer"] = project_name
        result["wall_layer"] = "PLAN3D_WALLS"

    print(
        "PLAN3D MAX LAYER TREE |",
        project_name,
        "-> PLAN3D_WALLS",
    )

    return result


# END PLAN3D_PROJECT_PARENT_LAYER_V1

# ============================================================
# PLAN3D_PROJECT_PARENT_LAYER_V2
# Correct project-name source:
# 1) MainWindow.current_project (.p3d filename)
# 2) active tab name
# 3) CAD source fallback
# ============================================================

from pathlib import Path as _Plan3DLayerPath


def _plan3d_project_name_from_panel(panel):
    page = None

    try:
        page = panel.parentWidget()
    except Exception:
        page = None

    # Walk QWidget parent chain until MainWindow-like object.
    current = page
    visited = set()

    while current is not None and id(current) not in visited:
        visited.add(id(current))

        project_path = getattr(
            current,
            "current_project",
            None,
        )

        if project_path:
            name = _Plan3DLayerPath(
                str(project_path)
            ).stem.strip()

            if name:
                return name

        # Project runtime also uses the tab title as project_name.
        tabs = getattr(
            current,
            "tabs",
            None,
        )

        if tabs is not None and page is not None:
            try:
                index = tabs.indexOf(page)

                if index >= 0:
                    tab_name = str(
                        tabs.tabText(index)
                        or ""
                    ).strip()

                    if tab_name and tab_name.lower() != "start":
                        return tab_name
            except Exception:
                pass

        try:
            current = current.parentWidget()
        except Exception:
            current = None

    # CAD source fallback only if no project is saved/opened.
    source_path = None

    if page is not None:
        viewport = getattr(
            page,
            "viewport",
            None,
        )

        if viewport is not None:
            source_path = getattr(
                viewport,
                "_source_path",
                None,
            )

        if not source_path:
            source_path = (
                getattr(
                    page,
                    "_source_cad_path",
                    None,
                )
                or getattr(
                    page,
                    "cad_path",
                    None,
                )
            )

    if source_path:
        name = _Plan3DLayerPath(
            str(source_path)
        ).stem.strip()

        if name:
            return name

    return "Plan3D_Project"




# END PLAN3D_PROJECT_PARENT_LAYER_V2

# ============================================================
# PLAN3D_PROJECT_PARENT_LAYER_V3
# Fix: MaxScript top-level cannot contain "local" declarations.
# Uses top-level assignments with unique PLAN3D_* names instead.
# ============================================================


def _plan3d_add_project_layer_hierarchy(
    pending_path,
    project_name,
):
    pending_path = _Plan3DLayerPath(
        pending_path
    )

    if not pending_path.exists():
        raise RuntimeError(
            "Max pending script was not found: "
            + str(pending_path)
        )

    script = pending_path.read_text(
        encoding="utf-8-sig"
    )

    # Remove older runtime hierarchy blocks if present.
    for marker in (
        "-- PLAN3D_PROJECT_PARENT_LAYER_RUNTIME_V2",
        "-- PLAN3D_PROJECT_PARENT_LAYER_RUNTIME",
    ):
        if marker in script:
            script = script.split(
                marker,
                1,
            )[0].rstrip()

    safe_name = (
        str(project_name)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
    )

    runtime = (
        "\n"
        "-- PLAN3D_PROJECT_PARENT_LAYER_RUNTIME_V3\n"
        'PLAN3D_PROJECT_LAYER_NAME = "'
        + safe_name
        + '"\n'
        'PLAN3D_WALL_LAYER_NAME = "PLAN3D_WALLS"\n'
        "PLAN3D_PROJECT_LAYER = "
        "LayerManager.getLayerFromName PLAN3D_PROJECT_LAYER_NAME\n"
        "if PLAN3D_PROJECT_LAYER == undefined do "
        "PLAN3D_PROJECT_LAYER = "
        "LayerManager.newLayerFromName PLAN3D_PROJECT_LAYER_NAME\n"
        "PLAN3D_WALL_LAYER = "
        "LayerManager.getLayerFromName PLAN3D_WALL_LAYER_NAME\n"
        "if PLAN3D_WALL_LAYER == undefined do "
        "PLAN3D_WALL_LAYER = "
        "LayerManager.newLayerFromName PLAN3D_WALL_LAYER_NAME\n"
        "if PLAN3D_PROJECT_LAYER == undefined then (\n"
        '    format "PLAN3D PROJECT LAYER ERROR | parent create failed | %\\n" '
        "PLAN3D_PROJECT_LAYER_NAME\n"
        ") else if PLAN3D_WALL_LAYER == undefined then (\n"
        '    format "PLAN3D PROJECT LAYER ERROR | wall layer missing | %\\n" '
        "PLAN3D_WALL_LAYER_NAME\n"
        ") else (\n"
        "    PLAN3D_PARENT_OK = "
        "PLAN3D_WALL_LAYER.setParent PLAN3D_PROJECT_LAYER\n"
        '    format "PLAN3D PROJECT LAYER | parent=% | child=% | setParent=%\\n" '
        "PLAN3D_PROJECT_LAYER_NAME PLAN3D_WALL_LAYER_NAME PLAN3D_PARENT_OK\n"
        "    PLAN3D_CHECK_PARENT = PLAN3D_WALL_LAYER.getParent()\n"
        "    if PLAN3D_CHECK_PARENT != undefined then (\n"
        '        format "PLAN3D PROJECT LAYER VERIFY | child=% | parent=%\\n" '
        "PLAN3D_WALL_LAYER_NAME PLAN3D_CHECK_PARENT.name\n"
        "    ) else (\n"
        '        format "PLAN3D PROJECT LAYER VERIFY ERROR | child has no parent\\n"\n'
        "    )\n"
        ")\n"
    )

    pending_path.write_text(
        script
        + runtime,
        encoding="utf-8",
    )


# END PLAN3D_PROJECT_PARENT_LAYER_V3

# ============================================================
# PLAN3D_WALL_EXTRUDE_BY_HEIGHT_V1
# Applies an Extrude modifier to each exported wall object
# using that floor's wall_height_cm value.
# ============================================================

from pathlib import Path as _Plan3DExtrudePath


_plan3d_prepare_wall_only_transfer_before_extrude = (
    _prepare_wall_with_project_layer
)


def _plan3d_escape_mxs_string(value):
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
    )


def _plan3d_append_wall_extrude_script(
    pending_path,
    floors,
):
    pending_path = _Plan3DExtrudePath(
        pending_path
    )

    if not pending_path.exists():
        raise RuntimeError(
            "Max pending script was not found: "
            + str(pending_path)
        )

    script = pending_path.read_text(
        encoding="utf-8-sig"
    )

    marker = (
        "-- PLAN3D_WALL_EXTRUDE_RUNTIME_V1"
    )

    if marker in script:
        script = script.split(
            marker,
            1,
        )[0].rstrip()

    lines = [
        "",
        marker,
        'PLAN3D_EXTRUDE_CM = units.decodeValue "1cm"',
    ]

    for floor in floors or ():
        floor_name = str(
            floor.get(
                "name",
                "Floor",
            )
        )

        safe_name = str(
            floor.get(
                "safe_name",
                floor_name,
            )
        )

        object_name = (
            "PLAN3D_WALL_"
            + safe_name
        )

        wall_height_cm = float(
            floor.get(
                "wall_height_cm",
                0.0,
            )
            or 0.0
        )

        if wall_height_cm <= 0.0:
            raise RuntimeError(
                "Invalid Wall Height for "
                + floor_name
                + ": "
                + str(
                    wall_height_cm
                )
                + " cm"
            )

        object_literal = (
            _plan3d_escape_mxs_string(
                object_name
            )
        )

        floor_literal = (
            _plan3d_escape_mxs_string(
                floor_name
            )
        )

        amount_text = (
            f"{wall_height_cm:.9f}"
        )

        lines.extend(
            [
                (
                    'PLAN3D_EXTRUDE_OBJ = getNodeByName "'
                    + object_literal
                    + '"'
                ),
                (
                    "if PLAN3D_EXTRUDE_OBJ == undefined then ("
                ),
                (
                    '    format "PLAN3D EXTRUDE ERROR | object not found | '
                    + object_literal
                    + '\\n"'
                ),
                (
                    ") else ("
                ),
                (
                    "    PLAN3D_EXTRUDE_MOD = Extrude()"
                ),
                (
                    "    PLAN3D_EXTRUDE_MOD.amount = ("
                    + amount_text
                    + " * PLAN3D_EXTRUDE_CM)"
                ),
                (
                    "    try(PLAN3D_EXTRUDE_MOD.capStart = true)catch()"
                ),
                (
                    "    try(PLAN3D_EXTRUDE_MOD.capEnd = true)catch()"
                ),
                (
                    "    addModifier PLAN3D_EXTRUDE_OBJ PLAN3D_EXTRUDE_MOD"
                ),
                (
                    '    format "PLAN3D EXTRUDE OK | '
                    + floor_literal
                    + ' | object='
                    + object_literal
                    + ' | height='
                    + f"{wall_height_cm:.3f}"
                    + ' cm\\n"'
                ),
                (
                    ")"
                ),
            ]
        )

    pending_path.write_text(
        script.rstrip()
        + "\n"
        + "\n".join(
            lines
        )
        + "\n",
        encoding="utf-8",
    )


def _prepare_wall_with_extrude(panel):
    result = (
        _plan3d_prepare_wall_only_transfer_before_extrude(
            panel
        )
    )

    if not isinstance(
        result,
        dict,
    ):
        raise RuntimeError(
            "Wall export result is not a dictionary."
        )

    floors = list(
        result.get(
            "floors",
            []
        )
        or []
    )

    if not floors:
        raise RuntimeError(
            "Wall export returned no floor payload."
        )

    pending_path = (
        result.get(
            "pending_script"
        )
        or result.get(
            "pending_path"
        )
        or (
            _Plan3DExtrudePath.cwd()
            / "runtime"
            / "max_bridge"
            / "pending.ms"
        )
    )

    _plan3d_append_wall_extrude_script(
        pending_path,
        floors,
    )

    result[
        "wall_extrude_applied"
    ] = True

    print(
        "PLAN3D WALL EXTRUDE PREPARED | floors=",
        len(
            floors
        ),
    )

    return result


# END PLAN3D_WALL_EXTRUDE_BY_HEIGHT_V1

# ============================================================
# PLAN3D_FLOOR_MAX_EXPORT_V1
# ============================================================

_plan3d_prepare_wall_only_transfer_before_floor_export_v1 = _prepare_wall_with_extrude


def _plan3d_floor_mxs_float_v1(value):
    value = float(value)
    if abs(value) < 1.0e-12:
        value = 0.0
    return format(value, ".12g")


def _plan3d_floor_mxs_escape_v1(value):
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _plan3d_append_floor_maxscript_v1(pending_path, floor_payload, project_name):
    from pathlib import Path as _Path

    pending = _Path(pending_path)

    if not pending.exists():
        raise RuntimeError("PLAN3D floor export: pending MaxScript not found.")

    parent_name = str(project_name or "queens road_test").strip()
    child_name = "floor"

    lines = [
        "",
        "-- PLAN3D_FLOOR_MAX_EXPORT_V1",
        'undo "Plan3D Floor Import" on (',
        '    local PLAN3D_CM = units.decodeValue "1cm"',
        '    local PLAN3D_FLOOR_PARENT_NAME = "' + _plan3d_floor_mxs_escape_v1(parent_name) + '"',
        '    local PLAN3D_FLOOR_LAYER_NAME = "floor"',
        "    local PLAN3D_FLOOR_PARENT = LayerManager.getLayerFromName PLAN3D_FLOOR_PARENT_NAME",
        "    if PLAN3D_FLOOR_PARENT == undefined do PLAN3D_FLOOR_PARENT = LayerManager.newLayerFromName PLAN3D_FLOOR_PARENT_NAME",
        "    local PLAN3D_FLOOR_LAYER = LayerManager.getLayerFromName PLAN3D_FLOOR_LAYER_NAME",
        "    if PLAN3D_FLOOR_LAYER == undefined do PLAN3D_FLOOR_LAYER = LayerManager.newLayerFromName PLAN3D_FLOOR_LAYER_NAME",
        "    try(PLAN3D_FLOOR_LAYER.setParent PLAN3D_FLOOR_PARENT)catch()",
        "    local PLAN3D_FLOOR_CREATED = #()",
    ]

    total_objects = 0

    for floor in list(floor_payload.get("floors", []) or []):
        floor_name = str(floor.get("name", "Floor") or "Floor")
        safe_floor = str(floor.get("safe_name", "Floor") or "Floor")
        safe_floor = "".join(
            ch if (ch.isalnum() or ch == "_") else "_"
            for ch in safe_floor
        ).strip("_") or "Floor"

        for obj in list(floor.get("objects", []) or []):
            object_index = int(obj.get("index", 0) or 0)
            if object_index <= 0:
                continue

            object_name = "PLAN3D_FLOOR_" + safe_floor + "_" + str(object_index).zfill(3)
            safe_var = safe_floor + "_" + str(object_index)

            lines.append(
                '    local oldFloor_' + safe_var
                + ' = getNodeByName "' + _plan3d_floor_mxs_escape_v1(object_name) + '" exact:true'
            )
            lines.append(
                "    if oldFloor_" + safe_var
                + " != undefined do delete oldFloor_" + safe_var
            )
            lines.append(
                '    local floorShp_' + safe_var
                + ' = splineShape name:"' + _plan3d_floor_mxs_escape_v1(object_name) + '"'
            )

            ring_count = 0

            for ring in list(obj.get("rings", []) or []):
                points = list(ring.get("points", []) or [])
                if len(points) < 3:
                    continue

                ring_count += 1

                lines.append("    addNewSpline floorShp_" + safe_var)
                lines.append(
                    "    local floorSpline_" + safe_var + "_" + str(ring_count)
                    + " = numSplines floorShp_" + safe_var
                )

                for point in points:
                    x, y, z = [float(value) for value in point[:3]]
                    lines.append(
                        "    addKnot floorShp_" + safe_var
                        + " floorSpline_" + safe_var + "_" + str(ring_count)
                        + " #corner #line "
                        + "[(" + _plan3d_floor_mxs_float_v1(x) + "*PLAN3D_CM),("
                        + _plan3d_floor_mxs_float_v1(y) + "*PLAN3D_CM),("
                        + _plan3d_floor_mxs_float_v1(z) + "*PLAN3D_CM)]"
                    )

                lines.append(
                    "    close floorShp_" + safe_var
                    + " floorSpline_" + safe_var + "_" + str(ring_count)
                )

            if ring_count <= 0:
                lines.append("    delete floorShp_" + safe_var)
                continue

            lines.append("    updateShape floorShp_" + safe_var)
            lines.append("    PLAN3D_FLOOR_LAYER.addNode floorShp_" + safe_var)
            lines.append("    local floorEditPoly_" + safe_var + " = Edit_Poly()")
            lines.append(
                "    addModifier floorShp_" + safe_var + " floorEditPoly_" + safe_var
            )
            lines.append("    append PLAN3D_FLOOR_CREATED floorShp_" + safe_var)
            lines.append(
                '    format "PLAN3D FLOOR SPLINE OK | floor='
                + _plan3d_floor_mxs_escape_v1(floor_name)
                + " | object="
                + _plan3d_floor_mxs_escape_v1(object_name)
                + ' | rings=%\\n" '
                + str(ring_count)
            )

            total_objects += 1

    lines.extend(
        [
            '    format "PLAN3D FLOOR EXPORT COMPLETE | objects=% | parent=% | layer=%\\n" PLAN3D_FLOOR_CREATED.count PLAN3D_FLOOR_PARENT_NAME PLAN3D_FLOOR_LAYER_NAME',
            "    completeRedraw()",
            ")",
            "",
        ]
    )

    if total_objects <= 0:
        raise RuntimeError("PLAN3D floor export: no floor spline object was produced.")

    original = pending.read_text(encoding="utf-8")

    pending.write_text(
        original.rstrip() + "\n" + "\n".join(lines),
        encoding="utf-8",
    )

    return int(total_objects)


def _prepare_wall_with_floor(panel):
    from floor_area_runtime import show_all_floor_areas as _show_floor_areas_v1
    import json as _floor_json
    from pathlib import Path as _FloorPath

    _show_floor_areas_v1(panel)

    result = _plan3d_prepare_wall_only_transfer_before_floor_export_v1(panel)

    if not isinstance(result, dict):
        raise RuntimeError("PLAN3D floor export: wall export result is not a dictionary.")

    payload_path = (
        _FloorPath.cwd()
        / "runtime"
        / "max_bridge"
        / "floor_export_payload.json"
    )

    if not payload_path.exists():
        raise RuntimeError("PLAN3D floor export payload was not created.")

    payload = _floor_json.loads(payload_path.read_text(encoding="utf-8"))

    try:
        project_name = _plan3d_project_name_from_panel(panel)
    except Exception:
        project_name = None

    if not str(project_name or "").strip():
        project_name = "queens road_test"

    pending_path = result.get("pending_script") or result.get("pending_path")

    if not pending_path:
        raise RuntimeError("PLAN3D floor export: pending MaxScript path is missing.")

    floor_object_count = _plan3d_append_floor_maxscript_v1(
        pending_path,
        payload,
        project_name,
    )

    result["floor_export_engine"] = "PLAN3D_FLOOR_MAX_EXPORT_V1"
    result["floor_object_count"] = int(floor_object_count)
    result["floor_parent_layer"] = str(project_name)
    result["floor_layer"] = "floor"

    print(
        "PLAN3D FLOOR MAX EXPORT V1 |",
        "objects=",
        floor_object_count,
        "| parent=",
        project_name,
        "| layer=floor",
        flush=True,
    )

    return result

# ============================================================
# PLAN3D_INTERIOR_DOOR_MAX_V1
#
# Proven topology order adapted to Plan3D:
#   1) Extruded wall object
#   2) Edit Poly
#   3) select ALL vertical edges
#   4) Connect once
#   5) move new horizontal Connect edges to UI door height
#   6) resolve the two upper jamb faces for each interior door
#   7) BridgePolygons pairwise
#
# Door height is per-floor and comes from Export Details.
# ============================================================

_plan3d_prepare_before_interior_door_max_v1 = (
    _prepare_wall_with_floor
)


def _plan3d_door_bounds_v1(value):
    if isinstance(value, dict):
        for key in (
            "bounds",
            "bbox",
            "source_bounds",
            "cad_bounds",
        ):
            raw = value.get(key)
            if (
                isinstance(raw, (list, tuple))
                and len(raw) >= 4
            ):
                try:
                    x0, y0, x1, y1 = [
                        float(v)
                        for v in raw[:4]
                    ]
                    return (
                        min(x0, x1),
                        min(y0, y1),
                        max(x0, x1),
                        max(y0, y1),
                    )
                except Exception:
                    pass

        for key in (
            "rect_values",
            "rect",
            "selection_rect",
        ):
            raw = value.get(key)
            if (
                isinstance(raw, (list, tuple))
                and len(raw) >= 4
            ):
                try:
                    x, y, w, h = [
                        float(v)
                        for v in raw[:4]
                    ]
                    return (
                        min(x, x + w),
                        min(y, y + h),
                        max(x, x + w),
                        max(y, y + h),
                    )
                except Exception:
                    pass

        for nested in value.values():
            found = _plan3d_door_bounds_v1(
                nested
            )
            if found is not None:
                return found

    if (
        isinstance(value, (list, tuple))
        and len(value) == 4
    ):
        try:
            x, y, w, h = [
                float(v)
                for v in value
            ]
            return (
                min(x, x + w),
                min(y, y + h),
                max(x, x + w),
                max(y, y + h),
            )
        except Exception:
            pass

    return None




def _plan3d_door_summary_owner_v1(panel):
    # PLAN3D_INTERIOR_DOOR_SUMMARY_OWNER_FIX_V4
    #
    # Resolve the same live preview object used elsewhere in Plan3D.
    # Do not assume preview is exposed as panel.viewport / page.preview.
    #
    # Search:
    #   1) direct panel/page/window relations
    #   2) every QObject descendant of those objects
    #   3) all live QApplication widgets and their descendants

    queue = []
    seen = set()

    def push(value):
        if value is None:
            return

        ident = id(value)

        if ident in seen:
            return

        seen.add(ident)
        queue.append(value)

    def push_children(value):
        try:
            children = value.children()
        except Exception:
            children = []

        for child in children or []:
            push(child)

    push(panel)

    try:
        push(panel.parentWidget())
    except Exception:
        pass

    try:
        push(panel.window())
    except Exception:
        pass

    # Global Qt widget search is required because the CAD preview is not
    # guaranteed to be exposed as a named attribute on ExportDetailsPanel.
    try:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()

        if app is not None:
            try:
                for widget in app.allWidgets():
                    push(widget)
            except Exception:
                pass

            try:
                for widget in app.topLevelWidgets():
                    push(widget)
            except Exception:
                pass
    except Exception:
        pass

    index = 0

    while index < len(queue):
        obj = queue[index]
        index += 1

        method = getattr(
            obj,
            "cad_summary_for_bounds",
            None,
        )

        if callable(method):
            print(
                "PLAN3D INTERIOR DOOR SUMMARY OWNER V4 |",
                type(obj).__name__,
                "| objectName=",
                (
                    obj.objectName()
                    if hasattr(obj, "objectName")
                    else ""
                ),
                flush=True,
            )
            return obj

        # Traverse the QObject tree.
        push_children(obj)

        # Also traverse known ownership attributes.
        for attr_name in (
            "preview",
            "viewport",
            "cad_view",
            "cad_preview",
            "cad_page",
            "page",
            "current_page",
            "tabs",
            "stack",
            "stacked_widget",
            "central_widget",
            "centralWidget",
        ):
            try:
                child = getattr(
                    obj,
                    attr_name,
                    None,
                )
            except Exception:
                child = None

            if (
                callable(child)
                and attr_name
                in {
                    "centralWidget",
                }
            ):
                try:
                    child = child()
                except Exception:
                    child = None

            push(child)

        for method_name in (
            "currentWidget",
            "widget",
        ):
            method = getattr(
                obj,
                method_name,
                None,
            )

            if not callable(method):
                continue

            if method_name == "currentWidget":
                try:
                    push(method())
                except Exception:
                    pass

        parent_widget = getattr(
            obj,
            "parentWidget",
            None,
        )

        if callable(parent_widget):
            try:
                push(parent_widget())
            except Exception:
                pass

    raise RuntimeError(
        "Interior Door Max: no live object exposing "
        "cad_summary_for_bounds() was found in the Qt object tree."
    )




def _build_door_maxscript_base(
    door_floors,
):
    import json as _json

    payload = _json.dumps(
        door_floors,
        ensure_ascii=False,
    )

    # JSON is embedded only as a comment for audit;
    # MaxScript statements below are generated explicitly.
    lines = [
        "",
        "-- PLAN3D_INTERIOR_DOOR_MAX_V1",
        "-- PAYLOAD " + payload,
        "",
        "fn PLAN3D_Door_GetFaceInfo ep obj faceIndex =",
        "(",
        "    local degree = ep.GetFaceDegree faceIndex node:obj",
        "    if degree < 3 then return undefined",
        "    local points = #()",
        "    local center = [0,0,0]",
        "    local minZ = 1.0e30",
        "    local maxZ = -1.0e30",
        "    for cornerIndex = 1 to degree do",
        "    (",
        "        local vertexIndex = ep.GetFaceVertex faceIndex cornerIndex node:obj",
        "        if vertexIndex <= 0 then return undefined",
        "        local p = ep.GetVertex vertexIndex node:obj",
        "        append points p",
        "        center += p",
        "        if p.z < minZ do minZ = p.z",
        "        if p.z > maxZ do maxZ = p.z",
        "    )",
        "    center /= degree",
        "    local normalValue = [0,0,0]",
        "    for cornerIndex = 2 to (degree - 1) while (length normalValue) <= 0.000001 do",
        "    (",
        "        local a = points[cornerIndex] - points[1]",
        "        local b = points[cornerIndex + 1] - points[1]",
        "        local n = cross a b",
        "        if (length n) > 0.000001 do normalValue = normalize n",
        "    )",
        "    #(center, minZ, maxZ, normalValue)",
        ")",
        "",
        "fn PLAN3D_Door_ResolveBestPair ep obj jambA jambB targetZ expectedWidth =",
        "(",
        "    local faceCount = ep.GetNumFaces node:obj",
        "    local openingVector = jambB - jambA",
        "    openingVector.z = 0.0",
        "    if (length openingVector) <= 0.000001 then return #(false,0,0,0,0,0,0,0,0,0,0,0,\"zero-opening-vector\",\"none\")",
        "    local openingDirection = normalize openingVector",
        "    local zTolerance = units.decodeValue \"1cm\"",
        "    local minUpperHeight = units.decodeValue \"2cm\"",
        "    local maxJambDistance = expectedWidth * 0.70",
        "    local minimumSearchDistance = units.decodeValue \"35cm\"",
        "    if maxJambDistance < minimumSearchDistance do maxJambDistance = minimumSearchDistance",
        "    local minAxisAlignment = 0.55",
        "    local minParallel = 0.75",
        "    local candidatesA = #()",
        "    local candidatesB = #()",
        "    local allUpperFaces = #()",
        "    for faceIndex = 1 to faceCount do",
        "    (",
        "        local info = PLAN3D_Door_GetFaceInfo ep obj faceIndex",
        "        if info != undefined do",
        "        (",
        "            local centerValue = info[1]",
        "            local minZ = info[2]",
        "            local maxZ = info[3]",
        "            local normalValue = info[4]",
        "            local startsAtHeader = (abs (minZ - targetZ)) <= zTolerance",
        "            local reachesAbove = maxZ > (targetZ + minUpperHeight)",
        "            local verticalFace = (abs normalValue.z) < 0.25",
        "            local axisAlignment = abs (dot normalValue openingDirection)",
        "            if startsAtHeader and reachesAbove and verticalFace and (axisAlignment >= minAxisAlignment) do",
        "            (",
        "                append allUpperFaces #(faceIndex, info, axisAlignment)",
        "                local dA = distance [centerValue.x,centerValue.y,0] [jambA.x,jambA.y,0]",
        "                local dB = distance [centerValue.x,centerValue.y,0] [jambB.x,jambB.y,0]",
        "                if dA <= maxJambDistance do append candidatesA #(faceIndex,dA,info,axisAlignment)",
        "                if dB <= maxJambDistance do append candidatesB #(faceIndex,dB,info,axisAlignment)",
        "            )",
        "        )",
        "    )",
        "    local bestFaceA = 0",
        "    local bestFaceB = 0",
        "    local bestDistanceA = 0.0",
        "    local bestDistanceB = 0.0",
        "    local bestPairDistance = 0.0",
        "    local bestWidthRatio = 0.0",
        "    local bestParallel = 0.0",
        "    local bestAlignA = 0.0",
        "    local bestAlignB = 0.0",
        "    local bestScore = 1.0e30",
        "    for candidateA in candidatesA do",
        "    (",
        "        for candidateB in candidatesB do",
        "        (",
        "            local faceA = candidateA[1]",
        "            local faceB = candidateB[1]",
        "            if faceA != faceB do",
        "            (",
        "                local infoA = candidateA[3]",
        "                local infoB = candidateB[3]",
        "                local centerA = infoA[1]",
        "                local centerB = infoB[1]",
        "                local normalA = infoA[4]",
        "                local normalB = infoB[4]",
        "                local pairVector = centerB - centerA",
        "                pairVector.z = 0.0",
        "                local pairDistance = length pairVector",
        "                if pairDistance > 0.000001 do",
        "                (",
        "                    local widthRatio = pairDistance / expectedWidth",
        "                    local normalParallel = abs (dot normalA normalB)",
        "                    local alignA = candidateA[4]",
        "                    local alignB = candidateB[4]",
        "                    local widthOK = (widthRatio >= 0.45) and (widthRatio <= 1.55)",
        "                    local parallelOK = normalParallel >= minParallel",
        "                    if widthOK and parallelOK do",
        "                    (",
        "                        local widthError = abs (pairDistance - expectedWidth)",
        "                        local score = candidateA[2] + candidateB[2] + (widthError * 0.75) + ((1.0-normalParallel)*expectedWidth*0.35)",
        "                        if score < bestScore do",
        "                        (",
        "                            bestScore = score",
        "                            bestFaceA = faceA",
        "                            bestFaceB = faceB",
        "                            bestDistanceA = candidateA[2]",
        "                            bestDistanceB = candidateB[2]",
        "                            bestPairDistance = pairDistance",
        "                            bestWidthRatio = widthRatio",
        "                            bestParallel = normalParallel",
        "                            bestAlignA = alignA",
        "                            bestAlignB = alignB",
        "                        )",
        "                    )",
        "                )",
        "            )",
        "        )",
        "    )",
        "    if bestFaceA <= 0 or bestFaceB <= 0 then return #(false,0,0,0,0,0,0,0,0,0,candidatesA.count,candidatesB.count,\"no-compatible-pair\",\"none\")",
        "    #(true,bestFaceA,bestFaceB,bestDistanceA,bestDistanceB,bestPairDistance,bestWidthRatio,bestParallel,bestAlignA,bestAlignB,candidatesA.count,candidatesB.count,\"ok\",\"primary\")",
        ")",
        "",
        "fn PLAN3D_Door_ProcessFloor obj doorHeightCm baseZCm doorRows =",
        "(",
        "    if obj == undefined then return false",
        "    if doorRows.count <= 0 then",
        "    (",
        "        format \"PLAN3D INTERIOR DOOR | % | no bridge-ready doors\\n\" obj.name",
        "        return true",
        "    )",
        "    local ep = Edit_Poly()",
        "    addModifier obj ep",
        "    max modify mode",
        "    select obj",
        "    ep.SetPrimaryNode obj",
        "    modPanel.setCurrentObject ep",
        "    ep.selectMode = 1",
        "    ep.SetEPolySelLevel #Edge",
        "    subObjectLevel = 2",
        "    ep.RefreshScreen()",
        "    completeRedraw()",
        "    local edgeCountBefore = ep.GetNumEdges node:obj",
        "    local verticalEdges = #{}",
        "    local verticalCount = 0",
        "    local absoluteXYTolerance = units.decodeValue \"0.01mm\"",
        "    local relativeXYTolerance = 0.000001",
        "    local minVerticalLength = units.decodeValue \"1mm\"",
        "    for edgeIndex = 1 to edgeCountBefore do",
        "    (",
        "        local va = ep.GetEdgeVertex edgeIndex 1 node:obj",
        "        local vb = ep.GetEdgeVertex edgeIndex 2 node:obj",
        "        if (va > 0) and (vb > 0) do",
        "        (",
        "            local pa = ep.GetVertex va node:obj",
        "            local pb = ep.GetVertex vb node:obj",
        "            local dx = abs (pb.x-pa.x)",
        "            local dy = abs (pb.y-pa.y)",
        "            local dz = abs (pb.z-pa.z)",
        "            local xyTolerance = absoluteXYTolerance",
        "            if (dz*relativeXYTolerance) > xyTolerance do xyTolerance = dz*relativeXYTolerance",
        "            if (dz > minVerticalLength) and (dx <= xyTolerance) and (dy <= xyTolerance) do",
        "            (",
        "                verticalEdges[edgeIndex] = true",
        "                verticalCount += 1",
        "            )",
        "        )",
        "    )",
        "    if verticalCount <= 0 then",
        "    (",
        "        format \"PLAN3D INTERIOR DOOR ERROR | % | no vertical edges\\n\" obj.name",
        "        return false",
        "    )",
        "    local clearEdges = #{}",
        "    ep.SetSelection #Edge &clearEdges node:obj",
        "    local selOK = ep.Select #Edge &verticalEdges select:true node:obj",
        "    local selRead = ep.GetSelection #Edge node:obj",
        "    if (selOK != true) or (selRead.numberSet != verticalCount) then",
        "    (",
        "        format \"PLAN3D INTERIOR DOOR ERROR | % | vertical edge selection failed | wanted=% selected=%\\n\" obj.name verticalCount selRead.numberSet",
        "        return false",
        "    )",
        "    ep.connectEdgeSegments = 1",
        "    ep.connectEdgePinch = 0",
        "    ep.connectEdgeSlide = 0",
        "    ep.ButtonOp #ConnectEdges",
        "    ep.RefreshScreen()",
        "    completeRedraw()",
        "    local edgeCountAfter = ep.GetNumEdges node:obj",
        "    if edgeCountAfter <= edgeCountBefore then",
        "    (",
        "        format \"PLAN3D INTERIOR DOOR ERROR | % | Connect created no edges\\n\" obj.name",
        "        return false",
        "    )",
        "    local horizontalEdges = #{}",
        "    local horizontalCount = 0",
        "    local zTol = units.decodeValue \"0.5mm\"",
        "    local minLen = units.decodeValue \"1mm\"",
        "    local firstHorizontal = 0",
        "    for edgeIndex = (edgeCountBefore+1) to edgeCountAfter do",
        "    (",
        "        local va = ep.GetEdgeVertex edgeIndex 1 node:obj",
        "        local vb = ep.GetEdgeVertex edgeIndex 2 node:obj",
        "        if (va > 0) and (vb > 0) do",
        "        (",
        "            local pa = ep.GetVertex va node:obj",
        "            local pb = ep.GetVertex vb node:obj",
        "            local dz = abs (pb.z-pa.z)",
        "            local dx = pb.x-pa.x",
        "            local dy = pb.y-pa.y",
        "            local xyLen = sqrt ((dx*dx)+(dy*dy))",
        "            if (dz <= zTol) and (xyLen > minLen) do",
        "            (",
        "                horizontalEdges[edgeIndex] = true",
        "                horizontalCount += 1",
        "                if firstHorizontal == 0 do firstHorizontal = edgeIndex",
        "            )",
        "        )",
        "    )",
        "    if horizontalCount <= 0 or firstHorizontal <= 0 then",
        "    (",
        "        format \"PLAN3D INTERIOR DOOR ERROR | % | new horizontal Connect edges not found\\n\" obj.name",
        "        return false",
        "    )",
        "    local firstV = ep.GetEdgeVertex firstHorizontal 1 node:obj",
        "    local firstP = ep.GetVertex firstV node:obj",
        "    local currentConnectZ = firstP.z",
        "    local targetZ = (baseZCm + doorHeightCm) * (units.decodeValue \"1cm\")",
        "    ep.SetSelection #Edge &clearEdges node:obj",
        "    local hSelOK = ep.Select #Edge &horizontalEdges select:true node:obj",
        "    local hRead = ep.GetSelection #Edge node:obj",
        "    if (hSelOK != true) or (hRead.numberSet != horizontalCount) then",
        "    (",
        "        format \"PLAN3D INTERIOR DOOR ERROR | % | header edge selection failed\\n\" obj.name",
        "        return false",
        "    )",
        "    ep.useSoftSel = false",
        "    ep.SetOperation #Transform",
        "    ep.MoveSelection [0,0,(targetZ-currentConnectZ)]",
        "    ep.Commit()",
        "    ep.RefreshScreen()",
        "    completeRedraw()",
        "    ep.SetEPolySelLevel #Face",
        "    subObjectLevel = 4",
        "    for d = 1 to doorRows.count do",
        "    (",
        "        local r = doorRows[d]",
        "        local jambA = [(r[1]*(units.decodeValue \"1cm\")),(r[2]*(units.decodeValue \"1cm\")),targetZ]",
        "        local jambB = [(r[3]*(units.decodeValue \"1cm\")),(r[4]*(units.decodeValue \"1cm\")),targetZ]",
        "        local expectedWidth = distance jambA jambB",
        "        if expectedWidth <= (units.decodeValue \"20cm\") then",
        "        (",
        "            format \"PLAN3D INTERIOR DOOR ERROR | % | door % invalid width=%\\n\" obj.name d expectedWidth",
        "            return false",
        "        )",
        "        local pairResult = PLAN3D_Door_ResolveBestPair ep obj jambA jambB targetZ expectedWidth",
        "        if pairResult[1] != true then",
        "        (",
        "            format \"PLAN3D INTERIOR DOOR ERROR | % | door % pair unresolved | candA=% candB=% reason=%\\n\" obj.name d pairResult[11] pairResult[12] pairResult[13]",
        "            return false",
        "        )",
        "    )",
        "    local completed = 0",
        "    for d = 1 to doorRows.count do",
        "    (",
        "        local r = doorRows[d]",
        "        local jambA = [(r[1]*(units.decodeValue \"1cm\")),(r[2]*(units.decodeValue \"1cm\")),targetZ]",
        "        local jambB = [(r[3]*(units.decodeValue \"1cm\")),(r[4]*(units.decodeValue \"1cm\")),targetZ]",
        "        local expectedWidth = distance jambA jambB",
        "        local pairResult = PLAN3D_Door_ResolveBestPair ep obj jambA jambB targetZ expectedWidth",
        "        local faceA = pairResult[2]",
        "        local faceB = pairResult[3]",
        "        if pairResult[1] != true then return false",
        "        local clearFaces = #{}",
        "        ep.SetSelection #Face &clearFaces node:obj",
        "        local pairFaces = #{}",
        "        pairFaces[faceA] = true",
        "        pairFaces[faceB] = true",
        "        local selectReturn = ep.Select #Face &pairFaces select:true node:obj",
        "        local readback = ep.GetSelection #Face node:obj",
        "        if (selectReturn != true) or (readback.numberSet != 2) or (readback[faceA] != true) or (readback[faceB] != true) then",
        "        (",
        "            format \"PLAN3D INTERIOR DOOR ERROR | % | door % exact face selection failed\\n\" obj.name d",
        "            return false",
        "        )",
        "        ep.BridgePolygons faceA faceB node:obj",
        "        ep.Commit()",
        "        ep.RefreshScreen()",
        "        completeRedraw()",
        "        completed += 1",
        "        format \"PLAN3D INTERIOR DOOR BRIDGED | % | door=% | faces=%<->% | height=% cm\\n\" obj.name d faceA faceB doorHeightCm",
        "    )",
        "    local emptyFaces = #{}",
        "    ep.SetSelection #Face &emptyFaces node:obj",
        "    ep.RefreshScreen()",
        "    completeRedraw()",
        "    format \"PLAN3D INTERIOR DOOR COMPLETE | % | connectVertical=% | headerEdges=% | bridged=%/% | height=% cm\\n\" obj.name verticalCount horizontalCount completed doorRows.count doorHeightCm",
        "    completed == doorRows.count",
        ")",
        "",
        "undo \"Plan3D Interior Doors\" on (",
    ]

    for floor in door_floors:
        safe = str(
            floor.get(
                "safe_name",
                "Floor",
            )
        )
        safe = "".join(
            ch if (
                ch.isalnum()
                or ch == "_"
            ) else "_"
            for ch in safe
        ).strip("_") or "Floor"

        name = (
            "PLAN3D_WALL_"
            + safe
        )

        door_height = float(
            floor[
                "door_height_cm"
            ]
        )
        base_z = float(
            floor[
                "base_z_cm"
            ]
        )

        rows = []

        for door in floor[
            "doors"
        ]:
            a = door[
                "jamb_a_cm"
            ]
            b = door[
                "jamb_b_cm"
            ]

            rows.append(
                "#("
                + ",".join(
                    format(
                        float(v),
                        ".12g",
                    )
                    for v in (
                        a[0],
                        a[1],
                        b[0],
                        b[1],
                    )
                )
                + ")"
            )

        row_expr = (
            "#("
            + ",".join(
                rows
            )
            + ")"
        )

        lines.extend(
            [
                (
                    '    local PLAN3D_DOOR_OBJ = getNodeByName "'
                    + name.replace(
                        '"',
                        '\\"',
                    )
                    + '" exact:true'
                ),
                (
                    "    if PLAN3D_DOOR_OBJ == undefined then "
                    + 'format "PLAN3D INTERIOR DOOR ERROR | object missing: '
                    + name.replace(
                        '"',
                        '\\"',
                    )
                    + '\\n"'
                    + " else"
                ),
                "    (",
                (
                    "        local PLAN3D_DOOR_ROWS = "
                    + row_expr
                ),
                (
                    "        local PLAN3D_DOOR_OK = PLAN3D_Door_ProcessFloor "
                    + "PLAN3D_DOOR_OBJ "
                    + format(
                        door_height,
                        ".12g",
                    )
                    + " "
                    + format(
                        base_z,
                        ".12g",
                    )
                    + " PLAN3D_DOOR_ROWS"
                ),
                (
                    "        if PLAN3D_DOOR_OK != true do "
                    + 'format "PLAN3D INTERIOR DOOR FAILED | '
                    + str(
                        floor[
                            "name"
                        ]
                    ).replace(
                        '"',
                        '\\"',
                    )
                    + '\\n"'
                ),
                "    )",
            ]
        )

    lines.extend(
        [
            "    completeRedraw()",
            ")",
            "",
        ]
    )

    return "\n".join(
        lines
    ) + "\n"


def _plan3d_append_interior_door_max_v1(
    pending_path,
    door_floors,
):
    from pathlib import Path as _P

    pending = _P(
        pending_path
    )

    if not pending.exists():
        raise RuntimeError(
            "Interior Door Max: pending.ms not found."
        )

    script = pending.read_text(
        encoding="utf-8"
    )

    runtime = _build_interior_door_maxscript(
        door_floors
    )

    pending.write_text(
        script.rstrip()
        + "\n"
        + runtime,
        encoding="utf-8",
    )



# ============================================================
# PLAN3D_INTERIOR_DOOR_DIRECT_VIEWPORT_V5
#
# Door data source is the SAME live viewport/document used by Create3D.
# No cad_summary_for_bounds() owner lookup is used.
# ============================================================

def _plan3d_direct_cad_geometry_v5(
    viewport,
    bounds,
):
    import math as _math

    document = getattr(
        viewport,
        "_document",
        None,
    )

    if document is None:
        raise RuntimeError(
            "Interior Door Max: viewport._document is not available."
        )

    try:
        modelspace = document.modelspace()
    except Exception as exc:
        raise RuntimeError(
            "Interior Door Max: document.modelspace() is not available: "
            + repr(exc)
        )

    x0, y0, x1, y1 = [
        float(v)
        for v in bounds
    ]

    min_x = min(x0, x1)
    min_y = min(y0, y1)
    max_x = max(x0, x1)
    max_y = max(y0, y1)

    def point2(value):
        try:
            return (
                float(value[0]),
                float(value[1]),
            )
        except Exception:
            try:
                return (
                    float(value.x),
                    float(value.y),
                )
            except Exception:
                return None

    def bbox_overlaps(points):
        valid = [
            p
            for p in points
            if p is not None
        ]

        if not valid:
            return False

        px0 = min(p[0] for p in valid)
        py0 = min(p[1] for p in valid)
        px1 = max(p[0] for p in valid)
        py1 = max(p[1] for p in valid)

        return not (
            px1 < min_x
            or px0 > max_x
            or py1 < min_y
            or py0 > max_y
        )

    def sample_arc(
        center,
        radius,
        start_deg,
        end_deg,
    ):
        cx, cy = center

        sweep = (
            float(end_deg)
            - float(start_deg)
        ) % 360.0

        if sweep <= 1.0e-9:
            sweep = 360.0

        steps = max(
            8,
            int(
                _math.ceil(
                    sweep / 7.5
                )
            ),
        )

        result = []

        for index in range(
            steps + 1
        ):
            angle_deg = (
                float(start_deg)
                + sweep
                * index
                / steps
            )

            angle = _math.radians(
                angle_deg
            )

            result.append(
                (
                    cx
                    + float(radius)
                    * _math.cos(angle),
                    cy
                    + float(radius)
                    * _math.sin(angle),
                )
            )

        return result

    def entity_points(entity):
        try:
            kind = str(
                entity.dxftype()
            ).upper()
        except Exception:
            return [], False

        if kind == "LINE":
            a = point2(
                entity.dxf.start
            )
            b = point2(
                entity.dxf.end
            )
            return (
                [
                    p
                    for p in (a, b)
                    if p is not None
                ],
                False,
            )

        if kind == "ARC":
            center = point2(
                entity.dxf.center
            )

            if center is None:
                return [], False

            try:
                points = sample_arc(
                    center,
                    float(
                        entity.dxf.radius
                    ),
                    float(
                        entity.dxf.start_angle
                    ),
                    float(
                        entity.dxf.end_angle
                    ),
                )
            except Exception:
                return [], False

            return points, False

        if kind == "CIRCLE":
            center = point2(
                entity.dxf.center
            )

            if center is None:
                return [], True

            try:
                radius = float(
                    entity.dxf.radius
                )
            except Exception:
                return [], True

            points = []

            for index in range(49):
                angle = (
                    2.0
                    * _math.pi
                    * index
                    / 48.0
                )

                points.append(
                    (
                        center[0]
                        + radius
                        * _math.cos(angle),
                        center[1]
                        + radius
                        * _math.sin(angle),
                    )
                )

            return points, True

        if kind in {
            "LWPOLYLINE",
            "POLYLINE",
        }:
            # First choice: flatten the real path so bulged door arcs
            # stay arcs instead of becoming only chord endpoints.
            try:
                from ezdxf.path import make_path

                path = make_path(
                    entity
                )

                points = [
                    point2(vertex)
                    for vertex in path.flattening(
                        distance=1.0,
                        segments=8,
                    )
                ]

                points = [
                    p
                    for p in points
                    if p is not None
                ]

                closed = bool(
                    getattr(
                        entity,
                        "closed",
                        False,
                    )
                )

                if (
                    not closed
                    and points
                    and len(points) >= 3
                ):
                    try:
                        closed = bool(
                            entity.is_closed
                        )
                    except Exception:
                        pass

                return points, closed
            except Exception:
                pass

            try:
                if kind == "LWPOLYLINE":
                    points = [
                        (
                            float(row[0]),
                            float(row[1]),
                        )
                        for row in entity.get_points(
                            "xy"
                        )
                    ]
                    closed = bool(
                        entity.closed
                    )
                else:
                    points = [
                        point2(
                            vertex.dxf.location
                        )
                        for vertex in entity.vertices
                    ]
                    points = [
                        p
                        for p in points
                        if p is not None
                    ]
                    closed = bool(
                        entity.is_closed
                    )

                return points, closed
            except Exception:
                return [], False

        if kind == "SPLINE":
            try:
                points = [
                    point2(p)
                    for p in entity.flattening(
                        distance=1.0,
                        segments=8,
                    )
                ]
                points = [
                    p
                    for p in points
                    if p is not None
                ]
                return points, False
            except Exception:
                return [], False

        return [], False

    geometry = []

    for entity in modelspace:
        points, closed = entity_points(
            entity
        )

        if len(points) < 2:
            continue

        if not bbox_overlaps(
            points
        ):
            continue

        try:
            layer = str(
                entity.dxf.layer
            )
        except Exception:
            layer = ""

        geometry.append(
            {
                "layer":
                    layer,
                "points":
                    [
                        [
                            float(p[0]),
                            float(p[1]),
                        ]
                        for p in points
                    ],
                "closed":
                    bool(
                        closed
                    ),
                "entity_type":
                    str(
                        entity.dxftype()
                    ),
            }
        )

    print(
        "PLAN3D INTERIOR DOOR DIRECT CAD V5 | geometry=",
        len(
            geometry
        ),
        "| bounds=",
        (
            min_x,
            min_y,
            max_x,
            max_y,
        ),
        flush=True,
    )

    return geometry



# ============================================================
# PLAN3D_INTERIOR_DOOR_PENDING_FIX_V6
#
# The interior-door stage must NOT assume pending.ms still exists.
# Earlier export stages may already have consumed/renamed it.
#
# Rule:
#   - call the last known-good pre-door export wrapper
#   - build door payload
#   - if pending.ms exists -> append door MaxScript
#   - if pending.ms does not exist -> create a fresh pending.ms
#     containing ONLY the door MaxScript
#   - always return the actual pending path
# ============================================================

def _plan3d_write_or_append_door_script_v6(
    pending_path,
    door_floors,
):
    from pathlib import Path as _P

    pending = _P(
        pending_path
    )

    pending.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    runtime = _build_interior_door_maxscript(
        door_floors
    )

    if pending.exists():
        current = pending.read_text(
            encoding="utf-8"
        )

        pending.write_text(
            current.rstrip()
            + "\n"
            + runtime,
            encoding="utf-8",
        )

        mode = "APPEND"
    else:
        pending.write_text(
            runtime,
            encoding="utf-8",
        )

        mode = "CREATE"

    print(
        "PLAN3D INTERIOR DOOR PENDING V6 |",
        mode,
        "|",
        str(
            pending
        ),
        flush=True,
    )

    return pending


def _prepare_wall_with_interior_doors(panel):
    result = (
        _plan3d_prepare_before_interior_door_max_v1(
            panel
        )
    )

    if not isinstance(
        result,
        dict,
    ):
        raise RuntimeError(
            "Interior Door Max V6: pre-door export result invalid."
        )

    wall_floors = list(
        result.get(
            "floors",
            [],
        )
        or []
    )

    if not wall_floors:
        raise RuntimeError(
            "Interior Door Max V6: wall floor payload is empty."
        )

    door_floors = (
        _collect_interior_doors(
            panel,
            wall_floors,
        )
    )

    project_root = (
        _P3D_DOOR_ROOT_V6
    )

    pending_value = (
        result.get(
            "pending_script"
        )
        or result.get(
            "pending_path"
        )
    )

    if pending_value:
        from pathlib import Path as _P

        candidate = _P(
            pending_value
        )

        if not candidate.is_absolute():
            candidate = (
                project_root
                / candidate
            )
    else:
        candidate = (
            project_root
            / "runtime"
            / "max_bridge"
            / "pending.ms"
        )

    pending = (
        _plan3d_write_or_append_door_script_v6(
            candidate,
            door_floors,
        )
    )

    result[
        "pending_script"
    ] = str(
        pending
    )

    result[
        "pending_path"
    ] = str(
        pending
    )

    result[
        "interior_door_engine"
    ] = (
        "PLAN3D_INTERIOR_DOOR_MAX_V1"
    )

    result[
        "interior_door_pending_fix"
    ] = (
        "PLAN3D_INTERIOR_DOOR_PENDING_FIX_V6"
    )

    result[
        "interior_door_floors"
    ] = door_floors

    result[
        "interior_door_count"
    ] = sum(
        int(
            floor.get(
                "door_count",
                0,
            )
            or 0
        )
        for floor in door_floors
    )

    print(
        "PLAN3D INTERIOR DOOR MAX V6 PREPARED |",
        "floors=",
        len(
            door_floors
        ),
        "| doors=",
        result[
            "interior_door_count"
        ],
        "| pending=",
        str(
            pending
        ),
        flush=True,
    )

    return result


from pathlib import Path as _P3DPathV6
_P3D_DOOR_ROOT_V6 = (
    _P3DPathV6(__file__)
    .resolve()
    .parents[2]
)

# ============================================================
# PLAN3D_INTERIOR_DOOR_FROM_FLOOR_ENGINE_V7
#
# Interior-door jamb source is now the SAME accepted topology used by
# Floor Areas:
#   Create3D export-prepared Wall
#   + _symbol_opening_bridge_paths(...)
#
# For each "Door" bridge:
#   first point = jamb/contact A
#   last point  = jamb/contact B
#
# No independent detect_doors() pass.
# No cad_summary_for_bounds().
# No separate door re-detection.
# ============================================================


# ============================================================
# PLAN3D_INTERIOR_DOOR_BRIDGE_RESOLVER_V8
#
# Connect is already confirmed working.
# This patch changes ONLY the post-Connect face-pair resolver.
#
# Old resolver was too strict:
#   - jamb distance <= 0.70 x opening width
#   - face normal alignment >= 0.55
#   - opposite faces parallel >= 0.75
#   - pair width 0.45..1.55 x expected
#
# New resolver keeps the geometric essentials only:
#   - face begins at header Z
#   - face continues upward
#   - face is vertical
#   - each face is locally near one jamb
#   - pair span is compatible with door width
#
# BridgePolygons execution itself is unchanged.
# ============================================================

_door_mxs_base = _build_door_maxscript_base


def _build_door_maxscript_pair_resolver(door_floors):
    script = (
        _door_mxs_base(
            door_floors
        )
    )

    replacements = (
        (
            'local maxJambDistance = expectedWidth * 0.70',
            'local maxJambDistance = expectedWidth * 1.25',
        ),
        (
            'local minAxisAlignment = 0.55',
            'local minAxisAlignment = 0.0',
        ),
        (
            'local minParallel = 0.75',
            'local minParallel = 0.0',
        ),
        (
            'local verticalFace = (abs normalValue.z) < 0.25',
            'local verticalFace = (abs normalValue.z) < 0.50',
        ),
        (
            'local widthOK = (widthRatio >= 0.45) and (widthRatio <= 1.55)',
            'local widthOK = (widthRatio >= 0.25) and (widthRatio <= 2.25)',
        ),
        (
            'local parallelOK = normalParallel >= minParallel',
            'local parallelOK = true',
        ),
    )

    for old, new in replacements:
        if old not in script:
            raise RuntimeError(
                "Interior Door Bridge V8: expected MaxScript token missing: "
                + old
            )

        script = script.replace(
            old,
            new,
            1,
        )

    # Make pair resolver diagnostics explicit in the Max Listener.
    old_line = (
        'if bestFaceA <= 0 or bestFaceB <= 0 then return '
        '#(false,0,0,0,0,0,0,0,0,0,candidatesA.count,candidatesB.count,'
        '"no-compatible-pair","none")'
    )

    new_line = (
        'if bestFaceA <= 0 or bestFaceB <= 0 then '
        '(format "PLAN3D DOOR PAIR V8 FAIL | obj=% | candA=% | candB=% | width=%\\n" '
        'obj.name candidatesA.count candidatesB.count expectedWidth; '
        'return #(false,0,0,0,0,0,0,0,0,0,candidatesA.count,candidatesB.count,'
        '"no-compatible-pair","none"))'
    )

    if old_line in script:
        script = script.replace(
            old_line,
            new_line,
            1,
        )

    return script

# ============================================================
# PLAN3D_INTERIOR_DOOR_PAIR_CLOSURES_V9
#
# Floor Areas produces TWO wall-thickness closure lines for one Door.
# A single closure line is wall thickness (~14 cm), NOT door width.
#
# General rule:
#   same Door group_index
#   -> collect its two closure paths
#   -> midpoint(path 1) = jamb/contact station A
#   -> midpoint(path 2) = jamb/contact station B
#   -> distance(midpoint A, midpoint B) = real door opening width
#
# Max Connect/header logic remains unchanged.
# ============================================================

# ============================================================
# PLAN3D_INTERIOR_DOOR_GEOMETRIC_PAIR_V10
#
# V9 assumed both wall-thickness closure lines of one Door shared the
# same group_index. Runtime showed that assumption is false.
#
# General rule:
#   - collect ALL semantic_type == "Door" closure lines
#   - each closure line is one jamb cross-section through wall thickness
#   - pair two compatible closure lines geometrically:
#       * nearly parallel
#       * similar wall-thickness length
#       * midpoint-to-midpoint direction nearly perpendicular to closure
#       * opening width larger than wall thickness
#   - each closure can belong to only one Door
#   - midpoint pair becomes jamb A/B for Max Bridge
#
# Connect/header/Bridge Max code is unchanged.
# ============================================================

def _collect_interior_doors(
    panel,
    wall_floors,
):
    import math as _math

    from floor_area_runtime import (
        _export_prepared_wall_paths,
        _symbol_opening_bridge_paths,
    )
    from plan3d_canonical_export import (
        _cad_unit_info,
    )

    page = panel.parentWidget()

    if page is None:
        raise RuntimeError(
            "Interior Door Max V10: CAD page is not available."
        )

    viewport = getattr(
        page,
        "viewport",
        None,
    )

    if viewport is None:
        raise RuntimeError(
            "Interior Door Max V10: viewport is not available."
        )

    values = panel.values()

    assignments = (
        values.get(
            "assignments",
            {},
        )
        .get(
            "floor_plans",
            {},
        )
        or {}
    )

    settings_map = (
        values.get(
            "floor_settings",
            {},
        )
        or {}
    )

    pivot_map = dict(
        getattr(
            panel,
            "_floor_pivots",
            {},
        )
        or {}
    )

    units_info = _cad_unit_info(
        viewport
    )

    cad_to_cm_global = float(
        units_info.get(
            "to_cm",
            1.0,
        )
        or 1.0
    )

    source_to_mm = (
        cad_to_cm_global
        * 10.0
    )

    floor_by_name = {
        str(
            row.get(
                "name",
                "",
            )
        ): row
        for row in (
            wall_floors
            or []
        )
        if isinstance(
            row,
            dict,
        )
    }

    payload = []

    for floor_name, rect_values in assignments.items():
        floor_name = str(
            floor_name
        )

        wall_floor = floor_by_name.get(
            floor_name
        )

        if not isinstance(
            wall_floor,
            dict,
        ):
            continue

        pivot = dict(
            pivot_map.get(
                floor_name,
                {},
            )
            or {}
        )

        pivot.setdefault(
            "pivot_x",
            float(
                wall_floor.get(
                    "pivot_x",
                    0.0,
                )
                or 0.0
            ),
        )
        pivot.setdefault(
            "pivot_y",
            float(
                wall_floor.get(
                    "pivot_y",
                    0.0,
                )
                or 0.0
            ),
        )

        settings = dict(
            settings_map.get(
                floor_name,
                {},
            )
            or {}
        )

        (
            wall_paths,
            _wall_topology,
            export_floor,
        ) = _export_prepared_wall_paths(
            viewport,
            floor_name,
            rect_values,
            pivot,
            settings,
            units_info,
        )

        (
            bridge_paths,
            bridge_meta,
            bridge_stats,
        ) = _symbol_opening_bridge_paths(
            viewport,
            rect_values,
            wall_paths,
            source_to_mm,
        )

        cad_to_cm = float(
            export_floor.get(
                "cad_to_cm",
                wall_floor.get(
                    "cad_to_cm",
                    cad_to_cm_global,
                ),
            )
            or cad_to_cm_global
        )

        pivot_x = float(
            export_floor.get(
                "pivot_x",
                wall_floor.get(
                    "pivot_x",
                    0.0,
                ),
            )
            or 0.0
        )

        pivot_y = float(
            export_floor.get(
                "pivot_y",
                wall_floor.get(
                    "pivot_y",
                    0.0,
                ),
            )
            or 0.0
        )

        closures = []

        def _plan3d_door_gap_is_clear_v25(closure_a, closure_b):
            import math as _math

            try:
                a0 = closure_a["path"][0]
                a1 = closure_a["path"][-1]
                b0 = closure_b["path"][0]
                b1 = closure_b["path"][-1]

                a0 = (float(a0[0]), float(a0[1]))
                a1 = (float(a1[0]), float(a1[1]))
                b0 = (float(b0[0]), float(b0[1]))
                b1 = (float(b1[0]), float(b1[1]))
            except Exception:
                return False

            def _dist(p, q):
                return _math.hypot(
                    q[0] - p[0],
                    q[1] - p[1],
                )

            direct = (
                _dist(a0, b0)
                + _dist(a1, b1)
            )

            crossed = (
                _dist(a0, b1)
                + _dist(a1, b0)
            )

            if direct <= crossed:
                side_pairs = (
                    (a0, b0),
                    (a1, b1),
                )
            else:
                side_pairs = (
                    (a0, b1),
                    (a1, b0),
                )

            source_per_cm = (
                1.0
                / max(
                    float(cad_to_cm),
                    1.0e-12,
                )
            )

            line_tol = (
                0.5
                * source_per_cm
            )

            endpoint_margin = (
                2.0
                * source_per_cm
            )

            def _wall_exists_inside_gap(start, end):
                sx = float(start[0])
                sy = float(start[1])
                ex = float(end[0])
                ey = float(end[1])

                vx = ex - sx
                vy = ey - sy

                length = _math.hypot(
                    vx,
                    vy,
                )

                if length <= 1.0e-9:
                    return True

                ux = vx / length
                uy = vy / length

                t0 = min(
                    endpoint_margin,
                    length * 0.20,
                )
                t1 = max(
                    t0,
                    length - t0,
                )

                if (t1 - t0) <= line_tol:
                    return False

                for wall_path in wall_paths:
                    if (
                        not isinstance(
                            wall_path,
                            (list, tuple),
                        )
                        or len(wall_path) < 2
                    ):
                        continue

                    for raw_c, raw_d in zip(
                        wall_path,
                        wall_path[1:],
                    ):
                        try:
                            cx = float(raw_c[0])
                            cy = float(raw_c[1])
                            dx = float(raw_d[0])
                            dy = float(raw_d[1])
                        except Exception:
                            continue

                        tc = (
                            (cx - sx) * ux
                            + (cy - sy) * uy
                        )
                        td = (
                            (dx - sx) * ux
                            + (dy - sy) * uy
                        )

                        pc = abs(
                            (cx - sx) * (-uy)
                            + (cy - sy) * ux
                        )
                        pd = abs(
                            (dx - sx) * (-uy)
                            + (dy - sy) * ux
                        )

                        if (
                            pc > line_tol
                            or pd > line_tol
                        ):
                            continue

                        seg0 = min(
                            tc,
                            td,
                        )
                        seg1 = max(
                            tc,
                            td,
                        )

                        overlap = (
                            min(
                                seg1,
                                t1,
                            )
                            - max(
                                seg0,
                                t0,
                            )
                        )

                        if overlap > line_tol:
                            return True

                return False

            return not (
                _wall_exists_inside_gap(
                    side_pairs[0][0],
                    side_pairs[0][1],
                )
                or _wall_exists_inside_gap(
                    side_pairs[1][0],
                    side_pairs[1][1],
                )
            )


        for path, meta in zip(
            bridge_paths,
            bridge_meta,
        ):
            if str(
                meta.get(
                    "semantic_type",
                    "",
                )
            ) != "Door":
                continue

            if not isinstance(
                path,
                (list, tuple),
            ) or len(path) < 2:
                continue

            try:
                p0 = path[0]
                p1 = path[-1]

                x0 = float(p0[0])
                y0 = float(p0[1])
                x1 = float(p1[0])
                y1 = float(p1[1])
            except Exception:
                continue

            dx = x1 - x0
            dy = y1 - y0
            length_src = _math.hypot(
                dx,
                dy,
            )

            if length_src <= 1.0e-9:
                continue

            closures.append(
                {
                    "mid": (
                        (x0 + x1) * 0.5,
                        (y0 + y1) * 0.5,
                    ),
                    "ux":
                        dx / length_src,
                    "uy":
                        dy / length_src,
                    "length_src":
                        length_src,
                    "length_cm":
                        length_src
                        * cad_to_cm,
                    "group_index":
                        int(
                            meta.get(
                                "group_index",
                                -1,
                            )
                        ),
                    "path":
                        path,
                }
            )

        candidates = []

        for i in range(
            len(
                closures
            )
        ):
            a = closures[i]

            for j in range(
                i + 1,
                len(
                    closures
                ),
            ):
                b = closures[j]

                parallel = abs(
                    a["ux"]
                    * b["ux"]
                    + a["uy"]
                    * b["uy"]
                )

                if parallel < 0.94:
                    continue

                min_len = min(
                    a["length_cm"],
                    b["length_cm"],
                )
                max_len = max(
                    a["length_cm"],
                    b["length_cm"],
                )

                if min_len <= 1.0e-9:
                    continue

                thickness_ratio = (
                    max_len
                    / min_len
                )

                if thickness_ratio > 1.50:
                    continue

                sx = (
                    b["mid"][0]
                    - a["mid"][0]
                )
                sy = (
                    b["mid"][1]
                    - a["mid"][1]
                )

                span_src = _math.hypot(
                    sx,
                    sy,
                )

                if span_src <= 1.0e-9:
                    continue

                span_cm = (
                    span_src
                    * cad_to_cm
                )

                sux = sx / span_src
                suy = sy / span_src

                # Door opening runs along wall direction, therefore it should
                # be nearly perpendicular to the jamb closure cross-section.
                cross_axis = abs(
                    sux
                    * a["ux"]
                    + suy
                    * a["uy"]
                )

                if cross_axis > 0.30:
                    continue

                wall_thickness_cm = (
                    a["length_cm"]
                    + b["length_cm"]
                ) * 0.5

                min_opening_cm = max(
                    40.0,
                    wall_thickness_cm * 2.5,
                )

                max_opening_cm = max(
                    250.0,
                    wall_thickness_cm * 18.0,
                )

                if not (
                    min_opening_cm
                    <= span_cm
                    <= max_opening_cm
                ):
                    continue

                score = (
                    span_cm
                    + (1.0 - parallel)
                    * 100.0
                    + cross_axis
                    * 100.0
                    + abs(
                        a["length_cm"]
                        - b["length_cm"]
                    )
                    * 2.0
                )


                # PLAN3D_INTERIOR_DOOR_CLEAR_GAP_PAIR_V25
                # A Door pair is valid only when BOTH wall-side lines
                # between the two closure cross-sections are actually empty.
                if not _plan3d_door_gap_is_clear_v25(
                    a,
                    b,
                ):
                    print(
                        "PLAN3D INTERIOR DOOR V25 REJECT |",
                        floor_name,
                        "| reason=WALL_EXISTS_BETWEEN_CLOSURES",
                        "| groups=",
                        (
                            a["group_index"],
                            b["group_index"],
                        ),
                        "| span_cm=",
                        format(
                            span_cm,
                            ".3f",
                        ),
                        flush=True,
                    )
                    continue

                candidates.append(
                    {
                        "score":
                            float(
                                score
                            ),
                        "i":
                            int(
                                i
                            ),
                        "j":
                            int(
                                j
                            ),
                        "span_cm":
                            float(
                                span_cm
                            ),
                        "parallel":
                            float(
                                parallel
                            ),
                        "cross_axis":
                            float(
                                cross_axis
                            ),
                        "wall_thickness_cm":
                            float(
                                wall_thickness_cm
                            ),
                    }
                )

        candidates.sort(
            key=lambda row: (
                row[
                    "score"
                ],
                row[
                    "span_cm"
                ],
                row[
                    "i"
                ],
                row[
                    "j"
                ],
            )
        )

        used = set()
        doors = []

        for candidate in candidates:
            i = candidate[
                "i"
            ]
            j = candidate[
                "j"
            ]

            if (
                i in used
                or j in used
            ):
                continue

            a = closures[i]
            b = closures[j]

            jamb_a_cm = [
                (
                    a["mid"][0]
                    - pivot_x
                )
                * cad_to_cm,
                (
                    a["mid"][1]
                    - pivot_y
                )
                * cad_to_cm,
            ]

            jamb_b_cm = [
                (
                    b["mid"][0]
                    - pivot_x
                )
                * cad_to_cm,
                (
                    b["mid"][1]
                    - pivot_y
                )
                * cad_to_cm,
            ]

            doors.append(
                {
                    "door_id":
                        "D"
                        + str(
                            len(
                                doors
                            )
                            + 1
                        ).zfill(
                            3
                        ),
                    "jamb_a_cm":
                        jamb_a_cm,
                    "jamb_b_cm":
                        jamb_b_cm,
                    "width_cm":
                        candidate[
                            "span_cm"
                        ],
                    "wall_thickness_cm":
                        candidate[
                            "wall_thickness_cm"
                        ],
                    "source":
                        "GEOMETRIC_CLOSURE_PAIR_V10",
                    "closure_a_index":
                        int(
                            i
                        ),
                    "closure_b_index":
                        int(
                            j
                        ),
                    "group_a":
                        int(
                            a[
                                "group_index"
                            ]
                        ),
                    "group_b":
                        int(
                            b[
                                "group_index"
                            ]
                        ),
                }
            )

            used.add(
                i
            )
            used.add(
                j
            )

            print(
                "PLAN3D INTERIOR DOOR V10 |",
                floor_name,
                "| door=",
                len(
                    doors
                ),
                "| opening_width_cm=",
                format(
                    candidate[
                        "span_cm"
                    ],
                    ".3f",
                ),
                "| wall_thickness_cm=",
                format(
                    candidate[
                        "wall_thickness_cm"
                    ],
                    ".3f",
                ),
                "| groups=",
                (
                    a[
                        "group_index"
                    ],
                    b[
                        "group_index"
                    ],
                ),
                flush=True,
            )

        door_height_cm = float(
            settings.get(
                "door_height_cm",
                values.get(
                    "door_height_cm",
                    210.0,
                ),
            )
            or 210.0
        )

        wall_height_cm = float(
            wall_floor.get(
                "wall_height_cm",
                settings.get(
                    "wall_height_cm",
                    280.0,
                ),
            )
            or 280.0
        )

        if not (
            0.0
            < door_height_cm
            < wall_height_cm
        ):
            raise RuntimeError(
                "Interior Door Height must be between 0 and Wall Height for "
                + floor_name
            )

        payload.append(
            {
                "name":
                    floor_name,
                "safe_name":
                    str(
                        wall_floor.get(
                            "safe_name",
                            floor_name,
                        )
                    ),
                "base_z_cm":
                    float(
                        wall_floor.get(
                            "base_z_cm",
                            0.0,
                        )
                        or 0.0
                    ),
                "wall_height_cm":
                    wall_height_cm,
                "door_height_cm":
                    door_height_cm,
                "door_count":
                    int(
                        len(
                            doors
                        )
                    ),
                "doors":
                    doors,
            }
        )

        print(
            "PLAN3D INTERIOR DOOR GEOMETRIC PAIR V10 |",
            floor_name,
            "| closure_lines=",
            len(
                closures
            ),
            "| pair_candidates=",
            len(
                candidates
            ),
            "| valid_doors=",
            len(
                doors
            ),
            "| door_height_cm=",
            format(
                door_height_cm,
                ".3f",
            ),
            flush=True,
        )

    total_doors = sum(
        int(
            row.get(
                "door_count",
                0,
            )
            or 0
        )
        for row in payload
    )

    if total_doors <= 0:
        raise RuntimeError(
            "Interior Door Max V10: no compatible geometric Door closure pairs."
        )

    return payload

# ============================================================
# INTERIOR DOOR VERTEX WELD
# Working generator stage: weld all vertices at 0.5 mm before Connect.
# ============================================================

_door_mxs_before_vertex_weld = _build_door_maxscript_pair_resolver

def _build_door_maxscript_vertex_weld(door_floors):
    # IMPORTANT:
    # _plan3d_door_mxs_before_vertex_weld_v13 points to the last working
    # generator BEFORE the broken V13 wrapper was installed.
    script = (
        _door_mxs_before_vertex_weld(
            door_floors
        )
    )

    marker = "PLAN3D_INTERIOR_DOOR_VERTEX_WELD"

    if marker in script:
        return script

    anchor = (
        "    local edgeCountBefore = ep.GetNumEdges node:obj"
    )

    if anchor not in script:
        raise RuntimeError(
            "Interior Door Vertex Weld: edgeCountBefore anchor not found."
        )

    weld = (
        "    -- PLAN3D_INTERIOR_DOOR_VERTEX_WELD\n"
        "    ep.selectMode = 1\n"
        "    ep.SetEPolySelLevel #Vertex\n"
        "    subObjectLevel = 1\n"
        "    local PLAN3D_WELD_BEFORE = ep.GetNumVertices node:obj\n"
        "    local PLAN3D_WELD_SET = #{}\n"
        "    if PLAN3D_WELD_BEFORE > 0 do\n"
        "    (\n"
        "        for PLAN3D_WI = 1 to PLAN3D_WELD_BEFORE do PLAN3D_WELD_SET[PLAN3D_WI] = true\n"
        "        ep.SetSelection #Vertex &PLAN3D_WELD_SET node:obj\n"
        "        try(ep.weldVertexThreshold = units.decodeValue \"0.5mm\")catch()\n"
        "        try(ep.ButtonOp #WeldVertex)catch()\n"
        "        ep.Commit()\n"
        "        ep.RefreshScreen()\n"
        "        completeRedraw()\n"
        "    )\n"
        "    local PLAN3D_WELD_AFTER = ep.GetNumVertices node:obj\n"
        "    format \"PLAN3D INTERIOR DOOR VERTEX WELD V15 | % | before=% | after=% | threshold=0.5mm\\n\" obj.name PLAN3D_WELD_BEFORE PLAN3D_WELD_AFTER\n"
        "    ep.SetEPolySelLevel #Edge\n"
        "    subObjectLevel = 2\n"
    )

    script = script.replace(
        anchor,
        weld + anchor,
        1,
    )

    return script

# ============================================================
# PLAN3D_WALL_FOOTPRINT_UNION_V16
#
# Fix overlapping/coplanar wall faces at T/L junctions BEFORE Max extrusion.
#
# Source stays authoritative:
#   plan3d_canonical_export._clean_floor()
#
# We post-process only its CLOSED wall contours:
#   1) rebuild shell/hole relationships by geometric containment
#   2) union separate solid wall polygons
#   3) serialize the cleaned polygon boundaries back to the same paths schema
#
# This preserves rooms/holes and removes overlapping wall footprint regions.
# ============================================================

import plan3d_canonical_export as _plan3d_canonical_v16

_plan3d_clean_floor_before_union_v16 = (
    _plan3d_canonical_v16._clean_floor
)


def _plan3d_wall_polygon_parts_v16(geometry):
    if geometry is None:
        return []

    geom_type = getattr(
        geometry,
        "geom_type",
        "",
    )

    if geom_type == "Polygon":
        return [geometry]

    if geom_type == "MultiPolygon":
        return [
            part
            for part in geometry.geoms
            if not part.is_empty
        ]

    if geom_type == "GeometryCollection":
        result = []

        for part in geometry.geoms:
            result.extend(
                _plan3d_wall_polygon_parts_v16(
                    part
                )
            )

        return result

    return []


def _plan3d_union_wall_footprint_v16(
    payload,
):
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    try:
        from shapely import make_valid
    except Exception:
        make_valid = None

    if not isinstance(
        payload,
        dict,
    ):
        return payload

    paths = list(
        payload.get(
            "paths",
            [],
        )
        or []
    )

    if not paths:
        return payload

    # Canonical wall export is expected to be closed-only.
    # If an open path somehow appears, do not alter the payload.
    if any(
        not bool(
            path.get(
                "closed",
                False,
            )
        )
        for path in paths
        if isinstance(
            path,
            dict,
        )
    ):
        print(
            "PLAN3D WALL FOOTPRINT UNION V16 |",
            payload.get(
                "name",
                "",
            ),
            "| skipped=open_path_present",
            flush=True,
        )
        return payload

    z_value = float(
        payload.get(
            "base_z_cm",
            0.0,
        )
        or 0.0
    )

    rings = []

    for path_index, path in enumerate(
        paths
    ):
        if not isinstance(
            path,
            dict,
        ):
            continue

        coords = []

        for raw in list(
            path.get(
                "points",
                [],
            )
            or []
        ):
            try:
                coords.append(
                    (
                        float(
                            raw[0]
                        ),
                        float(
                            raw[1]
                        ),
                    )
                )
            except Exception:
                continue

        if len(
            coords
        ) < 3:
            continue

        # Remove duplicate closing coordinate if present.
        if (
            len(
                coords
            ) >= 2
            and abs(
                coords[0][0]
                - coords[-1][0]
            )
            <= 1.0e-9
            and abs(
                coords[0][1]
                - coords[-1][1]
            )
            <= 1.0e-9
        ):
            coords = coords[
                :-1
            ]

        if len(
            coords
        ) < 3:
            continue

        try:
            polygon = Polygon(
                coords
            )
        except Exception:
            continue

        if polygon.is_empty:
            continue

        if not polygon.is_valid:
            try:
                polygon = (
                    make_valid(
                        polygon
                    )
                    if make_valid is not None
                    else polygon.buffer(
                        0
                    )
                )
            except Exception:
                polygon = polygon.buffer(
                    0
                )

        polygon_parts = (
            _plan3d_wall_polygon_parts_v16(
                polygon
            )
        )

        # A canonical contour should remain one polygon.
        # If repair splits it, keep each valid part as an independent ring.
        for part in polygon_parts:
            if (
                part.is_empty
                or float(
                    part.area
                )
                <= 1.0e-10
            ):
                continue

            rings.append(
                {
                    "source_index":
                        int(
                            path_index
                        ),
                    "polygon":
                        part,
                    "area":
                        float(
                            part.area
                        ),
                }
            )

    if not rings:
        return payload

    # --------------------------------------------------------
    # Reconstruct hole nesting before union.
    #
    # Even containment depth = solid shell.
    # Odd containment depth  = hole.
    #
    # This preserves room voids while still allowing separate
    # overlapping wall solids to be unioned.
    # --------------------------------------------------------
    for row in rings:
        polygon = row[
            "polygon"
        ]

        depth = 0

        for other in rings:
            if other is row:
                continue

            if (
                other[
                    "area"
                ]
                <= row[
                    "area"
                ]
                + 1.0e-10
            ):
                continue

            try:
                contained = bool(
                    other[
                        "polygon"
                    ].covers(
                        polygon
                    )
                )
            except Exception:
                contained = False

            if contained:
                depth += 1

        row[
            "depth"
        ] = int(
            depth
        )

    shells = [
        row
        for row in rings
        if (
            row[
                "depth"
            ]
            % 2
        )
        == 0
    ]

    holes = [
        row
        for row in rings
        if (
            row[
                "depth"
            ]
            % 2
        )
        == 1
    ]

    solids = []

    for shell in shells:
        shell_poly = shell[
            "polygon"
        ]

        child_holes = []

        target_depth = (
            shell[
                "depth"
            ]
            + 1
        )

        for hole in holes:
            if hole[
                "depth"
            ] != target_depth:
                continue

            try:
                inside = bool(
                    shell_poly.covers(
                        hole[
                            "polygon"
                        ]
                    )
                )
            except Exception:
                inside = False

            if not inside:
                continue

            # Immediate child only. If another smaller even shell
            # contains this hole, it belongs there instead.
            immediate = True

            for nested_shell in shells:
                if (
                    nested_shell is shell
                    or nested_shell[
                        "depth"
                    ]
                    != target_depth - 1
                ):
                    continue

                if (
                    nested_shell[
                        "area"
                    ]
                    >= shell[
                        "area"
                    ]
                    - 1.0e-10
                ):
                    continue

                try:
                    if nested_shell[
                        "polygon"
                    ].covers(
                        hole[
                            "polygon"
                        ]
                    ):
                        immediate = False
                        break
                except Exception:
                    pass

            if immediate:
                child_holes.append(
                    list(
                        hole[
                            "polygon"
                        ].exterior.coords
                    )
                )

        try:
            solid = Polygon(
                list(
                    shell_poly.exterior.coords
                ),
                holes=child_holes,
            )
        except Exception:
            solid = shell_poly

        if not solid.is_valid:
            try:
                solid = (
                    make_valid(
                        solid
                    )
                    if make_valid is not None
                    else solid.buffer(
                        0
                    )
                )
            except Exception:
                solid = solid.buffer(
                    0
                )

        solids.extend(
            _plan3d_wall_polygon_parts_v16(
                solid
            )
        )

    if not solids:
        return payload

    try:
        merged = unary_union(
            solids
        )
    except Exception:
        return payload

    if not getattr(
        merged,
        "is_valid",
        True,
    ):
        try:
            merged = (
                make_valid(
                    merged
                )
                if make_valid is not None
                else merged.buffer(
                    0
                )
            )
        except Exception:
            merged = merged.buffer(
                0
            )

    merged_parts = (
        _plan3d_wall_polygon_parts_v16(
            merged
        )
    )

    if not merged_parts:
        return payload

    cleaned_paths = []

    def add_ring(
        coords,
    ):
        points2 = list(
            coords
        )

        if (
            len(
                points2
            ) >= 2
            and points2[0]
            == points2[-1]
        ):
            points2 = points2[
                :-1
            ]

        if len(
            points2
        ) < 3:
            return

        cleaned_paths.append(
            {
                "closed":
                    True,
                "points":
                    [
                        (
                            float(
                                x
                            ),
                            float(
                                y
                            ),
                            z_value,
                        )
                        for x, y
                        in points2
                    ],
            }
        )

    for polygon in merged_parts:
        add_ring(
            polygon.exterior.coords
        )

        for interior in polygon.interiors:
            add_ring(
                interior.coords
            )

    if not cleaned_paths:
        return payload

    before_count = len(
        paths
    )
    after_count = len(
        cleaned_paths
    )

    before_area = sum(
        float(
            solid.area
        )
        for solid in solids
    )

    after_area = sum(
        float(
            polygon.area
        )
        for polygon in merged_parts
    )

    result = dict(
        payload
    )

    result[
        "paths"
    ] = cleaned_paths
    result[
        "path_count"
    ] = int(
        after_count
    )

    report = dict(
        result.get(
            "topology_report",
            {},
        )
        or {}
    )

    report.update(
        {
            "wall_footprint_union_v16":
                True,
            "pre_union_contours":
                int(
                    before_count
                ),
            "post_union_contours":
                int(
                    after_count
                ),
            "pre_union_area_cm2":
                float(
                    before_area
                ),
            "post_union_area_cm2":
                float(
                    after_area
                ),
            "overlap_area_removed_cm2":
                float(
                    max(
                        0.0,
                        before_area
                        - after_area,
                    )
                ),
        }
    )

    result[
        "topology_report"
    ] = report

    print(
        "PLAN3D WALL FOOTPRINT UNION V16 |",
        result.get(
            "name",
            "",
        ),
        "| contours=",
        before_count,
        "->",
        after_count,
        "| overlap_removed_cm2=",
        format(
            max(
                0.0,
                before_area
                - after_area,
            ),
            ".3f",
        ),
        flush=True,
    )

    return result


def _plan3d_clean_floor_union_v16(
    viewport,
    floor_name,
    bounds,
    pivot,
    settings,
):
    payload = (
        _plan3d_clean_floor_before_union_v16(
            viewport,
            floor_name,
            bounds,
            pivot,
            settings,
        )
    )

    return (
        _plan3d_union_wall_footprint_v16(
            payload
        )
    )


_plan3d_canonical_v16._clean_floor = (
    _plan3d_clean_floor_union_v16
)

# ============================================================
# INTERIOR DOOR STRICT LOCAL BRIDGE
# Working final door MaxScript stage.
# ============================================================

_door_mxs_before_strict_local = _build_door_maxscript_vertex_weld

_PLAN3D_DOOR_STRICT_LOCAL_RESOLVER_V18 = 'fn PLAN3D_Door_ResolveBestPair ep obj jambA jambB targetZ expectedWidth =\n(\n    -- PLAN3D_INTERIOR_DOOR_STRICT_LOCAL_BRIDGE\n    local faceCount = ep.GetNumFaces node:obj\n\n    local openingVector = jambB - jambA\n    openingVector.z = 0.0\n\n    if (length openingVector) <= 0.000001 then\n        return #(false,0,0,0,0,0,0,0,0,0,0,0,"zero-opening-vector","strict-local-v18")\n\n    local openingDirection = normalize openingVector\n    local zTolerance = units.decodeValue "1cm"\n    local minUpperHeight = units.decodeValue "2cm"\n    local localJambRadius = units.decodeValue "20cm"\n\n    local candidatesA = #()\n    local candidatesB = #()\n\n    for faceIndex = 1 to faceCount do\n    (\n        local info = PLAN3D_Door_GetFaceInfo ep obj faceIndex\n\n        if info != undefined do\n        (\n            local centerValue = info[1]\n            local minZ = info[2]\n            local maxZ = info[3]\n            local normalValue = info[4]\n\n            local startsAtHeader = (abs (minZ - targetZ)) <= zTolerance\n            local reachesAbove = maxZ > (targetZ + minUpperHeight)\n            local verticalFace = (abs normalValue.z) < 0.25\n\n            if startsAtHeader and reachesAbove and verticalFace do\n            (\n                local axisAlignment = abs (dot normalValue openingDirection)\n\n                if axisAlignment >= 0.90 do\n                (\n                    local dA = distance [centerValue.x,centerValue.y,0] [jambA.x,jambA.y,0]\n                    local dB = distance [centerValue.x,centerValue.y,0] [jambB.x,jambB.y,0]\n\n                    if dA <= localJambRadius do\n                        append candidatesA #(faceIndex,dA,info,axisAlignment)\n\n                    if dB <= localJambRadius do\n                        append candidatesB #(faceIndex,dB,info,axisAlignment)\n                )\n            )\n        )\n    )\n\n    if candidatesA.count <= 0 or candidatesB.count <= 0 then\n    (\n        format "PLAN3D DOOR STRICT FAIL | % | missing-local-face | candA=% candB=% | width=%\\n" obj.name candidatesA.count candidatesB.count expectedWidth\n        return #(false,0,0,0,0,0,0,0,0,0,candidatesA.count,candidatesB.count,"missing-local-face","strict-local-v18")\n    )\n\n    local bestFaceA = 0\n    local bestFaceB = 0\n    local bestDistanceA = 0.0\n    local bestDistanceB = 0.0\n    local bestPairDistance = 0.0\n    local bestWidthRatio = 0.0\n    local bestParallel = 0.0\n    local bestAlignA = 0.0\n    local bestAlignB = 0.0\n    local bestScore = 1.0e30\n\n    for candidateA in candidatesA do\n    (\n        for candidateB in candidatesB do\n        (\n            local faceA = candidateA[1]\n            local faceB = candidateB[1]\n\n            if faceA != faceB do\n            (\n                local infoA = candidateA[3]\n                local infoB = candidateB[3]\n                local centerA = infoA[1]\n                local centerB = infoB[1]\n                local normalA = infoA[4]\n                local normalB = infoB[4]\n\n                local pairVector = centerB - centerA\n                pairVector.z = 0.0\n\n                local pairDistance = length pairVector\n\n                if pairDistance > 0.000001 do\n                (\n                    local widthRatio = pairDistance / expectedWidth\n                    local normalParallel = abs (dot normalA normalB)\n\n                    local widthOK = (widthRatio >= 0.75) and (widthRatio <= 1.25)\n                    local parallelOK = normalParallel >= 0.90\n\n                    if widthOK and parallelOK do\n                    (\n                        local widthError = abs (pairDistance - expectedWidth)\n                        local score = candidateA[2] + candidateB[2] + widthError\n\n                        if score < bestScore do\n                        (\n                            bestScore = score\n                            bestFaceA = faceA\n                            bestFaceB = faceB\n                            bestDistanceA = candidateA[2]\n                            bestDistanceB = candidateB[2]\n                            bestPairDistance = pairDistance\n                            bestWidthRatio = widthRatio\n                            bestParallel = normalParallel\n                            bestAlignA = candidateA[4]\n                            bestAlignB = candidateB[4]\n                        )\n                    )\n                )\n            )\n        )\n    )\n\n    if bestFaceA <= 0 or bestFaceB <= 0 then\n    (\n        format "PLAN3D DOOR STRICT FAIL | % | no-exact-local-pair | candA=% candB=% | width=%\\n" obj.name candidatesA.count candidatesB.count expectedWidth\n        return #(false,0,0,0,0,0,0,0,0,0,candidatesA.count,candidatesB.count,"no-exact-local-pair","strict-local-v18")\n    )\n\n    format "PLAN3D DOOR STRICT PAIR | % | faces=%<->% | dA=% | dB=% | pairWidth=% | expected=%\\n" obj.name bestFaceA bestFaceB bestDistanceA bestDistanceB bestPairDistance expectedWidth\n\n    #(true,bestFaceA,bestFaceB,bestDistanceA,bestDistanceB,bestPairDistance,bestWidthRatio,bestParallel,bestAlignA,bestAlignB,candidatesA.count,candidatesB.count,"ok","strict-local-v18")\n)\n'


def _build_interior_door_maxscript(door_floors):
    script = _door_mxs_before_strict_local(
        door_floors
    )

    start_token = (
        "fn PLAN3D_Door_ResolveBestPair ep obj jambA jambB targetZ expectedWidth ="
    )
    end_token = (
        "fn PLAN3D_Door_ProcessFloor obj doorHeightCm baseZCm doorRows ="
    )

    start = script.find(start_token)
    end = script.find(end_token)

    if start < 0 or end < 0 or end <= start:
        raise RuntimeError(
            "Interior Door Strict Local: resolver function span not found."
        )

    return (
        script[:start]
        + _PLAN3D_DOOR_STRICT_LOCAL_RESOLVER_V18.strip()
        + "\n\n"
        + script[end:]
    )


# ============================================================

def _plan3d_ground_window_maxscript(
    window_floors,
):
    lines = [
        "",
        "-- PLAN3D_GROUND_WINDOW_EXPORT",
        "",
        "fn PLAN3D_Window_GetFaceInfo ep obj faceIndex =",
        "(",
        "    local degree = ep.GetFaceDegree faceIndex node:obj",
        "    if degree < 3 then return undefined",
        "    local points = #()",
        "    local center = [0,0,0]",
        "    local minZ = 1.0e30",
        "    local maxZ = -1.0e30",
        "    for k = 1 to degree do",
        "    (",
        "        local vi = ep.GetFaceVertex faceIndex k node:obj",
        "        if vi <= 0 then return undefined",
        "        local p = ep.GetVertex vi node:obj",
        "        append points p",
        "        center += p",
        "        if p.z < minZ do minZ = p.z",
        "        if p.z > maxZ do maxZ = p.z",
        "    )",
        "    center /= degree",
        "    local nrm = [0,0,0]",
        "    for k = 2 to (degree-1) while (length nrm) <= 0.000001 do",
        "    (",
        "        local a = points[k] - points[1]",
        "        local b = points[k+1] - points[1]",
        "        local n = cross a b",
        "        if (length n) > 0.000001 do nrm = normalize n",
        "    )",
        "    #(points, center, minZ, maxZ, nrm)",
        ")",
        "",
        "fn PLAN3D_Window_EnsureLevel ep obj targetZ =",
        "(",
        "    local edgeCountBefore = ep.GetNumEdges node:obj",
        "    local verticalEdges = #{}",
        "    local zTol = units.decodeValue \"0.5mm\"",
        "    local xyTol = units.decodeValue \"0.01mm\"",
        "    for edgeIndex = 1 to edgeCountBefore do",
        "    (",
        "        local va = ep.GetEdgeVertex edgeIndex 1 node:obj",
        "        local vb = ep.GetEdgeVertex edgeIndex 2 node:obj",
        "        if (va > 0) and (vb > 0) do",
        "        (",
        "            local pa = ep.GetVertex va node:obj",
        "            local pb = ep.GetVertex vb node:obj",
        "            local dx = abs(pb.x-pa.x)",
        "            local dy = abs(pb.y-pa.y)",
        "            local z0 = amin pa.z pb.z",
        "            local z1 = amax pa.z pb.z",
        "            if (dx <= xyTol) and (dy <= xyTol) and (targetZ > (z0+zTol)) and (targetZ < (z1-zTol)) do verticalEdges[edgeIndex] = true",
        "        )",
        "    )",
        "    if verticalEdges.numberSet <= 0 then",
        "    (",
        "        format \"PLAN3D WINDOW LEVEL EXISTS/SKIP | % | Z=%\\n\" obj.name targetZ",
        "        return true",
        "    )",
        "    ep.SetEPolySelLevel #Edge",
        "    subObjectLevel = 2",
        "    local clearEdges = #{}",
        "    ep.SetSelection #Edge &clearEdges node:obj",
        "    ep.SetSelection #Edge &verticalEdges node:obj",
        "    ep.connectEdgeSegments = 1",
        "    ep.connectEdgePinch = 0",
        "    ep.connectEdgeSlide = 0",
        "    ep.ButtonOp #ConnectEdges",
        "    ep.RefreshScreen()",
        "    completeRedraw()",
        "    local edgeCountAfter = ep.GetNumEdges node:obj",
        "    if edgeCountAfter <= edgeCountBefore then",
        "    (",
        "        format \"PLAN3D WINDOW LEVEL ERROR | % | Connect created no edges | Z=%\\n\" obj.name targetZ",
        "        return false",
        "    )",
        "    local newHorizontal = #{}",
        "    local firstEdge = 0",
        "    for edgeIndex = (edgeCountBefore+1) to edgeCountAfter do",
        "    (",
        "        local va = ep.GetEdgeVertex edgeIndex 1 node:obj",
        "        local vb = ep.GetEdgeVertex edgeIndex 2 node:obj",
        "        if (va > 0) and (vb > 0) do",
        "        (",
        "            local pa = ep.GetVertex va node:obj",
        "            local pb = ep.GetVertex vb node:obj",
        "            if (abs(pb.z-pa.z) <= zTol) do",
        "            (",
        "                newHorizontal[edgeIndex] = true",
        "                if firstEdge == 0 do firstEdge = edgeIndex",
        "            )",
        "        )",
        "    )",
        "    if firstEdge <= 0 then",
        "    (",
        "        format \"PLAN3D WINDOW LEVEL ERROR | % | new horizontal edges not found | Z=%\\n\" obj.name targetZ",
        "        return false",
        "    )",
        "    local fv = ep.GetEdgeVertex firstEdge 1 node:obj",
        "    local fp = ep.GetVertex fv node:obj",
        "    local deltaZ = targetZ - fp.z",
        "    ep.SetSelection #Edge &clearEdges node:obj",
        "    ep.SetSelection #Edge &newHorizontal node:obj",
        "    ep.useSoftSel = false",
        "    ep.SetOperation #Transform",
        "    ep.MoveSelection [0,0,deltaZ]",
        "    ep.Commit()",
        "    ep.RefreshScreen()",
        "    completeRedraw()",
        "    format \"PLAN3D WINDOW LEVEL CONNECTED | % | Z=% | vertical=% | newEdges=%\\n\" obj.name targetZ verticalEdges.numberSet newHorizontal.numberSet",
        "    true",
        ")",
        "",
        "fn PLAN3D_Window_ResolveBandFaces ep obj jambA jambB sillZ topZ expectedWidth =",
        "(",
        "    local axis = jambB - jambA",
        "    axis.z = 0",
        "    if (length axis) <= 0.000001 then return #(false,0,0,0,\"zero-axis\")",
        "    axis = normalize axis",
        "    local normalAxis = normalize (cross [0,0,1] axis)",
        "    local centerXY = (jambA + jambB) * 0.5",
        "    centerXY.z = 0",
        "    local halfWidth = expectedWidth * 0.5",
        "    local zTol = units.decodeValue \"1cm\"",
        "    local spanTol = units.decodeValue \"5cm\"",
        "    local acrossTol = units.decodeValue \"2cm\"",
        "    local candidates = #()",
        "    local faceCount = ep.GetNumFaces node:obj",
        "    for faceIndex = 1 to faceCount do",
        "    (",
        "        local info = PLAN3D_Window_GetFaceInfo ep obj faceIndex",
        "        if info != undefined do",
        "        (",
        "            local pts = info[1]",
        "            local center = info[2]",
        "            local minZ = info[3]",
        "            local maxZ = info[4]",
        "            local nrm = info[5]",
        "            local vertical = (abs nrm.z) < 0.25",
        "            local zOK = (abs(minZ-sillZ) <= zTol) and (abs(maxZ-topZ) <= zTol)",
        "            local normalOK = abs(dot nrm normalAxis) >= 0.90",
        "            if vertical and zOK and normalOK do",
        "            (",
        "                local minAlong = 1.0e30",
        "                local maxAlong = -1.0e30",
        "                local minAcross = 1.0e30",
        "                local maxAcross = -1.0e30",
        "                for p in pts do",
        "                (",
        "                    local rel = p - centerXY",
        "                    rel.z = 0",
        "                    local along = dot rel axis",
        "                    local across = dot rel normalAxis",
        "                    if along < minAlong do minAlong = along",
        "                    if along > maxAlong do maxAlong = along",
        "                    if across < minAcross do minAcross = across",
        "                    if across > maxAcross do maxAcross = across",
        "                )",
        "                local alongOK = (abs(minAlong + halfWidth) <= spanTol) and (abs(maxAlong - halfWidth) <= spanTol)",
        "                local planar = (maxAcross-minAcross) <= acrossTol",
        "                if alongOK and planar do",
        "                (",
        "                    local relC = center - centerXY",
        "                    relC.z = 0",
        "                    local acrossCenter = dot relC normalAxis",
        "                    append candidates #(faceIndex,acrossCenter,nrm)",
        "                )",
        "            )",
        "        )",
        "    )",
        "    local bestA = 0",
        "    local bestB = 0",
        "    local bestSep = 0.0",
        "    local bestScore = 1.0e30",
        "    if candidates.count >= 2 do",
        "    (",
        "        for i = 1 to (candidates.count-1) do",
        "        (",
        "            for j = (i+1) to candidates.count do",
        "            (",
        "                local a = candidates[i]",
        "                local b = candidates[j]",
        "                local oppositeSides = (a[2]*b[2]) < 0.0",
        "                local parallel = abs(dot a[3] b[3])",
        "                local sep = abs(a[2]-b[2])",
        "                local sepOK = (sep >= units.decodeValue \"5cm\") and (sep <= units.decodeValue \"60cm\")",
        "                if oppositeSides and (parallel >= 0.95) and sepOK do",
        "                (",
        "                    local score = (1.0-parallel)*100.0 - sep",
        "                    if score < bestScore do",
        "                    (",
        "                        bestScore = score",
        "                        bestA = a[1]",
        "                        bestB = b[1]",
        "                        bestSep = sep",
        "                    )",
        "                )",
        "            )",
        "        )",
        "    )",
        "    if bestA <= 0 or bestB <= 0 then return #(false,0,0,candidates.count,\"no-band-face-pair\")",
        "    #(true,bestA,bestB,candidates.count,bestSep)",
        ")",
        "",
        "fn PLAN3D_Window_ProcessFloor obj baseZCm windowRows levelRows =",
        "(",
        "    if obj == undefined then return false",
        "    if windowRows.count <= 0 then return true",
        "    local ep = Edit_Poly()",
        "    ep.name = \"Window Openings\"",
        "    addModifier obj ep",
        "    max modify mode",
        "    select obj",
        "    ep.SetPrimaryNode obj",
        "    modPanel.setCurrentObject ep",
        "    for levelCm in levelRows do",
        "    (",
        "        local absZ = (baseZCm + levelCm) * (units.decodeValue \"1cm\")",
        "        PLAN3D_Window_EnsureLevel ep obj absZ",
        "    )",
        "    ep.SetEPolySelLevel #Face",
        "    subObjectLevel = 4",
        "    local bridged = 0",
        "    local skipped = 0",
        "    for w = 1 to windowRows.count do",
        "    (",
        "        local r = windowRows[w]",
        "        local jambA = [r[1]*(units.decodeValue \"1cm\"), r[2]*(units.decodeValue \"1cm\"), 0]",
        "        local jambB = [r[3]*(units.decodeValue \"1cm\"), r[4]*(units.decodeValue \"1cm\"), 0]",
        "        local expectedWidth = r[5]*(units.decodeValue \"1cm\")",
        "        local sillZ = (baseZCm + r[6])*(units.decodeValue \"1cm\")",
        "        local topZ = (baseZCm + r[7])*(units.decodeValue \"1cm\")",
        "        local pair = PLAN3D_Window_ResolveBandFaces ep obj jambA jambB sillZ topZ expectedWidth",
        "        if pair[1] == true then",
        "        (",
        "            ep.BridgePolygons pair[2] pair[3] node:obj",
        "            ep.Commit()",
        "            ep.RefreshScreen()",
        "            completeRedraw()",
        "            bridged += 1",
        "            format \"PLAN3D WINDOW BRIDGED | % | window=% | faces=%<->% | sill=% cm | top=% cm | height=% cm\\n\" obj.name w pair[2] pair[3] r[6] r[7] (r[7]-r[6])",
        "        )",
        "        else",
        "        (",
        "            skipped += 1",
        "            format \"PLAN3D WINDOW SKIP | % | window=% | candidates=% | reason=% | sill=% | top=%\\n\" obj.name w pair[4] pair[5] r[6] r[7]",
        "        )",
        "    )",
        "    format \"PLAN3D WINDOW COMPLETE | % | windows=% | bridged=% | skipped=% | levels=%\\n\" obj.name windowRows.count bridged skipped levelRows.count",
        "    true",
        ")",
        "",
        "undo \"Plan3D Windows\" on (",
    ]

    for floor in window_floors:
        if not floor.get(
            "windows"
        ):
            continue

        safe = str(
            floor.get(
                "safe_name",
                floor.get(
                    "name",
                    "Floor",
                ),
            )
        )

        safe = "".join(
            ch
            if (
                ch.isalnum()
                or ch == "_"
            )
            else "_"
            for ch in safe
        ).strip(
            "_"
        ) or "Floor"

        object_name = (
            "PLAN3D_WALL_"
            + safe
        )

        rows = []

        levels = set()

        for window in floor[
            "windows"
        ]:
            a = window[
                "jamb_a_cm"
            ]
            b = window[
                "jamb_b_cm"
            ]
            width = float(
                window[
                    "width_cm"
                ]
            )
            sill = float(
                window[
                    "sill_cm"
                ]
            )
            top = float(
                window[
                    "top_cm"
                ]
            )

            levels.add(
                round(
                    sill,
                    6,
                )
            )
            levels.add(
                round(
                    top,
                    6,
                )
            )

            rows.append(
                "#("
                + ",".join(
                    format(
                        float(v),
                        ".12g",
                    )
                    for v in (
                        a[0],
                        a[1],
                        b[0],
                        b[1],
                        width,
                        sill,
                        top,
                    )
                )
                + ")"
            )

        level_expr = (
            "#("
            + ",".join(
                format(
                    float(value),
                    ".12g",
                )
                for value in sorted(
                    levels
                )
            )
            + ")"
        )

        row_expr = (
            "#("
            + ",".join(
                rows
            )
            + ")"
        )

        base_z = float(
            floor.get(
                "base_z_cm",
                0.0,
            )
            or 0.0
        )

        lines.extend(
            [
                (
                    '    local PLAN3D_WINDOW_OBJ = getNodeByName "'
                    + object_name.replace(
                        '"',
                        '\\"',
                    )
                    + '" exact:true'
                ),
                "    if PLAN3D_WINDOW_OBJ != undefined do",
                "    (",
                (
                    "        local PLAN3D_WINDOW_ROWS = "
                    + row_expr
                ),
                (
                    "        local PLAN3D_WINDOW_LEVELS = "
                    + level_expr
                ),
                (
                    "        PLAN3D_Window_ProcessFloor PLAN3D_WINDOW_OBJ "
                    + format(
                        base_z,
                        ".12g",
                    )
                    + " PLAN3D_WINDOW_ROWS PLAN3D_WINDOW_LEVELS"
                ),
                "    )",
            ]
        )

    lines.extend(
        [
            "    completeRedraw()",
            ")",
            "",
        ]
    )

    return "\n".join(
        lines
    ) + "\n"


# ============================================================
# GROUND FLOOR WINDOW EXPORT
#
# Uses only:
# - Ground V33 physical window contacts from the plan,
# - Ground facade window heights from ground_openings,
# - the already-computed facade/plan side mapping.
# No legacy height cache and no facade reanalysis during export.
# ============================================================

_plan3d_prepare_before_ground_window_export = _prepare_wall_with_interior_doors


def _ground_rect(values):
    x, y, w, h = [float(value) for value in values]
    return min(x, x + w), min(y, y + h), max(x, x + w), max(y, y + h)


def _collect_ground_physical_windows(
    viewport,
    floor_name,
    rect_values,
    pivot,
    settings,
    units_info,
):
    from floor_area_runtime import (
        _require_shapely,
        _export_prepared_wall_paths,
        _window_paths_in_floor,
        _resolve_windows_v33,
    )

    source_to_mm = float(units_info.get("to_cm", 1.0) or 1.0) * 10.0
    api = _require_shapely()

    wall_paths, _topology, export_floor = _export_prepared_wall_paths(
        viewport,
        floor_name,
        rect_values,
        pivot,
        settings,
        units_info,
    )
    window_paths = _window_paths_in_floor(viewport, rect_values)
    _closures, _footprint, window_meta, window_stats = _resolve_windows_v33(
        window_paths,
        wall_paths,
        source_to_mm,
        api,
    )

    x0, y0, x1, y1 = _ground_rect(rect_values)
    cx_plan = (x0 + x1) * 0.5
    cy_plan = (y0 + y1) * 0.5
    plan_w = max(x1 - x0, 1.0e-9)
    plan_h = max(y1 - y0, 1.0e-9)

    cad_to_cm = float(
        export_floor.get("cad_to_cm", units_info.get("to_cm", 1.0)) or 1.0
    )
    pivot_x = float(export_floor.get("pivot_x", pivot.get("pivot_x", 0.0)) or 0.0)
    pivot_y = float(export_floor.get("pivot_y", pivot.get("pivot_y", 0.0)) or 0.0)

    rows = []
    for meta_index, meta in enumerate(list(window_meta or [])):
        if not isinstance(meta, dict):
            continue
        try:
            A1 = (float(meta["A1"][0]), float(meta["A1"][1]))
            A2 = (float(meta["A2"][0]), float(meta["A2"][1]))
            B1 = (float(meta["B1"][0]), float(meta["B1"][1]))
            B2 = (float(meta["B2"][0]), float(meta["B2"][1]))
        except Exception:
            continue

        ax = (A1[0] + A2[0]) * 0.5
        ay = (A1[1] + A2[1]) * 0.5
        bx = (B1[0] + B2[0]) * 0.5
        by = (B1[1] + B2[1]) * 0.5
        cx = (ax + bx) * 0.5
        cy = (ay + by) * 0.5
        dx = bx - ax
        dy = by - ay

        if abs(dx) >= abs(dy):
            side = "bottom" if cy <= cy_plan else "top"
            pos = (cx - x0) / plan_w
        else:
            side = "left" if cx <= cx_plan else "right"
            pos = (cy - y0) / plan_h

        rows.append({
            "meta_index": meta_index,
            "side": side,
            "pos": max(0.0, min(1.0, float(pos))),
            "jamb_a_cm": [(ax - pivot_x) * cad_to_cm, (ay - pivot_y) * cad_to_cm],
            "jamb_b_cm": [(bx - pivot_x) * cad_to_cm, (by - pivot_y) * cad_to_cm],
        })

    return rows, dict(window_stats or {}), export_floor


def _ground_facade_windows(panel, facade_assignments):
    store = getattr(panel, "_analysis_results", {})
    ground = store.get("ground_openings", {}) if isinstance(store, dict) else {}
    facades = dict(ground.get("facades", {}) or {}) if isinstance(ground, dict) else {}

    output = {}
    for facade_name, rect_values in facade_assignments.items():
        x0, _y0, x1, _y1 = _ground_rect(rect_values)
        width = max(x1 - x0, 1.0e-9)
        rows = []

        facade_payload = dict(facades.get(str(facade_name), {}) or {})
        for window in list(facade_payload.get("windows", []) or []):
            if not isinstance(window, dict):
                continue
            try:
                cx = float(window["center"][0])
                sill = float(window["floor_local_sill_cm"])
                top = float(window["floor_local_top_cm"])
            except Exception:
                continue

            if top <= sill:
                continue

            rows.append({
                "pos": max(0.0, min(1.0, (cx - x0) / width)),
                "sill_cm": sill,
                "top_cm": top,
                "height_cm": float(window.get("height_cm", top - sill)),
                "source": window,
            })

        rows.sort(key=lambda row: row["pos"])
        output[str(facade_name)] = rows

    return output


def _ground_side_mapping(panel, floor_name):
    store = getattr(panel, "_analysis_results", {})
    if not isinstance(store, dict):
        store = {}

    match = dict(store.get("facade_plan_matching_v20r", {}) or {})
    floor_data = dict(dict(match.get("floors", {}) or {}).get(floor_name, {}) or {})
    sides = dict(floor_data.get("sides", {}) or {})

    mapping = {}
    side_name_map = {
        "bottom": "Front",
        "right": "Right",
        "top": "Rear",
        "left": "Left",
    }

    # V20R stores named plan sides. Use its actual facade_assignment when present.
    for physical_side, plan_side_name in side_name_map.items():
        payload = dict(sides.get(plan_side_name, {}) or {})
        facade_name = payload.get("facade_assignment")
        if not facade_name:
            facade_name = plan_side_name
        mapping[physical_side] = str(facade_name)

    return mapping


def _collect_ground_windows(panel, wall_floors):
    from plan3d_canonical_export import _cad_unit_info

    page = panel.parentWidget()
    viewport = getattr(page, "viewport", None) if page is not None else None
    if viewport is None:
        raise RuntimeError("Ground window export: viewport unavailable.")

    store = getattr(panel, "_analysis_results", {})
    ground = store.get("ground_openings", {}) if isinstance(store, dict) else {}
    if not isinstance(ground, dict) or not ground:
        raise RuntimeError("Run Facade Analysis before Create 3D Model.")

    floor_name = str(ground.get("ground_floor_name", "") or "")
    assignments = dict(getattr(panel, "_assignments", {}) or {})
    floor_assignments = dict(assignments.get("floor_plans", {}) or {})
    facade_assignments = dict(assignments.get("facades", {}) or {})
    settings_map = dict(getattr(panel, "_floor_settings", {}) or {})
    pivot_map = dict(getattr(panel, "_floor_pivots", {}) or {})

    rect_values = floor_assignments.get(floor_name)
    if rect_values is None:
        raise RuntimeError("Ground floor plan assignment is unavailable.")

    wall_floor = next(
        (
            row
            for row in list(wall_floors or [])
            if isinstance(row, dict) and str(row.get("name", "")) == floor_name
        ),
        None,
    )
    if not isinstance(wall_floor, dict):
        raise RuntimeError("Ground wall export payload is unavailable.")

    pivot = dict(pivot_map.get(floor_name, {}) or {})
    pivot.setdefault("pivot_x", float(wall_floor.get("pivot_x", 0.0) or 0.0))
    pivot.setdefault("pivot_y", float(wall_floor.get("pivot_y", 0.0) or 0.0))
    settings = dict(settings_map.get(floor_name, {}) or {})
    units_info = _cad_unit_info(viewport)

    physical, stats, export_floor = _collect_ground_physical_windows(
        viewport,
        floor_name,
        rect_values,
        pivot,
        settings,
        units_info,
    )
    signature = _ground_facade_windows(panel, facade_assignments)
    mapping = _ground_side_mapping(panel, floor_name)

    mapped = []
    summary = {}
    warnings = []

    for side in ("bottom", "top", "left", "right"):
        physical_rows = sorted(
            [row for row in physical if row["side"] == side],
            key=lambda row: row["pos"],
        )
        facade_name = mapping.get(side)
        facade_rows = sorted(
            list(signature.get(facade_name, []) or []),
            key=lambda row: row["pos"],
        )

        summary[side] = {
            "facade": facade_name,
            "physical": len(physical_rows),
            "facade_windows": len(facade_rows),
        }

        if len(physical_rows) != len(facade_rows):
            warnings.append(
                side
                + ": physical="
                + str(len(physical_rows))
                + " facade="
                + str(len(facade_rows))
            )

        pair_count = min(len(physical_rows), len(facade_rows))
        for index in range(pair_count):
            geom = physical_rows[index]
            height = facade_rows[index]
            sill = float(height["sill_cm"])
            top = float(height["top_cm"])

            if sill < -2.0 or top <= sill:
                warnings.append(
                    side
                    + "["
                    + str(index)
                    + "]: invalid height sill="
                    + str(sill)
                    + " top="
                    + str(top)
                )
                continue

            a = list(geom["jamb_a_cm"])
            b = list(geom["jamb_b_cm"])
            width = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5

            mapped.append({
                "window_id": "W" + str(len(mapped) + 1).zfill(3),
                "jamb_a_cm": a,
                "jamb_b_cm": b,
                "width_cm": float(width),
                "sill_cm": max(0.0, sill),
                "top_cm": top,
                "height_cm": float(height["height_cm"]),
                "facade": facade_name,
                "plan_side": side,
                "source": "GROUND_OPENING_PIPELINE",
            })

    if not mapped:
        raise RuntimeError(
            "Ground window export: no physical/facade window pairs were mapped. "
            + repr(summary)
        )

    if warnings:
        print(
            "PLAN3D GROUND WINDOW WARNING |",
            " ; ".join(warnings),
            flush=True,
        )

    payload = {
        "name": floor_name,
        "safe_name": str(wall_floor.get("safe_name", floor_name)),
        "base_z_cm": float(wall_floor.get("base_z_cm", 0.0) or 0.0),
        "window_count": len(mapped),
        "windows": mapped,
        "physical_count": len(physical),
        "resolver_stats": stats,
        "mapping_summary": summary,
        "warnings": warnings,
    }

    print(
        "PLAN3D GROUND WINDOW MAP COMPLETE |",
        "floor=",
        floor_name,
        "| physical=",
        len(physical),
        "| mapped=",
        len(mapped),
        "| sides=",
        summary,
        flush=True,
    )
    return [payload]


def _append_ground_opening_metadata(pending_path, panel, wall_floors):
    import json
    import base64

    store = getattr(panel, "_analysis_results", {})
    ground = store.get("ground_openings", {}) if isinstance(store, dict) else {}
    if not isinstance(ground, dict) or not ground:
        return

    floor_name = str(ground.get("ground_floor_name", "") or "")
    wall_floor = next(
        (
            row
            for row in list(wall_floors or [])
            if isinstance(row, dict) and str(row.get("name", "")) == floor_name
        ),
        {},
    )
    safe_name = str(wall_floor.get("safe_name", floor_name.replace(" ", "_")))
    object_name = "PLAN3D_WALL_" + safe_name

    payload = {
        "ground_floor_name": floor_name,
        "datum_source": ground.get("datum_source"),
        "datum_y": ground.get("datum_y"),
        "wall_height_cm": ground.get("wall_height_cm"),
        "facades": ground.get("facades", {}),
        "totals": ground.get("totals", {}),
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    encoded = base64.b64encode(raw.encode("utf-8")).decode("ascii")
    obj = object_name.replace('"', '\\"')

    lines = [
        "",
        "-- PLAN3D_GROUND_OPENING_METADATA",
        "try",
        "(",
        '    local obj = getNodeByName "' + obj + '" exact:true',
        "    if obj != undefined do",
        "    (",
        '        setUserProp obj "PLAN3D_GROUND_OPENINGS_JSON_B64" "' + encoded + '"',
        '        format "PLAN3D GROUND OPENING METADATA OK | %\\n" obj.name',
        "    )",
        ")",
        "catch",
        "(",
        '    format "PLAN3D GROUND OPENING METADATA ERROR | %\\n" (getCurrentException())',
        ")",
        "",
    ]

    pending = Path(pending_path)
    current = pending.read_text(encoding="utf-8") if pending.exists() else ""
    pending.write_text(current.rstrip() + "\n" + "\n".join(lines), encoding="utf-8")


def prepare_wall_only_transfer(panel):
    result = _plan3d_prepare_before_ground_window_export(panel)
    if not isinstance(result, dict):
        raise RuntimeError("Ground window export: previous export result invalid.")

    wall_floors = list(result.get("floors", []) or [])
    window_floors = _collect_ground_windows(panel, wall_floors)

    pending_value = result.get("pending_script") or result.get("pending_path")
    pending = (
        Path(pending_value)
        if pending_value
        else Path(__file__).resolve().parents[2] / "runtime" / "max_bridge" / "pending.ms"
    )
    pending.parent.mkdir(parents=True, exist_ok=True)

    runtime = _plan3d_ground_window_maxscript(window_floors)
    current = pending.read_text(encoding="utf-8") if pending.exists() else ""
    pending.write_text(current.rstrip() + "\n" + runtime, encoding="utf-8")
    _append_ground_opening_metadata(pending, panel, wall_floors)

    result["pending_script"] = str(pending)
    result["pending_path"] = str(pending)
    result["window_floors"] = window_floors
    result["window_count"] = sum(
        int(row.get("window_count", 0) or 0)
        for row in window_floors
    )
    result["window_export_engine"] = "GROUND_WINDOW_EXPORT"

    print(
        "PLAN3D GROUND WINDOW EXPORT PREPARED |",
        "floors=1 | windows=",
        result["window_count"],
        "| scope=GROUND_ONLY",
        flush=True,
    )
    return result


print(
    "PLAN3D GROUND WINDOW EXPORT ACTIVE | "
    "floors=GROUND_ONLY | legacy_window_pipeline=REMOVED"
)

