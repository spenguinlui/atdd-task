#!/bin/bash
# Agent Metrics 自動記錄
# Hook: SubagentStop
# 用途：Agent 完成後解析 metrics 更新任務 JSON
# 重邏輯在 lib/record-metrics.py（R-3 減重：原 296 行 → 薄分派）
set -u
HUB="${CLAUDE_PROJECT_DIR:?CLAUDE_PROJECT_DIR not set}"
TMP=$(mktemp); trap 'rm -f "$TMP"' EXIT
cat > "$TMP"

# Debug log（ATDD_DEBUG=1 啟用）
if [ "${ATDD_DEBUG:-0}" = "1" ]; then
    mkdir -p "$HUB/.claude/hooks/debug"
    cp "$TMP" "$HUB/.claude/hooks/debug/subagent-stop-$(date +%Y%m%d_%H%M%S).json"
fi

source "$HUB/.claude/hooks/lib/hooklog.sh"
python3 "$HUB/.claude/hooks/lib/record-metrics.py" "$TMP" "$HUB" || true
hooklog record-metrics recorded
exit 0
