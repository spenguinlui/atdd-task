# Pre-Modification Checks — 修改前驗證

> **起源**：Incident `docs/incidents/2026-04-20_coder-wrong-file-5a6e2879.md`
> Coder 將修復套用到 dead code `CreateDueDetails`，production 實際走 `CreatePeriodDues`。
> 測試因 stub 過高而虛假通過，若非 risk-reviewer 攔截，bug 會進 production。

---

## 核心原則

**修改任何檔案前，必須先證明該檔案在 production 會被執行。** 不得僅依賴 SA 指定的檔名。

## 觸發條件（任一成立即必做）

- SA 指定了要修改的具體檔案
- 目標目錄存在 ≥2 個命名相似的檔案（如 `create_due_details.rb` 與 `create_period_dues.rb`）
- 修改的 class/method 是 Sidekiq worker、use case、service 等「被注入」的元件
- Fix 類任務（production bug 修復）

## 必做步驟

### 步驟 1：搜尋所有 caller

```bash
# 以 class 名稱搜尋
grep -rn "ClassName" --include="*.rb" {project_path}/app {project_path}/lib {project_path}/domains

# 排除自身定義與 migration
grep -rn "ClassName" --include="*.rb" | grep -v "class ClassName" | grep -v "db/migrate"
```

判讀：
- **結果為空** → 目標是 dead code，**立刻停止並回報 SA**，不得修改
- **只有測試引用** → 可能是已停用的實作，需進一步確認
- **有 production caller** → 進入步驟 2

### 步驟 2：從 entry point 追蹤 call chain

從已知進入點（Controller、Background Job、Rake task、orchestrator use case）逐層追蹤到目標 class，證明 production 執行路徑會經過此處。

範例（取自 incident）：
```
BatchCreatePeriodDues#steps                ← entry point
  └─ period_due_creator.call(...)
     └─ CreatePeriodDues#steps             ← 這才是 production 路徑
        └─ batch_create_due_details
           └─ build_changed_contract_details
              └─ tax: 0                    ← 修改目標應在這裡
```

關鍵檢查：注入點（`option`、`Depedencies.inject`、`new` 呼叫）實際提供的 class 是什麼？
```ruby
option :period_due_creator, default: proc {
  ::...::CreatePeriodDues.new              # ← 這才是 production class
}
```

### 步驟 3：同目錄相似檔案比對

若同目錄存在多個命名相似的檔案：
- 逐個確認其 caller
- 比對兩者差異，判斷誰是 active、誰是 legacy
- 將結果寫入修改前的判斷紀錄（在報告中說明）

## 停止條件（必須回報 SA，不得自行決定）

| 情況 | 動作 |
|------|------|
| SA 指定檔案無 caller | **暫停**，回報 specist 修正 SA |
| SA 指定檔案存在但 call chain 無法追通到 production entry point | **暫停**，回報 specist 補齊 call chain |
| 同目錄有 ≥2 個相似檔案且 SA 未指明差異 | **暫停**，要求 SA 澄清 |

回報格式：
```
⚠️ 暫停修改 — SA 指定檔案驗證失敗

指定檔案：{file_path}
驗證結果：{無 caller / call chain 斷鏈 / 同目錄有替代檔案 {alt_path}}
建議 SA 更新：{具體建議}

已停止修改動作，等待 specist 確認。
```

## 測試必須驗證 Production 路徑

配合修改檔案的正確性，測試也必須走 production 進入點：

| 要求 | 說明 |
|------|------|
| 從 orchestrator / entry point 呼叫 | 不得直接 `new` 內部 class 測試 |
| Stub 只能在 external boundary | 允許 stub DB、HTTP client、外部 API；**禁止** stub 內部 orchestrator / use case / service 之間的呼叫 |
| 驗證修改行被執行 | 測試通過後，可用 `puts` / `Rails.logger.debug` / coverage 確認目標行真的被走到 |

反例（incident 中的錯誤 stub）：
```ruby
# ❌ stub 層級過高，繞過整個 ledger 建構流程
allow_any_instance_of(Client).to receive(:retrieve_ledger).and_return(ledger_stub)
BatchCreatePeriodDues.new.call(...)
```

正確做法：
```ruby
# ✅ 只 stub 外部 HTTP / DB，讓內部 call chain 真實執行
allow(ExternalAPI).to receive(:fetch).and_return(real_response_fixture)
BatchCreatePeriodDues.new.call(...)  # 會真實走到 CreatePeriodDues
```

## 檢查清單（修改前必填）

在報告開頭先列出：

- [ ] 目標 class/file：`{path}`
- [ ] Caller 搜尋結果：`{N 個 caller / 無 caller}`
- [ ] Entry point call chain：`{A → B → target}`
- [ ] 同目錄替代檔案：`{無 / 有: {alt}，已確認差異}`
- [ ] 決策：`{進入修改 / 回報 SA}`

任一項未填 → 不得進入 Phase 3 實作。
