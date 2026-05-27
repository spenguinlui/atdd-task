#!/bin/bash
# tester eval：給 base code + 需求 → 各 model 寫驗收測試 → 有效性 = 在 base 應 FAIL、套真實修復後應 PASS
# 設計圖：meta-harness prescriptions/2026-05-23-atdd-eval-harness.md（D.3 tester scorer）
# 機制：worktree@base（容器可見）→ 放 model 產的 spec → rspec(隔離 DB) 取 fail_before → git checkout FIX 套真實 code 修復 → rspec 取 fail_after
# Usage: eval-tester.sh <project> <ticket> [engine...]
#   預設：claude:opus claude:sonnet claude:haiku codex:gpt-5.5
set -u
PROJECT="${1:?project}"; TICKET="${2:?ticket}"; shift 2
ENGINES=("$@"); [ "${#ENGINES[@]}" -eq 0 ] && ENGINES=("claude:opus" "claude:sonnet" "claude:haiku" "codex:gpt-5.5")
N="${EVAL_N:-1}"
HUB="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
yml(){ python3 -c "import yaml;print((yaml.safe_load(open('$HUB/.claude/config/projects.yml'))or{}).get('projects',{}).get('$PROJECT',{})$1)" 2>/dev/null; }
REPO=$(yml ".get('path','')"); CONT=$(yml ".get('test',{}).get('container','')")
[ -d "$REPO/.git" ] && [ -n "$CONT" ] || { echo "repo/container 解析失敗（$PROJECT）" >&2; exit 1; }
FIX=$(git -C "$REPO" log --all --grep "$TICKET" --format='%h' -1); [ -n "$FIX" ] || { echo "找不到 $TICKET commit" >&2; exit 1; }
BASE=$(git -C "$REPO" rev-parse "${FIX}^")
SPECS=""; CODE=""
while IFS= read -r f; do case "$f" in *_spec.rb) SPECS="$SPECS $f";; *.rb) CODE="$CODE $f";; esac; done < <(git -C "$REPO" show --name-only --format= "$FIX" | grep '\.rb$')
[ -n "$SPECS" ] || { echo "此票無 *_spec.rb" >&2; exit 1; }
TARGET_SPEC=$(echo $SPECS | tr ' ' '\n' | head -1)   # model 產的 spec 放這個路徑

BRIEF=$(python3 - "$HUB" "$PROJECT" "$TICKET" <<'PY'
import yaml, glob, sys, re
hub, proj, ticket = sys.argv[1:4]
g = glob.glob(f"{hub}/tests/{proj}/suites/{ticket}*/suite.yml")
title=desc=""
if g:
    s=(yaml.safe_load(open(g[0]))or{}).get("suite",{}); title,desc=s.get("title",""),(s.get("description","")or"")
desc=re.split(r"Code\s*層|修復已在|改用|factory\.rb", desc)[0].strip()
print((title+"\n\n"+desc).strip() or ticket)
PY
)
# base 版 code（供 model 知道受測 API；不洩漏修復）
CODE_CTX=""; for c in $CODE; do CODE_CTX="$CODE_CTX

### $c
\`\`\`ruby
$(git -C "$REPO" show "$BASE:$c" 2>/dev/null)
\`\`\`"; done

# ── scaffolding：注入 repo factory 慣例（解決 model 猜錯 factory 名 → 跑不起來）──
DOMAIN_KEY=$(echo "$TARGET_SPEC" | sed -E 's#spec/domains/([^/]+)/.*#\1#')   # 如 project_management
FACTORY_LIST=$(git -C "$REPO" grep -rhoE "factory :[a-z_]+" -- 'spec/factories/*' 2>/dev/null \
  | sed 's/factory ://' | sort -u | grep -iE "${DOMAIN_KEY%%_*}|${DOMAIN_KEY}" | head -30 | sed 's/^/  - :/')
# 同 domain、用 create(:、非本票、最短的一支當「慣例教材」（教 factory 名 / helper / require 寫法）
SAMPLE=$(for f in $(git -C "$REPO" grep -rl "create(:project_${DOMAIN_KEY##*_}\|create(:" -- "spec/domains/$DOMAIN_KEY/" 2>/dev/null | grep '_spec\.rb$' | grep -vi "$TICKET"); do
           lc=$(git -C "$REPO" show "HEAD:$f" 2>/dev/null | wc -l | tr -d ' '); [ "${lc:-0}" -gt 20 ] && echo "$lc $f"; done | sort -n | awk 'NR==1{print $2}')
SAMPLE_CTX=""; [ -n "$SAMPLE" ] && SAMPLE_CTX="

本 repo 同領域的一支既有測試（**只當慣例範例**：學它怎麼 require、用哪些 factory、helper、describe 風格；不要照抄它的測試內容）：
### $SAMPLE
\`\`\`ruby
$(git -C "$REPO" show "HEAD:$SAMPLE" 2>/dev/null | head -120)
\`\`\`"

PROMPT="你是 tester。為以下需求寫一支 RSpec 驗收測試，放在路徑 \`$TARGET_SPEC\`。
測試要能驗證需求是否成立：**需求未實作時應 FAIL、實作後應 PASS**。
只輸出**一個** \`\`\`ruby 區塊，內含該 spec 完整可執行內容，不要其他文字、不要修改 production code。

本 repo 測試慣例（務必遵守，否則無法執行）：
- spec 第一行為 \`require 'rails_helper'\`。
- 測試資料用 FactoryBot，**只能用下列已註冊的 factory 名**（猜測不存在的名字會 \`Factory not registered\` 直接失敗）：
$FACTORY_LIST
- describe 直接針對受測類別/方法，使用標準 RSpec + FactoryBot DSL。
$SAMPLE_CTX

需求：
$BRIEF

受測程式碼（目前 base 版，可能尚未滿足需求）：$CODE_CTX"

OUTDIR="$HUB/experiments/atdd-eval/results/tester"; mkdir -p "$OUTDIR"

extract_ruby(){ python3 -c "
import sys,re
t=open(sys.argv[1],encoding='utf-8',errors='ignore').read()
m=re.search(r'\`\`\`ruby\s*(.*?)\`\`\`', t, re.S) or re.search(r'\`\`\`\s*(.*?)\`\`\`', t, re.S)
sys.stdout.write(m.group(1) if m else t)
" "$1"; }

run_rspec(){  # wt_name db -> echo "examples failures"
  local wt="$1" db="$2"
  local line
  docker exec "$CONT" sh -c "cd /app/$wt && RAILS_ENV=test DATABASE_DBTEST=$db bundle exec rails db:create db:schema:load >/dev/null 2>&1; DATABASE_DBTEST=$db bundle exec rspec $TARGET_SPEC 2>&1" > "/tmp/tester_${wt}.log" 2>&1
  line=$(grep -iE '[0-9]+ examples?,' "/tmp/tester_${wt}.log" | tail -1)
  local ex fa; ex=$(echo "$line"|grep -oE '[0-9]+ example'|grep -oE '[0-9]+'); ex=${ex:-0}
  fa=$(echo "$line"|grep -oE '[0-9]+ (failure|error)'|grep -oE '[0-9]+'|paste -sd+ -|bc 2>/dev/null); fa=${fa:-$ex}
  echo "$ex $fa"
}

run_one(){  # label model n
  local label="$1" model="$2" n="$3"
  local raw="$OUTDIR/tester-${label}-${model}-${n}.out"
  local t0; t0=$(date +%s); local tokens="?"
  if [ "$label" = claude ]; then
    local j; j=$(timeout 900 claude -p "$PROMPT" --model "$model" --output-format json --permission-mode bypassPermissions 2>/dev/null)
    printf '%s' "$j" | python3 -c "import sys,json;print(json.load(sys.stdin).get('result',''))" > "$raw" 2>/dev/null
    tokens=$(printf '%s' "$j" | python3 -c "import sys,json;u=json.load(sys.stdin).get('usage',{});print(u.get('input_tokens',0)+u.get('output_tokens',0))" 2>/dev/null||echo '?')
  else
    local last; last=$(mktemp)
    timeout 900 codex exec -s read-only --skip-git-repo-check -m "$model" --output-last-message "$last" "$PROMPT" </dev/null >"$last.full" 2>&1
    cp "$last" "$raw" 2>/dev/null
    tokens=$(grep -iA1 'tokens used' "$last.full" 2>/dev/null|grep -oE '[0-9][0-9,]*'|tr -d ','|tail -1); tokens=${tokens:-?}
    rm -f "$last" "$last.full"
  fi
  local secs=$(( $(date +%s)-t0 ))
  # 沙箱：worktree@base，放 model spec
  local wt=".evalt-${TICKET}-${label}-${n}"; local db; db="evt$(echo "${TICKET}${label}${n}"|tr -cd 'a-zA-Z0-9')"
  git -C "$REPO" worktree add -f "$REPO/$wt" "$BASE" >/dev/null 2>&1
  mkdir -p "$REPO/$wt/$(dirname "$TARGET_SPEC")"; extract_ruby "$raw" > "$REPO/$wt/$TARGET_SPEC"
  local rb; rb=($(run_rspec "$wt" "$db")); local fail_before=${rb[1]} ex_before=${rb[0]}
  # 套真實 code 修復（保留 model 的 spec）
  for c in $CODE; do mkdir -p "$REPO/$wt/$(dirname "$c")"; git -C "$REPO" show "$FIX:$c" > "$REPO/$wt/$c" 2>/dev/null; done
  local ra; ra=($(run_rspec "$wt" "$db")); local fail_after=${ra[1]} ex_after=${ra[0]}
  docker exec "$CONT" sh -c "cd /app/$wt && RAILS_ENV=test DATABASE_DBTEST=$db bundle exec rails db:drop >/dev/null 2>&1" 2>/dev/null
  git -C "$REPO" worktree remove --force "$REPO/$wt" >/dev/null 2>&1
  local secs2=$(( $(date +%s)-t0 ))
  # 有效性：base 有 example 且 fail>0、fix 後 fail==0
  local valid=0
  [ "${ex_before:-0}" -gt 0 ] && [ "${fail_before:-0}" -gt 0 ] && [ "${ex_after:-0}" -gt 0 ] && [ "${fail_after:-1}" -eq 0 ] && valid=1
  echo "METRICS|agent=tester|engine=$label|model=$model|secs=$secs2|tokens=$tokens|cost=-|correct=valid=$valid (base ${ex_before}ex/${fail_before}fail → fix ${ex_after}ex/${fail_after}fail)"
  echo "  $label($model) valid=$valid | base=${ex_before}ex,${fail_before}fail  fix=${ex_after}ex,${fail_after}fail  ${secs2}s"
}

echo "=== tester eval $PROJECT/$TICKET  fix=$FIX base=$BASE  target=$TARGET_SPEC  N=$N ==="
echo "有效 = base FAIL（抓到 bug）且 套修復後 PASS"
echo "------"
for e in "${ENGINES[@]}"; do
  label="${e%%:*}"; model="${e#*:}"
  for n in $(seq 1 "$N"); do run_one "$label" "$model" "$n"; done
done
