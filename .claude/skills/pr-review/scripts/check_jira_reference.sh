#!/usr/bin/env bash
#
# Extract and validate Jira reference from PR title.
#
# Usage:
#   ./check_jira_reference.sh <pr_number>
#
# Example:
#   ./check_jira_reference.sh 274
#
# Exit codes:
#   0 - Valid Jira reference found
#   1 - No Jira reference found or invalid format

set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: $0 <pr_number>"
    echo "Example: $0 274"
    exit 1
fi

PR_NUMBER="$1"

# Fetch PR title
PR_TITLE=$(gh pr view "$PR_NUMBER" --repo ansible/ansible.platform --json title --jq '.title')

echo "PR #${PR_NUMBER}: ${PR_TITLE}"
echo ""

# Extract Jira reference (AAP-XXXXX format)
JIRA_REF=$(echo "$PR_TITLE" | grep -oE 'AAP-[0-9]+' || true)

if [ -z "$JIRA_REF" ]; then
    echo "❌ No Jira reference found in PR title"
    echo ""
    echo "Required format:"
    echo "  [AAP-12345] Fix description"
    echo "or"
    echo "  AAP-12345: Fix description"
    exit 1
fi

echo "✅ Jira reference found: ${JIRA_REF}"
exit 0
