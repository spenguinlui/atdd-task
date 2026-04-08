# ATDD Hub - Agent 架構

詳細定義見各 Agent 檔案。工作流程見 `shared/task-flow-diagrams.md`。

| Agent | 角色 | Tools |
|-------|------|-------|
| specist | 規格專家 | Read, Glob, Grep, Write |
| tester | 測試專家 | Read, Glob, Grep, Write, Edit, Bash, Chrome MCP |
| coder | 開發專家 | Read, Glob, Grep, Write, Edit, Bash, Chrome MCP |
| style-reviewer | 風格審查 | Read, Glob, Grep (唯讀) |
| risk-reviewer | 風險審查 | Read, Glob, Grep, WebSearch (唯讀) |
| gatekeeper | 品質把關 | Read, Glob, Grep (唯讀) |
| curator | 知識策展 | Read, Glob, Grep, Write, Edit, AskUserQuestion |
| web-designer | 網頁設計 | Read, Glob, Grep, Write, Edit, Bash, Chrome MCP |
