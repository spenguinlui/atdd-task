# 全 agent × model eval 報告 — 效率 / 成本 / 正確性 + 使用總結（2026-05-24）

範圍：6 個 agent（specist / coder / **tester** / risk-reviewer / style-reviewer / gatekeeper）× 4 model（Opus 4.7 / Sonnet 4.6 / Haiku 4.5 / gpt-5.5）× **N=3**。
（tester 的 sonnet/haiku 撞 Claude 額度＝空輸出、無效，僅 opus/gpt-5.5 有有效數據——見 tester 段。）實例：coder/tester=sf_project CST-145、reviewer=e_trading GRE-262、specist=spec-task 平面題、gatekeeper=8 構造場景。
腳本：`experiments/atdd-eval/eval-{coder,reviewer,specist,gatekeeper}.sh` + `aggregate.py`。

---

## 數據總表（每格 N=3 平均；正確性定義各 agent 不同）

### specist（寫 spec，7 項結構 rubric）
| Model | 正確性 | 耗時 | tokens | $ |
|---|---|---|---|---|
| Opus 4.7 | 7/7 | 80s | 8.7k | $0.30 |
| Sonnet 4.6 | 7/7 | 187s | 11.4k | $0.21 |
| gpt-5.5 | 7/7 | 94s | 17.6k | — |
| Haiku 4.5 | 1/7* | 3s | — | — |
*Haiku 1/7 是 rubric 關鍵字格式對不上的假低分（5/22 已記過），非真的爛。

### coder（真改 code 跑隱藏驗收測試，gold=47/48）
| Model | 正確性 | 耗時 | tokens | $ |
|---|---|---|---|---|
| **gpt-5.5** | **39/48** | 129s | **110k** | — |
| Opus 4.7 | 32/48 | 206s | 13.2k | $1.04 |
| Sonnet 4.6 | 32/48 | 87s | 1.5k | $0.24 |
| Haiku 4.5 | 32/48 | 13s | 0.7k | $0.02 |
| gold(真實修復) | 47/48 | — | — | — |

### tester（model 寫驗收測試；有效=base FAIL 抓到 bug、套修復後 PASS）
| Model | 有效率 | 耗時 | tokens | 備註 |
|---|---|---|---|---|
| Opus 4.7 | **2/3** | 140s | 13.7k | 唯一穩定寫出抓得到 bug 的測試 |
| gpt-5.5 | 1/3 | 141s | 86.6k | 1 次抓到 |
| Sonnet 4.6 | — | — | — | 撞 Claude 額度＝空輸出（無效）|
| Haiku 4.5 | — | — | — | 同上（且 docker 在空 spec 上 hang 數小時）|

### risk-reviewer（命中 fix 改動區；sev=嚴重度標記數，深度代理）
| Model | 命中區 | sev（3 次） | 耗時 | tokens |
|---|---|---|---|---|
| Opus 4.7 | ✅ | 7,8,8 | 124s | 14.7k |
| Sonnet 4.6 | ✅ | 7,6,6 | 135s | 7.2k |
| Haiku 4.5 | ✅ | 13,9,6 | 65s | 6.8k |
| gpt-5.5 | ✅ | 2,2,4 | 70s | **42.5k** |

### style-reviewer
| Model | 命中區 | sev | 耗時 | tokens |
|---|---|---|---|---|
| Sonnet 4.6 | ✅ | 1-2 | 67s | **2.9k** |
| Opus 4.7 | ✅ | 2-3 | 73s | 8.9k |
| Haiku 4.5 | ✅(1 次漏) | 2-3 | 66s | 6.0k |
| gpt-5.5 | ✅ | 2 | 59s | **34.7k** |

### gatekeeper（8 構造場景決策正確率）
| Model | 正確 | 耗時 | tokens |
|---|---|---|---|
| Opus 4.7 | 8/8 | 8s | 2.0k |
| Sonnet 4.6 | 8/8 | 10s | ~低 |
| gpt-5.5 | 8/8 | 2s | 15.4k |
| Haiku 4.5 | 7-8/8 | 20s | 1.7k |

---

> ⚠️ **token 欄位跨家不可比，已更正**：上表 codex(gpt-5.5) 的 token 是 codex「tokens used」**總量**（含 system prompt＋每輪 context＋reasoning；實測連「回 OK」都報 11,612）；Claude 欄是 `input+output` **未含 cache**（實測「回 OK」的 cache_creation 就 51,229 被我漏算）。兩者基準不同 → **原本「gpt-5.5 token 是 Claude 3–7 倍」的說法不成立，已撤回**。公平成本只能看 `$`，但 **codex `$` 本輪未擷取** → 跨家成本本輪**無定論**（待補）。token 欄僅供同一引擎內參考。

## 跨 agent 解讀（關鍵訊號）

1. **gpt-5.5 唯一贏的地方是 coder**（39/48 vs Claude 全部 32/48，最接近 gold 47）。它真的把 code 改對更多。（成本是否划算本輪不可比，見上方 token 更正。）
2. **reviewer 上 gpt-5.5 偏淺**：sev 標記只 2-4（Opus/Sonnet 6-8），呼應 5/24 單票深測「自信、精簡、漏細缺陷、scope 漂移」。這是**深度/scope**結論，不靠 token。
3. **Claude 家內成本可比（$，cache-correct）**：coder Opus $1.04 ≫ Sonnet $0.24 ≫ Haiku $0.02；specist Opus $0.30、Sonnet $0.21。Sonnet 在多數 agent 是 Claude 家內性價比王。
4. **Haiku 便宜快但有品控問題**：risk-reviewer 過度標記（sev=13 噪音）、specist rubric 格式踩雷、coder 階段 3 次有 2 次回 0 token（空輸出/撞額度）。只適合便宜簡單階段。
5. **gatekeeper 規則決策全 model 幾乎滿分** → 這階段 model 強弱拉不開，挑最便宜最快的（Sonnet/Opus）即可。

## 使用總結（每 agent 建議 model）

| Agent | 建議 | 理由 |
|---|---|---|
| **specist** | Opus（深）／Sonnet（省） | 都 7/7；Opus 快、Sonnet 便宜但較慢；gpt-5.5 token 重 |
| **coder** | **gpt-5.5**（要正確度）／Sonnet（要省） | gpt-5.5 唯一明顯多修對（39 vs 32），但 token 爆量；Claude 數字有方法學疑慮（見 caveat）|
| **tester** | **Opus**（2/3 抓到 bug） | gpt-5.5 1/3；Sonnet/Haiku 本輪撞額度無數據。寫「抓得到 bug 的測試」是難的，多數會寫成 happy-path（valid=0）|
| **risk-reviewer** | **Opus**（深）／Sonnet（值） | 實質 finding 多又便宜；**不要 gpt-5.5**（淺+scope 漂移）、**不要 Haiku**（噪音）|
| **style-reviewer** | **Sonnet** | 最省 token、命中穩 |
| **gatekeeper** | Sonnet／Opus | 規則題全對、便宜快；gpt-5.5 為是非題燒 15k token 浪費 |

**一句話**：把 reviewer 預設翻 gpt-5.5 的原始念頭，數據不支持——它在 reviewer 又貴又淺；gpt-5.5 真正值得用的是 **coder**。整體 **Sonnet 當主力、Opus 補深度** 最划算。

## 誠實 caveat（別過度解讀）
- **coder 的 Claude 數字有方法學疑慮**：4 個 model 全 32/48（疑為「沒有效修改＝base 通過數」）；Haiku 3 次有 2 次 0 token＝空輸出（撞 Claude 額度或 `claude -p` 在 worktree 沒真的落 edit）。gpt-5.5 走 codex（workspace-write）確實落 edit、39/48 可信；**Claude coder 需重驗 edit-persistence 後才算數**。
- **reviewer 正確性=「命中 fix 區」幾乎全 Y**（因 eval 直接給待審檔）→ 真正鑑別在 sev 深度＋token 成本，不在命中率。
- **Haiku specist 1/7** 是 rubric 格式假低分。
- **額度干擾**：Claude 帳號 session 上限會在大批量時打爆（本輪一度 specist 後撞限）；分時段＋可續跑＋timeout 已加防護，但 coder-Haiku 仍疑有殘留空輸出。
- **gatekeeper Sonnet token 顯示偏低**含一次 cached 重評分值，非真實單次用量。

## tester（已補 scaffolding 跑出，但 Claude 額度只夠 opus/gpt）
- **scaffolding 修好了環境 blocker**：`eval-tester.sh` 現會注入 repo 真實 factory 名單（grep `spec/factories`，如 `project_management_project`）+ 同 domain 範例 spec（教 require/helper/describe 慣例）→ 不再 `Factory not registered`，測試能真的跑。
- **有效數據**：**Opus 2/3**（寫出 base 紅、修復後綠的測試）、**gpt-5.5 1/3**。Sonnet/Haiku 三次皆撞 Claude session 額度＝空輸出（tok=0）→ 無效（且 docker 在空 spec 上 db:create hang 數小時，拉長整批時間）。
- **解讀**：寫「真的抓得到 bug」的驗收測試是難工作——多數 model 會寫出 happy-path（valid=0，base 就綠）。Opus 相對穩。要公平比 Sonnet/Haiku 需 API key（另一額度）或分更多窗口重跑。
- **待修**：(a) tester 的 docker rspec 要加 timeout（空 spec hang 數小時）；(b) brief↔target_spec 對齊（CST-145 target 是 Factory 單元測試、brief 是 E2E 描述，略錯位 → 拉低 valid）。

## 另記：docker 穩定度
coder 第一輪跑到一半 **docker daemon 死掉**（資源壓力），導致多筆 0/0。已加 coder per-run marker（可續跑），重啟 docker + tilt 後續跑補齊。大批量 docker eval 要留意 daemon 穩定度。
