---
name: ba-writing
description: BA 報告撰寫指引。在撰寫、審查或修改 BA 報告（-ba.md）時使用。確保 BA 報告使用純業務語言，不包含任何技術術語。
user-invocable: false
---

# BA 報告撰寫指引

## 讀者定位

BA 報告的讀者是 **PM、業務人員、非工程師 Stakeholder**。他們不理解程式碼、資料庫結構、框架概念。BA 報告必須讓他們在 Jira 上就能完整理解需求。

## 必要結構

BA 報告必須包含以下三個區塊（由 Hook `validate-spec-format.sh` 驗證）：

1. `## 需求摘要` — 用一段話說明這個需求要做什麼
2. `## 業務分析結論` — 條列式業務規則、範圍界定、邊界情況
3. `## 驗收條件` — 用戶可觀察到的行為變化

模板：`.claude/templates/ba-report-template.md`

## 語言規則

### 全中文撰寫

報告內容**完全使用中文**，禁止任何英文技術詞彙。唯一允許的英文是產品名稱本身（如 ERP、ACH、xlsx）。

### 禁止出現

- Class / Model / Method 名稱（如 `ErpPeriod`、`User`、`Roof::Owner`）
- 資料表名稱（如 `unchanged_contract_programs`、`payments`）
- 技術術語（如 eager loading、N+1、query、migration、schema、serializer、decorator、partial、callback）
- 程式碼片段、檔案路徑
- backtick 包裹的任何內容
- 底線命名（snake_case）、雙冒號（::）等程式語法

### 必須使用

- 業務人員日常用語（「欄位」、「頁面」、「金額」、「單據」）
- 用戶介面上看得到的名稱（頁面標題、按鈕文字、欄位名稱）
- 用戶可觀察的行為描述（「顯示」、「空白」、「計算」、「下載」）
- 業務規則的白話表述

## 語言邊界對照表

以下對照表說明 BA 報告（業務語言）與 SA/Requirement（技術語言）的翻譯關係。撰寫 BA 時，所有左欄的技術表達都必須轉換為右欄的業務表達：

| 技術語言（SA 區可用） | 業務語言（BA 必須用） |
|---------------------|---------------------|
| `unchanged_contract_programs` table | 未換約紀錄 |
| `User` model / `Roof::Owner` | 用戶 / 屋主 |
| `account_identifier` 欄位 | 帳號識別碼 |
| 從 `payment.type` 判斷 | 依據款項類別判斷 |
| `ErpPeriod.period_number` | ERP 週期編號 |
| `preload_document_links` 機制 | 從對應的 ERP 單據取得 |
| eager loading / N+1 | （不需提及，屬於效能實作細節） |
| `Document.nil?` 時 render blank | 單據未拋轉時顯示空白 |
| 修改 view partial + decorator | 新增顯示欄位 |
| query / migration / schema | （不需提及，屬於技術實作細節） |
| `serializer` 新增欄位 | 匯出檔案新增欄位 |
| `U_{id}` 格式 | 用戶代碼格式為「U + 編號」 |
| `where(user_id: ...).exists?` | 查詢該用戶是否有紀錄 |
| `preload` / `includes` | （不需提及，屬於效能實作細節） |
| 修改 controller / action | 調整頁面功能 |
| 新增 scope / filter | 新增篩選條件 |

## 驗收條件撰寫規範

### 區分「查看」和「操作」

驗收條件必須明確區分**只看**（Read）和**有操作**（Write）的場景。涉及資料變更的 AC 必須包含完整的操作循環，不能只描述「顯示正確」。

```
❌ 模糊（容易讓 E2E 只驗證顯示就通過）
  AC1: 費用開關選「是」時，顯示費率輸入欄位

✅ 明確（強制 E2E 完成完整操作）
  AC1: 費用開關選「是」時顯示費率輸入欄位，修改費率後儲存成功，重新載入頁面確認費率已更新
```

### 多頁面功能必須逐頁列出

同一功能出現在多個頁面時，不可合併為一個 AC。每個頁面是獨立的驗收對象，因為背後的儲存路徑可能不同。

```
❌ 合併（讓 E2E 只測一個頁面就標通過）
  AC1: 費率欄位正確顯示（適用兩個頁面）

✅ 逐頁列出
  AC1a: 「單據帳戶管理」頁面 — 修改費率 → 儲存 → 驗證
  AC1b: 「用電戶契約資訊」頁面 — 修改費率 → 儲存 → 驗證
```

## 自我檢查清單

寫完 BA 報告後，逐行掃描以下信號。任何一項出現都代表技術洩漏，必須改寫：

- [ ] backtick（`` ` ``）
- [ ] 底線命名（`snake_case`，連續小寫字母中間有底線）
- [ ] 雙冒號（`::`，如 `Roof::Owner`）
- [ ] 英文類別名（首字母大寫的英文單字，如 `Payment`、`Document`）
- [ ] 檔案路徑（含 `/` 的字串，如 `app/models/...`）
- [ ] 括號內的英文方法（如 `.where()`、`.find()`）

## 好的 BA 報告範例

```markdown
## 需求摘要

在「加入 ERP 週期」頁面，將原本混在週期下拉選單中的「新建週期」選項
獨立出來，改為一個開關。開關打開時可直接建立新週期並送出，關閉時需
先選擇既有週期。

## 業務分析結論

- 適用頁面：電費單和屋頂租金的「加入 ERP 週期」頁面
- 開關預設為「開啟」狀態，因為實務上大多數操作是建立新週期
- 開關開啟時，週期下拉選單隱藏，按「確定」直接建立新週期
- 開關關閉時，顯示週期下拉選單，列出現有草稿狀態的同類型週期
- 不影響後續的匯出、核准、開票等流程

## 驗收條件

- 「加入 ERP 週期」頁面出現「新建週期」開關，預設為開啟
- 開關開啟時看不到週期下拉選單，按「確定」後系統自動建立新週期
- 開關關閉時顯示週期下拉選單，選擇週期後按「確定」加入帳款
```

## 壞的 BA 報告範例（技術洩漏）

```markdown
## 需求摘要

從 `unchanged_contract_programs` table 判斷 User 是否換約，
在 ACH 匯出的 serializer 新增 3 個欄位。

## 業務分析結論

- 用 `account_identifier` 拆出 type 和 id
- `Roof::Owner` 不適用換約判斷
- 需要 eager loading 避免 N+1

## 驗收條件

- serializer 輸出包含 user_type, user_number, is_unchanged
```

上面這段**全部不合格**：有 backtick、snake_case、Class 名稱、技術術語。
