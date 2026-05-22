#!/bin/bash
# Confidence Gate (通用信心度閘門)
# 用途：攔截需要信心度確認的 Write/Edit 操作
# 觸發：PreToolUse (Write|Edit)
# 輸入：stdin (JSON with tool_name, tool_input.file_path)
# 輸出：exit 0 = 允許, exit 2 = 阻止並顯示訊息
#
# 閘門類型：
# 1. 知識信心度：攔截 domains/**/*.md 的寫入（原有邏輯）
# 2. 調查前置檢查：攔截 fix 任務 development 階段未調查就編輯 codebase 的操作

set -e

ATDD_HUB_DIR="${CLAUDE_PROJECT_DIR:?CLAUDE_PROJECT_DIR not set}"
KNOWLEDGE_CONFIRMATION_FILE="${ATDD_HUB_DIR}/.claude/.knowledge-confirmed"
INVESTIGATION_CONFIRMATION_FILE="${ATDD_HUB_DIR}/.claude/.investigation-confirmed"
TASKS_DIR="${ATDD_HUB_DIR}/tasks"

# 從 stdin 讀取 JSON
INPUT=$(cat)

# 解析 file_path
FILE_PATH=$(echo "$INPUT" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('tool_input', {}).get('file_path', ''))" 2>/dev/null || echo "")

# 如果沒有 file_path，放行
if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# ═══════════════════════════════════════════════════════════════
# 閘門 1：知識信心度（domains/**/*.md）
# ═══════════════════════════════════════════════════════════════

if [[ "$FILE_PATH" =~ domains/.*\.md$ ]]; then
    # 排除模板檔案
    if [[ "$FILE_PATH" =~ TEMPLATE ]]; then
        exit 0
    fi

    # 檢查確認檔案（5 分鐘有效期）
    if [ -f "$KNOWLEDGE_CONFIRMATION_FILE" ]; then
        NOW=$(date +%s)
        while IFS='|' read -r timestamp filepath source; do
            if [ "$filepath" = "$FILE_PATH" ]; then
                TIME_DIFF=$((NOW - timestamp))
                if [ "$TIME_DIFF" -lt 300 ]; then
                    exit 0
                fi
            fi
        done < "$KNOWLEDGE_CONFIRMATION_FILE"
    fi

    # 未確認，阻止寫入
    cat >&2 << EOF

═══════════════════════════════════════════════════════════════
🚫 Knowledge Confidence Gate
═══════════════════════════════════════════════════════════════

目標檔案：$FILE_PATH

❌ 此檔案屬於 Domain 知識庫，需要先確認信心度。

請先執行以下步驟：

1. 列出所有假設及其來源
2. 標註每個假設的信心度（0-100%）
3. 使用 AskUserQuestion 向用戶確認
4. 用戶確認後，執行以下命令解鎖：

   echo "\$(date +%s)|${FILE_PATH}|user_confirmed" >> "${KNOWLEDGE_CONFIRMATION_FILE}"

═══════════════════════════════════════════════════════════════
EOF

    exit 2
fi

# ═══════════════════════════════════════════════════════════════
# 閘門 2：調查前置檢查（codebase 檔案，fix 任務 development 階段）
# 不使用信心度評分，改為檢查 task JSON 是否有調查記錄
# ═══════════════════════════════════════════════════════════════

# 只攔截程式碼檔案
CODE_EXTENSIONS="\.rb$|\.js$|\.py$|\.ts$|\.tsx$|\.jsx$|\.erb$|\.haml$|\.slim$|\.vue$|\.css$|\.scss$|\.sass$"
if [[ ! "$FILE_PATH" =~ ($CODE_EXTENSIONS) ]]; then
    exit 0
fi

# 找到活躍的 fix 任務
ACTIVE_TASKS=$(find "$TASKS_DIR"/*/active -name "*.json" 2>/dev/null || echo "")
if [ -z "$ACTIVE_TASKS" ]; then
    exit 0
fi

# 檢查是否有 fix 任務在 development 階段
FIX_TASK_JSON=""
for task_file in $ACTIVE_TASKS; do
    TASK_TYPE=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("type",""))' "$task_file" 2>/dev/null || echo "")
    TASK_STATUS=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("status",""))' "$task_file" 2>/dev/null || echo "")
    if [ "$TASK_TYPE" = "fix" ] && [ "$TASK_STATUS" = "development" ]; then
        FIX_TASK_JSON="$task_file"
        break
    fi
done

# 不是 fix development 階段，放行
if [ -z "$FIX_TASK_JSON" ]; then
    exit 0
fi

# 檢查 task JSON 是否有調查記錄（rootCause 或 reproduction 至少一個有值）
HAS_INVESTIGATION=$(python3 -c '
import json, sys
d = json.load(open(sys.argv[1]))
inv = d.get("investigation", {})
root_cause = inv.get("rootCause", "")
reproduction = inv.get("reproduction", "")
print("yes" if root_cause or reproduction else "no")
' "$FIX_TASK_JSON" 2>/dev/null || echo "no")

# 有調查記錄，放行
if [ "$HAS_INVESTIGATION" = "yes" ]; then
    exit 0
fi

# 檢查是否有有效的手動確認（5 分鐘有效期）
if [ -f "$INVESTIGATION_CONFIRMATION_FILE" ]; then
    NOW=$(date +%s)
    while IFS='|' read -r timestamp filepath source; do
        if [ "$filepath" = "$FILE_PATH" ] || [ "$filepath" = "__all__" ]; then
            TIME_DIFF=$((NOW - timestamp))
            if [ "$TIME_DIFF" -lt 300 ]; then
                exit 0
            fi
        fi
    done < "$INVESTIGATION_CONFIRMATION_FILE"
fi

# 未調查就嘗試編輯，阻止
TASK_DESC=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("description","")[:50])' "$FIX_TASK_JSON" 2>/dev/null || echo "")

cat >&2 << EOF

═══════════════════════════════════════════════════════════════
🚫 Investigation Gate
═══════════════════════════════════════════════════════════════

目標檔案：$FILE_PATH
任務：$TASK_DESC

❌ 尚未記錄調查結果，不建議直接修改程式碼。

task JSON 缺少 investigation.rootCause 和 investigation.reproduction。
請先完成調查，再編輯程式碼：

1. 記錄根因假設到 task JSON 的 investigation.rootCause
2. 記錄重現方式到 task JSON 的 investigation.reproduction
3. 或執行 /debug-tips 查詢經驗庫
4. 或手動解鎖：

   echo "\$(date +%s)|${FILE_PATH}|manual_override" >> "${INVESTIGATION_CONFIRMATION_FILE}"

═══════════════════════════════════════════════════════════════
EOF

exit 2
