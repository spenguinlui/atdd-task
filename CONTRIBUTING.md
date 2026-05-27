> 🌐 **繁體中文** | [English](CONTRIBUTING.en.md)

# ATDD Hub — 維護者指南

本文件面向需要擴充或維護 ATDD Hub 框架本身的工程師。  
如果你是使用框架跑任務的 PM / RD / 業務，請看 [README.md](README.md)。

---

## 架構概覽

ATDD Hub 由三個平面構成：

```
Orchestrator 平面（User 下 slash command）
    ↓
Commands 平面（.claude/commands/*.md）
    ↓  Task() 或 run-agent-codex.sh（依 agent-engines.yml）
Agent 平面（.claude/agents/*.md）
    ↓  atdd_* MCP tools
MCP 狀態平面（tasks / specs / domains / knowledge）
```

**核心設計**：Agent 間 context 不靠對話傳遞，全部落到 MCP state。這讓 `/continue` 可以從任意 session、任意引擎恢復，也讓同一份 agent prompt 可以委派給不同引擎（Claude、GPT-via-codex 等）。

### 主要模組

| 模組 | 路徑 | 說明 |
|------|------|------|
| Slash commands | `.claude/commands/` | 40 個指令的 markdown orchestrator |
| Shared 片段 | `.claude/commands/shared/` | 多個 command 共用邏輯 |
| Agents | `.claude/agents/` | 7 個 agent prompt（specist / tester / coder / style-reviewer / risk-reviewer / gatekeeper / curator）|
| Hooks | `.claude/hooks/` | Shell 主體（≤100 行）+ `lib/`（Python 重邏輯）|
| Config | `.claude/config/` | 引擎登記、預算、工具安全、信心度、專案清單 |
| Scripts | `.claude/scripts/` | Agent 委派腳本（`run-agent-codex.sh`）|
| Experiments | `experiments/` | 外層評估集（跨版本框架品質比對）|

---

## 目錄結構

```
atdd-task/
├── requirements/{project}/  # 需求文件（BA 分析產出）
├── specs/{project}/         # 驗收規格（Given-When-Then）
├── tasks/{project}/         # 任務追蹤
│   ├── active/              #   進行中任務 JSON
│   ├── completed/           #   已完成任務
│   └── failed/              #   失敗任務
├── epics/{project}/         # Epic 管理
├── tests/{project}/         # E2E 測試套件
│   └── suites/{suite-id}/   #   場景定義 + 執行記錄
├── domains/{project}/       # 領域知識庫（本地快取）
├── knowledge/               # 知識 schema 定義
├── debug-knowledge/         # Debug 經驗庫
├── acceptance/              # 驗收框架配置（profile / template）
├── style-guides/            # 程式碼風格指南（Ruby / JS / Python）
├── docs/                    # 操作文件
├── experiments/             # 外層 eval 實驗集
└── .claude/
    ├── agents/              # 7 個 agent prompt
    ├── commands/            # 40 個 slash command + shared/
    ├── config/              # 專案配置
    ├── hooks/               # hook 腳本 + lib/
    └── scripts/             # run-agent-codex.sh 等
```

---

## Wiring 怎麼運作

### settings.json — 事件綁定

Hook 以「事件 + matcher」掛載在 `.claude/settings.json`。

| Hook 腳本 | 事件 / Matcher | 檢查內容 |
|-----------|----------------|----------|
| `guard-skill-invoke.sh` | PreToolUse / Skill | 擋 subagent 自行呼叫 slash command |
| `validate-agent-call.sh` | PreToolUse / Task | 階段允許呼叫該 agent + 信心度 ≥95% 硬阻擋 |
| `validate-deliverables.sh` | PreToolUse / Task | 前一階段交付物是否完整 |
| `enforce-e2e-decision.sh` | PreToolUse / atdd_task_update | 轉移出 requirement 前必須有明確 E2E 決策 |
| `confidence-gate.sh` | PreToolUse / Write\|Edit | 知識信心度（domains/）+ fix 調查前置檢查 |
| `protect-e2e-mode.sh` | PreToolUse / Write\|Edit | 防 agent 自行竄改 E2E 模式 |
| `validate-spec-format.sh` | PostToolUse / Write | spec / BA 報告格式 + 技術語言洩漏檢查 |
| `workflow-router.sh` | UserPromptSubmit | `/continue` 自動注入階段轉移指引 |
| `validate-review-persisted.sh` | SubagentStop | reviewer findings 是否已持久化 |
| `record-metrics.sh` | SubagentStop | 自動記錄 agent metrics |

### hooks/

- **主體腳本**：目標 ≤100 行，讀 stdin、做基本判斷、呼叫 lib。
- **`lib/`**：Python 重邏輯，可獨立測試。
- **`lib/hooklog.sh`**：寫 `.hook-log.jsonl`，記錄每次觸發/通過/阻擋，供觀測。

### config/

| 檔案 | 作用 |
|------|------|
| `agent-engines.yml` | 每個 agent 的引擎登記（claude / codex + model）|
| `budget.yml` | 預設 `maxToolUses`（150）/ `maxTokens`（2M）上限；任務 JSON 的 `budget` 欄可覆寫 |
| `tool-safety.yml` | 每個 MCP tool / 危險命令的副作用標記（read / mutating / destructive）|
| `projects.yml` | 支援的專案 ID 與本地路徑（照 `projects.yml.example` 格式）|
| `confidence/` | 需求信心度 / 知識信心度的維度 + 權重定義 |

### Agent 委派（Claude vs GPT）

`shared/agent-dispatch.md` 在每次 agent 呼叫前查 `agent-engines.yml`：
- `engine: claude`（預設）→ 原生 `Task(subagent_type=X)`，hook 正常觸發。
- `engine: codex` → `run-agent-codex.sh X ...`，GPT-via-codex 執行；**in-agent hook 不觸發** → orchestrator 返回後補等效的 plane-1 檢查（見 `shared/agent-dispatch.md` 補洞表）。

---

## 怎麼擴充

### 加一個新 Slash Command
1. 在 `.claude/commands/<name>.md` 新增 markdown。
2. 跨 command 共用邏輯抽到 `shared/<name>.md`。
3. 在 `README.md` 指令清單補一列。

### 加或改一個 Agent
1. 編輯（或新增）`.claude/agents/<name>.md`。
2. 在 `agent-engines.yml` 補一列（預設 `engine: claude`）。
3. 新交付物若需驗收，在 `hooks/lib/validate_deliverables.py` 補規則。

### 把 Agent 改用 GPT 跑
1. 編輯 `.claude/config/agent-engines.yml`，把目標 agent 改為 `engine: codex`（可加 `model: gpt-5.5`）。
2. **前置**：`codex login` 完成；`~/.codex/config.toml` 加 `[mcp_servers.atdd]` / `[mcp_servers.atdd-admin]`（照 `.mcp.json` 的 command/args/env）。
3. **確認 plane-1 補洞**：`shared/agent-dispatch.md` 補洞表必須涵蓋此 agent（委派後 in-agent hook 失效，orchestrator 須補等效檢查）。
4. 先用一張低風險任務做監督式 live 端到端測試，確認後再正式啟用。
5. **代價**：codex 0.133 exec 需要 `--dangerously-bypass-approvals-and-sandbox`（full-access）。

> `specist` / `curator` 有人在環內互動（AskUserQuestion），不適合委派 headless 引擎。

### 加一個新 Hook
1. 在 `.claude/hooks/<name>.sh` 新增主體（≤100 行；重邏輯進 `lib/<name>.py`）。
2. 在 `settings.json` 加事件 + matcher 綁定。
3. 末段呼叫 `lib/hooklog.sh` 記錄觸發結果。

### 加一個新 Project
照 `.claude/config/projects.yml.example` 格式在 `projects.yml` 加 project id + 路徑。

### 調整預算上限
- 全局：`.claude/config/budget.yml` 的 `maxToolUses` / `maxTokens`。
- 單任務：任務 JSON 的 `budget` 欄覆寫，不影響預設值。

---

## 設計考量

### 為什麼用 MCP 狀態而不是對話記憶
對話記憶隨 session 消失、不能跨引擎共用。MCP state 讓 `/continue` 從任意 session 恢復，也是可插拔引擎的基礎。副作用：reviewer 等 agent 必須 read-merge-write（不能假設 state 在記憶裡）。

### 為什麼信心度是硬阻擋而不是軟提醒
軟提醒容易被 AI 忽略。硬阻擋（hook exit 2）保證 specist 在需求不清時無法進入規格階段，防止後續所有 agent 做錯方向的工作。

### 為什麼 hook 主體要 ≤100 行
主體過長代表業務邏輯滲入 hook 層。拆到 `lib/` 後：主體可讀、lib 可獨立測試。

### 為什麼外層 eval 獨立於 inner gatekeeper
Inner gatekeeper 回答「這張任務好不好」；outer eval（`experiments/atdd-harness-quality/`）回答「改了 agent prompt 或換了 model，框架整體品質升還是降」。兩者不能互替。

### 引擎委派的安全模型（Plane-1 / Plane-2）
- **Plane-2（in-agent hook）**：Claude subagent 執行中觸發，budget-gate / safety-gate 等在此層。
- **Plane-1（orchestrator）**：`/continue` / `/feature` 等 command 層，任何委派都倖存。
- **委派 = Plane-2 靜默失效**：每委派一個 agent，其 Plane-2 保證必須在 Plane-1 補等效，否則是靜默漏洞。補洞記錄在 `shared/agent-dispatch.md`。

### 自驗基建（self-verify infrastructure）

讓「沒驗就 commit」變成 OS 級不可能事件。三件套：

- `experiments/atdd-eval/run-self-verify.sh` — 跑所有 `test-*.sh` 的單一 entry point
- `experiments/atdd-eval/test-*.sh` — wiring 對應的 scorer（依四種 Pattern；檔頭標 `# pattern: A|B|C|D`）
- `experiments/atdd-eval/coverage.json` — 數據面板（scorers / check 總數 / mechanism 覆蓋率）
- `.claude/hooks/self-verify-on-stop.sh` + `settings.json` Stop 註冊 — 任一 scorer 失敗 → exit 2 物理擋住 session 結束

**四 Pattern**（寫新 scorer 時挑一個套，不發明）：

| Pattern | 適用 | 招式 |
|---|---|---|
| **A. 單一真實來源 + drift 偵測** | 配置 / wiring 跨檔一致性 | hardcode 真實來源，parse N 個檔比對 |
| **B. 觸發 + 斷言** | hook / 中介機制是否被正確 trigger | 構造 stdin / env，呼叫 hook，斷 exit / stderr |
| **C. Scorer + METRICS 行** | 行為品質 / agent 輸出 | 受控實例 + ground truth + 量化（如 `eval-coder.sh`）|
| **D. 快照 + Diff** | 副作用是否正確 | 跑前 snapshot、跑後比 |

**目前落地進度**：7 scorer / 58 check / **47% mechanism 覆蓋（7/15）**——`coverage.json.mechanisms_inventory.uncovered` 列出剩 8 個未覆蓋 hook + eval scorer（validate-deliverables / validate-agent-call / protect-e2e-mode / guard-skill-invoke / workflow-router / record-metrics 6 個 hook + coder-eval / tester-eval 2 個 Pattern C scorer）。

**加新 scorer 的步驟**：

1. 在 `experiments/atdd-eval/test-<name>.sh` 寫腳本，檔頭加 `# pattern: A|B|C|D`
2. `chmod +x`，runner 自動撿到
3. 跑 `bash experiments/atdd-eval/generate-coverage.sh` 更新 `coverage.json`（自動算 scorers/checks/totals；`mechanisms_inventory.total / uncovered` 由 builder 維護）
4. 跑 `bash experiments/atdd-eval/run-self-verify.sh` 確認全綠

### 維護者實驗室（行為比較 / agent×model 評測）

僅維護者用，跑得起來但會花 token。**這些不會出現在 viewer 的 README**——對 viewer 沒意義。

| 指令 / 腳本 | 用途 |
|---|---|
| `/eval-coder <project> <ticket>` | 對一張**真實票**比較各引擎改 code 的能力——`gold`（真實人類修復）+ `claude:claude-sonnet-4-6` + `codex:gpt-5.5` 各自在沙箱跑，由隱藏驗收測試判 pass/fail，附 token / cost / 耗時 |
| `bash experiments/atdd-eval/eval-reviewer.sh` | 對一張 review 任務跑同票比較（受控實例 + ground truth） |
| `bash experiments/atdd-eval/eval-specist.sh` / `eval-tester.sh` / `eval-gatekeeper.sh` | 對應 agent 的 Pattern C scorer 入口 |
| `bash experiments/atdd-eval/run-matrix.sh` | 跨 agent × model 的批次矩陣（含 resumability 標記；docker / session quota 中途斷掉可續跑） |
| `python experiments/atdd-eval/aggregate.py` | 彙整矩陣 raw 結果為可讀報告 |
| `bash experiments/atdd-eval/list-candidates.sh <project>` | 列出比較候選票（按改動規模排序，挑大改動才分得出強弱） |

> 跨引擎 token 數**不可直接比較**：codex CLI 報的「tokens used」是含 cache 的 grand total，Claude `input_tokens + output_tokens` 不含 cache → 同數量級也是表象。比 `pass/total` 為主，token 只看同引擎內趨勢。

---

## 怎麼驗證改動

| 驗收項目 | 觸發方式 | 預期結果 |
|----------|----------|----------|
| 預算天花板 | 造超出 `maxToolUses` 的任務 JSON | 下一次工具呼叫前硬 halt；逼近 80% 先警告 |
| 外層 eval | `experiments/atdd-harness-quality/run.sh` ≥3 次 | 輸出可比分數，升降可見 |
| Destructive 確認 | 觸發 `tool-safety.yml` 標 destructive 的工具 | 帶後果說明的確認提示 |
| Hook 大小 | `wc -l .claude/hooks/*.sh` | 主體皆 ≤100 行 |
| Hook 日誌 | 觸發任一 hook 後 `cat .claude/hooks/.hook-log.jsonl` | 有觸發/阻擋記錄 |
| 過期知識 | `/knowledge-stale` 盤點 + 造 stale 節點 | 正確標示 stale；同名 slug 衝突被攔 |
| 引擎委派 | `risk-reviewer` 設 `engine: codex`，跑一張 review | findings 落 MCP 正確巢狀位置；`/continue` 後續無感；plane-1 保險絲生效 |
| **自驗基建** | `bash experiments/atdd-eval/run-self-verify.sh` | 7 scorer 全綠（drift 任一支 → exit 1 + Stop hook 擋本輪結束）|
| **互動 model 選擇** | `/continue {task_id}`，進到 Step 2.9 | 彈 menu「本次 {agent} 用哪個 model？」第一個是 Recommended（讀 `agent-engines.yml`）；headless 或帶 `--model` 旗標時跳過此步 |

---

## 回報問題

框架問題或擴充討論：`spenguin100@gmail.com`
