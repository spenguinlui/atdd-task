---
description: 執行 Domain 全面診斷（任務健康度 + 程式碼品質 + 邊界分析）
---

# Domain Diagnose: $ARGUMENTS

執行指定 domain 或整個專案的全面健康診斷，產出診斷報告。

## 解析參數

格式：`{project}[, {domain}]`

- `/domain-diagnose core_web` → 全專案診斷
- `/domain-diagnose core_web, ElectricityBilling` → 單一 domain 診斷

有效專案：見 `.claude/config/projects.yml`

---

## 執行步驟

### Phase 1: 任務健康度分析

```
1. MCP: mcp__atdd__atdd_domain_list(project="{project}")（取得所有 domain 健康度）
2. 單一 domain 詳情：mcp__atdd-admin__atdd_domain_get(domain_id)
3. 擷取目標 domain（或全部 domain）的健康指標
4. 整理：fix rate, coupling rate, change frequency, knowledge coverage, escape rate
```

### Phase 2: 程式碼品質掃描（需要進入專案目錄）

根據專案的技術棧執行靜態分析。先確認專案路徑（從 `.claude/config/projects.yml` 讀取）。

**Ruby/Rails 專案**：
```bash
cd {project_path}

# Style: RuboCop（如已安裝）
bundle exec rubocop {domain_path} --format json 2>/dev/null || echo "RuboCop not available"

# Complexity: Flog（如已安裝）
bundle exec flog {domain_path} 2>/dev/null | head -20 || echo "Flog not available"

# Smells: Reek（如已安裝）
bundle exec reek {domain_path} --format json 2>/dev/null || echo "Reek not available"
```

**注意**：如果工具未安裝，跳過該項目並在報告中標註「未安裝」。**不要自行安裝套件。**

### Phase 3: 邊界分析

```
1. Grep: 找出 domain 相關檔案（models, services, controllers）
2. 分析 require/include 語句，找出跨 domain 引用
3. 對比 domain-health.json 中的 coupling pairs
4. 識別 boundary violations（A domain 的 code 直接引用 B domain 的 internal class）
```

### Phase 4: 命名一致性

```
1. MCP: mcp__atdd__atdd_term_list(project="{project}") → 擷取所有 UL 術語
2. Grep: 在 domain 相關程式碼中搜尋命名不一致
   - UL 定義 "ElectricBill" 但 code 用 "PowerBill" / "EBill"
   - UL 定義 "計費週期" 但 code 用 period / billing_cycle / term
3. 列出不一致項目
```

### Phase 5: 產出報告

輸出格式：

```markdown
# Domain 診斷報告：{domain}
日期：{date} | 專案：{project}

## 健康度卡片
┌────────────────────────────────┐
│  Health Score:  {score} / 100  │
│  Status:        {status}      │
│  Fix Rate:      {fix_rate}%   │
│  Coupling:      {coupling}%   │
│  Knowledge:     {coverage}%   │
└────────────────────────────────┘

## 程式碼品質
  RuboCop: {offense_count} offenses ({types})
  Flog 最高複雜度: {class}#{method} = {score}
  Reek: {smell_count} smells ({types})
  （未安裝的工具標註 N/A）

## 邊界分析
  跨域引用: {count} 處
  - {file}:{line} → 引用 {other_domain}::{class}
  Boundary violations: {count}

## 命名一致性
  UL 術語數: {term_count}
  不一致項目: {count}
  - UL: "{ul_term}" ↔ Code: "{code_term}" ({file})

## 重構建議（依優先序）
  1. [P0] {建議}
  2. [P1] {建議}
  3. [P2] {建議}

## 與上次診斷比較（如有歷史）
  Health Score: {prev} → {current} ({trend})
  Fix Rate: {prev} → {current}
```

如果指定 `--save`，將報告存入 `diagnostics/{project}/{domain}-{date}.md`。
