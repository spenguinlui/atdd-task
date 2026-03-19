# ATDD Hub - 7 Agent 架構

本目錄包含 ATDD Hub 的 7 個專職 Agent，採用 Command-Driven 工作流程。

## 設計原則

### 1. 角色分離
- **specist**：規格專家，負責需求分析與規格撰寫
- **tester**：測試專家，負責測試生成與執行
- **coder**：開發專家，負責代碼實作
- **style-reviewer**：風格審查專家，負責代碼風格檢查
- **risk-reviewer**：風險審查專家，負責安全/效能/風險檢查
- **gatekeeper**：品質把關專家，負責最終品質門檻
- **curator**：知識策展者（DDD/Clean Architecture 專家），負責知識盤點與補正

### 2. 工具邊界
每個 Agent 只能使用特定工具：

| Agent | Tools | 說明 |
|-------|-------|------|
| specist | Read, Glob, Grep, SlashCommand, WebSearch | 唯讀 + spec-kit |
| tester | Read, Glob, Grep, Write, Edit, Bash | 可寫測試 |
| coder | Read, Glob, Grep, Write, Edit, Bash | 可寫代碼 |
| style-reviewer | Read, Glob, Grep | 唯讀審查 |
| risk-reviewer | Read, Glob, Grep, WebSearch | 唯讀審查 |
| gatekeeper | Read, Glob, Grep | 唯讀審查 + 知識識別 |
| curator | Read, Glob, Grep, Write, Edit, AskUserQuestion | 知識庫讀寫 + 對話 |

### 3. 流程整合
透過 Slash Command 自動觸發對應 Agent：

```
/feature → requirement → specification → testing → development → review → gate
              ↓             ↓              ↓           ↓           ↓       ↓
           specist      specist        tester      coder      reviewers  gatekeeper
```

---

## Agent 說明

### specist（規格專家）

**檔案**：`specist.md`

**職責**：
- 需求分析與澄清
- 信心度評估（95% 門檻）
- **範圍評估**（信心度達標後判斷是否上升 Epic）
- Given-When-Then 規格撰寫
- Domain 知識載入
- **Epic Planning**（/epic 時負責拆分子任務）

**工具**：`Read, Glob, Grep, SlashCommand, WebSearch, WebFetch`

**使用 spec-kit**：
```
/sk-new {需求描述}      # 建立新規格
/sk-continue {spec}     # 繼續規格
/sk {問題或指令}        # 一般互動
```

**信心度評估維度**：
1. 業務規則明確性
2. 邊界條件定義
3. 資料結構
4. 錯誤處理
5. 整合點

**範圍評估維度**（信心度 ≥ 95% 後執行）：
1. 跨 Domain 數量（≥ 3 建議上升 Epic）
2. 需要前置調查/清理（有則建議上升）
3. 預估驗收場景數（> 15 建議上升）
4. 無法單次交付完整價值（是則建議上升）

---

### tester（測試專家）

**檔案**：`tester.md`

**職責**：
- 根據規格生成測試
- 執行測試
- 分析失敗原因
- 建議修復方向

**工具**：`Read, Glob, Grep, Write, Edit, Bash`

**支援框架**：
- Ruby: RSpec
- JavaScript/TypeScript: Jest
- Python: Pytest

**測試模式**：
- ATDD (Acceptance Test-Driven Development)
- Given-When-Then 映射

---

### coder（開發專家）

**檔案**：`coder.md`

**職責**：
- 實作業務邏輯
- 讓測試通過
- 遵循 DDD 架構

**工具**：`Read, Glob, Grep, Write, Edit, Bash`

**DDD 模式**：
- Entity
- Service
- Repository
- Use Case

**Ruby 特定**：
- Dry::Monads (Result, Do notation)
- Use Case Pattern

---

### style-reviewer（風格審查）

**檔案**：`style-reviewer.md`

**職責**：
- 檢查命名規範
- 檢查語言慣用法
- 計算複雜度
- 評分（A/B/C/D）

**工具**：`Read, Glob, Grep, WebSearch, WebFetch`（唯讀）

**參考指南**：
- `style-guides/ruby.md`
- `style-guides/python.md`
- `style-guides/javascript.md`

**評分標準**：
| 分數 | 等級 | 說明 |
|------|------|------|
| 90-100 | A | 優秀 |
| 70-89 | B | 良好 |
| 50-69 | C | 可接受 |
| 0-49 | D | 需改進 |

---

### risk-reviewer（風險審查）

**檔案**：`risk-reviewer.md`

**職責**：
- 安全漏洞檢查（OWASP Top 10）
- 效能問題檢測
- 風險評估

**工具**：`Read, Glob, Grep, WebSearch, WebFetch`（唯讀）

**風險等級**：
| 等級 | 說明 | 處理 |
|------|------|------|
| Critical | 必須立即修復 | 阻擋 |
| High | 應盡快修復 | 阻擋 |
| Medium | 建議修復 | 警告 |
| Low | 可改進 | 記錄 |

**檢查項目**：
- SQL Injection
- XSS
- CSRF
- 認證/授權
- 敏感資料處理
- N+1 Query
- 記憶體洩漏

---

### gatekeeper（品質把關）

**檔案**：`gatekeeper.md`

**職責**：
- 檢查所有品質門檻
- Go/No-Go 決策
- 知識識別（識別新規則供 Curator 處理）

**工具**：`Read, Glob, Grep`

**品質門檻**：
| Gate | 條件 |
|------|------|
| Test Gate | 所有測試通過 |
| Review Gate | 審查評分 ≥ C |
| Spec Gate | 規格完整對照 |
| Doc Gate | 無遺漏 TODO |

**知識識別**：
發現新業務規則時，在 Gate Report 中輸出 Knowledge Discoveries。
後續由 `/feature` 命令流程決定是否啟動 Curator Agent。

---

### curator（知識策展者）

**檔案**：`curator.md`

**職責**：
- 盤點現有知識完整度
- 識別 Knowledge Gaps 和矛盾
- **以 DDD 視角審視 domain 結構**
- **以 Clean Architecture 視角評估邊界和依賴**
- 引導結構化對話補正
- 產出知識更新提案
- 確認後執行寫入

**工具**：`Read, Glob, Grep, Write, Edit, AskUserQuestion`

**專業知識**：

| 領域 | 專長 |
|------|------|
| DDD Strategic | Bounded Context, Context Mapping, Ubiquitous Language |
| DDD Tactical | Aggregate, Entity, Value Object, Domain Service, Domain Event |
| Clean Architecture | 依賴規則, 層次分離, 模組邊界 |

**觸發方式**：`/knowledge {project}, {domain}`

**工作流程**：
```
Phase 1: Knowledge Audit（知識盤點）
    → 讀取 ul.md, business-rules.md, strategic/{domain}.md, tactical/{domain}.md
    → fallback: contexts/{domain}.md（未遷移的 domain）
    → 評估信心度
    → 識別 Gaps, Conflicts, DDD 問題, 架構問題

Phase 2: Clarification（對話補正）
    → 針對問題使用 AskUserQuestion 詢問
    → 持續對話直到信心度 >= 90%

Phase 3: Proposal（知識更新提案）
    → 產生結構化提案
    → 等待用戶確認

Phase 4: Commit（知識寫入）
    → 確認後寫入各文件
    → 更新 Maintenance Log
```

**相關文件**：
- 存取規範：`knowledge/access/reader.md`, `knowledge/access/writer.md`
- Schema：`knowledge/schemas/*.yml`、`.claude/config/confidence/knowledge.yml`

---

## 工作流程

### Feature 完整流程

```
1. /feature {project}, {title}
   → 建立任務記錄
   → 進入 requirement 階段
   → 呼叫 specist

2. specist 與用戶對話
   → 評估信心度
   → 達 95% 後進行範圍評估

3. 範圍評估（信心度達標後）
   → 判斷是否建議上升 Epic
   → 用戶選擇維持 Feature 或轉為 Epic
   → 若維持 Feature，進入 specification

4. /continue
   → specist 撰寫規格
   → 使用 spec-kit 建立正式文檔

5. /continue
   → 進入 testing 階段
   → 呼叫 tester 生成測試

6. /continue
   → 進入 development 階段
   → 呼叫 coder 實作

7. /continue
   → 進入 review 階段
   → 呼叫 risk-reviewer（預設）
   → 呼叫 style-reviewer（僅 refactor）

8. /continue
   → 進入 gate 階段
   → 呼叫 gatekeeper
   → Go/No-Go 決定
```

### Epic 流程

```
1. /epic {project}, {title}
   → 呼叫 specist 進行 Epic Planning

2. specist Epic Planning
   → 識別涉及的 Domains
   → 拆分 Phases（調查/清理/設計/實作）
   → 識別子任務（T1.1, T1.2...）
   → 建立依賴關係
   → 輸出提案（不建立檔案）

3. 用戶確認/調整/取消
   → 確認：建立 Epic YAML + 子任務 JSON + 更新 Kanban
   → 調整：修改提案後重新確認
   → 取消：放棄建立

4. 執行子任務
   → /feature {project}, T1.1
   → 自動檢查依賴、更新 Epic 進度
```

### Fix 簡化流程

```
requirement → testing → development → review → gate
    ↓           ↓           ↓           ↓       ↓
 specist     tester      coder    risk-reviewer gatekeeper
```

- 跳過 specification 階段
- 信心度門檻 80%
- Review 只做 risk-reviewer

### Test 最小流程

```
requirement → testing → gate
    ↓           ↓        ↓
 specist     tester   gatekeeper
```

- 只寫測試，不改代碼
- 跳過 development 和 review

---

## 檔案結構

```
.claude/agents/
├── README.md           # 本文件
├── specist.md          # 規格專家
├── tester.md           # 測試專家
├── coder.md            # 開發專家
├── style-reviewer.md   # 風格審查專家
├── risk-reviewer.md    # 風險審查專家
├── gatekeeper.md       # 品質把關專家
└── curator.md          # 知識策展者（DDD/Clean Architecture 專家）
```

---

## 相關文檔

- **CLAUDE.md**: `CLAUDE.md` - AI 指令
- **操作手冊**: `docs/operation-manual.md`
- **Style Guides**: `style-guides/`
- **Domain 知識**: `domains/`

---

## Command 參考

### 任務啟動
| Command | 說明 |
|---------|------|
| `/feature {project}, {title}` | 新功能 |
| `/fix {project}, {title}` | Bug 修復 |
| `/refactor {project}, {title}` | 重構 |
| `/test {project}, {title}` | 補測試 |
| `/epic {project}, {title}` | 大型功能（Epic） |

### 知識管理
| Command | 說明 |
|---------|------|
| `/knowledge {project}, {domain}` | 單域知識討論 |
| `/knowledge {project}, {domainA}, {domainB}` | 跨域知識討論（邊界和整合點） |

### 任務控制
| Command | 說明 |
|---------|------|
| `/continue` | 進入下一階段 |
| `/status` | 查看進度（含 Epic） |
| `/abort` | 放棄任務 |
