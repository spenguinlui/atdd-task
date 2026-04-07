#!/usr/bin/env bash
# kanban-adapter.sh - Kanban 操作抽象層
#
# Usage:
#   kanban-adapter.sh create   --project X --title "..." --column requirement ...
#   kanban-adapter.sh move     --project X --title "..." --from A --to B
#   kanban-adapter.sh complete --project X --title "..." --commit hash ... <<< "$metrics"
#   kanban-adapter.sh fail     --project X --title "..."
#   kanban-adapter.sh update   --project X --title "..." --description-file path
#
# Backend: KANBAN_BACKEND=markdown (default) or jira (future)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ATDD_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKEND="${KANBAN_BACKEND:-markdown}"

# ─── Column name mapping ───
column_header() {
  case "$1" in
    requirement)   echo "Requirement" ;;
    specification) echo "Specification" ;;
    testing)       echo "Testing" ;;
    development)   echo "Development" ;;
    review)        echo "Review" ;;
    gate)          echo "Gate" ;;
    completed)     echo "Completed" ;;
    failed)        echo "Failed" ;;
    *) echo "Error: Unknown column '$1'" >&2; exit 1 ;;
  esac
}

# ─── Phases list for step checking ───
PHASES="requirement specification testing development review gate"

# ═══════════════════════════════════════════
# Markdown Backend
# ═══════════════════════════════════════════

markdown_kanban_path() {
  echo "$ATDD_ROOT/tasks/$PROJECT/kanban.md"
}

# Extract a card block by title from kanban file
# Output: card text (from ### title to next ### or ##)
markdown_extract_card() {
  local file="$1" title="$2"
  awk -v title="### $title" '
    $0 == title { found=1 }
    found {
      if (NR > 1 && /^###? / && $0 != title) exit
      print
    }
  ' "$file"
}

# Remove a card block by title from file content (via temp file)
markdown_remove_card() {
  local file="$1" title="$2"
  local tmpfile="${file}.tmp"

  awk -v title="### $title" '
    $0 == title { skip=1; next }
    skip && /^###? / { skip=0 }
    !skip { print }
  ' "$file" > "$tmpfile"

  mv "$tmpfile" "$file"
}

# Insert text after a column header (## Header)
# Inserts after the header line + one blank line
# Uses a temp file for card content to avoid awk multi-line issues
markdown_insert_after_column() {
  local file="$1" column="$2" card_text="$3"
  local header
  header="## $(column_header "$column")"
  local tmpfile="${file}.tmp"
  local cardfile="${file}.card"

  # Write card to temp file
  echo "$card_text" > "$cardfile"

  awk -v header="$header" -v cardfile="$cardfile" '
    {print}
    $0 == header {
      print ""
      while ((getline line < cardfile) > 0) print line
      close(cardfile)
    }
  ' "$file" > "$tmpfile"

  mv "$tmpfile" "$file"
  rm -f "$cardfile"
}

# ─── create ───
markdown_create() {
  local file
  file="$(markdown_kanban_path)"

  if [[ ! -f "$file" ]]; then
    echo "Error: Kanban file not found: $file" >&2
    exit 1
  fi

  # Build card text
  local card
  card="### ${TITLE}

  - tags: [${TAGS}]
  - priority: ${PRIORITY}
  - workload: ${WORKLOAD}
  - defaultExpanded: true
  - steps:
    - [ ] requirement
    - [ ] specification
    - [ ] testing
    - [ ] development
    - [ ] review
    - [ ] gate
    \`\`\`md
    **變更背景**: ${BACKGROUND}
    **影響範圍**: ${SCOPE}
    \`\`\`"

  markdown_insert_after_column "$file" "$COLUMN" "$card"
  echo "✓ Card created: ${TITLE} → $(column_header "$COLUMN")"
}

# ─── move ───
markdown_move() {
  local file
  file="$(markdown_kanban_path)"

  if [[ ! -f "$file" ]]; then
    echo "Error: Kanban file not found: $file" >&2
    exit 1
  fi

  # Extract card
  local card
  card="$(markdown_extract_card "$file" "$TITLE")"

  if [[ -z "$card" ]]; then
    echo "Error: Card not found: ${TITLE}" >&2
    exit 1
  fi

  # Remove old ⬅️ marker
  card="$(echo "$card" | sed 's/ ⬅️$//')"

  # Update steps: check all phases up to (but not including) target
  local target_reached=0
  for phase in $PHASES; do
    if [[ "$phase" == "$TO" ]]; then
      # Mark current phase with ⬅️
      card="$(echo "$card" | sed "s/- \[ \] ${phase}/- [ ] ${phase} ⬅️/")"
      target_reached=1
      break
    fi
    # Check completed phases
    card="$(echo "$card" | sed "s/- \[ \] ${phase}/- [x] ${phase}/")"
  done

  # Remove card from old position
  markdown_remove_card "$file" "$TITLE"

  # Insert into new column
  markdown_insert_after_column "$file" "$TO" "$card"
  echo "✓ Card moved: ${TITLE} ($(column_header "$FROM") → $(column_header "$TO"))"
}

# ─── complete ───
markdown_complete() {
  local file
  file="$(markdown_kanban_path)"

  if [[ ! -f "$file" ]]; then
    echo "Error: Kanban file not found: $file" >&2
    exit 1
  fi

  # Read metrics from --metrics-file or STDIN
  local metrics_text=""
  if [[ -n "$METRICS_FILE" && -f "$METRICS_FILE" ]]; then
    metrics_text="$(cat "$METRICS_FILE")"
  elif [[ ! -t 0 ]]; then
    metrics_text="$(cat)"
  fi

  # Extract card
  local card
  card="$(markdown_extract_card "$file" "$TITLE")"

  if [[ -z "$card" ]]; then
    echo "Error: Card not found: ${TITLE}" >&2
    exit 1
  fi

  # Remove old ⬅️ marker
  card="$(echo "$card" | sed 's/ ⬅️$//')"

  # Check all steps
  for phase in $PHASES; do
    card="$(echo "$card" | sed "s/- \[ \] ${phase}/- [x] ${phase}/")"
  done

  # Add ✅ to gate
  card="$(echo "$card" | sed 's/- \[x\] gate$/- [x] gate ✅/')"

  # Set defaultExpanded to false
  card="$(echo "$card" | sed 's/defaultExpanded: true/defaultExpanded: false/')"

  # Build completion metadata
  local completion_block="    **任務 ID**: ${TASK_ID}
    **類型**: ${TYPE}
    **Domain**: ${DOMAIN}
    **Branch**: ${BRANCH}
    **階段歷程**: ${PHASE_HISTORY}"

  if [[ -n "$metrics_text" ]]; then
    # metrics_text contains two lines: **Agents**: ... and **總計**: ...
    # Add 4-space indent to each line if not already indented
    local indented_metrics
    indented_metrics="$(echo "$metrics_text" | sed 's/^[[:space:]]*/    /')"
    completion_block="${completion_block}
${indented_metrics}"
  fi

  completion_block="${completion_block}
    **commit**: ${COMMIT}"

  # Insert completion block before closing ```
  # Find the last ``` in the card and insert before it
  local blockfile
  blockfile="$(mktemp)"
  echo "$completion_block" > "$blockfile"

  card="$(echo "$card" | awk -v blockfile="$blockfile" '
    { lines[NR] = $0 }
    /^    ```$/ { last_fence = NR }
    END {
      for (i = 1; i <= NR; i++) {
        if (i == last_fence) {
          while ((getline line < blockfile) > 0) print line
          close(blockfile)
        }
        print lines[i]
      }
    }
  ')"
  rm -f "$blockfile"

  # Remove card from old position
  markdown_remove_card "$file" "$TITLE"

  # Insert into Completed column
  markdown_insert_after_column "$file" "completed" "$card"
  echo "✓ Card completed: ${TITLE}"
}

# ─── fail ───
markdown_fail() {
  local file
  file="$(markdown_kanban_path)"

  if [[ ! -f "$file" ]]; then
    echo "Error: Kanban file not found: $file" >&2
    exit 1
  fi

  # Extract card
  local card
  card="$(markdown_extract_card "$file" "$TITLE")"

  if [[ -z "$card" ]]; then
    echo "Error: Card not found: ${TITLE}" >&2
    exit 1
  fi

  # Remove card from old position
  markdown_remove_card "$file" "$TITLE"

  # Insert into Failed column
  markdown_insert_after_column "$file" "failed" "$card"
  echo "✓ Card failed: ${TITLE}"
}

# ═══════════════════════════════════════════
# Jira Backend
# ═══════════════════════════════════════════

JIRA_CONFIG="$ATDD_ROOT/.claude/config/jira.yml"

# ─── Config helpers ───

# Parse a simple top-level key from jira.yml (key: "value" or key: value)
_jira_yml_get() {
  local key="$1"
  sed -n "s/^${key}:[[:space:]]*\"\{0,1\}\([^\"]*\)\"\{0,1\}[[:space:]]*$/\1/p" "$JIRA_CONFIG" | head -1
}

# Parse a nested key under a section (section:\n  nested_key: "value")
_jira_yml_nested() {
  local section="$1" nested_key="$2"
  awk -v section="$section:" -v key="$nested_key" '
    $0 ~ "^"section"$" { in_section=1; next }
    in_section && /^[^ #]/ { exit }
    in_section {
      gsub(/^[[:space:]]+/, "")
      split($0, parts, ":[[:space:]]+")
      gsub(/^"/, "", parts[2]); gsub(/"$/, "", parts[2])
      gsub(/[[:space:]]+$/, "", parts[2])
      if (parts[1] == key) { print parts[2]; exit }
    }
  ' "$JIRA_CONFIG"
}

jira_load_config() {
  if [[ ! -f "$JIRA_CONFIG" ]]; then
    echo "Error: Jira config not found: $JIRA_CONFIG" >&2
    echo "Hint: Copy from jira.yml template and fill in your credentials." >&2
    exit 1
  fi

  JIRA_BASE_URL="$(_jira_yml_get "base_url")"
  JIRA_EMAIL="$(_jira_yml_get "email")"
  JIRA_API_TOKEN="$(_jira_yml_get "api_token")"

  if [[ -z "$JIRA_BASE_URL" || -z "$JIRA_EMAIL" || -z "$JIRA_API_TOKEN" ]]; then
    echo "Error: Jira config incomplete. Ensure base_url, email, and api_token are set." >&2
    exit 1
  fi

  # Validate not placeholder values
  if [[ "$JIRA_BASE_URL" == *"YOUR_TEAM"* || "$JIRA_API_TOKEN" == "YOUR_API_TOKEN" ]]; then
    echo "Error: Jira config contains placeholder values. Please fill in real credentials." >&2
    exit 1
  fi

  JIRA_PROJECT_KEY="$(_jira_yml_nested "projects" "$PROJECT")"
  if [[ -z "$JIRA_PROJECT_KEY" ]]; then
    echo "Error: No Jira project key configured for ATDD project '$PROJECT'" >&2
    exit 1
  fi
}

# ─── API helpers ───

# Make a Jira REST API call
# Usage: jira_api METHOD endpoint [json_body]
jira_api() {
  local method="$1" endpoint="$2" body="${3:-}"
  local url="${JIRA_BASE_URL}/rest/api/3${endpoint}"
  local auth
  auth="$(printf '%s:%s' "$JIRA_EMAIL" "$JIRA_API_TOKEN" | base64)"

  local curl_args=(
    -s -w "\n%{http_code}"
    -X "$method"
    -H "Authorization: Basic $auth"
    -H "Content-Type: application/json"
    -H "Accept: application/json"
  )

  if [[ -n "$body" ]]; then
    curl_args+=(-d "$body")
  fi

  local response http_code body_text
  response="$(curl "${curl_args[@]}" "$url")"
  http_code="$(echo "$response" | tail -1)"
  body_text="$(echo "$response" | sed '$d')"

  if [[ "$http_code" -ge 400 ]]; then
    echo "Error: Jira API returned HTTP $http_code" >&2
    echo "Endpoint: $method $endpoint" >&2
    echo "Response: $body_text" >&2
    return 1
  fi

  echo "$body_text"
}

# Search for a Jira issue by title in the configured project
# Returns the issue key (e.g. CORE-123)
jira_find_issue() {
  local title="$1"

  local payload
  payload="$(python3 -c "
import json, sys
title = sys.argv[1]
project_key = sys.argv[2]
jql = f'project = {project_key} AND summary ~ \"{title}\" ORDER BY created DESC'
print(json.dumps({'jql': jql, 'maxResults': 1, 'fields': ['key', 'summary']}, ensure_ascii=False))
" "$title" "$JIRA_PROJECT_KEY")"

  local result
  result="$(jira_api POST "/search/jql" "$payload")" || return 1

  local issue_key
  issue_key="$(echo "$result" | python3 -c "
import sys, json
data = json.load(sys.stdin)
issues = data.get('issues', [])
if issues:
    print(issues[0]['key'])
" 2>/dev/null)"

  if [[ -z "$issue_key" ]]; then
    echo "Error: Issue not found in Jira: '$title' (project: $JIRA_PROJECT_KEY)" >&2
    return 1
  fi

  echo "$issue_key"
}

# Transition an issue to a target Jira status
# Usage: jira_transition_to ISSUE_KEY TARGET_STATUS
jira_transition_to() {
  local issue_key="$1" target_status="$2"

  # Get available transitions
  local transitions
  transitions="$(jira_api GET "/issue/${issue_key}/transitions")" || return 1

  # Find transition ID for target status (case-insensitive match)
  local target_upper
  target_upper="$(echo "$target_status" | tr '[:lower:]' '[:upper:]')"

  local transition_id
  transition_id="$(echo "$transitions" | python3 -c "
import sys, json
data = json.load(sys.stdin)
target = '${target_upper}'.upper()
for t in data.get('transitions', []):
    if t.get('to', {}).get('name', '').upper() == target:
        print(t['id'])
        break
" 2>/dev/null)"

  if [[ -z "$transition_id" ]]; then
    # Target status might already be current — not an error for same-status moves
    echo "Info: No transition available to '$target_status' for $issue_key (may already be in that status)" >&2
    return 0
  fi

  local payload
  payload="$(printf '{"transition":{"id":"%s"}}' "$transition_id")"
  jira_api POST "/issue/${issue_key}/transitions" "$payload" > /dev/null
}

# Add a comment to a Jira issue (Atlassian Document Format)
jira_add_comment() {
  local issue_key="$1" comment_text="$2"
  local payload
  payload="$(printf '{"body":{"version":1,"type":"doc","content":[{"type":"paragraph","content":[{"type":"text","text":"%s"}]}]}}' \
    "$(echo "$comment_text" | sed 's/\\/\\\\/g; s/"/\\"/g; s/$/\\n/g' | tr -d '\n' | sed 's/\\n$//')")"
  jira_api POST "/issue/${issue_key}/comment" "$payload" > /dev/null
}

# ─── create ───
jira_create() {
  jira_load_config

  local issue_type
  issue_type="$(_jira_yml_nested "issue_types" "${TYPE:-Feature}")"
  if [[ -z "$issue_type" ]]; then
    issue_type="Task"
  fi

  # Map priority
  local jira_priority="Medium"
  case "${PRIORITY:-medium}" in
    high)   jira_priority="High" ;;
    medium) jira_priority="Medium" ;;
    low)    jira_priority="Low" ;;
  esac

  # Build description
  local description="Background: ${BACKGROUND}\\nScope: ${SCOPE}\\nWorkload: ${WORKLOAD}"

  # Build labels from tags (comma-separated → array)
  local labels_json="[]"
  if [[ -n "$TAGS" ]]; then
    labels_json="$(echo "$TAGS" | tr ',' '\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | \
      awk 'NF {printf "%s\"%s\"", (NR>1?",":""), $0} END {print ""}' | \
      sed 's/^/[/;s/$/]/')"
  fi

  local payload
  payload="$(cat <<EOJSON
{
  "fields": {
    "project": {"key": "${JIRA_PROJECT_KEY}"},
    "summary": "${TITLE}",
    "issuetype": {"name": "${issue_type}"},
    "description": {
      "version": 1,
      "type": "doc",
      "content": [
        {
          "type": "paragraph",
          "content": [
            {"type": "text", "text": "Background: ${BACKGROUND}"},
            {"type": "hardBreak"},
            {"type": "text", "text": "Scope: ${SCOPE}"},
            {"type": "hardBreak"},
            {"type": "text", "text": "Workload: ${WORKLOAD}"}
          ]
        }
      ]
    },
    "priority": {"name": "${jira_priority}"},
    "assignee": {"accountId": "712020:4ecde4a6-026e-49de-a1d0-46f5c3fcbdaa"},
    "labels": ${labels_json},
    "customfield_10119": {"id": "10152"},
    "customfield_10082": {"id": "10069"}
  }
}
EOJSON
)"

  local result
  result="$(jira_api POST "/issue" "$payload")" || exit 1

  local issue_key
  issue_key="$(echo "$result" | sed -n 's/.*"key":"\([^"]*\)".*/\1/p' | head -1)"

  if [[ -z "$issue_key" ]]; then
    echo "Error: Failed to parse issue key from Jira response" >&2
    exit 1
  fi

  # Transition to target status if not TO DO
  local target_status
  target_status="$(_jira_yml_nested "status_mapping" "$COLUMN")"
  if [[ -n "$target_status" && "$target_status" != "TO DO" ]]; then
    jira_transition_to "$issue_key" "$target_status"
  fi

  echo "✓ Jira issue created: ${issue_key} — ${TITLE}"
}

# ─── move ───
jira_move() {
  jira_load_config

  local issue_key
  issue_key="$(jira_find_issue "$TITLE")" || exit 1

  # Get target Jira status
  local from_status to_status
  from_status="$(_jira_yml_nested "status_mapping" "$FROM")"
  to_status="$(_jira_yml_nested "status_mapping" "$TO")"

  if [[ -z "$to_status" ]]; then
    echo "Error: No Jira status mapping for column '$TO'" >&2
    exit 1
  fi

  # Skip transition if source and target map to the same Jira status
  if [[ "$from_status" == "$to_status" ]]; then
    echo "✓ Jira: ${issue_key} stays in '${to_status}' ($(column_header "$FROM") → $(column_header "$TO"))"
    return 0
  fi

  jira_transition_to "$issue_key" "$to_status" || exit 1
  echo "✓ Jira issue moved: ${issue_key} ($(column_header "$FROM") → $(column_header "$TO"))"
}

# ─── complete ───
jira_complete() {
  jira_load_config

  local issue_key
  issue_key="$(jira_find_issue "$TITLE")" || exit 1

  # Read metrics from --metrics-file or STDIN
  local metrics_text=""
  if [[ -n "$METRICS_FILE" && -f "$METRICS_FILE" ]]; then
    metrics_text="$(cat "$METRICS_FILE")"
  elif [[ ! -t 0 ]]; then
    metrics_text="$(cat)"
  fi

  # Build completion comment
  local comment="Task completed.
Task ID: ${TASK_ID}
Type: ${TYPE}
Domain: ${DOMAIN}
Branch: ${BRANCH}
Phase history: ${PHASE_HISTORY}
Commit: ${COMMIT}"

  if [[ -n "$metrics_text" ]]; then
    comment="${comment}
Metrics:
${metrics_text}"
  fi

  # Add comment first
  jira_add_comment "$issue_key" "$comment"

  # Transition to DONE
  local done_status
  done_status="$(_jira_yml_nested "status_mapping" "completed")"
  if [[ -n "$done_status" ]]; then
    jira_transition_to "$issue_key" "$done_status"
  fi

  echo "✓ Jira issue completed: ${issue_key} — ${TITLE}"
}

# ─── fail ───
jira_fail() {
  jira_load_config

  local issue_key
  issue_key="$(jira_find_issue "$TITLE")" || exit 1

  # Add failure comment
  jira_add_comment "$issue_key" "Task failed. Moved to Failed status."

  # Transition to DONE (failed maps to DONE in Jira)
  local done_status
  done_status="$(_jira_yml_nested "status_mapping" "failed")"
  if [[ -n "$done_status" ]]; then
    jira_transition_to "$issue_key" "$done_status"
  fi

  echo "✓ Jira issue failed: ${issue_key} — ${TITLE}"
}

# ─── update (description) ───

# Convert markdown-like text to Jira ADF JSON
# Supports: ## headings, - [ ] task items, plain paragraphs
text_to_adf() {
  local input_file="$1"
  python3 -c "
import sys, json, uuid

lines = open('${input_file}', 'r').read().rstrip('\n').split('\n')
content = []
paragraph_texts = []

def flush_paragraph():
    global paragraph_texts
    if not paragraph_texts:
        return
    inline = []
    for i, t in enumerate(paragraph_texts):
        if i > 0:
            inline.append({'type': 'hardBreak'})
        inline.append({'type': 'text', 'text': t})
    content.append({'type': 'paragraph', 'content': inline})
    paragraph_texts = []

def make_task_item(text):
    return {
        'type': 'taskItem',
        'attrs': {'localId': str(uuid.uuid4())[:8], 'state': 'TODO'},
        'content': [{'type': 'text', 'text': text}]
    }

i = 0
task_items = []

def flush_task_list():
    global task_items
    if not task_items:
        return
    content.append({
        'type': 'taskList',
        'attrs': {'localId': str(uuid.uuid4())[:8]},
        'content': task_items
    })
    task_items = []

while i < len(lines):
    line = lines[i]

    if line.startswith('## '):
        flush_paragraph()
        flush_task_list()
        heading_text = line[3:].strip()
        content.append({
            'type': 'heading',
            'attrs': {'level': 2},
            'content': [{'type': 'text', 'text': heading_text}]
        })
    elif line.startswith('- [ ] '):
        flush_paragraph()
        task_text = line[6:].strip()
        task_items.append(make_task_item(task_text))
    elif line.strip() == '':
        flush_paragraph()
        flush_task_list()
    else:
        flush_task_list()
        paragraph_texts.append(line)

    i += 1

flush_paragraph()
flush_task_list()

if not content:
    content.append({'type': 'paragraph', 'content': [{'type': 'text', 'text': ' '}]})

doc = {'version': 1, 'type': 'doc', 'content': content}
print(json.dumps(doc, ensure_ascii=False))
"
}

jira_update() {
  jira_load_config

  local issue_key
  issue_key="$(jira_find_issue "$TITLE")" || exit 1

  if [[ -z "$DESCRIPTION_FILE" || ! -f "$DESCRIPTION_FILE" ]]; then
    echo "Error: --description-file is required and must exist" >&2
    exit 1
  fi

  # Convert description file to ADF
  local adf_body
  adf_body="$(text_to_adf "$DESCRIPTION_FILE")" || exit 1

  if [[ "$AS_COMMENT" == "true" ]]; then
    # 既有 Jira 票：寫入 Comment，不覆蓋 PM 原本的 Description
    local payload
    payload="$(printf '{"body":%s}' "$adf_body")"
    jira_api POST "/issue/${issue_key}/comment" "$payload" > /dev/null
    echo "✓ Jira issue commented: ${issue_key} — description added as comment"
  else
    # 新建 Jira 票：直接更新 Description
    local payload
    payload="$(printf '{"fields":{"description":%s}}' "$adf_body")"
    jira_api PUT "/issue/${issue_key}" "$payload" > /dev/null
    echo "✓ Jira issue updated: ${issue_key} — description updated"
  fi
}

markdown_update() {
  # Markdown backend: description is local, no-op
  echo "✓ Description update skipped (markdown backend — info is local)"
}

# ═══════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════

usage() {
  cat <<'EOF'
Usage: kanban-adapter.sh <command> [options]

Commands:
  create    Create a new card
  move      Move a card between columns
  complete  Move card to Completed with metrics
  fail      Move card to Failed
  update    Update issue description

Options (varies by command):
  --project       Project name (required)
  --title         Card title (required)
  --column        Target column (create)
  --tags          Tags, e.g. "ErpPeriod, feature" (create)
  --priority      Priority: high/medium/low (create)
  --workload      Workload: Easy/Normal/Hard/Extreme (create)
  --background    Background description (create)
  --scope         Impact scope (create)
  --task-id       Task ID prefix (create/complete)
  --from          Source column (move)
  --to            Target column (move)
  --commit        Commit hash (complete)
  --phase-history Phase history string (complete)
  --type          Task type: Feature/Fix/Refactor (complete)
  --domain        Domain name (complete)
  --branch        Git branch (complete)
  --description-file  Path to description file (update)
  --as-comment        Write as comment instead of description (update, for linked Jira tickets)

Metrics for 'complete' are read from STDIN (output of session-stats.rb --format kanban).
EOF
  exit 1
}

# Parse arguments
PROJECT="" TITLE="" COLUMN="" TAGS="" PRIORITY="" WORKLOAD=""
BACKGROUND="" SCOPE="" TASK_ID="" FROM="" TO=""
COMMIT="" PHASE_HISTORY="" TYPE="" DOMAIN="" BRANCH="" METRICS_FILE=""
DESCRIPTION_FILE="" AS_COMMENT="false"

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --project)       PROJECT="$2"; shift 2 ;;
      --title)         TITLE="$2"; shift 2 ;;
      --column)        COLUMN="$2"; shift 2 ;;
      --tags)          TAGS="$2"; shift 2 ;;
      --priority)      PRIORITY="$2"; shift 2 ;;
      --workload)      WORKLOAD="$2"; shift 2 ;;
      --background)    BACKGROUND="$2"; shift 2 ;;
      --scope)         SCOPE="$2"; shift 2 ;;
      --task-id)       TASK_ID="$2"; shift 2 ;;
      --from)          FROM="$2"; shift 2 ;;
      --to)            TO="$2"; shift 2 ;;
      --commit)        COMMIT="$2"; shift 2 ;;
      --phase-history) PHASE_HISTORY="$2"; shift 2 ;;
      --type)          TYPE="$2"; shift 2 ;;
      --domain)        DOMAIN="$2"; shift 2 ;;
      --branch)        BRANCH="$2"; shift 2 ;;
      --metrics-file)  METRICS_FILE="$2"; shift 2 ;;
      --description-file) DESCRIPTION_FILE="$2"; shift 2 ;;
      --as-comment) AS_COMMENT="true"; shift ;;
      *) echo "Error: Unknown option '$1'" >&2; exit 1 ;;
    esac
  done
}

validate_create() {
  local missing=""
  [[ -z "$PROJECT" ]] && missing="$missing --project"
  [[ -z "$TITLE" ]]   && missing="$missing --title"
  [[ -z "$COLUMN" ]]  && missing="$missing --column"
  [[ -z "$TAGS" ]]    && missing="$missing --tags"
  [[ -z "$PRIORITY" ]] && missing="$missing --priority"
  [[ -z "$WORKLOAD" ]] && missing="$missing --workload"
  [[ -z "$BACKGROUND" ]] && missing="$missing --background"
  [[ -z "$SCOPE" ]]   && missing="$missing --scope"
  if [[ -n "$missing" ]]; then
    echo "Error: Missing required options:$missing" >&2
    exit 1
  fi
}

validate_move() {
  local missing=""
  [[ -z "$PROJECT" ]] && missing="$missing --project"
  [[ -z "$TITLE" ]]   && missing="$missing --title"
  [[ -z "$FROM" ]]    && missing="$missing --from"
  [[ -z "$TO" ]]      && missing="$missing --to"
  if [[ -n "$missing" ]]; then
    echo "Error: Missing required options:$missing" >&2
    exit 1
  fi
}

validate_complete() {
  local missing=""
  [[ -z "$PROJECT" ]]       && missing="$missing --project"
  [[ -z "$TITLE" ]]         && missing="$missing --title"
  [[ -z "$COMMIT" ]]        && missing="$missing --commit"
  [[ -z "$PHASE_HISTORY" ]] && missing="$missing --phase-history"
  [[ -z "$TASK_ID" ]]       && missing="$missing --task-id"
  [[ -z "$TYPE" ]]          && missing="$missing --type"
  [[ -z "$DOMAIN" ]]        && missing="$missing --domain"
  [[ -z "$BRANCH" ]]        && missing="$missing --branch"
  if [[ -n "$missing" ]]; then
    echo "Error: Missing required options:$missing" >&2
    exit 1
  fi
}

validate_fail() {
  local missing=""
  [[ -z "$PROJECT" ]] && missing="$missing --project"
  [[ -z "$TITLE" ]]   && missing="$missing --title"
  if [[ -n "$missing" ]]; then
    echo "Error: Missing required options:$missing" >&2
    exit 1
  fi
}

validate_update() {
  local missing=""
  [[ -z "$PROJECT" ]] && missing="$missing --project"
  [[ -z "$TITLE" ]]   && missing="$missing --title"
  if [[ -n "$missing" ]]; then
    echo "Error: Missing required options:$missing" >&2
    exit 1
  fi
}

# ─── Main ───
if [[ $# -lt 1 ]]; then
  usage
fi

COMMAND="$1"; shift
parse_args "$@"

case "$COMMAND" in
  create)
    validate_create
    "${BACKEND}_create"
    ;;
  move)
    validate_move
    "${BACKEND}_move"
    ;;
  complete)
    validate_complete
    "${BACKEND}_complete"
    ;;
  fail)
    validate_fail
    "${BACKEND}_fail"
    ;;
  update)
    validate_update
    "${BACKEND}_update"
    ;;
  *)
    echo "Error: Unknown command '$COMMAND'" >&2
    usage
    ;;
esac
