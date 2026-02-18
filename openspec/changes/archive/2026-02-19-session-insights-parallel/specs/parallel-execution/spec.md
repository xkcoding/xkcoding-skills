## ADDED Requirements

### Requirement: Parallel threshold trigger
The Agent SHALL switch to parallel execution mode when both conditions are met: session count > 10 AND depth is "detailed". Otherwise the Agent SHALL use the existing serial execution.

#### Scenario: Threshold met
- **WHEN** the extracted JSON contains 15 sessions and depth is "detailed"
- **THEN** the Agent SHALL enter parallel execution mode for chapter three (各会话详情)

#### Scenario: Threshold not met — few sessions
- **WHEN** the extracted JSON contains 8 sessions and depth is "detailed"
- **THEN** the Agent SHALL use serial execution (existing behavior unchanged)

#### Scenario: Threshold not met — summary mode
- **WHEN** the extracted JSON contains 20 sessions and depth is "summary"
- **THEN** the Agent SHALL use serial execution (summary mode is always serial)

### Requirement: Session batching
In parallel mode, the Agent SHALL split sessions into batches of 5 and delegate each batch to a Sub-Agent via the Task tool.

#### Scenario: Even split
- **WHEN** there are 20 sessions to analyze
- **THEN** the Agent SHALL create 4 Sub-Agent tasks, each receiving 5 sessions

#### Scenario: Uneven split
- **WHEN** there are 13 sessions to analyze
- **THEN** the Agent SHALL create 3 Sub-Agent tasks: two with 5 sessions and one with 3 sessions

### Requirement: Sub-Agent delegation protocol
Each Sub-Agent SHALL receive the JSON data for its batch of sessions plus the chapter three format requirements, and SHALL return Markdown fragments for those sessions.

#### Scenario: Sub-Agent input
- **WHEN** a Sub-Agent is launched for sessions 6-10
- **THEN** its prompt SHALL contain: (1) the JSON data for sessions 6-10 only, (2) the detailed mode format specification (theme, sequence diagram, stats, curated inputs table, team topology), (3) instruction to return Markdown fragments without chapter heading

#### Scenario: Sub-Agent output
- **WHEN** a Sub-Agent completes analysis of its batch
- **THEN** it SHALL return Markdown containing each session's detailed analysis in chronological order

### Requirement: Parallel Sub-Agent launch
All batch Sub-Agents SHALL be launched in parallel (single message with multiple Task tool calls), not sequentially.

#### Scenario: Concurrent launch
- **WHEN** 4 batches are ready for analysis
- **THEN** the Agent SHALL issue 4 Task tool calls in a single response so they run concurrently

### Requirement: Result merging
The Main Agent SHALL collect all Sub-Agent results and merge them into the final report in session chronological order.

#### Scenario: Successful merge
- **WHEN** all 4 Sub-Agents return their Markdown fragments
- **THEN** the Main Agent SHALL assemble chapter three by concatenating fragments in session time order

#### Scenario: Sub-Agent failure fallback
- **WHEN** a Sub-Agent fails or returns empty/invalid output
- **THEN** the Main Agent SHALL generate a simplified summary (2-3 lines per session) for the missing batch sessions, and note the fallback in the report

### Requirement: Report assembly order
In parallel mode, the Main Agent SHALL generate chapters in this order: (1) data extraction, (2) launch parallel Sub-Agents for chapter three, (3) while waiting, generate data-aggregation chapters (four, five, six), (4) collect Sub-Agent results, (5) generate global chapters (one, two, seven through eleven) that require cross-session analysis.

#### Scenario: Execution order
- **WHEN** parallel mode is active
- **THEN** the Main Agent SHALL generate chapters four/five/six before collecting Sub-Agent results, and generate chapters one/two/seven-eleven after collecting all results
