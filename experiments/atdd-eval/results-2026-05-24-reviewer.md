# Model 比對結果 2026-05-24 — risk-reviewer 審 code（e_trading GRE-262 轉供結果訊息揭露）

題目：真實票 GRE-262 的 **base（fix 前）code**，跑同一份 `risk-reviewer.md` 提示，比各 model 抓問題的能力。
工具：`experiments/atdd-eval/eval-reviewer.sh e_trading GRE-262`。每 model 1 次（N=1，先取信號；N=3 待跑）。
Ground truth：fix `1714bd3c` 改動區 `validate_system_info.rb:18-42`、`_entity.slim:4-8`。

## 成本 + 校準（自動量）

| Model | 整體判級 | tokens | 耗時 | 輸出長度 | severity 標記數 |
|---|---|---|---|---|---|
| Opus 4.7 | Medium | 15.5k | 127s | 4725 字 | 9 |
| Sonnet 4.6 | Medium | 7.9k | 155s | 4929 字 | 6 |
| Haiku 4.5 | **HIGH（2 Critical + 2 High）** | 4.5k | 41s | 3813 字 | 13 |
| gpt-5.5（第1次） | Medium | 68k | ~~6131s（102 分，異常）~~ | 1383 字 | 6 |
| gpt-5.5（重測） | Medium | 52k | **75s** | 2539 字 | 7 |

> 全 4 model `hit_file=Y`、`hit_region=Y`（因 eval 直接給了待審檔，檔/區命中不具鑑別力——鑑別在「抓到哪些**真**問題 + 嚴重度校準 + scope 紀律」，見下）。

> **gpt-5.5 第1次 6131s 經重測確認為異常**（重測 75s、10 步正常 agentic、log 無 rate-limit/retry）——單次卡住（疑 ChatGPT 額度退避），**非常態**，延遲不列為缺點。但**review 內容 pattern 兩輪一致**（見解讀 1），品質結論不受延遲異常影響。

## 真問題覆蓋（in-scope code 缺陷；人工複核）

| 問題（risk-reviewer 範圍內） | Opus | Sonnet | Haiku | gpt-5.5 |
|---|:--:|:--:|:--:|:--:|
| `notify_error` message 型別不一致（4 呼叫點 2 個漏 `join` → Array vs String） | ✅ R-001 | · | · | · |
| 未防護例外／`dispatch_name` nil 解參考（2 個 validate 無 rescue） | ✅ N-004 | ✅ R-002 | · | · |
| N+1（per-account `retrieve_after_wheeling_task_by_account`） | ✅ R-002 | ✅ R-001 | · | ✅(第1次 note→重測升 finding) |
| 敏感資料（電號／account id）入訊息與 log | ~note | · | ✅(High) | · |
| **正確判定 base XSS guard 安全**（sanitize 只放 br） | ✅ | n/a | ❌(誤報 Critical) | ✅ |
| **scope 紀律**：spec 缺口歸 gatekeeper（不當 finding） | ✅(N-006→gatekeeper) | ✅ | ❌(混入 Critical) | ❌(當成 2 條 Medium finding) |

## 解讀（對 atdd-task 的意義，不替業主決定 model）

1. **gpt-5.5 重演 5/22 的 pattern（兩輪一致，非偶然）**：兩次都 **(a) 把 spec 缺口當 finding**（base 缺 D2 的四方向差集 / deep link），而 `risk-reviewer.md` 明定 spec-AC 落差歸 gatekeeper、不進 findings → **scope 跑掉**；**(b) 兩次都漏**真正 in-scope 的 code 缺陷（`notify_error` 型別不一致、nil 解參考）。唯一進步：N+1 第1次擺 note、重測升成 finding。「方向感對、抓錯層級、漏細節」與 specist 那次「自信但漏邊界」同源。延遲第1次 102 分為異常（重測 75s 正常），**不構成缺點**。
2. **Opus 最強**：唯一抓到 `notify_error` 型別不一致（最細、需追 monad 流），且**主動把 spec 缺口寫成 note 標『→ gatekeeper』**，scope 紀律最好；又正確判定 base XSS 無虞。深度 + 紀律 + 不浮誇。
3. **Sonnet 性價比**：N+1 + 例外/nil 兩條紮實 in-scope finding、不亂升級、tokens 最省（7.9k）。漏型別不一致。
4. **Haiku 過度升級**：唯一判 HIGH，丟 **2 個 Critical**（XSS、邏輯斷裂）——XSS 在 base 其實安全（它自己也提到 sanitize 只放 br 卻仍判 Critical）= **誤報**。對 review 閘門最危險：假 Critical 會誤擋發布 + 警報疲勞。但它是唯一點出「敏感資料入訊息」的。
5. **gpt-5.5 第1次 102 分為一次性異常，已排除**：重測 75s、正常 10 步 agentic、log 無 rate-limit/retry。延遲**不列入**評價（但提醒：codex 經 ChatGPT auth 偶發卡死，production 委派要設 timeout 兜底）。

## 結論對「reviewer 委派 GPT」的指向

- **先別把 risk-reviewer 預設翻成 gpt-5.5**。延遲異常排除後，仍有兩個對「審查閘門」最傷的特性、且**兩輪一致**：**scope 漂移**（spec 缺口當 finding）+ **漏 in-scope 細缺陷**（型別不一致、nil 解參考）。它不是差——3 條 Medium 含 N+1 都站得住——但**不夠 scope 紀律、不夠深**。
- 真要用不同 model 抓盲點，**Opus 當 reviewer 最穩**（最深 + scope 紀律）；要省成本 Sonnet。
- gpt-5.5 的價值可能在別處（如 coder，eval-coder 另測），不是 reviewer。

## 誠實校準（別過度解讀）
- **樣本**：Claude 各 N=1，gpt-5.5 N=2（含異常那次）。gpt-5.5 的 review 內容兩輪一致（scope 漂移 + 漏細缺陷穩定）；其 102 分延遲經重測排除。Haiku 的 2 Critical 是否每次都丟、Claude 三家穩定度仍需 N≥3 固化。
- **檔案已給** → 這測的是「給定檔案的審查深度/紀律」，非「從大 scope 找對檔」（後者更難，未測）。
- **題目偏 feature 改動**：base 的「缺陷」多是缺 D2 功能（spec 缺口），純 in-scope risk 缺陷較少 → 放大了「scope 紀律」這軸的權重。換一張**純 bug fix** 票（如 GRE-248 importer 少建 Rate）可補另一面向。
- severity 標記數為關鍵字近似；真問題覆蓋表為人工複核。

## eval 待強化（下一版）
- 跑 N=3 + 加一張純 bug-fix 票（GRE-248）對照。
- scorer 自動標「finding 是否落在 risk-scope（vs spec-gap）」需語意判斷，目前靠人工——可加一個 LLM-judge 子步驟。
- gpt-5.5 延遲需獨立計時複測（排除 host 節流干擾）。
