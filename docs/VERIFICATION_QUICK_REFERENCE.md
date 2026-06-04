# Verification Method - Quick Reference

## Excel Input Values

| Input | Output | Picklist ID |
|-------|--------|-------------|
| T     | Test   | 422 |
| I     | Inspection | 420 |
| D     | Demonstration | 419 |
| A     | Analysis | 418 |
| test  | Test   | 422 |
| TEST  | Test   | 422 |
| inspection | Inspection | 420 |

## Field Key Resolution

### Automatic (Recommended)
```env
JAMA_FIELD_VERIFICATION_METHOD=
```
Searches cached items for `verification_method$*` fields

### Explicit Override
```env
JAMA_FIELD_VERIFICATION_METHOD=verification_method$243
```
Uses exact key specified

## Payload Format

### ✅ CORRECT
```json
{
  "verification_method$243": 422
}
```
Flat integer value

### ❌ WRONG
```json
{
  "verification_method$243": "422"
}
```
String wrapped (wrong)

```json
{
  "verification_method$243": {"id": 422}
}
```
Object wrapped (wrong)

```json
{
  "verification_method$243": [422]
}
```
Array wrapped (wrong)

## Resolution Logic

```
1. Check .env for exact key → Use it
2. Search items with same itemType → Use if exactly 1 found
3. Search all project items → Use if exactly 1 found
4. Multiple found → Error with candidate list
5. None found → Error with guidance
```

## Common Errors

### Multiple candidates found
```text
Solution: Set JAMA_FIELD_VERIFICATION_METHOD=verification_method$243 in .env
```

### No candidates found
```text
Solution: Ensure project has items with verification fields in cache,
or set JAMA_FIELD_VERIFICATION_METHOD explicitly
```

### Jama rejects with value 422
```text
Diagnosis: Value is correct, field key suffix is wrong
Solution: Set correct key in .env (e.g., verification_method$243)
```

## Logging Output

### Dynamic Resolution
```
[INFO] Verification Method: T -> Test -> 422
[INFO] Verification field key candidates found (itemType=112): verification_method$243
[INFO] Verification field key resolved dynamically: verification_method$243
[INFO] Verification payload: "verification_method$243": 422 (flat integer)
```

### Explicit .env
```
[INFO] Verification Method: T -> Test -> 422
[INFO] Verification field key from .env: verification_method$243
[INFO] Verification payload: "verification_method$243": 422 (flat integer)
```

## Testing

```bash
# Compile check
python3 -m py_compile csv2jama.py

# Test mappings
python3 test_verification_simple.py

# Dry-run
python3 csv2jama.py

# Execute
python3 csv2jama.py --execute
```

## Key Points

✓ Uses `startswith("verification_method$")` like export script  
✓ Suffix does NOT always equal item type ID  
✓ Value is flat integer (never wrapped)  
✓ Only applies to requirement rows  
✓ Fails clearly if ambiguous with candidate list  
✓ No hardcoded .env value required  
