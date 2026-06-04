# Verification Method Dynamic Field-Key Resolution

## Overview

The verification method field-key resolution in `csv2jama.py` now uses dynamic detection similar to `jama2csv.py`. The script searches for fields starting with `verification_method$` in cached Jama items, rather than assuming a specific suffix.

## Key Changes

### 1. Dynamic Field Key Detection

**Uses `startswith()` instead of hardcoded suffixes:**

```python
def is_verification_method_field_key(field_name: str) -> bool:
    """Check if a field key matches the verification method pattern."""
    if not field_name:
        return False
    return str(field_name).startswith("verification_method$")
```

### 2. Search Cached Items

**Similar to export logic, searches actual Jama items:**

```python
def collect_verification_method_field_keys_from_cached_items(item_type_id: Optional[int] = None) -> set:
    """
    Dynamically collect verification method field keys from cached Jama items.
    Similar to jama2csv.py logic.
    """
    keys = set()
    for item in _item_metadata_by_id.values():
        if item_type_id is not None and item.get("itemType") != item_type_id:
            continue
        
        fields = item.get("fields", {})
        for field_name in fields.keys():
            if is_verification_method_field_key(field_name):
                keys.add(field_name)
    
    return keys
```

### 3. Resolution Strategy

**Priority order for resolving field keys:**

```
A. Exact .env configuration
   JAMA_FIELD_VERIFICATION_METHOD=verification_method$243
   → Use exactly as specified

B. Dynamic search - type-specific
   Search cached items of the same itemType (e.g., itemType=112)
   If exactly 1 candidate found → Use it
   If multiple found → Fail with list of candidates

C. Dynamic search - project-wide
   Search all cached items in the project
   If exactly 1 candidate found → Use it (with warning)
   If multiple found → Fail with list of candidates

D. No candidates found
   Fail with guidance to either:
   - Run with existing items in cache
   - Set JAMA_FIELD_VERIFICATION_METHOD explicitly
```

### 4. Error Messages

**Clear guidance when resolution fails:**

```text
Row has Verification Method populated, but multiple verification method field keys found for Software Requirement (itemType=112):
  verification_method$112, verification_method$243

Could not determine which to use.

Solution: Set JAMA_FIELD_VERIFICATION_METHOD in .env to the correct key.
Example: JAMA_FIELD_VERIFICATION_METHOD=verification_method$243
```

## Resolution Examples

### Example 1: Single Type-Specific Field

**Scenario:**
- Project has items with `verification_method$243`
- All Software Requirements (itemType=112) use `verification_method$243`
- Only one candidate found

**Resolution:**
```
[INFO] Verification Method: T -> Test -> 422
[INFO] Verification field key candidates found (itemType=112): verification_method$243
[INFO] Verification field key resolved dynamically: verification_method$243
[INFO] Verification payload: "verification_method$243": 422 (flat integer)
```

### Example 2: Multiple Candidates (Ambiguous)

**Scenario:**
- Project has both `verification_method$112` and `verification_method$243`
- No clear type-specific match

**Resolution:**
```
[ERROR] Row has Verification Method populated, but multiple verification method field keys found:
  verification_method$112, verification_method$243

Solution: Set JAMA_FIELD_VERIFICATION_METHOD=verification_method$243 in .env
```

### Example 3: Explicit .env Override

**Scenario:**
- `.env` has `JAMA_FIELD_VERIFICATION_METHOD=verification_method$243`

**Resolution:**
```
[INFO] Verification Method: T -> Test -> 422
[INFO] Verification field key from .env: verification_method$243
[INFO] Verification payload: "verification_method$243": 422 (flat integer)
```

### Example 4: Project-Wide Fallback

**Scenario:**
- No items of the target itemType have verification fields
- But exactly one verification field found project-wide: `verification_method$243`

**Resolution:**
```
[INFO] Verification Method: T -> Test -> 422
[INFO] Verification field key candidates found (project-wide): verification_method$243
[INFO] Verification field key resolved dynamically: verification_method$243
[INFO] Verification payload: "verification_method$243": 422 (flat integer)
```

## Configuration

### .env.example

```env
# Optional. Leave blank for dynamic detection from existing Jama item metadata.
# If dynamic detection is ambiguous, set the exact key seen in Jama, e.g. verification_method$243.
JAMA_FIELD_VERIFICATION_METHOD=
```

### Startup Summary

```
Verification Method Field:            dynamic (searches cached items for verification_method$...)
Verification Method Value Shape:      flat integer (e.g., 422)
Verification Method Detection:        searches fields.keys() using startswith('verification_method$')
```

## Important Notes

### 1. Field Suffix Does Not Always Match Item Type

The suffix (e.g., `$243`) is **not** guaranteed to match the item type ID (e.g., `112`).

**Do NOT assume:**
```python
verification_method$<itemType>  # This is wrong!
```

**Instead, search dynamically:**
```python
for field_name in fields.keys():
    if field_name.startswith("verification_method$"):
        # Found the actual field key
```

### 2. Value Format Remains Flat Integer

The value is always a flat integer:

```json
{
  "verification_method$243": 422
}
```

**Never wrapped:**
```json
// WRONG:
"verification_method$243": "422"
"verification_method$243": {"id": 422}
"verification_method$243": [422]
```

### 3. Only Applies to Requirements

Verification method only applies to:
- Stakeholder Requirement
- Subsystem Requirement
- Software Requirement
- System Requirement (if configured)

**Does NOT apply to:**
- Folder
- Set
- Segment
- Subsystem
- Text
- Text Document

### 4. Cache Must Be Built First

The dynamic search requires the project item cache to be populated. This happens automatically when:
- Running with `USE_FOLDER_DOCUMENT_KEY_CACHE=true` (default)
- The cache is built via GET `/items` with pagination

If cache is empty, the script will:
1. Try to use base name from .env if configured
2. Otherwise fail with guidance

## Testing

### 1. Compile Check

```bash
python3 -m py_compile csv2jama.py
```

(No output = success)

### 2. Verification Method Mapping

```bash
python3 test_verification_simple.py
```

Expected:
```
✓ T -> Test -> 422
✓ I -> Inspection -> 420
✓ D -> Demonstration -> 419
✓ A -> Analysis -> 418
```

### 3. Dry-Run with Verification

```bash
python3 csv2jama.py
```

Look for:
```
[INFO] Verification Method: T -> Test -> 422
[INFO] Verification field key candidates found (itemType=112): verification_method$243
[INFO] Verification field key resolved dynamically: verification_method$243
[INFO] Verification payload: "verification_method$243": 422 (flat integer)
```

## Comparison with Export Script

### Export (jama2csv.py)

```python
def get_verification_method(fields: Dict[str, Any]) -> str:
    raw_value = ""
    
    for field_name, field_value in fields.items():
        if field_name.startswith("verification_method$"):
            raw_value = field_value
            break
    
    if raw_value == "":
        raw_value = get_field(...)
```

### Import (csv2jama.py)

```python
def collect_verification_method_field_keys_from_cached_items(item_type_id: Optional[int] = None) -> set:
    keys = set()
    for item in _item_metadata_by_id.values():
        if item_type_id is not None and item.get("itemType") != item_type_id:
            continue
        
        fields = item.get("fields", {})
        for field_name in fields.keys():
            if field_name.startswith("verification_method$"):
                keys.add(field_name)
    
    return keys
```

**Key similarities:**
- Both use `startswith("verification_method$")`
- Both search dynamically through fields
- Both do not hardcode the suffix

**Differences:**
- Export searches one item's fields
- Import searches all cached items to discover the field key pattern

## Troubleshooting

### Problem: "Multiple verification method field keys found"

**Cause:** Project has both `verification_method$112` and `verification_method$243`

**Solution:** Set explicit field key in `.env`:
```env
JAMA_FIELD_VERIFICATION_METHOD=verification_method$243
```

### Problem: "No verification method field keys found in cached Jama items"

**Cause:** Cache is empty or no items have verification fields

**Solutions:**
1. Ensure project has existing items with verification method fields
2. Run script with items already in Jama so cache is populated
3. Set explicit field key in `.env`

### Problem: Jama rejects verification_method$112 with value 422

**Cause:** Field key suffix is wrong for this item type

**Diagnosis:**
- Value 422 is correct (flat integer)
- Suffix $112 may not be the right field for this project

**Solution:** Set correct field key in `.env`:
```env
JAMA_FIELD_VERIFICATION_METHOD=verification_method$243
```

Or inspect a known-good item in Jama to find the actual field key.

## Summary

The import script now:
✓ Searches dynamically for `verification_method$*` fields  
✓ Does not assume suffix matches item type ID  
✓ Prioritizes type-specific candidates  
✓ Falls back to project-wide search if needed  
✓ Fails clearly with candidate list if ambiguous  
✓ Supports explicit `.env` override when needed  
✓ Uses flat integer values (not wrapped)  
✓ Logs exactly what was resolved and how  

This matches the export script's dynamic approach and handles real-world scenarios where field suffixes vary.
