# SSL Certificate Setup for Jama

## Problem
The Jama server uses an internal General Atomics certificate chain that isn't in Python's trusted certificate store.

## Quick Fix (For Testing Only)

Edit `.env` and set:
```env
JAMA_SSL_VERIFY=false
```

**Warning:** This disables SSL verification. Use only for testing.

## Proper Solution

### Method 1: Export from Windows Certificate Store

1. **From PowerShell (as Administrator)**, run:
```powershell
cd \\wsl.localhost\Ubuntu-24.04-Anthropic\home\wsl-user\projects\Jama

# Export all General Atomics certificates
Get-ChildItem -Path Cert:\LocalMachine\Root, Cert:\LocalMachine\CA -Recurse | 
    Where-Object { $_.Subject -match "General Atomics" -or $_.Subject -match "GAPKI" -or $_.Subject -match "ASGI" } |
    ForEach-Object {
        $name = ($_.Subject -replace ".*CN=([^,]+).*", '$1') -replace "[^a-zA-Z0-9]", "_"
        $path = "certs\$name.cer"
        Write-Host "Exporting: $($_.Subject) -> $path"
        $certBytes = $_.Export([System.Security.Cryptography.X509Certificates.X509ContentType]::Cert)
        [System.IO.File]::WriteAllBytes($path, $certBytes)
    }
```

2. **From WSL**, convert and combine certificates:
```bash
cd /home/wsl-user/projects/Jama/certs

# Convert all .cer files to PEM format
for cert in *.cer; do
    if [ -f "$cert" ]; then
        openssl x509 -inform DER -in "$cert" -out "${cert%.cer}.pem" 2>/dev/null || \
        openssl x509 -inform PEM -in "$cert" -out "${cert%.cer}.pem" 2>/dev/null
    fi
done

# Combine all PEM certificates into one chain file
cat *.pem > jama_cert_chain.pem 2>/dev/null || true

# Verify
echo "Certificates in chain:"
grep -c "BEGIN CERTIFICATE" jama_cert_chain.pem

# Test
openssl x509 -in jama_cert_chain.pem -noout -subject
```

3. **Update .env**:
```env
JAMA_SSL_VERIFY=true
JAMA_SSL_CERT=certs/jama_cert_chain.pem
```

### Method 2: Manual Export via Certificate Manager

1. **Open Certificate Manager**:
   - Press `Win+R`
   - Type `certmgr.msc`
   - Press Enter

2. **Find General Atomics Certificates**:
   - Navigate to `Trusted Root Certification Authorities > Certificates`
   - Look for certificates with "General Atomics" or "GAPKI"
   - Also check `Intermediate Certification Authorities > Certificates`

3. **Export each certificate**:
   - Right-click certificate → All Tasks → Export
   - Choose "Base-64 encoded X.509 (.CER)"
   - Save to `\\wsl.localhost\Ubuntu-24.04-Anthropic\home\wsl-user\projects\Jama\certs\`

4. **Combine in WSL**:
```bash
cd /home/wsl-user/projects/Jama/certs
cat GAPKIRCA01.cer GAPKIIPCA01.cer ASGICA01.cer > jama_cert_chain.pem
```

### Method 3: Request from IT Department

Contact General Atomics IT and request:
- Root CA certificate (GAPKIRCA01)
- Intermediate CA certificates (GAPKIIPCA01, ASGICA01)

File format needed: PEM, CRT, or CER (Base64)

## Verification

After setting up the certificate chain:

```bash
# Check certificate count (should be 3 or 4)
grep -c "BEGIN CERTIFICATE" certs/jama_cert_chain.pem

# View certificate details
openssl x509 -in certs/jama_cert_chain.pem -noout -subject -issuer -dates

# Test the importer
source .venv/bin/activate
python csv2jama.py --dry-run
```

If successful, you should see:
```
[INFO] SSL verify: certs/jama_cert_chain.pem
```

And no SSL errors during OAuth token retrieval.

## Troubleshooting

### "unable to get local issuer certificate"
The certificate chain is incomplete. You need the root CA certificate.

### "certificate verify failed"
The certificate file path is wrong or the certificates are in the wrong format.

### File exists but still fails
Ensure certificates are in PEM format (text file starting with `-----BEGIN CERTIFICATE-----`).

### Quick test without fixing certificates
```env
JAMA_SSL_VERIFY=false
```
Then: `python csv2jama.py --dry-run`
