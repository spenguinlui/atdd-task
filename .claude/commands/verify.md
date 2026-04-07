---
description: 確認已部署任務在 production 正常運作
---

# Verify Deployed Task

確認已部署的任務在 production 環境中正常運作，將狀態從 `deployed` 轉為 `verified`（真正完成）。

## 執行步驟

1. **找到 deployed 任務**：呼叫 `atdd_task_list(status='deployed')`。
   - 如果沒有 deployed 任務 → 提示「沒有待驗證的任務」
   - 如果有多個 → 列出清單讓用戶選擇

2. **顯示任務資訊**：
   ```
   📦 待驗證任務：[{project}] {description}
   🏷️ 類型：{type}
   📍 部署時間：{deployedAt}
   ⏳ 已部署：{天數} 天
   ⚠️ 風險等級：{riskLevel}
   ```

3. **確認驗證**：詢問用戶
   ```
   你已經在 production 驗證過此功能嗎？
   - 功能正常運作？
   - 沒有發現新的 bug？
   - 相關功能沒有受到影響？
   ```

4. **執行狀態更新**：觸發 `task-state-update.md` 的 Event 5 `task-verified`
   - verified_by: "user"
   - 移動 JSON 檔案：`deployed/` → `completed/`
   - 更新 Kanban

5. **輸出結果**：
   ```
   ✅ 任務已驗證完成：[{project}] {description}
   狀態：deployed → verified → completed
   驗證方式：人工確認
   ```
