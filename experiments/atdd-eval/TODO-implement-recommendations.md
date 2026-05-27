# TODO：落地 eval 推薦 + subagent 開跑前的 model 選單

> 來源：`results-2026-05-24-matrix.md`（5/24 全 6-agent 矩陣）+ `results-2026-05-24-reviewer.md`（5/24 reviewer 深測）。
> 既有基建：`.claude/config/agent-engines.yml`、`.claude/scripts/run-agent-codex.sh`、`.claude/commands/shared/agent-dispatch.md`（5/24 引擎可插拔已落地）。
> 此檔給「另開 session 接續實作」用，自含上下文。

---

## 推薦對應表（這次 eval 的結論）

| Agent | 推薦 model | engine | 為什麼 |
|---|---|---|---|
| specist | Opus 4.7 | claude | 7/7 + 最快（80s） |
| coder | **gpt-5.5** | **codex** | 唯一明顯多修對（39/48 vs Claude 全 32/48；gold 47）|
| tester | Opus 4.7 | claude | 2/3 寫出抓得到 bug 的測試；唯一穩 |
| risk-reviewer | **Sonnet 4.6** | claude | 深度近 Opus（sev 6-7 vs 7-8）、scope 紀律一樣、token 更省（業主指定）|
| style-reviewer | Sonnet 4.6 | claude | 命中穩、token 最省 |
| gatekeeper | Sonnet 4.6 | claude | 規則題；便宜快 |
| curator | （不變） | claude | 本輪未測 |

**Haiku 暫無推薦**——specist rubric 假低分、reviewer 過度標記、coder/tester 撞額度，未看到穩定贏的場景。

---

## Task 1：把推薦變成各 agent 預設

### 1A. Claude 預設（agent `.md` frontmatter）

改動檔案與 `model:` 欄位（5 個 agent）：

| 檔案 | 加/改 frontmatter |
|---|---|
| `.claude/agents/specist.md` | `model: opus` |
| `.claude/agents/tester.md` | `model: opus` |
| `.claude/agents/risk-reviewer.md` | `model: sonnet` |
| `.claude/agents/style-reviewer.md` | 現為 `model: haiku` → 改 **`model: sonnet`** |
| `.claude/agents/gatekeeper.md` | `model: sonnet` |
| `.claude/agents/curator.md` | 不動 |

> `model:` 欄位只吃 Claude 模型別名（`sonnet`/`opus`/`haiku`）。GPT 走 engine-pluggable 那條（見 1B）。

### 1B. coder 走 codex/gpt-5.5（engine 覆寫）

改 `.claude/config/agent-engines.yml`：

```yaml
agents:
  coder:
    engine: codex
    model: gpt-5.5
```

**前置（已落地）**：`~/.codex/config.toml` 已掛 `[mcp_servers.atdd]`/`[mcp_servers.atdd-admin]`；`.claude/scripts/run-agent-codex.sh` 已可跑；continue.md Step 3 已會查引擎分派。

**警語（必看）**：codex exec 跑 MCP **需** `--dangerously-bypass-approvals-and-sandbox`（= 全 shell+網路+磁碟），這是 meta-harness Part G 已記錄的安全代價。coder 是 agentic 編輯、需要 MCP 寫 metrics，因此會吃到 bypass。若要降風險，把 codex 包進 OS 容器跑（Part G G.8.1 列為緩解）。

---

## Task 2：每次進 subagent 前彈 model 選單

### 2A. 哪裡插？

`continue.md` 的 **Step 3「呼叫 next_agent 並記錄 Metrics」開頭**，在「讀 `agent-engines.yml` 決定引擎」**之前**插一段「Step 2.9 互動式 model 選擇」。沒選＝走 `agent-engines.yml` 的 default（即 Task 1 設好的推薦）。

### 2B. 互動格式

用 `AskUserQuestion`（Claude Code 內建工具）：

```
question: "本次 {next_agent} 要用哪個 model？沒選＝預設（推薦）"
header: "Model 選擇"
options:
  - label: "{推薦 model}（Recommended）"
    description: "本 agent 的 eval 推薦（見 results-2026-05-24-matrix.md）"
  - label: "Opus 4.7"
    description: "深度活；最貴"
  - label: "Sonnet 4.6"
    description: "性價比；中等"
  - label: "Haiku 4.5"
    description: "便宜快；可能噪音/格式踩雷"
  # 第 5 個若需 GPT 另加（會觸發 codex bypass）
multiSelect: false
```

每 agent 的「推薦 model」依 Task 1 對應表代入。

### 2C. 怎麼把選擇接到 dispatch？

兩條路擇一：

1. **臨時環境變數覆寫**（最輕）：選擇後設 `EVAL_ONESHOT_MODEL` / `EVAL_ONESHOT_ENGINE`，`agent-dispatch.md`/run-agent-codex.sh 看到就用，沒看到就用 `agent-engines.yml`。
2. **修改 `agent-engines.yml` 寫回**（持久）：選了就改 yml＝改了 default。一般沒人想每次 task 都改 default，**走 1**。

選 GPT 的選項時，dispatch 走 `engine: codex`；選 Claude 三家走 `engine: claude` + 對應 `model:`。

### 2D. 跳過互動的情境

- 自動化跑（`run-matrix.sh`、headless）：偵測 `$ATDD_NO_PROMPT=1` 或 stdin 非 tty → 直接用 default，不彈問題。
- 用戶 `/continue --model gpt-5.5` 這種 inline 旗標 → 直接用旗標，不彈問題。

---

## 驗收（拿一張在審任務跑一次）

1. `/continue {task_id}` 進到「呼叫 next_agent」前 → **看到 model 選單，第一個選項標 `(Recommended)`**。
2. 直接按 Enter（不選）→ agent 跑的 model 等於 `agent-engines.yml` 對應 default（看 agent 完成後 ENGINE_METRICS / Task 回傳）。
3. 選非預設（如 Sonnet）→ agent 跑的 model 換成 Sonnet，其他無感。
4. 把 coder 設成 codex/gpt-5.5、跑 development→review 那次 → codex 路徑跑、findings 仍走原本 MCP 持久化（continue.md 保險絲照守）。

---

## 參考既有檔案（別重造）

- 引擎分派契約：`.claude/commands/shared/agent-dispatch.md`
- 引擎登記表：`.claude/config/agent-engines.yml`
- codex 委派腳本：`.claude/scripts/run-agent-codex.sh`
- meta-harness 設計圖（雙保險、安全代價）：`prescriptions/2026-05-22-atdd-task.md` Part G

## 風險清單

- coder→gpt-5.5：codex 需 full-access bypass，全機器可達（不是只有 worktree）。要不要走 Path 1 是政策決定。
- Sonnet/Haiku 在 tester 本輪數據缺失（撞訂閱 session 額度）→ 若想補完整資料，業主可選設 `ANTHROPIC_API_KEY`（另一額度）再跑 tester。
- 切 model 影響 hook：claude 路徑 hook 照觸發；codex 路徑 in-agent hook 不觸發、靠 plane-1 保險絲（continue.md 持久化驗證）兜底。
