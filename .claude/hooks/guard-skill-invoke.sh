#!/bin/bash
# Skill 呼叫守衛
# Hook: PreToolUse (Skill)
# 用途：防止 Agent（subagent）自行呼叫 Slash Command，只允許主對話（用戶）觸發
#
# 機制：檢查 hook input 是否包含 agent_id 欄位
#       有 agent_id → subagent 在呼叫 → 阻擋
#       沒有 agent_id → 用戶在呼叫 → 放行
#
# 輸入：stdin (JSON with tool_input, optional agent_id/agent_type)
# 輸出：exit 0 = 允許, exit 2 = 阻擋

set -e

# 從 stdin 讀取 hook input JSON
HOOK_INPUT=$(cat)

# 解析欄位
eval "$(echo "$HOOK_INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'SKILL_NAME={json.dumps(d.get(\"tool_input\", {}).get(\"skill\", \"\"))}')
print(f'AGENT_ID={json.dumps(d.get(\"agent_id\", \"\"))}')
print(f'AGENT_TYPE={json.dumps(d.get(\"agent_type\", \"\"))}')
")"

# 白名單：shared: 開頭的內部 skill 不需要授權
if [[ "$SKILL_NAME" == shared:* ]]; then
    exit 0
fi

# 主對話（無 agent_id）→ 放行
if [ -z "$AGENT_ID" ]; then
    exit 0
fi

# Subagent 呼叫 → 阻擋
echo "" >&2
echo "═══════════════════════════════════════════════════════════════" >&2
echo "🚫 Skill Guard — Slash Command 保護" >&2
echo "═══════════════════════════════════════════════════════════════" >&2
echo "" >&2
echo "❌ Agent (${AGENT_TYPE}) 嘗試自行呼叫 /${SKILL_NAME}，已阻擋。" >&2
echo "" >&2
echo "   Slash Command 只能由用戶直接輸入觸發。" >&2
echo "   Agent 不得自行呼叫 Skill tool 來執行工作流程命令。" >&2
echo "" >&2
echo "💡 如需執行此命令，請用戶在對話中輸入：/${SKILL_NAME}" >&2
echo "═══════════════════════════════════════════════════════════════" >&2
exit 2
