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

from . import DOORSTOP_DIR, INDEX_DIR, META_DIR
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

    item: BaseItem
    action: str  # "create", "update"
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
        core = QingsongCore.load()
        result = core.validate()
        if result.valid:
            core.build_cache()
    """

    # Paths
    meta_dir: Path = field(default_factory=lambda: META_DIR)
    doorstop_dir: Path = field(default_factory=lambda: DOORSTOP_DIR)
    index_dir: Path = field(default_factory=lambda: INDEX_DIR)

    # Loaded data
    metadata: Metadata | None = None
    items: dict[str, BaseItem] = field(default_factory=dict)

    # Staged changes (not yet written to disk)
    staged_changes: dict[str, StagedChange] = field(default_factory=dict)

    @classmethod
    def load(
        cls,
        meta_dir: Path | None = None,
        doorstop_dir: Path | None = None,
        index_dir: Path | None = None,
    ) -> "QingsongCore":
        """
        Load Qingsong core with all data.

        Args:
            meta_dir: Metadata directory path.
            doorstop_dir: Doorstop base directory path.
            index_dir: Index/cache directory path.

        Returns:
            Initialized QingsongCore instance.
        """
        core = cls(
            meta_dir=meta_dir or META_DIR,
            doorstop_dir=doorstop_dir or DOORSTOP_DIR,
            index_dir=index_dir or INDEX_DIR,
        )
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
            from .validate import ValidationError, ValidationResult
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
        **kwargs: Any,
    ) -> BaseItem:
        """
        Create a new item (staged, not written to disk).

        Args:
            item_type: Type of item to create.
            system_path: L1/L2 system path.
            title: Item title.
            text: Item text.
            owner: Owner person ID.
            **kwargs: Additional fields.

        Returns:
            Created item (staged).
        """
        if isinstance(item_type, str):
            item_type = ItemType(item_type)

        # Create item using doorstop_io (writes to disk immediately)
        # For true staging, we'd need to modify this
        item = create_new_item(
            item_type=item_type,
            system_path=system_path,
            title=title,
            text=text,
            owner=owner,
            base_dir=self.doorstop_dir,
            **kwargs,
        )

        # Add to items and staged changes
        self.items[item.id_full] = item
        self.staged_changes[item.id_full] = StagedChange(
            item=item,
            action="create",
        )

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
            item=updated,
            action="update",
            original=original,
        )

        return updated

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

    def flush(self) -> int:
        """
        Write all staged changes to disk.

        Returns:
            Number of items written.
        """
        count = 0

        for item_id, change in self.staged_changes.items():
            # Determine document directory
            parts = item_id.split("-")
            if len(parts) >= 4:
                type_code = parts[3]
                l1 = parts[1]
                l2 = parts[2]
                doc_dir = self.doorstop_dir / type_code / l1 / l2

                if doc_dir.exists():
                    save_item(change.item, doc_dir)
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

