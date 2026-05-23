# Gold scenario：specist 寫 spec 的 model 比對

**任務**：給定 `prompts/spec-task.md` 的需求（台電電費代收對帳），各 model 產出 spec，依下方客觀標準評分。

**比法**：同一份平面提示餵所有 model，不帶各自 agent 機制（公平比 model 在此任務的能力，非完整 specist runtime）。

## 評分標準（eval.sh 自動檢查，每項 1 分，共 7 分）

| # | 項目 | 通過條件 |
|---|------|----------|
| 1 | 信心度 | 出現百分比（如 `85%`）|
| 2 | 風險條數 | Risk Pre-mortem ≥ 3 條 |
| 3 | 風險類別多樣 | 涵蓋 ≥ 3 類（technical/domain/data/integration/ux）|
| 4 | 驗收標準 | 有 AC 列表（AC1…）|
| 5 | Given-When-Then | ≥ 1 個完整 G-W-T（Given/When/Then 或 假設/當/那麼）|
| 6 | BA 三段 | 含「需求摘要」「業務分析結論」「驗收條件」三標題 |
| 7 | BA 無技術洩漏 | BA 三段範圍內無 backtick / snake_case |

**領域陷阱**（高分 model 應自發覆蓋，人工複看用）：差額容差邊界（剛好 1 元算不算）、四捨五入、CSV 解析（引號內逗號 / 編碼 / CRLF）、孤兒紀錄反向（系統有台電無）、可重跑的去重鍵設計。

## 通過門檻
- 單次 ≥ 5/7 視為合格輸出。
- 跨 model 比較看：平均分、3 次穩定度（分數方差）、領域陷阱覆蓋。
