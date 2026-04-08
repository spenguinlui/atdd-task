# AI 決策與澄清原則

## 核心原則
- 澄清 > 猜測
- 不確定性識別是專業行為
- 承認不知道比錯誤假設更有價值

## 自信度檢查機制
- 信心度 < 95% → 必須澄清
- 涉及業務邏輯假設 → 立即停止詢問
- 預設值或格式不明 → 先確認再實作

## 澄清範本
當遇到不確定情況時，使用以下格式：
"根據分析，我發現 [具體情況]，但 [不確定點]，請確認應該如何處理？"

## 錯誤處理原則（強制執行）
- 碰到執行錯誤時，**先聚焦在為何發生錯誤與該如何修復**
- **禁止**跳過錯誤、繞道而行、或切換成其他替代方式來迴避問題
- 正確流程：閱讀錯誤訊息 → 理解根因 → 修復原本的做法 → 重新執行
- 只有在確認原本做法確實不可行（而非只是有 bug）時，才可以提議替代方案

---

# 系統環境保護（強制執行）

> **禁止未經許可修改系統環境或依賴套件**

## 禁止操作清單

以下操作**必須先詢問並獲得明確許可**才能執行：

### 套件管理
- `bundle install` / `bundle update` / `gem install`
- `npm install` / `npm update` / `yarn add` / `pnpm add`
- `pip install` / `pip install --upgrade`
- `brew install` / `brew upgrade`

### 系統環境
- 修改 `.ruby-version` / `.node-version` / `.python-version`
- 修改 `rbenv` / `pyenv` / `nvm` 設定
- 修改 shell 設定（`.zshrc`, `.bashrc`）
- 修改環境變數

### 設定檔
- 修改 `Gemfile` / `package.json` / `requirements.txt`
- 修改 `Dockerfile` / `docker-compose.yml`
- 修改 CI/CD 設定（`.github/workflows/`）

## 正確做法

當需要上述操作時，使用以下格式詢問：

```
我發現需要 [操作描述]，原因是 [為什麼需要]。
這會影響：[影響範圍]
請問是否允許執行？
```

## 例外情況

以下操作**不需要**詢問：
- `bundle exec` 執行已安裝的指令
- `npm run` / `yarn run` 執行已定義的 script
- `pytest` / `rspec` / `jest` 執行測試
- 讀取設定檔（不修改）

---

# 專案目錄與版本管理（重要）

> **必須進入專案目錄才能取得正確的語言/框架版本**

專案配置定義於 `.claude/config/projects.yml`。在錯誤目錄執行會使用錯誤版本。

執行專案指令的 Agent（tester、coder）各自定義了 rvm/rbenv 初始化方式，請參考各 agent 定義。

---

# ATDD 任務工作流程

> **本專案使用 Command-Driven 工作流程。所有專案任務必須透過 Slash Command 啟動。**

## 命令速查

所有可用命令詳見 Skill 列表。常用啟動命令：
- `/feature`, `/fix`, `/refactor`, `/test` — 任務啟動
- `/continue`, `/status`, `/abort` — 任務控制
- `/done`, `/commit`, `/close` — 結案

---

# Context 傳遞機制

> Agent 間的 context 傳遞**不依賴對話記憶**，而是透過任務 JSON 檔案傳遞。

用戶可在任何階段轉移時安全地 `/clear` 清理對話。`/continue` 會自動讀取任務 JSON 恢復狀態。

