## ADDED Requirements

### Requirement: Pi adapter
The `pi` adapter SHALL invoke the pi CLI once per round in JSON event mode without saving a session, with the repository root as working directory, and with discovery of the user's global skills, extensions and prompt templates disabled so that a round sees only its own prompt and the repository. The model and credentials SHALL come from pi's own configuration; when `harness.model` is set the adapter SHALL pass it as pi's model selection. The adapter SHALL take the agent's text from the last assistant message, SHALL sum usage over all assistant messages of the run, and SHALL record the summed cost. Because pi exits 0 when the model call fails, a final assistant message whose stop reason is `error` SHALL be a harness failure carrying the error message, regardless of the exit code. pi has no turn cap, so a subject whose harness is `pi` and that sets `max_turns` or `max_budget_usd` SHALL be refused before any round starts.

#### Scenario: Pi round
- **WHEN** pi exits 0 and its event stream contains three assistant messages, the last ending with stop reason `stop`
- **THEN** the checkpoint's `note` is the text of the last assistant message, its four usage numbers are the sums over the three messages, and `harness.type` is `pi`

#### Scenario: Authentication failure with exit code 0
- **WHEN** pi exits 0 but its last assistant message has stop reason `error` and error message `401: …`
- **THEN** the round outcome is `error` and its reason contains the 401 message

#### Scenario: Turn cap requested
- **WHEN** a subject with harness `pi` sets `max_turns: 40`
- **THEN** `run` refuses before the baseline and names `max_turns` as unsupported by pi

### Requirement: Goose adapter
The `goose` adapter SHALL invoke `goose run` once per round with JSON output, without saving a session, without the user's default extensions and with only the developer builtin, with the repository root as working directory. The model and credentials SHALL come from goose's own configuration; when `harness.model` is set the adapter SHALL pass it as goose's model. `max_turns` SHALL be passed to goose's turn cap; goose has no cost cap, so a subject whose harness is `goose` and that sets `max_budget_usd` SHALL be refused before any round starts. The adapter SHALL locate the JSON object in stdout even when goose prints a banner before it, SHALL take usage and cost from its cumulative metadata and the agent's text from the last assistant message. A metadata status of `error` or a non-zero exit SHALL be a harness failure with stderr preserved.

#### Scenario: Goose round with a banner on stdout
- **WHEN** goose exits 0 and stdout is a text banner followed by a JSON object whose metadata has `status: "completed"` and token totals
- **THEN** the checkpoint's usage comes from that metadata, its `note` is the last assistant text, and `harness.type` is `goose`

#### Scenario: Goose authentication failure
- **WHEN** goose exits 1 and the metadata status is `error`
- **THEN** the round outcome is `error` and `harness.err` holds goose's message

#### Scenario: Turn cap reached
- **WHEN** a goose round stops at `max_turns` and exits 0 with status `completed`
- **THEN** the round goes through boundary check, gate and score as usual and its outcome is decided by the score

### Requirement: Shell adapter runs model-free executors
The `shell` adapter SHALL run the command configured in `research.json` with the prompt on stdin and the repository root as working directory, so that the loop can be exercised without any model and custom executors can be plugged in. The agent's text SHALL be the tail of stdout, and usage SHALL be null; the adapter SHALL NOT interpret stdout as any agent CLI's output format.

#### Scenario: Toy executor
- **WHEN** the shell command is a script that edits one file and exits 0
- **THEN** the round proceeds to boundary check, gate and score exactly as with a model-backed adapter

#### Scenario: Stdout that looks like Claude Code JSON
- **WHEN** the shell command prints a Claude Code `type: result` JSON line
- **THEN** the checkpoint's `note` is the tail of stdout and its usage fields are null

## MODIFIED Requirements

### Requirement: Claude Code adapter
The `claude` adapter SHALL invoke the Claude Code CLI in non-interactive mode with JSON output, passing `max_turns`, `model` and `max_budget_usd` from `research.json` when set, SHALL remove the parent session's `CLAUDECODE` variable from the child environment, and SHALL take `usage`, the final text, the session id, turn count, cost, subtype and error flag from the JSON output. A non-JSON stdout SHALL be a harness failure with the raw output preserved. An error flag whose subtype is `error_max_turns` or `error_max_budget_usd` means one of the CLI's own caps tripped: the round SHALL still go through boundary check, gate and score, with the subtype recorded as `harness.cut_off`, even though the CLI exits non-zero in that case. Any other error flag SHALL be a harness failure. The `claude` adapter SHALL only drive Anthropic models: when the runner's environment sets `ANTHROPIC_BASE_URL`, a subject whose harness is `claude` SHALL be refused before any round starts, and the refusal SHALL name `pi` and `goose` as the harnesses for third-party models.

#### Scenario: Successful round with Claude Code
- **WHEN** the CLI exits 0 with a JSON object containing usage and result
- **THEN** the checkpoint records the four usage numbers, the session id and the result text as `note`

#### Scenario: Round cut off by the turn cap
- **WHEN** the CLI exits 1 with `is_error: true` and `subtype: "error_max_turns"`
- **THEN** the round is measured as usual, the checkpoint has `harness.cut_off: "error_max_turns"`, and its outcome is `keep` or `discard` by score, not `error`

#### Scenario: Nested invocation
- **WHEN** the runner itself was started from inside a Claude Code session
- **THEN** the child process does not inherit `CLAUDECODE` and starts normally

#### Scenario: Third-party endpoint in the environment
- **WHEN** `ANTHROPIC_BASE_URL` is set in the shell that starts `run cases` and subject `cases` uses the `claude` harness
- **THEN** the runner refuses before the baseline, naming `ANTHROPIC_BASE_URL` and pointing to the `pi` and `goose` harnesses

## REMOVED Requirements

### Requirement: Environment pass-through for endpoints and keys
**Reason**: Its only purpose was pointing the `claude` harness at third-party Anthropic-compatible endpoints, which is no longer supported. pi and goose read models and credentials from their own configuration, so the runner no longer carries keys or endpoints.
**Migration**: Delete `harness.env` from `research.json` (it is now refused as an unknown key). For a third-party model, set `"type": "pi"` or `"type": "goose"` and configure the model and key in that tool (`pi` then `/login`, or `goose configure`).

### Requirement: Shell adapter
**Reason**: Replaced by "Shell adapter runs model-free executors". The shell adapter no longer reads Claude Code's JSON from a wrapped `claude -p`, because wrapping Claude Code around a third-party model is the route this change closes.
**Migration**: A shell command that wrapped `claude -p` for a third-party model becomes `"type": "pi"` or `"type": "goose"`; one that wrapped it for an Anthropic model becomes `"type": "claude"`.
