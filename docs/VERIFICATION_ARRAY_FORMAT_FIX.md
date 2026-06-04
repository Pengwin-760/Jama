# Verification Method Array Format Fix

## Important Correction

The verification method payload format has been corrected to use an **array of picklist IDs** instead of a flat integer.

### Correct Format

```json
{
  "fields": {
    "name": "VMC Power-On BIT (PBIT) Execution",
    "description": "Test description",
    "verification_method$112": [
      422
    ]
  }
}
```

### Incorrect Format (Previous)

```json
{
  "fields": {
    "verification_method$112": 422
  }
}
```

## Reason for Change

Verification Method is a **Jama multi-select/picklist-style field** that expects an array of picklist option IDs, not a single integer value.

The export script handles this correctly:

```python
if isinstance(raw_value, list):
    if not raw_value:
        return ""
    raw_value = raw_value[0]  # Extract first element from list
```

## Changes Made

### 1. Added Helper Function

**Location:** Lines ~208-223

```python
def format_verification_method_value(picklist_id: int) -> list:
    """
    Format verification method picklist ID for Jama API payload.

    Verification Method is a Jama multi-select/picklist-style field and must be
    sent as an array of picklist option IDs.

    Args:
        picklist_id: Picklist option ID (e.g., 422)

    Returns:
        Array containing the picklist ID (e.g., [422])

    Examples:
        format_verification_method_value(422) → [422]
        format_verification_method_value(420) → [420]
    """
    return [int(picklist_id)]
```

### 2. Updated Payload Generation

**Location:** Lines ~1705-1710

**Before:**
```python
fields[verification_field_key] = picklist_id
```

**After:**
```python
fields[verification_field_key] = format_verification_method_value(picklist_id)
```

### 3. Updated Logging

**Location:** Line ~2479

**Before:**
```python
print(f"[INFO] Verification payload value: {picklist_id} (flat integer)")
```

**After:**
```python
print(f"[INFO] Verification payload value: [{picklist_id}]")
```

### 4. Updated Error Guidance

**Location:** Lines ~814-820

**Before:**
```text
The value is already a flat integer. This likely means the field key suffix is wrong...
```

**After:**
```text
Verification Method is a Jama multi-select/picklist-style field sent as an array of IDs.
If Jama rejects it, the field key suffix may be wrong...
```

### 5. Updated Configuration Summary

**Location:** Line ~526

**Before:**
```text
Verification Method Value Shape:      flat integer (e.g., 422)
```

**After:**
```text
Verification Method Value Format:     array of picklist IDs (e.g., [422])
```

### 6. Updated .env.example

**Location:** Line ~107

**Before:**
```env
# The value is sent as a flat integer (e.g., 422), not wrapped in object/array/string.
```

**After:**
```env
# Payload value is sent as an array of picklist option IDs, e.g. [422].
```

## Testing Results

### Compilation Check
```bash
test_venv/bin/python -m py_compile csv2jama.py
```
**Result:** ✅ PASSED (no syntax errors)

### Array Format Test
```bash
test_venv/bin/python test_array_format.py
```

**Results:**
```
✓ format_verification_method_value(422) = [422]
✓ format_verification_method_value(420) = [420]
✓ format_verification_method_value(419) = [419]
✓ format_verification_method_value(418) = [418]

✓ Verification field found: verification_method$112
✓ Verification value: [422]
✓ Value type: list
✓ Value is list
✓ List has exactly 1 element
✓ Element is int
✓ Correct value: [422]

✓ T -> Test -> [422]
✓ I -> Inspection -> [420]
✓ D -> Demonstration -> [419]
✓ A -> Analysis -> [418]
```

**Sample Payload:**
```json
{
  "fields": {
    "name": "VMC Power-On BIT (PBIT) Execution",
    "description": "The VMC shall execute PBIT",
    "verification_method$112": [422]
  }
}
```

## Verification Mappings

All mappings now produce array format:

| Excel Input | Normalized | Picklist ID | Payload Value |
|-------------|------------|-------------|---------------|
| T           | Test       | 422         | [422]         |
| I           | Inspection | 420         | [420]         |
| D           | Demonstration | 419      | [419]         |
| A           | Analysis   | 418         | [418]         |
| test        | Test       | 422         | [422]         |
| TEST        | Test       | 422         | [422]         |

## Export Compatibility

The export script (`jama2csv.py`) handles both formats:

```python
if isinstance(raw_value, list):
    if not raw_value:
        return ""
    raw_value = raw_value[0]
```

This means:
- Import sends: `[422]`
- Export reads: `[422]` → extracts `422` → maps to "Test"
- Round-trip works correctly

## Payload Format Comparison

### ✅ CORRECT (Array)
```json
{
  "verification_method$112": [422]
}
```

### ❌ WRONG (Flat Integer)
```json
{
  "verification_method$112": 422
}
```

### ❌ WRONG (String)
```json
{
  "verification_method$112": "422"
}
```

### ❌ WRONG (Object)
```json
{
  "verification_method$112": {"id": 422}
}
```

## Preserved Functionality

All other functionality remains unchanged:

✓ Dynamic field-key detection  
✓ Empty Set support  
✓ Project-wide fallback  
✓ item_type_id derivation  
✓ Letter aliases (T, I, D, A)  
✓ Case-insensitive input  
✓ Only applies to requirement rows  
✓ Does not assume suffix = item type  

## Sample Complete Payload

```json
{
  "fields": {
    "name": "VMC Power-On BIT (PBIT) Execution",
    "description": "The VMC shall execute Power-On Built-In Test (PBIT) upon receiving power.",
    "verification_method$112": [
      422
    ]
  },
  "itemType": 112,
  "location": {
    "parent": {
      "item": 123456
    },
    "sortOrder": 0
  }
}
```

## Key Points

✅ **Array Format Required**
- Jama expects `[422]` not `422`
- Multi-select/picklist-style field

✅ **Single Element Array**
- Contains exactly one integer
- Format: `[picklist_id]`

✅ **Export Compatible**
- Export script extracts first element
- Round-trip import/export works

✅ **All Tests Pass**
- Helper function works
- build_fields produces arrays
- All mappings correct

## Commands

```bash
# Compile check
test_venv/bin/python -m py_compile csv2jama.py

# Test array format
test_venv/bin/python test_array_format.py

# Dry-run
test_venv/bin/python csv2jama.py

# Execute
test_venv/bin/python csv2jama.py --execute
```

## Status

✅ **COMPLETE**

Verification method payload format corrected to use array of picklist IDs:
- ✓ Helper function added
- ✓ Payload generation updated
- ✓ Logging updated
- ✓ Error messages updated
- ✓ Documentation updated
- ✓ Tests passing
- ✓ Export compatible

Ready to use!
