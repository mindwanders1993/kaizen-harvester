#!/usr/bin/env bash
# PreToolUse(Bash) guard for the HARD RULE in .agents/AGENTS.md:
#
#   The dev -> main release merge is performed by the user, in the GitHub web UI, only.
#
# Exit 2 blocks the tool call and returns stderr to Claude as feedback.
# Everything else exits 0 and the call proceeds.

set -uo pipefail

CMD=$(cat | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null) || exit 0
[ -z "$CMD" ] && exit 0

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")

block() {
  echo "BLOCKED by .claude/hooks/block-main-merge.sh" >&2
  echo "" >&2
  echo "$1" >&2
  echo "" >&2
  echo "The dev -> main release merge is done by the user in the GitHub web UI only." >&2
  echo "See the HARD RULE in .agents/AGENTS.md. Do not work around this." >&2
  exit 2
}

# 1. Any git merge while sitting on main.
if [ "$BRANCH" = "main" ] && echo "$CMD" | grep -qE '(^|[;&|]|&&)[[:space:]]*git[[:space:]]+merge'; then
  block "Refusing 'git merge' while on branch main."
fi

# 2. Pushing anything onto main via a refspec (git push origin dev:main).
if echo "$CMD" | grep -qE 'git[[:space:]]+push.*:[[:space:]]*(refs/heads/)?main([[:space:]]|$)'; then
  block "Refusing a git push whose refspec targets main."
fi

# 3. Fast-forwarding main from another branch.
if echo "$CMD" | grep -qE 'git[[:space:]]+(merge|rebase)[[:space:]]+.*[[:space:]]main([[:space:]]|$)' \
   && [ "$BRANCH" = "main" ]; then
  block "Refusing to merge or rebase into main."
fi

# 4. gh pr merge on a PR whose base is main. Feature PRs into dev are fine.
if echo "$CMD" | grep -qE 'gh[[:space:]]+pr[[:space:]]+merge'; then
  PR=$(echo "$CMD" | grep -oE 'gh[[:space:]]+pr[[:space:]]+merge[[:space:]]+[0-9]+' | grep -oE '[0-9]+$' || true)
  BASE=$(gh pr view ${PR:-} --json baseRefName -q .baseRefName 2>/dev/null || echo "")
  if [ "$BASE" = "main" ]; then
    block "Refusing 'gh pr merge' on PR #${PR:-<current>}, whose base is main."
  fi
fi

exit 0
