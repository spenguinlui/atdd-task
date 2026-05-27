#!/bin/bash
# 全 agent × model eval 矩陣：跑 6 個 scorer，收集 METRICS 行，彙整報告
# 設計圖：meta-harness prescriptions/2026-05-23-atdd-eval-harness.md（Stage 4 跨 model matrix）
# Usage: run-matrix.sh [N]   N=每項跑幾次（預設 3）
# 前置：docker 測試容器在跑（coder/tester 用）；codex login（gpt-5.5）
set -u
N="${1:-3}"; export EVAL_N="$N"
HUB="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
export CLAUDE_PROJECT_DIR="$HUB"
D="$HUB/experiments/atdd-eval"
ENGINES="claude:opus claude:sonnet claude:haiku codex:gpt-5.5"
TS=$(date +%Y%m%d-%H%M)
LOG="$D/results/matrix-$TS.log"; mkdir -p "$D/results"

# 各 agent 用的實例票（reviewer/style 同票；coder/tester 同票）
CODER_TICKET="sf_project CST-145"
REVIEW_TICKET="e_trading GRE-262"

run(){ echo; echo "########## $1 ##########"; shift; "$@" 2>&1; }

{
echo "===== EVAL MATRIX N=$N  $(date) ====="
run "specist"        bash "$D/eval-specist.sh"    $ENGINES
run "gatekeeper"     bash "$D/eval-gatekeeper.sh" $ENGINES
run "risk-reviewer"  env EVAL_AGENT=risk-reviewer  bash "$D/eval-reviewer.sh" $REVIEW_TICKET $ENGINES
run "style-reviewer" env EVAL_AGENT=style-reviewer bash "$D/eval-reviewer.sh" $REVIEW_TICKET $ENGINES
run "coder"          bash "$D/eval-coder.sh"  $CODER_TICKET gold $ENGINES
# tester 預設跳過：model 產的 test 需 repo 專屬 factory 慣例（gold 用 create(:project_management_project)
# + domain Factory class + fake_version doubles），diff 看不到 → 產的 test 跑不起來，valid 被環境壓成 0，
# 非測 test-writing 能力。待補「factory inventory / sample spec 注入」scaffolding。設 INCLUDE_TESTER=1 才跑。
[ "${INCLUDE_TESTER:-0}" = 1 ] && run "tester" bash "$D/eval-tester.sh" $CODER_TICKET $ENGINES
echo "===== DONE $(date) ====="
} | tee "$LOG"

echo
echo ">>> 彙整報告："
python3 "$D/aggregate.py" "$LOG" > "$D/results-$TS-matrix.md"
echo "報告：experiments/atdd-eval/results-$TS-matrix.md"
