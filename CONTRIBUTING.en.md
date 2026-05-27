> 🌐 [繁體中文](CONTRIBUTING.md) | **English**

# ATDD Hub — Maintainer Guide

This document is for engineers who need to extend or maintain the ATDD Hub framework itself.  
If you are a PM / RD / business user running tasks, see [README.md](README.md).

---

## Architecture Overview

ATDD Hub is structured around three planes:

```
Orchestrator plane (User issues slash command)
    ↓
Commands plane (.claude/commands/*.md)
    ↓  Task() or run-agent-codex.sh (per agent-engines.yml)
Agent plane (.claude/agents/*.md)
    ↓  atdd_* MCP tools
MCP state plane (tasks / specs / domains / knowledge)
```

**Core design**: Context between agents is not passed through conversation — everything lands in MCP state. This lets `/continue` resume from any session or engine, and enables the same agent prompt to be delegated to different engines (Claude, GPT-via-codex, etc.).

### Main modules

| Module | Path | Description |
|--------|------|-------------|
| Slash commands | `.claude/commands/` | 40 command markdown orchestrators |
| Shared fragments | `.claude/commands/shared/` | Logic shared across commands |
| Agents | `.claude/agents/` | 7 agent prompts (specist / tester / coder / style-reviewer / risk-reviewer / gatekeeper / curator) |
| Hooks | `.claude/hooks/` | Shell entry points (≤100 lines) + `lib/` (Python business logic) |
| Config | `.claude/config/` | Engine registry, budget, tool safety, confidence, project list |
| Scripts | `.claude/scripts/` | Agent dispatch scripts (`run-agent-codex.sh`) |
| Experiments | `experiments/` | Outer evaluation set (cross-version framework quality comparison) |

---

## Directory Structure

```
atdd-task/
├── requirements/{project}/  # Requirement documents (BA analysis output)
├── specs/{project}/         # Acceptance criteria (Given-When-Then)
├── tasks/{project}/         # Task tracking
│   ├── active/              #   In-progress task JSON
│   ├── completed/           #   Completed tasks
│   └── failed/              #   Failed tasks
├── epics/{project}/         # Epic management
├── tests/{project}/         # E2E test suites
│   └── suites/{suite-id}/   #   Scenario definitions + execution records
├── domains/{project}/       # Domain knowledge base (local cache)
├── knowledge/               # Knowledge schema definitions
├── debug-knowledge/         # Debug experience library
├── acceptance/              # Acceptance framework config (profiles / templates)
├── style-guides/            # Code style guides (Ruby / JS / Python)
├── docs/                    # Operation documentation
├── experiments/             # Outer eval experiment sets
└── .claude/
    ├── agents/              # 7 agent prompts
    ├── commands/            # 40 slash commands + shared/
    ├── config/              # Project configuration
    ├── hooks/               # Hook scripts + lib/
    └── scripts/             # run-agent-codex.sh etc.
```

---

## How Wiring Works

### settings.json — Event bindings

Hooks are mounted in `.claude/settings.json` by "event + matcher".

| Hook script | Event / Matcher | Check |
|-------------|----------------|-------|
| `guard-skill-invoke.sh` | PreToolUse / Skill | Prevent subagents from self-invoking slash commands |
| `validate-agent-call.sh` | PreToolUse / Task | Stage allows this agent + confidence ≥95% hard block |
| `validate-deliverables.sh` | PreToolUse / Task | Previous stage deliverables complete |
| `enforce-e2e-decision.sh` | PreToolUse / atdd_task_update | Explicit E2E decision required before leaving requirement |
| `confidence-gate.sh` | PreToolUse / Write\|Edit | Knowledge confidence (domains/) + fix investigation pre-check |
| `protect-e2e-mode.sh` | PreToolUse / Write\|Edit | Prevent agent from self-modifying E2E mode |
| `validate-spec-format.sh` | PostToolUse / Write | spec / BA report format + technical language leak check |
| `workflow-router.sh` | UserPromptSubmit | `/continue` auto-injects stage transition guidance |
| `validate-review-persisted.sh` | SubagentStop | reviewer findings have been persisted |
| `record-metrics.sh` | SubagentStop | Auto-record agent metrics |

### hooks/

- **Entry scripts**: Target ≤100 lines; read stdin, do basic checks, call lib.
- **`lib/`**: Python business logic, independently testable.
- **`lib/hooklog.sh`**: Writes `.hook-log.jsonl`, recording trigger/pass/block events for observability.

### config/

| File | Purpose |
|------|---------|
| `agent-engines.yml` | Engine registry per agent (claude / codex + model) |
| `budget.yml` | Default `maxToolUses` (150) / `maxTokens` (2M) limits; overridable per task in the `budget` field |
| `tool-safety.yml` | Side-effect labels for every MCP tool / dangerous command (read / mutating / destructive) |
| `projects.yml` | Supported project IDs and local paths (follow `projects.yml.example` format) |
| `confidence/` | Requirement / knowledge confidence dimension + weight definitions |

### Agent dispatch (Claude vs GPT)

`shared/agent-dispatch.md` consults `agent-engines.yml` before every agent call:
- `engine: claude` (default) → native `Task(subagent_type=X)`; hooks fire normally.
- `engine: codex` → `run-agent-codex.sh X ...`; GPT-via-codex executes; **in-agent hooks do not fire** → orchestrator must run equivalent plane-1 checks after codex returns (see patch-up table in `shared/agent-dispatch.md`).

---

## How to Extend

### Add a new slash command
1. Create `.claude/commands/<name>.md`.
2. Extract shared logic to `shared/<name>.md` if needed.
3. Add a row to the command list in `README.md`.

### Add or modify an agent
1. Edit (or create) `.claude/agents/<name>.md`.
2. Add a row in `agent-engines.yml` (default `engine: claude`).
3. If new deliverables need validation, add rules in `hooks/lib/validate_deliverables.py`.

### Delegate an agent to GPT
1. Edit `.claude/config/agent-engines.yml`; change the agent's `engine` to `codex` (optionally add `model: gpt-5.5`).
2. **Prerequisites**: `codex login` complete; `~/.codex/config.toml` has `[mcp_servers.atdd]` / `[mcp_servers.atdd-admin]` (copy command/args/env from `.mcp.json`).
3. **Verify plane-1 patch-up**: Patch-up table in `shared/agent-dispatch.md` must cover this agent (in-agent hooks are disabled after delegation; orchestrator must compensate).
4. Test with one low-risk task in supervised mode before enabling in production.
5. **Trade-off**: codex 0.133 exec requires `--dangerously-bypass-approvals-and-sandbox` (full-access).

> `specist` / `curator` have human-in-the-loop interactions (AskUserQuestion) — do not delegate to headless engines.

### Add a new hook
1. Create `.claude/hooks/<name>.sh` (≤100 lines; heavy logic in `lib/<name>.py`).
2. Add the event + matcher binding in `settings.json`.
3. Call `lib/hooklog.sh` at the end to record the trigger result.

### Add a new project
Follow `.claude/config/projects.yml.example` format; add project id + path to `projects.yml`.

### Adjust budget limits
- Global: edit `maxToolUses` / `maxTokens` in `.claude/config/budget.yml`.
- Per task: override in the task JSON `budget` field; does not affect the default.

---

## Design Rationale

### Why MCP state instead of conversation memory
Conversation memory disappears when the session ends and cannot be shared across engines. MCP state lets `/continue` resume from any session — this is the foundation of the pluggable engine mechanism. Side effect: agents like reviewer must do read-merge-write (cannot assume state is in memory).

### Why confidence is a hard block, not a soft warning
Soft warnings are easily ignored by AI. A hard block (hook exit 2) ensures specist cannot proceed to the specification stage when requirements are unclear, preventing all downstream agents from working in the wrong direction.

### Why hook entry points must be ≤100 lines
Entry points over 100 lines indicate business logic leaking into the hook layer. Moving it to `lib/` makes the entry point readable and the lib independently testable.

### Why the outer eval is separate from the inner gatekeeper
The inner gatekeeper answers: "is this task good?" The outer eval (`experiments/atdd-harness-quality/`) answers: "after changing an agent prompt or swapping a model, did overall framework quality go up or down?" These cannot substitute for each other.

### Engine delegation security model (Plane-1 / Plane-2)
- **Plane-2 (in-agent hooks)**: Fires during Claude subagent execution; budget-gate, safety-gate, etc. live here.
- **Plane-1 (orchestrator)**: The `/continue` / `/feature` command layer; survives any delegation.
- **Delegation = Plane-2 silently disabled**: Every delegated agent's Plane-2 guarantees must be patched at Plane-1, or they become silent gaps. Patch-up record is in `shared/agent-dispatch.md`.

### Self-verify infrastructure

Makes "commit without verifying" an OS-level impossibility. Three-piece kit:

- `experiments/atdd-eval/run-self-verify.sh` — single entry point, runs all `test-*.sh`
- `experiments/atdd-eval/test-*.sh` — wiring-specific scorers (per the four Patterns; header marks `# pattern: A|B|C|D`)
- `experiments/atdd-eval/coverage.json` — data dashboard (scorers / check totals / mechanism coverage)
- `.claude/hooks/self-verify-on-stop.sh` + `settings.json` Stop registration — any scorer failing → exit 2 physically blocks session end

**Four Patterns** (pick one when writing a new scorer, don't invent):

| Pattern | When | How |
|---|---|---|
| **A. Single source of truth + drift detection** | Config / wiring cross-file consistency | Hardcode source of truth, parse N files to compare |
| **B. Trigger + assert** | Whether the hook / middleware gets triggered correctly | Build stdin / env, invoke hook, assert exit / stderr |
| **C. Scorer + METRICS line** | Behavioral quality / agent output | Controlled instance + ground truth + quantification (e.g., `eval-coder.sh`) |
| **D. Snapshot + diff** | Whether side effects are correct | Snapshot pre-run, compare post-run |

**Current landing progress**: 7 scorers / 58 checks / **47% mechanism coverage (7/15)** — `coverage.json.mechanisms_inventory.uncovered` lists the remaining 8 (validate-deliverables / validate-agent-call / protect-e2e-mode / guard-skill-invoke / workflow-router / record-metrics — 6 hooks — plus coder-eval / tester-eval — 2 Pattern C scorers).

**Steps to add a new scorer**:

1. Write `experiments/atdd-eval/test-<name>.sh`, header `# pattern: A|B|C|D`
2. `chmod +x`; runner picks it up automatically
3. Run `bash experiments/atdd-eval/generate-coverage.sh` to update `coverage.json` (auto-computes scorers/checks/totals; `mechanisms_inventory.total / uncovered` maintained manually)
4. Run `bash experiments/atdd-eval/run-self-verify.sh` to confirm all green

### Maintainer lab (behavioral comparison / agent×model eval)

Maintainer-only; runnable but burns tokens. **These never appear in the viewer's README** — they are meaningless to viewers.

| Command / script | Purpose |
|---|---|
| `/eval-coder <project> <ticket>` | Compare engines on a **real ticket** for code-fixing ability — `gold` (real human fix) + `claude:claude-sonnet-4-6` + `codex:gpt-5.5` each run in a sandbox; hidden acceptance tests judge pass/fail; report tokens / cost / wall time |
| `bash experiments/atdd-eval/eval-reviewer.sh` | Same-ticket comparison for a review task (controlled instance + ground truth) |
| `bash experiments/atdd-eval/eval-specist.sh` / `eval-tester.sh` / `eval-gatekeeper.sh` | Pattern C scorer entry points for the matching agent |
| `bash experiments/atdd-eval/run-matrix.sh` | Batch matrix across agent × model (resumability marker; restart-safe if docker / session quota dies mid-run) |
| `python experiments/atdd-eval/aggregate.py` | Aggregate raw matrix results into a readable report |
| `bash experiments/atdd-eval/list-candidates.sh <project>` | List candidate tickets for comparison (sorted by edit size; pick large edits or you can't tell engines apart) |

> Token counts across engines are **not directly comparable**: the codex CLI's "tokens used" is a grand total that includes cache; Claude's `input_tokens + output_tokens` excludes cache → similar magnitudes are misleading. Compare `pass/total` primarily; tokens only as a within-engine trend.

---

## How to Validate Changes

| Validation | How to trigger | Expected result |
|------------|----------------|-----------------|
| Budget ceiling | Create task JSON exceeding `maxToolUses` | Hard halt before next tool call; warning at 80% |
| Outer eval | `experiments/atdd-harness-quality/run.sh` ≥3 runs | Comparable scores; regression visible |
| Destructive confirmation | Trigger a tool marked `destructive` in `tool-safety.yml` | Confirmation prompt with consequence description |
| Hook size | `wc -l .claude/hooks/*.sh` | All entry points ≤100 lines |
| Hook log | Trigger any hook, then `cat .claude/hooks/.hook-log.jsonl` | Trigger/block record present |
| Stale knowledge | `/knowledge-stale` + create a stale node | Correctly marked stale; same-slug conflict blocked |
| Engine delegation | Set `risk-reviewer` to `engine: codex`, run a review task | findings land in correct MCP nested path; `/continue` unaffected; plane-1 fuse active |
| **Self-verify suite** | `bash experiments/atdd-eval/run-self-verify.sh` | All 7 scorers green (any scorer drift → exit 1 + Stop hook blocks session end) |
| **Interactive model picker** | `/continue {task_id}` reaching Step 2.9 | Menu pops: "Which model for {agent} this run?" first option marked Recommended (from `agent-engines.yml`); skipped in headless mode or with `--model` flag |

---

## Reporting Issues

Framework issues or extension discussions: `spenguin100@gmail.com`
