## ADDED Requirements

### Requirement: Detect frontend framework
The system SHALL identify the frontend framework used in the target project by inspecting `package.json` dependencies and directory structure. Supported frameworks: React, Vue, Svelte, static HTML. The detection result SHALL include the framework name and confidence level.

#### Scenario: React project detected
- **WHEN** `package.json` contains `react` or `react-dom` in dependencies
- **THEN** detection result SHALL report `framework: "react"` with `confidence: "high"`

#### Scenario: Vue project detected
- **WHEN** `package.json` contains `vue` in dependencies
- **THEN** detection result SHALL report `framework: "vue"` with `confidence: "high"`

#### Scenario: Svelte project detected
- **WHEN** `package.json` contains `svelte` in dependencies
- **THEN** detection result SHALL report `framework: "svelte"` with `confidence: "high"`

#### Scenario: Static HTML project detected
- **WHEN** no frontend framework dependency is found but `index.html` exists in the project root or a `public/` directory
- **THEN** detection result SHALL report `framework: "static"` with `confidence: "medium"`

#### Scenario: Unknown framework
- **WHEN** no recognized framework or static HTML is detected
- **THEN** detection result SHALL report `framework: "unknown"` with `confidence: "low"` and list the top-level dependencies found

### Requirement: Detect build tool
The system SHALL identify the build tool used in the target project. Supported build tools: Vite, Webpack, None.

#### Scenario: Vite detected
- **WHEN** `package.json` contains `vite` in devDependencies or a `vite.config.*` file exists
- **THEN** detection result SHALL report `buildTool: "vite"`

#### Scenario: Webpack detected
- **WHEN** `package.json` contains `webpack` in devDependencies or a `webpack.config.*` file exists
- **THEN** detection result SHALL report `buildTool: "webpack"`

#### Scenario: No build tool detected
- **WHEN** neither Vite nor Webpack is detected
- **THEN** detection result SHALL report `buildTool: "none"`

### Requirement: Detect API call patterns
The system SHALL scan the project source code for API call patterns to determine if an API proxy is needed. The system SHALL detect base URL configurations and API path prefixes.

#### Scenario: Fetch/axios with base URL detected
- **WHEN** source files contain `fetch("/api/` or axios `baseURL` configuration pointing to a relative `/api/` path
- **THEN** detection result SHALL report `apiProxy: true` with the detected `apiPrefix` (e.g., `"/api/"`)

#### Scenario: Environment variable API URL detected
- **WHEN** `.env` or `.env.production` files contain `VITE_API_BASE` or similar API URL environment variables
- **THEN** detection result SHALL report `apiProxy: true` and include the environment variable name and value

#### Scenario: No API calls detected
- **WHEN** no API call patterns or base URL configurations are found
- **THEN** detection result SHALL report `apiProxy: false`

### Requirement: Output detection results as JSON
The system SHALL output all detection results as a single JSON object to stdout, suitable for Agent parsing.

#### Scenario: Complete detection output
- **WHEN** detection script completes successfully
- **THEN** output SHALL be a valid JSON object containing `framework`, `buildTool`, `apiProxy`, `appName` (from `package.json` name field), and `appVersion` (from `package.json` version field)

#### Scenario: Missing package.json
- **WHEN** no `package.json` exists in the target directory
- **THEN** the script SHALL exit with code 1 and output a JSON error object with `error: "no package.json found"`
