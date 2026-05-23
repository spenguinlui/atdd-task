#!/bin/bash
# 執行預算閘門
# Hook: PreToolUse (Bash|Edit|Write|Task)
# 主煞車：工具呼叫次數（hook 自維護 per-task 計數，每次硬擋，可靠）
# 軟上限：token（讀 task metrics.totalTokens，record-metrics 於 SubagentStop 更新；agent 邊界粒度）
# 逼近 80% 警告；超過上限 exit 2 halt 交還 human
# read-only 查詢（Read/Glob/Grep）不掛此 hook → 不計入
set -u
HUB="${CLAUDE_PROJECT_DIR:?CLAUDE_PROJECT_DIR not set}"
cat >/dev/null 2>&1 || true   # 吞掉 hook stdin（本 hook 不需解析 payload）

# 找最近活躍任務；無則放行
TASK=$(find "$HUB"/tasks/*/active -name '*.json' 2>/dev/null | xargs ls -t 2>/dev/null | head -1)
[ -n "${TASK:-}" ] && [ -f "$TASK" ] || exit 0

# 讀 budget：task.budget 優先，缺則 budget.yml 預設
read -r MAXTOOLS MAXTOK TID < <(python3 - "$TASK" "$HUB/.claude/config/budget.yml" <<'PY'
import json, sys
t = json.load(open(sys.argv[1]))
b = t.get("budget") or {}
mt, mk = b.get("maxToolUses"), b.get("maxTokens")
if mt is None or mk is None:
    d = {}
    try:
        import yaml; d = yaml.safe_load(open(sys.argv[2])) or {}
    except Exception:
        pass
    mt = mt if mt is not None else d.get("maxToolUses", 150)
    mk = mk if mk is not None else d.get("maxTokens", 2000000)
print(mt, mk, t.get("id", "_"))
PY
) || exit 0

# ── 主煞車：工具呼叫次數（per-task 計數檔，每次 +1）──
CF="$HUB/.claude/.budget-${TID}.count"
n=$(( $(cat "$CF" 2>/dev/null || echo 0) + 1 ))
echo "$n" > "$CF"
warn=$(( MAXTOOLS * 80 / 100 ))
if [ "$n" -gt "$MAXTOOLS" ]; then
  echo "" >&2
  echo "🚫 執行預算超標：工具呼叫 $n > 上限 $MAXTOOLS — halt 交還 human。" >&2
  echo "   續跑：調高 task budget.maxToolUses，或 rm $CF" >&2
  exit 2
elif [ "$n" -ge "$warn" ]; then
  echo "⚠️ 執行預算：工具呼叫 ${n} / ${MAXTOOLS} （逼近上限）" >&2
fi

# ── 軟上限：token（邊界檢查）──
TOK=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("metrics",{}).get("totalTokens",0))' "$TASK" 2>/dev/null || echo 0)
if [ "${TOK:-0}" -gt "$MAXTOK" ]; then
  echo "" >&2
  echo "🚫 執行預算超標：token $TOK > 上限 $MAXTOK — halt 交還 human。" >&2
  echo "   續跑：調高 task budget.maxTokens。" >&2
  exit 2
fi
exit 0
