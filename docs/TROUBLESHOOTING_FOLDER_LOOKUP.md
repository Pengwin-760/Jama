# Troubleshooting Folder Lookup JSON Errors

## Problem
Folder lookup by documentKey fails with: "Expecting value: line 47 column 1 (char 46)"

## Root Cause
The Jama API `/items` search endpoint is not returning valid JSON. This usually means:
1. Authentication is failing (HTML error page returned)
2. API endpoint URL is incorrect
3. SSL/certificate issues causing partial responses
4. The search endpoint is not available or working

## Quick Fix: Disable Folder Resolution

Add this to your `.env` file:

```env
# Disable automatic folder resolution by documentKey
# This will skip the problematic API calls
RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=false

# You must provide explicit Jama IDs for all folders
# Or enable folder creation
CREATE_MISSING_FOLDERS=true
```

## Option 1: Disable Folder Lookup (Recommended for Now)

```env
RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=false
CREATE_MISSING_FOLDERS=false
```

**Result:** Folders without explicit Jama IDs will fail. You must provide Jama IDs in the spreadsheet.

## Option 2: Enable Folder Creation

```env
RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=false
CREATE_MISSING_FOLDERS=true
```

**Result:** Folders without Jama IDs will be created as new items (duplicates possible).

## Option 3: Debug the API Call

Test the API endpoint manually:

```bash
# Test with curl (adjust credentials)
curl -X GET "https://your-jama-instance.com/rest/v1/items?project=<project_id>&contains=PROJ-FLD-211" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Accept: application/json" \
  --cert certs/jama_cert_chain.pem

# Or with OAuth
curl -X GET "https://your-jama-instance.com/rest/v1/items?project=<project_id>&contains=PROJ-FLD-211" \
  -u "CLIENT_ID:CLIENT_SECRET" \
  -H "Accept: application/json"
```

Look for:
- Is the response HTML instead of JSON?
- Is there a redirect (301, 302)?
- Is authentication working?
- Is the endpoint URL correct?

## Common Causes:

### 1. Base URL Missing `/rest/v1`
Check your `.env`:
```env
# Wrong:
JAMA_BASE_URL=https://your-jama-instance.com

# Correct:
JAMA_BASE_URL=https://your-jama-instance.com/rest/v1
```

### 2. OAuth Token Expired
If using OAuth, the token might have expired. The script should auto-refresh but might fail if the endpoint is wrong.

### 3. SSL Certificate Chain Issues
If using custom certs:
```env
JAMA_SSL_CERT=certs/jama_cert_chain.pem
```

Try temporarily:
```env
JAMA_SSL_VERIFY=false  # TEMPORARY - for debugging only
```

### 4. Project ID Incorrect
Make sure JAMA_PROJECT_ID matches your actual Jama project:
```env
JAMA_PROJECT_ID=<your_project_id>
```

## Recommended Workflow

**For now, use Option 1 or 2 above to bypass the folder lookup entirely.**

Then:
1. Either populate all Jama IDs in your spreadsheet (no lookup needed)
2. Or enable CREATE_MISSING_FOLDERS=true and accept that folders will be created fresh

The folder lookup feature is a convenience but not required for the import to work.
