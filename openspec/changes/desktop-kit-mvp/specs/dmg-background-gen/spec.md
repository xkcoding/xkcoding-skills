## ADDED Requirements

### Requirement: Align with create-dmg coordinate system
The system SHALL generate DMG background images that precisely align with create-dmg parameters. The canvas MUST be 600x400 pixels. App icon drop zone MUST be centered at (150, 185). Applications folder drop zone MUST be centered at (450, 185). Icon size MUST be 72px.

#### Scenario: Drop zone coordinate alignment
- **WHEN** Agent generates a DMG background SVG
- **THEN** the SVG SHALL have `width="600" height="400"`, and the two drop zone reserved areas SHALL be positioned at centers (150, 185) and (450, 185) respectively, with 80x72 clear areas for icon placement

#### Scenario: create-dmg command generation
- **WHEN** Agent generates the build script referencing the DMG background
- **THEN** the create-dmg command SHALL use `--window-size 600 400`, `--icon-size 72`, `--icon "AppName.app" 150 185`, and `--app-drop-link 450 185`

### Requirement: Drop zone positions are immutable
The system SHALL NOT allow modification of drop zone positions in any template. Agent MAY modify decorative elements (colors, text, ornaments) but MUST NOT change the drop zone coordinates.

#### Scenario: Template customization preserves drop zones
- **WHEN** Agent customizes a DMG background template with user-specified colors and text
- **THEN** the drop zone reserved areas at (150, 185) and (450, 185) SHALL remain unchanged

### Requirement: Provide DMG background templates
The system SHALL provide at least 1 DMG background template for MVP. Each template SHALL include decorative elements, drop zone reservations, and installation guide text.

#### Scenario: Simple arrow template
- **WHEN** user selects a DMG background template
- **THEN** the generated SVG SHALL contain a background gradient or solid color, visual indicator (arrow) between the two drop zones, app name text, and bottom installation instructions

### Requirement: Include ad-hoc signing installation guide
The system SHALL include installation guide text in every DMG background for ad-hoc signed applications. The text MUST explain the right-click → Open workflow required for first launch.

#### Scenario: Installation guide text present
- **WHEN** a DMG background is generated
- **THEN** the bottom area of the background SHALL contain text explaining: "首次打开：右键点击 [AppName] → 选择「打开」→ 弹窗点「打开」" and "仅第一次需要，之后正常双击即可"

### Requirement: Provide SVG to PNG rendering pipeline
The system SHALL provide an HTML wrapper template for SVG rendering and document the conversion process from SVG → HTML → PNG.

#### Scenario: HTML wrapper generation
- **WHEN** Agent generates a DMG background
- **THEN** the system SHALL also generate a `background.html` file that wraps the SVG content with proper CSS (margin:0, PingFang SC font, -webkit-font-smoothing) for browser-based PNG rendering

#### Scenario: 2x resolution output
- **WHEN** the SVG is rendered to PNG
- **THEN** the output PNG SHALL be rendered at 2x resolution (1200x800 pixels) for Retina display quality
