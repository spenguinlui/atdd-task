#!/bin/bash
# 對單一 run 輸出客觀評分（7 項，對照 gold.md）
# Usage: eval.sh <run.txt>
set -u
F="${1:?run output file}"
[ -s "$F" ] || { echo "EMPTY/MISSING: $F → 0/7"; exit 0; }
pass=0
ok(){ pass=$((pass+1)); echo "  ✓ $1"; }
no(){ echo "  ✗ $1"; }

grep -qE '[0-9]{1,3}[[:space:]]*%' "$F" && ok "1 信心度%" || no "1 信心度%"

rc=$(grep -oE '\bR[0-9]+\b' "$F" | sort -u | wc -l | tr -d ' ')
[ "$rc" -ge 3 ] && ok "2 風險≥3 (R-ids×$rc)" || no "2 風險≥3 (R-ids×$rc)"

cat_n=0; for c in technical domain data integration ux; do grep -qiw "$c" "$F" && cat_n=$((cat_n+1)); done
[ "$cat_n" -ge 3 ] && ok "3 風險類別≥3 ($cat_n)" || no "3 風險類別≥3 ($cat_n)"

grep -qiE 'AC1|AC 1|驗收標準|acceptance criteria' "$F" && ok "4 AC 列表" || no "4 AC 列表"

if { grep -qiE 'given' "$F" && grep -qiE 'when' "$F" && grep -qiE 'then' "$F"; } || { grep -q '假設' "$F" && grep -q '當' "$F" && grep -q '那麼' "$F"; }; then ok "5 Given-When-Then"; else no "5 Given-When-Then"; fi

if grep -q '需求摘要' "$F" && grep -q '業務分析結論' "$F" && grep -q '驗收條件' "$F"; then ok "6 BA 三段"; else no "6 BA 三段"; fi

ba=$(awk '/需求摘要/{f=1} f{print} /驗收條件/{f=0}' "$F")
if echo "$ba" | grep -qE '`|[a-z]+_[a-z]+'; then no "7 BA 無技術洩漏"; else ok "7 BA 無技術洩漏"; fi

echo "  → $(basename "$F"): $pass/7"
