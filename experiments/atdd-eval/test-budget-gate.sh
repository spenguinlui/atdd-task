#!/bin/bash
# pattern: B
# Pattern B：觸發+斷言 — budget-gate.sh
# 沙箱 HUB（fake task + fake counter）；不污染真實 task/counter。
set -u
HUB="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
HOOK="$HUB/.claude/hooks/budget-gate.sh"
[ -f "$HOOK" ] || { echo "$HOOK 不存在"; exit 1; }

CHECKS=0; FAILS=0
pass(){ CHECKS=$((CHECKS+1)); echo "  ✓ $1"; }
fail(){ CHECKS=$((CHECKS+1)); FAILS=$((FAILS+1)); echo "  ✗ $1"; }

TMP=$(mktemp -d -t bgtest-XXXX)
trap "rm -rf $TMP" EXIT
mkdir -p "$TMP/.claude/hooks" "$TMP/.claude/config" "$TMP/tasks/test/active"
ln -s "$HUB/.claude/hooks/lib" "$TMP/.claude/hooks/lib"
[ -f "$HUB/.claude/config/budget.yml" ] && cp "$HUB/.claude/config/budget.yml" "$TMP/.claude/config/"

write_task(){  # $1=maxTools $2=maxTokens $3=totalTokens
  cat > "$TMP/tasks/test/active/t1.json" <<EOF
{"id":"t1","description":"sv","budget":{"maxToolUses":$1,"maxTokens":$2},"metrics":{"totalTokens":${3:-0}}}
EOF
  rm -f "$TMP/.claude/.budget-t1.count"
}
run_hook(){ CLAUDE_PROJECT_DIR="$TMP" bash "$HOOK" </dev/null 2>&1; }

echo "▶ budget-gate Pattern B 自驗"

# 1) 無 active task → 放行
rm -f "$TMP/tasks/test/active"/*.json
run_hook >/dev/null 2>&1; rc=$?
[ "$rc" -eq 0 ] && pass "無 active task → exit 0" || fail "無 task rc=$rc 應 0"

# 2) 工具次數超 max → exit 2
write_task 2 1000000 0
run_hook >/dev/null  # n=1
run_hook >/dev/null  # n=2
out=$(run_hook); rc=$?  # n=3 > 2 → halt
{ [ "$rc" -eq 2 ] && echo "$out" | grep -q "工具呼叫"; } \
  && pass "tools n=3>max=2 → exit 2 + 「工具呼叫」訊息" \
  || fail "rc=$rc / 訊息：$(echo "$out" | head -2 | tr '\n' '|')"

# 3) token 軟上限超標 → exit 2
write_task 100 100 200
out=$(run_hook); rc=$?
{ [ "$rc" -eq 2 ] && echo "$out" | grep -qi "token"; } \
  && pass "tokens 200>max=100 → exit 2 + 「token」訊息" \
  || fail "rc=$rc / 訊息：$(echo "$out" | head -2 | tr '\n' '|')"

# 4) under budget → 放行（counter 重置後）
write_task 100 1000000 0
out=$(run_hook); rc=$?
[ "$rc" -eq 0 ] && pass "under budget → exit 0" || fail "under budget rc=$rc"

echo
[ "$FAILS" -eq 0 ] && { echo "✅ budget-gate $CHECKS/$CHECKS"; exit 0; } \
  || { echo "❌ $FAILS/$CHECKS 失敗"; exit 1; }
