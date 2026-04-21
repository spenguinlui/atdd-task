# 規格撰寫指南

## 規格結構

每個規格必須包含：

1. **Business Context**：為什麼、給誰、影響
2. **Domain 資訊**：主要 Domain、相關 Domains
3. **ATDD Profile**：驗收類型、選擇原因
4. **Acceptance Criteria**：驗收標準清單
5. **Scenarios**：Given-When-Then 場景

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

### 場景類型

1. **Happy Path**：正常成功流程
2. **Alternative Path**：其他成功路徑
3. **Error Path**：錯誤處理
4. **Edge Case**：邊界情況

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
