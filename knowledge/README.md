# Knowledge Access Layer (Deprecated)

> **Note**: 本地 `domains/` 目錄和 `knowledge/access/` 讀寫規範已**廢棄**。
> 所有 domain 知識讀寫統一透過 MCP API，由 ATDD Platform DB 管理。

---

## MCP API 對照表

| 用途 | 工具 |
|------|------|
| 列出術語表 | `mcp__atdd__atdd_term_list(project, domain?)` |
| 列出知識條目 | `mcp__atdd__atdd_knowledge_list(project, domain?, file_type?)` |
| 取單筆知識 | `mcp__atdd-admin__atdd_knowledge_get(entry_id)` |
| 列出 domain 健康度 | `mcp__atdd__atdd_domain_list(project)` |
| 取單一 domain | `mcp__atdd-admin__atdd_domain_get(domain_id)` |
| 寫入術語（curator） | `mcp__atdd-admin__atdd_term_upsert` — 結構化欄位：type, definition, business_rules, examples, notes, related_terms, aggregate_root, related_entities |
| 刪除術語（curator） | `mcp__atdd-admin__atdd_term_delete(term_id)` |
| 寫入知識（curator） | `mcp__atdd-admin__atdd_knowledge_create` / `atdd_knowledge_update` / `atdd_knowledge_delete` |
| 寫入 domain（curator） | `mcp__atdd-admin__atdd_domain_upsert` |

### `file_type` 取值

- `business-rules` — 業務規則（VR/ST/CA/AU/CD）
- `strategic` — 商務邏輯、能力、範疇、狀態流程
- `tactical` — 系統設計、Pitfalls、Knowledge Gaps
- `domain-map` — 跨域 Context Mapping、邊界定義

---

## Schema 參考

- 術語：`schemas/ul-entry.yml`
- 規則：`schemas/business-rule.yml`
- 信心度評估：`.claude/config/confidence/knowledge.yml`

---

## 原則

1. **寫入只屬於 curator**：其他 agent 僅能透過讀取 MCP 工具取用知識。
2. **提案優先**：所有知識變更須先生成提案，經用戶確認後才寫入。
3. **最小變更**：使用 `atdd_knowledge_update` 精準修改指定 entry，不要大量重寫。
4. **來源標註**：每筆寫入須在 payload / metadata 記錄 `[用戶]` / `[文件]` / `[code]` / `[推導]`。

---

## 相關

- Curator Agent：`.claude/agents/curator.md`
- Curator Workflow：`.claude/agents/curator/audit-workflow.md`
- Knowledge Command：`.claude/commands/knowledge.md`
