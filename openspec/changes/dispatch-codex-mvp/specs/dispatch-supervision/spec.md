# Spec Delta

## Purpose

Keeps every dispatched lane moving without a private state protocol, by deriving the state of all lanes from herdr, git and OpenSpec on every sweep and handing anything that needs judgement back to the user.

## ADDED Requirements

### Requirement: Lane state is derived, not stored
A sweep SHALL derive the set of lanes and each lane's progress from the repository's worktree list, herdr's agent list, and OpenSpec's apply status evaluated inside each lane's worktree. Work state (tasks, progress, completion) SHALL NOT be written to any file other than the change's own OpenSpec artifacts.

#### Scenario: Fresh session with no conversation memory
- **WHEN** the status sub-command is invoked in a new session for a repository with running lanes
- **THEN** it SHALL produce the same overview as the session that dispatched them

#### Scenario: Stale copy in the main checkout
- **WHEN** the main checkout contains a copy of the change whose tasks are unticked while the lane's copy shows progress
- **THEN** the sweep SHALL report the lane's progress and SHALL NOT read progress from the main checkout

### Requirement: Disposable bookkeeping only
The supervisor MAY keep machine-local bookkeeping outside the repository for facts that cannot be derived, limited to: lane session identifiers, the approval posture and pull-request base a lane was launched with, when its goal was sent, nudge records, recorded escalations, and publishing attempts. Deleting that bookkeeping SHALL NOT lose any work state or change any lane's reported progress.

#### Scenario: Bookkeeping deleted mid-run
- **WHEN** the bookkeeping is removed while lanes are running
- **THEN** the next sweep SHALL still report every lane's progress, commits and tree state correctly

#### Scenario: Bookkeeping deleted after a lane was published without a pull request
- **WHEN** the bookkeeping is removed and the remote lane branch points at the lane's verified head
- **THEN** the sweep SHALL still report that lane as published rather than as having pushed itself

### Requirement: The overview is one line per lane
Each sweep SHALL report one line per lane giving the change, the agent status, completed and total tasks, the number of lane commits, whether the working tree is clean, and the pull request if one exists. It SHALL NOT print raw JSON.

#### Scenario: Four lanes
- **WHEN** four lanes exist
- **THEN** the sweep output SHALL contain exactly four lane lines

### Requirement: Completion is judged from tasks and tree, never from agent status
A lane SHALL be treated as claiming completion only when OpenSpec reports all of its tasks complete and its working tree is clean and its agent is not in the middle of a turn. The agent status reported by herdr SHALL NOT by itself establish completion or progress.

#### Scenario: Agent reports done with tasks remaining
- **WHEN** herdr reports the lane as done while tasks remain
- **THEN** the lane SHALL NOT be treated as complete

#### Scenario: All tasks ticked while a turn is still running
- **WHEN** all tasks are complete and the tree is clean but the agent is still working
- **THEN** the sweep SHALL leave the lane alone and re-evaluate it on the next sweep

### Requirement: Only lanes that are provably ours are steered
Before sending any input to a lane, the supervisor SHALL confirm that the agent it is about to address runs in that lane's worktree. It SHALL NOT act on any agent, pane or workspace it cannot tie to a lane worktree of this repository, SHALL NOT focus any pane, and SHALL NOT stop the herdr server.

#### Scenario: Name now belongs to a different agent
- **WHEN** the lane's agent name resolves to an agent whose working directory is not the lane's worktree
- **THEN** the supervisor SHALL send it nothing and SHALL surface the lane to the user

### Requirement: The pane is read before any input
Immediately before sending a prompt or key to a lane, the supervisor SHALL read the lane's visible pane. When a selection list or dialog is present it SHALL send no prompt.

#### Scenario: Dialog present when a nudge is due
- **WHEN** a continuation prompt is due and a selection list is visible
- **THEN** no prompt SHALL be sent in that sweep

### Requirement: A stopped lane is nudged only when it is not waiting on a person
When a lane's agent is idle with tasks remaining, the supervisor SHALL read the pane before deciding. When the lane asked a question or reported a blocker, the supervisor SHALL surface the lane's own words to the user and SHALL NOT nudge. Otherwise it SHALL send one continuation prompt that names the change.

#### Scenario: Lane asked for clarification
- **WHEN** an idle lane's last output asks the user a question
- **THEN** the supervisor SHALL report the question to the user and send no continuation prompt

#### Scenario: Lane simply stopped
- **WHEN** an idle lane's last output contains no question or blocker and tasks remain
- **THEN** the supervisor SHALL send one continuation prompt and record the nudge

### Requirement: Nudging stops when it does not produce progress
After each nudge the supervisor SHALL compare the lane's commits and task progress on the next sweep. After two consecutive nudges without a new commit or a change in completed tasks, it SHALL stop nudging that lane and escalate it to the user.

#### Scenario: Two nudges without progress
- **WHEN** a lane shows no new commit and no task progress after two consecutive nudges
- **THEN** the supervisor SHALL escalate the lane and SHALL NOT send a third nudge

### Requirement: Approval requests are surfaced, not answered
When a lane is blocked on an approval request, the supervisor SHALL report the request to the user and SHALL NOT approve or deny it on the user's behalf.

#### Scenario: Strict lane waiting for approval
- **WHEN** a lane under the strict posture shows an approval request
- **THEN** the supervisor SHALL surface the quoted request and leave the lane untouched

### Requirement: A parked goal is resumed only when nobody parked it on purpose
When codex reports a lane's goal as limited by usage, the supervisor SHALL resume it at most once per sweep. When the goal is paused and the supervisor has no record of pausing it, or when the goal is blocked or limited by a budget, the supervisor SHALL escalate and SHALL NOT resume it.

#### Scenario: Usage limit hit
- **WHEN** a lane's goal is reported as usage-limited
- **THEN** the supervisor SHALL send one resume in that sweep and re-evaluate on the next sweep

#### Scenario: Goal paused by an unknown hand
- **WHEN** a lane's goal is paused and no pause is recorded for it
- **THEN** the supervisor SHALL NOT resume it and SHALL report the lane as waiting on the user

### Requirement: Supervision recurs until every lane is settled
After a dispatch, unless `--no-loop` was given, a recurring sweep SHALL be armed and the user SHALL be told how to stop it. The recurrence SHALL end when every lane is published, failed, paused by the user, or waiting on the user. Invoking the status sub-command in a session without an armed recurrence SHALL re-arm it while unsettled lanes remain.

#### Scenario: Dispatching session ended
- **WHEN** the session that dispatched the lanes has ended and the user invokes the status sub-command in a new session
- **THEN** one sweep SHALL run and the recurrence SHALL be armed again

#### Scenario: All lanes settled
- **WHEN** a sweep finds every lane published, failed, paused by the user or waiting on the user
- **THEN** the recurrence SHALL stop and the user SHALL be told which lanes wait on what
