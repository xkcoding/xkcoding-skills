#!/usr/bin/env bash
# Keep the dispatch engine identical in every executor skill.
#
# dispatch/codex/scripts/ is the source; each other executor skill carries a byte-identical copy,
# because a skill directory must be self-contained and both entry commands supervise every lane.
#
#   dispatch/sync-engine.sh           copy the engine from codex into the other skills
#   dispatch/sync-engine.sh --check   exit 1 and list the files that differ (nothing is written)

set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_dir="$here/codex/scripts"
targets=("$here/omp/scripts")
files=(lane.py doctor.sh)

check=false
case "${1:-}" in
  "") ;;
  --check) check=true ;;
  *) echo "usage: $0 [--check]" >&2; exit 2 ;;
esac

differ=()
for target in "${targets[@]}"; do
  for f in "${files[@]}"; do
    if $check; then
      cmp -s "$source_dir/$f" "$target/$f" || differ+=("${target#"$here"/}/$f")
    else
      mkdir -p "$target"
      cp -p "$source_dir/$f" "$target/$f"
    fi
  done
done

if $check; then
  if ((${#differ[@]})); then
    echo "engine copies differ from dispatch/codex/scripts:" >&2
    printf '  %s\n' "${differ[@]}" >&2
    echo "edit dispatch/codex/scripts, then run dispatch/sync-engine.sh" >&2
    exit 1
  fi
  echo "engine copies are identical"
else
  echo "engine copied to: ${targets[*]#"$here"/}"
fi
