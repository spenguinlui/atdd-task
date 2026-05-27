# Agent 引擎分派（engine dispatch）

> 設計依據：meta-harness prescriptions/2026-05-22-atdd-task.md Part G。
> 目的：同一份 agent prompt 可委派給不同引擎——claude 原生 subagent，或 codex 跑 GPT。
> 呼叫 agent 一律先過此分派，再依引擎決定執行方式。

## Step A：解析引擎

優先順序（高 → 低）：

1. **本輪 oneshot 覆寫**：orchestrator（如 `continue.md` Step 2.9）已決定 `chosen_engine` / `chosen_model` → 直接用。
2. **YAML 預設**：讀 `.claude/config/agent-engines.yml`：
   - `agents.<name>.engine` 有值 → 用它；否則用 `defaults.engine`（預設 `claude`）。
   - model：`agents.<name>.model`（codex 預設 `gpt-5.5`；claude 無設則沿用 agent frontmatter）。

claude 路徑要套用 oneshot model：透過 `Task` 工具的 `model` 參數（覆寫 agent frontmatter 的 `model:`）。
codex 路徑要套用 oneshot model：傳給 `run-agent-codex.sh` 的第 6 位置參數。

## Step B-claude（預設）

照 `shared/agent-call-patterns.md`，`Task(subagent_type=<name>, prompt=...)`。
in-agent hook（budget-gate / safety-gate / validate-* 等）正常觸發，無額外處理。

## Step B-codex（Path 1：GPT 自走 atdd MCP）

改用 Bash 執行：

```
.claude/scripts/run-agent-codex.sh <name> <project> <task_id> "<title>" <type> <model>
```

腳本回傳該 agent 的最終報告 + 一行 `ENGINE_METRICS engine=codex model=... tokens=N rc=...`。
把報告當作該 agent 的產出，照各階段輸出規範呈現。

### ⚠️ plane-1 補洞（codex 路徑必讀）

codex 子程序的工具呼叫**不會觸發 Claude Code hook**。失效的 in-agent 保證必須在 orchestrator 補：

| 失效的 hook | plane-1 補法 |
|---|---|
| `validate-review-persisted`（SubagentStop） | codex 跑完，**用 `atdd_task_get` 確認 findings 已落 MCP 正確巢狀位置**（`reviewFindings.riskReview.findings` 為 array；refactor 另需 `styleReview.issues`）。缺失或平鋪 → 退回該引擎重跑 Phase 6。此檢查與 `continue.md` 的「Review 持久化保險絲」相同，review→gate 轉移前本就會跑。 |
| `budget-gate`（PreToolUse） | 對 codex 失效。委派耗用以 `ENGINE_METRICS` 的 tokens 記錄；coder 類委派需另做返回後預算對賬（不在 reviewer scope）。 |
| `safety-gate`（PreToolUse） | bypass = full-access。僅對讀為主的 agent（reviewer/gatekeeper）委派；prompt 維持唯讀意圖。 |

### 前置

- `codex login` 完成。
- `~/.codex/config.toml` 已註冊 `[mcp_servers.atdd]` / `[mcp_servers.atdd-admin]`（command/args 用絕對路徑、env 照搬 `.mcp.json`）。

## Step C：Metrics

- claude：照 `agent-call-patterns.md` 解析 Task 回傳的 `Done (X tool uses · Y tokens)`。
- codex：解析 `ENGINE_METRICS` 的 tokens。
- 兩者皆呼叫 `atdd_task_add_metrics`（codex 路徑標記 engine=codex 以利飛輪比對）。
