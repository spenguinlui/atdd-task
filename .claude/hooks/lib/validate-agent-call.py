#!/usr/bin/env python3
"""validate-agent-call 重邏輯（被 validate-agent-call.sh 呼叫）。
argv: <hook_input_json_file> <hub_dir>
PreToolUse(Task)：驗證該 agent 能否在當前 task 階段呼叫 + specist 信心度 ≥95% 硬阻擋。
復活兩處 bug：(1) 原讀 $TOOL_INPUT env（不存在）→ 改 stdin；(2) 原信心度回傳被忽略→現真的擋。
exit 0 = 允許；exit 1 = 阻擋。
"""
import sys, json, os, re, glob

inp, hub = sys.argv[1], sys.argv[2]
try:
    d = json.load(open(inp))
except Exception:
    sys.exit(0)
ti = d.get("tool_input", {}) or {}
agent = ti.get("subagent_type", "") or ""
prompt = ti.get("prompt", "") or ""
if not agent:
    sys.exit(0)

ATDD = {"specist", "tester", "coder", "style-reviewer", "risk-reviewer", "gatekeeper"}
if agent not in ATDD:
    sys.exit(0)

tasks = glob.glob(os.path.join(hub, "tasks", "*", "active", "*.json"))
if not tasks:
    print("⚠️ 沒有找到活躍的任務，無法驗證工作流程")
    print("請先使用 /feature 或 /fix 啟動任務")
    sys.exit(1)

# 多任務：UUID > 專案名 > 最近修改
task_path = tasks[0] if len(tasks) == 1 else None
if task_path is None:
    m = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", prompt)
    if m:
        task_path = next((t for t in tasks if m.group(0) in t), None)
if task_path is None:
    try:
        import yaml
        projects = (yaml.safe_load(open(os.path.join(hub, ".claude/config/projects.yml"))) or {}).get("projects", {})
    except Exception:
        projects = {}
    for proj in projects:
        if proj.lower() in prompt.lower():
            cand = [t for t in tasks if f"/{proj}/" in t]
            if cand:
                task_path = max(cand, key=os.path.getmtime)
                break
if task_path is None:
    task_path = max(tasks, key=os.path.getmtime)

if not os.path.isfile(task_path):
    print("⚠️ 無法讀取任務檔案")
    sys.exit(1)
task = json.load(open(task_path))
status = task.get("status", "")
try:
    conf = int(task.get("workflow", {}).get("confidence", 0))
except (TypeError, ValueError):
    conf = 0
profile = task.get("acceptance", {}).get("profile", "")
desc = task.get("description", "")[:50]
proj = task.get("projectId", "")

PHASE = {
    "specist": ({"requirement", "specification"}, "requirement/specification"),
    "tester": ({"testing", "development"}, "testing/development"),
    "coder": ({"development"}, "development"),
    "style-reviewer": ({"review"}, "review"),
    "risk-reviewer": ({"review"}, "review"),
    "gatekeeper": ({"gate", "review"}, "review/gate"),
}
errs = []
allowed, label = PHASE[agent]
ok = status in allowed
if not ok:
    errs.append(f"❌ {agent} 只能在 {label} 階段呼叫（當前狀態：{status}）")

# specist 進 spec 前信心度硬阻擋（修復：原回傳被忽略，現真的擋）
if ok and agent == "specist" and status == "requirement" and conf < 95:
    errs.append(f"❌ 信心度不足，阻擋進入 specification（當前 {conf}%，需 ≥95%）")
    errs.append("   參考：.claude/config/confidence/requirement.yml")
    ok = False

# tester profile 提醒（不阻擋）
if ok and agent == "tester" and status == "testing" and not profile:
    print("⚠️ ATDD Profile 未設定（acceptance.profile）— 提醒，不阻擋")

print("🔍 ATDD 工作流程驗證")
print(f"   任務：[{proj}] {desc}")
print(f"   狀態：{status}  Agent：{agent}")
if ok:
    print(f"✅ 驗證通過，允許呼叫 {agent}")
    sys.exit(0)
for e in errs:
    print(e)
sys.exit(1)
