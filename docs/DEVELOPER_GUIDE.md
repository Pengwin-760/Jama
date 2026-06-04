# Developer Guide

This guide provides technical details for developers working on csv2jama.py. For end-user documentation, see USAGE.md.

## Table of Contents

1. [Verification Method](#verification-method)
2. [Global ID Lookup](#global-id-lookup)
3. [Folder Resolution & childItemType](#folder-resolution--childitemtype)
4. [Section Hierarchy](#section-hierarchy)
5. [Duplicate Prevention](#duplicate-prevention)
6. [Text Items](#text-items)
7. [API Configuration](#api-configuration)

---

## Verification Method

### Overview

Verification Method is a Jama picklist field with item-type-specific suffixes (e.g., `verification_method$112`, `verification_method$243`). The suffix changes based on the item type and project configuration.

### Picklist IDs

```python
VERIFICATION_METHOD_MAP = {
    422: "Test",
    420: "Inspection",
    419: "Demonstration",
    418: "Analysis",
}
```

### Payload Format

The field expects a **list** of picklist option IDs:

```json
{
  "verification_method$112": [422]
}
```

### Aliases

The script accepts shorthand aliases in Excel:

```python
VERIFICATION_METHOD_ALIASES = {
    "T": "Test",
    "I": "Inspection",
    "D": "Demonstration",
    "A": "Analysis",
    "TEST": "Test",
    "INSPECTION": "Inspection",
    "DEMONSTRATION": "Demonstration",
    "DEMO": "Demonstration",
    "ANALYSIS": "Analysis",
}
```

All aliases are **case-insensitive**.

### Field Discovery Strategy

The script uses a **dynamic field discovery** approach to find the correct field key:

**Priority A: Explicit .env configuration**
```bash
JAMA_FIELD_VERIFICATION_METHOD=verification_method$243
```

**Priority B: Type-specific search**
- Search cached items with matching `itemType` for fields matching `^verification_method\$\d+$`
- Use the field if exactly one match found

**Priority C: Project-wide search**
- If no type-specific match, search all cached items
- Use the field if exactly one match found (with warning)
- Fail if multiple candidates exist

### Field Pattern

```python
VERIFICATION_FIELD_PATTERN = re.compile(r"^verification_method\$\d+$", re.IGNORECASE)
```

Examples:
- `verification_method$112` → Valid
- `verification_method$86` → Valid
- `verification_method` → Invalid (no suffix)

### Processing Flow

1. **Normalize Excel value**: `normalize_verification_method(value)` converts aliases to canonical form
2. **Map to picklist ID**: `get_verification_method_picklist_id(canonical)` returns the numeric ID
3. **Resolve field key**: `resolve_verification_method_field_key(item_type_name, item_type_id)` discovers the correct field
4. **Format payload**: `format_verification_method_value(picklist_id)` wraps ID in array `[422]`
5. **Add to fields**: `fields[verification_field_key] = [picklist_id]`

### Error Scenarios

**Multiple type-specific fields found:**
```
Row has Verification Method populated, but multiple verification method field keys found for Software Requirement (itemType=112):
  verification_method$112, verification_method$243

Solution: Set JAMA_FIELD_VERIFICATION_METHOD in .env to the correct key.
```

**No field found in cache:**
```
Row has Verification Method populated, but no verification method field keys found in cached Jama items.

The target Set may be empty, or no existing project item exposes the verification method field.

Solution: Either:
  1. Ensure the project cache includes items with verification method fields
  2. Set JAMA_FIELD_VERIFICATION_METHOD in .env to the correct key
```

---

## Global ID Lookup

### Pattern

Global IDs follow the pattern `GID-\d+`:

```python
GLOBAL_ID_PATTERN = re.compile(r'GID-\d+', re.IGNORECASE)
```

Examples:
- `GID-768902` → Valid
- `GID-123456` → Valid
- `gid-768902` → Valid (case-insensitive)

### Extraction from HYPERLINK Formulas

The script extracts Global IDs from Excel HYPERLINK formulas:

```excel
=HYPERLINK("https://jama.example.com/perspective.req#/items/123456","GID-768902")
```

The `extract_global_id_from_value()` function handles:
- Raw GID values: `"GID-768902"`
- HYPERLINK formulas: Extracts GID from display text

### Lookup Process

1. **Cache population**: `build_folder_document_key_cache()` indexes all items by Global ID
2. **Duplicate detection**: Items with duplicate Global IDs are tracked separately
3. **Lookup**: `find_existing_item_by_global_id(global_id)` searches the cache
4. **Validation**: `validate_item_type_match()` ensures resolved item type matches Excel

### Resolution Priority

For all item types:
1. Jama ID (explicit in Excel)
2. Global ID (if `USE_GLOBAL_ID_LOOKUP=true`)
3. Document Key (column value)
4. Excel ID as documentKey (for folders)

### Duplicate Handling

If multiple items have the same Global ID:

```python
if global_id_str in _items_by_global_id_duplicates:
    raise ValueError(
        f"Global ID '{global_id_str}' matched {duplicate_count} items. "
        f"Please provide explicit Jama ID to resolve ambiguity."
    )
```

---

## Folder Resolution & childItemType

### What is childItemType?

`childItemType` specifies the **content type** allowed inside a container (Set/Folder/Segment/Subsystem).

**Important distinction:**
- `itemType`: The type of the container itself (e.g., 32 = Folder)
- `childItemType`: The type of items the container can hold (e.g., 112 = Software Requirement)

### Why Folders Become Active Parents

When a Folder row is processed:
1. The folder becomes the **current parent** (`current_folder_item_id`)
2. All subsequent requirement rows go under this folder
3. Remains active until another folder/section is encountered

### childItemType Resolution Priority

**Priority 1: Inherit from parent container** (PREFERRED)
```python
if parent_metadata:
    inherited_child_type = parent_metadata.get("childItemType")
    if inherited_child_type:
        payload["childItemType"] = inherited_child_type
```

**Priority 2: Infer from lookahead**
```python
inferred_child_type = infer_folder_child_item_type(df, row_pos)
```
Looks at the next requirement row under the folder and uses its `itemType`.

**Priority 3: General fallback config**
```bash
DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE=112
```

**Priority 4: Folder-specific fallback** (legacy)
```bash
JAMA_FOLDER_CHILD_ITEM_TYPE=112
```

### Lookahead Logic

The `infer_folder_child_item_type()` function:
1. Starts at the folder's position in the DataFrame
2. Scans forward until it finds a requirement row
3. Skips:
   - Child containers (continue scanning)
   - Text items (don't determine childItemType)
   - Sibling/unrelated sections (stop scanning)
4. Returns the `itemType` of the first requirement found

### Compatibility Validation

When resolving an existing folder, the script validates childItemType compatibility:

```python
validate_folder_child_item_type_compatibility(
    found_folder, expected_child_type, name, resolution_method
)
```

If incompatible:
```
Folder resolved by documentKey has incompatible childItemType.
Folder: 'External Interfaces'
Jama ID: 123456
Existing childItemType: 87 (Subsystem Requirement)
Expected childItemType: 112 (Software Requirement)

This folder cannot hold the expected content type.
Either use a different folder or update the folder's childItemType in Jama.
```

### Folder Resolution Methods

1. **Jama ID**: Explicit ID in Excel
2. **Global ID**: `USE_GLOBAL_ID_LOOKUP=true`
3. **Document Key column**: Explicit documentKey value
4. **Excel ID as documentKey**: `USE_EXCEL_ID_AS_DOCUMENT_KEY=true`
5. **Parent+itemType+name**: `ENABLE_PRE_POST_DUPLICATE_CHECK=true`

Each method validates childItemType compatibility before resolving.

---

## Section Hierarchy

### Section Number Extraction

The `extract_section_number()` function recognizes:

**Pattern 1: "Section X.Y.Z"**
```
"Section 1.0" → "1.0"
"Folder Section 1.1" → "1.1"
"(U) Section 1.1.1 Signal Processing" → "1.1.1"
```

**Pattern 2: Number at start (after optional classification)**
```
"3.2.1 External Interfaces" → "3.2.1"
"(U) 3.2 Requirements" → "3.2"
"3. REQUIREMENTS" → "3."
"3 REQUIREMENTS" → "3"
```

**Anti-patterns (NOT matched):**
```
"UAI / 1553 Interface" → None (number in middle)
"MIL-STD-1553 Requirements" → None (large number > 99)
```

### Top-Level Normalization

All top-level sections normalize to `.0` format:

```python
normalize_top_level_section("3") → "3.0"
normalize_top_level_section("3.") → "3.0"
normalize_top_level_section("3.0") → "3.0"
normalize_top_level_section("3.1") → "3.1"  # No change
```

This allows Excel files to use any of these forms:
- `3 REQUIREMENTS`
- `3. REQUIREMENTS`
- `3.0 REQUIREMENTS`

### Parent Determination

```python
get_parent_section_number("1.0") → None
get_parent_section_number("1.1") → "1.0"
get_parent_section_number("1.1.1") → "1.1"
get_parent_section_number("3.2.4") → "3.2"
```

### Hierarchy Tracking

The script maintains a `folder_by_section` dictionary:

```python
folder_by_section = {
    "1.0": 12345,    # Section 1.0 → Jama ID 12345
    "1.1": 12346,    # Section 1.1 → Jama ID 12346
    "1.1.1": 12347,  # Section 1.1.1 → Jama ID 12347
}
```

Parent determination:
1. Extract section number from folder name
2. Normalize to standard form
3. Calculate parent section
4. Look up parent Jama ID in `folder_by_section`
5. Use `ROOT_PARENT_ITEM_ID` if no parent section

---

## Duplicate Prevention

### Pre-POST Duplicate Check

Enabled by `ENABLE_PRE_POST_DUPLICATE_CHECK=true` (default).

### Matching Strategy

The `find_existing_item_by_parent_type_name()` function searches for items matching:
1. **Parent ID**: `location.parent.item`
2. **Item Type ID**: `itemType`
3. **Normalized Name**: `fields.name` (whitespace-collapsed)
4. **childItemType** (optional): For folders

### Name Normalization

```python
normalize_for_match("  External  Interfaces  ") → "External Interfaces"
normalize_for_match("Test\n\nData") → "Test Data"
```

- Strips leading/trailing whitespace
- Collapses internal whitespace to single spaces

### When It Runs

1. **Before folder creation**: If documentKey lookup fails
2. **Folder resolution**: Last resort before creating new folder

### Error Handling

**If multiple matches found:**
```
Found 3 items matching parent=12345, itemType=32 (Folder), name='External Interfaces'.
Matching item IDs: 67890, 67891, 67892

Cannot determine which item to use. Provide explicit Jama ID to resolve ambiguity.
```

### Cache Requirements

The duplicate check requires:
- `build_folder_document_key_cache()` called first
- `_item_metadata_by_id` populated

The cache is built automatically on first import.

---

## Text Items

### Special Characteristics

Text items have:
- `location.parent.item` (like requirements)
- **No** `childItemType` (unlike containers)

### Validation Rules

Text items are **exempt** from strict parent childItemType validation:

```python
if item_type_name in ("Text", "Text Document"):
    print(f"[INFO] Text item: no childItemType, but location.parent.item is required")
    return  # Skip childItemType validation
```

### Why This Matters

Jama allows Text items in document trees with special placement rules. The script lets Jama API accept/reject Text placement rather than enforcing childItemType matching.

---

## API Configuration

### Pagination

```python
JAMA_ITEMS_PAGE_SIZE = 50  # Max allowed by Jama
```

Jama API caps `maxResults` at 50. The script clamps any higher value:

```python
if page_size > 50:
    print(f"[WARN] JAMA_ITEMS_PAGE_SIZE={page_size} exceeds Jama max of 50. Clamping to 50.")
    page_size = 50
```

### Timeouts

```python
JAMA_API_TIMEOUT = 60       # Standard API calls
OAUTH_TOKEN_TIMEOUT = 30    # OAuth token requests
```

### Rate Limiting

```python
API_CALL_DELAY_SECONDS = 0.2  # 200ms between calls
```

Used between individual item creation calls to avoid hammering the server.

### Dry-Run IDs

```python
DRY_RUN_ID_START = 900000
```

Fake IDs assigned in dry-run mode start at 900000 and increment.

### Cache Suppression

During cache build, `DEBUG_JAMA_GET` is temporarily suppressed to avoid excessive logging:

```python
original_debug_get = CONFIG.get("DEBUG_JAMA_GET", False)
if original_debug_get:
    CONFIG["DEBUG_JAMA_GET"] = False
try:
    # Build cache...
finally:
    CONFIG["DEBUG_JAMA_GET"] = original_debug_get
```

---

## Field Mapping

### Required Fields

```python
FIELD_MAP = {
    "name": "name",           # Required by Jama API
    "description": "description",
    "id": None,               # Optional: Excel ID → Jama custom field
    "verification_method": None  # Dynamic discovery
}
```

### Field Validation

POST payloads **must** include `fields.name`:

```python
if "name" not in fields or not str(fields.get("name", "")).strip():
    raise ValueError(
        f"POST payload missing required fields.name. "
        f"Check JAMA_FIELD_NAME in .env; it must normally be 'name'."
    )
```

### Description Handling

Description is **optional** for structure types (Set, Folder, Segment, Subsystem):

```python
if description:
    fields[FIELD_MAP["description"]] = description
```

Only **requirement rows** require descriptions.

---

## Item Type Classifications

### Requirement Types

```python
REQUIREMENT_ITEM_TYPES = {
    "Stakeholder Requirement",
    "Subsystem Requirement",
    "Software Requirement",
    "System Requirement",  # Legacy, requires mapping
}
```

### Structure Types

```python
STRUCTURE_ITEM_TYPES = {
    "Set",
    "Folder",
    "Segment",
    "Subsystem",  # Alias of Set
}
```

### Special Aliases

```python
"Text Document" → "Text"  # itemType=33
"Subsystem" → "Set"       # itemType=31 (uses Set ID)
```
