# Spec Delta

## Purpose

Defines where a research lives on disk: the definition directory inside the target repository, the ledger directory beside it, the checkpoint record, and the contracts of the score and gate executables that every subject provides.

## ADDED Requirements

### Requirement: A research is defined inside the target repository
A research SHALL be defined by `autoresearch/research.json` in the target repository root, declaring the research name, a description, the score `direction` (`max` by default, or `min`), harness defaults, and an ordered list of subjects. Keys the runner does not know SHALL be refused with the unknown and the accepted keys named, except keys starting with `_`, which are documentation and SHALL be ignored. Each subject SHALL have a directory `autoresearch/subjects/<name>/` containing `program.md`, an executable `score`, and an executable `gate`. The runner SHALL refuse to start when any of these is missing and SHALL name the missing item.

#### Scenario: Complete definition
- **WHEN** `research.json` lists subject `cases` and `autoresearch/subjects/cases/` contains `program.md`, `score` and `gate`
- **THEN** the runner accepts the subject as runnable

#### Scenario: Missing gate
- **WHEN** `autoresearch/subjects/cases/gate` does not exist or is not executable
- **THEN** the runner refuses to run `cases` and reports `gate` as missing

#### Scenario: Misspelt stop condition
- **WHEN** a subject carries `max_consecutive_discard` (singular)
- **THEN** the runner refuses to start, names the key and lists the keys it accepts

### Requirement: The ledger lives beside the repository
All checkpoint records, per-round artifacts, run logs and the report SHALL be written under `<research-name>.ar/` located in the parent directory of the repository root, unless `research.json` sets `ar_dir`. The runner SHALL NOT write any file into the repository other than through the agent's own changes and the commits it creates.

#### Scenario: Default ledger location
- **WHEN** the repository is at `/work/nano` and the research is named `nano-autoresearch`
- **THEN** checkpoints are written under `/work/nano-autoresearch.ar/researches/<subject>/`

#### Scenario: Repository stays clean of ledger files
- **WHEN** a round completes
- **THEN** `git status --porcelain` in the repository is empty and no ledger file appears in the commit

### Requirement: Score executable contract
The subject's `score` executable SHALL be run from the repository root after the gate passes. It SHALL print a single JSON object to stdout with a numeric `score`, a non-empty string `version`, and MAY include `details` (any JSON), `remaining` (array of strings) and `timings_ms` (object of numbers). The runner SHALL treat a non-zero exit code, missing `score` or `version`, or unparsable stdout as a scorer error for that round, not as a crash or discard.

#### Scenario: Valid score output
- **WHEN** `score` exits 0 and prints `{"score": 12.5, "version": "1.0.0", "remaining": ["a", "b"]}`
- **THEN** the round is scored 12.5 under version `1.0.0` with two remaining items

#### Scenario: Scorer prints prose
- **WHEN** `score` exits 0 but stdout is not a JSON object
- **THEN** the round outcome is `error` and the stdout is preserved in the round's artifacts

#### Scenario: Scorer declares a new version
- **WHEN** the best checkpoint has version `1.0.0` and `score` now reports version `1.1.0`
- **THEN** the round is not compared against the `1.0.0` best and becomes the first checkpoint of version `1.1.0`

### Requirement: Gate executable contract
The subject's `gate` executable SHALL be run from the repository root before scoring. Exit code 0 SHALL mean pass; any other exit code SHALL mean the round crashed. Its stdout and stderr SHALL be saved with the round's artifacts and the last lines SHALL be recorded as the crash reason.

#### Scenario: Gate fails
- **WHEN** `gate` exits 1 printing `Formatting issues found`
- **THEN** the round outcome is `crash`, no score is recorded, and the reason contains `Formatting issues found`

### Requirement: Checkpoint record
Every round, including the baseline, SHALL produce one JSON file `researches/<subject>/<checkpoint-id>.json` containing: `id`, `n`, `subject`, `status` (`keep` | `discard` | `crash` | `error`), `at`, `commit`, `reverted_by`, `score`, `version`, `best_before`, `details`, `remaining`, `timings_ms` (at least `agent`, `gate`, `score`), `usage` (`input`, `output`, `cache_read`, `cache_write`, each a number or null), `harness` (type, model, session or run id, turns, exit code), `note`, `changed_files`, `reason`. The checkpoint id SHALL be `<subject>-<n>-<6 hex>` and SHALL appear verbatim in the round's commit message.

#### Scenario: Keep record
- **WHEN** round 21 of `cases` is kept with score 155.95
- **THEN** `researches/cases/cases-21-<hex>.json` exists with `status: "keep"`, `score: 155.95`, and the commit whose message is `ar cases-21-<hex>`

#### Scenario: Crash record
- **WHEN** a round crashes at the gate
- **THEN** its record has `status: "crash"`, `score: null`, a non-empty `reason`, and `reverted_by` set to the revert commit unless the round commit was empty

### Requirement: Subject index is derivable
Each subject SHALL have `researches/<subject>/index.json` holding only derived summary state (next round number, best score and id, current version, consecutive discard and error counts, stop reason, totals). Deleting it and re-running `status` SHALL reconstruct identical content from the checkpoint files.

#### Scenario: Index rebuilt
- **WHEN** `index.json` is deleted and `status` runs
- **THEN** `index.json` is recreated and its `best` and `n_next` match the checkpoint files
