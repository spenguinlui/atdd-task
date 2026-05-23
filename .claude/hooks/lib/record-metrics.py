#!/usr/bin/env python3
"""record-metrics 重邏輯（被 record-metrics.sh 呼叫）。
argv: <hook_input_json_file> <hub_dir>
行為與原 hook 一致：解析 agent metrics（3 path + transcript fallback）+ tool breakdown，更新活躍 task JSON。
"""
import sys, json, re, os, glob
from datetime import datetime
from collections import Counter

inp_file, hub = sys.argv[1], sys.argv[2]
try:
    data = json.load(open(inp_file))
except Exception:
    sys.exit(0)

agent = data.get("agent_type") or data.get("tool_input", {}).get("subagent_type", "")
ATDD = {"specist", "tester", "coder", "style-reviewer", "risk-reviewer", "gatekeeper"}
if not agent or agent not in ATDD:
    sys.exit(0)

tool_uses = tokens = duration_ms = 0
# path 1: usage
u = data.get("usage", {}) or {}
if u:
    tool_uses, tokens, duration_ms = u.get("tool_uses", 0), u.get("total_tokens", 0), u.get("duration_ms", 0)
# path 2: tool_response.usage
if not tool_uses:
    resp = data.get("tool_response", {})
    if isinstance(resp, dict):
        u = resp.get("usage", {}) or {}
        tool_uses, tokens, duration_ms = u.get("tool_uses", 0), u.get("total_tokens", 0), u.get("duration_ms", 0)
# path 3: text <usage> 標籤
if not tool_uses:
    out = str(data.get("tool_response", data.get("agent_output", "")))
    m = re.search(r"tool_uses:\s*(\d+)", out);   tool_uses = int(m.group(1)) if m else tool_uses
    m = re.search(r"total_tokens:\s*(\d+)", out); tokens = int(m.group(1)) if m else tokens
    m = re.search(r"duration_ms:\s*(\d+)", out);  duration_ms = int(m.group(1)) if m else duration_ms

tpath = data.get("agent_transcript_path") or data.get("transcript_path", "")

# transcript fallback（全 0 時，讀 tail 50 行）
if not tool_uses and not tokens and tpath and os.path.isfile(tpath):
    tail = open(tpath).read().strip().split("\n")[-50:]
    text = "\n".join(tail)
    tk = 0
    for line in tail:
        try:
            e = json.loads(line)
            if "usage" in e:
                uu = e["usage"]; tk += uu.get("input_tokens", 0) + uu.get("output_tokens", 0)
        except Exception:
            pass
    m = re.search(r"tool_uses:\s*(\d+)", text);   tool_uses = int(m.group(1)) if m else 0
    m = re.search(r"total_tokens:\s*(\d+)", text); tokens = max(tk, int(m.group(1))) if m else tk
    m = re.search(r"duration_ms:\s*(\d+)", text);  duration_ms = int(m.group(1)) if m else 0

# tool breakdown（讀整份 transcript）
breakdown = {}
if tpath and os.path.isfile(tpath):
    counts = Counter()
    for line in open(tpath):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        msg = rec.get("message")
        content = msg.get("content") if isinstance(msg, dict) else None
        if content is None:
            content = rec.get("content")
        if not isinstance(content, list):
            continue
        for it in content:
            if isinstance(it, dict) and it.get("type") == "tool_use":
                counts[it.get("name", "unknown")] += 1
    breakdown = dict(sorted(counts.items(), key=lambda x: -x[1]))

if duration_ms > 0:
    mn, sc = duration_ms // 60000, (duration_ms % 60000) // 1000
    duration = f"{mn}m {sc}s" if mn > 0 else f"{sc}s"
else:
    duration = "0s"

ROLE = {"specist": "需求分析", "tester": "測試生成", "coder": "代碼實作",
        "style-reviewer": "風格審查", "risk-reviewer": "風險審查", "gatekeeper": "品質把關"}

tasks = sorted(glob.glob(os.path.join(hub, "tasks", "*", "active", "*.json")))
if not tasks:
    print("⚠️ 沒有找到活躍的任務，跳過 metrics 記錄"); sys.exit(0)
task_path = tasks[0]
task = json.load(open(task_path))
task.setdefault("agents", [])
task["agents"].append({
    "name": agent, "role": ROLE.get(agent, "未知"), "phase": task.get("status", ""),
    "metrics": {"toolUses": tool_uses, "tokens": tokens, "duration": duration, "toolBreakdown": breakdown},
    "timestamp": datetime.now().isoformat(),
})
total_tools = sum(a.get("metrics", {}).get("toolUses", 0) for a in task["agents"])
total_tokens = sum(a.get("metrics", {}).get("tokens", 0) for a in task["agents"])
tb = Counter()
for a in task["agents"]:
    for k, v in (a.get("metrics", {}).get("toolBreakdown", {}) or {}).items():
        tb[k] += v
if task.get("metrics") is None:
    task["metrics"] = {}
task["metrics"]["totalToolUses"] = total_tools
task["metrics"]["totalTokens"] = total_tokens
task["metrics"]["totalToolBreakdown"] = dict(sorted(tb.items(), key=lambda x: -x[1]))
task["updatedAt"] = datetime.now().isoformat()
json.dump(task, open(task_path, "w"), ensure_ascii=False, indent=2)
print(f"✅ Metrics 已記錄：{agent} {tool_uses} tools / {tokens} tokens → {task_path}")
