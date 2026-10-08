# Spec Delta

## Purpose

Provides the single human-facing view of a research: a static report generated from the ledger, showing every subject's progress, each checkpoint's measurements, and the agent's own account of each round.

## ADDED Requirements

### Requirement: Report is generated from the ledger only
The report SHALL be a single self-contained HTML file at `<research>.ar/report/index.html`, generated from the checkpoint files and subject indexes without network access or external assets. The runner SHALL regenerate it after every round, and the `report` command SHALL regenerate it on demand.

#### Scenario: Offline viewing
- **WHEN** the report is opened from disk without network access
- **THEN** all subjects, charts and checkpoint details render

### Requirement: Subject summary line
For each subject the report SHALL show, in this order: number of checkpoints, kept, discarded, crashed, errored, best score with its round number, scorer version range (first → latest), and the time of the last checkpoint.

#### Scenario: Summary after a run
- **WHEN** `cases` has 22 checkpoints with 20 kept, 2 discarded, best 155.95 at round 21 and versions 5.0.0 then 5.1.0
- **THEN** the summary line reads `22 checkpoints · 20 kept · 2 discarded · 0 crashed · 0 errors · best 155.95 at #21 · score v5.0.0 → v5.1.0 · updated <time>`

### Requirement: Score chart with version bands
Each subject SHALL have a score-over-round chart in which kept checkpoints form the line, discarded and errored rounds are drawn as hollow points at their score, crashed rounds as marks without a score, and each scorer version occupies a visually distinct band labelled with the version.

#### Scenario: Version change mid-research
- **WHEN** rounds 0–8 use version 5.0.0 and rounds 9–21 use 5.1.0
- **THEN** the chart shows two labelled bands and the line restarts at round 9

### Requirement: Checkpoint detail
Selecting a checkpoint SHALL show every field of its record: status, score and version, timestamp, commit (and revert commit when present), per-phase timings including any scorer-reported sub-phases, the four usage numbers, harness type and model, the agent's note, the changed files, the reason for crash or error, the `details` object rendered as a table, and the `remaining` list collapsed by default with its count visible.

#### Scenario: Viewing a crash
- **WHEN** a crashed checkpoint is selected
- **THEN** the detail shows the gate reason and the text `No measurement recorded` in place of score and details

#### Scenario: Viewing remaining work
- **WHEN** a kept checkpoint with 10 remaining items is selected
- **THEN** the detail shows `10 remaining` and expands to list them
