# Spec Delta

## Purpose

Describes the skill that lets a person set up a research, start and supervise the loop, and intervene by editing the scorer or the program, without the Claude Code session itself taking part in any round.

## ADDED Requirements

### Requirement: Sub-commands
The skill SHALL route `init`, `run`, `status`, `report` and `doctor`. `init` SHALL scaffold a research definition; `run` SHALL start the runner for one subject; `status` SHALL summarise every subject from the ledger; `report` SHALL regenerate and locate the report; `doctor` SHALL check the environment. Invoking the skill without a sub-command SHALL show the sub-command table and the current status when a research exists.

#### Scenario: Bare invocation in a repository with a research
- **WHEN** `/autoresearch` is invoked in a repository containing `autoresearch/research.json`
- **THEN** the sub-command table and each subject's summary line are shown

### Requirement: Init scaffolds a complete, runnable definition
`init` SHALL create `autoresearch/research.json` and, for each requested subject, `program.md`, `score` and `gate` as working templates whose fields and placeholders are documented inline. The scaffolded `score` SHALL already emit a valid score object and the scaffolded `gate` SHALL already exit 0, so that `run` works before the person edits anything. `init` SHALL NOT overwrite existing files.

#### Scenario: Scaffold then run
- **WHEN** `init` creates subject `cases` in an empty repository and `run cases` is invoked with the `shell` adapter
- **THEN** a baseline checkpoint is recorded without any manual edit

#### Scenario: Existing definition
- **WHEN** `autoresearch/subjects/cases/score` already exists
- **THEN** `init` leaves it unchanged and reports it as skipped

### Requirement: Init guides the scorer design
During `init` the skill SHALL walk the person through the questions that determine whether the research can work before any round runs: what is measured and how it becomes one number, what counts as a crash, what the `remaining` list contains, which paths the agent may edit, and when to stop. It SHALL point out that dimensions without a score term receive no agent effort and that a scorer insensitive to the intended change produces fake progress.

#### Scenario: Scorer without a remaining list
- **WHEN** the person's scorer design has no way to express what is still missing
- **THEN** the skill explains that the next round will have no state to act on and asks how the gap can be derived from the measurement

### Requirement: Run never participates in the round
`run` SHALL start the runner as a separate process and SHALL NOT read, edit or score anything on the subject's behalf inside the Claude Code session. When started in the background it SHALL tell the person where the run log is and how to stop it.

#### Scenario: Background run
- **WHEN** the person asks to run 20 rounds in the background
- **THEN** the runner is started detached, the log path under `<research>.ar/runs/` is shown, and the session returns immediately

### Requirement: Doctor checks by executing
`doctor` SHALL determine the availability of `python3`, `git`, `claude` and `codex` by executing their version commands, SHALL report the repository state (clean tree, branch, presence of a research definition), and SHALL only report; it SHALL NOT install, log in or create anything.

#### Scenario: Codex not installed
- **WHEN** `codex` is absent
- **THEN** doctor reports it as unavailable and still reports `claude` as available if it runs

### Requirement: Human intervention is through files, not the session
To change the research direction the skill SHALL direct the person to edit `program.md`, and to change what is measured to edit `score` and bump its reported version; it SHALL explain that the runner picks up both at the next round and that a version bump starts a new comparison baseline.

#### Scenario: Person wants to penalise redundancy
- **WHEN** the person says redundant cases should cost points
- **THEN** the skill proposes the change to `score`, reminds them to bump `version`, and does not touch the running loop
