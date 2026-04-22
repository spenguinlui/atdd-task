#!/bin/bash
# Review 持久化驗證
# Hook: SubagentStop
# 用途：risk-reviewer / style-reviewer 結束後，驗證 reviewFindings 已寫入 MCP（local task JSON）
#       未持久化 → 阻擋並指示 agent 重跑 Phase 6
#
# 防線：避免 reviewer 只在對話窗輸出 findings 但沒寫 DB，導致 /clear 後任務無法銜接
#
# 輸入：stdin JSON（SubagentStop payload）
# 輸出：exit 0 = 通過, exit 2 = 阻擋

set -e

ATDD_HUB_DIR="${CLAUDE_PROJECT_DIR:?CLAUDE_PROJECT_DIR not set}"
TASKS_DIR="${ATDD_HUB_DIR}/tasks"

HOOK_INPUT=$(cat)

AGENT_TYPE=$(echo "$HOOK_INPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('agent_type', data.get('tool_input', {}).get('subagent_type', '')))
" 2>/dev/null || echo "")

# 只對兩個 reviewer 做驗證
if [ "$AGENT_TYPE" != "risk-reviewer" ] && [ "$AGENT_TYPE" != "style-reviewer" ]; then
    exit 0
fi

# 找到當前活躍任務（最新修改）
ACTIVE_TASKS=$(find "$TASKS_DIR"/*/active -name "*.json" 2>/dev/null || echo "")
if [ -z "$ACTIVE_TASKS" ]; then
    exit 0
fi

TASK_COUNT=$(echo "$ACTIVE_TASKS" | wc -l | tr -d ' ')
if [ "$TASK_COUNT" -gt 1 ]; then
    ACTIVE_TASKS=$(ls -t $ACTIVE_TASKS 2>/dev/null | head -1)
fi

TASK_JSON="$ACTIVE_TASKS"
if [ ! -f "$TASK_JSON" ]; then
    exit 0
fi

python3 << PYEOF
import json, sys

task_path = "$TASK_JSON"
agent = "$AGENT_TYPE"

with open(task_path) as f:
    task = json.load(f)

status = task.get('status', '')
if status != 'review':
    sys.exit(0)

context = task.get('context') or task.get('metadata', {}).get('context', {}) or {}
findings = context.get('reviewFindings')

sub_key = 'riskReview' if agent == 'risk-reviewer' else 'styleReview'
items_key = 'findings' if agent == 'risk-reviewer' else 'issues'

def fail(msg):
    print("", file=sys.stderr)
    print("═══════════════════════════════════════════════════════════════", file=sys.stderr)
    print("🚫 Review 持久化驗證失敗", file=sys.stderr)
    print("═══════════════════════════════════════════════════════════════", file=sys.stderr)
    print(f"Agent：{agent}", file=sys.stderr)
    print(f"任務：{task.get('id', '')[:8]}... — {task.get('description', '')[:40]}", file=sys.stderr)
    print("", file=sys.stderr)
    print(f"❌ {msg}", file=sys.stderr)
    print("", file=sys.stderr)
    print(f"修復：{agent} 必須在對話輸出前呼叫 mcp__atdd__atdd_task_update", file=sys.stderr)
    print(f"      寫入 metadata.context.reviewFindings.{sub_key}.{items_key}", file=sys.stderr)
    print(f"      （即使零問題也必須寫入空陣列代表「已審查」）", file=sys.stderr)
    print("", file=sys.stderr)
    print(f"參考：.claude/agents/{agent}.md Phase 6", file=sys.stderr)
    print("═══════════════════════════════════════════════════════════════", file=sys.stderr)
    sys.exit(2)

if findings is None:
    fail("metadata.context.reviewFindings 不存在 — reviewer 未持久化 findings")

if not isinstance(findings, dict):
    fail(f"reviewFindings 格式錯誤（應為 object，實際 {type(findings).__name__}）")

sub = findings.get(sub_key)
if sub is None:
    fail(f"reviewFindings.{sub_key} 不存在 — {agent} 沒有寫入自己的區塊")

if not isinstance(sub, dict):
    fail(f"reviewFindings.{sub_key} 格式錯誤（應為 object）")

if items_key not in sub:
    fail(f"reviewFindings.{sub_key}.{items_key} 不存在 — 即使零問題也必須寫入空陣列")

if not isinstance(sub[items_key], list):
    fail(f"reviewFindings.{sub_key}.{items_key} 應為 array")

# 通過
print(f"✅ {agent} 持久化驗證通過（{len(sub[items_key])} 項 {items_key}）", file=sys.stderr)
PYEOF

exit 0
