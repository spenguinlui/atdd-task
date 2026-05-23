#!/bin/bash
# 跑 specist spec-writing 平面提示，比對不同 engine/model
# Usage: run.sh <claude|codex> <model> [n_runs]
#   claude: run.sh claude claude-opus-4-7 3
#   codex : run.sh codex  <gpt-model-id> 3
set -u
ENGINE="${1:?engine: claude|codex}"
MODEL="${2:?model id}"
N="${3:-3}"
DIR="$(cd "$(dirname "$0")" && pwd)"
PROMPT="$(cat "$DIR/prompts/spec-task.md")"
mkdir -p "$DIR/runs"
safe_model="${MODEL//\//_}"

for i in $(seq 1 "$N"); do
  OUT="$DIR/runs/${ENGINE}-${safe_model}-${i}.txt"
  case "$ENGINE" in
    claude) claude -p "$PROMPT" --model "$MODEL" --permission-mode bypassPermissions > "$OUT" 2>"$OUT.err" ;;
    codex)  codex exec -m "$MODEL" "$PROMPT" </dev/null > "$OUT" 2>"$OUT.err" ;;
    *) echo "unknown engine: $ENGINE" >&2; exit 1 ;;
  esac
  lines=$(wc -l < "$OUT" | tr -d ' ')
  echo "saved $OUT (${lines} lines)$([ "$lines" = 0 ] && echo '  ⚠️ 空輸出，看 .err')"
done
