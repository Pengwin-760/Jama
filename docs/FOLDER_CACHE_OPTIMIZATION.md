# Folder Cache Optimization Guide

## Overview

The folder documentKey lookup has been optimized to use a cache that fetches all project folders once at startup, instead of making separate API calls for each folder row.

## Performance Improvement

### Before (Slow):
```
For each Folder row without Jama ID:
  → GET /items?project=<project_id>&contains=PROJ-FLD-220&startAt=0&maxResults=20
  → GET /items?project=<project_id>&contains=PROJ-FLD-211&startAt=0&maxResults=20
  → GET /items?project=<project_id>&contains=PROJ-FLD-218&startAt=0&maxResults=20
  → ... (one GET per folder)
```

**Result:** If you have 50 folders without Jama IDs, that's 50+ separate API calls.

### After (Fast):
```
At startup:
  → GET /items?project=<project_id>&startAt=0&maxResults=100
  → GET /items?project=<project_id>&startAt=100&maxResults=100
  → ... (paginate until all project items fetched)
  → Build cache: documentKey -> folder item

For each Folder row without Jama ID:
  → Lookup in cache (no API call)
```

**Result:** Typically 1-5 API calls total to build the cache, regardless of folder count.

## Configuration

### .env Settings

```env
# Enable folder cache (default: true, recommended)
USE_FOLDER_DOCUMENT_KEY_CACHE=true

# Page size for fetching items (default: 100)
JAMA_ITEMS_PAGE_SIZE=100

# Must be enabled for folder resolution to work
RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=true
```

### Recommended Settings

**For best performance (default):**
```env
USE_FOLDER_DOCUMENT_KEY_CACHE=true
JAMA_ITEMS_PAGE_SIZE=100
```

**For debugging/troubleshooting:**
```env
USE_FOLDER_DOCUMENT_KEY_CACHE=false  # Fall back to per-folder lookup
JAMA_ITEMS_PAGE_SIZE=20
DEBUG_JAMA_GET=true
```

## How It Works

### 1. Cache Building (Startup)

When the first folder without Jama ID is encountered:

```
[INFO] Building folder documentKey cache from Jama project <project_id>...
[INFO] Fetched 523 total items from project.
[INFO] Cached 123 folders by documentKey.
```

**Process:**
1. Fetch all items from project (paginated with JAMA_ITEMS_PAGE_SIZE)
2. Filter to Folder itemType only
3. Filter to items with non-empty documentKey
4. Build dict: `documentKey -> full item`
5. Detect duplicates and store separately

**API Calls:**
- If project has 523 items and page size is 100:
  - Page 1: items 0-99 (100 items)
  - Page 2: items 100-199 (100 items)
  - Page 3: items 200-299 (100 items)
  - Page 4: items 300-399 (100 items)
  - Page 5: items 400-499 (100 items)
  - Page 6: items 500-522 (23 items)
  - **Total: 6 API calls**

### 2. Folder Resolution (Per Folder Row)

```
[INFO] Attempting to resolve folder by documentKey: PROJ-FLD-220
[INFO] Resolved existing folder by documentKey 'PROJ-FLD-220' -> Jama ID 999999
```

**Process:**
1. Check if cache exists (build if not)
2. Check if documentKey has duplicates → fail if yes
3. Look up documentKey in cache → return item or None
4. **No API call made**

### 3. Duplicate Detection

If multiple folders have the same documentKey:

```
[WARN] Found 2 documentKeys with multiple folders (will fail if resolved).
...
[ERROR] Row 96 failed.
[ERROR] Folder documentKey 'PROJ-FLD-220' matched 2 folders. Please provide explicit Jama ID to resolve ambiguity.
```

**Duplicates are detected during cache build and reported clearly.**

## Performance Comparison

### Example: 50 Folders Without Jama IDs

**Without cache (old behavior):**
- API calls: 50+ (one per folder, plus pagination)
- Time: ~50-100 seconds (assuming 1-2s per API call)

**With cache (new behavior):**
- API calls: 5-10 (paginated fetch of all project items)
- Time: ~5-10 seconds (assuming 1s per page)
- **Speed improvement: 5-10x faster**

### Example: 200 Folders Without Jama IDs

**Without cache:**
- API calls: 200+
- Time: ~200-400 seconds (3-7 minutes)

**With cache:**
- API calls: 5-10 (same as before - independent of folder count)
- Time: ~5-10 seconds
- **Speed improvement: 20-40x faster**

## Cache Behavior

### Cache Lifetime

- Built once per script execution
- Shared across all folder rows in the import
- Not persisted between script runs

### Cache Invalidation

The cache is not automatically invalidated. If you:
1. Run the import
2. Manually create/modify folders in Jama
3. Run the import again (same process)

The cache will be rebuilt on the second run (new process).

### Memory Usage

Typical folder item is ~1-2KB. For 100 folders:
- Memory used: ~100-200KB
- Negligible impact on memory

## Debug Mode

When `DEBUG_JAMA_GET=true`, the cache building temporarily suppresses debug output to avoid excessive logging:

```
[INFO] Building folder documentKey cache from Jama project <project_id>...
[DEBUG] Temporarily suppressing GET debug output during cache build...
[INFO] Fetched 523 total items from project.
[INFO] Cached 123 folders by documentKey.
```

After cache is built, debug mode resumes normal operation.

## Fallback Mode

If you encounter issues with the cache, you can disable it:

```env
USE_FOLDER_DOCUMENT_KEY_CACHE=false
```

This reverts to the old per-folder API lookup behavior:
- Slower but more isolated
- Each folder lookup is independent
- Useful for debugging specific folder resolution issues

## API Function Flow

### Cache-Enabled (Default)

```python
find_existing_folder_by_document_key(document_key)
  ↓
_find_folder_by_cache(document_key)
  ↓
build_folder_document_key_cache()  # Only on first call
  ↓ (GET /items paginated, no "contains" filter)
  ↓
Cache lookup (in-memory dict)
  ↓
Return item or None
```

### Cache-Disabled (Fallback)

```python
find_existing_folder_by_document_key(document_key)
  ↓
_find_folder_by_api_lookup(document_key)
  ↓ (GET /items?contains=documentKey per folder)
  ↓
Filter and return
```

## Troubleshooting

### Issue: Cache build is slow

**Symptoms:**
```
[INFO] Building folder documentKey cache from Jama project <project_id>...
(long pause)
[INFO] Fetched 50000 total items from project.
```

**Solution:**
Your project has many items. Increase page size:
```env
JAMA_ITEMS_PAGE_SIZE=200  # or 500
```

**Note:** Jama may have a server-side limit (typically 1000).

### Issue: Cache build fails

**Symptoms:**
```
[ERROR] Failed to build folder cache: GET failed: 500
```

**Solution:**
1. Check authentication is working
2. Enable debug mode:
   ```env
   DEBUG_JAMA_GET=true
   ```
3. Review error message
4. Fall back to per-folder lookup:
   ```env
   USE_FOLDER_DOCUMENT_KEY_CACHE=false
   ```

### Issue: Folder not found despite existing in Jama

**Possible causes:**
1. Folder is in a different project
2. Folder has empty/null documentKey
3. Folder itemType ID is wrong

**Debug steps:**
1. Enable debug mode
2. Check folder in Jama:
   - Verify project ID matches
   - Verify documentKey field is populated
   - Verify item type is "Folder" (32)
3. Disable cache temporarily to test per-folder lookup:
   ```env
   USE_FOLDER_DOCUMENT_KEY_CACHE=false
   DEBUG_JAMA_GET=true
   ```

### Issue: Duplicate documentKey error

**Symptoms:**
```
[WARN] Found 2 documentKeys with multiple folders (will fail if resolved).
...
[ERROR] Folder documentKey 'PROJ-FLD-220' matched 2 folders.
```

**Solution:**
This is a data integrity issue in Jama. Options:
1. **Best:** Add explicit Jama ID to spreadsheet for this folder
2. Merge or delete duplicate folders in Jama
3. Update documentKey in Jama to make unique

## API Call Count Examples

### Small Project (~500 items, 50 folders)

**With cache:**
- Cache build: 5 API calls (500 items ÷ 100 per page)
- Folder lookups: 0 API calls (cached)
- **Total: 5 API calls**

**Without cache:**
- Cache build: 0 API calls
- Folder lookups: 50 API calls (one per folder)
- **Total: 50 API calls**

**Speed improvement: 10x faster**

### Medium Project (~2000 items, 150 folders)

**With cache:**
- Cache build: 20 API calls (2000 items ÷ 100 per page)
- Folder lookups: 0 API calls (cached)
- **Total: 20 API calls**

**Without cache:**
- Cache build: 0 API calls
- Folder lookups: 150 API calls
- **Total: 150 API calls**

**Speed improvement: 7.5x faster**

### Large Project (~10000 items, 500 folders)

**With cache:**
- Cache build: 100 API calls (10000 items ÷ 100 per page)
- Folder lookups: 0 API calls (cached)
- **Total: 100 API calls**

**Without cache:**
- Cache build: 0 API calls
- Folder lookups: 500 API calls
- **Total: 500 API calls**

**Speed improvement: 5x faster**

## Summary

### Benefits
- ✅ 5-40x faster folder resolution
- ✅ Fewer API calls
- ✅ Reduced server load
- ✅ Duplicate detection at startup
- ✅ Scales better with large imports

### Trade-offs
- Small memory overhead (~1-2KB per folder)
- Initial startup delay to build cache
- All-or-nothing: fetches all project items (not just folders needed)

### When to Use Cache
- ✅ Importing many folders (>10 without Jama IDs)
- ✅ Large imports with multiple runs
- ✅ Projects with reasonable item counts (<50k items)

### When to Disable Cache
- Debugging specific folder resolution issues
- Projects with extremely large item counts (>50k items)
- Very small imports (1-2 folders)

**Default recommendation: Keep cache enabled (USE_FOLDER_DOCUMENT_KEY_CACHE=true)**
