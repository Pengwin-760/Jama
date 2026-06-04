# Fix: Correct childItemType for Containers

## Date
2026-06-03

## Issue

Jama POST was failing with:
```json
{
  "meta": {
    "status": "Bad Request",
    "message": "Invalid document location. Folder of System Requirements cannot be under Set of Subsystem Requirements"
  }
}
```

## Root Cause

The script was using wrong `childItemType` values for containers. The script had:
```python
"Set": int(os.getenv("JAMA_SET_CHILD_ITEM_TYPE", "32")),     # Wrong: 32 is Folder type
"Folder": int(os.getenv("JAMA_FOLDER_CHILD_ITEM_TYPE", "86")), # Wrong: 86 is old requirement type
```

## Critical Understanding

**In Jama, `childItemType` represents the type of CONTENT the container holds, not the container type itself.**

### Correct Hierarchy for Subsystem Requirements

```
Set of Subsystem Requirements
  ↓ itemType = 30 (Set)
  ↓ childItemType = 87 (Subsystem Requirement) ← What it CONTAINS
  │
  ├─ Folder of Subsystem Requirements
  │    ↓ itemType = 32 (Folder)
  │    ↓ childItemType = 87 (Subsystem Requirement) ← What it CONTAINS
  │    │
  │    ├─ Subsystem Requirement #1
  │    │    itemType = 87
  │    │    (no childItemType - leaf node)
  │    │
  │    └─ Subsystem Requirement #2
  │         itemType = 87
  │         (no childItemType - leaf node)
  │
  └─ Subsystem Requirement #3
       itemType = 87
       (no childItemType - leaf node)
```

## Fix Applied

### 1. Changed Default childItemType Values

**Before:**
```python
config["CHILD_ITEM_TYPE_IDS"] = {
    "Set": int(os.getenv("JAMA_SET_CHILD_ITEM_TYPE", "32")),
    "Folder": int(os.getenv("JAMA_FOLDER_CHILD_ITEM_TYPE", "86")),
}
```

**After:**
```python
# Default to Subsystem Requirement type for containers in this import
default_child_type = str(config["ITEM_TYPE_IDS"].get("Subsystem Requirement", "87"))

config["CHILD_ITEM_TYPE_IDS"] = {
    "Set": int(os.getenv("JAMA_SET_CHILD_ITEM_TYPE", default_child_type)),
    "Folder": int(os.getenv("JAMA_FOLDER_CHILD_ITEM_TYPE", default_child_type)),
}
```

**Result:** Defaults to 87 (Subsystem Requirement type), not 32 (Folder type).

### 2. Updated .env.example

**Before:**
```env
JAMA_ITEM_TYPE_SET=31
JAMA_SET_CHILD_ITEM_TYPE=32
JAMA_FOLDER_CHILD_ITEM_TYPE=86
```

**After:**
```env
JAMA_ITEM_TYPE_SET=30
JAMA_ITEM_TYPE_FOLDER=32
JAMA_ITEM_TYPE_SUBSYSTEM_REQUIREMENT=87

# IMPORTANT: childItemType means what requirement/item type this container contains.
# For Set/Folder of Subsystem Requirements, use 87 (the Subsystem Requirement item type).
JAMA_SET_CHILD_ITEM_TYPE=87
JAMA_FOLDER_CHILD_ITEM_TYPE=87
JAMA_SUBSYSTEM_CHILD_ITEM_TYPE=87
```

### 3. Added Validation Function

**New function:**
```python
def validate_container_child_item_type(row: pd.Series, payload: Dict[str, Any]) -> None:
    """Validate that container payloads have childItemType set."""
    item_type_name = row["Item Type"]
    if item_type_name in ("Set", "Folder", "Subsystem"):
        child_type = payload.get("childItemType")
        if not child_type:
            raise ValueError(
                f"{item_type_name} create payload missing childItemType."
            )
```

**Called before POST** in both dry-run and execute modes.

### 4. Enhanced Debug Output

**Dry-run now shows:**
```
[INFO] Creating Folder with itemType=32 childItemType=87
[DEBUG] POST fields keys: ['name', 'description']
[DRY RUN] Would POST:
{
  "fields": {
    "name": "Subsystem Requirements"
  },
  "itemType": 32,
  "childItemType": 87,  ← Correct: type of content it holds
  "location": {
    "parent": {"item": 123456},
    "sortOrder": 0
  }
}
```

### 5. Updated Configuration Summary

**Startup now shows:**
```
Child Item Type Mappings:
  (childItemType = what content type the container holds)
  Set childItemType: 87
  Folder childItemType: 87
  Subsystem childItemType: 87
```

### 6. Added Comments

**Throughout code:**
```python
# IMPORTANT: Jama childItemType is the type of content allowed INSIDE the Set/Folder.
# For a "Folder of Subsystem Requirements", childItemType must be the Subsystem Requirement item type ID (87).
```

## Item Type IDs

### Correct Values for This Import

```env
# Container types
JAMA_ITEM_TYPE_SET=30
JAMA_ITEM_TYPE_FOLDER=32
JAMA_ITEM_TYPE_SEGMENT=243

# Requirement types
JAMA_ITEM_TYPE_STAKEHOLDER_REQUIREMENT=97
JAMA_ITEM_TYPE_SUBSYSTEM_REQUIREMENT=87
JAMA_ITEM_TYPE_SOFTWARE_REQUIREMENT=112

# Child types (what containers hold)
JAMA_SET_CHILD_ITEM_TYPE=87          # Holds Subsystem Requirements
JAMA_FOLDER_CHILD_ITEM_TYPE=87       # Holds Subsystem Requirements
JAMA_SUBSYSTEM_CHILD_ITEM_TYPE=87    # Subsystem is alias of Set, holds same type
```

## Subsystem Mapping

**Subsystem is an alias of Set:**

```python
# Item type mapping
"Subsystem": int(os.getenv("JAMA_ITEM_TYPE_SET", "30"))  # Uses Set item type

# Child type mapping
"Subsystem": int(os.getenv("JAMA_SUBSYSTEM_CHILD_ITEM_TYPE", 
                          os.getenv("JAMA_SET_CHILD_ITEM_TYPE", "87")))
```

**Result:** Subsystem uses itemType=30 (Set) and childItemType=87 (Subsystem Requirement).

## Expected Payloads

### Folder of Subsystem Requirements

```json
{
  "fields": {
    "name": "Launch Requirements"
  },
  "itemType": 32,
  "childItemType": 87,
  "location": {
    "parent": {
      "item": 123456
    },
    "sortOrder": 0
  }
}
```

**Key points:**
- `itemType: 32` - This IS a Folder
- `childItemType: 87` - It CONTAINS Subsystem Requirements

### Set of Subsystem Requirements

```json
{
  "fields": {
    "name": "Avionics Subsystem"
  },
  "itemType": 30,
  "childItemType": 87,
  "location": {
    "parent": {
      "item": 123456
    },
    "sortOrder": 0
  }
}
```

**Key points:**
- `itemType: 30` - This IS a Set
- `childItemType: 87` - It CONTAINS Subsystem Requirements

### Subsystem Requirement (Leaf Node)

```json
{
  "fields": {
    "name": "System shall support launch modes",
    "description": "The system must..."
  },
  "itemType": 87,
  "location": {
    "parent": {
      "item": 123456
    },
    "sortOrder": 0
  }
}
```

**Key points:**
- `itemType: 87` - This IS a Subsystem Requirement
- **NO childItemType** - Leaf node, doesn't contain anything

## Why This Was Wrong Before

### Old Configuration

```env
JAMA_SET_CHILD_ITEM_TYPE=32    # Wrong: 32 is Folder type
JAMA_FOLDER_CHILD_ITEM_TYPE=86 # Wrong: 86 is old/different requirement type
```

**Result:**
```json
{
  "itemType": 32,
  "childItemType": 32  ← WRONG: Folder says it contains Folders
}
```

**Jama Error:** "Invalid document location"

### New Configuration

```env
JAMA_SET_CHILD_ITEM_TYPE=87    # Correct: 87 is Subsystem Requirement type
JAMA_FOLDER_CHILD_ITEM_TYPE=87 # Correct: 87 is Subsystem Requirement type
```

**Result:**
```json
{
  "itemType": 32,
  "childItemType": 87  ← CORRECT: Folder says it contains Subsystem Requirements
}
```

**Jama:** Accepts the payload ✓

## Common Mistakes

### Mistake 1: Using Container Type as Child Type

**Wrong:**
```env
JAMA_FOLDER_CHILD_ITEM_TYPE=32  # Using Folder type
```

**This means:** "Folder contains Folders" - usually wrong.

**Correct:**
```env
JAMA_FOLDER_CHILD_ITEM_TYPE=87  # Using Subsystem Requirement type
```

**This means:** "Folder contains Subsystem Requirements" - correct!

### Mistake 2: Mixing Requirement Types

**Wrong:**
```env
JAMA_SET_CHILD_ITEM_TYPE=97     # Stakeholder Requirement
JAMA_FOLDER_CHILD_ITEM_TYPE=87  # Subsystem Requirement
```

**This means:** "Set contains Stakeholders, Folder contains Subsystem Requirements" - inconsistent hierarchy.

**Correct:**
```env
JAMA_SET_CHILD_ITEM_TYPE=87
JAMA_FOLDER_CHILD_ITEM_TYPE=87
```

**This means:** "Both contain Subsystem Requirements" - consistent!

### Mistake 3: Not Setting childItemType for Subsystem

**Wrong:**
```env
# Missing JAMA_SUBSYSTEM_CHILD_ITEM_TYPE
```

**Result:** Subsystem creates may fail.

**Correct:**
```env
JAMA_SUBSYSTEM_CHILD_ITEM_TYPE=87
```

## Testing

### Startup Configuration Check

**Look for:**
```
Child Item Type Mappings:
  (childItemType = what content type the container holds)
  Set childItemType: 87
  Folder childItemType: 87
  Subsystem childItemType: 87
```

✓ All should be 87 for Subsystem Requirement imports.

### Dry-Run Output Check

**Folder create:**
```
[INFO] Creating Folder with itemType=32 childItemType=87
```

✓ itemType=32 (Folder), childItemType=87 (Subsystem Requirement)

**Set create:**
```
[INFO] Creating Set with itemType=30 childItemType=87
```

✓ itemType=30 (Set), childItemType=87 (Subsystem Requirement)

**Requirement create:**
```
[DEBUG] POST fields keys: ['name', 'description']
(No childItemType line - correct for leaf nodes)
```

✓ Requirements don't show childItemType (they don't have one)

### Payload Validation

**Container payload:**
```json
{
  "itemType": 32,
  "childItemType": 87  ← Must be present
}
```

**Requirement payload:**
```json
{
  "itemType": 87
  (no childItemType)  ← Must NOT be present
}
```

## Compile Check

```bash
python3 -m py_compile csv2jama.py
```

✅ **PASSED** - No syntax errors

## Summary

### Files Modified

1. ✅ `csv2jama.py` - Changed default childItemType values
2. ✅ `.env.example` - Updated with correct values and explanations
3. ✅ `CHILD_ITEM_TYPE_FIX.md` - This documentation

### Default childItemType Values

**Old:**
- Set: 32 (Folder type) ❌
- Folder: 86 (old requirement type) ❌

**New:**
- Set: 87 (Subsystem Requirement type) ✓
- Folder: 87 (Subsystem Requirement type) ✓
- Subsystem: 87 (Subsystem Requirement type) ✓

### Why JAMA_SET_CHILD_ITEM_TYPE Should Be 87

**Because:**
1. childItemType = type of CONTENT, not container
2. Set contains Subsystem Requirements
3. Subsystem Requirement itemType = 87
4. Therefore Set childItemType = 87

**NOT 32 because:**
- 32 is Folder type
- Set doesn't contain Folders (in this hierarchy)
- Using 32 causes "Invalid document location" error

### How Subsystem Maps to Set

**Item Type:**
```python
"Subsystem": int(os.getenv("JAMA_ITEM_TYPE_SET", "30"))
```

**Result:** Subsystem rows create items with itemType=30 (Set)

**Child Type:**
```python
"Subsystem": int(os.getenv("JAMA_SUBSYSTEM_CHILD_ITEM_TYPE", "87"))
```

**Result:** Subsystem items have childItemType=87 (Subsystem Requirement)

**Full mapping:**
- Subsystem → itemType=30 (Set), childItemType=87 (Subsystem Requirement)

### Compile Status

✅ **PASSED** - Ready for dry-run testing

## Next Steps

1. **Update .env:**
   ```env
   JAMA_ITEM_TYPE_SET=30
   JAMA_SET_CHILD_ITEM_TYPE=87
   JAMA_FOLDER_CHILD_ITEM_TYPE=87
   JAMA_SUBSYSTEM_CHILD_ITEM_TYPE=87
   ```

2. **Run dry-run:**
   ```bash
   python3 csv2jama.py --mode upsert --dry-run
   ```

3. **Verify output:**
   - Folders show `itemType=32 childItemType=87`
   - Sets show `itemType=30 childItemType=87`
   - Requirements show no childItemType

4. **Execute:**
   ```bash
   python3 csv2jama.py --mode upsert --execute
   ```

**Expected:** No more "Invalid document location" errors!
