# 驗收 Profile 指南

本文件為驗收 Profile 的索引頁。ATDD task 的驗收分為 Feature 與 Fix 兩大類：

| 文件 | 說明 |
|------|------|
| [Feature 驗收 Profile](feature-profiles.md) | 4 個 Profile（e2e / integration / calculation / unit）、選擇決策樹 |
| [Fix 驗收 Profile](fix-profiles.md) | 7 個 Profile、14 個 Discovery Source 調查流程、Affected Layer 對照 |

機器可讀的完整定義請見：
- `acceptance/registry.yml` — Feature Profile 配置
- `acceptance/fix-profiles.yml` — Fix Profile 與 Affected Layer
- `acceptance/fix-discovery-flows.yml` — 14 個 Discovery Source 調查流程
