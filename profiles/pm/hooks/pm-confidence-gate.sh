#!/bin/bash
# PM Confidence Gate (Stop Hook)
# 用途：在 PM Slack 模式下，信心度未達 95% 時阻止 Claude 停止回應
# 觸發：Stop
# 輸入：stdin JSON with last_assistant_message, stop_hook_active
# 輸出：JSON {"decision": "block", "reason": "..."} 或 exit 0 放行

set -e

INPUT=$(cat)

# 檢查 stop_hook_active，避免無限迴圈
STOP_HOOK_ACTIVE=$(echo "$INPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(str(data.get('stop_hook_active', False)).lower())
" 2>/dev/null || echo "false")

if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
    # 已經被 block 過一次了，這次放行避免無限迴圈
    exit 0
fi

# 取得 Claude 的最後回覆
LAST_MESSAGE=$(echo "$INPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('last_assistant_message', ''))
" 2>/dev/null || echo "")

# 如果沒有回覆內容，放行
if [ -z "$LAST_MESSAGE" ]; then
    exit 0
fi

# 檢查是否在 PM Slack 模式（看回覆是否包含信心度報告）
# 如果不包含信心度相關關鍵字，放行（不是 PM specist 的回覆）
if ! echo "$LAST_MESSAGE" | grep -qE '需求信心度|信心度.*[0-9]+%'; then
    exit 0
fi

# 提取信心度數字
CONFIDENCE=$(echo "$LAST_MESSAGE" | python3 -c "
import sys, re

text = sys.stdin.read()

# 匹配「需求信心度：XX%」或「信心度達 XX%」或「信心度約 XX%」或「信心度：XX%」
patterns = [
    r'需求信心度[：:]\s*\*{0,2}(\d+(?:\.\d+)?)\s*%',
    r'信心度[達約為：:]\s*\*{0,2}(\d+(?:\.\d+)?)\s*%',
    r'信心度\s*\*{0,2}(\d+(?:\.\d+)?)\s*%',
]

for pattern in patterns:
    match = re.search(pattern, text)
    if match:
        print(match.group(1))
        sys.exit(0)

# 沒找到信心度數字
print('-1')
" 2>/dev/null || echo "-1")

# 無法解析信心度，放行
if [ "$CONFIDENCE" = "-1" ]; then
    exit 0
fi

# 比較信心度與閾值
THRESHOLD=95

BELOW_THRESHOLD=$(python3 -c "
confidence = float('$CONFIDENCE')
threshold = float('$THRESHOLD')
print('yes' if confidence < threshold else 'no')
" 2>/dev/null || echo "no")

if [ "$BELOW_THRESHOLD" = "yes" ]; then
    # 信心度不足，阻止 Claude 停止，要求繼續澄清
    cat << EOF
{
  "decision": "block",
  "reason": "信心度 ${CONFIDENCE}% 未達 ${THRESHOLD}% 門檻。請根據扣分最高的維度，繼續向 PM 提出具體的澄清問題。不要建議 PM 確認 BA。"
}
EOF
    exit 0
fi

# 信心度達標，放行
exit 0
