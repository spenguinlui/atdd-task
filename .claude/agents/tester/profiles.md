# ATDD Profile 測試生成指南

## 測試分類原則

| 分類 | 性質 | 存放位置 | 觸發時機 |
|------|------|----------|----------|
| **E2E** | 單點驗收（任務形態） | atdd-hub `acceptance/fixtures/` 或 `tests/` | 任務驗收時手動/指令觸發 |
| **Integration / Calculation / Unit** | 防守型城牆（回歸測試） | 各專案 repo `spec/` 目錄內 | CI/CD 自動觸發，卡控品質 |

> E2E 由 atdd-hub 管理，Integration/Unit 屬於各專案 repo 的必要測試。

---

## Profile: E2E（端對端驗收）

**性質**：單點驗收，驗證特定任務的需求是否完成，由 atdd-hub 管理

**適用場景**：結果可在畫面即時看到（< 60 秒）

**執行器**：Chrome MCP

**生成物**（存放在 atdd-hub）：
```
acceptance/fixtures/{project}/{task_id}.yml
db/seeds/acceptance/{task_id}_setup.rb
db/seeds/acceptance/{task_id}_cleanup.rb
```

### E2E Fixture 結構

```yaml
id: "{task_id}"
description: "{task_description}"
profile: "e2e"

environment:
  target: "local"
  baseUrl: "http://localhost:3000"
  credentials:
    email: "test@example.com"
    password: "password"

setup:
  script:
    path: "db/seeds/acceptance/{task_id}_setup.rb"
    command: "cd {project_path} && rails runner {path}"
  creates:
    - entity: "Invoice"
      identifier: { serial: "ACC-INV-001" }
      attributes:
        status: "valid"
        amount: 10000

steps:
  - id: 1
    description: "登入系統"
    action:
      type: "navigate"
      target: "/login"
    expected:
      type: "element_exists"
      selector: "form.login"
    screenshot: true

expectedResults:
  - id: 1
    description: "業務結果驗證"
    verification:
      type: "visual"
      selector: ".result"
      contains: "預期值"

teardown:
  script:
    path: "db/seeds/acceptance/{task_id}_cleanup.rb"
```

---

## Profile: Integration（整合驗收）

**性質**：專案層級的回歸測試（防守型城牆），存放在各專案 repo 內，CI/CD 自動觸發

**適用場景**：
- 需要時間操作（travel_to/freeze_time）
- 需要 Mock 外部服務
- 跨 Domain 資料流
- 背景作業/排程

**執行器**：RSpec / Jest / Pytest

**生成物**（存放在各專案 repo）：
```
{project_path}/spec/domains/{domain}/{aggregate}/integration/{feature}_spec.rb
```

### Integration 測試結構

```ruby
# spec/acceptance/accounting/weekly_settlement_spec.rb
RSpec.describe "週結算驗收測試", type: :acceptance do
  describe "需求：每週一計算上週收益並產生報表" do
    let(:project) { create(:project, :with_revenue_data, electricity_income: 100_000, management_fee_rate: 0.05) }

    it "驗收：結算後產生正確期間和金額的報表" do
      travel_to(Time.zone.parse("2024-01-15 00:00:00")) do
        WeeklySettlementJob.perform_now
      end

      report = project.settlement_reports.last
      # ✅ 精確斷言：驗證具體值，不只是 be_present
      expect(report.period).to eq("2024-01-08..2024-01-14")
      expect(report.net_profit).to eq(95_000)
      expect(report.status).to eq("completed")
    end

    # ✅ 邊界測試：無收入資料時的處理
    it "驗收：無收入資料時不產生報表" do
      empty_project = create(:project)

      travel_to(Time.zone.parse("2024-01-15 00:00:00")) do
        WeeklySettlementJob.perform_now
      end

      expect(empty_project.settlement_reports.count).to eq(0)
    end
  end
end
```

> **斷言原則**：預設用 `eq(具體值)`，禁止用 `be_present`/`be_truthy` 驗證業務結果。詳見 tester.md「斷言精確度規則」。

### Integration 測試 Helpers

| Helper | 用途 | RSpec | Jest |
|--------|------|-------|------|
| time | 時間操作 | `travel_to`, `freeze_time` | `jest.useFakeTimers` |
| mock | 外部服務 | `stub_request`, `allow().to receive` | `jest.mock` |
| async | 非同步 | `perform_enqueued_jobs`, `Sidekiq::Testing.inline!` | `await`, `waitFor` |

---

## Profile: Unit（單元驗收）

**性質**：專案層級的回歸測試（防守型城牆），存放在各專案 repo 內，CI/CD 自動觸發

**適用場景**：
- 純計算邏輯
- 業務規則
- Value Object
- Domain Service

**執行器**：RSpec / Jest / Pytest

**生成物**（存放在各專案 repo）：
```
{project_path}/spec/domains/{domain}/{aggregate}/unit/{service}_spec.rb
```

### Unit 測試結構

```ruby
RSpec.describe RevenueCalculator do
  describe "需求：計算專案收益" do
    it "驗收：電費收入 - 管理費 = 淨收益" do
      calculator = described_class.new(
        electricity_income: 100_000,
        management_fee_rate: 0.05
      )

      result = calculator.calculate

      expect(result.net_profit).to eq(95_000)
    end
  end
end
```
