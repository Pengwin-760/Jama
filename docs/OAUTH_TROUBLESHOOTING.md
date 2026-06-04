# OAuth and JSON Parsing Troubleshooting Guide

## Fixed Issues

### 1. Double Slash in URLs ✅

**Problem:**
```
https://your-jama-instance.com/rest/v1//items
```

**Solution:**
Added `build_api_url()` helper that safely joins base URL and endpoint:

```python
def build_api_url(endpoint: str) -> str:
    base = JAMA_BASE_URL.rstrip("/")
    path = endpoint.lstrip("/")
    return f"{base}/{path}"
```

**Result:**
```
https://your-jama-instance.com/rest/v1/items  ✓
```

Works with both:
- `jama_get("/items")` → `https://host.com/rest/v1/items`
- `jama_get("items")` → `https://host.com/rest/v1/items`

### 2. JSON Parsing Errors ✅

**Problem:**
- Generic "Expecting value: line 47 column 1 (char 46)" errors
- No visibility into what the server actually returned
- Could be OAuth response or API response

**Solution:**
Added `parse_json_response()` helper with detailed diagnostics:

```python
def parse_json_response(response, context: str):
    # Shows: status, URL, content-type, first 500 chars
    # Used by: OAuth, GET, POST, PUT
```

**Now shows:**
```
OAuth token request did not return valid JSON.
Status: 200
URL: https://your-jama-instance.com/rest/oauth/token
Content-Type: text/html
Response preview:
<html><body>Login Required</body></html>

Likely causes: authentication failure, HTML login page, wrong OAuth URL,
wrong JAMA_BASE_URL, SSL/proxy issue, or expired/incorrect credentials.
```

### 3. OAuth Token URL ✅

**Problem:**
OAuth endpoint was incorrectly constructed from `JAMA_BASE_URL`

**Default behavior:**
```env
JAMA_BASE_URL=https://your-jama-instance.com/rest/v1
```

**Constructs:**
```
https://your-jama-instance.com/rest/oauth/token
```

**Custom override (if needed):**
```env
JAMA_OAUTH_TOKEN_URL=https://your-jama-instance.com/rest/oauth/token
```

## Debug Configuration

### Enable Debug Logging

Add to `.env`:

```env
DEBUG_JAMA_AUTH=true
DEBUG_JAMA_GET=true
```

### Debug Output Examples

**OAuth Debug:**
```
[INFO] Obtaining OAuth access token...
[DEBUG] OAuth token URL: https://your-jama-instance.com/rest/oauth/token
[DEBUG] OAuth status: 200
[DEBUG] OAuth token request content-type: application/json
[DEBUG] OAuth token request response preview (first 500 chars): {"access_token":"...","token_type":"Bearer"}
```

**GET Debug:**
```
[INFO] Attempting to resolve folder by documentKey: EGL_CV-FLD-220
[DEBUG] GET URL: https://your-jama-instance.com/rest/v1/items
[DEBUG] GET params: {'project': 279, 'contains': 'EGL_CV-FLD-220', 'startAt': 0, 'maxResults': 20}
[DEBUG] GET status: 200
[DEBUG] GET /items content-type: application/json
[DEBUG] GET /items response preview (first 500 chars): {"data":[...],"meta":{}}
```

**No credentials or tokens are printed in debug mode.**

## Common Issues and Solutions

### Issue 1: HTML Login Page Instead of JSON

**Symptoms:**
```
OAuth token request did not return valid JSON.
Content-Type: text/html
Response preview:
<html><body>Login Required</body></html>
```

**Solutions:**
1. Check `JAMA_CLIENT_ID` and `JAMA_CLIENT_SECRET` are correct
2. Verify OAuth credentials are not expired
3. Check if OAuth is enabled for your Jama instance
4. Try Bearer token or Basic auth instead

### Issue 2: Wrong OAuth URL

**Symptoms:**
```
OAuth token request failed: 404
URL: https://your-jama-instance.com/rest/v1/oauth/token
```

**Solutions:**
Set custom OAuth URL in `.env`:
```env
JAMA_OAUTH_TOKEN_URL=https://your-jama-instance.com/rest/oauth/token
```

Common variations:
- `https://host.com/rest/oauth/token` (most common)
- `https://host.com/oauth/token`
- `https://host.com/rest/v1/oauth/token`

Enable debug to see what URL is being used:
```env
DEBUG_JAMA_AUTH=true
```

### Issue 3: Double Slash in API URLs

**Symptoms:**
```
[DEBUG] GET URL: https://your-jama-instance.com/rest/v1//items
```

**Solution:**
This should now be fixed automatically by `build_api_url()`. If you still see double slashes, verify:

```env
JAMA_BASE_URL=https://your-jama-instance.com/rest/v1
```

Do NOT end with trailing slash:
```env
# Wrong:
JAMA_BASE_URL=https://your-jama-instance.com/rest/v1/

# Correct:
JAMA_BASE_URL=https://your-jama-instance.com/rest/v1
```

### Issue 4: SSL Certificate Errors

**Symptoms:**
```
SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]
```

**Solutions:**

**Option 1:** Use custom certificate
```env
JAMA_SSL_CERT=certs/jama_cert_chain.pem
```

**Option 2:** Disable verification (temporary debugging only)
```env
JAMA_SSL_VERIFY=false
```

### Issue 5: Authentication Redirect

**Symptoms:**
```
GET /items did not return JSON.
Status: 302
Content-Type: text/html
Response preview:
<html>Redirecting to login...</html>
```

**Solutions:**
1. OAuth token may have expired - script should auto-refresh
2. Check authentication credentials in `.env`
3. Verify you have API access enabled for your account
4. Try different auth method (OAuth vs Bearer vs Basic)

## Testing OAuth Configuration

### Test 1: Enable Debug Mode

```bash
export DEBUG_JAMA_AUTH=true
export DEBUG_JAMA_GET=true
python3 csv2jama.py --mode upsert --dry-run
```

Look for:
```
[INFO] OAuth token URL configured: yes (custom) / no (using default)
[DEBUG] OAuth token URL: <actual URL being used>
[DEBUG] OAuth status: 200
```

### Test 2: Verify Token Retrieval

Script should print:
```
[INFO] Obtaining OAuth access token...
[INFO] OAuth access token obtained successfully
```

If it fails, you'll see detailed error with:
- HTTP status code
- OAuth endpoint URL
- Content-Type header
- Response preview

### Test 3: Verify GET Requests Work

After OAuth succeeds, folder lookup should work:
```
[INFO] Attempting to resolve folder by documentKey: EGL_CV-FLD-220
[DEBUG] GET URL: https://your-jama-instance.com/rest/v1/items
[DEBUG] GET status: 200
[INFO] Resolved existing folder by documentKey 'EGL_CV-FLD-220' -> Jama ID 123456
```

## API Function Coverage

All API functions now use robust error handling:

| Function | Uses build_api_url() | Uses parse_json_response() | Error Diagnostics |
|----------|---------------------|---------------------------|-------------------|
| `get_oauth_token()` | N/A (custom URL logic) | ✅ | ✅ |
| `jama_get()` | ✅ | ✅ | ✅ |
| `jama_post()` | ✅ | ✅ | ✅ |
| `jama_put()` | ✅ | ✅ | ✅ |

## Startup Configuration Display

Script now shows at startup:

```
[INFO] Jama base URL: https://your-jama-instance.com/rest/v1
[INFO] Jama project ID: 279
[INFO] OAuth token URL configured: no (using default)
[INFO] SSL verify: certs/jama_cert_chain.pem
[INFO] Debug Jama Auth: True
[INFO] Debug Jama GET: True
```

This helps verify configuration before any API calls are made.

## Environment Variables Summary

### Required:
```env
JAMA_BASE_URL=https://your-jama-instance.com/rest/v1
JAMA_PROJECT_ID=279
ROOT_PARENT_ITEM_ID=67890

# Authentication (pick one method):
# OAuth:
JAMA_CLIENT_ID=your_client_id
JAMA_CLIENT_SECRET=your_client_secret

# OR Bearer Token:
# JAMA_BEARER_TOKEN=your_token

# OR Basic Auth:
# JAMA_USERNAME=your_username
# JAMA_PASSWORD=your_password
```

### Optional:
```env
# Debug settings
DEBUG_JAMA_AUTH=false
DEBUG_JAMA_GET=false

# Custom OAuth URL (if default doesn't work)
# JAMA_OAUTH_TOKEN_URL=https://your-jama-instance.com/rest/oauth/token

# SSL
JAMA_SSL_CERT=certs/jama_cert_chain.pem
# JAMA_SSL_VERIFY=false  # only for debugging

# Folder lookup
RESOLVE_EXISTING_FOLDERS_BY_DOCUMENT_KEY=true
CREATE_MISSING_FOLDERS=false
```

## Next Steps If Still Failing

1. **Enable both debug flags:**
   ```env
   DEBUG_JAMA_AUTH=true
   DEBUG_JAMA_GET=true
   ```

2. **Run dry-run and capture output:**
   ```bash
   python3 csv2jama.py --mode upsert --dry-run 2>&1 | tee debug.log
   ```

3. **Check the log for:**
   - OAuth token URL being used
   - OAuth response status and content-type
   - GET URL (should have no double slashes)
   - GET response status and content-type
   - First 500 chars of any failed response

4. **Share the relevant debug output** (redact any tokens/secrets)

5. **If OAuth URL is wrong**, set `JAMA_OAUTH_TOKEN_URL` explicitly

6. **If still getting HTML responses**, authentication is likely failing - try different auth method or verify credentials
