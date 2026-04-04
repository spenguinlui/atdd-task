#!/bin/bash
# Domain Name Normalization Script
# 修正 atdd-hub 中 task JSON 的 domain 命名不一致問題
#
# Usage: ./domain-normalize.sh [--dry-run] <atdd-hub-path>
#   --dry-run: 只顯示要修改的內容，不實際寫入
#
# Normalization Rules:
#   ErpPeriod → Tools::ErpPeriod
#   DigiwinErp → Tools::DigiwinErp
#   Tool::Receipt → Receipt
#   ProjectManagement → Project::Management
#   ProjectManagement::Project → Project::Management
#   infrastructure → InfrastructureAutomation
#   Tools::ErpPeriod, PaymentTransfer → Tools::ErpPeriod (relatedDomains 加 PaymentTransfer)

set -euo pipefail

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
  shift
fi

HUB_PATH="${1:-$HOME/atdd-hub}"

if [[ ! -d "$HUB_PATH/tasks" ]]; then
  echo "Error: $HUB_PATH/tasks not found"
  exit 1
fi

# Counters
TOTAL=0
MODIFIED=0
SKIPPED=0

# Normalization mapping (simple renames)
declare -A DOMAIN_MAP
DOMAIN_MAP["ErpPeriod"]="Tools::ErpPeriod"
DOMAIN_MAP["DigiwinErp"]="Tools::DigiwinErp"
DOMAIN_MAP["Tool::Receipt"]="Receipt"
DOMAIN_MAP["ProjectManagement"]="Project::Management"
DOMAIN_MAP["ProjectManagement::Project"]="Project::Management"
DOMAIN_MAP["infrastructure"]="InfrastructureAutomation"

echo "=== Domain Name Normalization ==="
echo "Hub path: $HUB_PATH"
echo "Dry run: $DRY_RUN"
echo ""

# Process all task JSON files
find "$HUB_PATH/tasks" -name "*.json" -type f | while read -r file; do
  TOTAL=$((TOTAL + 1))

  # Extract current domain
  domain=$(python3 -c "
import json, sys
try:
    d = json.load(open('$file'))
    print(d.get('domain', ''))
except:
    print('')
" 2>/dev/null)

  # Check if domain needs normalization
  needs_fix=false
  new_domain="$domain"

  # Case 1: Simple rename
  if [[ -n "${DOMAIN_MAP[$domain]+_}" ]]; then
    new_domain="${DOMAIN_MAP[$domain]}"
    needs_fix=true
  fi

  # Case 2: Comma-separated multi-domain (e.g., "Tools::ErpPeriod, PaymentTransfer")
  if echo "$domain" | grep -q ","; then
    # Take the first domain as primary, add rest to relatedDomains
    primary=$(echo "$domain" | cut -d',' -f1 | xargs)
    secondary=$(echo "$domain" | cut -d',' -f2- | xargs)

    # Normalize the primary domain too if needed
    if [[ -n "${DOMAIN_MAP[$primary]+_}" ]]; then
      primary="${DOMAIN_MAP[$primary]}"
    fi

    new_domain="$primary"
    needs_fix=true

    if [[ "$DRY_RUN" == "true" ]]; then
      echo "[MULTI-DOMAIN] $file"
      echo "  domain: '$domain' → '$new_domain'"
      echo "  will add '$secondary' to relatedDomains"
    else
      python3 -c "
import json
with open('$file', 'r') as f:
    d = json.load(f)
d['domain'] = '$new_domain'
# Add secondary domains to relatedDomains if not already there
related = d.get('context', {}).get('relatedDomains', [])
for s in '$secondary'.split(','):
    s = s.strip()
    if s and s not in related:
        related.append(s)
if 'context' not in d:
    d['context'] = {}
d['context']['relatedDomains'] = related
with open('$file', 'w') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
" 2>/dev/null
      echo "[FIXED-MULTI] $file: '$domain' → '$new_domain' (+relatedDomains)"
    fi
    MODIFIED=$((MODIFIED + 1))
    continue
  fi

  # Apply simple rename
  if [[ "$needs_fix" == "true" ]]; then
    if [[ "$DRY_RUN" == "true" ]]; then
      echo "[RENAME] $file"
      echo "  domain: '$domain' → '$new_domain'"
    else
      python3 -c "
import json
with open('$file', 'r') as f:
    d = json.load(f)
d['domain'] = '$new_domain'
with open('$file', 'w') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
" 2>/dev/null
      echo "[FIXED] $file: '$domain' → '$new_domain'"
    fi
    MODIFIED=$((MODIFIED + 1))
  fi
done

echo ""
echo "=== Summary ==="
echo "Modified: $MODIFIED"
echo "Dry run: $DRY_RUN"
