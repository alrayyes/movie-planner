#!/usr/bin/env bash
# lint-mechanics.sh checks the whole tree when run bare (CI), and only the
# Markdown it is given when the pre-push hook passes the pushed files, so a push
# that changed one document doesn't start a JVM over all of them. A fake
# ltex-cli-plus on PATH records what it was handed, and HOME and XDG_CACHE_HOME
# point at a temp dir so the real ltex cache is never touched. The hook's glob
# is checked statically.
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

failed=0
fail() {
  echo "FAIL: $1"
  failed=1
}

export HOME="$tmp/home" XDG_CACHE_HOME="$tmp/home/.cache"
mkdir -p "$HOME" "$tmp/bin" "$tmp/repo/scripts"
cp "${SCRIPT:-$root/scripts/lint-mechanics.sh}" "$tmp/repo/scripts/lint-mechanics.sh"
cat >"$tmp/bin/ltex-cli-plus" <<FAKE
#!/usr/bin/env bash
printf '%s\n' "\$@" | grep -v '^--' >"$tmp/seen"
FAKE
chmod +x "$tmp/bin/ltex-cli-plus"

cd "$tmp/repo"
git init -q
echo '{}' >.ltex.json
for f in README.md docs.md CHANGELOG.md openspec/changes/x.md openspec/specs/y.md .claude/z.md; do
  mkdir -p "$(dirname "$f")"
  echo hi >"$f"
done
echo hi >docs.md.bak
git add -A

# run [args…]: what the fake ltex saw, space-joined and sorted.
run() {
  rm -f "$tmp/seen"
  PATH="$tmp/bin:$PATH" scripts/lint-mechanics.sh "$@" >/dev/null 2>&1
  echo "$?" >"$tmp/status"
  if [ -f "$tmp/seen" ]; then LC_ALL=C sort "$tmp/seen" | tr '\n' ' '; else echo none; fi
}

[ "$(run)" = "README.md docs.md " ] || fail "bare run is not the whole tree minus exclusions: $(run)"
[ "$(run docs.md)" = "docs.md " ] || fail "a pushed file is not the only one checked: $(run docs.md)"
[ "$(run docs.md src/main.go)" = "docs.md " ] || fail "a non-Markdown file reached ltex: $(run docs.md src/main.go)"
[ "$(run CHANGELOG.md openspec/changes/x.md openspec/specs/y.md .claude/z.md)" = "none" ] || fail "excluded files were checked"
[ "$(run README.md docs.md)" = "README.md docs.md " ] || fail "only the first of two pushed files was checked: $(run README.md docs.md)"
[ "$(run docs.md.bak)" = "none" ] || fail "a file that merely contains a Markdown name was checked"
run CHANGELOG.md >/dev/null
[ "$(cat "$tmp/status")" = 0 ] || fail "a push with no prose must exit 0"
[ "$(run README.md .ltex.json)" = "README.md docs.md " ] || fail "a push with Markdown and .ltex.json did not check the whole tree: $(run README.md .ltex.json)"
[ "$(run docs.md scripts/lint-mechanics.sh)" = "README.md docs.md " ] || fail "a push with Markdown and the script did not check the whole tree"
[ "$(run .ltex.json)" = "README.md docs.md " ] || fail "a config-only push did not check the whole tree: $(run .ltex.json)"
[ "$(run scripts/lint-mechanics.sh)" = "README.md docs.md " ] || fail "a script-only push did not check the whole tree"

# With no ltex and no docker anywhere, a push with no prose must exit before
# the lookup: no download, no cache directory.
mkdir -p "$tmp/nobin"
for t in git grep dirname find head; do ln -s "$(command -v "$t")" "$tmp/nobin/$t"; done
printf '#!/bin/sh\ntouch "%s/curl-called"\n' "$tmp" >"$tmp/nobin/curl"
chmod +x "$tmp/nobin/curl"
PATH="$tmp/nobin" "$(command -v bash)" scripts/lint-mechanics.sh CHANGELOG.md >/dev/null 2>&1 ||
  fail "a no-prose push failed on a machine with no ltex"
[ ! -e "$tmp/curl-called" ] || fail "a no-prose push downloaded ltex"
[ ! -e "$XDG_CACHE_HOME/ltex-ls-plus" ] || fail "a no-prose push created the ltex cache"

cd "$root"
job=$(awk '/^    - name: mechanics$/{p=1;print;next} /^    - name:/{p=0} p' lefthook.yml)
grep -q 'glob:' <<<"$job" || fail "the mechanics hook has no glob, so every push starts a JVM"
grep -Fq '{push_files}' <<<"$job" || fail "the mechanics hook does not pass the pushed files"
grep -Fq '.ltex.json' <<<"$job" || fail "the mechanics hook ignores a change to .ltex.json"
grep -Fq 'lint-mechanics.sh' <<<"$job" || fail "the mechanics hook does not run lint-mechanics.sh"

exit "$failed"
