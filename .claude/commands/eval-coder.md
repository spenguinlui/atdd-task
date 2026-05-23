---
description: 實驗室比較（coder）— 同一真實票，Claude 與 gpt-5.5 各自在封閉沙箱改 code、跑驗收測試，比正確度+token
argument-hint: "<project> <ticket>   例：sf_project CST-145"
---

# 行為比較器（coder 階段）

對**一個真實票**比較各引擎把任務改對的能力（正確度由隱藏驗收測試 pass/fail 判定）+ token 成本。

## 執行
1. $ARGUMENTS 為空 → 先 `bash experiments/atdd-eval/list-candidates.sh <project>` 列候選（按改動規模排序），請用戶挑**大型改動**的票（小改動分不出強弱）。
2. 跑 `bash experiments/atdd-eval/eval-coder.sh $ARGUMENTS`（**背景跑**：各引擎實際改 code + 跑測試，需數分鐘 × 引擎數）。
3. 完成後貼結果表：各引擎 `pass/total`、`tokens`、`cost`、耗時；以 **gold 為基準**解讀（pass 越接近 gold 越正確）。

預設比 `gold`（真實人類修復）、`claude:claude-sonnet-4-6`、`codex:gpt-5.5`；可在參數後自訂引擎清單。

## 前置
- 該專案 docker 測試容器要在跑（`docker ps`）。
- 比 gpt-5.5 需 `codex login` 已完成。
- 機制：worktree@base（不動 target 本體、跑完即清）+ 隔離 test DB（不碰共用 DB）。
