# Phase 1: Structured Knowledge Nodes

> **Status**: 規劃中（不執行，待審核後再進 TODO 執行）
> **Owner**: specist 流程強化
> **Scope**: 只影響 specist 與 curator 的讀寫路徑；coder / tester / gatekeeper 不擴權
> **Last Updated**: 2026-04-13

## 1. Background

目前知識層（`knowledge_entries` / `knowledge_terms`）是「把 md 檔拆成 row」，`content` 是整塊 markdown，`section` 是自由字串，entry 與 term 完全沒有關聯。這導致：

1. **specist 只能整塊 md 塞進 context**，無法精準取用
2. **Knowledge ↔ Task 沒有追溯**，knowledge_coverage 指標是假的
3. **curator 的 audit 必須靠肉眼比對**，無法機械化驗收
4. **網站無法展開結構**，dashboard / graph 無從投影

### 主要目標

> 讓 specist 能從知識庫精準取出「跟這個任務相關的 entity / rule / term」，以結構化形式帶進 spec，下游 coder / tester 不需讀知識就能拿到足夠線索。

### 非目標

- 不擴充 coder / tester / gatekeeper 的讀取範圍
- 不做 graph UI 或 dashboard（留給 Phase 5）
- 不做 semantic search / embedding（留給 Phase 4）
- 不做 relation 表 / task_knowledge_links（留給 Phase 2-3）

---

## 2. Schema Design

### 2.1 Migration: `005_knowledge_nodes.sql`

策略：**additive**，不動 `knowledge_entries` / `knowledge_terms`，透過 merger 讓新舊並存。

```sql
CREATE TABLE knowledge_nodes (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID NOT NULL REFERENCES organizations(id),
    project     TEXT NOT NULL,
    domain      TEXT NOT NULL,

    layer       TEXT NOT NULL,       -- 'strategic' | 'tactical' | 'rule'
    node_type   TEXT NOT NULL,       -- see Registry
    slug        TEXT NOT NULL,       -- URL-safe
    title       TEXT NOT NULL,
    summary     TEXT NOT NULL,       -- 一句話

    attrs       JSONB NOT NULL DEFAULT '{}'::jsonb,
    body_md     TEXT,                -- 可選，人類敘述

    source_task_id  UUID REFERENCES tasks(id) ON DELETE SET NULL,
    legacy_entry_id UUID REFERENCES knowledge_entries(id) ON DELETE SET NULL,

    stale       BOOLEAN NOT NULL DEFAULT false,
    version     INT NOT NULL DEFAULT 1,
    updated_by  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (org_id, project, domain, layer, node_type, slug),
    CHECK (layer IN ('strategic', 'tactical', 'rule'))
);

CREATE INDEX idx_knowledge_nodes_project_domain ON knowledge_nodes (org_id, project, domain);
CREATE INDEX idx_knowledge_nodes_type           ON knowledge_nodes (org_id, project, layer, node_type);
CREATE INDEX idx_knowledge_nodes_stale          ON knowledge_nodes (org_id, project) WHERE stale = true;
CREATE INDEX idx_knowledge_nodes_attrs          ON knowledge_nodes USING GIN (attrs);

CREATE TRIGGER trg_knowledge_nodes_updated
    BEFORE UPDATE ON knowledge_nodes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


CREATE TABLE knowledge_node_revisions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id         UUID NOT NULL REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    version         INT NOT NULL,
    attrs           JSONB NOT NULL,
    body_md         TEXT,
    change_reason   TEXT,
    source_task_id  UUID REFERENCES tasks(id) ON DELETE SET NULL,
    changed_by      TEXT,
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (node_id, version)
);

CREATE INDEX idx_node_revisions_node ON knowledge_node_revisions (node_id, version DESC);

ALTER TABLE knowledge_terms
    ADD COLUMN node_id UUID REFERENCES knowledge_nodes(id) ON DELETE SET NULL;

CREATE INDEX idx_knowledge_terms_node ON knowledge_terms (node_id) WHERE node_id IS NOT NULL;

ALTER TABLE knowledge_entries
    ADD COLUMN migrated BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN migrated_to_node_id UUID REFERENCES knowledge_nodes(id) ON DELETE SET NULL;
```

> **`migrated` vs `migrated_to_node_id`**：大部分 entry 遷移後同時設 `migrated=true` + `migrated_to_node_id=<uuid>`。但有些純索引性 entry（Change History、核心概念列表等）不產生節點，此時設 `migrated=true` + `migrated_to_node_id=NULL`，表示「已處理但無對應節點」。merger 讀取時以 `WHERE migrated = false` 過濾，不看 `migrated_to_node_id`。

### 2.2 Node Type Registry

Phase 1 固定 12 種 node_type，用 pydantic model 定義 `attrs`。

| Layer | Node Type | 用途 |
|-------|-----------|------|
| strategic | `bounded_context` | 限界上下文 |
| strategic | `context_map` | 上下文關係圖 |
| strategic | `subdomain` | core / supporting / generic |
| tactical | `aggregate` | 聚合根 |
| tactical | `entity` | 實體 |
| tactical | `value_object` | 值物件 |
| tactical | `domain_service` | 領域服務 |
| tactical | `repository` | 儲存庫 |
| tactical | `domain_event` | 領域事件 |
| rule | `invariant` | 聚合內不變條件 |
| rule | `policy` | 跨聚合策略 |
| rule | `business_rule` | 業務規則（含 given/when/then）|

### 2.3 NodeRef: 用 slug 四元組引用

```python
class NodeRef(BaseModel):
    layer: Literal["strategic", "tactical", "rule"]
    node_type: str
    domain: Optional[str] = None   # 跨 domain 時填
    slug: str
```

**不用 UUID**：人類可讀、可 diff、可跨環境搬移。代價是 rename slug 需要一次改多處，Phase 3 的 relation 表會補上 UUID 索引解決這個問題。

### 2.4 Node Type 可迭代性

**可以迭代，但分兩類變動**：

| 變動類型 | 做法 | 風險 |
|---------|------|------|
| 新增 node_type | 加 pydantic class + registry entry | 低 |
| 在既有 type 加 `Optional` 欄位 | 直接加 | 低 |
| 改型別 / Optional 改 required / 刪欄位 | attrs 加 `schema_version`、寫 migration 腳本 | 中 |
| 刪 node_type | deprecation → 資料 migrate → 下線 | 高 |

Phase 1 先不做 `schema_version`，等到真的碰到 breaking change 再加。

---

## 3. 新舊並存策略

`knowledge_service.py` 改用 merger 模式：

```python
def list_entries(org_id, project, domain, file_type, ...):
    # 1. 讀新表
    nodes = _list_nodes(org_id, project, domain,
                        layer=_file_type_to_layer(file_type))
    # 2. 讀舊表（排除已 migrate，包含無對應節點但已處理的）
    legacy = _list_legacy_entries(org_id, project, domain, file_type,
                                  where_extra="AND migrated = false")
    # 3. 合併後統一分頁
    return merge_and_paginate(nodes, legacy)
```

`file_type → layer` 對應：

| 舊 file_type | 新 layer | 過濾 node_type |
|-------------|---------|--------------|
| strategic | strategic | `bounded_context`, `subdomain`, 部分 `value_object` |
| tactical | tactical | `aggregate`, `entity`, `value_object`, `domain_service`, `repository`, `domain_event` |
| business-rules | rule | `invariant`, `policy`, `business_rule` |
| domain-map | strategic | `context_map`, `bounded_context` |

結果：**specist / coder 的 MCP 呼叫不需要改**，底層 merger 自動處理。

---

## 4. Spec 輸出格式升級

specist 產生的 spec 同步寫到兩個地方：

### 4.1 `task.metadata.spec`（人類可讀 markdown）

```markdown
# Spec: 匯出所得申報檔案

## 參考節點
- bounded_context: `core_web/Crowdfund::TaxInfo/strategic/bounded_context/taxinfo`
- aggregate: `core_web/Crowdfund::TaxInfo/tactical/aggregate/tax-info`
- rule: `core_web/Crowdfund::TaxInfo/rule/business_rule/cr-001-export-payment-filter`
- rule: `core_web/Crowdfund::TaxInfo/rule/business_rule/cr-002-roofrental-bypass`
- term: `TaxInfo`, `Payment`, `RoofRentalAccount`

## Given-When-Then
### Scenario: 一般 Due 的成功付款
**Given** 一筆 Due 對應 Payment.status = "success" (business_rule:cr-001-export-payment-filter)
**When** 呼叫匯出功能
**Then** 該筆所得納入匯出檔案
```

### 4.2 `task.metadata.spec_refs`（結構化副本）

```json
{
  "metadata": {
    "spec_refs": {
      "nodes": [
        {"layer": "tactical", "node_type": "aggregate",
         "domain": "Crowdfund::TaxInfo", "slug": "tax-info"},
        {"layer": "rule", "node_type": "business_rule",
         "domain": "Crowdfund::TaxInfo", "slug": "cr-001-export-payment-filter"}
      ],
      "terms": ["TaxInfo", "Payment", "RoofRentalAccount"]
    }
  }
}
```

**下游消費**：
- coder 讀 spec markdown 即可，不碰知識庫
- tester 從 Given-When-Then 生成測試
- gatekeeper 機械化比對 spec_refs 與程式碼變更範圍
- curator（Phase 2）掃 spec_refs 寫 `task_knowledge_links`

---

## 5. TODO List

### Infra / DB

- [ ] **T1** 撰寫 migration `005_knowledge_nodes.sql`（additive）
  - 依賴：無
  - 線上影響：**有**（DDL），需排部署時段
- [ ] **T2** 寫 rollback / down migration
  - 依賴：T1

### Schema / Validation

- [ ] **T3** 建立 `ports/api/services/knowledge_schemas.py`，12 個 pydantic model + NodeRef + validate_attrs()
  - 依賴：無（可與 T1 並行）
  - 線上影響：無
- [ ] **T4** Unit test 覆蓋 12 個 node_type（valid / invalid 各一組）
  - 依賴：T3

### Service / API

- [ ] **T5** `knowledge_service.py` 新增 node CRUD（含 revision 自動寫入）
  - 依賴：T1 + T3
- [ ] **T6** `list_entries` / `list_entries_grouped` 加入 node merger，`file_type → layer` 對應
  - 依賴：T5
  - 線上影響：**中**，改現有讀取路徑，staging 必測
- [ ] **T7** `routers/knowledge.py` 新增 `/nodes` CRUD endpoints
  - 依賴：T5

### MCP

- [ ] **T8** `ports/mcp/server_admin.py` 新增 `atdd_node_create / update / get / list`
  - 依賴：T7
- [ ] **T9** 驗證 `atdd_knowledge_list` / `atdd_term_list` 簽名不變、specist / coder 無痛
  - 依賴：T6

### Agent

- [ ] **T10** 升級 `.claude/agents/specist.md`：加「參考節點」section + `spec_refs` 產出規範 + stale 節點的 clarify 原則
  - 依賴：T6
  - 線上影響：**有**，specist 產出格式改變
- [ ] **T11** 檢查 coder / tester 是否對 spec 格式有 parser 依賴
  - 依賴：T10

### Migration

- [ ] **T12** 半自動 migration script `ports/api/scripts/migrate_entries_to_nodes.py`
  - 功能：LLM 建議節點 shape → curator 審核 → 寫入 + 標記 `migrated_to_node_id`
  - 依賴：T5
- [ ] **T13** 更新 `.claude/agents/curator.md` / `curator/audit-workflow.md` 加 migration 職責
  - 依賴：T8 + T12

### Validation

- [ ] **T14** Staging 端到端驗收（開一個 feature 任務跑完 specist → coder → tester → gatekeeper）
  - 依賴：T1-T11 全部完成
- [ ] **T15** 加 dashboard metric：「已遷移 entry 比例」、「nodes by node_type」
  - 依賴：T12

### 依賴圖

```
T1 ──┬─▶ T2
     └─▶ T5 ──┬─▶ T6 ──┬─▶ T10 ──▶ T11 ──┐
              │        │                  │
              ├─▶ T7 ──▶ T8 ──▶ T13       ├─▶ T14 ──▶ 上線
              │                            │
              └─▶ T12 ────────────────────┘
T3 ──▶ T4 ──▶ (supports T5)
                        T9 (gate before T14)
                        T15 (post-launch)
```

### 排期建議

- **Week 1**：T1 / T2 / T3 / T4 並行（純新增，零風險）
- **Week 2**：T5 / T7 / T8
- **Week 3**：T6 / T9（碰讀取路徑，要謹慎）
- **Week 4**：T10 / T11 / T12 / T13
- **Week 5**：T14 staging → T15 上線後觀測

---

## 6. 實例預覽：`core_web/Crowdfund::TaxInfo` 遷移後長什麼樣

取自線上資料：17 筆 `knowledge_entries` + 10 筆 `knowledge_terms`，遷移後變成 **20 個結構化節點**。以下展示映射表與 3 個代表節點的完整 attrs。

### 6.1 映射表總覽

| 現況 (entries / terms) | → 節點 | layer / node_type | slug |
|------------------------|--------|-------------------|------|
| # | 現況 (entries / terms) | → 節點 | layer / node_type | slug |
|---|------------------------|--------|-------------------|------|
| 1 | strategic: 商務目的 + 商務能力 + 範疇定義 + 常見問題 (合併) | bounded_context | strategic / `bounded_context` | `taxinfo` |
| 2 | strategic: 商務依賴 + domain-map: Context Mapping | context_map | strategic / `context_map` | `taxinfo-context` |
| 3 | domain-map: Subdomain Type = Supporting | subdomain | strategic / `subdomain` | `taxinfo-subdomain` |
| 4 | term: TaxInfo (Aggregate) | aggregate | tactical / `aggregate` | `tax-info` |
| 5 | term: TaxInfoDetail (Entity) | entity | tactical / `entity` | `tax-info-detail` |
| 6 | term: Due (Entity) | entity | tactical / `entity` | `due` |
| 7 | term: Payment (Entity) | entity | tactical / `entity` | `payment` |
| 8 | term: RoofRentalAccount (Entity) | entity | tactical / `entity` | `roof-rental-account` |
| 9 | term: IdentityNumber (VO) | value_object | tactical / `value_object` | `identity-number` |
| 10 | term: IncomeMethod (VO) | value_object | tactical / `value_object` | `income-method` |
| 11 | term: IncomeMonth (VO) | value_object | tactical / `value_object` | `income-month` |
| 12 | term: OtherIncome (Concept) + strategic: OtherIncome 其他所得 | value_object | tactical / `value_object` | `other-income` |
| 13 | strategic: DocumentType 請款憑證形式 | value_object | tactical / `value_object` | `document-type` |
| 14 | term: RoofOwnerUnifiedIncomes (Concept) | value_object | tactical / `value_object` | `roof-owner-unified-incomes` |
| 15 | business-rules: CA-001 IncomeMethod Determination | business_rule | rule / `business_rule` | `ca-001-income-method-determination` |
| 16 | business-rules: CA-002 IdentityNumber Resolution | business_rule | rule / `business_rule` | `ca-002-identity-number-resolution` |
| 17 | business-rules: CA-003 IncomeMonth Conversion | business_rule | rule / `business_rule` | `ca-003-income-month-conversion` |
| 18 | business-rules: CR-001 Export Payment Status Filter | business_rule | rule / `business_rule` | `cr-001-export-payment-filter` |
| 19 | business-rules: CR-002 RoofRental Bypass | business_rule | rule / `business_rule` | `cr-002-roof-rental-bypass` |
| 20 | business-rules: CR-003 Due-Payment Cardinality | invariant | rule / `invariant` | `cr-003-due-payment-cardinality` |
| — | strategic: Change History | ❌ 不建節點（`migrated=true`, `migrated_to_node_id=NULL`）| — | — |
| — | strategic: 核心概念（術語列表） | ❌ 不建節點（已被 entity/VO 吸收）| — | — |
| — | strategic: 商務規則（規則列表） | ❌ 不建節點（已被 business_rule 吸收）| — | — |
| — | strategic: 商務規則 section（索引段落）| ❌ 不建節點（索引功能由查詢取代）| — | — |

**合併效果**：17 entries + 10 terms = 27 份來源 → **20 個結構化節點**，去重後更緊湊，且彼此可交叉引用。4 筆舊 entry 無對應節點但仍標記 `migrated=true`。

### 6.2 範例節點 A: `aggregate / tax-info`

來源：`term: TaxInfo`

```json
{
  "id": "<uuid>",
  "org_id": "00000000-0000-0000-0000-000000000002",
  "project": "core_web",
  "domain": "Crowdfund::TaxInfo",
  "layer": "tactical",
  "node_type": "aggregate",
  "slug": "tax-info",
  "title": "TaxInfo（所得稅申報資料）",
  "summary": "管理群眾集資平台所得稅申報資料的聚合根，支援批次上傳、XLSX 匯出、清單管理。",
  "attrs": {
    "root_entity": {
      "layer": "tactical", "node_type": "entity",
      "domain": "Crowdfund::TaxInfo", "slug": "tax-info"
    },
    "members": [
      {"layer": "tactical", "node_type": "entity",
       "domain": "Crowdfund::TaxInfo", "slug": "tax-info-detail"},
      {"layer": "tactical", "node_type": "entity",
       "domain": "Crowdfund::TaxInfo", "slug": "due"},
      {"layer": "tactical", "node_type": "entity",
       "domain": "Crowdfund::TaxInfo", "slug": "payment"}
    ],
    "invariants": [
      {"layer": "rule", "node_type": "invariant",
       "domain": "Crowdfund::TaxInfo", "slug": "cr-003-due-payment-cardinality"}
    ],
    "repository": null,
    "emits": []
  },
  "body_md": "管理群眾集資平台所得稅申報所需的完整資料（所得人身份、所得金額、所得類別等）。支援批次上傳、XLSX 匯出和清單管理。匯出功能與清單功能是同份資料的不同查詢視角，匯出有額外過濾條件。屋主和一般用戶的所得計算邏輯不同。\n\n相關規則: CA-001, CA-002, CA-003, CR-001, CR-002, CR-003。"
}
```

### 6.3 範例節點 B: `business_rule / ca-001-income-method-determination`

來源：`business-rules: CA-001 IncomeMethod Determination`

```json
{
  "layer": "rule",
  "node_type": "business_rule",
  "slug": "ca-001-income-method-determination",
  "title": "CA-001 IncomeMethod Determination",
  "summary": "所得類別判定：依來源、用戶身份、法人憑證形式、合約方案五級優先序決定 lease_income / other_income / incidental_trading_income。",
  "attrs": {
    "statement": "三種所得類別的判定需按優先序矩陣決定，優先序越高越先適用。",
    "given": [
      "source: 所得資料來源（RoofRentalAccount 或一般 Due）",
      "user_type: 用戶身份（Roof::Owner 或一般用戶）",
      "profile.category: 用戶類別（legal = 法人）",
      "profile.document_type: 請款憑證形式（receipt/payment_slip/invoice/unfilled）",
      "unchanged_contract_programs: 合約方案配置表"
    ],
    "when": "匯出 / 清單產生所得類別欄位時",
    "then": [
      "priority 1: source=RoofRentalAccount → lease_income",
      "priority 2: user_type=Roof::Owner → lease_income",
      "priority 3: profile.legal? AND profile.receipt? → other_income",
      "priority 4: in unchanged_contract_programs → lease_income",
      "priority 5: else → incidental_trading_income"
    ],
    "references": [
      {"layer": "tactical", "node_type": "value_object",
       "domain": "Crowdfund::TaxInfo", "slug": "income-method"},
      {"layer": "tactical", "node_type": "value_object",
       "domain": "Crowdfund::TaxInfo", "slug": "document-type"},
      {"layer": "tactical", "node_type": "entity",
       "domain": "Crowdfund::TaxInfo", "slug": "roof-rental-account"},
      {"layer": "rule", "node_type": "business_rule",
       "domain": "Crowdfund::TaxInfo", "slug": "cr-002-roof-rental-bypass"}
    ],
    "source": "Knowledge audit 2026-04-08"
  },
  "body_md": "### Edge Cases\n- 屋主同時以用戶身份購買案場：屋主身份的所得為 lease_income（優先序 2），用戶身份的所得依優先序 3-5 判定\n- 法人 + unfilled：不觸發優先序 3\n- 法人 + payment_slip 或 invoice：不算收據，fall through"
}
```

### 6.4 範例節點 C: `context_map / taxinfo-context`

來源：`domain-map: Crowdfund::TaxInfo Context Mapping` + `strategic: 商務依賴`

```json
{
  "layer": "strategic",
  "node_type": "context_map",
  "slug": "taxinfo-context",
  "title": "Crowdfund::TaxInfo 上下文映射",
  "summary": "5 個上游 customer-supplier 關係，無下游消費者。",
  "attrs": {
    "contexts": [
      {"layer": "strategic", "node_type": "bounded_context",
       "domain": "Crowdfund::TaxInfo", "slug": "taxinfo"},
      {"layer": "strategic", "node_type": "bounded_context",
       "domain": "Revenue", "slug": "revenue"},
      {"layer": "strategic", "node_type": "bounded_context",
       "domain": "PaymentTransfer", "slug": "payment-transfer"},
      {"layer": "strategic", "node_type": "bounded_context",
       "domain": "UserProfile", "slug": "user-profile"},
      {"layer": "strategic", "node_type": "bounded_context",
       "domain": "ElectricityBilling", "slug": "electricity-billing"},
      {"layer": "strategic", "node_type": "bounded_context",
       "domain": "Roof::Owner", "slug": "roof-owner"}
    ],
    "relationships": [
      {"from": "revenue", "to": "taxinfo", "type": "Customer-Supplier",
       "description": "TaxInfo 從 Revenue 取得 Due 作為所得計算基礎"},
      {"from": "payment-transfer", "to": "taxinfo", "type": "Customer-Supplier",
       "description": "TaxInfo 依賴 Payment.status 過濾匯出（CR-001）"},
      {"from": "user-profile", "to": "taxinfo", "type": "Customer-Supplier",
       "description": "COALESCE(vat_id, id_number) 解析身分碼（CA-002）"},
      {"from": "roof-owner", "to": "taxinfo", "type": "Customer-Supplier",
       "description": "屋主身份判定 → lease_income，RoofRentalAccount bypass（CA-001, CR-002）"},
      {"from": "electricity-billing", "to": "taxinfo", "type": "Customer-Supplier",
       "description": "屋主電費租賃所得來源"}
    ]
  },
  "body_md": null
}
```

### 6.5 遷移後 specist 可以做什麼

在遷移前，specist 接到「處理 RoofRental 匯出問題」的任務，會把整個 `Crowdfund::TaxInfo` 的 business-rules + strategic + tactical 全部撈進 context。

遷移後：

```python
# specist 的檢索（Phase 3 才有 /retrieve，Phase 1 先用精準 list）
nodes = atdd_node_list(
    project="core_web",
    domain="Crowdfund::TaxInfo",
    layer="rule",
    node_type="business_rule"
)
# → 拿到 5 個 business_rule 節點（~500 tokens）
# 而不是整塊 md（~4000 tokens）

relevant = [n for n in nodes if "roof-rental" in n["slug"]
            or "roof-rental" in str(n["attrs"].get("references", []))]
# → 精準命中 CR-002, CA-001 兩條
```

**對 spec 產出的影響**：

```markdown
## 參考節點
- business_rule: `core_web/Crowdfund::TaxInfo/rule/business_rule/cr-002-roof-rental-bypass`
- business_rule: `core_web/Crowdfund::TaxInfo/rule/business_rule/ca-001-income-method-determination`
- entity: `core_web/Crowdfund::TaxInfo/tactical/entity/roof-rental-account`

## Given-When-Then
### Scenario: RoofRentalAccount 的 failed payment 仍被納入匯出
**Given** 一筆 RoofRentalAccount (entity:roof-rental-account) 的 Due
  且 對應的 Payment.status = "failed"
**When** 執行所得匯出 (business_rule:cr-002-roof-rental-bypass)
**Then** 該筆所得納入匯出（bypass CR-001 的 success 過濾）
  且 所得類別 = lease_income (business_rule:ca-001-income-method-determination priority 1)
```

下游 coder 看到 spec 就知道：「我要改 export 邏輯，觸到 CR-002 與 CA-001 優先序 1 的分支」——**不需要讀知識庫**。

### 6.6 遷移前後 DB 資料量對比

#### 總計

| 階段 | Tables | Rows |
|------|--------|------|
| **遷移前** | 2（`knowledge_entries`, `knowledge_terms`）| 27（17 + 10）|
| **遷移後** | 4（+ `knowledge_nodes`, `knowledge_node_revisions`）| 67（17 + 10 + 20 + 20）|
| **淨增** | +2 | +40（20 nodes + 20 revisions）|

#### Per-Table 明細

| Table | 遷移前 rows | 遷移後 rows | 變化 |
|-------|------------|------------|------|
| `knowledge_entries` | 17 | 17（不刪）| 0（加 `migrated` + `migrated_to_node_id` 欄位）|
| `knowledge_terms` | 10 | 10（不刪）| 0（加 `node_id` 欄位）|
| `knowledge_nodes` | — | **20** | +20（新表）|
| `knowledge_node_revisions` | — | **20** | +20（每個 node 一筆 v1 初始版本）|

#### Entry 遷移歸類

| 歸類 | 數量 | 處理 |
|------|------|------|
| 1 entry → 1 node | 10 | `migrated=true`, `migrated_to_node_id=<uuid>` |
| N entries 合併 → 1 node | 4（商務目的+能力+範疇+FAQ → bounded_context；商務依賴+domain-map → context_map）| 各自 `migrated=true`, `migrated_to_node_id=同一 uuid` |
| 1 entry 拆成 N nodes | 1（domain-map → 3 nodes）| `migrated=true`, `migrated_to_node_id=主 node uuid` |
| 不建節點（索引性/歷史性）| 4（Change History / 核心概念 / 商務規則索引 × 2）| `migrated=true`, `migrated_to_node_id=NULL` |
| **合計** | **17** | |

#### Term 關聯回填

| 歸類 | 數量 | 處理 |
|------|------|------|
| term → entity node | 5（TaxInfo→aggregate, TaxInfoDetail/Due/Payment/RoofRentalAccount→entity）| `node_id=<entity uuid>` |
| term → value_object node | 5（IdentityNumber/IncomeMethod/IncomeMonth/OtherIncome/RoofOwnerUnifiedIncomes）| `node_id=<vo uuid>` |
| **合計** | **10** | |

#### 效率指標

| 指標 | 遷移前 | 遷移後 |
|------|-------|-------|
| 可程式化檢索的知識單元 | 27（但無法精準過濾）| **20**（每個有 layer/node_type/slug 可精準定位）|
| 單元間交叉引用 | 0 | ~35 條（分散在 attrs 的 NodeRef 裡）|
| 給 LLM 的平均 token/單元 | ~500（整段 md）| ~150（title + summary + attrs）|
| Context 節省（以 specist 取 rule 為例）| ~4000 tokens | ~500 tokens（**−87%**）|

---

## 7. Open Questions

1. `subdomain` 與 `bounded_context` 的關係：目前是分兩個 node，還是把 `subdomain.kind` 合進 `bounded_context.attrs`？**Phase 1 暫定分開**，理由是 context_map 畫圖時常需要獨立引用 subdomain 標籤
2. `domain-map` 現在是一個 entry，遷移時會拆成 `bounded_context` + `context_map` + `subdomain`。需要 curator 在 migration script 裡處理這個 1 → 3 的拆分邏輯
3. `knowledge_terms` 的 `node_id` 欄位在 Phase 1 怎麼填？建議：migration script 處理完一個 term 時，自動回填對應 entity / VO 節點的 id
4. 不建節點的 entry（Change History、核心概念、商務規則索引段落等）：已透過 `migrated=true` + `migrated_to_node_id=NULL` 處理，merger 的 `WHERE migrated = false` 會自動跳過。見 migration SQL 中的欄位說明

---

## 8. Out of Scope（Phase 2+）

- `knowledge_relations` 表（Phase 3）
- `task_knowledge_links` 表（Phase 2）
- `embedding` 欄位 + pgvector（Phase 4）
- `stale` gate 強制卡住 specist（Phase 4，目前僅做軟性原則）
- Graph UI / Dashboard 投影（Phase 5）
- coder / tester 的知識讀取擴權（**永遠不做**，除非 ATDD 流程本質改變）
