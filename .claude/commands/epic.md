---
description: 建立 Epic（大型功能拆分為多個子任務）
---

# Epic Task: $ARGUMENTS

## 解析參數

請解析參數格式：`{project}, {標題}`
- **專案**：逗號前的內容（去除空白）
- **標題**：逗號後的內容（去除空白）

有效的專案 ID：`sf_project`, `core_web`, `core_web_frontend`, `digiwin_erp`, `stock_commentary`, `jv_project`

如果格式不正確或專案不存在，請提示正確格式：
```
用法：/epic {project}, {Epic 標題}
範例：/epic sf_project, 發票折讓體系
```

---

## Epic 建立流程

```
/epic 啟動
    │
    ▼
┌─────────────────────┐
│ Step 1: REQUIREMENT │ ← specist（Epic Requirement 模式）
│    Domain 識別      │
│    需求分析         │
│    信心度 ≥ 95%     │
│    產出：           │
│    • Epic Requirement 文件（SA 整體分析）
│    • Epic BA 報告（純商務語言）
└──────────┬──────────┘
           │ 用戶確認業務規則
           ▼
┌─────────────────────┐
│ Step 2: DECOMPOSE   │ ← specist（Epic Decomposition 模式）
│    Phase 拆分       │
│    子任務識別       │
│    依賴關係         │
│    ⚠️ 只定義「做什麼」
│    ⚠️ 不設計「怎麼做」
└──────────┬──────────┘
           │ 用戶確認/調整拆分
           ▼
┌─────────────────────┐
│ Step 3: CREATE      │ ← 主流程直接執行
│    建立 epic.yml    │
│    建立 Kanban      │
└──────────┬──────────┘
           ▼
      📦 Epic 就緒
```

---

### Step 1: 輸出 Epic 啟動訊息

```markdown
┌──────────────────────────────────────────────────────┐
│ 📦 Epic 建立                                         │
├──────────────────────────────────────────────────────┤
│ 📁 專案：{project}                                   │
│ 📝 標題：{標題}                                      │
│                                                      │
│ 正在進入 Step 1: 業務需求分析...                     │
└──────────────────────────────────────────────────────┘
```

### Step 2: 產生 Epic ID

```bash
# 使用標題的 kebab-case 作為 ID
# 例如：發票折讓體系 → invoice-allowance
```

---

## Step 1: REQUIREMENT — 業務需求收斂

呼叫 specist 進行 Epic 層級的需求分析。

參考：`shared/agent-call-patterns.md` — Epic specist 呼叫（Requirement 階段）

```
Task(
  subagent_type: "specist",
  prompt: "
    專案：{project}
    Epic 標題：{標題}
    Epic ID：{epic-id}
    模式：Epic Requirement

    請執行 Epic Requirement 模式（見 specist agent 定義的「Epic 模式」區塊）。

    **產出路徑**：
    - Requirement：requirements/{project}/{epic-id}-{short_name}.md
    - BA 報告：requirements/{project}/{epic-id}-{short_name}-ba.md

    **Epic 特有指引**：
    - Requirement 的 SA 區塊要涵蓋**整個 Epic 的整體分析**，不只是單一功能
    - BA 報告的「驗收條件」是 **Epic 層級**的驗收條件（整個 Epic 完成後商務上要看到什麼）
    - 不需要 ATDD Profile 選擇（這是子任務層級的事）
    - 不需要 Given-When-Then 規格（這是子任務層級的事）

    **信心度閾值**：≥ 95%（與 Feature 相同）

    完成後輸出：
    1. Domain 識別結果
    2. 信心度與澄清問題（如需）
    3. BA 報告摘要（業務語言，禁止技術術語）
    4. Requirement 檔案路徑
    5. BA 報告檔案路徑
  "
)
```

### Step 1 完成後：等待用戶確認

輸出以下訊息，等待用戶確認業務規則：

```markdown
┌──────────────────────────────────────────────────────┐
│ ✅ Step 1 完成：業務需求分析                          │
├──────────────────────────────────────────────────────┤
│                                                      │
│ 📄 Requirement：requirements/{project}/{epic-id}-{short_name}.md
│ 📄 BA 報告：requirements/{project}/{epic-id}-{short_name}-ba.md
│                                                      │
│ 請確認業務規則：                                      │
│   • 回覆「確認」進入 Step 2（子任務拆分）             │
│   • 回覆調整內容（如：XX 規則需要修正）               │
│   • 回覆「取消」放棄建立                              │
└──────────────────────────────────────────────────────┘
```

**用戶要求調整時**：將修正意見傳回 specist，重新產出 Requirement + BA。

---

## Step 2: DECOMPOSE — 子任務拆分

用戶確認業務規則後，呼叫 specist 進行子任務拆分。

參考：`shared/agent-call-patterns.md` — Epic specist 呼叫（Decomposition 階段）

```
Task(
  subagent_type: "specist",
  prompt: "
    專案：{project}
    Epic 標題：{標題}
    Epic ID：{epic-id}
    模式：Epic Decomposition

    請執行 Epic Decomposition 模式（見 specist agent 定義的「Epic 模式」區塊）。

    **已確認的需求文件**（直接讀取，不要重新分析需求）：
    - Requirement：requirements/{project}/{epic-id}-{short_name}.md
    - BA 報告：requirements/{project}/{epic-id}-{short_name}-ba.md

    **輸出 Epic 提案**：
    使用以下格式，**不要建立任何檔案**：

    ```
    ┌──────────────────────────────────────────────────────┐
    │ 📋 Epic 提案：{標題}                                 │
    ├──────────────────────────────────────────────────────┤
    │                                                      │
    │ 🏷️ 涉及 Domains：{domains}                          │
    │ 📊 信心度：{confidence}%                             │
    │                                                      │
    │ ═══ Phase 1: {Phase 名稱} ═══                        │
    │                                                      │
    │   T1-1 {任務標題}                                    │
    │        類型：{type}                                  │
    │        Domain：{domain}                              │
    │                                                      │
    │   T1-2 {任務標題}                                    │
    │        類型：{type}                                  │
    │        依賴：T1-1                                    │
    │                                                      │
    │ ═══ Phase 2: {Phase 名稱} ═══                        │
    │                                                      │
    │   T2-1 {任務標題}                                    │
    │        類型：{type}                                  │
    │        依賴：T1-2                                    │
    │   ...                                                │
    │                                                      │
    │ ─────────────────────────────────────────────────── │
    │ 總計：{total_tasks} 個子任務                         │
    └──────────────────────────────────────────────────────┘
    ```

    **⛔ 禁止事項**（嚴格遵守）：
    - 禁止設計 code 結構、class 名稱、檔案命名
    - 禁止建議技術實作方式（如：用什麼 pattern、什麼 gem/package）
    - 禁止產出程式碼片段或虛擬碼
    - 子任務標題只描述業務目的（做什麼），不描述技術手段（怎麼做）
    - 這是提案階段，不要建立任何檔案
  "
)
```

### Step 2 完成後：等待用戶確認

```markdown
┌──────────────────────────────────────────────────────┐
│ ✅ Step 2 完成：子任務拆分                            │
├──────────────────────────────────────────────────────┤
│                                                      │
│ 請確認或調整：                                       │
│   • 回覆「確認」建立 Epic 與所有子任務                │
│   • 回覆調整內容（如：T1-3 不需要、合併 T2-1 T2-2）  │
│   • 回覆「取消」放棄建立                              │
└──────────────────────────────────────────────────────┘
```

**用戶要求調整時**：

根據用戶的調整要求更新提案：

- **移除任務**：從提案中刪除指定任務，更新依賴關係
- **合併任務**：將多個任務合併為一個
- **新增任務**：在指定位置新增任務
- **調整依賴**：修改任務間的依賴關係
- **調整 Phase**：移動任務到不同 Phase

調整後重新輸出提案，等待用戶再次確認。

---

## Step 3: CREATE — 建立 Epic 檔案

用戶確認提案後，直接執行以下步驟（不需要再呼叫 Agent）：

### 3a. 建立 Epic 目錄與檔案

建立目錄：`epics/{project}/{epic-id}/`

建立 `epic.yml`：

```yaml
id: {epic-id}
title: {標題}
status: pending_spec
projectId: {project}
createdAt: {ISO timestamp}
completedAt: null

description: |
  {Epic 簡述}

domains:
  - {domain1}
  - {domain2}

requirement:
  path: requirements/{project}/{epic-id}-{short_name}.md
  baPath: requirements/{project}/{epic-id}-{short_name}-ba.md

phases:
  - name: "Phase 1: {name}"
    status: pending_spec
    tasks:
      - id: "T1-1"
        title: "{title}"
        type: "{type}"
        dependencies: []
        status: pending_spec
      - id: "T1-2"
        title: "{title}"
        type: "{type}"
        dependencies: ["T1-1"]
        status: pending_spec

  - name: "Phase 2: {name}"
    status: pending_spec
    tasks:
      - id: "T2-1"
        title: "{title}"
        type: "{type}"
        dependencies: ["T1-2"]
        status: pending_spec

metrics:
  totalTasks: {count}
  completed: 0
  developing: 0
  pending_spec: {count}
  aborted: 0
  progress: 0%
```

### 3b. 更新專案索引

更新或建立 `epics/{project}/_index.yml`：

```yaml
projectId: {project}
updatedAt: {ISO timestamp}

epics:
  - id: {epic-id}
    title: {標題}
    status: pending_spec
    progress: 0%
    directory: ./{epic-id}/
```

### 3c. 子任務執行時建立 JSON

**注意**：Epic 子任務的 JSON **不在建立 Epic 時產生**，而是在執行子任務時（透過 `/feature`、`/fix` 等）才建立。

執行子任務時：
```
/feature {project}, {epic-id}:T1-1
```

此時才透過 `atdd_task_create()` 建立任務：

```json
{
  "id": "{uuid}",
  "type": "{type}",
  "description": "{title}",
  "status": "requirement",
  "projectId": "{project}",
  "domain": "{domain}",
  "epic": {
    "id": "{epic-id}",
    "taskId": "T1-1",
    "phase": "Phase 1: {name}",
    "requirementPath": "requirements/{project}/{epic-id}-{short_name}.md",
    "baReportPath": "requirements/{project}/{epic-id}-{short_name}-ba.md"
  },
  "workflow": {
    "mode": "guided",
    "currentAgent": "specist",
    "confidence": 0
  },
  "agents": [],
  "history": [
    { "phase": "requirement", "timestamp": "{ISO timestamp}" }
  ],
  "context": {},
  "createdAt": "{ISO timestamp}",
  "updatedAt": "{ISO timestamp}"
}
```

**ID 統一規則**：
- **任務 JSON 的 `id`**：使用 UUID（與一般 Feature/Fix 一致）
- **Epic 內部任務 ID**：使用 `T{phase}-{seq}` 格式（如 `T1-1`），存於 `epic.taskId`

### 3d. 更新 Kanban

執行 `shared/kanban-operations.md` 的「新增卡片」，在 Requirement 之前新增 Epic 區塊：

```markdown
## Epic: {標題}
> 📄 **Epic 文件**: [epics/{project}/{epic-id}/epic.yml]
>
> 進度：0/{total_tasks} (0%)

### T1-1 {title}

  - tags: [{domain}, {type}]
  - priority: high
  - workload: Easy
  - defaultExpanded: true
  - steps:
    - [ ] 待開始
    ```md
    **Epic**: {標題}
    **Phase**: Phase 1: {name}
    **依賴**: 無
    **狀態**: pending
    ```

### T1-2 {title}
  ...
```

### 3e. 輸出建立完成訊息

```markdown
┌──────────────────────────────────────────────────────┐
│ ✅ Epic 已建立                                       │
├──────────────────────────────────────────────────────┤
│                                                      │
│ 📦 Epic：{標題}                                      │
│ 🆔 ID：{epic-id}                                     │
│ 📁 檔案：epics/{project}/{epic-id}/epic.yml         │
│ 📄 Requirement：requirements/{project}/{epic-id}-{short_name}.md
│ 📄 BA 報告：requirements/{project}/{epic-id}-{short_name}-ba.md
│                                                      │
│ 📋 子任務：{total_tasks} 個                          │
│   • Phase 1：{count} 個                              │
│   • Phase 2：{count} 個                              │
│   ...                                                │
│                                                      │
│ ═══ 可開始的任務 ═══                                 │
│ • T1-1 {title}（無依賴）                             │
│ • T1-2 {title}（無依賴）                             │
│                                                      │
│ 📝 下一步：                                          │
│   執行 /feature {project}, {epic-id}:T1-1 開始第一個任務 │
│   執行 /status 查看 Epic 進度                        │
└──────────────────────────────────────────────────────┘
```

---

## 當用戶回覆「取消」時

在任何步驟回覆「取消」：

```markdown
┌──────────────────────────────────────────────────────┐
│ ❌ Epic 建立已取消                                   │
├──────────────────────────────────────────────────────┤
│                                                      │
│ 您可以：                                             │
│   • 使用 /feature 建立單一功能任務                   │
│   • 稍後再執行 /epic 重新規劃                        │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## 目錄結構

Epic 建立後的目錄結構：

```
epics/
└── {project}/
    ├── _index.yml             # 專案 Epic 索引
    ├── {epic-id}/
    │   ├── epic.yml           # Epic 狀態定義
    │   ├── README.md          # 詳細說明（可選）
    │   └── diagrams.md        # 流程圖（可選）
    └── {another-epic}/
        └── ...

requirements/
└── {project}/
    ├── {epic-id}-{short_name}.md      # Epic Requirement
    └── {epic-id}-{short_name}-ba.md   # Epic BA 報告

tasks/
└── {project}/
    ├── kanban.md
    ├── active/
    │   ├── {uuid}.json        # 子任務（含 epic.taskId 關聯）
    │   └── ...
    └── completed/
        └── ...
```

**重點**：
- Epic 使用目錄結構（`{epic-id}/epic.yml`），便於存放相關文檔
- Epic 層級有獨立的 Requirement + BA 報告
- 子任務 JSON 使用 UUID 作為檔名，與一般任務一致
- 子任務透過 `epic.taskId` 欄位關聯到 Epic 的 `T1-1` 等內部 ID

---

## 子任務的執行

Epic 的子任務使用標準 command 執行，格式為 `{epic-id}:{task-id}`：

```
/feature {project}, {epic-id}:T1-1    # 執行 feature 類型的子任務
/fix {project}, {epic-id}:T2-3        # 執行 fix 類型的子任務
/test {project}, {epic-id}:T1-5       # 執行 test 類型的子任務
```

**範例**：
```
/feature sf_project, invoice-allowance:T2-1
```

執行時會自動：
1. 讀取 `epic.yml` 確認任務存在
2. 檢查 dependencies 是否已完成（狀態為 `completed`）
3. 如果有未完成的依賴，提示用戶並列出阻塞的任務
4. 建立任務 JSON（使用 UUID），包含 `epic.taskId` 關聯
5. 完成後更新 Epic 的 task status 和 metrics
