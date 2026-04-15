---
name: archive-telemetry
description: Archive Claude Code telemetry logs to dated files (YYYY-MM-DD~YYYY-MM-DD.json). Use when user wants to archive, rotate, or save telemetry logs.
version: 1.0.0
---

# Archive Telemetry

將 `~/claude-telemetry/logs.json` 歸檔到指定目錄，檔名以資料的日期範圍命名。

歸檔目錄解析順序：
1. 若環境變數 `CLAUDE_TELEMETRY_ARCHIVE_DIR` 有設定（例如指向 Google Drive 雲端同步資料夾），優先使用
2. 否則 fallback 到 `~/claude-telemetry/archive/`

## Instructions

### 1. 執行歸檔腳本

使用本 skill 的 base directory 執行 `scripts/archive.sh`（路徑由 Claude 根據 skill 載入位置解析，勿寫死絕對路徑）：

```bash
bash "${CLAUDE_PROJECT_DIR:-.}/.claude/skills/archive-telemetry/scripts/archive.sh"
```

若 skill 安裝在 user-level（`~/.claude/skills/archive-telemetry`），改用：

```bash
bash "$HOME/.claude/skills/archive-telemetry/scripts/archive.sh"
```

### 2. 解讀結果

腳本輸出格式為 `OK|檔案路徑|行數|檔案大小`。

成功時回報：
- 歸檔檔案路徑
- 包含幾筆紀錄
- 檔案大小

失敗時顯示 ERROR 訊息並說明原因。

### 3. 列出歸檔目錄

歸檔後列出目前所有歸檔檔案：

```bash
ls -lh ~/claude-telemetry/archive/
```

## Notes

- Log 路徑：`~/claude-telemetry/logs.json`
- 歸檔路徑：`${CLAUDE_TELEMETRY_ARCHIVE_DIR:-~/claude-telemetry/archive}/YYYY-MM-DD~YYYY-MM-DD.json`
- 可透過 `CLAUDE_TELEMETRY_ARCHIVE_DIR` 環境變數將歸檔導向團隊雲端資料夾（例如 Google Drive 共用雲端硬碟）
- 若同日期範圍已存在，自動加後綴 `_1`, `_2`...
- 歸檔後 Collector 會自動建立新的 logs.json 繼續寫入（使用 cp + truncate 保留 inode）
