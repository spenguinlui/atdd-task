#!/bin/bash
# 全 repo 自驗 runner — 跑 experiments/atdd-eval/test-*.sh 所有支
# 一個 entry point：bash experiments/atdd-eval/run-self-verify.sh
# 退出碼 0=全過、1=有 drift。讓 Stop hook / /done / CI 都可叫同一個。
set -u
HUB="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$HUB" || { echo "cd HUB 失敗"; exit 1; }

# 找所有 test-*.sh（先只看 experiments/atdd-eval/；未來別處需要可擴）
TESTS=$(ls experiments/atdd-eval/test-*.sh 2>/dev/null)
if [ -z "$TESTS" ]; then
  echo "（無 test-*.sh 自驗腳本，視為通過）"; exit 0
fi

echo "▶ Self-verify suite（${HUB}）"
fails=0; ran=0
for f in $TESTS; do
  ran=$((ran+1))
  echo
  echo "──── $(basename "$f") ────"
  bash "$f"; rc=$?
  [ "$rc" -ne 0 ] && fails=$((fails+1))
done
echo
if [ "$fails" -eq 0 ]; then
  echo "✅ Self-verify: $ran 支腳本全過"
  exit 0
else
  echo "❌ Self-verify: $fails / $ran 支腳本失敗 — drift detected（按 R-10 須修到一致才能交付）"
  exit 1
fi
