"""
Generated modules for Qingsong.

This package contains dynamically generated code based on metadata files.

Design Decision:
----------------
Enums are generated dynamically at runtime when the metadata loader is invoked.
This approach was chosen over pre-generation because:
1. It ensures enums are always in sync with metadata
2. It doesn't require a separate build step
3. It works seamlessly with edits to metadata files

The enums.py module is generated on first import of the load_meta module.
"""

