# Spec Delta

## Purpose

Defines the harness as a replaceable, stateless executor invoked once per round through a uniform interface, with timeouts, usage capture, isolation from the invoking session, and environment pass-through for third-party model endpoints.

## ADDED Requirements

### Requirement: Uniform harness interface
A harness adapter SHALL accept a prompt, a working directory, a timeout and an environment, and SHALL return an exit code, the agent's final text, normalized usage (`input`, `output`, `cache_read`, `cache_write`, each a number or null) and adapter metadata. The runner SHALL NOT depend on any adapter-specific field outside the adapter.

#### Scenario: Adapter without usage data
- **WHEN** the `shell` adapter runs a command that reports no token counts
- **THEN** the round's usage fields are all null and the round is otherwise processed normally

### Requirement: Each round is a fresh, stateless invocation
The harness SHALL be started as a new process for every round with only the round's prompt as input. The runner SHALL NOT pass conversation history, session ids or transcripts from earlier rounds; all state the agent needs SHALL be in the prompt (program, rules, best checkpoint details and remaining items, recent round summaries including the reason of any crashed or errored round).

#### Scenario: Second round
- **WHEN** round 2 starts
- **THEN** a new harness process is spawned and its prompt references round 1 only through the ledger-derived summary

### Requirement: Claude Code adapter
The `claude` adapter SHALL invoke the Claude Code CLI in non-interactive mode with JSON output, passing `max_turns`, `model` and `max_budget_usd` from `research.json` when set, SHALL remove the parent session's `CLAUDECODE` variable from the child environment, and SHALL take `usage`, the final text, the session id, turn count, cost, subtype and error flag from the JSON output. A non-JSON stdout SHALL be a harness failure with the raw output preserved. An error flag whose subtype is `error_max_turns` or `error_max_budget_usd` means one of the CLI's own caps tripped: the round SHALL still go through boundary check, gate and score, with the subtype recorded as `harness.cut_off`, even though the CLI exits non-zero in that case. Any other error flag SHALL be a harness failure.

#### Scenario: Successful round with Claude Code
- **WHEN** the CLI exits 0 with a JSON object containing usage and result
- **THEN** the checkpoint records the four usage numbers, the session id and the result text as `note`

#### Scenario: Round cut off by the turn cap
- **WHEN** the CLI exits 1 with `is_error: true` and `subtype: "error_max_turns"`
- **THEN** the round is measured as usual, the checkpoint has `harness.cut_off: "error_max_turns"`, and its outcome is `keep` or `discard` by score, not `error`

#### Scenario: Nested invocation
- **WHEN** the runner itself was started from inside a Claude Code session
- **THEN** the child process does not inherit `CLAUDECODE` and starts normally

### Requirement: Codex adapter
The `codex` adapter SHALL invoke `codex exec` non-interactively with the workspace-write sandbox, the repository root as working directory, JSON event output, and the final message written to a file that the adapter reads as the agent's text. Token usage SHALL be filled when the events contain it and left null otherwise. The doctor SHALL warn that an untrusted repository makes codex exit at startup. When the runner itself is inside a Codex sandbox (`CODEX_SANDBOX` set), `run`, `status`, `report` and `serve` SHALL refuse up front, naming the sandbox and the way out, because the sandbox forbids writing `.git` and the ledger and a nested `codex exec` cannot start; `doctor` SHALL report it as a problem.

#### Scenario: Runner started from inside a Codex session
- **WHEN** `run cases` is executed by Codex's shell tool under its default sandbox
- **THEN** the runner refuses before calling any harness, with `codex_sandbox` in the refusal

#### Scenario: Codex round
- **WHEN** `codex exec` exits 0 and writes the last message file
- **THEN** the checkpoint's `note` is that file's content and `harness.type` is `codex`

### Requirement: Shell adapter
The `shell` adapter SHALL run the command configured in `research.json` with the prompt on stdin and the repository root as working directory, so that the loop can be exercised without any model and custom executors can be plugged in. When the command's stdout is Claude Code's JSON output — one object, or a `stream-json` event stream whose last `type: result` object carries the same fields — the adapter SHALL take the result text, usage, session id, turn count, cost and model from it exactly as the `claude` adapter does; otherwise the agent's text is the tail of stdout.

#### Scenario: Wrapper around claude -p with stream-json
- **WHEN** the shell command prints a stream-json event stream ending in a `type: result` line
- **THEN** the checkpoint's `note` is that line's `result`, its usage numbers are filled, and `harness.model` is the model named in `modelUsage`

#### Scenario: Toy executor
- **WHEN** the shell command is a script that edits one file and exits 0
- **THEN** the round proceeds to boundary check, gate and score exactly as with a model-backed adapter

### Requirement: Timeout kills the whole process group
Every adapter SHALL start the harness in its own process group and, when `timeout_sec` elapses, SHALL kill the entire group so that no child process keeps running. A timed-out round SHALL be recorded with outcome `error` and reason `timeout`.

#### Scenario: Hung agent
- **WHEN** the harness is still running at `timeout_sec`
- **THEN** the harness and all of its children are terminated, the round is reverted, and the checkpoint reason is `timeout`

### Requirement: Environment pass-through for endpoints and keys
`research.json` `harness.env` SHALL be passed to the harness process. Values of the form `$NAME` SHALL be resolved from the runner's environment at launch, and the runner SHALL refuse to start when a referenced variable is unset, so that keys for third-party endpoints never need to be written into the repository.

#### Scenario: Third-party endpoint
- **WHEN** `harness.env` is `{"ANTHROPIC_BASE_URL": "https://example/anthropic", "ANTHROPIC_AUTH_TOKEN": "$GLM_KEY"}` and `GLM_KEY` is set
- **THEN** the harness process receives both variables with `ANTHROPIC_AUTH_TOKEN` equal to the value of `GLM_KEY`

#### Scenario: Missing key
- **WHEN** `harness.env` references `$GLM_KEY` and it is not set
- **THEN** the runner does not start a round and names `GLM_KEY`

### Requirement: Harness output is preserved per round
The harness's full stdout and stderr and the exact prompt SHALL be saved under the round's artifact directory before the outcome is decided.

#### Scenario: Harness crashed
- **WHEN** the harness exits non-zero without reporting a cut-off
- **THEN** `harness.out` and `prompt.md` exist in the round's artifact directory and the checkpoint has outcome `error` with the exit code in `harness.exit`
