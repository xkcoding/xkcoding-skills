## ADDED Requirements

### Requirement: A parked goal is resumed only when nobody parked it deliberately
When the lane's executor reports its goal as limited by usage, the supervisor SHALL resume it at most once per sweep. When the goal is paused and the supervisor has no record of pausing it, or when the goal is blocked or limited by a budget, the supervisor SHALL escalate and SHALL NOT resume it. Goal states that an executor does not report SHALL NOT be inferred from the pane.

#### Scenario: Usage limit hit
- **WHEN** a lane's goal is reported as usage-limited
- **THEN** the supervisor SHALL send one resume in that sweep and re-evaluate on the next sweep

#### Scenario: Goal paused by an unknown hand
- **WHEN** a lane's goal is paused and no pause is recorded for it
- **THEN** the supervisor SHALL NOT resume it and SHALL report the lane as waiting on the user

#### Scenario: omp goal blocked
- **WHEN** an omp lane's goal is reported as blocked
- **THEN** the supervisor SHALL escalate the lane with the recorded reason and SHALL NOT resume it

## REMOVED Requirements

### Requirement: A parked goal is resumed only when nobody parked it on purpose
**Reason**: Its scenarios were written for the retired pi executor; the requirement continues under a new name with omp scenarios.
**Migration**: See "A parked goal is resumed only when nobody parked it deliberately".
