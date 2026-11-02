#!/usr/bin/env bash
# dispatch plugin environment diagnostic script
# Outputs a JSON report of the tools and environment a dispatch depends on.
#
# Usage: doctor.sh [--executor codex|omp]   (default codex)
# The same file ships in dispatch/codex and dispatch/omp; only the executor's own checks differ.
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
VERIFIED_OMP="18.15.0"
SANDBOX_RUNTIME="0.0.26"   # pinned in lane-guard/package.json

executor="codex"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --executor)
      if [[ $# -lt 2 ]]; then printf '{"error":"--executor needs a value: codex or omp"}\n'; exit 2; fi
      executor="$2"; shift 2 ;;
    *) printf '{"error":"unknown argument: %s"}\n' "$1"; exit 2 ;;
  esac
done
if [[ "$executor" != "codex" && "$executor" != "omp" ]]; then
  printf '{"error":"--executor must be codex or omp"}\n'
  exit 2
fi
script_dir="${BASH_SOURCE[0]}"
if [[ "$script_dir" == */* ]]; then script_dir="${script_dir%/*}"; else script_dir="."; fi

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

# The sandbox dependency of the lane-guard, installed into this skill directory by setup
probe_sandbox_runtime() {
  local pkg="$script_dir/lane-guard/node_modules/@anthropic-ai/sandbox-runtime/package.json"
  local line ver=""
  if [[ ! -f "$pkg" ]]; then
    printf '{"ok":false,"version":"","error":%s}' "$(json_str "not installed in $script_dir/lane-guard")"
    return
  fi
  while IFS= read -r line; do
    if [[ "$line" =~ \"version\":[[:space:]]*\"([^\"]+)\" ]]; then ver="${BASH_REMATCH[1]}"; break; fi
  done < "$pkg"
  if [[ "$ver" == "$SANDBOX_RUNTIME" ]]; then
    printf '{"ok":true,"version":%s,"error":""}' "$(json_str "$ver")"
  else
    printf '{"ok":false,"version":%s,"error":%s}' "$(json_str "$ver")" "$(json_str "expected $SANDBOX_RUNTIME")"
  fi
}

# --- Tools (required: openspec herdr git jq python3 + the executor's own; optional: gh, glab) ---
# gh / glab only matter for opening the review request; pushing a verified lane needs neither.

t_openspec=$(probe_tool openspec --version)
t_herdr=$(probe_tool herdr --version)
t_git=$(probe_tool git --version)
t_jq=$(probe_tool jq --version)
t_python3=$(probe_tool python3 --version)
t_gh=$(probe_tool gh --version)
t_glab=$(probe_tool glab --version)

gh_authenticated=$(bool quiet gh auth status)

# --- The executor (status only; never log in, never print a credential) ---

if [[ "$executor" == "codex" ]]; then
  t_codex=$(probe_tool codex --version)
  codex_logged_in=$(bool quiet codex login status)
else
  t_omp=$(probe_tool omp --version)
  t_rg=$(probe_tool rg --version)
  t_npm=$(probe_tool npm --version)
  t_sandbox=$(probe_sandbox_runtime)
  linux="false"
  if [[ "${OSTYPE:-}" == linux* ]]; then
    linux="true"
    t_bwrap=$(probe_tool bwrap --version)
    t_socat=$(probe_tool socat -V)
  fi
  # omp's default model, and whether one of its logged-in providers offers it (nothing about the credential)
  omp_model=""
  omp_model_ready="false"
  if quiet omp --version && quiet jq --version; then
    omp_model=$(omp config get modelRoles 2>/dev/null | jq -r '.default // empty' 2>/dev/null)
    if [[ -n "$omp_model" ]]; then
      omp_model_ready=$(bool quiet sh -c 'omp models --json 2>/dev/null | jq -e --arg m "$1" '"'"'any(.models[]; "\(.provider)/\(.id)" == $m)'"'"'' _ "$omp_model")
    fi
  fi
  omp_herdr_integration="false"
  if [[ "$(herdr integration status 2>/dev/null)" =~ (^|$'\n')[[:space:]]*omp:[[:space:]]*current ]]; then
    omp_herdr_integration="true"
  fi
fi

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
omp_skill_tracked="false"

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
  # omp discovers .omp/skills, .agents/skills and .claude/skills
  for d in .omp .agents .claude; do
    if quiet git -C "$repo_root" ls-files --error-unmatch "$d/skills/openspec-apply-change/SKILL.md"; then
      omp_skill_tracked="true"
    fi
  done
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
if [[ "$executor" == "codex" ]]; then
printf '%s\n' "{
  \"executor\": \"codex\",
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
exit 0
fi

linux_tools=""
linux_required=""
if [[ "$linux" == "true" ]]; then
  linux_tools=",
    \"bwrap\": $t_bwrap,
    \"socat\": $t_socat"
  linux_required=", \"bwrap\", \"socat\""
fi
printf '%s\n' "{
  \"executor\": \"omp\",
  \"tools\": {
    \"openspec\": $t_openspec,
    \"herdr\": $t_herdr,
    \"omp\": $t_omp,
    \"npm\": $t_npm,
    \"rg\": $t_rg,
    \"sandbox_runtime\": $t_sandbox,
    \"git\": $t_git,
    \"jq\": $t_jq,
    \"python3\": $t_python3,
    \"gh\": $t_gh,
    \"glab\": $t_glab$linux_tools
  },
  \"required_tools\": [\"openspec\", \"herdr\", \"omp\", \"npm\", \"rg\", \"sandbox_runtime\", \"git\", \"jq\", \"python3\"$linux_required],
  \"optional_tools\": [\"gh\", \"glab\"],
  \"logins\": {
    \"omp_model\": $(json_str "$omp_model"),
    \"omp_model_ready\": $omp_model_ready,
    \"gh_authenticated\": $gh_authenticated
  },
  \"env\": {
    \"in_herdr_pane\": $in_herdr_pane,
    \"herdr_pane_id\": $j_pane,
    \"sandbox_platform\": $(json_str "${OSTYPE:-unknown}"),
    \"herdr_omp_integration\": $omp_herdr_integration
  },
  \"repo\": {
    \"is_git_repo\": $is_git_repo,
    \"is_main_checkout\": $is_main_checkout,
    \"root\": $j_root,
    \"current_branch\": $j_branch,
    \"has_origin\": $has_origin,
    \"has_openspec_dir\": $has_openspec_dir,
    \"omp_apply_skill_tracked\": $omp_skill_tracked
  },
  \"verified_against\": {
    \"openspec\": $j_v_openspec,
    \"herdr\": $j_v_herdr,
    \"omp\": $(json_str "$VERIFIED_OMP"),
    \"sandbox_runtime\": $(json_str "$SANDBOX_RUNTIME")
  }
}"
