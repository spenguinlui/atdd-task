# Knowledge Reader Protocol

> **Purpose**: 定義 Agent 讀取 domain 知識的標準模式。
> 
> **MCP 優先**：所有讀取優先使用 MCP tools（從 DB 取得），local 檔案為 fallback。
> MCP 不可用時自動降級到本地檔案讀取。

---

## 讀取前準備

1. 確認 MCP 可用：嘗試 `atdd_health()`
2. 如果 MCP 可用 → 使用 MCP 讀取路徑（見各操作的「MCP」區塊）
3. 如果 MCP 不可用 → 使用 Local 讀取路徑（見各操作的「Local Fallback」區塊）

---

## 知識文件結構

### ul.md（術語表）

```markdown
## A

### TermName
**中文**: 中文名稱
**定義**: 定義描述
**類型**: Entity | ValueObject | Aggregate | ...
**相關 Entity/Component**: ...
...

## B

### AnotherTerm
...
```

**特點**：
- 按字母 A-Z 排序
- 每個術語以 `### TermName` 開頭
- 欄位以 `**欄位名**:` 格式

### business-rules.md（業務規則）

```markdown
### 1. Validation Rules (資料驗證規則)

#### Rule: RuleName
**ID**: `VR-001`
**Domain**: DomainName
**Description**: ...

### 2. Constraint Rules (約束條件規則)
...

### 3. State Transition Rules (狀態轉換規則)
...
```

**特點**：
- 按規則類別分區（6 大類）
- 每個規則以 `#### Rule:` 開頭
- ID 格式：`{VR|CR|ST|CA|AU|TE|CD}-{三位數字}`

### strategic/{domain}.md（商務邏輯）— 新格式

```markdown
## 商務目的
## 商務能力
## 範疇定義
## 核心概念
## 狀態流程
## 商務規則
## 商務依賴
## 常見問題
```

**特點**：
- 不含 Code Location、欄位定義、技術實作細節
- 讀者：specist、tester、stakeholder

### tactical/{domain}.md（系統設計）— 新格式

```markdown
## Domain Model
### Aggregates（含欄位、Code Location）
### Entities（含欄位、Code Location）
### Value Objects
### Domain Services（含 Code Location）
## Use Cases
## 狀態轉移實作（含 Side Effects）
## Integration 技術細節
## Patterns & Anti-Patterns
## Common Pitfalls
## Related Documentation
```

**特點**：
- 含完整技術細節
- 讀者：specist、coder、style-reviewer

### contexts/{domain}.md（深度知識）— DEPRECATED

> 待遷移至 strategic/ + tactical/。未遷移的專案仍使用此格式。

### domain-map.md（領域邊界）

```markdown
## Domain Overview
...
## Domain Boundaries
### Domain: DomainName
...
## Domain Relationships
### Context Mapping
...
```

---

## 讀取操作

### 1. 術語查詢

#### 查詢 Domain 相關術語

**MCP**：
```
atdd_term_list(project="{project}", domain="{domain}")
```
回傳所有術語含 english_term, chinese_term, context, source。

**Local Fallback**：
```
路徑：domains/{project}/ul.md
方法：搜尋 "**Domain**: {domain}" 收集所有匹配的術語區塊
```

#### 查詢單一術語

**MCP**：
```
atdd_term_list(project="{project}")
```
從結果中篩選 english_term 匹配的項目。

**Local Fallback**：
```
路徑：domains/{project}/ul.md
方法：
  1. 搜尋 "### {TermName}"
  2. 讀取到下一個 "### " 或 "## " 之前的所有內容
```

#### 列出所有術語

**MCP**：
```
atdd_term_list(project="{project}")
```

**Local Fallback**：
```
路徑：domains/{project}/ul.md
方法：搜尋所有 "### " 開頭的行，提取術語名稱
```

### 2. 規則查詢

#### 依 Domain 查詢

**MCP**：
```
atdd_knowledge_list(project="{project}", domain="{domain}", file_type="business-rules")
```

**Local Fallback**：
```
路徑：domains/{project}/business-rules.md
方法：搜尋 "**Domain**: {domain}"，收集所有匹配的規則區塊
```

#### 依 ID 查詢

**MCP**：
```
atdd_knowledge_list(project="{project}", file_type="business-rules")
```
從結果中搜尋 content 包含目標 ID 的項目。

**Local Fallback**：
```
路徑：domains/{project}/business-rules.md
方法：
  1. 搜尋 "**ID**: `{rule_id}`"
  2. 向上找到 "#### Rule:" 作為區塊開始
  3. 向下讀取到下一個 "#### " 或 "### "
```

#### 依類別查詢

**Local**（MCP 無類別欄位，用 local 更直接）：
```
路徑：domains/{project}/business-rules.md
方法：
  1. 找到 "### {N}. {CategoryName}" 區塊
  2. 讀取該區塊內所有規則
```

**類別對照**：
| 類別 | 標題 | ID 前綴 |
|------|------|---------|
| 驗證規則 | Validation Rules | VR |
| 約束規則 | Constraint Rules | CR |
| 狀態轉換 | State Transition Rules | ST |
| 計算規則 | Calculation Rules | CA |
| 授權規則 | Authorization Rules | AU |
| 時間規則 | Temporal Rules | TE |
| 跨域規則 | Cross-Domain Rules | CD |

### 3. 深度知識查詢

#### 商務邏輯（Strategic）

**MCP**：
```
atdd_knowledge_list(project="{project}", domain="{domain}", file_type="strategic")
```
回傳段落級內容。如需完整文件，合併所有段落。

**Local Fallback**：
```
路徑（優先）：domains/{project}/strategic/{domain}.md
路徑（fallback）：domains/{project}/contexts/{domain}.md
方法：Read 整個文件
```

#### 系統設計（Tactical）

**MCP**：
```
atdd_knowledge_list(project="{project}", domain="{domain}", file_type="tactical")
```

**Local Fallback**：
```
路徑（優先）：domains/{project}/tactical/{domain}.md
路徑（fallback）：domains/{project}/contexts/{domain}.md
方法：Read 整個文件
```

> **建議**：完整文件讀取（整個 strategic 或 tactical）時，local 檔案讀取通常更高效。MCP 更適合特定 section 的查詢。

### 4. Domain Health 查詢

**MCP**（優先）：
```
atdd_domain_list(project="{project}")
```
回傳所有 domain 的 health_score, status, fix_rate, coupling_rate, escape_rate。

查詢單一 domain：
```
atdd_domain_get(domain_id="{domain_uuid}")
```

**Local Fallback**：
```
路徑：domain-health.json（~/atdd-hub/domain-health.json）
方法：Read 後查詢 domains.{domain_name}
```

### 5. 邊界查詢

#### Domain 邊界

**Local**（domain-map 未存入 DB，用 local）：
```
路徑：domains/{project}/domain-map.md
方法：
  1. 搜尋 "### Domain: {DomainName}"
  2. 讀取該 Domain 的邊界區塊
```

#### 跨域關係

**MCP**：
```
atdd_coupling_list(project="{project}")
```
回傳 domain 間的 co-occurrence 排序。

**Local Fallback**：
```
路徑：domains/{project}/domain-map.md
方法：在 "## Domain Relationships" 區塊搜尋
```

---

## DDD 視角的讀取

### 識別 Aggregate

```
位置（優先）：tactical/{domain}.md → Domain Model → Aggregates
位置（fallback）：contexts/{domain}.md → Domain Model → Aggregates
尋找：
- Aggregate Root 標記
- 內部 Entity 清單
- Value Object 清單
- Invariants（不變式）
```

### 識別 Domain Event

```
位置（優先）：tactical/{domain}.md → Domain Events
位置（fallback）：contexts/{domain}.md → Domain Events
尋找：
- Event 名稱（過去式動詞）
- Trigger（觸發條件）
- Payload（資料結構）
- Publishers/Subscribers
```

### 識別 Context Mapping

```
位置（優先）：strategic/{domain}.md → 商務依賴
位置（fallback）：domain-map.md → Domain Relationships
模式辨識：
- Customer-Supplier：上游/下游關係
- Conformist：直接使用上游模型
- ACL：有翻譯層
- Shared Kernel：共享模型
- Partnership：互相依賴
- Published Language：穩定發布
```

---

## 快取策略

- **同一對話內**：相同 MCP 查詢結果可快取，避免重複呼叫
- **檔案變更後**：快取失效，需重新讀取
- **跨對話**：不快取，每次重新讀取確保最新

---

## 錯誤處理

| 情況 | 處理方式 |
|------|----------|
| MCP 不可用 | 降級到 local 檔案讀取，記錄警告 |
| 專案目錄不存在 | 提示用戶確認專案 ID |
| Context 文件不存在 | 詢問是否建立新文件 |
| 術語/規則不存在 | 標記為 Knowledge Gap |
| 格式不符預期 | 嘗試模糊匹配，標記為需要修正 |
