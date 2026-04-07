#!/bin/bash
# 階段交付物驗證
# Hook: PreToolUse (Task)
# 用途：在呼叫 ATDD agent 前，驗證前一階段的交付物是否完整
#
# 與 validate-agent-call.sh 分工：
#   validate-agent-call.sh → 驗證「能不能在這個 phase 跑」（工作流程規則）
#   validate-deliverables.sh → 驗證「前一 phase 的交付物是否完整」（交付物規則）
#
# 輸入：TOOL_INPUT 環境變數（JSON: {subagent_type, prompt}）
# 輸出：exit 0 = 通過, exit 2 = 阻擋並顯示訊息

set -e

ATDD_HUB_DIR="${CLAUDE_PROJECT_DIR:?CLAUDE_PROJECT_DIR not set}"
TASKS_DIR="${ATDD_HUB_DIR}/tasks"
PROJECTS_YML="${ATDD_HUB_DIR}/.claude/config/projects.yml"

# ─── 解析 subagent_type ───
SUBAGENT_TYPE=$(echo "$TOOL_INPUT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('subagent_type', ''))" 2>/dev/null || echo "")

if [ -z "$SUBAGENT_TYPE" ]; then
    exit 0
fi

# 只檢查 ATDD 相關的 agents
ATDD_AGENTS="specist tester coder style-reviewer risk-reviewer gatekeeper"
if ! echo "$ATDD_AGENTS" | grep -qw "$SUBAGENT_TYPE"; then
    exit 0
fi

# ─── 找到活躍任務 ───
ACTIVE_TASKS=$(find "$TASKS_DIR"/*/active -name "*.json" 2>/dev/null || echo "")
if [ -z "$ACTIVE_TASKS" ]; then
    exit 0
fi

TASK_COUNT=$(echo "$ACTIVE_TASKS" | wc -l | tr -d ' ')
if [ "$TASK_COUNT" -gt 1 ]; then
    PROMPT=$(echo "$TOOL_INPUT" | python3 -c "import sys, json; print(json.load(sys.stdin).get('prompt', ''))" 2>/dev/null || echo "")
    TASK_ID=$(echo "$PROMPT" | grep -oE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' | head -1 || echo "")
    if [ -n "$TASK_ID" ]; then
        MATCHED=$(echo "$ACTIVE_TASKS" | grep "$TASK_ID" | head -1)
        if [ -n "$MATCHED" ]; then
            ACTIVE_TASKS="$MATCHED"
            TASK_COUNT=1
        fi
    fi
    if [ "$TASK_COUNT" -gt 1 ]; then
        for project_dir in "$TASKS_DIR"/*/active; do
            project_name=$(basename "$(dirname "$project_dir")")
            if echo "$PROMPT" | grep -qi "$project_name"; then
                MATCHED=$(find "$project_dir" -name "*.json" 2>/dev/null | head -1)
                if [ -n "$MATCHED" ]; then
                    ACTIVE_TASKS="$MATCHED"
                    TASK_COUNT=1
                    break
                fi
            fi
        done
    fi
    if [ "$TASK_COUNT" -gt 1 ]; then
        ACTIVE_TASKS=$(ls -t $ACTIVE_TASKS 2>/dev/null | head -1)
    fi
fi

TASK_JSON="$ACTIVE_TASKS"
if [ ! -f "$TASK_JSON" ]; then
    exit 0
fi

# ─── Python 驗證 ───
python3 << PYEOF
import json, os, re, sys

task_path = "$TASK_JSON"
agent = "$SUBAGENT_TYPE"
hub_dir = "$ATDD_HUB_DIR"
projects_yml = "$PROJECTS_YML"

with open(task_path) as f:
    task = json.load(f)

status = task.get('status', '')
task_type = task.get('type', '')

# Load projects config
projects = {}
try:
    import yaml
    with open(projects_yml) as f:
        projects = yaml.safe_load(f).get('projects', {})
except Exception:
    pass

errors = []
warnings = []


def get_path(key):
    """Get path from top level or context."""
    return task.get(key, '') or task.get('context', {}).get(key, '') or ''


def file_exists(rel_path):
    if not rel_path:
        return False
    return os.path.isfile(os.path.join(hub_dir, rel_path))


def read_file(rel_path):
    full = os.path.join(hub_dir, rel_path)
    if os.path.isfile(full):
        with open(full) as f:
            return f.read()
    return ''


# ═══ Determine which check to run ═══

check = None

if agent == 'specist' and status == 'specification':
    check = 'requirement'
elif agent == 'tester' and status == 'testing':
    check = 'specification'
elif agent == 'coder' and status == 'development':
    check = 'testing'
elif agent in ('risk-reviewer', 'style-reviewer') and status == 'review':
    check = 'development'
    # Also check review cycle limit
    review_cycle = task.get('context', {}).get('reviewFindings', {}).get('reviewCycle', 0)
    if isinstance(review_cycle, int) and review_cycle >= 2:
        errors.append(
            f"Review-fix 迴圈已達上限（reviewCycle = {review_cycle}，上限 2）\n"
            "   超過 2 輪的 review-fix 迴圈必須人工介入。\n"
            "   請用戶評估剩餘 findings 是否需要修復，或調整 fixScope。"
        )
elif agent == 'gatekeeper' and status in ('gate', 'review'):
    check = 'review'

if not check:
    sys.exit(0)


# ═══ Requirement Phase Deliverables ═══

if check == 'requirement':
    req_path = get_path('requirementPath')
    if not req_path:
        errors.append("requirementPath 未設定")
    elif not file_exists(req_path):
        errors.append(f"需求文件不存在: {req_path}")
    else:
        content = read_file(req_path)
        if len(content.strip()) < 100:
            errors.append(f"需求文件內容過短 ({len(content.strip())} chars)")

    if task_type == 'feature':
        ba_path = get_path('baReportPath')
        if not ba_path:
            errors.append("baReportPath 未設定（feature 類型必須有 BA 報告）")
        elif not file_exists(ba_path):
            errors.append(f"BA 報告不存在: {ba_path}")


# ═══ Specification Phase Deliverables ═══

elif check == 'specification':
    spec_path = get_path('specPath')
    if not spec_path:
        errors.append("specPath 未設定")
    elif not file_exists(spec_path):
        errors.append(f"規格文件不存在: {spec_path}")
    else:
        content = read_file(spec_path)

        ac_matches = re.findall(r'- \[[ x]\]\s*AC\d+', content)
        scenario_matches = re.findall(r'###\s*Scenario\s+\d+', content)

        if not ac_matches:
            errors.append("規格文件沒有 Acceptance Criteria（格式: - [ ] AC1: ...）")
        if not scenario_matches:
            errors.append("規格文件沒有 Scenario（格式: ### Scenario 1: ...）")

        if ac_matches and scenario_matches:
            if len(scenario_matches) < len(ac_matches):
                warnings.append(
                    f"Scenario 數量 ({len(scenario_matches)}) 少於 AC 數量 ({len(ac_matches)})"
                    f" — 部分 AC 可能沒有對應的驗證場景"
                )

    profile = task.get('acceptance', {}).get('profile', '')
    if not profile:
        errors.append("ATDD Profile 未設定（acceptance.profile）")


# ═══ Testing Phase Deliverables ═══

elif check == 'testing':
    test_layers = task.get('acceptance', {}).get('testLayers', {})
    if not test_layers:
        errors.append("testLayers 為空 — tester 沒有記錄任何測試層")
    else:
        project_id = task.get('projectId', '')
        project_path = projects.get(project_id, {}).get('path', '')

        has_any_files = False
        for layer, info in test_layers.items():
            if not isinstance(info, dict):
                continue
            files = info.get('files', [])
            if files:
                has_any_files = True
                if project_path:
                    for fpath in files:
                        full = os.path.join(project_path, fpath)
                        if not os.path.isfile(full):
                            errors.append(f"測試檔案不存在 [{layer}]: {fpath}")

        if not has_any_files:
            has_fixture = any(
                isinstance(info, dict) and info.get('fixture')
                for info in test_layers.values()
            )
            if not has_fixture:
                warnings.append("testLayers 有定義但沒有列出測試檔案路徑或 fixture")


# ═══ Development Phase Deliverables ═══

elif check == 'development':
    modified = task.get('context', {}).get('modifiedFiles', [])
    if not modified:
        errors.append("modifiedFiles 為空 — coder 沒有記錄任何修改檔案")

    req_path = get_path('requirementPath')
    if req_path and file_exists(req_path) and modified:
        content = read_file(req_path)
        change_sections = re.findall(r'####\s+\d+\.', content)
        if change_sections and len(modified) < len(change_sections):
            warnings.append(
                f"修改檔案數 ({len(modified)}) 少於需求定義的變更區域 ({len(change_sections)})"
                f" — 請確認是否有遺漏"
            )

    results = task.get('acceptance', {}).get('results', {})
    if not results:
        warnings.append("acceptance.results 為空 — 測試是否已執行並通過？")


# ═══ Review Phase Deliverables ═══

elif check == 'review':
    findings = task.get('context', {}).get('reviewFindings', None)
    if findings is None:
        errors.append("reviewFindings 未填寫 — reviewer 沒有記錄審查結果")

    results = task.get('acceptance', {}).get('results', {})
    if not results:
        errors.append("acceptance.results 為空 — 沒有測試結果記錄")


# ═══ Output ═══

if errors or warnings:
    desc = task.get('description', '')[:40]
    project_id = task.get('projectId', '')

    print("", file=sys.stderr)
    print("═══════════════════════════════════════════════════════════════", file=sys.stderr)
    print("🚫 Deliverable Gate — 交付物驗證", file=sys.stderr)
    print("═══════════════════════════════════════════════════════════════", file=sys.stderr)
    print(f"", file=sys.stderr)
    print(f"任務：[{project_id}] {desc}", file=sys.stderr)
    print(f"階段轉移：{check} → {status}", file=sys.stderr)
    print(f"Agent：{agent}", file=sys.stderr)
    print(f"", file=sys.stderr)

    if errors:
        print("❌ 阻擋項目（必須修復）：", file=sys.stderr)
        for e in errors:
            print(f"   • {e}", file=sys.stderr)
        print("", file=sys.stderr)

    if warnings:
        print("⚠️  警告項目（建議檢查）：", file=sys.stderr)
        for w in warnings:
            print(f"   • {w}", file=sys.stderr)
        print("", file=sys.stderr)

    if errors:
        print("💡 請在前一階段補齊交付物後再繼續。", file=sys.stderr)
        print("   缺少的欄位需由對應 agent 在該階段填入任務 JSON。", file=sys.stderr)
        print("═══════════════════════════════════════════════════════════════", file=sys.stderr)
        sys.exit(2)
    else:
        print("═══════════════════════════════════════════════════════════════", file=sys.stderr)
        sys.exit(0)
else:
    print(f"✅ 交付物驗證通過：{check} → {status}")
    sys.exit(0)
PYEOF

EXIT_CODE=$?
exit $EXIT_CODE
