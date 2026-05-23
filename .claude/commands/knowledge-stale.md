---
description: 盤點標記為過期/待修（stale）的 domain 知識節點，供 curator 逐筆修正
argument-hint: "[project]（可選，過濾專案）"
---

# 過期知識盤點

列出被標記 `stale=true`（與現況不符、待重新確認）的結構化知識節點。

## 執行步驟

1. 呼叫 `atdd_node_list(stale=true${ARGUMENTS:+, project=<由 $ARGUMENTS 解析>})`（有給專案就過濾）。
2. 依 domain / node_type 分組列出：`slug`、`title`、`change_reason`（為何被標 stale）、`node_id`。
3. 若清單為空 → 回報「目前無過期知識」。

## 輸出格式

```
🗂️ 過期知識（stale）盤點　[{project}]
─ {domain} / {node_type}
   • {slug} — {title}
     原因：{change_reason}　id：{node_id}
…
共 N 筆待修
```

## 收尾

> 過期知識**不自動修**。提示用戶：逐筆走 `/knowledge` 讓 curator 重新確認（[code]/[用戶] 來源），確認正確後 `atdd_node_update(node_id, stale=false, ...)`，仍不符則更新內容。

備註：本命令唯讀盤點。自動依時間判定過期（TTL）屬 server 端排程（`ports/worker/scheduler.py`），不在此命令範圍。
