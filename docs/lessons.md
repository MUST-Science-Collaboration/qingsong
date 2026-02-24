# Qingsong Development Lessons

## 1. Hierarchy & Storage (2026-02-25)
### Flexible L3 Folders
**Decision**: Allow L3 task codes (e.g., `FID-AIT`) to be used as sub-directories under `L1/L2` in the Doorstop storage.
**Rationale**: Complex systems like MUST require more than two levels of organization. Treating L3 folders as first-class Doorstop documents allows for cleaner separation of files and localized `.doorstop.yml` configuration (including custom prefixes).
**Implementation**: 
- `_infer_hierarchy_context` in `doorstop_io.py` now extracts both `system_path` (L1/L2) and `l3` from the file path.
- `QingsongCore.create_item` and `flush()` were updated to respect this nested structure.

### Flexible ID Validation
**Decision**: Relaxed the `id_full` regex and validation to support 5 or 6-part IDs.
**Rationale**: Standard Doorstop IDs are typically 4-5 parts. By supporting 6 parts (`MUST-L1-L2-L3-TYPE-NNN`), we accommodate systems where L3 provides its own naming scope.
**Implementation**: 
- Updated Pydantic `BaseItem` regex.
- Updated `validate_id_format` to check consistency between ID segments and item attributes (`system_path`, `l3`).

## 2. API & Staging (2026-02-24)
### In-Memory Staging
**Decision**: `QingsongCore` implements a `staged_changes` map.
**Rationale**: Direct-to-disk writes can lead to partial or invalid states. Staging allows for a "dry run" validation before persistent changes are committed via `flush()`.
**Implementation**: `create_item` and `update_item` add to `staged_changes` and `items` cache, but `doorstop_io.save_item` is only called during `flush()`.
