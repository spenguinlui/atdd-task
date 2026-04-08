#!/bin/bash
# ATDD 工作流程路由器
# Hook: UserPromptSubmit
# 用途：在用戶輸入 /continue 時，自動注入正確的階段轉移指令
#
# 輸入：透過環境變數 TOOL_INPUT 取得用戶輸入
# 輸出：注入路由資訊到 AI 的 context

set -e

ATDD_HUB_DIR="${CLAUDE_PROJECT_DIR:?CLAUDE_PROJECT_DIR not set}"
TASKS_DIR="${ATDD_HUB_DIR}/tasks"
USER_PROMPT="${TOOL_INPUT:-}"

# /e2e-manual 授權 flag（供 protect-e2e-mode.sh 驗證）
if [[ "$USER_PROMPT" == "/e2e-manual"* ]]; then
    echo "$(date +%s)|e2e-manual|user_command" > "${ATDD_HUB_DIR}/.claude/.e2e-manual-authorized"
fi

# ─── Skill 授權 flag（供 guard-skill-invoke.sh 驗證）───
# 偵測用戶輸入的 /xxx 命令，寫入一次性授權 flag
if [[ "$USER_PROMPT" =~ ^/([a-zA-Z][a-zA-Z0-9_-]*) ]]; then
    SKILL_NAME="${BASH_REMATCH[1]}"
    AUTH_DIR="${ATDD_HUB_DIR}/.claude/.skill-authorized"
    mkdir -p "$AUTH_DIR"
    echo "$(date +%s)|${SKILL_NAME}|user_command" > "${AUTH_DIR}/${SKILL_NAME}"
fi

# 只處理 /continue 命令（後續路由邏輯）
if [[ "$USER_PROMPT" != "/continue"* ]]; then
    exit 0
fi

# 找到所有活躍的任務
ACTIVE_TASKS=$(find "$TASKS_DIR"/*/active -name "*.json" 2>/dev/null || echo "")

if [ -z "$ACTIVE_TASKS" ]; then
    echo "═══ 工作流程路由 ═══"
    echo "⚠️ 沒有進行中的任務"
    echo "請先使用 /feature 或 /fix 啟動任務"
    echo "═══════════════════"
    exit 0
fi

# 計算活躍任務數量
TASK_COUNT=$(echo "$ACTIVE_TASKS" | wc -l | tr -d ' ')

# 如果有多個任務，使用最近更新的
if [ "$TASK_COUNT" -gt 1 ]; then
    ACTIVE_TASKS=$(ls -t $ACTIVE_TASKS 2>/dev/null | head -1)
fi

TASK_JSON="$ACTIVE_TASKS"

# 解析任務資訊
TASK_TYPE=$(python3 -c "import json; print(json.load(open('$TASK_JSON')).get('type', ''))" 2>/dev/null || echo "")
TASK_STATUS=$(python3 -c "import json; print(json.load(open('$TASK_JSON')).get('status', ''))" 2>/dev/null || echo "")
TASK_DESC=$(python3 -c "import json; print(json.load(open('$TASK_JSON')).get('description', '')[:40])" 2>/dev/null || echo "")
PROJECT_ID=$(python3 -c "import json; print(json.load(open('$TASK_JSON')).get('projectId', ''))" 2>/dev/null || echo "")
TASK_ID=$(python3 -c "import json; print(json.load(open('$TASK_JSON')).get('id', ''))" 2>/dev/null || echo "")
E2E_MODE=$(python3 -c "import json; print(json.load(open('$TASK_JSON')).get('acceptance', {}).get('e2eMode', ''))" 2>/dev/null || echo "")
E2E_REQUIRED=$(python3 -c "import json; print(json.load(open('$TASK_JSON')).get('acceptance', {}).get('testLayers', {}).get('e2e', {}).get('required', False))" 2>/dev/null || echo "False")

# 輸出路由資訊
echo "═══ 工作流程路由 ═══"
echo "📋 任務：[$PROJECT_ID] $TASK_DESC"
echo "🏷️ 類型：$TASK_TYPE"
echo "📍 階段：$TASK_STATUS"
echo ""

# 根據任務類型和當前階段決定下一步
get_next_step() {
    local type="$1"
    local status="$2"

    case "$type" in
        "feature")
            case "$status" in
                "requirement")
                    echo "→ 下一步：specification"
                    echo "→ 動作：呼叫 specist 撰寫完整規格"
                    ;;
                "specification")
                    echo "→ 下一步：testing"
                    echo "→ 動作：呼叫 tester 生成測試"
                    ;;
                "testing")
                    echo "→ 下一步：development"
                    echo "→ 動作：呼叫 coder 實作代碼"
                    ;;
                "development")
                    if [ "$E2E_REQUIRED" = "True" ] && [ -z "$E2E_MODE" ]; then
                        echo "⚠️ 需要選擇 E2E 模式"
                        echo "→ /continue - 自動化 E2E"
                        echo "→ /e2e-manual - 人工 E2E"
                    else
                        echo "→ 下一步：review"
                        echo "→ 動作：呼叫 risk-reviewer"
                    fi
                    ;;
                "review")
                    echo "→ 下一步：gate"
                    echo "→ 動作：呼叫 gatekeeper 做最終檢查"
                    ;;
                "gate")
                    echo "✅ 任務已通過 Gate"
                    echo "→ /done 直接結案（傳統流程）"
                    echo "→ /done --deploy 進入部署驗證（推薦）"
                    ;;
                "deployed")
                    echo "📦 任務已部署，等待驗證"
                    echo "→ /verify 確認 production 正常"
                    echo "→ /escape 回報 production 問題"
                    ;;
            esac
            ;;
        "fix")
            case "$status" in
                "requirement")
                    echo "→ 下一步：testing（跳過 specification）"
                    echo "→ 動作：呼叫 tester 生成測試"
                    ;;
                "testing")
                    echo "→ 下一步：development"
                    echo "→ 動作：呼叫 coder 修復 bug"
                    ;;
                "development")
                    echo "→ 下一步：review"
                    echo "→ 動作：呼叫 risk-reviewer"
                    ;;
                "review")
                    echo "→ 下一步：gate"
                    echo "→ 動作：呼叫 gatekeeper 做最終檢查"
                    ;;
                "gate")
                    echo "✅ 任務已通過 Gate"
                    echo "→ /done 直接結案（傳統流程）"
                    echo "→ /done --deploy 進入部署驗證（推薦）"
                    ;;
                "deployed")
                    echo "📦 任務已部署，等待驗證"
                    echo "→ /verify 確認 production 正常"
                    echo "→ /escape 回報 production 問題"
                    ;;
            esac
            ;;
        "test")
            case "$status" in
                "requirement")
                    echo "→ 下一步：testing"
                    echo "→ 動作：呼叫 tester 執行 E2E 測試"
                    ;;
                "testing")
                    echo "→ 下一步：gate（跳過 development）"
                    echo "→ 動作：呼叫 gatekeeper 彙總結果"
                    ;;
                "gate")
                    echo "✅ 測試任務完成"
                    echo "→ 使用 /close 結案"
                    ;;
            esac
            ;;
        "refactor")
            case "$status" in
                "requirement")
                    echo "→ 下一步：specification"
                    echo "→ 動作：呼叫 specist 撰寫重構計畫"
                    ;;
                "specification")
                    echo "→ 下一步：testing"
                    echo "→ 動作：呼叫 tester 確認現有測試覆蓋"
                    ;;
                "testing")
                    echo "→ 下一步：development"
                    echo "→ 動作：呼叫 coder 執行重構"
                    ;;
                "development")
                    echo "→ 下一步：review"
                    echo "→ 動作：平行呼叫 style-reviewer 和 risk-reviewer（refactor 預設含風格審查）"
                    ;;
                "review")
                    echo "→ 下一步：gate"
                    echo "→ 動作：呼叫 gatekeeper 做最終檢查"
                    ;;
                "gate")
                    echo "✅ 任務已通過 Gate"
                    echo "→ /done 直接結案（傳統流程）"
                    echo "→ /done --deploy 進入部署驗證（推薦）"
                    ;;
                "deployed")
                    echo "📦 任務已部署，等待驗證"
                    echo "→ /verify 確認 production 正常"
                    echo "→ /escape 回報 production 問題"
                    ;;
            esac
            ;;
        *)
            echo "⚠️ 未知的任務類型：$type"
            ;;
    esac
}

get_next_step "$TASK_TYPE" "$TASK_STATUS"

echo ""
echo "📁 任務 JSON：$TASK_JSON"
echo "═══════════════════════"
