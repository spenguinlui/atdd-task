#!/bin/bash
# Skill 呼叫守衛
# Hook: PreToolUse (Skill)
# 用途：防止 Agent 自行呼叫 Slash Command，只允許用戶明確輸入的命令
#
# 機制：workflow-router.sh（UserPromptSubmit）偵測到 /xxx 時寫授權 flag
#       本 hook 檢查 flag 是否存在且匹配 → 放行或阻擋
#
# 輸入：stdin (JSON with tool_input)
# 輸出：exit 0 = 允許, exit 2 = 阻擋

set -e

ATDD_HUB_DIR="${CLAUDE_PROJECT_DIR:?CLAUDE_PROJECT_DIR not set}"
AUTH_DIR="${ATDD_HUB_DIR}/.claude/.skill-authorized"

# 從 stdin 讀取 hook input JSON
HOOK_INPUT_FILE=$(mktemp)
trap "rm -f $HOOK_INPUT_FILE" EXIT
cat > "$HOOK_INPUT_FILE"

# 解析 skill name
SKILL_NAME=$(python3 -c "
import sys, json
d = json.load(open('$HOOK_INPUT_FILE'))
print(d.get('tool_input', {}).get('skill', ''))
" 2>/dev/null || echo "")

# 空的 skill name → 放行（不該發生，但不阻擋）
if [ -z "$SKILL_NAME" ]; then
    exit 0
fi

# 白名單：shared: 開頭的內部 skill 不需要授權
if [[ "$SKILL_NAME" == shared:* ]]; then
    exit 0
fi

# 檢查授權 flag
AUTH_FILE="${AUTH_DIR}/${SKILL_NAME}"

if [ -f "$AUTH_FILE" ]; then
    # 驗證時效（60 秒內有效）
    AUTH_TS=$(head -1 "$AUTH_FILE" | cut -d'|' -f1)
    NOW=$(date +%s)
    ELAPSED=$(( NOW - AUTH_TS ))

    if [ "$ELAPSED" -lt 60 ]; then
        # 授權有效 → 消耗 flag（一次性）並放行
        rm -f "$AUTH_FILE"
        exit 0
    fi
fi

# 未授權 → 阻擋
echo "" >&2
echo "═══════════════════════════════════════════════════════════════" >&2
echo "🚫 Skill Guard — Slash Command 保護" >&2
echo "═══════════════════════════════════════════════════════════════" >&2
echo "" >&2
echo "❌ Agent 嘗試自行呼叫 /${SKILL_NAME}，但沒有用戶授權。" >&2
echo "" >&2
echo "   Slash Command 只能由用戶直接輸入觸發。" >&2
echo "   Agent 不得自行呼叫 Skill tool 來執行工作流程命令。" >&2
echo "" >&2
echo "💡 如需執行此命令，請用戶在對話中輸入：/${SKILL_NAME}" >&2
echo "═══════════════════════════════════════════════════════════════" >&2
exit 2
