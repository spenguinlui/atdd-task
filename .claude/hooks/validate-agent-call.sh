#!/bin/bash
# ATDD 工作流程驗證
# Hook: PreToolUse (Task)
# 驗證 agent 能否在當前 task 階段呼叫 + specist 信心度 ≥95% 硬阻擋
# 重邏輯在 lib/validate-agent-call.py（R-3 減重：原 212 行 → 薄分派）
# 修復：原讀 $TOOL_INPUT env（Claude Code 不存在此 env）→ 改讀 stdin
set -u
HUB="${CLAUDE_PROJECT_DIR:?CLAUDE_PROJECT_DIR not set}"
TMP=$(mktemp); trap 'rm -f "$TMP"' EXIT
cat > "$TMP"
python3 "$HUB/.claude/hooks/lib/validate-agent-call.py" "$TMP" "$HUB"
exit $?
