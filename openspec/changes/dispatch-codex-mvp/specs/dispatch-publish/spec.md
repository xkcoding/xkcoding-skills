# Spec Delta

## Purpose

Ensures that only independently verified work leaves the machine, records that verification inside the change itself, and hands merging, archiving and cleanup back to the human.

## ADDED Requirements

### Requirement: A lane's claim is verified independently before anything is published
When a lane claims completion, the orchestrator SHALL itself, inside the lane's worktree, re-run the verification stated in each task, run strict OpenSpec validation of the change, and confirm that the working tree is clean and that the lane added commits beyond the propose commit. It SHALL NOT accept the lane's own statement, the agent status, or the goal status as proof.

#### Scenario: A task's verification fails
- **WHEN** one task's stated verification does not pass when re-run by the orchestrator
- **THEN** nothing SHALL be pushed, the lane SHALL receive a corrective prompt naming the failed check, and the lane SHALL remain open

#### Scenario: Every check passes
- **WHEN** all re-run verifications pass, validation succeeds and the tree is clean
- **THEN** the lane SHALL be treated as verified at its current head commit

### Requirement: Verification is recorded in the change
For a verified lane the orchestrator SHALL write `verify.md` in the change directory and commit it on the lane branch. The file SHALL record the verified commit, the result of each task's verification, any deviation from the plan that the lane reported, and the executor, its version and its approval posture.

#### Scenario: Record written before publishing
- **WHEN** a lane is verified
- **THEN** `verify.md` SHALL exist on the lane branch before the branch is pushed

#### Scenario: Commits arrive after verification
- **WHEN** the lane branch gains commits other than the verification record after it was verified
- **THEN** the earlier verification SHALL be treated as stale and SHALL be repeated before publishing

### Requirement: A lane that published itself is flagged
Before pushing, the orchestrator SHALL check whether the lane branch already exists on the remote. When it exists and the orchestrator did not push it, the lane SHALL be flagged to the user as having crossed its boundary and SHALL NOT be reported as published by the orchestrator.

#### Scenario: Lane pushed its own branch
- **WHEN** the lane branch is present on the remote before the orchestrator's first push
- **THEN** the orchestrator SHALL surface the violation and wait for the user's decision

### Requirement: Publishing pushes one branch and opens one review request
For a verified lane the orchestrator SHALL push exactly the lane branch by explicit refspec, without force and without skipping hooks, and SHALL then open one review request (a pull request or merge request) against the base branch. The text of the review request SHALL be written to a file before any tool is asked to open it. It SHALL reuse an existing review request for the branch instead of creating another. Review requests SHALL be opened as drafts unless `--ready` was given.

#### Scenario: Review request already exists
- **WHEN** a review request for the lane branch already exists
- **THEN** the orchestrator SHALL record it and SHALL NOT create a second one

### Requirement: The review-request tool follows the remote, not an assumption about GitHub
Pushing SHALL use plain git and SHALL NOT depend on any forge tool. The tool that opens the review request SHALL be chosen from the host of the `origin` remote: `gh` for GitHub, `glab` for GitLab, and for any other host the choice the user made for that host. When the chosen tool is a forge command-line tool, the orchestrator SHALL invoke it with fully explicit arguments so that it cannot stop at an interactive prompt. When the choice is a tool or skill of the agent runtime, the orchestrator SHALL push, hand that tool the remote, source branch, target branch, title, body file and draft flag, and record the address of the review request it returns.

#### Scenario: Repository hosted on GitLab
- **WHEN** the `origin` host is a GitLab instance and `glab` is authenticated for it
- **THEN** the review request SHALL be opened as a merge request through `glab`

#### Scenario: Repository hosted on an internal forge
- **WHEN** the user chose a merge-request skill of the runtime for the `origin` host
- **THEN** the orchestrator SHALL push the branch, pass the hand-off fields to that skill, and record the returned address so that the lane overview shows it

#### Scenario: Unknown host, nothing remembered
- **WHEN** the `origin` host is neither GitHub nor GitLab and no choice is remembered for it
- **THEN** the user SHALL be asked once, within the dispatch confirmation, which tool opens review requests for that host

### Requirement: The choice of review-request tool is remembered per host
The user's choice for a host SHALL be stored outside the repository, keyed by host, and SHALL apply to every repository on that host without asking again. The user SHALL be able to change or forget it.

#### Scenario: Second repository on the same internal host
- **WHEN** a repository on a host with a remembered choice is dispatched
- **THEN** the user SHALL NOT be asked again and the remembered tool SHALL be used

#### Scenario: Choice forgotten
- **WHEN** the user asks to forget the choice for a host
- **THEN** the next dispatch on that host SHALL ask again

#### Scenario: Non-fast-forward rejection
- **WHEN** the push is rejected as non-fast-forward
- **THEN** the orchestrator SHALL stop, surface the rejection, and SHALL NOT force the push

### Requirement: The review request tells the reviewer what they are reading
The review request body SHALL contain the final state of the task list, the verification result for each task, any recorded deviation, and a provenance line naming the change, the executor with its version, and the approval posture it ran under.

#### Scenario: Reviewer opens the review request
- **WHEN** a review request is opened by the orchestrator
- **THEN** its body SHALL state that the code was written by codex and under which posture

### Requirement: Publishing degrades with a stated reason
When there is no remote, the orchestrator SHALL leave the lane verified and report it as local only. When the forge tool chosen for the host is missing or unauthenticated, or `--no-pr` was given, it SHALL push, state the reason, and give the user what is needed to open the review request themselves. When the base branch does not exist on the remote, it SHALL push and SHALL NOT open a review request against a substituted base. Publishing SHALL be safe to repeat, and after three failed attempts the orchestrator SHALL stop retrying and hand the command to the user.

#### Scenario: Forge tool unauthenticated
- **WHEN** a lane is verified and the forge tool for its host is not authenticated
- **THEN** the branch SHALL be pushed and the user SHALL be given the reason and the pieces needed to open the review request

#### Scenario: Repeated publish failure
- **WHEN** opening the review request has failed three times
- **THEN** the orchestrator SHALL stop retrying, record the last error as the reason, and print the command

### Requirement: Merging, archiving and cleanup stay with the human
The dispatch skill SHALL NOT merge a review request, archive a change, remove a worktree, delete a branch, force-push, or push the base branch. The final report SHALL print the commands for these steps, in an order that is safe to run, for the user to execute after review.

#### Scenario: All lanes published
- **WHEN** every lane is published
- **THEN** the report SHALL print the cleanup, merge and archive commands and SHALL execute none of them

#### Scenario: User asks the dispatcher to archive
- **WHEN** the user asks the dispatch skill to archive a change
- **THEN** the skill SHALL NOT archive it and SHALL point the user to the project's own OpenSpec archive workflow

### Requirement: Rework reopens the lane through the task list
When review requires changes, adding or unticking tasks in the lane's copy of `tasks.md` SHALL make the lane eligible for continuation. The next sweep SHALL resume it, its earlier verification SHALL become stale, and the same review request SHALL receive the new commits once the lane is verified again.

#### Scenario: Reviewer requests a change
- **WHEN** a task is added to the lane's `tasks.md` after its review request was opened
- **THEN** the next sweep SHALL treat the lane as unfinished, and publishing SHALL wait for a new verification
