# Understanding childItemType

## What is childItemType?

In Jama, containers (Sets, Folders) have a `childItemType` property that specifies **what type of content** they can hold.

**Example:**
- A "Folder of Subsystem Requirements" has `childItemType=87` (Subsystem Requirement item type ID)
- This means only Subsystem Requirements (itemType=87) can be placed inside it

## How the Script Determines childItemType

The script uses **3 methods in priority order**:

### 1. Lookahead Inference (Automatic)
**Most common and recommended**

The script looks ahead at items that will go under the folder:
```
Row 96: Folder | UAI Interface Requirements
Row 97: Subsystem Requirement | MIL-STD-1760
Row 98: Subsystem Requirement | MIL-STD-1553
```

Script infers: "Rows 97-98 are Subsystem Requirements, so Folder needs childItemType=87"

### 2. Parent Inheritance (Automatic)
**For nested folders**

The script inherits from the parent container:
```
Parent Folder has childItemType=87
  └─ Child Folder (inherits childItemType=87)
      └─ Requirements go here
```

### 3. Config Fallback (Manual)
**Only needed for edge cases**

If lookahead and inheritance both fail, uses .env fallback:
```env
JAMA_FOLDER_CHILD_ITEM_TYPE=87
```

## When Fallback is Needed

**Rare edge cases:**
1. **Empty root folder** - No items under it, no parent to inherit from
2. **Placeholder folder** - Created before requirements are imported
3. **Special project structure** - Root-level folders with no parent

## Recommended Configuration

### For Most Users (Recommended)
**Leave child item types unset** in .env - the script will figure it out:

```env
# These are optional - script auto-determines childItemType
# JAMA_SET_CHILD_ITEM_TYPE=87
# JAMA_FOLDER_CHILD_ITEM_TYPE=87
```

### For Edge Cases Only
If you get errors about missing childItemType, set to match YOUR requirement type:

**⚠️ IMPORTANT: Set to match what you're actually importing!**

```env
# For Stakeholder Requirements:
JAMA_FOLDER_CHILD_ITEM_TYPE=97

# For Subsystem Requirements:
JAMA_FOLDER_CHILD_ITEM_TYPE=87

# For Software Requirements:
JAMA_FOLDER_CHILD_ITEM_TYPE=112
```

**Don't blindly copy 87** - that only works if importing Subsystem Requirements!

## Error Messages

### Cannot determine childItemType
```
Cannot determine childItemType for Folder 'System Requirements'.

The script tried to:
  1. Infer from items under this folder (none found)
  2. Inherit from parent container (no parent metadata)
  3. Use fallback from .env (not configured)

This usually means the folder is empty or at root level.

Solution 1 (Recommended): Add requirement items under this folder in Excel

Solution 2: Set fallback in .env based on what requirements you're importing:
  - Stakeholder Requirement: 97
  - Subsystem Requirement: 87
  - Software Requirement: 112

Add to .env:
  JAMA_FOLDER_CHILD_ITEM_TYPE=<type_id>
```

**How to fix:**
1. **Option A (Recommended)**: Add requirement rows under the folder in Excel
2. **Option B**: Set fallback in .env to match YOUR requirement type (don't blindly use 87!)

## Validation

The script validates childItemType compatibility:

### Before CREATE
```
Creating: Subsystem Requirement (itemType=87)
Under:    Folder (childItemType=87)
Result:   ✓ MATCH - Item can be created
```

### Mismatch Example
```
Creating: Subsystem Requirement (itemType=87)
Under:    References Folder (childItemType=243)
Result:   ✗ MISMATCH - Wrong parent!
Error:    Cannot create Subsystem Requirement under this folder
```

## Best Practices

1. **Let the script infer** - Don't set child item types in .env unless needed
2. **Group requirements** - Put similar requirement types under same folder
3. **Check Excel structure** - Ensure folders have items under them
4. **Use dry-run** - Validates childItemType before executing

## Examples

### Example 1: Normal Case (No Config Needed)
```
Excel:
  Row 10: Folder | Requirements
  Row 11: Subsystem Requirement | Req 1
  Row 12: Subsystem Requirement | Req 2

Script automatically infers childItemType=87 for Folder
```

### Example 2: Nested Folders (No Config Needed)
```
Excel:
  Row 10: Folder | System (inferred childItemType=87)
  Row 11:   Folder | Interface (inherits childItemType=87)
  Row 12:     Subsystem Requirement | Req 1
  Row 13:     Subsystem Requirement | Req 2

Parent inheritance handles nested structure
```

### Example 3: Empty Root Folder (Config Needed)
```
Excel:
  Row 1: Folder | To Be Populated Later

No items under it, no parent to inherit from
→ Set JAMA_FOLDER_CHILD_ITEM_TYPE=87 in .env
```

## Summary

| Method | When Used | Config Required? |
|--------|-----------|------------------|
| Lookahead Inference | Items under folder | ❌ No |
| Parent Inheritance | Nested folders | ❌ No |
| Config Fallback | Empty root folders | ✅ Only if needed |

**Default recommendation**: Leave child item type settings commented out in .env. The script will auto-determine them from your Excel structure.
