#!/usr/bin/env bash
# dispatch plugin environment diagnostic script
# Outputs a JSON report of the tools and environment a dispatch depends on.
#
# Read-only: never installs, logs in, or initializes anything.
# Tools are detected by RUNNING their version command, never by `command -v`:
# a shim can resolve on PATH while the real tool does not run.
# Uses bash builtins only, so it still reports correctly on a minimal PATH.

set -uo pipefail

# Versions the driver documentation was verified against (see verified-facts.md)
VERIFIED_OPENSPEC="1.13.1"
VERIFIED_HERDR="0.9.0"
VERIFIED_CODEX="0.155.0"

# --- Helpers ---

json_str() {
  # Escape special JSON characters
  local val="${1:-}"
  val="${val//\\/\\\\}"
  val="${val//\"/\\\"}"
  val="${val//$'\n'/ }"
  val="${val//$'\r'/}"
  val="${val//$'\t'/ }"
  printf '"%s"' "$val"
}

first_line() {
  local val="${1:-}"
  printf '%s' "${val%%$'\n'*}"
}

# Run "<tool> <args…>" and emit {"ok":bool,"version":str,"error":str}
probe_tool() {
  local out rc
  out=$("$@" 2>&1)
  rc=$?
  if [[ $rc -eq 0 ]]; then
    printf '{"ok":true,"version":%s,"error":""}' "$(json_str "$(first_line "$out")")"
  else
    printf '{"ok":false,"version":"","error":%s}' "$(json_str "exit $rc: $(first_line "$out")")"
  fi
}

# Run a command for its exit status only
quiet() {
  "$@" >/dev/null 2>&1
}

bool() {
  if "$@"; then printf 'true'; else printf 'false'; fi
}

# --- Tools (required: openspec herdr codex git jq python3; optional: gh, glab) ---
# gh / glab only matter for opening the review request; pushing a verified lane needs neither.

t_openspec=$(probe_tool openspec --version)
t_herdr=$(probe_tool herdr --version)
t_codex=$(probe_tool codex --version)
t_git=$(probe_tool git --version)
t_jq=$(probe_tool jq --version)
t_python3=$(probe_tool python3 --version)
t_gh=$(probe_tool gh --version)
t_glab=$(probe_tool glab --version)

# --- Logins (status only; never log in) ---

codex_logged_in=$(bool quiet codex login status)
gh_authenticated=$(bool quiet gh auth status)

# --- herdr pane ---

in_herdr_pane="false"
if [[ "${HERDR_ENV:-}" == "1" && -n "${HERDR_PANE_ID:-}" ]] && quiet herdr agent list; then
  in_herdr_pane="true"
fi

# --- Repository ---

is_git_repo="false"
is_main_checkout="false"
repo_root=""
current_branch=""
has_origin="false"
has_openspec_dir="false"
codex_skill_tracked="false"

if repo_root=$(git rev-parse --show-toplevel 2>/dev/null) && [[ -n "$repo_root" ]]; then
  is_git_repo="true"
  git_dir=$(cd "$repo_root" && cd "$(git rev-parse --git-dir 2>/dev/null)" 2>/dev/null && pwd -P)
  common_dir=$(cd "$repo_root" && cd "$(git rev-parse --git-common-dir 2>/dev/null)" 2>/dev/null && pwd -P)
  if [[ -n "$git_dir" && "$git_dir" == "$common_dir" ]]; then
    is_main_checkout="true"
  fi
  current_branch=$(git -C "$repo_root" branch --show-current 2>/dev/null || true)
  has_origin=$(bool quiet git -C "$repo_root" remote get-url origin)
  if [[ -d "$repo_root/openspec" ]]; then
    has_openspec_dir="true"
  fi
  codex_skill_tracked=$(bool quiet git -C "$repo_root" ls-files --error-unmatch .agents/skills/openspec-apply-change/SKILL.md)
else
  repo_root=""
fi

# --- Report ---

j_pane=$(json_str "${HERDR_PANE_ID:-}")
j_root=$(json_str "$repo_root")
j_branch=$(json_str "$current_branch")
j_v_openspec=$(json_str "$VERIFIED_OPENSPEC")
j_v_herdr=$(json_str "$VERIFIED_HERDR")
j_v_codex=$(json_str "$VERIFIED_CODEX")

# printf (a builtin) rather than cat: the report must still print on a minimal PATH
printf '%s\n' "{
  \"tools\": {
    \"openspec\": $t_openspec,
    \"herdr\": $t_herdr,
    \"codex\": $t_codex,
    \"git\": $t_git,
    \"jq\": $t_jq,
    \"python3\": $t_python3,
    \"gh\": $t_gh,
    \"glab\": $t_glab
  },
  \"required_tools\": [\"openspec\", \"herdr\", \"codex\", \"git\", \"jq\", \"python3\"],
  \"optional_tools\": [\"gh\", \"glab\"],
  \"logins\": {
    \"codex_logged_in\": $codex_logged_in,
    \"gh_authenticated\": $gh_authenticated
  },
  \"env\": {
    \"in_herdr_pane\": $in_herdr_pane,
    \"herdr_pane_id\": $j_pane
  },
  \"repo\": {
    \"is_git_repo\": $is_git_repo,
    \"is_main_checkout\": $is_main_checkout,
    \"root\": $j_root,
    \"current_branch\": $j_branch,
    \"has_origin\": $has_origin,
    \"has_openspec_dir\": $has_openspec_dir,
    \"codex_apply_skill_tracked\": $codex_skill_tracked
  },
  \"verified_against\": {
    \"openspec\": $j_v_openspec,
    \"herdr\": $j_v_herdr,
    \"codex\": $j_v_codex
  }
}"
