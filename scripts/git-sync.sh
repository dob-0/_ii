#!/usr/bin/env bash
# Commit and push all repository changes, then print the final git state.
#
# Usage:
#   scripts/git-sync.sh "update readme"
#   scripts/git-sync.sh

set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

branch="$(git branch --show-current)"
if [ -z "$branch" ]; then
    echo "[git-sync] ERROR: detached HEAD; switch to a branch before syncing." >&2
    exit 1
fi

if [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ] || [ -f .git/MERGE_HEAD ]; then
    echo "[git-sync] ERROR: merge/rebase in progress; finish it before syncing." >&2
    exit 1
fi

msg="${1:-}"
if [ -z "$msg" ]; then
    msg="sync: $(date '+%Y-%m-%d %H:%M')"
fi

echo "[git-sync] branch: $branch"
echo "[git-sync] staging all repo changes..."
git add -A

if git diff --cached --quiet; then
    echo "[git-sync] no changes to commit."
else
    git commit -m "$msg"
fi

if git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' >/dev/null 2>&1; then
    echo "[git-sync] pushing to upstream..."
    git push
else
    echo "[git-sync] setting upstream and pushing to origin/$branch..."
    git push -u origin "$branch"
fi

echo "[git-sync] latest commit:"
git log -1 --oneline

echo "[git-sync] final status:"
git status --short --branch
