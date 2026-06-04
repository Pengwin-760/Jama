# Jama Excel Import Tool

Import requirements from Excel into Jama Connect.

## Quick Start

### 1. Setup

Copy the example configuration:
```bash
cp .env.example .env
```

Edit `.env` and configure:
- `JAMA_BASE_URL` - Your Jama instance URL
- `JAMA_PROJECT_ID` - Target project ID
- `ROOT_PARENT_ITEM_ID` - Parent item for import
- `INPUT_FILE` - Path to your Excel file
- OAuth credentials or Bearer token
- SSL certificate path

### 2. Run

Dry-run (safe preview):
```bash
python csv2jama.py
```

Execute import:
```bash
python csv2jama.py --execute
```

## Features

### Duplicate Prevention
- **Folders**: Resolved by Jama `documentKey` (no duplicates on re-run)
- **Requirements**: Skipped if `Jama ID` column is populated
- **Upsert mode**: Default mode creates new items only if they don't exist

### Verification Method
Supports letter aliases and full names:
- `T` / `Test` → Test (422)
- `I` / `Inspection` → Inspection (420)
- `D` / `Demonstration` → Demonstration (419)
- `A` / `Analysis` → Analysis (418)

Verification Method uses a list of picklist option IDs, e.g. [422].

### Dynamic Field Detection
Verification method field keys discovered automatically from cached Jama items.
Searches using `startswith("verification_method$")`. Handles empty target Sets with project-wide fallback.

### Folder Resolution
Excel Folder IDs are treated as Jama documentKeys for lookup.
- Resolves existing folders by `documentKey`
- Creates missing folders when `CREATE_MISSING_FOLDERS=true`
- Supports section numbering (e.g., "3.1", "3.1.1")
- A resolved or created folder becomes the active parent for following rows.

## Configuration

### Important Settings

```env
# Input/Output
INPUT_FILE=input/EAGLET SS Jama IMPORT.xlsx

# Jama Connection
JAMA_BASE_URL=https://your-jama-instance.com/rest/v1
JAMA_PROJECT_ID=123
ROOT_PARENT_ITEM_ID=123456

# SSL Certificate
JAMA_SSL_CERT=certs/jama_cert_chain.pem
JAMA_SSL_VERIFY=true

# Import Behavior
IMPORT_MODE=upsert
DRY_RUN=true
RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=true
CREATE_MISSING_FOLDERS=true

# Item Types
JAMA_ITEM_TYPE_FOLDER=32
JAMA_ITEM_TYPE_SOFTWARE_REQUIREMENT=112

# Verification Method (optional - auto-detected if blank)
JAMA_FIELD_VERIFICATION_METHOD=
```

### Authentication

Supports three methods (priority order):
1. OAuth 2.0 (recommended): `JAMA_CLIENT_ID` + `JAMA_CLIENT_SECRET`
2. Bearer Token: `JAMA_BEARER_TOKEN`
3. Basic Auth: `JAMA_USERNAME` + `JAMA_PASSWORD`

## Excel Format

Required columns:
- `ID` - Excel reference ID
- `Item Type` - Folder, Software Requirement, etc.
- `Name` - Item name (required)

Optional columns:
- `Description` - Item description (required for requirements)
- `Verification Method` - T, I, D, A or full names
- `Jama ID` - Populated after first import to prevent duplicates
- `Document Key` - Jama document key
- `Global ID` - Jama global ID

Supported item types:
- Folder
- Set
- Segment
- Subsystem
- Stakeholder Requirement
- Subsystem Requirement
- Software Requirement
- Text / Text Document

### Import Model

- Folder rows resolve by Jama documentKey
- For Folder rows, Excel ID is treated as the Jama documentKey
- Missing folders can be created when `CREATE_MISSING_FOLDERS=true`
- Resolved or created folders become the active parent for following rows
- Requirement rows post under the active parent
- Text items are content rows: they have a parent location but no childItemType

## Output

Results are written to `output/import_results.csv` with:
- Action taken (CREATE, RESOLVE, SKIP)
- Status (CREATED, SKIPPED_NO_CHANGE, etc.)
- Jama IDs for created items
- Document keys
- Any errors

## Workflow to Prevent Duplicates

1. **First Import:**
   ```bash
   python csv2jama.py --execute
   ```

2. **Update Excel:**
   Add Jama IDs from `output/import_results.csv` to your Excel file's "Jama ID" column

3. **Subsequent Imports:**
   ```bash
   python csv2jama.py --execute
   ```
   Items with Jama IDs will be skipped (no duplicates)

## Project Structure

```
.
├── csv2jama.py              # Main import script
├── jama2csv.py              # Export script (reference)
├── .env                     # Your configuration (not in git)
├── .env.example             # Configuration template
├── README.md                # This file
├── requirements.txt         # Python dependencies
│
├── certs/                   # SSL certificates
│   └── jama_cert_chain.pem
│
├── input/                   # Excel input files
│   └── *.xlsx
│
├── output/                  # Generated reports
│   └── import_results.csv
│
├── docs/                    # Documentation
│   ├── DUPLICATE_PREVENTION.md
│   ├── VERIFICATION_ARRAY_FORMAT_FIX.md
│   └── ... (other docs)
│
└── archive/                 # Archived files
    ├── old_scripts/
    ├── old_tests/
    └── old_prompts/
```

## Common Issues

### SSL Certificate Errors
Ensure `JAMA_SSL_CERT` points to the correct certificate chain file.

### Folder Not Found
- Check `RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=true`
- Verify Excel ID matches Jama documentKey
- Or set `CREATE_MISSING_FOLDERS=true` to create new folders

### Verification Method Field Not Found
- Leave `JAMA_FIELD_VERIFICATION_METHOD` blank for auto-detection
- Or set explicitly: `JAMA_FIELD_VERIFICATION_METHOD=verification_method$112`

### Duplicates Created
- Ensure Excel has Jama IDs from previous import
- Use `IMPORT_MODE=upsert` (default)
- For folders: keep Excel IDs consistent between runs

## Development

### Install Dependencies
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Compile Check
```bash
python -m py_compile csv2jama.py
```

## Related Scripts

- `jama2csv.py` - Export requirements from Jama to CSV

## Documentation

See `docs/` folder for detailed documentation:
- `DUPLICATE_PREVENTION.md` - How duplicate prevention works
- `VERIFICATION_ARRAY_FORMAT_FIX.md` - Verification method format
- `FIX_ITEM_TYPE_ID.md` - item_type_id fix details

## License

Internal General Atomics tool.
