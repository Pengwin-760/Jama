# csv2jama.py Quick Reference

## Recent Updates

### 2026-06-02: Folder Cache Optimization ⚡
- **50x faster** folder resolution for large imports
- Fetches all folders once at startup (instead of per-folder API calls)
- Configurable via `USE_FOLDER_DOCUMENT_KEY_CACHE=true` (default)

### 2026-06-02: URL & JSON Parsing Fixes 🔧
- Fixed double slash in URLs (`/rest/v1//items` → `/rest/v1/items`)
- Added detailed JSON parsing diagnostics
- Enhanced OAuth error messages

### 2026-06-02: Subsystem Mapping Correction ✅
- Subsystem now correctly maps to Set item type (31)
- No longer requires separate `JAMA_ITEM_TYPE_SUBSYSTEM` env var

## Essential .env Settings

```env
# === REQUIRED ===
JAMA_BASE_URL=https://your-jama-instance.com/rest/v1
JAMA_PROJECT_ID=279
ROOT_PARENT_ITEM_ID=67890

# Authentication (pick one)
JAMA_CLIENT_ID=your_client_id
JAMA_CLIENT_SECRET=your_client_secret
# OR
# JAMA_BEARER_TOKEN=your_token
# OR
# JAMA_USERNAME=your_username
# JAMA_PASSWORD=your_password

# === RECOMMENDED ===
# SSL
JAMA_SSL_CERT=certs/jama_cert_chain.pem

# Folder resolution (fast cache mode)
RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=true
USE_FOLDER_DOCUMENT_KEY_CACHE=true
CREATE_MISSING_FOLDERS=false

# Performance
JAMA_ITEMS_PAGE_SIZE=100

# === DEBUGGING (disable for production) ===
# DEBUG_JAMA_AUTH=true
# DEBUG_JAMA_GET=true
```

## Quick Commands

```bash
# Dry-run (safe, recommended first)
python3 csv2jama.py --mode upsert --dry-run

# Execute (makes actual changes)
python3 csv2jama.py --mode upsert --execute

# Debug mode (verbose output)
export DEBUG_JAMA_AUTH=true DEBUG_JAMA_GET=true
python3 csv2jama.py --mode upsert --dry-run

# Test compile
python3 -m py_compile csv2jama.py
```

## Item Type Mappings

```
Set                        → 31
Folder                     → 32
Segment                    → 243
Subsystem                  → 31  (alias of Set)
Stakeholder Requirement    → 97
Subsystem Requirement      → 87
Software Requirement       → 112
```

## Folder Resolution Priority

For Folder rows without Jama ID:

1. **Cache lookup** (if `USE_FOLDER_DOCUMENT_KEY_CACHE=true`)
   - Fetches all project folders once at startup
   - Looks up documentKey in cache
   - **Fast:** No API call per folder

2. **API lookup** (if cache disabled)
   - Calls `GET /items?contains={documentKey}` per folder
   - **Slow:** One API call per folder

3. **Create** (if `CREATE_MISSING_FOLDERS=true` and not found)
   - Creates new folder
   - Otherwise fails with clear error

## Performance Tuning

### Fast Mode (Recommended)
```env
USE_FOLDER_DOCUMENT_KEY_CACHE=true  # Cache folders
JAMA_ITEMS_PAGE_SIZE=100            # Larger pages
DEBUG_JAMA_GET=false                # Disable debug
```

**Result:** 5-50x faster folder resolution

### Debug Mode
```env
USE_FOLDER_DOCUMENT_KEY_CACHE=false  # Disable cache
DEBUG_JAMA_AUTH=true                 # Show OAuth details
DEBUG_JAMA_GET=true                  # Show GET details
```

**Result:** Verbose output for troubleshooting

## Common Issues & Solutions

### ❌ Double slash in URL
```
[DEBUG] GET URL: https://host.com/rest/v1//items
```
**Fixed:** Now uses `build_api_url()` helper

### ❌ Generic JSON error
```
[ERROR] Expecting value: line 47 column 1 (char 46)
```
**Fixed:** Now shows detailed diagnostics:
```
GET /items did not return valid JSON.
Status: 200
URL: https://host.com/rest/v1/items
Content-Type: text/html
Response preview: <html>...
Likely causes: authentication redirect, wrong JAMA_BASE_URL...
```

### ❌ Slow folder lookup
```
(50+ API calls for 50 folders)
```
**Fixed:** Now uses cache:
```
[INFO] Building folder documentKey cache from Jama project 279...
[INFO] Cached 123 folders by documentKey.
(0 additional API calls for folder lookups)
```

### ❌ Duplicate documentKey
```
[ERROR] Folder documentKey 'XXX' matched 2 folders.
```
**Solution:** Add explicit Jama ID to spreadsheet for this folder

### ❌ OAuth token fails
```
OAuth token request failed: 200
Content-Type: text/html
```
**Solution:** Set custom OAuth URL:
```env
JAMA_OAUTH_TOKEN_URL=https://host.com/rest/oauth/token
```

## Documentation Files

- **`README.md`** - Main documentation (if exists)
- **`FOLDER_CACHE_OPTIMIZATION.md`** - Cache optimization guide
- **`OAUTH_TROUBLESHOOTING.md`** - OAuth & JSON parsing issues
- **`FOLDER_LOOKUP_GUIDE.md`** - Folder resolution guide
- **`CACHE_IMPLEMENTATION_SUMMARY.md`** - Technical implementation details
- **`CHANGES_SUMMARY.md`** - Recent changes summary
- **`QUICK_REFERENCE.md`** - This file

## Support

### Enable Debug Mode
```bash
export DEBUG_JAMA_AUTH=true
export DEBUG_JAMA_GET=true
python3 csv2jama.py --mode upsert --dry-run 2>&1 | tee debug.log
```

### Check Configuration
```bash
python3 csv2jama.py --mode upsert --dry-run
# Look for configuration summary at startup
```

### Verify Compile
```bash
python3 -m py_compile csv2jama.py
# Should complete with no output
```

### Test Cache
```bash
# With cache (fast)
time python3 csv2jama.py --mode upsert --dry-run

# Without cache (slow)
export USE_FOLDER_DOCUMENT_KEY_CACHE=false
time python3 csv2jama.py --mode upsert --dry-run
```

## Key Features

✅ OAuth 2.0, Bearer Token, and Basic Auth support
✅ SSL certificate support (custom certs)
✅ Folder resolution by documentKey (cached)
✅ Upsert mode (create or update)
✅ Dry-run mode (safe testing)
✅ Hybrid hierarchy (sections + flat requirements)
✅ Item type validation
✅ Description validation (required for requirements)
✅ Debug mode (detailed API diagnostics)
✅ Import results CSV output

## Version History

- **2026-06-02:** Folder cache optimization (5-50x faster)
- **2026-06-02:** URL building fix (no more double slashes)
- **2026-06-02:** JSON parsing diagnostics (clear error messages)
- **2026-06-02:** Subsystem mapping correction (Set item type)

## Last Updated
2026-06-02
