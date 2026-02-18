## ADDED Requirements

### Requirement: Interactive option selection
The Skill SHALL guide the user through analysis options before running, using `AskUserQuestion`.

#### Scenario: User selects analysis scope and depth
- **WHEN** the user invokes `/session-insights` without explicit parameters
- **THEN** the Agent SHALL ask two questions: (1) analysis scope (last 5/10/20/all sessions), (2) analysis depth (summary/detailed)

#### Scenario: User provides explicit parameters
- **WHEN** the user invokes `/session-insights --last 5 --depth detailed`
- **THEN** the Agent SHALL skip the interactive guide and proceed directly

### Requirement: Data extraction via Python script
The Skill SHALL extract session data by executing the bundled Python script, which reads from `~/.claude/projects/`.

#### Scenario: Successful extraction
- **WHEN** the Agent executes `python3 ${SKILL_DIR}/scripts/session-insights.py --last N --depth summary|detailed`
- **THEN** the script SHALL output structured JSON to stdout containing `totals`, `all_tools`, `all_sub_agents`, `all_files_edited`, `sessions[]`

#### Scenario: Auto-detect project from CWD
- **WHEN** the script is invoked without explicit project argument
- **THEN** it SHALL use the current working directory to locate the corresponding project in `~/.claude/projects/`

#### Scenario: Script execution failure fallback
- **WHEN** the Python script fails (e.g., Python not available)
- **THEN** the Agent SHALL fall back to reading JSONL files directly using Glob + Read tools

### Requirement: Semantic analysis by Agent
The Agent SHALL perform semantic analysis on the extracted data, not merely reproduce it.

#### Scenario: Session theme identification
- **WHEN** processing session data
- **THEN** the Agent SHALL infer each session's theme from `user_inputs` rather than listing raw messages

#### Scenario: Development phase recognition
- **WHEN** analyzing multiple sessions
- **THEN** the Agent SHALL identify development phases (setup, development, debugging, optimization, etc.)

#### Scenario: Highlights and pain points extraction (detailed mode)
- **WHEN** depth is "detailed"
- **THEN** the Agent SHALL extract 3-5 highlights (with data support and reusable patterns) and 3-5 pain points (with impact quantification and improvement suggestions)

### Requirement: Markdown report with Mermaid charts
The Agent SHALL generate a structured Chinese Markdown report with embedded Mermaid diagrams.

#### Scenario: Summary mode report structure
- **WHEN** depth is "summary"
- **THEN** the report SHALL contain sections: project overview, development timeline (Gantt + xychart-beta), session summaries (brief), tool distribution (pie), sub-agent analysis (flowchart), file change overview

#### Scenario: Detailed mode report structure
- **WHEN** depth is "detailed"
- **THEN** the report SHALL contain all summary sections plus: per-session sequence diagrams (max 15 nodes), curated user input tables, Agent team topology, user interaction patterns, key decisions, highlights, pain points, cross-project experience summary

#### Scenario: Mermaid chart quality
- **WHEN** generating Mermaid diagrams
- **THEN** sequence diagrams SHALL use `par` blocks for parallel operations and `Note over` for phase markers; flowcharts SHALL use `style` commands for node coloring; active time comparison SHALL use `xychart-beta`

### Requirement: Timestamped output file
The report SHALL be written to a timestamped file path preserving history.

#### Scenario: Output file naming
- **WHEN** the report is generated
- **THEN** it SHALL be written to `./docs/session-insights-{project-name}-{YYYYMMDD-HHmmss}.md`

#### Scenario: Existing reports preserved
- **WHEN** generating a new report for the same project
- **THEN** previous reports SHALL NOT be overwritten due to unique timestamps

### Requirement: Security and privacy
The report SHALL not expose sensitive information from session data.

#### Scenario: No secrets in output
- **WHEN** session data contains API keys, passwords, or credentials
- **THEN** the Agent SHALL NOT include them in the generated report

#### Scenario: Output language
- **WHEN** generating the report
- **THEN** all text SHALL be in Chinese, with section numbers using Chinese numerals (一、二、三...)
