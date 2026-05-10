#!/usr/bin/env bash
# Pull latest main and restart only the affected show components.
#
# Usage:
#   scripts/update-and-restart.sh
#   scripts/update-and-restart.sh --dry-run
#   scripts/update-and-restart.sh --force-x
#
# Exit codes:
#   0 success (or no update)
#   1 usage/runtime error
#
# Notes:
# - Requires a clean git worktree.
# - Uses /home/dob/bin/ii restart commands when available.

set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

dry_run=0
force_x=0
branch="main"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            dry_run=1
            ;;
        --force-x)
            force_x=1
            ;;
        --branch)
            shift
            if [[ $# -eq 0 ]]; then
                echo "[update] ERROR: --branch requires a value" >&2
                exit 1
            fi
            branch="$1"
            ;;
        -h|--help)
            sed -n '1,80p' "$0"
            exit 0
            ;;
        *)
            echo "[update] ERROR: unknown option: $1" >&2
            exit 1
            ;;
    esac
    shift
done

if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "[update] ERROR: worktree is not clean. Commit or stash first." >&2
    exit 1
fi

if [[ -d .git/rebase-merge || -d .git/rebase-apply || -f .git/MERGE_HEAD ]]; then
    echo "[update] ERROR: merge/rebase in progress." >&2
    exit 1
fi

old_head="$(git rev-parse HEAD)"

echo "[update] fetching origin/$branch..."
git fetch origin "$branch"
new_remote="$(git rev-parse "origin/$branch")"

if [[ "$old_head" == "$new_remote" ]]; then
    echo "[update] already up to date ($old_head)"
    exit 0
fi

echo "[update] updating to $new_remote"
git pull --ff-only origin "$branch"

new_head="$(git rev-parse HEAD)"

mapfile -t changed_files < <(git diff --name-only "$old_head" "$new_head")

if [[ ${#changed_files[@]} -eq 0 ]]; then
    echo "[update] no changed files detected in range"
    exit 0
fi

echo "[update] changed files:"
printf '  - %s\n' "${changed_files[@]}"

need_vis=0
need_ctrl=0
need_web=0
need_x=0

for f in "${changed_files[@]}"; do
    case "$f" in
        visuals.py|architecture.py|audio.py|output.py|fb_mapper.py|config.json|modes/*)
            need_vis=1
            ;;
    esac

    case "$f" in
        _ii.py|nodes.py|node_lib.py|cues.py|midi.py|osc_server.py|map_engine.py|config.json)
            need_ctrl=1
            ;;
    esac

    case "$f" in
        map_server.py|README.md|ii-web.service|scripts/start-x.sh|scripts/kwin-place-visuals.js)
            need_web=1
            ;;
    esac

    case "$f" in
        window.py|run.sh|ii-boot.service|ii-ctrl.service|ii-visuals.service|ii-web.service|install-services.sh|scripts/start-x.sh)
            need_x=1
            ;;
    esac
done

if [[ "$force_x" -eq 1 ]]; then
    need_x=1
fi

ii_helper="/home/dob/bin/ii"

restart_component() {
    local target="$1"
    if [[ "$dry_run" -eq 1 ]]; then
        echo "[update] dry-run: would run: $ii_helper restart $target"
        return 0
    fi
    if [[ -x "$ii_helper" ]]; then
        echo "[update] restarting $target"
        "$ii_helper" restart "$target"
        return 0
    fi

    echo "[update] WARN: ii helper missing, trying systemctl fallback for $target"
    case "$target" in
        vis)
            systemctl restart ii-visuals
            ;;
        ctrl)
            systemctl restart ii-ctrl
            ;;
        web)
            systemctl restart ii-web
            ;;
        x)
            echo "[update] WARN: no fallback for x restart without ii helper"
            return 1
            ;;
        *)
            echo "[update] ERROR: unknown restart target: $target" >&2
            return 1
            ;;
    esac
}

if [[ "$need_x" -eq 1 ]]; then
    restart_component x
else
    if [[ "$need_vis" -eq 1 ]]; then
        restart_component vis
    fi
    if [[ "$need_ctrl" -eq 1 ]]; then
        restart_component ctrl
    fi
    if [[ "$need_web" -eq 1 ]]; then
        restart_component web
    fi
fi

echo "[update] done: $old_head -> $new_head"
