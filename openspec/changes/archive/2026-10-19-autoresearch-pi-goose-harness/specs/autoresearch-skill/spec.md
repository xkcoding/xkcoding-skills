## ADDED Requirements

### Requirement: Doctor checks every harness by executing
`doctor` SHALL determine the availability of `python3`, `git`, `claude`, `codex`, `pi` and `goose` by executing their version commands, SHALL report the repository state (clean tree, branch, presence of a research definition), SHALL report as a problem a subject whose harness CLI is not available, SHALL report as a problem a `claude` subject while `ANTHROPIC_BASE_URL` is set, and SHALL only report; it SHALL NOT install, log in, configure a model or create anything.

#### Scenario: Codex not installed
- **WHEN** `codex` is absent
- **THEN** doctor reports it as unavailable and still reports `claude` as available if it runs

#### Scenario: Subject wants an absent harness
- **WHEN** subject `cases` uses the `goose` harness and `goose --version` cannot be executed
- **THEN** doctor lists a problem naming `cases` and `goose`, and `ok` is false

#### Scenario: Claude subject with a third-party endpoint set
- **WHEN** `ANTHROPIC_BASE_URL` is set and a subject uses the `claude` harness
- **THEN** doctor lists a problem naming the subject and `ANTHROPIC_BASE_URL`, and suggests `pi` or `goose`

## REMOVED Requirements

### Requirement: Doctor checks by executing
**Reason**: Replaced by "Doctor checks every harness by executing". The warning about endpoint models without a declared context window goes away with the `claude` harness's third-party endpoint support; doctor now also checks `pi` and `goose` and reports a `claude` subject while `ANTHROPIC_BASE_URL` is set.
**Migration**: None for users; `doctor` output gains `tools.pi` and `tools.goose`, and the window warning no longer appears.
