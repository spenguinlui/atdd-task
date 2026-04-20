---
description: 查看測試套件的執行歷史
---

# Test History: $ARGUMENTS

## 解析參數

格式：`{project}, {suite-id}` 或 `{project}, {suite-id}, {run-id}`

- `{project}`：專案 ID（必填）
- `{suite-id}`：套件 ID（必填）
- `{run-id}`：特定執行記錄（可選，查看詳細）

有效專案：見 `.claude/config/projects.yml`

---

## 流程

### 列出執行歷史

1. 掃描 `tests/{project}/suites/{suite-id}/runs/*/run.yml`
2. 依時間降序排列
3. 輸出摘要表格

### 查看特定執行

1. 讀取 `tests/{project}/suites/{suite-id}/runs/{run-id}/run.yml`
2. 輸出詳細資訊
3. 列出錄製檔案

---

## 輸出格式

### 執行歷史列表

```
📜 執行歷史：{suite-id} - {title}

| # | 時間 | 狀態 | 通過 | 失敗 | 跳過 | 耗時 |
|---|------|------|------|------|------|------|
| 1 | 2026-01-21 14:30 | ✅ passed | 16 | 0 | 0 | 8m 32s |
| 2 | 2026-01-20 10:15 | ❌ failed | 14 | 2 | 0 | 9m 45s |
| 3 | 2026-01-19 16:00 | ⚠️ aborted | 8 | 0 | 8 | 4m 12s |

共 3 次執行 | 通過率：66.7%

📌 查看詳細：/test-history {project}, {suite-id}, {run-id}
```

### 特定執行詳細

```
═══════════════════════════════════════════════════════════
📋 執行記錄：{run-id}

Suite: {suite-id} - {title}
Test Run ID: {test_run_id}
執行時間: 2026-01-20 10:15:32 ~ 10:25:17

📊 結果摘要：
- 狀態：❌ failed
- 總場景：16
- 通過：14
- 失敗：2
- 跳過：0
- 耗時：9m 45s

❌ 失敗場景：
┌──────┬───────────────────────────┬────────────────────────┐
│ 場景 │ 標題                      │ 錯誤                   │
├──────┼───────────────────────────┼────────────────────────┤
│ S10  │ 開立發票                  │ 按鈕無法點擊           │
│ S12  │ 同步發票                  │ 逾時                   │
└──────┴───────────────────────────┴────────────────────────┘

🎬 錄製檔案：
- S1-navigate-to-list.gif (2.5MB)
- S2-filter-accounts.gif (3.1MB)
- ... (共 16 個)

📁 目錄：
tests/{project}/suites/{suite-id}/runs/{run-id}/

🔗 關聯問題：
- ISSUE-004: CreateInvoiceByPeriod 傳入錯誤的 bill_id
  - 嚴重度：critical
  - Fix 任務：#abc123
═══════════════════════════════════════════════════════════
```

---

## 快速操作

```
📌 快速操作：

重新執行：/test-run {project}, {suite-id}
查看套件：/test-list {project}
比較執行：/test-history {project}, {suite-id}, compare
```

---

## 比較功能（進階）

若第三參數為 `compare`：

```
📊 執行比較：{suite-id}

| 場景 | #1 (最新) | #2 | #3 |
|------|-----------|-----|-----|
| S1 | ✅ | ✅ | ✅ |
| S2 | ✅ | ✅ | ❌ |
| S10 | ❌ | ❌ | ✅ |
| S12 | ❌ | ✅ | ✅ |

趨勢：S10, S12 自 #2 開始失敗
```

---

## 保留政策

執行記錄預設保留策略（可在 `suite.yml` 設定）：

```yaml
retention:
  maxRuns: 10           # 最多保留 10 次
  keepPassed: 3         # 保留最近 3 次 passed
  keepFailed: 5         # 保留最近 5 次 failed（供除錯）
```

超過限制時，`/test-run` 會自動清理舊記錄。
