> 🌐 [繁體中文](README.md) | **English**

# ATDD Hub

Give a requirement to AI, and it will handle requirement clarification, acceptance criteria, tests, implementation, and code review — until the gatekeeper says "ready to ship." You only confirm at key checkpoints.

## What It Does

- Turns vague requirements into clear acceptance criteria (Given / When / Then)
- Automatically generates and runs acceptance tests (browser automation or code tests)
- Implements code to make tests pass
- Performs code quality and security review
- Gatekeeper makes the final GO / NO-GO decision and gives you a manual verification guide
- Manages task progress across multiple projects

## Quick Start

### 1. Set up environment

```bash
cp .env.example .env
# Edit .env and fill in the values (see "Environment Setup" below)
```

### 2. Start your first task

```bash
/feature sf_project, Project approval workflow
```

The AI (requirement analyst) will immediately start asking you questions until it has 95% confidence in the requirements.  
Just answer in your own words — no technical knowledge needed.

### 3. Advance through stages

When each stage is complete:

```bash
/continue    # Advance to the next stage
/status      # Check progress at any time
```

### 4. Review and wrap up

After review is complete:

```bash
/fix-critical    # Fix critical issues (if any)
/continue        # Enter final gate
/done            # After gatekeeper GO: commit and close task
```

## Environment Setup

Copy `.env.example` to `.env` and fill in:

| Variable | Description | How to obtain |
|----------|-------------|---------------|
| `ATDD_SERVER_API_KEY` | ATDD system API key | Request from administrator |
| `TEST_USER_EMAIL` | E2E test account email | Use staging test account |
| `TEST_USER_PASSWORD` | E2E test account password | Use staging test account |
| `CORE_WEB_PATH` | Local path to target project | Absolute path on your machine |
| `AWS_SF_INSTANCE_ID` | AWS instance ID (for deploy) | Confirm with administrator |

The list of supported project IDs is maintained by the administrator — confirm your project is registered before first use.

## How to Use: Common Tasks

### Develop a new feature

```bash
/feature sf_project, User refund request feature
```

AI will: ask about requirements → write acceptance criteria (you confirm) → generate tests → implement code → review → gatekeeper decision.  
At every `/continue`, you can review the previous stage's output before pushing forward.

### Fix a bug

```bash
/fix sf_project, Order page shows wrong amount
```

Simplified flow (skips the spec stage). AI clarifies the error symptoms and expected behavior before fixing.

### Large feature (spanning multiple modules)

```bash
/epic sf_project, Invoice credit system
```

AI first proposes a breakdown plan (sub-tasks and order). You confirm before execution begins.

### Code refactor

```bash
/refactor sf_project, Clean up order settlement logic
```

Same flow as Feature, but the review specifically checks that behavior hasn't changed.

### Check current progress

```bash
/status
```

Lists all active tasks and their current stage, with quick action options.

### Fix after review

When review is complete, AI lists all issues by severity. Choose how much to fix:

```bash
/fix-critical         # Fix Critical only (must fix)
/fix-high             # Fix Critical + High
/fix-all              # Fix all severity levels
```

Then run `/continue` to enter the final gate.

### Close and deploy

```bash
/done      # After gatekeeper GO: commit code + update task status
/deploy    # Deploy to remote server
/verify    # Confirm feature works correctly in production
```

## Workflow Loop: What AI Does, What You Do

Every task runs through the full loop. AI executes automatically for most stages — you only need to act at a few fixed handoff points.

| Stage | AI does automatically | Your turn |
|-------|-----------------------|-----------|
| **Requirement clarification** | Analyzes requirements, asks questions one by one, evaluates confidence | Answer questions, add business rules, until AI says "confidence reached 95%" |
| **E2E decision** | — | When asked "Do you need E2E tests?" → choose (automated / manual / skip) |
| **Spec writing** | Converts requirements into Given / When / Then acceptance criteria | Read the spec to confirm AI understood correctly → `/continue` |
| **Test generation** | Generates and runs acceptance tests based on the spec | If tests need environment setup, follow the prompts → `/continue` |
| **Implementation** | Writes code to make tests pass | No action needed → `/continue` |
| **Quality review** | Performs code style + security review, outputs a graded issue list | Read the list → decide fix scope (`/fix-critical` / `/fix-high` / `/fix-all`) → `/continue` |
| **Gate decision** | Verifies all quality gates, makes GO / NO-GO decision, provides manual verification guide | GO → `/done` to close; NO-GO → address the issues and `/continue` again |

**There are only six human touchpoints**: start the task → answer requirement questions → E2E decision → confirm spec → choose fix scope after review → close after gatekeeper GO. AI runs all other stages automatically.

## Available Commands

### Task lifecycle

| Command | Description |
|---------|-------------|
| `/atdd {natural-language requirement}` | **Natural-language entry**: describe your need in a sentence; AI auto-classifies (feature / fix / refactor / health-check / spec-update) and starts |
| `/feature {project}, {title}` | Start new feature development |
| `/fix {project}, {title}` | Start a bug fix |
| `/refactor {project}, {title}` | Start a code refactor |
| `/test {project}, {title}` | Create a standalone E2E test suite |
| `/epic {project}, {title}` | Create a large feature (split into sub-tasks) |
| `/continue [task_id]` | Advance to the next stage |
| `/status` | View all task progress |
| `/abort [task_id]` | Abandon current task |
| `/done [task_id]` | Close task after gatekeeper GO (commit) |
| `/commit` | **Git commit only**, no task close (when you need staged commits) |
| `/close [task_id]` | Close without deploying |
| `/deploy` | Deploy framework to remote server |
| `/verify [task_id]` | Confirm production is working after deploy |
| `/escape {task_id}, {issue}` | **Production issue report**: escalation flow when a deployed task hits a production issue |

### Post-review fixes

| Command | Description |
|---------|-------------|
| `/fix-critical [task_id]` | Fix Critical issues |
| `/fix-high [task_id]` | Fix Critical + High issues |
| `/fix-all [task_id]` | Fix all issues |

### Knowledge and diagnostics

| Command | Description |
|---------|-------------|
| `/knowledge {project}, {topic}` | Discuss business domain knowledge with AI to enrich or correct the knowledge base |
| `/knowledge-stale [project]` | List knowledge nodes pending re-verification |
| `/domain-diagnose {project}` | Run a domain health diagnosis for a project |
| `/debug-tips` | Get debugging suggestions |

### E2E test management

#### Test suite management

| Command | Description |
|---------|-------------|
| `/test-create {project}, {suite description}` | Create a new E2E test suite |
| `/test-run {project}, {suite-id}` | Run an E2E test suite |
| `/test-list [project]` | List test suites |
| `/test-edit {project}, {suite-id}` | Edit an existing test suite |
| `/test-history {project}, {suite-id}` | View test execution history |
| `/e2e-manual` | E2E test operation guide |

#### Test flow control (used mid-test)

| Command | Description |
|---------|-------------|
| `/test-pause` | Pause the current E2E test, wait for manual intervention |
| `/test-resume` | Resume a paused E2E test |
| `/test-fail` | Mark current test as failed and stop |
| `/test-skip` | Skip the current test step or scenario |
| `/test-revise` | Fix the expected value (system correct, test wrong); pause for confirmation, then continue |

#### Issues found mid-test → spawn follow-up tasks

When testing surfaces work that lives outside the test itself, these commands log issues and spin out tasks:

| Command | Description |
|---------|-------------|
| `/test-feature` | Log missing feature, create a Feature task, continue testing |
| `/test-fix` | Log issue, create a Fix task, continue testing |
| `/test-fix-stop` | Log issue, create a Fix task, **stop** testing |
| `/test-refactor` | Log architectural issue, create a Refactor task, continue testing |
| `/test-knowledge` | Log knowledge gap, stop testing and roll back to the requirement stage |

### Other / help

| Command | Description |
|---------|-------------|
| `/guide` | Show command cheat sheet |

## What Comes Out and How to Verify Success

After a complete task flow, you receive:

| Output | Description |
|--------|-------------|
| Acceptance criteria | Given / When / Then format; confirms AI understood your requirements |
| Automated tests | Code tests that directly verify the feature works correctly |
| Code changes | Implemented commits that pass tests and review |
| Manual verification guide | Step-by-step instructions from the gatekeeper to manually verify in staging / production |

**How to verify success:**

1. **Gatekeeper says GO** — passed all quality gates; ready to ship
2. **Follow the manual verification guide** — check off each acceptance scenario from the gatekeeper's output
3. **`/verify` complete** — production confirmed working; task is truly done

If the gatekeeper says NO-GO, the reason is explained — address it and `/continue` again.

## What It Doesn't Do / Known Limitations

**Doesn't do:**
- Operate directly on production data (all commands limited to local / staging)
- Proceed with implementation before you've confirmed requirements (stops and asks when confidence < 95%)
- Install packages or change system configuration (bundle install, version switching, etc.)
- Modify things you didn't ask for (specist / curator have business confirmation steps and won't expand scope)

**Known limitations:**
- Vaguer requirements mean more clarifying questions — it helps to think through the main business rules before starting
- E2E tests require Chrome open and connectable to staging; staging accounts need corresponding test data
- Some security concerns (injection defense for external sources) require server-side support; framework coverage is partial

## Troubleshooting

| Symptom | Common cause | Fix |
|---------|-------------|-----|
| `/continue` does nothing | Previous stage output incomplete | Read AI's message; complete what's missing and retry |
| AI keeps asking questions, confidence stuck below 95% | Requirements still ambiguous | Add specific business rules or example data |
| E2E tests keep failing | Staging account / test data issue | Verify `.env` account can log into staging; check that test data exists |
| Hook blocks with error message | Quality gate blocked action | AI message explains the specific reason; complete missing items and retry |
| Task stuck, AI not progressing | AI loop or execution limit reached | Run `/abort` to abandon; restart the task; or see [Operation Manual](docs/operation-manual.md) |
| Gatekeeper NO-GO, not sure what to do | Review has critical issues or tests not all passing | Follow gatekeeper report: run `/fix-critical` or go back to clarify requirements with specist |

Full operation guide: [Operation Manual](docs/operation-manual.md)

## Maintenance & Reporting

Framework maintainer: `spenguin100@gmail.com`  
For usage questions, feature feedback, or bug reports, contact directly.  
For framework extension and modifications, see [CONTRIBUTING.md](CONTRIBUTING.md).

## Glossary

| Term | Plain explanation |
|------|-------------------|
| **Confidence** | How certain AI is about the requirements (0–100%). Below 95%, AI keeps asking questions and won't start implementation |
| **specist** (requirement analyst) | The AI role that clarifies requirements and writes acceptance criteria with you |
| **tester** (test engineer) | The AI role that generates and runs tests based on acceptance criteria |
| **coder** (developer) | The AI role that writes code to make tests pass |
| **reviewer** | The AI role that checks code quality and security (split into style review and risk review) |
| **gatekeeper** | The AI role that makes the final GO / NO-GO decision and provides a manual verification guide |
| **curator** (knowledge curator) | The AI role that manages the business knowledge base (domains, ubiquitous language terms) |
| **spec / acceptance criteria** | Acceptance conditions written in "Given (precondition) / When (action) / Then (expected result)" format |
| **E2E test** | Automated test that simulates a real user operating in the browser |
| **Domain** | A functional module within the system (e.g. Invoices, Project Management, User Permissions) |
| **Epic** | A large feature that's too broad for one task; split into multiple sub-tasks (Features / Fixes) |
| **GO / NO-GO** | Gatekeeper's final decision: GO = ready to ship; NO-GO = needs fixes |
| **Confidence gate** | Hard block mechanism: AI cannot proceed when confidence is below the threshold |

---

For more details on workflow, see the [Operation Manual](docs/operation-manual.md).
