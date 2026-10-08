# Spec Delta

## Purpose

Specifies how one round runs and ends: the phase order, the three outcomes plus scorer error, the append-only git log with reverts, the baseline, scorer version switches, the edit boundary, stop conditions, and interruption and resumption.

## ADDED Requirements

### Requirement: Preconditions before a round
Before starting a round the runner SHALL verify that the working tree is clean, that the current branch is `research/<research-name>` (creating it from HEAD when absent), and that every subject listed in the subject's `depends_on` has at least one kept checkpoint. A working tree whose only changes are under `autoresearch/` SHALL be committed by the runner as `ar scorer <subject>` before the round starts; any other dirty state SHALL stop the runner with the offending paths listed.

#### Scenario: Scorer edited by hand
- **WHEN** the only uncommitted change is `autoresearch/subjects/cases/score`
- **THEN** the runner commits it as `ar scorer cases` and then starts the round

#### Scenario: Unrelated dirty file
- **WHEN** `src/x.py` has uncommitted changes
- **THEN** the runner does not start a round and names `src/x.py`

#### Scenario: Dependency unmet
- **WHEN** `impl` declares `depends_on: ["cases"]` and `cases` has no kept checkpoint
- **THEN** the runner refuses to run `impl` and says which dependency is unmet

### Requirement: Baseline round
When a subject has no checkpoint under the scorer's current version, the runner SHALL first run gate and score on HEAD without invoking the harness and record it as round 0 (or the next round number after a version switch) with status `keep`. A failing gate at baseline SHALL stop the runner.

#### Scenario: First run
- **WHEN** `run cases` is invoked on a subject with no checkpoints
- **THEN** checkpoint `cases-0-<hex>` is recorded from HEAD before any harness call and becomes the best

### Requirement: Round phases in fixed order
A round SHALL proceed: build prompt → run harness → boundary check → gate → score → commit → decide outcome → revert when required → write checkpoint → regenerate report → evaluate stop conditions. Each of agent, gate and score SHALL be timed and recorded in `timings_ms`.

#### Scenario: Normal keep
- **WHEN** the harness exits 0, no locked path changed, gate passes, and the score exceeds the best under the same version
- **THEN** the round commit stays on the branch and the checkpoint status is `keep`

### Requirement: Locked paths cannot be changed by the agent
After the harness returns, the runner SHALL compare the changed paths (tracked and untracked) against the subject's locked patterns, which always include `autoresearch/**`. Any match SHALL make the round outcome `crash` with reason `locked:<path>` before gate or score run.

#### Scenario: Agent edits the scorer
- **WHEN** the harness modified `autoresearch/subjects/cases/score`
- **THEN** the round is a crash with reason `locked:autoresearch/subjects/cases/score`, the gate and scorer do not run, and the change is reverted

### Requirement: Every round is one append-only commit
The runner SHALL commit all changes after the harness with `--allow-empty` and the message `ar <checkpoint-id>`. For outcomes `discard`, `crash` and `error` the runner SHALL revert that commit with `git revert`, never with `git reset`; when the round commit introduced no changes it SHALL skip the revert. A failed revert SHALL stop the runner and report; it SHALL NOT reset or stash.

#### Scenario: Discard is reverted but kept in history
- **WHEN** a round scores below the best
- **THEN** `git log` shows the round commit followed by its revert commit, and HEAD's tree equals the best checkpoint's tree

#### Scenario: Empty round
- **WHEN** the harness changed nothing and the score equals the best
- **THEN** an empty commit `ar <id>` is created, no revert is made, and the checkpoint status is `discard`

### Requirement: Outcome decision
Under the same scorer version, a score strictly greater than the best SHALL be `keep`; equal or lower SHALL be `discard`. A gate failure or boundary violation SHALL be `crash`. A scorer failure SHALL be `error`. `error` SHALL NOT increment the consecutive-discard counter, and `keep` SHALL reset both the consecutive-discard and consecutive-error counters.

#### Scenario: Equal score
- **WHEN** the score equals the best exactly
- **THEN** the outcome is `discard`

#### Scenario: Scorer broken twice
- **WHEN** two consecutive rounds end in `error`
- **THEN** the consecutive-discard counter is unchanged and the consecutive-error counter is 2

### Requirement: Scorer version switch resets comparison
When the version reported by the scorer differs from the version of the current best, the runner SHALL record the round as `keep` regardless of its score, SHALL make it the best for the new version, and SHALL keep all older checkpoints untouched.

#### Scenario: Version bump lowers the score
- **WHEN** best is 143.6 under `5.0.0` and the round scores 140.3 under `5.1.0`
- **THEN** the round is `keep` and the best becomes 140.3 under `5.1.0`

### Requirement: Stop conditions
The runner SHALL stop after a round when any configured condition is met: `max_rounds`, `max_consecutive_discards`, `max_consecutive_errors`, `target_score` reached or exceeded, `budget.minutes` elapsed since the run started, or `budget.tokens` exceeded by the sum of all usage fields recorded in this run. The reason SHALL be written to the subject index and printed.

#### Scenario: Five discards in a row
- **WHEN** `max_consecutive_discards` is 5 and the fifth consecutive discard is recorded
- **THEN** the runner exits with stop reason `consecutive_discards`

#### Scenario: Token budget
- **WHEN** the run's accumulated usage exceeds `budget.tokens` after a kept round
- **THEN** the runner exits with stop reason `budget.tokens` and the kept round remains kept

### Requirement: Interruption and resumption
On the first SIGINT the runner SHALL let the current harness finish, complete the round normally, then exit; a second SIGINT SHALL kill the harness process group and exit without recording a checkpoint. A later `run` SHALL resume from the subject index when HEAD equals the best checkpoint's commit or the end of its revert chain, and SHALL refuse with an explanation when the working tree is dirty or HEAD does not match.

#### Scenario: Graceful interrupt
- **WHEN** SIGINT arrives while the harness is running
- **THEN** the round still ends with a checkpoint record and a commit, and the runner exits afterwards

#### Scenario: Resume after kill
- **WHEN** the previous run was killed mid-round leaving uncommitted agent changes
- **THEN** `run` refuses, lists the leftover paths, and suggests committing or discarding them by hand
