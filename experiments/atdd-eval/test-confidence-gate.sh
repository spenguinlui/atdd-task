#!/bin/bash
# pattern: B
# Pattern B 範例：觸發 + 斷言 — 測 .claude/hooks/confidence-gate.sh
# 不需 live session、不需 MCP、不需 docker。純 stdin/exit code 驗證。
#
# 證明：寫自驗工具的 pattern 可重用，每次 30 分鐘以內。
set -u
HUB="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$HUB" || exit 1
export CLAUDE_PROJECT_DIR="$HUB"
HOOK=.claude/hooks/confidence-gate.sh
[ -f "$HOOK" ] || { echo "找不到 $HOOK"; exit 1; }

CHECKS=0; FAILS=0
pass(){ CHECKS=$((CHECKS+1)); echo "  ✓ $1"; }
fail(){ CHECKS=$((CHECKS+1)); FAILS=$((FAILS+1)); echo "  ✗ $1"; }

echo "▶ confidence-gate Pattern B 自驗（觸發+斷言）"

# 用獨特路徑避免撞到實際的 .knowledge-confirmed 記錄
FAKE="domains/__self_verify_fake_$(date +%s)__.md"

# Case 1：domains/*.md 未確認 → 應 exit 2 + 知識信心度訊息
in1="{\"tool_input\":{\"file_path\":\"$FAKE\"}}"
out=$(echo "$in1" | bash "$HOOK" 2>&1); rc=$?
if [ "$rc" -eq 2 ] && echo "$out" | grep -q "Knowledge Confidence Gate"; then
  pass "domains/*.md 未確認 → exit 2 + Knowledge Confidence Gate 訊息"
else
  fail "rc=$rc，訊息頭：$(echo "$out" | head -2 | tr -d '\n')"
fi

# Case 2：TEMPLATE 排除 → exit 0
in2='{"tool_input":{"file_path":"domains/foo/TEMPLATE.md"}}'
bash "$HOOK" <<<"$in2" >/dev/null 2>&1; rc=$?
[ "$rc" -eq 0 ] && pass "TEMPLATE 排除 → exit 0" || fail "TEMPLATE 應 exit 0（rc=$rc）"

# Case 3：空 file_path → exit 0
in3='{"tool_input":{}}'
bash "$HOOK" <<<"$in3" >/dev/null 2>&1; rc=$?
[ "$rc" -eq 0 ] && pass "空 file_path → exit 0" || fail "空 file_path 應 exit 0（rc=$rc）"

# Case 4：非 domain、非 code 副檔名 → exit 0
in4='{"tool_input":{"file_path":"README.md"}}'
bash "$HOOK" <<<"$in4" >/dev/null 2>&1; rc=$?
[ "$rc" -eq 0 ] && pass "README.md（非 domain/code）→ exit 0" || fail "README.md 應 exit 0（rc=$rc）"

# Case 5：code 副檔名但無 active fix task → exit 0（投資門先過）
in5='{"tool_input":{"file_path":"/tmp/foo.rb"}}'
bash "$HOOK" <<<"$in5" >/dev/null 2>&1; rc=$?
[ "$rc" -eq 0 ] && pass "code 檔但無 active fix task → exit 0" || fail "rc=$rc"

echo
if [ "$FAILS" -eq 0 ]; then echo "✅ confidence-gate $CHECKS/$CHECKS 全過"; exit 0
else echo "❌ $FAILS/$CHECKS 項失敗"; exit 1; fi
