#!/bin/bash
# E2E 模式保護
# Hook: PreToolUse (Write|Edit)
# 用途：防止 agent 自行將 e2eMode 改為 "manual" 繞過 E2E 測試
#
# 唯一合法路徑：用戶下 /e2e-manual → workflow-router.sh 寫授權 flag → 本 hook 放行
#
# 保護範圍：
#   1. e2eMode 被改為 "manual"（需授權 flag）
#   2. testLayers.e2e.required 從 true 被改為 false（testing 階段後禁止）
#
# 輸入：stdin (JSON with tool_input)
# 輸出：exit 0 = 允許, exit 2 = 阻擋

set -e

ATDD_HUB_DIR="${CLAUDE_PROJECT_DIR:?CLAUDE_PROJECT_DIR not set}"
AUTH_FLAG="${ATDD_HUB_DIR}/.claude/.e2e-manual-authorized"

# 從 stdin 讀取 hook input JSON → 暫存檔（避免 heredoc 轉義問題）
HOOK_INPUT_FILE=$(mktemp)
trap "rm -f $HOOK_INPUT_FILE" EXIT
cat > "$HOOK_INPUT_FILE"

# 解析 file_path
FILE_PATH=$(python3 -c "
import sys, json
d = json.load(open('$HOOK_INPUT_FILE'))
print(d.get('tool_input', {}).get('file_path', ''))
" 2>/dev/null || echo "")

# 只檢查 task JSON 檔案（tasks/*/active/*.json）
if [[ ! "$FILE_PATH" =~ tasks/.*/active/.*\.json$ ]]; then
    exit 0
fi

# 如果檔案尚不存在（新建任務），放行
if [ ! -f "$FILE_PATH" ]; then
    exit 0
fi

# ─── Python 驗證 ───
python3 - "$HOOK_INPUT_FILE" "$FILE_PATH" "$AUTH_FLAG" << 'PYEOF'
import json, os, re, sys, time

hook_input_file = sys.argv[1]
file_path = sys.argv[2]
auth_flag_path = sys.argv[3]

with open(hook_input_file) as f:
    hook_input = json.load(f)

tool_name = hook_input.get('tool_name', '')
tool_input = hook_input.get('tool_input', {})

errors = []


def check_auth_flag():
    """Check if /e2e-manual authorization exists and is recent (< 10 min)."""
    if not os.path.isfile(auth_flag_path):
        return False
    try:
        with open(auth_flag_path) as f:
            line = f.readline().strip()
        ts = int(line.split('|')[0])
        return (time.time() - ts) < 600
    except Exception:
        return False


def read_current_task():
    """Read the current task JSON."""
    with open(file_path) as f:
        return json.load(f)


# ═══ Write Tool ═══
if tool_name == 'Write':
    new_content = tool_input.get('content', '')
    if not new_content:
        sys.exit(0)

    try:
        new_task = json.loads(new_content)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    current_task = read_current_task()

    # Check 1: e2eMode → "manual"
    current_mode = current_task.get('acceptance', {}).get('e2eMode', None)
    new_mode = new_task.get('acceptance', {}).get('e2eMode', None)

    if new_mode == 'manual' and current_mode != 'manual':
        if not check_auth_flag():
            errors.append(
                'e2eMode 被改為 "manual"，但沒有 /e2e-manual 授權。\n'
                '   只有用戶下 /e2e-manual 命令才能切換為手動 E2E 模式。'
            )

    # Check 2: e2e.required true → false (after testing)
    current_e2e = current_task.get('acceptance', {}).get('testLayers', {}).get('e2e', {})
    new_e2e = new_task.get('acceptance', {}).get('testLayers', {}).get('e2e', {})
    current_required = current_e2e.get('required') if isinstance(current_e2e, dict) else None
    new_required = new_e2e.get('required') if isinstance(new_e2e, dict) else None

    if current_required is True and new_required is False:
        if current_task.get('status', '') != 'testing':
            errors.append(
                'testLayers.e2e.required 從 true 被改為 false。\n'
                '   E2E 測試需求在 testing 階段確定後不可關閉。'
            )

# ═══ Edit Tool ═══
elif tool_name == 'Edit':
    old_string = tool_input.get('old_string', '')
    new_string = tool_input.get('new_string', '')

    # Check 1: e2eMode → "manual"
    manual_pattern = r'"?e2eMode"?\s*[:=]\s*"?manual"?'
    if re.search(manual_pattern, new_string) and not re.search(manual_pattern, old_string):
        if not check_auth_flag():
            errors.append(
                'Edit 將 e2eMode 改為 "manual"，但沒有 /e2e-manual 授權。\n'
                '   只有用戶下 /e2e-manual 命令才能切換為手動 E2E 模式。'
            )

    # Check 2: e2e required true → false
    if re.search(r'"required"\s*:\s*false', new_string) and re.search(r'"required"\s*:\s*true', old_string):
        current_task = read_current_task()
        if current_task.get('status', '') != 'testing':
            errors.append(
                'Edit 將 e2e.required 改為 false。\n'
                '   E2E 測試需求在 testing 階段確定後不可關閉。'
            )


# ═══ Output ═══
if errors:
    desc = ''
    try:
        t = read_current_task()
        pid = t.get('projectId', '')
        desc = t.get('description', '')[:40]
        desc = f"[{pid}] {desc}"
    except:
        pass

    print("", file=sys.stderr)
    print("═══════════════════════════════════════════════════════════════", file=sys.stderr)
    print("🚫 E2E Mode Protection — E2E 模式保護", file=sys.stderr)
    print("═══════════════════════════════════════════════════════════════", file=sys.stderr)
    print("", file=sys.stderr)
    if desc:
        print(f"任務：{desc}", file=sys.stderr)
    print(f"目標檔案：{os.path.basename(file_path)}", file=sys.stderr)
    print("", file=sys.stderr)
    print("❌ 阻擋項目：", file=sys.stderr)
    for e in errors:
        print(f"   • {e}", file=sys.stderr)
    print("", file=sys.stderr)
    print("💡 如需切換手動 E2E，請用戶執行 /e2e-manual 命令。", file=sys.stderr)
    print("   Agent 不得自行修改 E2E 測試模式。", file=sys.stderr)
    print("═══════════════════════════════════════════════════════════════", file=sys.stderr)
    sys.exit(2)

sys.exit(0)
PYEOF

EXIT_CODE=$?
exit $EXIT_CODE
