---
name: rails-local-dev
description: 在 4 個 Rails 專案（sf_project / jv_project / core_web / e_trading）跑 local dev 指令——console、server、rspec、migrate、rake、bundle。這些指令一律「進 Tilt 起的 web container」跑，不在 host 直接跑。Use when 要對這些 rails 專案開 console、跑 rspec、跑 migration / rake / bundle，或 local server（sf.local / jv.local / core.local / et.local）連不上要排查時。
version: 1.0.0
---

# Rails Local Dev 指令

4 個 Rails 專案的 local 開發環境由 **Tilt + Docker** 統一管理（workspace 在
`~/sunnyfounder/tilt-workspace`，由 ai-infra-management 維護）。

## 核心模型（先讀這段）

| 你想做的事 | 怎麼做 |
|---|---|
| **server**（看畫面） | 不用自己起。web server 就是 Tilt 起的 web container 本身，瀏覽 `http://sf.local` 等即可。改 code 會 auto-reload（`.:/app` 已 mount） |
| **console** | `docker exec -it <container> bundle exec rails console` |
| **rspec** | `docker exec -i -e RAILS_ENV=test <container> bundle exec rspec <file>`　⚠️ **必帶 `-e RAILS_ENV=test`**（見下方「資料庫安全」） |
| **migrate** | `docker exec -i <container> bundle exec rails db:migrate` |
| **rake / bundle / runner** | 同上，`docker exec -i <container> bundle exec <...>` |

## ⚠️ 資料庫安全：rspec 必帶 `RAILS_ENV=test`（會清庫的地雷）

**跑 rspec 一定要 `docker exec -i -e RAILS_ENV=test <container> ...`，否則會 truncate 掉 dev DB 的全部資料（含 production dump）。**

機制（2026-05-25 實際踩雷後查證，sf_project）：
1. Tilt web container 的 env 寫死 `RAILS_ENV=development`。
2. `.rspec` 預設 `--require lite_helper`；lite_helper / rails_helper 都用 `ENV['RAILS_ENV'] ||= 'test'`，但 `||=` 對「已是 development」**無效** → rspec 實際跑在 `Rails.env=development`，連的是 dev DB（如 `sf_project`）。
3. `spec/support/database_cleaner.rb` 在 `before(:suite)` 就 `DatabaseCleaner.clean_with :truncation`，且 docker 下 `allow_remote_database_url=true`、**沒有 test-env 守門**（只擋 production）。
4. 結果：第一發 rspec 的 suite 前置 truncation 就把 dev DB 全表清空，74 張業務表瞬間歸零，schema 留著。

**正解**：明確 `-e RAILS_ENV=test`（不能靠 `||=`，因 container 已設 development）。test env 連的是另一個 DB（`database.yml` test = `<dbname>_test`），清的是 test DB，dev 的 dump 不受影響。

> 跑前自我檢查（可選但建議）：
> `docker exec -i -e RAILS_ENV=test <container> bundle exec ruby -e "require './config/environment'; abort('NOT TEST ENV') unless Rails.env.test?"`

**為什麼一律進 container，不在 host 直接 `bundle exec`**：各專案 `.env` 的
`DATABASE_PORT` 多半還指向已廢棄的 PG12 舊 port（sf=15432 / jv=15434 / core=15436），
`REDIS_URL` 也指 `localhost:6379`——host 上直接跑會連不到 DB / Redis。container 內
由 compose 覆寫成 `db-pg16:5432` 與 `redis:6379`，是唯一能正常連的路徑。

> 例外：Capybara feature spec 因需要 host 端 chromedriver，走法不同，見
> `.claude/guides/capybara-setup.md`。

## 後台登入：admin 帳密（= seed）+ 一鍵正規化

local dev DB 常是 production dump，admin 密碼是 production hash（沒人知道）、可能開 OTP，
**E2E / 手動看後台每次都卡在登入**。一鍵把指定 admin 密碼設回「seed 版本」+ 關 OTP + 解鎖
（admin 不存在時自動 `db:seed` 建）：

```bash
.claude/scripts/ensure-admin-login.sh <sf_project|jv_project|core_web|e_trading>
```

帳密一律對齊各 repo `db/seeds`（`default_staff.rb` / `default_admin.rb`）：

| 專案 | model | email | 密碼 |
|------|-------|-------|------|
| sf_project | `Admin::Models::Staff` | admin@sunnyfounder.com | `admin123456` |
| jv_project | `Admin::Models::Staff` | admin@sunnyfounder.com | `admin123456` |
| core_web | `Admin::Models::AdminUser` | admin@sunnyfounder.com | `admin12345` |
| e_trading | `Admin::Models::Staff` | admin@sunnyfounder.com | `test123456` |

> 腳本操作 dev DB（`RAILS_ENV=development`，rails runner / db:seed 不觸發 DatabaseCleaner，安全）。
> email 是加密欄位，`find_by(email:)` 比對密文會失敗 → 腳本用 detect 逐筆解密比對。
> 安全界線：密碼**打進登入表單**那一步由人做（原廠規範禁止 agent 代填密碼）；腳本只負責讓帳密可用。

## 前置條件：Tilt 要在跑

```bash
# 確認 web container 是否 Up
docker ps --format '{{.Names}}\t{{.Status}}' | grep -E 'sf-web|jv-app|core-web|et-app'

# 沒在跑就啟動全部（image 已 build 好，啟動很快）
cd ~/sunnyfounder/tilt-workspace && /opt/homebrew/bin/tilt up --stream=true
#  ↑ 用絕對路徑，避開 RVM 的 tilt gem 衝突
#  Tilt UI: http://localhost:10350   Traefik dashboard: http://localhost:8080
```

## 專案 → 容器 / URL 對照

| 專案 | 容器（`docker exec` 對象） | URL | DB 名 / user | PG16 host port |
|---|---|---|---|---|
| sf_project | `sf_project-sf-web-1`（+ sidekiq `sf_project-sf-sidekiq-1`） | http://sf.local | sf_project / root | 15433 |
| jv_project | `jv_project-jv-app-1` | http://jv.local | jv_project / sunnyfounder | 15435 |
| core_web | `core_web-core-web-1` | **http://admin.core.local** ⚠️ | sunny_founder / sunnyfounder | 15437 |
| e_trading | `e_trading-et-app-1` | **http://et.local/admin** | e_trading / sunnyfounder | 15439 |

> **core_web / e_trading 前端已下架，主用 admin 後台**，入口不是裸網址：
> - **core_web → `http://admin.core.local`**（admin 走 **subdomain**，`slices/admin` 約束 `/^admin/`）。
>   ⚠️ 需 `/etc/hosts` 有 `admin.core.local`，且 Traefik 有路由該 host（compose `core_web.yml` 的 router rule）。裸 `core.local` 只會回 Rails 預設歡迎頁。
> - **e_trading → `http://et.local/admin`**（admin 是 **path** `namespace :admin`，非 subdomain）。現有 Traefik 即可用，裸 `et.local` 會 302 轉 `/dashboard` 登入。

（host port 只在 host 端用 `psql` 直連 DB 時需要；rails 指令進 container 不需要它。
DB 密碼皆 `1111`。）

core_web_frontend（Next.js）走 `http://localhost:3100`，由 Tilt 的 `frontend`
local_resource 跑 `yarn dev`，與上表 Rails 無關。

## 指令範本（以 sf_project 為例，換容器名即套用其他專案）

```bash
# Console（互動，要 -it）
docker exec -it sf_project-sf-web-1 bundle exec rails console

# 跑單一 spec ── ⚠️ rspec 一律帶 -e RAILS_ENV=test（理由見「資料庫安全」段）
docker exec -i -e RAILS_ENV=test sf_project-sf-web-1 bundle exec rspec spec/models/foo_spec.rb --format documentation

# Migrate
docker exec -i sf_project-sf-web-1 bundle exec rails db:migrate

# Migration 狀態
docker exec -i sf_project-sf-web-1 bundle exec rails db:migrate:status

# rake task
docker exec -i sf_project-sf-web-1 bundle exec rake <task>

# 一次性 runner
docker exec -i sf_project-sf-web-1 bundle exec rails runner 'puts User.count'

# 改了 Gemfile 後重裝
docker exec -i sf_project-sf-web-1 bundle install
```

> 容器內 WORKDIR 已是 `/app`、Ruby 走容器自帶 rbenv 2.6.0，不必 `cd`、不必 `rvm use`。
> 互動式（console）才需要 `-it`；非互動（rspec / migrate / runner）用 `-i` 即可。

## 故障排除

| 症狀 | 原因 / 解法 |
|---|---|
| `http://*.local` 全 `HTTP 000` / 連不上、`docker ps` 看不到 web container | Tilt 沒在跑或 reconcile 卡住。`cd ~/sunnyfounder/tilt-workspace && tilt up` 重起；若報 `port 10350 in use` 是舊 Tilt 卡著，先 `kill` 該 process 再起 |
| `docker exec` 報 `No such container` | 該 service 沒起（被 disable 或崩了）。看 Tilt UI（localhost:10350）對應 group，或 `docker ps -a` 查狀態 |
| rails 報 `PG::ConnectionBad: could not translate host name "db-pg16"` 或整片 500 | 最常見：PG container 被 OOM / 休眠 SIGKILL（`docker ps -a \| grep db-pg16` 看到 `Exited (137)`）。一行修復：`docker start sf_project-sf-db-pg16-1 jv_project-jv-db-pg16-1 core_web-core-db-pg16-1 e_trading-et-db-pg16-1`，資料不會掉 |
| web container `Exited (255)`（剛開機 / docker 重啟後） | DB / redis 還沒起就被拉起來撞掛。`tilt up` 重跑會照 depends_on 正確順序帶起 |

## 權威來源

- 指令定義（每專案 `test.*` 欄位）：`.claude/config/projects.yml`
- Tilt 架構 / port 盤點 / 完整故障排除：`~/ai-infra-management/docs/local-dev/tilt-workspace.md`
- Production 資料同步到 local DB：`~/ai-infra-management/docs/local-dev/db-sync-pg16.md`
</content>
</invoke>
