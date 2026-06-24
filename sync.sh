#!/bin/bash
set -e

# 检查工作区是否干净
if ! git diff --quiet; then
  echo "错误：工作区有未提交的改动，请先提交或 stash。"
  git status --short
  exit 1
fi

# 检查 remote 是否存在
for remote in origin gitcode; do
  if ! git remote get-url "$remote" >/dev/null 2>&1; then
    echo "错误：remote '$remote' 未配置。"
    exit 1
  fi
done

# 拉取两边最新提交
git fetch origin
git fetch gitcode || echo "警告：gitcode fetch 失败，继续..."

# 依次合并（若出现冲突需手动解决）
git merge origin/main --no-edit || {
  echo "合并 origin/main 失败，请手动解决冲突后执行 git merge --abort 或 git commit"
  exit 1
}
git merge gitcode/main --no-edit || {
  echo "合并 gitcode/main 失败，请手动解决冲突后执行 git merge --abort 或 git commit"
  exit 1
}

# 推送到两边
ORIGIN_SHA=$(git rev-parse HEAD)
git push origin main || echo "警告：推送 origin 失败"
git push gitcode main || {
  echo "警告：推送 gitcode 失败，origin 已推送至 $ORIGIN_SHA，请手动补推 gitcode"
  exit 1
}

echo "已同步推送到 origin (GitHub) 和 gitcode。"
