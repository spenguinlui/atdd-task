#!/bin/bash
# Spec / BA 報告檔案格式驗證
# Hook: PostToolUse (Write)
# 用途：驗證寫入的 spec 檔案和 BA 報告包含必要區塊
#
# 輸入：透過環境變數取得檔案路徑和內容
# 輸出：exit 0 = 通過, exit 1 = 阻擋（並輸出錯誤訊息）

set -e

# 從 stdin 讀 hook 輸入（PostToolUse JSON：tool_input.file_path / .content）
# 註：原讀 $TOOL_INPUT env（Claude Code 不存在此 env）→ 本 hook 過去是 no-op，此處修復
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path', ''))" 2>/dev/null || echo "")

# 只檢查 .md 檔案
if [[ "$FILE_PATH" != *.md ]]; then
    exit 0
fi

# 取得檔案內容
CONTENT=$(echo "$INPUT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('tool_input',{}).get('content', ''))" 2>/dev/null || echo "")

# ─── BA 報告驗證（requirements/ 目錄的 -ba.md 檔案）───
if [[ "$FILE_PATH" == *"/requirements/"* && "$FILE_PATH" == *-ba.md ]]; then
    echo "🔍 驗證 BA 報告格式..."
    echo "   檔案：$FILE_PATH"

    ERRORS=()

    if ! echo "$CONTENT" | grep -q "## 需求摘要"; then
        ERRORS+=("缺少「## 需求摘要」區塊")
    fi

    if ! echo "$CONTENT" | grep -q "## 業務分析結論"; then
        ERRORS+=("缺少「## 業務分析結論」區塊")
    fi

    if ! echo "$CONTENT" | grep -q "## 驗收條件"; then
        ERRORS+=("缺少「## 驗收條件」區塊")
    fi

    if [ ${#ERRORS[@]} -gt 0 ]; then
        echo ""
        echo "❌ BA 報告格式驗證失敗："
        for error in "${ERRORS[@]}"; do
            echo "   • $error"
        done
        echo ""
        echo "📝 BA 報告必須包含："
        echo "   1. ## 需求摘要"
        echo "   2. ## 業務分析結論"
        echo "   3. ## 驗收條件"
        echo ""
        echo "💡 參考模板：.claude/templates/ba-report-template.md"
        exit 1
    fi

    # ─── 技術語言洩漏檢查 ───
    # 排除：標題行(#)、metadata 行(>)、模板區塊(--- 之後)，只檢查報告本體
    REPORT_BODY=$(echo "$CONTENT" | sed '/^---$/,$d' | grep -v '^#\|^>')

    TECH_WARNINGS=()

    # 檢查 backtick（程式碼片段）
    if echo "$REPORT_BODY" | grep -q '`'; then
        TECH_WARNINGS+=("包含 backtick（\`），疑似程式碼片段或技術名稱")
    fi

    # 檢查 snake_case 模式（連續小寫字母_小寫字母）
    if echo "$REPORT_BODY" | grep -qE '[a-z]+_[a-z]+'; then
        MATCHED=$(echo "$REPORT_BODY" | grep -oE '[a-z]+_[a-z_]+' | head -3 | tr '\n' ', ')
        TECH_WARNINGS+=("包含 snake_case 命名：${MATCHED% ,}（疑似資料表或變數名稱）")
    fi

    # 檢查 Ruby 雙冒號（::）
    if echo "$REPORT_BODY" | grep -qE '[A-Z][a-z]+::[A-Z]'; then
        MATCHED=$(echo "$REPORT_BODY" | grep -oE '[A-Z][a-z]+::[A-Z][a-zA-Z:]+' | head -3 | tr '\n' ', ')
        TECH_WARNINGS+=("包含雙冒號命名：${MATCHED% ,}（疑似 Class/Module 名稱）")
    fi

    # 檢查常見技術術語
    if echo "$REPORT_BODY" | grep -qiE 'eager.?load|N\+1|migration|schema|serializer|decorator|partial|query|preload|callback'; then
        MATCHED=$(echo "$REPORT_BODY" | grep -oiE 'eager.?load|N\+1|migration|schema|serializer|decorator|partial|query|preload|callback' | head -3 | tr '\n' ', ')
        TECH_WARNINGS+=("包含技術術語：${MATCHED% ,}")
    fi

    if [ ${#TECH_WARNINGS[@]} -gt 0 ]; then
        echo ""
        echo "⚠️  BA 報告技術語言洩漏警告："
        for warning in "${TECH_WARNINGS[@]}"; do
            echo "   • $warning"
        done
        echo ""
        echo "📝 BA 報告讀者為 PM 和業務人員，必須全中文、無技術詞彙。"
        echo "💡 參考撰寫指引：.claude/skills/ba-writing/SKILL.md"
        echo ""
        echo "❌ 請改寫後重新提交"
        exit 1
    fi

    echo "✅ BA 報告格式驗證通過（含技術語言檢查）"
    exit 0
fi

# ─── Spec 檔案驗證（specs/ 目錄）───
if [[ "$FILE_PATH" == *"/specs/"* ]]; then
    echo "🔍 驗證 Spec 檔案格式..."
    echo "   檔案：$FILE_PATH"

    ERRORS=()

    # 檢查必要區塊
    if ! echo "$CONTENT" | grep -q "## Acceptance Criteria\|## 驗收標準"; then
        ERRORS+=("缺少 Acceptance Criteria 區塊")
    fi

    if ! echo "$CONTENT" | grep -q "## Scenarios\|## 場景"; then
        ERRORS+=("缺少 Scenarios 區塊")
    fi

    # 檢查 Given-When-Then 結構
    if ! echo "$CONTENT" | grep -qi "given\|when\|then"; then
        ERRORS+=("缺少 Given-When-Then 結構")
    fi

    # 如果有錯誤，輸出並阻擋
    if [ ${#ERRORS[@]} -gt 0 ]; then
        echo ""
        echo "❌ Spec 檔案格式驗證失敗："
        for error in "${ERRORS[@]}"; do
            echo "   • $error"
        done
        echo ""
        echo "📝 Spec 檔案必須包含："
        echo "   1. ## Acceptance Criteria（驗收標準）"
        echo "   2. ## Scenarios（場景）"
        echo "   3. Given-When-Then 結構"
        echo ""
        echo "💡 參考模板：.claude/templates/spec-template.md"
        exit 1
    fi

    echo "✅ Spec 檔案格式驗證通過"
    exit 0
fi

# 非 specs/ 或 requirements/ -ba.md 的檔案：不檢查
exit 0
