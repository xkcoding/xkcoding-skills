# Spec Delta

## Purpose

Turns an already-proposed OpenSpec change into a running lane: an isolated git worktree on its own branch, with a codex agent applying that change through the standard OpenSpec apply workflow.

## ADDED Requirements

### Requirement: Only planned, unfinished changes are dispatched
A change SHALL be dispatched only when OpenSpec reports that every artifact required for apply exists and at least one task remains. When invoked without a change name, the skill SHALL list the eligible changes and ask the user which to dispatch.

#### Scenario: Planning incomplete
- **WHEN** OpenSpec reports the apply state of the named change as blocked by a missing artifact
- **THEN** the change SHALL NOT be dispatched and the user SHALL be told which artifact is missing

#### Scenario: Nothing left to do
- **WHEN** OpenSpec reports all tasks of the named change complete
- **THEN** the change SHALL NOT be dispatched

#### Scenario: No change named
- **WHEN** `/dispatch:codex` is invoked with no change name
- **THEN** the skill SHALL list the eligible changes and ask the user to choose

### Requirement: One lane per change
Each dispatched change SHALL get exactly one lane, consisting of one git worktree, one branch and one codex agent. The dispatcher SHALL NOT split a single change across lanes and SHALL NOT create a second lane for a change that already has one.

#### Scenario: Several changes named
- **WHEN** three eligible changes are named in one invocation
- **THEN** three lanes SHALL be created, one per change, and all agents SHALL be started before any lane is supervised

#### Scenario: Change already has a lane
- **WHEN** a worktree for the named change already exists
- **THEN** the dispatcher SHALL NOT create another lane and SHALL point the user to the status sub-command

### Requirement: Dispatch runs from the main checkout
A dispatch SHALL run only from the main checkout of a git repository. It SHALL stop when the current directory is not in a git repository or is a linked worktree.

#### Scenario: Invoked from a linked worktree
- **WHEN** the current checkout's git directory differs from the repository's common git directory
- **THEN** the dispatcher SHALL stop and ask the user to re-run from the main checkout

### Requirement: One confirmation before anything is created
Before creating any worktree, workspace, branch or agent, the dispatcher SHALL show, per change, the lane branch, the approval posture and what will happen when the lane finishes, and SHALL ask the user once to confirm. Nothing SHALL be created before the user confirms.

#### Scenario: User declines
- **WHEN** the user does not confirm
- **THEN** no worktree, workspace, branch, commit or agent SHALL exist as a result of the invocation

### Requirement: The base branch is never written
The dispatcher SHALL NOT commit to the base branch and SHALL NOT push it. The change's planning artifacts SHALL travel on the lane branch.

#### Scenario: Change not yet committed
- **WHEN** the change directory is untracked in the main checkout
- **THEN** the lane branch SHALL be forked from the freshly fetched upstream of the base branch, the change directory SHALL become the lane branch's first commit with the message `docs(openspec): propose <change>`, the directory SHALL no longer be present in the main checkout, and the base branch's head SHALL be unchanged

#### Scenario: Change already committed on the current branch
- **WHEN** the change directory is tracked and unmodified on the current branch
- **THEN** the lane branch SHALL be forked from that branch's local head and no propose commit SHALL be created

#### Scenario: Tracked change with local modifications
- **WHEN** the change directory is tracked but has uncommitted modifications
- **THEN** that lane SHALL NOT be created and the user SHALL be asked to commit or discard the modifications first

### Requirement: Approval posture defaults to automatic review and never bypasses the sandbox
By default a lane SHALL run with codex's automatic approval review inside a workspace-write sandbox. With `--strict`, a lane SHALL run in an explicitly selected workspace-write sandbox with approvals requested from a human. In both postures the lane SHALL be able to commit to its branch. The dispatcher SHALL NOT launch a lane with approvals and sandbox bypassed.

#### Scenario: Default posture
- **WHEN** no posture flag is given
- **THEN** the lane SHALL start under automatic approval review, and the confirmation SHALL have named that posture

#### Scenario: Strict posture
- **WHEN** `--strict` is given
- **THEN** the lane SHALL start with the workspace-write sandbox selected explicitly rather than inherited from defaults

#### Scenario: Bypass requested
- **WHEN** the user asks for a lane with approvals and sandbox bypassed
- **THEN** the dispatcher SHALL decline and explain that this posture is not offered

### Requirement: Startup dialogs are read, never answered by default
Before sending any input to a lane, the dispatcher SHALL read the lane's pane. When a selection list or dialog is present it SHALL NOT submit the highlighted default. It SHALL choose an option that changes nothing on the user's machine and persists no preference, and it SHALL ask the user before accepting a dialog that persists a setting.

#### Scenario: Update prompt at startup
- **WHEN** codex shows an update prompt whose default option upgrades codex
- **THEN** the dispatcher SHALL select the option that skips the update for this launch only, and codex SHALL NOT be upgraded

#### Scenario: Directory trust prompt
- **WHEN** codex asks whether to trust the repository
- **THEN** the dispatcher SHALL ask the user before accepting, because acceptance is recorded in the user's codex configuration

#### Scenario: Agent exits during startup
- **WHEN** the agent process exits before becoming ready
- **THEN** the dispatcher SHALL read the pane for the actual error, record that lane as failed with that error, and continue launching the other lanes

### Requirement: A lane is primed once with a goal and its boundaries
After the composer is visible, the dispatcher SHALL prime the lane exactly once with a codex goal that applies the change through the OpenSpec apply skill and states the lane boundaries: work only in this checkout, tick each task when it is complete, make one Conventional Commits commit per task, never push, never merge, never open a pull request, and finish when every task is ticked and the working tree is clean.

#### Scenario: Goal accepted
- **WHEN** the goal command is accepted
- **THEN** the lane SHALL begin applying the change without further input

#### Scenario: Goal mode unavailable
- **WHEN** codex rejects the goal command
- **THEN** the dispatcher SHALL send the same instructions as a plain prompt and report that lane as driven by supervision nudges

### Requirement: Delivery of a prompt is established from the lane, not from the call
When a prompt call fails, times out or is interrupted, the dispatcher SHALL inspect the lane's actual state before sending anything again, and SHALL NOT re-send a goal to a lane that has already received one.

#### Scenario: Prompt call interrupted after delivery
- **WHEN** the prompt call is interrupted and the lane shows a session, new commits or task progress
- **THEN** the dispatcher SHALL treat the goal as delivered and SHALL NOT send it again

### Requirement: Lane identity follows from the change name
The lane's agent name, workspace label and branch SHALL be derived from the change name, so that a lane can be located again without stored state. Names SHALL satisfy herdr's naming limits, and a collision SHALL be resolved by a short suffix rather than by reusing an existing name.

#### Scenario: Change name exceeds the agent name limit
- **WHEN** the derived agent name would exceed herdr's limit
- **THEN** it SHALL be shortened to a valid, unused name and the mapping SHALL remain recoverable from the worktree path

### Requirement: One failed lane does not abort the others
A failure while creating or starting one lane SHALL be recorded for that lane only. The remaining lanes SHALL still be created, started and supervised, and the failure SHALL appear in the report.

#### Scenario: Second of three lanes fails to start
- **WHEN** the second lane's agent cannot be started
- **THEN** the first and third lanes SHALL run, and the report SHALL show the second as failed with its cause
