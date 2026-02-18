## ADDED Requirements

### Requirement: Delayed decision point
When parallel threshold is met and `--background`/`--bg` is NOT specified, the Agent SHALL ask the user to choose between foreground and background execution AFTER Step 1 (script execution) completes and BEFORE Step 2 (semantic analysis) begins.

#### Scenario: Decision point shown
- **WHEN** session count is 15, depth is "detailed", and no `--background` flag
- **THEN** the Agent SHALL use AskUserQuestion with: (1) header "执行方式", (2) option "前台执行（可以看实时进度）(Recommended)", (3) option "后台执行（你可以继续其他工作）", and display detected session count and estimated time

#### Scenario: Decision point not shown — below threshold
- **WHEN** session count is 8 and depth is "detailed"
- **THEN** the Agent SHALL NOT show the decision point and proceed with foreground execution

#### Scenario: Decision point not shown — summary mode
- **WHEN** session count is 20 and depth is "summary"
- **THEN** the Agent SHALL NOT show the decision point and proceed with foreground execution

### Requirement: Background parameter
The Agent SHALL recognize `--background` and `--bg` in the user's invocation arguments. When present, the Agent SHALL skip the decision point and execute in background mode directly.

#### Scenario: Explicit background flag
- **WHEN** user invokes `/session-insights --last 20 --depth detailed --background`
- **THEN** the Agent SHALL skip the foreground/background question and immediately launch background execution

#### Scenario: Short form flag
- **WHEN** user invokes `/session-insights --last 20 --depth detailed --bg`
- **THEN** the behavior SHALL be identical to `--background`

#### Scenario: Background flag below threshold
- **WHEN** user invokes `/session-insights --last 5 --depth summary --background`
- **THEN** the Agent SHALL still run in background mode (user explicitly requested it, even if workload is small)

### Requirement: Background execution via Task tool
When background mode is selected, the Agent SHALL wrap the entire analysis (Step 2 through Step 4) in a single Task tool call with `run_in_background: true`.

#### Scenario: Background launch
- **WHEN** background mode is selected (via user choice or `--background` flag)
- **THEN** the Agent SHALL launch a Task with `run_in_background: true` containing all analysis and report generation work, and immediately inform the user with the expected output file path

#### Scenario: Foreground with parallel
- **WHEN** foreground mode is selected at the decision point
- **THEN** the Agent SHALL proceed with parallel Sub-Agent execution in the foreground, showing progress as each batch completes

### Requirement: Progress feedback
In foreground parallel mode, the Main Agent SHALL report progress as each Sub-Agent batch completes.

#### Scenario: Batch completion message
- **WHEN** Sub-Agent for batch 2/4 (sessions 6-10) completes
- **THEN** the Main Agent SHALL display a progress message like "✓ 批次 2/4 完成（会话 6-10）"

#### Scenario: All batches complete
- **WHEN** all Sub-Agent batches have completed
- **THEN** the Main Agent SHALL display "✓ 所有批次分析完成，正在生成全局章节..." before proceeding to cross-session analysis

### Requirement: Background completion notification
When background execution completes, the background Task agent SHALL write the report file and its completion message SHALL be visible when the user checks the task output.

#### Scenario: Background task done
- **WHEN** the background Task completes successfully
- **THEN** the report SHALL be written to `./docs/session-insights-{project-name}-{YYYYMMDD-HHmmss}.md` and the task output SHALL include the file path and a completion summary
