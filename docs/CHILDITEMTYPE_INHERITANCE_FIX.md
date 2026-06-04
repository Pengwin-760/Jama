# Folder childItemType Dynamic Inheritance

## Issue
Previously, `JAMA_FOLDER_CHILD_ITEM_TYPE` was treated as a static required setting that had to be hardcoded in `.env` for each import:

```env
JAMA_FOLDER_CHILD_ITEM_TYPE=112  # Software Requirements
```

This only worked for Software Requirement imports. For other imports (Subsystem Requirements, Stakeholder Requirements), the value had to be manually changed.

## Solution
Updated `csv2jama.py` to make `JAMA_FOLDER_CHILD_ITEM_TYPE` a **fallback-only** setting. Folder `childItemType` is now determined dynamically with this priority:

### Priority Order

**1. Inherit from parent container (PREFERRED)**
- When creating a folder under "SW Requirements" (childItemType=112), new folder automatically uses 112
- When creating a folder under "Subsystem Requirements" (childItemType=87), new folder automatically uses 87
- This is the preferred and most common method

**2. Infer from next requirement row**
- If parent has no childItemType, look ahead at the first requirement under this folder
- Software Requirement row → 112
- Subsystem Requirement row → 87
- Stakeholder Requirement row → 97
- Text rows are skipped (they don't determine childItemType)

**3. Use .env fallback (last resort)**
- Only used if parent inheritance and inference both fail
- Typically only needed for empty root-level folders
- Optional - most imports won't need this

**4. Fail with clear error**
- If none of the above methods work, provide clear guidance

## Changes Made

### 1. Updated `import_excel()` (line 1773)
Added root parent metadata fetch before processing rows:

```python
if not dry_run and ROOT_PARENT_ITEM_ID not in _item_metadata_by_id:
    print(f"[INFO] Fetching root parent item metadata (ID: {ROOT_PARENT_ITEM_ID})...")
    root_response = jama_get(f"/items/{ROOT_PARENT_ITEM_ID}")
    root_item = root_response.get("data")
    if root_item:
        store_item_metadata(ROOT_PARENT_ITEM_ID, root_item)
```

This ensures folders created directly under root can inherit root's childItemType.

### 2. Updated `build_payload()` (line 1443)
Changed priority order from:
- ~~1) Inferred, 2) Inherited, 3) Fallback~~

To:
- **1) Inherited, 2) Inferred, 3) Fallback**

Added tracking of how childItemType was determined for logging.

### 3. Added childItemType Resolution Logging (line 2128)
When creating folders, the script now prints:

```text
[INFO] Folder childItemType resolved from parent metadata: 112
```

or:

```text
[INFO] Folder childItemType inferred from next requirement row: 87 (Subsystem Requirement)
```

or:

```text
[INFO] Folder childItemType using fallback JAMA_FOLDER_CHILD_ITEM_TYPE: 112
```

### 4. Updated Folder Resolution Logic (line 1960)
When resolving existing folders, also changed priority to inherit from parent first.

### 5. Updated Error Messages
Changed error messages to reflect new priority:
- "1. Inherit from parent container (no parent metadata or no childItemType)"
- "2. Infer from items under this folder (none found)"
- "3. Use fallback from .env (not configured)"

## Recommended .env.example Entry

```env
# ============================================================
# CHILD ITEM TYPE IDS (Optional Fallback)
# ============================================================
# childItemType represents what content a container (Set/Folder) holds.
#
# IMPORTANT: The script normally determines childItemType automatically:
#   1. Inherits from parent container (most common)
#   2. Infers from requirement rows under the folder
#
# These settings are FALLBACK ONLY - used only if both methods above fail.
# Most imports don't need these settings.
#
# Only set these if you have empty root-level folders with no parent to inherit from.
#
# Examples:
#   Software Requirement folders: 112
#   Subsystem Requirement folders: 87
#   Stakeholder Requirement folders: 97
#
# JAMA_FOLDER_CHILD_ITEM_TYPE=
# JAMA_SET_CHILD_ITEM_TYPE=
```

## Text Row Handling
Text rows are correctly skipped when inferring folder childItemType:

| Folder Contents                  | childItemType | Method      |
|----------------------------------|---------------|-------------|
| Text + Software Requirement      | 112           | Inference   |
| Text only (parent SW Req)        | 112           | Inheritance |
| Text only (no parent, no config) | Error         | Fail        |

## Behavior Examples

### Example 1: Software Requirements Import
```
Root: SW Requirements (childItemType=112)
  └─ Folder: 3. REQUIREMENTS (new)
      └─ Folder: 3.1 States (new)
```

Result:
- Folder "3. REQUIREMENTS": inherits childItemType=112 from root
- Folder "3.1 States": inherits childItemType=112 from "3. REQUIREMENTS"
- Log: `[INFO] Folder childItemType resolved from parent metadata: 112`

### Example 2: Subsystem Requirements Import
```
Root: Subsystem Requirements (childItemType=87)
  └─ Folder: 4. REQUIREMENTS (new)
```

Result:
- Folder "4. REQUIREMENTS": inherits childItemType=87 from root
- Log: `[INFO] Folder childItemType resolved from parent metadata: 87`

### Example 3: Mixed Content (Inference Fallback)
```
Root: Generic Container (no childItemType)
  └─ Folder: 5. REQUIREMENTS (new)
      └─ Text row
      └─ Subsystem Requirement row
```

Result:
- Parent has no childItemType → tries inference
- Text row skipped
- Next requirement found: Subsystem Requirement (87)
- Folder "5. REQUIREMENTS": uses childItemType=87
- Log: `[INFO] Folder childItemType inferred from next requirement row: 87 (Subsystem Requirement)`

### Example 4: Config Fallback
```
Root: Generic Container (no childItemType)
  └─ Folder: Empty Folder (new, no children)

.env: JAMA_FOLDER_CHILD_ITEM_TYPE=112
```

Result:
- Parent has no childItemType → tries inference
- No requirement rows found → tries fallback
- Uses JAMA_FOLDER_CHILD_ITEM_TYPE=112
- Log: `[INFO] Folder childItemType using fallback JAMA_FOLDER_CHILD_ITEM_TYPE: 112`

## Preserved Behavior
- Folder resolution by documentKey
- Missing folder creation (CREATE_MISSING_FOLDERS=true)
- Parent childItemType validation for requirement rows
- Text rows still have location.parent.item but no childItemType
- Dry-run remains default
- Simple commands:
  - `python csv2jama.py` (dry-run)
  - `python csv2jama.py --execute` (execute)

## Testing
```bash
# Syntax check
python3 -m py_compile csv2jama.py

# Dry-run to verify
python3 csv2jama.py

# Look for logs showing inheritance:
# [INFO] Fetching root parent item metadata (ID: 12345)...
# [INFO] Root parent childItemType: 112
# [INFO] Folder childItemType resolved from parent metadata: 112
```

## Files Changed
- `csv2jama.py` - Updated 5 sections:
  1. `import_excel()` - Added root metadata fetch
  2. `build_payload()` - Changed priority order for Set/Folder
  3. `build_payload()` - Changed priority order for Segment/Subsystem
  4. Row processing - Added childItemType resolution logging
  5. Folder resolution - Changed priority order
  6. Error messages - Updated to reflect new priority

## Result
✓ Software imports automatically use childItemType=112  
✓ Subsystem imports automatically use childItemType=87  
✓ Stakeholder imports automatically use childItemType=97  
✓ No manual `.env` changes needed between imports  
✓ `JAMA_FOLDER_CHILD_ITEM_TYPE` is truly optional now  
