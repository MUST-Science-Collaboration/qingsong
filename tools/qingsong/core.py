"""
Core API for Qingsong.

This module provides the main API for interacting with Qingsong:
- Loading metadata and items
- Validation
- Cache building
- Staging edits and flushing to YAML

Design Decision:
----------------
The Core API follows a "load → validate → stage → flush" pattern:
1. Load: Read items from YAML into memory
2. Validate: Check all constraints
3. Stage: Make changes to in-memory objects
4. Flush: Write changes back to YAML (explicit action)

This ensures no accidental writes and allows for validation before persistence.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from . import get_project_root
from .cache_build import build_cache, get_cache_stats, query_cache, search_items
from .doorstop_io import (
    create_new_item,
    list_documents,
    load_all_items,
    save_item,
)
from .load_meta import (
    Metadata,
    clear_cache as clear_meta_cache,
    load_metadata,
    validate_metadata,
)
from .models import BaseItem, ItemType
from .validate import ValidationResult, validate_all, validate_item


@dataclass
class StagedChange:
    """Represents a staged change to an item."""

    item_id: str
    item: BaseItem | None  # None for deletion
    action: str  # "create", "update", "delete"
    original: BaseItem | None = None


@dataclass
class QingsongCore:
    """
    Main API class for Qingsong operations.

    This class provides a unified interface for:
    - Loading metadata and items
    - Validating items
    - Building and querying the cache
    - Staging edits and flushing changes

    Usage:
        core = QingsongCore.load(project_root="/path/to/vault")
        result = core.validate()
        if result.valid:
            core.build_cache()
    """

    # Paths
    project_root: Path
    meta_dir: Path = field(init=False)
    doorstop_dir: Path = field(init=False)
    index_dir: Path = field(init=False)

    def __post_init__(self):
        self.meta_dir = self.project_root / "meta"
        self.doorstop_dir = self.project_root / "doorstop"
        self.index_dir = self.project_root / "index"

    # Loaded data
    metadata: Metadata | None = None
    items: dict[str, BaseItem] = field(default_factory=dict)

    # Staged changes (not yet written to disk)
    staged_changes: dict[str, StagedChange] = field(default_factory=dict)

    @classmethod
    def load(
        cls,
        project_root: Path | str | None = None,
    ) -> "QingsongCore":
        """
        Load Qingsong core with all data.

        Args:
            project_root: Path to the project/vault root. Defaults to auto-detected root.

        Returns:
            Initialized QingsongCore instance.
        """
        if project_root is None:
            root = get_project_root()
        else:
            root = Path(project_root)

        core = cls(project_root=root)
        core.reload()
        return core

    def reload(self) -> None:
        """Reload all data from disk."""
        clear_meta_cache()
        self.metadata = load_metadata(self.meta_dir, force_reload=True)
        self.items = load_all_items(self.doorstop_dir)
        self.staged_changes = {}

    def validate_metadata(self) -> list[str]:
        """
        Validate metadata files.

        Returns:
            List of error messages. Empty means valid.
        """
        return validate_metadata(self.meta_dir)

    def validate(self) -> ValidationResult:
        """
        Validate all items.

        Returns:
            ValidationResult with all errors and warnings.
        """
        return validate_all(self.doorstop_dir, self.meta_dir)

    def validate_item(self, item_id: str) -> ValidationResult:
        """
        Validate a single item.

        Args:
            item_id: ID of item to validate.

        Returns:
            ValidationResult for the item.
        """
        if item_id not in self.items:
            from .validate import ValidationError
            return ValidationResult(
                valid=False,
                errors=[ValidationError(item_id, "id_full", f"Item not found: {item_id}")],
                warnings=[],
                item_count=0,
            )

        item = self.items[item_id]
        errors = validate_item(item, self.items, self.metadata)
        return ValidationResult(
            valid=len([e for e in errors if e.severity == "error"]) == 0,
            errors=[e for e in errors if e.severity == "error"],
            warnings=[e for e in errors if e.severity == "warning"],
            item_count=1,
        )

    def build_cache(self, output_path: Path | None = None) -> Path:
        """
        Build SQLite cache.

        Args:
            output_path: Optional custom output path.

        Returns:
            Path to created cache file.
        """
        if output_path is None:
            output_path = self.index_dir / "qingsong.sqlite"
        return build_cache(output_path, self.doorstop_dir, self.meta_dir)

    def query(self, sql: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
        """
        Execute SQL query on cache.

        Args:
            sql: SQL query string.
            params: Query parameters.

        Returns:
            List of result dictionaries.
        """
        cache_path = self.index_dir / "qingsong.sqlite"
        return query_cache(sql, params, cache_path)

    def search(self, query: str) -> list[dict[str, Any]]:
        """
        Full-text search items.

        Args:
            query: Search query.

        Returns:
            List of matching items.
        """
        cache_path = self.index_dir / "qingsong.sqlite"
        return search_items(query, cache_path)

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        cache_path = self.index_dir / "qingsong.sqlite"
        return get_cache_stats(cache_path)

    def get_item(self, item_id: str) -> BaseItem | None:
        """
        Get an item by ID.

        Args:
            item_id: Item ID.

        Returns:
            Item or None if not found.
        """
        # Check staged changes first
        if item_id in self.staged_changes:
            return self.staged_changes[item_id].item
        return self.items.get(item_id)

    def create_item(
        self,
        item_type: ItemType | str,
        system_path: str,
        title: str,
        text: str,
        owner: str,
        category_path: str | None = None,
        l3: str | None = None,
        **kwargs: Any,
    ) -> BaseItem:
        """
        Create a new item (staged, not written to disk until flush).

        Args:
            item_type: Type of item to create.
            system_path: L1/L2 system path.
            title: Item title.
            text: Item text.
            owner: Owner person ID.
            category_path: Optional category path.
            l3: Optional L3 task code.
            **kwargs: Additional fields.

        Returns:
            Created item (staged).
        """
        if isinstance(item_type, str):
            item_type = ItemType(item_type)

        # Get the appropriate model class
        from .models import ITEM_TYPE_MODELS
        model_class = ITEM_TYPE_MODELS[item_type]

        # Determine next ID (requires reading current files for sequence)
        parts = system_path.split("/")
        l1, l2 = parts
        
        # Determine doc_dir with optional L3
        doc_dir = self.doorstop_dir / item_type.value / l1 / l2
        if l3:
            doc_dir = doc_dir / l3
        
        # Use l3 for prefix if provided
        id_prefix = f"MUST-{l1}-{l3 or l2}-{item_type.value}"
        
        # We need to consider staged items when calculating next number
        existing_nums = []
        if doc_dir.exists():
            from .doorstop_io import _find_item_files
            existing_nums = [int(f.stem) for f in _find_item_files(doc_dir) if f.stem.isdigit()]
        
        # Add staged numbers for this doc_dir/prefix
        for staged_id in self.staged_changes:
            if staged_id.startswith(f"{id_prefix}-"):
                try:
                    existing_nums.append(int(staged_id.split("-")[-1]))
                except ValueError:
                    pass
        
        next_num = max(existing_nums, default=0) + 1
        id_full = f"{id_prefix}-{next_num:03d}"

        # Build initial data
        now = datetime.now(timezone.utc)
        
        # Defaults for category_path
        if category_path is None:
            if item_type == ItemType.REQ:
                category_path = "functional/observation"
            elif item_type == ItemType.RSK:
                category_path = "technical/design"
            elif item_type == ItemType.IFC:
                category_path = "mechanical/mounting"
            else:
                category_path = "other"

        data = {
            "type": item_type,
            "id_full": id_full,
            "title": title,
            "text": text,
            "system_path": system_path,
            "owner": owner,
            "status": "draft",
            "created_at": now,
            "updated_at": now,
            "category_path": category_path,
            "l3": l3,
            **kwargs,
        }

        # Add more type-specific defaults
        if item_type == ItemType.RSK:
            if "likelihood" not in data: data["likelihood"] = 3
            if "consequence" not in data: data["consequence"] = 3
            if "risk_status" not in data: data["risk_status"] = "identified"
        elif item_type == ItemType.IFC:
            if "provider_system" not in data: data["provider_system"] = system_path
            if "interface_status" not in data: data["interface_status"] = "proposed"

        # Create instance
        item = model_class.model_validate(data)

        # Stage change
        self.staged_changes[item.id_full] = StagedChange(
            item_id=item.id_full,
            item=item,
            action="create",
        )
        # Add to current items for immediate visibility
        self.items[item.id_full] = item

        return item

    def update_item(self, item_id: str, **updates: Any) -> BaseItem:
        """
        Update an item (staged).

        Args:
            item_id: ID of item to update.
            **updates: Fields to update.

        Returns:
            Updated item.

        Raises:
            KeyError: If item not found.
        """
        if item_id not in self.items:
            raise KeyError(f"Item not found: {item_id}")

        original = self.items[item_id]
        data = original.model_dump()
        data.update(updates)
        data["updated_at"] = datetime.now(timezone.utc)

        # Create new instance with updates
        from .models import ITEM_TYPE_MODELS
        model_class = ITEM_TYPE_MODELS[original.type]
        updated = model_class.model_validate(data)

        self.items[item_id] = updated
        self.staged_changes[item_id] = StagedChange(
            item_id=item_id,
            item=updated,
            action="update",
            original=original,
        )

        return updated

    def delete_item(self, item_id: str) -> None:
        """
        Delete an item (staged).

        Args:
            item_id: ID of item to delete.

        Raises:
            KeyError: If item not found.
        """
        if item_id not in self.items:
            raise KeyError(f"Item not found: {item_id}")

        original = self.items.pop(item_id)
        self.staged_changes[item_id] = StagedChange(
            item_id=item_id,
            item=None,
            action="delete",
            original=original,
        )

    def migrate_item(
        self,
        item_id: str,
        new_system_path: str,
        new_l3: str | None = None,
    ) -> BaseItem:
        """
        Migrate an item to a new system or L3 folder, updating its ID and links.

        Args:
            item_id: Current item ID.
            new_system_path: New L1/L2 path.
            new_l3: Optional new L3 task code.

        Returns:
            Migrated item (staged).
        """
        if item_id not in self.items:
            raise KeyError(f"Item not found: {item_id}")

        item = self.items[item_id]
        
        # Calculate new ID prefix
        parts = new_system_path.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid system_path: {new_system_path}")
        l1, l2 = parts
        
        id_prefix = f"MUST-{l1}-{new_l3 or l2}-{item.type.value}"
        
        # Determine next number in the NEW directory
        doc_dir = self.doorstop_dir / item.type.value / l1 / l2
        if new_l3:
            doc_dir = doc_dir / new_l3
            
        existing_nums = []
        if doc_dir.exists():
            from .doorstop_io import _find_item_files
            existing_nums = [int(f.stem) for f in _find_item_files(doc_dir) if f.stem.isdigit()]
            
        # Add staged numbers for this new prefix
        for staged_id in self.staged_changes:
            if staged_id.startswith(f"{id_prefix}-"):
                try:
                    existing_nums.append(int(staged_id.split("-")[-1]))
                except ValueError:
                    pass
                    
        next_num = max(existing_nums, default=0) + 1
        new_id = f"{id_prefix}-{next_num:03d}"
        
        # 1. Stage deletion of old ID
        self.delete_item(item_id)
        
        # 2. Create new item data (preserving most fields)
        data = item.model_dump()
        data.update({
            "id_full": new_id,
            "system_path": new_system_path,
            "l3": new_l3,
            "updated_at": datetime.now(timezone.utc),
        })
        
        # 3. Create and stage the new item
        from .models import ITEM_TYPE_MODELS
        model_class = ITEM_TYPE_MODELS[item.type]
        migrated = model_class.model_validate(data)
        
        self.items[new_id] = migrated
        self.staged_changes[new_id] = StagedChange(
            item_id=new_id,
            item=migrated,
            action="create",
        )
        
        # 4. Find all other items that link to item_id and update them
        for other_id, other_item in self.items.items():
            if other_id == new_id:
                continue
                
            links_updated = False
            new_links = []
            for link in other_item.links:
                if link.target_id == item_id:
                    new_links.append(link.model_copy(update={"target_id": new_id}))
                    links_updated = True
                else:
                    new_links.append(link)
                    
            if links_updated:
                self.update_item(other_id, links=new_links)
                
        return migrated

    def retire_item(
        self,
        item_id: str,
        reason: str,
        retired_by: str,
        superseded_by: str | None = None,
    ) -> BaseItem:
        """
        Retire an item (no hard delete).

        Args:
            item_id: ID of item to retire.
            reason: Reason for retirement.
            retired_by: Person ID retiring the item.
            superseded_by: Optional ID of superseding item.

        Returns:
            Updated item.
        """
        status = "superseded" if superseded_by else "retired"

        return self.update_item(
            item_id,
            status=status,
            retirement={
                "retired_at": datetime.now(timezone.utc),
                "retired_by": retired_by,
                "retired_reason": reason,
                "superseded_by": superseded_by,
            },
        )

    def flush(self, strict: bool = True) -> int:
        """
        Write all staged changes to disk.

        Args:
            strict: If True, validate items before flushing.

        Returns:
            Number of items written/deleted.

        Raises:
            ValueError: If validation fails in strict mode.
        """
        if strict:
            for item_id, change in self.staged_changes.items():
                if change.action == "delete":
                    continue
                result = self.validate_item(item_id)
                if not result.valid:
                    errors_msg = "; ".join([f"{e.field}: {e.message}" for e in result.errors])
                    raise ValueError(f"Validation failed for staged item {item_id}: {errors_msg}")

        count = 0
        for item_id, change in self.staged_changes.items():
            if change.action == "delete":
                # Delete old file
                item = change.original
                if item:
                    parts = item.system_path.split("/")
                    l1, l2 = parts
                    doc_dir = self.doorstop_dir / item.type.value / l1 / l2
                    if item.l3:
                        doc_dir = doc_dir / item.l3
                    
                    # Filename from ID
                    id_parts = item.id_full.split("-")
                    num = id_parts[-1]
                    file_path = doc_dir / f"{num}.yml"
                    
                    if file_path.exists():
                        file_path.unlink()
                        count += 1
                continue

            item = change.item
            if item:
                # Determine document directory
                parts = item.system_path.split("/")
                if len(parts) == 2:
                    l1, l2 = parts
                    type_code = item.type.value
                    l3 = item.l3
                    
                    # Ensure document exists (creates .doorstop.yml if missing)
                    from .doorstop_io import create_doorstop_document
                    doc_dir = create_doorstop_document(type_code, l1, l2, l3=l3, base_dir=self.doorstop_dir)

                    if doc_dir.exists():
                        save_item(item, doc_dir)
                        count += 1

        self.staged_changes = {}
        return count

    def discard_changes(self) -> None:
        """Discard all staged changes and reload from disk."""
        self.reload()

    def list_documents(self) -> list[dict[str, Any]]:
        """List all Doorstop documents."""
        return list_documents(self.doorstop_dir)

    def get_items_by_type(self, item_type: ItemType | str) -> list[BaseItem]:
        """Get all items of a specific type."""
        if isinstance(item_type, str):
            item_type = ItemType(item_type)
        return [item for item in self.items.values() if item.type == item_type]

    def get_items_by_system(self, system_path: str) -> list[BaseItem]:
        """Get all items for a system path."""
        return [item for item in self.items.values() if item.system_path == system_path]

    def get_items_by_owner(self, owner: str) -> list[BaseItem]:
        """Get all items owned by a person."""
        return [item for item in self.items.values() if item.owner == owner]

    def get_items_by_status(self, status: str) -> list[BaseItem]:
        """Get all items with a specific status."""
        return [item for item in self.items.values() if item.status.value == status]

    def get_linked_items(self, item_id: str) -> dict[str, list[BaseItem]]:
        """
        Get items linked to/from a specific item.

        Args:
            item_id: Item ID.

        Returns:
            Dictionary with "outgoing" and "incoming" link lists.
        """
        result: dict[str, list[BaseItem]] = {"outgoing": [], "incoming": []}

        item = self.items.get(item_id)
        if not item:
            return result

        # Outgoing links
        for link in item.links:
            target = self.items.get(link.target_id)
            if target:
                result["outgoing"].append(target)

        # Incoming links
        for other in self.items.values():
            for link in other.links:
                if link.target_id == item_id:
                    result["incoming"].append(other)
                    break

        return result

    # DataFrame methods for UI integration

    def items_to_dataframe(self, items: list[BaseItem] | None = None) -> pd.DataFrame:
        """
        Convert items to a Pandas DataFrame.

        Args:
            items: List of items. Defaults to all items.

        Returns:
            DataFrame with item data.
        """
        if items is None:
            items = list(self.items.values())

        if not items:
            return pd.DataFrame()

        records = []
        for item in items:
            record = {
                "id_full": item.id_full,
                "type": item.type.value,
                "title": item.title,
                "system_path": item.system_path,
                "l3": item.l3,
                "owner": item.owner,
                "status": item.status.value,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
            }
            # Add category_path if available
            if hasattr(item, "category_path"):
                record["category_path"] = item.category_path
            # Add risk fields if risk
            if hasattr(item, "likelihood"):
                record["likelihood"] = item.likelihood
                record["consequence"] = item.consequence
                record["risk_score"] = item.risk_score
            records.append(record)

        return pd.DataFrame(records)

    def links_to_dataframe(self) -> pd.DataFrame:
        """
        Get all links as a DataFrame.

        Returns:
            DataFrame with link data.
        """
        records = []
        for item in self.items.values():
            for link in item.links:
                records.append({
                    "source_id": item.id_full,
                    "target_id": link.target_id,
                    "link_type": link.link_type,
                    "description": link.description,
                })

        return pd.DataFrame(records)

    def get_traceability_matrix(
        self,
        item_type: ItemType | str = ItemType.REQ,
        direction: str = "downward",
    ) -> list[dict[str, Any]]:
        """
        Generate a traceability matrix.

        Args:
            item_type: Base item type to trace.
            direction: "upward" (to parents) or "downward" (to children).

        Returns:
            List of rows for the matrix.
        """
        if isinstance(item_type, str):
            item_type = ItemType(item_type)

        base_items = self.get_items_by_type(item_type)
        matrix = []

        # Find all relevant links
        trace_links = ["derives_from", "implements", "verifies", "related_to"]

        for item in base_items:
            row = {
                "id": item.id_full,
                "title": item.title,
                "status": item.status.value,
                "links": [],
            }

            if direction == "upward":
                # Find parents (outgoing links from item)
                for link in item.links:
                    if link.link_type in trace_links:
                        target = self.get_item(link.target_id)
                        row["links"].append({
                            "id": link.target_id,
                            "type": link.link_type,
                            "title": target.title if target else "Unknown",
                        })
            else:
                # Find children (incoming links to item)
                for other in self.items.values():
                    for link in other.links:
                        if link.target_id == item.id_full and link.link_type in trace_links:
                            row["links"].append({
                                "id": other.id_full,
                                "type": link.link_type,
                                "title": other.title,
                            })

            matrix.append(row)

        return matrix

    def get_verification_summary(self) -> dict[str, Any]:
        """
        Get a summary of requirement verification status.

        Returns:
            Dictionary with verification statistics.
        """
        reqs = self.get_items_by_type(ItemType.REQ)
        total = len(reqs)
        if total == 0:
            return {"total": 0, "verified": 0, "percent": 0}

        verified_count = len([r for r in reqs if getattr(r, "verified", False)])
        
        # Breakdown by method
        methods = {}
        for r in reqs:
            m = str(getattr(r, "verification_method", "None"))
            methods[m] = methods.get(m, 0) + 1

        # Breakdown by system
        systems = {}
        for r in reqs:
            s = r.system_path
            if s not in systems:
                systems[s] = {"total": 0, "verified": 0}
            systems[s]["total"] += 1
            if getattr(r, "verified", False):
                systems[s]["verified"] += 1

        return {
            "total": total,
            "verified": verified_count,
            "percent": (verified_count / total) * 100,
            "by_method": methods,
            "by_system": systems,
        }

    def summary(self) -> dict[str, Any]:
        """
        Get a summary of the repository state.

        Returns:
            Summary dictionary.
        """
        return {
            "total_items": len(self.items),
            "items_by_type": {
                t.value: len([i for i in self.items.values() if i.type == t])
                for t in ItemType
            },
            "items_by_status": {
                s: len([i for i in self.items.values() if i.status.value == s])
                for s in ["draft", "active", "retired", "superseded"]
            },
            "systems": self.metadata.valid_system_paths if self.metadata else [],
            "people_count": len(self.metadata.people) if self.metadata else 0,
            "staged_changes": len(self.staged_changes),
        }

