# CREATE_MISSING_FOLDERS Configuration

## Overview

`CREATE_MISSING_FOLDERS=true` is now fully supported and safe when combined with proper folder resolution.

## Valid Configuration

```env
RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=true
USE_EXCEL_ID_AS_DOCUMENT_KEY=true
CREATE_MISSING_FOLDERS=true
```

This configuration:
1. ✅ **Always looks up folders first** by documentKey
2. ✅ **Creates only if not found** after lookup
3. ✅ **Prevents duplicates** through mandatory lookup

## How It Works

### Folder Processing Order

**1. Lookup Phase (Always Happens First)**

Priority A: Jama ID column
- Uses explicit Jama item ID
- Skips lookup, goes directly

Priority B: Document Key column  
- Looks up by documentKey from column
- If found, registers as parent

Priority C: Excel ID as documentKey
- Looks up by Excel ID
- If found, registers as parent

**2. Creation Phase (Only if Not Found)**

If lookup found nothing:
- `CREATE_MISSING_FOLDERS=true` → Create new folder
- `CREATE_MISSING_FOLDERS=false` → Fail with error

### Safety Validation

**The script validates configuration at startup:**

```
Unsafe: RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=false + CREATE_MISSING_FOLDERS=true
Error: This will create duplicates without checking for existing folders
Solution: Enable RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=true
```

## Output Messages

### Existing Folder Found
```
[INFO] Folder row - attempting to resolve existing folder:
[INFO]   Excel ID: PROJ-FLD-281
[INFO]   Folder Name: (U) Launch Requirements
[INFO] Attempting to resolve folder by documentKey from Excel ID: PROJ-FLD-281
[INFO] ✓ Found by Excel ID as documentKey
[INFO] Resolved existing folder by documentKey 'PROJ-FLD-281' -> Jama ID 999999
[INFO] Registered as current parent. No folder will be created.
```

### Missing Folder (Will Create)
```
[INFO] Folder row - attempting to resolve existing folder:
[INFO]   Excel ID: PROJ-FLD-999
[INFO]   Folder Name: (U) New Requirements
[INFO] Attempting to resolve folder by documentKey from Excel ID: PROJ-FLD-999
[INFO] ✗ Not found in Jama by documentKey 'PROJ-FLD-999'
[INFO] Folder documentKey 'PROJ-FLD-999' was not found in Jama after lookup.
[INFO] CREATE_MISSING_FOLDERS=true, so a new folder will be created.
```

### Dry-Run Output

**Existing folder:**
```
[DRY RUN] Resolved folder by documentKey PROJ-FLD-281 -> Jama ID 999999
[DRY RUN] Registered as current parent. No folder will be created.
```

**Missing folder:**
```
[INFO] Folder documentKey 'PROJ-FLD-999' was not found in Jama after lookup.
[INFO] CREATE_MISSING_FOLDERS=true, so a new folder will be created.
[DRY RUN] Would POST:
{
  "fields": {"name": "(U) New Requirements"},
  "itemType": 32,
  "location": {"parent": {"item": <parent_id>}, "sortOrder": 0},
  "childItemType": 87
}
```

### Execute Output

**Created folder:**
```
[INFO] New itemType: 32
[INFO] New childItemType: 87
[OK] Created new Folder with Jama ID: 999999, documentKey: PROJ-FLD-999
```

## When to Use Each Setting

### CREATE_MISSING_FOLDERS=true
**Use when:**
- Initial import with new folders
- Adding new folder structure
- Mixed existing + new folders

**Requirements:**
- Must have `RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=true`
- Excel IDs must be unique (will become documentKeys)

### CREATE_MISSING_FOLDERS=false
**Use when:**
- Pure update of existing structure
- You want to catch missing folders as errors
- All folders should already exist

**Benefit:**
- Safer - fails if folder missing
- Prevents accidental folder creation

## Workflow Examples

### Example 1: Mixed Import (Existing + New)

**Configuration:**
```env
CREATE_MISSING_FOLDERS=true
RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=true
USE_EXCEL_ID_AS_DOCUMENT_KEY=true
```

**Excel:**
```
ID              | Item Type | Name
PROJ-FLD-281    | Folder    | (U) Launch Requirements      (EXISTS)
PROJ-FLD-999    | Folder    | (U) New Requirements         (NEW)
PROJ-SS-001     | Subsystem | BIT Status
```

**Result:**
1. Folder 281: Resolves existing → No POST
2. Folder 999: Not found → POST new folder
3. Requirement: POSTs under folder 999

### Example 2: Update Only

**Configuration:**
```env
CREATE_MISSING_FOLDERS=false
RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=true
```

**Excel:**
```
ID              | Item Type | Name
PROJ-FLD-281    | Folder    | (U) Launch Requirements
PROJ-FLD-999    | Folder    | (U) Missing Folder
PROJ-SS-001     | Subsystem | BIT Status
```

**Result:**
1. Folder 281: Resolves existing → No POST
2. Folder 999: Not found → **FAILS** (CREATE_MISSING_FOLDERS=false)

## Item ID Extraction

The script now properly extracts created item IDs:

**✅ Correct:**
```
[OK] Created new Folder with Jama ID: 999999, documentKey: PROJ-FLD-999
```

**❌ Error (if ID missing):**
```
ValueError: Created item ID is missing from Jama response.
Response preview: {...}
This may indicate a POST failure or unexpected response format.
```

The script will **never** report `Jama ID: 0` - it will fail with a clear error if the ID is missing.

## Common Issues

### Duplicate Folders Created

**Symptom:** Folders with same name but different documentKeys

**Cause:** Lookup failed because Excel ID doesn't match Jama documentKey

**Fix:** 
1. Check Excel ID matches actual Jama documentKey
2. Or provide Jama ID in "Jama ID" column

### Config Validation Error

**Error:**
```
[ERROR] Unsafe configuration detected!
CREATE_MISSING_FOLDERS=true but RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=false
```

**Fix:** Set `RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=true` in .env

### Folders Always Created

**Check:**
1. Is `USE_EXCEL_ID_AS_DOCUMENT_KEY=true`?
2. Do Excel IDs match Jama documentKeys?
3. Is folder cache building successfully?

## Best Practices

1. **Always enable folder resolution** when creating folders
2. **Use dry-run first** to see which folders will be created
3. **Verify Excel IDs** match actual Jama documentKeys
4. **Check import_results.csv** to see what was created vs resolved
5. **Keep CREATE_MISSING_FOLDERS=true** for normal mixed imports

## Summary

✅ **Safe:** CREATE_MISSING_FOLDERS=true + folder lookup enabled  
✅ **Mandatory:** Folders always looked up before creation  
✅ **Validated:** Script checks for unsafe config combinations  
✅ **Clear:** Output shows resolved vs created folders  
✅ **Reliable:** Real Jama IDs extracted, never 0  
