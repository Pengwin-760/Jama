# Summary: GET and POST Only (No PUT Support)

## Date
2026-06-03

## Critical Change

The importer now **only uses GET and POST**. PUT has been **completely disabled**.

## Files Modified

1. ✅ **`csv2jama.py`** - Removed PUT functionality
2. ✅ **`NO_PUT_UPDATE.md`** - Comprehensive documentation (NEW)
3. ✅ **`SUMMARY_NO_PUT.md`** - This summary (NEW)

## Where PUT Calls Were Removed/Disabled

### 1. `jama_put()` Function (Line ~542)

**Changed from:** Functional PUT implementation

**Changed to:**
```python
def jama_put(item_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    raise NotImplementedError(
        "PUT /items is not supported in this workflow. "
        "This importer only supports GET (lookup) and POST (create)."
    )
```

**Result:** Calling `jama_put()` immediately raises error.

### 2. Update Mode Validation (Line ~143)

**Added:**
```python
if config["IMPORT_MODE"] == "update":
    print("[ERROR] Update mode is not supported because this API workflow does not support PUT.")
    sys.exit(1)
```

**Result:** Script fails at startup if `--mode update` is used.

### 3. Action Determination (Line ~1280)

**Before:**
```python
elif mode == "upsert":
    action = "UPDATE" if existing_jama_id else "CREATE"
```

**After:**
```python
elif mode == "upsert":
    if existing_jama_id:
        if item_type in ("Set", "Folder", "Segment", "Subsystem"):
            action = "RESOLVE"  # Container: register as parent
        else:
            action = "SKIP"     # Requirement: skip (no update)
    else:
        action = "CREATE"
```

### 4. Payload Building (Line ~1365)

**Before:**
```python
payload = build_payload(
    row=row,
    parent_item_id=parent_item_id,
    sort_order=sort_order,
    is_update=is_update,
    allow_move=allow_move
)
```

**After:**
```python
payload = None
if action == "CREATE":
    payload = build_payload(
        row=row,
        parent_item_id=parent_item_id,
        sort_order=sort_order,
        is_update=False,
        allow_move=False
    )
```

**Result:** Payload only built for CREATE actions.

### 5. Dry-Run Logic (Line ~1392)

**Removed:**
```python
elif action == "RESOLVE":
    print(f"[DRY RUN] Would PUT item {existing_jama_id}:")
    print(json.dumps(payload, indent=2))
```

**Added:**
```python
elif action == "RESOLVE":
    print(f"[DRY RUN] Resolved existing {item_type} -> Jama ID {existing_jama_id}")
    print(f"[DRY RUN] No write will be performed. It will only be used as a parent container.")
elif action == "SKIP":
    print(f"[DRY RUN] SKIP: Existing {item_type} has Jama ID {existing_jama_id}")
    print(f"[DRY RUN] Update is not supported because PUT is not available.")
```

### 6. Execute Logic (Line ~1414)

**Removed:**
```python
elif action == "RESOLVE":
    response = jama_put(existing_jama_id, payload)
    print(f"[OK] Resolved and updated folder {existing_jama_id}")
```

**Added:**
```python
elif action == "RESOLVE":
    final_jama_id = existing_jama_id
    print(f"[OK] Resolved existing {item_type} -> Jama ID {final_jama_id}")
    print(f"[OK] Existing item registered as parent container. No update performed.")
elif action == "SKIP":
    final_jama_id = existing_jama_id
    print(f"[SKIP] Existing {item_type} has Jama ID {final_jama_id}")
    print(f"[SKIP] Update is not supported because PUT is not available.")
```

**Result:** No `jama_put()` calls made.

## How Resolved Existing Folders Behave Now

### Discovery

**Folder found by:**
1. Populated Jama ID in spreadsheet
2. Cache lookup by documentKey

### Registration

**Actions taken:**
```
1. Register Jama ID into hierarchy:
   folder_by_section[section_number] = final_jama_id
   
2. Set as current active parent:
   current_folder_item_id = final_jama_id
   
3. Increment sort order:
   sort_order_by_parent[parent_item_id] = sort_order + 1
```

### No Update

**Actions NOT taken:**
- ❌ Build update payload
- ❌ Call `jama_put()`
- ❌ Modify item in Jama

**Result:** Existing folder participates in hierarchy but is not modified.

## How Existing Rows with Jama ID Behave Now

### Container Rows (Set, Folder, Segment, Subsystem)

**Action:** `RESOLVE`

**Behavior:**
- Register as parent container
- Participate in hierarchy
- No POST, no PUT
- Used as parent for child items

**Output:**
```
[OK] Resolved existing Folder by jama_id -> Jama ID 1175461
[OK] Existing item registered as parent container. No update performed.
```

**CSV Status:** `RESOLVED_PARENT`

### Requirement Rows

**Action:** `SKIP`

**Behavior:**
- Not modified
- Not registered
- No POST, no PUT
- Simply skipped

**Output:**
```
[SKIP] Existing Stakeholder Requirement has Jama ID 123456
[SKIP] Update is not supported because PUT is not available in this workflow.
```

**CSV Status:** `SKIPPED_UPDATE_UNSUPPORTED`

## How New Requirement POST Behavior Works Now

### For New Requirements (No Jama ID)

**Process:**
1. Check current active parent (from resolved folder)
2. Build POST payload:
   ```python
   {
     "fields": {
       "name": "System shall...",
       "description": "The system must..."
     },
     "itemType": 97,  # Stakeholder Requirement
     "location": {
       "parent": {"item": 1175461},  # Resolved folder
       "sortOrder": 0
     }
   }
   ```
3. Call `jama_post("/items", payload)`
4. Extract new Jama ID from response
5. Register in results

**Output:**
```
[OK] Created Jama item ID: 1234567
```

**CSV Status:** `CREATED`

### Child Item Type

**Not included for requirements:**
```python
# Requirements do NOT include childItemType
payload = {
    "fields": {...},
    "itemType": 97,
    "location": {...}
    # No childItemType
}
```

**Only included for containers:**
```python
# Folders/Sets include childItemType
if item_type in ("Set", "Folder"):
    payload["childItemType"] = CHILD_ITEM_TYPE_IDS[item_type]
```

## Statuses in import_results.csv

### New Statuses

| Status | Meaning | API Calls |
|--------|---------|-----------|
| `CREATED` | New item created | POST /items |
| `RESOLVED_PARENT` | Existing container registered as parent | None |
| `SKIPPED_UPDATE_UNSUPPORTED` | Existing item skipped (no PUT available) | None |
| `FAILED` | Row processing failed | Varies |

### Dry-Run Statuses

| Status | Meaning |
|--------|---------|
| `DRY_RUN_OK` | Would create |
| `DRY_RUN_RESOLVED_PARENT` | Would resolve existing |
| `DRY_RUN_SKIPPED` | Would skip |

### CSV Columns

```csv
excel_row,action,status,jama_id,document_key,global_id,source_id,item_type,name,resolved_by,section_number,parent_item_id,created_item_id,updated_item_id,error
```

**For RESOLVED rows:**
- `action` = RESOLVE
- `status` = RESOLVED_PARENT
- `jama_id` = existing Jama ID
- `resolved_by` = document_key or jama_id
- `created_item_id` = blank
- `updated_item_id` = blank

**For SKIPPED rows:**
- `action` = SKIP
- `status` = SKIPPED_UPDATE_UNSUPPORTED
- `jama_id` = existing Jama ID
- `resolved_by` = jama_id
- `error` = Explanation message

**For CREATED rows:**
- `action` = CREATE
- `status` = CREATED
- `jama_id` = new Jama ID
- `created_item_id` = new Jama ID

## Compile Check

```bash
python3 -m py_compile csv2jama.py
```

✅ **PASSED** - No syntax errors

## API Calls Summary

### Before (With PUT)

```
GET /items: cache build
POST /items: create new items
PUT /items/{id}: update existing items ← WRONG
```

### After (No PUT)

```
GET /items: cache build
POST /items: create new items only
(No PUT calls)
```

### Example Import (50 Rows)

**Rows:**
- 5 existing folders (resolved)
- 5 new folders (created)
- 30 new requirements (created)
- 10 existing requirements (skipped)

**API calls:**
```
GET /items: 11 (cache build)
POST /items: 35 (5 folders + 30 requirements)
PUT /items: 0
Total: 46 calls
```

## Import Summary Output

**Example:**
```
IMPORT SUMMARY
================================================================================
Mode: upsert
Execution: EXECUTE
Created rows: 35
Resolved parent rows: 5
Skipped rows: 10
Failed rows: 0
Total successful: 40
Results CSV: import_results.csv
```

**Note:** Skipped rows are not counted as successful (they weren't modified).

## Mode Support

| Mode | Supported | Behavior |
|------|-----------|----------|
| `create` | ✅ Yes | Create new items only; fail if Jama ID exists |
| `upsert` | ✅ Yes | Create new; resolve existing containers; skip existing requirements |
| `update` | ❌ No | Fails at startup with error message |

## Testing Checklist

- [ ] Compile check passed
- [ ] Update mode fails at startup
- [ ] Resolved folders register as parents
- [ ] New requirements POST under resolved folders
- [ ] Existing requirements skipped (not updated)
- [ ] No PUT calls made
- [ ] import_results.csv shows correct statuses
- [ ] Summary counts are accurate

## Next Steps

1. Run dry-run test:
   ```bash
   python3 csv2jama.py --mode upsert --dry-run
   ```

2. Verify output:
   - Resolved folders show "No write will be performed"
   - Existing requirements show "SKIP"
   - New items show "Would POST"

3. Review import_results.csv

4. Execute if satisfied:
   ```bash
   python3 csv2jama.py --mode upsert --execute
   ```

## Documentation

- **`NO_PUT_UPDATE.md`** - Full technical documentation
- **`SUMMARY_NO_PUT.md`** - This quick summary
- **`QUICK_REFERENCE.md`** - Updated with no-PUT info

All documentation updated to reflect GET/POST-only workflow.
