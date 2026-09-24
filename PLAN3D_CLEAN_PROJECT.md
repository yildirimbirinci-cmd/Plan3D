# Plan3D Clean Baseline

This package is a cleaned baseline built from the uploaded project.

## Active vertical/opening scope
- Ground Floor only for facade opening heights.
- `C Ölçü` lowest horizontal line is the single Z=0 datum.
- Window, Door and Sliding Door semantics come from assigned CAD layers.
- Ground opening membership is centre-based; opening height is measured directly from Z=0.
- No entrance offset, facade-local datum, storey lattice, legacy V20S/V20U/V20AQ height cache, or export-time height reanalysis is used.
- Ground window Max export consumes the already-computed Ground opening result plus V33 plan contacts.

## Preserved systems
- Canonical wall export and Exterior Wall exclusion.
- Floor export.
- Existing interior-door Max chain. It was not behaviorally rewritten because it is a confirmed working system.

## Structural cleanup
- Historical root patch/audit scripts, backups and Python caches removed.
- `prepare_wall_only_transfer` override chain flattened into named wall/project/extrude/floor/interior-door stages plus one public final transfer function.
- Dead early project-layer helper definitions removed.
- Ground opening and Ground window export code rewritten as one readable active path.

## Run
```powershell
cd "C:\Users\yildi\Desktop\Plan3D"; py -3.12 ".\src\app\main.py"
```
