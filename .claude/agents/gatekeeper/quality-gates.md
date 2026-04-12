# Quality Gates 詳細說明

## 0. Domain Gate (Domain 門檻)

| Criterion | Threshold |
|-----------|-----------|
| Domain Recorded | task.domain 必須已記錄 |
| Domain Format | 必須使用 `mcp__atdd__atdd_domain_list` 取得的標準名稱 |
| Cross-Domain Noted | 如有跨 domain 影響，必須已記錄 |

**驗證步驟**：
```
1. 檢查 task.domain 是否存在且非空
2. 對照 `mcp__atdd__atdd_domain_list(project)` 取得的標準名稱驗證格式正確
3. 如果任務涉及多個 domain，確認 context.relatedDomains 已記錄
```

**如果 Domain 未記錄**：
- 根據 modifiedFiles 推斷 domain
- 更新 task.domain 欄位
- 在報告中標註「⚠️ Domain 由 gatekeeper 補充」

## 1. Test Gate (測試門檻)

| Criterion | Threshold |
|-----------|-----------|
| Test Pass Rate | 100% |
| Coverage (new code) | >= 80% |
| No Skipped Tests | 0 |

## 2. Review Gate (審查門檻)

| Criterion | Threshold |
|-----------|-----------|
| Style Grade | >= B |
| Risk Level | <= Medium |
| Critical Issues | 0 |

## 3. Spec Gate (規格門檻)

| Criterion | Threshold |
|-----------|-----------|
| Scenarios Implemented | 100% |
| Acceptance Criteria | 100% |
| Business Rules | 100% |

## 4. Documentation Gate (文件門檻)

| Criterion | Threshold |
|-----------|-----------|
| Spec File | Exists |
| Code Comments | Adequate |
| API Docs | If applicable |

## 5. Cross-Domain Gate (跨 Domain 門檻)

| Criterion | Threshold |
|-----------|-----------|
| Impact Analysis | Done |
| Backward Compat | If breaking |
| Related Tests | If cross-domain |

**驗證步驟**：
```
1. MCP: mcp__atdd__atdd_domain_list(project="{project}")（取得所有 domain 與邊界）；如需單筆詳情用 mcp__atdd-admin__atdd_domain_get(domain_id)
2. 檢查主要 domain 的依賴和被依賴關係
3. 如果修改了被其他 domain 依賴的介面：
   - 確認是否向下相容
   - 確認相關測試是否通過
4. 如果無法驗證跨 domain 影響，標記為 CONDITIONAL
```

## 6. Acceptance Gate (驗收門檻)

| Criterion | Threshold |
|-----------|-----------|
| Unit Tests | 100% pass |
| Integration Tests | 100% pass |
| E2E Tests | See e2e-decision.md |
| Recording | If required |
