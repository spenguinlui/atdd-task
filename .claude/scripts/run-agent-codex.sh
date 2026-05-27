#!/bin/bash
# 將一個 atdd agent 委派給 codex 引擎執行（Path 1：GPT 自走 atdd MCP）
# 設計依據：meta-harness prescriptions/2026-05-22-atdd-task.md Part G（G.8.1 實測確立）
#
# 前置：
#   - codex login 完成
#   - ~/.codex/config.toml 已註冊 [mcp_servers.atdd] / [mcp_servers.atdd-admin]
# 機制：在 hub（atdd-task）以 bypass 模式跑 codex exec，餵原 agent 本體（剝 frontmatter）。
#   codex 自行讀 .claude/config/projects.yml 解析 repo 路徑、走 atdd MCP 讀寫任務。
# 注意：bypass = full-access；in-agent hook 不觸發，持久化等保證由 orchestrator plane-1 補。
#
# Usage: run-agent-codex.sh <agent> <project> <task_id> [title] [type] [model]
set -u

AGENT="${1:?agent name 必填}"
PROJECT="${2:?project 必填}"
TASK_ID="${3:?task_id 必填}"
TITLE="${4:-}"
TYPE="${5:-}"
MODEL="${6:-gpt-5.5}"

HUB="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
AGENT_FILE="$HUB/.claude/agents/${AGENT}.md"
[ -f "$AGENT_FILE" ] || { echo "[run-agent-codex] 找不到 agent 定義：$AGENT_FILE" >&2; exit 1; }
command -v codex >/dev/null 2>&1 || { echo "[run-agent-codex] PATH 找不到 codex CLI" >&2; exit 1; }

# 剝 YAML frontmatter（首兩個 --- 之間），保留 agent 本體
BODY=$(awk 'BEGIN{fm=0} /^---[[:space:]]*$/{fm++; next} fm>=2{print}' "$AGENT_FILE")
[ -n "$BODY" ] || { echo "[run-agent-codex] agent 本體為空（frontmatter 解析失敗？）：$AGENT_FILE" >&2; exit 1; }

PROMPT="專案：$PROJECT
任務標題：$TITLE
任務類型：$TYPE
任務 ID：$TASK_ID

你正以「委派引擎」身分執行以下 atdd agent 的完整職責。重要事項：
- 透過 atdd MCP 工具讀寫任務（atdd_task_get / atdd_task_update 等），工具名以你環境中看到的為準。
- 讀 $HUB/.claude/config/projects.yml 取本專案 path，cd 進該 repo 審查改動檔案。
- 你的 SubagentStop 驗證 hook 不會觸發，Phase 6「持久化 findings 到 MCP」由你自己負全責，務必完成且格式正確（巢狀 reviewFindings.{riskReview|styleReview}）。
- read-merge-write：寫 reviewFindings 前先 atdd_task_get 取既有值合併，勿覆寫其他鍵。

────────── agent 定義（$AGENT）──────────
$BODY"

LAST=$(mktemp -t codex-agent-XXXXXX)
FULL="${LAST}.full"
( cd "$HUB" && codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check \
    -m "$MODEL" --output-last-message "$LAST" "$PROMPT" </dev/null ) >"$FULL" 2>&1
rc=$?

# token 數：codex 把數字放在「tokens used」同行/下一行
TOKENS=$(grep -iA1 'tokens used' "$FULL" 2>/dev/null | grep -oE '[0-9][0-9,]*' | tr -d ',' | tail -1)

echo "───── [engine=codex model=$MODEL agent=$AGENT] 報告 ─────"
if [ -s "$LAST" ]; then
  cat "$LAST"
else
  echo "[run-agent-codex] codex 無最終訊息（rc=$rc）。原始輸出末段："
  tail -20 "$FULL"
fi
echo
echo "ENGINE_METRICS engine=codex model=$MODEL tokens=${TOKENS:-?} rc=$rc"

rm -f "$LAST" "$FULL"
exit "$rc"
