# Phase 0：現狀盤點結論

## 0-1 Command 分類

### MVP 遷移到 Server（PM Slack 端）
- `/feature` — PM 發起需求 + specist 多輪對話
- `/status` — PM 查任務狀態（Phase 5）

### Phase 5 補完
- `/knowledge` — PM 知識對話（curator）
- 看板功能（新建 Slack 命令）

### 留在 Dev Local（不遷移）
- 所有 `/test-*` 系列（17 個）
- `/fix-critical`, `/fix-high`, `/fix-all`
- `/refactor`, `/commit`, `/done`, `/continue`
- `/debug-tips`

### 淘汰
- `/atdd`, `/atdd-list`, `/atdd-status`, `/guide`

---

## 0-2 Agent 依賴

### Server 可調用（PM 端）
| Agent | 用途 | 備註 |
|-------|------|------|
| specist | 需求對話、規格產出 | AskUserQuestion → Slack thread |
| gatekeeper（輕量） | PM 驗收時判斷是否觸發知識迭代 | 不做完整 quality gate |
| curator | 知識對話 | 需 repo write access |

### 必須留在 Dev Local
| Agent | 原因 |
|-------|------|
| tester | Chrome MCP 綁死 local |
| coder | 需 Bash + 專案目錄 |
| style-reviewer | review 對象是 Dev 剛寫的 code |
| risk-reviewer | 同上 |
| gatekeeper（完整） | 技術 quality gate 留 local |

---

## 0-3 資料模型

### 新增狀態（僅 PM 任務觸發，Dev local 任務不受影響）

```
Feature (PM):
  requirement → specification → pending_dev → testing → development
  → review → gate → pending_acceptance → [accepted → knowledge? → completed]
                                        → [rejected → Dev 修改 → pending_acceptance]

Feature (Dev local，不變):
  requirement → specification → testing → development → review → gate → completed
```

### 向下相容機制

```
if task.ownership?.createdBy == "pm"
  → 走 PM 流程（有 pending_dev、pending_acceptance）
else
  → 走現有流程（直接 completed）
```

### 新增 JSON 欄位

```json
{
  "ownership": {
    "createdBy": "pm|dev",
    "currentOwner": "pm|dev",
    "pmSlackUserId": "U12345"
  },
  "slack": {
    "channelId": "C12345",
    "threadTs": "1234567890.123",
    "notificationTs": null
  },
  "acceptance": {
    "pmVerdict": null,
    "pmComment": null,
    "acceptedAt": null,
    "knowledgeTriggered": false
  }
}
```

---

## 0-5 資料量

| 資料類型 | 現有數量 | 大小 | 成長率 |
|---------|---------|------|--------|
| 任務 JSON | 244 | 1.9 MB | ~10/月 |
| 規格 | 85 | 696 KB | ~5/月 |
| 需求 | 92 | 460 KB | ~5/月 |
| Epic | 18 | 292 KB | ~1/月 |
| Domain | 36 | ~200 KB | 低頻 |
| **總計** | **~475 檔** | **~3.5 MB** | |

結論：JSON + Git 足夠，無需 DB。
