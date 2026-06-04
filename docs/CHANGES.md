# csv2jama.py - Move Support Update

## Summary

Updated csv2jama.py to support safe item moving and better parent validation. The script can now:
1. Detect when items are under the wrong parent
2. Move items to the correct parent (when enabled)
3. Validate parent compatibility before creating or moving items
4. Support both PATCH and PUT methods for item updates

## Key Changes

### 1. Re-enabled PUT/PATCH Support

**Before**: `jama_put()` raised `NotImplementedError`

**After**: 
- `jama_put()` - Full item update (requires all fields)
- `jama_patch()` - Partial update (location-only for moves)

### 2. New Configuration Options

Added to `.env`:
```env
ALLOW_MOVE_EXISTING_ITEMS=false  # Enable item moves (default: false)
MOVE_METHOD=PATCH                # Use PATCH or PUT (default: PATCH)
```

### 3. New CLI Option

```bash
python csv2jama.py --mode upsert --dry-run --allow-move
python csv2jama.py --mode upsert --execute --allow-move
```

The `--allow-move` flag overrides `.env` setting.

### 4. Enhanced Item Caching

New global caches:
- `_items_by_document_key` - Find any item by documentKey (not just folders)
- `_items_by_source_id` - Find items by Excel source ID
- All items from project are now cached with location information

### 5. Parent Validation

**For CREATE operations**:
- Validates parent childItemType matches item itemType before POST
- Prevents creating requirements under incompatible parents
- Fails with clear error message if mismatch detected

**For MOVE operations**:
- Validates target parent childItemType before move
- Prevents moving items to incompatible parents
- Compares current parent vs desired parent

### 6. New Actions

- **MOVE** - Move existing item to correct parent (when --allow-move enabled)
- **SKIP_NEEDS_MOVE** - Item needs move but moves disabled (warning only)

### 7. Enhanced Results CSV

New columns in `import_results.csv`:
- `current_parent_item_id` - Where item currently is
- `desired_parent_item_id` - Where item should be
- `moved` - true/false
- `move_method` - PATCH or PUT

### 8. Dry-Run Output

For misplaced existing items:

```text
[DRY RUN] Existing item PROJ-SS-066 / Jama ID 999999 is under parent <current_parent>.
[DRY RUN] Desired parent is <desired_parent>.
[DRY RUN] Would MOVE item 999999 to parent <desired_parent> using PATCH
[DRY RUN] Move payload:
{
  "location": {
    "parent": {
      "item": <desired_parent>
    },
    "sortOrder": 0
  }
}
```

Without --allow-move:

```text
[WARN] Item is under parent <current_parent>, but should be under <desired_parent>
[WARN] Enable --allow-move to move this item to the correct parent
```

### 9. Execute Output

```text
[MOVE] Moving item PROJ-SS-066 / Jama ID 999999 from parent <current_parent> to <desired_parent>
[OK] Moved item 999999 from parent <current_parent> to <desired_parent> using PATCH
```

### 10. Configuration Summary

Now shows move settings:

```text
Allow Move Existing Items:            true
Move Method:                          PATCH
[WARN] Existing item moves are enabled. Dry-run strongly recommended before execute.
```

### 11. Import Summary

Enhanced statistics:

```text
IMPORT SUMMARY
Mode: upsert
Execution: DRY RUN
Created rows: 5
Resolved parent rows: 10
Skipped rows: 2
Moved rows: 7
Rows needing move: 3 (enable --allow-move to move these)
Failed rows: 0
Total successful: 22
```

## Safety Features

1. **Dry-run by default** - Must explicitly use --execute
2. **Moves disabled by default** - Must enable with --allow-move
3. **Parent validation** - Checks childItemType compatibility before create/move
4. **Warning on enable** - Shows warning when moves are enabled
5. **Full diagnostics** - Shows current/desired parent for all items

## Backward Compatibility

All existing behavior preserved:
- Dry-run remains default
- Upsert remains default
- POST-only mode still works
- Folder resolution by documentKey unchanged
- Parent hierarchy resolution unchanged
- Description validation unchanged
- childItemType inference unchanged

## Usage Examples

### Check for misplaced items (dry-run):
```bash
python csv2jama.py --mode upsert --dry-run --allow-move
```

### Move misplaced items (execute):
```bash
python csv2jama.py --mode upsert --execute --allow-move
```

### Create new items only (no moves):
```bash
python csv2jama.py --mode create --execute
```

### Standard import (no moves):
```bash
python csv2jama.py --mode upsert --execute
```

## Testing Recommendation

Always run dry-run first:
```bash
# 1. Check what would happen
python csv2jama.py --mode upsert --dry-run --allow-move

# 2. Review import_results.csv for MOVE/SKIP_NEEDS_MOVE rows

# 3. Execute only if dry-run looks correct
python csv2jama.py --mode upsert --execute --allow-move
```

## Implementation Details

### Move Method Choice

**PATCH (default)**:
- Only sends location change
- Safer - doesn't risk overwriting fields
- Requires API support for PATCH

**PUT (fallback)**:
- Sends full item data with location change
- Requires existing item metadata
- May overwrite if fields changed externally

### Parent Detection

1. Tries to find existing item by Jama ID (from Excel)
2. Falls back to documentKey lookup in cache
3. Extracts current parent from `item.location.parent.item`
4. Compares with desired parent from hierarchy logic
5. Flags mismatch if different

### Validation Order

1. Determine desired parent (from section hierarchy or current_folder)
2. Get parent metadata from cache
3. Check parent childItemType
4. For CREATE: validate itemType matches childItemType before POST
5. For MOVE: validate itemType matches target childItemType before PATCH/PUT

## Files Modified

- `csv2jama.py` - Main script (all changes)

## Files Created

- `CHANGES.md` - This document
