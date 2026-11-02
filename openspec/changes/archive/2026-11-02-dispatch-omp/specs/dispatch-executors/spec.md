## MODIFIED Requirements

### Requirement: The executor is a property of each lane
The executor of a lane SHALL be determined from the agent herdr reports in the lane's worktree when one is running, and otherwise from the disposable bookkeeping, where a record written before executors were recorded counts as codex. A lane whose executor cannot be determined either way, or whose executor is not one the engine supports, SHALL be reported with an unknown executor and SHALL NOT be steered.

#### Scenario: Bookkeeping lost while the agent runs
- **WHEN** the bookkeeping is deleted while an omp lane's agent is running
- **THEN** the next sweep SHALL still report that lane as an omp lane

#### Scenario: Lanes from before executors were recorded
- **WHEN** a lane created by an earlier version has no executor in the bookkeeping and herdr reports a codex agent in its worktree
- **THEN** the lane SHALL be treated as a codex lane

#### Scenario: Earlier lane whose agent has exited
- **WHEN** a lane created by an earlier version has a bookkeeping record without an executor and no running agent
- **THEN** the lane SHALL be treated as a codex lane

#### Scenario: No agent and no record
- **WHEN** a lane has no running agent and no recorded executor
- **THEN** the sweep SHALL report its executor as unknown and SHALL NOT send it any input

#### Scenario: A lane left by the retired pi executor
- **WHEN** a lane's agent is pi, or its bookkeeping records pi as its executor
- **THEN** the sweep SHALL report its executor as unknown and SHALL NOT send it any input

### Requirement: Any entry command supervises every lane by that lane's executor
The `status` sub-command of either entry command SHALL report every lane of the repository, and SHALL interpret each lane's pane, goal state and readiness by the rules of that lane's own executor.

#### Scenario: Mixed lanes
- **WHEN** a repository has one codex lane and one omp lane and the user runs `/dispatch:codex status`
- **THEN** both lanes SHALL appear in the overview with their executor named, and the omp lane's verdict SHALL be derived from omp's goal state and pane

### Requirement: Both entry commands run the same engine
The lane mechanics shipped in the `codex` and `omp` skill directories SHALL be identical copies, so that the two entry commands cannot disagree about lane state. The repository SHALL provide a check that fails when the copies differ.

#### Scenario: One copy edited alone
- **WHEN** the lane mechanics in one skill directory are changed without the other
- **THEN** the repository's sync check SHALL fail and name the files that differ

## ADDED Requirements

### Requirement: The entry command selects codex or omp
`/dispatch:codex` SHALL dispatch changes to codex and `/dispatch:omp` SHALL dispatch changes to omp (oh-my-pi). Both entry commands SHALL accept the same sub-commands (`status`, `setup`, or change names) and the same flags (`--strict`, `--ready`, `--no-pr`, `--no-loop`). A single invocation SHALL dispatch all of its named changes to one executor. No entry command SHALL dispatch to pi.

#### Scenario: Dispatch to omp
- **WHEN** the user invokes `/dispatch:omp add-owner-filter`
- **THEN** the lane for `add-owner-filter` SHALL be started with an omp agent, and the confirmation SHALL name omp as the executor

#### Scenario: Same change name, different executors in one repository
- **WHEN** one change was dispatched with `/dispatch:codex` and another with `/dispatch:omp` in the same repository
- **THEN** each lane SHALL run its own executor and neither dispatch SHALL alter the other lane

### Requirement: An omp lane's shell runs inside an operating-system sandbox
Every shell command an omp lane runs — through its shell tool or a user-entered shell command — SHALL execute inside an operating-system sandbox whose writable locations are only the lane's worktree, the repository's common git directory excluding that directory's hooks and config, the user's package-manager caches, and a temporary directory private to the lane. The files that tell git where the lane's repository is — the worktree's `.git` pointer and its administrative `commondir`, `gitdir` and `config.worktree` — SHALL NOT be writable, and the dispatcher's own git commands SHALL NOT run a repository-configured file-system monitor. The sandbox SHALL deny reading the user's SSH, cloud and GnuPG credential directories. Outbound network access from the sandbox SHALL be limited to an allowlist of package-registry hosts: the public registries and the registries and mirrors the user configured for npm, pip, Go, Maven and Cargo. Package managers that do not use the sandbox's proxy on their own SHALL be configured inside the sandbox to use it. When the sandbox cannot be initialized, shell commands SHALL be refused rather than run unsandboxed.

#### Scenario: Commit from the lane
- **WHEN** an omp lane runs `git commit` in its worktree
- **THEN** the commit SHALL succeed

#### Scenario: Installing dependencies
- **WHEN** an omp lane installs a dependency with npm, pnpm, bun, pip, uv, Go, Maven or Cargo from a registry on the allowlist
- **THEN** the install SHALL succeed, writing only to the worktree, the package-manager caches and the lane's temporary directory, and leaving the worktree's other files untouched

#### Scenario: Write outside the lane through the shell
- **WHEN** an omp lane's shell command writes to the main checkout, the home directory, or the common git directory's hooks or config
- **THEN** the write SHALL fail with a permission error

#### Scenario: Redirecting git
- **WHEN** an omp lane tries to rewrite or remove its worktree's `.git` pointer or the worktree's `commondir`
- **THEN** the write SHALL fail, and a later `list` SHALL run no program named in a repository configuration

#### Scenario: Host not on the allowlist
- **WHEN** an omp lane's shell command connects to a host that is not on the allowlist
- **THEN** the connection SHALL be refused

#### Scenario: Sandbox unavailable
- **WHEN** the sandbox fails to initialize in an omp lane
- **THEN** every shell command SHALL be refused with that reason and no shell command SHALL run outside the sandbox

### Requirement: An omp lane's file tools are confined to the same writable locations
omp's file-writing tools SHALL be allowed to write only inside the same writable locations as the sandbox, with paths resolved through symbolic links before comparison. omp's file-reading tools SHALL NOT read the directories the sandbox denies reading — directly, through a symbolic link, or by searching or finding through one of their ancestors — and SHALL NOT read any target that is not a plain filesystem path, except the `skill://` resources that make the OpenSpec apply skill readable. By default a call outside these limits SHALL be blocked and the reason returned to the model. Under `--strict` an out-of-bounds write SHALL instead wait for a human's approval, which the supervisor SHALL surface and SHALL NOT answer; out-of-bounds reads SHALL stay blocked.

#### Scenario: Write inside the lane through an alias path
- **WHEN** an omp lane writes a file whose path reaches the worktree through a symbolic link
- **THEN** the write SHALL succeed

#### Scenario: Reading a protected directory
- **WHEN** an omp lane's read tool targets a file under `~/.ssh`, or its grep or find tool searches the home directory
- **THEN** the call SHALL be blocked and nothing from the protected directory SHALL reach the model

#### Scenario: Reading a URL or an internal resource
- **WHEN** an omp lane's read tool targets `https://example.com`, a `www.` address, or an internal URI such as `ssh://`, `proc://`, `vault://` or `mcp://`
- **THEN** the call SHALL be blocked and no network request or internal resource read SHALL happen

#### Scenario: Reading the OpenSpec apply skill
- **WHEN** an omp lane's read tool targets `skill://openspec-apply-change`
- **THEN** the call SHALL be allowed

#### Scenario: Write outside the lane, default posture
- **WHEN** an omp lane's write or edit tool targets a path outside the writable locations
- **THEN** the call SHALL be blocked, no file SHALL change, and the model SHALL receive the reason

#### Scenario: Write outside the lane, strict posture
- **WHEN** the same call happens in a lane started with `--strict`
- **THEN** the lane SHALL wait for approval and the next sweep SHALL report the request to the user

### Requirement: An omp lane runs only an allowlisted set of tools
An omp lane SHALL start with only the tools needed to apply a change — read, the sandboxed shell, edit, write and the goal tool — available to the model. Code-evaluation, web, browser, sub-agent, file-search tools that the guard does not cover, structured-edit devices, the interactive pseudo-terminal shell and language-server tools SHALL NOT be available in the lane, and MCP tools SHALL NOT be callable from it. MCP servers that omp itself starts from the user's or the repository's configuration are outside this requirement and are documented as such.

#### Scenario: Model lists its tools
- **WHEN** an omp lane's model is asked which tools it has
- **THEN** only read, bash, edit, write and goal SHALL be available

#### Scenario: MCP servers configured for omp
- **WHEN** the user's or the repository's omp configuration declares MCP servers and an omp lane calls one of their tools
- **THEN** the call SHALL be blocked and the model SHALL receive the reason

### Requirement: An omp lane changes nothing in the user's omp configuration
Starting an omp lane SHALL NOT install packages into, or write settings, model roles or trust decisions to, the user's omp configuration. The lane SHALL use the model the user set as omp's default.

#### Scenario: Lane finished
- **WHEN** an omp lane has finished
- **THEN** the user's omp settings and installed plugin list SHALL be identical to before the lane started

#### Scenario: No default model set
- **WHEN** the user has not set a default model in omp
- **THEN** the dispatch-time gate SHALL stop and point the user to the setup sub-command, and no lane SHALL be started

### Requirement: An omp lane receives its goal when it starts
An omp lane SHALL be given its goal — applying the change through the OpenSpec apply skill and stating the same lane boundaries as a codex lane — as part of starting the agent, exactly once, and SHALL NOT be sent a separate goal prompt. The goal's state SHALL be read from the lane's session record.

#### Scenario: Goal completes
- **WHEN** the omp lane finishes every task and marks its goal complete
- **THEN** the sweep SHALL read the goal as complete and SHALL still judge completion only from tasks and tree

#### Scenario: Goal state after leaving goal mode
- **WHEN** the session records a goal as complete and afterwards records mode changes without a goal
- **THEN** the sweep SHALL still read the goal as complete

#### Scenario: Start command not delivered
- **WHEN** the start command typed into the lane's pane never reaches the shell intact, so no agent runs and the bare shell is in the foreground
- **THEN** the dispatcher SHALL clear the pane's input and start the agent once more, and SHALL report the retry; an agent that started and then exited SHALL NOT be retried

#### Scenario: Agent already working when the start returns
- **WHEN** the omp lane is already working on its goal when the start returns
- **THEN** the lane SHALL count as started

#### Scenario: Goal requested again
- **WHEN** a goal prompt is requested for an omp lane that was started with its goal
- **THEN** nothing SHALL be sent and the request SHALL be refused as already primed

### Requirement: An omp prompt is confirmed as submitted
After sending a corrective or continuation prompt to an omp lane, the dispatcher SHALL confirm that the lane started working. When that exact prompt text is still in the lane's input box and the lane has not started, it SHALL submit it once more and SHALL NOT retype the text; any other content of the input box or an open dialog SHALL never receive a keypress.

#### Scenario: Text left in the input box
- **WHEN** a continuation prompt was typed into an omp lane but the lane remains idle with that text in its input box
- **THEN** the dispatcher SHALL press enter once and the prompt SHALL be delivered exactly once

## REMOVED Requirements

### Requirement: The entry command selects the executor
**Reason**: Its scenarios were written for the retired pi executor; the requirement continues under a new name with omp scenarios.
**Migration**: See "The entry command selects codex or omp". `/dispatch:pi` no longer exists; use `/dispatch:omp`.

### Requirement: A pi lane's shell runs inside an operating-system sandbox
**Reason**: pi is retired as an executor; omp replaces it.
**Migration**: The same sandbox applies to omp lanes ("An omp lane's shell runs inside an operating-system sandbox"). Finish remaining pi lanes by hand.

### Requirement: A pi lane's file tools are confined to the same writable locations
**Reason**: pi is retired as an executor; omp replaces it.
**Migration**: See "An omp lane's file tools are confined to the same writable locations", which also blocks URL and internal-URI reads.

### Requirement: A pi lane does not load the user's MCP servers
**Reason**: pi is retired as an executor; omp replaces it.
**Migration**: See "An omp lane runs only an allowlisted set of tools".

### Requirement: A pi lane changes nothing in the user's pi configuration
**Reason**: pi is retired as an executor; omp replaces it.
**Migration**: See "An omp lane changes nothing in the user's omp configuration".

### Requirement: A pi lane is primed with a pinned goal extension
**Reason**: omp has goal mode built in; no goal extension is loaded.
**Migration**: See "An omp lane receives its goal when it starts".

### Requirement: Pi lanes are started and primed one at a time
**Reason**: The spacing and restart existed because concurrent pi processes lost a race for pi's own configuration lock. Four concurrent omp starts and requests succeeded on 2026-11-02; omp keeps credentials in a database rather than a locked file.
**Migration**: None. omp lanes start back to back.

### Requirement: A pi prompt is confirmed as submitted
**Reason**: pi is retired as an executor.
**Migration**: See "An omp prompt is confirmed as submitted".
