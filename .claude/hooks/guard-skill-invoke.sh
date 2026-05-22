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
#
# 安全：所有判斷在 python 內完成，不可信值（skill 名稱等）僅經 stdin → json
#       解析，絕不流入 shell eval。python 腳本本身為固定單引號字串，shell 不展開。

HOOK_INPUT=$(cat)

echo "$HOOK_INPUT" | python3 -c '
import sys, json

try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)  # 無法解析則放行（與原行為一致，fail-open）

skill = d.get("tool_input", {}).get("skill", "") or ""
agent_id = d.get("agent_id", "") or ""
agent_type = d.get("agent_type", "") or ""

# 白名單：shared: 開頭的內部 skill 不需要授權
if skill.startswith("shared:"):
    sys.exit(0)

# 主對話（無 agent_id）→ 放行
if not agent_id:
    sys.exit(0)

# Subagent 呼叫 → 阻擋
bar = "═" * 63
msg = f"""
{bar}
\U0001f6ab Skill Guard — Slash Command 保護
{bar}

❌ Agent ({agent_type}) 嘗試自行呼叫 /{skill}，已阻擋。

   Slash Command 只能由用戶直接輸入觸發。
   Agent 不得自行呼叫 Skill tool 來執行工作流程命令。

\U0001f4a1 如需執行此命令，請用戶在對話中輸入：/{skill}
{bar}"""
print(msg, file=sys.stderr)
sys.exit(2)
'
exit $?
