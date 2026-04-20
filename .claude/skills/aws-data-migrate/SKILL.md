---
name: aws-data-migrate
description: 資料遷移工具，從 Production 安全地遷移資料到 Local/Staging 環境。自動清理敏感資料，硬編碼禁止反向遷移。
version: 3.0.0
---

# AWS Data Migrate

安全地從 Production 環境遷移資料到 Local/Staging，用於本地除錯和測試。

## Core Principles

> **Production 資料不可變** - 只允許 Production → Local/Staging 的單向遷移

### 允許的遷移方向

```
✅ Production → Local
✅ Production → Staging
❌ Local → Production     # 硬性禁止
❌ Staging → Production   # 硬性禁止
❌ Local → Staging        # 需要討論
```

## Prerequisites

- AWS CLI 已配置且認證有效（`aws sts get-caller-identity`）
- 目標資料庫已建立（PostgreSQL）
- 有 Production 資料庫的讀取權限
- SSM 可連線到相關 EC2 instance

## Instructions

### 1. 確認遷移需求

在開始遷移前，必須確認：

```markdown
📦 資料遷移需求確認

1. 遷移模式：{full_sync / partial_reset / selective}
2. 目標環境：{local / staging}
3. 需要遷移的 Table(s)：{all / 指定 tables / 全部但排除某些 table 的資料}
4. 敏感資料處理：{mask / keep}（Staging 同 VPC 可選 keep）

請確認以上資訊是否正確？
```

根據遷移模式選擇對應路徑：
- **全庫同步（full_sync）** → 走 Path A（DROP DATABASE 重建，需要 RDS master 權限）
- **部分重置（partial_reset）** → 走 Path C（保留指定 table 的資料，其他全部從 production 取代；不需要 master 權限）
- **選擇性遷移（selective）** → 走 Path B

---

## Path A：全庫同步（Production → Staging）

適用場景：Staging 環境需要完整的 Production 資料副本。

### A1. 前置檢查

```bash
# 1. 確認 AWS CLI 認證
aws sts get-caller-identity

# 2. 確認 Production / Staging EC2 都在 running
aws ec2 describe-instances --instance-ids "$PROD_INSTANCE_ID" "$STAGING_INSTANCE_ID" \
  --query "Reservations[].Instances[].{Id:InstanceId,State:State.Name}" --output table
```

### A2. 取得資料庫連線資訊

從兩邊的 `.env` 或 `shared/.env` 取得 DB 連線：

```bash
# Production DB 連線（從 shared/.env 取得）
aws ssm send-command --instance-ids "$PROD_INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["cat /home/apps/{app_name}/shared/.env | grep -E \"^(DATABASE_|RAILS_ENV)\""]'

# Staging DB 連線
aws ssm send-command --instance-ids "$STAGING_INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["cat /home/apps/{app_name}/shared/.env | grep -E \"^(DATABASE_|RAILS_ENV)\""]'
```

### A3. 測試 RDS 直連

Staging 可能能直連 Production RDS（同 VPC / peering），這樣可以省去檔案傳輸：

```bash
# 在 Staging EC2 上測試連線 Production RDS
aws ssm send-command --instance-ids "$STAGING_INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["sudo su - apps -c \"PGPASSWORD={prod_password} psql -h {prod_rds_host} -U {prod_user} -d {db_name} -c \\\"SELECT 1 as test;\\\"\""]'
```

- **連得上** → 直接在 Staging 上 pg_dump（推薦，省去傳輸步驟）
- **連不上** → 在 Production dump 後透過 S3 傳輸

### A4. 檢查磁碟空間

**重要：dump 前必須確認磁碟空間足夠（建議可用空間 > dump 預估大小的 1.5 倍）**

```bash
# 檢查磁碟空間和舊 dump 檔案
aws ssm send-command --instance-ids "$TARGET_INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["df -h /home/apps && echo --- && ls -lhS /home/apps/*.sql /home/apps/*.sql.gz /home/apps/*.dump 2>/dev/null || echo no dump files"]'
```

空間不足時，確認後刪除舊的 dump 檔案：

```bash
# 列出舊檔讓用戶確認後再刪除
rm -f /home/apps/{app_name}_YYYYMMDD.sql  # 逐一刪除確認過的舊檔
```

### A5. 執行 pg_dump

**情境一：Staging 直連 Production RDS（推薦）**

```bash
# 在 Staging EC2 上直接 dump Production RDS
PGPASSWORD={prod_password} pg_dump \
  -h {prod_rds_host} -U {prod_user} -d {db_name} \
  --no-owner --no-acl \
  -f /home/apps/{app_name}_YYYYMMDD.sql
```

**情境二：需要傳輸（Staging 無法直連 Production RDS）**

```bash
# Step 1: 在 Production EC2 上 dump
PGPASSWORD={prod_password} pg_dump \
  -h {prod_rds_host} -U {prod_user} -d {db_name} \
  --no-owner --no-acl \
  -f /home/apps/{app_name}_YYYYMMDD.sql

# Step 2: 壓縮 + 上傳 S3
gzip -c /home/apps/{app_name}_YYYYMMDD.sql > /home/apps/{app_name}_YYYYMMDD.sql.gz
aws s3 cp /home/apps/{app_name}_YYYYMMDD.sql.gz s3://{bucket}/db-backup/

# Step 3: Staging 下載 + 解壓
aws s3 cp s3://{bucket}/db-backup/{app_name}_YYYYMMDD.sql.gz /home/apps/
gunzip -f /home/apps/{app_name}_YYYYMMDD.sql.gz
```

> **注意**：如果 Staging EC2 沒有 S3 權限（403 Forbidden），需要先設定 IAM Role 或改用 scp。

### A6. Drop + Recreate + Restore

**重要：這會清掉 Staging 現有資料，執行前必須確認用戶同意。**

SSM 的多層引號 escape 容易出錯，複雜命令建議用 **JSON 檔 + printf 寫腳本** 的方式：

```bash
# 在本地建立 SSM 參數檔
cat > /tmp/ssm-restore-commands.json << 'EOF'
{
  "commands": [
    "printf '#!/bin/bash\\nexport PGPASSWORD={staging_password}\\nexport PGHOST={staging_rds_host}\\nexport PGUSER={staging_user}\\npsql -d postgres -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '\"'\"'{db_name}'\"'\"' AND pid <> pg_backend_pid();\"\\npsql -d postgres -c \"DROP DATABASE IF EXISTS {db_name};\"\\npsql -d postgres -c \"CREATE DATABASE {db_name};\"\\npsql -d {db_name} < /home/apps/{app_name}_YYYYMMDD.sql\\npsql -d {db_name} -c \"SELECT count(*) as table_count FROM information_schema.tables WHERE table_schema = '\"'\"'public'\"'\"' AND table_type = '\"'\"'BASE TABLE'\"'\"';\"\\n' > /tmp/db_restore.sh",
    "chmod +x /tmp/db_restore.sh",
    "sudo su - apps -c 'bash /tmp/db_restore.sh 2>&1'"
  ]
}
EOF

# 透過 JSON 檔傳參數給 SSM
COMMAND_ID=$(aws ssm send-command \
  --instance-ids "$STAGING_INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters file:///tmp/ssm-restore-commands.json \
  --timeout-seconds 600 \
  --output text \
  --query "Command.CommandId")
```

腳本執行的步驟：
1. `pg_terminate_backend` — 斷開所有連到目標 DB 的 session
2. `DROP DATABASE IF EXISTS` — 刪除舊 DB
3. `CREATE DATABASE` — 建立空 DB
4. `psql < dump.sql` — 匯入資料
5. 查詢 `table_count` — 驗證結果

### A7. 驗證（使用 real count(*)，不要依賴 pg_stat）

```bash
# 檢查 stderr 是否有錯誤
aws ssm get-command-invocation \
  --command-id "$COMMAND_ID" \
  --instance-id "$STAGING_INSTANCE_ID" \
  --query "[Status, StandardErrorContent]" --output text

# 用 real count(*) 對比 prod / staging 的幾個代表性 table
# （勿用 pg_stat_user_tables.n_live_tup — 統計常失準，production 尤其常見）
for t in {large_table_1} {large_table_2} {medium_table}; do
  P=$(PGPASSWORD={prod_pw} psql -h {prod_rds} -U {prod_user} -d {db} -tAc "SELECT count(*) FROM $t;")
  S=$(PGPASSWORD={stg_pw} psql -h {stg_rds} -U {stg_user} -d {db} -tAc "SELECT count(*) FROM $t;")
  printf "%-50s prod=%s staging=%s\n" "$t" "$P" "$S"
done
```

**為什麼不用 `pg_stat_user_tables`**
- `n_live_tup` 是統計值，需要 ANALYZE 才更新
- Production 經常看到 stale 統計（tens of thousands 的 table 顯示只有幾十筆）
- 剛 restore 的 staging stats 是「新的」，拿它跟 production 的舊 stats 比會看到誤差
- 資料正確與否，只有 `SELECT count(*)` 說了算

### A8. 清理暫存

```bash
# 清理 Production 上的暫存（如果有）
rm -f /home/apps/{app_name}_YYYYMMDD.sql.gz

# 清理 S3 上的暫存（如果有）
aws s3 rm s3://{bucket}/db-backup/{app_name}_YYYYMMDD.sql.gz

# Staging 上的 dump 檔可保留作為回滾用，或清理
# rm -f /tmp/db_restore.sh
```

---

## Path B：選擇性遷移（Production → Local/Staging）

適用場景：只需要特定 table 或特定時間範圍的資料，用於除錯或分析。

### B1. 識別敏感欄位（若需要清理）

自動偵測以下類型的敏感欄位：

| 類型 | 欄位名稱模式 | 處理方式 |
|------|-------------|---------|
| Email | `*email*`, `*mail*` | 替換為 `xxx@example.com` |
| 電話 | `*phone*`, `*tel*`, `*mobile*` | 替換為 `0900-000-000` |
| 地址 | `*address*` | 替換為 `測試地址` |
| 密碼 | `*password*`, `*passwd*` | 清空或替換為固定 hash |
| Token | `*token*`, `*secret*`, `*key*` | 清空 |
| 身分證 | `*id_number*`, `*identity*` | 替換為 `A000000000` |
| 銀行帳號 | `*bank*`, `*account*` | 替換為 `000-0000000` |

> **Production → Staging（同 VPC）** 且用戶確認不需要清理時，可跳過此步驟。

### B2. 匯出資料

**方法 A：使用 pg_dump（單表或多表）**

```bash
# 單表匯出
PGPASSWORD={password} pg_dump -h {rds_host} -U {user} -d {db_name} \
  -t {table_name} --data-only \
  -f /tmp/{table_name}.sql

# 多表匯出
PGPASSWORD={password} pg_dump -h {rds_host} -U {user} -d {db_name} \
  -t table1 -t table2 -t table3 --data-only \
  -f /tmp/selected_tables.sql
```

**方法 B：使用 Rails Runner（需要條件過濾時）**

```ruby
# /tmp/export_data.rb
require 'csv'

records = Invoice.where(created_at: 30.days.ago..Time.current).limit(1000)

CSV.open('/tmp/export.csv', 'w') do |csv|
  csv << records.first.attributes.keys
  records.each { |r| csv << r.attributes.values }
end

puts "Exported #{records.count} records"
```

### B3. 下載到本地（如果目標是 Local）

```bash
# 透過 SSM cat 取得小型檔案
COMMAND_ID=$(aws ssm send-command \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["cat /tmp/export.csv"]' \
  --output text --query "Command.CommandId")

aws ssm get-command-invocation \
  --command-id "$COMMAND_ID" \
  --instance-id "$INSTANCE_ID" \
  --query "StandardOutputContent" \
  --output text > /tmp/downloaded_data.csv
```

### B4. 清理敏感資料（本地處理，若需要）

```ruby
require 'csv'

data = CSV.read('/tmp/downloaded_data.csv', headers: true)

data.each do |row|
  row['email'] = "test_#{row['id']}@example.com" if row['email']
  row['phone'] = '0900-000-000' if row['phone']
  row['address'] = '測試地址' if row['address']
  row['password_digest'] = nil if row['password_digest']
  row['token'] = nil if row['token']
end

CSV.open('/tmp/sanitized_data.csv', 'w') do |csv|
  csv << data.headers
  data.each { |row| csv << row.values_at(*data.headers) }
end
```

### B5. 匯入

```bash
# SQL 匯入
psql -d {db_name} < /tmp/selected_tables.sql

# 或 CSV 匯入
psql -d {db_name} -c "COPY {table} FROM '/tmp/sanitized_data.csv' CSV HEADER"
```

### B6. 驗證 + 清理

```bash
# 驗證
psql -d {db_name} -c "SELECT count(*) FROM {table};"

# 清理遠端暫存
rm -f /tmp/export_data.rb /tmp/export.csv /tmp/*.sql
```

---

## Path C：部分重置（保留指定 table 的資料）

適用場景：Staging 要刷新 Production 最新資料，**但某些 table 的 staging 測試資料要保留**（例如 `admin_staffs`、`users` 只存測試帳號的情境）。

**優點**：不需要 RDS master 權限（不做 DROP DATABASE），app user 即可完成整個流程。

### C1. 備份要保留的 table（data-only）

```bash
# 在 Staging EC2 上用 pg_dump 備份要保留的 table
PGPASSWORD={stg_password} pg_dump \
  -h {stg_rds_host} -U {stg_user} -d {db_name} \
  -t {keep_table} --data-only --no-owner --no-acl \
  -f /home/apps/{keep_table}_backup_YYYYMMDD.sql

# 驗證備份筆數
PGPASSWORD={stg_password} psql -h {stg_rds_host} -U {stg_user} -d {db_name} \
  -c "SELECT count(*) FROM {keep_table};"
```

> 💡 多個 table 可重複 `-t table1 -t table2` 一起備份。

### C2. pg_dump production（--clean --if-exists + 排除要保留 table 的資料）

```bash
PGPASSWORD={prod_password} pg_dump \
  -h {prod_rds_host} -U {prod_user} -d {db_name} \
  --no-owner --no-acl \
  --clean --if-exists \
  --exclude-table-data={keep_table} \
  -f /home/apps/{app_name}_prod_YYYYMMDD.sql
```

**三個關鍵 flag**：
- `--clean --if-exists` → dump 內含 `DROP TABLE IF EXISTS`，restore 時自動清掉舊 table（不需 DROP DATABASE 權限）
- `--exclude-table-data={keep_table}` → 保留 schema 但清空資料，restore 後是空表等待 C4 灌入
- `--no-owner --no-acl` → 跨 user restore 時避免 owner / grant 衝突

### C3. Restore dump 到 staging（不需 DROP DATABASE）

```bash
export PGPASSWORD={stg_password}
export PGHOST={stg_rds_host}
export PGUSER={stg_user}

# 先斷掉既有連線（app user 可以終止自己的 session，如 Rails app）
psql -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='{db_name}' AND pid <> pg_backend_pid();"

# Restore（--clean 會自動 DROP 再 CREATE 每個 table）
psql -d {db_name} -v ON_ERROR_STOP=0 -f /home/apps/{app_name}_prod_YYYYMMDD.sql \
  > /tmp/restore.stdout 2> /tmp/restore.stderr

# 檢查錯誤數（0 最理想；extension-related 錯誤通常可忽略，但要人工 review）
wc -l /tmp/restore.stderr
head -30 /tmp/restore.stderr
```

### C4. 灌回保留的 table 資料

```bash
psql -d {db_name} -v ON_ERROR_STOP=1 -f /home/apps/{keep_table}_backup_YYYYMMDD.sql

# 驗證
psql -d {db_name} -c "SELECT count(*) FROM {keep_table};"
```

### C5. 驗證（real count(*)，參照 A7）

比對幾個代表性 table 的 `count(*)`，確認 `{keep_table}` 的筆數等於備份時的筆數，其他 table 等於 production。

### C6. 清理

```bash
rm -f /home/apps/{app_name}_prod_YYYYMMDD.sql
rm -f /home/apps/{keep_table}_backup_YYYYMMDD.sql
# /tmp/*.sh 暫存會被 tmpreaper 清掉，不用手動處理
```

---

## SSM 實用技巧

### 避免引號地獄

SSM `send-command` 的多層引號 escape 非常容易出錯。推薦做法：

**方法一：JSON 檔案傳參數（推薦）**

```bash
# 本地建立 JSON 參數檔
cat > /tmp/ssm-commands.json << 'EOF'
{
  "commands": [
    "printf '#!/bin/bash\\n...' > /tmp/script.sh",
    "chmod +x /tmp/script.sh",
    "sudo su - apps -c 'bash /tmp/script.sh 2>&1'"
  ]
}
EOF

aws ssm send-command --instance-ids "$ID" \
  --document-name "AWS-RunShellScript" \
  --parameters file:///tmp/ssm-commands.json
```

**方法二：簡單命令可直接用 parameters**

```bash
aws ssm send-command --instance-ids "$ID" \
  --document-name "AWS-RunShellScript" \
  --parameters 'commands=["ls -la /home/apps/"]'
```

**方法三（推薦，複雜腳本）：base64 encode 把整個 bash 腳本灌進 SSM**

避開所有 quote / escape 地獄：本地把 shell script 寫好、base64 編碼、SSM 在遠端 decode 回檔案後執行。

```bash
# 1. 本地寫好腳本（想怎麼用 quote 都行，不用 escape）
cat > /tmp/remote.sh << 'EOF'
#!/bin/bash
set -e
echo "hello from $(hostname)"
PGPASSWORD=xxx psql -h rds-host -U user -d db -c "SELECT count(*) FROM tablename;"
EOF

# 2. Base64 編碼
B64=$(base64 < /tmp/remote.sh | tr -d '\n')

# 3. SSM 透過 JSON 檔傳 3 行命令：decode → chmod → 用指定 user 執行
cat > /tmp/ssm.json << EOF
{
  "commands": [
    "echo '$B64' | base64 -d > /tmp/s.sh && chmod +x /tmp/s.sh",
    "sudo -u apps bash /tmp/s.sh 2>&1"
  ]
}
EOF

aws ssm send-command --instance-ids "$ID" \
  --document-name "AWS-RunShellScript" \
  --parameters file:///tmp/ssm.json \
  --timeout-seconds 600
```

**優點**：
- 腳本內想怎麼 `'"'` / `EOF` 都不會壞
- 本地先 `bash /tmp/remote.sh` dry-run 更直覺
- 長腳本（幾 KB）也塞得進 SSM parameters

### 等待 SSM 命令完成

```bash
# 送出命令後取得 CommandId
COMMAND_ID=$(aws ssm send-command ... --output text --query "Command.CommandId")

# 等待並取得結果（根據預期時間調整 sleep）
sleep {seconds} && aws ssm get-command-invocation \
  --command-id "$COMMAND_ID" \
  --instance-id "$INSTANCE_ID" \
  --query "[Status, StandardOutputContent, StandardErrorContent]" \
  --output text

# 如果 Status 是 InProgress，再等一下重試
```

---

## Safety Guidelines

### 絕對禁止

```
❌ 將 Local/Staging 資料推到 Production
❌ 直接在 Production 執行 UPDATE/DELETE
❌ 遷移超過必要範圍的資料（selective 模式）
```

### 必須執行

```
✅ 遷移前確認需求和範圍
✅ 遷移前檢查磁碟空間
✅ 全庫同步前確認用戶同意覆蓋目標 DB
✅ 遷移後驗證資料完整性
✅ 清理遠端暫存檔案
```

### 敏感資料處理原則

```
Production → Local     # 建議清理敏感資料
Production → Staging   # 同 VPC 內可選擇保留，由用戶決定
```

## Common Patterns

### 全庫同步到 Staging（最常見）

```
1. 確認 staging 能直連 production RDS
2. 檢查磁碟空間，清理舊 dump
3. 在 staging 上 pg_dump production RDS
4. terminate connections → drop → create → restore
5. 驗證 table count
```

### 遷移特定專案的資料

```ruby
project = Project.find_by(serial: 'RT130044')
export_data = {
  project: project.attributes,
  invoices: project.invoices.map(&:attributes),
  payments: project.payments.map(&:attributes)
}
File.write('/tmp/project_data.json', export_data.to_json)
```

### 只遷移結構（不含資料）

```bash
pg_dump -h {rds_host} -U {user} -d {db_name} --schema-only -f /tmp/schema.sql
```

## Output Format

遷移完成後輸出：

```markdown
┌──────────────────────────────────────────────────────┐
│ 📦 資料遷移完成                                       │
├──────────────────────────────────────────────────────┤
│ 來源：Production RDS ({prod_rds_host})               │
│ 目標：Staging RDS ({staging_rds_host})               │
│ 資料庫：{db_name}                                     │
│                                                      │
│ 📊 遷移統計：                                        │
│   • 資料表數：{table_count} 張                        │
│   • Dump 大小：{size}                                │
│                                                      │
│ ✅ 無錯誤 / ⚠️ 有警告（列出）                        │
│ ✅ 目標 DB 已完整覆蓋                                │
└──────────────────────────────────────────────────────┘
```
