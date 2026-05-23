#!/bin/bash
# 列出可當 eval 實例的 GRE 票：有驗收套件（tests/<proj>/suites/）+ target repo 有修復 commit
# 附改動規模（files / ±lines），按規模排序 → 供挑「大型改動」當測試題（小改動分不出 model 強弱）
# Usage: list-candidates.sh <project>     e.g. e_trading
set -u
PROJECT="${1:?project, e.g. e_trading}"
HUB="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
REPO=$(python3 -c "import yaml; print((yaml.safe_load(open('$HUB/.claude/config/projects.yml')) or {}).get('projects',{}).get('$PROJECT',{}).get('path',''))" 2>/dev/null)
[ -n "$REPO" ] && [ -d "$REPO/.git" ] || { echo "找不到 $PROJECT 的 git repo（projects.yml path=$REPO）" >&2; exit 1; }
SUITES="$HUB/tests/$PROJECT/suites"
[ -d "$SUITES" ] || { echo "無 $SUITES" >&2; exit 1; }

rows=""
for d in "$SUITES"/*/; do
  [ -d "$d" ] || continue
  base=$(basename "$d")
  gre=$(echo "$base" | grep -oE '[A-Z]+-[0-9]+'); [ -n "$gre" ] || continue   # 通用票號前綴（GRE/CST/PVO…）
  commit=$(git -C "$REPO" log --all --grep "$gre" --format='%h' -1 2>/dev/null)
  if [ -z "$commit" ]; then
    rows+="$(printf '%08d\t%s\t%s\t%s\t%s\t%s' 0 "$gre" "-" "-" "-" "$base")"$'\n'; continue
  fi
  stat=$(git -C "$REPO" show --stat --format='' "$commit" 2>/dev/null | tail -1)
  files=$(echo "$stat" | grep -oE '[0-9]+ file' | grep -oE '[0-9]+'); files=${files:-0}
  ins=$(echo "$stat" | grep -oE '[0-9]+ insertion' | grep -oE '[0-9]+'); ins=${ins:-0}
  dele=$(echo "$stat" | grep -oE '[0-9]+ deletion' | grep -oE '[0-9]+'); dele=${dele:-0}
  lines=$(( ins + dele ))
  rows+="$(printf '%08d\t%s\t%s\t%s\t%s\t%s' "$lines" "$gre" "$commit" "$files" "$lines" "$base")"$'\n'
done

printf "%-12s %-9s %5s %7s  %s\n" "TICKET" "COMMIT" "FILES" "±LINES" "SUITE"
printf '%s' "$rows" | sort -rn | while IFS=$'\t' read -r _ gre commit files lines base; do
  [ -n "$gre" ] || continue
  printf "%-12s %-9s %5s %7s  %s\n" "$gre" "$commit" "$files" "$lines" "$base"
done
