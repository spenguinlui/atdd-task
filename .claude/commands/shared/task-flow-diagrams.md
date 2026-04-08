# 任務流程圖

## Feature 流程

```
requirement → specification → testing → development → review → gate → (knowledge?) → completed
   specist      specist       tester      coder      reviewers  gatekeeper  curator
```

信心度 95% | 完整 specification | 雙 reviewer（risk + style 僅 refactor）

## Fix 流程（簡化）

```
requirement → testing → development → review → gate → (knowledge?) → completed
   specist     tester      coder    risk-reviewer gatekeeper  curator
```

信心度 80% | 跳過 specification | 只做 risk-reviewer

## Test 流程

### /test-create（建立套件）

```
requirement → 套件就緒
   specist（信心度 90%，固定 E2E）
```

### /test-run（執行套件）

```
setup(seed) → testing(E2E + GIF) → cleanup → 執行記錄保存
```

Tagged Data 策略：seed 加 test_run_id 標記，cleanup 只刪該標記的資料。

## 部署驗證流程（Gate 後）

| 路徑 | 說明 |
|------|------|
| `/done` | commit → completed（無部署驗證） |
| `/done --deploy` | commit → deployed → `/verify` → verified 或 `/escape` → escaped → 自動建立 /fix |

## 階段轉移

| 從 | 到 | 條件 |
|----|-----|------|
| requirement | specification/testing | 信心度達標 |
| specification | testing | /continue |
| testing | development/gate | /continue |
| development | review | 測試通過 |
| review | gate | /continue |
| gate | completed | /done, /close |
| gate | deployed | /done --deploy |
| deployed | verified | /verify |
| deployed | escaped | /escape |

允許循環：`testing ↔ development`（測試失敗）、`review → testing`（/fix-*）

## 風險分級（Deployed 驗證策略）

| 等級 | 條件 | 策略 |
|------|------|------|
| Low | refactor 或 healthy domain | 7 天無 fix 票自動 verified |
| Medium | 一般 feature 或 degraded domain | production 驗證後 /verify |
| High | 核心計算/金流 或 critical domain | 驗證 + 客戶確認後 /verify |
