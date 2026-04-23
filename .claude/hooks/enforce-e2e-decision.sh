#!/bin/bash
# E2E 決策強制門檻
# Hook: PreToolUse (mcp__atdd__atdd_task_update)
# 用途：所有任務在 requirement → specification/testing 轉移前，必須有明確的 E2E 決策
#
# 規則：
#   - 預設：e2e.required = true，tool = "chrome-mcp"
#   - 跳過：必須有 metadata.acceptance.e2eDecision.decision = "skipped" 且附 reason
#   - 轉移出 requirement 階段時（status → specifying/testing），若 e2eDecision 缺失則阻擋
#
# 設計意圖：
#   強制 /continue 走 E2E 詢問流程；避免任何 agent 繞過預設 E2E。
#
# 輸入：stdin (hook JSON with tool_name, tool_input)
# 輸出：exit 0 = 允許, exit 2 = 阻擋

set -e

HOOK_INPUT_FILE=$(mktemp)
trap "rm -f $HOOK_INPUT_FILE" EXIT
cat > "$HOOK_INPUT_FILE"

python3 - "$HOOK_INPUT_FILE" << 'PYEOF'
import json, sys

with open(sys.argv[1]) as f:
    hook_input = json.load(f)

tool_name = hook_input.get('tool_name', '')
if tool_name != 'mcp__atdd__atdd_task_update':
    sys.exit(0)

tool_input = hook_input.get('tool_input', {}) or {}
new_status = tool_input.get('status')

# 只攔截轉移出 requirement 的動作
TRIGGER_STATUSES = {'specifying', 'specification', 'testing', 'pending_test'}
if new_status not in TRIGGER_STATUSES:
    sys.exit(0)

metadata = tool_input.get('metadata') or {}
# metadata 可能是 dict 或 JSON 字串（視 MCP client 而定）
if isinstance(metadata, str):
    try:
        metadata = json.loads(metadata)
    except Exception:
        metadata = {}

acceptance = metadata.get('acceptance', {}) or {}
decision = acceptance.get('e2eDecision', {}) or {}

# 支援兩種格式：
#   1. e2eDecision = "required" | "skipped"
#   2. e2eDecision = { "decision": "...", "reason": "...", "tool": "chrome-mcp" }
if isinstance(decision, str):
    decision_value = decision
    reason = acceptance.get('e2eReason', '')
else:
    decision_value = decision.get('decision')
    reason = decision.get('reason', '')

errors = []

if decision_value not in ('required', 'skipped'):
    errors.append(
        'metadata.acceptance.e2eDecision 未設定或不合法。\n'
        '   合法值：\n'
        '     - {"decision": "required", "tool": "chrome-mcp"}  ← 預設\n'
        '     - {"decision": "skipped",  "reason": "<為何可跳過>"}\n'
        '\n'
        '   請由 /continue 於 requirement → specification 轉移時，\n'
        '   以 AskUserQuestion 向用戶確認後再寫入。'
    )
elif decision_value == 'skipped' and not str(reason).strip():
    errors.append(
        'e2eDecision = "skipped" 但缺少 reason。\n'
        '   跳過 E2E 必須附明確理由（例如：純後端重構、無 UI 變更、DB migration only）。'
    )

if not errors:
    sys.exit(0)

print("", file=sys.stderr)
print("═══════════════════════════════════════════════════════════════", file=sys.stderr)
print("🚫 E2E Decision Required — 缺少 E2E 決策，阻擋階段轉移", file=sys.stderr)
print("═══════════════════════════════════════════════════════════════", file=sys.stderr)
print("", file=sys.stderr)
print(f"任務 ID：{tool_input.get('task_id', '?')}", file=sys.stderr)
print(f"目標 status：{new_status}", file=sys.stderr)
print("", file=sys.stderr)
print("❌ 阻擋項目：", file=sys.stderr)
for e in errors:
    print(f"   • {e}", file=sys.stderr)
print("", file=sys.stderr)
print("💡 正確流程：/continue 在 requirement → spec 轉移前必須", file=sys.stderr)
print("   用 AskUserQuestion 詢問用戶「是否需要 E2E 測試？」", file=sys.stderr)
print("   預設採用 chrome-mcp；跳過需填理由。", file=sys.stderr)
print("═══════════════════════════════════════════════════════════════", file=sys.stderr)
sys.exit(2)
PYEOF
