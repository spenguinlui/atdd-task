#!/bin/bash
# 安全閘門：destructive 操作強制確認
# Hook: PreToolUse (Bash | mcp__atdd-admin__atdd_knowledge_delete | mcp__atdd-admin__atdd_term_delete)
# 機制：destructive（清單於 tool-safety.yml）→ exit 2 擋下，要求先經 user 確認
#       （寫 .safety-confirmed flag，5 分鐘 TTL）；read/mutating → 放行
# 注意：hook JSON 寫 temp 檔走 argv 傳入（避免 heredoc 佔走 stdin 的 fail-open 陷阱）
set -u
HUB="${CLAUDE_PROJECT_DIR:?CLAUDE_PROJECT_DIR not set}"
TMP=$(mktemp); trap 'rm -f "$TMP"' EXIT
cat > "$TMP"

python3 - "$TMP" "$HUB/.claude/config/tool-safety.yml" "$HUB/.claude/.safety-confirmed" <<'PY'
import sys, json, os, re, time
inp, reg_path, flag_path = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    d = json.load(open(inp))
except Exception:
    sys.exit(0)
tool = d.get("tool_name", "")
cmd = (d.get("tool_input", {}) or {}).get("command", "") or ""

reg = {}
try:
    import yaml; reg = yaml.safe_load(open(reg_path)) or {}
except Exception:
    pass

reason = None
if tool in set(reg.get("destructive_mcp", [])):
    reason = f"不可逆 MCP 工具：{tool}"
elif tool == "Bash":
    for p in reg.get("bash_destructive_patterns", []):
        if re.search(p, cmd):
            reason = f"不可逆 Bash 樣式：/{p}/"
            break

if not reason:
    sys.exit(0)

def confirmed():
    if not os.path.isfile(flag_path):
        return False
    now = time.time()
    try:
        for line in open(flag_path):
            p = line.strip().split("|")
            if p and p[0].isdigit() and (now - int(p[0])) < 300:
                return True
    except Exception:
        pass
    return False

if confirmed():
    sys.exit(0)

bar = "=" * 55
out = ["", bar, "🚫 Safety Gate — destructive 操作需確認", bar, f"攔下：{reason}"]
if cmd:
    out.append(f"命令：{cmd[:160]}")
out += ["", "此為不可逆操作。請先用 AskUserQuestion 向用戶確認，確認後解鎖：",
        f'  echo "$(date +%s)|{tool}|confirmed" >> "{flag_path}"', bar]
print("\n".join(out), file=sys.stderr)
sys.exit(2)
PY
