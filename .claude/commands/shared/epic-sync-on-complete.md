# Epic 同步（任務完成時）

> 共用模組：供 `/done` 和 `/close` 在任務結案時同步 Epic 狀態。

## 前提檢查

讀取任務 JSON 的 `epic` 字段：

```json
{
  "epic": {
    "id": "erp-period-domain",
    "taskId": "T2-1",
    "phase": "Phase 2: 核心 UseCases"
  }
}
```

如果沒有 `epic` 字段 → **跳過，不執行以下步驟**。

---

## 步驟 A: 更新 epic.yml

用 Read 工具讀取 `epics/{project}/{epic.id}/epic.yml`。如果檔案不存在 → 跳過 Epic 同步，輸出警告「Epic 定義檔不存在，跳過同步」。

存在時，更新對應任務：

```yaml
phases:
  - name: "Phase 2: 核心 UseCases"
    status: developing  # 如果所有任務完成則改為 completed
    tasks:
      - id: "T2-1"
        title: "..."
        status: completed  # ← 更新這裡
        completedAt: "{ISO timestamp}"
        commit: "{commit hash 或 N/A}"
```

更新 metrics：

```yaml
metrics:
  totalTasks: 30
  completed: 15        # +1
  developing: 0        # -1（如果之前是 developing）
  pending_spec: 15     # （不變）
  progress: 50%        # 重新計算
```

如果 phase 下所有 task 都 completed → phase status 改為 `completed`。

---

## 步驟 B: 更新 tasks.md（如果存在）

讀取 `epics/{project}/{epic.id}/tasks.md`。

**如果檔案不存在 → 跳過此步驟。**

如果存在，更新以下內容：

1. **進度總覽表格**：
   ```markdown
   | 指標 | 數值 |
   |------|------|
   | **已完成任務** | 15 / 32 |  ← 更新
   | **進度百分比** | 47% |       ← 更新
   | **當前 Phase** | Phase 2 進行中 |
   | **下一個任務** | T2-4: ... |  ← 更新為下一個可開始的任務
   ```

2. **已完成任務清單**：
   ```markdown
   | ID | 標題 | commit |
   |----|------|--------|
   | T2-1 | 實作 CreatePeriod UseCase | {commit 或 N/A} |  ← 新增
   ```

3. **對應任務區塊**：
   在任務標題後加上 `✅ COMPLETED`

---

## 步驟 C: 輸出同步結果

```markdown
│ ═══ Epic 同步 ═══                                    │
│ 📦 Epic：{epic.id}                                   │
│ ✅ 任務：{epic.taskId} 已標記完成                    │
│ 📊 進度：{completed}/{total} ({progress}%)           │
```
