#!/bin/bash
# generate-coverage.sh — 從 test-*.sh 跑結果生成 coverage.json（軸 13 數據面板）
# 用法：bash experiments/meta-harness-eval/generate-coverage.sh
# 行為：
#   1. 對每支 test-*.sh：parse `# pattern: X` 標記、跑該 test、抓 rc + check 數
#   2. 讀既有 coverage.json 的 mechanisms_inventory（builder 手動維護的欄）→ 保留
#   3. 寫回 coverage.json（automated 欄重算、manual 欄 preserve）
# 設計依據：docs/design-axes/13-self-verify-coverage.md
set -u

HUB="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$HUB" || exit 1
# 自動從腳本位置推 EVAL_DIR（portable，meta-harness 與各 target 共用同一份程式）
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
EVAL_DIR=${SCRIPT_DIR#${HUB}/}
COV="${EVAL_DIR}/coverage.json"
TARGET_NAME=$(basename "${HUB}")

# 對每支 test 跑一次、抓 rc 與 check 數
SCORERS_JSON=""; TOTAL_SCORERS=0; TOTAL_CHECKS=0; PASSED_CHECKS=0; ANY_FAIL=0
for f in "$EVAL_DIR"/test-*.sh; do
  [ -f "$f" ] || continue
  name=$(basename "$f")
  pattern=$(grep -m1 "^# pattern:" "$f" | sed -E 's/^# pattern:[[:space:]]*([A-D]).*/\1/')
  pattern="${pattern:-?}"
  # 跑 test，捕捉輸出與 rc
  out=$(bash "$f" 2>&1); rc=$?
  # 抓 check 數：找「全部 N 項」「全 N 項」「N/N」「N 項檢查」這類模式
  checks=$(printf '%s\n' "$out" | grep -oE "([0-9]+)[[:space:]]*(項|處|/)" | grep -oE "^[0-9]+" | sort -rn | head -1)
  checks="${checks:-0}"
  pass_str=$([ "$rc" -eq 0 ] && echo true || echo false)
  [ "$rc" -ne 0 ] && ANY_FAIL=1
  [ -n "$SCORERS_JSON" ] && SCORERS_JSON="$SCORERS_JSON,"
  SCORERS_JSON="$SCORERS_JSON{\"name\":\"$name\",\"pattern\":\"$pattern\",\"checks\":$checks,\"last_pass\":$pass_str}"
  TOTAL_SCORERS=$((TOTAL_SCORERS+1))
  TOTAL_CHECKS=$((TOTAL_CHECKS+checks))
  [ "$rc" -eq 0 ] && PASSED_CHECKS=$((PASSED_CHECKS+checks))
done

NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
LAST_RC=$([ "$ANY_FAIL" -eq 0 ] && echo 0 || echo 1)

# 寫 coverage.json：auto 欄重算、mechanisms_inventory preserve（python merge）
python3 - "$COV" "$TARGET_NAME" "$NOW" "$EVAL_DIR/run-self-verify.sh" \
                 "$TOTAL_SCORERS" "$TOTAL_CHECKS" "$PASSED_CHECKS" "$LAST_RC" "$SCORERS_JSON" <<'PY'
import json, sys, os
cov_path, target, now, runner, ns, nc, np_, rc, scorers_raw = sys.argv[1:10]
# 讀既有（preserve mechanisms_inventory）
existing = {}
if os.path.isfile(cov_path):
    try: existing = json.load(open(cov_path))
    except Exception: existing = {}
inv = existing.get("mechanisms_inventory") or {
    "total": None, "covered": None, "coverage_pct": None,
    "uncovered": [], "_note": "builder 手動維護 total / uncovered；covered / coverage_pct 自動算"
}
scorers = json.loads("[" + scorers_raw + "]")
# 若 builder 已填 total + 有 scorers covers，計算 covered = sum unique covers
# 目前 scorers 還沒記 covers list（builder 後續可在 coverage.json 加），先讓 covered 由 total 推算或 manual
if isinstance(inv.get("total"), int) and inv["total"] > 0:
    # 簡單策略：covered = scorer 數（每 scorer 視為覆蓋 1 個 mechanism；builder 可手動精修）
    if not isinstance(inv.get("covered"), int):
        inv["covered"] = int(ns)
    inv["coverage_pct"] = round(inv["covered"] / inv["total"] * 100)
out = {
    "target": target,
    "generated_at": now,
    "runner": runner,
    "scorers": scorers,
    "totals": {"scorers": int(ns), "checks_total": int(nc), "checks_passed": int(np_)},
    "mechanisms_inventory": inv,
    "last_run": {"timestamp": now, "rc": int(rc)},
}
json.dump(out, open(cov_path, "w"), ensure_ascii=False, indent=2)
print(f"wrote {cov_path}")
PY

echo
echo "── coverage 摘要 ──"
python3 -c "
import json
c = json.load(open('$COV'))
t = c['totals']; inv = c['mechanisms_inventory']; lr = c['last_run']
print(f\"  scorers       : {t['scorers']}\")
print(f\"  checks_total  : {t['checks_total']}（passed: {t['checks_passed']}）\")
print(f\"  last_run      : rc={lr['rc']} @ {lr['timestamp']}\")
if inv.get('total'):
    print(f\"  coverage_pct  : {inv.get('coverage_pct', '?')}%（covered {inv.get('covered','?')} / total {inv['total']}）\")
else:
    print(f\"  mechanisms_inventory: builder 尚未填 total（手動維護該欄後 coverage_pct 才會出數字）\")
"
