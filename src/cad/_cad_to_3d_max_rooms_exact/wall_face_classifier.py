from __future__ import annotations

from cad._cad_to_3d_max_rooms_exact.cad_intelligence import (
    extract_segments,
    find_parallel_pairs,
    infer_cad_profile,
)


def classify_wall_faces(geometry):
    profile = infer_cad_profile(geometry)
    structural_layers = list(profile.get("structural_layers") or [])
    primary = profile.get("primary_structural_layer")
    if not structural_layers and primary:
        structural_layers = [primary]

    segments = extract_segments(geometry, structural_layers)
    pairs = find_parallel_pairs(
        segments,
        profile.get("gap_families") or None,
    )

    accepted_segment_ids = set()
    family_counts = {}

    for pair in pairs:
        accepted_segment_ids.add(pair["a"]["id"])
        accepted_segment_ids.add(pair["b"]["id"])
        family_index = int(pair.get("family_index", 0))
        family_counts[family_index] = family_counts.get(family_index, 0) + 1

    wall_geometry = []
    for segment in segments:
        if segment["id"] not in accepted_segment_ids:
            continue
        wall_geometry.append({
            "layer": "__WALL_CONFIRMED__",
            "points": [
                (segment["x1"], segment["y1"]),
                (segment["x2"], segment["y2"]),
            ],
            "wall_kind": "confirmed_face",
            "source_layer": segment["layer"],
        })

    families = profile.get("gap_families") or []
    return {
        "engine": "GENERIC_WALL_FACE_CLASSIFIER_V1",
        "profile": profile,
        "structural_layers": structural_layers,
        "primary_structural_layer": primary,
        "axis_segments": len(segments),
        "candidate_pairs": len(pairs),
        "mutual_pairs": len(pairs),
        "seed_pairs": len(pairs),
        "recovered_pairs": 0,
        "wall_faces": len(wall_geometry),
        "normal_pairs": int(family_counts.get(0, 0)),
        "thick_pairs": int(family_counts.get(1, 0)),
        "gap_families": families,
        "wall_geometry": wall_geometry,
    }
