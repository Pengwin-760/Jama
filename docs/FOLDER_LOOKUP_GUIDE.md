# Folder Lookup by documentKey - Quick Reference

## Overview

The script now robustly resolves existing Jama folders by matching the spreadsheet `ID` column against Jama's `documentKey` field.

## How It Works

### Priority Order for Folder Rows:

1. **If Jama ID is populated** → Use that ID directly (no API lookup needed)
2. **Else if `RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=true`** → Call `GET /items` to find folder
3. **Else** → Create the folder (if mode allows)

### Lookup Process:

```
GET /rest/v1/items?project=<project_id>&contains=PROJ-FLD-211&startAt=0&maxResults=20
```

Filters applied:
- `item.documentKey == "PROJ-FLD-211"` (exact match)
- `item.itemType == 32` (Folder type)
- `item.project == <project_id>` (correct project)

Results:
- **Exactly 1 match** → Use that folder (action = RESOLVE)
- **No matches** → Create folder if `CREATE_MISSING_FOLDERS=true`, else fail
- **Multiple matches** → Fail with error asking for explicit Jama ID

## Configuration

### Required `.env` Settings:

```env
JAMA_BASE_URL=https://your-jama-instance.com/rest/v1
JAMA_PROJECT_ID=<your_project_id>
RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=true
CREATE_MISSING_FOLDERS=false
```

### Optional Debug Setting:

```env
DEBUG_JAMA_GET=true
```

Enables detailed logging of GET requests (non-sensitive data only):
```
[DEBUG] GET URL: https://your-jama-instance.com/rest/v1/items
[DEBUG] GET params: {'project': <project_id>, 'contains': 'PROJ-FLD-211', 'startAt': 0, 'maxResults': 20}
[DEBUG] GET status: 200
[DEBUG] GET content-type: application/json
[DEBUG] GET response preview (first 500 chars): {"data":[...]}
```

## Error Handling

### Non-JSON Response:

If the API returns HTML instead of JSON, you'll see:

```
GET /items did not return JSON.
Status: 200
URL: https://your-jama-instance.com/rest/v1/items?project=<project_id>&contains=PROJ-FLD-211
Content-Type: text/html
Response preview:
<html>...

Likely causes: authentication redirect, wrong JAMA_BASE_URL, SSL/proxy issue, or API endpoint mismatch.
```

**Solutions:**
1. Check `JAMA_BASE_URL` ends with `/rest/v1`
2. Verify authentication (OAuth/Bearer/Basic)
3. Check SSL certificate if using custom cert
4. Enable `DEBUG_JAMA_GET=true` for more details

### Multiple Matches:

```
Found 2 folders with documentKey 'PROJ-FLD-211'.
documentKey should be unique. Please provide explicit Jama ID to resolve ambiguity.
```

**Solution:** Add the correct Jama ID to the spreadsheet's "Jama ID" column.

### Folder Not Found:

```
Folder with documentKey 'PROJ-FLD-211' not found in Jama.
Set CREATE_MISSING_FOLDERS=true to create missing folders,
or provide explicit Jama ID to update existing folder.
```

**Solutions:**
1. Set `CREATE_MISSING_FOLDERS=true` to create the folder
2. Add the Jama ID to the spreadsheet
3. Check that `documentKey` in Jama matches the spreadsheet ID exactly

## Output

### import_results.csv

Resolved folders show:
```csv
excel_row,action,status,jama_id,document_key,global_id,resolved_by,...
2,RESOLVE,RESOLVED,999999,PROJ-FLD-211,GID-XXXXX,document_key,...
```

### Console Output

```
[INFO] Attempting to resolve folder by documentKey: PROJ-FLD-211
[INFO] Resolved existing folder by documentKey 'PROJ-FLD-211' -> Jama ID 999999
[OK] Resolved and updated folder 999999
```

### Summary Report

```
IMPORT SUMMARY
==================================================
Mode: upsert
Execution: EXECUTE
Created rows: 50
Updated rows: 10
Resolved rows: 8
Failed rows: 0
Total successful: 68
```

## Common Scenarios

### Scenario 1: Fresh Import (No Jama IDs)

```env
RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=true
CREATE_MISSING_FOLDERS=true
```

**Result:** Folders are looked up first. If found, they're updated. If not found, they're created.

### Scenario 2: Update Existing (All Jama IDs Provided)

```env
RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=false  # Not needed - Jama IDs provided
```

**Result:** All items updated using their Jama IDs. No lookups needed.

### Scenario 3: Mixed (Some Jama IDs, Some Missing)

```env
RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=true
CREATE_MISSING_FOLDERS=false
```

**Result:** 
- Rows with Jama IDs → Updated
- Folder rows without Jama IDs → Looked up by documentKey
- Other rows without Jama IDs → Created

### Scenario 4: Strict Updates Only

```env
RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=false
CREATE_MISSING_FOLDERS=false
```

**Result:** All rows must have Jama IDs. Any missing Jama IDs will fail.

## Troubleshooting Checklist

- [ ] `JAMA_BASE_URL` ends with `/rest/v1`
- [ ] Authentication credentials are correct
- [ ] `JAMA_PROJECT_ID` matches your Jama project
- [ ] SSL certificate path is correct (if using custom cert)
- [ ] `documentKey` in Jama matches spreadsheet ID exactly
- [ ] Folder item type ID is correct (32)
- [ ] Enable `DEBUG_JAMA_GET=true` for detailed diagnostics

## API Pagination

The lookup automatically handles pagination:
- Requests 20 results per page
- Continues until all matching items are found
- Stops early if exact match is found
- Validates uniqueness across all pages

## Performance Notes

- Lookups only happen for Folder rows without Jama IDs
- Each lookup makes 1+ API calls (depending on pagination)
- Folders are cached in hierarchy after resolution
- Subsequent child requirements use the cached folder ID
- Small delay (0.2s) between API calls to avoid rate limiting
