---
name: run-jama-importer
description: Run the Jama Excel import tool - build, validate, dry-run, or execute the csv2jama.py importer
---

# run-jama-importer

Import requirements from Excel into Jama Connect. This is a CLI tool that reads Excel files and creates/updates Jama items via REST API. Safe dry-run is the default; execute mode requires explicit flag.

**Agent path**: Use `.claude/skills/run-jama-importer/smoke.sh` to validate setup, or run `.venv/bin/python csv2jama.py` directly for dry-run.

All paths in this document are relative to the project root (`/home/wsl-user/projects/Jama`).

## Prerequisites

Python 3.8+ with venv. Dependencies are in `requirements.txt`.

```bash
# Already installed in this project:
# - Python venv at .venv/
# - Dependencies: pandas, openpyxl, requests, python-dotenv
```

## Setup from clean checkout

```bash
# 1. Create virtual environment
python -m venv .venv

# 2. Activate it
source .venv/bin/activate

# 3. Install dependencies
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 4. Copy environment template
cp .env.example .env

# 5. Edit .env with your Jama configuration
# Required: JAMA_BASE_URL, JAMA_PROJECT_ID, ROOT_PARENT_ITEM_ID, INPUT_FILE
# Required: Authentication (OAuth, Bearer token, or Basic auth)
# Required: Item type IDs (JAMA_ITEM_TYPE_SET, FOLDER, TEXT, REQUIREMENT, etc.)
```

## Configuration

Edit `.env` to include your local Jama instance values:

```env
# Connection
JAMA_BASE_URL=https://your-jama-instance.com/rest/v1
JAMA_PROJECT_ID=<project_id>
ROOT_PARENT_ITEM_ID=<root_parent_id>
INPUT_FILE=input/requirements_import.xlsx

# Authentication (pick one)
JAMA_CLIENT_ID=<client_id>
JAMA_CLIENT_SECRET=<client_secret>

# Item Type IDs (required - get from your Jama admin panel)
JAMA_ITEM_TYPE_SET=<id>
JAMA_ITEM_TYPE_FOLDER=<id>
JAMA_ITEM_TYPE_TEXT=<id>
JAMA_ITEM_TYPE_REQUIREMENT=<id>

# Optional
JAMA_SSL_CERT=certs/jama_cert_chain.pem
```

**CRITICAL**: `.env` is not tracked in Git. Never commit real item type IDs, URLs, project IDs, document keys, Global IDs, or credentials.

## Build

Compile check:

```bash
.venv/bin/python -m py_compile csv2jama.py
```

No compilation needed - Python is interpreted.

## Run (agent path)

**Smoke test** (validates setup + runs dry-run):

```bash
.claude/skills/run-jama-importer/smoke.sh
```

**Expected output**:
```
=== Jama Import Tool Smoke Test ===
[1/5] Checking prerequisites...
✓ Prerequisites OK
[2/5] Running compile check...
✓ Compilation OK
[3/5] Validating .env configuration...
✓ Configuration OK
[4/5] Checking input file...
✓ Input file exists: input/requirements_import.xlsx
[5/5] Running dry-run...
[INFO] Loaded configuration from .env
...
IMPORT SUMMARY
Created rows: 218
Resolved parent rows: 51
Skipped rows: 0
Failed rows: 0
Results CSV: output/import_results.csv
✓ Dry-run completed successfully
=== All checks passed ===
```

**Dry-run only** (safe, no Jama changes):

```bash
.venv/bin/python csv2jama.py
```

**Execute mode** (creates real Jama items - only run when explicitly asked):

```bash
.venv/bin/python csv2jama.py --execute
```

## Run (human path)

Same as agent path. This is a CLI tool with no GUI.

Activate venv first if preferred:

```bash
source .venv/bin/activate
python csv2jama.py          # dry-run
python csv2jama.py --execute # execute
```

## Test

Run the smoke test:

```bash
.claude/skills/run-jama-importer/smoke.sh
```

Unit tests are not implemented. The smoke test validates:
- Prerequisites (venv, .env, csv2jama.py)
- Compilation
- Configuration (required env vars)
- Input file exists
- Dry-run completes successfully
- Output CSV is created

## Direct invocation

Import and call functions directly for testing internal logic:

```bash
.venv/bin/python -c "
from csv2jama import normalize_for_match, load_configuration

# Test duplicate matching normalization
print(normalize_for_match('  Test  Name  123  '))

# Load config
config = load_configuration()
print(f'Project ID: {config[\"JAMA_PROJECT_ID\"]}')
"
```

## Output

**Dry-run**:
- Prints import configuration
- Shows what would be created
- Writes `output/import_results.csv` with actions (CREATE, RESOLVE, SKIP)
- Does NOT create Jama items

**Execute**:
- All dry-run behavior
- **Actually creates/updates Jama items via API**
- Records Jama IDs and Global IDs in output CSV
- Use output CSV to update Excel "Jama ID" column to prevent duplicates on re-run

## Gotchas

**1. Item type IDs are instance-specific**

Item type IDs vary between Jama instances. You MUST get the correct IDs from your Jama admin panel. The `.env.example` template has blank values - fill them in with your instance's IDs.

```bash
# Wrong (example IDs from docs):
JAMA_ITEM_TYPE_FOLDER=32

# Right (your instance's IDs):
JAMA_ITEM_TYPE_FOLDER=<your_folder_type_id>
```

**2. Verification Method uses dynamic field discovery**

The script searches for `verification_method$<suffix>` fields in cached Jama items. If you see:

```
[WARN] verification_method field key not found
```

This means the script couldn't find any items with verification method fields. This is informational - the script will skip verification method if your project doesn't use it.

**3. Folder resolution requires documentKey**

Folders are resolved by Jama `documentKey` (not ID). The Excel "ID" column is treated as the documentKey for folder rows. If folder lookup fails:

- Set `RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=true` (default)
- Verify Excel ID matches Jama documentKey
- Or set `CREATE_MISSING_FOLDERS=true` to create new folders

**4. SSL certificate errors**

If you see `SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]`:

```env
# Option 1: Use custom certificate
JAMA_SSL_CERT=certs/jama_cert_chain.pem

# Option 2: Disable verification (debugging only, not production)
JAMA_SSL_VERIFY=false
```

**5. OAuth token URL may need customization**

Default OAuth URL is `https://<base>/rest/oauth/token`. If this fails with 404:

```env
JAMA_OAUTH_TOKEN_URL=https://your-jama-instance.com/rest/oauth/token
```

Enable debug to see what URL is being used:

```env
DEBUG_JAMA_AUTH=true
DEBUG_JAMA_GET=true
```

**6. Always use .venv/bin/python, not system python3**

The venv contains required packages (pandas, requests, dotenv, openpyxl). Using system `python3` will fail with `ModuleNotFoundError`.

```bash
# Wrong:
python3 csv2jama.py

# Right:
.venv/bin/python csv2jama.py
```

**7. Duplicate prevention uses Global ID lookup + pre-POST checking**

The script prevents duplicates by:
- Checking Excel "Jama ID" column (skip if populated)
- Looking up Global IDs from previous imports (pattern: GID-\d+)
- Pre-POST check: matching by parent + itemType + normalized name

If you interrupt the script mid-import and re-run, it will skip already-created items.

## Troubleshooting

**Missing `.env`**:
```
FileNotFoundError: .env file not found
```
**Fix**: `cp .env.example .env` and edit with your values.

**Missing item type IDs**:
```
[ERROR] Missing required configuration: JAMA_ITEM_TYPE_SET
```
**Fix**: Add real item type IDs to `.env` (check your Jama admin panel).

**Missing dependencies**:
```
ModuleNotFoundError: No module named 'pandas'
```
**Fix**: Use `.venv/bin/python` not system `python3`. Run `pip install -r requirements.txt` inside venv.

**Missing input file**:
```
FileNotFoundError: input/requirements_import.xlsx not found
```
**Fix**: Place Excel file in `input/` directory and update `INPUT_FILE` in `.env`.

**OAuth credential errors**:
```
OAuth token request did not return valid JSON.
Content-Type: text/html
```
**Fix**: Check `JAMA_CLIENT_ID` and `JAMA_CLIENT_SECRET` are correct. Try Bearer token or Basic auth instead.

**Child item type errors**:
```
[ERROR] Cannot infer childItemType for parent <id>
```
**Fix**: Add `JAMA_ITEM_TYPE_SEGMENT=<id>` to `.env` if using Segments as containers, or add explicit `childItemType` column in Excel.

## Safety rules

**CRITICAL**:
- **Do not run `--execute` unless explicitly asked**
- Do not modify `.env` unless explicitly asked
- Do not print secrets (tokens, passwords, client secrets)
- Do not commit `.env`, `certs/`, `output/`, `input/` directories
- Do not hardcode real Jama IDs in code or templates
- Always use `.venv/bin/python` for validation and execution

Before committing, verify sensitive files are not staged:

```bash
git status --short
git diff --cached
```

Verify `.env`, `certs/`, `output/`, `archive/`, real item type IDs, real Jama URLs, real project IDs, real document keys, and Global IDs are **NOT** staged.

## Related documentation

- `docs/CLAUDE_PROJECT_GUIDE.md` - Project behavior and coding rules
- `docs/DEVELOPER_GUIDE.md` - Technical implementation details
- `docs/QUICK_REFERENCE.md` - Configuration reference
- `docs/OAUTH_TROUBLESHOOTING.md` - OAuth debugging guide
- `docs/README.md` - Documentation index
