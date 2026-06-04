# csv2jama.py - Usage Guide

## Simple Workflow (Recommended)

### 1. Preview Changes (Dry-Run)
```bash
python csv2jama.py
```
**What it does:**
- Loads requirements from Excel file
- Validates parent relationships
- Shows what would be created/resolved
- **Makes NO changes to Jama**
- Generates `import_results.csv` preview

### 2. Execute Import
```bash
python csv2jama.py --execute
```
**What it does:**
- Creates new items in Jama via POST
- Resolves existing folders by documentKey
- Validates parent childItemType compatibility
- Skips existing requirements (no updates)
- **Does NOT move existing items**
- Generates `import_results.csv` with results

## What the Default Command Does

Running `python csv2jama.py` with no flags:
- Uses settings from `.env` file
- Defaults to `IMPORT_MODE=upsert` (create new + resolve existing)
- Defaults to `DRY_RUN=true` (safe preview)
- Resolves folders by documentKey
- Validates all parent relationships
- Shows detailed output of what would happen
- Creates `import_results.csv` for review

## Configuration

All settings are in `.env` file:
```env
IMPORT_MODE=upsert              # create, upsert
DRY_RUN=true                    # true = preview, false = execute
ALLOW_MOVE_EXISTING_ITEMS=false # Keep false for normal imports
MOVE_METHOD=PATCH               # PATCH or PUT
```

Copy `.env.example` to `.env` and configure your Jama instance settings.

## Advanced Options

### Check for Misplaced Items
```bash
python csv2jama.py --allow-move
```
**When to use:** Recovery/fix operations when items are under wrong parent

**What it does:**
- Shows which items need to be moved
- Validates target parent compatibility
- **Makes NO changes (still dry-run)**
- Use this to preview moves first

### Move Items to Correct Parent
```bash
python csv2jama.py --execute --allow-move
```
**⚠️ USE WITH CAUTION**

**When to use:**
- Only after reviewing dry-run with `--allow-move`
- When items are confirmed to be under wrong parent
- For recovery/fix operations, not routine imports

**What it does:**
- Moves existing items to correct parent
- Validates childItemType compatibility before move
- Uses PATCH by default (location-only update)
- Shows warning about relocating items

### Create-Only Mode
```bash
python csv2jama.py --mode create --execute
```
**When to use:** Initial import where everything is new

**What it does:**
- Only creates new items (all rows must have blank Jama ID)
- Fails if any row has Jama ID populated

## Import Process

### For New Rows (no Jama ID)
1. **Folders**: Checks if documentKey exists in Jama
   - If found and childItemType compatible: Resolve and use as parent
   - If found but childItemType mismatch: Create new folder
   - If not found: Create new folder (if CREATE_MISSING_FOLDERS=true)

2. **Requirements**: Create new item
   - Validates parent childItemType matches requirement itemType
   - Places under current active folder
   - Fails if parent incompatible

### For Existing Rows (has Jama ID)
1. **Folders**: Resolve and register as parent container
   - No update/move performed
   - Used for hierarchy reference

2. **Requirements**: Skip (default)
   - With `--allow-move`: Check parent and move if wrong

## Output Files

### import_results.csv
Contains all import operations:
- `action`: CREATE, RESOLVE, SKIP, MOVE, SKIP_NEEDS_MOVE
- `status`: Success/failure status
- `current_parent_item_id`: Where item currently is
- `desired_parent_item_id`: Where item should be
- `moved`: true/false
- `error`: Error details if failed

## Safety Features

1. **Dry-run by default** - Always preview first
2. **Moves disabled by default** - Prevents accidental relocations
3. **Parent validation** - Checks childItemType before create/move
4. **Strong warnings** - Alerts when move mode enabled
5. **Full diagnostics** - Shows all parent relationships

## Troubleshooting

### "Cannot create X under parent Y"
**Cause:** Parent childItemType doesn't match item itemType

**Fix:** Check Excel file - item routed to wrong folder

### "Folder documentKey not found"
**Cause:** Folder doesn't exist in Jama

**Fix:** 
- Set `CREATE_MISSING_FOLDERS=true` to create it
- Or add Jama ID to Excel for existing folder

### "Row X needs move but moves disabled"
**Status:** Item exists but under wrong parent

**Fix:**
1. Run `python csv2jama.py --allow-move` to preview
2. Review `import_results.csv` for SKIP_NEEDS_MOVE rows
3. Run `python csv2jama.py --execute --allow-move` to fix

## Best Practices

1. **Always dry-run first**
   ```bash
   python csv2jama.py
   ```

2. **Review import_results.csv** before executing

3. **Keep moves disabled** for routine imports

4. **Only enable moves** for recovery operations:
   ```bash
   python csv2jama.py --allow-move          # Preview
   python csv2jama.py --execute --allow-move # Execute
   ```

5. **Use version control** for Excel file and .env

6. **Test with small batch** before large imports

## Example Session

```bash
# 1. Configure
cp .env.example .env
vim .env  # Edit settings

# 2. Preview
python csv2jama.py

# 3. Review results
cat import_results.csv

# 4. Execute if preview looks good
python csv2jama.py --execute

# 5. Check results
cat import_results.csv
```

## Getting Help

```bash
python csv2jama.py --help
```

Shows all available options and examples.
