# 行為驗證 eval harness — Stage 1 findings（2026-05-23）

各 agent 階段 × model 客觀比分，用**真實票 + 封閉 worktree + docker 實跑驗收測試**取 ground truth。
設計圖：meta-harness `prescriptions/2026-05-23-atdd-eval-harness.md`。

## 狀態
- ✅ **Stage 1 命門已打通**（整套設計賴以成立的最大未知）。
- ⬜ 尚未固化成腳本：`build-instance.sh` / `sandbox.sh` / `run-coder.sh` / gold-relative `score.sh`；Stage 2-4 未做。
- 已有：`list-candidates.sh`（列有驗收套件 + 有修復 commit 的票，按改動規模排序，供挑大型任務）。

## 命門證明（CST-145, sf_project）— 已驗證的 recipe
實例：票 CST-145，修復 commit `607c12a8`，base = `607c12a8^`。
- 測試（ground truth）：`spec/.../project/repositories/project/factory_cst145_spec.rb` + `spec/.../project/use_cases/rollback_project_version_spec.rb`（commit 內含）
- code 修復：`project.rb` / `factory.rb` / `wrapper.rb`（同 commit）

可用沙箱 recipe（實測 OK）：
```bash
REPO=/Users/liu/sunnyfounder/sf_project; CONT=sf_project-sf-web-1; FIX=607c12a8
WT="$REPO/.eval-<id>"; EVALDB=sunnyfounder_eval<id>
git -C "$REPO" worktree add -f "$WT" "$FIX"            # 或 base（worktree 在 repo 下→容器 /app/.eval-<id> 可見）
docker exec "$CONT" sh -c "cd /app/.eval-<id> && RAILS_ENV=test DATABASE_DBTEST=$EVALDB bundle exec rails db:create db:schema:load"
docker exec "$CONT" sh -c "cd /app/.eval-<id> && DATABASE_DBTEST=$EVALDB bundle exec rspec <specs>"
# 清理
docker exec "$CONT" sh -c "cd /app/.eval-<id> && RAILS_ENV=test DATABASE_DBTEST=$EVALDB bundle exec rails db:drop"
git -C "$REPO" worktree remove --force "$WT"
```

實測結果：
- base + 測試 patch（無 code 修復）→ **48 examples, 16 failures**（強鑑別 ✅）
- base + 真實 code 修復 / 或 worktree 直接到 fix → **48 examples, 1 failure**（47/48）
- 容器可見性 ✅、worktree 內 bundle ✅、隔離 test DB 建/遷/清 ✅

## 兩條設計 refinement（spike 逼出，已入設計圖）
1. **沙箱**：worktree 放 `<repo>/.eval-<id>`（bind-mount 可見）+ 隔離 test DB（`DATABASE_DBTEST`）→ 不碰共用 test DB、schema 對齊實例。
2. **scorer = gold-relative，非絕對 0**：gold（真實修復）自己也剩 1 個環境依賴 example（seed/順序/CI-only）。
   → 先跑 gold 取「passing set」，model 修法對照該集合計分（過幾 / |passing set|），自動濾環境噪音。

## 下一步（固化）
1. `build-instance.sh <project> <ticket>`：自 commit 推 base / 分 spec(測試)+code 檔 / 產實例 manifest（含測試指令）。
2. `sandbox.sh`：上面 recipe 函式化（建 worktree + 隔離 DB + trap 清理）。
3. `run-coder.sh <instance> <engine> <model>`：sandbox 內讓 coder 重做 → 套 diff → 跑 specs。
4. `score.sh`：gold-relative（先跑 gold 取 passing set → model 對照）。
5. Stage 2：tester / reviewers（git 真相，不需 API）。Stage 3：specist / gatekeeper（需本機 API localhost:8001 起來）。Stage 4：跨 model matrix。

## 前置
- docker 測試容器要在跑（4 個 Rails 專案）。
- Stage 3 兩階段需本機 API（localhost:8001）——目前未起。
