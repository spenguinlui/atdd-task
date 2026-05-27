#!/bin/bash
# pattern: B
# Pattern B：觸發+斷言 — validate-spec-format.sh
# PostToolUse(Write)：驗 BA 報告（requirements/*-ba.md）必含三大區塊；非 md/非 BA 放行
set -u
HUB="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
HOOK="$HUB/.claude/hooks/validate-spec-format.sh"
[ -f "$HOOK" ] || { echo "$HOOK 不存在"; exit 1; }

CHECKS=0; FAILS=0
pass(){ CHECKS=$((CHECKS+1)); echo "  ✓ $1"; }
fail(){ CHECKS=$((CHECKS+1)); FAILS=$((FAILS+1)); echo "  ✗ $1"; }

# JSON payload builder（用 python 安全處理多行中文 content）
mkpayload(){  # $1=file_path  $2=content
  python3 -c "import json,sys; print(json.dumps({'tool_input':{'file_path':sys.argv[1],'content':sys.argv[2]}}))" "$1" "$2"
}
run_hook(){ echo "$1" | CLAUDE_PROJECT_DIR="$HUB" bash "$HOOK" 2>&1; }

echo "▶ validate-spec-format Pattern B 自驗"

# 1) 非 .md 檔（.rb）→ 放行
out=$(run_hook "$(mkpayload '/some/foo.rb' 'class Foo; end')"); rc=$?
[ "$rc" -eq 0 ] && pass "非 .md（.rb）→ exit 0" || fail "rc=$rc"

# 2) 一般 .md（非 BA 路徑）→ 放行
out=$(run_hook "$(mkpayload '/some/README.md' '# Hello')"); rc=$?
[ "$rc" -eq 0 ] && pass "非 BA 路徑（README.md）→ exit 0" || fail "rc=$rc"

# 3) BA 報告缺三大區塊 → exit 1 + 錯誤訊息
BAD_BA="# 隨便寫
這份報告什麼必要區塊都沒有。"
out=$(run_hook "$(mkpayload '/proj/requirements/CST-99-ba.md' "$BAD_BA")"); rc=$?
{ [ "$rc" -eq 1 ] && echo "$out" | grep -q "缺少「## 需求摘要」"; } \
  && pass "BA 缺三大區塊 → exit 1 + 「缺少」訊息" \
  || fail "rc=$rc / 訊息：$(echo "$out" | head -4 | tr '\n' '|')"

# 4) BA 報告齊三大區塊 + 無技術洩漏 → 放行
GOOD_BA="## 需求摘要
某 PM 想要某功能，讓使用者能完成某情境。

## 業務分析結論
此需求屬於既有流程的擴充，影響 X 區域。

## 驗收條件
- 條件一達成
- 條件二達成"
out=$(run_hook "$(mkpayload '/proj/requirements/CST-99-ba.md' "$GOOD_BA")"); rc=$?
[ "$rc" -eq 0 ] && pass "BA 三區塊齊 + 無技術洩漏 → exit 0" \
  || fail "rc=$rc / 訊息：$(echo "$out" | head -4 | tr '\n' '|')"

# 5) BA 三區塊齊但含 backtick（技術洩漏）→ exit 1
LEAK_BA="## 需求摘要
要呼叫 \`SomeService.call\` 來完成。

## 業務分析結論
技術細節...

## 驗收條件
- 完成"
out=$(run_hook "$(mkpayload '/proj/requirements/CST-99-ba.md' "$LEAK_BA")"); rc=$?
{ [ "$rc" -eq 1 ] && echo "$out" | grep -qi "技術\|backtick\|語言"; } \
  && pass "BA 含 backtick 技術洩漏 → exit 1" \
  || fail "rc=$rc / 訊息：$(echo "$out" | head -4 | tr '\n' '|')"

echo
[ "$FAILS" -eq 0 ] && { echo "✅ validate-spec-format $CHECKS/$CHECKS"; exit 0; } \
  || { echo "❌ $FAILS/$CHECKS 失敗"; exit 1; }
