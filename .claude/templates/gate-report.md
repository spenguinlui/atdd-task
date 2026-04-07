# Gate Report 格式

> Gatekeeper 輸出的品質門檻報告格式

## 報告結構

Gate Report 必須包含以下區塊：

### 1. 決策摘要

- 決策結果：GO / NO-GO / CONDITIONAL GO
- 任務資訊：專案、標題、ID

### 2. 門檻檢查

每個門檻顯示：
- 門檻名稱
- 檢查項目和結果（✅ PASS / ❌ FAIL）
- 總結（PASS / FAIL）

必要門檻：
- Domain 門檻
- 測試門檻
- 審查門檻
- 規格門檻
- 文件門檻
- 跨 Domain 門檻（如適用）
- 驗收門檻

### 3. 驗收測試摘要

- Profile 類型
- 各層測試結果（Unit / Integration / E2E）
- E2E 模式和狀態

### 4. Metrics 彙總

- 各 Agent 的 metrics
- 總計

### 5. 人工驗收指南（必須提供）

- 驗收清單
- E2E 錄製連結（如有）
- 手動驗收步驟
- 清理指令

### 6. 結案選項

- `/done` — Commit + 直接結案
- `/done --deploy` — Commit + 進入部署驗證（需後續 `/verify` 確認）
- `/commit` — 僅 Commit
- `/close` — 僅結案

## 輸出要素

報告必須包含的資訊：

1. **決策**：明確的 GO / NO-GO / CONDITIONAL
2. **門檻結果**：每個門檻的 PASS / FAIL
3. **Metrics**：Agent 執行統計
4. **驗收指南**：人工驗證步驟
5. **下一步**：結案選項

使用 markdown 結構化格式，包含清晰的區塊標題和分隔線。
