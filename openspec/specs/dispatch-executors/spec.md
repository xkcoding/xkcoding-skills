# dispatch-executors Specification

## Purpose
Lets the same dispatch workflow hand OpenSpec changes to more than one coding agent — codex or pi — while every lane stays supervised by the rules of the agent actually running in it, and defines the boundaries a pi lane runs under.

## Requirements

### Requirement: The entry command selects the executor
`/dispatch:codex` SHALL dispatch changes to codex and `/dispatch:pi` SHALL dispatch changes to pi. Both entry commands SHALL accept the same sub-commands (`status`, `setup`, or change names) and the same flags (`--strict`, `--ready`, `--no-pr`, `--no-loop`). A single invocation SHALL dispatch all of its named changes to one executor.

#### Scenario: Dispatch to pi
- **WHEN** the user invokes `/dispatch:pi add-owner-filter`
- **THEN** the lane for `add-owner-filter` SHALL be started with a pi agent, and the confirmation SHALL name pi as the executor

#### Scenario: Same change name, different executors in one repository
- **WHEN** one change was dispatched with `/dispatch:codex` and another with `/dispatch:pi` in the same repository
- **THEN** each lane SHALL run its own executor and neither dispatch SHALL alter the other lane

### Requirement: The executor is a property of each lane
The executor of a lane SHALL be determined from the agent herdr reports in the lane's worktree when one is running, and otherwise from the disposable bookkeeping. A lane whose executor cannot be determined either way SHALL be reported with an unknown executor and SHALL NOT be steered.

#### Scenario: Bookkeeping lost while the agent runs
- **WHEN** the bookkeeping is deleted while a pi lane's agent is running
- **THEN** the next sweep SHALL still report that lane as a pi lane

#### Scenario: Lanes from before executors were recorded
- **WHEN** a lane created by an earlier version has no executor in the bookkeeping and herdr reports a codex agent in its worktree
- **THEN** the lane SHALL be treated as a codex lane

#### Scenario: No agent and no record
- **WHEN** a lane has no running agent and no recorded executor
- **THEN** the sweep SHALL report its executor as unknown and SHALL NOT send it any input

### Requirement: Any entry command supervises every lane by that lane's executor
The `status` sub-command of either entry command SHALL report every lane of the repository, and SHALL interpret each lane's pane, goal state and readiness by the rules of that lane's own executor.

#### Scenario: Mixed lanes
- **WHEN** a repository has one codex lane and one pi lane and the user runs `/dispatch:codex status`
- **THEN** both lanes SHALL appear in the overview with their executor named, and the pi lane's verdict SHALL be derived from pi's goal state and pane

### Requirement: Both entry commands run the same engine
The lane mechanics shipped in the `codex` and `pi` skill directories SHALL be identical copies, so that the two entry commands cannot disagree about lane state. The repository SHALL provide a check that fails when the copies differ.

#### Scenario: One copy edited alone
- **WHEN** the lane mechanics in one skill directory are changed without the other
- **THEN** the repository's sync check SHALL fail and name the files that differ

### Requirement: A pi lane's shell runs inside an operating-system sandbox
Every shell command a pi lane runs — through its shell tool or a user-entered shell command — SHALL execute inside an operating-system sandbox whose writable locations are only the lane's worktree, the repository's common git directory excluding that directory's hooks and config, the user's package-manager caches, and a temporary directory private to the lane. The sandbox SHALL deny reading the user's SSH, cloud and GnuPG credential directories. Outbound network access from the sandbox SHALL be limited to an allowlist of package-registry hosts: the public registries and the registries and mirrors the user configured for npm, pip, Go, Maven and Cargo. Package managers that do not use the sandbox's proxy on their own SHALL be configured inside the sandbox to use it. When the sandbox cannot be initialized, shell commands SHALL be refused rather than run unsandboxed.

#### Scenario: Commit from the lane
- **WHEN** a pi lane runs `git commit` in its worktree
- **THEN** the commit SHALL succeed

#### Scenario: Installing dependencies
- **WHEN** a pi lane installs a dependency with npm, pnpm, bun, pip, uv, Go, Maven or Cargo from a registry on the allowlist
- **THEN** the install SHALL succeed, writing only to the worktree, the package-manager caches and the lane's temporary directory, and leaving the worktree's other files untouched

#### Scenario: Write outside the lane through the shell
- **WHEN** a pi lane's shell command writes to the main checkout, the home directory, or the common git directory's hooks or config
- **THEN** the write SHALL fail with a permission error

#### Scenario: Host not on the allowlist
- **WHEN** a pi lane's shell command connects to a host that is not on the allowlist
- **THEN** the connection SHALL be refused

#### Scenario: Sandbox unavailable
- **WHEN** the sandbox fails to initialize in a pi lane
- **THEN** every shell command SHALL be refused with that reason and no shell command SHALL run outside the sandbox

### Requirement: A pi lane's file tools are confined to the same writable locations
pi's built-in file-writing tools SHALL be allowed to write only inside the same writable locations as the sandbox, with paths resolved through symbolic links before comparison. By default a write outside them SHALL be blocked and the reason returned to the model. Under `--strict` such a write SHALL instead wait for a human's approval, which the supervisor SHALL surface and SHALL NOT answer.

#### Scenario: Write inside the lane through an alias path
- **WHEN** a pi lane writes a file whose path reaches the worktree through a symbolic link
- **THEN** the write SHALL succeed

#### Scenario: Write outside the lane, default posture
- **WHEN** a pi lane's write or edit tool targets a path outside the writable locations
- **THEN** the call SHALL be blocked, no file SHALL change, and the model SHALL receive the reason

#### Scenario: Write outside the lane, strict posture
- **WHEN** the same call happens in a lane started with `--strict`
- **THEN** the lane SHALL wait for approval and the next sweep SHALL report the request to the user

### Requirement: A pi lane does not load the user's MCP servers
A pi lane SHALL start with MCP support disabled, so that no tool runs outside the lane's sandbox through an MCP server.

#### Scenario: User has MCP servers configured for pi
- **WHEN** the user's pi configuration declares MCP servers and a pi lane starts
- **THEN** no MCP server SHALL be connected in that lane

### Requirement: A pi lane changes nothing in the user's pi configuration
Starting a pi lane SHALL NOT install packages into, or write settings or trust decisions to, the user's pi configuration. Project resources of the lane's worktree SHALL be trusted for that run only, and the goal extension SHALL be loaded for that run only at a pinned version.

#### Scenario: Lane started in an untrusted repository
- **WHEN** a pi lane starts in a repository the user never trusted in pi
- **THEN** no trust prompt SHALL be shown, the OpenSpec apply skill SHALL be available to the lane, and the user's saved trust decisions SHALL be unchanged

#### Scenario: Lane finished
- **WHEN** a pi lane has finished
- **THEN** the user's pi settings and installed package list SHALL be identical to before the lane started

### Requirement: A pi lane is primed with a pinned goal extension
A pi lane SHALL be primed once with a goal that applies the change through the OpenSpec apply skill, using the goal extension loaded for that lane, and stating the same lane boundaries as a codex lane. The goal's state SHALL be read from the lane's session record.

#### Scenario: Goal completes
- **WHEN** the pi lane finishes every task and marks its goal complete
- **THEN** the sweep SHALL read the goal as complete and SHALL still judge completion only from tasks and tree

#### Scenario: Goal extension cannot be loaded
- **WHEN** the pinned goal extension cannot be fetched at startup
- **THEN** the lane SHALL be reported as failed to start with the error from the pane, and no goal SHALL be sent

### Requirement: Pi lanes are started and primed one at a time
When several pi lanes are dispatched, the dispatcher SHALL start them one after another, beginning each start only after the previous lane is ready and a fixed spacing has passed, and SHALL space the goals sent to pi lanes by the same interval. A pi lane that comes up without a usable model — because pi could not read its own configuration while another pi held the lock — SHALL be stopped and started once more after the spacing, before any goal is sent; a second such start, or any other startup failure, SHALL be recorded as that lane's failure.

#### Scenario: Four pi lanes dispatched together
- **WHEN** four pi lanes are dispatched in one invocation
- **THEN** no two of them SHALL be starting at the same time, and all four SHALL reach the ready state

#### Scenario: Started without a usable model
- **WHEN** a pi lane reaches its input box but shows no model, or reports that no API key was found
- **THEN** the dispatcher SHALL stop it, start it once more after the spacing, send no goal before the restart, and the report SHALL mention the retry

#### Scenario: Still without a model after the restart
- **WHEN** the restarted lane again shows no usable model
- **THEN** the dispatcher SHALL record the lane as failed to start, naming the missing model, and SHALL NOT retry again

#### Scenario: Startup fails for another reason
- **WHEN** a pi lane exits during startup with any error
- **THEN** the dispatcher SHALL NOT retry it and SHALL record the error as the lane's failure

### Requirement: A pi prompt is confirmed as submitted
After sending a prompt to a pi lane, the dispatcher SHALL confirm that the lane started working. When the prompt text is still in the lane's input box and the lane has not started, it SHALL submit it once more and SHALL NOT retype the text.

#### Scenario: Text left in the input box
- **WHEN** a goal was typed into a pi lane but the lane remains idle with the text in its input box
- **THEN** the dispatcher SHALL press enter once and the goal SHALL be delivered exactly once
