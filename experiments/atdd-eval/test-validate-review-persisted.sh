#!/bin/bash
# pattern: B
# Pattern B：觸發+斷言 — validate-review-persisted.sh
# 構造 reviewer SubagentStop payload + 各種 reviewFindings 形狀，驗 hook 對/錯都接得住。
set -u
HUB="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
HOOK="$HUB/.claude/hooks/validate-review-persisted.sh"
[ -f "$HOOK" ] || { echo "$HOOK 不存在"; exit 1; }

CHECKS=0; FAILS=0
pass(){ CHECKS=$((CHECKS+1)); echo "  ✓ $1"; }
fail(){ CHECKS=$((CHECKS+1)); FAILS=$((FAILS+1)); echo "  ✗ $1"; }

TMP=$(mktemp -d -t rptest-XXXX)
trap "rm -rf $TMP" EXIT
mkdir -p "$TMP/tasks/test/active"

write_task(){  # $1=status $2=reviewFindings_json（注意要合法 JSON）
  cat > "$TMP/tasks/test/active/t1.json" <<EOF
{"id":"t1","description":"自驗","status":"$1","metadata":{"context":{"reviewFindings":$2}}}
EOF
}
run_hook(){  # $1=agent_type
  echo "{\"agent_type\":\"$1\"}" | CLAUDE_PROJECT_DIR="$TMP" bash "$HOOK" 2>&1
}

echo "▶ validate-review-persisted Pattern B 自驗"

# 1) 非 reviewer agent → 跳過放行
write_task reviewing 'null'
out=$(run_hook coder); rc=$?
[ "$rc" -eq 0 ] && pass "非 reviewer agent_type → exit 0" || fail "rc=$rc"

# 2) 任務 status 不是 reviewing/review → 跳過
write_task development 'null'
out=$(run_hook risk-reviewer); rc=$?
[ "$rc" -eq 0 ] && pass "status=development → exit 0（不檢驗）" || fail "rc=$rc"

# 3) reviewing 但 reviewFindings 缺失 → 擋
write_task reviewing 'null'
out=$(run_hook risk-reviewer); rc=$?
{ [ "$rc" -eq 2 ] && echo "$out" | grep -q "持久化驗證失敗"; } \
  && pass "reviewFindings null → exit 2 + 驗證失敗訊息" \
  || fail "rc=$rc / 訊息：$(echo "$out" | head -3 | tr '\n' '|')"

# 4) 正確巢狀格式（即使空陣列）→ 放行
write_task reviewing '{"riskReview":{"findings":[]}}'
out=$(run_hook risk-reviewer); rc=$?
[ "$rc" -eq 0 ] && pass "riskReview.findings=[] → exit 0（零問題也合規）" \
  || fail "rc=$rc / 訊息：$(echo "$out" | head -3 | tr '\n' '|')"

# 5) style-reviewer 缺 styleReview 區塊 → 擋
write_task reviewing '{"riskReview":{"findings":[]}}'
out=$(run_hook style-reviewer); rc=$?
[ "$rc" -eq 2 ] && pass "style-reviewer 缺 styleReview → exit 2" \
  || fail "rc=$rc"

# 6) 平鋪格式 reviewFindings.findings（錯）→ 擋
write_task reviewing '{"findings":[]}'
out=$(run_hook risk-reviewer); rc=$?
[ "$rc" -eq 2 ] && pass "平鋪 reviewFindings.findings → exit 2（強制巢狀）" \
  || fail "rc=$rc"

echo
[ "$FAILS" -eq 0 ] && { echo "✅ validate-review-persisted $CHECKS/$CHECKS"; exit 0; } \
  || { echo "❌ $FAILS/$CHECKS 失敗"; exit 1; }
