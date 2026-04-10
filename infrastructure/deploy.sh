#!/bin/bash
# 部署 atdd-task 到遠端 EC2 Server（via AWS SSM）
#
# Usage:
#   ./infrastructure/deploy.sh          # 部署 master 分支
#   ./infrastructure/deploy.sh develop   # 部署指定分支

set -euo pipefail

# === 設定 ===
INSTANCE_ID="i-0ea3db0e802d2a4de"
APP_DIR="/home/ubuntu/atdd-task"
REMOTE_USER="ubuntu"
BRANCH="${1:-master}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# === Helper ===
info()  { echo "  $1"; }
error() { echo "  $1" >&2; }
step()  { echo ""; echo "==> $1"; }

ssm_run() {
  local cmd="$1"
  local wait="${2:-10}"

  local command_id
  command_id=$(aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --document-name "AWS-RunShellScript" \
    --parameters "commands=[\"sudo -u $REMOTE_USER bash -c \\\"$cmd\\\"\"]" \
    --output text \
    --query "Command.CommandId" 2>&1)

  if [ $? -ne 0 ]; then
    error "SSM send-command failed: $command_id"
    return 1
  fi

  sleep "$wait"

  local result
  result=$(aws ssm get-command-invocation \
    --command-id "$command_id" \
    --instance-id "$INSTANCE_ID" \
    --output json 2>&1)

  if [ $? -ne 0 ]; then
    error "SSM get-command-invocation failed: $result"
    return 1
  fi

  local status
  status=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin)['Status'])")

  local stdout
  stdout=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin)['StandardOutputContent'])")

  local stderr
  stderr=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin)['StandardErrorContent'])")

  if [ "$status" = "InProgress" ]; then
    info "Still running, waiting..."
    sleep "$wait"
    result=$(aws ssm get-command-invocation \
      --command-id "$command_id" \
      --instance-id "$INSTANCE_ID" \
      --output json)
    status=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin)['Status'])")
    stdout=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin)['StandardOutputContent'])")
    stderr=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin)['StandardErrorContent'])")
  fi

  if [ "$status" != "Success" ]; then
    error "Command failed (status: $status)"
    [ -n "$stdout" ] && echo "$stdout"
    [ -n "$stderr" ] && echo "$stderr" >&2
    return 1
  fi

  [ -n "$stdout" ] && echo "$stdout"
  return 0
}

# === Prerequisites ===
step "Checking prerequisites..."

# 1. AWS CLI
if ! command -v aws &>/dev/null; then
  error "AWS CLI is not installed."
  echo ""
  info "Install:"
  info "  brew install awscli"
  echo ""
  info "Then configure:"
  info "  aws configure"
  exit 1
fi
info "AWS CLI: OK"

# 2. AWS credentials
if ! aws sts get-caller-identity &>/dev/null; then
  error "AWS credentials not configured or expired."
  echo ""
  info "Run:"
  info "  aws configure"
  echo ""
  info "You need:"
  info "  - AWS Access Key ID"
  info "  - AWS Secret Access Key"
  info "  - Default region: ap-northeast-1"
  exit 1
fi
info "AWS credentials: OK"

# 3. SSM connectivity
ping_status=$(aws ssm describe-instance-information \
  --filters "Key=InstanceIds,Values=$INSTANCE_ID" \
  --query "InstanceInformationList[0].PingStatus" \
  --output text 2>/dev/null || echo "None")

if [ "$ping_status" != "Online" ]; then
  error "Cannot reach instance $INSTANCE_ID (status: $ping_status)"
  echo ""
  info "Possible causes:"
  info "  - EC2 instance is stopped"
  info "  - SSM Agent is not running"
  info "  - Your IAM user lacks SSM permissions"
  info ""
  info "Contact the administrator."
  exit 1
fi
info "SSM connectivity: OK"

# === Step 1: Check local git status ===
step "Checking local git status..."

cd "$PROJECT_DIR"

unpushed=$(git log "origin/$BRANCH..$BRANCH" --oneline 2>/dev/null || true)
if [ -n "$unpushed" ]; then
  echo ""
  info "Unpushed commits on $BRANCH:"
  echo "$unpushed" | sed 's/^/    /'
  echo ""
  read -p "  Push before deploying? [Y/n] " answer
  answer="${answer:-Y}"
  if [[ "$answer" =~ ^[Yy] ]]; then
    git push origin "$BRANCH"
    info "Pushed."
  else
    error "Aborted. Server pulls from GitHub, so you need to push first."
    exit 1
  fi
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  info "Note: you have uncommitted local changes (won't be deployed)"
fi

# === Step 2: Git Pull ===
step "Pulling $BRANCH on server..."

pull_output=$(ssm_run "cd $APP_DIR && git pull origin $BRANCH 2>&1" 5)
echo "$pull_output" | head -5

# === Step 3: Docker Compose Rebuild ===
step "Rebuilding containers..."

build_output=$(ssm_run "cd $APP_DIR/infrastructure && docker compose up -d --build api worker 2>&1" 15)

# Restart nginx to pick up new container DNS (api container gets a new IP after rebuild)
step "Restarting nginx..."

ssm_run "cd $APP_DIR/infrastructure && docker compose restart nginx 2>&1" 5 >/dev/null

# === Step 4: Health Check ===
step "Health check..."

health_output=$(ssm_run "cd $APP_DIR/infrastructure && docker compose ps --format 'table {{.Name}}\t{{.Status}}' 2>&1" 3)
echo "$health_output"

# === Done ===
echo ""
echo "=============================="
echo "  Deploy complete!"
echo "  Branch: $BRANCH"
echo "  https://atdd.sunnyfounder.com"
echo "=============================="
