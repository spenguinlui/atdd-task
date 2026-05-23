#!/bin/bash
# 階段交付物驗證
# Hook: PreToolUse (Task)
# 呼叫 ATDD agent 前，驗證前一階段交付物是否完整
# 重邏輯在 lib/validate-deliverables.py（R-3 減重：原 306 行 → 薄分派）
# 修復：原讀 $TOOL_INPUT env（Claude Code 不存在此 env）→ 改讀 stdin
set -u
HUB="${CLAUDE_PROJECT_DIR:?CLAUDE_PROJECT_DIR not set}"
TMP=$(mktemp); trap 'rm -f "$TMP"' EXIT
cat > "$TMP"
source "$HUB/.claude/hooks/lib/hooklog.sh"
python3 "$HUB/.claude/hooks/lib/validate-deliverables.py" "$TMP" "$HUB"
rc=$?
hooklog validate-deliverables "$([ "$rc" = 0 ] && echo allow || echo block)"
exit $rc
