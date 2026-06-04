# API Restriction: GET and POST Only (No PUT)

## Date
2026-06-03

## Important Change

The Jama API workflow used by this importer **does NOT support PUT** for updates.

The script now only uses:
- **GET /items** - Lookup existing items
- **POST /items** - Create new items

**PUT /items/{id}** is NOT supported and has been disabled.

## What Changed

### 1. PUT Function Disabled

**`jama_put()` function:**
```python
def jama_put(item_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    NOTE: PUT is NOT supported in this workflow.
    This function is preserved for reference but should not be called.
    """
    raise NotImplementedError(
        "PUT /items is not supported in this workflow. "
        "This importer only supports GET (lookup) and POST (create)."
    )
```

**Result:** Calling `jama_put()` will raise an error immediately.

### 2. Update Mode Disabled

**Import modes:**
```python
# Fails immediately on startup
if config["IMPORT_MODE"] == "update":
    print("[ERROR] Update mode is not supported because this API workflow does not support PUT.")
    sys.exit(1)
```

**Allowed modes:**
- ✅ `create` - Create new items only
- ✅ `upsert` - Create new + resolve existing (no updates)
- ❌ `update` - NOT SUPPORTED (fails at startup)

### 3. Existing Items Behavior Changed

#### For Containers (Set, Folder, Segment, Subsystem)

**Before (incorrect):**
```
action = RESOLVE
is_update = True
Calls jama_put() to update the item
```

**After (correct):**
```
action = RESOLVE
Register as parent container only
No API call made (no POST, no PUT)
```

**Output:**
```
[INFO] Resolved existing folder by documentKey 'EGL_CV-FLD-211' -> Jama ID 1175461
[INFO] Existing folder will be registered as parent container. No update will be performed.
[OK] Resolved existing Folder by document_key -> Jama ID 1175461
[OK] Existing item registered as parent container. No update performed.
```

#### For Requirements

**Before (incorrect):**
```
action = UPDATE
Attempts jama_put() which would fail
```

**After (correct):**
```
action = SKIP
status = SKIPPED_UPDATE_UNSUPPORTED
No API call made
```

**Output:**
```
[SKIP] Existing Stakeholder Requirement has Jama ID 123456
[SKIP] Update is not supported because PUT is not available in this workflow.
```

## Workflow Behavior

### Scenario 1: New Folder Without Jama ID

**Spreadsheet:**
```
ID              | Item Type | Name                    | Jama ID
EGL_CV-FLD-220  | Folder    | UAI Interface Reqs      | (blank)
```

**Cache lookup:** Not found

**Mode: upsert**
```
action = CREATE
POST /items (create new folder)
Register new Jama ID as parent
```

### Scenario 2: Existing Folder Found by documentKey

**Spreadsheet:**
```
ID              | Item Type | Name                    | Jama ID
EGL_CV-FLD-211  | Folder    | Launch Requirements     | (blank)
```

**Cache lookup:** Found Jama ID 1175461

**Mode: upsert**
```
action = RESOLVE
status = RESOLVED_PARENT
No POST, no PUT
Register 1175461 as parent
```

### Scenario 3: Existing Folder with Jama ID Provided

**Spreadsheet:**
```
ID              | Item Type | Name                    | Jama ID
EGL_CV-FLD-211  | Folder    | Launch Requirements     | 1175461
```

**Mode: upsert**
```
action = RESOLVE
status = RESOLVED_PARENT
No POST, no PUT
Register 1175461 as parent
```

### Scenario 4: New Requirement Without Jama ID

**Spreadsheet:**
```
ID              | Item Type                  | Name                | Jama ID
EGL_CV-SR-001   | Stakeholder Requirement    | System shall...     | (blank)
```

**Mode: upsert**
```
action = CREATE
POST /items (create new requirement)
Parent = current resolved folder
```

### Scenario 5: Existing Requirement with Jama ID

**Spreadsheet:**
```
ID              | Item Type                  | Name                | Jama ID
EGL_CV-SR-001   | Stakeholder Requirement    | System shall...     | 123456
```

**Mode: upsert**
```
action = SKIP
status = SKIPPED_UPDATE_UNSUPPORTED
No POST, no PUT
Item not modified
```

**Reason:** Update requires PUT, which is not supported.

## Import Results CSV

### Status Values

**New statuses:**
- `CREATED` - Item created via POST
- `RESOLVED_PARENT` - Existing container registered as parent (no update)
- `SKIPPED_UPDATE_UNSUPPORTED` - Existing item not updated (PUT unavailable)
- `FAILED` - Row failed with error

**Dry-run statuses:**
- `DRY_RUN_OK` - Would create
- `DRY_RUN_RESOLVED_PARENT` - Would resolve existing
- `DRY_RUN_SKIPPED` - Would skip (update unsupported)

### Example CSV Output

```csv
excel_row,action,status,jama_id,document_key,source_id,item_type,name,resolved_by,created_item_id,updated_item_id,error
2,RESOLVE,RESOLVED_PARENT,1175461,EGL_CV-FLD-211,EGL_CV-FLD-211,Folder,Launch Requirements,document_key,,,
3,CREATE,CREATED,1234567,EGL_CV-SR-001,EGL_CV-SR-001,Stakeholder Requirement,System shall support...,created,1234567,,
4,SKIP,SKIPPED_UPDATE_UNSUPPORTED,123456,EGL_CV-SR-002,EGL_CV-SR-002,Stakeholder Requirement,System shall provide...,jama_id,,,Existing item update not supported (PUT unavailable)
```

## Import Summary Output

**Before:**
```
Created rows: 50
Updated rows: 10
Resolved rows: 8
Failed rows: 0
Total successful: 68
```

**After:**
```
Created rows: 50
Resolved parent rows: 8
Skipped rows: 10
Failed rows: 0
Total successful: 58
```

**Note:** Skipped rows are NOT counted as successful (they weren't modified).

## Configuration Changes

### .env Changes

**No changes required** - existing `.env` works as-is.

**Modes:**
```env
# Supported modes:
IMPORT_MODE=create    # Create only (fail if Jama ID exists)
IMPORT_MODE=upsert    # Create + resolve existing (default)

# NOT supported:
# IMPORT_MODE=update  # Fails at startup
```

### CLI Changes

**Before:**
```bash
# These all worked
python3 csv2jama.py --mode create --dry-run
python3 csv2jama.py --mode update --dry-run  ← Would attempt PUT
python3 csv2jama.py --mode upsert --dry-run
```

**After:**
```bash
# These work
python3 csv2jama.py --mode create --dry-run
python3 csv2jama.py --mode upsert --dry-run

# This fails immediately
python3 csv2jama.py --mode update --dry-run
[ERROR] Update mode is not supported because this API workflow does not support PUT.
```

## API Calls Made

### With Resolved Existing Folders

**Before (incorrect):**
```
GET /items (cache build)
POST /items (new items)
PUT /items/{id} (resolved folders) ← WRONG
```

**After (correct):**
```
GET /items (cache build)
POST /items (new items only)
(No PUT calls)
```

### Example Import

**50 rows:**
- 5 existing folders resolved by documentKey
- 5 new folders created
- 40 new requirements created

**API calls:**
```
GET /items: 11 calls (cache build, 523 items ÷ 50 per page)
POST /items: 45 calls (5 new folders + 40 new requirements)
Total: 56 calls
```

**No PUT calls made.**

## Hierarchy Registration

**Existing folders still participate in hierarchy:**

```python
# For resolved folder (no POST, no PUT)
if item_type in ("Set", "Folder", "Segment", "Subsystem"):
    if section_number and final_jama_id:
        folder_by_section[section_number] = final_jama_id  ← Registered
    
    if final_jama_id:
        current_folder_item_id = final_jama_id  ← Active parent
```

**Result:** New child requirements can be created under resolved existing folders.

## Error Handling

### If Row Has Jama ID But Mode is "create"

```
[ERROR] Row 5 failed.
[ERROR] Mode is 'create' but Jama ID is populated: 123456. Remove Jama ID for create mode.
```

**Status:** `FAILED`

### If Requirement Has Jama ID in "upsert" Mode

**Not an error** - row is skipped:

```
[SKIP] Existing Stakeholder Requirement has Jama ID 123456
[SKIP] Update is not supported because PUT is not available in this workflow.
```

**Status:** `SKIPPED_UPDATE_UNSUPPORTED`

### If Folder Has Jama ID in "upsert" Mode

**Not an error** - folder is resolved:

```
[OK] Resolved existing Folder by jama_id -> Jama ID 1175461
[OK] Existing item registered as parent container. No update performed.
```

**Status:** `RESOLVED_PARENT`

## Migration Guide

### For Existing Users

**No action required if you:**
- Use `create` mode (new items only)
- Use `upsert` mode (new + resolve existing)
- Don't try to update existing requirements

**Action required if you:**
- Use `update` mode → Switch to `upsert` mode
- Expect existing requirements to be updated → They will be skipped instead

### Updating .env

**No changes needed:**
```env
# This continues to work
IMPORT_MODE=upsert
```

**If using update mode:**
```env
# Before:
IMPORT_MODE=update

# After:
IMPORT_MODE=upsert  # Resolves existing, creates new, skips existing requirements
```

## Limitations

### Cannot Update Existing Items

**Limitation:** Once an item is created in Jama, it cannot be updated via this script.

**Workarounds:**
1. Delete items in Jama and re-import
2. Update directly in Jama UI
3. Use a different tool that supports PUT
4. Modify Jama API workflow to support PUT (requires API/server changes)

### Existing Requirements Are Skipped

**If spreadsheet has:**
```
ID              | Item Type                  | Name                | Description (updated) | Jama ID
EGL_CV-SR-001   | Stakeholder Requirement    | System shall...     | New description       | 123456
```

**Result:**
```
action = SKIP
status = SKIPPED_UPDATE_UNSUPPORTED
Jama item 123456 NOT updated with new description
```

**Workaround:** Remove Jama ID from spreadsheet to create a duplicate (not recommended).

## Benefits

### 1. Clearer Behavior

**Before:** Script attempted PUT, which would fail at API level.

**After:** Script explicitly skips/resolves, clear feedback to user.

### 2. Faster Imports

**Before:** Failed PUT calls waste time.

**After:** No attempted PUT calls.

### 3. Correct Hierarchy

**Before:** Resolved folders might not register properly.

**After:** Resolved folders always register as parents.

### 4. Better Error Messages

**Before:** Generic API 405 or 400 errors.

**After:** Clear SKIP status with explanation.

## Summary

| Operation | Before | After |
|-----------|--------|-------|
| Create new items | POST /items ✓ | POST /items ✓ |
| Update existing items | PUT /items/{id} ✗ | (not attempted) |
| Resolve existing folders | PUT /items/{id} ✗ | Register only ✓ |
| Lookup existing items | GET /items ✓ | GET /items ✓ |
| Update mode | Enabled | Disabled (fails) |
| Upsert mode | Create + update | Create + resolve |
| Existing requirements | Attempted update | Skipped |
| Existing containers | Attempted update | Resolved as parent |

**Compile status:** ✅ PASSED

**Ready for:** Dry-run testing with existing spreadsheets
