#!/bin/bash
# specist eval：平面提示寫 spec → 7 項結構 rubric（複用 atdd-harness-quality 的 spec-task + eval.sh）
# 設計圖：meta-harness prescriptions/2026-05-23-atdd-eval-harness.md（specist 結構 rubric，無需 API）
# Usage: eval-specist.sh [engine...]   預設 claude:opus claude:sonnet claude:haiku codex:gpt-5.5
set -u
ENGINES=("$@"); [ "${#ENGINES[@]}" -eq 0 ] && ENGINES=("claude:opus" "claude:sonnet" "claude:haiku" "codex:gpt-5.5")
N="${EVAL_N:-1}"
HUB="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
HQ="$HUB/experiments/atdd-harness-quality"
PROMPT="$(cat "$HQ/prompts/spec-task.md")"
OUTDIR="$HUB/experiments/atdd-eval/results/specist"; mkdir -p "$OUTDIR"

run_one(){  # label model n
  local label="$1" model="$2" n="$3"
  local out="$OUTDIR/specist-${label}-${model}-${n}.out"
  if [ -s "$out" ] && ! grep -qi "session limit\|usage limit" "$out"; then
    local sc; sc=$(bash "$HQ/eval.sh" "$out" 2>/dev/null|grep -oE '[0-7]/7'|tail -1); sc=${sc:-0/7}
    echo "METRICS|agent=specist|engine=$label|model=$model|secs=0|tokens=cached|cost=-|correct=rubric=$sc"; echo "  $label($model) rubric=$sc (cached)"; return
  fi
  local t0; t0=$(date +%s); local tokens="?" cost="-"
  if [ "$label" = claude ]; then
    local j; j=$(timeout 900 claude -p "$PROMPT" --model "$model" --output-format json --permission-mode bypassPermissions 2>/dev/null)
    printf '%s' "$j" | python3 -c "import sys,json;print(json.load(sys.stdin).get('result',''))" > "$out" 2>/dev/null
    tokens=$(printf '%s' "$j"|python3 -c "import sys,json;u=json.load(sys.stdin).get('usage',{});print(u.get('input_tokens',0)+u.get('output_tokens',0))" 2>/dev/null||echo '?')
    cost=$(printf '%s' "$j"|python3 -c "import sys,json;print(round(json.load(sys.stdin).get('total_cost_usd',0),4))" 2>/dev/null||echo '-')
  else
    local last; last=$(mktemp)
    timeout 900 codex exec -s read-only --skip-git-repo-check -m "$model" --output-last-message "$last" "$PROMPT" </dev/null >"$last.full" 2>&1
    cp "$last" "$out" 2>/dev/null
    tokens=$(grep -iA1 'tokens used' "$last.full" 2>/dev/null|grep -oE '[0-9][0-9,]*'|tr -d ','|tail -1); tokens=${tokens:-?}
    rm -f "$last" "$last.full"
  fi
  local secs=$(( $(date +%s)-t0 ))
  local score; score=$(bash "$HQ/eval.sh" "$out" 2>/dev/null | grep -oE '[0-7]/7' | tail -1); score=${score:-0/7}
  echo "METRICS|agent=specist|engine=$label|model=$model|secs=$secs|tokens=$tokens|cost=$cost|correct=rubric=$score"
  echo "  $label($model) rubric=$score  ${secs}s  tok=$tokens"
}

echo "=== specist eval（spec-task 平面提示，7 項結構 rubric）N=$N ==="
echo "------"
for e in "${ENGINES[@]}"; do
  label="${e%%:*}"; model="${e#*:}"
  for n in $(seq 1 "$N"); do run_one "$label" "$model" "$n"; done
done
