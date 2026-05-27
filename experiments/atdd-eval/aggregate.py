#!/usr/bin/env python3
# 讀 matrix log 的 METRICS 行 → 彙整成報告（效率/成本/正確性 + 使用總結）
import sys, re, statistics as st
from collections import defaultdict

log = open(sys.argv[1], encoding='utf-8', errors='ignore').read()
rows = []
for ln in log.splitlines():
    if not ln.startswith('METRICS|'):
        continue
    d = {}
    for kv in ln.split('|')[1:]:
        if '=' in kv:
            k, v = kv.split('=', 1); d[k] = v
    rows.append(d)

def num(x):
    try: return float(x)
    except: return None

def correctness(agent, c):
    # 回傳 (fraction 0..1, 顯示字串)
    if agent == 'coder':
        m = re.search(r'pass=(\d+)/(\d+)', c)
        if m and int(m.group(2)) > 0: return int(m.group(1))/int(m.group(2)), f"{m.group(1)}/{m.group(2)}"
    if agent == 'tester':
        m = re.search(r'valid=(\d)', c); return (int(m.group(1)), f"valid={m.group(1)}") if m else (None, c)
    if agent in ('risk-reviewer', 'style-reviewer'):
        hit = 'hit_region=Y' in c; sev = re.search(r'sev_marks=(\d+)', c)
        return (1.0 if hit else 0.0, f"命中={'Y' if hit else 'N'},sev={sev.group(1) if sev else '?'}")
    if agent == 'specist':
        m = re.search(r'rubric=(\d+)/(\d+)', c)
        if m: return int(m.group(1))/int(m.group(2)), f"{m.group(1)}/{m.group(2)}"
    if agent == 'gatekeeper':
        m = re.search(r'(\d+)/(\d+)', c)
        if m: return int(m.group(1))/int(m.group(2)), f"{m.group(1)}/{m.group(2)}"
    return None, c

MODEL = {('claude','opus'):'Opus 4.7',('claude','sonnet'):'Sonnet 4.6',
         ('claude','haiku'):'Haiku 4.5',('codex','gpt-5.5'):'gpt-5.5',
         ('gold','gold'):'gold(真實修復)'}
def mname(e,m): return MODEL.get((e,m), f"{e}:{m}")

AGENTS = ['specist','coder','tester','risk-reviewer','style-reviewer','gatekeeper']
agg = defaultdict(lambda: defaultdict(list))  # agent -> model -> [row...]
for d in rows:
    agg[d['agent']][mname(d['engine'], d.get('model','?'))].append(d)

out = []
out.append("# 全 agent × model eval 報告 — 效率 / 成本 / 正確性\n")
out.append(f"來源 log：`{sys.argv[1].split('/')[-1]}`。每格為 N 次平均。\n")

best = {}  # agent -> (model, frac)
for agent in AGENTS:
    if agent not in agg: continue
    out.append(f"\n## {agent}\n")
    out.append("| Model | 正確性 | 平均耗時 | 平均 tokens | 平均 $ | N |")
    out.append("|---|---|---|---|---|---|")
    best_frac = -1; best_model = None
    for model, rs in sorted(agg[agent].items()):
        secs = [num(r.get('secs')) for r in rs if num(r.get('secs')) is not None]
        toks = [num(r.get('tokens')) for r in rs if num(r.get('tokens')) is not None]
        costs = [num(r.get('cost')) for r in rs if num(r.get('cost')) is not None]
        fracs, labels = [], []
        for r in rs:
            f, lab = correctness(agent, r.get('correct',''))
            if f is not None: fracs.append(f)
            labels.append(lab)
        avg_secs = f"{st.mean(secs):.0f}s" if secs else "-"
        avg_tok = f"{st.mean(toks):.0f}" if toks else "-"
        avg_cost = f"${st.mean(costs):.4f}" if costs else "-"
        corr = f"{st.mean(fracs)*100:.0f}%" if fracs else "-"
        corr += f" ({'/'.join(dict.fromkeys(labels))})" if labels else ""
        out.append(f"| {model} | {corr} | {avg_secs} | {avg_tok} | {avg_cost} | {len(rs)} |")
        if model != 'gold(真實修復)' and fracs and st.mean(fracs) > best_frac:
            best_frac = st.mean(fracs); best_model = model
    if best_model: best[agent] = (best_model, best_frac)

out.append("\n## 使用總結（每 agent 推薦 model）\n")
out.append("| Agent | 正確性最佳 | 備註 |")
out.append("|---|---|---|")
for agent in AGENTS:
    if agent in best:
        m, f = best[agent]
        out.append(f"| {agent} | **{m}**（{f*100:.0f}%） | 見上表權衡成本/效率 |")
out.append("\n> 正確性相同時，選成本/耗時較低者。gpt-5.5 vs Claude 的取捨見各 agent 表。")
out.append("> ⚠️ 自動彙整；正確性定義各 agent 不同（coder=隱藏測試通過率、tester=fail-before/pass-after 有效性、reviewer=命中 fix 區、specist=結構 rubric、gatekeeper=決策正確率）。")

print('\n'.join(out))
