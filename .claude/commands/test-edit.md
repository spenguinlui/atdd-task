---
description: 修改現有測試套件（新增、刪除、修改場景或更新 seed）
---

# Test Edit: $ARGUMENTS

## 概述

在測試執行**外**修改現有測試套件。支援新增場景、刪除場景、修改場景、更新 seed 腳本等操作。會呼叫 specist agent 進行場景設計。

**使用時機**：非測試執行期間，需要調整測試套件內容。

**前提**：該套件不能有正在執行的測試（status == "running"）。

## 參數解析

`$ARGUMENTS` = `{project}, {suite-id}, {operation}` 或 `{project}, {suite-id}`

- `project`：專案 ID（必填）
- `suite-id`：套件 ID（必填）
- `operation`：操作類型（可選，不填則進入互動模式）
  - `add`：新增場景
  - `remove`：刪除場景
  - `modify`：修改場景
  - `update-seed`：更新 seed/cleanup 腳本

如果參數不足：
```
⚠️ 請提供專案和套件 ID
用法：/test-edit {project}, {suite-id}, {operation}
      /test-edit {project}, {suite-id}
範例：/test-edit core_web, E2E-A1, add
      /test-edit core_web, E2E-A1
```

## 執行步驟

### Step 1: 驗證套件存在

讀取 `tests/{project}/suites/{suite-id}/suite.yml`。

如果不存在：
```
⚠️ 找不到測試套件：{suite-id}
可用套件請使用 /test-list {project} 查看
```

### Step 2: 檢查沒有執行中的測試

搜尋 `tests/{project}/suites/{suite-id}/runs/*/run.yml`，確認沒有 `status == "running"` 的記錄。

如果有：
```
⚠️ 套件 {suite-id} 有執行中的測試（{run_id}）
請先等待測試完成或使用 /test-fail 停止
```

### Step 3: 顯示當前套件資訊

```markdown
┌──────────────────────────────────────────────────────────────┐
│ 📦 測試套件：{suite-id}                                      │
├──────────────────────────────────────────────────────────────┤
│ 📝 名稱：{suite_name}                                        │
│ 🏷️ Domain：{domain}                                         │
│ 📊 場景數：{scenario_count}                                   │
│                                                              │
│ 場景清單：                                                   │
│   S1 - {scenario_1_name}                                     │
│   S2 - {scenario_2_name}                                     │
│   S3 - {scenario_3_name}                                     │
│   ...                                                        │
└──────────────────────────────────────────────────────────────┘
```

### Step 4: 確定操作（互動模式或直接執行）

如果 operation 未指定，使用 AskUserQuestion 詢問：

```
要對套件 {suite-id} 執行什麼操作？
- add：新增場景
- remove：刪除場景
- modify：修改現有場景
- update-seed：更新 seed/cleanup 腳本
```

### Step 5: 執行操作

#### 5a: add（新增場景）

1. 詢問用戶：新場景的簡要描述
2. 讀取 domain 知識：透過 `mcp__atdd__atdd_term_list` / `atdd_knowledge_list` MCP API 取得
3. 呼叫 specist agent，prompt 包含：
   - 套件現有場景清單
   - domain 知識
   - 用戶描述
   - 指示：生成新場景 YAML（遵循現有場景格式）
4. specist 產出新場景 YAML 到 `tests/{project}/suites/{suite-id}/scenarios/`
5. 更新 `suite.yml` 的 scenarios 清單
6. 更新 `tests/{project}/index.yml` 的場景數和時間戳

#### 5b: remove（刪除場景）

1. 顯示場景清單，詢問要刪除哪個
2. 確認刪除（AskUserQuestion）
3. 刪除場景 YAML 檔案
4. 更新 `suite.yml` 的 scenarios 清單
5. 更新 `tests/{project}/index.yml`

#### 5c: modify（修改場景）

1. 顯示場景清單，詢問要修改哪個
2. 讀取該場景 YAML，顯示內容摘要
3. 詢問用戶：要修改什麼
4. 呼叫 specist agent，prompt 包含：
   - 當前場景 YAML 全文
   - domain 知識
   - 用戶的修改要求
   - 指示：修改場景並生成 revision 記錄
5. specist 修改場景 YAML + 附加 revision 記錄：
   ```yaml
   revisions:
     - id: "REV-{seq}"
       timestamp: "{ISO timestamp}"
       type: "{change_type}"
       source: "test-edit"
       runId: null
       before: { ... }
       after: { ... }
       reason: "{用戶描述的修改原因}"
   ```
6. 更新 `tests/{project}/index.yml` 時間戳

#### 5d: update-seed（更新 seed 腳本）

1. 讀取現有 `fixtures/seed.rb` 和 `fixtures/cleanup.rb`
2. 顯示現有腳本摘要
3. 詢問用戶：要修改什麼
4. 呼叫 specist agent，prompt 包含：
   - 現有腳本內容
   - 場景清單（了解需要什麼資料）
   - 用戶的修改要求
   - 指示：修改 seed/cleanup 腳本
5. specist 產出修改後的腳本
6. 更新 `tests/{project}/index.yml` 時間戳

### Step 6: 輸出變更摘要

```markdown
┌──────────────────────────────────────────────────────────────┐
│ ✅ 套件已更新：{suite-id}                                     │
├──────────────────────────────────────────────────────────────┤
│ 操作：{operation_description}                                │
│                                                              │
│ 變更內容：                                                   │
│   {change_summary}                                           │
│                                                              │
│ 更新的檔案：                                                 │
│   - {file_1}                                                 │
│   - {file_2}                                                 │
│                                                              │
│ 📝 使用 /test-run {project}, {suite-id} 執行測試             │
└──────────────────────────────────────────────────────────────┘
```

## Specist Agent 呼叫模板

### add 操作

```
你正在為 E2E 測試套件 {suite-id} 新增場景。

**套件資訊**：
- Domain: {domain}
- 現有場景：{scenario_list}

**Domain 知識**：
{domain_knowledge_content}

**用戶需求**：
{user_description}

**指示**：
1. 設計新場景，生成符合以下格式的 YAML
2. 場景 ID 為 S{next_number}
3. 遵循現有場景的步驟格式和粒度
4. 將 YAML 寫入 tests/{project}/suites/{suite-id}/scenarios/S{n}-{name}.yml
```

### modify 操作

```
你正在修改 E2E 測試套件 {suite-id} 的場景 {scenario_id}。

**當前場景 YAML**：
{current_scenario_yaml}

**Domain 知識**：
{domain_knowledge_content}

**修改要求**：
{user_modification_request}

**指示**：
1. 修改場景 YAML 中對應的部分
2. 在 revisions 區段新增修訂記錄（source: "test-edit", runId: null）
3. 將修改後的完整 YAML 寫回原檔案
```

## 範例

### 新增場景
```
/test-edit core_web, E2E-A1, add
```

### 互動模式
```
/test-edit core_web, E2E-A1
```

### 修改場景
```
/test-edit core_web, E2E-A1, modify
```

### 更新 seed
```
/test-edit core_web, E2E-A1, update-seed
```
