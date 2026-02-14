## ADDED Requirements

### Requirement: Follow macOS icon canvas specification
The system SHALL generate app icons conforming to the macOS icon specification: 1024x1024 canvas, 112px padding on each side, 800x800 background rectangle starting at (112, 112), corner radius rx=179 ry=179.

#### Scenario: Generated SVG dimensions
- **WHEN** Agent generates an app icon SVG
- **THEN** the SVG SHALL have `width="1024" height="1024" viewBox="0 0 1024 1024"` and a background `<rect>` at `x=112 y=112 width=800 height=800 rx=179 ry=179`

### Requirement: Provide icon style templates
The system SHALL provide at least 2 icon style templates for MVP. Each template SHALL be a complete SVG with parameterizable elements (colors, text, shapes).

#### Scenario: Gradient + letter template (Template A)
- **WHEN** user selects "gradient letter" style
- **THEN** the system SHALL generate an icon with a diagonal linear gradient background and the app's initial letter in white bold strokes, centered in the safe area

#### Scenario: Solid + geometric template (Template B)
- **WHEN** user selects "solid geometric" style
- **THEN** the system SHALL generate an icon with a solid brand color background and a centered geometric shape (circle, hexagon, or triangle) in white strokes

### Requirement: Support brand color customization
The system SHALL accept brand colors from the user or extract them from the project's CSS/Tailwind configuration, and apply them to the icon template.

#### Scenario: User-specified brand colors
- **WHEN** user provides primary and secondary colors (e.g., `#334155` and `#0D9488`)
- **THEN** the icon template SHALL use these colors for gradient stops or background fill

#### Scenario: Auto-extracted colors from Tailwind
- **WHEN** project contains `tailwind.config.*` with custom color definitions and user does not specify colors
- **THEN** the system SHALL extract the primary color from the Tailwind config and suggest it to the user for confirmation

### Requirement: Convert SVG to ICNS via script
The system SHALL provide a `scripts/svg-to-icns.sh` script that converts an SVG file to a macOS `.icns` file through the multi-size PNG iconset pipeline.

#### Scenario: Successful SVG to ICNS conversion
- **WHEN** user runs `svg-to-icns.sh appicon.svg`
- **THEN** the script SHALL generate an `.iconset` directory containing all required sizes (16, 32, 128, 256, 512 at 1x and 2x), then run `iconutil --convert icns` to produce the final `.icns` file

#### Scenario: Fallback rendering tool
- **WHEN** `rsvg-convert` is not available on the system
- **THEN** the script SHALL fall back to macOS built-in `sips` for PNG conversion and log a warning about potential quality differences

#### Scenario: Missing required tools
- **WHEN** neither `rsvg-convert` nor `sips` is available
- **THEN** the script SHALL exit with code 1 and print an error message listing the required tools
