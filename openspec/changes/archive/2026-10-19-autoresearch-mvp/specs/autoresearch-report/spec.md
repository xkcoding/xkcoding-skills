# Spec Delta

## Purpose

Provides the single human-facing view of a research: a static report generated from the ledger, and the same page served live, showing where a subject stands, what every round did, and what it cost. The page states facts and draws no conclusions; the judgement about what to do next stays with the person and the session.

## ADDED Requirements

### Requirement: Report is generated from the ledger only
The report SHALL be a single self-contained HTML file at `<research>.ar/report/index.html`, generated from the checkpoint files, the subject indexes, `run.lock` and the per-round artifacts, with the data and the charting library embedded, so that it renders from disk without network access or external assets. The runner SHALL regenerate it when a round starts and when it ends; the `report` command SHALL regenerate it on demand; `serve` SHALL render the same page on every request.

#### Scenario: Offline viewing
- **WHEN** the report is opened from disk without network access
- **THEN** all subjects, charts and round details render, and the top bar says it is a static snapshot

### Requirement: Served report refreshes itself
When the page is loaded from `serve`, it SHALL poll `/data.json` (every 5 seconds while a run is in progress, every 10 seconds otherwise), re-render in place only when the data changed, keep expanded rows across refreshes, and show when it last heard from the server; a failed poll SHALL be shown as a lost connection, not as stale data presented as current.

#### Scenario: Round completes while the page is open
- **WHEN** a checkpoint is written while the served page is open
- **THEN** within the polling interval the new round appears in the list and the counts update without a page reload

#### Scenario: Server stopped
- **WHEN** the serve process is stopped while the page is open
- **THEN** the top bar switches to "连接已断开" with the time of the last successful poll

### Requirement: Visual system
The page SHALL use one token set (`--ar-*`: colours, type scale 28 / 20 / 16 / 14 / 13 / 12 with key numbers at 40, spacing on a 4 px scale, radii, shadows) and a fixed set of components (tag, table, card, tabs, stat, matrix cell, code, diff), with no colour literal outside the token block. Colour SHALL express meaning only: keep green, crash red, error amber, discard neutral, deltas green or red by direction; everything else neutral. Text SHALL be Chinese product copy; keep / discard / crash / error keep their ledger names.

#### Scenario: Outcome colours
- **WHEN** a subject has kept, discarded, crashed and errored rounds
- **THEN** the matrix cells and the row tags use the four outcome colours and nothing else on the page uses them for another meaning

### Requirement: Page structure per subject
For each subject (tabs when there are several, the dependency named on the tab) the page SHALL show, in this order: a header with the subject name, its state tag (运行中 / 已停止 / 空闲), harness, round count, scorer version and last update; action lines that appear only when true (a round in progress with its elapsed time and the median round time; a stop condition with the limit to raise; a scorer edited since the best; unreadable checkpoint files; in a static snapshot, a round older than `timeout_sec` with no update since); the conclusion row — best score with the direction, baseline → best with the relative change, and the number of remaining items as a link to its card; a stat strip — rounds with outcome counts, consecutive discards against the limit, cost with the median per round, time with the median agent time, tokens; the outcome matrix (one cell per round, clickable); the score chart; two cards — the latest round (outcome, delta, changed files, the agent's note) and the remaining items of the best checkpoint; the best checkpoint's `details` as tables; the round list.

#### Scenario: Nothing exceptional
- **WHEN** a subject is idle, not stopped, and its scorer is unchanged since the best
- **THEN** no action line is shown and the conclusion row is the first block under the header

#### Scenario: Stopped subject
- **WHEN** `cases` stopped with reason `consecutive_discards` at limit 8
- **THEN** the action line reads `已停止：连续 discard 到上限（8 / 8）` and names `max_consecutive_discards` as what to raise

### Requirement: Score chart
The chart SHALL be drawn with the embedded Apache ECharts (version recorded in `scripts/vendor/README.md`): kept checkpoints form a monotone curve restarted at every scorer version, discarded rounds are hollow points at their score, crashed and errored rounds are dashed vertical markers labelled with the outcome, each scorer version is a labelled band, and two aligned bar rows below show each round's agent time and cost with their medians. The baseline SHALL always be drawn; the y axis SHALL be logarithmic (base 2, fitted to the data) when every score is positive and linear otherwise. There SHALL be no zoom controls. Hovering a point SHALL show the round, outcome, score, delta, time, cost and the first line of the note; clicking SHALL open that round's row.

#### Scenario: Far baseline
- **WHEN** `compress` has baseline 105248 and later scores between 27869 and 38694
- **THEN** the curve shows all of them on a log axis without any point left off the chart

#### Scenario: Scores that can be negative
- **WHEN** a subject's scores include negative values
- **THEN** the y axis is linear and the chart still draws every round

### Requirement: Round list and detail
Rounds SHALL be listed newest first, one row each: number, outcome tag, score, delta against the best before it, agent time, cost, first line of the note or reason. A row SHALL expand in place to show the agent's note in full; the round's patch from `changes.patch` (first 20 KB, with the path to the rest) or a sentence saying no patch was saved; the numeric leaves of `details` compared with the previous best under the same version, with deltas; phase timings including scorer sub-phases; the four usage numbers; harness type, model, turns, cost and cut-off; commit and revert shas; and a link to the artifacts directory. A crashed or errored round SHALL show its reason and where the gate, scorer and harness outputs are, with `未评分` in place of the score.

#### Scenario: Viewing a kept round
- **WHEN** round 29 of `codec` is expanded
- **THEN** the detail shows the diff of `codec.py` and a table where `total` reads 27883 → 27869 with delta −14

#### Scenario: Viewing a crash
- **WHEN** a crashed checkpoint is expanded
- **THEN** the detail shows the gate reason, `未评分` in place of the score, and the artifacts path for `gate.out`
