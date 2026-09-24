from __future__ import annotations

import math

from collections import Counter
from pathlib import Path

import ezdxf
import pythoncom
import win32com.client

from ezdxf import bbox
from ezdxf.path import make_path


SUPPORTED_PATH_TYPES = {
    "LINE",
    "LWPOLYLINE",
    "POLYLINE",
    "ARC",
    "CIRCLE",
    "ELLIPSE",
    "SPLINE",
}


# ============================================================
# DXF/DWG INSUNITS -> physical millimeters
# ============================================================

INSUNITS_TABLE = {
    1: ("in", "Inches", 25.4),
    2: ("ft", "Feet", 304.8),
    3: ("mi", "Miles", 1609344.0),
    4: ("mm", "Millimeters", 1.0),
    5: ("cm", "Centimeters", 10.0),
    6: ("m", "Meters", 1000.0),
    7: ("km", "Kilometers", 1000000.0),
    8: ("microin", "Microinches", 0.0000254),
    9: ("mil", "Mils", 0.0254),
    10: ("yd", "Yards", 914.4),
    12: ("nm", "Nanometers", 0.000001),
    13: ("um", "Microns", 0.001),
    14: ("dm", "Decimeters", 100.0),
    15: ("dam", "Decameters", 10000.0),
    16: ("hm", "Hectometers", 100000.0),
}


def _cad_unit_info(
    doc,
) -> dict:
    try:
        code = int(
            doc.header.get(
                "$INSUNITS",
                0,
            )
            or 0
        )
    except Exception:
        code = 0

    try:
        measurement = int(
            doc.header.get(
                "$MEASUREMENT",
                1,
            )
            or 0
        )
    except Exception:
        measurement = 1

    known = INSUNITS_TABLE.get(
        code
    )

    if known is not None:
        token, name, to_mm = known

        return {
            "source_unit_code": code,
            "source_unit_token": token,
            "source_unit_name": name,
            "source_to_mm": float(
                to_mm
            ),
            "source_unit_confidence": "explicit_insunits",
            "measurement": measurement,
        }

    # --------------------------------------------------------
    # Unitless CAD cannot contain enough information to prove
    # its physical scale mathematically.
    #
    # Use AutoCAD's METRIC/ENGLISH measurement convention as a
    # deterministic fallback, not a drawing-specific rule.
    # --------------------------------------------------------

    if measurement == 0:
        token = "in"
        name = "Inches"
        to_mm = 25.4
        confidence = "measurement_fallback"
    else:
        token = "mm"
        name = "Millimeters"
        to_mm = 1.0
        confidence = "measurement_fallback"

    return {
        "source_unit_code": code,
        "source_unit_token": token,
        "source_unit_name": name,
        "source_to_mm": float(
            to_mm
        ),
        "source_unit_confidence": confidence,
        "measurement": measurement,
    }


def _open_autocad():
    errors = []

    for prog_id in (
        "AutoCAD.Application.24.1",
        "AutoCAD.Application",
    ):
        try:
            app = win32com.client.DispatchEx(
                prog_id
            )

            app.Visible = False

            return app

        except Exception as exc:
            errors.append(
                f"{prog_id}: {exc}"
            )

    raise RuntimeError(
        "AutoCAD COM acilamadi: "
        + " | ".join(
            errors
        )
    )


def _dwg_to_dxf(
    source: Path,
    output: Path,
) -> None:
    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    pythoncom.CoInitialize()

    acad = None
    doc = None

    try:
        acad = _open_autocad()

        doc = acad.Documents.Open(
            str(source),
            True,
        )

        if output.exists():
            output.unlink()

        # AutoCAD 2022:
        # ac2018_dxf = 65
        doc.SaveAs(
            str(output),
            65,
        )

    finally:
        if doc is not None:
            try:
                doc.Close(
                    False
                )
            except Exception:
                pass

        if acad is not None:
            try:
                acad.Quit()
            except Exception:
                pass

        pythoncom.CoUninitialize()

    if not output.exists():
        raise RuntimeError(
            f"DXF olusturulamadi: {output}"
        )


def ensure_dxf(
    source: Path,
    cache_dir: Path,
) -> Path:
    source = Path(
        source
    )

    suffix = source.suffix.lower()

    if suffix == ".dxf":
        return source

    if suffix != ".dwg":
        raise ValueError(
            f"Desteklenmeyen CAD turu: {suffix}"
        )

    cache_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = (
        cache_dir
        / f"{source.stem}.cad_to_3d.dxf"
    )

    if (
        output.exists()
        and output.stat().st_mtime
        >= source.stat().st_mtime
    ):
        return output

    _dwg_to_dxf(
        source,
        output,
    )

    return output


def _entity_closed(
    entity,
    entity_type,
) -> bool:
    if entity_type in {
        "CIRCLE",
    }:
        return True

    if entity_type == "LWPOLYLINE":
        try:
            return bool(
                entity.closed
            )
        except Exception:
            return False

    if entity_type == "POLYLINE":
        try:
            return bool(
                entity.is_closed
            )
        except Exception:
            return False

    if entity_type == "SPLINE":
        try:
            return bool(
                entity.closed
            )
        except Exception:
            return False

    if entity_type == "ELLIPSE":
        try:
            start = float(
                entity.dxf.start_param
            )

            end = float(
                entity.dxf.end_param
            )

            span = abs(
                end - start
            )

            return (
                abs(
                    span
                    - 2.0 * math.pi
                )
                <= 1e-5
            )

        except Exception:
            return False

    return False


def load_cad_preview_data(
    source: Path,
    cache_dir: Path,
) -> dict:
    dxf_path = ensure_dxf(
        Path(
            source
        ),
        Path(
            cache_dir
        ),
    )

    doc = ezdxf.readfile(
        str(
            dxf_path
        )
    )

    unit_info = (
        _cad_unit_info(
            doc
        )
    )

    msp = doc.modelspace()

    entity_counts = Counter(
        entity.dxftype()
        for entity in msp
    )

    layer_counts = Counter(
        str(
            entity.dxf.layer
        )
        for entity in msp
    )

    try:
        bb = bbox.extents(
            msp,
            fast=True,
        )

        if bb.has_data:
            dx = float(
                bb.extmax.x
                - bb.extmin.x
            )

            dy = float(
                bb.extmax.y
                - bb.extmin.y
            )

            drawing_span = max(
                dx,
                dy,
                1.0,
            )

        else:
            drawing_span = 1000.0

    except Exception:
        drawing_span = 1000.0

    flatten_distance = max(
        drawing_span
        / 6000.0,
        drawing_span
        * 1e-7,
        1e-9,
    )

    geometry = []

    min_x = float(
        "inf"
    )

    min_y = float(
        "inf"
    )

    max_x = float(
        "-inf"
    )

    max_y = float(
        "-inf"
    )

    def effective_linetype(
        entity,
        layer_name,
    ):
        try:
            raw = str(
                entity.dxf.linetype
            ).strip()

        except Exception:
            raw = "BYLAYER"

        effective = raw

        if raw.upper() == "BYLAYER":
            try:
                effective = str(
                    doc.layers.get(
                        str(
                            layer_name
                        )
                    ).dxf.linetype
                ).strip()

            except Exception:
                effective = raw

        return (
            raw,
            effective,
        )

    def add_geometry(
        points,
        layer,
        *,
        closed=False,
        entity_type="",
        linetype="",
        effective_linetype_name="",
        handle="",
    ):
        nonlocal min_x
        nonlocal min_y
        nonlocal max_x
        nonlocal max_y

        clean = []

        for point in points:
            try:
                x = float(
                    point[0]
                )

                y = float(
                    point[1]
                )

            except Exception:
                continue

            clean.append(
                (
                    x,
                    y,
                )
            )

            min_x = min(
                min_x,
                x,
            )

            min_y = min(
                min_y,
                y,
            )

            max_x = max(
                max_x,
                x,
            )

            max_y = max(
                max_y,
                y,
            )

        if len(
            clean
        ) < 2:
            return

        if (
            closed
            and clean[0]
            != clean[-1]
        ):
            clean.append(
                clean[0]
            )

        geometry.append(
            {
                "layer":
                    str(
                        layer
                    ),

                "points":
                    clean,

                "closed":
                    bool(
                        closed
                    ),

                "entity_type":
                    str(
                        entity_type
                    ),

                "linetype":
                    str(
                        linetype
                    ),

                "effective_linetype":
                    str(
                        effective_linetype_name
                    ),

                "handle":
                    str(
                        handle
                    ),
            }
        )

    for entity in msp:
        entity_type = (
            entity.dxftype()
        )

        layer = (
            entity.dxf.layer
        )

        raw_linetype, actual_linetype = (
            effective_linetype(
                entity,
                layer,
            )
        )

        try:
            handle = str(
                entity.dxf.handle
            )
        except Exception:
            handle = ""

        if entity_type == "SOLID":
            try:
                points = [
                    (
                        entity.dxf.vtx0.x,
                        entity.dxf.vtx0.y,
                    ),
                    (
                        entity.dxf.vtx1.x,
                        entity.dxf.vtx1.y,
                    ),
                    (
                        entity.dxf.vtx3.x,
                        entity.dxf.vtx3.y,
                    ),
                    (
                        entity.dxf.vtx2.x,
                        entity.dxf.vtx2.y,
                    ),
                ]

                add_geometry(
                    points,
                    layer,
                    closed=True,
                    entity_type=(
                        entity_type
                    ),
                    linetype=(
                        raw_linetype
                    ),
                    effective_linetype_name=(
                        actual_linetype
                    ),
                    handle=handle,
                )

            except Exception:
                pass

            continue

        if (
            entity_type
            not in SUPPORTED_PATH_TYPES
        ):
            continue

        try:
            cad_path = make_path(
                entity
            )

            vertices = list(
                cad_path.flattening(
                    distance=(
                        flatten_distance
                    ),
                    segments=8,
                )
            )

            points = [
                (
                    float(
                        vertex.x
                    ),
                    float(
                        vertex.y
                    ),
                )
                for vertex
                in vertices
            ]

            add_geometry(
                points,
                layer,
                closed=(
                    _entity_closed(
                        entity,
                        entity_type,
                    )
                ),
                entity_type=(
                    entity_type
                ),
                linetype=(
                    raw_linetype
                ),
                effective_linetype_name=(
                    actual_linetype
                ),
                handle=handle,
            )

        except Exception:
            continue

    if not geometry:
        raise RuntimeError(
            "CAD dosyasindan goruntulenebilir geometri cikarilamadi."
        )

    return {
        "source":
            str(
                source
            ),

        "dxf_path":
            str(
                dxf_path
            ),

        "entity_count":
            int(
                sum(
                    entity_counts.values()
                )
            ),

        "layer_count":
            len(
                doc.layers
            ),

        "geometry_count":
            len(
                geometry
            ),

        "entity_counts":
            dict(
                entity_counts
            ),

        "layer_counts":
            dict(
                layer_counts
            ),

        "bounds":
            (
                min_x,
                min_y,
                max_x,
                max_y,
            ),

        "geometry":
            geometry,

        **unit_info,
    }
