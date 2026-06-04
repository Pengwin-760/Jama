# Claude Project Guide — Jama Excel Import Tool

This guide captures the working assumptions, style preferences, and safety rules for this project. Read this before editing `csv2jama.py`, docs, or related helper scripts.

## Project purpose

This project imports Jama items from Excel into Jama Connect using the REST API.

The main script is:

```bash
python csv2jama.py
```

Normal usage:

```bash
python csv2jama.py            # dry-run
python csv2jama.py --execute  # execute import
```

Dry-run must remain the default.

## High-priority safety rules

1. Do not rewrite the script from scratch.
2. Make targeted changes only.
3. Do not change working behavior unless explicitly requested.
4. Do not reintroduce automatic move/update behavior unless specifically requested.
5. Do not run execute unless explicitly asked.
6. Do not expose `.env` secrets, OAuth credentials, tokens, passwords, or cert contents.
7. Use the project Python environment/venv for validation, not bare system Python.

Validation commands:

```bash
.venv/bin/python -m py_compile csv2jama.py
.venv/bin/python csv2jama.py
```

or, if the venv is activated:

```bash
source .venv/bin/activate
python -m py_compile csv2jama.py
python csv2jama.py
```

Do not use bare `python3` unless dependencies are installed there.

## Use multiple agents/subagents when useful

For larger reviews, cleanup, refactors, testing, or validation work, use multiple agents/subagents if available.

Suggested split:

```text
- one agent to inspect current behavior and risks
- one agent to implement the requested change
- one agent to review diffs and run validation
```

Coordinate results before final edits so changes do not conflict.

## Core working behavior to preserve

Preserve these behaviors unless explicitly asked otherwise:

```text
- Existing folders resolve by documentKey.
- Global ID lookup is enabled when configured.
- Missing folders can be created when CREATE_MISSING_FOLDERS=true.
- Resolved and created folders become the active parent.
- New requirements/Text rows post under the active parent.
- Existing requirements/Text rows are skipped/resolved, not duplicated.
- Text rows include location.parent.item and no childItemType.
- Verification Method uses array payload, e.g. "verification_method$###": [422].
- Verification Method supports T/Test, I/Inspection, D/Demonstration, A/Analysis.
- Dynamic verification_method$... field discovery remains unchanged.
- Parent childItemType validation remains active for requirement rows.
- Folder childItemType inheritance/inference/fallback remains unchanged.
- Section number parsing supports 3, 3., and 3.0.
- Dry-run remains default.
```

## Identifier resolution priority

For most rows, resolve existing Jama items before creating new ones.

Resolution priority:

```text
1. Jama ID
2. Global ID
3. Document Key
4. Excel ID as documentKey for Folder rows, if configured
5. parent item ID + itemType + normalized Name duplicate check
6. Create only if no existing item is found
```

## Global ID behavior

Global ID is more robust than documentKey and should be used when available.

Global IDs look like:

```text
GID-768902
```

The importer should support raw Global IDs and Excel hyperlink formulas such as:

```text
=HYPERLINK("https://...","GID-768902")
```

Use a helper that extracts:

```regex
GID-\d+
```

Handle blank, NaN, and non-string values safely.

Do not call `.strip()` directly on raw pandas values.

If the Global ID cell is populated but no `GID-####` pattern can be extracted, warn and fall back to documentKey lookup.

Do not lowercase Global IDs unless Jama Global IDs are confirmed case-insensitive. Strip whitespace only.

Maintain a Global ID cache:

```python
_items_by_global_id = {}
_items_by_global_id_duplicates = {}
```

If duplicate Global IDs are found, fail clearly instead of overwriting.

## Folder behavior

Folder rows are routing anchors.

If a Folder row resolves to an existing Jama folder by Jama ID, Global ID, documentKey, Excel ID-as-documentKey, or parent/type/name match:

```text
- do not POST
- action = RESOLVE
- resolved_by = lookup method used
- register the folder as current_folder_item_id
- if section-numbered, register folder_by_section[section_number] = folder_id
- following rows should go under this folder
```

Folder resolution priority:

```text
A. Jama ID
B. Global ID
C. Document Key column
D. Excel ID as documentKey
E. parent + itemType + normalized name duplicate check
F. create if not found and CREATE_MISSING_FOLDERS=true
G. fail clearly
```

If an existing folder is found but its `childItemType` is incompatible, fail clearly.

Do not create a second folder with the same name just because the existing one is incompatible.

Safe rule:

```text
found existing folder + compatible childItemType = resolve
found existing folder + incompatible childItemType = fail
not found + CREATE_MISSING_FOLDERS=true = create
```

## Requirements and Text behavior

Requirement and Text rows are content rows, not routing anchors.

If a Requirement or Text row resolves to an existing Jama item by Jama ID, Global ID, documentKey, or parent/type/name match:

```text
- do not POST
- action = SKIP_EXISTING or RESOLVE
- record Jama ID / documentKey / globalId in import_results.csv
- do not update current_folder_item_id
```

If an existing content row resolves but has a different parent than the current active folder:

```text
- warn clearly
- do not POST a duplicate
- do not move the item
```

Do not add PUT/PATCH update or move behavior unless explicitly requested.

## Duplicate prevention

Before any POST, do a final duplicate check when enabled:

```env
ENABLE_PRE_POST_DUPLICATE_CHECK=true
DUPLICATE_MATCH_MODE=parent_type_name
```

Duplicate match rule:

```text
same parent item ID
same itemType
same normalized Name
```

For folders, also check `childItemType` when available.

If exactly one match is found:

```text
Folder row:
- resolve it
- register as active parent
- do not POST

Requirement/Text row:
- skip or resolve it
- do not POST
- do not change active parent
```

If multiple matches are found:

```text
- fail clearly
- print candidate Jama IDs/documentKeys/globalIds
- do not guess
```

## childItemType behavior

`childItemType` describes what a container can hold. It is not the folder’s own item type.

Folder/container `childItemType` should be determined in this priority:

```text
1. inherit from parent container metadata
2. infer from the next real requirement row under the folder
3. use DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE
4. use container-specific fallback, if configured
5. fail clearly
```

Text rows must not drive `childItemType` inference.

Text items have a parent location but no `childItemType`.

## Verification Method behavior

Verification Method maps to Jama picklist IDs:

```python
T / Test -> 422
I / Inspection -> 420
D / Demonstration -> 419
A / Analysis -> 418
```

Payload format is an array/list of picklist option IDs:

```json
"verification_method$112": [422]
```

Do not send a flat integer, object, or string.

The field key suffix may vary:

```text
verification_method$86
verification_method$112
verification_method$243
verification_method$<any number>
```

Do not assume the suffix equals itemType.

Discover dynamically from cached Jama item fields using field names that start with:

```python
"verification_method$"
```

If dynamic detection is ambiguous, fail clearly and ask for `JAMA_FIELD_VERIFICATION_METHOD` to be set explicitly.

## Section hierarchy behavior

Section parsing should support:

```text
3 REQUIREMENTS   -> 3.0
3. REQUIREMENTS  -> 3.0
3.0 REQUIREMENTS -> 3.0
3.1 Something    -> 3.1
3.1.1 Something  -> 3.1.1
```

Do not falsely parse standards or interface names as sections:

```text
MIL-STD-1553
MIL-STD-1760
UAI / 1553 Interface
```

Folders with section numbers should register in:

```python
folder_by_section[section_number] = jama_id
```

Child sections must resolve their parent section before creation/resolution.

## Configuration style

Configuration should live in `.env` and `.env.example`.

Do not modify `.env` unless explicitly asked.

It is okay to update `.env.example` comments.

Important config values include:

```env
JAMA_BASE_URL=
JAMA_PROJECT_ID=
ROOT_PARENT_ITEM_ID=
INPUT_FILE=

CREATE_MISSING_FOLDERS=true
USE_EXCEL_ID_AS_DOCUMENT_KEY=true
USE_GLOBAL_ID_LOOKUP=true
ENABLE_PRE_POST_DUPLICATE_CHECK=true
DUPLICATE_MATCH_MODE=parent_type_name

DEFAULT_REQUIREMENT_CHILD_ITEM_TYPE=
JAMA_FIELD_VERIFICATION_METHOD=
```

## Code style

Prefer practical engineering style over AI-looking explanations.

### Comments

Keep comments that explain why something exists.

Good:

```python
# Folder rows establish the active parent for following content rows.
```

```python
# childItemType describes what the container can hold, not the container's own type.
```

```python
# Verification Method is sent as a list of picklist option IDs, e.g. [422].
```

Bad:

```python
# Check for duplicates
# First occurrence
# Return response
# Set variable
# Loop through rows
```

Remove comments that simply restate the code.

### Docstrings

Use short docstrings. Avoid long Args/Returns/Examples blocks for obvious helper functions.

Good:

```python
def normalize_for_match(text: str) -> str:
    """Normalize text for duplicate matching."""
```

Move long examples or background notes into `docs/developer-notes.md`.

### Function organization

For functions with endpoints, pagination, fixed settings, or magic values, group tunable local settings near the top.

Good:

```python
def get_all_project_relationships(project_id: int, max_results: int = 1000):
    endpoint = "/relationships"
    omit_count = "true"

    all_relationships = []
    last_id = 1

    while True:
        params = {
            "project": project_id,
            "lastId": last_id,
            "omitCount": omit_count,
            "maxResults": max_results,
        }

        response_json = jama_get(endpoint, params=params)
```

This makes settings easy to find and modify.

Do not over-refactor working code. Prefer readability cleanup over architecture churn.

## Documentation style

Keep docs concise and practical.

Good doc sections:

```text
Overview
Setup
Configuration
Excel Format
Dry Run
Execute
Troubleshooting
Developer Notes
```

Avoid AI-like phrasing:

```text
This document provides a comprehensive overview...
It is important to note...
The following section will...
```

Prefer direct wording:

```text
Use this tool to import Jama items from Excel.
```

## Output/reporting behavior

`import_results.csv` should preserve useful debugging fields:

```text
excel_row
action
status
jama_id
document_key
global_id
source_id
item_type
name
resolved_by
parent_item_id
created_item_id
updated_item_id
error
```

If a row resolves by Global ID:

```text
resolved_by = global_id
```

If a row resolves by parent/type/name:

```text
resolved_by = parent_type_name_match
```

## Validation expectations

After edits, always run:

```bash
.venv/bin/python -m py_compile csv2jama.py
.venv/bin/python csv2jama.py
```

Do not run:

```bash
python csv2jama.py --execute
```

unless explicitly asked.

Final summary should include:

```text
- what changed
- what behavior was preserved
- whether compile passed
- whether dry-run passed
- any risks or follow-up items
```

## When uncertain

If a requested change risks breaking working import behavior, make the smallest safe change and explain the risk.

Prefer failing clearly over guessing, duplicating items, or silently moving/updating Jama content.
