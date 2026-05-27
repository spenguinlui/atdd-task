#!/bin/bash
# Stage 2 reviewer eval：給 base（含問題）code → 跑 risk-reviewer 提示 → findings 命中 fix 改動區域為 ground truth
# 設計圖：meta-harness prescriptions/2026-05-23-atdd-eval-harness.md（Part D.3 reviewer scorer）
# 純 git ground truth：不需 docker / 不需 API / 不需 MCP（codex 走 -s read-only，無需 bypass）
#
# Usage: eval-reviewer.sh <project> <ticket> [engine...]
#   engine: claude:<model> | codex:<model>
#   預設：claude:opus claude:sonnet claude:haiku codex:gpt-5.5
set -u

PROJECT="${1:?project}"; TICKET="${2:?ticket}"; shift 2
ENGINES=("$@"); [ "${#ENGINES[@]}" -eq 0 ] && ENGINES=("claude:opus" "claude:sonnet" "claude:haiku" "codex:gpt-5.5")
N="${EVAL_N:-1}"   # 每引擎跑幾次（預設 1；export EVAL_N=3 跑三次）

HUB="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
REPO=$(python3 -c "import yaml;print((yaml.safe_load(open('$HUB/.claude/config/projects.yml'))or{}).get('projects',{}).get('$PROJECT',{}).get('path',''))" 2>/dev/null)
[ -d "$REPO/.git" ] || { echo "repo 解析失敗：$PROJECT（path=$REPO）" >&2; exit 1; }
FIX=$(git -C "$REPO" log --all --grep "$TICKET" --format='%h' -1); [ -n "$FIX" ] || { echo "找不到 $TICKET 的 commit" >&2; exit 1; }
BASE=$(git -C "$REPO" rev-parse "$FIX^")

# ── ground truth：非 spec 改動檔 + base 側改動行範圍 ──
FILES=$(git -C "$REPO" show --name-only --format= "$FIX" | grep -vE '_spec\.rb$|^spec/' | grep -E '\.(rb|slim|erb|haml|js|rake)$' || true)
[ -n "$FILES" ] || { echo "此票無可審 code 檔" >&2; exit 1; }

WORK=$(mktemp -d -t evalrev-XXXXXX)
REVIEW_DIR="$WORK/code"; mkdir -p "$REVIEW_DIR"
GT="$WORK/ground_truth.txt"; : > "$GT"
FILE_LIST=""
for f in $FILES; do
  mkdir -p "$REVIEW_DIR/$(dirname "$f")"
  git -C "$REPO" show "$BASE:$f" > "$REVIEW_DIR/$f" 2>/dev/null || continue
  FILE_LIST="$FILE_LIST
- $f"
  git -C "$REPO" diff "$BASE" "$FIX" -- "$f" | grep -E '^@@' \
    | sed -E 's/^@@ -([0-9]+),?([0-9]*) .*/\1 \2/' | while read -r a b; do
      b=${b:-1}; echo "$f $a $((a+b))" >> "$GT"
    done
done

BRIEF=$(python3 -c "
import yaml,glob
g=glob.glob('$HUB/tests/$PROJECT/suites/$TICKET*/suite.yml')
s=(yaml.safe_load(open(g[0]))or{}).get('suite',{}) if g else {}
print((str(s.get('title',''))+chr(10)+str(s.get('description',''))).strip())
" 2>/dev/null)

AGENT="${EVAL_AGENT:-risk-reviewer}"; export AGENT   # 可設 style-reviewer
REVIEWER_BODY=$(awk 'BEGIN{fm=0}/^---[[:space:]]*$/{fm++;next}fm>=2{print}' "$HUB/.claude/agents/${AGENT}.md")

PROMPT="$REVIEWER_BODY

────────── 本次審查任務（EVAL 模式）──────────
重要：這是離線評測。**只審不寫**：不要呼叫任何 MCP 工具、不要修改任何檔案、不要嘗試持久化（忽略原文涉及 MCP 持久化的步驟）。直接在對話輸出審查結果。

你在審查 ${PROJECT}（Rails DDD）的既有 code。待審檔案（相對路徑，根目錄即當前資料夾）：${FILE_LIST}

需求背景（供判斷正確性，勿據此只做 spec 比對——仍以 ${AGENT} 的職責視角審查）：
$BRIEF

輸出規範：每條 finding/issue 務必標 \`相對檔案路徑:行號\`、severity/grade、問題描述、建議。"

score_one(){  # out gt label model tokens secs
  python3 - "$@" <<'PY'
import sys,os,re
out,gt,label,model,tokens,secs=sys.argv[1:7]
txt=open(out,encoding='utf-8',errors='ignore').read() if os.path.exists(out) else ''
ranges=[]
for ln in open(gt):
    p=ln.split()
    if len(p)==3: ranges.append((p[0],int(p[1]),int(p[2])))
gt_files=set(r[0] for r in ranges)
def match(rf,f): return rf.endswith(f) or f.endswith(rf.split('/')[-1])
refs=re.findall(r'([\w./-]+\.(?:rb|slim|erb|haml|js|rake)):(\d+)', txt)
hit_file=any(any(match(rf,f) for f in gt_files) for rf,_ in refs)
hit_region=False
for rf,ln in refs:
    ln=int(ln)
    for f,a,b in ranges:
        if match(rf,f) and a-15<=ln<=b+15: hit_region=True
sev=len(re.findall(r'(?i)\b(critical|high|medium)\b',txt))
agent=os.environ.get('AGENT','risk-reviewer')
print(f"METRICS|agent={agent}|engine={label}|model={model}|secs={secs}|tokens={tokens}|cost=-|correct=hit_region={'Y' if hit_region else 'N'},hit_file={'Y' if hit_file else 'N'},sev_marks={sev}")
print(f"  {label}({model})|tok={tokens}|{secs}s|hit_file={'Y' if hit_file else 'N'}|hit_region={'Y' if hit_region else 'N'}|sev_marks={sev}|chars={len(txt)}")
PY
}

run_one(){  # label model engine n
  local label="$1" model="$2" engine="$3" n="$4"
  local out="$HUB/experiments/atdd-eval/results/reviewer/${TICKET}-${AGENT}-${label}-${model}-${n}.out"
  mkdir -p "$(dirname "$out")"
  # 可續跑：已有有效輸出（非額度訊息）→ 直接重評分、不重打 model
  if [ -s "$out" ] && ! grep -qi "session limit\|usage limit" "$out"; then score_one "$out" "$GT" "$label" "$model" cached 0; return; fi
  local t0; t0=$(date +%s); local tokens="?"
  if [ "$engine" = claude ]; then
    local j; j=$(cd "$REVIEW_DIR" && timeout 900 claude -p "$PROMPT" --model "$model" --output-format json --permission-mode bypassPermissions 2>/dev/null)
    printf '%s' "$j" | python3 -c "import sys,json;print(json.load(sys.stdin).get('result',''))" > "$out" 2>/dev/null
    tokens=$(printf '%s' "$j" | python3 -c "import sys,json;u=json.load(sys.stdin).get('usage',{});print(u.get('input_tokens',0)+u.get('output_tokens',0))" 2>/dev/null || echo '?')
  else
    local last="$WORK/last.$label.$n"
    (cd "$REVIEW_DIR" && timeout 900 codex exec -s read-only --skip-git-repo-check -m "$model" --output-last-message "$last" "$PROMPT" </dev/null) >"$WORK/full.$label.$n" 2>&1
    cp "$last" "$out" 2>/dev/null
    tokens=$(grep -iA1 'tokens used' "$WORK/full.$label.$n" 2>/dev/null | grep -oE '[0-9][0-9,]*' | tr -d ',' | tail -1); tokens=${tokens:-?}
  fi
  local secs=$(( $(date +%s)-t0 ))
  score_one "$out" "$GT" "$label" "$model" "$tokens" "$secs"
}

echo "=== reviewer eval $PROJECT/$TICKET  fix=$FIX base=$BASE  N=$N ==="
echo "ground truth（檔 起 迄）："; cat "$GT"
echo "review dir：$REVIEW_DIR"
echo "------ 結果 ------"
for e in "${ENGINES[@]}"; do
  label="${e%%:*}"; model="${e#*:}"
  for n in $(seq 1 "$N"); do run_one "$label" "$model" "$label" "$n"; done
done
echo "------"
echo "raw outputs：experiments/atdd-eval/results/reviewer/${TICKET}-*.out"
echo "WORK=${WORK}（review dir + codex full log 留供人工複看，完後可 rm -rf）"
