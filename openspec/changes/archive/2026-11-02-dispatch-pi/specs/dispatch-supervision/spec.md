## MODIFIED Requirements

### Requirement: Disposable bookkeeping only
The supervisor MAY keep machine-local bookkeeping outside the repository for facts that cannot be derived, limited to: the executor a lane was launched with, lane session identifiers, the approval posture and pull-request base a lane was launched with, when its goal was sent, nudge records, recorded escalations, and publishing attempts. Deleting that bookkeeping SHALL NOT lose any work state or change any lane's reported progress.

#### Scenario: Bookkeeping deleted mid-run
- **WHEN** the bookkeeping is removed while lanes are running
- **THEN** the next sweep SHALL still report every lane's progress, commits and tree state correctly

#### Scenario: Bookkeeping deleted after a lane was published without a pull request
- **WHEN** the bookkeeping is removed and the remote lane branch points at the lane's verified head
- **THEN** the sweep SHALL still report that lane as published rather than as having pushed itself

### Requirement: The overview is one line per lane
Each sweep SHALL report one line per lane giving the change, the executor, the agent status, completed and total tasks, the number of lane commits, whether the working tree is clean, and the pull request if one exists. It SHALL NOT print raw JSON.

#### Scenario: Four lanes
- **WHEN** four lanes exist
- **THEN** the sweep output SHALL contain exactly four lane lines

### Requirement: A parked goal is resumed only when nobody parked it on purpose
When the lane's executor reports its goal as limited by usage, the supervisor SHALL resume it at most once per sweep. When the goal is paused and the supervisor has no record of pausing it, or when the goal is blocked or limited by a budget, the supervisor SHALL escalate and SHALL NOT resume it. Goal states that an executor does not report SHALL NOT be inferred from the pane.

#### Scenario: Usage limit hit
- **WHEN** a lane's goal is reported as usage-limited
- **THEN** the supervisor SHALL send one resume in that sweep and re-evaluate on the next sweep

#### Scenario: Goal paused by an unknown hand
- **WHEN** a lane's goal is paused and no pause is recorded for it
- **THEN** the supervisor SHALL NOT resume it and SHALL report the lane as waiting on the user

#### Scenario: Pi goal blocked
- **WHEN** a pi lane's goal is reported as blocked
- **THEN** the supervisor SHALL escalate the lane with the recorded reason and SHALL NOT resume it
