# Simplified Folder Resolution

## Overview

The importer now uses simple, predictable folder resolution. Excel ID column for Folder rows is treated as the Jama documentKey.

## How It Works

### For Folder Rows

**Resolution Priority:**

1. **Jama ID column** (if populated)
   - Uses explicit Jama item ID
   - Skips lookup, goes directly to item

2. **Document Key column** (if populated)
   - Uses explicit documentKey from separate column
   - Looks up folder in Jama

3. **Excel ID as documentKey** (default)
   - Treats Excel ID as Jama documentKey
   - Looks up folder: `item.documentKey == row["ID"]`

**Result:**
- If found: Register as current parent, no POST
- If not found and `CREATE_MISSING_FOLDERS=false`: Fail with error
- If not found and `CREATE_MISSING_FOLDERS=true`: Create new folder

### For Requirement Rows

- Excel ID is source/import ID only
- POST requirement under current active parent folder
- Validates parent childItemType matches requirement itemType

## Configuration

### Recommended Settings (.env)
```env
RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=true
USE_EXCEL_ID_AS_DOCUMENT_KEY=true
CREATE_MISSING_FOLDERS=false
RESOLVE_EXISTING_FOLDERS_BY_NAME=false
USE_STATIC_FOLDER_SOURCE_ID_MAP=false
```

### What Each Setting Does

**RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=true**
- Enables documentKey lookup for folders
- Default: true (recommended)

**USE_EXCEL_ID_AS_DOCUMENT_KEY=true**
- Treats Excel ID column as documentKey for Folder rows
- Default: true (recommended for normal imports)

**CREATE_MISSING_FOLDERS=false**
- Fails if folder not found (prevents duplicates)
- Default: false (safe)

**RESOLVE_EXISTING_FOLDERS_BY_NAME=false**
- Disables name-based matching (not recommended)
- Default: false

**USE_STATIC_FOLDER_SOURCE_ID_MAP=false**
- Disables advanced path-based routing map
- Default: false (not needed for normal imports)

## Example

### Excel File
```
ID              | Item Type              | Name
PROJ-FLD-276  | Folder                 | (U) Flight Computer Assembly Requirements
PROJ-FLD-277  | Folder                 | Status and Monitoring
PROJ-SS-001   | Subsystem Requirement  | BIT Status Reporting
```

### Behavior

**Row 1: Folder PROJ-FLD-276**
```
[INFO] Attempting to resolve folder by documentKey from Excel ID: PROJ-FLD-276
[INFO] Resolved existing folder by documentKey 'PROJ-FLD-276' -> Jama ID 999999
[INFO] Registered as current parent. No folder will be created.
```

**Row 2: Folder PROJ-FLD-277**
```
[INFO] Attempting to resolve folder by documentKey from Excel ID: PROJ-FLD-277
[INFO] Resolved existing folder by documentKey 'PROJ-FLD-277' -> Jama ID 888888
[INFO] Registered as current parent. No folder will be created.
```

**Row 3: Subsystem Requirement**
```
[INFO] Parent item ID: 1234568
[INFO] Parent documentKey: PROJ-FLD-277
[INFO] Parent name: Status and Monitoring
[INFO] Parent itemType: 32
[INFO] Parent childItemType: 87 (parent accepts this content type)
[INFO] New itemType: 87
[INFO] Compatibility check: requirement itemType=87 vs parent accepts childItemType=87 → ✓ MATCH
[DRY RUN] Would POST Subsystem Requirement under parent item 1234568
```

## Dry-Run Output

### Successful Resolution
```
[DRY RUN] Resolved folder by documentKey PROJ-FLD-276 -> Jama ID 999999
[DRY RUN] Registered as current parent. No folder will be created.
```

### Folder Not Found
```
[ERROR] Folder documentKey 'PROJ-FLD-276' was not found in Jama.
Folder name: (U) Flight Computer Assembly Requirements
CREATE_MISSING_FOLDERS=false, so no duplicate folder was created.
Solution: Either provide the Jama ID in Excel, or set CREATE_MISSING_FOLDERS=true.
```

### Requirement Would Be Created
```
[DRY RUN] Would POST Subsystem Requirement:
{
  "fields": {
    "name": "BIT Status Reporting",
    "description": "..."
  },
  "itemType": 87,
  "location": {
    "parent": {
      "item": 1234568
    },
    "sortOrder": 0
  }
}
```

## Execute Output

### Folder Resolved
```
[OK] Resolved folder by documentKey PROJ-FLD-276 -> Jama ID 999999
[OK] Registered as current parent. No folder created.
```

### Requirement Created
```
[INFO] New itemType: 87
[OK] Created Jama item ID: 9999999
```

## Error Messages

### Folder documentKey Not Found
```
Folder documentKey 'PROJ-FLD-276' was not found in Jama.
Folder name: (U) Flight Computer Assembly Requirements
CREATE_MISSING_FOLDERS=false, so no duplicate folder was created.
Solution: Either provide the Jama ID in Excel, or set CREATE_MISSING_FOLDERS=true.
```

**Fix:** Verify the documentKey in Jama matches Excel ID exactly

### Parent childItemType Mismatch
```
Cannot create Subsystem Requirement (itemType=87) under parent item 1234567.
Parent documentKey: PROJ-FLD-276
Parent name: Flight Computer Assembly Requirements
Parent itemType: 32
Parent childItemType: 243
Expected new itemType to match parent childItemType (243), but got 87.
This row is routed to the wrong folder/container.
```

**Fix:** Check Excel structure - requirement is under wrong folder

## What Was Removed/Disabled

❌ **Static source ID to parent path map** - Not needed  
❌ **Path-based folder routing** - Too complex  
❌ **Exact-name matching as default** - Unreliable  
❌ **Ambiguous name resolution** - Error-prone  

## What Was Kept

✅ **documentKey cache** - Fast lookups  
✅ **Parent childItemType validation** - Safety check  
✅ **Dry-run default** - Safe preview  
✅ **OAuth/auth handling** - All methods supported  
✅ **import_results.csv** - Full audit trail  
✅ **Simple CLI** - `python csv2jama.py` just works  

## Usage

### Normal Import (Dry-Run)
```bash
python csv2jama.py
```

### Execute Import
```bash
python csv2jama.py --execute
```

### With Move Support (Advanced)
```bash
python csv2jama.py --execute --allow-move
```

## Troubleshooting

### All folders fail with "not found"
**Check:** Is `USE_EXCEL_ID_AS_DOCUMENT_KEY=true` in .env?

### Folders created as duplicates
**Check:** Is `CREATE_MISSING_FOLDERS=true`? Set to false for safety.

### Parent childItemType errors
**Check:** Are requirements under correct folder in Excel? Verify folder structure.

### Requirements not created
**Check:** Did folders resolve successfully? Requirements need valid parent.

## Best Practices

1. **Verify Excel IDs** - Must match Jama documentKeys exactly
2. **Use dry-run first** - Always preview before execute
3. **Keep CREATE_MISSING_FOLDERS=false** - Prevents duplicates
4. **Check import_results.csv** - Review all operations
5. **Simple is better** - Use documentKey resolution, not complex maps
