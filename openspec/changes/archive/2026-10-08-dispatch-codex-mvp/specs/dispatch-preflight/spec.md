# Spec Delta

## Purpose

Ensures that the tools and environment a dispatch depends on are present before any lane is created, and helps a user install what is missing only with their explicit consent.

## ADDED Requirements

### Requirement: Dependencies are detected by running them
The setup sub-command and the dispatch-time gate SHALL determine whether `openspec`, `herdr`, `codex`, `git`, `gh` and `glab` are available by executing each tool's version command. Resolving a path to an executable SHALL NOT count as evidence that the tool works.

#### Scenario: A shim resolves but the tool does not run
- **WHEN** an executable named `codex` is found on `PATH` but its version command exits with an error
- **THEN** `codex` SHALL be reported as missing, together with the error text

#### Scenario: All tools run
- **WHEN** every version command succeeds
- **THEN** the report SHALL list each tool with the version string it printed

### Requirement: Setup installs only with per-tool consent
For each missing tool that can be installed by a command, the setup sub-command SHALL show the exact install command, ask the user whether to run it, and run it only after the user agrees. It SHALL ask separately for each tool and SHALL NOT use `sudo`.

#### Scenario: User agrees to one install
- **WHEN** `herdr` is missing and the user approves the shown install command
- **THEN** the setup sub-command SHALL run exactly that command and re-run the version check afterwards

#### Scenario: User declines
- **WHEN** the user declines an install
- **THEN** the setup sub-command SHALL leave the machine unchanged, keep the command visible for the user to run later, and continue with the remaining checks

### Requirement: Credentials, session placement and repository initialization are guided, never performed
The setup sub-command SHALL NOT log in to any service, handle any credential, launch herdr, or initialize OpenSpec in a repository on the user's behalf. For these conditions it SHALL state what is missing and the command the user should run themselves.

#### Scenario: Codex is installed but not logged in
- **WHEN** `codex` runs but reports that no login is present
- **THEN** the setup sub-command SHALL tell the user to run the login command themselves and SHALL NOT run it

#### Scenario: Session is not inside a herdr pane
- **WHEN** the herdr pane environment is absent or the herdr socket cannot be reached
- **THEN** the setup sub-command SHALL explain that dispatching requires Claude Code to be started inside a herdr pane, and SHALL NOT start herdr

#### Scenario: Repository lacks the Codex OpenSpec skills
- **WHEN** the target repository has no committed `.agents/skills/openspec-apply-change/SKILL.md`
- **THEN** the setup sub-command SHALL tell the user to run `openspec init --tools codex` and commit the result, and SHALL NOT run it

### Requirement: Onboarding includes how to leave
After its checks, the setup sub-command SHALL present a short walkthrough covering the day-to-day flow (propose, dispatch, review the pull request, archive by hand) and the exit procedure. The walkthrough SHALL state that the target repository contains nothing installed by this plugin.

#### Scenario: Walkthrough shown after a clean check
- **WHEN** all required tools are present
- **THEN** the setup sub-command SHALL show the flow and the exit procedure before finishing

### Requirement: The dispatch-time gate is check-only
Before creating anything, a dispatch SHALL verify the required tools and environment. It SHALL NOT install, log in, or initialize anything. When a required item is missing it SHALL stop, name the item, and point the user to the setup sub-command.

#### Scenario: Required tool missing at dispatch time
- **WHEN** `/dispatch:codex` is invoked and `codex` does not run
- **THEN** no worktree, workspace or agent SHALL be created, and the user SHALL be told what is missing and to run the setup sub-command

#### Scenario: Review-request tool missing
- **WHEN** the forge tool that matches the `origin` host is missing or unauthenticated but all required tools are present
- **THEN** the dispatch SHALL continue, and the confirmation shown before dispatch SHALL state that lanes will be pushed without a review request being opened

#### Scenario: Forge tools are irrelevant to the host
- **WHEN** the repository is hosted on a forge for which the user chose a tool of the runtime
- **THEN** the absence of `gh` and `glab` SHALL NOT be reported as a problem

### Requirement: Version drift is reported, not blocking
When an installed tool's version differs from the version the driver documentation was verified against, the skill SHALL report the difference as a single line and SHALL continue.

#### Scenario: Newer codex than verified
- **WHEN** the installed `codex` is newer than the verified version
- **THEN** the dispatch SHALL proceed and its report SHALL include one line naming both versions
