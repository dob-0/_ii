# Repository Instructions

This repo is `_ii`. The live controller entrypoint is `_ii.py`.

When making intentional code or documentation changes:

1. Check the working tree before editing with `git status --short --branch`.
2. Keep edits scoped to the requested change.
3. Run the relevant lightweight validation, such as `git diff --check`, `bash -n`
   for shell scripts, or Python syntax checks for changed Python files.
4. Commit and push the finished change with:

   ```bash
   scripts/git-sync.sh "short commit message"
   ```

5. Confirm the final state is aligned with `origin/main`.

Do not commit runtime state files ignored by `.gitignore`, including
`control.json`, `status.json`, temp files, or Python caches.
