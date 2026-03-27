#!/bin/bash
# Agent Metrics 自動記錄
# Hook: SubagentStop
# 用途：在 Agent 執行完成後，自動解析 metrics 並更新任務 JSON
#
# 輸入：透過 stdin 接收 JSON（包含 agent_type, transcript 等）
# 輸出：更新任務 JSON 的 agents 和 metrics 欄位

set -e

ATDD_HUB_DIR="${CLAUDE_PROJECT_DIR:?CLAUDE_PROJECT_DIR not set}"
TASKS_DIR="${ATDD_HUB_DIR}/tasks"

# 從 stdin 讀取 hook input JSON
HOOK_INPUT=$(cat)

# Debug log（設定 ATDD_DEBUG=1 啟用）
if [ "${ATDD_DEBUG:-0}" = "1" ]; then
    DEBUG_DIR="${ATDD_HUB_DIR}/.claude/hooks/debug"
    mkdir -p "$DEBUG_DIR"
    echo "$HOOK_INPUT" > "$DEBUG_DIR/subagent-stop-$(date +%Y%m%d_%H%M%S).json"
fi

# 解析 agent type（SubagentStop 使用 agent_type 欄位）
AGENT_TYPE=$(echo "$HOOK_INPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
# SubagentStop 可能用 agent_type 或從 tool_input.subagent_type 取得
print(data.get('agent_type', data.get('tool_input', {}).get('subagent_type', '')))
" 2>/dev/null || echo "")

# 只處理 ATDD 相關的 agents
ATDD_AGENTS="specist tester coder style-reviewer risk-reviewer gatekeeper"
if [ -z "$AGENT_TYPE" ] || ! echo "$ATDD_AGENTS" | grep -qw "$AGENT_TYPE"; then
    exit 0
fi

# 從 hook input 解析 metrics
# SubagentStop 提供 transcript_path 或直接提供 usage 資訊
METRICS=$(echo "$HOOK_INPUT" | python3 -c "
import sys, json

data = json.load(sys.stdin)

# 嘗試多種路徑取得 metrics
tool_uses = 0
tokens = 0
duration_ms = 0

# 路徑 1：直接從 usage 欄位
usage = data.get('usage', {})
if usage:
    tool_uses = usage.get('tool_uses', 0)
    tokens = usage.get('total_tokens', 0)
    duration_ms = usage.get('duration_ms', 0)

# 路徑 2：從 tool_response 的 usage
if not tool_uses:
    resp = data.get('tool_response', {})
    if isinstance(resp, dict):
        usage = resp.get('usage', {})
        tool_uses = usage.get('tool_uses', 0)
        tokens = usage.get('total_tokens', 0)
        duration_ms = usage.get('duration_ms', 0)

# 路徑 3：從 agent output 文字解析 <usage> 標籤
if not tool_uses:
    import re
    output = str(data.get('tool_response', data.get('agent_output', '')))

    m = re.search(r'tool_uses:\s*(\d+)', output)
    if m:
        tool_uses = int(m.group(1))

    m = re.search(r'total_tokens:\s*(\d+)', output)
    if m:
        tokens = int(m.group(1))

    m = re.search(r'duration_ms:\s*(\d+)', output)
    if m:
        duration_ms = int(m.group(1))

# 轉換 duration
if duration_ms > 0:
    minutes = duration_ms // 60000
    seconds = (duration_ms % 60000) // 1000
    if minutes > 0:
        duration = f'{minutes}m {seconds}s'
    else:
        duration = f'{seconds}s'
else:
    duration = '0s'

print(json.dumps({
    'tool_uses': tool_uses,
    'tokens': tokens,
    'duration': duration
}))
" 2>/dev/null || echo '{"tool_uses":0,"tokens":0,"duration":"0s"}')

TOOL_USES=$(echo "$METRICS" | python3 -c "import sys,json; print(json.load(sys.stdin)['tool_uses'])")
TOKENS=$(echo "$METRICS" | python3 -c "import sys,json; print(json.load(sys.stdin)['tokens'])")
DURATION=$(echo "$METRICS" | python3 -c "import sys,json; print(json.load(sys.stdin)['duration'])")

# 提前提取 transcript path（供 fallback metrics 和 tool breakdown 使用）
TRANSCRIPT_PATH=$(echo "$HOOK_INPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('agent_transcript_path', data.get('transcript_path', '')))
" 2>/dev/null || echo "")

# 如果 metrics 全為 0，嘗試從 transcript 解析
if [ "$TOOL_USES" = "0" ] && [ "$TOKENS" = "0" ]; then
    if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
        TRANSCRIPT_METRICS=$(tail -50 "$TRANSCRIPT_PATH" | python3 -c "
import sys, json, re

lines = sys.stdin.read()
tool_uses = 0
tokens = 0
duration_ms = 0

# 解析 JSONL 中的 usage
for line in lines.strip().split('\n'):
    try:
        entry = json.loads(line)
        if 'usage' in entry:
            u = entry['usage']
            tokens += u.get('input_tokens', 0) + u.get('output_tokens', 0)
    except:
        pass

# 從文字中搜尋 <usage> 標籤
m = re.search(r'tool_uses:\s*(\d+)', lines)
if m: tool_uses = int(m.group(1))
m = re.search(r'total_tokens:\s*(\d+)', lines)
if m: tokens = max(tokens, int(m.group(1)))
m = re.search(r'duration_ms:\s*(\d+)', lines)
if m: duration_ms = int(m.group(1))

if duration_ms > 0:
    mins = duration_ms // 60000
    secs = (duration_ms % 60000) // 1000
    duration = f'{mins}m {secs}s' if mins > 0 else f'{secs}s'
else:
    duration = '0s'

print(json.dumps({'tool_uses': tool_uses, 'tokens': tokens, 'duration': duration}))
" 2>/dev/null || echo '{"tool_uses":0,"tokens":0,"duration":"0s"}')

        TOOL_USES=$(echo "$TRANSCRIPT_METRICS" | python3 -c "import sys,json; print(json.load(sys.stdin)['tool_uses'])")
        TOKENS=$(echo "$TRANSCRIPT_METRICS" | python3 -c "import sys,json; print(json.load(sys.stdin)['tokens'])")
        DURATION=$(echo "$TRANSCRIPT_METRICS" | python3 -c "import sys,json; print(json.load(sys.stdin)['duration'])")
    fi
fi

# 從 transcript 解析 tool 類型分佈
TOOL_BREAKDOWN="{}"
if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
    TOOL_BREAKDOWN=$(cat "$TRANSCRIPT_PATH" | python3 -c "
import sys, json
from collections import Counter

counts = Counter()
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        record = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        continue
    # assistant message 的 content 中包含 tool_use items
    content = None
    msg = record.get('message')
    if isinstance(msg, dict):
        content = msg.get('content')
    if content is None:
        content = record.get('content')
    if not isinstance(content, list):
        continue
    for item in content:
        if isinstance(item, dict) and item.get('type') == 'tool_use':
            name = item.get('name', 'unknown')
            counts[name] += 1

# 依數量降序排列
sorted_counts = dict(sorted(counts.items(), key=lambda x: -x[1]))
print(json.dumps(sorted_counts))
" 2>/dev/null || echo "{}")
fi

echo "📊 記錄 Agent Metrics..."
echo "   Agent：$AGENT_TYPE"
echo "   Tool Uses：$TOOL_USES"
echo "   Tokens：$TOKENS"
echo "   Duration：$DURATION"
echo "   Tool Breakdown：$TOOL_BREAKDOWN"

# 找到當前活躍的任務
ACTIVE_TASKS=$(find "$TASKS_DIR"/*/active -name "*.json" 2>/dev/null | head -1 || echo "")

if [ -z "$ACTIVE_TASKS" ]; then
    echo "⚠️ 沒有找到活躍的任務，跳過 metrics 記錄"
    exit 0
fi

TASK_JSON="$ACTIVE_TASKS"

# 決定 Agent 的 role
get_agent_role() {
    case "$1" in
        "specist") echo "需求分析" ;;
        "tester") echo "測試生成" ;;
        "coder") echo "代碼實作" ;;
        "style-reviewer") echo "風格審查" ;;
        "risk-reviewer") echo "風險審查" ;;
        "gatekeeper") echo "品質把關" ;;
        *) echo "未知" ;;
    esac
}

AGENT_ROLE=$(get_agent_role "$AGENT_TYPE")

# 使用 Python 更新 JSON
python3 << PYEOF
import json
from datetime import datetime
from collections import Counter

task_path = "$TASK_JSON"
agent_name = "$AGENT_TYPE"
agent_role = "$AGENT_ROLE"
tool_uses = int("$TOOL_USES" or "0")
tokens = int("$TOKENS" or "0")
duration = "$DURATION"

tool_breakdown_raw = """$TOOL_BREAKDOWN"""
try:
    tool_breakdown = json.loads(tool_breakdown_raw) if tool_breakdown_raw.strip() else {}
except (json.JSONDecodeError, ValueError):
    tool_breakdown = {}

with open(task_path, 'r') as f:
    task = json.load(f)

if 'agents' not in task:
    task['agents'] = []

phase = task.get('status', '')

task['agents'].append({
    "name": agent_name,
    "role": agent_role,
    "phase": phase,
    "metrics": {
        "toolUses": tool_uses,
        "tokens": tokens,
        "duration": duration,
        "toolBreakdown": tool_breakdown
    },
    "timestamp": datetime.now().isoformat()
})

total_tools = sum(a.get('metrics', {}).get('toolUses', 0) for a in task['agents'])
total_tokens = sum(a.get('metrics', {}).get('tokens', 0) for a in task['agents'])

# 聚合所有 agent 的 toolBreakdown
total_breakdown = Counter()
for a in task['agents']:
    bd = a.get('metrics', {}).get('toolBreakdown', {})
    if isinstance(bd, dict):
        for tool_name, count in bd.items():
            total_breakdown[tool_name] += count

if task.get('metrics') is None:
    task['metrics'] = {}
task['metrics']['totalToolUses'] = total_tools
task['metrics']['totalTokens'] = total_tokens
task['metrics']['totalToolBreakdown'] = dict(
    sorted(total_breakdown.items(), key=lambda x: -x[1])
)

task['updatedAt'] = datetime.now().isoformat()

with open(task_path, 'w') as f:
    json.dump(task, f, ensure_ascii=False, indent=2)

print(f"✅ Metrics 已記錄到：{task_path}")
print(f"   累計：{total_tools} tools / {total_tokens} tokens")
if total_breakdown:
    top3 = ", ".join(f"{k}:{v}" for k, v in list(total_breakdown.most_common(3)))
    print(f"   Tool 分佈 Top 3：{top3}")
PYEOF

exit 0
