# Fix: Dynamic Verification Method Field-Key Discovery for Empty Sets

## Problem

When the target Set is empty, dynamic verification method field-key discovery could fail or choose incorrectly because there are no existing items in that branch to inspect.

**Scenario:**
- Importing requirements into an empty Set
- No existing items of the same type have `verification_method$...` fields
- Script needs to discover which `verification_method$###` field key to use

## Solution

Updated `csv2jama.py` to implement robust dynamic discovery with project-wide fallback:

### 1. Enhanced Resolution Strategy

```
Priority Order:
A. Explicit .env → Use exact configured key
B. Type-specific search → Search cached items with same itemType
C. Project-wide search → Search all cached items (with warning)
D. Fail with guidance → List candidates or suggest explicit config
```

### 2. Key Improvements

**Cache Building Before Discovery:**
```python
if not _item_metadata_by_id:
    print("[INFO] Building project item cache for verification field discovery...")
    try:
        build_folder_document_key_cache()
    except Exception as e:
        print(f"[WARN] Could not build project cache: {e}")
```

**Project-Wide Fallback:**
```python
# Step 2: No type-specific fields found - search whole project
all_keys = collect_verification_method_field_keys_from_cached_items()

if len(all_keys) == 1:
    # Found exactly one verification method field in the whole project
    # Use it with a warning (target Set may be empty)
    return (next(iter(all_keys)), "project_wide")
```

**Resolution Source Tracking:**
- `env_explicit` - From .env with exact key
- `type_specific` - From cached items of same type
- `project_wide` - From cached items project-wide (with warning)
- `multiple_type_specific` - Multiple same-type candidates (ambiguous)
- `multiple_project_wide` - Multiple project candidates (ambiguous)
- `not_found` - No candidates found
- `no_cache` - Cache is empty

### 3. Enhanced Error Messages

**Multiple Project-Wide Candidates:**
```text
Row has Verification Method populated, but multiple verification method field keys found in project:
  verification_method$112, verification_method$243

No items of type Software Requirement (itemType=112) were found in the cache with verification method fields.
The target Set may be empty or may not contain existing examples.

Solution: Set JAMA_FIELD_VERIFICATION_METHOD in .env to the correct key.
Example: JAMA_FIELD_VERIFICATION_METHOD=verification_method$243
```

**No Candidates Found:**
```text
Row has Verification Method populated, but no verification method field keys found in cached Jama items.

The script searched for fields starting with 'verification_method$' in cached items but found none.
The target Set may be empty, or no existing project item exposes the verification method field.

Solution: Either:
  1. Ensure the project cache includes items with verification method fields (run with existing items in Jama)
  2. Set JAMA_FIELD_VERIFICATION_METHOD in .env to the correct key
     Example: JAMA_FIELD_VERIFICATION_METHOD=verification_method$243
```

### 4. Enhanced Logging

**Type-Specific Resolution:**
```text
[INFO] Verification Method: T -> Test -> 422
[INFO] Verification field key candidates for itemType=112: verification_method$243
[INFO] Verification field key resolved dynamically (type-specific): verification_method$243
[INFO] Verification payload value: 422 (flat integer)
```

**Project-Wide Fallback (with warning):**
```text
[INFO] Verification Method: T -> Test -> 422
[WARN] No same-itemType verification field found for itemType=112
[WARN] Using only project-wide candidate: verification_method$243
[INFO] Project-wide verification field key candidates: verification_method$243
[INFO] Verification payload value: 422 (flat integer)
```

**Explicit .env Override:**
```text
[INFO] Verification Method: T -> Test -> 422
[INFO] Verification field key from .env (explicit): verification_method$243
[INFO] Verification payload value: 422 (flat integer)
```

## Changes Made

### File: `csv2jama.py`

**1. Updated `resolve_verification_method_field_key()` (lines ~101-187):**
- Returns tuple `(field_key, resolution_source)` instead of just field_key
- Builds cache if empty before searching
- Implements project-wide fallback with clear source tracking
- Returns resolution source for better logging

**2. Updated `build_fields()` (lines ~1615-1690):**
- Handles new tuple return from resolver
- Improved error messages mentioning empty target Sets
- Uses resolution source for better diagnostics

**3. Updated verification logging (lines ~2443-2462):**
- Shows different messages based on resolution source
- Warns when using project-wide fallback
- Shows candidates list for clarity

**4. Updated `.env.example` (lines ~90-107):**
- Mentions empty Set scenario
- Updated guidance for dynamic detection

## Testing

### Compilation Check
```bash
test_venv/bin/python -m py_compile csv2jama.py
```
**Result:** ✅ PASSED

### Integration Test
```bash
test_venv/bin/python test_with_env_override.py
```
**Result:** ✅ PASSED
- All verification mappings correct
- item_type_id properly derived
- Flat integer values
- All requirement types work

### Empty Set Scenario Test
```bash
python3 test_empty_set_scenario.py
```
**Result:** ✅ PASSED
- Documents all scenarios
- Resolution strategy verified
- Error messages documented

## Scenarios

### Scenario 1: Empty Set, Single Project-Wide Field

**Setup:**
- Target Set is empty
- No Software Requirements (112) exist with verification fields
- Project has exactly one: `verification_method$243`

**Behavior:**
```text
[WARN] No same-itemType verification field found for itemType=112
[WARN] Using only project-wide candidate: verification_method$243
→ Uses verification_method$243 successfully
```

### Scenario 2: Empty Set, Multiple Project-Wide Fields (Ambiguous)

**Setup:**
- Target Set is empty
- No Software Requirements (112) exist with verification fields
- Project has: `verification_method$112`, `verification_method$243`

**Behavior:**
```text
[ERROR] Multiple verification method field keys found in project:
  verification_method$112, verification_method$243
→ Fails with list of candidates
→ Suggests explicit .env configuration
```

### Scenario 3: Empty Set, No Fields Found

**Setup:**
- Target Set is empty
- No items in project have verification fields

**Behavior:**
```text
[ERROR] No verification method field keys found in cached Jama items.
[ERROR] The target Set may be empty, or no existing project item
        exposes the verification method field.
→ Fails with guidance
→ Suggests either adding sample items or explicit .env config
```

### Scenario 4: Explicit .env Override (Safest)

**Setup:**
```env
JAMA_FIELD_VERIFICATION_METHOD=verification_method$243
```

**Behavior:**
```text
[INFO] Verification field key from .env (explicit): verification_method$243
→ Bypasses dynamic discovery completely
→ No warnings
→ Recommended when target Set is empty and field key is known
```

## Recommendations

### For Empty Target Sets:

**Option 1: Explicit Configuration (Safest)**
```env
JAMA_FIELD_VERIFICATION_METHOD=verification_method$243
```
- Bypasses dynamic discovery
- No warnings
- Always works regardless of cache state

**Option 2: Ensure Sample Items Exist**
- Add at least one requirement of the target type to the project
- Script will discover the field dynamically
- Works automatically after first item

**Option 3: Let Script Use Project-Wide Fallback**
- If project has exactly one verification field
- Script will use it with warning
- Works but shows warning about fallback

## Key Points

✅ **Does not assume suffix equals item type ID**
- `verification_method$243` may be used for itemType=112
- Dynamic discovery finds actual field key

✅ **Searches using `startswith('verification_method$')`**
- Same concept as export script
- Flexible field key detection

✅ **Works even if target Set is empty**
- Falls back to project-wide search
- Warns when using fallback
- Fails clearly when ambiguous

✅ **Values remain flat integers**
- `422` (not `"422"`, `{"id": 422}`, or `[422]`)

✅ **Mappings unchanged**
- T / Test → 422
- I / Inspection → 420
- D / Demonstration → 419
- A / Analysis → 418

## Status

✅ **COMPLETE**

Dynamic verification method field-key discovery now:
- ✓ Handles empty target Sets
- ✓ Falls back to project-wide search when needed
- ✓ Warns about fallback usage
- ✓ Fails clearly with guidance when ambiguous
- ✓ Builds cache before searching
- ✓ Provides detailed error messages
- ✓ Supports explicit .env override

Ready to use!
