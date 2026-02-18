## ADDED Requirements

### Requirement: Skill directory structure
The Skill SHALL follow the xkcoding-skills directory convention with the following structure:

```
session-insights/
├── SKILL.md
├── README.md
└── scripts/
    └── session-insights.py
```

#### Scenario: Directory structure is complete
- **WHEN** the skill is installed to `~/.claude/skills/session-insights/`
- **THEN** all three files (`SKILL.md`, `README.md`, `scripts/session-insights.py`) SHALL exist

### Requirement: SKILL.md frontmatter format
The SKILL.md SHALL contain YAML frontmatter with exactly two fields: `name` and `description`.

#### Scenario: Valid frontmatter
- **WHEN** Claude Code parses the SKILL.md
- **THEN** the frontmatter SHALL contain `name: session-insights` and an English-language `description` summarizing the skill's purpose

#### Scenario: No extra frontmatter fields
- **WHEN** comparing to the original commands format
- **THEN** fields `category`, `complexity`, `mcp-servers`, `personas` SHALL NOT be present

### Requirement: Script path reference via SKILL_DIR
The SKILL.md SHALL use the `${SKILL_DIR}` placeholder pattern for all script references, following baoyu-skills convention.

#### Scenario: Script Directory section present
- **WHEN** Agent reads the SKILL.md
- **THEN** a "Script Directory" section SHALL exist with instructions to: (1) determine SKILL.md directory path as `SKILL_DIR`, (2) resolve script path as `${SKILL_DIR}/scripts/<script-name>`, (3) replace all `${SKILL_DIR}` references with actual path

#### Scenario: Script invocation uses placeholder
- **WHEN** the SKILL.md contains a script invocation command
- **THEN** it SHALL use `python3 ${SKILL_DIR}/scripts/session-insights.py` instead of any hardcoded path

### Requirement: Marketplace registration
The Skill SHALL be registered in `.claude-plugin/marketplace.json`.

#### Scenario: Marketplace entry added
- **WHEN** reading `.claude-plugin/marketplace.json`
- **THEN** the `skills` array SHALL contain `"./session-insights"`

### Requirement: Repository README update
The repository `README.md` SHALL list the new skill in the Skills table and update the directory structure.

#### Scenario: Skills table includes session-insights
- **WHEN** reading the repository `README.md`
- **THEN** the Skills table SHALL contain a row for `session-insights` with description and status

#### Scenario: Directory structure shows session-insights
- **WHEN** reading the repository structure section
- **THEN** the `session-insights/` directory SHALL be listed alongside `desktop-kit/`
