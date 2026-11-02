## MODIFIED Requirements

### Requirement: The review request tells the reviewer what they are reading
The review request body SHALL contain the final state of the task list, the verification result for each task, any recorded deviation, and a provenance line naming the change, the lane's executor with its version, and the approval posture it ran under.

#### Scenario: Reviewer opens the review request
- **WHEN** a review request is opened by the orchestrator
- **THEN** its body SHALL state which executor wrote the code and under which posture

#### Scenario: Pi lane published
- **WHEN** a verified pi lane is published
- **THEN** its review request and its `verify.md` SHALL name pi with its version, the goal extension version, and the pi posture, and SHALL NOT name codex
