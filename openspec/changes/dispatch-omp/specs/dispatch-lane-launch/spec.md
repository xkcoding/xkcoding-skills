## MODIFIED Requirements

### Requirement: Only planned, unfinished changes are dispatched
A change SHALL be dispatched only when OpenSpec reports that every artifact required for apply exists and at least one task remains. When invoked without a change name, the skill SHALL list the eligible changes and ask the user which to dispatch.

#### Scenario: Planning incomplete
- **WHEN** OpenSpec reports the apply state of the named change as blocked by a missing artifact
- **THEN** the change SHALL NOT be dispatched and the user SHALL be told which artifact is missing

#### Scenario: Nothing left to do
- **WHEN** OpenSpec reports all tasks of the named change complete
- **THEN** the change SHALL NOT be dispatched

#### Scenario: No change named
- **WHEN** `/dispatch:codex` or `/dispatch:omp` is invoked with no change name
- **THEN** the skill SHALL list the eligible changes and ask the user to choose

### Requirement: One lane per change
Each dispatched change SHALL get exactly one lane, consisting of one git worktree, one branch and one agent of the executor selected by the entry command. The dispatcher SHALL NOT split a single change across lanes and SHALL NOT create a second lane for a change that already has one, whichever executor that lane runs.

#### Scenario: Several changes named
- **WHEN** three eligible changes are named in one invocation
- **THEN** three lanes SHALL be created, one per change, and all agents SHALL be started before any lane is supervised

#### Scenario: Change already has a lane
- **WHEN** a worktree for the named change already exists
- **THEN** the dispatcher SHALL NOT create another lane and SHALL point the user to the status sub-command

#### Scenario: Change already has a lane run by the other executor
- **WHEN** `/dispatch:omp` names a change that already has a codex lane
- **THEN** the dispatcher SHALL NOT create another lane and SHALL tell the user which executor runs the existing lane

### Requirement: Approval posture defaults to automatic review and never bypasses the sandbox
Every lane SHALL run inside a sandbox that confines writes to the lane and still lets it commit to its branch, and the dispatcher SHALL NOT launch a lane with approvals and sandbox bypassed. For codex, the default posture SHALL be codex's automatic approval review inside a workspace-write sandbox, and `--strict` SHALL select the workspace-write sandbox explicitly with approvals requested from a human. For omp, the default posture SHALL block out-of-bounds operations and return the reason to the model, and `--strict` SHALL send out-of-bounds file writes to a human for approval; in both omp postures shell commands SHALL stay inside the operating-system sandbox and the lane's tools SHALL stay limited to its allowlist. The confirmation SHALL name the posture in the terms of the selected executor.

#### Scenario: Default posture
- **WHEN** no posture flag is given
- **THEN** a codex lane SHALL start under automatic approval review, an omp lane SHALL start with out-of-bounds operations blocked, and the confirmation SHALL have named that posture

#### Scenario: Strict posture
- **WHEN** `--strict` is given
- **THEN** a codex lane SHALL start with the workspace-write sandbox selected explicitly rather than inherited from defaults, and an omp lane SHALL start with out-of-bounds file writes routed to human approval

#### Scenario: Bypass requested
- **WHEN** the user asks for a lane with approvals and sandbox bypassed
- **THEN** the dispatcher SHALL decline and explain that this posture is not offered

### Requirement: A lane is primed once with a goal and its boundaries
Each lane SHALL be primed exactly once with a goal, through the executor's goal facility, that applies the change through the OpenSpec apply skill and states the lane boundaries: work only in this checkout, tick each task when it is complete, make one Conventional Commits commit per task, never push, never merge, never open a pull request, and finish when every task is ticked and the working tree is clean. The skill SHALL be named in the form the executor understands. A codex lane SHALL be primed after its input box is visible; an omp lane SHALL be primed as part of starting the agent.

#### Scenario: Goal accepted
- **WHEN** the goal is accepted
- **THEN** the lane SHALL begin applying the change without further input

#### Scenario: Goal mode unavailable
- **WHEN** the executor rejects the goal command
- **THEN** the dispatcher SHALL send the same instructions as a plain prompt and report that lane as driven by supervision nudges

#### Scenario: Session known before the goal
- **WHEN** herdr already reports a session for a lane whose executor reports sessions before the first turn
- **THEN** the session alone SHALL NOT count as evidence that the lane was primed

## ADDED Requirements

### Requirement: Startup dialogs and notices are read, never answered by default
Before sending any input to a lane, the dispatcher SHALL read the lane's pane. When a selection list or dialog is present it SHALL NOT submit the highlighted default. It SHALL choose an option that changes nothing on the user's machine and persists no preference, and it SHALL ask the user before accepting a dialog that persists a setting. Notices that do not take input SHALL NOT be treated as dialogs.

#### Scenario: Update prompt at startup
- **WHEN** codex shows an update prompt whose default option upgrades codex
- **THEN** the dispatcher SHALL select the option that skips the update for this launch only, and codex SHALL NOT be upgraded

#### Scenario: Directory trust prompt
- **WHEN** codex asks whether to trust the repository
- **THEN** the dispatcher SHALL ask the user before accepting, because acceptance is recorded in the user's codex configuration

#### Scenario: Banner and tips in omp
- **WHEN** omp draws its startup banner, a tip, or an update notice
- **THEN** the dispatcher SHALL judge the lane by its input box and status line, and omp SHALL NOT be updated

#### Scenario: Agent exits during startup
- **WHEN** the agent process exits before becoming ready
- **THEN** the dispatcher SHALL read the pane for the actual error, record that lane as failed with that error, and continue launching the other lanes

## REMOVED Requirements

### Requirement: Startup dialogs are read, never answered by default
**Reason**: Its scenarios were written for the retired pi executor; the requirement continues under a new name with omp scenarios.
**Migration**: See "Startup dialogs and notices are read, never answered by default".
