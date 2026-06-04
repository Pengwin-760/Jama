# Dynamic Verification Method Field Key Resolution

## Overview
Updated `csv2jama.py` to support dynamic verification method field key resolution with item-type-specific suffixes like `verification_method$112`, `verification_method$87`, etc.

## Problem
Jama field keys may have item-type-specific suffixes:
```
verification_method$86   (Stakeholder Requirement)
verification_method$87   (Subsystem Requirement)
verification_method$112  (Software Requirement)
verification_method$<any number>
```

The script previously could not dynamically determine which field key to use based on the current requirement item type.

## Solution
Added dynamic field key resolution that:
1. Prefers exact configured field keys
2. Appends item type ID to base names
3. Searches cached items for matching patterns
4. Falls back intelligently when multiple keys exist

## Changes Made

### 1. New Helper Functions (after line 41)

**`is_verification_method_field_key(key)`**
```python
def is_verification_method_field_key(key: str) -> bool:
    """Check if a field key matches verification_method$<number> pattern."""
```

**`collect_verification_method_field_keys(items_or_fields)`**
```python
def collect_verification_method_field_keys(items_or_fields) -> set:
    """Collect all verification method field keys from items or fields."""
```

**`find_verification_method_field_key(item_type_id)`**
```python
def find_verification_method_field_key(item_type_id: int = None) -> Optional[str]:
    """Dynamically resolve the verification method field key."""
```

### 2. Updated `build_fields()` (line 1481)

**Before:**
```python
def build_fields(row: pd.Series) -> Dict[str, Any]:
    # Used hardcoded FIELD_MAP["verification_method"]
    verification_field = FIELD_MAP.get("verification_method")
    fields[verification_field] = picklist_id
```

**After:**
```python
def build_fields(row: pd.Series, item_type_id: int = None) -> Dict[str, Any]:
    # Dynamically resolves field key based on item type
    verification_field_key = find_verification_method_field_key(item_type_id)
    fields[verification_field_key] = picklist_id
```

### 3. Updated `build_payload()` (line 1597)

Now passes `item_type_id` to `build_fields()`:
```python
item_type_id = ITEM_TYPE_IDS[item_type_name]
payload = {
    "fields": build_fields(row, item_type_id),
    "itemType": item_type_id,
    ...
}
```

### 4. Enhanced Logging (line 2330)

Shows resolved field key:
```python
print(f"[INFO] Verification Method: T -> Test -> picklist ID 422")
print(f"[INFO] Verification Method field key resolved: verification_method$112")
```

### 5. Updated `.env.example`

Added comprehensive comments explaining usage.

## Field Key Resolution Priority

**A. Exact configured key**
```env
JAMA_FIELD_VERIFICATION_METHOD=verification_method$112
```
→ Uses `verification_method$112` directly

**B. Base name + item type ID**
```env
JAMA_FIELD_VERIFICATION_METHOD=verification_method
```
For Software Requirement (itemType=112):
→ Uses `verification_method$112`

**C. Dynamic search in cached items**
```env
JAMA_FIELD_VERIFICATION_METHOD=
```
Searches cached items for `verification_method$112` (matches item type)

**D. Fallback to any single match**
If only one `verification_method$<number>` exists in cache, uses it

**E. Fail with clear error**
If multiple keys exist and none match, provides helpful error message

## Excel Input Support

Verification Method column accepts:

| Excel Value | Normalized | Picklist ID |
|-------------|------------|-------------|
| T           | Test       | 422         |
| Test        | Test       | 422         |
| TEST        | Test       | 422         |
| A           | Analysis   | 418         |
| Analysis    | Analysis   | 418         |
| I           | Inspection | 420         |
| Inspection  | Inspection | 420         |
| D           | Demonstration | 419      |
| Demo        | Demonstration | 419      |

## Payload Examples

### Software Requirement (itemType=112)
```json
{
  "fields": {
    "name": "Launch Modes Support",
    "description": "The software shall...",
    "verification_method$112": 422
  },
  "itemType": 112,
  "location": {
    "parent": {"item": 123456}
  }
}
```

### Subsystem Requirement (itemType=87)
```json
{
  "fields": {
    "name": "Power Supply Requirements",
    "description": "The subsystem shall...",
    "verification_method$87": 418
  },
  "itemType": 87,
  "location": {
    "parent": {"item": 123456}
  }
}
```

### Stakeholder Requirement (itemType=97)
```json
{
  "fields": {
    "name": "User Interface Requirements",
    "description": "The system shall...",
    "verification_method$97": 420
  },
  "itemType": 97,
  "location": {
    "parent": {"item": 123456}
  }
}
```

## Error Messages

### Multiple keys, no match
```
Row X has Verification Method populated, but multiple verification method fields found:
verification_method$86, verification_method$112.
Could not determine which to use for itemType 87.
Configure JAMA_FIELD_VERIFICATION_METHOD explicitly in .env.
```

### No keys found
```
Row X has Verification Method populated, but no verification method field key could be resolved.
Searched for JAMA_FIELD_VERIFICATION_METHOD and dynamic keys matching verification_method$<number>.
Configure JAMA_FIELD_VERIFICATION_METHOD in .env.
```

## Logging Examples

### With exact field key
```
[INFO] Verification Method: T -> Test -> picklist ID 422
[INFO] Verification Method field key resolved: verification_method$112
```

### With base name
```
[INFO] Verification Method: A -> Analysis -> picklist ID 418
[INFO] Verification Method field key resolved: verification_method$87
```

### With dynamic detection
```
[INFO] Verification Method: I -> Inspection -> picklist ID 420
[INFO] Verification Method field key resolved: verification_method$97
```

## Text Rows
Text rows do not have verification method (preserved behavior):
- No verification method field in payload
- Verification Method column ignored for Text rows
- Only applies to requirement item types

## Configuration Examples

### Software Requirements Import
```env
# Option 1: Exact key
JAMA_FIELD_VERIFICATION_METHOD=verification_method$112

# Option 2: Base name (script appends $112)
JAMA_FIELD_VERIFICATION_METHOD=verification_method

# Option 3: Blank (dynamic detection)
JAMA_FIELD_VERIFICATION_METHOD=
```

### Subsystem Requirements Import
```env
# Option 1: Exact key
JAMA_FIELD_VERIFICATION_METHOD=verification_method$87

# Option 2: Base name (script appends $87)
JAMA_FIELD_VERIFICATION_METHOD=verification_method

# Option 3: Blank (dynamic detection)
JAMA_FIELD_VERIFICATION_METHOD=
```

### Stakeholder Requirements Import
```env
# Option 1: Exact key
JAMA_FIELD_VERIFICATION_METHOD=verification_method$97

# Option 2: Base name (script appends $97)
JAMA_FIELD_VERIFICATION_METHOD=verification_method

# Option 3: Blank (dynamic detection)
JAMA_FIELD_VERIFICATION_METHOD=
```

## Preserved Behavior

✓ Text rows don't include verification method
✓ Verification Method is optional for requirements
✓ Blank values are skipped
✓ Parent childItemType validation remains active
✓ Folder resolution by documentKey
✓ Section hierarchy preserved
✓ Dry-run default
✓ Simple commands:
  ```bash
  python csv2jama.py
  python csv2jama.py --execute
  ```

## Testing

### Syntax Check
```bash
python3 -m py_compile csv2jama.py
```
✓ SUCCESS

### Expected Dry-Run Logs

For Software Requirement with Verification Method "T":
```
[ROW 10] CREATE Software Requirement: Launch Modes Support
[INFO] Verification Method: T -> Test -> picklist ID 422
[INFO] Verification Method field key resolved: verification_method$112
[DRY RUN] Would POST:
{
  "fields": {
    "name": "Launch Modes Support",
    "description": "...",
    "verification_method$112": 422
  },
  "itemType": 112,
  ...
}
```

For Subsystem Requirement with Verification Method "Analysis":
```
[ROW 20] CREATE Subsystem Requirement: Power Requirements
[INFO] Verification Method: Analysis -> Analysis -> picklist ID 418
[INFO] Verification Method field key resolved: verification_method$87
[DRY RUN] Would POST:
{
  "fields": {
    "name": "Power Requirements",
    "description": "...",
    "verification_method$87": 418
  },
  "itemType": 87,
  ...
}
```

## Files Changed

1. **csv2jama.py**
   - Added VERIFICATION_FIELD_PATTERN regex
   - Added `is_verification_method_field_key()`
   - Added `collect_verification_method_field_keys()`
   - Added `find_verification_method_field_key()`
   - Updated `build_fields()` signature
   - Updated `build_payload()` to pass item_type_id
   - Enhanced logging for verification method
   - Syntax: ✓ python3 -m py_compile → SUCCESS

2. **.env.example**
   - Updated JAMA_FIELD_VERIFICATION_METHOD comments
   - Added examples for exact key, base name, and blank
   - Documented supported Excel values

## Summary

✓ **Dynamic field key resolution** - automatically matches item type
✓ **Flexible configuration** - supports exact key, base name, or auto-detect
✓ **Clear error messages** - helps troubleshoot configuration issues
✓ **Enhanced logging** - shows resolved field key for transparency
✓ **Excel flexibility** - accepts letters (T, A, I, D) or full words
✓ **Item type aware** - prefers keys matching current item type
✓ **Fallback support** - uses single available key when appropriate
✓ **All behavior preserved** - no breaking changes
