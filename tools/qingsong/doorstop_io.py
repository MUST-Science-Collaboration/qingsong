"""
Doorstop I/O module for Qingsong.

Handles reading and writing Doorstop items using ruamel.yaml for safe
round-tripping with preserved formatting.

Design Decision:
----------------
While Doorstop has its own API, we use ruamel.yaml directly for YAML
manipulation to:
1. Preserve formatting and comments
2. Have full control over the YAML structure
3. Add our custom attributes without Doorstop interference
"""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from . import get_project_root
from .load_meta import load_metadata
from .models import (
    ITEM_TYPE_MODELS,
    BaseItem,
    DataRecord,
    Document,
    Interface,
    ItemType,
    Note,
    Requirement,
    Risk,
)


def _get_yaml() -> YAML:
    """Get a configured YAML instance for round-tripping."""
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.default_flow_style = False
    yaml.width = 120
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def _find_doorstop_documents(base_dir: Path | None = None) -> list[Path]:
    """
    Find all Doorstop document directories (containing .doorstop.yml).

    Args:
        base_dir: Base directory to search. Defaults to DOORSTOP_DIR.

    Returns:
        List of paths to Doorstop document directories.
    """
    if base_dir is None:
        base_dir = DOORSTOP_DIR

    docs = []
    for root, dirs, files in os.walk(base_dir):
        if ".doorstop.yml" in files:
            docs.append(Path(root))
    return docs


def _parse_doorstop_config(doc_path: Path) -> dict[str, Any]:
    """Parse a Doorstop document configuration file."""
    yaml = YAML(typ="safe")
    config_path = doc_path / ".doorstop.yml"
    if not config_path.exists():
        return {}
    with open(config_path) as f:
        return yaml.load(f) or {}


def _find_item_files(doc_path: Path) -> list[Path]:
    """Find all item YAML files in a Doorstop document directory."""
    items = []
    for f in doc_path.iterdir():
        if f.is_file() and f.suffix in (".yml", ".yaml") and f.name != ".doorstop.yml":
            items.append(f)
    return sorted(items)


def _infer_item_type(data: dict[str, Any], doc_config: dict[str, Any]) -> ItemType:
    """
    Infer item type from data or document configuration.

    Args:
        data: Item data dictionary.
        doc_config: Doorstop document configuration.

    Returns:
        Inferred ItemType.
    """
    # First check if type is explicitly set
    if "type" in data:
        return ItemType(data["type"])

    # Try to infer from the document prefix
    prefix = doc_config.get("prefix", "")
    if "-REQ" in prefix:
        return ItemType.REQ
    elif "-RSK" in prefix:
        return ItemType.RSK
    elif "-IFC" in prefix:
        return ItemType.IFC
    elif "-DOC" in prefix:
        return ItemType.DOC
    elif "-DAT" in prefix:
        return ItemType.DAT
    elif "-NOTE" in prefix:
        return ItemType.NOTE

    # Default to REQ if we can't determine
    return ItemType.REQ


def _infer_hierarchy_context(doc_path: Path) -> tuple[str, str | None]:
    """
    Infer system path and optional L3 code from document directory structure.

    Args:
        doc_path: Path to Doorstop document directory.

    Returns:
        Tuple of (system_path, l3_code).
    """
    # Expected structure: doorstop/TYPE/L1/L2/[L3]
    parts = doc_path.parts
    # Find the position after 'doorstop' and type folder
    try:
        doorstop_idx = parts.index("doorstop")
        if len(parts) > doorstop_idx + 3:
            l1 = parts[doorstop_idx + 2]  # Skip type folder
            l2 = parts[doorstop_idx + 3]
            system_path = f"{l1}/{l2}"
            l3 = None
            if len(parts) > doorstop_idx + 4:
                l3 = parts[doorstop_idx + 4]
            return system_path, l3
    except (ValueError, IndexError):
        pass

    return "UNKNOWN/UNKNOWN", None


def load_item(file_path: Path, doc_config: dict[str, Any] | None = None) -> BaseItem:
    """
    Load a single Doorstop item from a YAML file.

    Args:
        file_path: Path to the item YAML file.
        doc_config: Optional Doorstop document configuration.

    Returns:
        Parsed item as appropriate Pydantic model.

    Raises:
        ValueError: If the file is not a valid YAML or doesn't match the model.
    """
    yaml = YAML(typ="safe")
    try:
        with open(file_path) as f:
            data = yaml.load(f) or {}
    except Exception as e:
        raise ValueError(f"Failed to parse YAML in {file_path}: {e}")

    # Get document config if not provided
    if doc_config is None:
        doc_config = _parse_doorstop_config(file_path.parent)

    # Infer type
    try:
        item_type = _infer_item_type(data, doc_config)
        data["type"] = item_type.value
    except Exception as e:
        # Fallback to REQ if type inference fails
        data["type"] = ItemType.REQ.value
        item_type = ItemType.REQ

    # Ensure required fields have defaults
    if "id_full" not in data:
        # Try to construct from filename or UID
        uid = data.get("uid", file_path.stem)
        prefix = doc_config.get("settings", {}).get("prefix", "MUST-UNK-UNK-UNK")
        if uid.startswith(prefix):
            data["id_full"] = uid
        else:
            # Try to parse the UID as a number
            try:
                num = int(uid)
                data["id_full"] = f"{prefix}-{num:03d}"
            except ValueError:
                data["id_full"] = f"{prefix}-{uid}"

    # Infer hierarchy context from directory structure
    system_path, l3 = _infer_hierarchy_context(file_path.parent)

    if "system_path" not in data:
        data["system_path"] = system_path

    if "l3" not in data:
        data["l3"] = l3

    if "title" not in data:
        data["title"] = data.get("header", "Untitled")

    if "text" not in data:
        data["text"] = data.get("text", "No description provided.")

    if "owner" not in data:
        data["owner"] = "ps001"  # Default owner

    if "status" not in data:
        data["status"] = "draft"

    # Handle category_path for type-specific models
    if item_type in (ItemType.REQ, ItemType.RSK, ItemType.IFC) and "category_path" not in data:
        data["category_path"] = "other"

    # Convert Doorstop links to Qingsong links format
    if "links" in data:
        doorstop_links = data["links"]
        qingsong_links = []
        for link in doorstop_links:
            if isinstance(link, str):
                qingsong_links.append({
                    "target_id": link,
                    "link_type": "related_to",
                })
            elif isinstance(link, dict):
                # Already in our format or Doorstop extended format
                if "target_id" in link:
                    qingsong_links.append(link)
                elif "uid" in link:
                    qingsong_links.append({
                        "target_id": link["uid"],
                        "link_type": link.get("type", "related_to"),
                        "description": link.get("description"),
                    })
        data["links"] = qingsong_links

    # Get the appropriate model class
    try:
        model_class = ITEM_TYPE_MODELS[item_type]
        return model_class.model_validate(data)
    except Exception as e:
        raise ValueError(f"Validation failed for {file_path}: {e}")


def load_all_items(
    base_dir: Path | None = None,
) -> dict[str, BaseItem]:
    """
    Load all Doorstop items from the repository.

    Args:
        base_dir: Base directory to search. Defaults to project doorstop dir.

    Returns:
        Dictionary mapping item IDs to item objects.
    """
    if base_dir is None:
        base_dir = get_project_root() / "doorstop"

    items: dict[str, BaseItem] = {}

    for doc_path in _find_doorstop_documents(base_dir):
        doc_config = _parse_doorstop_config(doc_path)

        for item_file in _find_item_files(doc_path):
            try:
                item = load_item(item_file, doc_config)
                items[item.id_full] = item
            except Exception as e:
                # Log error but continue loading other items
                print(f"Warning: Failed to load {item_file}: {e}")

    return items


def save_item(item: BaseItem, doc_dir: Path) -> Path:
    """
    Save an item to a Doorstop YAML file.

    Args:
        item: Item to save.
        doc_dir: Directory for the Doorstop document.

    Returns:
        Path to the saved file.

    Raises:
        IOError: If the directory cannot be created or the file cannot be written.
    """
    yaml = _get_yaml()

    # Ensure doc_dir exists
    try:
        doc_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise IOError(f"Failed to create directory {doc_dir}: {e}")

    # Prepare data for YAML
    data = item.to_doorstop_dict()

    # Doorstop expects specific fields at top
    ordered_data = {}

    # Doorstop standard fields first
    for key in ["active", "derived", "normative", "reviewed"]:
        if key in data:
            ordered_data[key] = data.pop(key)

    # Add remaining fields
    ordered_data.update(data)

    # Convert links to Doorstop format
    if "links" in ordered_data:
        doorstop_links = []
        for link in ordered_data["links"]:
            if isinstance(link, dict):
                doorstop_links.append({
                    "uid": link["target_id"],
                    "type": link.get("link_type", "related_to"),
                })
        ordered_data["links"] = doorstop_links

    # Determine filename from ID
    # Format: MUST-L1-L2-TYPE-NNN → NNN.yml
    parts = item.id_full.split("-")
    if len(parts) >= 5:
        num = parts[-1]
    else:
        num = item.id_full

    file_path = doc_dir / f"{num}.yml"

    # Write file safely using a temporary file if possible, or just open and dump
    try:
        with open(file_path, "w") as f:
            yaml.dump(ordered_data, f)
    except Exception as e:
        raise IOError(f"Failed to save item to {file_path}: {e}")

    return file_path


def create_doorstop_document(
    type_code: str,
    l1: str,
    l2: str,
    l3: str | None = None,
    base_dir: Path | None = None,
) -> Path:
    """
    Create a new Doorstop document directory with configuration.

    Args:
        type_code: Item type code (REQ, RSK, IFC, DOC, DAT, NOTE).
        l1: L1 system code.
        l2: L2 subsystem code.
        l3: Optional L3 task code for nested document.
        base_dir: Base directory. Defaults to project doorstop dir.

    Returns:
        Path to the created document directory.
    """
    if base_dir is None:
        base_dir = get_project_root() / "doorstop"

    doc_dir = base_dir / type_code / l1 / l2
    if l3:
        doc_dir = doc_dir / l3
    doc_dir.mkdir(parents=True, exist_ok=True)

    # Create .doorstop.yml configuration
    # Use L3 code if provided, otherwise L2
    prefix = f"MUST-{l1}-{l3 or l2}-{type_code}"
    config = {
        "settings": {
            "digits": 3,
            "prefix": prefix,
            "sep": "-",
        }
    }

    yaml = _get_yaml()
    config_path = doc_dir / ".doorstop.yml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)

    return doc_dir


def get_next_item_number(doc_dir: Path) -> int:
    """
    Get the next available item number for a Doorstop document.

    Args:
        doc_dir: Path to Doorstop document directory.

    Returns:
        Next available item number.
    """
    existing_items = _find_item_files(doc_dir)
    max_num = 0

    for item_file in existing_items:
        try:
            num = int(item_file.stem)
            max_num = max(max_num, num)
        except ValueError:
            continue

    return max_num + 1


def create_new_item(
    item_type: ItemType,
    system_path: str,
    title: str,
    text: str,
    owner: str,
    category_path: str | None = None,
    l3: str | None = None,
    base_dir: Path | None = None,
    **kwargs: Any,
) -> BaseItem:
    """
    Create a new item with scaffolded defaults.

    Args:
        item_type: Type of item to create.
        system_path: L1/L2 system path (e.g., "FPS/FID").
        title: Item title.
        text: Item text/description.
        owner: Owner person ID.
        category_path: Category path (required for REQ, RSK, IFC).
        l3: Optional L3 task code.
        base_dir: Base directory. Defaults to project doorstop dir.
        **kwargs: Additional fields for the item.

    Returns:
        Created item (also saved to disk).
    """
    if base_dir is None:
        base_dir = get_project_root() / "doorstop"

    # Parse system path
    parts = system_path.split("/")
    if len(parts) != 2:
        raise ValueError(f"Invalid system_path format: {system_path}")
    l1, l2 = parts

    # Ensure document exists (use L3 folder if l3 is provided)
    doc_dir = create_doorstop_document(item_type.value, l1, l2, l3=l3, base_dir=base_dir)

    # Get next item number
    next_num = get_next_item_number(doc_dir)

    # Construct full ID (use L3 if provided)
    id_full = f"MUST-{l1}-{l3 or l2}-{item_type.value}-{next_num:03d}"

    # Build item data
    now = datetime.now(timezone.utc)
    data: dict[str, Any] = {
        "type": item_type.value,
        "id_full": id_full,
        "title": title,
        "text": text,
        "system_path": system_path,
        "owner": owner,
        "status": "draft",
        "created_at": now,
        "updated_at": now,
        "links": [],
        "tags": [],
        "references": [],
        "collaborators": [],
        "active": True,
        "derived": False,
        "normative": True,
    }

    if l3:
        data["l3"] = l3

    # Add type-specific fields
    if item_type == ItemType.REQ:
        data["category_path"] = category_path or "functional/observation"
        data["priority"] = "must"
        data["verified"] = False
        data["allocated_to"] = []

    elif item_type == ItemType.RSK:
        data["category_path"] = category_path or "technical/design"
        data["likelihood"] = 3
        data["consequence"] = 3
        data["risk_status"] = "identified"
        data["trigger_conditions"] = []

    elif item_type == ItemType.IFC:
        data["category_path"] = category_path or "mechanical/mounting"
        data["provider_system"] = system_path
        data["consumer_system"] = kwargs.get("consumer_system", "SPS/OPT")
        data["interface_status"] = "proposed"
        data["parameters"] = {}
        data["tolerances"] = {}

    elif item_type == ItemType.DOC:
        data["category_path"] = category_path or "report"
        data["document_type"] = "other"
        data["version"] = "1.0"
        data["authors"] = [owner]
        data["keywords"] = []

    elif item_type == ItemType.DAT:
        data["category_path"] = category_path or "measurement"
        data["data_type"] = "other"
        data["version"] = "1.0"
        data["key_results"] = {}

    elif item_type == ItemType.NOTE:
        data["category_path"] = category_path or "technical"
        data["note_type"] = "other"
        data["version"] = "1.0"
        data["authors"] = [owner]
        data["action_items"] = []
        data["options_considered"] = []
        data["attachments"] = []

    # Add any additional kwargs
    data.update(kwargs)

    # Create and validate item
    model_class = ITEM_TYPE_MODELS[item_type]
    item = model_class.model_validate(data)

    # Save to disk
    save_item(item, doc_dir)

    return item


def list_documents(base_dir: Path | None = None) -> list[dict[str, Any]]:
    """
    List all Doorstop documents in the repository.

    Args:
        base_dir: Base directory. Defaults to project doorstop dir.

    Returns:
        List of document information dictionaries.
    """
    if base_dir is None:
        base_dir = get_project_root() / "doorstop"

    docs = []
    for doc_path in _find_doorstop_documents(base_dir):
        config = _parse_doorstop_config(doc_path)
        item_count = len(_find_item_files(doc_path))
        system_path, l3 = _infer_hierarchy_context(doc_path)

        docs.append({
            "path": str(doc_path),
            "prefix": config.get("settings", {}).get("prefix", "UNKNOWN"),
            "item_count": item_count,
            "system_path": system_path,
            "l3": l3,
        })

    return docs

