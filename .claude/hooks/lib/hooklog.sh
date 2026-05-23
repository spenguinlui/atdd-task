#!/bin/bash
# 共用：把 hook 觸發/決策留痕到 .claude/.hook-log.jsonl
# 用法：hooklog <hook-name> <decision> [detail]
#   decision: allow | block | halt | warn | recorded ...
# 目的：防「閘門靜默死掉沒人發現」——有 log 才看得出 hook 真的在跑、擋了什麼
hooklog() {
  local f="${CLAUDE_PROJECT_DIR:-.}/.claude/.hook-log.jsonl"
  local detail="${3:-}"
  detail="${detail//\"/\'}"
  printf '{"ts":"%s","hook":"%s","decision":"%s","detail":"%s"}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" "$detail" >> "$f" 2>/dev/null || true
}
