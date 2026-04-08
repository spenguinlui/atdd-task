---
description: Debug 經驗知識庫查詢工具。偵測調查卡住的行為訊號，並從知識庫中查詢相關的除錯提示。
---

# Debug Tips Query

## 輸入解析

用戶輸入格式：`/debug-tips {症狀描述}`

**範例**：
```
/debug-tips 2FA 登入失敗
/debug-tips N+1 查詢效能問題
/debug-tips Sidekiq 任務卡住
```

---

## Step 1: 解析關鍵字

從用戶輸入中提取關鍵字：

$ARGUMENTS → 拆分為關鍵字列表

**範例**：
- `2FA 登入失敗` → `["2FA", "登入", "失敗"]`
- `N+1 查詢效能` → `["N+1", "查詢", "效能"]`

---

## Step 3: 搜尋知識庫

在所有類型資料夾中搜尋匹配的 tips：

```bash
# 列出所有 tip 檔案
find debug-knowledge -name "*.yml" -not -name "tip-template.yml" -not -name "tag-taxonomy.yml"
```

對每個檔案，檢查是否匹配：
1. `identification.keywords` 是否包含輸入關鍵字
2. `identification.symptoms` 是否語意相似
3. `identification.error_patterns` 是否匹配

---

## Step 3: 輸出結果

### 找到匹配的 Tips

```markdown
┌──────────────────────────────────────────────────────┐
│ 💡 Debug Tips 查詢結果                               │
├──────────────────────────────────────────────────────┤
│                                                      │
│ 🔍 查詢：{用戶輸入}                                  │
│ 📊 找到 {N} 個相關提示                              │
│                                                      │
├──────────────────────────────────────────────────────┤
│                                                      │
│ 1️⃣ {tip_1.title}                                    │
│    📁 {type}/{filename}.yml                         │
│    📝 {tip_1.root_cause.summary}                    │
│                                                      │
│ 2️⃣ {tip_2.title}                                    │
│    📁 {type}/{filename}.yml                         │
│    📝 {tip_2.root_cause.summary}                    │
│                                                      │
└──────────────────────────────────────────────────────┘
```

詢問用戶要查看哪一個詳細內容。

### 顯示詳細內容

```markdown
┌──────────────────────────────────────────────────────┐
│ 📖 {tip.title}                                       │
├──────────────────────────────────────────────────────┤
│                                                      │
│ 🔍 問題根源：                                        │
│ {tip.root_cause.detailed_explanation}                │
│                                                      │
│ 📋 建議調查路徑：                                    │
│ 1. {step_1.action}                                   │
│    工具：{step_1.tools}                              │
│    目標：{step_1.target}                             │
│                                                      │
│ 2. {step_2.action}                                   │
│    ...                                               │
│                                                      │
│ ⚠️ 避免走彎路：                                      │
│ • {anti_pattern_1}                                   │
│ • {anti_pattern_2}                                   │
│                                                      │
│ 🔧 快速修復：                                        │
│ {solution.quick_fix.description}                     │
│                                                      │
│ ✅ 正式修復：                                        │
│ {solution.proper_fix.description}                    │
│                                                      │
│ 📚 相關資源：                                        │
│ • {reference_1}                                      │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### 未找到匹配

```markdown
┌──────────────────────────────────────────────────────┐
│ 📭 未找到匹配的 Debug Tips                           │
├──────────────────────────────────────────────────────┤
│                                                      │
│ 🔍 查詢：{用戶輸入}                                  │
│                                                      │
│ 這可能是一個新的問題類型。                           │
│                                                      │
│ 建議：                                               │
│ 1. 使用系統性方法調查問題                            │
│ 2. 解決後將經驗記錄到知識庫                          │
│                                                      │
│ 新增提示：                                           │
│ 複製範本到對應類型資料夾：                           │
│ cp debug-knowledge/tip-template.yml \               │
│    debug-knowledge/{type}/{描述}.yml                │
│                                                      │
│ 類型選擇：                                           │
│ • ui - 頁面/介面問題                                │
│ • data - 資料問題                                   │
│ • worker - 背景任務問題                             │
│ • performance - 效能問題                            │
│ • integration - 外部服務整合問題                    │
│ • alert - 監控警報問題                              │
│ • security - 安全/權限問題                          │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## 自動觸發模式

當 coder agent 處理 fix 任務時，此 Skill 會自動被觸發：

**觸發條件**（任一）：
- 重複嘗試相同方法失敗 >= 3 次
- 已執行 10+ 次工具呼叫但 MCP 任務資料仍無 `investigation.rootCause`
- 嘗試 3+ 個不同方向都沒結果

**Gate 機制**：
- fix 任務 development 階段，若 MCP 任務資料無 `investigation.rootCause` 和 `investigation.reproduction`，編輯程式碼會被 `confidence-gate.sh` 阻擋
- 阻擋訊息會提示使用 `/debug-tips` 查詢經驗庫

---

## 新增 Debug Tip

解決問題後，使用以下流程新增經驗到知識庫：

```bash
# 1. 確定問題類型
# ui | data | worker | performance | integration | alert | security

# 2. 複製範本
cp debug-knowledge/tip-template.yml \
   debug-knowledge/{type}/{描述性名稱}.yml

# 3. 編輯填入內容（參考範本中的說明）
```

**命名慣例**：
- 使用 kebab-case（小寫 + 連字符）
- 包含關鍵識別詞
- 範例：`2fa-local-user-mismatch.yml`、`sidekiq-dead-set-overflow.yml`
