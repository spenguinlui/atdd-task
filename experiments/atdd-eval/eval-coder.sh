#!/bin/bash
# 行為比較器（coder 階段）：同一真實票，各引擎在封閉沙箱改 code → 跑隱藏驗收測試 → gold-relative + token
# Usage: eval-coder.sh <project> <ticket> [engine...]
#   engine: gold | claude:<model> | codex:<model>   （預設 gold claude:claude-sonnet-4-6 codex:gpt-5.5）
# 機制：worktree@base（容器 /app 下可見）→ 引擎改 code → 套隱藏 *_spec.rb → 隔離 test DB 跑 rspec → 清理
# bash 3.2 相容（無 mapfile）
set -u
PROJECT="${1:?project}"; TICKET="${2:?ticket}"; shift 2
ENGINES=("$@"); [ "${#ENGINES[@]}" -eq 0 ] && ENGINES=("gold" "claude:claude-sonnet-4-6" "codex:gpt-5.5")
HUB="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
yml(){ python3 -c "import yaml;print((yaml.safe_load(open('$HUB/.claude/config/projects.yml'))or{}).get('projects',{}).get('$PROJECT',{})$1)" 2>/dev/null; }
REPO=$(yml ".get('path','')"); CONT=$(yml ".get('test',{}).get('container','')")
[ -d "$REPO/.git" ] && [ -n "$CONT" ] || { echo "repo/container 解析失敗（$PROJECT）" >&2; exit 1; }
FIX=$(git -C "$REPO" log --all --grep "$TICKET" --format='%h' -1); [ -n "$FIX" ] || { echo "找不到 $TICKET 的 commit" >&2; exit 1; }
BASE=$(git -C "$REPO" rev-parse "${FIX}^")
SPECS=""; CODE=""
while IFS= read -r f; do case "$f" in *_spec.rb) SPECS="$SPECS $f";; *.rb) CODE="$CODE $f";; esac; done < <(git -C "$REPO" show --name-only --format= "$FIX" | grep '\.rb$')
[ -n "$SPECS" ] || { echo "此票 commit 無 *_spec.rb，無法當行為實例" >&2; exit 1; }
# brief：取需求行為，剝除實作提示（避免洩答）
BRIEF=$(python3 - "$HUB" "$PROJECT" "$TICKET" <<'PY'
import yaml, glob, sys, re
hub, proj, ticket = sys.argv[1:4]
g = glob.glob(f"{hub}/tests/{proj}/suites/{ticket}*/suite.yml")
title = desc = ""
if g:
    s = (yaml.safe_load(open(g[0])) or {}).get("suite", {})
    title, desc = s.get("title", ""), (s.get("description", "") or "")
# 剝除實作洩漏（"Code 層修復已在..." 之後）
desc = re.split(r"Code\s*層|修復已在|改用|factory\.rb", desc)[0].strip()
print((title + "\n\n" + desc).strip() or ticket)
PY
)

echo "=== 實例 $PROJECT/$TICKET  fix=$FIX base=$BASE ==="
echo "隱藏測試:$SPECS"
echo "brief: $(echo "$BRIEF" | head -3 | tr '\n' ' ')…"
echo ""

GOLD_PASS=""
run_one(){
  local label="$1" mode="$2" model="${3:-}" n="${4:-1}"
  local tag; tag=$(echo "${label}${model}${n}" | tr -cd 'a-zA-Z0-9')
  local wt="$REPO/.eval-${TICKET}-${tag}" base_name
  base_name=".eval-${TICKET}-${tag}"
  local db; db="eval$(echo "${TICKET}${tag}" | tr -cd 'a-zA-Z0-9')"
  local marker="$HUB/experiments/atdd-eval/results/coder/${TICKET}-${tag}.metrics"
  mkdir -p "$(dirname "$marker")"
  # 可續跑：已有有效結果（非 0/0、非 docker 死掉）→ 直接重用，不重跑（防 docker 中途死掉要從頭來）
  if [ -s "$marker" ] && ! grep -q "pass=0/0" "$marker"; then cat "$marker"; [ "$label" = gold ] && GOLD_PASS=$(grep -oE 'pass=[0-9]+' "$marker"|grep -oE '[0-9]+'); return; fi
  git -C "$REPO" worktree add -f "$wt" "$BASE" >/dev/null 2>&1
  local tokens="-" cost="-"; local t0; t0=$(date +%s)
  local instr="$BRIEF

只修改程式碼讓需求成立。不要新增或修改任何測試檔（*_spec.rb）。"
  case "$mode" in
    gold) for c in $CODE; do mkdir -p "$wt/$(dirname "$c")"; git -C "$REPO" show "$FIX:$c" > "$wt/$c"; done ;;
    claude)
      local out; out=$(cd "$wt" && timeout 900 claude -p "$instr" --model "$model" --output-format json --permission-mode bypassPermissions 2>/dev/null)
      tokens=$(printf '%s' "$out" | python3 -c "import sys,json;u=json.load(sys.stdin).get('usage',{});print(u.get('input_tokens',0)+u.get('output_tokens',0))" 2>/dev/null || echo "?")
      cost=$(printf '%s' "$out" | python3 -c "import sys,json;print(round(json.load(sys.stdin).get('total_cost_usd',0),4))" 2>/dev/null || echo "?") ;;
    codex)
      local out; out=$(cd "$wt" && timeout 900 codex exec -s workspace-write --skip-git-repo-check -m "$model" "$instr" </dev/null 2>&1)
      # codex 把數字放在「tokens used」的下一行 → 抓該行+下一行的數字
      tokens=$(printf '%s' "$out" | grep -iA1 'tokens used' | grep -oE '[0-9][0-9,]*' | tr -d ',' | tail -1); tokens="${tokens:-?}" ;;
  esac
  local secs=$(( $(date +%s) - t0 ))
  for s in $SPECS; do mkdir -p "$wt/$(dirname "$s")"; git -C "$REPO" show "$FIX:$s" > "$wt/$s"; done
  docker exec "$CONT" sh -c "cd /app/$base_name && RAILS_ENV=test DATABASE_DBTEST=$db bundle exec rails db:create db:schema:load >/dev/null 2>&1; DATABASE_DBTEST=$db bundle exec rspec$SPECS" > "/tmp/eval_${tag}.log" 2>&1
  local line; line=$(grep -iE '[0-9]+ examples?,' "/tmp/eval_${tag}.log" | tail -1)
  local ex fa pass
  ex=$(echo "$line" | grep -oE '[0-9]+ example' | grep -oE '[0-9]+'); ex="${ex:-0}"
  fa=$(echo "$line" | grep -oE '[0-9]+ (failure|error)' | grep -oE '[0-9]+' | paste -sd+ - | bc 2>/dev/null); fa="${fa:-$ex}"
  pass=$(( ex - fa ))
  [ "$label" = "gold" ] && GOLD_PASS="$pass"
  docker exec "$CONT" sh -c "cd /app/$base_name && RAILS_ENV=test DATABASE_DBTEST=$db bundle exec rails db:drop >/dev/null 2>&1" 2>/dev/null
  git -C "$REPO" worktree remove --force "$wt" >/dev/null 2>&1
  local mline="METRICS|agent=coder|engine=$label|model=${model:-gold}|secs=$secs|tokens=$tokens|cost=$cost|correct=pass=$pass/$ex"
  echo "$mline"; [ "$ex" -gt 0 ] && echo "$mline" > "$marker"   # 只在有效（跑得起來）時寫 marker
  printf "%-22s pass=%s/%s  tokens=%s  cost=%s  %ss\n" "$label($model)" "$pass" "$ex" "$tokens" "$cost" "$secs"
}

echo "結果（pass = 通過的隱藏測試數；gold 為基準）"
echo "------------------------------------------------------------"
NRUN="${EVAL_N:-1}"
for e in "${ENGINES[@]}"; do
  label="${e%%:*}"; model="${e#*:}"; [ "$label" = "$model" ] && model=""
  if [ "$label" = gold ]; then run_one "$label" "$label" "$model" 1   # gold 確定性，跑一次即可
  else for n in $(seq 1 "$NRUN"); do run_one "$label" "$label" "$model" "$n"; done; fi
done
echo "------------------------------------------------------------"
echo "gold 基準 pass=$GOLD_PASS → 引擎 pass 越接近 gold 越好（gold-relative）"
