## Why

The OS sandbox of an omp lane gets in the way of ordinary work. A real lane (the `aimicontextstudio` change `agent-eval-runner-dedicated-models`, 2026-11-02) failed in two places, and neither had anything to do with the boundary the sandbox protects:

- A test that starts a local mock server failed with `bind failed: Operation not permitted` (`JevDecisionClientTest`). The sandbox forbids listening on any port.
- The model wrote a scratch file to `/tmp/DebugFreezeTest.java` and got `Operation not permitted`. Only the lane's own temporary directory is writable, and `$TMPDIR` already points there, but models hard-code `/tmp`.

That session contained no network refusals; these two were the only friction.

## What Changes

- Shell commands in an omp lane may listen on and connect to ports on this machine (sandbox-runtime's `allowLocalBinding`). On macOS this covers all of the machine's own addresses, not just loopback. Connections to any other host still go through the package-registry allowlist.
- `/tmp` (its real path, `/private/tmp` on macOS) becomes writable for the lane: for its shell commands through the sandbox, and for its write and edit tools through the guard, since they share the writable locations.
- `/tmp` is not opened when the repository's main checkout, the lane's worktree, or the common git directory lies under it. Opening it there would make the main checkout and the git files that must stay protected writable as well. The lane then keeps only its private temporary directory, and `launch` reports that `/tmp` was left closed.
- Docs say what this costs:
  - the lane can reach services that listen on this machine (local databases, model servers);
  - a test server the lane binds to `0.0.0.0` is reachable from the local network while it runs, unless the macOS firewall blocks it;
  - it can change other programs' files in `/tmp`.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `dispatch-executors`: the requirement "An omp lane's shell runs inside an operating-system sandbox" adds `/tmp` (except when the repository lives under it) to the writable locations, and allows listening on and connecting to this machine's own addresses.

## Impact

- **Code:**
  - `dispatch/codex/scripts/lane.py`, then synced to `dispatch/omp/scripts/lane.py`: `guard_policy` adds `/tmp` and a network flag to the policy, and `launch` reports when `/tmp` stays closed.
  - `dispatch/omp/scripts/lane-guard/index.ts`: passes `allowLocalBinding` to `SandboxManager.initialize` and accepts the new policy field.
- **Codex lanes:** unchanged. Only the omp executor has a policy.
- **Docs:** `dispatch/omp/SKILL.md`, `references/setup.md`, `references/known-behaviors.md`, `dispatch/README.md`, `CHANGELOG.md`, and the `dispatch-executors` main spec on archive.
- **Dependencies:** none new. `allowLocalBinding` already exists in the pinned `@anthropic-ai/sandbox-runtime` 0.0.26.
