## ADDED Requirements

### Requirement: The review request names the executor that wrote the code
The review request body SHALL contain the final state of the task list, the verification result for each task, any recorded deviation, and a provenance line naming the change, the lane's executor with its version, and the approval posture it ran under.

#### Scenario: Reviewer opens the review request
- **WHEN** a review request is opened by the orchestrator
- **THEN** its body SHALL state which executor wrote the code and under which posture

#### Scenario: omp lane published
- **WHEN** a verified omp lane is published
- **THEN** its review request and its `verify.md` SHALL name omp with its version, the model it used, and the omp posture, and SHALL NOT name codex

## REMOVED Requirements

### Requirement: The review request tells the reviewer what they are reading
**Reason**: Its scenarios were written for the retired pi executor; the requirement continues under a new name with omp scenarios.
**Migration**: See "The review request names the executor that wrote the code".
