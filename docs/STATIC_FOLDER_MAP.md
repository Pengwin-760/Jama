# Static Folder Source ID Map

## Overview

The static folder source ID map provides path-based resolution for folders when Excel IDs are fabricated source identifiers rather than Jama documentKeys.

## Problem It Solves

**Without the map:**
- Excel ID column contains fabricated IDs (e.g., `EGL_CV-FLD-281`)
- These are NOT Jama documentKeys
- Script cannot resolve which existing folder to use
- Risk of creating duplicate folders

**With the map:**
- Maps fabricated Excel ID → intended parent path
- Resolves exact folder by path + name
- Prevents duplicate folder creation
- Ensures requirements go under correct parent

## Configuration

### Enable in .env
```env
USE_STATIC_FOLDER_SOURCE_ID_MAP=true
USE_EXCEL_ID_AS_DOCUMENT_KEY=false
CREATE_MISSING_FOLDERS=false
```

### Define Map in Script

In `csv2jama.py`, the map is defined as:

```python
FOLDER_SOURCE_ID_TO_PARENT_PATH = {
    "EGL_CV-FLD-281": "EAGLET Subsystem Requirements",
    "EGL_CV-FLD-282": "EAGLET Subsystem Requirements/DFCS SRS",
    # ...
}
```

**Key:** Excel source ID (fabricated, not a Jama documentKey)  
**Value:** Parent path (slash-separated folder names, empty = root)

## How It Works

### Resolution Priority

For each Folder row, the script tries in order:

**A. Jama ID** (if populated in Excel)
- Use explicitly provided Jama ID

**B. Document Key** (if USE_EXCEL_ID_AS_DOCUMENT_KEY=true)
- Treat Excel ID as Jama documentKey
- Look up in Jama

**C. Static Map** (if USE_STATIC_FOLDER_SOURCE_ID_MAP=true and ID in map)
- **This is the new method**
- Look up parent path from map
- Walk path from root
- Find exact child folder by name

**D. Parent Path column** (if present in Excel)
- Not yet implemented

**E. Exact name** (globally unique)
- Last resort, not recommended

**F. Fail** (if CREATE_MISSING_FOLDERS=false)
- Prevents duplicate creation

### Example

**Excel row:**
```
ID: EGL_CV-FLD-281
Item Type: Folder
Name: (U) Launch Requirements
```

**Map entry:**
```python
"EGL_CV-FLD-281": "EAGLET Subsystem Requirements"
```

**Resolution process:**
1. Parent path: `"EAGLET Subsystem Requirements"`
2. Walk from ROOT_PARENT_ITEM_ID → find "EAGLET Subsystem Requirements"
3. Under that folder, find exact child named "(U) Launch Requirements"
4. Resolve that folder as parent for subsequent requirements

## Output

### Successful Resolution (Dry-Run)
```
[INFO] Source folder ID EGL_CV-FLD-281 has mapped parent path: 'EAGLET Subsystem Requirements'
[INFO] Resolving folder name: (U) Launch Requirements
[INFO] Resolved existing folder by source ID map -> Jama ID 1234567
[INFO] Existing folder childItemType: 87 matches expected: 87 (compatible)
[INFO] Existing folder will be registered as parent container. No update will be performed.
[DRY RUN] Resolved existing Folder -> Jama ID 1234567
[DRY RUN] No write will be performed for this existing item. It will only be used as a parent container.
```

### Failed Resolution
```
[INFO] Source folder ID EGL_CV-FLD-282 has mapped parent path: 'EAGLET Subsystem Requirements/DFCS SRS'
[INFO] Resolving folder name: (U) Software Requirements
[ERROR] Could not resolve mapped parent path 'EAGLET Subsystem Requirements/DFCS SRS' for source folder EGL_CV-FLD-282.
The path does not exist in Jama. No folder will be created.
```

## Error Handling

### Parent Path Not Found
```
RuntimeError: Could not resolve mapped parent path 'X/Y/Z' for source folder ABC.
The path does not exist in Jama. No folder will be created.
```

**Cause:** One of the path segments doesn't exist  
**Fix:** Create missing path segments in Jama, or correct the map

### Folder Not Found Under Parent
```
ValueError: Folder 'Launch Requirements' (ID: EGL_CV-FLD-281) not found in Jama.
Set CREATE_MISSING_FOLDERS=true to create missing folders, or provide explicit Jama ID or map entry.
```

**Cause:** Folder doesn't exist under mapped parent  
**Fix:** Create folder in Jama, or set CREATE_MISSING_FOLDERS=true

### Multiple Folders Match
```
ValueError: Found 2 folders named 'Requirements' under parent 12345.
Cannot determine which to use. Please provide explicit Jama ID or Document Key.
```

**Cause:** Duplicate folder names under same parent  
**Fix:** Provide explicit Jama ID in Excel for this row

## Benefits

✅ **Prevents duplicates** - Resolves exact existing folders  
✅ **Path-based routing** - Maps to intended parent hierarchy  
✅ **Safe defaults** - Fails instead of creating wrong structure  
✅ **Clear errors** - Shows exactly what failed and why  
✅ **Preserves validation** - childItemType checks still active  

## Limitations

⚠️ **Requires manual map** - Each folder ID must be mapped  
⚠️ **Paths must exist** - All path segments must already exist in Jama  
⚠️ **Exact name match** - Folder name must match exactly (whitespace normalized)  
⚠️ **No fuzzy matching** - Won't guess similar names  

## When to Use

**Use this method when:**
- Excel IDs are fabricated (not Jama documentKeys)
- You know the exact folder structure in Jama
- You want to prevent duplicate folders
- You need deterministic folder resolution

**Don't use this method when:**
- Excel IDs are actual Jama documentKeys (use USE_EXCEL_ID_AS_DOCUMENT_KEY=true instead)
- Folder structure is simple/flat (section numbering may be enough)
- Creating new folders is desired (use CREATE_MISSING_FOLDERS=true)

## Best Practices

1. **Build the map carefully** - Verify paths exist in Jama
2. **Use dry-run first** - Check resolution before executing
3. **Empty path = root** - Use `""` for direct children of ROOT_PARENT_ITEM_ID
4. **Exact names** - Copy folder names from Jama exactly
5. **Keep map updated** - If Jama structure changes, update map

## Example Map

```python
FOLDER_SOURCE_ID_TO_PARENT_PATH = {
    # Root-level folder
    "EGL_CV-FLD-265": "",  # Empty = direct child of root
    
    # First-level folders
    "EGL_CV-FLD-266": "EAGLET Subsystem Requirements",
    "EGL_CV-FLD-272": "EAGLET Subsystem Requirements",
    
    # Nested folders (2 levels)
    "EGL_CV-FLD-267": "EAGLET Subsystem Requirements/(U) Starshield Requirements",
    "EGL_CV-FLD-269": "EAGLET Subsystem Requirements/(U) Mission Computer Requirements",
    
    # Deeply nested (3 levels)
    "EGL_CV-FLD-282": "EAGLET Subsystem Requirements/DFCS SRS/Software Requirements",
}
```

## Troubleshooting

### Map not being used
**Check:** Is `USE_STATIC_FOLDER_SOURCE_ID_MAP=true` in .env?

### Wrong folder resolved
**Check:** Is the parent path correct? Does folder name match exactly?

### Path not found
**Check:** Do all path segments exist in Jama? Use dry-run to see resolution steps.

### Duplicate detection still happening
**Check:** Are there multiple folders with same name under parent? Add Jama ID to Excel.
