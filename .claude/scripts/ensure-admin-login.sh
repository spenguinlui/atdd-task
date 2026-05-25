#!/usr/bin/env bash
# ensure-admin-login.sh —— 確保某 Rails 專案的 dev DB 有一個「能用 seed 帳密登入」的 admin。
#
# 為什麼需要：local dev DB 常從 production dump 灌入，admin 密碼是 production hash（沒人知道），
# 且可能開了 OTP / 被鎖 → 每次 E2E 都卡在登入。這支腳本把指定 admin 的密碼設回「seed 版本」、
# 關閉 OTP、解鎖，讓 E2E 登入永遠用同一組已知帳密。冪等，可重複跑。
#   - admin 已存在（dump 常態）→ 直接重設密碼 / OTP / 解鎖
#   - admin 不存在（DB 空）   → 自動跑 `rails db:seed` 建出，再重設
#
# 重要：操作的是 dev DB（container 預設 RAILS_ENV=development）。rails runner / db:seed 不觸發
#       DatabaseCleaner，不會清庫；這正是 E2E 真瀏覽器（sf.local 等）連的那個 DB。
#
# 用法：.claude/scripts/ensure-admin-login.sh <sf_project|jv_project|core_web|e_trading>
set -euo pipefail

proj="${1:?usage: ensure-admin-login.sh <sf_project|jv_project|core_web|e_trading>}"

# 帳密一律對齊各專案 db/seeds 的 default_staff.rb / default_admin.rb
case "$proj" in
  sf_project) container=sf_project-sf-web-1;  model='Admin::Models::Staff';     email='admin@sunnyfounder.com'; pw='admin123456' ;;
  jv_project) container=jv_project-jv-app-1;  model='Admin::Models::Staff';     email='admin@sunnyfounder.com'; pw='admin123456' ;;
  core_web)   container=core_web-core-web-1;  model='Admin::Models::AdminUser'; email='admin@sunnyfounder.com'; pw='admin12345'  ;;
  e_trading)  container=e_trading-et-app-1;   model='Admin::Models::Staff';     email='admin@sunnyfounder.com'; pw='test123456'  ;;
  *) echo "unknown project: $proj （支援 sf_project / jv_project / core_web / e_trading）" >&2; exit 1 ;;
esac

# email 多為加密欄位，find_by(email:) 比對密文會失敗 → 用 detect 逐筆解密比對。
# 找不到時印 NOT_FOUND（由外層 bash 接手跑 db:seed）。
build_ruby() {
cat <<RUBY
model = ${model}
email = '${email}'
pw    = '${pw}'
abort('[ensure-admin] 拒絕在 production 執行') if Rails.env.production?
rec = model.all.detect { |r| (r.email == email rescue false) }
if rec.nil?
  puts '[ensure-admin] NOT_FOUND'
else
  rec.password = pw
  rec.password_confirmation = pw if rec.respond_to?(:password_confirmation=)
  rec.otp_required_for_login = false if rec.respond_to?(:otp_required_for_login=)
  rec[:failed_attempts] = 0   if rec.respond_to?(:failed_attempts)
  rec[:locked_at]       = nil if rec.respond_to?(:locked_at)
  ok = rec.save
  puts ok ? "[ensure-admin] SAVED #{model.name} email=#{email}" : "[ensure-admin] FAILED: #{rec.errors.full_messages.join(', ')}"
  rec.reload
  otp = rec.respond_to?(:otp_required_for_login) ? rec.otp_required_for_login : 'n/a'
  puts "[ensure-admin] verify valid_password?=#{rec.valid_password?(pw)} otp=#{otp}"
end
RUBY
}

run_reset() { docker exec -i "$container" bundle exec rails runner "$(build_ruby)" 2>&1 | grep -vE 'ttyname|Spring preloader'; }

out="$(run_reset)"; echo "$out"
if echo "$out" | grep -q 'NOT_FOUND'; then
  echo "[ensure-admin] DB 無此 admin → 跑 rails db:seed 建立…"
  docker exec -i "$container" bundle exec rails db:seed 2>&1 | grep -vE 'ttyname|Spring preloader' | tail -5
  echo "[ensure-admin] 重新設定…"
  run_reset
fi

echo
echo "→ 登入帳密：${email} / ${pw}（OTP 已關）  容器：${container}"
