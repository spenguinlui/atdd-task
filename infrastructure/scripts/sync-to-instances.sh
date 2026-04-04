#!/bin/bash
# 同步框架更新到所有已註冊的實例
# 實例清單定義於 .instances（每行一個路徑，# 開頭為註解）
#
# Usage: ./scripts/sync-to-instances.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TASK_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"  # infrastructure/scripts/ → project root
INSTANCES_FILE="$TASK_DIR/.instances"

if [ ! -f "$INSTANCES_FILE" ]; then
  exit 0
fi

while IFS= read -r line; do
  # 跳過空行和註解
  line="$(echo "$line" | sed 's/#.*//' | xargs)"
  [ -z "$line" ] && continue

  # 展開 ~
  target="${line/#\~/$HOME}"

  if [ ! -d "$target" ]; then
    echo "⚠️  跳過（目錄不存在）: $line"
    continue
  fi

  echo "🔄 同步到: $line"

  # === .claude (排除實例本地設定) ===
  rsync -a --delete \
    --exclude='config/projects.yml' \
    --exclude='config/jira.yml' \
    --exclude='config/aws-instances.yml' \
    --exclude='.knowledge-confirmed' \
    --exclude='.investigation-confirmed' \
    --exclude='settings.local.json' \
    --exclude='.DS_Store' \
    "$TASK_DIR/.claude/" "$target/.claude/"

  # === 純框架目錄 ===
  rsync -a --delete "$TASK_DIR/style-guides/" "$target/style-guides/"
  rsync -a --delete "$TASK_DIR/knowledge/" "$target/knowledge/"
  rsync -a --delete "$TASK_DIR/debug-knowledge/" "$target/debug-knowledge/"

  # === Profiles（角色設定）===
  rsync -a --delete "$TASK_DIR/profiles/" "$target/profiles/"

  # === acceptance (保留實例的 fixtures) ===
  rsync -a --delete --exclude='fixtures/' \
    "$TASK_DIR/acceptance/" "$target/acceptance/"

  # === domains (僅 README + TEMPLATE) ===
  mkdir -p "$target/domains"
  cp "$TASK_DIR/domains/README.md" "$target/domains/" 2>/dev/null || true
  for f in "$TASK_DIR"/domains/TEMPLATE-*.md; do
    [ -f "$f" ] && cp "$f" "$target/domains/"
  done

  # === docs (僅框架文件) ===
  mkdir -p "$target/docs"
  for f in operation-manual.md fix-workflow.md confidence-mechanism.md \
           review-fix-workflow.md acceptance-profiles.md \
           feature-profiles.md fix-profiles.md; do
    [ -f "$TASK_DIR/docs/$f" ] && cp "$TASK_DIR/docs/$f" "$target/docs/"
  done

  # === 根目錄 ===
  cp "$TASK_DIR/CLAUDE.md" "$target/"
  cp "$TASK_DIR/README.md" "$target/"
  cp "$TASK_DIR/.env.example" "$target/"
  cp "$TASK_DIR/.gitignore" "$target/"

  # === 自動 commit（僅框架檔案） ===
  cd "$target"
  FRAMEWORK_PATHS=(
    .claude/
    profiles/
    acceptance/
    style-guides/
    knowledge/
    debug-knowledge/
    domains/README.md
    domains/TEMPLATE-*.md
    docs/operation-manual.md
    docs/fix-workflow.md
    docs/confidence-mechanism.md
    docs/review-fix-workflow.md
    docs/acceptance-profiles.md
    docs/feature-profiles.md
    docs/fix-profiles.md
    CLAUDE.md
    README.md
    .env.example
    .gitignore
  )
  git add -- "${FRAMEWORK_PATHS[@]}" 2>/dev/null || true
  if git diff --cached --quiet; then
    echo "  ⏭  無變更"
  else
    COMMIT_MSG="$(cd "$TASK_DIR" && git log -1 --format='%s')"
    git commit -m "$(cat <<EOF
sync: $COMMIT_MSG

Source: $(cd "$TASK_DIR" && git log -1 --format='%h')
EOF
)"
    echo "  ✅ 同步並 commit 完成"
  fi

done < "$INSTANCES_FILE"
