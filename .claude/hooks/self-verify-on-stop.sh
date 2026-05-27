#!/bin/bash
# Stop hook：每次 Claude 想結束本輪前跑全 repo 自驗；drift → exit 2 擋住結束
# 對應 R-10（可機驗 outcome 必先自驗再交付）的硬規則層。
# 如果 runner 不存在或自驗通過 → exit 0 安靜放行。
ATDD_HUB_DIR="${CLAUDE_PROJECT_DIR:?CLAUDE_PROJECT_DIR not set}"
RUNNER="${ATDD_HUB_DIR}/experiments/atdd-eval/run-self-verify.sh"

[ -f "$RUNNER" ] || exit 0   # 還沒佈 runner → 放行

OUT=$(bash "$RUNNER" 2>&1); rc=$?
if [ "$rc" -ne 0 ]; then
  {
    echo ""
    echo "$OUT"
    echo ""
    echo "⛔ Stop hook 擋下本輪結束：自驗失敗（drift 與設計圖不一致）。"
    echo "   修到 \`bash experiments/atdd-eval/run-self-verify.sh\` 通過再結束。"
    echo "   依據：R-10 可機驗 outcome 必先自驗再交付。"
  } >&2
  exit 2
fi
exit 0
