# ATDD Hub - Agent 架構

詳細定義見各 Agent 檔案。工作流程見 `shared/task-flow-diagrams.md`。

| Agent | 角色 | Tools |
|-------|------|-------|
| specist | 規格專家 | Read, Glob, Grep, Write, AskUserQuestion, ATDD MCP |
| tester | 測試專家 | Read, Glob, Grep, Write, Edit, Bash, Chrome MCP, ATDD MCP |
| coder | 開發專家 | Read, Glob, Grep, Write, Edit, Bash, Chrome MCP, ATDD MCP |
| style-reviewer | 風格審查 | Read, Glob, Grep, ATDD MCP (唯讀) |
| risk-reviewer | 風險審查 | Read, Glob, Grep, WebSearch, ATDD MCP (唯讀) |
| gatekeeper | 品質把關 | Read, Glob, Grep, ATDD MCP |
| curator | 知識策展 | Read, Glob, Grep, AskUserQuestion, ATDD MCP |
| web-designer | 網頁設計 | Read, Glob, Grep, Write, Edit, Bash, Chrome MCP |
