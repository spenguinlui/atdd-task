---
description: 回報已部署任務在 production 發現問題
---

# Escape: Production 問題回報

將已部署的任務標記為 `escaped`（bug 逃逸到 production），並建議建立 fix 票。

## 解析參數

格式：`/escape [問題描述]`（可選，也可在互動中補充）

## 執行步驟

1. **找到 deployed 任務**：呼叫 `atdd_task_list(status='deployed')`。
   - 如果沒有 deployed 任務 → 提示「沒有已部署的任務」
   - 如果有多個 → 列出清單讓用戶選擇

2. **收集問題資訊**：
   - 如果參數有描述 → 使用參數
   - 否則詢問：
     ```
     在 production 發現了什麼問題？
     - 問題現象是什麼？
     - 影響範圍多大？
     ```

3. **執行狀態更新**：觸發 `task-state-update.md` 的 Event 6 `task-escaped`
   - escape_reason: 用戶描述的問題
   - 移動 JSON 檔案：`deployed/` → `escaped/`
   - 更新 Kanban

4. **輸出結果 + 建議 fix**：
   ```
   ⚠️ 任務已標記為 escaped：[{project}] {description}
   問題：{escape_reason}

   建議建立 Fix 票：
   /fix {project}, {建議的 fix 標題}

   新 fix 票的 causation 將自動設定：
   - causedBy.taskId: {escaped_task_id}
   - causedBy.description: {escaped_task_description}
   - discoveredIn: production
   - rootCauseType: 待調查
   ```
