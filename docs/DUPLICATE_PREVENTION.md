# Duplicate Prevention - Will the Script Create Duplicates?

## Short Answer

**No, the script will NOT create duplicates if run again** - with the default settings and proper workflow.

## How Duplicate Prevention Works

### 1. Import Mode: "upsert" (Default)

The script defaults to `IMPORT_MODE=upsert`, which means:

**For Requirements:**
- If row has a Jama ID → **SKIP** (no duplicate created)
- If row has no Jama ID → **CREATE** new item

**For Folders:**
- If row has a Jama ID → **RESOLVE** (reuse existing)
- If row has no Jama ID → Try to find by `documentKey`
  - Found → **RESOLVE** (reuse existing)
  - Not found → **CREATE** new folder (only if `CREATE_MISSING_FOLDERS=true`)

### 2. Folder Resolution by documentKey

**Default Settings (.env):**
```env
RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=true
USE_EXCEL_ID_AS_DOCUMENT_KEY=true
CREATE_MISSING_FOLDERS=true
```

**How It Works:**

When processing a Folder row:

```
Priority:
A. Jama ID in Excel → Use that Jama ID (RESOLVE)
B. Document Key column → Search Jama for that documentKey (RESOLVE if found)
C. Excel ID as documentKey → Search Jama for that documentKey (RESOLVE if found)
D. Not found → CREATE new folder (only if CREATE_MISSING_FOLDERS=true)
```

### 3. First Run vs Second Run

#### First Run (Empty Excel IDs)
```
Excel Row: ID="REQ-001", Name="Test Requirement", Jama ID=""
Action: CREATE
Result: New item created in Jama with ID 123456
```

#### Second Run (If you update Excel with Jama IDs)
```
Excel Row: ID="REQ-001", Name="Test Requirement", Jama ID="123456"
Action: SKIP
Result: No duplicate created, existing item left unchanged
```

#### Second Run (If you DON'T update Excel)
```
Excel Row: ID="REQ-001", Name="Test Requirement", Jama ID=""
Action: CREATE (because no Jama ID to check)
Result: DUPLICATE CREATED ⚠️
```

## Recommended Workflow to Prevent Duplicates

### Option 1: Update Excel After First Import (Recommended)

**Step 1: First Import**
```bash
python csv2jama.py --execute
```

**Step 2: Export Results**
The script creates `import_results.csv` with:
- `jama_id` - The created Jama ID
- `document_key` - The Jama document key
- `source_id` - Your Excel ID

**Step 3: Update Excel**
Add the `jama_id` values back to your Excel file in the "Jama ID" column.

**Step 4: Subsequent Imports**
```bash
python csv2jama.py --execute
```
Rows with Jama IDs will be SKIPPED (no duplicates).

### Option 2: Use Document Key Resolution (For Folders Only)

**Folders automatically resolve by documentKey:**

First run:
```
Excel: ID="3.1", Item Type="Folder", Name="Section 3.1"
Result: Folder created with documentKey="3.1"
```

Second run:
```
Excel: ID="3.1", Item Type="Folder", Name="Section 3.1"
Action: Script searches for documentKey="3.1" → Found → RESOLVE
Result: No duplicate, uses existing folder
```

### Option 3: Use "create" Mode (Safety Mode)

If you want to prevent accidental re-runs:

```env
IMPORT_MODE=create
```

**Behavior:**
- If any row has a Jama ID → **ERROR** (prevents accidental duplicate)
- Forces you to clear Jama IDs before re-running

## What Happens in Each Scenario

### Scenario 1: Clean Re-run (Jama IDs Populated)

**Excel has Jama IDs:**
```
ID          Item Type           Name                    Jama ID
REQ-001     Software Req        Test Requirement        123456
REQ-002     Software Req        Another Requirement     123457
```

**Result:**
```
[SKIP] Existing Software Requirement has Jama ID 123456
[SKIP] Existing Software Requirement has Jama ID 123457
```

✅ **No duplicates created**

### Scenario 2: Re-run Without Jama IDs (Requirements)

**Excel has NO Jama IDs:**
```
ID          Item Type           Name                    Jama ID
REQ-001     Software Req        Test Requirement        
REQ-002     Software Req        Another Requirement     
```

**Result:**
```
[CREATE] Software Requirement: Test Requirement
[CREATE] Software Requirement: Another Requirement
```

⚠️ **DUPLICATES CREATED** (new items with new Jama IDs)

### Scenario 3: Re-run Without Jama IDs (Folders)

**Excel has NO Jama IDs but has consistent Excel IDs:**
```
ID          Item Type           Name                    Jama ID
3.1         Folder             Section 3.1              
3.1.1       Folder             Section 3.1.1            
```

**Result (with default settings):**
```
[RESOLVE] Existing folder by documentKey '3.1' -> Jama ID 123456
[RESOLVE] Existing folder by documentKey '3.1.1' -> Jama ID 123457
```

✅ **No duplicates created** (folders resolved by documentKey)

### Scenario 4: Folder with Inconsistent IDs

**Excel IDs change between runs:**

First run:
```
ID="folder_a"  →  Creates folder with documentKey="folder_a"
```

Second run (changed ID):
```
ID="folder_b"  →  Searches for documentKey="folder_b"  →  Not found  →  Creates NEW folder
```

⚠️ **DUPLICATE CREATED** (because documentKey changed)

## Configuration Options

### Prevent Duplicate Folders

**Safest Setting (no duplicate folders):**
```env
RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=true
USE_EXCEL_ID_AS_DOCUMENT_KEY=true
CREATE_MISSING_FOLDERS=false
```

**Behavior:**
- Searches for existing folders by documentKey
- If not found → **ERROR** (prevents duplicate)
- Forces you to add Jama ID or create folder manually first

### Allow Duplicate Folders (Not Recommended)

```env
RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=false
CREATE_MISSING_FOLDERS=true
```

**Behavior:**
- Does NOT search for existing folders
- Always creates new folders
⚠️ **Every run creates duplicate folders**

### Safety Validation

The script prevents this unsafe combination:

```env
CREATE_MISSING_FOLDERS=true
RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=false
```

**Error:**
```
[ERROR] Unsafe configuration detected!
CREATE_MISSING_FOLDERS=true but RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=false
This combination will create duplicate folders.
Solution: Set RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=true
```

## Best Practices

### ✅ DO

1. **Keep Excel IDs consistent** - Don't change them between runs
2. **Use dry-run first** - Always check what will happen
   ```bash
   python csv2jama.py  # Dry-run
   ```
3. **Update Excel after import** - Add Jama IDs from `import_results.csv`
4. **Use default settings** - They're designed to prevent duplicates
5. **Review import_results.csv** - Check what was created/skipped

### ❌ DON'T

1. **Don't change Excel IDs** - Folders won't resolve correctly
2. **Don't run without checking** - Use dry-run first
3. **Don't disable folder resolution** - Leads to duplicates
4. **Don't mix modes** - Stick with "upsert" (default)

## Checking for Duplicates

### Before Second Run

**Use dry-run mode:**
```bash
python csv2jama.py
```

**Look for:**
```
[DRY RUN] Would POST: ...  # New item will be created
[DRY RUN] SKIP: Existing ... has Jama ID ...  # No duplicate
[DRY RUN] Resolved folder by documentKey ...  # No duplicate
```

### After Import

**Check the results CSV:**
```bash
cat import_results.csv
```

**Look for:**
- `action=CREATE, status=CREATED` - New items
- `action=SKIP, status=SKIPPED_NO_CHANGE` - Existing items (no duplicate)
- `action=RESOLVE, status=RESOLVED_PARENT` - Existing folders (no duplicate)

## Summary

### Will It Create Duplicates?

| Scenario | Folders | Requirements | Solution |
|----------|---------|--------------|----------|
| First run, no Jama IDs | Create new | Create new | Normal ✓ |
| Second run, WITH Jama IDs | RESOLVE | SKIP | No duplicates ✓ |
| Second run, NO Jama IDs, same Excel IDs | RESOLVE | CREATE | Folders OK, Requirements duplicated ⚠️ |
| Second run, NO Jama IDs, changed Excel IDs | CREATE | CREATE | All duplicated ⚠️ |

### Recommendation

**To prevent duplicates:**

1. Use default settings (already correct)
2. After first import, update Excel with Jama IDs from `import_results.csv`
3. Always dry-run first: `python csv2jama.py`
4. Keep Excel IDs consistent for folder resolution

**With these practices, no duplicates will be created!**
