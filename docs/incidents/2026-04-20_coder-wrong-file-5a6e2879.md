# Incident Report: Coder Agent 修改錯誤檔案

> **Task**: 5a6e2879-fcba-4b86-924f-f1e4340048d2 (PVO-343)
> **日期**: 2026-04-20
> **階段**: development → review（由 risk-reviewer 攔截）
> **嚴重度**: Critical — production bug 未被修復

---

## 事件摘要

Coder agent 將修復套用到 **已停用的遺留檔案** `CreateDueDetails`，而非 production 實際使用的 `CreatePeriodDues`。測試因 stub 整個 ledger client 而通過，但驗證的是錯誤的程式碼路徑。若未被 risk-reviewer 攔截，此修復部署後 production bug 仍然存在。

---

## 錯誤鏈分析

### 第一環：SA 階段指向錯誤檔案

SA（需求分析）的「關鍵程式碼」列出：

```
- create_due_details.rb
  - create_other_adjustment_detail (L105-116): 硬編碼 tax: 0
```

修復方向也寫：

> 在 `create_other_adjustment_detail` 中，對法人含稅戶（tax_included = true）...

SA **沒有提及** `create_period_dues.rb`，也沒有追蹤從 orchestrator 到實際 worker 的 call chain。

### 第二環：Coder 未驗證 call chain

同一目錄下有兩個檔案：

| 檔案 | 類別 | Production 使用 |
|------|------|----------------|
| `create_due_details.rb` | `CreateDueDetails` (Sidekiq worker, legacy) | **否** — 無任何 caller |
| `create_period_dues.rb` | `CreatePeriodDues` (Sidekiq worker, active) | **是** — `BatchCreatePeriodDues` 注入 |

Coder 直接根據 SA 指示的檔案名修改，沒有：
1. 搜尋 `CreateDueDetails` 的 caller（會發現無人引用）
2. 確認 orchestrator `BatchCreatePeriodDues` 實際注入的是哪個 class
3. 比對兩個同目錄檔案的差異與角色

### 第三環：測試給予虛假信心

測試使用 `allow_any_instance_of(Client).to receive(:retrieve_ledger).and_return(ledger_stub)` 繞過整個 ledger 建構，直接呼叫 `BatchCreatePeriodDues.new.call`。

問題：`BatchCreatePeriodDues` 內部注入的是 `CreatePeriodDues`（非 `CreateDueDetails`），所以測試實際走的是 `CreatePeriodDues` 路徑 — **但那個路徑沒被修改**。

這代表測試要嘛：
- 走到未修改的 `CreatePeriodDues`（測試應該 fail 才對），或
- stub 層級太高，完全沒觸及 tax 計算邏輯

無論哪種，測試未能驗證修復是否生效。

---

## 證據

### 1. Production call chain

```
BatchCreatePeriodDues#steps
  └─ period_due_creator.call(...)
     └─ CreatePeriodDues#steps          ← production 路徑
        └─ batch_create_due_details
           └─ build_changed_contract_details
              └─ line 171: tax: 0       ← BUG 仍在
```

**佐證**：`batch_create_period_dues.rb:12`
```ruby
option :period_due_creator, default: proc {
  ::ElectricityAccounting::PeriodicLedger::UseCases::BatchCreatePeriodDues::CreatePeriodDues.new
}
```

### 2. CreateDueDetails 無人引用

全 codebase 搜尋 `CreateDueDetails` 僅出現在：
- 自己的定義（`create_due_details.rb:4`）
- DB migration（`20251002154726_create_due_details.rb`）

**零個 caller**。

### 3. Coder 修改的內容（正確邏輯，錯誤位置）

`create_due_details.rb` diff：
```ruby
-def create_other_adjustment_detail(due_id:, ledger:)
+def create_other_adjustment_detail(due_id:, ledger:, user_parameter:)
   amount = ledger.other_adjustment_amount
   return if amount.zero?

+  if user_parameter.tax_included
+    pre_tax_amount = (amount / 1.05).round
+    tax = amount - pre_tax_amount
+  else
+    pre_tax_amount = amount
+    tax = 0
+  end

   create_due_detail(
     due_id: due_id,
     category: 'other',
     amount: amount,
-    pre_tax_amount: amount,
-    tax: 0
+    pre_tax_amount: pre_tax_amount,
+    tax: tax
   )
```

### 4. 應修改的位置（仍有 bug）

`create_period_dues.rb:168-172`：
```ruby
# other adjustment (差額)
other_amount = ledger.other_adjustment_amount
unless other_amount.zero?
  records << { due_id: due_id, category: 'other', amount: other_amount,
               pre_tax_amount: other_amount, tax: 0,    # ← BUG
               created_at: now, updated_at: now }
end
```

此處有 `user_parameter` 可用（method signature 已包含），且同檔案已定義 `TAX_MULTIPLIER = BigDecimal('1.05')`。

---

## 根因分類

| 層級 | 問題 | 負責角色 |
|------|------|---------|
| SA | 關鍵程式碼指向遺留檔案，未追蹤 call chain | specist / SA 分析 |
| Development | 未驗證修改的檔案是否為 production 進入點 | **coder** |
| Testing | stub 層級過高，未驗證端到端路徑 | **coder** (test author) |
| Review | risk-reviewer 正確攔截 | ✅ 運作正常 |

---

## Coder Agent 改善建議

### 建議 1：強制 Call Chain 驗證（修改前置步驟）

在修改任何檔案前，coder 應執行：

```
1. 搜尋目標 class/method 的所有 caller
2. 從 orchestrator/entry point 追蹤到目標，確認是 production 路徑
3. 若目標 class 無 caller → 標記為 dead code，搜尋同目錄的替代檔案
```

**觸發條件**：SA 指定的修改檔案、或同目錄存在多個相似命名的檔案時。

### 建議 2：Dead Code 偵測

修改前檢查：
```
grep -r "ClassName" --include="*.rb" | grep -v "class ClassName" | grep -v migration
```
如果結果為空 → 該 class 可能是 dead code，不應作為修復目標。

### 建議 3：測試必須走 Production 路徑

Integration test 應從 production entry point（orchestrator）開始呼叫，而非直接測試內部 class。
- 若 stub 是必要的，stub 層級應在 external dependency（DB、API），不應 stub 內部 call chain。
- 測試通過後，應驗證修改的程式碼行確實被執行（可用 coverage 或 debug log 確認）。

### 建議 4：SA 品質回饋迴路

當 coder 發現 SA 指向的檔案有疑慮（如 dead code、命名相似但不同的檔案並存），應回報而非盲目執行。可在 coder agent 規則中加入：

> 若 SA 指定的修改檔案在 codebase 中無 caller，必須暫停並回報，不得直接修改。

---

## 時間線

| 時間 | 事件 |
|------|------|
| 2026-04-16 | 任務建立，SA 完成（指向 create_due_details.rb） |
| 2026-04-20 05:32 | 任務進入 development |
| 2026-04-20 05:55 | Coder 完成修改（修改了錯誤檔案） |
| 2026-04-20 06:30 | /continue 進入 review，risk-reviewer 發現 Critical |
| 2026-04-20 06:30 | 攔截成功，未進入 production |
