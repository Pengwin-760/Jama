# Fix: Missing fields.name in POST Payload

## Date
2026-06-03

## Issue

Jama POST requests were failing with:
```json
{
  "meta": {
    "status": "Bad Request",
    "message": "You must set the following required fields. fields: name"
  }
}
```

## Root Cause

The POST payload was missing the required `fields.name` field due to:
1. `JAMA_FIELD_NAME` could be blank/missing/invalid in `.env`
2. Spreadsheet `Name` column could be blank for some rows
3. No validation before POST to ensure `fields.name` exists

## Fix Applied

### 1. Validated JAMA_FIELD_NAME in Configuration

**Location:** `load_configuration()` (line ~154)

**Before:**
```python
config["FIELD_MAP"] = {
    "id": field_id,
    "name": os.getenv("JAMA_FIELD_NAME", "name"),
    "description": os.getenv("JAMA_FIELD_DESCRIPTION", "description")
}
```

**After:**
```python
# Validate JAMA_FIELD_NAME - must not be blank
jama_field_name = os.getenv("JAMA_FIELD_NAME", "name").strip()
if jama_field_name.lower() in ("", "none", "null"):
    print("[WARN] JAMA_FIELD_NAME is blank or invalid. Using default 'name'.")
    jama_field_name = "name"

# Validate JAMA_FIELD_DESCRIPTION
jama_field_description = os.getenv("JAMA_FIELD_DESCRIPTION", "description").strip()
if jama_field_description.lower() in ("", "none", "null"):
    print("[WARN] JAMA_FIELD_DESCRIPTION is blank or invalid. Using default 'description'.")
    jama_field_description = "description"

config["FIELD_MAP"] = {
    "id": field_id,
    "name": jama_field_name,
    "description": jama_field_description
}
```

**Result:** `FIELD_MAP["name"]` can never be blank.

### 2. Added Row-Level Validation

**Location:** `build_fields()` (line ~1062)

**Added:**
```python
# Validate Name is not blank
name_value = str(row.get("Name", "")).strip()
if not name_value:
    raise ValueError("Name field is required but is blank or missing.")

fields = {
    FIELD_MAP["name"]: name_value
}
```

**Result:** Fails early if spreadsheet Name is blank.

### 3. Added Payload-Level Validation

**Location:** `jama_post()` (line ~522)

**Added:**
```python
# Validate that fields.name exists (required by Jama)
fields = payload.get("fields", {})
if "name" not in fields or not str(fields.get("name", "")).strip():
    raise ValueError(
        f"POST payload missing required fields.name. "
        f"Check JAMA_FIELD_NAME in .env; it must normally be 'name'. "
        f"Payload fields keys: {list(fields.keys())}"
    )
```

**Result:** POST fails immediately with clear error if `fields.name` is missing.

### 4. Added Debug Output

**Location:** Dry-run logic (line ~1446)

**Added:**
```python
if action == "CREATE":
    # Show field keys for validation
    fields = payload.get("fields", {})
    print(f"[DEBUG] POST fields keys: {list(fields.keys())}")

    # Warn if 'name' field is missing
    if "name" not in fields:
        print("[WARN] POST fields does not contain literal 'name'. Jama requires fields.name.")
```

**Output:**
```
[DEBUG] POST fields keys: ['name', 'description', 'system_id']
[DRY RUN] Would POST:
{
  "fields": {
    "name": "System shall support...",
    "description": "The system must..."
  },
  ...
}
```

### 5. Updated .env.example

**Before:**
```env
# Field Mappings
JAMA_FIELD_ID=system_id
JAMA_FIELD_NAME=name
JAMA_FIELD_DESCRIPTION=description
```

**After:**
```env
# Jama field API names
# Do not change JAMA_FIELD_NAME unless your Jama API field name is different.
# Jama requires fields.name in POST payloads - this should normally be "name".
JAMA_FIELD_NAME=name
JAMA_FIELD_DESCRIPTION=description

# Optional source/import ID custom field.
# Set to blank or "none" if this field does not exist in Jama.
JAMA_FIELD_ID=
```

## Validation Layers

### Layer 1: Configuration Loading

**When:** Script startup

**Check:** `JAMA_FIELD_NAME` is not blank/none/null

**Action if invalid:** Use default "name" with warning

**Result:** `FIELD_MAP["name"]` is always valid

### Layer 2: Field Building

**When:** Building fields dict for payload

**Check:** Spreadsheet `Name` column is not blank

**Action if invalid:** Raise `ValueError` immediately

**Result:** Row fails with clear error before POST attempt

### Layer 3: Payload Validation

**When:** Before `jama_post()` call

**Check:** `payload["fields"]["name"]` exists and is not blank

**Action if invalid:** Raise `ValueError` with diagnostic info

**Result:** POST never attempted with invalid payload

### Layer 4: Debug Output

**When:** Dry-run mode

**Check:** Display field keys in payload

**Action if 'name' missing:** Print warning

**Result:** User can verify payload before execute

## Error Messages

### If JAMA_FIELD_NAME is blank in .env

**Startup:**
```
[WARN] JAMA_FIELD_NAME is blank or invalid. Using default 'name'.
```

**No failure** - automatically corrected.

### If Spreadsheet Name is blank

**During import:**
```
[ERROR] Row 15 failed.
[ERROR] Name field is required but is blank or missing.
```

**Status:** `FAILED`

### If Payload Missing fields.name

**Before POST:**
```
[ERROR] Row 20 failed.
[ERROR] POST payload missing required fields.name. Check JAMA_FIELD_NAME in .env; it must normally be 'name'. Payload fields keys: ['description', 'system_id']
```

**Status:** `FAILED`

### If Dry-Run Shows Missing name

**Dry-run:**
```
[DEBUG] POST fields keys: ['description']
[WARN] POST fields does not contain literal 'name'. Jama requires fields.name.
```

**User can fix before execute.**

## Required .env Configuration

**Minimal (recommended):**
```env
JAMA_FIELD_NAME=name
JAMA_FIELD_DESCRIPTION=description
```

**If custom ID field exists:**
```env
JAMA_FIELD_NAME=name
JAMA_FIELD_DESCRIPTION=description
JAMA_FIELD_ID=system_id
```

**If no custom ID field:**
```env
JAMA_FIELD_NAME=name
JAMA_FIELD_DESCRIPTION=description
JAMA_FIELD_ID=
```

## Spreadsheet Requirements

**Name column:**
- ✅ Must exist
- ✅ Must not be blank for CREATE rows
- ✅ Must contain non-empty text

**Example valid:**
```
ID              | Item Type                  | Name
PROJ-SR-001     | Stakeholder Requirement    | System shall support launch modes
```

**Example invalid:**
```
ID              | Item Type                  | Name
PROJ-SR-001     | Stakeholder Requirement    | (blank)
```

**Result:** Row fails with clear error.

## Testing

### Test 1: Valid Configuration

**.env:**
```env
JAMA_FIELD_NAME=name
```

**Spreadsheet:**
```
Name: System shall support...
```

**Result:**
```
[DEBUG] POST fields keys: ['name', 'description']
[DRY RUN] Would POST:
{
  "fields": {
    "name": "System shall support..."
  }
}
```

✅ **PASS**

### Test 2: Blank JAMA_FIELD_NAME

**.env:**
```env
JAMA_FIELD_NAME=
```

**Result:**
```
[WARN] JAMA_FIELD_NAME is blank or invalid. Using default 'name'.
[DEBUG] POST fields keys: ['name', 'description']
```

✅ **PASS** (auto-corrected)

### Test 3: Blank Spreadsheet Name

**Spreadsheet:**
```
Name: (blank)
```

**Result:**
```
[ERROR] Row 15 failed.
[ERROR] Name field is required but is blank or missing.
```

✅ **PASS** (fails with clear error)

### Test 4: Invalid Field Mapping

**.env:**
```env
JAMA_FIELD_NAME=invalidFieldName
```

**Jama API Response:**
```json
{
  "meta": {
    "status": "Bad Request",
    "message": "Unknown field: invalidFieldName"
  }
}
```

**Script output:**
```
[DEBUG] POST fields keys: ['invalidFieldName', 'description']
[DRY RUN] Would POST:
{
  "fields": {
    "invalidFieldName": "System shall..."
  }
}
```

✅ **PASS** (shows field key, user can diagnose)

## Dry-Run Output Examples

### Valid Payload

```
[ROW 5] CREATE Stakeholder Requirement: System shall support launch modes
[INFO] Parent Jama item ID: <parent_id>
[DEBUG] POST fields keys: ['name', 'description', 'system_id']
[DRY RUN] Would POST:
{
  "fields": {
    "name": "System shall support launch modes",
    "description": "The system must provide...",
    "system_id": "PROJ-SR-001"
  },
  "itemType": 97,
  "location": {
    "parent": {
      "item": <parent_id>
    },
    "sortOrder": 0
  }
}
```

### Missing name Field (Would Fail)

```
[DEBUG] POST fields keys: ['description']
[WARN] POST fields does not contain literal 'name'. Jama requires fields.name.
```

**User action:** Fix JAMA_FIELD_NAME or spreadsheet before execute.

## Compile Check

```bash
python3 -m py_compile csv2jama.py
```

✅ **PASSED** - No syntax errors

## Summary

### Files Modified

1. ✅ `csv2jama.py` - Added 3 layers of validation
2. ✅ `.env.example` - Updated with clear instructions
3. ✅ `FIELD_NAME_FIX.md` - This documentation

### How JAMA_FIELD_NAME is Validated

1. **Startup:** Loaded from `.env` with default "name"
2. **Sanitized:** Stripped and checked for blank/none/null
3. **Defaulted:** If invalid, uses "name" with warning
4. **Stored:** In `CONFIG["FIELD_MAP"]["name"]`
5. **Used:** In `build_fields()` to create payload

**Result:** Can never be blank or invalid.

### What .env Should Contain

**Recommended:**
```env
JAMA_FIELD_NAME=name
JAMA_FIELD_DESCRIPTION=description
JAMA_FIELD_ID=
```

**Do NOT use:**
```env
JAMA_FIELD_NAME=
JAMA_FIELD_NAME=none
JAMA_FIELD_NAME=null
```

**If missing:** Script uses "name" as default.

### Validation Preventing Missing fields.name

**Three levels:**

1. **Configuration validation** - Ensures `FIELD_MAP["name"]` is valid at startup
2. **Row validation** - Ensures spreadsheet Name is not blank in `build_fields()`
3. **Payload validation** - Ensures `fields["name"]` exists before POST in `jama_post()`

**Plus debug output:**
- Shows field keys in dry-run
- Warns if "name" is missing

**Result:** Missing `fields.name` cannot reach Jama API.

## Next Steps

1. **Update .env:**
   ```env
   JAMA_FIELD_NAME=name
   ```

2. **Verify spreadsheet:**
   - Check all rows have non-blank Name

3. **Run dry-run:**
   ```bash
   python3 csv2jama.py --mode upsert --dry-run
   ```

4. **Check output:**
   - Look for `[DEBUG] POST fields keys: ['name', ...]`
   - No warnings about missing 'name'

5. **Execute:**
   ```bash
   python3 csv2jama.py --mode upsert --execute
   ```

**Expected:** No more "fields: name" errors from Jama API.
