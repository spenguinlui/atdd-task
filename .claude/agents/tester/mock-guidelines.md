# Mock 使用指南

## 避免過度 Mock

過度 mock 會導致測試通過但實際執行失敗。

## Stub 層級規則（強制）

> ⛔ **Stub 只能在 external boundary，禁止 stub 內部 call chain。**
> 起源 incident：`docs/incidents/2026-04-20_coder-wrong-file-5a6e2879.md`
> 該案測試 stub 了整個 `retrieve_ledger`，繞過 production 真正的 `CreatePeriodDues` 路徑，讓修錯檔案的 bug 依然通過測試。

| 層級 | 可否 Stub | 說明 |
|------|-----------|------|
| 外部 HTTP / API | ✅ | 避免依賴外部服務 |
| DB query（僅邊界測試） | ⚠️ | 至少一個測試走真實 DB |
| 時間 / 亂數 | ✅ | 確保可重現 |
| **內部 orchestrator → use case** | ❌ | 會跳過真正的 production 路徑 |
| **內部 use case → service** | ❌ | 同上 |
| **注入點提供的 class**（`option :xxx, default: ...`） | ❌ | stub 後無法驗證 production 實際走哪條路 |

### 驗收測試的起點

Integration / acceptance 測試必須從 **production entry point**（Controller action、Sidekiq worker `perform`、orchestrator `call`）開始呼叫，讓內部 call chain 真實執行。

反例：
```ruby
# ❌ 直接測試內部 class，繞過注入點
CreatePeriodDues.new.call(...)

# ❌ stub 內部 dependency，繞過 production 路徑
allow_any_instance_of(Client).to receive(:retrieve_ledger).and_return(stub)
BatchCreatePeriodDues.new.call(...)
```

正例：
```ruby
# ✅ 從 entry point 呼叫，只 stub 外部 HTTP
allow(ExternalAPI).to receive(:fetch).and_return(fixture_response)
BatchCreatePeriodDues.new.call(...)
```

### 驗證目標行實際被執行

Fix 類測試通過後，必須驗證修改的行真的被走到（避免 stub 過高造成虛假通過）：
- 方法 A：在目標行加臨時 `Rails.logger.debug`，執行測試確認 log 出現
- 方法 B：用 `expect(instance).to receive(:target_method)` 確認被呼叫
- 方法 C：用 SimpleCov 的 line coverage 確認

驗證通過再移除臨時 log。

## Mock 規則

| 情況 | 可否 Mock | 說明 |
|------|-----------|------|
| 外部 API | ✅ 應該 Mock | 避免依賴外部服務 |
| 時間 (`Time.now`) | ✅ 可以 Mock | 確保測試可重現 |
| Repository | ⚠️ 謹慎 | 至少要有一個真實測試 |
| Domain Entity | ❌ 不要 Mock | 直接使用真實物件 |
| 核心業務邏輯 | ❌ 不要 Mock | 這正是要測試的東西 |

## 測試結構範例

```ruby
RSpec.describe SomeUseCase do
  # 初始化測試（避免過度 mock）
  describe '初始化' do
    it '可以使用預設值初始化' do
      expect { described_class.new }.not_to raise_error
    end
  end

  # 驗收測試（至少一個真實依賴測試）
  describe '驗收測試', :acceptance do
    let(:use_case) { described_class.new }  # 使用預設依賴

    it '完整流程驗收' do
      result = use_case.call(valid_params)
      expect(result).to be_success
    end
  end

  # 邊界情況測試（可以用 mock）
  describe '邊界情況' do
    let(:repository) { instance_double(SomeRepository) }
    let(:use_case) { described_class.new(repository: repository) }

    # ... 用 mock 測試各種情境
  end
end
```

## 失敗分析類型

| Failure Type | Indicators | Typical Fix |
|--------------|------------|-------------|
| Assertion | `expected X, got Y` | Logic error in implementation |
| Mock/Stub | `undefined method`, `not stubbed` | Missing or incorrect mock |
| Setup | `nil`, `not found` | Factory/fixture issue |
| Async | `timeout`, `pending` | Missing await/async handling |
| Time | `freeze_time not working` | Missing ActiveSupport::Testing::TimeHelpers |
