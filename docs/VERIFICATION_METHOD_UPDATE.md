# Verification Method Import Logic Update

## Summary

Updated `csv2jama.py` to correct the Verification Method import logic. The verification method value is now sent as a **flat integer** (e.g., `422`), not wrapped in an object, array, or string.

## Changes Made

### 1. Import Mapping (Lines 15-42)

**Created separate import mapping:**
```python
VERIFICATION_METHOD_IMPORT_MAP = {
    "Test": 422,
    "Inspection": 420,
    "Demonstration": 419,
    "Analysis": 418,
}
```

**Updated aliases to support:**
- Letter aliases: `T`, `I`, `D`, `A`
- Case-insensitive full words: `test`, `TEST`, `Test`, `inspection`, `demonstration`, `analysis`

### 2. Value Format (Line 1568)

**Verification method values are sent as flat integers:**
```python
fields[verification_field_key] = 422  # Flat integer, not wrapped
```

**Example Jama-style field payload:**
```json
{
  "verification_method$243": 419,
  "notes$243": "Requirement"
}
```

### 3. Field Key Resolution (Lines 101-158)

**Dynamic field-key detection with priority:**

A. **Exact `.env` configuration:**
   ```env
   JAMA_FIELD_VERIFICATION_METHOD=verification_method$243
   ```

B. **Base name + item type:**
   ```env
   JAMA_FIELD_VERIFICATION_METHOD=verification_method
   ```
   Script appends `$<itemType>` automatically.

C. **Auto-detect from cached metadata:**
   - First tries: `verification_method$<current itemType>`
   - If not found, searches for any `verification_method$<number>`
   - If exactly one candidate exists, uses it
   - If multiple candidates exist, fails with clear error message

### 4. Configuration Summary (Lines 512-520)

**Added startup summary:**
```
Verification Method Field:            verification_method$112 / auto / disabled
Verification Method Value Shape:      flat integer (e.g., 422)
```

### 5. Dry-Run Logging (Lines 2330-2345)

**Enhanced logging for each row:**
```
[INFO] Verification Method: T -> Test -> 422
[INFO] Verification field key resolved: verification_method$112
[INFO] Verification payload value: 422 (flat integer)
```

### 6. Error Handling (Lines 751-819)

**Improved error message when Jama rejects the field:**
```
VERIFICATION METHOD ERROR GUIDANCE:
The verification method field 'verification_method$112' was rejected with value '422'.
The value is already a flat integer. This likely means the field key suffix is wrong
for this item type/project. Try configuring JAMA_FIELD_VERIFICATION_METHOD explicitly
using the field key seen in a known-good Jama item, such as verification_method$243.
```

### 7. Updated `.env.example` (Lines 90-107)

**Documented configuration options:**
```env
# Optional. Can be exact key or base name.
# Exact example: verification_method$243
# Base example: verification_method
# Leave blank to auto-detect from cached Jama fields when possible.
JAMA_FIELD_VERIFICATION_METHOD=
```

## Behavior

### Supported Input Values

| Excel Value | Normalized | Picklist ID |
|-------------|------------|-------------|
| T           | Test       | 422         |
| test        | Test       | 422         |
| TEST        | Test       | 422         |
| I           | Inspection | 420         |
| D           | Demonstration | 419      |
| A           | Analysis   | 418         |

### Field Key Examples

The script supports any verification field key suffix:
- `verification_method$86`
- `verification_method$112` (Software Requirement)
- `verification_method$243` (Other item type)
- `verification_method$<any number>`

### Verification Method Application

**Only applies to requirement rows:**
- Stakeholder Requirement
- Subsystem Requirement
- Software Requirement

**Does NOT apply to:**
- Folder
- Set
- Segment
- Subsystem
- Text
- Text Document

## Testing

Run the test to verify mapping correctness:

```bash
python3 test_verification_simple.py
```

Expected output:
```
✓ T -> Test -> 422
✓ I -> Inspection -> 420
✓ D -> Demonstration -> 419
✓ A -> Analysis -> 418
```

## Compilation Check

```bash
python3 -m py_compile csv2jama.py
```

(No output = success)

## Dry-Run Test

```bash
python3 csv2jama.py
```

Look for:
```
Verification Method Field:            verification_method$112 / auto / disabled
Verification Method Value Shape:      flat integer (e.g., 422)
```

And per-row output:
```
[INFO] Verification Method: T -> Test -> 422
[INFO] Verification field key resolved: verification_method$112
[INFO] Verification payload value: 422 (flat integer)
```

## Important Notes

1. **Flat Integer Format:**
   - Do NOT use: `{"id": 422}`, `[422]`, `"422"`, or `[{"id": 422}]`
   - Always use: `422` (flat integer)

2. **Field Key Suffix:**
   - The suffix does not always equal the item type ID
   - If ambiguous, configure `JAMA_FIELD_VERIFICATION_METHOD` explicitly in `.env`

3. **Existing Behavior Preserved:**
   - Folder resolution by documentKey
   - Parent childItemType validation
   - Dry-run default mode
   - All existing commands work unchanged

## Commands

```bash
# Dry-run (default, safe preview)
python3 csv2jama.py

# Execute (makes actual API calls)
python3 csv2jama.py --execute
```
