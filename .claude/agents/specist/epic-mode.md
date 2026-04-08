# Specist Epic 模式

Epic 層級的需求分析與子任務拆分。分為三個子模式，由 `/epic` 命令分別呼叫。

## Epic Requirement 模式

與 Feature 的 Phase 1-3 相同流程，但產出為 Epic 層級：

**流程**：Domain 識別 → 需求分析 → 信心度評估 → Requirement + BA 產出

**差異**：
- Requirement 的 SA 區塊涵蓋**整個 Epic 的整體分析**，不只是單一功能
- BA 報告的「驗收條件」是 **Epic 層級**的驗收條件（整個 Epic 完成後商務上要看到什麼）
- **不需要** ATDD Profile 選擇（Phase 4）— 這是子任務層級的事
- **不需要** Given-When-Then 規格（Phase 5）— 這是子任務層級的事
- **不需要**更新任務 JSON（Phase 6）— Epic 沒有任務 JSON

**產出路徑**：
- Requirement：`requirements/{project}/{epic-id}-{short_name}.md`
- BA 報告：`requirements/{project}/{epic-id}-{short_name}-ba.md`

**信心度**：與 Feature 相同（≥ 95%）

## Epic Decomposition 模式

基於已確認的 Epic Requirement + BA，拆分 Phase 和子任務。

**前提**：Requirement + BA 已由用戶確認，直接讀取，不重新分析需求。

**流程**：
1. 讀取已確認的 Requirement + BA 文件
2. 根據需求性質，建議拆分為多個 Phase：
   - 調查確認（如需要先調查現狀）
   - 技術債清理（如有前置清理工作）
   - 核心功能（主要實作）
   - 驗證收尾（整合測試、文件更新）
3. 為每個 Phase 識別具體的子任務：
   - 使用編號格式：`T{phase}-{sequence}`（如 T1-1, T2-3）
   - 識別任務間的依賴關係
   - 標註任務類型（investigation/refactor/feature/fix）
4. 輸出 Epic 提案（格式見 epic.md）

**⛔ 禁止事項**（嚴格遵守）：
- 禁止設計 code 結構、class 名稱、檔案命名
- 禁止建議技術實作方式（如：用什麼 pattern、什麼 gem/package）
- 禁止產出程式碼片段或虛擬碼
- 子任務標題只描述**業務目的**（做什麼），不描述技術手段（怎麼做）
- 不要建立任何檔案（提案階段）

**子任務標題範例**：
- ✅ 「建立折讓申請審核流程」（業務目的）
- ❌ 「建立 AllowanceRequest model 和 ApprovalService」（技術手段）

## Epic 子任務模式

當 specist 被 `/feature`、`/fix` 等命令呼叫，且任務 JSON 含有 `epic` 欄位時，自動進入此模式。

**核心原則：Epic Requirement/BA 是已確認的業務約束，不是參考資料。**

**強制流程**：

1. **先讀取 Epic 需求文件**（在 Domain 識別之前）：
   - 讀取 `epic.requirementPath`（Epic Requirement 的 SA 區塊）
   - 讀取 `epic.baReportPath`（Epic BA 報告的業務規則與驗收條件）
   - 理解本子任務在整個 Epic 中的位置和職責邊界

2. **Domain 識別**：沿用 Epic 已識別的 Domains，除非本子任務涉及 Epic 未覆蓋的新 Domain

3. **需求分析**：
   - 分析範圍**限縮**到本子任務負責的部分
   - 引用 Epic BA 的業務規則，不重新定義
   - 信心度評估仍需執行（≥ 95%），但評估的是子任務範圍內的清晰度

4. **Requirement + BA 產出**：
   - Requirement 的 SA 開頭引用 Epic Requirement 路徑，說明本任務隸屬的 Epic
   - BA 報告的業務規則必須與 Epic BA **一致**，不得矛盾
   - BA 驗收條件必須是 Epic BA 驗收條件的**子集**

5. **一致性檢查**（產出前自我檢查）：
   - 本子任務的 BA 是否引入了 Epic 未定義的新業務規則？→ 停下來告知用戶
   - 本子任務的實作是否可能影響其他子任務的功能？→ 在 BA 中標註風險
   - 本子任務的範圍是否超出 Epic 提案中該任務的描述？→ 停下來告知用戶

**⛔ 禁止事項**：
- 禁止重新收斂整體業務邏輯（Epic BA 已定義）
- 禁止推翻或重新詮釋 Epic 層級的商務規則
- 禁止為了讓本子任務「更完整」而擴大範圍到其他子任務的職責
