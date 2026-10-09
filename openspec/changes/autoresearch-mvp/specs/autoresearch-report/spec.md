# Spec Delta

## Purpose

Provides the single human-facing view of a research: a static report generated from the ledger, showing every subject's progress, each checkpoint's measurements, and the agent's own account of each round.

## ADDED Requirements

### Requirement: Report is generated from the ledger only
The report SHALL be a single self-contained HTML file at `<research>.ar/report/index.html`, generated from the checkpoint files and subject indexes without network access or external assets. The runner SHALL regenerate it after every round, and the `report` command SHALL regenerate it on demand.

#### Scenario: Offline viewing
- **WHEN** the report is opened from disk without network access
- **THEN** all subjects, charts and checkpoint details render

### Requirement: Subject summary
The report's text SHALL be Chinese. For each subject it SHALL show a summary line in this order: number of checkpoints, kept, discarded, crashed, errored, best score with its round number, scorer version range (first → latest), and the time of the last checkpoint; the `status` command SHALL print the same facts in the same order as `summary`. Above the line the report SHALL show state cards: best score and round, distance from the baseline, outcome counts, cost (priced rounds, median per round, tokens), time (median agent duration, last update), and run state — running (read from `run.lock`), stopped with the reason and what to raise, or idle with each counter against its limit.

#### Scenario: Summary after a run
- **WHEN** `cases` has 22 checkpoints with 20 kept, 2 discarded, best 155.95 at round 21 and versions 5.0.0 then 5.1.0
- **THEN** the report's summary line reads `22 个 checkpoint · 20 keep · 2 discard · 0 crash · 0 error · 最佳 155.95（#21） · 打分器 v5.0.0 → v5.1.0 · 更新于 <time>` and `status` prints `22 checkpoints · 20 kept · 2 discarded · 0 crashed · 0 errors · best 155.95 at #21 · score v5.0.0 → v5.1.0 · updated <time>`

#### Scenario: Stopped subject
- **WHEN** `cases` stopped with reason `consecutive_discards`
- **THEN** its state card says it is stopped, shows the consecutive-discard count against the limit, and says the limit in `research.json` is what to raise

### Requirement: The best checkpoint is explained
For each subject the report SHALL show, without any click, how the best score was composed (its `details`) and what the scorer still lists as missing (its `remaining`), so that the person can tell whether the loop is working on the right things.

#### Scenario: Empty remaining
- **WHEN** the best checkpoint's `remaining` is empty
- **THEN** the panel says so and that the scorer sees nothing left to do under this version

### Requirement: Score chart with version bands
Each subject SHALL have a score-over-round chart in which kept checkpoints form a smooth monotone curve that never overshoots the points, restarted at every scorer version; discarded rounds are hollow points at their score, crashed and errored rounds are marks at the bottom without a score, and each scorer version occupies a visually distinct band labelled with the version. The baseline (#0) SHALL be left off the axis by default when it is farther from the median of the other scores than three times their spread, with its value listed as off-chart and a toggle to show it.

#### Scenario: Version change mid-research
- **WHEN** rounds 0–8 use version 5.0.0 and rounds 9–21 use 5.1.0
- **THEN** the chart shows two labelled bands and the curve restarts at round 9

#### Scenario: Baseline far from the rest
- **WHEN** `compress` has baseline 105248 and every later score lies between 27869 and 38694
- **THEN** the chart opens without #0, lists `#0 = 105248` as off-chart, and a checkbox brings it back

### Requirement: Checkpoint detail
Each round SHALL be one row that expands in place to show every field of its record: status, score and version with the best before it, timestamp, commit (and revert commit when present), per-phase timings including any scorer-reported sub-phases, the four usage numbers, harness type and model, the agent's note, the changed files, the reason for crash or error, the `details` object rendered as nested tables, and the `remaining` list with its first items shown and the rest behind an expander that states the total.

#### Scenario: Viewing a crash
- **WHEN** a crashed checkpoint is selected
- **THEN** the detail shows the gate reason and `没有测量` in place of score and details

#### Scenario: Viewing remaining work
- **WHEN** a kept checkpoint with 10 remaining items is expanded
- **THEN** the first 8 are listed and `展开全部 10 条` reveals the rest
