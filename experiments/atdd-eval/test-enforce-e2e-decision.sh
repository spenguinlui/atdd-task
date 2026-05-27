#!/bin/bash
# pattern: B
# Pattern B：觸發+斷言 — enforce-e2e-decision.sh
# PreToolUse(mcp__atdd__atdd_task_update)：轉移到 specifying/testing 前必須有合法 e2eDecision
set -u
HUB="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
HOOK="$HUB/.claude/hooks/enforce-e2e-decision.sh"
[ -f "$HOOK" ] || { echo "$HOOK 不存在"; exit 1; }

CHECKS=0; FAILS=0
pass(){ CHECKS=$((CHECKS+1)); echo "  ✓ $1"; }
fail(){ CHECKS=$((CHECKS+1)); FAILS=$((FAILS+1)); echo "  ✗ $1"; }

mkpayload(){  # $1=tool_name $2=tool_input_json
  python3 -c "import json,sys; print(json.dumps({'tool_name':sys.argv[1],'tool_input':json.loads(sys.argv[2])}))" "$1" "$2"
}
run_hook(){ echo "$1" | CLAUDE_PROJECT_DIR="$HUB" bash "$HOOK" 2>&1; }

echo "▶ enforce-e2e-decision Pattern B 自驗"

# 1) 工具名不是 atdd_task_update → 放行
out=$(run_hook "$(mkpayload 'Write' '{"file_path":"foo"}')"); rc=$?
[ "$rc" -eq 0 ] && pass "非 task_update tool → exit 0" || fail "rc=$rc"

# 2) status 不在轉移觸發集（如 review）→ 放行
out=$(run_hook "$(mkpayload 'mcp__atdd__atdd_task_update' '{"status":"review"}')"); rc=$?
[ "$rc" -eq 0 ] && pass "status=review 非觸發 → exit 0" || fail "rc=$rc"

# 3) status=testing 缺 e2eDecision → exit 2
out=$(run_hook "$(mkpayload 'mcp__atdd__atdd_task_update' '{"status":"testing"}')"); rc=$?
{ [ "$rc" -eq 2 ] && echo "$out" | grep -q "e2eDecision"; } \
  && pass "status=testing 缺 e2eDecision → exit 2 + 提示" \
  || fail "rc=$rc / 訊息：$(echo "$out" | head -4 | tr '\n' '|')"

# 4) status=specification + e2eDecision=required + tool=chrome-mcp → 放行
PAYLOAD='{"status":"specification","metadata":{"acceptance":{"e2eDecision":{"decision":"required","tool":"chrome-mcp"}}}}'
out=$(run_hook "$(mkpayload 'mcp__atdd__atdd_task_update' "$PAYLOAD")"); rc=$?
[ "$rc" -eq 0 ] && pass "required + chrome-mcp → exit 0" \
  || fail "rc=$rc / 訊息：$(echo "$out" | head -3 | tr '\n' '|')"

# 5) status=testing + e2eDecision=skipped 但缺 reason → exit 2
PAYLOAD='{"status":"testing","metadata":{"acceptance":{"e2eDecision":{"decision":"skipped"}}}}'
out=$(run_hook "$(mkpayload 'mcp__atdd__atdd_task_update' "$PAYLOAD")"); rc=$?
{ [ "$rc" -eq 2 ] && echo "$out" | grep -q "reason\|理由"; } \
  && pass "skipped 缺 reason → exit 2 + 「reason」訊息" \
  || fail "rc=$rc / 訊息：$(echo "$out" | head -3 | tr '\n' '|')"

# 6) status=testing + skipped + reason → 放行
PAYLOAD='{"status":"testing","metadata":{"acceptance":{"e2eDecision":{"decision":"skipped","reason":"純 DB migration、無 UI 變更"}}}}'
out=$(run_hook "$(mkpayload 'mcp__atdd__atdd_task_update' "$PAYLOAD")"); rc=$?
[ "$rc" -eq 0 ] && pass "skipped + reason → exit 0" \
  || fail "rc=$rc / 訊息：$(echo "$out" | head -3 | tr '\n' '|')"

echo
[ "$FAILS" -eq 0 ] && { echo "✅ enforce-e2e-decision $CHECKS/$CHECKS"; exit 0; } \
  || { echo "❌ $FAILS/$CHECKS 失敗"; exit 1; }
