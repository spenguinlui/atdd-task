# 任務流程圖

## Feature 流程

```
/feature 啟動
    │
    ▼
┌─────────────────┐
│ 1. REQUIREMENT  │ ← specist
│    需求分析     │
│    信心度評估   │
└────────┬────────┘
         │ 信心度 >= 95%
         ▼
┌─────────────────┐
│ 2. SPEC         │ ← specist
│    撰寫規格     │
│    用戶確認     │
└────────┬────────┘
         │ /continue
         ▼
┌─────────────────┐
│ 3. TESTING      │ ← tester
└────────┬────────┘
         │ /continue
         ▼
┌─────────────────┐
│ 4. DEVELOPMENT  │ ← coder
└────────┬────────┘
         │ 測試通過
         ▼
┌─────────────────┐
│ 5. REVIEW       │ ← reviewers
└────────┬────────┘
         │ /continue
         ▼
┌─────────────────┐
│ 6. GATE         │ ← gatekeeper
└────────┬────────┘
         │ GO
         ▼
┌─────────────────┐
│ 7. KNOWLEDGE?   │ ← curator（條件式）
│    有新知識？    │   Gatekeeper 識別到新知識時觸發
└────────┬────────┘
         │
         ▼
    ✅ COMPLETED
```

## Fix 流程（簡化）

```
/fix 啟動
    │
    ▼
┌─────────────────┐
│ 1. REQUIREMENT  │ ← specist（信心度 80%）
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 2. TESTING      │ ← tester
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 3. DEVELOPMENT  │ ← coder
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 4. REVIEW       │ ← risk-reviewer only
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 5. GATE         │ ← gatekeeper
└────────┬────────┘
         │ GO
         ▼
┌─────────────────┐
│ 6. KNOWLEDGE?   │ ← curator（條件式）
│    有新知識？    │   Gatekeeper 識別到新知識時觸發
└────────┬────────┘
         │
         ▼
    ✅ COMPLETED
```

## Test 流程（套件建立 + 執行）

### /test-create（建立套件）

```
/test 或 /test-create 啟動
    │
    ▼
┌─────────────────┐
│ 1. REQUIREMENT  │ ← specist
│    識別範圍     │
│    規劃場景     │
│    定義資料需求 │
└────────┬────────┘
         │ 信心度 >= 90%
         ▼
    ✅ 套件就緒
```

### /test-run（執行套件）

```
/test-run 啟動
    │
    ▼
┌─────────────────┐
│ 1. SETUP        │ ← command
│    生成 run ID  │
│    執行 seed.rb │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 2. TESTING      │ ← tester
│    執行 E2E     │
│    錄製 GIF     │
│    記錄結果     │
└────────┬────────┘
         │ 測試完成
         ▼
┌─────────────────┐
│ 3. CLEANUP      │ ← command
│    執行 cleanup │
│    更新 stats   │
└────────┬────────┘
         │
         ▼
    ✅ 執行記錄保存
```

### Tagged Data 策略

```
seed.rb 建立資料時
    │
    ├── 資料加上 test_run_id 標記
    │   （存在 metadata 欄位）
    │
    ▼
cleanup.rb 清理時
    │
    └── 只刪除有該標記的資料
        （不影響其他測試）
```

## 部署驗證流程（Gate 後）

```
gate 通過 (GO)
    │
    ├── /done（傳統流程）── commit ──→ ✅ COMPLETED
    │   （無部署驗證時直接完成）
    │
    └── /done --deploy（啟用部署驗證時）
        │
        ▼
┌─────────────────┐
│ 7. DEPLOYED     │ ← 等待人工驗證
│    部署觀察期   │
│                 │   風險分級決定驗證策略：
│                 │   Low:  7天自動 verified
│                 │   Med:  你 production 驗證
│                 │   High: 你驗 + 客戶確認
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
/verify    /escape
    │         │
    ▼         ▼
✅ VERIFIED  ⚠️ ESCAPED
 (真正完成)   │
              ▼
         自動建立 /fix 任務
         （帶 causedBy 指向原任務）
```

## 階段轉移

| 從 | 到 | 觸發 |
|----|-----|------|
| requirement | specification | 信心度 >= 95% |
| specification | testing | /continue |
| testing | development | /continue |
| development | review | 測試通過 |
| review | gate | /continue |
| gate | completed | /done, /close（傳統流程） |
| gate | deployed | /done --deploy（啟用部署驗證） |
| deployed | verified | /verify（人工確認 production 正常） |
| deployed | escaped | /escape（production 發現問題） |
| verified | completed | 自動（verified 即為真正完成） |

## 允許循環

```
testing ↔ development  # 測試失敗時
review → testing       # /fix-critical 等
```

## 風險分級（Deployed 狀態的驗證策略）

| 風險等級 | 判斷條件 | 驗證策略 |
|---------|---------|---------|
| Low | refactor 或 domain=healthy 且 fix rate < 20% | 7 天無 fix 票自動 verified |
| Medium | 一般 feature 或 domain=degraded | 你 production 點一輪後 /verify |
| High | 核心計算/金流 或 domain=critical 或 跨域 > 70% | 你驗 + 客戶確認後 /verify |
