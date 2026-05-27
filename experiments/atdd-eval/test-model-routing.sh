#!/bin/bash
# pattern: A
# test-model-routing.sh — 一鍵驗 model 推薦在多處保持一致（無需 live task）
# 比對：
#   (A) 本檔內推薦表（單一真實來源）
#   (B) .claude/config/agent-engines.yml          → engine / model
#   (C) .claude/agents/<name>.md frontmatter      → model:
#   (D) .claude/commands/continue.md Step 2.9     → Recommended 欄
#   (E) dispatch 接口（continue.md + dispatch.md + run-agent-codex.sh）
# 用法：bash experiments/atdd-eval/test-model-routing.sh    退出碼 0=全過，1=有 drift
set -u

HUB="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$HUB" || { echo "cd HUB 失敗：$HUB"; exit 1; }

CHECKS=0; FAILS=0
pass(){ CHECKS=$((CHECKS+1)); echo "  ✓ $1"; }
fail(){ CHECKS=$((CHECKS+1)); FAILS=$((FAILS+1)); echo "  ✗ $1"; }
section(){ echo; echo "▶ $1"; }

# ─── (A) 推薦表：唯一真實來源 ─────────────────────────────────────────
# 修改推薦時改這裡一處；script 確保其他四處跟得上。
recommended(){  # agent → "engine model"   model="-" 表示無強制推薦
  case "$1" in
    specist|tester)                          echo "claude opus";;
    risk-reviewer|style-reviewer|gatekeeper) echo "claude sonnet";;
    coder)                                   echo "codex gpt-5.5";;
    curator)                                 echo "claude -";;
    *)                                       echo "";;
  esac
}
AGENTS="specist tester risk-reviewer style-reviewer gatekeeper coder curator"

# ─── (B) agent-engines.yml ───────────────────────────────────────────
section "(B) agent-engines.yml engine/model"
for a in $AGENTS; do
  rec=$(recommended "$a"); rec_eng=${rec% *}; rec_mod=${rec#* }
  yml=$(python3 -c "
import yaml
c=yaml.safe_load(open('.claude/config/agent-engines.yml'))
ag=(c.get('agents') or {}).get('$a') or {}
eng=ag.get('engine') or (c.get('defaults') or {}).get('engine','claude')
mod=ag.get('model') or '-'
print(eng, mod)
" 2>/dev/null)
  yml_eng=${yml% *}; yml_mod=${yml#* }
  if [ "$rec_eng" != "$yml_eng" ]; then
    fail "$a → yml engine='$yml_eng'，推薦 '$rec_eng'"
  elif [ "$rec_eng" = codex ]; then
    if [ "$rec_mod" = "$yml_mod" ]; then pass "$a → engine=codex model=$yml_mod"
    else fail "$a → yml model='$yml_mod'，推薦 '$rec_mod'"; fi
  else
    pass "$a → engine=${yml_eng}（model 由 frontmatter 把關，見 C 節）"
  fi
done

# ─── (C) agents/*.md frontmatter model: ───────────────────────────────
section "(C) agents/*.md frontmatter model:"
for a in $AGENTS; do
  rec=$(recommended "$a"); rec_eng=${rec% *}; rec_mod=${rec#* }
  if [ "$rec_eng" != claude ] || [ "$rec_mod" = "-" ]; then
    pass "$a → 略（engine=$rec_eng / 無推薦 model）"; continue
  fi
  fm=$(awk '/^---$/{c++; next} c==1 && /^model:/{print $2; exit}' ".claude/agents/$a.md" 2>/dev/null)
  if [ "$fm" = "$rec_mod" ]; then pass "$a → frontmatter model: $fm"
  else fail "$a → frontmatter model: '${fm:-(無)}'，推薦 '$rec_mod'"; fi
done

# ─── (D) continue.md Step 2.9 Recommended 欄 ─────────────────────────
section "(D) continue.md Step 2.9 Recommended 欄"
label_to_em(){  # 把 Step 2.9 表的標籤轉成 "engine model"
  case "$1" in
    "Opus 4.7")            echo "claude opus";;
    "Sonnet 4.6")          echo "claude sonnet";;
    "Haiku 4.5")           echo "claude haiku";;
    "GPT-5.5")             echo "codex gpt-5.5";;
    *"沿用 yml default"*)  echo "yml -";;
    *)                     echo "?? ??";;
  esac
}
for a in $AGENTS; do
  rec=$(recommended "$a")
  row=$(grep -E "^\| *${a} *\|" .claude/commands/continue.md | head -1)
  if [ -z "$row" ]; then fail "$a → 在 Step 2.9 表找不到"; continue; fi
  rec_label=$(echo "$row" | awk -F'|' '{gsub(/^ +| +$/,"",$3); print $3}')
  parsed=$(label_to_em "$rec_label")
  if [ "$rec" = "claude -" ] && [ "$parsed" = "yml -" ]; then
    pass "$a → Recommended「${rec_label}」（沿用 yml）"
  elif [ "$rec" = "$parsed" ]; then
    pass "$a → Recommended「${rec_label}」"
  else
    fail "$a → Recommended「${rec_label}」對應 ${parsed}，推薦 $rec"
  fi
done

# ─── (E) 接口檢查 ────────────────────────────────────────────────────
section "(E) dispatch 接口"
grep -q "^## Step 2.9" .claude/commands/continue.md \
  && pass "continue.md 有 Step 2.9 段" \
  || fail "continue.md 缺 Step 2.9 段"
grep -q "chosen_engine\|chosen_model" .claude/commands/continue.md \
  && pass "continue.md 用 chosen_engine/chosen_model 變數" \
  || fail "continue.md 缺 chosen_engine/chosen_model"
grep -q "ATDD_NO_PROMPT" .claude/commands/continue.md \
  && pass "continue.md 有 ATDD_NO_PROMPT 跳過（headless）" \
  || fail "continue.md 缺 ATDD_NO_PROMPT 跳過"
grep -q -- "--model " .claude/commands/continue.md \
  && pass "continue.md 有 --model inline 旗標跳過" \
  || fail "continue.md 缺 --model 旗標"
grep -qE 'MODEL=.*\$\{6' .claude/scripts/run-agent-codex.sh \
  && pass "run-agent-codex.sh 收 \$6 為 MODEL" \
  || fail "run-agent-codex.sh 沒收 \$6"
grep -q "oneshot\|chosen_engine\|chosen_model" .claude/commands/shared/agent-dispatch.md \
  && pass "agent-dispatch.md 有 oneshot 覆寫優先順序" \
  || fail "agent-dispatch.md 缺 oneshot 覆寫描述"

echo
if [ "$FAILS" -eq 0 ]; then
  echo "✅ 全 $CHECKS 項通過"; exit 0
else
  echo "❌ $FAILS / $CHECKS 項失敗（任一處 drift → 修到一致再來一次）"; exit 1
fi
