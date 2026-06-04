#!/bin/bash
# Smoke test for Jama Excel Import Tool
# Validates that the tool can load config, parse Excel, and run dry-run successfully

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

cd "$PROJECT_ROOT"

echo "=== Jama Import Tool Smoke Test ==="
echo "Project root: $PROJECT_ROOT"
echo ""

# Check prerequisites
echo "[1/5] Checking prerequisites..."
if [ ! -d ".venv" ]; then
    echo "ERROR: Virtual environment not found at .venv/"
    echo "Run: python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

if [ ! -f ".env" ]; then
    echo "ERROR: .env file not found"
    echo "Run: cp .env.example .env"
    echo "Then edit .env with your Jama configuration"
    exit 1
fi

if [ ! -f "csv2jama.py" ]; then
    echo "ERROR: csv2jama.py not found"
    exit 1
fi

echo "✓ Prerequisites OK"
echo ""

# Compile check
echo "[2/5] Running compile check..."
if ! .venv/bin/python -m py_compile csv2jama.py; then
    echo "ERROR: csv2jama.py has syntax errors"
    exit 1
fi
echo "✓ Compilation OK"
echo ""

# Check .env has required values
echo "[3/5] Validating .env configuration..."
required_vars=("JAMA_BASE_URL" "JAMA_PROJECT_ID" "ROOT_PARENT_ITEM_ID" "INPUT_FILE")
missing_vars=()

for var in "${required_vars[@]}"; do
    if ! grep -q "^${var}=" .env 2>/dev/null || [ -z "$(grep "^${var}=" .env | cut -d= -f2-)" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -gt 0 ]; then
    echo "ERROR: Missing required configuration in .env:"
    for var in "${missing_vars[@]}"; do
        echo "  - $var"
    done
    exit 1
fi
echo "✓ Configuration OK"
echo ""

# Check input file exists
echo "[4/5] Checking input file..."
INPUT_FILE=$(grep "^INPUT_FILE=" .env | cut -d= -f2-)
if [ ! -f "$INPUT_FILE" ]; then
    echo "ERROR: Input file not found: $INPUT_FILE"
    echo "Update INPUT_FILE in .env or add the Excel file to the input/ directory"
    exit 1
fi
echo "✓ Input file exists: $INPUT_FILE"
echo ""

# Run dry-run
echo "[5/5] Running dry-run..."
if ! .venv/bin/python csv2jama.py 2>&1 | tee /tmp/jama_smoke_test.log; then
    echo ""
    echo "ERROR: Dry-run failed"
    exit 1
fi

# Check for success indicators
if ! grep -q "IMPORT SUMMARY" /tmp/jama_smoke_test.log; then
    echo ""
    echo "ERROR: Dry-run did not complete successfully (no summary found)"
    exit 1
fi

# Check output CSV was created
if ! grep -q "Results CSV:" /tmp/jama_smoke_test.log; then
    echo ""
    echo "ERROR: No results CSV mentioned in output"
    exit 1
fi

OUTPUT_CSV=$(grep "Results CSV:" /tmp/jama_smoke_test.log | awk '{print $NF}')
if [ ! -f "$OUTPUT_CSV" ]; then
    echo ""
    echo "ERROR: Output CSV not created: $OUTPUT_CSV"
    exit 1
fi

echo ""
echo "✓ Dry-run completed successfully"
echo "✓ Output CSV created: $OUTPUT_CSV"
echo ""
echo "=== All checks passed ==="
