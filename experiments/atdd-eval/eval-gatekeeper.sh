#!/bin/bash
# gatekeeper eval：餵構造的任務狀態 → 各 model 的 Go/No-Go 決策是否符合決策矩陣（ground truth）
# 設計圖：meta-harness prescriptions/2026-05-23-atdd-eval-harness.md（D.3 gatekeeper scorer）
# 純 inline 場景：不需 docker / API / MCP / git。測「規則遵循正確性」。
#
# Usage: eval-gatekeeper.sh [engine...]
#   預設：claude:opus claude:sonnet claude:haiku codex:gpt-5.5
set -u
ENGINES=("$@"); [ "${#ENGINES[@]}" -eq 0 ] && ENGINES=("claude:opus" "claude:sonnet" "claude:haiku" "codex:gpt-5.5")
N="${EVAL_N:-1}"
HUB="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
GK_BODY=$(awk 'BEGIN{fm=0}/^---[[:space:]]*$/{fm++;next}fm>=2{print}' "$HUB/.claude/agents/gatekeeper.md")
OUTDIR="$HUB/experiments/atdd-eval/results/gatekeeper"; mkdir -p "$OUTDIR"

# ground truth：6 情境 × 正解（覆蓋決策矩陣各觸發）
EXPECTED="S1 GO
S2 NO-GO
S3 NO-GO
S4 NO-GO
S5 NO-GO
S6 CONDITIONAL
S7 NO-GO
S8 NO-GO"

SCENARIOS='你是 gatekeeper。以下 8 個任務狀態，各依「決策矩陣」與「Quality Gates」做 Go/No-Go 決策。
**只輸出 8 行**，每行格式：`S<n>: <GO|NO-GO|CONDITIONAL>`（理由可省略）。不要呼叫任何工具、不要其他內容。

【S1】tests: 100% pass(48/48)；riskReview: riskLevel=low, 0 open findings；styleReview: Grade A；metadata.risks: 4 條、覆蓋 technical/domain/data/integration 4 類、每條 5 欄位齊全且 mitigation 可追溯；e2e: required=true, mode=auto, status=passed。
【S2】tests: 2 failures(46/48)；riskReview: low, 0 findings；risks: 4 條合規；e2e: auto, passed。
【S3】tests: 100% pass；riskReview: **1 條 open Critical**(SQL injection)；risks: 4 條合規；e2e: auto, passed。
【S4】tests: 100% pass；riskReview: low 0 findings；risks: 4 條合規；e2e: **required=true, mode=auto, status=not_executed**。
【S5】tests: 100% pass；riskReview: low；risks: **只有 2 條**(technical, data)；e2e: auto, passed。
【S6】tests: 100% pass；riskReview: low 0 findings；risks: 4 條合規；e2e: **required=true, mode=manual**。
【S7】tests: 100% pass；riskReview: **riskLevel=high**(1 條 open High，非 Critical)；risks: 4 條合規；e2e: auto, passed。（提示：看 Quality Gates 的 Review 門檻）
【S8】tests: 100% pass；riskReview: low；risks: **3 條但只覆蓋 2 類**(technical×2, data×1)；e2e: auto, passed。'

PROMPT="$GK_BODY

────────── EVAL：只做決策、只輸出 6 行、不呼叫工具 ──────────
$SCENARIOS"

score_one(){  # out label model tokens secs
  python3 - "$@" <<'PY'
import sys,os,re
out,label,model,tokens,secs=sys.argv[1:6]
txt=open(out,encoding='utf-8',errors='ignore').read() if os.path.exists(out) else ''
exp={'S1':'GO','S2':'NO-GO','S3':'NO-GO','S4':'NO-GO','S5':'NO-GO','S6':'CONDITIONAL','S7':'NO-GO','S8':'NO-GO'}
def norm(s):
    s=s.upper()
    if 'NO-GO' in s or 'NO GO' in s or 'NOGO' in s: return 'NO-GO'
    if 'CONDITIONAL' in s: return 'CONDITIONAL'
    if 'GO' in s: return 'GO'
    return '?'
got={}
for m in re.finditer(r'S([1-8])\s*[:：\-]\s*([^\n]*)', txt):
    n='S'+m.group(1);
    if n not in got: got[n]=norm(m.group(2))
correct=sum(1 for k,v in exp.items() if got.get(k)==v)
detail=' '.join(f"{k}={got.get(k,'?')}{'' if got.get(k)==v else '(want '+v+')'}" for k,v in exp.items())
print(f"METRICS|agent=gatekeeper|engine={label}|model={model}|secs={secs}|tokens={tokens}|cost=-|correct={correct}/8")
print(f"  {label}({model}) {correct}/8 | {detail}")
PY
}

run_one(){  # label model n
  local label="$1" model="$2" n="$3"
  local out="$OUTDIR/gk-${label}-${model}-${n}.out"
  # 可續跑：已有有效輸出（非額度訊息）→ 直接重評分、不重打 model（省 Claude 額度）
  if [ -s "$out" ] && ! grep -qi "session limit\|usage limit" "$out"; then score_one "$out" "$label" "$model" "cached" 0; return; fi
  local t0; t0=$(date +%s); local tokens="?"
  if [ "$label" = claude ]; then
    local j; j=$(timeout 900 claude -p "$PROMPT" --model "$model" --output-format json --permission-mode bypassPermissions 2>/dev/null)
    printf '%s' "$j" | python3 -c "import sys,json;print(json.load(sys.stdin).get('result',''))" > "$out" 2>/dev/null
    tokens=$(printf '%s' "$j" | python3 -c "import sys,json;u=json.load(sys.stdin).get('usage',{});print(u.get('input_tokens',0)+u.get('output_tokens',0))" 2>/dev/null||echo '?')
  else
    local last; last=$(mktemp)
    timeout 900 codex exec -s read-only --skip-git-repo-check -m "$model" --output-last-message "$last" "$PROMPT" </dev/null >"$last.full" 2>&1
    cp "$last" "$out" 2>/dev/null
    tokens=$(grep -iA1 'tokens used' "$last.full" 2>/dev/null|grep -oE '[0-9][0-9,]*'|tr -d ','|tail -1); tokens=${tokens:-?}
    rm -f "$last" "$last.full"
  fi
  local secs=$(( $(date +%s)-t0 ))
  score_one "$out" "$label" "$model" "$tokens" "$secs"
}

echo "=== gatekeeper eval（6 構造場景，ground truth 決策）N=$N ==="
echo "正解：S1 GO / S2-S5,S7,S8 NO-GO / S6 CONDITIONAL"
echo "------"
for e in "${ENGINES[@]}"; do
  label="${e%%:*}"; model="${e#*:}"
  for n in $(seq 1 "$N"); do run_one "$label" "$model" "$n"; done
done
