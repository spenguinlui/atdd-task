---
description: 列出專案的測試套件清單
---

# Test List: $ARGUMENTS

## 解析參數

格式：`{project}` 或 `{project}, {group}`

- `{project}`：專案 ID（必填）
- `{group}`：群組名稱（可選，如 `smoke`, `regression`, `erp-period`）

有效專案：見 `.claude/config/projects.yml`

---

## 流程

1. **讀取索引檔案**：`tests/{project}/index.yml`

2. **若索引不存在**：
   - 掃描 `tests/{project}/suites/*/suite.yml`
   - 自動建立 `index.yml`

3. **若指定群組**：
   - 篩選該群組的套件

4. **輸出表格**

---

## 輸出格式

### 全部套件

```
📋 測試套件清單：{project}

| Suite ID | 標題 | Domain | 場景 | 上次執行 | 狀態 | 通過率 |
|----------|------|--------|------|----------|------|--------|
| E2E-T0 | 環境盤點 | - | 6 | 2026-01-20 | ✅ passed | 100% |
| E2E-A1 | 電費單 Happy Path | ErpPeriod | 16 | 2026-01-21 | ❌ failed | 75% |
| E2E-A2 | 屋頂租金 Happy Path | ErpPeriod | 12 | - | ⏸️ never | - |

共 3 個套件 | 可執行：/test-run {project}, {suite-id}
```

### 群組套件

```
📋 測試群組：{project} / {group}

| Suite ID | 標題 | 場景 | 上次狀態 |
|----------|------|------|----------|
| ... |

執行全部：/test-run {project}, group:{group}
```

---

## 快速操作提示

```
📌 快速操作：

執行單一套件：/test-run {project}, {suite-id}
執行群組測試：/test-run {project}, group:{group}
執行全部測試：/test-run {project}, all
查看套件歷史：/test-history {project}, {suite-id}
建立新套件：  /test-create {project}, {title}
```

---

## 狀態圖示

| 狀態 | 圖示 |
|------|------|
| passed | ✅ |
| failed | ❌ |
| aborted | ⚠️ |
| never | ⏸️ |

---

## 索引檔案格式

參考：`acceptance/templates/test-index.yml`

```yaml
projectId: "{project}"
updatedAt: "ISO_timestamp"

suites:
  - id: "E2E-T0"
    title: "環境盤點"
    domain: null
    scenarios: 6
    lastRun: "2026-01-20"
    lastStatus: "passed"
    passRate: "100%"

groups:
  smoke:
    description: "快速冒煙測試"
    suites: ["E2E-T0"]
```
