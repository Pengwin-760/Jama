# Section Number Parsing Fix

## Issue
The script failed when Excel used "3. REQUIREMENTS" as a top-level section name because:
- `extract_section_number("3. REQUIREMENTS")` returned `"3"` (without the dot)
- This was registered as-is without normalization
- Child section "3.1" looked for parent "3.0"
- Parent was registered as "3" but child looked for "3.0" → **MISMATCH**

**Error message:**
```
Could not find parent section '3.0' for folder '3.1' / '3.1 REQUIRED STATES AND MODES'. 
Make sure the parent container appears earlier in the Excel file.
```

## Root Cause
The section number extraction and normalization did not handle the trailing dot format ("3.") used by some Excel files.

## Solution
Updated three functions in `csv2jama.py`:

### 1. `extract_section_number()` (line 1221)
**Changed:** Added support for trailing dots in section numbers.

**Before:**
- Regex: `(\d+(?:\.\d+)*)`
- Result: "3. REQUIREMENTS" → "3" (no dot)

**After:**
- Regex: `(\d+(?:\.\d+)*\.?)`
- Result: "3. REQUIREMENTS" → "3." (with dot)

### 2. `normalize_top_level_section()` (line 1264)
**Changed:** Now strips trailing dots before normalizing.

**Before:**
```python
parts = section_number.split(".")
if len(parts) == 1:
    return f"{section_number}.0"
```

**After:**
```python
section_number = section_number.rstrip(".")
parts = section_number.split(".")
if len(parts) == 1:
    return f"{section_number}.0"
```

**Behavior:**
- "3" → "3.0" ✓
- "3." → "3.0" ✓ (NEW)
- "3.0" → "3.0" ✓
- "3.1" → "3.1" ✓ (unchanged)

### 3. Added Debug Logging (line 1988)
When a section is detected, the script now prints:
```
[INFO] Detected section: raw='3.' normalized='3.0'
```

## Supported Formats
All these forms now register as section "3.0":

| Excel Name              | Raw Extracted | Normalized | Parent |
|-------------------------|---------------|------------|--------|
| `3 REQUIREMENTS`        | `3`           | `3.0`      | None   |
| `3. REQUIREMENTS`       | `3.`          | `3.0`      | None   |
| `3.0 REQUIREMENTS`      | `3.0`         | `3.0`      | None   |
| `(U) 3. REQUIREMENTS`   | `3.`          | `3.0`      | None   |

Child sections work correctly:

| Excel Name                     | Raw Extracted | Normalized | Parent |
|--------------------------------|---------------|------------|--------|
| `3.1 REQUIRED STATES`          | `3.1`         | `3.1`      | `3.0`  |
| `3.1.1 Something`              | `3.1.1`       | `3.1.1`    | `3.1`  |

## False Positive Protection
Still correctly rejects non-section numbers:

| Excel Name                  | Result |
|-----------------------------|--------|
| `MIL-STD-1553 Compliance`   | None   |
| `UAI / 1553 Interface`      | None   |

## Testing
Two test scripts verify the fix:

1. **test_section_parsing.py** - Unit tests for all three functions
   ```bash
   python3 test_section_parsing.py
   ```
   Result: ✓ ALL TESTS PASSED

2. **test_section_integration.py** - Integration test simulating the user's issue
   ```bash
   python3 test_section_integration.py
   ```
   Result: ✓ SUCCESS: Child correctly finds parent

## Preserved Behavior
- Folder resolution by documentKey (priority: Jama ID → Document Key column → Excel ID)
- Missing folder creation (CREATE_MISSING_FOLDERS=true)
- Parent childItemType validation
- Text rows still have location.parent.item but don't drive childItemType inference
- Dry-run mode remains default
- Simple commands:
  - `python csv2jama.py` (dry-run)
  - `python csv2jama.py --execute` (execute)

## Files Changed
- `csv2jama.py` - Updated 3 functions, added 1 debug print
- `test_section_parsing.py` - NEW test file
- `test_section_integration.py` - NEW integration test
- `SECTION_PARSING_FIX.md` - This documentation
