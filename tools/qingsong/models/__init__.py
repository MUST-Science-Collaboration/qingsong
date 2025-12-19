"""
Pydantic models for Qingsong item types.

These models are the canonical schema definitions. All validation is done
through Pydantic, not separate JSON Schema files.
"""

from .common import (
    ItemType,
    Link,
    LifecycleStatus,
    BaseItem,
    RetirementInfo,
)
from .requirement import Requirement
from .risk import Risk
from .interface import Interface
from .document import Document
from .data import DataRecord
from .note import Note

__all__ = [
    "ItemType",
    "Link",
    "LifecycleStatus",
    "BaseItem",
    "RetirementInfo",
    "Requirement",
    "Risk",
    "Interface",
    "Document",
    "DataRecord",
    "Note",
]

# Type mapping for dynamic model selection
ITEM_TYPE_MODELS = {
    ItemType.REQ: Requirement,
    ItemType.RSK: Risk,
    ItemType.IFC: Interface,
    ItemType.DOC: Document,
    ItemType.DAT: DataRecord,
    ItemType.NOTE: Note,
}


def get_model_for_type(item_type: ItemType | str):
    """Get the appropriate Pydantic model class for an item type."""
    if isinstance(item_type, str):
        item_type = ItemType(item_type)
    return ITEM_TYPE_MODELS[item_type]

