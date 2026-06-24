#!/bin/bash
set -e

# 拉取两边最新提交
git fetch origin
git fetch gitcode

# 依次合并（若出现冲突需手动解决）
git merge origin/main --no-edit
git merge gitcode/main --no-edit

# 推送到两边
git push origin main
git push gitcode main

echo "已同步推送到 origin (GitHub) 和 gitcode。"
