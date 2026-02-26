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

## 3. Project Portability (2026-02-26)
### Dynamic Root Context
**Decision**: Use an environment variable (`QINGSONG_ROOT`) to bridge the gap between CLI arguments and deep Pydantic validation.
**Rationale**: Pydantic's `model_validator` methods are often called in isolated contexts where CLI-level state isn't available. A standardized env var ensures all layers of the engine resolve metadata paths consistently.
**Implementation**: `get_project_root` checks `QINGSONG_ROOT` before falling back to auto-discovery.

## 4. UI Architecture (2026-02-27)
### Multi-Page Dashboard
**Decision**: Transition from a single `app_streamlit.py` to a `pages/` directory structure.
**Rationale**: As features like Impact Analysis and Traceability grew, a single-page layout became cluttered. A multi-page approach improves focus and allows for deeper interactive components (like the Item Editor) without side effects on other views.

## 5. Analytical Intelligence (2026-02-27)
### Transitive Impact Tracing
**Decision**: Implement bi-directional recursive traversal for impact analysis.
**Rationale**: Simple link checking only shows the first level of impact. True system engineering requires seeing the "end-to-end" ripple effect of a change across the parent/child requirement chain.
