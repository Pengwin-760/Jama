# Fix: item_type_id Undefined Error

## Problem

**Error:**
```text
Row 8 | EGL_CV-SWREQ-001 | Software Requirement | VMC Power-On BIT (PBIT) Execution | name 'item_type_id' is not defined
```

**Root Cause:**
The variable `item_type_id` was referenced in verification method logic but was not defined in the scope where it was being used.

## Solution

### 1. Fixed in `build_fields()` Function

**Location:** Line 1556-1667

**Before:**
```python
def build_fields(row: pd.Series, item_type_id: int = None) -> Dict[str, Any]:
    item_type = row["Item Type"]
    # ... code ...
    # Later: item_type_id is used but might be None!
    verification_field_key = resolve_verification_method_field_key(
        item_type_name=item_type,
        item_type_id=item_type_id,  # ERROR: Could be None!
        ...
    )
```

**After:**
```python
def build_fields(row: pd.Series, item_type_id: int = None) -> Dict[str, Any]:
    item_type = row["Item Type"]

    # Derive item_type_id from row if not provided
    if item_type_id is None:
        if item_type not in ITEM_TYPE_IDS:
            raise ValueError(f"Unsupported Item Type for verification method lookup: {item_type}")
        item_type_id = ITEM_TYPE_IDS[item_type]

    # ... rest of code ...
    # Now item_type_id is guaranteed to be defined!
```

### 2. Fixed in Main Import Loop

**Location:** Line 2119-2138

**Before:**
```python
for row_pos, (row_index, row) in enumerate(df.iterrows()):
    excel_row_number = row_pos + 2
    item_type = row["Item Type"]
    name = row["Name"]
    # ... more code ...
    # item_type_id never defined in this scope!
```

**After:**
```python
for row_pos, (row_index, row) in enumerate(df.iterrows()):
    excel_row_number = row_pos + 2
    item_type = row["Item Type"]
    name = row["Name"]
    # ... other variables ...

    # Derive item_type_id from item_type for verification method and other uses
    if item_type not in ITEM_TYPE_IDS:
        raise ValueError(f"Unsupported Item Type: {item_type}")
    item_type_id = ITEM_TYPE_IDS[item_type]

    # ... rest of code ...
    # Now item_type_id is available throughout the loop!
```

## Changes Made

### File: `csv2jama.py`

**Change 1: build_fields() function (lines ~1556-1580)**
- Added defensive check at start of function
- Derives `item_type_id` from `row["Item Type"]` if not provided as parameter
- Raises clear error if item type is unsupported

**Change 2: Main import loop (lines ~2122-2129)**
- Added early derivation of `item_type_id` from `item_type`
- Variable now defined at start of loop iteration
- Available for all subsequent code in the loop

## Testing

### Compilation Check
```bash
python3 -m py_compile csv2jama.py
```
**Result:** ✅ PASSED (no syntax errors)

### Verification Mapping Test
```bash
python3 test_verification_simple.py
```
**Result:** ✅ PASSED (all mappings correct)

### item_type_id Fix Test
```bash
python3 test_item_type_id_simple.py
```
**Result:** ✅ PASSED
- ✓ item_type_id derived correctly from item_type
- ✓ No NameError
- ✓ Works for all requirement types (Software, Subsystem, Stakeholder)
- ✓ Fails gracefully for unsupported types

## Expected Behavior

### Before Fix
```text
[ERROR] Row 8 failed.
[ERROR] name 'item_type_id' is not defined
```

### After Fix
```text
[ROW 8] CREATE Software Requirement: VMC Power-On BIT (PBIT) Execution
[INFO] Verification Method: T -> Test -> 422
[INFO] Verification field key candidates found (itemType=112): verification_method$243
[INFO] Verification field key resolved dynamically: verification_method$243
[INFO] Verification payload: "verification_method$243": 422 (flat integer)
```

## Verification Method Behavior (Unchanged)

✓ Dynamic field-key detection still works  
✓ Uses `startswith("verification_method$")` to find fields  
✓ Does not assume suffix equals item type  
✓ Value remains flat integer (e.g., 422)  
✓ Mapping unchanged:
  - T / Test → 422
  - I / Inspection → 420
  - D / Demonstration → 419
  - A / Analysis → 418

✓ Only applies to requirement rows  
✓ Does not apply to Folder, Set, Segment, Subsystem, Text, Text Document

## Status

✅ **FIXED**

The error "name 'item_type_id' is not defined" has been resolved. Row 8 and all similar rows will now process correctly.

## Commands

```bash
# Compile check
python3 -m py_compile csv2jama.py

# Run tests
python3 test_verification_simple.py
python3 test_item_type_id_simple.py

# Dry-run
python3 csv2jama.py

# Execute
python3 csv2jama.py --execute
```
