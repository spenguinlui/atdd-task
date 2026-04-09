# Triage Bot 部署指南

## Phase 1 + Phase 2 實現完成

本文檔指導如何部署 Business Triage Bot。

---

## 前置要求

### Slack 設定
1. **建立獨立 Slack App** (不要使用現有的 PM Bot 應用)
   - 應用名稱：`Triage Bot`
   - 選擇 Socket Mode：啟用
   - 複製 Bot Token 和 App Token

2. **設定權限 (OAuth Scopes)**
   ```
   - chat:write
   - chat:write.public
   - commands
   - app_mentions:read
   ```

3. **啟用 Socket Mode**
   - 在 App Settings → Socket Mode 中啟用
   - 生成並複製 App Token (`xapp-...`)

### Jira 設定
1. **建立 API Token**
   - Atlassian Account → Security → API tokens
   - 生成新 token，複製內容

2. **確認 Project Key**
   - 在 Jira 中找到目標 project 的 key（如 `CORE`）

3. **Slack Channels**
   - 建立專用 channel：`#triage-reports` (業務報告)
   - 建立專用 channel：`#pm-triage-review` (PM review)
   - 記錄 Channel IDs（`C0XXXXXXX` 格式）

### 本地準備
1. **Code repos clone** 到 EC2
   ```bash
   mkdir -p /opt/repos
   cd /opt/repos
   git clone <repo-url> core_web
   git clone <repo-url> sf_project
   # ... 根據實際項目
   ```

2. **atdd-hub clone** 到 EC2
   ```bash
   mkdir -p /opt
   cd /opt
   git clone <atdd-hub-repo> atdd-hub
   ```

---

## 環境變數配置

編輯 `infrastructure/.env`：

```bash
# Triage Bot - Slack
TRIAGE_BOT_TOKEN=xoxb-your-bot-token
TRIAGE_APP_TOKEN=xapp-your-app-token
TRIAGE_CHANNEL_ID=C...           # #triage-reports channel ID
PM_CHANNEL_ID=C...               # #pm-triage-review channel ID
RD_LEAD_SLACK_USER_ID=U...       # @rd-lead user ID

# Triage Bot - Jira Cloud
JIRA_BASE_URL=https://team.atlassian.net
JIRA_EMAIL=triage-bot@company.com
JIRA_API_TOKEN=ATATT...          # 從 Jira API tokens 頁面複製
JIRA_PROJECT_KEY=CORE             # 預設 project
JIRA_ISSUE_TYPE=Bug               # Bug 或 Task

# 路徑設定
ATDD_HUB_PATH=/opt/atdd-hub
REPOS_PATH=/opt/repos

# Claude
CLAUDE_MODEL=claude-sonnet-4-6
```

---

## 部署步驟

### 1. 建立 Docker image

```bash
cd infrastructure
docker-compose build triage-bot
```

### 2. 啟動容器

```bash
docker-compose up -d triage-bot

# 驗證運行
docker-compose logs -f triage-bot
```

### 3. 初始化 Claude 認證

```bash
# 進入容器
docker-compose exec triage-bot bash

# 登入 Claude CLI（需要 Anthropic API key）
claude login

# 確認可以執行 Claude
claude -p "你好" --model claude-sonnet-4-6 --output-format json

# 退出
exit
```

### 4. 在 Slack 中測試

1. 進入 #triage-reports channel
2. 輸入 `/report` 命令
3. 填寫表單：
   - 系統：選擇一個 project
   - 問題描述：輸入測試問題（如「測試問題」）
4. 點擊「開始分析」
5. 按照 Bot 的問題回答（選擇選項）
6. 完成訪談後按「確認立單」

---

## 故障排除

### Slack Bot 無響應

```bash
# 檢查 logs
docker-compose logs triage-bot | tail -50

# 常見原因：
# 1. TRIAGE_BOT_TOKEN 或 TRIAGE_APP_TOKEN 無效
# 2. TRIAGE_CHANNEL_ID 錯誤（需要 Bot 在 channel 中）
```

### Claude 執行失敗

```bash
# 驗證 Claude CLI 已登入
docker-compose exec triage-bot claude -p "test" --output-format json

# 如果失敗，重新登入
docker-compose exec triage-bot bash
claude login  # 輸入 API key
exit
```

### Jira 建票失敗

```bash
# 檢查 Jira 連接
docker-compose exec triage-bot python3 -c "
import os
from jira_client import _request
try:
    result = _request('GET', '/rest/api/3/projects')
    print('Jira 連接正常')
    print(result)
except Exception as e:
    print(f'Jira 連接失敗: {e}')
"

# 檢查環境變數
docker-compose exec triage-bot env | grep JIRA
```

---

## 驗收清單 (Phase 1 + 2)

### Phase 1：訪談流程
- [ ] `/report` 命令彈出 Modal ✓
- [ ] 填寫後進入 Round 1 訪談 ✓
- [ ] 業務選擇選項後進入 Round 2 ✓
- [ ] Round 3 顯示摘要確認 ✓
- [ ] 全程使用中文業務語言（無技術術語）✓
- [ ] Slack 按鈕友好（無 Markdown 表格）✓

### Phase 2：Jira 立單
- [ ] 業務按「確認立單」→ Jira 票自動建立 ✓
- [ ] 票包含完整信息（問題描述、優先級、受影響範圍）✓
- [ ] PM channel 收到通知 ✓
- [ ] Jira 票連結可點擊 ✓
- [ ] 優先級映射正確（P0→Highest, P1→High...）✓
- [ ] Labels 包含 `triage-auto` 和 `awaiting-pm-review` ✓

### 邊界條件
- [ ] 現有 PM Bot (`/feature`, `/knowledge`) 不受影響 ✓
- [ ] P0 時同時 DM PM + RD Lead ✓
- [ ] 業務選擇「補充說明」後回到訪談 ✓
- [ ] 業務選擇「取消」後清理 state ✓

---

## 下一步 (Phase 3)

當 Phase 1 + 2 穩定運行後，實施 Phase 3：

- 代碼分析（Glob/Grep 定位受影響模組）
- 相似歷史票查詢
- AI 自動生成分析報告
- P0 緊急升級機制

詳見 `/home/caesar/workspace/atdd-task/.claude/plans/wiggly-churning-moth.md` Phase 3 部分。

---

## 常用命令

```bash
# 查看日誌
docker-compose logs -f triage-bot

# 重啟服務
docker-compose restart triage-bot

# 進入容器 debug
docker-compose exec triage-bot bash

# 清理 state 文件（清除所有對話記錄）
docker-compose exec triage-bot rm ~/atdd-server/triage-conversations.json
```

---

## 支援聯絡

如有問題，請檢查：
1. Slack App 權限和 token
2. Jira API token 有效性
3. Claude CLI 已登入
4. EC2 路徑正確（`/opt/atdd-hub`, `/opt/repos`）
