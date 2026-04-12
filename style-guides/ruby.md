# Ruby Style Guide

本指南定義團隊特有的架構與風格決策，供 `style-reviewer` agent 使用。Ruby 基礎慣例（命名、慣用語法等）不在此重複。

## 專案分層原則

- **領域層**放入 `domains/` — 業務邏輯、UseCase、Entity、Repository
- **顯示層**放入 `slices/` — Controller、ViewModel、View、Form

## 代碼結構

- 方法保持簡短（< 20 行），過長應拆分
- 使用 guard clause 提前返回，避免深層嵌套
- 單一職責，一個 class 只做一件事

## Dry::Monads 使用

- 不混用例外和 Result，統一使用 `Success` / `Failure`
- 沒有明確 Failure 語意的地方不要使用 `yield`，避免寫出 `Success(true)` 這類無意義的回傳

## Domain 層規範

### UseCase

繼承 `Boxenn::UseCase`，入口方法為 `def steps`（非 `def call`）。

**命名：** 趨近「職責」而非「職務（在做的事）」。

**資料傳遞：** dependency 用 `option` 宣告（DI），params 在 `steps` 以 keyword arguments 傳入。

```ruby
class PlaceOrder < Boxenn::UseCase
  option :repository, default: -> { Repositories::Order.new }
  option :notifier, default: -> { OrderNotifier.new }

  def steps(product_id:, quantity:, buyer_id:)
    product = yield find_product(product_id: product_id)
    yield validate_stock(product: product, quantity: quantity)
    order = yield create_order(product: product, quantity: quantity, buyer_id: buyer_id)
    notifier.notify(order)
    Success(order)
  end

  private

  def find_product(product_id:)
    # ...
  end
end
```

- **dependency**（option 宣告）：有 method 的 class，如 repository、client
- **params**（steps 傳入）：以 keyword arguments 傳入，純資料

**拆分原則：** 過度複雜可拆分成子 Case，放在以父 Case 命名的資料夾內。

**Pub/Sub：** subscribe 與 publish 放在同一個 method。Event 命名規則為**名詞 + 動詞過去式**（e.g. `invoice_created`）。

### Entity

放在 `domains/{domain}/entities/`。由 Repository 產生，擁有 primary keys。使用 `Boxen::Entity`，以**領域物件**命名。

### ValueObject

放在 `domains/{domain}/value_objects/`。由 relation 產生或其他情境需要的資料結構。可使用 `Dry::Struct`，以**使用角度**命名。

### Services

未來可以**獨立出 Domain** 的 Class（不耦合原 Domain）。第三方服務只處理 HTTP request/response，input 應為 hash。

### Client

跨領域 Domain 溝通用的介面，適用於做**單一件事**。使用 Instance Method，**禁止使用 Instance Variables**（除了 DI 注入的 dependency）。

```ruby
class Accounting::Client
  def retrieve_invoice(serial:)
    repo = InvoiceRepo.new
    repo.find_by_serial(serial)
  end
end
```

### Listener

跨領域 Domain 溝通用的介面，適用於**做多件事**。一個 Domain 只有一個 Listener，method 命名為 `on_event_name`。

```ruby
class Accounting::Listener
  def on_invoice_created(event)
  end

  def on_payment_received(event)
  end
end
```

### Wrapper（DAL 層）

| 做法 | 適用情境 |
|------|----------|
| ActiveRecord `accepts_nested_attributes_for` | 一對多，需完整處理 association 的建立、刪除、更新 |
| Wrapper 內拆分多個 model 各自 save | 跨 Domain 單一欄位更新，相對簡單 |

## Slices 層規範

### Controller — 統一模板，禁止業務邏輯

Controller 必須使用統一 mixin，不得自行實作 CRUD action。**行數上限：30 行**（不含空行與 `end`）。

| 模式 | Mixin | 設定 | 適用情境 |
|------|-------|------|----------|
| Repository（優先） | `ActiveRecordRepositoryControllerActions` | `repo_name` + `aggregate_root_model` | 有 Domain 層 |
| ActiveRecord | `ActiveRecordControllerActions` | `model_name` | 簡單 CRUD |

```ruby
module Admin::Accounting
  class AccountsTypesController < Admin::BaseController
    include Admin::ControllerHelpers::ActiveRecordRepositoryControllerActions

    repo_name '::Accounting::AccountsType::Repositories::Category'
    aggregate_root_model '::Accounting::AccountsType::Models::AccountsType'

    before_action :authorized?

    private

    def authorized?
      authorize :master_data
    end
  end
end
```

Override action 時仍禁止業務邏輯，應委派給 UseCase / Service。

#### Flash 訊息大小限制（CookieOverflow 防護）

Rails 的 `flash[:alert]` / `flash[:notice]` 儲存於 cookie 中，Rails 預設上限 **4KB**。中文字元經 URL encoding 會膨脹約 3 倍，因此**批量操作**（匯入、批次建立、批次更新）的錯誤訊息必須在 Controller 層截斷，禁止直接將 UseCase 回傳的完整錯誤陣列塞入 flash。

**禁止**：

```ruby
flash[:alert] = Array(result[:errors]).join("\n")   # 大量錯誤會觸發 CookieOverflow
flash[:alert] = result.failure                       # 未知大小的 failure message 直接塞入
```

**正確做法**：前 10 筆錯誤 + 摘要

```ruby
errors = Array(result[:errors])
max_display = 10
if errors.size > max_display
  truncated = errors.first(max_display)
  truncated << "...等，共 #{errors.size} 筆錯誤，請修正後重新上傳"
  flash[:alert] = truncated.join("\n")
else
  flash[:alert] = errors.join("\n")
end
```

**適用情境**：所有可能產生 N 筆錯誤的 action（xlsx 匯入、批次表單、批次 API），UseCase 仍回傳完整錯誤，Controller 負責截斷後存入 flash。

### ViewModel — 統一繼承 BaseIndex / BaseShow

**Index ViewModel** 繼承 `Admin::Layout::BaseIndex`，必須實作：

| 方法 | 用途 |
|------|------|
| `relation` | ActiveRecord relation（含 ransack） |
| `search_tab` | 搜尋表單欄位定義 |
| `action_items` | 頁面操作按鈕 |
| `collection_list` | 表格欄位 header 定義 |
| `decorate_collection(collection)` | 資料列轉換為顯示用 hash |

**Show ViewModel** 繼承 `Admin::Layout::BaseShow`，必須實作：

| 方法 | 用途 |
|------|------|
| `entity` | 回傳要顯示的 entity 物件 |
| `entity_partial` | 對應的 partial view 路徑 |
| `action_items` | 頁面操作按鈕 |

**命名對齊規則：** Controller、ViewModel、Form 三者 namespace 必須一致。

```
Controller: Admin::Accounting::AccountsTypesController#index
ViewModel:  Admin::Accounting::AccountsTypes::Index
Form:       Admin::Accounting::AccountsTypes::Form
```

### Form — 格式驗證，非業務邏輯驗證

Form 繼承 `Homebrew::Form`（即 `Dry::Validation::Contract`），**只做格式驗證**（欄位存在性、型別、格式）。業務邏輯驗證（唯一性、狀態檢查、跨欄位規則）應在 Domain 層處理。

```ruby
class Form < Homebrew::Form
  params do
    required(:source_type).filled(:string)
    required(:name).filled(:string)
    required(:code).filled(:string)
    optional(:sub_item).maybe(:string)
  end
end
```

### Worker / Rake

- **Worker**：有**排程性質**的非同步任務（非同步不一定要放 Worker）
- **Rake**：一次性的資料變更、讀取或產出任務

## 測試規範

### Production Code 純淨性

- **禁止為了測試在 production code 加 workaround**。如果測試需要 stub/mock 某個方法但遇到技術限制（如 prepended module），應在測試端解決，不可在 production code 加空 override
- **禁止為了測試建立頂層常數 alias**（如 `Entities = SomeModule::Entities`）。測試應使用完整 namespace 引用

```ruby
# ❌ 不要在 production code 加空 override 讓測試能 mock
def broadcast(*args)
  super
end

# ❌ 不要建立 spec/support/xxx_alias.rb
Entities = PowerWheeling::AccountingResult::Entities

# ✅ 測試直接用完整 namespace
allow(PowerWheeling::AccountingResult::Entities::AccountCode).to receive(:calculate)
```

### RSpec Stub 偏好

- **避免 `allow_any_instance_of`**，優先使用 instance stub 或 dependency injection
- 如果 `any_instance` 因 prepended module 失敗，改 stub 更高層級的方法（如 stub `broadcast_event` 而非 `broadcast`）

```ruby
# ❌ any_instance 容易因 prepend 失敗
allow_any_instance_of(MyUseCase).to receive(:broadcast)

# ✅ 使用 instance stub
instance = MyUseCase.new(client: mock_client)
allow(instance).to receive(:broadcast_event)
```

### 資料庫操作一律使用 ActiveRecord ORM

- 所有對資料庫的操作**一律使用 ActiveRecord ORM**（包含 Migration、UseCase、Repository、Rake 等）
- 禁止 raw SQL 字串插值（`"#{var}"`），避免 SQL Injection 風險
- **唯一例外**：Relation 物件（view、複雜查詢）可使用 raw SQL，但必須用 bind parameters（`$1, $2`）

```ruby
# ❌ raw SQL 字串插值（任何場景都禁止）
execute "UPDATE fees SET rate = #{rate} WHERE category = '#{category}'"

# ✅ ActiveRecord ORM
MyModel.where(category: category).update_all(rate: rate)

# ✅ Relation 物件例外，但須用 bind parameters
connection.exec_query("SELECT * FROM fees WHERE category = $1", "SQL", [category])
```

## 資料庫查詢規範

- 優先使用 **Rails ActiveRecord** 查詢，避免寫 raw SQL
- 必須寫 raw SQL 時，確保使用 **PostgreSQL 語法**（如位置參數 `$1, $2`，而非 `?`）

## 檢查清單

style-reviewer 應檢查：

- [ ] 方法長度合理（< 20 行）
- [ ] 使用 guard clause 而非深層嵌套
- [ ] Dry::Monads 使用正確（不混用例外、yield 有明確 Failure 語意）
- [ ] 無 magic number（用常數取代）
- [ ] **Domain UseCase** 繼承 Boxenn::UseCase，入口為 `def steps`
- [ ] **Domain UseCase** dependency 用 option 宣告，不用 instance variable 傳資料
- [ ] **Domain UseCase** 命名為職責而非職務
- [ ] **Domain Client** 使用 instance method，禁止 instance variable（DI 除外）
- [ ] **Domain Listener** 一個 Domain 一個，method 命名為 `on_event_name`
- [ ] **Domain Form vs Domain** 格式驗證在 Form，業務邏輯驗證在 Domain
- [ ] **Slices Controller** 使用統一模板（Repository 或 ActiveRecord mixin）
- [ ] **Slices Controller** action 內無業務邏輯，行數 ≤ 30
- [ ] **Slices ViewModel** 繼承 BaseIndex / BaseShow，實作所有必要方法
- [ ] **Slices ViewModel** namespace 與 Controller、Form 三者對齊
- [ ] **Slices Form** 只做格式驗證，業務邏輯驗證在 Domain 層
- [ ] **資料庫查詢** 優先使用 Rails ActiveRecord，raw SQL 須用 PostgreSQL 語法
- [ ] **測試純淨性** Production code 無為測試加的 workaround（空 override、頂層 alias）
- [ ] **測試 Stub** 避免 `any_instance`，優先用 instance stub 或 DI
- [ ] **資料庫操作** 一律使用 ActiveRecord ORM，禁止 raw SQL 字串插值（Relation 物件例外，須用 bind parameters）
