#!/usr/bin/env python3
"""validate-deliverables 重邏輯（被 validate-deliverables.sh 呼叫）。
argv: <hook_input_json_file> <hub_dir>
PreToolUse(Task)：呼叫 ATDD agent 前，驗證「前一階段交付物」是否完整。
修復：原讀 $TOOL_INPUT env（不存在）→ 改 stdin → gate 過去 no-op，今復活。
exit 0 = 通過/僅警告；exit 2 = 阻擋。
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
if not agent or agent not in {"specist", "tester", "coder", "style-reviewer", "risk-reviewer", "gatekeeper"}:
    sys.exit(0)

# projects config（多任務比對 + testing 階段檔案路徑共用）
try:
    import yaml
    projects = (yaml.safe_load(open(os.path.join(hub, ".claude/config/projects.yml"))) or {}).get("projects", {})
except Exception:
    projects = {}

tasks = glob.glob(os.path.join(hub, "tasks", "*", "active", "*.json"))
if not tasks:
    sys.exit(0)
task_path = tasks[0] if len(tasks) == 1 else None
if task_path is None:
    m = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", prompt)
    if m:
        task_path = next((t for t in tasks if m.group(0) in t), None)
if task_path is None:
    for proj in projects:
        if proj.lower() in prompt.lower():
            cand = [t for t in tasks if f"/{proj}/" in t]
            if cand:
                task_path = max(cand, key=os.path.getmtime)
                break
if task_path is None:
    task_path = max(tasks, key=os.path.getmtime)
if not os.path.isfile(task_path):
    sys.exit(0)

task = json.load(open(task_path))
status = task.get("status", "")
task_type = task.get("type", "")
errors, warnings = [], []

def get_path(key):
    return task.get(key, "") or task.get("context", {}).get(key, "") or ""

def file_exists(rel):
    return bool(rel) and os.path.isfile(os.path.join(hub, rel))

def read_file(rel):
    full = os.path.join(hub, rel)
    return open(full).read() if os.path.isfile(full) else ""

check = None
if agent == "specist" and status == "specification":
    check = "requirement"
elif agent == "tester" and status == "testing":
    check = "specification"
elif agent == "coder" and status == "development":
    check = "testing"
elif agent in ("risk-reviewer", "style-reviewer") and status == "review":
    check = "development"
    rc = task.get("context", {}).get("reviewFindings", {}).get("reviewCycle", 0)
    if isinstance(rc, int) and rc >= 2:
        errors.append(f"Review-fix 迴圈已達上限（reviewCycle={rc}，上限 2）— 須人工介入")
elif agent == "gatekeeper" and status in ("gate", "review"):
    check = "review"
if not check:
    sys.exit(0)

if check == "requirement":
    req = get_path("requirementPath")
    if not req:
        errors.append("requirementPath 未設定")
    elif not file_exists(req):
        errors.append(f"需求文件不存在: {req}")
    elif len(read_file(req).strip()) < 100:
        errors.append(f"需求文件內容過短 ({len(read_file(req).strip())} chars)")
    if task_type == "feature":
        ba = get_path("baReportPath")
        if not ba:
            errors.append("baReportPath 未設定（feature 必須有 BA 報告）")
        elif not file_exists(ba):
            errors.append(f"BA 報告不存在: {ba}")
elif check == "specification":
    spec = get_path("specPath")
    if not spec:
        errors.append("specPath 未設定")
    elif not file_exists(spec):
        errors.append(f"規格文件不存在: {spec}")
    else:
        c = read_file(spec)
        ac = re.findall(r"- \[[ x]\]\s*AC\d+", c)
        sc = re.findall(r"###\s*Scenario\s+\d+", c)
        if not ac:
            errors.append("規格文件沒有 Acceptance Criteria（- [ ] AC1: ...）")
        if not sc:
            errors.append("規格文件沒有 Scenario（### Scenario 1: ...）")
        if ac and sc and len(sc) < len(ac):
            warnings.append(f"Scenario 數 ({len(sc)}) 少於 AC 數 ({len(ac)})")
    if not task.get("acceptance", {}).get("profile", ""):
        errors.append("ATDD Profile 未設定（acceptance.profile）")
elif check == "testing":
    tl = task.get("acceptance", {}).get("testLayers", {})
    if not tl:
        errors.append("testLayers 為空 — tester 沒有記錄任何測試層")
    else:
        ppath = projects.get(task.get("projectId", ""), {}).get("path", "")
        has_any = False
        for layer, info in tl.items():
            if not isinstance(info, dict):
                continue
            for fp in info.get("files", []):
                has_any = True
                if ppath and not os.path.isfile(os.path.join(ppath, fp)):
                    errors.append(f"測試檔案不存在 [{layer}]: {fp}")
        if not has_any and not any(isinstance(i, dict) and i.get("fixture") for i in tl.values()):
            warnings.append("testLayers 有定義但沒列測試檔案路徑或 fixture")
elif check == "development":
    modified = task.get("context", {}).get("modifiedFiles", [])
    if not modified:
        errors.append("modifiedFiles 為空 — coder 沒有記錄任何修改檔案")
    req = get_path("requirementPath")
    if req and file_exists(req) and modified:
        cs = re.findall(r"####\s+\d+\.", read_file(req))
        if cs and len(modified) < len(cs):
            warnings.append(f"修改檔案數 ({len(modified)}) 少於需求變更區域 ({len(cs)})")
    if not task.get("acceptance", {}).get("results", {}):
        warnings.append("acceptance.results 為空 — 測試是否已執行並通過？")
elif check == "review":
    if task.get("context", {}).get("reviewFindings", None) is None:
        errors.append("reviewFindings 未填寫 — reviewer 沒有記錄審查結果")
    if not task.get("acceptance", {}).get("results", {}):
        errors.append("acceptance.results 為空 — 沒有測試結果記錄")

if not errors and not warnings:
    print(f"✅ 交付物驗證通過：{check} → {status}")
    sys.exit(0)
print(f"🚫 Deliverable Gate — 交付物驗證（{check} → {status}，agent={agent}）", file=sys.stderr)
for e in errors:
    print(f"   ❌ {e}", file=sys.stderr)
for w in warnings:
    print(f"   ⚠️  {w}", file=sys.stderr)
sys.exit(2 if errors else 0)
