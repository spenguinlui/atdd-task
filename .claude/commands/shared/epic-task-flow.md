# Epic 子任務流程

## 識別 Epic 子任務

### 方式一：顯式指定

標題格式：`{epic-id}:{task-id}`

例如：`erp-period-domain:T2-3`

### 方式二：自動偵測

標題包含 `T{N}-{N}` 模式時自動掃描：

```bash
# 列出專案的所有 Epic
ls epics/{project}/

# 搜尋匹配的任務
grep -l "id: \"T2-3\"" epics/{project}/*/epic.yml
```

## 判斷流程

```
標題輸入
    │
    ▼
符合 {epic-id}:{task-id}？
    │
  ┌─┴─┐
 YES   NO
  │     │
  ▼     ▼
Epic  包含 T{N}-{N}？
子任務   │
流程   ┌─┴─┐
      YES  NO
       │    │
       ▼    ▼
    掃描  一般
    Epic  任務
```

## Epic 子任務處理

### 1. 讀取 Epic 定義

```bash
cat epics/{project}/{epic-id}/epic.yml
```

### 2. 檢查依賴

如果 task 有 `dependencies`，檢查是否已完成。

**未完成依賴時**：
```
⚠️ 任務被阻塞

📦 Epic：{epic-id}
📋 任務：{task-id} - {title}

此任務依賴以下未完成的任務：
• {dep-id}: {dep-title} (status: {status})

請先完成依賴任務後再開始此任務。
```

**停止執行，不建立任務 JSON。**

### 3. 建立任務 JSON

使用標準模板，加入 epic 欄位：

```json
{
  "epic": {
    "id": "{epic-id}",
    "taskId": "{task-id}",
    "phase": "{phase name}"
  }
}
```

### 4. 更新 Epic 狀態

```yaml
- id: "T2-3"
  status: developing
  startedAt: "{ISO timestamp}"
```

### 5. 建立任務 JSON 時保存 Epic 需求路徑

任務 JSON 的 `epic` 欄位必須包含需求文件路徑，確保跨對話 context 不會斷：

```json
{
  "epic": {
    "id": "{epic-id}",
    "taskId": "{task-id}",
    "phase": "{phase name}",
    "requirementPath": "requirements/{project}/{epic-id}-{short_name}.md",
    "baReportPath": "requirements/{project}/{epic-id}-{short_name}-ba.md"
  }
}
```

路徑從 `epic.yml` 的 `requirement.path` 和 `requirement.baPath` 取得。

### 6. 呼叫 Agent

在 prompt 中加入 Epic 上下文。**Epic 需求文件是 binding constraint，不是參考資料**：

```
=== Epic 上下文 ===
Epic ID：{epic-id}
Epic Task ID：{task-id}
Phase：{phase name}

Epic 定義：epics/{project}/{epic-id}/epic.yml

=== Epic 層級需求文件（強制遵守） ===
⚠️ 此子任務隸屬於 Epic，Epic 已完成整體業務需求收斂。
以下文件是已由用戶確認的業務規則，具有約束力：

- Epic Requirement：requirements/{project}/{epic-id}-{short_name}.md
- Epic BA 報告：requirements/{project}/{epic-id}-{short_name}-ba.md

=== 子任務 specist 強制規則 ===
1. **必須先讀取** Epic Requirement（SA 區塊）和 Epic BA 報告，作為本次分析的前提
2. **禁止重新收斂業務邏輯** — Epic BA 已定義整體商務規則，子任務不得推翻或重新詮釋
3. **範圍限縮** — 子任務的 Requirement + BA 只聚焦在本任務負責的部分，引用 Epic BA 的規則而非重新定義
4. **一致性檢查** — 子任務的 BA 驗收條件必須是 Epic BA 驗收條件的子集，不得出現 Epic 未定義的新業務規則
5. 如果分析過程中發現 Epic 層級的規則可能有問題或遺漏，**停下來告知用戶**，不要自行修改

=== 其他 Agent（tester/coder）===
- 必須讀取 Epic Requirement 了解整體背景
- 實作範圍嚴格限制在本子任務的 spec 內
- 不得為了「方便」而修改其他子任務負責的功能
```
