## MODIFIED Requirements

### Requirement: Setup installs only with per-tool consent
For each missing tool or dependency that can be installed by a command, the setup sub-command SHALL show the exact install command, ask the user whether to run it, and run it only after the user agrees. It SHALL ask separately for each item and SHALL NOT use `sudo`. The omp sandbox dependency SHALL be installed only into the skill's own directory.

#### Scenario: User agrees to one install
- **WHEN** `herdr` is missing and the user approves the shown install command
- **THEN** the setup sub-command SHALL run exactly that command and re-run the version check afterwards

#### Scenario: User declines
- **WHEN** the user declines an install
- **THEN** the setup sub-command SHALL leave the machine unchanged, keep the command visible for the user to run later, and continue with the remaining checks

#### Scenario: Sandbox dependency missing
- **WHEN** `/dispatch:omp setup` finds the sandbox dependency absent and the user agrees to install it
- **THEN** it SHALL be installed into the omp skill directory and nothing SHALL be installed globally or into the target repository

### Requirement: The dispatch-time gate is check-only
Before creating anything, a dispatch SHALL verify the tools and environment the selected executor requires. It SHALL NOT install, log in, or initialize anything. When a required item is missing it SHALL stop, name the item, and point the user to the setup sub-command of the same entry command.

#### Scenario: Required tool missing at dispatch time
- **WHEN** `/dispatch:codex` is invoked and `codex` does not run, or `/dispatch:omp` is invoked and `omp` does not run
- **THEN** no worktree, workspace or agent SHALL be created, and the user SHALL be told what is missing and to run the setup sub-command

#### Scenario: Review-request tool missing
- **WHEN** the forge tool that matches the `origin` host is missing or unauthenticated but all required tools are present
- **THEN** the dispatch SHALL continue, and the confirmation shown before dispatch SHALL state that lanes will be pushed without a review request being opened

#### Scenario: Forge tools are irrelevant to the host
- **WHEN** the repository is hosted on a forge for which the user chose a tool of the runtime
- **THEN** the absence of `gh` and `glab` SHALL NOT be reported as a problem

## ADDED Requirements

### Requirement: Credentials, models, session placement and repository initialization are guided, never performed
The setup sub-command SHALL NOT log in to any service, handle any credential, choose a model, launch herdr, install a herdr integration, or initialize OpenSpec in a repository on the user's behalf. For these conditions it SHALL state what is missing and the command the user should run themselves.

#### Scenario: Codex is installed but not logged in
- **WHEN** `codex` runs but reports that no login is present
- **THEN** the setup sub-command SHALL tell the user to run the login command themselves and SHALL NOT run it

#### Scenario: omp has no usable default model
- **WHEN** `omp` runs but no default model is set, or the default model is not among the models its logged-in providers offer
- **THEN** the setup sub-command SHALL tell the user to log in and choose a default model in omp themselves, and SHALL NOT print or handle any credential

#### Scenario: herdr's omp integration is missing
- **WHEN** herdr reports its omp integration as not installed
- **THEN** the setup sub-command SHALL tell the user to run `herdr integration install omp` themselves and SHALL NOT run it

#### Scenario: Session is not inside a herdr pane
- **WHEN** the herdr pane environment is absent or the herdr socket cannot be reached
- **THEN** the setup sub-command SHALL explain that dispatching requires Claude Code to be started inside a herdr pane, and SHALL NOT start herdr

#### Scenario: Repository lacks the Codex OpenSpec skills
- **WHEN** the executor is codex and the target repository has no committed `.agents/skills/openspec-apply-change/SKILL.md`
- **THEN** the setup sub-command SHALL tell the user to run `openspec init --tools codex` and commit the result, and SHALL NOT run it

#### Scenario: Repository lacks an OpenSpec skill omp can find
- **WHEN** the executor is omp and the target repository has no committed `openspec-apply-change/SKILL.md` under `.omp/skills/`, `.agents/skills/` or `.claude/skills/`
- **THEN** the setup sub-command SHALL tell the user to run `openspec init --tools oh-my-pi` and commit the result, and SHALL NOT run it

### Requirement: Each executor's dependencies are detected by running them
The setup sub-command and the dispatch-time gate SHALL determine whether each tool the selected executor needs is available by executing that tool's version command. For every executor these are `openspec`, `herdr`, `git`, `gh` and `glab`; codex additionally needs `codex`; omp additionally needs `omp`, `rg`, `npm`, and the sandbox dependency installed in the skill directory. Resolving a path to an executable SHALL NOT count as evidence that the tool works. Tools only another executor needs SHALL NOT be reported as missing.

#### Scenario: A shim resolves but the tool does not run
- **WHEN** an executable named `codex` is found on `PATH` but its version command exits with an error
- **THEN** `codex` SHALL be reported as missing, together with the error text

#### Scenario: All tools run
- **WHEN** every version command succeeds
- **THEN** the report SHALL list each tool with the version string it printed

#### Scenario: Codex absent when dispatching to omp
- **WHEN** `/dispatch:omp setup` runs on a machine without codex
- **THEN** codex SHALL NOT be reported as missing

#### Scenario: pi is not needed
- **WHEN** `/dispatch:omp setup` runs on a machine without pi
- **THEN** pi SHALL NOT be reported as missing

## REMOVED Requirements

### Requirement: Credentials, session placement and repository initialization are guided, never performed
**Reason**: Its scenarios were written for the retired pi executor; the requirement continues under a new name with omp scenarios.
**Migration**: See "Credentials, models, session placement and repository initialization are guided, never performed".

### Requirement: Dependencies are detected by running them
**Reason**: Its scenarios were written for the retired pi executor; the requirement continues under a new name with omp scenarios.
**Migration**: See "Each executor's dependencies are detected by running them".
