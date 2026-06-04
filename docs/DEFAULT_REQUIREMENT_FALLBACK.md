# DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE Fallback

## Issue
Dry-run failures occurred when:
1. Row 30 (section 3.2) failed: "Cannot determine childItemType"
2. Row 30 never registered as section 3.2
3. Row 32 (section 3.2.1) failed: "Could not find parent section '3.2'"

This was a cascade failure - the first folder couldn't determine childItemType, so it failed before being registered, causing child sections to fail.

## Root Cause
When the ROOT_PARENT_ITEM_ID metadata is unavailable or does not expose childItemType:
- Parent inheritance fails (no metadata)
- Inference may fail (empty folders)
- No fallback available → folder creation fails
- Section not registered → child sections fail

## Solution
Added new `.env` fallback setting: `DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE`

This provides a general import-level fallback before the folder-specific fallback.

### New Priority Order

**Folder childItemType determination:**

A. **Inherit from parent_metadata["childItemType"]** (PREFERRED)
   - Automatic for folders under existing containers
   - Most common case

B. **Infer from next requirement row under folder**
   - Used when parent has no childItemType
   - Software Requirement → 112
   - Subsystem Requirement → 87
   - Stakeholder Requirement → 97
   - Text rows are skipped

C. **Use DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE** (NEW - general fallback)
   - Import-level fallback
   - Set once per import type
   - Examples:
     - Software Requirements import: `DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE=112`
     - Subsystem Requirements import: `DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE=87`
     - Stakeholder Requirements import: `DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE=97`

D. **Use JAMA_FOLDER_CHILD_ITEM_TYPE** (legacy folder-specific fallback)
   - Usually leave blank

E. **Fail with clear error**
   - Lists all 4 methods tried
   - Provides specific solutions

## Changes Made

### 1. Configuration Loading (line ~204)
Added loading of `DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE`:

```python
default_req_child_type = os.getenv("DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE", "")
if default_req_child_type:
    try:
        config["DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE"] = int(default_req_child_type)
        print(f"[INFO] Default requirement child item type: {config['DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE']}")
    except ValueError:
        print(f"[ERROR] DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE must be an integer")
        sys.exit(1)
else:
    config["DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE"] = None
```

### 2. Updated build_payload() for Set/Folder (line ~1498)
Changed priority order:
- Added Priority 3: `DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE`
- Moved folder-specific fallback to Priority 4

```python
# Priority 3: Use general DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE
elif CONFIG.get("DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE"):
    payload["childItemType"] = CONFIG["DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE"]
    child_type_source = "default_requirement"
# Priority 4: Use folder-specific JAMA_FOLDER_CHILD_ITEM_TYPE
elif item_type_name in CHILD_ITEM_TYPE_IDS:
    payload["childItemType"] = CHILD_ITEM_TYPE_IDS[item_type_name]
    child_type_source = "fallback_folder"
```

### 3. Updated build_payload() for Segment/Subsystem (line ~1554)
Same priority change - added DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE as Priority 3.

### 4. Updated Logging (line ~2160)
Added logs for the new fallback:

```python
elif child_type_source == "default_requirement":
    print(f"[INFO] Folder childItemType using DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE fallback: {child_type_value}")
elif child_type_source == "fallback_folder":
    print(f"[INFO] Folder childItemType using JAMA_FOLDER_CHILD_ITEM_TYPE fallback: {child_type_value}")
```

### 5. Updated Folder Resolution Logic (line ~2016)
Added DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE as Priority 3 when resolving existing folders.

### 6. Updated Error Messages
Changed error messages in:
- `build_payload()` - now lists 4 priorities
- `validate_container_child_item_type()` - now lists 4 priorities

Error now shows:
```
The script tried to:
  1. Inherit from parent container (no parent metadata or no childItemType)
  2. Infer from items under this folder (none found)
  3. Use DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE from .env (not configured)
  4. Use JAMA_FOLDER_CHILD_ITEM_TYPE from .env (not configured)
```

### 7. Updated .env.example
Added new section before Field Mappings:

```env
# ==============================================================================
# Child Item Type Fallbacks (Optional)
# ==============================================================================
# childItemType represents what content a container (Set/Folder) holds.
#
# IMPORTANT: The script normally determines childItemType automatically:
#   1. Inherits from parent container (most common)
#   2. Infers from requirement rows under the folder
#
# These settings are FALLBACK ONLY - used only if both methods above fail.
# Most imports don't need these settings.
#
# DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE:
#   General fallback for the current import's expected requirement type.
#   Set this once per import type (Software/Subsystem/Stakeholder).
#
#   Examples:
#     Software Requirement = 112
#     Subsystem Requirement = 87
#     Stakeholder Requirement = 97
#
DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE=

# JAMA_FOLDER_CHILD_ITEM_TYPE:
#   Legacy folder-specific fallback.
#   Usually leave blank unless needed for specific folder types.
#
JAMA_FOLDER_CHILD_ITEM_TYPE=
```

## Expected Behavior After Fix

### With DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE=112

**Row 30: Folder 3.2 CAPABILITY REQUIREMENTS**
```
Priority order:
A. Parent metadata: Not available
B. Infer from rows: None found
C. DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE: 112 ✓ USED
D. JAMA_FOLDER_CHILD_ITEM_TYPE: Not set

Result:
- Folder creates successfully with childItemType=112
- Section 3.2 registers: folder_by_section["3.2"] = <jama_id>
- Log: [INFO] Folder childItemType using DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE fallback: 112
```

**Row 32: Folder 3.2.1 Auto-Preflight**
```
Parent section lookup:
- Section number: 3.2.1
- Parent section: 3.2
- folder_by_section["3.2"]: FOUND ✓

Result:
- Folder creates successfully under section 3.2
- No cascade failure
```

## Text Row Handling
Text rows (itemType=33) are correctly skipped during inference:

| Scenario                              | childItemType | Method                           |
|---------------------------------------|---------------|----------------------------------|
| Parent SW Req (112)                   | 112           | Inherit from parent              |
| No parent, Text + SW Req rows         | 112           | Infer (Text skipped)             |
| No parent, only Text, DEFAULT=112     | 112           | DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE |
| No parent, only Text, no DEFAULT      | Error         | Fail                             |

## Usage

### Software Requirements Import
```env
DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE=112
```

### Subsystem Requirements Import
```env
DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE=87
```

### Stakeholder Requirements Import
```env
DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE=97
```

## Cascade Prevention
With the fallback in place:
1. Row 30 (section 3.2) creates successfully with childItemType=112
2. Section 3.2 registers in folder_by_section
3. Row 32 (section 3.2.1) finds parent section 3.2 ✓
4. No cascade failure

## Preserved Behavior
- Existing folders resolve by documentKey
- Missing folders can be created when CREATE_MISSING_FOLDERS=true
- Created/resolved folders become active parent
- Requirements post under current active folder
- Parent childItemType validation remains active
- Text rows have location.parent.item but no childItemType
- Text rows don't drive childItemType inference
- Section number normalization: "3.", "3", "3.0" all → "3.0"
- Dry-run remains default
- Simple commands:
  ```bash
  python csv2jama.py
  python csv2jama.py --execute
  ```

## Testing
```bash
# Syntax check
python3 -m py_compile csv2jama.py

# Add to .env
echo "DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE=112" >> .env

# Dry-run
python3 csv2jama.py

# Expected logs:
# [INFO] Default requirement child item type: 112
# [INFO] Folder childItemType using DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE fallback: 112
# [DRY RUN] Would POST: (folder payload with childItemType=112)
# ✓ Row 30 creates successfully
# ✓ Section 3.2 registers
# ✓ Row 32 finds parent section 3.2
```

## Files Changed
- `csv2jama.py` (7 sections):
  1. Configuration loading - added DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE
  2. build_payload() Set/Folder - added Priority 3
  3. build_payload() Segment/Subsystem - added Priority 3
  4. Logging - added new fallback logs
  5. Folder resolution - added Priority 3
  6. Error messages - updated to show 4 priorities
  7. Syntax: ✓ python3 -m py_compile passed

- `.env.example` - added Child Item Type Fallbacks section

## Summary
✓ **Cascade failure fixed** - folders can now create even without parent metadata  
✓ **Import-level fallback** - set once per import type  
✓ **Clear priority order** - Parent → Infer → General → Specific → Fail  
✓ **Better logging** - shows which method was used  
✓ **Text rows handled** - don't affect childItemType  
✓ **Section registration** - successful creation enables child sections  
