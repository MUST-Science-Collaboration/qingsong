# Beginner's Guide to Qingsong

**A Professional System Engineer's Guide to Using Qingsong for MUST Project Management**

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Understanding the Qingsong Workflow](#understanding-the-qingsong-workflow)
3. [Working with Metadata Files](#working-with-metadata-files)
4. [Working with Vocabularies](#working-with-vocabularies)
5. [Creating and Managing Items](#creating-and-managing-items)
6. [Linking Items](#linking-items)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)
9. [Q&A](#qa)

---

## Getting Started

### Initial Setup

1. **Install Qingsong** (if not already done):
   ```bash
   cd /path/to/qingsong
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   ```

2. **Install pre-commit hooks** (recommended):
   ```bash
   pre-commit install
   ```

3. **Validate the repository**:
   ```bash
   qingsong meta validate    # Check metadata files
   qingsong validate         # Check all items
   ```

4. **Build the cache**:
   ```bash
   qingsong cache build
   ```

### Your First Validation

Always run validation after any changes:
```bash
qingsong meta validate && qingsong validate
```

If validation fails, fix the errors before proceeding.

---

## Understanding the Qingsong Workflow

### The Qingsong Philosophy

Qingsong follows a **"validate early, validate often"** approach:

```
┌─────────────────┐
│  Edit Metadata  │
│  or Items       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Validate       │
│  (meta validate)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Validate Items │
│  (validate)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Build Cache    │
│  (cache build)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Commit to Git  │
└─────────────────┘
```

### Key Principles

1. **Metadata is the foundation**: Changes to metadata affect all items
2. **Validation is mandatory**: Never commit invalid data
3. **Cache is derived**: Always rebuild after structural changes
4. **Git is your friend**: Commit frequently, validate before committing

---

## Working with Metadata Files

### Understanding Metadata Files

Metadata files define the **structure and rules** of your project:

- `meta/hierarchy.yaml` - Project organization (L0-L3)
- `meta/people.yaml` - Team directory
- `meta/glossary.yaml` - Terms and acronyms
- `meta/vocab/*.yaml` - Controlled vocabularies

### Workflow: Modifying `hierarchy.yaml`

**Scenario**: You need to add a new subsystem or reorganize the project structure.

#### Step 1: Edit the File

```yaml
# meta/hierarchy.yaml
systems:
  NEW_SYS:
    name: "New System"
    description: "Description here"
    owner: eng001
    subsystems:
      NEW_SUB:
        name: "New Subsystem"
        description: "Description"
        owner: eng001
        tasks:
          - NEW_SUB-TASK1
          - NEW_SUB-TASK2
```

**Important**: Also update `valid_system_paths` and `valid_l3_codes` lists!

```yaml
valid_system_paths:
  - "NEW_SYS/NEW_SUB"  # Add this

valid_l3_codes:
  - NEW_SUB-TASK1      # Add these
  - NEW_SUB-TASK2
```

#### Step 2: Validate Metadata

```bash
qingsong meta validate
```

**What this checks**:
- YAML syntax is valid
- All owner references exist in `people.yaml`
- System paths match the hierarchy structure
- L3 codes are defined in subsystem tasks

#### Step 3: Check for Impacted Items

```bash
# Find items that might be affected
qingsong query "SELECT id_full, system_path FROM items WHERE system_path NOT IN (SELECT system_path FROM meta_hierarchy)"
```

**What to look for**:
- Items with `system_path` that no longer exists → **ERROR**
- Items with `l3` codes that no longer exist → **WARNING**

#### Step 4: Fix or Migrate Items

**Option A: Items reference old system path**

If you renamed a system (e.g., `OLD_SYS/OLD_SUB` → `NEW_SYS/NEW_SUB`):

1. **Update items manually** or use a script:
   ```bash
   # Find affected items
   qingsong list --system OLD_SYS/OLD_SUB
   
   # Edit each item file in doorstop/REQ/OLD_SYS/OLD_SUB/
   # Change system_path to NEW_SYS/NEW_SUB
   ```

2. **Or use Python**:
   ```python
   from qingsong.core import QingsongCore
   
   core = QingsongCore.load()
   for item in core.get_items_by_system("OLD_SYS/OLD_SUB"):
       core.update_item(item.id_full, system_path="NEW_SYS/NEW_SUB")
   core.flush()  # Write changes
   ```

**Option B: Items have invalid L3 codes**

1. **Remove invalid L3**:
   ```python
   core = QingsongCore.load()
   invalid_l3 = ["OLD-L3-CODE"]
   for item in core.items.values():
       if item.l3 in invalid_l3:
           core.update_item(item.id_full, l3=None)
   core.flush()
   ```

2. **Or update to valid L3**:
   ```python
   # Map old L3 to new L3
   l3_mapping = {"OLD-L3-CODE": "NEW_SUB-TASK1"}
   for item in core.items.values():
       if item.l3 in l3_mapping:
           core.update_item(item.id_full, l3=l3_mapping[item.l3])
   core.flush()
   ```

#### Step 5: Re-validate Everything

```bash
qingsong meta validate
qingsong validate
```

#### Step 6: Rebuild Cache

```bash
qingsong cache build
```

#### Step 7: Commit

```bash
git add meta/hierarchy.yaml doorstop/
git commit -m "Add NEW_SYS/NEW_SUB subsystem"
```

---

### Workflow: Modifying `people.yaml`

**Scenario**: Adding a new team member or updating roles.

#### Step 1: Edit the File

```yaml
# meta/people.yaml
people:
  new_person:
    name: "New Person"
    email: "new.person@must.edu"
    role: "Engineer"
    organization: "MUST Engineering"
    systems:
      - FPS
      - SPS
    active: true

valid_person_ids:
  - new_person  # Add this
```

#### Step 2: Validate Metadata

```bash
qingsong meta validate
```

#### Step 3: Check for Impacted Items

**No items should be affected** by adding new people. However, if you:

- **Remove a person**: Check if they're referenced as owner/collaborator
- **Deactivate a person**: Items can still reference them (historical)

```bash
# Find items owned by a person
qingsong query "SELECT id_full, owner FROM items WHERE owner = 'old_person_id'"

# Find items with person as collaborator
qingsong query "SELECT id_full, collaborators FROM items WHERE collaborators LIKE '%old_person_id%'"
```

#### Step 4: Update Items (if person removed)

```python
from qingsong.core import QingsongCore

core = QingsongCore.load()

# Reassign ownership
for item in core.get_items_by_owner("old_person_id"):
    core.update_item(item.id_full, owner="new_person_id")

# Remove from collaborators
for item in core.items.values():
    if "old_person_id" in item.collaborators:
        new_collabs = [c for c in item.collaborators if c != "old_person_id"]
        core.update_item(item.id_full, collaborators=new_collabs)

core.flush()
```

#### Step 5: Validate and Commit

```bash
qingsong validate
qingsong cache build
git add meta/people.yaml doorstop/
git commit -m "Add new team member"
```

---

## Working with Vocabularies

### Understanding Vocabularies

Vocabularies define **controlled lists** of valid values:

- `meta/vocab/status.yaml` - Item lifecycle status
- `meta/vocab/req_category.yaml` - Requirement categories
- `meta/vocab/risk_category.yaml` - Risk categories
- `meta/vocab/ifc_type.yaml` - Interface types
- `meta/vocab/link_types.yaml` - Relationship types

### Workflow: Modifying `req_category.yaml`

**Scenario**: Adding a new requirement category or reorganizing the taxonomy.

#### Step 1: Edit the File

```yaml
# meta/vocab/req_category.yaml
categories:
  new_category:
    label: "New Category"
    description: "New category for requirements"
    subcategories:
      new_subcat:
        label: "New Subcategory"
        description: "Description"

valid_paths:
  - "new_category/new_subcat"  # Add this
```

#### Step 2: Validate Metadata

```bash
qingsong meta validate
```

#### Step 3: Check for Impacted Items

```bash
# Find items using old category paths
qingsong query "SELECT id_full, category_path FROM items WHERE type = 'REQ' AND category_path NOT IN (SELECT value FROM meta_vocab WHERE vocab_name = 'req_category')"
```

**What to look for**:
- Items with `category_path` that no longer exists → **ERROR**
- Items that should be migrated to new categories

#### Step 4: Migrate Items (if needed)

**Option A: Category was renamed**

```python
from qingsong.core import QingsongCore

core = QingsongCore.load()

# Map old categories to new
category_mapping = {
    "old_category/old_subcat": "new_category/new_subcat",
    "functional/obs": "functional/observation",  # Abbreviation expanded
}

for item in core.get_items_by_type("REQ"):
    if item.category_path in category_mapping:
        core.update_item(item.id_full, category_path=category_mapping[item.category_path])

core.flush()
```

**Option B: Category was removed (deprecated)**

1. **Decide on migration strategy**:
   - Map to closest equivalent category
   - Create "legacy" category for historical items
   - Mark items as retired

2. **Migrate**:
   ```python
   # Option 1: Map to equivalent
   deprecated_mapping = {
       "old_category/deprecated": "functional/observation",
   }
   
   # Option 2: Create legacy category (add to vocab first!)
   legacy_mapping = {
       "old_category/deprecated": "legacy/deprecated",
   }
   
   # Option 3: Retire items
   for item in items_with_deprecated_category:
       core.retire_item(
           item.id_full,
           reason="Category deprecated",
           retired_by="ps001",
       )
   ```

#### Step 5: Validate

```bash
qingsong validate
```

**Expected errors**:
- Items with invalid `category_path` → Fix by migration

#### Step 6: Rebuild Cache

```bash
qingsong cache build
```

#### Step 7: Commit

```bash
git add meta/vocab/req_category.yaml doorstop/
git commit -m "Add new requirement category and migrate items"
```

---

### Workflow: Modifying `link_types.yaml`

**Scenario**: Adding a new link type or changing link type constraints.

#### Step 1: Edit the File

```yaml
# meta/vocab/link_types.yaml
link_types:
  new_link_type:
    label: "New Link Type"
    description: "New relationship type"
    reverse_label: "Reverse Label"
    allowed_source_types:
      - REQ
      - DOC
    allowed_target_types:
      - REQ
    cardinality: "many-to-many"
```

#### Step 2: Validate Metadata

```bash
qingsong meta validate
```

#### Step 3: Check for Impacted Links

**Adding a new link type**: No impact on existing items.

**Changing constraints**: Check existing links that violate new rules.

```bash
# Find links that would violate new constraints
qingsong query """
SELECT l.source_id, l.target_id, l.link_type, 
       i1.type as source_type, i2.type as target_type
FROM links l
JOIN items i1 ON l.source_id = i1.id_full
JOIN items i2 ON l.target_id = i2.id_full
WHERE l.link_type = 'modified_link_type'
  AND (i1.type NOT IN ('REQ', 'DOC') OR i2.type != 'REQ')
"""
```

#### Step 4: Fix Invalid Links

**Option A: Remove invalid links**

```python
from qingsong.core import QingsongCore

core = QingsongCore.load()

# Find items with invalid links
for item in core.items.values():
    valid_links = []
    for link in item.links:
        if link.link_type == "modified_link_type":
            # Check if link is still valid
            target = core.items.get(link.target_id)
            if target and is_link_valid(item, target, link.link_type, core.metadata):
                valid_links.append(link)
            # Otherwise, skip (remove invalid link)
        else:
            valid_links.append(link)
    
    if len(valid_links) != len(item.links):
        core.update_item(item.id_full, links=valid_links)

core.flush()
```

**Option B: Change link type**

```python
# Change invalid links to "related_to" (most permissive)
for item in core.items.values():
    updated_links = []
    for link in item.links:
        if link.link_type == "modified_link_type":
            target = core.items.get(link.target_id)
            if not is_link_valid(item, target, link.link_type, core.metadata):
                # Change to related_to
                link.link_type = "related_to"
        updated_links.append(link)
    
    if updated_links != item.links:
        core.update_item(item.id_full, links=updated_links)

core.flush()
```

#### Step 5: Validate

```bash
qingsong validate
```

#### Step 6: Commit

```bash
git add meta/vocab/link_types.yaml doorstop/
git commit -m "Add new link type and fix invalid links"
```

---

## Creating and Managing Items

### Creating a New Requirement

```bash
qingsong new req \
  --title "Detector Readout Speed" \
  --system SPS/DET \
  --owner eng002 \
  --text "The detector shall read out at 100 kpixel/s" \
  --category performance/throughput \
  --l3 DET-ELEC
```

**What happens**:
1. Creates new YAML file in `doorstop/REQ/SPS/DET/`
2. Assigns next available number (e.g., `MUST-SPS-DET-REQ-002`)
3. Sets defaults: `status=draft`, timestamps, empty links

**Next steps**:
```bash
# Validate the new item
qingsong validate

# View it
qingsong show MUST-SPS-DET-REQ-002

# Edit manually if needed
# File: doorstop/REQ/SPS/DET/002.yml
```

### Creating a New Risk

```bash
qingsong new rsk \
  --title "Detector Cooling Failure" \
  --system SPS/DET \
  --owner eng002 \
  --text "Risk that cryogenic cooling system fails" \
  --category technical/design
```

**Then edit the file** to add:
- `likelihood` (1-5)
- `consequence` (1-5)
- `mitigation_strategy`
- etc.

### Creating a New Interface

```bash
qingsong new ifc \
  --title "Detector-to-Readout Interface" \
  --system SPS/DET \
  --owner eng002 \
  --text "Interface between detector and readout electronics" \
  --category electrical/signal
```

**Then edit the file** to add:
- `provider_system` and `consumer_system`
- `parameters` and `tolerances`
- etc.

---

## Linking Items

### Understanding Links

Links create **relationships** between items with semantic meaning.

### Creating Links

**Method 1: Edit YAML file directly**

```yaml
# doorstop/REQ/SPS/DET/001.yml
links:
  - target_id: MUST-FPS-FID-IFC-001
    link_type: related_to
    description: "Related to fiber interface"
```

**Method 2: Use Python API**

```python
from qingsong.core import QingsongCore
from qingsong.models import Link

core = QingsongCore.load()

item = core.get_item("MUST-SPS-DET-REQ-001")
new_link = Link(
    target_id="MUST-FPS-FID-IFC-001",
    link_type="related_to",
    description="Related to fiber interface"
)

updated_links = list(item.links) + [new_link]
core.update_item(item.id_full, links=updated_links)
core.flush()
```

### Link Validation Rules

Links are validated against `link_types.yaml`:

- **Source type constraint**: Item type must be in `allowed_source_types`
- **Target type constraint**: Target item type must be in `allowed_target_types`
- **Same type only**: Some links require source and target to be same type

**Example**: `implements` link
- Source: DOC, DAT, or NOTE
- Target: REQ
- ❌ REQ → REQ (invalid)
- ✅ DOC → REQ (valid)

### Finding Linked Items

```bash
# Show item with its links
qingsong show MUST-FPS-FID-RSK-001

# Query links
qingsong query "SELECT * FROM links WHERE source_id = 'MUST-FPS-FID-RSK-001'"

# Find all items linked to a requirement
qingsong query """
SELECT DISTINCT source_id, link_type
FROM links
WHERE target_id = 'MUST-FPS-FID-REQ-001'
"""
```

---

## Best Practices

### 1. Always Validate Before Committing

```bash
# Standard workflow
qingsong meta validate && qingsong validate && git commit
```

### 2. Use Pre-commit Hooks

```bash
pre-commit install
```

This automatically runs validation before commits.

### 3. Rebuild Cache After Structural Changes

After modifying:
- `hierarchy.yaml` (system paths, L3 codes)
- `people.yaml` (if removing people)
- `vocab/*.yaml` (categories, link types)

Always run:
```bash
qingsong cache build
```

### 4. Use Git Branches for Major Changes

```bash
# Create branch for metadata changes
git checkout -b update-hierarchy

# Make changes
# ... edit hierarchy.yaml ...

# Validate
qingsong meta validate
qingsong validate

# Test migration
# ... migrate items ...

# Validate again
qingsong validate

# Commit
git commit -m "Update hierarchy and migrate items"
```

### 5. Document Changes

When making significant changes, document:
- What changed
- Why it changed
- Migration strategy
- Items affected

### 6. Regular Validation

Run validation regularly:
```bash
# Daily check
qingsong validate

# Before major work
qingsong meta validate && qingsong validate
```

### 7. Use the UI for Exploration

```bash
qingsong ui
```

The UI is great for:
- Browsing items
- Finding relationships
- Understanding the project structure

---

## Troubleshooting

### Problem: Validation Fails After Metadata Change

**Symptoms**:
```
Error: System path 'OLD_SYS/OLD_SUB' not found in hierarchy
```

**Solution**:
1. Check if you forgot to update `valid_system_paths`
2. Check if items need migration
3. Run: `qingsong query "SELECT id_full, system_path FROM items WHERE system_path = 'OLD_SYS/OLD_SUB'"`

### Problem: Items Have Invalid Category Paths

**Symptoms**:
```
Error: Category path 'old/category' not found in req_category vocabulary
```

**Solution**:
1. Check if category was removed or renamed
2. Migrate items to valid categories
3. Or add category back to vocabulary (if it was removed by mistake)

### Problem: Links Fail Validation

**Symptoms**:
```
Error: Link type 'implements' does not allow source type 'REQ'
```

**Solution**:
1. Check `link_types.yaml` for allowed types
2. Change link type to valid one (e.g., `related_to`)
3. Or remove the link if not needed

### Problem: Cache is Out of Date

**Symptoms**:
- Queries return old data
- UI shows incorrect counts

**Solution**:
```bash
qingsong cache build
```

### Problem: Can't Find Items After System Path Change

**Solution**:
```bash
# Search by old path (if items weren't migrated)
qingsong list --system OLD_SYS/OLD_SUB

# Or query cache
qingsong query "SELECT * FROM items WHERE system_path LIKE '%OLD%'"
```

---

## Q&A

### Q1: I modified `hierarchy.yaml` to add a new subsystem. What should I do next?

**A**: Follow this checklist:

1. ✅ **Update `valid_system_paths`** - Add the new system path
2. ✅ **Update `valid_l3_codes`** - Add any new L3 task codes
3. ✅ **Validate metadata**: `qingsong meta validate`
4. ✅ **Check for impacted items**: Look for items with old system paths
5. ✅ **Migrate items** (if needed): Update `system_path` in affected items
6. ✅ **Validate items**: `qingsong validate`
7. ✅ **Rebuild cache**: `qingsong cache build`
8. ✅ **Commit**: `git add meta/hierarchy.yaml doorstop/ && git commit`

### Q2: I removed a person from `people.yaml`. Will this break existing items?

**A**: It depends:

- **If person is `owner`**: Items will fail validation. You must:
  1. Find items: `qingsong query "SELECT id_full FROM items WHERE owner = 'removed_person'"`
  2. Reassign ownership: Update items to use a valid person ID
  3. Validate: `qingsong validate`

- **If person is `collaborator`**: Items will fail validation. You must:
  1. Find items: `qingsong query "SELECT id_full, collaborators FROM items WHERE collaborators LIKE '%removed_person%'"`
  2. Remove from collaborators: Update items to remove the person ID
  3. Validate: `qingsong validate`

- **If person is just `deactivated`** (not removed): Items remain valid (historical record).

### Q3: I changed a requirement category in `req_category.yaml`. How do I migrate existing items?

**A**: Use this workflow:

1. **Identify affected items**:
   ```bash
   qingsong query "SELECT id_full, category_path FROM items WHERE type = 'REQ' AND category_path = 'old/category'"
   ```

2. **Create migration mapping**:
   ```python
   category_mapping = {
       "old/category": "new/category",
   }
   ```

3. **Migrate items**:
   ```python
   from qingsong.core import QingsongCore
   
   core = QingsongCore.load()
   for item in core.get_items_by_type("REQ"):
       if item.category_path in category_mapping:
           core.update_item(
               item.id_full,
               category_path=category_mapping[item.category_path]
           )
   core.flush()
   ```

4. **Validate**: `qingsong validate`

### Q4: I added a new link type to `link_types.yaml`. Do I need to do anything?

**A**: No immediate action needed! New link types don't affect existing items. However:

- **If you changed constraints** for an existing link type:
  1. Check for invalid links: `qingsong validate`
  2. Fix or remove invalid links
  3. Validate again

### Q5: How do I safely rename a system path (e.g., `FPS/FID` → `FPS/FIBER`)?

**A**: Follow this migration process:

1. **Add new system path** to `hierarchy.yaml` (keep old one temporarily)
2. **Update items** to use new path:
   ```python
   core = QingsongCore.load()
   for item in core.get_items_by_system("FPS/FID"):
       # Update system_path
       core.update_item(item.id_full, system_path="FPS/FIBER")
       
       # Update ID if needed (optional, but recommended)
       # Old: MUST-FPS-FID-REQ-001
       # New: MUST-FPS-FIBER-REQ-001
       # This requires manual file renaming
   core.flush()
   ```

3. **Rename Doorstop directories**:
   ```bash
   mv doorstop/REQ/FPS/FID doorstop/REQ/FPS/FIBER
   mv doorstop/RSK/FPS/FID doorstop/RSK/FPS/FIBER
   # etc.
   ```

4. **Update `.doorstop.yml` files** with new prefix:
   ```yaml
   settings:
     prefix: MUST-FPS-FIBER-REQ  # Changed from MUST-FPS-FID-REQ
   ```

5. **Remove old system path** from `hierarchy.yaml`
6. **Validate**: `qingsong meta validate && qingsong validate`
7. **Rebuild cache**: `qingsong cache build`

### Q6: What happens if I delete a vocabulary value that's in use?

**A**: Items using that value will **fail validation**. You have two options:

**Option 1: Migrate items** (recommended)
- Map old value to new value
- Update all items
- Validate

**Option 2: Keep value for legacy items**
- Add value back to vocabulary
- Mark as deprecated in description
- Use for historical items only

### Q7: How do I check if my changes will break anything before committing?

**A**: Use this validation workflow:

```bash
# 1. Validate metadata
qingsong meta validate

# 2. Validate all items
qingsong validate

# 3. Check for specific issues
qingsong query "SELECT id_full, system_path FROM items WHERE system_path NOT IN (SELECT system_path FROM meta_hierarchy)"

# 4. If all pass, commit
git add .
git commit -m "Your changes"
```

### Q8: Can I undo a metadata change?

**A**: Yes, using Git:

```bash
# View changes
git diff meta/hierarchy.yaml

# Undo changes
git checkout meta/hierarchy.yaml

# Or revert entire commit
git revert HEAD
```

**Important**: After reverting, you may need to:
1. Revert item changes too (if items were migrated)
2. Rebuild cache: `qingsong cache build`

### Q9: How often should I rebuild the cache?

**A**: Rebuild when:
- ✅ After modifying metadata files
- ✅ After adding/removing many items
- ✅ Before running queries
- ✅ When UI shows incorrect data

**Not needed** for:
- ❌ Adding a single item
- ❌ Editing item text (content changes)
- ❌ Minor link updates

### Q10: What's the difference between `qingsong meta validate` and `qingsong validate`?

**A**:
- **`qingsong meta validate`**: Validates metadata files only (hierarchy, people, vocab)
  - Checks YAML syntax
  - Checks internal consistency
  - Does NOT check items

- **`qingsong validate`**: Validates all items
  - Checks item schemas (Pydantic)
  - Checks referential integrity (owners, systems, categories)
  - Checks links
  - Uses metadata for validation rules

**Always run both** after metadata changes!

---

## Summary Checklist

When making changes to Qingsong, use this checklist:

### Metadata Changes
- [ ] Edit metadata file(s)
- [ ] Update related lists (valid_system_paths, valid_l3_codes, etc.)
- [ ] Run `qingsong meta validate`
- [ ] Check for impacted items
- [ ] Migrate items if needed
- [ ] Run `qingsong validate`
- [ ] Run `qingsong cache build`
- [ ] Commit changes

### Vocabulary Changes
- [ ] Edit vocabulary file
- [ ] Update `valid_paths` or `valid_values`
- [ ] Run `qingsong meta validate`
- [ ] Check for items using old values
- [ ] Migrate items if needed
- [ ] Run `qingsong validate`
- [ ] Run `qingsong cache build`
- [ ] Commit changes

### Item Changes
- [ ] Create/edit items
- [ ] Run `qingsong validate`
- [ ] Commit changes

### Link Changes
- [ ] Add/edit links
- [ ] Run `qingsong validate` (checks link constraints)
- [ ] Commit changes

---

**Remember**: When in doubt, validate! `qingsong validate` is your friend.

