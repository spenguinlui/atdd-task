#!/bin/bash
# pattern: B
# Pattern B：觸發+斷言 — safety-gate.sh
# destructive 操作必確認；mutating/read 放行；confirmed flag 5 分鐘 TTL。
set -u
HUB="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
HOOK="$HUB/.claude/hooks/safety-gate.sh"
[ -f "$HOOK" ] || { echo "$HOOK 不存在"; exit 1; }

CHECKS=0; FAILS=0
pass(){ CHECKS=$((CHECKS+1)); echo "  ✓ $1"; }
fail(){ CHECKS=$((CHECKS+1)); FAILS=$((FAILS+1)); echo "  ✗ $1"; }

TMP=$(mktemp -d -t sgtest-XXXX)
trap "rm -rf $TMP" EXIT
mkdir -p "$TMP/.claude/hooks" "$TMP/.claude/config"
ln -s "$HUB/.claude/hooks/lib" "$TMP/.claude/hooks/lib"
cp "$HUB/.claude/config/tool-safety.yml" "$TMP/.claude/config/"

run_hook(){  # $1=tool_payload_json
  echo "$1" | CLAUDE_PROJECT_DIR="$TMP" bash "$HOOK" 2>&1
}

echo "▶ safety-gate Pattern B 自驗"

# 1) mutating MCP（atdd_task_update）→ 放行
out=$(run_hook '{"tool_name":"atdd_task_update","tool_input":{}}'); rc=$?
[ "$rc" -eq 0 ] && pass "mutating MCP → exit 0" || fail "rc=$rc"

# 2) destructive MCP（atdd_knowledge_delete）未確認 → exit 2
rm -f "$TMP/.claude/.safety-confirmed"
out=$(run_hook '{"tool_name":"mcp__atdd-admin__atdd_knowledge_delete","tool_input":{}}'); rc=$?
{ [ "$rc" -eq 2 ] && echo "$out" | grep -q "Safety Gate"; } \
  && pass "destructive MCP 未確認 → exit 2 + Safety Gate 訊息" \
  || fail "rc=$rc / 訊息：$(echo "$out" | head -3 | tr '\n' '|')"

# 3) Bash 一般命令（ls）→ 放行
out=$(run_hook '{"tool_name":"Bash","tool_input":{"command":"ls -la /tmp"}}'); rc=$?
[ "$rc" -eq 0 ] && pass "Bash ls → exit 0" || fail "rc=$rc"

# 4) confirmed flag 在 5 分鐘內 → 放行（即使 destructive）
echo "$(date +%s)|test|confirmed" > "$TMP/.claude/.safety-confirmed"
out=$(run_hook '{"tool_name":"mcp__atdd-admin__atdd_knowledge_delete","tool_input":{}}'); rc=$?
[ "$rc" -eq 0 ] && pass "destructive + 近期 confirmed → exit 0" \
  || fail "rc=$rc / 訊息：$(echo "$out" | head -2)"

# 5) confirmed flag 過期（>5min）→ 擋
OLD=$(( $(date +%s) - 600 ))
echo "$OLD|test|confirmed" > "$TMP/.claude/.safety-confirmed"
out=$(run_hook '{"tool_name":"mcp__atdd-admin__atdd_knowledge_delete","tool_input":{}}'); rc=$?
[ "$rc" -eq 2 ] && pass "destructive + 過期 confirmed → exit 2（TTL 失效）" \
  || fail "rc=$rc"

echo
[ "$FAILS" -eq 0 ] && { echo "✅ safety-gate $CHECKS/$CHECKS"; exit 0; } \
  || { echo "❌ $FAILS/$CHECKS 失敗"; exit 1; }
