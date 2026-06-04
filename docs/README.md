# Jama Requirements Importer

Python script to import and update requirements in Jama from Excel/CSV files.

## Features

- **Upsert support**: Create new items or update existing items
- **Folder resolution**: Automatically find existing folders by documentKey
- **Hierarchy support**: Numbered sections (1.0, 1.1, 1.1.1) and unnumbered folders
- **OAuth 2.0 authentication**: Secure authentication with client credentials
- **SSL certificate support**: Works with internal/company certificates
- **Dry-run mode**: Preview changes before executing

## Prerequisites

- Python 3.8+
- WSL (Windows Subsystem for Linux) or Linux/macOS

## Installation

### 1. Create and activate virtual environment

```bash
cd /home/wsl-user/projects/Jama
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

## SSL Certificate Configuration

If your Jama instance uses an internal or company-issued certificate, you need to provide the certificate chain for SSL verification.

### Export Jama Certificate Chain

Run this command from WSL to export the certificate:

```bash
# Create certs directory
mkdir -p certs

# Export certificate chain from Jama server
openssl s_client -showcerts \
  -connect your-jama-instance.com:443 \
  -servername your-jama-instance.com </dev/null 2>/dev/null \
  | awk '/BEGIN CERTIFICATE/,/END CERTIFICATE/ { print }' \
  > certs/jama_cert_chain.pem
```

### Verify Certificate File

Check that the certificate was captured correctly:

```bash
# Count certificates in the chain (should be 1 or more)
grep -c "BEGIN CERTIFICATE" certs/jama_cert_chain.pem

# Display certificate details
openssl x509 -in certs/jama_cert_chain.pem -noout -subject -issuer -dates
```

Expected output shows subject, issuer, and validity dates:
```
subject=CN=your-jama-instance.com, O=Your Company, ...
issuer=CN=Your Company Internal CA, ...
notBefore=Jan 1 00:00:00 2024 GMT
notAfter=Dec 31 23:59:59 2025 GMT
```

### Configure SSL in .env

Update your `.env` file with the SSL settings:

```env
# Use custom certificate file
JAMA_SSL_VERIFY=true
JAMA_SSL_CERT=certs/jama_cert_chain.pem
```

**SSL Options:**
- `JAMA_SSL_VERIFY=true` (default) - Use standard certificate verification
- `JAMA_SSL_CERT=certs/jama_cert_chain.pem` - Use custom certificate file
- `JAMA_SSL_VERIFY=false` - Disable SSL verification (not recommended, debugging only)

## Configuration

### 1. Copy example configuration

```bash
cp .env.example .env
```

### 2. Edit .env with your settings

```bash
nano .env
```

Required settings:
- `JAMA_BASE_URL` - Your Jama instance URL
- `JAMA_CLIENT_ID` and `JAMA_CLIENT_SECRET` - OAuth credentials
- `ROOT_PARENT_ITEM_ID` - Parent folder ID for imports
- `JAMA_SSL_CERT` - Path to certificate file (if needed)

See `.env.example` for all available options.

## Usage

### Dry Run (recommended first step)

Preview what would be created/updated without making changes:

```bash
source .venv/bin/activate
python csv2jama.py --mode upsert --dry-run
```

### Execute Import

After reviewing the dry run output:

```bash
source .venv/bin/activate
python csv2jama.py --mode upsert --execute
```

### Import Modes

- `--mode create` - All rows must be new (no Jama ID)
- `--mode update` - All rows must exist (Jama ID required)
- `--mode upsert` - Update existing, create new (default)

### Command Options

```bash
python csv2jama.py --help

Options:
  --mode {create,update,upsert}  Import mode (default: upsert)
  --dry-run                      Simulate without making changes (default)
  --execute                      Execute and make actual API calls
```

## Input File Format

### Required Columns

- `ID` - Source identifier (e.g., documentKey)
- `Item Type` - Folder, Set, Segment, Subsystem, or requirement type
- `Name` - Item name
- `Description` - Item description

### Optional Columns

- `Jama ID` - Existing Jama item ID (for updates)
- `Document Key` - Jama documentKey
- `Global ID` - Jama globalId

### Example

```csv
Jama ID,ID,Item Type,Name,Description
,EGL_CV-FLD-211,Folder,(U) Launch Requirements,
,EGL_CV-SS-001,Subsystem Requirement,Launch Modes,The subsystem shall support...
```

## Troubleshooting

### SSL Certificate Errors

If you see SSL errors like:
```
SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]
```

Solution:
1. Export the certificate using the command above
2. Set `JAMA_SSL_CERT=certs/jama_cert_chain.pem` in `.env`
3. Run dry-run to test

### Empty Certificate File

If `certs/jama_cert_chain.pem` is empty:
```bash
# Try with verbose output
openssl s_client -showcerts -connect your-jama-instance.com:443 </dev/null

# Or try without SNI
openssl s_client -showcerts -connect your-jama-instance.com:443 </dev/null \
  | awk '/BEGIN CERTIFICATE/,/END CERTIFICATE/ { print }' \
  > certs/jama_cert_chain.pem
```

### Connection Refused

If connection to Jama fails:
1. Check `JAMA_BASE_URL` in `.env`
2. Verify network connectivity: `ping your-jama-instance.com`
3. Check VPN connection if required

### OAuth Token Errors

If OAuth token request fails:
1. Verify `JAMA_CLIENT_ID` and `JAMA_CLIENT_SECRET` in `.env`
2. Check that OAuth is enabled in your Jama instance
3. Ensure credentials have appropriate permissions

## Output

After import, review `import_results.csv` for:
- Created items and their new Jama IDs
- Updated items
- Failed rows with error messages
- `resolved_by` column showing how folders were resolved

Copy new Jama IDs back to your source Excel file for future updates.

## Support

For issues or questions, check:
- `.env.example` for configuration options
- Dry-run output for detailed operation preview
- `import_results.csv` for error details
