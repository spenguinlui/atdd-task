# AI 決策核心

## 澄清 > 猜測

- 信心度 < 95% → 必須澄清
- 業務邏輯不確定 → 立即停止詢問
- 預設值或格式不明 → 先確認再實作

澄清格式：
> 根據分析，我發現 [具體情況]，但 [不確定點]，請確認應該如何處理？

## 錯誤處理

- 遇到錯誤先聚焦**根因與修復**，不得繞道或切換替代方式
- 正確流程：閱讀錯誤訊息 → 理解根因 → 修復原本做法 → 重新執行
- 只有在確認原本做法**確實不可行**（非單純 bug）時，才提議替代方案

---

# atdd-task 的角色

atdd-task 是 **ATDD 框架本身**：agent 定義、slash command、hook、template、style guide、跨專案共用設定（`.claude/config/`）。

## 任務資料持久化

任務個別資料一律透過 MCP API 存取：

| 資料 | MCP API |
|------|---------|
| 需求 + 技術分析 (SA) | `atdd_task_update(task_id, requirement=...)` |
| BA 報告 | `atdd_task_update(task_id, metadata={"baReport": ...})` |
| Spec (Given-When-Then) | `atdd_task_update(task_id, metadata={"spec": ...})` |
| UL 術語 | `atdd_term_upsert(project, english_term, chinese_term, type, ...)` |
| 商務邏輯知識節點（優先） | `atdd_node_create(project, domain, layer, node_type, slug, ...)` |
| 商務邏輯（fallback） | `atdd_knowledge_create(project, file_type, ...)` |
| 任務狀態、歷史、metrics | `atdd_task_*` 系列 |
| Domain 健康度 | `atdd_domain_upsert(project, name, ...)` |

UL schema 完整定義見 `knowledge/schemas/ul-entry.yml`。

**Why**：集中於 MCP DB 才能支援多專案多任務管理，避免框架與實例混雜。
