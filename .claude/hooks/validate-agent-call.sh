#!/bin/bash
# ATDD 工作流程驗證腳本
# 用途：在呼叫 Agent 前驗證工作流程狀態
# 輸入：透過環境變數 TOOL_INPUT 取得 Task 工具的參數
# 輸出：exit 0 = 允許, exit 1 = 阻止（並輸出錯誤訊息）

set -e

ATDD_HUB_DIR="${CLAUDE_PROJECT_DIR:?CLAUDE_PROJECT_DIR not set}"
TASKS_DIR="${ATDD_HUB_DIR}/tasks"

# 從 TOOL_INPUT 解析 subagent_type
# TOOL_INPUT 是 JSON 格式，例如：{"subagent_type": "coder", "prompt": "..."}
SUBAGENT_TYPE=$(echo "$TOOL_INPUT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('subagent_type', ''))" 2>/dev/null || echo "")

# 如果沒有 subagent_type，放行（可能不是 ATDD 相關的 agent）
if [ -z "$SUBAGENT_TYPE" ]; then
    exit 0
fi

# 定義 ATDD 相關的 agents
ATDD_AGENTS="specist tester coder style-reviewer risk-reviewer gatekeeper"

# 如果不是 ATDD agent，放行
if ! echo "$ATDD_AGENTS" | grep -qw "$SUBAGENT_TYPE"; then
    exit 0
fi

# 找到所有活躍的任務
ACTIVE_TASKS=$(find "$TASKS_DIR"/*/active -name "*.json" 2>/dev/null || echo "")

if [ -z "$ACTIVE_TASKS" ]; then
    echo "⚠️ 沒有找到活躍的任務，無法驗證工作流程"
    echo "請先使用 /feature 或 /fix 啟動任務"
    exit 1
fi

# 計算活躍任務數量
TASK_COUNT=$(echo "$ACTIVE_TASKS" | wc -l | tr -d ' ')

# 如果有多個任務，嘗試從 prompt 中找到任務 ID 或專案名稱
if [ "$TASK_COUNT" -gt 1 ]; then
    # 嘗試從 prompt 中提取任務資訊
    PROMPT=$(echo "$TOOL_INPUT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('prompt', ''))" 2>/dev/null || echo "")

    # 嘗試匹配任務 ID（UUID 格式）
    TASK_ID=$(echo "$PROMPT" | grep -oE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' | head -1 || echo "")

    if [ -n "$TASK_ID" ]; then
        MATCHED_TASK=$(echo "$ACTIVE_TASKS" | grep "$TASK_ID" | head -1)
        if [ -n "$MATCHED_TASK" ]; then
            ACTIVE_TASKS="$MATCHED_TASK"
            TASK_COUNT=1
        fi
    fi

    # 如果還是有多個，嘗試匹配專案名稱
    if [ "$TASK_COUNT" -gt 1 ]; then
        PROJECTS_YML="${ATDD_HUB_DIR}/.claude/config/projects.yml"
        PROJECT_LIST=$(python3 -c '
import yaml, sys
with open(sys.argv[1]) as f:
    data = yaml.safe_load(f)
for name in data.get("projects", {}):
    print(name)
' "$PROJECTS_YML" 2>/dev/null || echo "")
        for project in $PROJECT_LIST; do
            if echo "$PROMPT" | grep -qi "$project"; then
                MATCHED_TASKS=$(echo "$ACTIVE_TASKS" | grep "/$project/" || echo "")
                if [ -n "$MATCHED_TASKS" ]; then
                    # 取最近更新的任務
                    ACTIVE_TASKS=$(echo "$MATCHED_TASKS" | head -1)
                    TASK_COUNT=1
                    break
                fi
            fi
        done
    fi
fi

# 如果還是有多個任務，取最近更新的
if [ "$TASK_COUNT" -gt 1 ]; then
    ACTIVE_TASKS=$(ls -t $ACTIVE_TASKS 2>/dev/null | head -1)
fi

# 讀取任務 JSON
TASK_JSON="$ACTIVE_TASKS"
if [ ! -f "$TASK_JSON" ]; then
    echo "⚠️ 無法讀取任務檔案"
    exit 1
fi

# 解析任務狀態
TASK_STATUS=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("status",""))' "$TASK_JSON" 2>/dev/null || echo "")
TASK_TYPE=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("type",""))' "$TASK_JSON" 2>/dev/null || echo "")
CONFIDENCE=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("workflow",{}).get("confidence",0))' "$TASK_JSON" 2>/dev/null || echo "0")
ACCEPTANCE_PROFILE=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("acceptance",{}).get("profile",""))' "$TASK_JSON" 2>/dev/null || echo "")
TASK_DESC=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("description","")[:50])' "$TASK_JSON" 2>/dev/null || echo "")
PROJECT_ID=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("projectId",""))' "$TASK_JSON" 2>/dev/null || echo "")

# 驗證邏輯
validate_agent_call() {
    local agent="$1"
    local status="$2"

    case "$agent" in
        "specist")
            # specist 可以在 requirement 或 specification 階段呼叫
            if [ "$status" = "requirement" ] || [ "$status" = "specification" ]; then
                return 0
            fi
            echo "❌ specist 只能在 requirement/specification 階段呼叫"
            echo "   當前狀態：$status"
            return 1
            ;;
        "tester")
            # tester 可以在 testing 階段呼叫
            if [ "$status" = "testing" ]; then
                return 0
            fi
            # 也允許在 development 階段（測試失敗需要補測試）
            if [ "$status" = "development" ]; then
                return 0
            fi
            echo "❌ tester 只能在 testing/development 階段呼叫"
            echo "   當前狀態：$status"
            return 1
            ;;
        "coder")
            # coder 可以在 development 階段呼叫
            if [ "$status" = "development" ]; then
                return 0
            fi
            echo "❌ coder 只能在 development 階段呼叫"
            echo "   當前狀態：$status"
            return 1
            ;;
        "style-reviewer"|"risk-reviewer")
            # reviewers 可以在 review 階段呼叫
            if [ "$status" = "review" ]; then
                return 0
            fi
            echo "❌ $agent 只能在 review 階段呼叫"
            echo "   當前狀態：$status"
            return 1
            ;;
        "gatekeeper")
            # gatekeeper 可以在 gate 階段呼叫
            if [ "$status" = "gate" ]; then
                return 0
            fi
            # 也允許在 review 階段（review 完成後進入 gate）
            if [ "$status" = "review" ]; then
                return 0
            fi
            echo "❌ gatekeeper 只能在 review/gate 階段呼叫"
            echo "   當前狀態：$status"
            return 1
            ;;
        *)
            # 未知的 agent，放行
            return 0
            ;;
    esac
}

# 額外的工作流程檢查
check_workflow_requirements() {
    local agent="$1"
    local status="$2"

    # pre-specification 檢查：信心度（硬阻擋）
    if [ "$agent" = "specist" ] && [ "$status" = "requirement" ]; then
        if [ "$CONFIDENCE" -lt 95 ]; then
            echo "❌ 信心度不足，阻擋進入 specification"
            echo "   當前信心度：${CONFIDENCE}%"
            echo "   需要達到 95% 才能進入 specification"
            echo ""
            echo "   💡 請先澄清需求，提高信心度後再繼續"
            echo "   參考：.claude/config/confidence/requirement.yml"
            return 1
        fi
    fi

    # pre-testing 檢查：ATDD Profile
    if [ "$agent" = "tester" ] && [ "$status" = "testing" ]; then
        if [ -z "$ACCEPTANCE_PROFILE" ]; then
            echo "⚠️ ATDD Profile 檢查"
            echo "   任務缺少 acceptance.profile 設定"
            echo "   建議在 specist 階段設定 profile"
            echo ""
            echo "   💡 這是提醒，不會阻止操作"
        fi
    fi

    return 0
}

# 執行驗證
echo "🔍 ATDD 工作流程驗證"
echo "   任務：[$PROJECT_ID] $TASK_DESC"
echo "   狀態：$TASK_STATUS"
echo "   Agent：$SUBAGENT_TYPE"
echo ""

if validate_agent_call "$SUBAGENT_TYPE" "$TASK_STATUS"; then
    check_workflow_requirements "$SUBAGENT_TYPE" "$TASK_STATUS"
    echo "✅ 驗證通過，允許呼叫 $SUBAGENT_TYPE"
    exit 0
else
    exit 1
fi
