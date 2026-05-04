# 規格撰寫指南

## 規格結構

每個規格必須包含（順序固定，禁止跳過）：

1. **Problem Statement**：解決什麼問題、為什麼非修不可、不修的後果
2. **Solution Overview**：採用方案一句話 + 為什麼選這個（trade-off）
3. **Business Context**：為什麼、給誰、影響
4. **Domain 資訊**：主要 Domain、相關 Domains
5. **ATDD Profile**：驗收類型、選擇原因
6. **Acceptance Criteria**：驗收標準清單
7. **Scenarios**：Given-When-Then 場景（依分類標籤分組）

## 冷讀者測試（強制 — Cold-Reader Test）

> ⛔ **規格必須能被「沒看過 requirement 的讀者」獨立讀懂。**
>
> 撰寫完成後，把自己當作下游 tester / coder：你只看 spec 內容（不看 requirement、不看任務歷史），是否能回答這 4 個問題？
>
> 1. 這個任務在解決什麼業務問題？
> 2. 為什麼非做不可？（不做的後果是什麼？）
> 3. 採用什麼方案？為什麼選這個而非其他？
> 4. 每個 Scenario 是主流程、邊界、還是回歸保護？

任一答不出來 → 補 Problem Statement / Solution Overview / Scenario 標籤後重寫。

### Problem Statement 範例

```markdown
## Problem Statement

**現象**：production 716 筆工程款收入單的 tax 欄位是 NULL（空的）。
**影響**：用戶編輯這些舊單時，程式 nil.to_i 出錯 → 404。
**為什麼會這樣**：VR-143 規則（price + tax = price_with_tax）2024 年才上線，之前建的單沒有 tax。
**為什麼非修不可**：主任務 be88a60f 已用 nil-guard 暫貼，但要拆掉貼布、執行 hardening #2 (NOT NULL constraint) 必須先把資料補乾淨。
```

### Solution Overview 範例

```markdown
## Solution Overview

**方案**：對每個 project 重算 5 期工程款的 tax（總價 × 5%，尾差落最後一期），同時補 price_with_tax / amount_with_tax。

**為什麼選這個（vs Option A: tax=0 / Option C: price_with_tax - price）**：
- Option A 違反 VR-143（tax=0 但 price>0 ⇒ price_with_tax 對不上）
- Option C 多數舊單 price_with_tax 也是 NULL，無法回算
- 只有本方案同時滿足 VR-143、VR-144 尾差規則、抵抗 SaveSaleElements 重算
```

## 撰寫原則

### Acceptance Criteria

- 使用業務語言，不用技術語言
- 每條標準必須可驗證
- 避免模糊詞彙（「快速」、「友善」）

```markdown
## Acceptance Criteria

- [ ] 使用者可以看到發票狀態變更為「已作廢」
- [ ] 系統記錄作廢時間和原因
- [ ] 作廢後發票無法再次修改
```

### Scenarios

每個場景必須有：
- **Given**：前置條件（系統狀態、資料）— 使用具體值，不用「某個」「一些」
- **When**：使用者動作（觸發事件）
- **Then**：預期結果（可驗證的業務結果）— **必須是具體、精確的預期值**

#### Then 精確度規則（強制）

> ⛔ **禁止模糊描述**。Then 必須寫出可直接比對的預期值，不允許「包含」「類似」「相關」等模糊詞。

| 禁止寫法 | 正確寫法 | 原因 |
|----------|----------|------|
| 包含兩者 | `"屋主希望下午聯繫\n廣告傳單(DM)"` | 必須寫出確切字串和格式 |
| 顯示正確金額 | 顯示金額 `"$95,000"` | 必須寫出具體數字 |
| 狀態更新 | 狀態變為 `"已作廢"` | 必須寫出具體狀態值 |
| 包含相關資訊 | 顯示 `"來源：廣告傳單(DM)"` | 必須寫出完整預期字串 |
| 正確排序 | 順序為 `["A", "B", "C"]` | 必須寫出具體排序結果 |

**關鍵原則**：如果 tester 無法從 Then 直接寫出 `eq("具體值")` 斷言，就代表 Then 寫得不夠精確。

#### 持久化斷言規則（強制 — Persistence Assertion Rule）

> ⛔ 當 SA 中出現「UPDATE / 修改 / 重算 / 覆寫 既有 DB record」字樣時，Spec 的 Then **必須**明確指定驗證的是 **DB 持久化後的 record**，不是回傳的 entity 物件。

| 情境 | 禁止寫法 | 正確寫法 |
|------|----------|----------|
| 更新既有訂單 | Then SalesOrder 的 order_amount = X | Then **reload 同一筆** SalesOrder (id 不變)，order_amount = X |
| 重算並覆寫 | Then 重算後金額為 X | Then **DB 中既有的** SalesOrder record 的 order_amount **被更新為** X，items **被替換為** N 筆 |
| 刪除子項目 | Then items 數量為 2 | Then **reload 後** items.count = 2，且舊 items **已從 DB 移除** |

**Why**：GRE-225 教訓——SA 寫「需 UPDATE」，Then 只寫「金額 = X」，tester 用 `.send(:private_method)` 驗算回傳值就通過了，但 DB 完全沒被更新。

**檢查清單**（specist 自我驗證）：
1. SA 有沒有提到 UPDATE / 修改 / 重算 / 覆寫？
2. 如果有，對應的 Then 是否包含「reload」「同一筆 record」「DB 中既有的」等語意？
3. 是否有驗證 record.id 不變（排除「新建一筆」的假象）？
4. 若有子表（items/details），是否也有 DB-level 驗證？

**格式驗證**：當預期值涉及字串組合時，必須明確寫出：
- 連接符號（換行 `\n`、逗號、空格、分隔線等）
- 各部分的順序
- 完整的預期字串

```markdown
### Scenario 1: 成功作廢有效發票

**Given** 有一張有效的發票 ACC-001，金額 $10,000
**And** 該發票尚未被 ERP 結算
**When** 會計人員點擊「作廢」並填入原因「開錯客戶」
**Then** 發票狀態應為 `"已作廢"`
**And** 系統記錄作廢原因為 `"開錯客戶"`
**And** 頁面顯示訊息 `"發票 ACC-001 已成功作廢"`
```

### 場景類型與命名規範（強制）

> ⛔ Scenario 必須帶分類標籤，讓讀者一眼看出此場景在驗證主流程、邊界還是回歸。
>
> 命名格式：`S{n}-{tag}: {一句話說明}`

| 標籤 | 意義 | 範例 |
|------|------|------|
| `happy` | 主成功流程 | `S1-happy: 單 project 5 期回填正確` |
| `alt` | 其他成功路徑 | `S2-alt: 4 期工程款也能正確分配尾差` |
| `error` | 錯誤處理 | `S3-error: 真實 update 期間 DB 中斷可回滾` |
| `edge` | 邊界情況 | `S4-edge: key_name 不符 PROGRESS_INCOME_KEY_NAMES 不被更動` |
| `regression` | 回歸保護（不破壞既有行為） | `S5-regression: 主任務 nil_tax_spec 仍綠` |
| `safety` | 安全機制（rollback / dry-run / idempotent） | `S6-safety: rollback 完整還原至 NULL` |

**每個 Scenario 開頭必須有「目的」一句話**，說明此場景驗證什麼，避免讀者只看 Given/When/Then 推測意圖。

```markdown
### S1-happy: 單 project 5 期回填正確

**目的**：驗證核心算法 — 總稅按 5% 計算、尾差落最後一期、3 個欄位同步寫入。

**Given** project RT080026 v3 有 5 期工程款收入單 ...
**When** ...
**Then** ...
```

## 規格檔案位置

```
specs/{project}/{task_id}-{short_name}.md
```

範例：
```
specs/core_web/abc123-void-invoice.md
```

## 驗收標準數量建議

- 簡單功能：3-5 個
- 一般功能：5-8 個
- 複雜功能：8-12 個

如果超過 12 個，考慮拆分為多個任務或上升為 Epic。

## 規格模板

使用 `.claude/templates/spec-template.md` 作為起始模板。
