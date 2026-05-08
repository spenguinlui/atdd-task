# Specist - /test-create 模式

`/test-create`（或 `/test`）任務建立可重複執行的測試套件。

## 工作內容

1. Domain 識別
2. 測試範圍定義
3. 場景清單規劃
4. 前置條件定義
5. 資料需求分析（供 seed 腳本使用）

## 信心度

- 閾值：90%（較 feature 低）
- 不需 ATDD Profile 選擇（固定 E2E）

## 產出物

1. **更新 suite.yml**：`domain.primary` / `domain.related` / `validationCriteria` / `scenarios`
2. **建立場景 YAML**：`scenarios/S{n}-{name}.yml`，含 Given-When-Then
3. **定義資料需求**：供 tester 生成 `fixtures/seed.rb`

## 套件目錄結構

```
tests/{project}/suites/{suite-id}/
├── suite.yml           # ← 更新
├── scenarios/          # ← 建立
│   ├── S1-{name}.yml
│   └── S2-{name}.yml
├── fixtures/           # ← 建立結構（tester 填入）
│   ├── seed.rb
│   └── cleanup.rb
└── runs/               # 執行時建立
```

## 與舊 /test 的差異

| 面向 | 舊 /test | 新 /test-create |
|------|----------|-----------------|
| 目錄 | `tests/{project}/{uuid}/` | `tests/{project}/suites/{suite-id}/` |
| 定義檔 | `test.yml` | `suite.yml` |
| 可重複 | ❌ 一次性 | ✅ 可重複執行 |
| 資料策略 | Prefix | Tagged Data |
