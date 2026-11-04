# dispatch-executors Specification

## Purpose
Lets the same dispatch workflow hand OpenSpec changes to more than one coding agent — codex or omp — while every lane stays supervised by the rules of the agent actually running in it, and defines the boundaries an omp lane runs under.

## Requirements

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

### Requirement: The entry command selects codex or omp
`/dispatch:codex` SHALL dispatch changes to codex and `/dispatch:omp` SHALL dispatch changes to omp (oh-my-pi). Both entry commands SHALL accept the same sub-commands (`status`, `setup`, or change names) and the same flags (`--strict`, `--ready`, `--no-pr`, `--no-loop`). A single invocation SHALL dispatch all of its named changes to one executor. No entry command SHALL dispatch to pi.

#### Scenario: Dispatch to omp
- **WHEN** the user invokes `/dispatch:omp add-owner-filter`
- **THEN** the lane for `add-owner-filter` SHALL be started with an omp agent, and the confirmation SHALL name omp as the executor

#### Scenario: Same change name, different executors in one repository
- **WHEN** one change was dispatched with `/dispatch:codex` and another with `/dispatch:omp` in the same repository
- **THEN** each lane SHALL run its own executor and neither dispatch SHALL alter the other lane

### Requirement: An omp lane's shell runs inside an operating-system sandbox
Every shell command an omp lane runs — through its shell tool or a user-entered shell command — SHALL execute inside an operating-system sandbox whose writable locations are only the lane's worktree, the parts of the repository's common git directory a commit writes (objects, loose and packed refs, reflogs and LFS objects) plus the lane's own administrative directory, the user's package-manager caches, a temporary directory private to the lane, and the system temporary directory `/tmp` (by its real path) unless the repository's main checkout, the lane's worktree or the common git directory lies under it, in which case `/tmp` SHALL stay closed and the launch SHALL report it. Nothing that tells git where a repository or its configuration is — the worktree's `.git` pointer, the lane's administrative `commondir`, `gitdir` and `config.worktree`, the common directory's `config`, `commondir`, `config.worktree` and hooks, and other worktrees' administrative files — SHALL be writable, and the dispatcher's own git commands SHALL NOT run a repository-configured file-system monitor. The sandbox SHALL deny reading the user's SSH, cloud, GnuPG, container, Kubernetes, `netrc`, GitHub and GitLab CLI, codex and omp credential locations. Shell commands SHALL be allowed to listen on and connect to ports on this machine's own addresses. Connections to any other host SHALL be limited to an allowlist of package-registry hosts: the public registries and the registries and mirrors the user configured for npm, pip, Go, Maven and Cargo. Package managers that do not use the sandbox's proxy on their own SHALL be configured inside the sandbox to use it. When the sandbox cannot be initialized, shell commands SHALL be refused rather than run unsandboxed.

#### Scenario: Commit from the lane
- **WHEN** an omp lane runs `git commit` in its worktree
- **THEN** the commit SHALL succeed

#### Scenario: Installing dependencies
- **WHEN** an omp lane installs a dependency with npm, pnpm, bun, pip, uv, Go, Maven or Cargo from a registry on the allowlist
- **THEN** the install SHALL succeed, writing only to the worktree, the package-manager caches and the lane's temporary directory, and leaving the worktree's other files untouched

#### Scenario: Test with a local server
- **WHEN** a test in an omp lane starts a server on a `localhost` port and connects to it
- **THEN** the server SHALL start and the connection SHALL succeed

#### Scenario: Another host on the local network
- **WHEN** an omp lane's shell command connects directly to another host on the local network, such as the gateway
- **THEN** the connection SHALL be refused

#### Scenario: Scratch file in /tmp
- **WHEN** an omp lane writes `/tmp/DebugFreezeTest.java` through its shell or its write tool, in a repository that does not live under `/tmp`
- **THEN** the write SHALL succeed

#### Scenario: Repository under /tmp
- **WHEN** an omp lane is launched for a repository whose main checkout lies under `/tmp`
- **THEN** `/tmp` SHALL NOT be added to the writable locations, a shell write to the main checkout SHALL still fail, and the launch result SHALL say that `/tmp` stayed closed

#### Scenario: Write outside the lane through the shell
- **WHEN** an omp lane's shell command writes to the main checkout, the home directory, the common git directory's hooks, config or `commondir`, or another worktree's administrative files
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
omp's file-writing tools SHALL be allowed to write only inside the same writable locations as the sandbox, with every symbolic-link component resolved and every existing component spelled as on disk before comparison, including a final link whose target does not exist yet. An edit SHALL be checked against every file it names — each file header of its patch text however indented or spaced, every move or rename destination, and any `path` it also carries — and an edit whose files cannot all be named SHALL be blocked. omp's file-reading tools SHALL NOT read the directories the sandbox denies reading — directly, through a symbolic link, or by searching or finding through one of their ancestors — and SHALL read only plain filesystem paths: a target carrying a scheme (with or without `//`, by omp's own rule that a one-letter scheme, a dotted name or a following line selector such as `README.md:1-20` is not one), containing `://` or starting with `www.` SHALL be blocked, and a target listing several paths SHALL have each of them checked. The goal SHALL name the OpenSpec apply skill by its path in the lane. By default a call outside these limits SHALL be blocked and the reason returned to the model. Under `--strict` an out-of-bounds write SHALL instead wait for a human's approval, which the supervisor SHALL surface and SHALL NOT answer; out-of-bounds reads SHALL stay blocked.

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
- **WHEN** an omp lane reads the apply skill's `SKILL.md` by the path its goal names
- **THEN** the call SHALL be allowed, while `skill://openspec-apply-change` SHALL be blocked

#### Scenario: Read target that omp would repair or split
- **WHEN** an omp lane's read tool targets `https:/host/x`, `urn:x:y`, or `README.md;~/.ssh/id_rsa`
- **THEN** the call SHALL be blocked and nothing SHALL be fetched or read

#### Scenario: Reading lines of a root file
- **WHEN** an omp lane's read tool targets `README.md:1-20` or `Makefile:12`
- **THEN** the call SHALL be allowed

#### Scenario: Different letter case on a case-insensitive disk
- **WHEN** an omp lane writes `.GIT` in its worktree or reads `~/.SSH/config`
- **THEN** the call SHALL be blocked as for `.git` and `~/.ssh/config`

#### Scenario: Multi-file or moving edit
- **WHEN** an omp lane's edit names a file inside the lane together with one outside it, or moves a file inside the lane to a destination outside it
- **THEN** the call SHALL be blocked and no file SHALL change

#### Scenario: Write through a dangling symbolic link
- **WHEN** an omp lane writes to a link inside its worktree whose not-yet-existing target lies outside the writable locations
- **THEN** the call SHALL be blocked and the target SHALL NOT be created

#### Scenario: Write outside the lane, default posture
- **WHEN** an omp lane's write or edit tool targets a path outside the writable locations
- **THEN** the call SHALL be blocked, no file SHALL change, and the model SHALL receive the reason

#### Scenario: Write outside the lane, strict posture
- **WHEN** the same call happens in a lane started with `--strict`
- **THEN** the lane SHALL wait for approval and the next sweep SHALL report the request to the user

### Requirement: A lane that changed omp's project configuration is not restarted on its own
omp loads extensions, settings, MCP servers and hooks from the project — `.omp/`, `.claude/`, `mcp.json`, `.mcp.json`, `.vscode/`, `.cursor/`, `.codex/`, `.gemini/` — in its own process, outside the sandbox. Launching an omp lane whose own commits or worktree files, ignored ones included and compared case-insensitively, touch those locations SHALL be refused with the list of files; after a human reviewed them, launching with `--reviewed-config` SHALL proceed.

#### Scenario: Relaunch after the lane wrote an extension
- **WHEN** an omp lane created `.omp/extensions/x.ts` and its agent is launched again
- **THEN** the launch SHALL be refused, naming `.omp/extensions/x.ts`, and no agent SHALL start

#### Scenario: Configuration hidden from git
- **WHEN** an omp lane added `.omp/extensions/` to `.gitignore` and wrote a file there
- **THEN** a relaunch SHALL still be refused, naming that directory

#### Scenario: Human reviewed the files
- **WHEN** the user reviewed the listed files and the lane is launched with `--reviewed-config`
- **THEN** the launch SHALL proceed

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
