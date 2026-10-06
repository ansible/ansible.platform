#!/usr/bin/env bash
#
# Check if a new module follows the required seven-file pattern.
#
# Usage:
#   ./check_seven_file_pattern.sh <module_name>
#
# Example:
#   ./check_seven_file_pattern.sh service_cluster
#
# Exit codes:
#   0 - All required files present
#   1 - One or more required files missing

set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: $0 <module_name>"
    echo "Example: $0 service_cluster"
    exit 1
fi

MODULE_NAME="$1"
PLURALIZED="${MODULE_NAME}s"  # Simple pluralization (most cases)

# Define required files (seven-file pattern)
REQUIRED_FILES=(
    "plugins/modules/${MODULE_NAME}.py"
    "plugins/plugin_utils/ansible_models/${MODULE_NAME}.py"
    "plugins/plugin_utils/api/gateway/v1/${MODULE_NAME}.py"
    "plugins/action/${MODULE_NAME}.py"
    "tests/integration/targets/${PLURALIZED}_test/tasks/main.yml"
    "tests/integration/targets/${PLURALIZED}_test/meta/main.yml"
)

# Recommended files
RECOMMENDED_FILES=(
    "extensions/molecule/${MODULE_NAME}_mock/"
    "tests/unit/plugins/plugin_utils/api/gateway/v1/test_${MODULE_NAME}.py"
)

# Track failures
MISSING_COUNT=0
MISSING_RECOMMENDED=0

echo "Checking seven-file pattern for module: ${MODULE_NAME}"
echo ""
echo "=== REQUIRED FILES ==="

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ] || [ -d "$file" ]; then
        echo "✅ $file"
    else
        echo "❌ MISSING REQUIRED: $file"
        ((MISSING_COUNT++))
    fi
done

echo ""
echo "=== RECOMMENDED FILES ==="

for file in "${RECOMMENDED_FILES[@]}"; do
    if [ -f "$file" ] || [ -d "$file" ]; then
        echo "✅ $file"
    else
        echo "⚠️  Missing (recommended): $file"
        ((MISSING_RECOMMENDED++))
    fi
done

echo ""
echo "=== SUMMARY ==="
if [ "$MISSING_COUNT" -eq 0 ]; then
    echo "✅ All required files present"
    if [ "$MISSING_RECOMMENDED" -gt 0 ]; then
        echo "⚠️  ${MISSING_RECOMMENDED} recommended file(s) missing (non-blocking)"
    fi
    exit 0
else
    echo "❌ FAILED: ${MISSING_COUNT} required file(s) missing"
    exit 1
fi
